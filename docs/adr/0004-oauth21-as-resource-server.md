# ADR 0004 — Run as an OAuth 2.1 resource server, not an IdP

* Status: Accepted
* Date: 2026-05-17
* Deciders: Sebastien Henry

## Context and Problem Statement

MCP spec 2025-11-25 §authorization specifies that an MCP server requiring
authentication is a resource server. We need to decide whether to also ship
an embedded IdP (for self-contained demos) or rely on an external IdP
(Auth0 / Authentik / Keycloak). The decision affects the security surface,
the demo setup time, and what hiring managers see in CI.

## Decision Drivers

* SEC 17a-4 / FINRA / SOX environments expect identity provisioning to
  live in a dedicated IdP, not application code.
* Embedding an IdP into a public OSS repo is an attractive target for
  drive-by exploits.
* External IdPs make the demo harder to spin up locally (need to register
  a client, get a JWKS URL, etc.).

## Considered Options

* **Resource server only; external IdP.** Production-shaped. Demo runs
  against a local Authentik / Keycloak / Auth0 dev tenant.
* **Embedded IdP.** Smaller demo footprint, but ships a token-minting
  surface that is out of scope and potentially insecure.
* **No auth.** Defers the problem; would invalidate the entire OAuth 2.1
  story and lose the Anthropic FDE anchor.

## Decision Outcome

Run as a resource server only:

1. Validate JWTs against `MCP_OAUTH_JWKS_URL`, audience
   `MCP_OAUTH_AUDIENCE`, and required scopes
   `MCP_OAUTH_REQUIRED_SCOPES`.
2. Expose a `dev-token` CLI subcommand (`prompts/01_oauth_resource_server.md`)
   that mints a short-lived HS256 JWT with the configured audience for
   local CLI testing only — gated behind an explicit `--dev-only` flag and
   never enabled in container images.
3. Reject any token whose `aud` / `iss` / `exp` / `scope` checks fail with
   RFC 6750 `WWW-Authenticate: Bearer error=...` headers.

## Consequences

* The demo expects a running IdP. We document Authentik in
  `prompts/01_oauth_resource_server.md` because it is OSS, free, and
  Docker-Compose-able.
* Production deployments swap the IdP via env vars — no code change.
* The integration test suite uses HS256 dev tokens; the unit test suite
  asserts shape but never hits a real IdP.

## References

* https://modelcontextprotocol.io/specification/2025-11-25 (Authorization).
* https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1
* https://datatracker.ietf.org/doc/html/rfc6750
