# Phase 1: Core MCP Server - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 1-Core MCP Server
**Areas discussed:** Project layout, MCP + FastAPI wiring, Cloudflare Tunnel scope, Naive search scoring

---

## Project Layout

**Q1: How should the server code be organized?**

| Option | Description | Selected |
|--------|-------------|----------|
| Flat — single server.py | All 20 tools in one file. Simple to run, easy to grep, no import complexity. | ✓ |
| Package — app/ with modules | app/main.py + app/tools/navigation.py etc. Cleaner separation but more scaffolding. | |
| Package — flat tool files | app/main.py + app/navigation.py etc. Middle ground. | |

**User's choice:** Single server.py monolith

---

**Q2: Where should the vault path be configured?**

| Option | Description | Selected |
|--------|-------------|----------|
| VAULT_PATH env var in .env | Consistent with VAULT_SECRET. One .env file for all config. | ✓ |
| Hardcoded default + override via arg | DEFAULT_VAULT_PATH constant, overridable via --vault CLI arg. | |
| Config file (config.yml) | Separate config.yml alongside server.py. | |

**User's choice:** VAULT_PATH env var in .env

---

**Q3: How should the server be started during development?**

| Option | Description | Selected |
|--------|-------------|----------|
| uvicorn server:app --reload | Standard FastAPI dev run. Hot-reload. PM2 wraps this in production. | ✓ |
| python server.py | server.py calls uvicorn.run() in __main__. Loses hot-reload. | |
| Makefile with make dev / make start | Unified run commands but adds a non-Python file. | |

**User's choice:** `uvicorn server:app --reload`

---

**Q4: What supporting files should live alongside server.py?**

| Option | Description | Selected |
|--------|-------------|----------|
| server.py + .env + requirements.txt + README.md | Minimal, conventional. | ✓ |
| server.py + .env + pyproject.toml | Modern packaging but more setup. | |
| Add ecosystem.config.js for PM2 too | PM2 config for one-command production startup. | |

**User's choice:** server.py + .env + requirements.txt + README.md
**Notes:** ecosystem.config.js was later confirmed as in-scope under the Cloudflare Tunnel discussion.

---

## MCP + FastAPI Wiring

**Q1: Which approach to wire the MCP SDK with FastAPI over SSE?**

| Option | Description | Selected |
|--------|-------------|----------|
| fastapi-mcp library | Mounts MCP onto FastAPI with one line. Handles SSE routing automatically. | ✓ |
| mcp.server.fastapi from official SDK | Official SDK FastAPI integration. Has been evolving — may need pinning. | |
| Raw SSE endpoint — custom implementation | Full control, no extra dep, but more boilerplate. | |

**User's choice:** fastapi-mcp library

---

**Q2: How should bearer token auth be enforced?**

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI middleware on all routes | Single enforcement point, applies automatically to all tools. | ✓ |
| Per-tool dependency injection | Each tool declares Depends(verify_token). Explicit but repetitive. | |
| HTTP header check at top of each tool | Simpler but no standard pattern. | |

**User's choice:** FastAPI middleware on all routes

---

**Q3: How should CLOUD.md/CLAUDE.md be injected as the MCP system prompt?**

| Option | Description | Selected |
|--------|-------------|----------|
| MCP server instructions field | Pass content as instructions param when creating FastAPI MCP server. | ✓ |
| MCP resource — expose as cloud://rules | Register as MCP resource. Requires explicit tool call — less reliable. | |
| Embed in each tool's description string | Prefix every docstring with rules. Verbose, duplicates content. | |

**User's choice:** MCP server instructions field
**Notes:** User corrected the file name — it's `CLAUDE.md`, NOT `CLOUD.md` as labeled throughout the PRD. This is a critical naming correction for all downstream agents.

---

**Q4: How should MCP tool errors be returned?**

