#!/usr/bin/env python3
"""Guided video demo for mcp-financial-data.

Usage:
    make demo-start        # recommended — story hub in browser (single window)
    make demo-video        # legacy prep checklist
    make demo-video-script # teleprompter for recording
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import textwrap
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

import httpx

from mcp_financial_data.demo.hub import build_demo_hub, default_hub_dir
from mcp_financial_data.demo.preview import build_tenk_preview_html
from mcp_financial_data.settings import get_settings

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DOC = ROOT / "docs" / "demo" / "video-script.md"
HARNESS_MODULE = "mcp_financial_data.evals.harness"

_INIT_BODY: Final[dict[str, Any]] = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "demo-video", "version": "1.0"},
    },
}
_MCP_HEADERS: Final[dict[str, str]] = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
}


def _banner(title: str) -> None:
    line = "─" * 60
    print(f"\n{line}\n  {title}\n{line}")


def _run_smoke_eval() -> Path:
    subprocess.run(
        [sys.executable, "-m", HARNESS_MODULE, "--smoke", "--offline"],
        check=True,
        cwd=ROOT,
    )
    summaries = sorted((ROOT / "evals" / "runs").glob("*/summary.json"), reverse=True)
    if not summaries:
        msg = "No evals/runs/*/summary.json found after smoke eval."
        raise RuntimeError(msg)
    return summaries[0]


DEFAULT_HUB_PORT: Final[int] = 8766

TELEPROMPTER_SLIDES: Final[list[tuple[str, str]]] = [
    (
        "Slide 1 — The ask",
        "An analyst needs Apple 10-K Item 1A risks for a diligence memo — "
        "every claim must trace to the filing.",
    ),
    (
        "Slide 2 — The answer",
        "tenk.extract_section returns only cited facts. Click a pill — it opens "
        "SEC EDGAR. Uncited output never appears on this card.",
    ),
    (
        "Slide 3 — The proof",
        "INFERENCE stays in notes, never on the card. CI scores exec-accuracy "
        "and citation coverage — all ones, offline, zero dollars.",
    ),
    (
        "Slide 4 — The stack",
        "MCP 2025-11-25, OAuth resource server, Sonnet 4.5 Citations API, "
        "Opus 4.7 judge, smoke eval on every PR.",
    ),
]


def _print_teleprompter_slides() -> None:
    _banner("Teleprompter — advance slides with ← → in the browser")
    for title, say in TELEPROMPTER_SLIDES:
        print(f"\n  {title}")
        print(f"  SAY: {say}")
    print(f"\n  Full script: {SCRIPT_DOC}\n")


def _serve_directory(
    directory: Path,
    *,
    preferred_port: int,
    max_attempts: int = 20,
) -> tuple[ThreadingHTTPServer, int]:
    """Bind a static file server, advancing the port if the preferred one is taken."""

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

    last_err: OSError | None = None
    for offset in range(max_attempts):
        port = preferred_port + offset
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
            server.allow_reuse_address = True
            if offset > 0:
                print(
                    f"Port {preferred_port} in use; serving on {port} instead.",
                    file=sys.stderr,
                )
            return server, port
        except OSError as exc:
            if exc.errno not in {48, 98} and not isinstance(exc, socket.gaierror):
                raise
            last_err = exc
    end = preferred_port + max_attempts - 1
    msg = f"No free port in range {preferred_port}-{end}"
    raise OSError(last_err.errno if last_err else 48, msg) from last_err


def cmd_start(*, port: int = DEFAULT_HUB_PORT, open_browser: bool = True) -> int:
    _banner("Story demo hub")
    print("Running offline smoke eval…")
    summary_path = _run_smoke_eval()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    hub_path = build_demo_hub(repo_root=ROOT, eval_summary=summary)
    hub_dir = default_hub_dir().resolve()

    _print_teleprompter_slides()
    server, bound_port = _serve_directory(hub_dir, preferred_port=port)
    url = f"http://127.0.0.1:{bound_port}/{hub_path.name}"
    print(f"Serving {hub_dir}")
    print(f"Open: {url}\nPress Ctrl+C to stop.\n")

    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped demo hub.")
    return 0


def cmd_prep() -> int:
    _banner("Demo prep")
    print("Running offline smoke eval…")
    summary_path = _run_smoke_eval()
    preview_path = build_tenk_preview_html()
    settings = get_settings()

    print(
        textwrap.dedent(
            f"""
            Ready to record (legacy flow). Prefer: make demo-start

              Recommended — single browser window:
                make demo-start

              Legacy multi-window:
                make serve              # Terminal A (leave running)
                make demo-video-oauth   # Scene 4 (after server is up)
                make demo-video-audit   # Scene 3 metrics

            Server URL : http://{settings.mcp_host}:{settings.mcp_port}/mcp
            Preview    : {preview_path}
            Eval audit : {summary_path}
            Script     : {SCRIPT_DOC}

            Teleprompter: make demo-video-script
            """
        ).strip()
    )
    return 0


def cmd_card(*, open_browser: bool = True, serve: bool = False, port: int = 8766) -> int:
    preview_path = build_tenk_preview_html()
    preview_dir = preview_path.parent

    if serve:
        server, bound_port = _serve_directory(preview_dir, preferred_port=port)
        url = f"http://127.0.0.1:{bound_port}/{preview_path.name}"
        _banner(f"Serving preview at {url}")
        print("Press Ctrl+C to stop.\n")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped preview server.")
        return 0

    url = preview_path.as_uri()
    _banner("TenKSummaryCard preview")
    print(f"Open in browser:\n  {url}\n")
    if open_browser:
        webbrowser.open(url)
    return 0


def cmd_audit() -> int:
    summaries = sorted((ROOT / "evals" / "runs").glob("*/summary.json"), reverse=True)
    if not summaries:
        print("No summary.json found. Run `make demo-video` first.", file=sys.stderr)
        return 1

    data = json.loads(summaries[0].read_text(encoding="utf-8"))
    _banner("Eval audit trail (offline smoke)")
    metrics = [
        ("exec-accuracy", data.get("mean_exec_accuracy")),
        ("citation coverage", data.get("mean_citation_coverage")),
        ("judge score", data.get("mean_judge_score")),
        ("cases passed", f"{data.get('n_pass')}/{data.get('n_cases')}"),
        ("offline", data.get("offline")),
        ("cost", f"${data.get('total_cost_usd', 0):.2f}"),
    ]
    width = max(len(label) for label, _ in metrics)
    for label, value in metrics:
        print(f"  {label:<{width}}  {value}")
    print(f"\n  source  {summaries[0]}")
    print("\n  SAY: Every surfaced fact carries a citation. Uncited model output")
    print("       stays in notes. CI runs this smoke eval on every PR.")
    return 0


def cmd_oauth() -> int:
    settings = get_settings()
    base = f"http://{settings.mcp_host}:{settings.mcp_port}"
    token_proc = subprocess.run(
        [sys.executable, "-m", "mcp_financial_data.auth.oauth", "dev-token"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    token = token_proc.stdout.strip()

    _banner("OAuth gate (server must be running: make serve)")
    print(f"  token prefix  {token[:20]}…\n")

    with httpx.Client(base_url=base, timeout=10.0) as client:
        no_token = client.post("/mcp", headers=_MCP_HEADERS, json=_INIT_BODY)
        authed = client.post(
            "/mcp",
            headers={**_MCP_HEADERS, "authorization": f"Bearer {token}"},
            json=_INIT_BODY,
        )

    def _line(label: str, resp: httpx.Response) -> None:
        mark = "✓" if resp.status_code in {200, 401} else "✗"
        print(f"  {mark} {label:<22} HTTP {resp.status_code}")
        if resp.status_code == 401:
            www = resp.headers.get("www-authenticate", "")
            if www:
                print(f"      {www[:72]}…")

    _line("no Bearer token", no_token)
    _line("valid dev JWT", authed)

    ok = no_token.status_code == 401 and authed.status_code == 200
    print()
    if ok:
        print("  PASS — OAuth 2.1 resource server is enforcing JWTs.")
        return 0

    print("  FAIL — expected 401 without token and 200 with token.", file=sys.stderr)
    if no_token.status_code != 401:
        print("       Restart `make serve` to pick up the latest server code.", file=sys.stderr)
    return 1


def cmd_script() -> int:
    if not SCRIPT_DOC.is_file():
        print(f"Missing {SCRIPT_DOC}", file=sys.stderr)
        return 1
    print(SCRIPT_DOC.read_text(encoding="utf-8"))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Build story hub, serve, open browser")
    p_start.add_argument("--port", type=int, default=DEFAULT_HUB_PORT)
    p_start.add_argument("--no-open", action="store_true")

    sub.add_parser("prep", help="Run smoke eval + build preview + print checklist")
    p_card = sub.add_parser("card", help="Build and open TenKSummaryCard preview")
    p_card.add_argument("--no-open", action="store_true", help="Skip opening the browser")
    p_card.add_argument(
        "--serve",
        action="store_true",
        help="Serve preview over HTTP (better for screen recording)",
    )
    p_card.add_argument("--port", type=int, default=8766, help="Preview server port")

    sub.add_parser("audit", help="Pretty-print latest smoke eval summary")
    sub.add_parser("oauth", help="Labeled OAuth 401 → 200 check")
    sub.add_parser("script", help="Print the teleprompter markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "start":
        return cmd_start(port=args.port, open_browser=not args.no_open)
    if args.cmd == "prep":
        return cmd_prep()
    if args.cmd == "card":
        return cmd_card(open_browser=not args.no_open, serve=args.serve, port=args.port)
    if args.cmd == "audit":
        return cmd_audit()
    if args.cmd == "oauth":
        return cmd_oauth()
    if args.cmd == "script":
        return cmd_script()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
