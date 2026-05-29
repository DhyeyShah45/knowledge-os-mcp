---
phase: 01-core-mcp-server
plan: 05
status: completed
wave: 4
subsystem: retrieval-tools
tags: [fastmcp, retrieval, full-text-search, python-frontmatter, path-traversal, mcp-tools]
requires: [01-04]
provides:
  - search_full_text() MCP tool — naive rglob wiki/ scan with D-12 scoring (RET-01)
  - get_note_summary() MCP tool — first 200 chars + heading outline (RET-02)
  - read_note() MCP tool — full content + JSON-serializable frontmatter (RET-03)
  - read_note_section() MCP tool — single section extract with available_headings on miss (RET-04)
  - _get_sections() internal helper — markdown heading parser
  - _find_heading_index() internal helper — case-insensitive partial heading search
affects: [all-subsequent-plans]
tech-stack:
  added: [re.compile (already present), pathlib.rglob (stdlib)]
  patterns:
    - _HEADING_RE regex for heading parsing
    - Normalized occurrence-count scoring (D-12)
    - 2-line snippet window centered on first match (D-15)
    - available_headings augmented error dict for HEADING_NOT_FOUND
    - datetime coercion to ISO strings for JSON serialisability
key-files:
  created:
    - tests/test_retrieval.py
  modified:
    - server.py
decisions:
  - "search_full_text uses rglob scoped to VAULT_PATH/wiki — raw/ files are never scanned (D-14)"
  - "Snippet truncation at 150 chars per D-15 (2-line window then hard cap)"
  - "D-12 score computed after top_k slice — max_count is from sorted[0] (already max)"
  - "read_note_section uses level-based section end detection: next heading with level <= current"
  - "available_headings returned as extra key merged into standard error dict (not a separate field)"
  - "15 tests written vs 14 required — added test_get_note_summary_blocks_traversal (Rule 2)"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-29"
  task_count: 2
  file_count: 2
---

# Phase 1 Plan 05: Retrieval Tools Summary

## One-liner

Four FastMCP retrieval tools — search_full_text (naive rglob wiki/ scan), get_note_summary (200-char truncation + heading outline), read_note (full content + frontmatter), read_note_section (single section with available_headings on miss) — added to server.py with D-12..D-15 compliance.

## What was built

### server.py additions (lines 538–844)

**Internal helper functions:**

`_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)`

`_get_sections(content: str) -> list[dict]`
- Scans content line-by-line using a regex match on each line
- Returns `[{"heading": str, "level": int, "start_line": int}, ...]`

`_find_heading_index(sections: list[dict], target: str) -> int | None`
- Case-insensitive partial substring match on heading text
- Returns the first matching index or None

**search_full_text(query: str, top_k: int = 5) — RET-01**
- Empty query fast-path: returns `{"results": []}` immediately
- Iterates `(VAULT_PATH / "wiki").rglob("*.md")` — raw/ excluded (D-14)
- Case-insensitive occurrence count via `content.lower().count(query.lower())` (D-13)
- 2-line snippet: matching line + next line (or prev line if at end), truncated to 150 chars (D-15)
- Frontmatter title resolution via `frontmatter.load()`, falls back to stem
- Sort by `_count` descending, slice to `top_k`, then normalize scores (D-12)
- Single result → score 1.0; multiple results → `score = count / max_count`

**get_note_summary(path: str) — RET-02**
- Validates via `safe_vault_path(path)`; rejects traversal and raw/ access
- Returns NOT_FOUND for missing files or non-`.md` extensions
- `summary = body[:200]` — hard 200-char cap per PRD §5.2
- `headings = [s["heading"] for s in _get_sections(body)]`
- `word_count = len(body.split())`
- Returns `{title, summary, headings, word_count}` — full body excluded

**read_note(path: str) — RET-03**
- Validates via `safe_vault_path(path)`
- Loads with `frontmatter.load()`; coerces datetime/date values in `post.metadata` to ISO strings
- Returns `{path, title, frontmatter (dict), content (str)}`

**read_note_section(path: str, heading: str) — RET-04**
- Validates via `safe_vault_path(path)`
- Reads raw content; parses sections with `_get_sections`
- Heading match via `_find_heading_index` (case-insensitive partial)
- Section end: next heading with `level <= current_level`
- On miss: returns error dict merged with `available_headings: [...]` per CONTEXT.md Specifics

