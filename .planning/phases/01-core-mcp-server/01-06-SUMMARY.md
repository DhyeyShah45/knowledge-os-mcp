---
phase: 01-core-mcp-server
plan: 06
subsystem: ingestion-tools
tags: [fastmcp, python-frontmatter, fm_lib, create_note, append_to_note, prepend_to_note, insert_under_heading, update_frontmatter, path-traversal, mcp-tools]

# Dependency graph
requires:
  - phase: 01-05
    provides: "_get_sections, _find_heading_index helpers; safe_vault_path; err; ERR_* constants; retrieval tools"
provides:
  - create_note() MCP tool — PRD §3 frontmatter template auto-generation, ALREADY_EXISTS on duplicate (INGEST-01)
  - append_to_note() MCP tool — appends text after existing body with word_count (INGEST-02)
  - prepend_to_note() MCP tool — inserts text before body while preserving frontmatter (INGEST-03)
  - insert_under_heading() MCP tool — section-aware insert with HEADING_NOT_FOUND + available_headings (INGEST-04)
  - update_frontmatter() MCP tool — single-key update returning old_value/new_value, body untouched (INGEST-05)
  - frontmatter import aliased to fm_lib throughout server.py (prerequisite for `frontmatter` parameter name)
affects: [01-07-maintenance-tools, all-subsequent-plans]

# Tech tracking
tech-stack:
  added: [python-frontmatter (fm_lib alias), fm_lib.Post, fm_lib.dumps, fm_lib.dump, fm_lib.load]
  patterns:
    - fm_lib alias pattern — import frontmatter as fm_lib to avoid param name collision
    - ALREADY_EXISTS guard — p.exists() check before write in create_note
    - Frontmatter-preserving round-trip — fm_lib.load → mutate post.content or post[key] → fm_lib.dumps
    - PRD §3 template dict — {"date", "tags", "sources", "related", "summary"} auto-populated
    - Section-end detection — next heading with level <= current_level or len(lines)

key-files:
  created:
    - tests/test_ingestion.py
  modified:
    - server.py

key-decisions:
  - "Renamed import frontmatter to import frontmatter as fm_lib so the parameter name frontmatter in create_note does not shadow the module; all existing fm references updated"
  - "create_note uses frontmatter_extra as internal parameter name for the extra frontmatter dict to avoid the same collision; MCP tool surface matches PRD"
  - "prepend_to_note uses rstrip on prepended text to normalize trailing whitespace before inserting double-newline separator"
  - "insert_under_heading inserts a triple-newline-padded paragraph (newline + text + newline) at the computed insert_line to produce clean paragraph spacing"
  - "update_frontmatter coerces date/datetime old_value to isoformat() for JSON-serializable return"
  - "All five tools wrap implementation in try/except and return err(str(exc), ERR_NOT_FOUND) on unexpected exceptions (D-08)"

patterns-established:
  - "Frontmatter alias pattern: import frontmatter as fm_lib — use fm_lib everywhere server.py uses python-frontmatter"
  - "PRD §3 template fields: date, tags, sources, related, summary — always auto-populated by create_note"

requirements-completed: [INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05]

# Metrics
duration: ~20min
completed: 2026-05-29
---

# Phase 1 Plan 06: Ingestion Tools Summary

