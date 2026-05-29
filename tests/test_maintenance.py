"""Unit tests for maintenance MCP tools — MAINT-01 (update_index) and MAINT-02 (append_log).

Tests use tmp_vault and vault_env fixtures from conftest.py and reload the
server module so each test sees the fixture's VAULT_PATH.

asyncio_mode = "auto" is configured in pyproject.toml — no @pytest.mark.asyncio
decorator is needed.

Tests:
  1.  test_update_index_inserts_under_category      — MAINT-01 insert new entry
  2.  test_update_index_upserts_existing_entry       — MAINT-01 upsert (RESEARCH A7)
  3.  test_update_index_refreshes_totals             — MAINT-01 header totals
  4.  test_update_index_rejects_unknown_category     — MAINT-01 (T-07-01)
  5.  test_update_index_missing_index_file           — MAINT-01 NOT_FOUND
  6.  test_append_log_writes_prd_format              — MAINT-02 PRD §3 format
  7.  test_append_log_prepends_below_header          — MAINT-02 newest-first (PRD §3)
  8.  test_append_log_rejects_unknown_operation      — MAINT-02 (T-07-02)
  9.  test_append_log_missing_log_file               — MAINT-02 NOT_FOUND
  10. test_full_phase1_suite_discovery               — meta smoke-test: 7 test files present
"""

from __future__ import annotations

import importlib
import re
from datetime import date
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper: reload server so VAULT_PATH matches the fixture's tmp_vault.
# ---------------------------------------------------------------------------


def fresh_server(tmp_vault: Path, vault_env: None):  # noqa: ARG001
    """Reload server module so it picks up the current fixture's VAULT_PATH."""
    import server as srv

    importlib.reload(srv)
    return srv


# ---------------------------------------------------------------------------
# MAINT-01 — update_index
# ---------------------------------------------------------------------------


