# knowledge-os-mcp

A personal, persistent knowledge base built on Obsidian — maintained by Claude, accessible from any device. A FastAPI MCP server runs on your laptop and exposes your Obsidian vault to Claude over a secure HTTPS connection via Cloudflare Tunnel. Claude handles all bookkeeping (filing, indexing, cross-referencing). You handle curation and intent.

**Phase 1 scope:** Full vault read/write over MCP. Keyword search, note navigation, ingestion, and maintenance tools. No media ingestion or semantic search yet (Phase 2/3).

---

## Architecture

```
Claude on phone / web          Claude Desktop (same machine)
        │  HTTPS + OAuth                │  HTTP localhost
        ▼                              ▼
Cloudflare Tunnel              localhost:8000
(knowledge-os-mcp.cyrque.com)          │
        │                              │
        └──────────────┬───────────────┘
                       ▼
          FastAPI MCP server (uvicorn)
               server.py :8000
                       │
                       ▼
          Obsidian Vault (local disk)
           /raw/   — immutable sources
           /wiki/  — Claude-maintained wiki
```

---

## Prerequisites

- **Python 3.11+** — `brew install python@3.11`
- **cloudflared** — `brew install cloudflared` *(only for remote/cloud access)*
- **Cloudflare account** with a domain whose DNS is managed by Cloudflare *(only for remote/cloud access)*

No Node.js, no PM2.

---

## Files You Must Create Yourself

These files contain secrets or machine-specific paths and are not committed to the repository.

| File | Purpose |
|---|---|
| `.env` | Environment variables (secrets, paths) |
| `~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist` | launchd service to auto-start uvicorn |

`start-server.sh` is committed — it contains no secrets, only sources `.env` at runtime.

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd knowledge-os-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create .env

```bash
cp .env.example .env
```

Edit `.env` and set all values:

```bash
VAULT_PATH=/path/to/your/obsidian-vault   # must not exist yet — init_vault.py creates it
VAULT_SECRET=$(openssl rand -hex 32)       # bearer token used by all clients
OAUTH_CLIENT_ID=claude-ai                  # sent by claude.ai during OAuth handshake
OAUTH_REDIRECT_URI=https://your-domain.com/callback  # must match your Cloudflare domain
```

> For localhost-only use, `OAUTH_CLIENT_ID` and `OAUTH_REDIRECT_URI` can be any placeholder values — they are only used by the OAuth flow for remote clients.

### 3. Initialize the vault

```bash
source .venv/bin/activate
python init_vault.py
```

This creates the vault directory tree at `VAULT_PATH` and seeds `wiki/index.md` and `wiki/log.md`. Run this **exactly once** — it fails if `VAULT_PATH` already exists.

### 4. Make the start script executable

```bash
chmod +x start-server.sh
```

### 5. Create the launchd service

Create `~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist` with the following content, replacing the username and paths:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cyrque.knowledge-os-mcp</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/YOUR_USERNAME/Projects/knowledge-os-mcp/start-server.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/Projects/knowledge-os-mcp</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/knowledge-os-mcp.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/knowledge-os-mcp.error.log</string>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist
```

Verify it started:

```bash
launchctl list | grep knowledge-os-mcp
tail -f ~/Library/Logs/knowledge-os-mcp.log
```

---

## Option A — Localhost Only (Claude Desktop, same machine)

No Cloudflare setup needed. The server runs on `http://localhost:8000` and the bearer auth middleware automatically skips authentication for localhost connections.

Add to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vault": {
      "command": "/path/to/knowledge-os-mcp/.venv/bin/python",
      "args": ["/path/to/knowledge-os-mcp/server.py"]
    }
  }
}
```

This uses the stdio transport (the `__main__` block in `server.py`). No bearer token configuration is needed.

Test the HTTP server directly:

```bash
curl http://localhost:8000/mcp
```

---

## Option B — Remote Access via Cloudflare Tunnel

Exposes `localhost:8000` as a persistent public HTTPS URL so Claude on your phone or any remote client can reach the vault.

### Step 1 — Point your domain DNS to Cloudflare

Your domain's nameservers must be set to Cloudflare's in your registrar's dashboard. Cloudflare must be the DNS authority for the domain (free plan is sufficient).

### Step 2 — Create the tunnel

There are two ways to do this in the Cloudflare dashboard — both work:

**Via Cloudflare Zero Trust:**
Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create a tunnel

**Via the Networking tab:**
Cloudflare dashboard → (select your domain) → Network → Tunnels → Create a tunnel

In either case: name the tunnel, select **Cloudflared** as the connector, and set the public hostname to your subdomain pointing to `http://localhost:8000`. The dashboard provides a token and an install command.

