# Requirements: knowledge-os-mcp

**Defined:** 2026-05-28
**Last updated:** 2026-05-29 (INFRA-01 transport corrected to streamable-HTTP per checker feedback)
**Core Value:** Claude on any device can query and modify a single persistent Obsidian vault over a secure remote connection — accumulating knowledge that compounds across sessions.

## v1 Requirements

### Infrastructure

- [x] **INFRA-01**: FastAPI server serves MCP tools over streamable-HTTP transport on port 8000
- [x] **INFRA-02**: All endpoints require bearer token authentication via VAULT_SECRET env var
- [ ] **INFRA-03**: Cloudflare Tunnel exposes the server at a persistent custom subdomain
- [ ] **INFRA-04**: Server process is managed via PM2 with auto-restart on failure
- [x] **INFRA-05**: CLOUD.md operational rules are embedded as the MCP system prompt for Claude

### Navigation

- [ ] **NAV-01**: Claude can retrieve the full vault folder tree with note counts via list_folders()
- [ ] **NAV-02**: Claude can list notes in any folder with paths, titles, and last_modified via list_notes()
- [ ] **NAV-03**: Claude can read note frontmatter and stats without reading body content via get_note_metadata()
- [ ] **NAV-04**: Claude can read wiki/index.md (the master catalog) as the primary navigation entry point via get_index()

### Retrieval

- [ ] **RET-01**: Claude can search all vault markdown files by keyword via search_full_text(), returning snippets and scores
- [ ] **RET-02**: Claude can get a note summary (first 200 chars + heading outline) before committing to a full read via get_note_summary()
- [ ] **RET-03**: Claude can read the full content of a note via read_note()
- [ ] **RET-04**: Claude can read only a specific heading section of a note via read_note_section()

### Ingestion

- [ ] **INGEST-01**: Claude can create a new markdown note with auto-generated frontmatter via create_note()
- [ ] **INGEST-02**: Claude can safely append text to an existing note via append_to_note()
- [ ] **INGEST-03**: Claude can prepend text after frontmatter (for newest-first log entries) via prepend_to_note()
- [ ] **INGEST-04**: Claude can insert text under a specific heading in a note via insert_under_heading()
- [ ] **INGEST-05**: Claude can update a single frontmatter key without touching the note body via update_frontmatter()

### Maintenance

- [ ] **MAINT-01**: Claude can add or update entries in wiki/index.md after every create_note() via update_index()
- [ ] **MAINT-02**: Claude can append timestamped operation entries to wiki/log.md via append_log()

### Media Ingestion

- [ ] **MEDIA-01**: Claude can probe any URL and classify it as video/webpage/document without downloading via classify_url()
- [ ] **MEDIA-02**: Claude can fetch a webpage, extract article body, and save as clean markdown to /raw/webpages/ via ingest_webpage()
- [ ] **MEDIA-03**: Claude can download audio from a video URL, transcribe it locally with Whisper, and save transcript to /raw/transcripts/ via ingest_video()
- [ ] **MEDIA-04**: Claude can download a PDF and extract text to /raw/documents/ via ingest_document()

### Search & Health

- [ ] **SEARCH-01**: search_full_text() is backed by SQLite FTS5 with BM25 ranking (replaces naive file scan)
- [ ] **SEARCH-02**: Watchdog file watcher keeps the SQLite FTS5 index in sync with vault markdown changes
- [ ] **SEARCH-03**: Claude can run a vault health check reporting orphans, broken links, missing pages, and sourceless pages via lint_wiki()

### Semantic Search

- [ ] **SEM-01**: Claude can find conceptually related notes without exact keyword matches via semantic_search() backed by ChromaDB
- [ ] **SEM-02**: Embeddings are computed locally using sentence-transformers all-MiniLM-L6-v2 (no external API calls)
- [ ] **SEM-03**: Note summaries are pre-computed and cached in SQLite for token-efficient navigation
- [ ] **SEM-04**: Watchdog keeps both FTS5 and ChromaDB indices in sync with vault file changes

## v2 Requirements

### Enhanced Search

- **HSEARCH-01**: Hybrid search combines FTS5 keyword score + ChromaDB cosine similarity for re-ranked results
- **HSEARCH-02**: Response caching for repeated queries reduces latency

### Vault Integrations

- **CLIP-01**: Obsidian Web Clipper drops to /raw/webpages/ and watchdog triggers an ingest notification
- **GIT-01**: Vault directory is git-tracked with history for every note change
- **GIT-02**: Auto-commit after each ingest with meaningful commit message

### Extended Ingestion

- **MEDIA-05**: Claude can ingest DOCX documents via ingest_document() (via python-docx)
- **MEDIA-06**: Whisper "small" model option exposed as ingest_video() parameter

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user access | Single-user system by design; bearer token is not user-specific |
| Obsidian Sync | Vault is local disk; cloud sync is Obsidian's concern, not the MCP server's |
| Real-time collaboration | Not a shared knowledge base |
| OAuth / JWT auth | Overkill for single-user remote access; bearer token sufficient |
| Mobile native app | Claude on phone IS the client via claude.ai mobile |
| Video file storage default | Transcript-only by default; video storage always requires user confirmation |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Complete |
| NAV-01 | Phase 1 | Pending |
| NAV-02 | Phase 1 | Pending |
| NAV-03 | Phase 1 | Pending |
| NAV-04 | Phase 1 | Pending |
| RET-01 | Phase 1 | Pending |
| RET-02 | Phase 1 | Pending |
| RET-03 | Phase 1 | Pending |
| RET-04 | Phase 1 | Pending |
| INGEST-01 | Phase 1 | Pending |
| INGEST-02 | Phase 1 | Pending |
| INGEST-03 | Phase 1 | Pending |
| INGEST-04 | Phase 1 | Pending |
| INGEST-05 | Phase 1 | Pending |
| MAINT-01 | Phase 1 | Pending |
| MAINT-02 | Phase 1 | Pending |
| MEDIA-01 | Phase 2 | Pending |
| MEDIA-02 | Phase 2 | Pending |
| MEDIA-03 | Phase 2 | Pending |
| MEDIA-04 | Phase 2 | Pending |
| SEARCH-01 | Phase 2 | Pending |
| SEARCH-02 | Phase 2 | Pending |
| SEARCH-03 | Phase 2 | Pending |
| SEM-01 | Phase 3 | Pending |
| SEM-02 | Phase 3 | Pending |
| SEM-03 | Phase 3 | Pending |
| SEM-04 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-28*
*Last updated: 2026-05-29 — INFRA-01 transport corrected from SSE to streamable-HTTP per CONTEXT.md D-05.*