async def test_update_index_inserts_under_category(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_index inserts a new entry under the correct category section.

    Calls update_index with category="concepts". Reads wiki/index.md and
    asserts the wikilink appears under the "## Concepts" heading.
    """
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.update_index(
        "wiki/concepts/transformer.md", "Attention model", "concepts"
    )

    assert result.get("updated") is True
    assert "entry" in result

    content = (tmp_vault / "wiki" / "index.md").read_text(encoding="utf-8")

    # The wikilink should appear as [[wiki/concepts/transformer]] (no .md)
    assert "[[wiki/concepts/transformer]]" in content

    # And it should be in the Concepts section, not in Entities
    concepts_idx = content.find("## Concepts")
    entities_idx = content.find("## Entities")
    entry_idx = content.find("[[wiki/concepts/transformer]]")

    assert concepts_idx != -1, "## Concepts section not found"
    assert entry_idx != -1, "wikilink entry not found"
    assert entry_idx > concepts_idx, "entry should come after ## Concepts"

    # If Entities appears after Concepts, the entry must come before Entities
    # (i.e. it stays within the Concepts section).
    if entities_idx > concepts_idx:
        assert entry_idx < entities_idx, "entry leaked outside ## Concepts section"


async def test_update_index_upserts_existing_entry(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_index replaces an existing entry for the same path (upsert — RESEARCH A7).

    Calls update_index twice with the same path but different summaries. Reads
    wiki/index.md and asserts only one entry for that path remains, containing
    the second (newer) summary and NOT the first.
    """
    srv = fresh_server(tmp_vault, vault_env)

    path = "wiki/entities/karpathy.md"
    await srv.update_index(path, "v1 summary", "entities")
    await srv.update_index(path, "v2 summary", "entities")

    content = (tmp_vault / "wiki" / "index.md").read_text(encoding="utf-8")

    # Only one wikilink entry for this path should exist
    wikilink_key = "[[wiki/entities/karpathy]]"
    count = content.count(wikilink_key)
    assert count == 1, f"Expected 1 entry for {wikilink_key}, got {count}"

    # The entry must carry the v2 summary, not v1
    assert "v2 summary" in content
    assert "v1 summary" not in content


async def test_update_index_refreshes_totals(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_index refreshes Total pages and Total sources in the header line.

    Adds 4 entries (1 entity, 1 concept, 1 source, 1 query). Asserts the header
    line reads "Total pages: 4" and "Total sources: 1".
    """
    srv = fresh_server(tmp_vault, vault_env)

    await srv.update_index("wiki/entities/alice.md", "A person", "entities")
    await srv.update_index("wiki/concepts/ml.md", "Machine learning", "concepts")
    await srv.update_index("wiki/sources/paper.md", "A source paper", "sources")
    await srv.update_index("wiki/queries/2026-q1.md", "A query answer", "queries")

    content = (tmp_vault / "wiki" / "index.md").read_text(encoding="utf-8")

    assert "Total pages: 4" in content, f"Expected 'Total pages: 4' in:\n{content}"
    assert "Total sources: 1" in content, f"Expected 'Total sources: 1' in:\n{content}"


async def test_update_index_rejects_unknown_category(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_index returns an error dict for an unknown category (T-07-01)."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.update_index("wiki/concepts/foo.md", "desc", "random")

    assert result.get("error") is True


async def test_update_index_missing_index_file(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_index returns NOT_FOUND when wiki/index.md does not exist."""
    (tmp_vault / "wiki" / "index.md").unlink()

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.update_index("wiki/concepts/foo.md", "desc", "concepts")

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# MAINT-02 — append_log
# ---------------------------------------------------------------------------


async def test_append_log_writes_prd_format(
    tmp_vault: Path, vault_env: None
) -> None:
    """append_log writes an entry matching the PRD §3 format.

    Calls append_log("ingest", "Test source", "Notes here"). Reads wiki/log.md
    and asserts the entry has the correct heading format and contains notes.
    """
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.append_log("ingest", "Test source", "Notes here")

    assert result.get("appended") is True
    assert "entry" in result

    content = (tmp_vault / "wiki" / "log.md").read_text(encoding="utf-8")

    # Heading must match ## [YYYY-MM-DD] ingest | Test source
    today = date.today().isoformat()
    expected_heading = f"## [{today}] ingest | Test source"
    assert expected_heading in content, (
        f"Expected heading '{expected_heading}' not found in log:\n{content}"
    )

    assert "Notes here" in content, "'Notes here' not found in log content"


async def test_append_log_prepends_below_header(
    tmp_vault: Path, vault_env: None
) -> None:
    """append_log prepends entries below the header so newest appears first.

    Calls append_log twice with distinct titles (A then B). Reads log.md and
    asserts B's title appears BEFORE A's title in the file (newest-first per PRD §3).
    """
    srv = fresh_server(tmp_vault, vault_env)

    await srv.append_log("ingest", "First entry", "")
    await srv.append_log("query", "Second entry", "")

    content = (tmp_vault / "wiki" / "log.md").read_text(encoding="utf-8")

    idx_first = content.find("First entry")
    idx_second = content.find("Second entry")

    assert idx_first != -1, "'First entry' not found"
    assert idx_second != -1, "'Second entry' not found"
    assert idx_second < idx_first, (
        "'Second entry' (newer) should appear before 'First entry' (older) "
        f"but got positions: second={idx_second}, first={idx_first}"
    )


async def test_append_log_rejects_unknown_operation(
    tmp_vault: Path, vault_env: None
) -> None:
    """append_log returns an error dict for an unknown operation (T-07-02)."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.append_log("invalid_op", "t")

    assert result.get("error") is True


async def test_append_log_missing_log_file(
    tmp_vault: Path, vault_env: None
) -> None:
    """append_log returns NOT_FOUND when wiki/log.md does not exist."""
    (tmp_vault / "wiki" / "log.md").unlink()

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.append_log("ingest", "anything")

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Meta smoke-test — full Phase 1 suite discovery
# ---------------------------------------------------------------------------


def test_full_phase1_suite_discovery() -> None:
    """Verify all 7 Phase 1 test files exist and each contains at least one test_ function.

    This is a static discovery smoke-test.  It does NOT require the virtualenv
    to be active — it simply checks file presence and basic content, which is
    enough to detect a regression where a prior test file was accidentally deleted
    or emptied.

    The 7 expected test files are:
      tests/test_smoke.py
      tests/test_auth.py
      tests/test_oauth.py
      tests/test_infra.py
      tests/test_nav.py
      tests/test_retrieval.py
      tests/test_ingestion.py
      tests/test_maintenance.py  (this file)
    """
    import os

    # Determine tests/ directory relative to this file
    tests_dir = Path(__file__).parent

    expected_files = [
        "test_smoke.py",
        "test_auth.py",
        "test_oauth.py",
        "test_infra.py",
        "test_nav.py",
        "test_retrieval.py",
        "test_ingestion.py",
        "test_maintenance.py",
    ]

    missing = []
    empty = []

    for fname in expected_files:
        fpath = tests_dir / fname
        if not fpath.exists():
            missing.append(fname)
        else:
            text = fpath.read_text(encoding="utf-8")
            if "def test_" not in text and "async def test_" not in text:
                empty.append(fname)

    assert not missing, f"Missing test files: {missing}"
    assert not empty, f"Test files with no test_ functions: {empty}"
