# Phase 1: Core MCP Server - Research

**Researched:** 2026-05-29
**Domain:** FastAPI + MCP SSE/HTTP transport + Cloudflare Tunnel + Obsidian vault file operations
**Confidence:** MEDIUM-HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single flat `server.py` monolith — all tools in one file. No `app/` package. No subdirectories for tool categories.
- **D-02:** Configuration via `.env` file using `python-dotenv`. Two required env vars: `VAULT_SECRET` (bearer token) and `VAULT_PATH` (absolute path to vault directory).
- **D-03:** Dev command: `uvicorn server:app --reload`. PM2 wraps the same command in production.
- **D-04:** Root files: `server.py`, `.env` (gitignored), `requirements.txt`, `README.md`, `ecosystem.config.js`, `init_vault.py`, `setup.sh`.
- **D-05:** Use `fastapi-mcp` library to mount the MCP server onto the FastAPI app. Handles SSE routing automatically.
- **D-06:** Bearer auth enforced via FastAPI middleware on all routes. Reads `Authorization: Bearer <token>`, compares to `VAULT_SECRET`. Single enforcement point.
- **D-07:** Vault rules document is named `CLAUDE.md`. Its content is injected as the MCP server's `instructions` field on startup.
- **D-08:** All tool errors return `{"error": true, "message": "...", "code": "NOT_FOUND"}`. Codes: `NOT_FOUND`, `ALREADY_EXISTS`, `INVALID_PATH`, `HEADING_NOT_FOUND`, `AUTH_ERROR`. Never raise HTTPException from tool functions.
- **D-09:** Phase 1 delivers: `setup.sh` (creates Cloudflare tunnel, generates `~/.cloudflared/config.yml` template), `ecosystem.config.js` (PM2 starts both `vault-mcp` and `cloudflare-tunnel` with auto-restart), README section for DNS + dashboard steps.
- **D-10:** `init_vault.py` creates a fresh vault at `VAULT_PATH` — full directory structure, seeds `wiki/index.md` and `wiki/log.md`, copies `CLAUDE.md` into vault root.
- **D-11:** `VAULT_PATH` points to a new directory — `init_vault.py` creates it from scratch.
- **D-12:** Naive search scoring: `score = occurrence_count / max_occurrences_across_results`. Produces 0–1 float. Single result scores 1.0.
- **D-13:** Search is case-insensitive (`query.lower() in line.lower()`), scans full file including YAML frontmatter.
- **D-14:** Search scope: `wiki/` subdirectory only. Raw sources excluded.
- **D-15:** Snippet: 2-line window (~150 chars) centered on first occurrence of query in file.

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
| INFRA-01 | FastAPI server serves MCP tools over SSE transport on port 8000 | MCP SDK `FastMCP.sse_app()` or `http_app(transport="streamable-http")` mounted to FastAPI |
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

Phase 1 builds a greenfield FastAPI server that exposes a set of Obsidian vault read/write operations as MCP tools, secured by bearer auth, with a Cloudflare Tunnel providing a persistent HTTPS endpoint. The MCP Python SDK (`mcp` package) is the correct tool: `mcp.server.fastmcp.FastMCP` provides the `@mcp.tool()` decorator for custom tool registration, the `instructions` constructor parameter for injecting `CLAUDE.md` as the system prompt, and `.sse_app()` / `.http_app()` methods for mounting to a FastAPI app.

A critical finding: D-05 names `fastapi-mcp` (the tadata-org package), but that library exclusively exposes FastAPI HTTP routes as MCP tools — it cannot register custom functions directly. For a vault with 14 custom tools that read/write files, the correct library is `mcp.server.fastmcp.FastMCP` from the official `mcp` SDK (pip package: `mcp`). The planner must resolve this naming discrepancy with the user before implementation.

A second critical finding: the primary use case (Claude on phone via claude.ai mobile/web) requires OAuth for remote MCP servers — claude.ai's connector does not support static bearer tokens as of May 2026. For Claude Desktop on localhost this is not an issue. This is a known limitation that should be flagged explicitly.

