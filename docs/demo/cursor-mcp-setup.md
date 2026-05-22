# Cursor MCP setup (appendix)

Use this only if you want a **live** Cursor tool call instead of Slide 2 in the
browser demo hub. The primary recording flow is `make demo-start` — no Cursor
setup required.

## Prerequisites

- `MCP_OAUTH_DEV_SECRET` set in [`.env`](../.env.example)
- Server running: `make serve`

## Steps

1. Mint a project-level MCP config (macOS GUI Cursor does not inherit terminal env vars):

   ```bash
   make oauth-dev-cursor
   ```

   This writes `.cursor/mcp.json` with a literal Bearer token (gitignored, expires in 60 minutes).

2. Reload MCP in Cursor: **Settings → MCP** → disable/re-enable **mcp-financial-data**, or restart Cursor.

3. Remove or disable the duplicate entry in `~/.cursor/mcp.json` if it still uses
   `${env:MCP_TOKEN}` — that resolves empty on macOS.

4. In Cursor chat, ask:

   > Call tenk.extract_section for Apple 10-K Item 1A risk factors.

5. Hover citation pills on the inline **TenKSummaryCard**.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `missing bearer token` | Re-run `make oauth-dev-cursor` and reload MCP |
| Token expired (60 min) | Re-run `make oauth-dev-cursor` |
| Connection refused | Start `make serve` in a separate terminal |
| Wrong server version | Restart `make serve` after pulling latest `main` |

## OAuth verification (optional)

With `make serve` running:

```bash
make demo-video-oauth
```

Expect **401** without token, **200** with dev JWT.
