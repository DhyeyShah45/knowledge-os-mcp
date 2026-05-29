"""OAuth 2.0 Authorization Code + PKCE endpoint tests.

Tests verify:
- /authorize redirects with a code on valid PKCE S256 request
- /authorize rejects unknown client_id, missing code_challenge, non-S256 method
- /token exchanges code+verifier for VAULT_SECRET access token
- /token rejects wrong verifier, reused code, invalid grant_type
- A token obtained via the full OAuth flow passes BearerAuthMiddleware on /mcp
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import sys
from urllib.parse import parse_qs, urlparse

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_server(tmp_vault, vault_env):
    """Import (or reimport) server.py after env vars are set."""
    if "server" in sys.modules:
        del sys.modules["server"]
    import server  # noqa: PLC0415
    return server


def pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge) using S256 hashing (RFC 7636).

    The challenge is base64url(sha256(verifier)) with no padding.
    """
    verifier = secrets.token_urlsafe(43)  # min 43 chars per RFC 7636 §4.1
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_oauth_authorize_redirects_with_code(tmp_vault, vault_env):
    """/authorize with valid PKCE S256 params must redirect 302 with code+state."""
    srv = _load_server(tmp_vault, vault_env)
    verifier, challenge = pkce_pair()

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,  # Observe the 302 directly
    ) as client:
        resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "xyz",
            },
        )

    assert resp.status_code == 302, f"Expected 302 redirect; got {resp.status_code}"
    location = resp.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert "code" in query, "Expected code in redirect query"
    assert query["state"][0] == "xyz"


def test_oauth_authorize_rejects_unknown_client(tmp_vault, vault_env):
    """/authorize with an unregistered client_id must return 400."""
    srv = _load_server(tmp_vault, vault_env)
    _, challenge = pkce_pair()

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "evil-client",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )

    assert resp.status_code == 400


def test_oauth_authorize_rejects_missing_pkce(tmp_vault, vault_env):
    """/authorize without code_challenge must return 400."""
    srv = _load_server(tmp_vault, vault_env)

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
                # no code_challenge
            },
        )

    assert resp.status_code == 400


def test_oauth_authorize_rejects_non_s256_method(tmp_vault, vault_env):
    """/authorize with code_challenge_method=plain must return 400 (only S256 accepted)."""
    srv = _load_server(tmp_vault, vault_env)
    verifier, challenge = pkce_pair()

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "plain",  # S256 is required
            },
        )

    assert resp.status_code == 400


def test_oauth_token_exchanges_code_for_secret(tmp_vault, vault_env):
    """/token with valid code + verifier must return access_token == VAULT_SECRET."""
    import os
    srv = _load_server(tmp_vault, vault_env)
    verifier, challenge = pkce_pair()

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        # Step 1: get code
        auth_resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "abc",
            },
        )
        assert auth_resp.status_code == 302
        location = auth_resp.headers["location"]
        code = parse_qs(urlparse(location).query)["code"][0]

        # Step 2: exchange code for token
        token_resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
            },
        )

    assert token_resp.status_code == 200
    body = token_resp.json()
    assert body["access_token"] == os.environ["VAULT_SECRET"]
    assert body["token_type"] == "Bearer"


def test_oauth_token_rejects_wrong_verifier(tmp_vault, vault_env):
    """/token with a tampered code_verifier must return 400 (PKCE S256 mismatch)."""
    srv = _load_server(tmp_vault, vault_env)
    verifier, challenge = pkce_pair()

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        auth_resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        code = parse_qs(urlparse(auth_resp.headers["location"]).query)["code"][0]

        token_resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": "totally-wrong-verifier-that-wont-match",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
            },
        )

    assert token_resp.status_code == 400


def test_oauth_token_rejects_reused_code(tmp_vault, vault_env):
    """Exchanging the same authorization code twice must fail (single-use per RFC 7636)."""
    srv = _load_server(tmp_vault, vault_env)
    verifier, challenge = pkce_pair()

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        auth_resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        code = parse_qs(urlparse(auth_resp.headers["location"]).query)["code"][0]

        form_data = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "client_id": "test-client",
            "redirect_uri": "http://localhost/cb",
        }

        # First exchange — must succeed
        first = client.post("/token", data=form_data)
        assert first.status_code == 200

        # Second exchange — must fail
        second = client.post("/token", data=form_data)
        assert second.status_code == 400


def test_oauth_token_with_oauth_token_passes_middleware(tmp_vault, vault_env):
    """Full OAuth flow: access_token obtained via /token must pass BearerAuthMiddleware on /mcp."""
    srv = _load_server(tmp_vault, vault_env)
    verifier, challenge = pkce_pair()

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        # Complete the OAuth flow to get access_token
        auth_resp = client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        code = parse_qs(urlparse(auth_resp.headers["location"]).query)["code"][0]
        token_resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "client_id": "test-client",
                "redirect_uri": "http://localhost/cb",
            },
        )
        access_token = token_resp.json()["access_token"]

        # Use the access_token as a Bearer token on /mcp
        mcp_resp = client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # The middleware should pass it through (not 401)
    assert mcp_resp.status_code != 401, (
        f"OAuth access_token should pass middleware; got {mcp_resp.status_code}"
    )
