# Phase 1: Core MCP Server - Research

**Researched:** 2026-05-29
**Domain:** FastAPI + MCP streamable-HTTP transport + Cloudflare Tunnel + Obsidian vault file operations
**Confidence:** HIGH (post-user-resolution of 3 open questions; see Open Questions section)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single flat `server.py` monolith — all tools in one file. No `app/` package. No subdirectories for tool categories.
- **D-02:** Configuration via `.env` file using `python-dotenv`. Required env vars: `VAULT_SECRET`, `VAULT_PATH`, `OAUTH_CLIENT_ID`, `OAUTH_REDIRECT_URI`.
- **D-03:** Dev command: `uvicorn server:app --reload`. PM2 wraps the same command in production.
- **D-04:** Root files: `server.py`, `.env` (gitignored), `requirements.txt`, `README.md`, `ecosystem.config.js`, `init_vault.py`, `setup.sh`.
- **D-05:** Use the official `mcp` SDK (`pip install mcp`). Import `from mcp.server.fastmcp import FastMCP`. Mount via streamable-HTTP: `mcp_app = mcp.http_app(path='/mcp', transport='streamable-http')`. SSE transport is deprecated (MCP spec March 2025).
- **D-06:** Bearer auth enforced via FastAPI middleware on all routes except OAuth endpoints. Reads `Authorization: Bearer <token>`, compares to `VAULT_SECRET`. Single enforcement point.
- **D-07:** Vault rules document is named `CLAUDE.md`. Its content is injected as the MCP server's `instructions` field on startup.
- **D-08:** All tool errors return `{"error": true, "message": "...", "code": "NOT_FOUND"}`. Codes: `NOT_FOUND`, `ALREADY_EXISTS`, `INVALID_PATH`, `HEADING_NOT_FOUND`, `AUTH_ERROR`. Never raise HTTPException from tool functions.
- **D-09:** Phase 1 delivers: `setup.sh` (creates Cloudflare tunnel, generates `~/.cloudflared/config.yml` template), `ecosystem.config.js` (PM2 starts both `vault-mcp` and `cloudflare-tunnel` with auto-restart), README section for DNS + dashboard steps.
- **D-10:** `init_vault.py` creates a fresh vault at `VAULT_PATH` — full directory structure, seeds `wiki/index.md` and `wiki/log.md`, copies `CLAUDE.md` into vault root.
- **D-11:** `VAULT_PATH` points to a new directory — `init_vault.py` creates it from scratch.
- **D-12:** Naive search scoring: `score = occurrence_count / max_occurrences_across_results`. Produces 0–1 float. Single result scores 1.0.
- **D-13:** Search is case-insensitive (`query.lower() in line.lower()`), scans full file including YAML frontmatter.
- **D-14:** Search scope: `wiki/` subdirectory only. Raw sources excluded.
- **D-15:** Snippet: 2-line window (~150 chars) centered on first occurrence of query in file.
- **D-16:** OAuth 2.0 Authorization Code + PKCE (S256) endpoints implemented in Phase 1 to enable claude.ai mobile. Env vars `OAUTH_CLIENT_ID` and `OAUTH_REDIRECT_URI` required.

### Claude's Discretion

- Frontmatter auto-generation logic in `create_note()` — specific field inference (tags, related) is Claude's call as long as PRD §3 template fields are populated.
- Index entry format in `update_index()` — handling duplicates (upsert vs. error) is left to planner/researcher.
- Heading match logic in `insert_under_heading()` and `read_note_section()` — partial case-insensitive match is specified; exact tie-breaking is planner's call.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | FastAPI server serves MCP tools over streamable-HTTP transport on port 8000 | MCP SDK `FastMCP.http_app(path='/mcp', transport='streamable-http')` mounted to FastAPI |
| INFRA-02 | All endpoints require bearer token authentication via VAULT_SECRET env var | FastAPI `BaseHTTPMiddleware` intercepts all requests before MCP receives them |
| INFRA-03 | Cloudflare Tunnel exposes server at persistent custom subdomain | `cloudflared tunnel create` + `config.yml` + `cloudflared tunnel run` |
| INFRA-04 | Server process managed via PM2 with auto-restart | `ecosystem.config.js` with `interpreter: "uvicorn"` and `autorestart: true` |
| INFRA-05 | CLAUDE.md operational rules embedded as MCP system prompt | `FastMCP(name, instructions=claude_md_content)` on startup |
| NAV-01 | `list_folders()` returns full vault folder tree with note counts | `pathlib.Path.rglob("*.md")` scan scoped to `wiki/` |
| NAV-02 | `list_notes(folder)` returns paths, titles, last_modified | File stat + frontmatter title extraction |
| NAV-03 | `get_note_metadata(path)` returns frontmatter + stats without body | `python-frontmatter` load + word count of content |
| NAV-04 | `get_index()` reads `wiki/index.md` as primary navigation entry point | Simple file read; parse total_pages/total_sources from header line |
| RET-01 | `search_full_text(query, top_k)` scans wiki/ with ranked snippets | Pure Python line scan (D-12–D-15 spec) |
| RET-02 | `get_note_summary(path)` returns first 200 chars + heading outline | Read file, slice content[:200], regex headings |
| RET-03 | `read_note(path)` returns full note content + frontmatter | `python-frontmatter` load |
| RET-04 | `read_note_section(path, heading)` reads single section only | Parse markdown headings, slice between heading and next heading |
| INGEST-01 | `create_note(path, content, tags, frontmatter)` creates new note | Check file existence; write YAML frontmatter + body |
| INGEST-02 | `append_to_note(path, text)` appends to existing note | Open in append mode; prepend newline |
| INGEST-03 | `prepend_to_note(path, text)` inserts after frontmatter | Parse with `python-frontmatter`, prepend before body, write back |
| INGEST-04 | `insert_under_heading(path, heading, text)` inserts under heading | Regex heading scan; insert before next heading or EOF |
| INGEST-05 | `update_frontmatter(path, key, value)` updates single frontmatter key | `python-frontmatter` load, set key, dump back |
| MAINT-01 | `update_index(path, summary, category)` adds/updates `wiki/index.md` | Parse index sections, upsert `[[path]]` line under category |
| MAINT-02 | `append_log(operation, title, notes)` appends to `wiki/log.md` | Prepend timestamped block in `## [date] op | title` format |
</phase_requirements>

