#!/usr/bin/env bash
# Print copy-paste commands for the 60s Loom demo (see docs/demo/loom-tenk-summary-card.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-8765}"
BASE="http://${HOST}:${PORT}"

echo "==> Running offline smoke eval (audit-trail scene)..."
uv run python -m mcp_financial_data.evals.harness --smoke --offline >/dev/null

LATEST="$(ls -td evals/runs/*/summary.json 2>/dev/null | head -1 || true)"
if [[ -z "${LATEST}" ]]; then
  echo "ERROR: no evals/runs/*/summary.json found" >&2
  exit 1
fi

echo ""
echo "=== Loom demo prep — mcp-financial-data v0.1.0 ==="
echo ""
echo "1) Terminal A — start server:"
echo "   make serve"
echo ""
echo "2) Terminal B — OAuth dev token (requires MCP_OAUTH_DEV_SECRET in .env):"
echo "   export TOKEN=\$(make oauth-dev 2>/dev/null)"
echo "   echo \"\$TOKEN\" | cut -c1-20"
echo ""
echo "3) OAuth scene — 401 without token, 200 with token (MCP requires Content-Type + Accept):"
echo "   curl -s -o /dev/null -w 'no token: HTTP %{http_code}\\n' -X POST ${BASE}/mcp \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -H 'Accept: application/json, text/event-stream' \\"
echo "     -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"loom\",\"version\":\"1.0\"}}}'"
echo "   curl -s -o /dev/null -w 'with token: HTTP %{http_code}\\n' \\"
echo "     -X POST ${BASE}/mcp \\"
echo "     -H \"Authorization: Bearer \$TOKEN\" \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -H 'Accept: application/json, text/event-stream' \\"
echo "     -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"loom\",\"version\":\"1.0\"}}}'"
echo ""
echo "4) MCP client — call tenk.extract_section (see docs/demo for JSON args)."
echo "   Highlight TenKSummaryCard citation pills + footer (model, tokens, cost, latency)."
echo ""
echo "5) Audit trail — smoke eval summary (offline, deterministic):"
echo "   cat ${LATEST}"
echo ""
echo "6) Close — GitHub main CI badge + sticky eval-delta PR comment."
echo ""
echo "Post-recording: paste Loom URL into README.md Demo section."
echo "Full script: docs/demo/loom-tenk-summary-card.md"