| Option | Description | Selected |
|--------|-------------|----------|
| Consistent error dict: {"error": true, "message": "...", "code": "..."} | Predictable across all 14 tools. Claude can inspect the error key. | ✓ |
| Raise HTTPException | FastAPI returns JSON error responses. Mixes HTTP semantics into tool layer. | |
| Return None and log | Less explicit. | |

**User's choice:** Consistent error dict

---

## Cloudflare Tunnel Scope

**Q1: What does Phase 1 deliver for Cloudflare Tunnel setup?**

| Option | Description | Selected |
|--------|-------------|----------|
| Setup script + config template + README steps | setup.sh + ~/.cloudflared/config.yml template + README for manual steps. | ✓ |
| README documentation only | Step-by-step README. No scripts. | |
| Full automation — everything scripted | Near-zero manual steps. More complex but turnkey. | |

**User's choice:** Setup script + config template + README steps

---

**Q2: How should PM2 process management be delivered?**

| Option | Description | Selected |
|--------|-------------|----------|
| ecosystem.config.js included in the repo | Starts vault-mcp and cloudflare-tunnel with auto-restart. | ✓ |
| README commands only | User copies pm2 start commands from README. | |
| Makefile targets | make start / make stop wrapping pm2. | |

**User's choice:** ecosystem.config.js included in the repo

---

**Q3: Should Phase 1 include a vault initialization script?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — init_vault.py script | Creates vault structure, seeds index.md/log.md, copies CLAUDE.md. | ✓ |
| No — server creates directories on startup | Path.mkdir(exist_ok=True) in server.py. | |
| No — user creates manually per README | Friction for first run. | |

**User's choice:** Yes — init_vault.py script

---

**Q4: Where should VAULT_PATH point?**

| Option | Description | Selected |
|--------|-------------|----------|
| Existing Obsidian vault | init_vault.py adds wiki/ and raw/ inside an existing vault. | |
| Fresh vault created by init_vault.py | No existing vault. init_vault.py creates everything from scratch. | ✓ |
| You decide | Researcher/planner decides. | |

**User's choice:** Fresh vault created by init_vault.py

---

## Naive Search Scoring

**Q1: How should search_full_text() score results in Phase 1?**

| Option | Description | Selected |
|--------|-------------|----------|
| Normalized match count | score = occurrences / max_occurrences_in_results. 0–1 float. | ✓ |
| Binary match — score always 1.0 | Not ranked, just filtered. | |
| Simple TF — count / word_count | Term frequency. Slightly more principled. | |

**User's choice:** Normalized match count

---

**Q2: Case sensitivity and search scope within files?**

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive, full file (frontmatter + body) | Consistent with how FTS5 will work in Phase 2. | ✓ |
| Case-insensitive, body only | Strips frontmatter before searching. | |
| Case-sensitive, full file | Simplest but least useful in practice. | |

**User's choice:** Case-insensitive, full file

---

**Q3: What should the snippet look like?**

| Option | Description | Selected |
|--------|-------------|----------|
| 2-line window around first match, ~150 chars | Consistent with PRD "2-line context snippets". | ✓ |
| First 200 chars of note body | Match context may not appear. | |
| All matching lines joined, truncated | Verbose. | |

**User's choice:** 2-line window around first match, ~150 chars

---

**Q4: Which directories should the naive search scan?**

| Option | Description | Selected |
|--------|-------------|----------|
| wiki/ only — skip raw/ | Consistent with tiered retrieval model. | ✓ |
| Entire vault — wiki/ + raw/ | Broader but noisy (large transcripts). | |
| Configurable — search_path parameter | Flexible but adds API complexity before FTS5. | |

**User's choice:** wiki/ only

---

## Claude's Discretion

- Frontmatter tag/related field inference in `create_note()` — specific inference logic is Claude's call.
- `update_index()` duplicate handling — upsert vs. error is planner's call.
- Heading tie-breaking in `insert_under_heading()` and `read_note_section()` — exact behavior when multiple headings partially match is planner's call.

## Deferred Ideas

- None — discussion stayed within phase scope.
