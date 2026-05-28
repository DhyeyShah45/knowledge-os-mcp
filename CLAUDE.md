<!-- GSD:project-start source:PROJECT.md -->
## Project

**knowledge-os-mcp**

A personal, persistent, compounding knowledge base built on Obsidian — maintained by Claude, accessible from any device. A FastAPI-based MCP server runs on a local laptop, exposed via Cloudflare Tunnel, so Claude on any device (phone, desktop, web) can read from and write to the same vault over HTTPS. The vault is a living wiki: every ingested source, query, and operation makes the knowledge base richer.

**Core Value:** Claude on any device can query and modify a single persistent Obsidian vault over a secure remote connection — accumulating knowledge that compounds across sessions.

### Constraints

- **Language**: Python 3.11+ — Whisper and ChromaDB have Python-first support
- **Transport**: MCP over SSE — required by custom MCP server spec; no websocket alternative
- **Auth**: Bearer token (VAULT_SECRET env var) — simple, sufficient for single-user; no JWT overhead
- **Local-only models**: Whisper (transcription) and sentence-transformers (embeddings) run on laptop CPU/GPU — no external API calls for AI features
- **Vault mutability**: `/raw/` directory is immutable — Claude never modifies raw sources
- **System deps**: ffmpeg required for Whisper audio processing; cloudflared binary for tunnel
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
