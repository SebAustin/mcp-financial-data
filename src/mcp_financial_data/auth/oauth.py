"""OAuth 2.1 resource-server primitives for the MCP server.

Per MCP spec 2025-11-25 §authorization, an MCP server that requires OAuth
acts as a *resource server*: it validates JWTs minted by an external IdP
(Auth0, Authentik, Keycloak, ...). The contract is captured in ADR 0004 and
the JWT algorithm allowlist in ADR 0005.

This module is the only place in the codebase that talks to PyJWT or the
JWKS endpoint. It exposes:

- ``validate_bearer_token(token, settings)`` — full RFC 6750 validation.
- ``issue_dev_token(subject, settings)`` — dev-only HS256 minter, gated on
  a local issuer URL.
- ``oauth_dependency(settings)`` — ASGI middleware factory that gates every
  HTTP request to the FastMCP server.
- ``build_www_authenticate(error, description)`` — RFC 6750 header builder.
- A ``dev-token`` CLI subcommand for local testing
  (``python -m mcp_financial_data.auth.oauth dev-token``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Any, Final

import httpx
import jwt
from pydantic import BaseModel, ConfigDict, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mcp_financial_data.logging import configure_logging, get_logger
from mcp_financial_data.settings import Settings, get_settings

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

WWW_AUTHENTICATE_HEADER: Final[str] = "WWW-Authenticate"

#: JWT algorithms accepted by ``validate_bearer_token``. See ADR 0005 for the
#: rationale (HS256 for local dev tokens; RS256/ES256 for production IdPs;
#: ``none`` and weaker symmetric variants are rejected at the header level).
ALLOWED_ALGORITHMS: Final[tuple[str, ...]] = ("HS256", "RS256", "ES256")

#: TTL of an ``issue_dev_token`` JWT. Sixty minutes is enough for an iterative
#: local CLI session and short enough to keep stale tokens from drifting.
DEV_TOKEN_TTL_SECONDS: Final[int] = 60 * 60

#: HTTP timeout for JWKS fetches. JWKS endpoints are CDN-fronted and fast;
#: we want to fail closed rather than block a tool call.
_JWKS_HTTP_TIMEOUT_SECONDS: Final[float] = 5.0

# ---------------------------------------------------------------------------
# Minimal ASGI type aliases (kept local so we do not depend on Starlette here)
# ---------------------------------------------------------------------------

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_log = get_logger("auth.oauth")


# ---------------------------------------------------------------------------
# Errors + models
# ---------------------------------------------------------------------------


class OAuthError(Exception):
    """Base class for OAuth resource-server errors."""


class InvalidTokenError(OAuthError):
    """RFC 6750 ``invalid_token``: token is missing, expired, or malformed."""


class InsufficientScopeError(OAuthError):
    """RFC 6750 ``insufficient_scope``: token is valid but lacks required scope."""


class TokenClaims(BaseModel):
    """Validated JWT claim set surfaced to tools.

    Only the fields we actually consume are typed; the rest are dropped so a
    malicious claim cannot smuggle data through.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sub: str = Field(..., description="Subject — opaque user/client ID from IdP.")
    aud: str = Field(..., description="Audience — must match settings.mcp_oauth_audience.")
    iss: str = Field(..., description="Issuer URL — must match settings.mcp_oauth_issuer.")
    scopes: tuple[str, ...] = Field(
        default=(), description="Granted scopes parsed from the ``scope`` claim."
    )
    exp: int = Field(..., ge=0, description="Expiry epoch seconds (UTC).")


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------


@dataclass
class JwksCache:
    """Process-local cache of JWKS public keys keyed by ``kid``.

    The cache is intentionally tiny: a single ``dict[kid, PyJWK]`` plus a
    monotonic ``_fetched_at`` timestamp. When ``ttl_seconds`` elapses or when
    a ``kid`` is missing on lookup, the caller re-fetches the JWKS document.

    Instances are not safe to share across event loops, but a single process
    that runs one asyncio loop is the common case here.
    """

    ttl_seconds: int = 3600
    _keys: dict[str, jwt.PyJWK] = field(default_factory=dict)
    _fetched_at: float = 0.0

    def is_fresh(self: JwksCache) -> bool:
        return self._fetched_at > 0.0 and (time.monotonic() - self._fetched_at) < self.ttl_seconds

    def invalidate(self: JwksCache) -> None:
        self._keys.clear()
        self._fetched_at = 0.0

    def load(self: JwksCache, jwks: dict[str, Any]) -> None:
        """Replace the cache with a freshly-fetched JWKS document."""
        new_keys: dict[str, jwt.PyJWK] = {}
        for raw in jwks.get("keys", []):
            if not isinstance(raw, dict):
                continue
            kid = raw.get("kid")
            if not isinstance(kid, str) or not kid:
                continue
            try:
                new_keys[kid] = jwt.PyJWK(raw)
            except jwt.PyJWKError:
                continue
        self._keys = new_keys
        self._fetched_at = time.monotonic()

    def get(self: JwksCache, kid: str) -> jwt.PyJWK | None:
        return self._keys.get(kid)


