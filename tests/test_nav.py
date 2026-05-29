"""Unit tests for navigation MCP tools — NAV-01..NAV-04.

These tests use the tmp_vault and vault_env fixtures from conftest.py and
reload the server module so each test sees the fixture's VAULT_PATH rather
than any real vault that may be on disk.

asyncio_mode = "auto" is configured in pyproject.toml — no @pytest.mark.asyncio
decorator is needed.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# conftest.py exports make_note as a plain function, not a fixture.
from tests.conftest import make_note


# ---------------------------------------------------------------------------
# Helper: reload server so VAULT_PATH matches the fixture's tmp_vault.
# ---------------------------------------------------------------------------


def fresh_server(tmp_vault: Path, vault_env: None):  # noqa: ARG001  (vault_env sets env)
    """Reload server module so it picks up the current fixture's VAULT_PATH."""
    import server as srv

    importlib.reload(srv)
    return srv


# ---------------------------------------------------------------------------
# NAV-01 — list_folders
# ---------------------------------------------------------------------------


async def test_list_folders_returns_wiki_subdirs(tmp_vault: Path, vault_env: None) -> None:
    """list_folders returns an entry for each subfolder under wiki/ with note counts."""
    # Seed notes in two sub-folders so we have known counts.
    make_note(tmp_vault, "wiki/concepts/note_a.md", {"title": "A"}, "body a")
    make_note(tmp_vault, "wiki/concepts/note_b.md", {"title": "B"}, "body b")
    make_note(tmp_vault, "wiki/entities/person.md", {"title": "Person"}, "body p")

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.list_folders()

    assert "folders" in result
    entries = result["folders"]
    assert isinstance(entries, list)

    # Every entry must have the required keys.
    for entry in entries:
        assert "path" in entry
        assert "note_count" in entry

    # wiki/concepts should report 2 notes.
    concepts_entry = next((e for e in entries if e["path"] == "wiki/concepts"), None)
    assert concepts_entry is not None, "wiki/concepts folder not found in result"
    assert concepts_entry["note_count"] == 2


async def test_list_folders_empty_wiki_returns_folders(tmp_vault: Path, vault_env: None) -> None:
    """list_folders returns folders list even when no notes exist."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.list_folders()

    assert "folders" in result
    assert isinstance(result["folders"], list)
    # wiki/ itself should be in the list (it exists from the scaffold).
    paths = [e["path"] for e in result["folders"]]
    assert "wiki" in paths


async def test_list_folders_missing_wiki_returns_empty(tmp_vault: Path, vault_env: None) -> None:
    """list_folders returns empty list when wiki/ directory does not exist."""
    import shutil

    shutil.rmtree(tmp_vault / "wiki")

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.list_folders()

    assert result == {"folders": []}


# ---------------------------------------------------------------------------
# NAV-02 — list_notes
# ---------------------------------------------------------------------------


async def test_list_notes_defaults_to_wiki(tmp_vault: Path, vault_env: None) -> None:
    """list_notes() with no argument defaults to the wiki/ folder."""
    make_note(tmp_vault, "wiki/index.md", {"title": "Index"}, "# Index")

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.list_notes()

    assert "notes" in result
    for entry in result["notes"]:
        assert "path" in entry
        assert "title" in entry
        assert "last_modified" in entry


async def test_list_notes_with_folder(tmp_vault: Path, vault_env: None) -> None:
    """list_notes with an explicit folder returns notes from that folder."""
    make_note(
        tmp_vault,
        "wiki/entities/karpathy.md",
        {"title": "Andrej Karpathy"},
        "body",
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.list_notes("wiki/entities")

    assert "notes" in result
    notes = result["notes"]
    assert len(notes) == 1
    assert notes[0]["title"] == "Andrej Karpathy"
    assert "karpathy.md" in notes[0]["path"]


async def test_list_notes_invalid_path_returns_error(tmp_vault: Path, vault_env: None) -> None:
    """list_notes with a traversal path returns INVALID_PATH error dict."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.list_notes("../../etc")

    assert result.get("error") is True
    assert result.get("code") == "INVALID_PATH"


async def test_list_notes_nonexistent_folder(tmp_vault: Path, vault_env: None) -> None:
    """list_notes on a folder that doesn't exist returns NOT_FOUND error dict."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.list_notes("wiki/does-not-exist")

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# NAV-03 — get_note_metadata
# ---------------------------------------------------------------------------


async def test_get_note_metadata_returns_frontmatter(tmp_vault: Path, vault_env: None) -> None:
    """get_note_metadata returns frontmatter fields + stats; body content is absent."""
    # "word " * 50 produces exactly 50 words.
    make_note(
        tmp_vault,
        "wiki/concepts/t.md",
        {"title": "T", "tags": ["a", "b"], "sources": ["s1"]},
        "word " * 50,
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_note_metadata("wiki/concepts/t.md")

    # Required fields present.
    assert result.get("title") == "T"
    assert result.get("tags") == ["a", "b"]
    assert result.get("sources") == ["s1"]
    assert "word_count" in result
    # "word " * 50 produces 50 tokens when split on whitespace.
    assert 48 <= result["word_count"] <= 52, f"Expected ~50 words, got {result['word_count']}"
    assert "last_modified" in result

    # Body content MUST NOT be present.
    assert "content" not in result


async def test_get_note_metadata_missing_file(tmp_vault: Path, vault_env: None) -> None:
    """get_note_metadata on a missing file returns NOT_FOUND error dict."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_note_metadata("wiki/concepts/missing.md")

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"


async def test_get_note_metadata_blocks_traversal(tmp_vault: Path, vault_env: None) -> None:
    """get_note_metadata rejects path traversal and returns INVALID_PATH."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_note_metadata("../../etc/passwd")

    assert result.get("error") is True
    assert result.get("code") == "INVALID_PATH"


# ---------------------------------------------------------------------------
# NAV-04 — get_index
# ---------------------------------------------------------------------------


async def test_get_index_parses_header(tmp_vault: Path, vault_env: None) -> None:
    """get_index parses the header line and returns correct totals."""
    # Overwrite the seeded index.md with a known header.
    index_content = (
        "# Vault Index\n"
        "Last updated: 2026-05-29 | Total pages: 42 | Total sources: 17\n"
        "\n"
        "## Entities\n"
    )
    (tmp_vault / "wiki" / "index.md").write_text(index_content, encoding="utf-8")

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_index()

    assert result.get("total_pages") == 42
    assert result.get("total_sources") == 17
    assert result.get("last_updated") == "2026-05-29"
    assert result.get("content", "").startswith("# Vault Index")


async def test_get_index_missing_returns_error(tmp_vault: Path, vault_env: None) -> None:
    """get_index returns NOT_FOUND error dict when wiki/index.md is absent."""
    (tmp_vault / "wiki" / "index.md").unlink()

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_index()

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"
