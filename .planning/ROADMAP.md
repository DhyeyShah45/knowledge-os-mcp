# Roadmap: knowledge-os-mcp

## Overview

Three vertical phases deliver a fully operational remote knowledge base. Phase 1 ships a working MCP server that Claude on phone can connect to today. Phase 2 adds media ingestion and indexed full-text search, making any URL an ingestible source. Phase 3 adds semantic search and token-efficiency optimizations, completing a knowledge base Claude can navigate cheaply from mobile.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Core MCP Server** - FastAPI server with streamable-HTTP transport, OAuth 2.0 PKCE + bearer auth, Cloudflare Tunnel, and all 15 navigation/retrieval/ingestion/maintenance tools
- [ ] **Phase 2: Media Ingestion + Full-Text Search** - URL classification, media ingestion pipeline (webpage/video/PDF), SQLite FTS5 search, and vault health check
- [ ] **Phase 3: Semantic Search + Token Efficiency** - ChromaDB vector search, local sentence-transformer embeddings, summary cache, and unified watchdog sync

## Phase Details

### Phase 1: Core MCP Server
**Goal**: Claude on any device can connect to the vault over a secure HTTPS connection and perform full read/write/maintenance operations against Obsidian markdown files
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, NAV-01, NAV-02, NAV-03, NAV-04, RET-01, RET-02, RET-03, RET-04, INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, MAINT-01, MAINT-02
**Success Criteria** (what must be TRUE):
  1. Claude on phone can call get_index() via the Cloudflare Tunnel URL and receive the vault catalog without authentication errors
  2. Claude can create a new note with auto-generated frontmatter, append text to it, and read it back in the same session
  3. Claude can search vault markdown files by keyword via search_full_text() and receive ranked snippets
  4. After every create_note() call, update_index() adds the entry to wiki/index.md and append_log() records the operation in wiki/log.md
  5. Server process survives a restart (PM2 auto-restarts it) and the CLAUDE.md rules are injected as the MCP system prompt
**Plans**: 7 plans
Plans:
- [x] 01-01-PLAN.md — Project scaffold: requirements.txt, .env.example, .gitignore, init_vault.py, CLAUDE.md, setup.sh, ecosystem.config.js, README.md (+ package legitimacy checkpoint)
- [x] 01-02-PLAN.md — Test harness: pyproject.toml pytest config + tests/conftest.py with tmp_vault fixture + smoke test
- [x] 01-03-PLAN.md — Server bootstrap: server.py with FastMCP + streamable-HTTP + BearerAuthMiddleware + OAuth 2.0 PKCE endpoints + path/error helpers + auth/oauth/infra tests
- [ ] 01-04-PLAN.md — Navigation tools: list_folders, list_notes, get_note_metadata, get_index + tests
- [ ] 01-05-PLAN.md — Retrieval tools: search_full_text (naive scan), get_note_summary, read_note, read_note_section + tests
- [ ] 01-06-PLAN.md — Ingestion tools: create_note, append_to_note, prepend_to_note, insert_under_heading, update_frontmatter + tests
- [ ] 01-07-PLAN.md — Maintenance tools: update_index (upsert), append_log + tests + end-to-end deployment verification checkpoint

**Wave dependency notes:**
- Wave 1: Plans 01-01 + 01-02 — run in parallel (disjoint files)
- Wave 2 *(blocked on Wave 1 completion)*: Plan 01-03
- Wave 3 *(blocked on Wave 2 completion)*: Plan 01-04
- Wave 4 *(blocked on Wave 3 completion)*: Plan 01-05
- Wave 5 *(blocked on Wave 4 completion)*: Plan 01-06
- Wave 6 *(blocked on Wave 5 completion)*: Plan 01-07

**Cross-cutting constraints:**
- `safe_vault_path()` must exist in server.py before tool plans (01-04 through 01-07) run
- All tool errors return `{"error": true, "message": "...", "code": "..."}` — never raise HTTPException (D-08)
- OAuth bypass paths constant (`OAUTH_BYPASS_PATHS`) is single source of truth for /authorize and /token exclusions

### Phase 2: Media Ingestion + Full-Text Search
**Goal**: Any URL — webpage, YouTube video, podcast, or PDF — can be ingested into the vault as clean markdown, and all vault content is searchable via a ranked SQLite FTS5 index
**Depends on**: Phase 1
**Requirements**: MEDIA-01, MEDIA-02, MEDIA-03, MEDIA-04, SEARCH-01, SEARCH-02, SEARCH-03
**Success Criteria** (what must be TRUE):
  1. Claude can call classify_url() on a YouTube link and receive type, title, duration, and size estimate before any download begins
  2. Claude can ingest a webpage URL and find the extracted markdown saved under /raw/webpages/ with correct frontmatter
  3. Claude can ingest a video URL and find the Whisper-generated transcript saved under /raw/transcripts/ — no video file stored by default
  4. search_full_text() returns BM25-ranked results from the SQLite FTS5 index; a new note appears in results within seconds of being created (watchdog sync)
  5. Claude can call lint_wiki() and receive a structured report of orphans, broken links, missing pages, and sourceless pages
**Plans**: TBD
**UI hint**: no

### Phase 3: Semantic Search + Token Efficiency
**Goal**: Claude can find conceptually related notes without exact keyword matches and navigate the vault within tight token budgets using cached summaries and section-level reads
**Depends on**: Phase 2
**Requirements**: SEM-01, SEM-02, SEM-03, SEM-04
**Success Criteria** (what must be TRUE):
  1. Claude can call semantic_search() with a conceptual query and receive results for notes that contain no exact keyword from the query
  2. Embeddings are computed entirely on-device using sentence-transformers all-MiniLM-L6-v2 — no external API calls during search
  3. get_note_summary() returns pre-computed summaries from the SQLite cache rather than opening note files on every call
  4. Both the FTS5 index and the ChromaDB vector store reflect a newly created note within the same watchdog sync cycle
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core MCP Server | 3/7 | In Progress|  |
| 2. Media Ingestion + Full-Text Search | 0/TBD | Not started | - |
| 3. Semantic Search + Token Efficiency | 0/TBD | Not started | - |
