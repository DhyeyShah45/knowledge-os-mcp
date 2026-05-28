"""Smoke test — verifies the test harness itself is wired correctly.

This test intentionally does NOT depend on any production code so it can run
before server.py, init_vault.py, or any dependency is in place. Its sole
purpose is to confirm that pytest discovers tests under tests/ and that
the asyncio_mode = "auto" config in pyproject.toml is valid.
"""

from pathlib import Path


def test_smoke():
    """Trivial assertion: harness is wired and pytest can run."""
    assert 1 + 1 == 2


def test_smoke_vault_fixture(tmp_vault):
    """Verifies the tmp_vault fixture produces a properly seeded vault."""
    assert tmp_vault.is_dir(), "tmp_vault must be a directory"
    assert (tmp_vault / "wiki" / "index.md").exists(), "wiki/index.md must exist"
    assert (tmp_vault / "wiki" / "log.md").exists(), "wiki/log.md must exist"
    index_content = (tmp_vault / "wiki" / "index.md").read_text()
    assert index_content.startswith("# Vault Index"), "index.md must start with '# Vault Index'"
    log_content = (tmp_vault / "wiki" / "log.md").read_text()
    assert log_content.startswith("# Vault Log"), "log.md must start with '# Vault Log'"