---

## Summary

Phase 1 builds a greenfield FastAPI server that exposes a set of Obsidian vault read/write operations as MCP tools, secured by bearer auth (with an OAuth 2.0 PKCE wrapper for claude.ai mobile), with a Cloudflare Tunnel providing a persistent HTTPS endpoint. The official MCP Python SDK (`mcp` package) is used: `mcp.server.fastmcp.FastMCP` provides the `@mcp.tool()` decorator for custom tool registration, the `instructions` constructor parameter for injecting `CLAUDE.md` as the system prompt, and `mcp.http_app(path='/mcp', transport='streamable-http')` to mount the streamable-HTTP transport onto a FastAPI app.

The original D-05 wording ("fastapi-mcp library") was a naming ambiguity — the user has confirmed the official `mcp` SDK is the correct dependency (see RESOLVED Open Question 1). The `fastapi-mcp` (tadata-org) package only converts existing FastAPI routes into MCP tools and cannot register the 14 custom file-operation functions this project needs.

For claude.ai mobile compatibility, OAuth 2.0 Authorization Code + PKCE endpoints are implemented in Phase 1 (see RESOLVED Open Question 2). The `/token` endpoint exchanges the PKCE-verified code for an `access_token` that equals `VAULT_SECRET` — a thin OAuth wrapper sufficient for a single-user system. claude.ai's connector UI does not accept static bearer tokens, so OAuth is required to unblock the primary mobile use case.

Transport is streamable-HTTP (see RESOLVED Open Question 3), not SSE. SSE is deprecated in the MCP spec (March 2025), and starting with the current standard avoids a Phase 2 migration.

**Primary recommendation:** Use `from mcp.server.fastmcp import FastMCP` (official MCP SDK), mount via `mcp.http_app(path='/mcp', transport='streamable-http')` onto a FastAPI app that runs bearer auth middleware (with OAuth bypass for `/authorize` and `/token`), and document the OAuth setup in the README.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MCP tool registration & protocol | MCP SDK (FastMCP) | — | FastMCP owns the MCP protocol layer |
| Bearer auth enforcement | FastAPI middleware | — | Middleware executes before MCP receives any request |
| OAuth 2.0 PKCE flow | FastAPI routes (/authorize, /token) | `secrets`, `hashlib`, `base64` stdlib | Thin in-process OAuth wrapper for claude.ai mobile (D-16) |
| Vault file read/write | Python stdlib (pathlib, io) | python-frontmatter | File operations are pure local disk I/O |
| Frontmatter parse/serialize | python-frontmatter | — | Handles YAML parsing/serialization of markdown files |
| Process persistence | PM2 | — | Node process manager wrapping uvicorn subprocess |
| Tunnel / network exposure | cloudflared | — | Cloudflare Tunnel binary handles network translation |
| CLAUDE.md system prompt injection | FastMCP `instructions=` | — | Read at startup, passed to FastMCP constructor |
| Vault initialization | `init_vault.py` (stdlib only) | — | One-shot script, no server dependency |
| Search | Python line scan | — | Naive grep over `wiki/` files (Phase 1 only) |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.111.0 (PRD) / 0.136.x current [ASSUMED] | HTTP framework, app lifecycle, middleware | De facto Python async web framework |
| `uvicorn[standard]` | 0.30.0 (PRD) | ASGI server | Required to run FastAPI; `[standard]` adds websockets/HTTP2 support |
| `mcp` | 1.9.1 (current) [VERIFIED: PyPI search] | MCP protocol — tools, streamable-HTTP transport, instructions | Official Anthropic SDK; `FastMCP` class provides decorator-based tool registration and `instructions` field |
| `python-dotenv` | 1.2.2 (current) [VERIFIED: PyPI search] | Load `.env` into `os.environ` at startup | Standard `.env` pattern for Python |
| `pydantic` | 2.7.0 (PRD) | Data validation (FastAPI dependency) | FastAPI uses Pydantic v2 internally |
| `python-frontmatter` | 1.1.0 (current) [VERIFIED: PyPI search] | Parse and write YAML frontmatter in markdown files | Only maintained library for this; correct import is `import frontmatter` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `watchdog` | 4.0.0 (PRD) | File system event watcher | Install now for Phase 2/3 use; not used in Phase 1 |
| `pathlib` | stdlib | Path manipulation | Used throughout for all file path operations |
| `re` | stdlib | Regex for heading extraction and search | Heading parsing in `read_note_section()`, `insert_under_heading()` |
| `datetime` | stdlib | Timestamps for log entries, frontmatter dates | `append_log()`, frontmatter `date` field |
| `secrets` | stdlib | Cryptographically-strong code generation (OAuth) | `/authorize` issues `secrets.token_urlsafe(32)` codes |
| `hashlib` | stdlib | PKCE S256 verifier hashing | `/token` verifies `sha256(code_verifier)` against stored challenge |
| `base64` | stdlib | URL-safe base64 (PKCE encoding) | PKCE challenge/verifier comparison |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `mcp.server.fastmcp.FastMCP` | `fastapi-mcp` (tadata) | `fastapi-mcp` only exposes FastAPI routes — cannot register custom functions; wrong tool for this project |
| `mcp.server.fastmcp.FastMCP` | `fastmcp` (standalone package) | `fastmcp` is the standalone FastMCP 2.x library; `mcp.server.fastmcp` ships the v1-compatible FastMCP inside the official SDK — either works, but the official SDK is the locked dependency |
| Streamable-HTTP (`http_app(transport="streamable-http")`) | SSE transport (`.sse_app()`) | SSE is deprecated in MCP spec (March 2025); streamable-HTTP is the current standard. Project uses streamable-HTTP per D-05 / RESOLVED Open Question 3. |
| `BaseHTTPMiddleware` | FastAPI `Depends()` per-tool | Middleware is a single enforcement point (D-06); `Depends()` would require adding to every tool decorator |

