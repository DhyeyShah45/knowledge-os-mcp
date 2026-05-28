/**
 * ecosystem.config.js — PM2 process configuration for knowledge-os-mcp.
 *
 * Manages two processes:
 *   1. vault-mcp          — FastAPI MCP server (uvicorn from virtualenv)
 *   2. cloudflare-tunnel  — Cloudflare Tunnel (cloudflared binary)
 *
 * Usage:
 *   pm2 start ecosystem.config.js
 *   pm2 save
 *   pm2 startup   # auto-start on boot
 *
 * IMPORTANT: Run `python init_vault.py` and populate .env before starting.
 *
 * The vault-mcp process uses .venv/bin/uvicorn (full virtualenv path) so PM2
 * does not need the venv activated. The .env file is loaded by server.py via
 * python-dotenv at startup — PM2 does not need to manage env vars directly.
 */

module.exports = {
  apps: [
    {
      // FastAPI MCP server — served at http://localhost:8000
      name: "vault-mcp",
      script: ".venv/bin/uvicorn",
      args: "server:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      cwd: process.cwd(),
      autorestart: true,
      max_restarts: 10,
      restart_delay: 4000,
      watch: false,
      env: {
        // server.py loads VAULT_SECRET, VAULT_PATH, OAUTH_CLIENT_ID,
        // OAUTH_REDIRECT_URI from .env via python-dotenv
      }
    },
    {
      // Cloudflare Tunnel — exposes localhost:8000 as vault.<your-domain.com>
      name: "cloudflare-tunnel",
      script: "cloudflared",
      args: "tunnel run vault",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 4000,
      watch: false
    }
  ]
};
