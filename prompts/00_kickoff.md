# Kickoff prompt — mcp-financial-data (W1, May 18 2026)

> Open in Cursor with Claude Sonnet 4.5 (or Opus 4.7) and paste below into
> the chat to kick off W1. The repo is fully scaffolded; this prompt sets
> the build order and the first PR scope.

---

You are pair-programming with Sebastien Henry on `mcp-financial-data`,
project P1 of a 9-project portfolio sprint. The repo has been scaffolded
with typed stubs and a green CI gate. Your job today is to land the **first
PR** and tag `v0.0.2`.

## What's already done

- `make ci` is green (ruff + ruff format + mypy --strict + pytest with 85%
  coverage gate + smoke eval offline + server build smoke).
- Five eval cases pass in `--offline` mode with mean judge score 1.0.
- All public functions are typed; the bodies raise `NotImplementedError`
  with a pointer to the prompt that fills them in.
- ADRs 0001–0004 are merged. Read them. Don't re-litigate.

## Your build order (W1)

| # | Prompt | Owns | Eval target after merge |
| --- | --- | --- | --- |
| 1 | `prompts/01_oauth_resource_server.md` | `src/mcp_financial_data/auth/oauth.py` | `validate_bearer_token` round-trips an HS256 dev token. |
| 2 | `prompts/02_edgar_client.md` | `src/mcp_financial_data/tools/{edgar,fred,polygon}.py` | First 4 eval cases pass against `respx` mocks AND against live APIs nightly. |
| 3 | `prompts/03_tenk_citations_extractor.md` | `src/mcp_financial_data/extractors/tenk.py` | `tenk-aapl-risk-factors` case passes with citation_coverage = 1.0. |
| 4 | `prompts/04_mcp_apps_ui.md` | `src/mcp_financial_data/apps/ui.py` | UI envelope renders in Claude Desktop. |
| 5 | `prompts/05_evals_full_run.md` | `src/mcp_financial_data/evals/harness.py` (online mode) | Nightly eval green for 3 days. |
| 6 | `prompts/06_ci_polish_release.md` | tag, README polish, Loom | `v0.1.0` tagged. |

## Hard constraints (skim every prompt)

- **Citations are non-optional** for the 10-K extractor. ADR 0003.
- **EDGAR Fair Access:** every request carries `EDGAR_USER_AGENT`; rate
  limit ≤ 10 req/sec. ADR 0002, `.cursor/rules/edgar-fair-access.mdc`.
- **OAuth 2.1 RS:** validate JWTs against the configured JWKS; never
  hardcode public keys. ADR 0004.
- **Spend cap:** `MAX_API_SPEND_USD` enforced in extractor + harness.
- **No `requests`, no `print()`, no `subprocess shell=True`, no bare `except`.**
- **No `langgraph.prebuilt.create_react_agent`** — this is an MCP server,
  not an agent.

## First PR scope (today, May 18, 19:00–22:00 CT)

> All paths below are **relative to the repo root**. Make sure your shell is
> inside `mcp-financial-data/`:
>
> ```bash
> cd ~/Documents/Personal/Training/Project/Github/mcp-financial-data
> pwd  # should end in `/mcp-financial-data`
> ```

1. Install the CI workflows (one-time, security-hook workaround):

   ```bash
   mkdir -p .github/workflows
   cp .github/workflows-templates/ci.yml          .github/workflows/ci.yml
   cp .github/workflows-templates/eval-nightly.yml .github/workflows/eval-nightly.yml
   git add .github/workflows
   git commit -m "ci: install ci + eval-nightly workflows"
   ```

   See `.github/workflows-templates/README.md` for why these ship as
   templates instead of being created at scaffold time.

2. Run `make setup` and `make ci`. Fix any local environmental issues
   (e.g. Docker not running for `docker-compose.yml` smoke).
3. Open `prompts/01_oauth_resource_server.md` and follow the steps. Land
   the first eval delta as a sticky comment. Tag `v0.0.2` after merge.

## Style

- Conventional commits. Each PR closes one issue from
  `.github/issues-seed/`.
- One file per PR when possible. When not possible, group changes by
  ADR'd boundary.
- Every ADR-worthy decision goes in `docs/adr/NNNN-*.md` BEFORE the PR
  that depends on it.

When you're ready, open `prompts/01_oauth_resource_server.md`.
