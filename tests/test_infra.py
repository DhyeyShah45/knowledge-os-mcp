"""Infrastructure tests for the knowledge-os-mcp server.

Tests verify:
- server.py imports without raising under the vault_env environment
- FastMCP instance carries CLAUDE.md content as instructions (INFRA-05)
- safe_vault_path blocks directory traversal and raw/ writes
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_server(tmp_vault, vault_env):
    """Import (or reimport) server.py after env vars are set."""
    if "server" in sys.modules:
        del sys.modules["server"]
    import server  # noqa: PLC0415
    return server


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_app_importable(tmp_vault, vault_env):
    """server.py must import cleanly under the test environment."""
    srv = _load_server(tmp_vault, vault_env)
    # If import raises, the test will fail with that exception.
    # We just verify `app` and `mcp` attributes exist.
    assert hasattr(srv, "app"), "server.app not defined"
    assert hasattr(srv, "mcp"), "server.mcp not defined"


def test_instructions_injected(tmp_vault, vault_env):
    """FastMCP instance must carry CLAUDE.md content as instructions (INFRA-05)."""
    srv = _load_server(tmp_vault, vault_env)
    expected = (tmp_vault / "CLAUDE.md").read_text(encoding="utf-8")
    assert srv.mcp.instructions == expected, (
        "server.mcp.instructions does not match CLAUDE.md content in vault"
    )


def test_safe_vault_path_blocks_traversal(tmp_vault, vault_env):
    """safe_vault_path must reject ../traversal paths and return INVALID_PATH dict."""
    srv = _load_server(tmp_vault, vault_env)

    result = srv.safe_vault_path("../../etc/passwd")
    assert isinstance(result, dict), "Expected error dict for traversal path"
    assert result["error"] is True
    assert result["code"] == "INVALID_PATH"


def test_safe_vault_path_allows_valid_path(tmp_vault, vault_env):
    """safe_vault_path must return a Path for valid relative paths inside the vault."""
    srv = _load_server(tmp_vault, vault_env)

    result = srv.safe_vault_path("wiki/concepts/foo.md")
    assert isinstance(result, Path), (
        f"Expected Path for valid relative path; got {type(result)}: {result}"
    )
    assert str(result).startswith(str(tmp_vault))


def test_safe_vault_path_blocks_raw(tmp_vault, vault_env):
    """safe_vault_path must reject paths under raw/ (raw/ is immutable per CLAUDE.md)."""
    srv = _load_server(tmp_vault, vault_env)

    result = srv.safe_vault_path("raw/webpages/something.md")
    assert isinstance(result, dict), "Expected error dict for raw/ path"
    assert result["error"] is True
    assert result["code"] == "INVALID_PATH"