**Installation (Phase 1):**
```bash
pip install fastapi==0.111.0 "uvicorn[standard]==0.30.0" mcp python-dotenv==1.2.2 pydantic==2.7.0 python-frontmatter watchdog==4.0.0
```

---

## Package Legitimacy Audit

> slopcheck was unavailable at research time (pip proxy restriction). All packages are tagged `[ASSUMED]` below except those verified via official authoritative sources. The planner must gate each install behind a `checkpoint:human-verify` task.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `fastapi` | PyPI | ~6 yrs | 488M/month [ASSUMED] | github.com/fastapi/fastapi | N/A | Approved — mainstream framework |
| `uvicorn` | PyPI | ~6 yrs | [ASSUMED] high | github.com/encode/uvicorn | N/A | Approved — official ASGI server |
| `mcp` | PyPI | ~1.5 yrs | 256K+ wkly [ASSUMED] | github.com/modelcontextprotocol/python-sdk | N/A | Approved — official Anthropic SDK [CITED: pypi.org/project/mcp/1.9.1/] |
| `python-dotenv` | PyPI | ~9 yrs | [ASSUMED] high | github.com/theskumar/python-dotenv | N/A | Approved — standard pattern |
| `pydantic` | PyPI | ~7 yrs | [ASSUMED] very high | github.com/pydantic/pydantic | N/A | Approved — FastAPI dependency |
| `python-frontmatter` | PyPI | ~8 yrs | 111K wkly [CITED: snyk.io/advisor/python/python-frontmatter] | github.com/eyeseast/python-frontmatter | N/A | Approved — only library for this purpose |
| `watchdog` | PyPI | ~12 yrs | [ASSUMED] high | github.com/gorakhargosh/watchdog | N/A | Approved — standard file watcher |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable — all packages above are tagged `[ASSUMED]` and the planner must gate each install behind a `checkpoint:human-verify` task.*

---

## Architecture Patterns

### System Architecture Diagram

```
  startup
     │
     ├── read CLAUDE.md from vault root
     ├── FastMCP("vault-mcp", instructions=claude_md_content)
     └── mount mcp.http_app(path='/mcp', transport='streamable-http') → FastAPI app

  request flow (per tool call)
     │
     ▼
  Cloudflare Tunnel (HTTPS) → localhost:8000
     │
     ▼
  FastAPI BaseHTTPMiddleware
     │  bypasses /authorize and /token (OAuth flow)
     │  checks Authorization: Bearer <token> == VAULT_SECRET
     │  returns 401 {"error":true,...} on mismatch
     ▼
  MCP streamable-HTTP transport layer  (/mcp)
     │
     ▼
  @mcp.tool() function
     │
     ├── reads/writes files under VAULT_PATH via pathlib
     └── returns dict {"field": value} OR {"error": true, "message": "...", "code": "..."}
```

### Recommended Project Structure

```
/project-root/
├── server.py              # Single monolith — FastAPI app + all MCP tools + OAuth endpoints
├── init_vault.py          # One-shot vault scaffolding script
├── setup.sh               # cloudflared tunnel create + config.yml template
├── ecosystem.config.js    # PM2 config: vault-mcp + cloudflare-tunnel processes
├── requirements.txt       # Phase 1 pip deps
├── .env                   # VAULT_SECRET + VAULT_PATH + OAUTH_CLIENT_ID + OAUTH_REDIRECT_URI (gitignored)
└── README.md              # Setup walkthrough + DNS steps + OAuth configuration
```

### Pattern 1: FastMCP Tool Registration with Instructions

**What:** Create FastMCP server, read `CLAUDE.md` from vault, pass as `instructions=` so Claude receives it on MCP connection.

**When to use:** Server startup; read file if it exists, empty string fallback if not yet initialized.

```python
# Source: official MCP Python SDK + gofastmcp.com documentation [CITED]
from mcp.server.fastmcp import FastMCP
from pathlib import Path
import os

VAULT_PATH = Path(os.getenv("VAULT_PATH", ""))
claude_md_path = VAULT_PATH / "CLAUDE.md"
instructions = claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""

mcp = FastMCP("vault-mcp", instructions=instructions)

@mcp.tool()
async def list_folders() -> dict:
    """Returns the full folder tree of the vault."""
    # implementation
```

**Key:** `instructions` is a supported constructor parameter on `mcp.server.fastmcp.FastMCP`. [CITED: gofastmcp.com/servers/server]

### Pattern 2: Bearer Auth Middleware (Single Enforcement Point)

**What:** FastAPI `BaseHTTPMiddleware` intercepts all requests before MCP processes them. Returns 401 with error dict on failure. Bypasses `/authorize` and `/token` (these are the auth flow itself).

**When to use:** Wrap the entire FastAPI app; applies to every route including the streamable-HTTP MCP mount.

```python
# Source: FastAPI middleware docs [CITED: fastapi.tiangolo.com/tutorial/middleware/]
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import os

VAULT_SECRET = os.getenv("VAULT_SECRET", "")
OAUTH_BYPASS_PATHS = {"/authorize", "/token"}

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in OAUTH_BYPASS_PATHS:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != VAULT_SECRET:
            return JSONResponse(
                status_code=401,
                content={"error": True, "message": "Unauthorized", "code": "AUTH_ERROR"}
            )
        return await call_next(request)

# Mount order: middleware added BEFORE mount
mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")
app = FastAPI(lifespan=mcp_app.lifespan)
app.add_middleware(BearerAuthMiddleware)
app.mount("/mcp", mcp_app)
```

**Caution:** When mounting an MCP app, middleware must be added to the outer `FastAPI` app BEFORE `app.mount(...)`. The `lifespan=mcp_app.lifespan` parameter is required so the MCP session manager initializes.

### Pattern 3: MCP Streamable-HTTP Transport Mount