**Primary recommendation:** Use `from mcp.server.fastmcp import FastMCP` (official MCP SDK) for custom tool definitions, mount via `.sse_app()` onto a FastAPI app that runs bearer auth middleware, and document the claude.ai OAuth gap prominently in the README.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MCP tool registration & protocol | MCP SDK (FastMCP) | — | FastMCP owns the MCP protocol layer |
| Bearer auth enforcement | FastAPI middleware | — | Middleware executes before MCP receives any request |
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
| `mcp` | 1.9.1 (current) [VERIFIED: PyPI search] | MCP protocol — tools, SSE/HTTP transport, instructions | Official Anthropic SDK; `FastMCP` class provides decorator-based tool registration and `instructions` field |
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

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `mcp.server.fastmcp.FastMCP` | `fastapi-mcp` (tadata) | `fastapi-mcp` only exposes FastAPI routes — cannot register custom functions; wrong tool for this project |
| `mcp.server.fastmcp.FastMCP` | `fastmcp` (standalone package) | `fastmcp` is the standalone FastMCP 2.x library; `mcp.server.fastmcp` ships the v1-compatible FastMCP inside the official SDK — either works, but the official SDK is the locked dependency |
| SSE transport (`.sse_app()`) | Streamable-HTTP (`http_app(transport="streamable-http")`) | SSE is deprecated in MCP spec (March 2025); streamable-HTTP is the current standard. Both work today. For Claude Desktop, both work. For claude.ai mobile web, neither works with simple bearer auth (OAuth required). |
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
     └── mount mcp.sse_app() → FastAPI app

  request flow (per tool call)
     │
     ▼
  Cloudflare Tunnel (HTTPS) → localhost:8000
     │
     ▼
  FastAPI BaseHTTPMiddleware
     │  checks Authorization: Bearer <token> == VAULT_SECRET
     │  returns 401 {"error":true,...} on mismatch
     ▼
  MCP SSE transport layer  (/sse, /messages)
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
├── server.py              # Single monolith — FastAPI app + all MCP tools
├── init_vault.py          # One-shot vault scaffolding script
├── setup.sh               # cloudflared tunnel create + config.yml template
├── ecosystem.config.js    # PM2 config: vault-mcp + cloudflare-tunnel processes
├── requirements.txt       # Phase 1 pip deps
├── .env                   # VAULT_SECRET + VAULT_PATH (gitignored)
└── README.md              # Setup walkthrough + DNS steps
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

**What:** FastAPI `BaseHTTPMiddleware` intercepts all requests before MCP processes them. Returns 401 with error dict on failure.

**When to use:** Wrap the entire FastAPI app; applies to every route including SSE and messages endpoints.

```python
# Source: FastAPI middleware docs [CITED: fastapi.tiangolo.com/tutorial/middleware/]
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import os

VAULT_SECRET = os.getenv("VAULT_SECRET", "")

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != VAULT_SECRET:
            return JSONResponse(
                status_code=401,
                content={"error": True, "message": "Unauthorized", "code": "AUTH_ERROR"}
            )
        return await call_next(request)

app = FastAPI()
app.add_middleware(BearerAuthMiddleware)
app.mount("/", mcp.sse_app())
```

**Caution:** When using `mcp.sse_app()` mounted at root `/`, middleware must be added to the outer `FastAPI` app, not the Starlette app returned by `.sse_app()`. [ASSUMED]

### Pattern 3: MCP SSE Transport Mount

**What:** Mount MCP server's SSE app onto the FastAPI app. This exposes `/sse` (connection endpoint) and `/messages` (message posting endpoint).

**When to use:** Phase 1 uses SSE (per D-05/D-06). Transport is functional but deprecated in MCP spec — plan migration to streamable-HTTP in Phase 2 or later.

```python
# Source: ragie.ai SSE+FastAPI example [CITED], gofastmcp.com [CITED]
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI

mcp = FastMCP("vault-mcp", instructions=instructions)
app = FastAPI()
app.add_middleware(BearerAuthMiddleware)  # added BEFORE mounting
app.mount("/", mcp.sse_app())            # SSE at /sse and /messages/
```

