# CLOUD.md
## Obsidian Vault — Remote MCP Knowledge Base
### Product Requirements Document (PRD) + System Architecture + Operational Rules

**Version:** 1.0  
**Author:** Dhyey  
**Status:** Implementation Ready  
**Last Updated:** 2026-05-28

---

## Table of Contents

1. [Vision & Context](#1-vision--context)
2. [System Architecture](#2-system-architecture)
3. [Vault Structure](#3-vault-structure)
4. [Phase Breakdown](#4-phase-breakdown)
5. [Tool Specifications](#5-tool-specifications)
6. [Package Dependencies](#6-package-dependencies)
7. [CLOUD.md Operational Rules](#7-cloudmd-operational-rules)
8. [Future Scope](#8-future-scope)

---

## 1. Vision & Context

### What This Is

A personal, persistent, compounding knowledge base — built on Obsidian, maintained by Claude, accessible from any device. The vault is not a static file store. It is a living wiki where every new source, every ingested video, every query answer makes the knowledge base richer.

The pattern is derived from the LLM Wiki architecture: raw sources are immutable, the wiki layer is LLM-owned, and a schema file (this document) governs all operations. The novel addition is remote access — a FastAPI-based MCP server running on a local laptop, exposed via Cloudflare Tunnel, so Claude on any device (phone, desktop, web) can read from and write to the same vault.

### Core Principles

- **Accumulation over retrieval.** Knowledge is compiled once, kept current, not re-derived per query.
- **Claude writes, Dhyey directs.** The LLM handles all bookkeeping. The human handles curation and intent.
- **Token efficiency by design.** Tools are tiered. Claude reads summaries before full notes. The index is always the first call.
- **Source agnosticism.** Text files, webpages, PDFs, YouTube videos, podcasts — all become markdown in `/raw/`.
- **Remote-first.** The system is designed assuming the client (phone) and the server (laptop) are always on separate devices.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTS                              │
│                                                             │
│   Claude on Phone          Claude Desktop (laptop)          │
│   (claude.ai mobile)       (MCP config: localhost)          │
└──────────────┬──────────────────────────┬───────────────────┘
               │ HTTPS (custom MCP)        │ HTTP localhost
               ▼                          ▼
┌──────────────────────────────────────────────────────────────┐
│                   Cloudflare Tunnel                          │
│              vault.yourdomain.com → localhost:8000           │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              FastAPI MCP Server  (localhost:8000)            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Navigation  │  │  Retrieval   │  │    Ingestion     │   │
│  │   Tools      │  │   Tools      │  │    Tools         │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Maintenance  │  │  URL/Media   │  │  Search Engine   │   │
│  │   Tools      │  │   Tools      │  │  (Phase 2/3)     │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  Obsidian Vault (local disk)                 │
│                                                              │
│  /raw/          immutable source documents                   │
│  /wiki/         LLM-maintained wiki pages                    │
│  /wiki/index.md master catalog                               │
│  /wiki/log.md   append-only operation log                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. System Architecture

### Components

#### 2.1 FastAPI MCP Server

- Language: Python 3.11+
- Framework: FastAPI
- Transport: Streamable HTTP (MCP spec) mounted at `/mcp`
- Port: 8000 (local), exposed via Cloudflare Tunnel
- Auth: Bearer token (`VAULT_SECRET`) + OAuth 2.0 PKCE for claude.ai remote
- Process manager: launchd (macOS) via `~/Library/LaunchAgents/` plist

The server exposes tools as MCP-compatible endpoints. Claude connects to it as a custom MCP server via the SSE URL.

#### 2.2 Cloudflare Tunnel

- Persistent subdomain (no URL rotation)
- Zero port-forwarding required
- Free tier sufficient
- Installed as a native launchd service via `sudo cloudflared service install <token>`
- Token-based setup — no `config.yml` required when using the dashboard flow

#### 2.3 Obsidian Vault

- Local directory, not synced to Obsidian Sync
- MCP server has full read/write access
- Claude Desktop connects directly via `localhost:8000`
- Claude on phone connects via Cloudflare Tunnel URL

#### 2.4 Whisper (Phase 2)

- `openai-whisper` Python package
- Runs locally on laptop CPU/GPU
- Model: `base` (140MB, fast) or `small` (244MB, better accuracy)
- Called by `ingest_video()` tool after audio download

#### 2.5 Search Index (Phase 2 / Phase 3)

- Phase 2: SQLite FTS5 — shadow index of all vault markdown files
- Phase 3: ChromaDB — vector embeddings for semantic search
- Both maintained by the MCP server, rebuilt on file changes via watchdog

---

## 3. Vault Structure

```
obsidian-vault/
│
├── raw/                          # IMMUTABLE — never modified by Claude
│   ├── sources/                  # Manually added files
│   ├── webpages/                 # Ingested via ingest_webpage()
│   ├── transcripts/              # Video/audio transcripts
│   ├── videos/                   # Optional: stored video files
│   ├── documents/                # PDFs and docs
│   └── assets/                   # Images referenced by wiki pages
│
├── wiki/                         # CLAUDE-OWNED — fully managed by LLM
│   ├── index.md                  # Master catalog — ALWAYS read first
│   ├── log.md                    # Append-only operation log
│   ├── overview.md               # High-level synthesis of the entire wiki
│   ├── entities/                 # Pages for people, companies, products
│   ├── concepts/                 # Pages for ideas, frameworks, topics
│   ├── sources/                  # Summary pages per ingested source
│   └── queries/                  # Valuable query answers filed as pages
│
└── CLOUD.md                      # This file — schema and rules
```

### index.md Format

```markdown
# Vault Index
Last updated: YYYY-MM-DD | Total pages: N | Total sources: N

## Entities
- [[entities/andrej-karpathy]] — AI researcher, OpenAI/Tesla. 3 sources.
- [[entities/sam-altman]] — OpenAI CEO. 2 sources.

## Concepts
- [[concepts/transformer-architecture]] — Attention mechanisms, BERT, GPT. 5 sources.
- [[concepts/rag-vs-finetuning]] — Retrieval vs. parameter updates. 2 sources.

## Sources
- [[sources/karpathy-llm-wiki]] — LLM Wiki pattern for personal knowledge bases.
- [[sources/attention-is-all-you-need]] — Original transformer paper.

## Queries
- [[queries/2026-05-01-rag-comparison]] — Comparison of RAG architectures.
```

### log.md Format

```markdown
## [2026-05-28] ingest | Andrej Karpathy — LLM Wiki
Pages touched: sources/llm-wiki, concepts/rag, entities/karpathy, index.md
Notes: New concept page created for wiki-pattern. Karpathy entity updated.

## [2026-05-28] query | What is the difference between RAG and finetuning?
Answer filed: queries/2026-05-28-rag-vs-finetuning
Pages read: concepts/rag-vs-finetuning, concepts/transformer-architecture

## [2026-05-28] lint | Weekly health check
Orphans found: 2. Contradictions: 1 (noted in overview.md). Gaps: 3 new pages suggested.
```

### Note Frontmatter Template

```yaml
---
date: YYYY-MM-DD
tags: []
sources: []
related: []
summary: ""
---
```

---

## 4. Phase Breakdown

### Phase 1 — Core MCP Server (Text & File Access)

**Goal:** A working MCP server on the laptop that Claude on phone can connect to and use for basic vault read/write operations.

**Scope:**
- FastAPI server with SSE transport
- Bearer token authentication
- All Navigation tools
- All basic Retrieval tools (no search engine — file scan only)
- All Ingestion tools
- All Maintenance tools
- Cloudflare Tunnel setup
- CLOUD.md schema enforced via system prompt

**What Claude can do in Phase 1:**
- Browse vault structure
- Read notes by path
- Search notes by keyword (naive file scan)
- Create, append, and update notes
- Maintain index.md and log.md
- Answer questions from vault content

**What is NOT in Phase 1:**
- Video/audio ingestion
- Webpage fetching
- Full-text search index (uses naive scan)
- Semantic search
- Whisper transcription

**Deliverable:** A running server where Claude on phone can query and write to the Obsidian vault over a secure HTTPS connection.

---

### Phase 2 — Media Ingestion + ELP (Enriched Language Processing)

**Goal:** Any URL — webpage, YouTube video, podcast, PDF — can be ingested into the vault. Whisper provides local transcription. SQLite FTS5 provides fast full-text search.

**Scope:**
- `classify_url()` tool
- `ingest_webpage()` tool (readability + markdownify)
- `ingest_video()` tool (yt-dlp + Whisper)
- `ingest_document()` tool (PDF text extraction)
- SQLite FTS5 search index (replaces naive file scan)
- `search_full_text()` now queries SQLite, not raw files
- File watcher (watchdog) to keep SQLite index in sync
- `lint_wiki()` tool

**What Claude can do in Phase 2:**
- Accept any URL and classify it automatically
- Ingest YouTube/podcast transcripts
- Ingest web articles as clean markdown
- Ingest PDFs
- Fast keyword search across entire vault
- Run lint passes and report vault health

**Deliverable:** Full source ingestion pipeline. Any content format becomes a searchable wiki page.

---

### Phase 3 — Token Efficiency + Semantic Search

**Goal:** Minimize tokens consumed per query. Claude reads the minimum necessary content through tiered retrieval. Semantic search enables conceptual queries without exact keywords.

**Scope:**
- ChromaDB vector store (local, on-device)
- `sentence-transformers` embeddings (model: `all-MiniLM-L6-v2`, 80MB)
- `semantic_search()` tool
- `get_note_summary()` now returns AI-generated summaries (cached)
- Summary cache — pre-computed 200-char summaries for every wiki page
- `read_note_section()` — reads only one heading section
- Embedding index kept in sync with watchdog
- Response caching for repeated queries

**What Claude can do in Phase 3:**
- Find conceptually related notes without exact keyword matches
- Read section-level content instead of full notes
- Use cached summaries to navigate without full reads
- Operate within tight token budgets on mobile

**Deliverable:** A fully optimized, semantically-aware knowledge base that Claude can navigate with minimal token cost per interaction.

---

## 5. Tool Specifications

All tools are exposed as MCP tools via FastAPI. Each tool is a Python async function decorated with the MCP tool registration pattern.

---

### 5.1 Navigation Tools

These tools return pointers and metadata — never full note content. Token cost is minimal.

---

#### `list_folders()`

```
Purpose:    Returns the full folder tree of the vault
Phase:      1
Returns:    List of folder paths with note counts
Token cost: Tiny (~100 tokens)
```

```python
async def list_folders() -> dict:
    """
    Returns:
    {
      "folders": [
        {"path": "wiki/entities", "note_count": 12},
        {"path": "wiki/concepts", "note_count": 34},
        ...
      ]
    }
    """
```

---

#### `list_notes(folder: str = None)`

```
Purpose:    Lists notes in a folder (or root). Returns paths and titles only — no content.
Phase:      1
Returns:    List of {path, title, last_modified}
Token cost: Tiny (~200 tokens for 50 notes)
```

```python
async def list_notes(folder: str = None) -> dict:
    """
    Returns:
    {
      "notes": [
        {"path": "wiki/concepts/transformer.md", "title": "Transformer Architecture", "last_modified": "2026-05-20"},
        ...
      ]
    }
    """
```

---

#### `get_note_metadata(path: str)`

```
Purpose:    Returns frontmatter + stats for a note without reading body content
Phase:      1
Returns:    {title, date, tags, sources, related, word_count, last_modified}
Token cost: Small (~80 tokens)
```

```python
async def get_note_metadata(path: str) -> dict:
    """
    Returns:
    {
      "title": "Transformer Architecture",
      "date": "2026-05-10",
      "tags": ["ml", "attention", "nlp"],
      "sources": ["attention-is-all-you-need"],
      "related": ["concepts/bert", "concepts/gpt"],
      "word_count": 842,
      "last_modified": "2026-05-20"
    }
    """
```

---

#### `get_index()`

```
Purpose:    Reads wiki/index.md — the master catalog. MUST be the first call on any query.
Phase:      1
Returns:    Full content of index.md
Token cost: Medium (~800–1500 tokens depending on vault size)
Note:       This is the navigation entry point. Claude reads this to decide which notes
            to look at. It avoids blind searching.
```

```python
async def get_index() -> dict:
    """
    Returns:
    {
      "content": "# Vault Index\n...",
      "total_pages": 87,
      "total_sources": 34,
      "last_updated": "2026-05-28"
    }
    """
```

---

### 5.2 Retrieval Tools

Used after navigation tools have identified candidate notes. Token costs are higher — use sparingly.

---

#### `search_full_text(query: str, top_k: int = 5)`

```
Purpose:    Keyword search across all vault markdown files
Phase:      1 — naive file scan (slow but functional)
Phase:      2 — SQLite FTS5 (fast, ranked results)
Returns:    List of {path, title, snippet, score}
Token cost: Small (snippets only, ~50 tokens per result)
Note:       Returns 2-line context snippets, not full note content.
            Claude uses these to decide which notes to read fully.
```

```python
async def search_full_text(query: str, top_k: int = 5) -> dict:
    """
    Returns:
    {
      "results": [
        {
          "path": "wiki/concepts/transformer.md",
          "title": "Transformer Architecture",
          "snippet": "...the attention mechanism allows the model to...",
          "score": 0.94
        },
        ...
      ]
    }
    """
```

---

#### `get_note_summary(path: str)`

```
Purpose:    Returns first 200 chars + heading outline of a note.
            Used to confirm relevance BEFORE calling read_note().
Phase:      1 — extracts from file on demand
Phase:      3 — returns from pre-computed summary cache
Returns:    {title, summary, headings, word_count}
Token cost: Small (~150 tokens)
```

```python
async def get_note_summary(path: str) -> dict:
    """
    Returns:
    {
      "title": "Transformer Architecture",
      "summary": "The transformer model introduced in 'Attention Is All You Need' replaced...",
      "headings": ["Overview", "Attention Mechanism", "Multi-Head Attention", "Applications"],
      "word_count": 842
    }
    """
```

---

#### `read_note(path: str)`

```
Purpose:    Returns full content of a note.
            ONLY call after get_note_summary() confirms relevance.
Phase:      1
Returns:    {path, title, content, frontmatter}
Token cost: Large (full note — can be 500–2000 tokens)
Rule:       Never call without first calling get_note_summary() or search_full_text().
```

```python
async def read_note(path: str) -> dict:
    """
    Returns:
    {
      "path": "wiki/concepts/transformer.md",
      "title": "Transformer Architecture",
      "frontmatter": {...},
      "content": "## Overview\n\nThe transformer model..."
    }
    """
```

---

#### `read_note_section(path: str, heading: str)`

```
Purpose:    Reads ONLY the content under a specific heading. Surgical read.
            Use when you know which section has the answer.
Phase:      1
Returns:    {path, heading, content}
Token cost: Medium (~200–600 tokens, section only)
Note:       Heading match is case-insensitive, partial match supported.
```

```python
async def read_note_section(path: str, heading: str) -> dict:
    """
    Returns:
    {
      "path": "wiki/concepts/transformer.md",
      "heading": "Attention Mechanism",
      "content": "The attention mechanism computes a weighted sum..."
    }
    """
```

---

#### `semantic_search(query: str, top_k: int = 5)`

```
Purpose:    Embedding-based search. Finds conceptually related notes
            even without exact keyword matches.
Phase:      3 only
Returns:    List of {path, title, similarity_score, snippet}
Token cost: Small (snippets only)
Requires:   ChromaDB + sentence-transformers (Phase 3)
```

```python
async def semantic_search(query: str, top_k: int = 5) -> dict:
    """
    Returns:
    {
      "results": [
        {
          "path": "wiki/concepts/attention.md",
          "title": "Attention Mechanisms",
          "similarity_score": 0.87,
          "snippet": "..."
        }
      ]
    }
    """
```

---

### 5.3 Ingestion Tools

These tools create or modify notes. All writes are logged automatically.

---

#### `create_note(path: str, content: str, tags: list = [], frontmatter: dict = {})`

```
Purpose:    Creates a new markdown note at the given path.
Phase:      1
Behavior:   Fails if path already exists (use append_to_note instead).
            Auto-generates frontmatter if not provided.
            Does NOT update index.md — Claude must call update_index() after.
Returns:    {path, created, word_count}
```

```python
async def create_note(
    path: str,
    content: str,
    tags: list = [],
    frontmatter: dict = {}
) -> dict:
    """
    Returns:
    {
      "path": "wiki/concepts/new-topic.md",
      "created": true,
      "word_count": 312
    }
    """
```

---

#### `append_to_note(path: str, text: str)`

```
Purpose:    Appends text to the end of an existing note. Safe, non-destructive.
Phase:      1
Behavior:   Adds a newline before appended text.
            Preferred over create_note for adding to existing notes.
Returns:    {path, appended, new_word_count}
```

```python
async def append_to_note(path: str, text: str) -> dict
```

---

#### `prepend_to_note(path: str, text: str)`

```
Purpose:    Adds text immediately after the frontmatter, before body content.
Phase:      1
Use case:   Timestamped daily log entries where newest appears first.
Returns:    {path, prepended, new_word_count}
```

```python
async def prepend_to_note(path: str, text: str) -> dict
```

---

#### `insert_under_heading(path: str, heading: str, text: str)`

```
Purpose:    Inserts text at the end of a specific section (under a heading).
Phase:      1
Behavior:   Heading match is case-insensitive. Inserts before the next heading.
            Fails gracefully if heading not found — returns error with available headings.
Returns:    {path, heading_found, inserted}
```

```python
async def insert_under_heading(path: str, heading: str, text: str) -> dict
```

---

#### `update_frontmatter(path: str, key: str, value)`

```
Purpose:    Updates a single frontmatter key without touching the body.
Phase:      1
Use case:   Adding tags, updating source lists, marking notes as reviewed.
Returns:    {path, key, old_value, new_value}
```

```python
async def update_frontmatter(path: str, key: str, value) -> dict
```

---

### 5.4 Maintenance Tools

These tools keep the vault healthy and navigable.

---

#### `update_index(path: str, summary: str, category: str)`

```
Purpose:    Adds or updates a single entry in wiki/index.md.
Phase:      1
Behavior:   Claude calls this after every create_note() operation.
            Category must be one of: entities, concepts, sources, queries.
Returns:    {updated, entry}
```

```python
async def update_index(path: str, summary: str, category: str) -> dict
```

---

#### `append_log(operation: str, title: str, notes: str = "")`

```
Purpose:    Appends a timestamped entry to wiki/log.md.
Phase:      1
Behavior:   Claude calls this after every ingest, query (if valuable), and lint.
            Format: ## [YYYY-MM-DD] {operation} | {title}
Operations: ingest | query | lint | update
Returns:    {appended, entry}
```

```python
async def append_log(operation: str, title: str, notes: str = "") -> dict
```

---

#### `lint_wiki()`

```
Purpose:    Health check of the entire wiki. Reports issues, does not auto-fix.
Phase:      2
Checks:
  - Orphan pages (no inbound links from other wiki pages)
  - Stale cross-references (links pointing to non-existent pages)
  - Concepts mentioned in notes but lacking their own page
  - Pages with no sources listed in frontmatter
  - index.md entries missing actual files
Returns:    {orphans, broken_links, missing_pages, sourceless_pages, suggestions}
Behavior:   Returns a structured report. Claude presents it to user before
            taking any action. Never auto-deletes or auto-modifies.
```

```python
async def lint_wiki() -> dict:
    """
    Returns:
    {
      "orphans": ["wiki/concepts/old-topic.md"],
      "broken_links": [{"from": "wiki/entities/x.md", "to": "wiki/concepts/missing.md"}],
      "missing_pages": ["neural-scaling-laws", "moe-architecture"],
      "sourceless_pages": ["wiki/queries/2026-04-01-question.md"],
      "suggestions": ["Consider creating a page for 'mixture of experts'"]
    }
    """
```

---

### 5.5 URL & Media Ingestion Tools

---

#### `classify_url(url: str)`

```
Purpose:    Probes a URL and classifies it without downloading content.
Phase:      2
Method:     Try yt-dlp --simulate first. Fall back to HTTP Content-Type header.
Returns:    {type, title, duration_seconds, size_estimate_mb, url}
Types:      video | webpage | document | unknown
Token cost: Tiny (metadata only)
Note:       Always the FIRST call when a URL is provided.
            Never download without classifying first.
```

```python
async def classify_url(url: str) -> dict:
    """
    Returns (video):
    {
      "type": "video",
      "title": "Andrej Karpathy — Let's build GPT",
      "duration_seconds": 7823,
      "size_estimate_mb": {"audio_only": 48, "video_720p": 820},
      "url": "https://youtube.com/watch?v=..."
    }

    Returns (webpage):
    {
      "type": "webpage",
      "title": "The Illustrated Transformer",
      "duration_seconds": null,
      "size_estimate_mb": {"content": 0.2},
      "url": "https://jalammar.github.io/..."
    }
    """
```

---

#### `ingest_webpage(url: str)`

```
Purpose:    Fetches a webpage, strips to clean markdown, saves to /raw/webpages/.
Phase:      2
Method:     requests → readability-lxml (extract article body) → markdownify
Filename:   Slugified title + date (e.g., illustrated-transformer-2026-05-28.md)
Returns:    {path, title, word_count, url}
Frontmatter auto-set: date, source_url, tags (empty, for Claude to fill)
```

```python
async def ingest_webpage(url: str) -> dict
```

---

#### `ingest_video(url: str, store_video: bool = False)`

```
Purpose:    Downloads audio from video URL, transcribes with Whisper,
            saves transcript to /raw/transcripts/.
Phase:      2
Pipeline:
  1. yt-dlp downloads audio only (mp3/m4a, much smaller than video)
  2. openai-whisper transcribes to text
  3. Audio file deleted after transcription (unless store_video=True)
  4. Transcript saved as markdown with frontmatter
  5. If store_video=True, video file saved to /raw/videos/

Whisper model: "base" (default) — balance of speed and accuracy
               "small" — better accuracy, ~2x slower

Returns:    {transcript_path, title, duration_seconds, video_path (if stored)}

Behavior:
  - Short video (<10 min): ask user once if they want video stored
  - Long video (>30 min): explicitly recommend transcript-only, still ask
  - Never store video without user confirmation

Frontmatter auto-set: source_url, title, duration, transcribed_date, tags
```

```python
async def ingest_video(url: str, store_video: bool = False) -> dict
```

---

#### `ingest_document(url: str)`

```
Purpose:    Downloads a PDF or document and extracts text to /raw/documents/.
Phase:      2
Method:     requests download → pdfminer.six text extraction
Returns:    {path, title, page_count, word_count}
Supports:   PDF (primary). DOCX support optional via python-docx.
```

```python
async def ingest_document(url: str) -> dict
```

---

## 6. Package Dependencies

### 6.1 Phase 1 — Core Server

```toml
# pyproject.toml or requirements.txt

# Server
fastapi==0.111.0
uvicorn[standard]==0.30.0
python-dotenv==1.0.1
pydantic==2.7.0

# MCP transport
mcp==1.0.0                    # Official Anthropic MCP Python SDK

# File handling
python-frontmatter==1.1.0     # Parse/write YAML frontmatter in markdown
pathlib                        # stdlib, no install needed
watchdog==4.0.0               # File system watcher (used in Phase 2/3 but install now)

# Auth
python-jose==3.3.0            # JWT if needed in future; bearer token is simpler for now
```

### 6.2 Phase 2 — Media Ingestion

```toml
# Video/audio
yt-dlp==2024.5.27             # URL classification + audio download (500+ sites)
openai-whisper==20231117      # Local transcription (requires ffmpeg system package)

# Webpage ingestion
requests==2.32.2
readability-lxml==0.8.1       # Article body extraction (removes nav, ads, etc.)
markdownify==0.12.1           # HTML to markdown conversion

# PDF ingestion
pdfminer.six==20221105        # PDF text extraction

# Full-text search
# SQLite FTS5 is built into Python's sqlite3 stdlib — no package needed
# Just use: import sqlite3

# System dependency (install via brew/apt, not pip)
# ffmpeg                       # Required by Whisper for audio processing
```

### 6.3 Phase 3 — Semantic Search

```toml
# Vector embeddings
sentence-transformers==3.0.0  # Local embedding model (all-MiniLM-L6-v2, 80MB)
chromadb==0.5.0               # Local vector store, persists to disk

# Embedding model will auto-download on first run (~80MB)
# Model: sentence-transformers/all-MiniLM-L6-v2
```

### 6.4 System Dependencies (not pip)

```bash
# macOS
brew install ffmpeg            # Required for Whisper audio processing
brew install cloudflared       # Cloudflare Tunnel

# Ubuntu/Debian
sudo apt install ffmpeg
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

### 6.5 Process Management

Both processes run as native macOS launchd services — no Node.js or PM2 required.

**uvicorn (MCP server):**
- Managed via `~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist`
- Started by `start-server.sh` which sources `.env` at runtime
- `launchctl load ~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist`

**Cloudflare Tunnel:**
- Installed as a system service: `sudo cloudflared service install <token>`
- Managed by launchd at `/Library/LaunchDaemons/com.cloudflare.cloudflared.plist`
- Survives reboots automatically

---

## 7. CLOUD.md Operational Rules

*This section is the system prompt / skill injected into Claude when connecting to the MCP server. It governs Claude's behavior for all vault operations.*

---

### Identity

You have access to Dhyey's Obsidian knowledge vault via a local MCP server running on his laptop. The vault is a persistent, compounding knowledge base. You are its maintainer. Dhyey is the curator and director.

Your job: handle all bookkeeping — summarizing, cross-referencing, filing, indexing, logging. Dhyey's job: decide what to add, what to explore, what to question.

---

### Query Rules

1. **Always call `get_index()` first.** Never start a query by searching blindly. Read the index, identify candidate pages, then drill in.
2. **Never call `read_note()` without first calling `get_note_summary()`.** Confirm relevance cheaply before reading fully.
3. **Prefer `read_note_section()` over `read_note()` when the target heading is known.**
4. **Use `search_full_text()` when the index doesn't give enough signal.** Try 2–3 alternative phrasings if first search returns nothing.
5. **File valuable answers.** If a query produces a useful synthesis or comparison, call `create_note()` to save it in `wiki/queries/`. Call `update_index()` and `append_log()` after.
6. **Ask one clarifying question if the query is ambiguous.** Do not guess intent.

---

### Ingest Rules

When a source (URL, file, text) is provided for ingestion:

1. Classify the source type first.
   - URL → call `classify_url()`
   - File → check extension
   - Raw text → proceed directly
2. For URLs: always present title, type, and size estimate before downloading.
3. For videos > 30 minutes: recommend transcript-only and ask for confirmation.
4. For videos of any length: ask if video file should be stored. Default is transcript-only.
5. After download/fetch: run the full ingest pipeline —
   a. `create_note()` — summary page in `wiki/sources/`
   b. `search_full_text()` — find related wiki pages
   c. Update related pages (cross-references, contradictions, new data)
   d. `update_index()` — add new page entry
   e. `append_log()` — log the ingest with pages touched
6. Never modify anything in `/raw/`. It is immutable.
7. Never rewrite a note when `append_to_note()` will do.
8. Surface contradictions explicitly. Do not silently overwrite existing claims.
9. Auto-generate frontmatter on every new note: date, tags (inferred), sources, related.

---

### Ingestion Frontmatter Template

```yaml
---
date: YYYY-MM-DD
tags: []           # infer from content
sources: []        # source file or URL
related: []        # links to related wiki pages
summary: ""        # one-sentence summary
---
```

---

### Lint Rules

When asked to lint the vault:

1. Call `lint_wiki()` to generate the report.
2. Present the full report to the user before taking any action.
3. Do not auto-delete orphan pages — ask first.
4. Do not auto-fix broken links — ask which resolution is correct.
5. Suggest new pages to create for missing concepts — but create only on confirmation.
6. Call `append_log("lint", "Weekly health check", summary_of_findings)` after.

---

### Storage Decisions

| Condition | Default action |
|---|---|
| Any URL | Always call `classify_url()` first |
| Video < 10 min | Ask once: store video or transcript only? |
| Video > 30 min | Recommend transcript-only, still ask |
| File > 500MB | Always ask before storing |
| Unknown URL type | Tell user, ask how to proceed |
| PDF/document | Download and extract — no confirmation needed unless > 100MB |
| Webpage | Fetch and convert — no confirmation needed |

---

### What Never to Do

- Never read a full note without first reading its summary
- Never start a query without reading the index
- Never create a note without calling `update_index()` after
- Never modify files in `/raw/`
- Never store video without user confirmation
- Never auto-fix lint issues without confirmation
- Never overwrite an existing note — append, prepend, or insert under heading instead
- Never fabricate content — only synthesize from vault sources

---

## 8. Future Scope

### 8.1 SQLite FTS5 (Phase 2 Search)

SQLite's built-in full-text search engine. No external dependencies. Runs entirely in-process.

**Schema:**
```sql
CREATE VIRTUAL TABLE vault_fts USING fts5(
  path,
  title,
  content,
  tags,
  tokenize = "porter unicode61"   -- porter stemming + unicode support
);
```

**Sync strategy:** `watchdog` monitors the vault directory. On any markdown file change (create/modify/delete), the corresponding FTS row is updated.

**Search query:** BM25 ranking is built into FTS5. Returns ranked results with snippet extraction via `snippet()` function.

**Why this before ChromaDB:** Zero dependencies, instant setup, works on any machine, good enough for 95% of queries. ChromaDB adds conceptual search that FTS5 can't do.

---

### 8.2 ChromaDB Semantic Search (Phase 3)

Local vector database. Persists embeddings to disk. No network calls.

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`
- 80MB download, cached locally after first run
- 384-dimensional embeddings
- Fast on CPU (~50ms per query)

**Collection structure:**
```python
collection = chroma_client.get_or_create_collection(
    name="vault",
    metadata={"hnsw:space": "cosine"}
)

# Each document = one wiki page
collection.add(
    ids=[note_path],
    documents=[note_content],
    metadatas=[{"title": ..., "tags": ..., "date": ...}]
)
```

**Hybrid search (Phase 3 goal):** Combine FTS5 keyword score + ChromaDB cosine similarity for re-ranked results. This is the qmd approach from the LLM Wiki doc, implemented locally.

**Sync strategy:** Same `watchdog` watcher updates both FTS5 and ChromaDB on file changes. Embeddings are computed once and cached.

---

### 8.3 Summary Cache (Phase 3)

Pre-computed summaries stored in a SQLite table alongside FTS5.

```sql
CREATE TABLE note_summaries (
  path TEXT PRIMARY KEY,
  title TEXT,
  summary TEXT,        -- first 200 chars
  headings TEXT,       -- JSON array of heading strings
  word_count INTEGER,
  last_modified TEXT,
  embedding_id TEXT    -- reference to ChromaDB entry
);
```

`get_note_summary()` in Phase 3 reads from this cache instead of opening files. Cache is invalidated when `watchdog` detects a file change.

---

### 8.4 Obsidian Web Clipper Integration

The Obsidian Web Clipper browser extension (from the LLM Wiki doc) converts web articles to markdown directly into the vault's `/raw/webpages/` folder. This complements `ingest_webpage()` for cases where Dhyey wants to clip directly from the browser rather than asking Claude to fetch a URL.

When a new file appears in `/raw/webpages/`, `watchdog` can trigger an auto-ingest notification — Claude can ask on next interaction whether to process it.

---

### 8.5 Dataview-Compatible Frontmatter

All wiki pages use YAML frontmatter (already specified in the template). This means Obsidian's Dataview plugin can query the vault without any additional setup. Example Dataview query that works out of the box:

```dataview
TABLE date, tags, summary
FROM "wiki/concepts"
SORT date DESC
```

---

### 8.6 Git Version Control

The vault is a directory of markdown files. Adding a git repo gives:
- Full change history for every note
- Ability to see what Claude changed during an ingest
- Rollback if an ingest corrupts a wiki page
- Branch-based experimentation

Recommended `.gitignore`:
```
raw/videos/          # Large video files
*.db                 # SQLite index (rebuild on clone)
chroma_db/           # Vector store (rebuild on clone)
__pycache__/
.env
```

---

*End of CLOUD.md*