**What:** Mount the MCP server's streamable-HTTP app onto the FastAPI app. Exposes a single `/mcp` endpoint that handles initialization, tool listing, and tool calls.

**When to use:** Phase 1 uses streamable-HTTP (per D-05). This is the current MCP-spec-recommended transport (SSE is deprecated).

```python
# Source: official MCP SDK docs [CITED: modelcontextprotocol.io/docs/develop/build-server]
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI

mcp = FastMCP("vault-mcp", instructions=instructions)
mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")
app = FastAPI(lifespan=mcp_app.lifespan)
app.add_middleware(BearerAuthMiddleware)  # added BEFORE mounting
app.mount("/mcp", mcp_app)                # streamable-HTTP exposed at /mcp
```

**Note:** Only the documented form `mcp.http_app(path='/mcp', transport='streamable-http')` is used. Earlier drafts of this research speculated about an alternate `mcp.streamable_http_app()` shortcut method, but it is not documented in the MCP SDK and is not used by the plan.

### Pattern 4: OAuth 2.0 Authorization Code + PKCE (D-16)

**What:** Implement `/authorize` (issues single-use code) and `/token` (exchanges code+PKCE verifier for access token) endpoints. Access token is `VAULT_SECRET`.

**When to use:** Required by claude.ai mobile/web connector UI, which does not accept static bearer tokens.

```python
# Source: RFC 7636 (PKCE) + standard OAuth 2.0 Authorization Code flow
import secrets, hashlib, base64, time
from fastapi import FastAPI, Form, Request
from starlette.responses import RedirectResponse, JSONResponse

_pkce_codes: dict[str, dict] = {}  # in-memory single-use code store

@app.get("/authorize")
async def authorize(request: Request):
    params = request.query_params
    if params.get("response_type") != "code":
        return JSONResponse(status_code=400, content=err("invalid response_type", "AUTH_ERROR"))
    if params.get("client_id") != os.environ["OAUTH_CLIENT_ID"]:
        return JSONResponse(status_code=400, content=err("invalid client_id", "AUTH_ERROR"))
    if params.get("redirect_uri") != os.environ["OAUTH_REDIRECT_URI"]:
        return JSONResponse(status_code=400, content=err("invalid redirect_uri", "AUTH_ERROR"))
    if not params.get("code_challenge") or params.get("code_challenge_method") != "S256":
        return JSONResponse(status_code=400, content=err("PKCE required (S256)", "AUTH_ERROR"))
    code = secrets.token_urlsafe(32)
    _pkce_codes[code] = {
        "challenge": params["code_challenge"],
        "client_id": params["client_id"],
        "redirect_uri": params["redirect_uri"],
        "used": False,
        "issued_at": time.time(),
    }
    state = params.get("state", "")
    return RedirectResponse(url=f"{params['redirect_uri']}?code={code}&state={state}", status_code=302)

@app.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    code_verifier: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
):
    if grant_type != "authorization_code" or code not in _pkce_codes:
        return JSONResponse(status_code=400, content=err("invalid grant", "AUTH_ERROR"))
    entry = _pkce_codes[code]
    if entry["used"] or entry["client_id"] != client_id or entry["redirect_uri"] != redirect_uri:
        return JSONResponse(status_code=400, content=err("invalid grant", "AUTH_ERROR"))
    expected = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    if expected != entry["challenge"]:
        return JSONResponse(status_code=400, content=err("PKCE verification failed", "AUTH_ERROR"))
    entry["used"] = True
    return JSONResponse(status_code=200, content={
        "access_token": VAULT_SECRET, "token_type": "Bearer", "expires_in": 3600
    })
```

**Key:** `/authorize` and `/token` must be registered BEFORE `app.mount("/mcp", ...)` and bypassed by `BearerAuthMiddleware`.

### Pattern 5: python-frontmatter Read/Write Cycle

**What:** Load a markdown file with YAML frontmatter, access metadata dict, modify, write back.

**When to use:** Every tool that reads or modifies note frontmatter (`get_note_metadata`, `update_frontmatter`, `create_note`, `prepend_to_note`).

```python
# Source: python-frontmatter docs [CITED: python-frontmatter.readthedocs.io]
import frontmatter

# Load (returns Post object with .metadata dict and .content str)
post = frontmatter.load(str(note_path))
title = post.get("title", "")
post["tags"] = ["ml", "nlp"]         # update key

# Write back
with open(str(note_path), "w", encoding="utf-8") as f:
    frontmatter.dump(post, f)
```

**Important:** `import frontmatter` (not `import python_frontmatter`). The installed package name is `python-frontmatter` but the module is `frontmatter`. [CITED: pypi.org/project/python-frontmatter/]

### Pattern 6: Heading-Based Section Operations

**What:** Parse markdown headings, extract section content between target heading and next same-or-higher-level heading, or insert text at end of section.

**When to use:** `read_note_section()`, `insert_under_heading()`.

```python
# [ASSUMED] — standard markdown parsing approach
import re

def get_sections(content: str) -> list[dict]:
    """Returns list of {heading, level, start_line, end_line}"""
    lines = content.split("\n")
    sections = []
    heading_re = re.compile(r'^(#{1,6})\s+(.+)')
    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if m:
            sections.append({
                "heading": m.group(2).strip(),
                "level": len(m.group(1)),
                "start": i
            })
    return sections

def find_heading(sections: list, target: str) -> int | None:
    """Case-insensitive partial match; returns section index."""
    target_lower = target.lower()
    for i, s in enumerate(sections):
        if target_lower in s["heading"].lower():
            return i
    return None
```

### Anti-Patterns to Avoid