**Alternative (if migrating to streamable-HTTP):**
```python
# [ASSUMED] — streamable-http mount pattern
mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")
app = FastAPI(lifespan=mcp_app.lifespan)
app.add_middleware(BearerAuthMiddleware)
app.mount("/mcp", mcp_app)
```

### Pattern 4: python-frontmatter Read/Write Cycle

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

### Pattern 5: Heading-Based Section Operations

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
- **Using `fastapi-mcp` (tadata package) for this project:** That library converts FastAPI routes into MCP tools. This project has no HTTP routes — all functionality is direct file access. Using `fastapi-mcp` would require wrapping every tool as a FastAPI endpoint first, adding unnecessary indirection.
- **Reading CLAUDE.md from vault on every tool call:** Read once at startup and pass to FastMCP constructor. Re-reading per request adds I/O overhead and risk if the file is temporarily missing.
- **Constructing file paths from raw user input without validation:** `INVALID_PATH` error code exists for a reason. Validate that all paths stay within `VAULT_PATH` boundaries to prevent path traversal.
- **Modifying files under `raw/`:** The vault rules explicitly make `raw/` immutable. Phase 1 tools operate only on `wiki/` and the vault root.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter parse/write | Custom regex YAML parser | `python-frontmatter` | YAML edge cases (multiline strings, null values, arrays) are non-trivial |
| MCP protocol layer | Raw SSE endpoint + JSON-RPC handler | `mcp.server.fastmcp.FastMCP` | MCP protocol has initialization handshake, capability negotiation, schema generation — all handled by SDK |
| `.env` loading | `os.environ` manual parsing | `python-dotenv` | Handles quoting, comments, multi-line values |
| Tunnel management | Raw ngrok/SSH tunnel scripts | `cloudflared` binary | Cloudflare Tunnel is persistent, free, production-grade, no IP rotation |

**Key insight:** The MCP protocol layer in particular is non-trivial — tool schema generation from Python type hints, initialization negotiation, ping/pong keepalive, and the SSE connection management are all handled by the SDK. Hand-rolling any of this would be weeks of work.

---

## Common Pitfalls

### Pitfall 1: Library Name Confusion — `fastapi-mcp` vs `mcp.server.fastmcp`

**What goes wrong:** Developer installs `fastapi-mcp` (tadata-org package) expecting to register custom tool functions, but finds it only converts FastAPI HTTP routes into MCP tools. The project cannot work this way.

**Why it happens:** D-05 says "use `fastapi-mcp` library" which is an ambiguous name. The official Anthropic `mcp` SDK contains a class also called `FastMCP` accessed as `from mcp.server.fastmcp import FastMCP`.

**How to avoid:** Install `mcp` (the official SDK), not `fastapi-mcp`. Use `from mcp.server.fastmcp import FastMCP`. [CITED: pypi.org/project/mcp/1.9.1/]

**Warning signs:** If you find yourself needing to define FastAPI route handlers (`@app.get(...)`) for each MCP tool, you're using the wrong library.

### Pitfall 2: Bearer Auth Middleware Does Not Protect MCP Messages Endpoint

**What goes wrong:** Middleware is added to the outer FastAPI app, but the MCP SSE app mounted with `app.mount()` may not route all POST requests through the same middleware depending on mount order.

**Why it happens:** Starlette's `Mount` routing can bypass middleware if the mount is added before the middleware, or if the inner app is a full ASGI app with its own routing.

**How to avoid:** Add middleware to the FastAPI app BEFORE calling `app.mount()`. Test explicitly that a POST to `/messages/` without a Bearer token returns 401. [ASSUMED — verify at integration test time]

### Pitfall 3: SSE Transport Deprecation Gap with Claude.ai Mobile

**What goes wrong:** The project is built for "Claude on phone" via claude.ai mobile, but claude.ai's remote MCP connector does not support static bearer tokens — it requires OAuth 2.0. The server works perfectly with Claude Desktop (localhost, no tunnel needed) and with the Claude Code CLI (which supports bearer tokens in config), but the claude.ai web/mobile connector path requires OAuth.

