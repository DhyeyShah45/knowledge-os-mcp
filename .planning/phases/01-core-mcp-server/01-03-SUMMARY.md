---
phase: 01-core-mcp-server
plan: 03
status: completed
wave: 2
subsystem: server-core
tags: [fastmcp, bearer-auth, oauth-pkce, middleware, mcp-transport]
requires: [01-01, 01-02]
provides:
  - FastAPI app (server.app) with MCP streamable-HTTP at /mcp
  - FastMCP instance (server.mcp) with CLAUDE.md instructions
  - BearerAuthMiddleware enforcing VAULT_SECRET on all non-OAuth routes
  - OAuth 2.0 Authorization Code + PKCE /authorize and /token endpoints
  - safe_vault_path() path validator
  - err() error dict builder + ERR_* code constants
  - OAUTH_BYPASS_PATHS shared constant
affects: [all-subsequent-plans]
tech-stack:
  added: [mcp-sdk, fastmcp, starlette-middleware, oauth-pkce]
  patterns:
    - FastMCP with instructions= injection
    - BaseHTTPMiddleware single enforcement point
    - streamable-HTTP transport via mcp.http_app()
    - OAuth 2.0 PKCE S256 in-memory flow
    - safe_vault_path path traversal guard
key-files:
  created:
    - server.py
    - tests/test_auth.py
    - tests/test_infra.py
    - tests/test_oauth.py
  modified: []
decisions:
  - "mcp.http_app(path='/mcp', transport='streamable-http') is the only mount form used — no speculative API"
  - "safe_vault_path rejects empty, absolute, raw/, and traversal paths — four distinct guards"
  - "OAUTH_BYPASS_PATHS is a module-level set shared by middleware and routes — single source of truth"
  - "access_token returned by /token equals VAULT_SECRET (single-user system per D-16)"
  - "test_infra.py has 5 tests (3 core + 2 extra for safe_vault_path positive/raw cases) vs plan spec of 3 — added Rule 2 tests for completeness"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-29"
  task_count: 2
  file_count: 4
---

# Phase 1 Plan 03: FastMCP Server Core Summary

## One-liner

FastAPI app with FastMCP streamable-HTTP transport, single-point BearerAuthMiddleware enforcing VAULT_SECRET, and OAuth 2.0 Authorization Code + PKCE endpoints so both Claude Desktop (direct bearer) and claude.ai mobile (OAuth flow) can connect.

## What was built

### server.py (336 lines)

Single monolith implementing the full server core:

**Exported symbols for Plans 04-07:**
- `app` — FastAPI application (uvicorn target: `uvicorn server:app`)
- `mcp` — FastMCP instance with `instructions=` set to CLAUDE.md content
- `safe_vault_path(rel: str) -> Path | dict` — validates and resolves relative vault paths
- `err(message: str, code: str) -> dict` — canonical error dict builder
- `ERR_NOT_FOUND`, `ERR_ALREADY_EXISTS`, `ERR_INVALID_PATH`, `ERR_HEADING_NOT_FOUND`, `ERR_AUTH` — error code constants
- `OAUTH_BYPASS_PATHS: set[str]` — shared `{"/authorize", "/token"}` bypass set
- `VAULT_PATH: Path`, `VAULT_SECRET: str` — loaded at module level from env vars

**Key structural properties (all verified):**
- `load_dotenv()` called immediately after imports
- `VAULT_PATH`, `VAULT_SECRET`, `OAUTH_CLIENT_ID`, `OAUTH_REDIRECT_URI` read with `os.environ[...]` (fail-fast on missing)
- CLAUDE.md read at startup, not per-request; passed to `FastMCP("vault-mcp", instructions=...)`
- `mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")` — the only documented mount form
- `app = FastAPI(lifespan=mcp_app.lifespan)` — required for MCP session manager initialization
- `app.add_middleware(BearerAuthMiddleware)` appears at line 184; `app.mount("/mcp", mcp_app)` at line 336 — middleware is before mount
- `/authorize` GET route registered at line 196; `/token` POST at line 255 — both before mount
- `_pkce_codes: dict[str, dict]` in-memory store for single-use authorization codes

### tests/test_auth.py (3 tests)

| Test | What it verifies |
|------|-----------------|
| `test_bearer_auth_missing_returns_401` | POST /mcp with no Authorization header → 401 + AUTH_ERROR code |
| `test_bearer_auth_wrong_token_returns_401` | POST /mcp with wrong bearer token → 401 + AUTH_ERROR code |
| `test_bearer_auth_correct_token_passes_middleware` | POST /mcp with correct token → NOT 401 |

### tests/test_infra.py (5 tests)

