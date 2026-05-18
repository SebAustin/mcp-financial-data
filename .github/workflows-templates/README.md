# GitHub Actions workflow templates

The Cursor / Claude write hook blocks the creation of NEW
`.github/workflows/*.yml` files at scaffold time as a security guardrail
against workflow-injection patterns. Both workflows below are written to
this directory as `*.yml` files so a human (you) can review them and copy
them into `.github/workflows/` as a single conscious commit.

## How to install

```bash
mkdir -p .github/workflows
cp .github/workflows-templates/ci.yml         .github/workflows/ci.yml
cp .github/workflows-templates/eval-nightly.yml .github/workflows/eval-nightly.yml
git add .github/workflows
git commit -m "ci: install ci + eval-nightly workflows"
```

## Why two files

- `ci.yml` runs on every PR + push to `main`. Lints, type-checks, runs the
  full pytest suite with the 85% coverage gate, and runs the smoke eval in
  `--offline` mode (no secrets needed). Posts the eval delta as a sticky
  PR comment.
- `eval-nightly.yml` runs at 07:17 UTC daily and on `workflow_dispatch`.
  Runs the FULL eval against live SEC EDGAR / FRED / Polygon / Anthropic
  endpoints with `MAX_API_SPEND_USD=5` to bound spend.

## Secrets these workflows expect

`eval-nightly.yml` reads:

- `ANTHROPIC_API_KEY`
- `FRED_API_KEY`
- `POLYGON_API_KEY`
- `EDGAR_USER_AGENT`

`ci.yml` needs no secrets — it always runs `--offline`.

## Security posture

Both files follow the patterns in
<https://github.blog/security/vulnerability-research/how-to-catch-github-actions-workflow-injections-before-attackers-do/>:

- No untrusted GitHub event payload values are interpolated into `run:`
  blocks. Anything that comes from event context goes through `env:` first.
- The PR-comment poster reads PR number from `GITHUB_EVENT_PATH` (a path,
  not a string), then calls `gh pr comment` with fixed argv — no shell.
