---
plan: 01-02
phase: 01-core-mcp-server
status: completed
wave: 1
subsystem: test-harness
tags: [testing, pytest, fixtures, conftest]
requires: []
provides: [pytest-config, tmp_vault-fixture, test-harness]
affects: [all-subsequent-plans]
tech-stack:
  added: [pytest-asyncio]
  patterns: [function-scoped-fixtures, monkeypatch-env, inline-vault-scaffolding]
key-files:
  created:
    - pyproject.toml
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_smoke.py
  modified: []
decisions:
  - "Inlined vault scaffolding in conftest.py instead of importing init_vault.py to avoid parallel-plan dependency"
  - "Used alias `_fm_lib` for `import frontmatter` to avoid shadowing the `frontmatter: dict` parameter in make_note"
  - "vault_env fixture uses monkeypatch (not direct os.environ mutation) per threat T-02-01"
metrics:
  completed: "2026-05-29"
---
# Phase 1 Plan 02: Test Harness Summary

## One-liner
pytest-asyncio harness with inline-scaffolded `tmp_vault` fixture, `vault_env` monkeypatched env fixture, and `make_note` helper for seeding vault content in tests.

## What was built

- **pyproject.toml** — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `python_files = "test_*.py"`, `addopts = "-ra"`
- **tests/__init__.py** — empty package marker so pytest resolves conftest fixtures correctly from the project root
- **tests/conftest.py** — three fixtures/helpers:
  - `tmp_vault` (function-scoped): creates a fresh vault directory tree (10 subdirs: raw/{webpages,transcripts,videos,documents,assets,sources}, wiki/{entities,concepts,sources,queries}), seeds wiki/index.md and wiki/log.md with canonical content, and writes a CLAUDE.md placeholder at the vault root. Vault scaffolding is inlined so the fixture has no dependency on init_vault.py existing.
  - `vault_env` (function-scoped): uses pytest monkeypatch to set VAULT_PATH, VAULT_SECRET, OAUTH_CLIENT_ID, OAUTH_REDIRECT_URI for the duration of each test, then auto-reverts (T-02-01 mitigation).
  - `make_note(vault, rel, frontmatter, body)`: helper that writes a markdown note with YAML frontmatter; tries python-frontmatter library first, falls back to manual serialization if unavailable.
- **tests/test_smoke.py** — two smoke tests: `test_smoke` (trivial 1+1==2) and `test_smoke_vault_fixture` (verifies tmp_vault produces wiki/index.md and wiki/log.md with correct headers)

## Verification

All verify commands passed:
```
test -f pyproject.toml && test -f tests/__init__.py && test -f tests/conftest.py && test -f tests/test_smoke.py && grep -q 'asyncio_mode' pyproject.toml && grep -q 'tmp_vault' tests/conftest.py
```

Python AST parse succeeded for both conftest.py and test_smoke.py.

git commit `66b1599` created: "feat(tests): test harness with pytest-asyncio config and tmp_vault fixture"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `frontmatter` parameter/module name collision in make_note**
- **Found during:** Task 2 implementation review
- **Issue:** The `make_note` function parameter `frontmatter: dict` shared the exact same name as `import frontmatter` (python-frontmatter library), causing the import to shadow the dict parameter in the local scope, making `**frontmatter` unpack the module and `frontmatter.items()` call `.items()` on the module rather than the dict.
- **Fix:** Saved the dict to `fm_dict` before the try block; imported the library as `_fm_lib` to avoid shadowing.
- **Files modified:** tests/conftest.py
- **Commit:** included in 66b1599

## Known Stubs

None — this plan creates only test infrastructure with no UI or data-flow components.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. All changes are test-only code.

## Self-Check: PASSED

- pyproject.toml: FOUND
- tests/__init__.py: FOUND
- tests/conftest.py: FOUND (tmp_vault, vault_env, make_note all present)
- tests/test_smoke.py: FOUND
- Commit 66b1599: FOUND
