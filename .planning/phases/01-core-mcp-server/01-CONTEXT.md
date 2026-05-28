# Phase 1: Core MCP Server - Context

**Gathered:** 2026-05-28
**Last updated:** 2026-05-29 (D-05 corrected, D-16 added per checker feedback)
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a running FastAPI MCP server with streamable-HTTP transport and bearer auth (plus OAuth 2.0 PKCE wrapper for claude.ai mobile), a Cloudflare Tunnel exposing it at a persistent HTTPS subdomain, and the complete set of navigation / retrieval / ingestion / maintenance tools — so Claude on any device can read and write a fresh Obsidian vault over a secure connection.

Naive keyword search (file scan) is in scope. FTS5, Whisper, ChromaDB, and media ingestion are NOT in scope.

</domain>

<decisions>
## Implementation Decisions

### Project Layout
- **D-01:** Single flat `server.py` monolith — all tools in one file. No `app/` package. No subdirectories for tool categories.
- **D-02:** Configuration via `.env` file using `python-dotenv`. Required env vars: `VAULT_SECRET` (bearer token), `VAULT_PATH` (absolute path to vault directory), `OAUTH_CLIENT_ID` (see D-16), `OAUTH_REDIRECT_URI` (see D-16).
- **D-03:** Dev command: `uvicorn server:app --reload`. PM2 wraps the same command in production.
- **D-04:** Root files: `server.py`, `.env` (gitignored), `requirements.txt` (Phase 1 deps), `README.md`, `ecosystem.config.js`, `init_vault.py`, `setup.sh`.

### MCP + FastAPI Wiring
- **D-05:** Use the official `mcp` SDK (`pip install mcp`). Import `from mcp.server.fastmcp import FastMCP`. Mount via streamable-HTTP: `mcp_app = mcp.http_app(path='/mcp', transport='streamable-http')`. SSE transport is deprecated (MCP spec March 2025) and MUST NOT be used. The `fastapi-mcp` (tadata) library is NOT used — it only converts existing FastAPI routes into MCP tools and cannot register custom functions, which is the wrong fit for this project's 14 custom file-operation tools.
- **D-06:** Bearer auth enforced via FastAPI middleware on all routes EXCEPT the OAuth endpoints (`/authorize`, `/token`) — a single enforcement point that applies automatically to every tool call. Reads `Authorization: Bearer <token>` and compares to `VAULT_SECRET`.
- **D-07:** The vault's operational rules document is named `CLAUDE.md` (NOT `CLOUD.md` as labeled in PRD.md — user correction). Its content is injected as the MCP server's `instructions` field on startup so Claude receives it on connection.
- **D-08:** All tool errors return a consistent dict: `{"error": true, "message": "...", "code": "NOT_FOUND"}`. Code values include at minimum: `NOT_FOUND`, `ALREADY_EXISTS`, `INVALID_PATH`, `HEADING_NOT_FOUND`, `AUTH_ERROR`. Never raise HTTPException from tool functions.

### Cloudflare Tunnel + Setup Scope
- **D-09:** Phase 1 delivers: `setup.sh` (creates Cloudflare tunnel, generates `~/.cloudflared/config.yml` template), `ecosystem.config.js` (PM2 config starting both `vault-mcp` and `cloudflare-tunnel` processes with auto-restart), and a README section covering DNS + dashboard steps that cannot be scripted.
- **D-10:** `init_vault.py` creates a **fresh vault** at `VAULT_PATH`. It creates the full directory structure (`raw/webpages/`, `raw/transcripts/`, `raw/videos/`, `raw/documents/`, `raw/assets/`, `raw/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/sources/`, `wiki/queries/`), seeds `wiki/index.md` and `wiki/log.md` with correct initial format, and copies `CLAUDE.md` into the vault root. Run once before starting the server.
- **D-11:** `VAULT_PATH` points to a new directory that does not exist yet — `init_vault.py` creates it entirely from scratch.

### Naive search_full_text() (Phase 1 only — replaced by FTS5 in Phase 2)
- **D-12:** Scoring: normalized match count — `score = occurrence_count / max_occurrences_across_results`. Produces a 0–1 float. If only one result, score is 1.0.
- **D-13:** Search is case-insensitive (`query.lower() in line.lower()`), scans the full file including YAML frontmatter.
- **D-14:** Search scope: `wiki/` subdirectory only. Raw sources are excluded from the naive scan.
- **D-15:** Snippet: 2-line window (≈150 chars) centered on the first occurrence of the query in the file. Matches the PRD's "2-line context snippets" description.

