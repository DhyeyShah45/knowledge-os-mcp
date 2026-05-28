"""Shared pytest fixtures and helpers for the knowledge-os-mcp test suite.

All fixtures are function-scoped (default) unless noted otherwise.
The `tmp_vault` fixture produces a fully-seeded temporary vault directory
that mirrors the output of init_vault.py — tests never depend on a real vault
on disk.

Security note (T-02-01): `vault_env` uses pytest monkeypatch so every env
mutation is automatically reverted after each test — no leakage between tests.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest


# ---------------------------------------------------------------------------
# Vault scaffolding helpers
# ---------------------------------------------------------------------------

_VAULT_DIRS = [
    "raw/webpages",
    "raw/transcripts",
    "raw/videos",
    "raw/documents",
    "raw/assets",
    "raw/sources",
    "wiki/entities",
    "wiki/concepts",
    "wiki/sources",
    "wiki/queries",
]

_INDEX_SEED = (
    "# Vault Index\n"
    "Last updated: 2026-05-29 | Total pages: 0 | Total sources: 0\n"
    "\n"
    "## Entities\n"
    "\n"
    "## Concepts\n"
    "\n"
    "## Sources\n"
    "\n"
    "## Queries\n"
)

_LOG_SEED = "# Vault Log\n"

_CLAUDE_MD_SEED = "# CLAUDE.md\n\nTest instructions placeholder.\n"


def _scaffold_vault(vault_root: Path) -> None:
    """Create the full vault directory tree and seed required files."""
    for rel_dir in _VAULT_DIRS:
        (vault_root / rel_dir).mkdir(parents=True, exist_ok=True)

    (vault_root / "wiki" / "index.md").write_text(_INDEX_SEED, encoding="utf-8")
    (vault_root / "wiki" / "log.md").write_text(_LOG_SEED, encoding="utf-8")
    (vault_root / "CLAUDE.md").write_text(_CLAUDE_MD_SEED, encoding="utf-8")


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Generator[Path, None, None]:
    """Return a path to a fresh, fully-seeded temporary vault.

    The vault directory tree matches the output produced by init_vault.py:
      raw/{webpages,transcripts,videos,documents,assets,sources}/
      wiki/{entities,concepts,sources,queries}/
      wiki/index.md    — seeded with header and section stubs
      wiki/log.md      — seeded with header only
      CLAUDE.md        — placeholder operational rules file

    Cleanup is handled automatically by pytest's `tmp_path` fixture.

    Usage::

        def test_something(tmp_vault):
            assert (tmp_vault / "wiki" / "index.md").exists()
    """
    vault_root = tmp_path / "vault"
    vault_root.mkdir(parents=True, exist_ok=True)
    _scaffold_vault(vault_root)
    yield vault_root


@pytest.fixture()
def vault_env(tmp_vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure environment variables required by server.py.

    Sets the following env vars for the duration of the calling test:
      VAULT_PATH        — absolute path to the tmp_vault directory
      VAULT_SECRET      — static test token ("test-secret-token")
      OAUTH_CLIENT_ID   — static test client id ("test-client")
      OAUTH_REDIRECT_URI — localhost callback URL

    All mutations are reverted automatically by monkeypatch after each test
    (addresses threat T-02-01 — no env leakage between tests).

    Usage::

        def test_server_startup(tmp_vault, vault_env):
            import os
            assert os.environ["VAULT_PATH"] == str(tmp_vault)
    """
    monkeypatch.setenv("VAULT_PATH", str(tmp_vault))
    monkeypatch.setenv("VAULT_SECRET", "test-secret-token")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost/cb")
    return None


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


def make_note(vault: Path, rel: str, frontmatter: dict, body: str) -> Path:
    """Write a markdown note at ``vault / rel`` with YAML frontmatter.

    The function serialises *frontmatter* manually (strings and lists of
    strings) to avoid a hard dependency on PyYAML or python-frontmatter at
    import time — later plans install these packages, at which point this
    helper will still work identically.

    Args:
        vault:       Absolute path to the vault root (typically from tmp_vault).
        rel:         Relative path inside the vault, e.g. ``"wiki/concepts/AI.md"``.
        frontmatter: Mapping of YAML front-matter key → value.
                     Supported value types: str, int, float, list[str].
        body:        Markdown body text (written after the closing ``---``).

    Returns:
        The ``Path`` of the written file.

    Example::

        note = make_note(
            tmp_vault,
            "wiki/concepts/python.md",
            {"title": "Python", "tags": ["language", "scripting"], "created": "2026-05-29"},
            "Python is a high-level programming language.",
        )
        assert note.exists()
    """
    # Keep a local reference to the frontmatter dict under an unambiguous name
    # so that the ``import frontmatter`` statement below (which would shadow the
    # parameter name in the local scope) does not cause confusion.
    fm_dict: dict = frontmatter

    # Attempt to use python-frontmatter for serialisation if installed.
    try:
        import frontmatter as _fm_lib  # type: ignore[import]

        post = _fm_lib.Post(body, **fm_dict)
        content = _fm_lib.dumps(post)
    except ImportError:
        # Fallback: hand-serialise the minimal subset needed by tests.
        lines = ["---"]
        for key, value in fm_dict.items():
            if isinstance(value, list):
                serialised = "[" + ", ".join(str(v) for v in value) + "]"
            else:
                serialised = str(value)
            lines.append(f"{key}: {serialised}")
        lines.append("---")
        lines.append("")
        lines.append(body)
        content = "\n".join(lines)

    note_path = vault / rel
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    return note_path