### Step 3 — Install the tunnel as a service

```bash
sudo cloudflared service install <TOKEN_FROM_DASHBOARD>
```

This registers a launchd daemon at `/Library/LaunchDaemons/com.cloudflare.cloudflared.plist` that starts automatically on boot. No further configuration needed.

Verify the tunnel is connected:

```bash
sudo launchctl list | grep cloudflared
```

### Step 4 — Update .env

Set `OAUTH_REDIRECT_URI` to your actual domain:

```bash
OAUTH_REDIRECT_URI=https://your-subdomain.yourdomain.com/callback
```

Restart the uvicorn service to pick up the change:

```bash
launchctl unload ~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist
launchctl load ~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist
```

### Step 5 — Connect from claude.ai

Go to **claude.ai → Settings → Integrations → Add MCP server** and enter:

- **MCP server URL:** `https://your-subdomain.yourdomain.com/mcp`

Claude.ai will trigger the OAuth 2.0 PKCE flow automatically. The server handles `/authorize` and `/token` endpoints — no additional configuration required.

Test the endpoint first:

```bash
curl -I https://your-subdomain.yourdomain.com/mcp
# Should return 401 (auth required), not a connection error
```

---

## Vault Structure

```
obsidian-vault/
├── raw/                    # IMMUTABLE — Claude never modifies this
│   ├── sources/
│   ├── webpages/           # Phase 2
│   ├── transcripts/        # Phase 2
│   └── documents/          # Phase 2
└── wiki/                   # Claude-owned — fully managed by LLM
    ├── index.md            # Master catalog — always read first
    ├── log.md              # Append-only operation log
    ├── entities/           # People, companies, products
    ├── concepts/           # Ideas, frameworks, topics
    ├── sources/            # Summary pages per ingested source
    └── queries/            # Valuable query answers filed as pages
```

---

## Project Structure

```
knowledge-os-mcp/
├── server.py               # FastAPI MCP server — all 15 Phase 1 tools
├── init_vault.py           # One-shot vault scaffolding — run before starting server
├── start-server.sh         # launchd entry point — sources .env, launches uvicorn
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template — copy to .env
├── .gitignore
├── CLAUDE.md               # Vault operational rules injected as MCP instructions
└── PRD.md                  # Full product requirements document
```

---

## Troubleshooting

### Server not starting

```bash
tail -50 ~/Library/Logs/knowledge-os-mcp.error.log
```

Common causes:
- `.env` missing or incomplete — all four vars are required at startup
- `VAULT_PATH` does not exist — run `python init_vault.py`
- `.venv` not created — run `python3 -m venv .venv && pip install -r requirements.txt`
- `start-server.sh` not executable — run `chmod +x start-server.sh`

### Reload after .env changes

```bash
launchctl unload ~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist
launchctl load ~/Library/LaunchAgents/com.cyrque.knowledge-os-mcp.plist
```

### Tunnel not connecting

```bash
sudo launchctl list | grep cloudflared
# If not listed, re-run: sudo cloudflared service install <token>
```

### Test auth manually

```bash
# Should return 401
curl -I https://your-subdomain.yourdomain.com/mcp

# Should return 200 or MCP response
source .env
curl -H "Authorization: Bearer $VAULT_SECRET" https://your-subdomain.yourdomain.com/mcp
```

### Dev mode (hot reload, no launchd)

```bash
source .venv/bin/activate
source .env
uvicorn server:app --reload --port 8000
```

### Run tests

```bash
source .venv/bin/activate
pytest tests/ -x -q
```