**Why it happens:** claude.ai's MCP connector specification prohibits credentials in query params and only supports OAuth or no auth for the web connector UI. Static bearer tokens are listed as "not yet supported" in Anthropic's own connector auth documentation. [CITED: claude.com/docs/connectors/building/authentication]

**How to avoid:** Document this limitation clearly in the README. For Phase 1, Claude Desktop is the primary test client. Claude on phone via claude.ai is a future OAuth-gated milestone. The bearer token approach is fully functional for Claude Desktop and API-level usage.

**Warning signs:** If you configure the Cloudflare Tunnel URL in the claude.ai connector UI and get an auth error even with the correct token, this is the root cause.

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

# Load CLAUDE.md as MCP instructions
claude_md = (VAULT_PATH / "CLAUDE.md")
instructions = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""

# Initialize MCP server
mcp = FastMCP("vault-mcp", instructions=instructions)

# Auth middleware
class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != VAULT_SECRET:
            return JSONResponse(
                status_code=401,
                content={"error": True, "message": "Unauthorized", "code": "AUTH_ERROR"}
            )
        return await call_next(request)

app = FastAPI()
app.add_middleware(BearerAuthMiddleware)
app.mount("/", mcp.sse_app())
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
        // VAULT_SECRET and VAULT_PATH loaded from .env by dotenv in server.py
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
| SSE transport (HTTP+SSE) | Streamable HTTP transport | MCP spec 2025-03-26 | SSE is deprecated; HTTP streamable is the new standard. SSE still works but plan migration. |
| `fastmcp` (standalone package v1) | `mcp.server.fastmcp.FastMCP` (built into `mcp` SDK) | Mid-2024 | FastMCP v1 was absorbed into the official SDK. No separate install needed. |
| `mount()` (fastapi-mcp) | `mount_http()` / `mount_sse()` | fastapi-mcp 0.3+ | The generic `mount()` method is deprecated in tadata's fastapi-mcp |

**Deprecated/outdated:**
- `fastmcp` standalone package: Superseded by `mcp.server.fastmcp` in the official `mcp` SDK. FastMCP 2.x is a separate project (`pip install fastmcp`) that is a superset of v1 with more features — both are valid.
- SSE as primary transport: Deprecated in MCP spec. Still functional, but new builds should prefer streamable-HTTP.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `fastapi` latest version is ~0.136.x; PRD pins 0.111.0 which still works but is several releases behind | Standard Stack | Pinned version works fine; this only matters if specific newer API features are needed |
| A2 | Bearer auth middleware applies to the mounted MCP SSE sub-app when middleware is added before mount | Architecture Patterns / Pitfall 2 | If wrong, MCP endpoints would be unauthenticated; requires integration test to verify |
| A3 | Using `mcp.sse_app()` with `app.mount("/", ...)` works without lifespan management issues | Code Examples | If wrong, server may fail to initialize session manager; may need `lifespan=` parameter |
| A4 | PM2 `ecosystem.config.js` with `interpreter: "none"` and `script: "uvicorn"` works when uvicorn is on PATH | Code Examples | If uvicorn is in a venv not on PATH, PM2 cannot start the process |
| A5 | All listed packages are legitimate (not slopcheck-flagged) — slopcheck was unavailable | Package Legitimacy Audit | All are well-known packages with years of history; risk is very low |
| A6 | `insert_under_heading()` error dict should include `available_headings` field (per PRD §5.3 + D-08) | Architecture Patterns | CONTEXT.md §Specifics explicitly states this; very low risk |
| A7 | `update_index()` should use upsert logic (update existing entry if path matches, insert if new) | Claude's Discretion area | Duplicates would corrupt index if error-on-duplicate is used; upsert is safer default |

---

## Open Questions