_jwks_cache_singleton: JwksCache = JwksCache()


def reset_jwks_cache() -> None:
    """Re-init the module-level JWKS cache. Used by tests and key rotation."""
    global _jwks_cache_singleton
    settings = get_settings()
    _jwks_cache_singleton = JwksCache(ttl_seconds=settings.mcp_oauth_jwks_ttl_seconds)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scopes_from_claim(raw: Any) -> tuple[str, ...]:
    """Parse an OAuth ``scope`` claim into a tuple. Accepts list or string."""
    if raw is None:
        return ()
    if isinstance(raw, list):
        return tuple(str(s) for s in raw if str(s).strip())
    if isinstance(raw, str):
        return tuple(s for s in raw.split() if s)
    return ()


@retry(
    reraise=True,
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
)
async def _fetch_jwks(jwks_url: str) -> dict[str, Any]:
    """Fetch the JWKS document with bounded retries on transport errors."""
    async with httpx.AsyncClient(timeout=_JWKS_HTTP_TIMEOUT_SECONDS) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise InvalidTokenError("JWKS response was not a JSON object")
        return data


async def _resolve_signing_key(
    token: str, settings: Settings, cache: JwksCache
) -> str | bytes | jwt.PyJWK:
    """Return the signing key for ``token`` (HS256 secret or PyJWK)."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(f"token header invalid: {exc}") from exc

    alg = header.get("alg")
    if alg not in ALLOWED_ALGORITHMS:
        raise InvalidTokenError(f"algorithm {alg!r} not in allowlist {ALLOWED_ALGORITHMS}")

    if alg == "HS256":
        secret = settings.mcp_oauth_dev_secret
        if secret is None:
            raise InvalidTokenError("HS256 token rejected: MCP_OAUTH_DEV_SECRET is not set")
        return secret.get_secret_value()

    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise InvalidTokenError("token header missing 'kid' for asymmetric algorithm")

    if not cache.is_fresh() or cache.get(kid) is None:
        try:
            jwks = await _fetch_jwks(settings.mcp_oauth_jwks_url)
        except httpx.HTTPError as exc:
            raise InvalidTokenError(f"jwks fetch failed: {exc}") from exc
        cache.load(jwks)

    pyjwk = cache.get(kid)
    if pyjwk is None:
        # Treat unknown kid as key rotation: drop cache and retry once.
        cache.invalidate()
        try:
            jwks = await _fetch_jwks(settings.mcp_oauth_jwks_url)
        except httpx.HTTPError as exc:
            raise InvalidTokenError(f"jwks fetch failed: {exc}") from exc
        cache.load(jwks)
        pyjwk = cache.get(kid)

    if pyjwk is None:
        raise InvalidTokenError(f"no JWKS key for kid={kid!r}")
    return pyjwk


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def validate_bearer_token(token: str, settings: Settings | None = None) -> TokenClaims:
    """Validate a Bearer JWT against the configured JWKS and return its claims.

    Raises:
        InvalidTokenError: token is missing, malformed, expired, or signed by
            a key not in the JWKS, or audience/issuer mismatch.
        InsufficientScopeError: token is structurally valid but missing one
            or more required scopes from ``settings.required_scopes_list``.
    """
    s = settings or get_settings()
    if not token:
        raise InvalidTokenError("missing bearer token")

    signing_key = await _resolve_signing_key(token, s, _jwks_cache_singleton)
    key: Any = signing_key.key if isinstance(signing_key, jwt.PyJWK) else signing_key

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=list(ALLOWED_ALGORITHMS),
            audience=s.mcp_oauth_audience,
            issuer=s.mcp_oauth_issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("token expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise InvalidTokenError("token audience invalid") from exc
    except jwt.InvalidIssuerError as exc:
        raise InvalidTokenError("token issuer invalid") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(f"token invalid: {exc}") from exc

    if not isinstance(payload, dict):
        raise InvalidTokenError("decoded JWT payload was not a JSON object")

    scopes = _scopes_from_claim(payload.get("scope") or payload.get("scopes"))
    required = s.required_scopes_list
    missing = tuple(sc for sc in required if sc not in scopes)
    if missing:
        raise InsufficientScopeError(f"missing required scope(s): {' '.join(missing)}")

    return TokenClaims(
        sub=str(payload["sub"]),
        aud=str(payload["aud"]),
        iss=str(payload["iss"]),
        scopes=scopes,
        exp=int(payload["exp"]),
    )


def _is_dev_issuer(issuer: str) -> bool:
    """Allow local Authentik/Keycloak dev tenants and ``http://localhost`` only."""
    return issuer.startswith("https://idp.local.test") or issuer.startswith("http://localhost")


