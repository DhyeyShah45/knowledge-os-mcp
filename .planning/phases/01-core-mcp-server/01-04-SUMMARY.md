---
phase: 01-core-mcp-server
plan: 04
status: completed
wave: 3
subsystem: navigation-tools
tags: [fastmcp, navigation, python-frontmatter, path-traversal, mcp-tools]
requires: [01-03]
provides:
  - list_folders() MCP tool — wiki/ folder tree with per-folder note counts (NAV-01)
  - list_notes() MCP tool — directory listing with title and last_modified (NAV-02)
  - get_note_metadata() MCP tool — frontmatter fields + word_count without body (NAV-03)
  - get_index() MCP tool — full wiki/index.md content with parsed header stats (NAV-04)
affects: [all-subsequent-plans]
tech-stack:
  added: [python-frontmatter, re (stdlib), datetime.date (stdlib)]
  patterns:
    - @mcp.tool() async function registration
    - safe_vault_path() guard on all path inputs
    - err() canonical error dict for all I/O failures
    - frontmatter.load() for title resolution and metadata extraction
    - regex header parsing for structured stats from index.md
key-files:
  created:
    - tests/test_nav.py
  modified:
    - server.py
decisions:
  - "Navigation tools scope is wiki/ only — list_folders and list_notes never expose raw/ filenames"
  - "list_notes defaults folder to 'wiki' when argument is None — enables zero-arg entry point"
  - "get_note_metadata silently skips unparseable notes in list_notes; returns error in direct metadata call"
  - "get_index uses regex over header line (not YAML) because index.md header is a custom free-text format"
  - "word_count computed via post.content.split() — body only, frontmatter excluded (python-frontmatter contract)"
  - "12 tests written vs 10 required — added test_list_folders_empty and test_list_folders_missing_wiki (Rule 2)"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-29"
  task_count: 2
  file_count: 2
---

# Phase 1 Plan 04: Navigation Tools Summary

## One-liner

Four FastMCP navigation tools — list_folders, list_notes, get_note_metadata, get_index — added to server.py with python-frontmatter integration and safe_vault_path guards on all user-supplied paths.

## What was built

### server.py additions (lines 343–541)

Four `@mcp.tool()` async functions appended before `app.mount("/mcp", mcp_app)`:

**list_folders() — NAV-01**
- Walks `VAULT_PATH / "wiki"` using `os.walk`, skipping hidden directories
- Returns `{"folders": [{"path": "wiki/entities", "note_count": N}, ...]}` sorted by path
- Counts direct-child `*.md` files per directory (non-recursive within each dir)
- Returns `{"folders": []}` if `wiki/` does not exist (vault not initialized)

**list_notes(folder: str = None) — NAV-02**
- Defaults `folder` to `"wiki"` when omitted
- Validates via `safe_vault_path(folder)` — returns INVALID_PATH on traversal
- Returns NOT_FOUND if resolved path is not a directory
- For each `.md` file: loads frontmatter, resolves title (frontmatter `title` → stem fallback)
- Returns `{"notes": [{"path": ..., "title": ..., "last_modified": "YYYY-MM-DD"}, ...]}`

**get_note_metadata(path: str) — NAV-03**
- Validates via `safe_vault_path(path)`; rejects traversal and raw/ access
- Returns NOT_FOUND for missing files or non-`.md` extensions
- Loads with `frontmatter.load()`; coerces date field to ISO string
- Returns `{title, date, tags, sources, related, word_count, last_modified}` — no body content
- Body is intentionally excluded: `word_count = len(post.content.split())`

**get_index() — NAV-04**
- Reads `VAULT_PATH / "wiki" / "index.md"` directly (no user path input — no traversal risk)
- Parses header line via `r"Last updated:\s*(\S+)\s*\|\s*Total pages:\s*(\d+)\s*\|\s*Total sources:\s*(\d+)"`
- Falls back to `last_updated=""`, `total_pages=0`, `total_sources=0` if header is absent/malformed
- Returns `{content, total_pages, total_sources, last_updated}`

**New imports added to server.py:**
- `import re` (stdlib)
- `from datetime import date` (stdlib)
- `import frontmatter` (python-frontmatter package)