### tests/test_retrieval.py (15 tests)

| Test | Tool | What it verifies |
|------|------|-----------------|
| `test_search_empty_query_returns_empty` | RET-01 | `""` → `{"results": []}` |
| `test_search_finds_keyword` | RET-01 | 5-count note is first; scores 1.0 and 0.2 (D-12) |
| `test_search_case_insensitive` | RET-01 | `"TRANSFORMER"` matches lowercase body (D-13) |
| `test_search_respects_top_k` | RET-01 | 7 notes seeded; `top_k=3` returns exactly 3 |
| `test_search_snippet_is_short` | RET-01 | snippet ≤ 200 chars containing query (D-15) |
| `test_search_scoped_to_wiki` | RET-01 | raw/ file not in results; wiki note appears (D-14) |
| `test_get_note_summary_truncates_at_200` | RET-02 | 500-char body → summary ≤ 200 |
| `test_get_note_summary_extracts_headings` | RET-02 | headings == `["Overview", "Attention", "Mechanism"]` |
| `test_get_note_summary_missing` | RET-02 | missing file → NOT_FOUND |
| `test_get_note_summary_blocks_traversal` | RET-02 | `../../etc/passwd` → INVALID_PATH |
| `test_read_note_returns_content_and_frontmatter` | RET-03 | path, title, frontmatter (dict), content (str) present |
| `test_read_note_invalid_path` | RET-03 | `../etc/passwd` → INVALID_PATH |
| `test_read_note_missing_file` | RET-03 | missing file → NOT_FOUND |
| `test_read_note_section_extracts_section` | RET-04 | "mech" matches "## Mech"; body1 in, body2 out |
| `test_read_note_section_heading_not_found_returns_available` | RET-04 | HEADING_NOT_FOUND + available_headings list |
| `test_read_note_section_blocks_traversal` | RET-04 | `../foo` → INVALID_PATH |

## Verification Results

All static checks passed (virtualenv not installed; dynamic tests deferred to CI):

```
PASS: server.py AST OK
PASS: search_full_text found in server.py
PASS: get_note_summary found in server.py
PASS: read_note found in server.py
PASS: read_note_section found in server.py
PASS: _get_sections found in server.py
PASS: _find_heading_index found in server.py
PASS: available_headings literal found
PASS: wiki scope + rglob found in server.py
PASS: @mcp.tool() count = 8 (expected >= 8)
PASS: tests/test_retrieval.py AST OK
PASS: All 14 required test function names present
```

## Deviations from Plan

### One extra test added — get_note_summary INVALID_PATH case

**Found during:** Task 2 test file creation
**Issue:** Plan §acceptance_criteria specified "At least one INVALID_PATH test per path-taking tool (read_note, read_note_section, get_note_summary)". The task behavior section listed only `test_get_note_summary_missing` for RET-02. The acceptance criteria explicitly required an INVALID_PATH test for `get_note_summary`.
**Fix:** Added `test_get_note_summary_blocks_traversal` — total 15 tests vs 14 required.
**Rule:** Rule 2 (auto-add missing critical functionality — INVALID_PATH coverage required by plan acceptance criteria).

## Known Stubs

None — all four tools perform real filesystem operations on the tmp_vault in tests. No hardcoded empty values or placeholder responses in production paths.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model.

- T-05-01 (Path traversal via path args): `get_note_summary`, `read_note`, `read_note_section` all call `safe_vault_path()` as the first guard. Tests verify `INVALID_PATH` for traversal inputs.
- T-05-02 (raw/ information disclosure): `search_full_text` iterates `VAULT_PATH / "wiki"` only — raw/ is structurally excluded, not filtered. `test_search_scoped_to_wiki` verifies no raw/ path leaks.
- T-05-03 (DoS on huge vault): accepted for Phase 1; Phase 2 replaces with FTS5.
- T-05-04 (read_note returning raw/ content): `safe_vault_path()` rejects first component `raw` before any filesystem access.

## Self-Check: PASSED

- server.py: FOUND (modified, 8 @mcp.tool() instances, AST OK)
- tests/test_retrieval.py: FOUND (15 tests, AST OK)
- Commit 811d0c8: FOUND