### OAuth 2.0 (claude.ai mobile compatibility)
- **D-16:** Implement OAuth 2.0 Authorization Code + PKCE (S256) endpoints in Phase 1 so the claude.ai mobile/web connector can complete a handshake. Two additional env vars are required and MUST be present in `.env` / `.env.example`:
  - `OAUTH_CLIENT_ID` — unique identifier registered for the claude.ai connector (free-form string, validated by `/authorize` against this env value)
  - `OAUTH_REDIRECT_URI` — callback URL the connector must use (validated by `/authorize` against this env value; matches the URL registered with the claude.ai connector UI / Cloudflare Tunnel hostname)
  - The `/token` endpoint exchanges the PKCE-verified authorization code for an `access_token` equal to `VAULT_SECRET`. This thin OAuth wrapper exists solely to satisfy claude.ai's connector requirement; the access token is the same shared secret used by Claude Desktop's direct bearer-token path, because the system is single-user by design.
  - `/authorize` and `/token` paths MUST bypass `BearerAuthMiddleware` (they are the auth flow itself).

### Claude's Discretion
- Frontmatter auto-generation logic in `create_note()` — specific field inference from content (tags, related) is Claude's call as long as the template fields from PRD §3 are populated.
- Index entry format in `update_index()` — how to handle duplicates (upsert vs. error) is left to planner/researcher.
- Heading match logic in `insert_under_heading()` and `read_note_section()` — partial case-insensitive match is specified; exact tie-breaking is planner's call.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary Design Doc
- `PRD.md` — Full PRD + system architecture + tool specifications with exact signatures and return shapes + package dependency list + CLOUD.md operational rules (§7). **This is the authoritative spec for all tool behavior.** Note: PRD refers to the vault rules file as `CLOUD.md` but the correct name is `CLAUDE.md` (D-07).

### Planning Artifacts
- `.planning/ROADMAP.md` — Phase goals, success criteria (5 items for Phase 1), and dependency order
- `.planning/REQUIREMENTS.md` — All 20 Phase 1 requirements (INFRA-01–05, NAV-01–04, RET-01–04, INGEST-01–05, MAINT-01–02) with acceptance criteria

### Key Sections in PRD.md
- `PRD.md §2` — System architecture, component descriptions, port/auth/transport decisions
- `PRD.md §3` — Vault structure (directory layout, index.md format, log.md format, frontmatter template)
- `PRD.md §4` — Phase 1 scope boundaries (what is and is NOT in Phase 1)
- `PRD.md §5.1–5.4` — Tool specifications for all Phase 1 tools (Navigation, Retrieval, Ingestion, Maintenance) with exact Python signatures and return shapes
- `PRD.md §6.1` — Phase 1 package dependencies with pinned versions
- `PRD.md §7` — CLAUDE.md operational rules (the MCP system prompt / instructions content)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — project is greenfield. No existing source code.

### Established Patterns
- None established yet. Phase 1 sets the patterns.

### Integration Points
- `wiki/index.md` is the central integration point: `create_note()` → `update_index()` → `append_log()` is the mandatory call chain after every note creation (enforced by CLAUDE.md rules, not the server itself).
- `wiki/log.md` receives every significant operation via `append_log()`.
- `CLAUDE.md` in the vault root is the system prompt source — `init_vault.py` places it there; `server.py` reads it at startup and passes it as MCP `instructions`.

</code_context>

<specifics>
## Specific Ideas

- PRD §3 defines exact `index.md` and `log.md` formats with markdown examples — planner should use these verbatim in `init_vault.py` and tool implementation.
- PRD §5.3 specifies `create_note()` behavior: "Fails if path already exists (use append_to_note instead)" — this is an explicit behavioral constraint.
- PRD §5.3 specifies `insert_under_heading()`: "Fails gracefully if heading not found — returns error with available headings." The error dict (D-08) should include an `available_headings` field in this case.
- PRD §6.5 shows exact PM2 commands (`pm2 start "python server.py" --name vault-mcp`) — `ecosystem.config.js` should match these process names.
- PRD §2.2 specifies Cloudflare Tunnel config path: `~/.cloudflared/config.yml`.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Core MCP Server*
*Context gathered: 2026-05-28*
*Revised: 2026-05-29 — D-05 corrected to official `mcp` SDK + streamable-HTTP transport; D-16 added to formalize OAuth env vars; D-02 expanded to list all four required env vars.*
