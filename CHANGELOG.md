# Changelog

All notable changes to this project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-05-21

W1 milestone: OAuth 2.1 resource server, live data tools, citation-grounded
10-K extractor, MCP Apps inline UI, and online eval harness with nightly gates.

### Added

- OAuth 2.1 JWT validation against external JWKS (`auth/oauth.py`).
- Async EDGAR, FRED, and Polygon clients with Fair Access headers, rate
  limiting, retries, and 24-hour SQLite response cache.
- Claude Sonnet 4.5 10-K extractor with Anthropic Citations API; uncited
  spans demoted to `[INFERENCE]` notes.
- MCP Apps `TenKSummaryCard` inline UI with citation pills and SEC browse URLs.
- Eval harness with offline fixtures, live dispatch, Opus 4.7 five-axis judge,
  `--budget`, and `--min-judge-score` gates.
- CI workflow (lint, mypy, pytest ≥85%, smoke eval) and nightly full eval
  workflow with sticky PR eval-delta comments.

### Changed

- Seed eval cases and offline fixtures aligned with live EDGAR/FRED reference
  data for nightly judge scoring.
- Model pricing table supports Anthropic snapshot ids (`claude-sonnet-4-6`,
  dated suffixes) with explicit lookup failures.

### Fixed

- Judge payload compaction for MSFT-scale `company_facts` responses (context
  window overflow).
- `UnknownModelPricingError` misclassified as missing offline fixture in the
  harness.

[0.1.0]: https://github.com/SebAustin/mcp-financial-data/releases/tag/v0.1.0