- **Raising HTTPException inside MCP tools:** D-08 mandates returning error dicts. HTTPException is for FastAPI routes, not MCP tools. An unhandled exception in a tool function will surface as an MCP protocol error to the client, not a clean dict.
- **Using `fastapi-mcp` (tadata package) for this project:** That library converts FastAPI routes into MCP tools. This project has no HTTP routes — all functionality is direct file access. Using `fastapi-mcp` would require wrapping every tool as a FastAPI endpoint first, adding unnecessary indirection. (D-05 / Open Question 1 RESOLVED.)
- **Using SSE transport:** Deprecated in MCP spec (March 2025). Use streamable-HTTP. (Open Question 3 RESOLVED.)
- **Calling speculative/undocumented MCP SDK methods (e.g., `mcp.streamable_http_app()`):** Only the documented `mcp.http_app(path='/mcp', transport='streamable-http')` is used.
- **Reading CLAUDE.md from vault on every tool call:** Read once at startup and pass to FastMCP constructor. Re-reading per request adds I/O overhead and risk if the file is temporarily missing.
- **Constructing file paths from raw user input without validation:** `INVALID_PATH` error code exists for a reason. Validate that all paths stay within `VAULT_PATH` boundaries to prevent path traversal.
- **Modifying files under `raw/`:** The vault rules explicitly make `raw/` immutable. Phase 1 tools operate only on `wiki/` and the vault root.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter parse/write | Custom regex YAML parser | `python-frontmatter` | YAML edge cases (multiline strings, null values, arrays) are non-trivial |
| MCP protocol layer | Raw streamable-HTTP endpoint + JSON-RPC handler | `mcp.server.fastmcp.FastMCP` | MCP protocol has initialization handshake, capability negotiation, schema generation — all handled by SDK |
| `.env` loading | `os.environ` manual parsing | `python-dotenv` | Handles quoting, comments, multi-line values |
| Tunnel management | Raw ngrok/SSH tunnel scripts | `cloudflared` binary | Cloudflare Tunnel is persistent, free, production-grade, no IP rotation |
| OAuth code generation / PKCE hashing | Custom token logic | `secrets` + `hashlib` + `base64` stdlib | Stdlib primitives are correct, safe, and audited |

**Key insight:** The MCP protocol layer in particular is non-trivial — tool schema generation from Python type hints, initialization negotiation, ping/pong keepalive, and the streamable-HTTP connection management are all handled by the SDK. Hand-rolling any of this would be weeks of work.

---

## Common Pitfalls

### Pitfall 1: Library Name Confusion — `fastapi-mcp` vs `mcp.server.fastmcp`

**What goes wrong:** Developer installs `fastapi-mcp` (tadata-org package) expecting to register custom tool functions, but finds it only converts FastAPI HTTP routes into MCP tools. The project cannot work this way.

**Why it happens:** D-05 originally said "use `fastapi-mcp` library" which is an ambiguous name. The official Anthropic `mcp` SDK contains a class also called `FastMCP` accessed as `from mcp.server.fastmcp import FastMCP`. **D-05 has been corrected to name the official `mcp` SDK explicitly** (see RESOLVED Open Question 1).

**How to avoid:** Install `mcp` (the official SDK), not `fastapi-mcp`. Use `from mcp.server.fastmcp import FastMCP`. [CITED: pypi.org/project/mcp/1.9.1/]

**Warning signs:** If you find yourself needing to define FastAPI route handlers (`@app.get(...)`) for each MCP tool (other than `/authorize` and `/token`), you're using the wrong library.

### Pitfall 2: Bearer Auth Middleware Does Not Protect MCP Mount

**What goes wrong:** Middleware is added to the outer FastAPI app, but the MCP streamable-HTTP app mounted with `app.mount()` may not route requests through the same middleware depending on mount order.

**Why it happens:** Starlette's `Mount` routing can bypass middleware if the mount is added before the middleware, or if the inner app is a full ASGI app with its own routing.

**How to avoid:** Add middleware to the FastAPI app BEFORE calling `app.mount()`. Test explicitly that a POST to `/mcp/` without a Bearer token returns 401. [ASSUMED — verify at integration test time]

### Pitfall 3: claude.ai Mobile Requires OAuth (not Bearer)

**What goes wrong:** Without OAuth, the claude.ai web/mobile connector cannot complete a handshake — it only accepts OAuth 2.0 or no auth in the connector UI. Static bearer tokens are not supported in the connector UI as of May 2026.

**Why it happens:** claude.ai's MCP connector specification prohibits credentials in query params and only supports OAuth or no auth for the web connector UI. [CITED: claude.com/docs/connectors/building/authentication]

**How to avoid:** Implement OAuth 2.0 Authorization Code + PKCE in Phase 1 (D-16; RESOLVED Open Question 2). The `/token` endpoint can return `VAULT_SECRET` as the access token — this is fine because the system is single-user.

**Warning signs:** If you skip OAuth and configure the Cloudflare Tunnel URL in the claude.ai connector UI, the connector will reject the setup or return auth errors regardless of the bearer token.

### Pitfall 4: `python-frontmatter` Module Name vs Package Name

**What goes wrong:** `import python_frontmatter` raises `ModuleNotFoundError`. The pip install is `pip install python-frontmatter` but the Python import is `import frontmatter`.

**Why it happens:** PyPI package name and Python module name differ by design.

**How to avoid:** Always use `import frontmatter` (no `python_` prefix). [CITED: pypi.org/project/python-frontmatter/]

### Pitfall 5: Concurrent Writes to vault files

**What goes wrong:** Two simultaneous tool calls (e.g., `append_to_note` and `update_frontmatter` on the same file) can interleave, producing corrupt markdown.

**Why it happens:** Phase 1 is a single-user tool and the risk is low but non-zero during testing. There is no file locking by default.

**How to avoid:** For Phase 1, document that concurrent writes are not safe. Add `asyncio.Lock` per note path if needed. A simple global `asyncio.Lock` (or per-path lock dict) suffices for single-user use. [ASSUMED — implementation detail]

### Pitfall 6: PM2 Python Process Requires Explicit Interpreter Path

**What goes wrong:** `pm2 start server.py` fails because PM2 cannot find the Python interpreter, or picks the wrong Python version.

**Why it happens:** PM2 defaults to Node.js. For Python, you must specify `interpreter` and `script` explicitly.