| Test | What it verifies |
|------|-----------------|
| `test_app_importable` | server.py imports cleanly; `app` and `mcp` attributes present |
| `test_instructions_injected` | `server.mcp.instructions` equals `(tmp_vault / "CLAUDE.md").read_text()` |
| `test_safe_vault_path_blocks_traversal` | `../../etc/passwd` returns INVALID_PATH dict |
| `test_safe_vault_path_allows_valid_path` | `wiki/concepts/foo.md` returns Path rooted at VAULT_PATH |
| `test_safe_vault_path_blocks_raw` | `raw/webpages/something.md` returns INVALID_PATH dict |

### tests/test_oauth.py (8 tests)

| Test | What it verifies |
|------|-----------------|
| `test_oauth_authorize_redirects_with_code` | Valid S256 request → 302 with code+state |
| `test_oauth_authorize_rejects_unknown_client` | Evil client_id → 400 |
| `test_oauth_authorize_rejects_missing_pkce` | No code_challenge → 400 |
| `test_oauth_authorize_rejects_non_s256_method` | `plain` method → 400 |
| `test_oauth_token_exchanges_code_for_secret` | Full flow → access_token == VAULT_SECRET |
| `test_oauth_token_rejects_wrong_verifier` | Tampered verifier → 400 |
| `test_oauth_token_rejects_reused_code` | Code used twice → second exchange 400 |
| `test_oauth_token_with_oauth_token_passes_middleware` | OAuth access_token passes /mcp middleware |

## Verification Results

All static verification checks passed (virtualenv not installed; dynamic tests deferred):

```
AST parse: server.py, test_auth.py, test_infra.py, test_oauth.py — all OK
from mcp.server.fastmcp import FastMCP: FOUND
load_dotenv: FOUND
BearerAuthMiddleware: FOUND
safe_vault_path + is_relative_to: FOUND
add_middleware (line 184) < app.mount (line 336): OK
/authorize route (line 196) < app.mount (line 336): OK
transport="streamable-http" + mcp.http_app: FOUND
instructions= to FastMCP: FOUND
OAUTH_BYPASS_PATHS: FOUND
base64.urlsafe_b64encode + hashlib.sha256 + secrets.token_urlsafe: FOUND
RedirectResponse + access_token: FOUND
no streamable_http_app, no sse_app, no fastapi_mcp: CONFIRMED ABSENT
server.py line count: 336 (min_lines 200: PASSED)
```

## Deviations from Plan

### Added extra safe_vault_path tests

**Found during:** Task 1 test file creation
**Issue:** The plan spec listed 3 tests for test_infra.py, but test 6 in the behavior spec covered only the negative traversal case and one positive case. To make coverage complete for the INFRA-05 + path guard requirements, two additional tests were added.
**Fix:** `test_safe_vault_path_allows_valid_path` and `test_safe_vault_path_blocks_raw` added alongside the 3 plan-specified tests — total 5 tests in test_infra.py.
**Rule:** Rule 2 (auto-add missing critical functionality — path guard correctness)

### Test function naming uses descriptive suffix

**Found during:** Task 1 test file creation
**Issue:** Plan's acceptance criteria listed `test_bearer_auth` as a pattern to `contains:` — this is a partial match, not a full test name. The tests were named with descriptive suffixes (`_missing_returns_401`, `_wrong_token_returns_401`, `_correct_token_passes_middleware`) for clarity.
**Fix:** All three pattern-check names from the acceptance criteria (`test_bearer_auth`, `test_oauth`, `test_instructions_injected`) are substrings present in the actual function names — grep matches pass.

### Virtual environment not installed

**Context:** The prompt explicitly states "Do NOT run the server or actual tests — the virtualenv is not installed yet." The `python -m pytest` commands from the plan verification block were not executed. All verification was performed via static analysis (AST parse, grep checks).

## Known Stubs

None — server.py has no hardcoded empty values flowing to UI or placeholder text. No `@mcp.tool()` functions registered yet (deferred to Plans 04-07 as specified).

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model. All STRIDE mitigations from T-03-01 through T-03-07 are implemented:
- T-03-01: BearerAuthMiddleware returns 401 with AUTH_ERROR dict before MCP layer
- T-03-02: /authorize validates client_id against OAUTH_CLIENT_ID env var
- T-03-03: _pkce_codes tracks `used: bool`; /token marks code used and rejects reuse
- T-03-04: PKCE S256 challenge/verifier hash comparison in /token
- T-03-05: safe_vault_path returns INVALID_PATH if resolved path escapes VAULT_PATH
- T-03-06: safe_vault_path rejects paths whose first component is `raw`
- T-03-07: BearerAuthMiddleware never logs the Authorization header value

## Self-Check: PASSED

- server.py: FOUND (336 lines, AST OK)
- tests/test_auth.py: FOUND (3 tests, AST OK)
- tests/test_infra.py: FOUND (5 tests, AST OK)
- tests/test_oauth.py: FOUND (8 tests, AST OK)
- Commit 489a90c (RED): FOUND
- Commit 4f316f0 (GREEN): FOUND