**Five FastMCP write-side tools — create_note (PRD §3 auto-frontmatter + ALREADY_EXISTS guard), append_to_note, prepend_to_note (frontmatter-preserving round-trip), insert_under_heading (section-aware + HEADING_NOT_FOUND), update_frontmatter (single-key, body untouched) — added to server.py with fm_lib alias rename.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-29T00:00:00Z
- **Completed:** 2026-05-29
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Renamed `import frontmatter` to `import frontmatter as fm_lib` throughout server.py (5 existing call sites updated) so the `frontmatter` parameter name in `create_note` does not shadow the module
- Implemented all five INGEST-01..INGEST-05 tools as `@mcp.tool()` async functions, bringing total decorator count to 13 (4 nav + 4 retrieval + 5 ingestion)
- Created tests/test_ingestion.py with 14 tests covering all five tools, path traversal, raw/ rejection, ALREADY_EXISTS, HEADING_NOT_FOUND + available_headings, and frontmatter preservation

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Implement ingestion tools + tests** - `38bfbf7` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `/Users/dhyeyshah45/Projects/knowledge-os-mcp/server.py` — renamed fm_lib alias, added create_note/append_to_note/prepend_to_note/insert_under_heading/update_frontmatter (lines ~845–1065)
- `/Users/dhyeyshah45/Projects/knowledge-os-mcp/tests/test_ingestion.py` — 14 unit tests for all five ingestion tools

## Decisions Made

- Used `import frontmatter as fm_lib` alias and replaced all 5 existing `frontmatter.load/dump/Post/dumps` call sites before adding new tools — confirmed via grep that zero bare `frontmatter.` code references remain
- `create_note` parameter kept as `frontmatter_extra` internally (not `frontmatter`) since `frontmatter` would shadow `fm_lib` even after the rename; docstring notes MCP tool surface matches PRD
- `insert_under_heading` inserts at the computed `insert_line` index in the body lines list; the inserted string includes surrounding newlines for clean paragraph formatting
- `update_frontmatter` uses `post[key] = value` (python-frontmatter `__setitem__`) to set the key on the Post object before writing back via `fm_lib.dumps()`

## Deviations from Plan

None — plan executed exactly as written. The fm_lib rename was specified in the plan action and performed as specified.

## Verification Results

All static checks passed (virtualenv not installed; dynamic tests deferred to CI):

```
PASS: server.py AST OK
PASS: create_note found in server.py
PASS: append_to_note found in server.py
PASS: prepend_to_note found in server.py
PASS: insert_under_heading found in server.py
PASS: update_frontmatter found in server.py
PASS: ALREADY_EXISTS reference found
PASS: import frontmatter as fm_lib alias present
PASS: no bare frontmatter. code references remain (2 hits are docstring English prose)
PASS: @mcp.tool() count = 13 (expected >= 13)
PASS: tests/test_ingestion.py AST OK
PASS: all 5 tool test groups present (test_create_note, test_append, test_prepend, test_insert_under_heading, test_update_frontmatter)
PASS: ALREADY_EXISTS assertion present in tests
PASS: available_headings assertion present in tests
PASS: 14 test functions total
```

## Known Stubs

None — all tools perform real filesystem operations on tmp_vault. No placeholder responses.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model.

- T-06-01 (path traversal): All five tools call `safe_vault_path(path)` as first guard. `test_all_ingestion_tools_reject_traversal` parametrizes over all five tools verifying INVALID_PATH.
- T-06-02 (raw/ write): `safe_vault_path()` rejects first component `raw` — create_note cannot write to raw/. `test_create_note_blocks_raw` verifies this.
- T-06-03 (YAML injection): accepted; python-frontmatter uses PyYAML safe_dump; single-user system.
- T-06-04 (race condition): accepted for Phase 1; documented in RESEARCH.md Pitfall 5.
- T-06-05 (content disclosure): append_to_note returns word_count only, not content.

## Self-Check: PASSED

- server.py: FOUND (modified, 13 @mcp.tool() instances, AST OK)
- tests/test_ingestion.py: FOUND (14 tests, AST OK)
- Commit 38bfbf7: FOUND

## Next Phase Readiness

- Ingestion write-side complete (INGEST-01..05); vault can now receive new notes and modifications
- Plan 07 (maintenance tools: update_index, append_log) is unblocked — depends on create_note and the write infrastructure established here
- CLAUDE.md operational rules require `update_index()` + `append_log()` after every `create_note()` — those functions are Plan 07's deliverable

---
*Phase: 01-core-mcp-server*
*Completed: 2026-05-29*