**How to avoid:** In `ecosystem.config.js`, set `script: "uvicorn"`, `args: "server:app --host 0.0.0.0 --port 8000"`, `interpreter: "none"` (if uvicorn is on PATH), or use `script: "/path/to/venv/bin/uvicorn"` for virtualenv. [ASSUMED]

---

## Code Examples

### MCP Server Bootstrap (server.py top section)

```python
# Source: official MCP SDK docs [CITED: modelcontextprotocol.io/docs/develop/build-server]
#         FastAPI middleware docs [CITED: fastapi.tiangolo.com/tutorial/middleware/]
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

VAULT_PATH = Path(os.environ["VAULT_PATH"])
VAULT_SECRET = os.environ["VAULT_SECRET"]
OAUTH_CLIENT_ID = os.environ["OAUTH_CLIENT_ID"]
OAUTH_REDIRECT_URI = os.environ["OAUTH_REDIRECT_URI"]

# Load CLAUDE.md as MCP instructions
claude_md = (VAULT_PATH / "CLAUDE.md")
instructions = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""

# Initialize MCP server
mcp = FastMCP("vault-mcp", instructions=instructions)

# Auth middleware
OAUTH_BYPASS_PATHS = {"/authorize", "/token"}

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in OAUTH_BYPASS_PATHS:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != VAULT_SECRET:
            return JSONResponse(
                status_code=401,
                content={"error": True, "message": "Unauthorized", "code": "AUTH_ERROR"}
            )
        return await call_next(request)

mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")
app = FastAPI(lifespan=mcp_app.lifespan)
app.add_middleware(BearerAuthMiddleware)
# /authorize and /token routes registered here (see Pattern 4)
app.mount("/mcp", mcp_app)
```

### Error Response Pattern (D-08)

```python
# [ASSUMED] — consistent with D-08 spec
def not_found(msg: str) -> dict:
    return {"error": True, "message": msg, "code": "NOT_FOUND"}

def already_exists(path: str) -> dict:
    return {"error": True, "message": f"Note already exists: {path}", "code": "ALREADY_EXISTS"}

def invalid_path(path: str) -> dict:
    return {"error": True, "message": f"Path outside vault or invalid: {path}", "code": "INVALID_PATH"}

def heading_not_found(heading: str, available: list[str]) -> dict:
    return {
        "error": True,
        "message": f"Heading not found: {heading}",
        "code": "HEADING_NOT_FOUND",
        "available_headings": available
    }
```

### init_vault.py Skeleton

```python
# [ASSUMED] — derived from PRD §3 format specs
from pathlib import Path
from datetime import date
import os, shutil

VAULT_PATH = Path(os.environ["VAULT_PATH"])

DIRS = [
    "raw/webpages", "raw/transcripts", "raw/videos",
    "raw/documents", "raw/assets", "raw/sources",
    "wiki/entities", "wiki/concepts", "wiki/sources", "wiki/queries"
]

INDEX_SEED = f"""# Vault Index
Last updated: {date.today()} | Total pages: 0 | Total sources: 0

## Entities

## Concepts

## Sources

## Queries
"""

LOG_SEED = f"""# Vault Log
"""

VAULT_PATH.mkdir(parents=True, exist_ok=False)
for d in DIRS:
    (VAULT_PATH / d).mkdir(parents=True, exist_ok=True)

(VAULT_PATH / "wiki" / "index.md").write_text(INDEX_SEED, encoding="utf-8")
(VAULT_PATH / "wiki" / "log.md").write_text(LOG_SEED, encoding="utf-8")

# Copy CLAUDE.md from project root into vault
src_claude = Path(__file__).parent / "CLAUDE.md"
if src_claude.exists():
    shutil.copy(src_claude, VAULT_PATH / "CLAUDE.md")
```

### Cloudflare Tunnel Config Template

```yaml
# ~/.cloudflared/config.yml (generated by setup.sh)
# Source: Cloudflare Tunnel docs [CITED: developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/]
tunnel: <TUNNEL-UUID>
credentials-file: /Users/<USER>/.cloudflared/<TUNNEL-UUID>.json
ingress:
  - hostname: vault.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

### ecosystem.config.js

```javascript
// [ASSUMED] — derived from PM2 docs [CITED: pm2.keymetrics.io/docs/usage/application-declaration/]
// and PRD §6.5 process names
module.exports = {
  apps: [
    {
      name: "vault-mcp",
      script: "uvicorn",
      args: "server:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      cwd: "/path/to/project",   // set to actual project dir in setup.sh
      autorestart: true,
      max_restarts: 10,
      restart_delay: 4000,
      env: {
        // VAULT_SECRET, VAULT_PATH, OAUTH_* loaded from .env by dotenv in server.py
      }
    },
    {
      name: "cloudflare-tunnel",
      script: "cloudflared",
      args: "tunnel run vault",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 4000
    }
  ]
};
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSE transport (HTTP+SSE) | Streamable HTTP transport | MCP spec 2025-03-26 | SSE is deprecated; HTTP streamable is the new standard. Phase 1 uses streamable-HTTP. |
| `fastmcp` (standalone package v1) | `mcp.server.fastmcp.FastMCP` (built into `mcp` SDK) | Mid-2024 | FastMCP v1 was absorbed into the official SDK. No separate install needed. |
| `mount()` (fastapi-mcp) | `mount_http()` / `mount_sse()` | fastapi-mcp 0.3+ | Irrelevant to this project — `fastapi-mcp` is not used. |

