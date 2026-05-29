"""knowledge-os-mcp: FastAPI + FastMCP server with bearer auth and OAuth 2.0 PKCE.

Startup sequence:
  1. load_dotenv() — read .env into os.environ
  2. Read VAULT_PATH, VAULT_SECRET, OAUTH_CLIENT_ID, OAUTH_REDIRECT_URI from env (fail-fast)
  3. Read CLAUDE.md from vault root → inject as FastMCP `instructions` (INFRA-05)
  4. Build BearerAuthMiddleware (single auth enforcement point, INFRA-02)
  5. Mount MCP streamable-HTTP transport at /mcp (INFRA-01, D-05)
  6. Register /authorize and /token OAuth 2.0 PKCE endpoints (D-16)

Transport: streamable-HTTP via mcp.http_app(path='/mcp', transport='streamable-http')
Auth: Bearer token (VAULT_SECRET env var) + OAuth 2.0 PKCE wrapper for claude.ai mobile
CLAUDE.md: read at startup, not on every request (performance + resilience)
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

# ---------------------------------------------------------------------------
# 1. Load environment
# ---------------------------------------------------------------------------

load_dotenv()

# Fail-fast on missing env vars — a misconfigured server must not start silently.
VAULT_PATH: Path = Path(os.environ["VAULT_PATH"])
VAULT_SECRET: str = os.environ["VAULT_SECRET"]
OAUTH_CLIENT_ID: str = os.environ["OAUTH_CLIENT_ID"]
OAUTH_REDIRECT_URI: str = os.environ["OAUTH_REDIRECT_URI"]

# ---------------------------------------------------------------------------
# 2. Read CLAUDE.md operational rules → MCP instructions (INFRA-05, D-07)
# ---------------------------------------------------------------------------

_claude_md: Path = VAULT_PATH / "CLAUDE.md"
_instructions_text: str = (
    _claude_md.read_text(encoding="utf-8") if _claude_md.exists() else ""
)

# Initialize the MCP server with vault instructions so Claude receives the
# operational rules on every connection.
mcp: FastMCP = FastMCP("vault-mcp", instructions=_instructions_text)

# ---------------------------------------------------------------------------
# 3. Error dict builder — public surface used by Plans 04-07 (D-08)
# ---------------------------------------------------------------------------

ERR_NOT_FOUND: str = "NOT_FOUND"
ERR_ALREADY_EXISTS: str = "ALREADY_EXISTS"
ERR_INVALID_PATH: str = "INVALID_PATH"
ERR_HEADING_NOT_FOUND: str = "HEADING_NOT_FOUND"
ERR_AUTH: str = "AUTH_ERROR"


def err(message: str, code: str) -> dict:
    """Return the canonical error dict shape used by all tool functions.

    Shape: {"error": True, "message": str, "code": str}
    Code values: ERR_NOT_FOUND, ERR_ALREADY_EXISTS, ERR_INVALID_PATH,
                 ERR_HEADING_NOT_FOUND, ERR_AUTH
    """
    return {"error": True, "message": message, "code": code}


# ---------------------------------------------------------------------------
# 4. Path validation helper — used by every tool that accepts a path param
#    (CONTEXT.md decision 5, T-03-05, T-03-06)
# ---------------------------------------------------------------------------


def safe_vault_path(rel: str) -> Path | dict:
    """Validate and resolve a relative vault path.

    Returns a resolved pathlib.Path if the path is safe, or an error dict
    with code INVALID_PATH if:
      - rel is empty or None
      - rel is an absolute path (starts with /)
      - the first path component is 'raw' (raw/ is immutable per CLAUDE.md)
      - the resolved path escapes VAULT_PATH (path traversal)

    Args:
        rel: A relative path string intended to be inside VAULT_PATH.

    Returns:
        Resolved Path on success, or {"error": True, "message": ..., "code": "INVALID_PATH"}.
    """
    # Reject empty or None
    if not rel:
        return err("Path must not be empty", ERR_INVALID_PATH)

    # Reject absolute paths — callers must supply relative paths only
    if rel.startswith("/"):
        return err(f"Absolute paths are not allowed: {rel}", ERR_INVALID_PATH)

    # Reject raw/ directory — immutable vault archive
    # Check the first component of the path (handles raw/, raw\, etc.)
    first_component = Path(rel).parts[0] if Path(rel).parts else ""
    if first_component == "raw":
        return err(f"raw/ is immutable: {rel}", ERR_INVALID_PATH)

    # Resolve and check containment — protects against ../../ traversal
    candidate = (VAULT_PATH / rel).resolve()
    vault_resolved = VAULT_PATH.resolve()
    if not candidate.is_relative_to(vault_resolved):
        return err(f"Path outside vault: {rel}", ERR_INVALID_PATH)

    return candidate


# ---------------------------------------------------------------------------
# 5. OAuth bypass paths — shared source of truth for middleware + routes (D-16)
# ---------------------------------------------------------------------------

OAUTH_BYPASS_PATHS: set[str] = {"/authorize", "/token"}

# ---------------------------------------------------------------------------
# 6. Bearer auth middleware (INFRA-02, D-06, T-03-01, T-03-07)
# ---------------------------------------------------------------------------


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Enforce VAULT_SECRET bearer token on all routes except OAuth endpoints.

    OAuth endpoints (/authorize, /token) are the auth flow itself — auth is
    established by completing the PKCE handshake, so they must not be gated.

    Security note (T-03-07): The Authorization header value is never logged.
    """

    async def dispatch(self, request: Request, call_next):
        # OAuth endpoints bypass auth — they ARE the auth flow
        if request.url.path in OAUTH_BYPASS_PATHS:
            return await call_next(request)

        auth_header: str = request.headers.get("Authorization", "")

        # Reject missing or malformed Authorization header
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content=err("Unauthorized", ERR_AUTH),
            )

        # Reject wrong token — constant-time comparison is not required here
        # because VAULT_SECRET is a shared secret on a personal single-user system,
        # but we still avoid logging the value (T-03-07).
        token = auth_header[len("Bearer "):]
        if token != VAULT_SECRET:
            return JSONResponse(
                status_code=401,
                content=err("Unauthorized", ERR_AUTH),
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# 7. MCP ASGI app — streamable-HTTP transport (INFRA-01, D-05)
#    ONLY the documented form is used: mcp.http_app(path, transport)
#    No speculative API names, no try/except fallback chains.
# ---------------------------------------------------------------------------

mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")

# ---------------------------------------------------------------------------
# 8. FastAPI application — lifespan must come from mcp_app (RESEARCH Pitfall 2)
# ---------------------------------------------------------------------------

app: FastAPI = FastAPI(lifespan=mcp_app.lifespan)

# Middleware is added BEFORE routes and mount so it applies to all requests.
app.add_middleware(BearerAuthMiddleware)

# ---------------------------------------------------------------------------
# OAUTH ENDPOINTS — see Task 2
# ---------------------------------------------------------------------------

# In-memory store for PKCE authorization codes (single-user, single-process).
# Acceptable per CONTEXT.md D-16 / RESEARCH Assumption A8.
# T-03-09: unbounded growth is accepted as a v1 tradeoff (single-user system).
_pkce_codes: dict[str, dict] = {}


@app.get("/authorize")
async def authorize(request: Request) -> RedirectResponse | JSONResponse:
    """OAuth 2.0 Authorization Code endpoint with PKCE (RFC 7636).

    Validates client_id, redirect_uri, and PKCE S256 challenge, then issues a
    single-use authorization code as a 302 redirect to the registered callback.
    """
    params = request.query_params

    # Validate response_type
    if params.get("response_type") != "code":
        return JSONResponse(
            status_code=400,
            content=err("response_type must be 'code'", ERR_AUTH),
        )

    # Validate client_id (T-03-02)
    if params.get("client_id") != OAUTH_CLIENT_ID:
        return JSONResponse(
            status_code=400,
            content=err("invalid client_id", ERR_AUTH),
        )

    # Validate redirect_uri — must match registered value exactly
    if params.get("redirect_uri") != OAUTH_REDIRECT_URI:
        return JSONResponse(
            status_code=400,
            content=err("invalid redirect_uri", ERR_AUTH),
        )

    # PKCE is required — only S256 is accepted (RFC 7636)
    code_challenge = params.get("code_challenge", "")
    code_challenge_method = params.get("code_challenge_method", "")
    if not code_challenge:
        return JSONResponse(
            status_code=400,
            content=err("code_challenge is required", ERR_AUTH),
        )
    if code_challenge_method != "S256":
        return JSONResponse(
            status_code=400,
            content=err("code_challenge_method must be S256", ERR_AUTH),
        )

    # Issue a cryptographically-random single-use authorization code
    code = secrets.token_urlsafe(32)
    _pkce_codes[code] = {
        "challenge": code_challenge,
        "client_id": params["client_id"],
        "redirect_uri": params["redirect_uri"],
        "used": False,
        "issued_at": time.time(),
    }

    state = params.get("state", "")
    redirect_url = f"{params['redirect_uri']}?code={code}&state={state}"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    code_verifier: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
) -> JSONResponse:
    """OAuth 2.0 Token endpoint — exchanges PKCE-verified code for access token.

    Access token is VAULT_SECRET (the single shared secret for this system).
    Per CONTEXT.md D-16: the OAuth wrapper is thin; the access token equals
    VAULT_SECRET so both claude.ai mobile (OAuth) and Claude Desktop (direct
    bearer) use the same credential.
    """
    # Validate grant type
    if grant_type != "authorization_code":
        return JSONResponse(
            status_code=400,
            content=err("invalid grant_type", ERR_AUTH),
        )

    # Validate code exists and has not been used (T-03-03)
    if code not in _pkce_codes:
        return JSONResponse(
            status_code=400,
            content=err("invalid or unknown code", ERR_AUTH),
        )

    entry = _pkce_codes[code]

    if entry["used"]:
        return JSONResponse(
            status_code=400,
            content=err("code has already been used", ERR_AUTH),
        )

    if entry["client_id"] != client_id:
        return JSONResponse(
            status_code=400,
            content=err("client_id mismatch", ERR_AUTH),
        )

    if entry["redirect_uri"] != redirect_uri:
        return JSONResponse(
            status_code=400,
            content=err("redirect_uri mismatch", ERR_AUTH),
        )

    # PKCE S256 verification (T-03-04): sha256(verifier) base64url == stored challenge
    expected_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    if expected_challenge != entry["challenge"]:
        return JSONResponse(
            status_code=400,
            content=err("PKCE verification failed", ERR_AUTH),
        )

    # Mark code as used — single-use enforcement (T-03-03)
    entry["used"] = True

    # Return access_token = VAULT_SECRET per D-16
    return JSONResponse(
        status_code=200,
        content={
            "access_token": VAULT_SECRET,
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )


# ---------------------------------------------------------------------------
# 9. Mount MCP streamable-HTTP transport (after routes, after middleware)
# ---------------------------------------------------------------------------

app.mount("/mcp", mcp_app)