async def issue_dev_token(subject: str = "dev-user", settings: Settings | None = None) -> str:
    """Mint a 60-minute HS256 JWT for local CLI testing. NEVER used in prod.

    Raises:
        RuntimeError: the configured issuer is not a local dev URL or the
            HS256 shared secret is not configured.
    """
    s = settings or get_settings()
    if not _is_dev_issuer(s.mcp_oauth_issuer):
        raise RuntimeError(
            "issue_dev_token refused: issuer is not a local dev URL. "
            "Set MCP_OAUTH_ISSUER to https://idp.local.test or http://localhost."
        )
    secret = s.mcp_oauth_dev_secret
    if secret is None:
        raise RuntimeError("issue_dev_token refused: MCP_OAUTH_DEV_SECRET is not set.")

    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "aud": s.mcp_oauth_audience,
        "iss": s.mcp_oauth_issuer,
        "iat": now,
        "exp": now + DEV_TOKEN_TTL_SECONDS,
        "scope": " ".join(s.required_scopes_list),
    }
    _log.info("oauth.dev_token.issued", subject=subject, audience=s.mcp_oauth_audience)
    return jwt.encode(payload, secret.get_secret_value(), algorithm="HS256")


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------


def oauth_dependency(settings: Settings) -> Callable[[ASGIApp], ASGIApp]:
    """Return an ASGI middleware factory that enforces OAuth 2.1 per request.

    The returned callable wraps an ``ASGIApp``. On every ``http`` scope it
    extracts the Bearer token from the ``Authorization`` header, validates it
    via :func:`validate_bearer_token`, and either:

    1. Forwards the request to the inner app, with ``TokenClaims`` attached
       at ``scope["state"]["oauth_claims"]``.
    2. Short-circuits with an RFC 6750 ``401`` (``invalid_token``) or ``403``
       (``insufficient_scope``) response carrying the matching
       ``WWW-Authenticate`` header.

    Non-``http`` scopes (lifespan, websocket) are forwarded unchanged.
    """

    def wrap(app: ASGIApp) -> ASGIApp:
        async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
            if scope.get("type") != "http":
                await app(scope, receive, send)
                return

            token = _bearer_token_from_headers(scope.get("headers", []))
            try:
                claims = await validate_bearer_token(token, settings)
            except InsufficientScopeError as exc:
                await _send_oauth_error(send, "insufficient_scope", str(exc), status=403)
                return
            except InvalidTokenError as exc:
                await _send_oauth_error(send, "invalid_token", str(exc), status=401)
                return

            state = scope.get("state")
            if not isinstance(state, dict):
                state = {}
                scope["state"] = state
            state["oauth_claims"] = claims

            await app(scope, receive, send)

        return asgi

    return wrap


def _bearer_token_from_headers(headers: Any) -> str:
    """Pull the Bearer token out of an ASGI ``headers`` list. Returns ``""`` if absent."""
    for name, value in headers or ():
        if not isinstance(name, bytes | bytearray) or not isinstance(value, bytes | bytearray):
            continue
        if name.lower() != b"authorization":
            continue
        decoded = bytes(value).decode("ascii", "ignore").strip()
        if decoded.lower().startswith("bearer "):
            return decoded[7:].strip()
        return ""
    return ""


async def _send_oauth_error(send: Send, error: str, description: str, status: int) -> None:
    """Emit an RFC 6750-shaped error response over ASGI."""
    safe_desc = description.replace('"', "'")[:200]
    body = json.dumps({"error": error, "error_description": safe_desc}).encode("utf-8")
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
        (b"www-authenticate", build_www_authenticate(error, safe_desc).encode("ascii")),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body, "more_body": False})


def build_www_authenticate(error: str, error_description: str) -> str:
    """Build an RFC 6750 ``WWW-Authenticate`` header value.

    Example::

        build_www_authenticate("invalid_token", "Token expired") ->
            'Bearer error="invalid_token", error_description="Token expired"'
    """
    if '"' in error or '"' in error_description:
        raise ValueError("error and error_description must not contain double quotes")
    return f'Bearer error="{error}", error_description="{error_description}"'


# ---------------------------------------------------------------------------
# CLI entry point: ``python -m mcp_financial_data.auth.oauth dev-token``
# ---------------------------------------------------------------------------


def _cli_main(argv: list[str] | None = None) -> int:
    """Tiny argparse shell so ``make oauth-dev`` mints a token without ceremony."""
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m mcp_financial_data.auth.oauth")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_dev = sub.add_parser("dev-token", help="Mint a dev-only HS256 JWT.")
    p_dev.add_argument("--subject", default="dev-user", help="Subject claim (default: dev-user).")
    args = parser.parse_args(argv)

    if args.cmd == "dev-token":
        token = asyncio.run(issue_dev_token(args.subject))
        sys.stdout.write(token + "\n")
        return 0
    return 2  # pragma: no cover -- argparse already raises before we reach this


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli_main())
