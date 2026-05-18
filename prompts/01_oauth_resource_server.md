# Prompt 01 — OAuth 2.1 resource server

> Owns: `src/mcp_financial_data/auth/oauth.py` and the dev-token CLI.

You are implementing the OAuth 2.1 resource server for an MCP spec
2025-11-25 streamable-HTTP server. The contract is in ADR 0004 and
`.cursor/rules/citations.mdc` is irrelevant here.

## Goals

1. `validate_bearer_token(token, settings)` returns a `TokenClaims` object
   for valid tokens and raises `InvalidTokenError` /
   `InsufficientScopeError` per RFC 6750.
2. `issue_dev_token(subject)` mints a 60-minute HS256 JWT for local CLI
   testing **only**, gated behind a runtime check that
   `settings.mcp_oauth_issuer` starts with `https://idp.local.test` or
   `http://localhost`.
3. A small ASGI middleware factory `oauth_dependency(settings)` that
   FastMCP's HTTP layer can use to gate every tool call.

## Acceptance

- `tests/unit/auth/test_oauth.py` adds:
  - HS256 token valid → returns `TokenClaims` with parsed scopes.
  - Wrong audience → `InvalidTokenError`.
  - Missing required scope → `InsufficientScopeError`.
  - Expired `exp` → `InvalidTokenError`.
  - JWKS-cached RS256 token round-trip via `respx` mock of JWKS URL.
- A new integration test under `tests/integration/auth/` (skipped by
  default) round-trips against a local Authentik via Docker compose.
- `make ci` stays green; coverage on `auth/` ≥ 90%.

## Implementation hints

- Use `PyJWT[crypto]` for verification; `jwt.decode(... options=...)` with
  algorithms list constrained to `["HS256", "RS256", "ES256"]`.
- Use `httpx.AsyncClient` for the JWKS fetch, with `tenacity` retry on
  `httpx.HTTPError`.
- Cache JWKS keys for `JwksCache.ttl_seconds` (default 3600). Invalidate
  on `kid` mismatch.
- Required scopes are checked against `settings.required_scopes_list` —
  ALL must be present.
- Build the `WWW-Authenticate` value using `auth.oauth.build_www_authenticate`
  (already shipped in the scaffold).

## File-by-file change list

- `src/mcp_financial_data/auth/oauth.py` (fill `validate_bearer_token`,
  `issue_dev_token`, add `oauth_dependency`).
- `tests/unit/auth/test_oauth.py` (extend with HS256 + RS256 round-trips).
- `tests/integration/auth/test_authentik.py` (new; skipped by default).
- `docs/adr/0005-jwt-algorithm-allowlist.md` (new ADR explaining the
  algorithm allowlist choice).
- `prompts/02_edgar_client.md` is the next prompt — do NOT touch it.
