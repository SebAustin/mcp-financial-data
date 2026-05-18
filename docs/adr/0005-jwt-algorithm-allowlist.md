# ADR 0005 — JWT algorithm allowlist for the OAuth resource server

* Status: Accepted
* Date: 2026-05-18
* Deciders: Sebastien Henry

## Context and Problem Statement

`validate_bearer_token` calls `jwt.decode` from `PyJWT`. By default, PyJWT
will accept any signing algorithm advertised in the token's header. This is
the historical root cause of the
[JWT "alg=none" confusion attacks](https://datatracker.ietf.org/doc/html/rfc8725#section-3.2)
and several
[key-confusion attacks](https://datatracker.ietf.org/doc/html/rfc8725#section-3.1)
(HS256 token forged against an RS256 public key). PyJWT lets the caller
constrain accepted algorithms via the `algorithms=` parameter, but only if
the caller actually sets it.

This ADR records the explicit allowlist used by the resource server and the
rationale for which algorithms are in or out.

## Decision Drivers

* RFC 8725 (JWT Best Current Practices) §3.1 + §3.2 mandate that resource
  servers fix the accepted algorithm set per key, never trust the header.
* MCP spec 2025-11-25 §authorization assumes an external OAuth 2.1 IdP. The
  IdPs we target (Auth0, Authentik, Keycloak, Cognito, Okta) default to
  RS256 or ES256; HS256 is only used by `issue_dev_token` for local CLI work.
* Hiring managers reviewing this repo will fail any auth code that does not
  set `algorithms=` on `jwt.decode`. The allowlist must be explicit, narrow,
  and documented.
* The allowlist must reject `none`, weak HMAC variants (HS384/HS512 with
  user-controllable secret length), and any future fast-moving "draft"
  algorithm that hasn't shipped in a stable PyJWT release.

## Considered Options

* **Strict allowlist:** `("HS256", "RS256", "ES256")`. Default-safe; works
  with every mainstream IdP and the dev-token flow.
* **Permissive allowlist:** `("HS256", "HS384", "HS512", "RS256", "RS384",
  "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512")`. Matches
  PyJWT's full algorithm map. Maximizes IdP compatibility, but enlarges the
  attack surface and silently allows weak HMAC variants.
* **Configurable allowlist via env var.** Pushes the decision onto the
  operator. Higher operational risk, weaker default.
* **JWKS-derived allowlist:** Use the `alg` field of the JWKS entry that
  matched the token's `kid`. Cleanest theoretically, but PyJWT does not
  expose this directly and the dev-token (HS256) flow has no JWKS entry.

## Decision Outcome

Use the **strict allowlist** `("HS256", "RS256", "ES256")` (see
`auth.oauth.ALLOWED_ALGORITHMS`). Specifically:

1. `validate_bearer_token` peeks the unverified header, rejects any `alg`
   not in the allowlist with `InvalidTokenError`, and then passes
   `algorithms=list(ALLOWED_ALGORITHMS)` to `jwt.decode`.
2. `issue_dev_token` is hard-coded to `HS256`. The matching `validate_bearer_token`
   path requires `MCP_OAUTH_DEV_SECRET` to be set and refuses HS256 tokens
   otherwise.
3. The allowlist may grow only via an ADR amendment. Adding an algorithm
   requires (a) an updated unit test asserting the new alg validates,
   (b) explicit rationale here, (c) a regression test asserting prior
   rejected algs remain rejected.

## Consequences

* IdPs configured for PS256 / RS384 / etc. must rotate to a supported alg
  before integrating, or this ADR must be amended first.
* The dev-token flow is intentionally HS256-only — the smaller surface is
  worth the inconvenience for a local CLI.
* A future migration to EdDSA (`EdDSA` / `Ed25519`) is one ADR amendment
  away. The PyJWT API already supports it; we are not enabling it today
  because no target IdP defaults to it in 2026.
* The unit test `test_validate_rejects_alg_none` and
  `test_validate_rejects_disallowed_alg_hs512` guard the allowlist against
  accidental widening.

## References

* RFC 8725 — JSON Web Token Best Current Practices (algorithm confusion,
  alg=none): https://datatracker.ietf.org/doc/html/rfc8725
* RFC 7518 §3 — JSON Web Algorithms:
  https://datatracker.ietf.org/doc/html/rfc7518
* RFC 6750 — OAuth 2.0 Bearer Token Usage:
  https://datatracker.ietf.org/doc/html/rfc6750
* PyJWT `jwt.decode` algorithms parameter:
  https://pyjwt.readthedocs.io/en/stable/usage.html
* ADR 0004 — Run as an OAuth 2.1 resource server, not an IdP.
