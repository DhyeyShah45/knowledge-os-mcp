"""knowledge-os-mcp: FastAPI + FastMCP server with bearer auth and OAuth 2.0 PKCE.

Startup sequence:
  1. load_dotenv() — read .env into os.environ
  2. Read VAULT_PATH, VAULT_SECRET, OAUTH_CLIENT_ID, OAUTH_REDIRECT_URI from env (fail-fast)
  3. Read CLAUDE.md from vault root → inject as FastMCP `instructions` (INFRA-05)
  4. Build BearerAuthMiddleware (single auth enforcement point, INFRA-02)
  5. Mount MCP streamable-HTTP transport at /mcp (INFRA-01, D-05)
  6. Register /authorize and /token OAuth 2.0 PKCE endpoints (D-16)

Transport: streamable-HTTP via mcp.streamable_http_app() mounted at /mcp
Auth: Bearer token (VAULT_SECRET env var) + OAuth 2.0 PKCE wrapper for claude.ai mobile
CLAUDE.md: read at startup, not on every request (performance + resilience)
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import os
import re
import secrets
import time
from datetime import date
from pathlib import Path

import frontmatter as fm_lib

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
mcp: FastMCP = FastMCP("vault-mcp", instructions=_instructions_text, streamable_http_path="/")

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

        # Localhost connections are inherently secure — Claude Desktop on the
        # same machine doesn't support custom headers in its MCP config.
        client_host = request.client.host if request.client else ""
        if client_host in ("127.0.0.1", "::1"):
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
#    streamable_http_app() initialises the session manager; we wire its
#    lifespan into FastAPI so the manager starts/stops with the process.
# ---------------------------------------------------------------------------

mcp_starlette = mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def _lifespan(fastapi_app: FastAPI):
    async with mcp.session_manager.run():
        yield


# ---------------------------------------------------------------------------
# 8. FastAPI application
# ---------------------------------------------------------------------------

app: FastAPI = FastAPI(lifespan=_lifespan)

# Middleware is added BEFORE routes and mount so it applies to all requests.
app.add_middleware(BearerAuthMiddleware)

# ---------------------------------------------------------------------------
# OAUTH ENDPOINTS — see Task 2
# ---------------------------------------------------------------------------

# In-memory store for PKCE authorization codes (single-user, single-process).
# Acceptable per CONTEXT.md D-16 / RESEARCH Assumption A8.
# T-03-09: unbounded growth is accepted as a v1 tradeoff (single-user system).
_pkce_codes: dict[str, dict] = {}


@app.get("/authorize", response_model=None)
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


@app.post("/token", response_model=None)
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
                post = fm_lib.load(str(p))
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
        post = fm_lib.load(str(resolved))
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
# 10. Retrieval helper functions — internal (NOT @mcp.tool decorated)
#     Used by read_note_section (RET-04) and other retrieval tools.
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _get_sections(content: str) -> list[dict]:
    """Parse markdown headings from content into a structured list.

    Returns a list of dicts with keys:
      - "heading": heading text (without # prefix)
      - "level": heading level (1-6)
      - "start_line": zero-based line index of the heading line
    """
    lines = content.splitlines()
    sections: list[dict] = []
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            sections.append({
                "heading": m.group(2),
                "level": len(m.group(1)),
                "start_line": i,
            })
    return sections


def _find_heading_index(sections: list[dict], target: str) -> int | None:
    """Find the index into *sections* of the first heading matching *target*.

    Match is case-insensitive and partial (substring). Returns None if not found.
    """
    target_lower = target.lower()
    for i, section in enumerate(sections):
        if target_lower in section["heading"].lower():
            return i
    return None


# ---------------------------------------------------------------------------
# 11. Retrieval MCP tools (RET-01..RET-04)
#     All tools return plain dicts — FastMCP serializes them as MCP tool results.
#     All tools catch I/O errors and return the canonical error dict (D-08).
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_full_text(query: str, top_k: int = 5) -> dict:
    """RET-01: Naive case-insensitive keyword search across wiki/ markdown files.

    Phase 1 uses a full-file scan (rglob). Phase 2 will replace this with
    SQLite FTS5 for performance.

    Scoring: normalized occurrence count per D-12 — score = count / max_count.
    A single result receives score 1.0. Snippet: 2-line window centered on the
    first occurrence per D-15.

    Args:
        query:  Search term. Empty string returns {"results": []}.
        top_k:  Maximum number of results to return (default 5).

    Returns:
        {"results": [{"path": str, "title": str, "snippet": str, "score": float}, ...]}
        sorted by score descending. Empty list if no matches.
    """
    if not query or not query.strip():
        return {"results": []}

    query_lower = query.lower()
    wiki_dir: Path = VAULT_PATH / "wiki"

    if not wiki_dir.exists():
        return {"results": []}

    candidates: list[dict] = []

    try:
        for p in wiki_dir.rglob("*.md"):
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except (FileNotFoundError, PermissionError):
                continue

            content_lower = content.lower()
            count = content_lower.count(query_lower)
            if count == 0:
                continue

            # Find the first matching line (D-15: 2-line window)
            lines = content.splitlines()
            first_match_idx = -1
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    first_match_idx = i
                    break

            # Build 2-line snippet centered on first occurrence
            if first_match_idx >= 0:
                if first_match_idx < len(lines) - 1:
                    # Take the matching line + next line
                    snippet_lines = lines[first_match_idx:first_match_idx + 2]
                else:
                    # Last line — take previous + matching
                    start = max(0, first_match_idx - 1)
                    snippet_lines = lines[start:first_match_idx + 1]
                snippet = "\n".join(snippet_lines)
                # Truncate to ~150 chars per D-15
                if len(snippet) > 150:
                    snippet = snippet[:150]
            else:
                snippet = ""

            # Resolve title from frontmatter or stem
            try:
                post = fm_lib.load(str(p))
                title: str = post.get("title") or p.stem
            except Exception:
                title = p.stem

            rel = p.relative_to(VAULT_PATH).as_posix()
            candidates.append({
                "path": rel,
                "title": title,
                "snippet": snippet,
                "_count": count,
            })
    except (FileNotFoundError, PermissionError) as exc:
        return err(f"Cannot search wiki directory: {exc}", ERR_NOT_FOUND)

    # Sort by count descending, take top_k
    candidates.sort(key=lambda c: c["_count"], reverse=True)
    candidates = candidates[:top_k]

    # D-12: normalize scores — max_count becomes 1.0
    if candidates:
        max_count = candidates[0]["_count"]  # already sorted descending
        results = []
        for c in candidates:
            results.append({
                "path": c["path"],
                "title": c["title"],
                "snippet": c["snippet"],
                "score": round(c["_count"] / max_count, 10),
            })
    else:
        results = []

    return {"results": results}


@mcp.tool()
async def get_note_summary(path: str) -> dict:
    """RET-02: Return a token-efficient summary of a note — no full body content.

    Returns the first 200 chars of the body plus the heading outline so Claude
    can evaluate relevance before paying the full read_note token cost.

    Args:
        path: Relative vault path to a *.md file (e.g. "wiki/concepts/AI.md").

    Returns:
        {"title": str, "summary": str, "headings": list[str], "word_count": int}
        or an error dict on invalid path, traversal, or missing file.
    """
    result = safe_vault_path(path)
    if isinstance(result, dict):
        return result

    resolved: Path = result

    if not resolved.exists() or not resolved.is_file() or resolved.suffix != ".md":
        return err(f"Note not found: {path}", ERR_NOT_FOUND)

    try:
        post = fm_lib.load(str(resolved))
    except Exception as exc:
        return err(f"Cannot read note: {exc}", ERR_NOT_FOUND)

    title: str = post.get("title") or resolved.stem
    body: str = post.content

    # PRD §5.2: first 200 chars of body
    summary = body[:200]

    headings = [s["heading"] for s in _get_sections(body)]
    word_count = len(body.split())

    return {
        "title": title,
        "summary": summary,
        "headings": headings,
        "word_count": word_count,
    }


@mcp.tool()
async def read_note(path: str) -> dict:
    """RET-03: Return full content and frontmatter of a note.

    Higher token cost than get_note_summary — Claude should call
    get_note_summary first to evaluate relevance (CLAUDE.md operational rules).

    Args:
        path: Relative vault path to a *.md file (e.g. "wiki/concepts/AI.md").

    Returns:
        {"path": str, "title": str, "frontmatter": dict, "content": str}
        or an error dict on invalid path, traversal, or missing file.
    """
    result = safe_vault_path(path)
    if isinstance(result, dict):
        return result

    resolved: Path = result

    if not resolved.exists() or not resolved.is_file():
        return err(f"Note not found: {path}", ERR_NOT_FOUND)

    try:
        post = fm_lib.load(str(resolved))
    except Exception as exc:
        return err(f"Cannot read note: {exc}", ERR_NOT_FOUND)

    title: str = post.get("title") or resolved.stem
    content: str = post.content
    fm_dict = dict(post.metadata)

    # Coerce datetime/date values to ISO strings for JSON serialisability
    for key, value in fm_dict.items():
        if hasattr(value, "isoformat"):
            fm_dict[key] = value.isoformat()

    rel = resolved.relative_to(VAULT_PATH).as_posix()
    return {
        "path": rel,
        "title": title,
        "frontmatter": fm_dict,
        "content": content,
    }


@mcp.tool()
async def read_note_section(path: str, heading: str) -> dict:
    """RET-04: Return the content of a single named section within a note.

    More token-efficient than read_note when only one section is needed.
    Heading match is case-insensitive and partial.

    Args:
        path:    Relative vault path to a *.md file.
        heading: Heading text to search for (partial, case-insensitive).

    Returns:
        {"path": str, "heading": str, "content": str}
        or an error dict. HEADING_NOT_FOUND errors include available_headings list.
    """
    result = safe_vault_path(path)
    if isinstance(result, dict):
        return result

    resolved: Path = result

    if not resolved.exists() or not resolved.is_file():
        return err(f"Note not found: {path}", ERR_NOT_FOUND)

    try:
        content = resolved.read_text(encoding="utf-8")
    except Exception as exc:
        return err(f"Cannot read note: {exc}", ERR_NOT_FOUND)

    sections = _get_sections(content)
    idx = _find_heading_index(sections, heading)

    if idx is None:
        # Return HEADING_NOT_FOUND with available_headings (CONTEXT.md Specifics, D-08)
        error_dict = err(f"Heading not found: {heading}", ERR_HEADING_NOT_FOUND)
        error_dict["available_headings"] = [s["heading"] for s in sections]
        return error_dict

    lines = content.splitlines()
    section_start = sections[idx]["start_line"] + 1  # line after heading
    section_level = sections[idx]["level"]

    # Find where this section ends: next heading at same or higher level
    section_end = len(lines)
    for j in range(idx + 1, len(sections)):
        if sections[j]["level"] <= section_level:
            section_end = sections[j]["start_line"]
            break

    section_content = "\n".join(lines[section_start:section_end]).rstrip()
    rel = resolved.relative_to(VAULT_PATH).as_posix()

    return {
        "path": rel,
        "heading": sections[idx]["heading"],
        "content": section_content,
    }


# ---------------------------------------------------------------------------
# 12. Ingestion MCP tools (INGEST-01..INGEST-05)
#     All tools call safe_vault_path() first (T-06-01).
#     raw/ writes are NOT permitted via these tools — safe_vault_path rejects
#     them (T-06-02). Use ingest_source (Plan 07) for raw/ writes.
#     All tools return the canonical error dict (D-08) on failure.
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_note(
    path: str,
    content: str,
    tags: list = [],
    frontmatter_extra: dict = {},
) -> dict:
    """INGEST-01: Create a new markdown note with auto-generated YAML frontmatter.

    The note is created at VAULT_PATH/path with frontmatter fields populated
    from PRD §3 template: date (today), tags, sources (empty), related (empty),
    summary (empty string).  Caller can override or extend via frontmatter_extra.

    Args:
        path:              Relative vault path, e.g. "wiki/concepts/python.md".
                           Must be inside wiki/ — raw/ is rejected (T-06-01).
        content:           Markdown body text written after the frontmatter block.
        tags:              List of tag strings to attach to the note.
        frontmatter_extra: Additional or override frontmatter key/value pairs.
                           Caller-supplied keys override the template defaults.

    Returns:
        {"path": str, "created": True, "word_count": int}
        or error dict with code ALREADY_EXISTS if the file already exists (PRD §5.3),
        INVALID_PATH if the path is invalid or traverses outside the vault.
    """
    try:
        result = safe_vault_path(path)
        if isinstance(result, dict):
            return result
        p: Path = result

        if p.exists():
            return err(f"Note already exists: {path}", ERR_ALREADY_EXISTS)

        # Build frontmatter from PRD §3 template, then merge caller overrides
        fm_dict: dict = {
            "date": date.today().isoformat(),
            "tags": list(tags) if tags else [],
            "sources": [],
            "related": [],
            "summary": "",
        }
        fm_dict.update(frontmatter_extra)

        # Serialize using python-frontmatter
        post = fm_lib.Post(content, **fm_dict)
        serialized: str = fm_lib.dumps(post)

        # Ensure parent directories exist
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(serialized, encoding="utf-8")

        word_count = len(content.split())
        rel = p.relative_to(VAULT_PATH).as_posix()
        return {"path": rel, "created": True, "word_count": word_count}
    except Exception as exc:
        return err(str(exc), ERR_NOT_FOUND)


@mcp.tool()
async def append_to_note(path: str, text: str) -> dict:
    """INGEST-02: Append text to an existing note's body.

    Inserts exactly one blank line between the existing content and the new
    text, then adds a trailing newline.

    Args:
        path: Relative vault path to an existing *.md file.
        text: Text to append after the current body.

    Returns:
        {"path": str, "appended": True, "new_word_count": int}
        or error dict with NOT_FOUND / INVALID_PATH.
    """
    try:
        result = safe_vault_path(path)
        if isinstance(result, dict):
            return result
        p: Path = result

        if not p.exists():
            return err(f"Note not found: {path}", ERR_NOT_FOUND)

        existing = p.read_text(encoding="utf-8")
        new_content = existing.rstrip("\n") + "\n\n" + text + "\n"
        p.write_text(new_content, encoding="utf-8")

        # Compute word count from body only (excludes frontmatter)
        post = fm_lib.load(str(p))
        new_word_count = len(post.content.split())

        rel = p.relative_to(VAULT_PATH).as_posix()
        return {"path": rel, "appended": True, "new_word_count": new_word_count}
    except Exception as exc:
        return err(str(exc), ERR_NOT_FOUND)


@mcp.tool()
async def prepend_to_note(path: str, text: str) -> dict:
    """INGEST-03: Insert text before the existing body content, after frontmatter.

    Reads the note via python-frontmatter, prepends text to the body, writes
    back so the YAML frontmatter block is preserved unchanged.

    Args:
        path: Relative vault path to an existing *.md file.
        text: Text to insert at the beginning of the body.

    Returns:
        {"path": str, "prepended": True, "new_word_count": int}
        or error dict with NOT_FOUND / INVALID_PATH.
    """
    try:
        result = safe_vault_path(path)
        if isinstance(result, dict):
            return result
        p: Path = result

        if not p.exists():
            return err(f"Note not found: {path}", ERR_NOT_FOUND)

        post = fm_lib.load(str(p))
        new_body = text.rstrip("\n") + "\n\n" + post.content
        post.content = new_body
        p.write_text(fm_lib.dumps(post), encoding="utf-8")

        new_word_count = len(new_body.split())
        rel = p.relative_to(VAULT_PATH).as_posix()
        return {"path": rel, "prepended": True, "new_word_count": new_word_count}
    except Exception as exc:
        return err(str(exc), ERR_NOT_FOUND)


@mcp.tool()
async def insert_under_heading(path: str, heading: str, text: str) -> dict:
    """INGEST-04: Insert text at the end of a named section within a note.

    Finds the first heading matching *heading* (case-insensitive partial match)
    and appends *text* as a new paragraph just before the next same-or-higher-
    level heading (or end-of-file).  The YAML frontmatter is preserved.

    Args:
        path:    Relative vault path to an existing *.md file.
        heading: Heading text to locate (partial, case-insensitive).
        text:    Text to insert at the end of the found section.

    Returns:
        {"path": str, "heading_found": True, "inserted": True, "heading": str}
        or error dict with HEADING_NOT_FOUND + available_headings if no match,
        NOT_FOUND / INVALID_PATH on other failures.
    """
    try:
        result = safe_vault_path(path)
        if isinstance(result, dict):
            return result
        p: Path = result

        if not p.exists():
            return err(f"Note not found: {path}", ERR_NOT_FOUND)

        post = fm_lib.load(str(p))
        body = post.content

        sections = _get_sections(body)
        idx = _find_heading_index(sections, heading)

        if idx is None:
            error_dict = err(
                f"Heading not found: {heading}", ERR_HEADING_NOT_FOUND
            )
            error_dict["available_headings"] = [s["heading"] for s in sections]
            return error_dict

        # Find insertion point: end of the matched section (just before the
        # next heading at same or higher level, or EOF)
        lines = body.split("\n")
        matched_level = sections[idx]["level"]

        # Find next section with level <= matched_level (same or higher hierarchy)
        insert_line = len(lines)
        for j in range(idx + 1, len(sections)):
            if sections[j]["level"] <= matched_level:
                insert_line = sections[j]["start_line"]
                break

        # Insert as a new paragraph (blank line + text + blank line)
        lines.insert(insert_line, "\n" + text + "\n")
        post.content = "\n".join(lines)
        p.write_text(fm_lib.dumps(post), encoding="utf-8")

        rel = p.relative_to(VAULT_PATH).as_posix()
        return {
            "path": rel,
            "heading_found": True,
            "inserted": True,
            "heading": sections[idx]["heading"],
        }
    except Exception as exc:
        return err(str(exc), ERR_NOT_FOUND)


@mcp.tool()
async def update_frontmatter(path: str, key: str, value) -> dict:
    """INGEST-05: Update a single frontmatter key without modifying the body.

    Loads the note, updates (or adds) the specified key in the YAML frontmatter,
    then writes back via python-frontmatter so the body content is untouched.

    Args:
        path:  Relative vault path to an existing *.md file.
        key:   Frontmatter key to set (created or overwritten).
        value: New value for the key.  Must be JSON-serializable.

    Returns:
        {"path": str, "key": str, "old_value": any, "new_value": any}
        old_value is None if the key did not previously exist.
        date/datetime old/new values are coerced to ISO strings.
        Error dict with NOT_FOUND / INVALID_PATH on failure.
    """
    try:
        result = safe_vault_path(path)
        if isinstance(result, dict):
            return result
        p: Path = result

        if not p.exists():
            return err(f"Note not found: {path}", ERR_NOT_FOUND)

        post = fm_lib.load(str(p))
        old_value = post.metadata.get(key)

        # Coerce date/datetime to ISO string for JSON serialisability
        if hasattr(old_value, "isoformat"):
            old_value = old_value.isoformat()

        new_val = value
        if hasattr(new_val, "isoformat"):
            new_val = new_val.isoformat()

        post[key] = value
        p.write_text(fm_lib.dumps(post), encoding="utf-8")

        rel = p.relative_to(VAULT_PATH).as_posix()
        return {
            "path": rel,
            "key": key,
            "old_value": old_value,
            "new_value": new_val,
        }
    except Exception as exc:
        return err(str(exc), ERR_NOT_FOUND)


# ---------------------------------------------------------------------------
# 13. Maintenance MCP tools (MAINT-01..MAINT-02)
#     update_index — upsert entry in wiki/index.md under named section (MAINT-01)
#     append_log   — prepend timestamped block in wiki/log.md (MAINT-02)
# ---------------------------------------------------------------------------

_VALID_CATEGORIES: frozenset[str] = frozenset({"entities", "concepts", "sources", "queries"})
_VALID_OPERATIONS: frozenset[str] = frozenset({"ingest", "query", "lint", "update"})

# Regex that matches any "- [[...]]" list entry inside an index section
_ENTRY_RE = re.compile(r"^- \[\[.+?\]\]")

# Regex for the totals header line
_TOTALS_RE = re.compile(
    r"(Last updated:\s*)(\S+)(\s*\|\s*Total pages:\s*)(\d+)(\s*\|\s*Total sources:\s*)(\d+)"
)


@mcp.tool()
async def update_index(path: str, summary: str, category: str) -> dict:
    """MAINT-01: Upsert an entry in wiki/index.md under the named category section.

    Strips a trailing .md from path to form an Obsidian wikilink.  If an entry
    for the same path already exists in the section it is replaced in-place (upsert).
    After writing the entry the header line totals are refreshed so get_index()
    always returns accurate counts.

    Args:
        path:     Relative vault path of the note to reference (e.g. "wiki/concepts/foo.md").
        summary:  Short human-readable description for the index entry.
        category: Section to target — one of {entities, concepts, sources, queries}.

    Returns:
        {"updated": True, "entry": "<the line written>"}
        or an error dict with INVALID_PATH / NOT_FOUND.
    """
    try:
        # --- Validate category (T-07-01) ---
        if category not in _VALID_CATEGORIES:
            return err(f"Invalid category: {category}", ERR_INVALID_PATH)

        # --- Validate path stays within vault (path need not exist yet) ---
        resolved = safe_vault_path(path)
        if isinstance(resolved, dict):
            return resolved

        # --- Build the wikilink key (strip trailing .md per Obsidian convention) ---
        path_without_md = path[:-3] if path.endswith(".md") else path
        entry = f"- [[{path_without_md}]] — {summary}"

        # --- Read index.md ---
        index_path: Path = VAULT_PATH / "wiki" / "index.md"
        if not index_path.exists():
            return err("Index not found — has init_vault.py run?", ERR_NOT_FOUND)

        content: str = index_path.read_text(encoding="utf-8")
        lines: list[str] = content.splitlines(keepends=True)

        # Section heading map
        section_heading = (
            f"## {category.capitalize()}"
            if category != "queries"
            else "## Queries"
        )
        # Exact heading per PRD §3
        _SECTION_MAP: dict[str, str] = {
            "entities": "## Entities",
            "concepts": "## Concepts",
            "sources": "## Sources",
            "queries": "## Queries",
        }
        section_heading = _SECTION_MAP[category]

        # --- Locate the target section heading ---
        section_start: int | None = None
        for i, line in enumerate(lines):
            if line.rstrip("\r\n") == section_heading:
                section_start = i
                break

        if section_start is None:
            # Section heading not present in index — insert it before EOF
            # and then insert the entry on the next line
            lines.append(f"{section_heading}\n")
            lines.append(f"{entry}\n")
        else:
            # Scan section body for an existing entry with the same wikilink key
            existing_key = f"- [[{path_without_md}]]"
            section_end = len(lines)
            for i in range(section_start + 1, len(lines)):
                stripped = lines[i].rstrip("\r\n")
                if stripped.startswith("## ") and i != section_start:
                    section_end = i
                    break

            replaced = False
            for i in range(section_start + 1, section_end):
                if lines[i].startswith(existing_key):
                    lines[i] = entry + "\n"
                    replaced = True
                    break

            if not replaced:
                # Insert new entry just before section_end
                lines.insert(section_end, entry + "\n")

        # --- Refresh header line totals ---
        new_content = "".join(lines)
        all_lines = new_content.splitlines()

        # Count total "- [[...]]" entries across all sections
        total_pages = sum(1 for ln in all_lines if _ENTRY_RE.match(ln))

        # Count entries in Sources section only
        in_sources = False
        total_sources = 0
        for ln in all_lines:
            stripped = ln.strip()
            if stripped == "## Sources":
                in_sources = True
                continue
            if in_sources:
                if stripped.startswith("## "):
                    in_sources = False
                elif _ENTRY_RE.match(stripped):
                    total_sources += 1

        today = date.today().isoformat()

        # Replace the header stats line
        updated_lines: list[str] = []
        for ln in all_lines:
            m = _TOTALS_RE.search(ln)
            if m:
                ln = f"Last updated: {today} | Total pages: {total_pages} | Total sources: {total_sources}"
            updated_lines.append(ln)

        final_content = "\n".join(updated_lines)
        # Preserve trailing newline if original had one
        if new_content.endswith("\n"):
            final_content += "\n"

        index_path.write_text(final_content, encoding="utf-8")

        return {"updated": True, "entry": entry}
    except Exception as exc:
        return err(str(exc), ERR_NOT_FOUND)


@mcp.tool()
async def append_log(operation: str, title: str, notes: str = "") -> dict:
    """MAINT-02: Prepend a timestamped entry to wiki/log.md (newest-first per PRD §3).

    The entry is inserted immediately below the "# Vault Log" header line so
    the most recent operation is always at the top of the log.

    Args:
        operation: One of {ingest, query, lint, update} (T-07-02).
        title:     Short description of the operation subject.
        notes:     Optional multi-line details appended after the heading line.

    Returns:
        {"appended": True, "entry": "<the block written>"}
        or an error dict with NOT_FOUND / INVALID_PATH.
    """
    try:
        # --- Validate operation (T-07-02) ---
        if operation not in _VALID_OPERATIONS:
            return err(f"Invalid operation: {operation}", ERR_INVALID_PATH)

        # --- Read log.md ---
        log_path: Path = VAULT_PATH / "wiki" / "log.md"
        if not log_path.exists():
            return err("Log not found — has init_vault.py run?", ERR_NOT_FOUND)

        content: str = log_path.read_text(encoding="utf-8")

        # --- Build entry block (PRD §3 format) ---
        today = date.today().isoformat()
        entry_block = f"## [{today}] {operation} | {title}\n{notes}\n\n"

        # --- Prepend below "# Vault Log" header ---
        lines = content.splitlines(keepends=True)
        if lines and lines[0].rstrip("\r\n") == "# Vault Log":
            # Consume any blank lines immediately after the header
            header_end = 1
            while header_end < len(lines) and lines[header_end].strip() == "":
                header_end += 1
            body_lines = lines[header_end:]
            new_content = "# Vault Log\n\n" + entry_block + "".join(body_lines)
        else:
            # Header not in expected format — prepend unconditionally
            new_content = entry_block + content

        log_path.write_text(new_content, encoding="utf-8")

        return {"appended": True, "entry": entry_block}
    except Exception as exc:
        return err(str(exc), ERR_NOT_FOUND)


# ---------------------------------------------------------------------------
# 14. Mount MCP streamable-HTTP transport (after routes, after middleware)
# ---------------------------------------------------------------------------

app.mount("/mcp", mcp_starlette)

# ---------------------------------------------------------------------------
# 15. stdio entry point — used by Claude Desktop (mcpServers stdio config)
#     Running `python server.py` directly bypasses FastAPI/HTTP entirely and
#     serves all 15 tools over stdin/stdout for local desktop integration.
#     Remote access (Cloudflare tunnel) still uses uvicorn + HTTP above.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
