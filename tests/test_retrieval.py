"""Unit tests for retrieval MCP tools — RET-01..RET-04.

Tests use tmp_vault and vault_env fixtures from conftest.py and reload the
server module so each test sees the fixture's VAULT_PATH.

asyncio_mode = "auto" is configured in pyproject.toml — no @pytest.mark.asyncio
decorator is needed.

Tests:
  1.  test_search_empty_query_returns_empty          — RET-01
  2.  test_search_finds_keyword                      — RET-01 (D-12 scoring)
  3.  test_search_case_insensitive                   — RET-01 (D-13)
  4.  test_search_respects_top_k                     — RET-01
  5.  test_search_snippet_is_short                   — RET-01 (D-15)
  6.  test_search_scoped_to_wiki                     — RET-01 (D-14)
  7.  test_get_note_summary_truncates_at_200         — RET-02
  8.  test_get_note_summary_extracts_headings        — RET-02
  9.  test_get_note_summary_missing                  — RET-02
  10. test_read_note_returns_content_and_frontmatter — RET-03
  11. test_read_note_invalid_path                    — RET-03
  12. test_read_note_section_extracts_section        — RET-04
  13. test_read_note_section_heading_not_found_returns_available — RET-04
  14. test_read_note_section_blocks_traversal        — RET-04
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

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
# RET-01 — search_full_text
# ---------------------------------------------------------------------------


async def test_search_empty_query_returns_empty(tmp_vault: Path, vault_env: None) -> None:
    """search_full_text('') returns {'results': []} without scanning any files."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.search_full_text("")

    assert result == {"results": []}


async def test_search_finds_keyword(tmp_vault: Path, vault_env: None) -> None:
    """search_full_text finds notes by keyword; scores are normalized per D-12.

    Note A has 'transformer' 5 times → score 1.0 (top result).
    Note B has 'transformer' 1 time  → score 0.2 (second result).
    """
    # Note A: 5 occurrences
    body_a = " ".join(["transformer"] * 5) + "\n\nSome extra content."
    make_note(tmp_vault, "wiki/concepts/attn.md", {"title": "Attention"}, body_a)

    # Note B: 1 occurrence
    body_b = "The transformer architecture is useful.\n\nMore content here."
    make_note(tmp_vault, "wiki/concepts/basic.md", {"title": "Basic"}, body_b)

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.search_full_text("transformer")

    assert "results" in result
    results = result["results"]
    assert len(results) == 2

    # Top result must be Note A (5 occurrences) with score == 1.0
    assert results[0]["title"] == "Attention"
    assert results[0]["score"] == 1.0

    # Second result must have score == 0.2 (1/5)
    assert results[1]["score"] == pytest.approx(0.2)


