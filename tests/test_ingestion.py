"""Unit tests for ingestion MCP tools — INGEST-01..INGEST-05.

Tests use tmp_vault and vault_env fixtures from conftest.py and reload the
server module so each test sees the fixture's VAULT_PATH.

asyncio_mode = "auto" is configured in pyproject.toml — no @pytest.mark.asyncio
decorator is needed.

Tests:
  1.  test_create_note_writes_file_with_frontmatter        — INGEST-01
  2.  test_create_note_fails_if_exists                     — INGEST-01 (PRD §5.3)
  3.  test_create_note_blocks_traversal                    — INGEST-01 (T-06-01)
  4.  test_create_note_blocks_raw                          — INGEST-01 (T-06-02)
  5.  test_create_note_creates_parent_dirs                 — INGEST-01
  6.  test_append_to_note_appends_text                     — INGEST-02
  7.  test_append_to_note_missing_file                     — INGEST-02
  8.  test_prepend_to_note_inserts_after_frontmatter       — INGEST-03
  9.  test_insert_under_heading_inserts_in_section         — INGEST-04
  10. test_insert_under_heading_returns_available_on_miss  — INGEST-04 (PRD §5.3)
  11. test_update_frontmatter_changes_single_key           — INGEST-05
  12. test_update_frontmatter_returns_old_and_new          — INGEST-05
  13. test_update_frontmatter_does_not_touch_body          — INGEST-05
  14. test_all_ingestion_tools_reject_traversal            — all tools (T-06-01)
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import frontmatter as fm_lib

from tests.conftest import make_note


# ---------------------------------------------------------------------------
# Helper: reload server so VAULT_PATH matches the fixture's tmp_vault.
# ---------------------------------------------------------------------------


def fresh_server(tmp_vault: Path, vault_env: None):  # noqa: ARG001
    """Reload server module so it picks up the current fixture's VAULT_PATH."""
    import server as srv

    importlib.reload(srv)
    return srv


# ---------------------------------------------------------------------------
# INGEST-01 — create_note
# ---------------------------------------------------------------------------


async def test_create_note_writes_file_with_frontmatter(
    tmp_vault: Path, vault_env: None
) -> None:
    """create_note creates the file with correct frontmatter and body.

    Verifies: created=True, word_count correct, file exists on disk,
    frontmatter contains date/tags/summary/sources/related (PRD §3 template).
    """
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.create_note("wiki/concepts/new.md", "body text", tags=["ml"])

    assert result.get("created") is True
    assert result.get("word_count") == 2

    note_path = tmp_vault / "wiki" / "concepts" / "new.md"
    assert note_path.exists(), "Note file was not created on disk"

    post = fm_lib.load(str(note_path))
    assert post.metadata.get("tags") == ["ml"]
    assert "date" in post.metadata
    assert "summary" in post.metadata
    assert "sources" in post.metadata
    assert "related" in post.metadata


async def test_create_note_fails_if_exists(tmp_vault: Path, vault_env: None) -> None:
    """create_note returns ALREADY_EXISTS if the path already exists (PRD §5.3)."""
    srv = fresh_server(tmp_vault, vault_env)
    await srv.create_note("wiki/concepts/dup.md", "first content")

    # Second call with same path must fail
    result = await srv.create_note("wiki/concepts/dup.md", "second content")
    assert result.get("error") is True
    assert result.get("code") == "ALREADY_EXISTS"


async def test_create_note_blocks_traversal(tmp_vault: Path, vault_env: None) -> None:
    """create_note rejects path traversal and returns INVALID_PATH."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.create_note("../../etc/foo.md", "x")

    assert result.get("error") is True
    assert result.get("code") == "INVALID_PATH"


async def test_create_note_blocks_raw(tmp_vault: Path, vault_env: None) -> None:
    """create_note rejects writes into raw/ and returns INVALID_PATH (T-06-02)."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.create_note("raw/sources/foo.md", "x")

    assert result.get("error") is True
    assert result.get("code") == "INVALID_PATH"


