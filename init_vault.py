"""
init_vault.py — One-shot vault scaffolding script.

Creates the full Obsidian vault directory tree at VAULT_PATH, seeds wiki/index.md
and wiki/log.md with correct initial content, and copies CLAUDE.md from the project
root into the vault root.

Usage:
    python init_vault.py   # reads .env automatically if present
    # or with an explicit override:
    VAULT_PATH=/path/to/new/vault python init_vault.py

IMPORTANT: VAULT_PATH must point to a directory that does NOT yet exist.
This script will fail immediately if the directory already exists (exist_ok=False),
preventing accidental re-initialization of an existing vault.
"""

from pathlib import Path
from datetime import date
import os
import shutil

# Load .env file if present so the script works without manually sourcing it
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed yet; fall back to environment variables


# ---------------------------------------------------------------------------
# Configuration — read from environment
# ---------------------------------------------------------------------------

VAULT_PATH = Path(os.environ["VAULT_PATH"])  # raises KeyError if not set

# ---------------------------------------------------------------------------
# Directory structure per PRD §3
# ---------------------------------------------------------------------------

SUBDIRS = [
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

# ---------------------------------------------------------------------------
# Seed file content per PRD §3 formats
# ---------------------------------------------------------------------------

today = date.today().isoformat()

INDEX_SEED = f"""# Vault Index
Last updated: {today} | Total pages: 0 | Total sources: 0

## Entities

## Concepts

## Sources

## Queries
"""

LOG_SEED = """# Vault Log
"""


def main() -> None:
    """Create vault directory tree and seed files. Fails fast if vault exists."""

    # Step 1: Create vault root — exist_ok=False ensures re-init fails fast (D-11)
    print(f"Creating vault at: {VAULT_PATH}")
    VAULT_PATH.mkdir(parents=True, exist_ok=False)

    # Step 2: Create all subdirectories
    for subdir in SUBDIRS:
        target = VAULT_PATH / subdir
        target.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {subdir}/")

    # Step 3: Seed wiki/index.md
    index_path = VAULT_PATH / "wiki" / "index.md"
    index_path.write_text(INDEX_SEED, encoding="utf-8")
    print(f"  Seeded: wiki/index.md")

    # Step 4: Seed wiki/log.md
    log_path = VAULT_PATH / "wiki" / "log.md"
    log_path.write_text(LOG_SEED, encoding="utf-8")
    print(f"  Seeded: wiki/log.md")

    # Step 5: Copy CLAUDE.md from project root into vault root
    src_claude = Path(__file__).parent / "CLAUDE.md"
    if src_claude.exists():
        shutil.copy(src_claude, VAULT_PATH / "CLAUDE.md")
        print(f"  Copied: CLAUDE.md → vault root")
    else:
        print(f"  WARNING: CLAUDE.md not found at {src_claude} — skipping copy")

    print(f"\nVault initialized successfully at: {VAULT_PATH}")
    print("Next steps:")
    print("  1. Populate .env with VAULT_SECRET, OAUTH_CLIENT_ID, OAUTH_REDIRECT_URI")
    print("  2. Run `pm2 start ecosystem.config.js` to start the server")


if __name__ == "__main__":
    main()