1. **D-05 library clarification: `fastapi-mcp` (tadata) vs `mcp.server.fastmcp`**
   - What we know: `fastapi-mcp` (tadata) only works with existing FastAPI routes. This project has no REST routes — all tools are custom functions.
   - What's unclear: Whether D-05 intended the official MCP SDK's FastMCP class (accessed via `from mcp.server.fastmcp import FastMCP` after `pip install mcp`) or the tadata `pip install fastapi-mcp` package.
   - Recommendation: Use `from mcp.server.fastmcp import FastMCP`. The planner should confirm this interpretation. The `mcp` package is the correct dependency.

2. **Claude.ai mobile auth gap**
   - What we know: claude.ai web/mobile connector does not support static bearer tokens — requires OAuth 2.0. Phase 1 bearer token works for Claude Desktop only.
   - What's unclear: Whether the user considers Claude Desktop sufficient for Phase 1 success criteria, or whether OAuth is needed before the project is functional for the primary phone use case.
   - Recommendation: Document this clearly in the README. Mark Phase 1 success criteria as "Claude Desktop can connect and use all tools." Mobile access via claude.ai is a separate OAuth-gated milestone.

3. **Transport: SSE vs streamable-HTTP**
   - What we know: SSE is deprecated in MCP spec (March 2025). Streamable-HTTP is the current standard. Both work today in `mcp` SDK. Claude Desktop supports both.
   - What's unclear: Whether to start with SSE (per D-05) or upgrade immediately to streamable-HTTP since SSE is deprecated.
   - Recommendation: Implement SSE per D-05 for now. Note the deprecation in README. Plan migration in Phase 2 as a low-effort task.

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
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest]` — Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Server starts on port 8000 and responds to MCP init | smoke | `pytest tests/test_infra.py::test_server_starts -x` | ❌ Wave 0 |
| INFRA-02 | Missing/wrong bearer token returns 401 | unit | `pytest tests/test_auth.py::test_bearer_auth -x` | ❌ Wave 0 |
| INFRA-05 | MCP instructions field contains CLAUDE.md content | unit | `pytest tests/test_infra.py::test_instructions_injected -x` | ❌ Wave 0 |
| NAV-01 | `list_folders()` returns folder list with note counts | unit | `pytest tests/test_nav.py::test_list_folders -x` | ❌ Wave 0 |
| NAV-02 | `list_notes(folder)` returns metadata for notes | unit | `pytest tests/test_nav.py::test_list_notes -x` | ❌ Wave 0 |
| NAV-03 | `get_note_metadata()` returns frontmatter without body | unit | `pytest tests/test_nav.py::test_get_note_metadata -x` | ❌ Wave 0 |
| NAV-04 | `get_index()` reads wiki/index.md content | unit | `pytest tests/test_nav.py::test_get_index -x` | ❌ Wave 0 |
| RET-01 | `search_full_text()` returns ranked snippets | unit | `pytest tests/test_retrieval.py::test_search -x` | ❌ Wave 0 |
| RET-02 | `get_note_summary()` returns first 200 chars + headings | unit | `pytest tests/test_retrieval.py::test_get_note_summary -x` | ❌ Wave 0 |
| RET-03 | `read_note()` returns full content + frontmatter | unit | `pytest tests/test_retrieval.py::test_read_note -x` | ❌ Wave 0 |
| RET-04 | `read_note_section()` returns single section content | unit | `pytest tests/test_retrieval.py::test_read_note_section -x` | ❌ Wave 0 |
| INGEST-01 | `create_note()` creates file, fails if exists | unit | `pytest tests/test_ingestion.py::test_create_note -x` | ❌ Wave 0 |
| INGEST-02 | `append_to_note()` appends text | unit | `pytest tests/test_ingestion.py::test_append_to_note -x` | ❌ Wave 0 |
| INGEST-03 | `prepend_to_note()` inserts after frontmatter | unit | `pytest tests/test_ingestion.py::test_prepend_to_note -x` | ❌ Wave 0 |
| INGEST-04 | `insert_under_heading()` inserts under correct section | unit | `pytest tests/test_ingestion.py::test_insert_under_heading -x` | ❌ Wave 0 |
| INGEST-05 | `update_frontmatter()` updates key without touching body | unit | `pytest tests/test_ingestion.py::test_update_frontmatter -x` | ❌ Wave 0 |
| MAINT-01 | `update_index()` upserts entry in wiki/index.md | unit | `pytest tests/test_maintenance.py::test_update_index -x` | ❌ Wave 0 |
| MAINT-02 | `append_log()` appends timestamped entry to log.md | unit | `pytest tests/test_maintenance.py::test_append_log -x` | ❌ Wave 0 |
| INFRA-03 | Cloudflare Tunnel accessible from external URL | manual | N/A — requires live cloudflared + DNS | Manual only |
| INFRA-04 | PM2 auto-restarts server on crash | manual | N/A — requires live PM2 session | Manual only |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q --ignore=tests/test_infra.py`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — shared `tmp_vault` fixture (creates temp dir, seeds index.md + log.md)
- [ ] `tests/test_auth.py` — bearer auth middleware tests
- [ ] `tests/test_infra.py` — server startup, MCP init, instructions injection
- [ ] `tests/test_nav.py` — navigation tool tests (4 tools)
- [ ] `tests/test_retrieval.py` — retrieval tool tests (4 tools)
- [ ] `tests/test_ingestion.py` — ingestion tool tests (5 tools)
- [ ] `tests/test_maintenance.py` — maintenance tool tests (2 tools)
- [ ] Framework install: `pip install pytest pytest-asyncio httpx`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Bearer token middleware (VAULT_SECRET env var) |
| V3 Session Management | no | Stateless MCP protocol; no sessions |
| V4 Access Control | yes | Single user; bearer token is the only access gate |
| V5 Input Validation | yes | Validate all `path` parameters stay within VAULT_PATH |
| V6 Cryptography | no | Bearer token is a shared secret, not crypto — acceptable for single-user personal tool |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `path` parameter | Tampering | `Path(VAULT_PATH / path).resolve().is_relative_to(VAULT_PATH)` check in every tool |
| Missing/invalid Authorization header | Spoofing | BearerAuthMiddleware returns 401 before any tool executes |
| Raw VAULT_SECRET in logs | Information Disclosure | Never log the `Authorization` header value |
| Vault `raw/` directory modification | Tampering | Tool implementations must refuse paths starting with `raw/` |

