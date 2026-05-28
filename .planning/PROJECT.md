# knowledge-os-mcp

## What This Is

A personal, persistent, compounding knowledge base built on Obsidian — maintained by Claude, accessible from any device. A FastAPI-based MCP server runs on a local laptop, exposed via Cloudflare Tunnel, so Claude on any device (phone, desktop, web) can read from and write to the same vault over HTTPS. The vault is a living wiki: every ingested source, query, and operation makes the knowledge base richer.

## Core Value

Claude on any device can query and modify a single persistent Obsidian vault over a secure remote connection — accumulating knowledge that compounds across sessions.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] FastAPI MCP server with SSE transport and bearer token auth running on localhost:8000
- [ ] Cloudflare Tunnel exposes the server at a persistent subdomain
- [ ] Full suite of navigation tools (list_folders, list_notes, get_note_metadata, get_index)
- [ ] Full suite of retrieval tools (search_full_text, get_note_summary, read_note, read_note_section)
- [ ] Full suite of ingestion tools (create_note, append/prepend/insert/update_frontmatter)
- [ ] Maintenance tools (update_index, append_log) keep wiki/index.md and wiki/log.md current
- [ ] URL classification and media ingestion (webpage, video/Whisper, PDF)
- [ ] SQLite FTS5 full-text search with watchdog file sync
- [ ] lint_wiki() health check tool
- [ ] ChromaDB semantic search with local sentence-transformer embeddings
- [ ] Summary cache for token-efficient navigation on mobile

### Out of Scope

- Multi-user access — single user (Dhyey) only; no auth beyond bearer token
- Obsidian Sync — vault is local disk; no cloud sync dependency
- Obsidian Web Clipper auto-trigger — manual ingestion via ingest_webpage() for now
- Git versioning of vault contents — in future scope (§8.6) but not in phases
- DOCX support — PDF primary, DOCX deferred
- Real-time collaboration — not a shared system

## Context

- Architecture is derived from the "LLM Wiki" pattern: raw sources are immutable, wiki layer is LLM-owned, and this document (CLOUD.md) governs operations
- Novel addition is remote access — Cloudflare Tunnel provides persistent HTTPS with no port-forwarding
- Claude Desktop connects via localhost:8000; Claude on phone connects via tunnel URL
- Vault uses Obsidian markdown format with YAML frontmatter; compatible with Dataview plugin out of the box
- Token efficiency is a first-class concern: tiered tools (index → summary → section → full note) minimize tokens per query — critical for mobile usage
- Process management via PM2 for development; systemd for production

## Constraints

- **Language**: Python 3.11+ — Whisper and ChromaDB have Python-first support
- **Transport**: MCP over SSE — required by custom MCP server spec; no websocket alternative
- **Auth**: Bearer token (VAULT_SECRET env var) — simple, sufficient for single-user; no JWT overhead
- **Local-only models**: Whisper (transcription) and sentence-transformers (embeddings) run on laptop CPU/GPU — no external API calls for AI features
- **Vault mutability**: `/raw/` directory is immutable — Claude never modifies raw sources
- **System deps**: ffmpeg required for Whisper audio processing; cloudflared binary for tunnel

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE transport over WebSocket | Simpler server implementation; MCP SDK supports SSE natively | — Pending |
| SQLite FTS5 before ChromaDB | Zero deps, instant setup, handles 95% of queries; ChromaDB adds Phase 3 conceptual search | — Pending |
| Whisper "base" model default | 140MB, fast on CPU; "small" available for better accuracy at 2x slower | — Pending |
| all-MiniLM-L6-v2 embeddings | 80MB, 384-dim, ~50ms/query on CPU — best balance for local use | — Pending |
| Naive file scan in Phase 1 | FTS5 is Phase 2; Phase 1 scan is functional for small vaults during initial setup | — Pending |
| PM2 for process management | Developer-friendly; systemd as production alternative | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-28 after initialization*