async def test_create_note_creates_parent_dirs(
    tmp_vault: Path, vault_env: None
) -> None:
    """create_note creates all intermediate parent directories automatically."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.create_note("wiki/concepts/deep/nested/note.md", "x")

    assert result.get("created") is True
    assert (tmp_vault / "wiki" / "concepts" / "deep" / "nested" / "note.md").exists()


# ---------------------------------------------------------------------------
# INGEST-02 — append_to_note
# ---------------------------------------------------------------------------


async def test_append_to_note_appends_text(tmp_vault: Path, vault_env: None) -> None:
    """append_to_note appends text after existing body content.

    Both original and appended text must be present; appended text appears after.
    """
    make_note(
        tmp_vault,
        "wiki/concepts/append_test.md",
        {"title": "Append Test"},
        "first",
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.append_to_note("wiki/concepts/append_test.md", "second")

    assert result.get("appended") is True

    post = fm_lib.load(str(tmp_vault / "wiki" / "concepts" / "append_test.md"))
    body = post.content
    first_idx = body.find("first")
    second_idx = body.find("second")
    assert first_idx != -1, "original content 'first' is missing"
    assert second_idx != -1, "appended content 'second' is missing"
    assert first_idx < second_idx, "'second' should appear after 'first'"


async def test_append_to_note_missing_file(tmp_vault: Path, vault_env: None) -> None:
    """append_to_note on a non-existent file returns NOT_FOUND."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.append_to_note("wiki/concepts/ghost.md", "text")

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# INGEST-03 — prepend_to_note
# ---------------------------------------------------------------------------


