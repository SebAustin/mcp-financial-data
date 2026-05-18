# ADR 0001 — Record architecture decisions in MADR

* Status: Accepted
* Date: 2026-05-17
* Deciders: Sebastien Henry

## Context and Problem Statement

The 9-project portfolio sprint produces ~10 architectural decisions per repo,
read by hiring managers across Anthropic, Cursor, Snowflake, Databricks, and
others. We need a uniform, low-overhead format that records *why* each
decision was made and what alternatives were considered, so a reviewer can
trace any non-default behaviour back to a one-page rationale.

## Decision Drivers

* Master `.cursorrules` §9 mandates an ADR for every deviation from defaults.
* Reviewers should not have to grep commit messages to understand why a
  given approach was chosen.
* The format should be searchable, version-controllable, and renderable on
  GitHub without tooling.

## Considered Options

* **MADR (Markdown Any Decision Records).** Lightweight, headings-driven.
* **Y-statements.** Single-paragraph decisions; too compact to capture
  alternatives and consequences.
* **arc42 / Architecture Haiku.** Heavyweight; designed for whole-system
  documents, not decisions.

## Decision Outcome

Use **MADR** for every architecture decision in this repo, stored under
`docs/adr/NNNN-kebab-case-title.md`.

## Consequences

* Reviewers can read the ADRs in order and reconstruct the architecture.
* Adding a new architectural decision is a 5-minute Markdown task.
* CI does not enforce ADR creation today; we trust the PR template's
  checklist instead.

## References

* https://adr.github.io/madr/
* Master `.cursorrules` §9 (Documentation).
