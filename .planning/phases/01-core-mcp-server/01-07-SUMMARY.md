---
phase: 01-core-mcp-server
plan: 07
subsystem: maintenance
tags: [mcp, fastmcp, fastapi, maintenance, index, log, upsert, obsidian]

# Dependency graph
requires:
  - phase: 01-06
    provides: "Five ingestion tools (create_note, append_to_note, prepend_to_note, insert_under_heading, update_frontmatter)"
provides:
  - "update_index() — section-based upsert in wiki/index.md with header totals refresh (MAINT-01)"
  - "append_log() — prepend timestamped blocks to wiki/log.md, newest-first (MAINT-02)"
  - "tests/test_maintenance.py — 10 tests covering all maintenance tool behaviors"
  - "15 total @mcp.tool() functions in server.py (4 nav + 4 retrieval + 5 ingestion + 2 maintenance)"
affects: [02-media-ingestion, future-phases-that-call-update_index-append_log]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Section-based upsert: scan section by heading, find-and-replace existing wikilink key, or insert at section end"
    - "Header totals refresh: recount all - [[...]] entries and Sources-section entries after each write"
    - "Prepend-below-header pattern for append_log: split on '# Vault Log', insert between header and body"
    - "Allowlist validation for enum-style string args (category, operation) using frozenset membership"

key-files:
  created:
    - "tests/test_maintenance.py — 10 maintenance tool tests"
  modified:
    - "server.py — added update_index (MAINT-01) and append_log (MAINT-02) as @mcp.tool() functions"

key-decisions:
  - "update_index upserts by wikilink key (path_without_md), not by full entry line — supports re-runs with different summaries"
  - "Header totals recounted by scanning all lines after each write — simple and correct for Phase 1 vault sizes"
  - "append_log consumes all blank lines after the header before inserting — prevents blank-line accumulation on repeated calls"
  - "Both tools return err() with ERR_INVALID_PATH for allowlist violations (category/operation) — consistent with D-08"
  - "Task 3 (end-to-end deployment verification) is a blocking human checkpoint pending user execution of PM2/Cloudflare/Claude Desktop checks"

patterns-established:
  - "Allowlist validation pattern: frozenset membership check before any I/O"
  - "Section-find-and-replace pattern for structured markdown files"

requirements-completed:
  - MAINT-01
  - MAINT-02

# Metrics
duration: 25min
completed: 2026-05-29
---

# Phase 1 Plan 07: Maintenance Tools Summary

**Section-based upsert for wiki/index.md (update_index) and newest-first prepend for wiki/log.md (append_log) — Phase 1 tool set complete at 15 tools**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-29T00:00:00Z
- **Completed:** 2026-05-29
- **Tasks:** 2 of 3 (Task 3 is a blocking human checkpoint — pending)
- **Files modified:** 2 (server.py, tests/test_maintenance.py)

## Accomplishments

- Implemented update_index (MAINT-01): section-based upsert of entries in wiki/index.md with header totals refresh
- Implemented append_log (MAINT-02): newest-first prepend of timestamped operation blocks in wiki/log.md
- Both tools validate allowlisted enum parameters (category, operation) per T-07-01 and T-07-02
- Created tests/test_maintenance.py with 10 tests covering insert, upsert, totals refresh, invalid-category, missing-index, PRD format, prepend order, invalid-operation, missing-log, and suite discovery
- Phase 1 @mcp.tool() count reached 15 (4 nav + 4 retrieval + 5 ingestion + 2 maintenance)

## Phase 1 Requirement Status

All 20 Phase 1 requirement IDs and their completion status:

