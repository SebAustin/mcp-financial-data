"""Build a slide-based story demo hub for video recordings."""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any, Final

from mcp_financial_data.apps.ui import (
    TenKSummaryCardProps,
    _bundle_path,
    render_tenk_summary_card,
)
from mcp_financial_data.demo.preview import PREVIEW_BUNDLE_NAME, build_tenk_preview_html
from mcp_financial_data.evals.fixtures import get_offline_fixture
from mcp_financial_data.extractors.tenk import ExtractionResult

DEFAULT_HUB_DIR: Final[Path] = Path("recordings/demo")
HUB_INDEX_NAME: Final[str] = "index.html"

ANALYST_QUESTION: Final[str] = (
    "What supply chain and macroeconomic risks does Apple disclose in "
    "10-K Item 1A? Cite the filing — I need this for a diligence memo."
)

TOOL_CALL_LABEL: Final[str] = "tenk.extract_section · AAPL · item_1a_risk_factors"

INFERENCE_EXAMPLE: Final[str] = (
    "[INFERENCE] Apple may face increased regulatory scrutiny in the EU " "over App Store policies."
)

DEFAULT_EVAL_METRICS: Final[dict[str, Any]] = {
    "mean_exec_accuracy": 1.0,
    "mean_citation_coverage": 1.0,
    "mean_judge_score": 1.0,
    "n_pass": 1,
    "n_cases": 1,
    "offline": True,
    "total_cost_usd": 0.0,
    "run_id": "offline-smoke",
}

CI_BADGE_URL: Final[str] = (
    "https://github.com/SebAustin/mcp-financial-data/actions/workflows/ci.yml/badge.svg"
)
REPO_URL: Final[str] = "https://github.com/SebAustin/mcp-financial-data"


def default_hub_dir() -> Path:
    """Return the gitignored directory used for the story demo hub."""
    return DEFAULT_HUB_DIR


