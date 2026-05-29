"""Bearer auth middleware tests for the knowledge-os-mcp server.

Tests verify that BearerAuthMiddleware:
- Rejects requests with no Authorization header (returns 401 with AUTH_ERROR code)
- Rejects requests with wrong bearer token (returns 401 with AUTH_ERROR code)
- Passes requests with the correct bearer token through to the next handler

Security note (T-03-01): Every /mcp/* request must pass through the bearer auth check.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_server(tmp_vault, vault_env):
    """Import (or reimport) server.py after env vars are set via vault_env."""
    # Remove stale module if already imported so env changes are picked up.
    if "server" in sys.modules:
        del sys.modules["server"]
    import server  # noqa: PLC0415  (module import not at top level — intentional)
    return server


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_bearer_auth_missing_returns_401(tmp_vault, vault_env):
    """POST /mcp with no Authorization header must return 401 AUTH_ERROR."""
    srv = _load_server(tmp_vault, vault_env)

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
    ) as client:
        resp = client.post("/mcp")

    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] is True
    assert body["code"] == "AUTH_ERROR"


def test_bearer_auth_wrong_token_returns_401(tmp_vault, vault_env):
    """POST /mcp with wrong bearer token must return 401 AUTH_ERROR."""
    srv = _load_server(tmp_vault, vault_env)

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        headers={"Authorization": "Bearer wrong-token"},
    ) as client:
        resp = client.post("/mcp")

    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] is True
    assert body["code"] == "AUTH_ERROR"


def test_bearer_auth_correct_token_passes_middleware(tmp_vault, vault_env):
    """POST /mcp with the correct bearer token must NOT return 401.

    The middleware passes the request through — the response status may be
    400/404/405/422 from the MCP layer (it requires a valid MCP handshake),
    but the key property is that the middleware does not reject it with 401.
    """
    srv = _load_server(tmp_vault, vault_env)

    with httpx.Client(
        transport=httpx.ASGITransport(app=srv.app),
        base_url="http://test",
        headers={"Authorization": "Bearer test-secret-token"},
    ) as client:
        resp = client.post("/mcp")

    assert resp.status_code != 401, (
        f"Middleware should pass correct token through; got {resp.status_code}"
    )