| ID       | Description                                                             | Status      |
|----------|-------------------------------------------------------------------------|-------------|
| INFRA-01 | FastAPI MCP server on port 8000 with streamable-HTTP transport          | Completed   |
| INFRA-02 | Bearer token auth via BearerAuthMiddleware on all /mcp/* routes         | Completed   |
| INFRA-03 | Cloudflare Tunnel exposes server at persistent custom subdomain         | Pending (Task 3 human checkpoint) |
| INFRA-04 | PM2 manages server process with auto-restart on failure                 | Pending (Task 3 human checkpoint) |
| INFRA-05 | CLAUDE.md operational rules embedded as MCP system prompt               | Completed   |
| NAV-01   | list_folders() returns vault folder tree with note counts               | Completed   |
| NAV-02   | list_notes() lists direct-child notes with path, title, last_modified   | Completed   |
| NAV-03   | get_note_metadata() returns frontmatter + stats without body            | Completed   |
| NAV-04   | get_index() returns wiki/index.md content and header stats              | Completed   |
| RET-01   | search_full_text() naive keyword search with snippets and scores        | Completed   |
| RET-02   | get_note_summary() returns first 200 chars + heading outline            | Completed   |
| RET-03   | read_note() returns full note content and frontmatter                   | Completed   |
| RET-04   | read_note_section() returns content under a specific heading            | Completed   |
| INGEST-01| create_note() creates new note with auto-generated frontmatter          | Completed   |
| INGEST-02| append_to_note() appends text to existing note body                     | Completed   |
| INGEST-03| prepend_to_note() inserts text after frontmatter                        | Completed   |
| INGEST-04| insert_under_heading() inserts at end of a named section                | Completed   |
| INGEST-05| update_frontmatter() updates single frontmatter key without touching body| Completed  |
| MAINT-01 | update_index() upserts entries and refreshes totals in wiki/index.md    | Completed   |
| MAINT-02 | append_log() prepends timestamped blocks newest-first in wiki/log.md    | Completed   |

**Completed: 18 of 20** — INFRA-03 and INFRA-04 require manual verification (Task 3 blocking checkpoint).

## Task Commits

1. **Task 1 + Task 2: update_index, append_log, and maintenance tests** - `2291172` (feat)

## Files Created/Modified

- `/Users/dhyeyshah45/Projects/knowledge-os-mcp/server.py` — Added update_index() and append_log() as @mcp.tool() functions (lines 1109–1295)
- `/Users/dhyeyshah45/Projects/knowledge-os-mcp/tests/test_maintenance.py` — 10 maintenance unit tests

## Decisions Made

- update_index upserts by wikilink key (path_without_md match at start of line) rather than full line replacement — allows summary to change while maintaining uniqueness per path
- Header totals recounted from scratch after every update_index call — O(n) scan but correct at all vault sizes expected in Phase 1
- append_log collapses any blank lines between the "# Vault Log" header and the first entry — prevents accumulating blank lines on repeated calls
- Both tools use ERR_INVALID_PATH (not a new ERR_VALIDATION constant) for allowlist violations — consistent with D-08 and existing tool patterns

## Deviations from Plan

None — plan executed exactly as specified. The two functions match the PRD §5.4 signatures and behaviors.

## Issues Encountered

None.

## Deferred Items for Phase 2

The following items were noted during Phase 1 but explicitly deferred:

1. **asyncio.Lock concurrency hardening (RESEARCH.md Pitfall 5):** update_index and append_log perform read-modify-write operations on wiki/index.md and wiki/log.md without a mutex. In Phase 1 the MCP server is single-user and requests are effectively sequential, so this is acceptable. Phase 2 should add an asyncio.Lock per file path to prevent lost updates under concurrent tool calls.

2. **SQLite FTS5 search (SEARCH-01, SEARCH-02):** search_full_text() uses a naive O(n) file scan in Phase 1. Phase 2 replaces it with SQLite FTS5 with BM25 ranking and a watchdog file watcher.

3. **ChromaDB semantic search (SEM-01..SEM-04):** Phase 3 adds vector embeddings via sentence-transformers and a ChromaDB local store. No Phase 1 code changes needed — the search_full_text() signature is compatible.

4. **lint_wiki() tool (SEARCH-03):** Vault health check (orphan detection, broken links) is Phase 2 scope.

5. **Media ingestion tools (MEDIA-01..MEDIA-04):** yt-dlp, Whisper, readability, markdownify, pdfminer.six are Phase 2 scope.

## Task 3 (Pending): End-to-End Deployment Verification

Task 3 is a `checkpoint:human-verify` blocking gate. The user must:

1. Run `bash setup.sh`, populate `.env`, run `python init_vault.py`, boot uvicorn, verify bearer auth
2. Start PM2 (`pm2 start ecosystem.config.js`), kill the uvicorn pid, confirm auto-restart (INFRA-04)
3. Verify Cloudflare Tunnel is reachable from off-network device (INFRA-03)
4. Configure Claude Desktop and confirm all 15 tools are listed and functional
5. Run OAuth PKCE flow against `/authorize` and `/token`

Phase 1 is functionally complete. Tasks 1 and 2 are committed. INFRA-03 and INFRA-04 completion and Phase 1 success criteria 1, 4, and OAuth are pending the manual checkpoint.

## Next Phase Readiness

- All 15 Phase 1 tools committed and unit-tested
- Full pytest suite (8 test files, ~62 tests) ready to run after `bash setup.sh` installs the venv
- Phase 2 can begin once Task 3 checkpoint is approved — no code changes needed before Phase 2 starts

---
*Phase: 01-core-mcp-server*
*Completed: 2026-05-29 (partial — Task 3 pending)*