def _latest_eval_summary(repo_root: Path) -> dict[str, Any]:
    summaries = sorted((repo_root / "evals" / "runs").glob("*/summary.json"), reverse=True)
    if not summaries:
        return dict(DEFAULT_EVAL_METRICS)
    try:
        loaded: dict[str, Any] = json.loads(summaries[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_EVAL_METRICS)
    return loaded


def _tenk_envelope_json(*, cik: str = "0000320193", company_name: str = "Apple Inc.") -> str:
    extraction = ExtractionResult.model_validate(get_offline_fixture("tenk-aapl-risk-factors"))
    envelope = render_tenk_summary_card(
        TenKSummaryCardProps(
            extraction=extraction,
            cik=cik,
            company_name=company_name,
        )
    )
    return json.dumps(envelope, separators=(",", ":"))


def _cited_facts_html() -> str:
    extraction = ExtractionResult.model_validate(get_offline_fixture("tenk-aapl-risk-factors"))
    items: list[str] = []
    for claim in extraction.facts:
        text = html.escape(claim.text)
        items.append(f'<li>{text} <span class="pill">SEC citation</span></li>')
    return "\n".join(items)


def build_demo_hub(
    *,
    out_dir: Path | None = None,
    repo_root: Path | None = None,
    eval_summary: dict[str, Any] | None = None,
) -> Path:
    """Write the 4-slide demo hub and card page; return path to index.html."""
    root = (repo_root or Path.cwd()).resolve()
    target_dir = (out_dir or default_hub_dir()).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    build_tenk_preview_html(out_dir=target_dir)

    bundle_src = _bundle_path()
    if not bundle_src.is_file():
        msg = f"MCP Apps bundle missing at {bundle_src}; run `make ui-build`."
        raise FileNotFoundError(msg)
    shutil.copy2(bundle_src, target_dir / PREVIEW_BUNDLE_NAME)

    metrics = eval_summary if eval_summary is not None else _latest_eval_summary(root)
    props_json = _tenk_envelope_json()
    cited_facts = _cited_facts_html()

    exec_acc = metrics.get("mean_exec_accuracy", 1.0)
    cite_cov = metrics.get("mean_citation_coverage", 1.0)
    judge = metrics.get("mean_judge_score", 1.0)
    offline = metrics.get("offline", True)
    run_id = html.escape(str(metrics.get("run_id", "offline-smoke")))
    inference = html.escape(INFERENCE_EXAMPLE)
    question = html.escape(ANALYST_QUESTION)
    tool_label = html.escape(TOOL_CALL_LABEL)

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>mcp-financial-data — story demo</title>
  <style>
    :root {{
      --bg: #0a0e16;
      --bg-2: #0f1622;
      --surface: #141d2e;
      --surface-2: #1a2436;
      --text: #eef2f8;
      --muted: #8c9bb5;
      --faint: #5d6b86;
      --accent: #4f8cff;
      --accent-2: #7c5cff;
      --good: #2ee08a;
      --bad: #ff5d6c;
      --amber: #ffb347;
      --border: #243049;
      --glow: 0 0 0 1px rgba(79,140,255,0.25), 0 18px 50px -12px rgba(79,140,255,0.35);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      font-family: "Inter", system-ui, -apple-system, sans-serif;
      background:
        radial-gradient(900px 520px at 88% -8%, rgba(124,92,255,0.16), transparent 70%),
        radial-gradient(820px 480px at 6% 108%, rgba(79,140,255,0.16), transparent 70%),
        var(--bg);
      color: var(--text);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }}
    .progress {{
      position: fixed; top: 0; left: 0; right: 0; height: 3px; z-index: 30;
      background: rgba(255,255,255,0.04);
    }}
    .progress > span {{
      display: block; height: 100%; width: 25%;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
      transition: width 0.35s cubic-bezier(.4,0,.2,1);
    }}
    .nav {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.85rem 1.5rem;
      background: rgba(15,22,34,0.82);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--border);
      position: sticky; top: 0; z-index: 20;
    }}
    .brand {{ display: flex; align-items: center; gap: 0.6rem; }}
    .brand .mark {{
      width: 26px; height: 26px; border-radius: 7px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      display: grid; place-items: center;
      font-size: 0.8rem; font-weight: 800; color: white;
      box-shadow: 0 6px 18px -6px rgba(79,140,255,0.7);
    }}
    .brand .nav-title {{ font-size: 0.84rem; color: var(--text); font-weight: 600; letter-spacing: -0.01em; }}
    .brand .nav-sub {{ font-size: 0.72rem; color: var(--faint); }}
    .nav-right {{ display: flex; align-items: center; gap: 1rem; }}
    .counter {{ font-size: 0.78rem; color: var(--muted); font-variant-numeric: tabular-nums; }}
    .counter b {{ color: var(--text); }}
    .nav-dots {{ display: flex; gap: 0.4rem; }}
    .dot {{
      width: 1.85rem; height: 1.85rem; border-radius: 9px;
      border: 1px solid var(--border); background: var(--surface);
      color: var(--muted); cursor: pointer; font-size: 0.74rem; font-weight: 600;
      transition: all 0.18s ease;
    }}
    .dot:hover {{ color: var(--text); border-color: var(--accent); }}
    .dot.active {{
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: white; border-color: transparent;
    }}
    .stage {{ max-width: 60rem; margin: 0 auto; padding: 2.6rem 1.5rem 5.5rem; }}
    .slide {{ display: none; }}
    .slide.active {{ display: block; animation: rise 0.42s cubic-bezier(.2,.7,.2,1); }}
    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(14px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .kicker {{
      display: inline-flex; align-items: center; gap: 0.5rem;
      font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em;
      text-transform: uppercase; color: var(--accent);
      background: rgba(79,140,255,0.1); border: 1px solid rgba(79,140,255,0.22);
      padding: 0.32rem 0.7rem; border-radius: 999px; margin-bottom: 1rem;
    }}
    .kicker .num {{ color: var(--faint); }}
    h1 {{
      font-size: 2.05rem; line-height: 1.12; margin: 0 0 0.6rem;
      letter-spacing: -0.025em; font-weight: 800;
    }}
    h1 .hl {{
      background: linear-gradient(120deg, var(--accent), var(--accent-2));
      -webkit-background-clip: text; background-clip: text; color: transparent;
    }}
    .subtitle {{ color: var(--muted); margin: 0 0 1.7rem; font-size: 1.02rem; line-height: 1.5; max-width: 42rem; }}
    code {{
      font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 0.92em;
      background: rgba(79,140,255,0.1); padding: 0.08rem 0.34rem; border-radius: 5px;
      color: #cfe0ff;
    }}
    .chat {{
      background: linear-gradient(180deg, var(--surface), var(--bg-2));
      border: 1px solid var(--border); border-radius: 16px;
      padding: 1.4rem; max-width: 40rem;
      box-shadow: 0 24px 60px -28px rgba(0,0,0,0.8);
    }}
    .chat-label {{
      font-size: 0.72rem; color: var(--faint); margin-bottom: 0.7rem;
      display: flex; align-items: center; gap: 0.45rem; font-weight: 600;
    }}
    .chat-label .av {{
      width: 1.4rem; height: 1.4rem; border-radius: 50%;
      background: linear-gradient(135deg, #ff9a5c, #ff5d6c);
      display: grid; place-items: center; font-size: 0.66rem; color: white; font-weight: 800;
    }}
    .bubble {{
      background: var(--surface-2); border: 1px solid var(--border);
      border-radius: 14px 14px 14px 5px; padding: 1.1rem 1.2rem;
      line-height: 1.55; font-size: 1.06rem;
    }}
    .tool-chip {{
      display: inline-flex; align-items: center; gap: 0.5rem; margin-top: 1.1rem;
      padding: 0.46rem 0.85rem; border-radius: 999px;
      background: rgba(46,224,138,0.1); border: 1px solid rgba(46,224,138,0.28);
      color: var(--good); font-size: 0.82rem;
      font-family: "JetBrains Mono", ui-monospace, monospace;
    }}
    .tool-chip .dotpulse {{
      width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--good);
      box-shadow: 0 0 0 0 rgba(46,224,138,0.6); animation: pulse 1.8s infinite;
    }}
    @keyframes pulse {{
      0% {{ box-shadow: 0 0 0 0 rgba(46,224,138,0.55); }}
      70% {{ box-shadow: 0 0 0 9px rgba(46,224,138,0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(46,224,138,0); }}
    }}
    .card-frame {{
      background: #ffffff; border-radius: 16px; padding: 1.4rem 1.6rem;
      min-height: 320px; box-shadow: var(--glow);
    }}
    .card-frame .tk-card {{ color: #0b1220; }}
    .card-cap {{
      display: flex; align-items: center; gap: 0.5rem;
      font-size: 0.76rem; color: var(--faint); margin-top: 0.85rem;
    }}
    .card-cap .swatch {{ width: 0.7rem; height: 0.7rem; border-radius: 3px; background: #e8f0fe; border: 1px solid #1a56db; }}
    .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.1rem; }}
    @media (max-width: 760px) {{ .split {{ grid-template-columns: 1fr; }} h1 {{ font-size: 1.6rem; }} }}
    .panel {{
      background: linear-gradient(180deg, var(--surface), var(--bg-2));
      border: 1px solid var(--border); border-radius: 14px; padding: 1.25rem;
    }}
    .panel h2 {{
      font-size: 0.74rem; margin: 0 0 0.85rem; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700;
      display: flex; align-items: center; gap: 0.45rem;
    }}
    .panel h2 .tag {{ font-size: 0.66rem; padding: 0.12rem 0.42rem; border-radius: 5px; }}
    .panel.bad {{ border-color: rgba(255,93,108,0.4); }}
    .panel.bad h2 .tag {{ background: rgba(255,93,108,0.15); color: var(--bad); }}
    .panel.good {{ border-color: rgba(46,224,138,0.4); }}
    .panel.good h2 .tag {{ background: rgba(46,224,138,0.15); color: var(--good); }}
    .inference {{
      color: #ffb9bf; font-style: italic; font-size: 0.96rem; line-height: 1.5;
      border-left: 2px solid var(--bad); padding-left: 0.85rem;
    }}
    .facts {{ list-style: none; padding: 0; margin: 0; }}
    .facts li {{
      margin-bottom: 0.8rem; font-size: 0.95rem; line-height: 1.5;
      padding-left: 1.15rem; position: relative;
    }}
    .facts li:last-child {{ margin-bottom: 0; }}
    .facts li::before {{
      content: "✓"; position: absolute; left: 0; top: 0;
      color: var(--good); font-weight: 800; font-size: 0.85rem;
    }}
    .pill {{
      display: inline-block; font-size: 0.66rem; padding: 0.12rem 0.5rem;
      border-radius: 999px; background: rgba(79,140,255,0.16);
      color: #9dc0ff; margin-left: 0.3rem; vertical-align: middle;
      border: 1px solid rgba(79,140,255,0.3);
    }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem; margin-top: 1.2rem; }}
    @media (max-width: 540px) {{ .metrics {{ grid-template-columns: 1fr; }} }}
    .metric {{
      background: linear-gradient(180deg, var(--surface), var(--bg-2));
      border: 1px solid var(--border); border-radius: 14px;
      padding: 1.15rem 1rem; text-align: center; position: relative; overflow: hidden;
    }}
    .metric::after {{
      content: ""; position: absolute; inset: 0 0 auto 0; height: 2px;
      background: linear-gradient(90deg, var(--good), var(--accent));
    }}
    .metric .val {{
      font-size: 2rem; font-weight: 800; letter-spacing: -0.03em;
      background: linear-gradient(120deg, var(--good), var(--accent));
      -webkit-background-clip: text; background-clip: text; color: transparent;
      font-variant-numeric: tabular-nums;
    }}
    .metric .lbl {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.3rem; font-weight: 600; }}
    .meta {{
      font-size: 0.78rem; color: var(--faint); margin-top: 1.05rem;
      font-family: "JetBrains Mono", ui-monospace, monospace;
    }}
    .meta .ok {{ color: var(--good); }}
    .arch {{
      display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem;
      font-size: 0.82rem; margin: 0.4rem 0 1.3rem;
    }}
    .arch span.node {{
      background: var(--surface-2); border: 1px solid var(--border);
      padding: 0.5rem 0.78rem; border-radius: 9px; font-weight: 500;
    }}
    .arch span.node.key {{
      border-color: rgba(79,140,255,0.45);
      background: rgba(79,140,255,0.1); color: #cfe0ff;
    }}
    .arch .arrow {{ color: var(--faint); font-size: 0.95rem; }}
    .pillrow {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.4rem; }}
    .feat {{
      display: inline-flex; align-items: center; gap: 0.4rem;
      background: var(--surface); border: 1px solid var(--border);
      padding: 0.4rem 0.72rem; border-radius: 999px;
      font-size: 0.78rem; color: var(--muted);
    }}
    .feat .d {{ width: 0.42rem; height: 0.42rem; border-radius: 50%; background: var(--accent); }}
    .ci {{
      display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 12px; padding: 0.85rem 1.1rem;
    }}
    .ci img {{ height: 20px; vertical-align: middle; }}
    .ci a {{ color: var(--accent); font-size: 0.86rem; text-decoration: none; font-weight: 600; }}
    .ci a:hover {{ text-decoration: underline; }}
    .ci .sep {{ color: var(--border); }}
    .hint {{
      position: fixed; bottom: 0; left: 0; right: 0; padding: 0.6rem;
      text-align: center; font-size: 0.74rem; color: var(--faint);
      background: rgba(15,22,34,0.9); backdrop-filter: blur(10px);
      border-top: 1px solid var(--border);
    }}
    .hint kbd {{
      background: var(--surface-2); border: 1px solid var(--border);
      border-radius: 5px; padding: 0.06rem 0.4rem; font-size: 0.72rem;
      color: var(--muted); font-family: ui-monospace, monospace;
    }}
  </style>
</head>
<body>
  <div class="progress"><span id="bar"></span></div>

  <nav class="nav">
    <div class="brand">
      <div class="mark">F</div>
      <div>
        <div class="nav-title">mcp-financial-data</div>
        <div class="nav-sub">citation-grounded 10-K · story demo</div>
      </div>
    </div>
    <div class="nav-right">
      <span class="counter"><b id="cur">1</b> / 4</span>
      <div class="nav-dots" id="dots"></div>
    </div>
  </nav>

  <div class="stage">
    <section class="slide active" data-slide="0">
      <span class="kicker"><span class="num">01</span> · The ask</span>
      <h1>Slide 1 — The ask: an analyst needs <span class="hl">filing-grounded</span> risk factors</h1>
      <p class="subtitle">A compliance analyst is preparing a diligence memo on Apple. Every claim must
        trace back to the 10-K — not to model paraphrase.</p>
      <div class="chat">
        <div class="chat-label"><span class="av">A</span> Analyst · via MCP client</div>
        <div class="bubble">{question}</div>
        <div class="tool-chip"><span class="dotpulse"></span> &rarr; {tool_label}</div>
      </div>
    </section>

    <section class="slide" data-slide="1">
      <span class="kicker"><span class="num">02</span> · The answer</span>
      <h1>Slide 2 — The answer: a <span class="hl">citation-grounded</span> card</h1>
      <p class="subtitle">The server calls <code>tenk.extract_section</code>. Only citation-grounded facts
        surface on the MCP Apps inline card. Click a pill to open SEC EDGAR.</p>
      <div class="card-frame">
        <div id="tenk-summary-card-root"></div>
      </div>
      <div class="card-cap"><span class="swatch"></span> Each pill is an Anthropic Citations API span
        linking to <code>cgi-bin/browse-edgar</code>.</div>
    </section>

    <section class="slide" data-slide="2">
      <span class="kicker"><span class="num">03</span> · The proof</span>
      <h1>Slide 3 — The proof: uncited output <span class="hl">never</span> ships</h1>
      <p class="subtitle">Speculative output stays in notes, tagged INFERENCE. CI scores citation
        coverage and exec-accuracy on every pull request.</p>
      <div class="split">
        <div class="panel bad">
          <h2>Never surfaced as a fact <span class="tag">dropped</span></h2>
          <p class="inference">{inference}</p>
        </div>
        <div class="panel good">
          <h2>Surfaced with SEC citations <span class="tag">shipped</span></h2>
          <ul class="facts">{cited_facts}</ul>
        </div>
      </div>
      <div class="metrics">
        <div class="metric"><div class="val">{exec_acc}</div><div class="lbl">exec-accuracy</div></div>
        <div class="metric"><div class="val">{cite_cov}</div><div class="lbl">citation coverage</div></div>
        <div class="metric"><div class="val">{judge}</div><div class="lbl">judge score</div></div>
      </div>
      <p class="meta">run_id: {run_id} · offline: <span class="ok">{str(offline).lower()}</span> · cost: <span class="ok">$0.00</span></p>
    </section>

    <section class="slide" data-slide="3">
      <span class="kicker"><span class="num">04</span> · The stack</span>
      <h1>Slide 4 — The stack: <span class="hl">production-grade</span> by construction</h1>
      <p class="subtitle">MCP spec 2025-11-25 · OAuth 2.1 resource server · citation-grounded
        extraction · deterministic eval gate in CI.</p>
      <div class="pillrow">
        <span class="feat"><span class="d"></span> MCP 2025-11-25</span>
        <span class="feat"><span class="d"></span> OAuth 2.1 + PKCE</span>
        <span class="feat"><span class="d"></span> Citations API</span>
        <span class="feat"><span class="d"></span> Opus 4.7 judge</span>
        <span class="feat"><span class="d"></span> mypy --strict</span>
        <span class="feat"><span class="d"></span> 85% coverage gate</span>
      </div>
      <div class="arch">
        <span class="node">MCP Client</span><span class="arrow">&rarr;</span>
        <span class="node key">OAuth 2.1 JWT</span><span class="arrow">&rarr;</span>
        <span class="node">FastMCP Server</span><span class="arrow">&rarr;</span>
        <span class="node key">tenk.extract_section</span><span class="arrow">&rarr;</span>
        <span class="node">Claude Sonnet 4.5 + Citations API</span><span class="arrow">&rarr;</span>
        <span class="node key">TenKSummaryCard</span>
      </div>
      <div class="arch">
        <span class="node">EDGAR · FRED · Polygon</span><span class="arrow">·</span>
        <span class="node">SQLite cache 24h</span><span class="arrow">·</span>
        <span class="node">Opus 4.7 eval judge</span><span class="arrow">·</span>
        <span class="node">smoke eval every PR</span>
      </div>
      <div class="ci">
        <img src="{CI_BADGE_URL}" alt="CI passing" />
        <span class="sep">|</span>
        <a href="{REPO_URL}" target="_blank" rel="noopener">github.com/SebAustin/mcp-financial-data</a>
      </div>
    </section>
  </div>

  <p class="hint"><kbd>&larr;</kbd> <kbd>&rarr;</kbd> arrow keys or click the numbered tiles · teleprompter: <code>make demo-video-script</code></p>

  <script>window.__TENK_UI_PROPS__ = {props_json};</script>
  <script src="./{PREVIEW_BUNDLE_NAME}"></script>
  <script>
    const slides = document.querySelectorAll(".slide");
    const dotsEl = document.getElementById("dots");
    const bar = document.getElementById("bar");
    const curEl = document.getElementById("cur");
    let current = 0;
    slides.forEach((_, i) => {{
      const btn = document.createElement("button");
      btn.className = "dot" + (i === 0 ? " active" : "");
      btn.textContent = String(i + 1);
      btn.type = "button";
      btn.setAttribute("aria-label", "Slide " + (i + 1));
      btn.onclick = () => show(i);
      dotsEl.appendChild(btn);
    }});
    function show(n) {{
      current = Math.max(0, Math.min(slides.length - 1, n));
      slides.forEach((s, i) => s.classList.toggle("active", i === current));
      dotsEl.querySelectorAll(".dot").forEach((d, i) => d.classList.toggle("active", i === current));
      bar.style.width = (((current + 1) / slides.length) * 100) + "%";
      curEl.textContent = String(current + 1);
    }}
    document.addEventListener("keydown", (e) => {{
      if (e.key === "ArrowRight" || e.key === " ") {{ e.preventDefault(); show(current + 1); }}
      if (e.key === "ArrowLeft") {{ e.preventDefault(); show(current - 1); }}
    }});
    show(0);
  </script>
</body>
</html>
"""

    index_path = target_dir / HUB_INDEX_NAME
    index_path.write_text(index_html, encoding="utf-8")
    return index_path