**Deprecated/outdated:**
- `fastmcp` standalone package: Superseded by `mcp.server.fastmcp` in the official `mcp` SDK. FastMCP 2.x is a separate project (`pip install fastmcp`) that is a superset of v1 with more features — both are valid.
- SSE as primary transport: Deprecated in MCP spec. Phase 1 uses streamable-HTTP only.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `fastapi` latest version is ~0.136.x; PRD pins 0.111.0 which still works but is several releases behind | Standard Stack | Pinned version works fine; this only matters if specific newer API features are needed |
| A2 | Bearer auth middleware applies to the mounted MCP streamable-HTTP sub-app when middleware is added before mount | Architecture Patterns / Pitfall 2 | If wrong, MCP endpoints would be unauthenticated; requires integration test to verify |
| A3 | Using `mcp.http_app(path='/mcp', transport='streamable-http')` with `app.mount("/mcp", ...)` and `lifespan=mcp_app.lifespan` works without session manager issues | Code Examples | If wrong, server may fail to initialize session manager; lifespan param mitigates this |
| A4 | PM2 `ecosystem.config.js` with `interpreter: "none"` and `script: "uvicorn"` works when uvicorn is on PATH | Code Examples | If uvicorn is in a venv not on PATH, PM2 cannot start the process |
| A5 | All listed packages are legitimate (not slopcheck-flagged) — slopcheck was unavailable | Package Legitimacy Audit | All are well-known packages with years of history; risk is very low |
| A6 | `insert_under_heading()` error dict should include `available_headings` field (per PRD §5.3 + D-08) | Architecture Patterns | CONTEXT.md §Specifics explicitly states this; very low risk |
| A7 | `update_index()` should use upsert logic (update existing entry if path matches, insert if new) | Claude's Discretion area | Duplicates would corrupt index if error-on-duplicate is used; upsert is safer default |
| A8 | In-memory `_pkce_codes` dict is acceptable for single-user OAuth (no DB) | Pattern 4 / D-16 | Codes are single-use and short-lived; restart drops in-flight codes (acceptable) |

---

## Open Questions (RESOLVED)

> All three originally open questions have been **RESOLVED** by direct user confirmation during the planning session on 2026-05-29. The resolutions are now reflected in CONTEXT.md D-05, D-16, and the patterns above.

1. **D-05 library clarification: `fastapi-mcp` (tadata) vs `mcp.server.fastmcp`** — **RESOLVED**
   - **Resolution:** Use the official `mcp` SDK (`pip install mcp`). Import as `from mcp.server.fastmcp import FastMCP`. The `fastapi-mcp` (tadata) package is NOT used because it only exposes existing FastAPI routes as MCP tools and cannot register the 14 custom file-operation functions this project needs.
   - **Where reflected:** CONTEXT.md D-05 (rewritten); Pattern 3; Standard Stack; Pitfall 1.

2. **Claude.ai mobile auth gap** — **RESOLVED**
   - **Resolution:** Implement OAuth 2.0 Authorization Code + PKCE (S256) in Phase 1 to enable claude.ai mobile. `/token` returns `VAULT_SECRET` as `access_token` — sufficient for a single-user system. Two env vars (`OAUTH_CLIENT_ID`, `OAUTH_REDIRECT_URI`) are added.
   - **Where reflected:** CONTEXT.md D-16 (new); CONTEXT.md D-02 (env vars expanded); Pattern 4; Pitfall 3; Architectural Responsibility Map.

3. **Transport: SSE vs streamable-HTTP** — **RESOLVED**
   - **Resolution:** Implement streamable-HTTP transport using `mcp.http_app(path='/mcp', transport='streamable-http')`. SSE is deprecated in the MCP spec (March 2025) and is NOT used. Starting on streamable-HTTP avoids a Phase 2 migration.
   - **Where reflected:** CONTEXT.md D-05 (rewritten); INFRA-01 (updated in REQUIREMENTS.md); Pattern 3; State of the Art.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Runtime | ✓ | 3.12.13 | — |
| npm / Node.js | PM2 install | ✓ | Node 22.22.2 / npm 10.9.7 | — |
| Homebrew | cloudflared install | ✓ | found at /opt/homebrew/bin/brew | — |
| uvicorn | Dev/prod server | ✗ | — | Install via `pip install uvicorn[standard]` in requirements.txt |
| PM2 | Process manager | ✗ | — | Install via `npm install -g pm2` (node available) |
| cloudflared | Tunnel | ✗ | — | Install via `brew install cloudflared` |
| pip (system-wide) | Package install | ✗ (externally-managed) | — | Use virtualenv or `pip install --break-system-packages` |

**Missing dependencies with no fallback:** None — all have clear install paths.

**Missing dependencies with fallback:**
- `uvicorn`, `mcp`, `fastapi`, and all Python deps: require virtual environment setup (`python3 -m venv .venv && source .venv/bin/activate`) since system Python is externally managed (macOS).
- `pm2`: requires `npm install -g pm2`; Node.js is available at v22.
- `cloudflared`: requires `brew install cloudflared`; Homebrew is available.