async def test_prepend_to_note_inserts_after_frontmatter(
    tmp_vault: Path, vault_env: None
) -> None:
    """prepend_to_note inserts text before the existing body; frontmatter survives.

    Verifies: frontmatter fields preserved, body starts with prepended text.
    """
    make_note(
        tmp_vault,
        "wiki/concepts/prepend_test.md",
        {"title": "Prepend Test", "tags": ["keep"]},
        "original",
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.prepend_to_note("wiki/concepts/prepend_test.md", "newest")

    assert result.get("prepended") is True

    post = fm_lib.load(str(tmp_vault / "wiki" / "concepts" / "prepend_test.md"))

    # Frontmatter must be intact
    assert post.metadata.get("title") == "Prepend Test"
    assert post.metadata.get("tags") == ["keep"]

    # Body starts with 'newest', and 'original' still present but after
    body = post.content
    newest_idx = body.find("newest")
    original_idx = body.find("original")
    assert newest_idx != -1, "'newest' not found in body"
    assert original_idx != -1, "'original' not found in body"
    assert newest_idx < original_idx, "'newest' should appear before 'original'"


# ---------------------------------------------------------------------------
# INGEST-04 — insert_under_heading
# ---------------------------------------------------------------------------


async def test_insert_under_heading_inserts_in_section(
    tmp_vault: Path, vault_env: None
) -> None:
    """insert_under_heading inserts text inside the matched section only.

    "new" must appear between "old" and "## Section B", not after Section B.
    """
    body = "## Section A\nold\n\n## Section B\nother\n"
    make_note(
        tmp_vault,
        "wiki/concepts/headings.md",
        {"title": "Headings"},
        body,
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.insert_under_heading(
        "wiki/concepts/headings.md", "section a", "new"
    )

    assert result.get("heading_found") is True
    assert result.get("inserted") is True

    post = fm_lib.load(str(tmp_vault / "wiki" / "concepts" / "headings.md"))
    body_after = post.content

    # 'new' must appear before '## Section B'
    new_idx = body_after.find("new")
    section_b_idx = body_after.find("## Section B")
    assert new_idx != -1, "'new' text not found"
    assert section_b_idx != -1, "'## Section B' not found"
    assert new_idx < section_b_idx, "'new' should appear before '## Section B'"

    # 'other' still present (Section B content intact)
    assert "other" in body_after


async def test_insert_under_heading_returns_available_on_miss(
    tmp_vault: Path, vault_env: None
) -> None:
    """insert_under_heading returns HEADING_NOT_FOUND with available_headings on miss."""
    body = "## Alpha\ncontent a\n\n## Beta\ncontent b\n"
    make_note(
        tmp_vault,
        "wiki/concepts/headings2.md",
        {"title": "Headings2"},
        body,
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.insert_under_heading(
        "wiki/concepts/headings2.md", "Nonexistent Section", "x"
    )

    assert result.get("error") is True
    assert result.get("code") == "HEADING_NOT_FOUND"
    assert "available_headings" in result
    available = result["available_headings"]
    assert "Alpha" in available
    assert "Beta" in available


# ---------------------------------------------------------------------------
# INGEST-05 — update_frontmatter
# ---------------------------------------------------------------------------


async def test_update_frontmatter_changes_single_key(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_frontmatter updates a key without touching unrelated keys."""
    make_note(
        tmp_vault,
        "wiki/concepts/fm_test.md",
        {"title": "T", "tags": ["a"]},
        "body content",
    )

    srv = fresh_server(tmp_vault, vault_env)
    await srv.update_frontmatter("wiki/concepts/fm_test.md", "tags", ["a", "b"])

    post = fm_lib.load(str(tmp_vault / "wiki" / "concepts" / "fm_test.md"))
    assert post.metadata.get("tags") == ["a", "b"]
    assert post.metadata.get("title") == "T"  # Unrelated key untouched


async def test_update_frontmatter_returns_old_and_new(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_frontmatter returns old_value and new_value in the response dict."""
    make_note(
        tmp_vault,
        "wiki/concepts/fm_old_new.md",
        {"title": "T", "tags": ["a"]},
        "body",
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.update_frontmatter(
        "wiki/concepts/fm_old_new.md", "tags", ["a", "b"]
    )

    assert "old_value" in result
    assert "new_value" in result
    assert result["old_value"] == ["a"]
    assert result["new_value"] == ["a", "b"]


async def test_update_frontmatter_does_not_touch_body(
    tmp_vault: Path, vault_env: None
) -> None:
    """update_frontmatter leaves the note body unchanged."""
    make_note(
        tmp_vault,
        "wiki/concepts/fm_body.md",
        {"title": "Old"},
        "important content",
    )

    srv = fresh_server(tmp_vault, vault_env)
    await srv.update_frontmatter("wiki/concepts/fm_body.md", "title", "New")

    post = fm_lib.load(str(tmp_vault / "wiki" / "concepts" / "fm_body.md"))
    assert "important content" in post.content
    assert post.metadata.get("title") == "New"


# ---------------------------------------------------------------------------
# Cross-tool — path traversal rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_name,extra_args",
    [
        ("create_note", {"content": "x"}),
        ("append_to_note", {"text": "x"}),
        ("prepend_to_note", {"text": "x"}),
        ("insert_under_heading", {"heading": "h", "text": "x"}),
        ("update_frontmatter", {"key": "k", "value": "v"}),
    ],
)
async def test_all_ingestion_tools_reject_traversal(
    tmp_vault: Path,
    vault_env: None,
    tool_name: str,
    extra_args: dict,
) -> None:
    """All five ingestion tools return INVALID_PATH for path traversal attempts."""
    srv = fresh_server(tmp_vault, vault_env)
    tool_fn = getattr(srv, tool_name)
    result = await tool_fn(path="../evil", **extra_args)

    assert result.get("error") is True, f"{tool_name}: expected error=True"
    assert result.get("code") == "INVALID_PATH", (
        f"{tool_name}: expected INVALID_PATH, got {result.get('code')}"
    )