### tests/test_nav.py (12 tests)

| Test | Tool | What it verifies |
|------|------|-----------------|
| `test_list_folders_returns_wiki_subdirs` | NAV-01 | Seeded vault returns folders; wiki/concepts has note_count == 2 |
| `test_list_folders_empty_wiki_returns_folders` | NAV-01 | Empty vault still returns wiki/ folder list |
| `test_list_folders_missing_wiki_returns_empty` | NAV-01 | Missing wiki/ dir returns `{"folders": []}` |
| `test_list_notes_defaults_to_wiki` | NAV-02 | No-arg call defaults to wiki/; entry shape is correct |
| `test_list_notes_with_folder` | NAV-02 | Explicit folder; returns single note with correct title |
| `test_list_notes_invalid_path_returns_error` | NAV-02 | `../../etc` → INVALID_PATH |
| `test_list_notes_nonexistent_folder` | NAV-02 | Missing folder → NOT_FOUND |
| `test_get_note_metadata_returns_frontmatter` | NAV-03 | title, tags, sources, word_count correct; `content` key absent |
| `test_get_note_metadata_missing_file` | NAV-03 | Missing note → NOT_FOUND |
| `test_get_note_metadata_blocks_traversal` | NAV-03 | `../../etc/passwd` → INVALID_PATH |
| `test_get_index_parses_header` | NAV-04 | total_pages=42, total_sources=17, last_updated="2026-05-29" |
| `test_get_index_missing_returns_error` | NAV-04 | Deleted index.md → NOT_FOUND |

## Verification Results

All static checks passed (virtualenv not installed; dynamic tests deferred):

```
PASS: @mcp.tool() found (4 instances)
PASS: async def list_folders found
PASS: async def list_notes found
PASS: async def get_note_metadata found
PASS: async def get_index found
PASS: import frontmatter found
PASS: safe_vault_path calls in list_notes and get_note_metadata
PASS: server.py AST OK
PASS: test_nav.py exists (12 tests)
PASS: test_list_folders found
PASS: test_list_notes found
PASS: test_get_note_metadata found
PASS: test_get_index found
PASS: test_nav.py AST OK
PASS: no HTTPException in tool sections (D-08 satisfied)
```

## Deviations from Plan

### Two extra list_folders tests added

**Found during:** Task 2 test file creation
**Issue:** The plan specified 1 list_folders test (`test_list_folders_returns_wiki_subdirs`). Two additional edge cases were clearly important for correctness: empty wiki/ and missing wiki/ directory.
**Fix:** Added `test_list_folders_empty_wiki_returns_folders` and `test_list_folders_missing_wiki_returns_empty` — total 3 list_folders tests vs 1 required.
**Rule:** Rule 2 (auto-add missing critical functionality — correctness for initialization edge cases)

### Plan tool names vs PRD alignment

The task prompt referenced `get_note` and `get_raw_source` as the planned tools. The actual PLAN.md (authoritative) specifies `get_note_metadata` and `get_index`. The PLAN.md specification was followed exactly — the prompt description was an informal summary, not the spec.

## Known Stubs

None — all four tools are fully implemented with real filesystem operations. `list_notes` and `get_note_metadata` read real frontmatter from disk. `get_index` reads and parses the real index.md file. No hardcoded empty values or placeholder responses.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model.

- T-04-01 (Path traversal): `list_notes` and `get_note_metadata` both call `safe_vault_path()` before any filesystem access; `test_list_notes_invalid_path_returns_error` and `test_get_note_metadata_blocks_traversal` assert INVALID_PATH on `../` paths.
- T-04-02 (raw/ information disclosure): `list_folders` and `list_notes` are scoped to `wiki/` only via `os.walk(wiki_dir)` and `safe_vault_path()` raw/ rejection; raw/ filenames never appear in responses.
- T-04-03 (DoS on large vault): accepted for Phase 1 per plan disposition.

## Self-Check: PASSED

- server.py: FOUND (modified, 4 @mcp.tool() instances, AST OK)
- tests/test_nav.py: FOUND (12 tests, AST OK)
- Commit d2f7b7a: FOUND