**Critical setup step:** The project must use a Python virtual environment (`python3 -m venv .venv`) because the system Python is externally managed. `setup.sh` must include venv creation and activation. The PM2 `ecosystem.config.js` must reference the full virtualenv path for uvicorn (e.g., `.venv/bin/uvicorn`).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` + `httpx` (async test client) |
| Config file | `pyproject.toml [tool.pytest]` — created by Plan 01-02 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Server starts on port 8000 and responds to MCP init | smoke | `pytest tests/test_infra.py::test_server_starts -x` | created in 01-03 |
| INFRA-02 | Missing/wrong bearer token returns 401 | unit | `pytest tests/test_auth.py::test_bearer_auth -x` | created in 01-03 |
| INFRA-05 | MCP instructions field contains CLAUDE.md content | unit | `pytest tests/test_infra.py::test_instructions_injected -x` | created in 01-03 |
| NAV-01 | `list_folders()` returns folder list with note counts | unit | `pytest tests/test_nav.py::test_list_folders -x` | created in 01-04 |
| NAV-02 | `list_notes(folder)` returns metadata for notes | unit | `pytest tests/test_nav.py::test_list_notes -x` | created in 01-04 |
| NAV-03 | `get_note_metadata()` returns frontmatter without body | unit | `pytest tests/test_nav.py::test_get_note_metadata -x` | created in 01-04 |
| NAV-04 | `get_index()` reads wiki/index.md content | unit | `pytest tests/test_nav.py::test_get_index -x` | created in 01-04 |
| RET-01 | `search_full_text()` returns ranked snippets | unit | `pytest tests/test_retrieval.py::test_search -x` | created in 01-05 |
| RET-02 | `get_note_summary()` returns first 200 chars + headings | unit | `pytest tests/test_retrieval.py::test_get_note_summary -x` | created in 01-05 |
| RET-03 | `read_note()` returns full content + frontmatter | unit | `pytest tests/test_retrieval.py::test_read_note -x` | created in 01-05 |
| RET-04 | `read_note_section()` returns single section content | unit | `pytest tests/test_retrieval.py::test_read_note_section -x` | created in 01-05 |
| INGEST-01 | `create_note()` creates file, fails if exists | unit | `pytest tests/test_ingestion.py::test_create_note -x` | created in 01-06 |
| INGEST-02 | `append_to_note()` appends text | unit | `pytest tests/test_ingestion.py::test_append_to_note -x` | created in 01-06 |
| INGEST-03 | `prepend_to_note()` inserts after frontmatter | unit | `pytest tests/test_ingestion.py::test_prepend_to_note -x` | created in 01-06 |
| INGEST-04 | `insert_under_heading()` inserts under correct section | unit | `pytest tests/test_ingestion.py::test_insert_under_heading -x` | created in 01-06 |
| INGEST-05 | `update_frontmatter()` updates key without touching body | unit | `pytest tests/test_ingestion.py::test_update_frontmatter -x` | created in 01-06 |
| MAINT-01 | `update_index()` upserts entry in wiki/index.md | unit | `pytest tests/test_maintenance.py::test_update_index -x` | created in 01-07 |
| MAINT-02 | `append_log()` appends timestamped entry to log.md | unit | `pytest tests/test_maintenance.py::test_append_log -x` | created in 01-07 |
| INFRA-03 | Cloudflare Tunnel accessible from external URL | manual | N/A — requires live cloudflared + DNS | Manual only |
| INFRA-04 | PM2 auto-restarts server on crash | manual | N/A — requires live PM2 session | Manual only |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q --ignore=tests/test_infra.py`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Scope (clarified)

Plan 01-02 (Wave 1) establishes Wave 0 test infrastructure:

- [ ] `tests/conftest.py` — shared `tmp_vault` fixture (creates temp dir, seeds index.md + log.md)
- [ ] `tests/test_smoke.py` — single sanity test that conftest + pytest discovery work
- [ ] `pyproject.toml` `[tool.pytest]` config block + framework install (`pytest`, `pytest-asyncio`, `httpx`)

The per-tool test files (`test_auth.py`, `test_infra.py`, `test_nav.py`, `test_retrieval.py`, `test_ingestion.py`, `test_maintenance.py`, `test_oauth.py`) are created in their respective implementation plans (01-03 through 01-07) using TDD: tests are written first, then the implementation makes them pass. See `01-VALIDATION.md` for the per-plan ownership map.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Bearer token middleware (VAULT_SECRET env var) + OAuth 2.0 PKCE wrapper |
| V3 Session Management | no | Stateless MCP protocol; no sessions |
| V4 Access Control | yes | Single user; bearer token / OAuth-issued access token is the only access gate |
| V5 Input Validation | yes | Validate all `path` parameters stay within VAULT_PATH |
| V6 Cryptography | no | Bearer token is a shared secret, not crypto — acceptable for single-user personal tool. PKCE S256 uses stdlib hashlib. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `path` parameter | Tampering | `Path(VAULT_PATH / path).resolve().is_relative_to(VAULT_PATH)` check in every tool |
| Missing/invalid Authorization header | Spoofing | BearerAuthMiddleware returns 401 before any tool executes |
| OAuth code replay | Tampering | `_pkce_codes` tracks `used` flag; reuse rejected at /token |
| OAuth code substitution without PKCE verifier | Tampering | S256 challenge/verifier hash comparison at /token |
| Raw VAULT_SECRET in logs | Information Disclosure | Never log the `Authorization` header value |
| Vault `raw/` directory modification | Tampering | Tool implementations must refuse paths starting with `raw/` |

---

## Sources

### Primary (HIGH confidence)
- `pypi.org/project/mcp/1.9.1/` — confirmed mcp SDK version, official Anthropic package
- `modelcontextprotocol.io/docs/develop/build-server` — FastMCP tool registration, instructions param, streamable-HTTP mount
- `gofastmcp.com/servers/server` — FastMCP constructor signature with `instructions` parameter
- `python-frontmatter.readthedocs.io` — frontmatter.load/dump API, module name
- `developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/` — cloudflared commands
- `pm2.keymetrics.io/docs/usage/application-declaration/` — ecosystem.config.js format
- `fastapi.tiangolo.com/tutorial/middleware/` — BaseHTTPMiddleware pattern
- `datatracker.ietf.org/doc/html/rfc7636` — PKCE S256 specification
- `claude.com/docs/connectors/building/authentication` — bearer token auth not supported on claude.ai; OAuth required

### Secondary (MEDIUM confidence)
- `fastapi-mcp.tadata.com/getting-started/FAQ` — confirmed fastapi-mcp only supports route-based tools
- `snyk.io/advisor/python/python-frontmatter` — download stats 111K/wk, 8yr old package
- `github.com/anthropics/claude-ai-mcp/issues/112` — bearer token not supported in claude.ai UI

### Tertiary (LOW confidence)
- Various WebSearch results about PM2 Python ecosystem config (exact `interpreter: "none"` syntax unverified)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — mcp SDK and transport confirmed via official docs; user-resolved naming question
- Architecture: HIGH — patterns derived from official docs and confirmed examples
- Pitfalls: HIGH — bearer auth/claude.ai gap confirmed by official Anthropic docs; library confusion confirmed by tadata FAQ; OAuth flow confirmed against RFC 7636

**Research date:** 2026-05-29
**Last revised:** 2026-05-29 (Open Questions resolved by user; D-05/D-16 reflected throughout)
**Valid until:** 2026-07-29 (60 days — MCP ecosystem is fast-moving; check transport spec changes)
