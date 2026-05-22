#!/usr/bin/env bash
# Write .cursor/mcp.json with a literal dev Bearer token for Cursor on macOS.
# GUI Cursor does NOT inherit MCP_TOKEN from your terminal shell.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p .cursor

export MCP_DEV_TOKEN="$(uv run python -m mcp_financial_data.auth.oauth dev-token 2>/dev/null)"

uv run python - <<'PY'
import json
import os
from pathlib import Path

token = os.environ["MCP_DEV_TOKEN"]
cfg = {
    "mcpServers": {
        "mcp-financial-data": {
            "url": "http://127.0.0.1:8765/mcp",
            "headers": {
                "Authorization": f"Bearer {token}",
            },
        }
    }
}
path = Path(".cursor/mcp.json")
path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {path}")
print(f"Token prefix: {token[:20]}… (expires in 60 minutes)")
print("In Cursor: Settings → MCP → disable/re-enable mcp-financial-data or restart Cursor.")
PY