async def test_search_case_insensitive(tmp_vault: Path, vault_env: None) -> None:
    """search_full_text is case-insensitive per D-13."""
    make_note(
        tmp_vault,
        "wiki/concepts/transformers.md",
        {"title": "Transformers"},
        "The Transformer model changed NLP forever.",
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.search_full_text("TRANSFORMER")

    assert "results" in result
    assert len(result["results"]) >= 1
    assert result["results"][0]["score"] == 1.0


async def test_search_respects_top_k(tmp_vault: Path, vault_env: None) -> None:
    """search_full_text returns at most top_k results."""
    for i in range(7):
        make_note(
            tmp_vault,
            f"wiki/concepts/ml_{i}.md",
            {"title": f"ML note {i}"},
            f"Machine learning concepts {i}. ml ml ml",
        )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.search_full_text("ml", top_k=3)

    assert "results" in result
    assert len(result["results"]) == 3


async def test_search_snippet_is_short(tmp_vault: Path, vault_env: None) -> None:
    """search_full_text returns a snippet ≤ ~200 chars containing the query."""
    prefix = "A" * 300  # 300 chars before the keyword line
    body = "\n".join([
        "Line 1",
        "Line 2",
        "Line 3",
        "Line 4",
        "The attention mechanism is the key innovation here.",
        "Line 6 which is very long " + ("x" * 200),
        "Line 7",
    ])

    make_note(tmp_vault, "wiki/concepts/long.md", {"title": "Long"}, body)

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.search_full_text("attention")

    assert "results" in result
    assert len(result["results"]) >= 1

    snippet = result["results"][0]["snippet"]
    assert len(snippet) <= 200
    assert "attention" in snippet.lower()


async def test_search_scoped_to_wiki(tmp_vault: Path, vault_env: None) -> None:
    """search_full_text does NOT return results from raw/ per D-14."""
    # Place a matching file under raw/
    raw_file = tmp_vault / "raw" / "sources" / "external.md"
    raw_file.write_text("transformer transformer transformer", encoding="utf-8")

    # Also place one in wiki/ so we know search runs at all
    make_note(
        tmp_vault,
        "wiki/concepts/ok.md",
        {"title": "OK"},
        "transformer mentioned once.",
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.search_full_text("transformer")

    assert "results" in result
    paths = [r["path"] for r in result["results"]]

    # No path should begin with "raw/"
    for p in paths:
        assert not p.startswith("raw/"), f"raw/ path leaked into results: {p}"

    # The wiki note must appear
    assert any("ok.md" in p for p in paths)


# ---------------------------------------------------------------------------
# RET-02 — get_note_summary
# ---------------------------------------------------------------------------


async def test_get_note_summary_truncates_at_200(tmp_vault: Path, vault_env: None) -> None:
    """get_note_summary returns a summary truncated to 200 chars per PRD §5.2."""
    body = "X" * 500  # 500 chars — well over the 200-char limit
    make_note(tmp_vault, "wiki/concepts/long.md", {"title": "Long"}, body)

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_note_summary("wiki/concepts/long.md")

    assert "summary" in result
    assert len(result["summary"]) <= 200


async def test_get_note_summary_extracts_headings(tmp_vault: Path, vault_env: None) -> None:
    """get_note_summary returns all markdown headings from the note body."""
    body = "## Overview\n\n## Attention\n\n### Mechanism\n\nSome body text."
    make_note(tmp_vault, "wiki/concepts/heads.md", {"title": "Heads"}, body)

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_note_summary("wiki/concepts/heads.md")

    assert "headings" in result
    headings = result["headings"]
    assert "Overview" in headings
    assert "Attention" in headings
    assert "Mechanism" in headings
    assert headings == ["Overview", "Attention", "Mechanism"]


async def test_get_note_summary_missing(tmp_vault: Path, vault_env: None) -> None:
    """get_note_summary on a missing file returns NOT_FOUND error dict."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_note_summary("wiki/concepts/nonexistent.md")

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"


async def test_get_note_summary_blocks_traversal(tmp_vault: Path, vault_env: None) -> None:
    """get_note_summary rejects path traversal and returns INVALID_PATH."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.get_note_summary("../../etc/passwd")

    assert result.get("error") is True
    assert result.get("code") == "INVALID_PATH"


# ---------------------------------------------------------------------------
# RET-03 — read_note
# ---------------------------------------------------------------------------


async def test_read_note_returns_content_and_frontmatter(
    tmp_vault: Path, vault_env: None
) -> None:
    """read_note returns path, title, frontmatter dict, and content string."""
    make_note(
        tmp_vault,
        "wiki/entities/test.md",
        {"title": "Test Entity", "tags": ["ml", "ai"]},
        "This is the body of the note.",
    )

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.read_note("wiki/entities/test.md")

    assert "path" in result
    assert "title" in result
    assert "frontmatter" in result
    assert "content" in result

    assert result["title"] == "Test Entity"
    assert isinstance(result["frontmatter"], dict)
    assert result["frontmatter"].get("tags") == ["ml", "ai"]
    assert isinstance(result["content"], str)
    assert "body of the note" in result["content"]


async def test_read_note_invalid_path(tmp_vault: Path, vault_env: None) -> None:
    """read_note rejects path traversal and returns INVALID_PATH."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.read_note("../etc/passwd")

    assert result.get("error") is True
    assert result.get("code") == "INVALID_PATH"


async def test_read_note_missing_file(tmp_vault: Path, vault_env: None) -> None:
    """read_note on a missing file returns NOT_FOUND error dict."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.read_note("wiki/concepts/missing.md")

    assert result.get("error") is True
    assert result.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# RET-04 — read_note_section
# ---------------------------------------------------------------------------


async def test_read_note_section_extracts_section(tmp_vault: Path, vault_env: None) -> None:
    """read_note_section returns only the content under the matched heading.

    Case-insensitive partial match: "mech" matches "## Mech".
    """
    body = "# A\n\n## Mech\nbody1\n\n## Other\nbody2\n"
    make_note(tmp_vault, "wiki/concepts/sec.md", {"title": "Sec"}, body)

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.read_note_section("wiki/concepts/sec.md", "mech")

    assert "content" in result
    assert "heading" in result
    assert result["heading"] == "Mech"
    assert "body1" in result["content"]
    assert "body2" not in result["content"]


async def test_read_note_section_heading_not_found_returns_available(
    tmp_vault: Path, vault_env: None
) -> None:
    """read_note_section returns HEADING_NOT_FOUND with available_headings list."""
    body = "# A\n\n## Mech\nbody1\n\n## Other\nbody2\n"
    make_note(tmp_vault, "wiki/concepts/sec2.md", {"title": "Sec2"}, body)

    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.read_note_section("wiki/concepts/sec2.md", "Nonexistent")

    assert result.get("error") is True
    assert result.get("code") == "HEADING_NOT_FOUND"
    assert "available_headings" in result
    available = result["available_headings"]
    assert "Mech" in available
    assert "Other" in available


async def test_read_note_section_blocks_traversal(tmp_vault: Path, vault_env: None) -> None:
    """read_note_section rejects path traversal and returns INVALID_PATH."""
    srv = fresh_server(tmp_vault, vault_env)
    result = await srv.read_note_section("../foo", "heading")

    assert result.get("error") is True
    assert result.get("code") == "INVALID_PATH"
