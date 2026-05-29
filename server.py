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
import re
import secrets
import time
from datetime import date
from pathlib import Path

import frontmatter

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
# 9. Navigation MCP tools (NAV-01..NAV-04)
#    All tools return plain dicts — FastMCP serializes them as MCP tool results.
#    All tools catch I/O errors and return the canonical error dict (D-08).
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_folders() -> dict:
    """NAV-01: Return every folder under wiki/ with its direct-child note count.

    Walks the wiki/ subdirectory of VAULT_PATH.  For each directory (including
    wiki/ itself), counts direct-child *.md files (non-recursive).  Hidden
    directories (names starting with '.') are skipped.

    Returns:
        {"folders": [{"path": "wiki/entities", "note_count": 12}, ...]}
        sorted by path, or {"folders": []} if wiki/ does not exist.
    """
    wiki_dir: Path = VAULT_PATH / "wiki"
    if not wiki_dir.exists():
        return {"folders": []}

    folders: list[dict] = []
    try:
        for dirpath, dirnames, filenames in os.walk(wiki_dir):
            # Skip hidden directories in-place so os.walk prunes them too
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            current = Path(dirpath)
            note_count = sum(1 for f in filenames if f.endswith(".md"))
            rel = current.relative_to(VAULT_PATH).as_posix()
            folders.append({"path": rel, "note_count": note_count})
    except (FileNotFoundError, PermissionError) as exc:
        return err(f"Cannot read wiki directory: {exc}", ERR_NOT_FOUND)

    folders.sort(key=lambda x: x["path"])
    return {"folders": folders}


@mcp.tool()
async def list_notes(folder: str = None) -> dict:
    """NAV-02: List direct-child *.md files in a vault folder.

    Args:
        folder: Relative path inside the vault (e.g. "wiki/entities").
                Defaults to "wiki" when None or omitted.

    Returns:
        {"notes": [{"path": "wiki/entities/karpathy.md",
                    "title": "Andrej Karpathy",
                    "last_modified": "2026-05-29"}, ...]}
        sorted by path.  Returns an error dict on invalid or missing folder.
    """
    if folder is None:
        folder = "wiki"

    result = safe_vault_path(folder)
    if isinstance(result, dict):
        return result

    resolved: Path = result

    if not resolved.is_dir():
        return err(f"Not a directory: {folder}", ERR_NOT_FOUND)

    notes: list[dict] = []
    try:
        for p in sorted(resolved.glob("*.md")):
            try:
                post = frontmatter.load(str(p))
                title: str = post.get("title") or p.stem
            except Exception:
                title = p.stem

            try:
                last_modified: str = date.fromtimestamp(p.stat().st_mtime).isoformat()
            except (OSError, OverflowError, ValueError):
                last_modified = ""

            rel_path = p.relative_to(VAULT_PATH).as_posix()
            notes.append({"path": rel_path, "title": title, "last_modified": last_modified})
    except (FileNotFoundError, PermissionError) as exc:
        return err(f"Cannot list notes in {folder}: {exc}", ERR_NOT_FOUND)

    return {"notes": notes}


@mcp.tool()
async def get_note_metadata(path: str) -> dict:
    """NAV-03: Return frontmatter fields and stats for a note — no body content.

    Validates the path, loads the note with python-frontmatter, and returns
    structured metadata so Claude can decide whether to read the full note
    without paying the token cost of fetching the body.

    Args:
        path: Relative vault path to a *.md file (e.g. "wiki/concepts/AI.md").

    Returns:
        {
          "title": str,
          "date": str (ISO-8601 or ""),
          "tags": list[str],
          "sources": list[str],
          "related": list[str],
          "word_count": int,
          "last_modified": str (YYYY-MM-DD),
        }
        or an error dict on invalid path, traversal, or missing file.
    """
    result = safe_vault_path(path)
    if isinstance(result, dict):
        return result

    resolved: Path = result

    if not resolved.exists() or not resolved.is_file() or resolved.suffix != ".md":
        return err(f"Note not found: {path}", ERR_NOT_FOUND)

    try:
        post = frontmatter.load(str(resolved))
    except (FileNotFoundError, PermissionError) as exc:
        return err(f"Cannot read note: {exc}", ERR_NOT_FOUND)
    except Exception as exc:
        return err(f"Failed to parse note: {exc}", ERR_NOT_FOUND)

    # Coerce date field to ISO string regardless of whether python-frontmatter
    # parsed it as a datetime.date / datetime.datetime object or a raw string.
    raw_date = post.get("date", "")
    if hasattr(raw_date, "isoformat"):
        date_str: str = raw_date.isoformat()
    else:
        date_str = str(raw_date) if raw_date else ""

    try:
        last_modified: str = date.fromtimestamp(resolved.stat().st_mtime).isoformat()
    except (OSError, OverflowError, ValueError):
        last_modified = ""

    return {
        "title": post.get("title", resolved.stem),
        "date": date_str,
        "tags": post.get("tags", []),
        "sources": post.get("sources", []),
        "related": post.get("related", []),
        "word_count": len(post.content.split()),
        "last_modified": last_modified,
    }


@mcp.tool()
async def get_index() -> dict:
    """NAV-04: Return the full content of wiki/index.md plus parsed header stats.

    The index is the primary navigation entry point — Claude is instructed to
    call get_index() before any other navigation tool per CLAUDE.md rules.

    Returns:
        {
          "content": str (full file text),
          "total_pages": int,
          "total_sources": int,
          "last_updated": str (YYYY-MM-DD or ""),
        }
        or an error dict if wiki/index.md does not exist.
    """
    index_path: Path = VAULT_PATH / "wiki" / "index.md"

    if not index_path.exists():
        return err("Index not found — has init_vault.py run?", ERR_NOT_FOUND)

    try:
        content: str = index_path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError) as exc:
        return err(f"Cannot read index: {exc}", ERR_NOT_FOUND)

    # Parse the header line (line 2) for structured stats.
    # Expected format: "Last updated: YYYY-MM-DD | Total pages: N | Total sources: N"
    _HEADER_RE = re.compile(
        r"Last updated:\s*(\S+)\s*\|\s*Total pages:\s*(\d+)\s*\|\s*Total sources:\s*(\d+)"
    )
    last_updated: str = ""
    total_pages: int = 0
    total_sources: int = 0

    for line in content.splitlines():
        m = _HEADER_RE.search(line)
        if m:
            last_updated = m.group(1)
            total_pages = int(m.group(2))
            total_sources = int(m.group(3))
            break

    return {
        "content": content,
        "total_pages": total_pages,
        "total_sources": total_sources,
        "last_updated": last_updated,
    }


# ---------------------------------------------------------------------------
# 10. Mount MCP streamable-HTTP transport (after routes, after middleware)
# ---------------------------------------------------------------------------

app.mount("/mcp", mcp_app)
