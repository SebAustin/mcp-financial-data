# Prompt 06 — CI polish, README, v0.1.0 release

> Owns: tag, README polish (real eval numbers), Loom recording, three
> filed GitHub issues.

## Goals

1. Run `make ci` locally and a clean nightly. Capture the summary JSON.
2. Paste real numbers into the README "Eval targets (W1)" table —
   replace the targets with actuals.
3. Record a 60-second Loom (script: `prompts/99_loom_script.md`) showing:
   OAuth round-trip → `tenk.extract_section` call → MCP Apps UI rendering
   → eval JSONL appearing in `evals/runs/`.
4. File the three issues from `.github/issues-seed/` with `gh issue
   create -F`.
5. Tag `v0.1.0` and push the tag.

## Acceptance

- README eval table cells are numbers, not "TBD" or "TODO".
- The Loom is linked from the README and pinned at the top of the GitHub
  repo's About panel.
- Three issues are open under labels `feat`, `bug`, `eval`.
- Tag `v0.1.0` exists on `main` with a CHANGELOG entry.
- The repo's About panel contains the W1 anchor companies as a one-liner.

## Files touched

- `README.md` (numbers), `CHANGELOG.md` (new), `prompts/99_loom_script.md`
  (revisit if reality diverges).

## Application send

After the tag, send applications per `SPRINT_PLAN.md §A.6`:

- Anthropic FDE (LinkedIn DM + careers + referral ping).
- Cursor FDE (cold email engineering lead + LinkedIn DM).