---

## Sources

### Primary (HIGH confidence)
- `pypi.org/project/mcp/1.9.1/` — confirmed mcp SDK version, official Anthropic package
- `modelcontextprotocol.io/docs/develop/build-server` — FastMCP tool registration, instructions param
- `gofastmcp.com/servers/server` — FastMCP constructor signature with `instructions` parameter
- `python-frontmatter.readthedocs.io` — frontmatter.load/dump API, module name
- `developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/` — cloudflared commands
- `pm2.keymetrics.io/docs/usage/application-declaration/` — ecosystem.config.js format
- `fastapi.tiangolo.com/tutorial/middleware/` — BaseHTTPMiddleware pattern
- `claude.com/docs/connectors/building/authentication` — bearer token auth not supported on claude.ai

### Secondary (MEDIUM confidence)
- `ragie.ai/blog/building-a-server-sent-events-sse-mcp-server-with-fastapi` — SSE mount pattern with mcp SDK
- `fastapi-mcp.tadata.com/getting-started/FAQ` — confirmed fastapi-mcp only supports route-based tools
- `snyk.io/advisor/python/python-frontmatter` — download stats 111K/wk, 8yr old package
- `github.com/anthropics/claude-ai-mcp/issues/112` — bearer token not supported in claude.ai UI

### Tertiary (LOW confidence)
- Various WebSearch results about PM2 Python ecosystem config (exact `interpreter: "none"` syntax unverified)

---

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM-HIGH — mcp SDK version confirmed via search; exact compatible versions with fastapi 0.111.0 are [ASSUMED]
- Architecture: HIGH — patterns derived from official docs and confirmed examples
- Pitfalls: HIGH — bearer auth/claude.ai gap confirmed by official Anthropic docs; library confusion confirmed by tadata FAQ

**Research date:** 2026-05-29
**Valid until:** 2026-07-29 (60 days — MCP ecosystem is fast-moving; check SSE deprecation timeline)
