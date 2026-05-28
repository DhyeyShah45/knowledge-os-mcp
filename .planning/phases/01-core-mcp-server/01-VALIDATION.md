---
phase: 1
slug: core-mcp-server
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
revised: 2026-05-29
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio + httpx |
| **Config file** | `pyproject.toml [tool.pytest]` — created by Plan 01-02 |
| **Quick run command** | `pytest tests/ -x -q --ignore=tests/test_infra.py` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --ignore=tests/test_infra.py`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Requirement | Threat Ref | Test Type | Automated Command | File Owner | Status |
|---------|-------------|------------|-----------|-------------------|------------|--------|
| auth middleware | INFRA-02 | Missing bearer token | unit | `pytest tests/test_auth.py::test_bearer_auth -x` | 01-03 (TDD) | ⬜ pending |
| server bootstrap | INFRA-01, INFRA-05 | — | smoke | `pytest tests/test_infra.py::test_server_starts -x` | 01-03 (TDD) | ⬜ pending |
| instructions injection | INFRA-05 | — | unit | `pytest tests/test_infra.py::test_instructions_injected -x` | 01-03 (TDD) | ⬜ pending |
| oauth pkce flow | INFRA-02 (D-16) | OAuth code replay | unit | `pytest tests/test_oauth.py -x` | 01-03 (TDD) | ⬜ pending |
| list_folders | NAV-01 | — | unit | `pytest tests/test_nav.py::test_list_folders -x` | 01-04 (TDD) | ⬜ pending |
| list_notes | NAV-02 | — | unit | `pytest tests/test_nav.py::test_list_notes -x` | 01-04 (TDD) | ⬜ pending |
| get_note_metadata | NAV-03 | — | unit | `pytest tests/test_nav.py::test_get_note_metadata -x` | 01-04 (TDD) | ⬜ pending |
| get_index | NAV-04 | — | unit | `pytest tests/test_nav.py::test_get_index -x` | 01-04 (TDD) | ⬜ pending |
| search_full_text | RET-01 | — | unit | `pytest tests/test_retrieval.py::test_search -x` | 01-05 (TDD) | ⬜ pending |
| get_note_summary | RET-02 | — | unit | `pytest tests/test_retrieval.py::test_get_note_summary -x` | 01-05 (TDD) | ⬜ pending |
| read_note | RET-03 | — | unit | `pytest tests/test_retrieval.py::test_read_note -x` | 01-05 (TDD) | ⬜ pending |
| read_note_section | RET-04 | — | unit | `pytest tests/test_retrieval.py::test_read_note_section -x` | 01-05 (TDD) | ⬜ pending |
| create_note | INGEST-01 | Path traversal | unit | `pytest tests/test_ingestion.py::test_create_note -x` | 01-06 (TDD) | ⬜ pending |
| append_to_note | INGEST-02 | — | unit | `pytest tests/test_ingestion.py::test_append_to_note -x` | 01-06 (TDD) | ⬜ pending |
| prepend_to_note | INGEST-03 | — | unit | `pytest tests/test_ingestion.py::test_prepend_to_note -x` | 01-06 (TDD) | ⬜ pending |
| insert_under_heading | INGEST-04 | — | unit | `pytest tests/test_ingestion.py::test_insert_under_heading -x` | 01-06 (TDD) | ⬜ pending |
| update_frontmatter | INGEST-05 | — | unit | `pytest tests/test_ingestion.py::test_update_frontmatter -x` | 01-06 (TDD) | ⬜ pending |
| update_index | MAINT-01 | — | unit | `pytest tests/test_maintenance.py::test_update_index -x` | 01-07 (TDD) | ⬜ pending |
| append_log | MAINT-02 | — | unit | `pytest tests/test_maintenance.py::test_append_log -x` | 01-07 (TDD) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements (owned by Plan 01-02 only)

Wave 0 is the test-infrastructure scaffold that all later plans depend on. Plan 01-02 is the SOLE owner of Wave 0; it creates exactly these artifacts and nothing else:

- [ ] `tests/conftest.py` — shared fixtures: `tmp_vault` (creates temp directory, seeds `wiki/index.md`, `wiki/log.md`, and `CLAUDE.md`), `vault_env` (sets `VAULT_PATH`, `VAULT_SECRET`, `OAUTH_CLIENT_ID`, `OAUTH_REDIRECT_URI` env vars for the test run)
- [ ] `tests/test_smoke.py` — single sanity test that proves conftest loads and pytest discovery works (e.g., `def test_tmp_vault_fixture_creates_dirs(tmp_vault): assert (tmp_vault / "wiki").is_dir()`)
- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` block with `asyncio_mode = "auto"` and any required test paths; lists `pytest`, `pytest-asyncio`, `httpx` as dev dependencies
- [ ] Framework install: `pip install pytest pytest-asyncio httpx` (Plan 01-02 task creates / updates `requirements.txt` or `pyproject.toml` accordingly)

## Per-Plan Test File Ownership (NOT Wave 0)

Each later plan creates its own test files using TDD (write failing test first, then implementation):

| Test File | Owner Plan | Wave | Tools Covered |
|-----------|-----------|------|---------------|
| `tests/test_auth.py` | 01-03 | 2 | Bearer middleware (INFRA-02) |
| `tests/test_oauth.py` | 01-03 | 2 | OAuth PKCE flow (D-16) |
| `tests/test_infra.py` | 01-03 | 2 | Server bootstrap, MCP instructions injection (INFRA-01, INFRA-05) |
| `tests/test_nav.py` | 01-04 | 3 | list_folders, list_notes, get_note_metadata, get_index (NAV-01..04) |
| `tests/test_retrieval.py` | 01-05 | 3 | search_full_text, get_note_summary, read_note, read_note_section (RET-01..04) |
| `tests/test_ingestion.py` | 01-06 | 3 | create_note, append_to_note, prepend_to_note, insert_under_heading, update_frontmatter (INGEST-01..05) |
| `tests/test_maintenance.py` | 01-07 | 3 | update_index, append_log (MAINT-01..02) |

These files are NOT Wave 0 — they ship inside their owning plan's TDD step. Wave 0 (Plan 01-02) only delivers the `conftest.py`, `test_smoke.py`, and `pyproject.toml` scaffold.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cloudflare Tunnel accessible from external URL | INFRA-03 | Requires live cloudflared + DNS config + external network | Configure tunnel via dashboard, access from phone browser |
| PM2 auto-restarts server on crash | INFRA-04 | Requires live PM2 session + process kill | Run `pm2 start ecosystem.config.js`, kill the uvicorn pid, verify pm2 restarts |
| Claude on phone connects via claude.ai mobile | Success Criteria #1 | Requires OAuth flow + live tunnel | Connect via claude.ai mobile MCP connector, complete OAuth handshake, call get_index() |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 scope is precisely what Plan 01-02 creates (conftest.py + test_smoke.py + pyproject.toml only)
- [ ] Per-plan test files are owned by their TDD plan (not by Wave 0)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

*Revised 2026-05-29 — Wave 0 scope clarified per checker BLOCKER 3: Wave 0 (Plan 01-02) creates only conftest.py / test_smoke.py / pyproject.toml. Per-tool test files (test_auth, test_oauth, test_infra, test_nav, test_retrieval, test_ingestion, test_maintenance) are created in their owning plans (01-03 through 01-07) using TDD.*
