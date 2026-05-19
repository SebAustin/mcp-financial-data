"""Tests for ``mcp_financial_data.auth.oauth``.

Covers the OAuth 2.1 resource-server contract from ADR 0004 and ADR 0005:

- HS256 dev-token round-trip (issue + validate).
- Wrong audience / issuer / expired / missing-scope error mapping per RFC 6750.
- RS256 JWKS-cached round-trip via ``respx`` mock of the JWKS URL.
- Disallowed algorithms (``none``, ``HS512``) raise ``InvalidTokenError``.
- ``issue_dev_token`` refuses non-local issuers.
- ``oauth_dependency`` ASGI middleware enforces the same contract on every
  HTTP request and emits an RFC 6750 ``WWW-Authenticate`` header on failure.
"""

from __future__ import annotations

import json
import time
from typing import Any, cast

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from mcp_financial_data.auth import oauth as oauth_mod
from mcp_financial_data.auth.oauth import (
    InsufficientScopeError,
    InvalidTokenError,
    OAuthError,
    TokenClaims,
    build_www_authenticate,
    issue_dev_token,
    oauth_dependency,
    reset_jwks_cache,
    validate_bearer_token,
)
from mcp_financial_data.settings import Settings, reload_settings


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    """Force a fresh JWKS cache for every test in this module."""
    reset_jwks_cache()


# ---------------------------------------------------------------------------
# Pure-shape tests (preserved from the scaffold).
# ---------------------------------------------------------------------------


def test_token_claims_rejects_extras() -> None:
    with pytest.raises(ValueError):
        TokenClaims.model_validate(
            {
                "sub": "u1",
                "aud": "mcp-financial-data",
                "iss": "https://idp.local.test",
                "scopes": ["mcp:read"],
                "exp": 1,
                "extra": "bad",
            }
        )


def test_token_claims_happy_path() -> None:
    c = TokenClaims(
        sub="u1",
        aud="mcp-financial-data",
        iss="https://idp.local.test",
        scopes=("mcp:read", "mcp:tools"),
        exp=1_900_000_000,
    )
    assert c.scopes == ("mcp:read", "mcp:tools")


def test_error_hierarchy() -> None:
    assert issubclass(InvalidTokenError, OAuthError)
    assert issubclass(InsufficientScopeError, OAuthError)


def test_build_www_authenticate_format() -> None:
    h = build_www_authenticate("invalid_token", "Token expired")
    assert h == 'Bearer error="invalid_token", error_description="Token expired"'


def test_build_www_authenticate_rejects_quotes() -> None:
    with pytest.raises(ValueError):
        build_www_authenticate('bad"err', "ok")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hs256_token(
    settings: Settings,
    *,
    sub: str = "u1",
    aud: str | None = None,
    iss: str | None = None,
    scope: str | None = None,
    exp_offset: int = 3600,
) -> str:
    """Mint an HS256 token directly with the dev secret. Used to forge edge cases."""
    secret_obj = settings.mcp_oauth_dev_secret
    assert secret_obj is not None, "test env must set MCP_OAUTH_DEV_SECRET"
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "aud": aud if aud is not None else settings.mcp_oauth_audience,
        "iss": iss if iss is not None else settings.mcp_oauth_issuer,
        "iat": now,
        "exp": now + exp_offset,
        "scope": scope if scope is not None else " ".join(settings.required_scopes_list),
    }
    return jwt.encode(payload, secret_obj.get_secret_value(), algorithm="HS256")


def _make_rsa_keypair() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    """Generate an RSA keypair and return ``(private_key, jwk_dict)`` with ``kid``."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk_json = RSAAlgorithm.to_jwk(private_key.public_key())
    jwk: dict[str, Any] = json.loads(jwk_json)
    jwk["kid"] = "kid-1"
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return private_key, jwk


# ---------------------------------------------------------------------------
# validate_bearer_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_hs256_valid_returns_token_claims() -> None:
    settings = reload_settings()
    token = _hs256_token(settings)
    claims = await validate_bearer_token(token, settings)
    assert claims.sub == "u1"
    assert claims.aud == settings.mcp_oauth_audience
    assert claims.iss == settings.mcp_oauth_issuer
    assert claims.scopes == ("mcp:read", "mcp:tools")
    assert claims.exp > int(time.time())


@pytest.mark.asyncio
async def test_validate_wrong_audience_raises_invalid_token() -> None:
    settings = reload_settings()
    token = _hs256_token(settings, aud="not-our-audience")
    with pytest.raises(InvalidTokenError, match="audience"):
        await validate_bearer_token(token, settings)


@pytest.mark.asyncio
async def test_validate_missing_required_scope_raises_insufficient_scope() -> None:
    settings = reload_settings()
    token = _hs256_token(settings, scope="mcp:read")  # missing mcp:tools
    with pytest.raises(InsufficientScopeError, match="mcp:tools"):
        await validate_bearer_token(token, settings)


@pytest.mark.asyncio
async def test_validate_expired_exp_raises_invalid_token() -> None:
    settings = reload_settings()
    token = _hs256_token(settings, exp_offset=-60)
    with pytest.raises(InvalidTokenError, match="expired"):
        await validate_bearer_token(token, settings)


@pytest.mark.asyncio
async def test_validate_empty_token_raises_invalid_token() -> None:
    settings = reload_settings()
    with pytest.raises(InvalidTokenError, match="missing"):
        await validate_bearer_token("", settings)


@pytest.mark.asyncio
async def test_validate_rejects_alg_none() -> None:
    settings = reload_settings()
    payload = {
        "sub": "u1",
        "aud": settings.mcp_oauth_audience,
        "iss": settings.mcp_oauth_issuer,
        "exp": int(time.time()) + 60,
        "scope": "mcp:read mcp:tools",
    }
    unsigned = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(InvalidTokenError, match="algorithm"):
        await validate_bearer_token(unsigned, settings)


@pytest.mark.asyncio
async def test_validate_rejects_disallowed_alg_hs512() -> None:
    settings = reload_settings()
    payload = {
        "sub": "u1",
        "aud": settings.mcp_oauth_audience,
        "iss": settings.mcp_oauth_issuer,
        "exp": int(time.time()) + 60,
        "scope": "mcp:read mcp:tools",
    }
    long_key = b"x" * 64  # forging HS512 requires a 64-byte key to avoid PyJWT warnings
    bad = jwt.encode(payload, long_key, algorithm="HS512")
    with pytest.raises(InvalidTokenError, match="algorithm"):
        await validate_bearer_token(bad, settings)


@pytest.mark.asyncio
async def test_validate_rs256_jwks_cached_roundtrip() -> None:
    settings = reload_settings()
    private_key, jwk = _make_rsa_keypair()

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "rs-user",
            "aud": settings.mcp_oauth_audience,
            "iss": settings.mcp_oauth_issuer,
            "iat": now,
            "exp": now + 3600,
            "scope": "mcp:read mcp:tools",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "kid-1"},
    )

    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(settings.mcp_oauth_jwks_url).mock(
            return_value=httpx.Response(200, json={"keys": [jwk]})
        )
        claims_1 = await validate_bearer_token(token, settings)
        claims_2 = await validate_bearer_token(token, settings)

    assert claims_1.sub == "rs-user"
    assert claims_2.sub == "rs-user"
    assert claims_1.scopes == ("mcp:read", "mcp:tools")
    assert route.call_count == 1, "JWKS should be cached across calls within TTL"


@pytest.mark.asyncio
async def test_validate_rs256_unknown_kid_refetches_then_raises() -> None:
    settings = reload_settings()
    private_key, jwk = _make_rsa_keypair()

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "rs-user",
            "aud": settings.mcp_oauth_audience,
            "iss": settings.mcp_oauth_issuer,
            "iat": now,
            "exp": now + 3600,
            "scope": "mcp:read mcp:tools",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "unknown-kid"},
    )

    with respx.mock(assert_all_called=False) as mock:
        mock.get(settings.mcp_oauth_jwks_url).mock(
            return_value=httpx.Response(200, json={"keys": [jwk]})
        )
        with pytest.raises(InvalidTokenError, match="kid"):
            await validate_bearer_token(token, settings)


@pytest.mark.asyncio
async def test_validate_rs256_missing_kid_raises() -> None:
    settings = reload_settings()
    private_key, _ = _make_rsa_keypair()
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "rs-user",
            "aud": settings.mcp_oauth_audience,
            "iss": settings.mcp_oauth_issuer,
            "iat": now,
            "exp": now + 3600,
            "scope": "mcp:read mcp:tools",
        },
        private_key,
        algorithm="RS256",
    )
    with pytest.raises(InvalidTokenError, match="kid"):
        await validate_bearer_token(token, settings)


@pytest.mark.asyncio
async def test_validate_rs256_jwks_fetch_http_error_raises_invalid_token() -> None:
    settings = reload_settings()
    private_key, _ = _make_rsa_keypair()
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "rs-user",
            "aud": settings.mcp_oauth_audience,
            "iss": settings.mcp_oauth_issuer,
            "iat": now,
            "exp": now + 3600,
            "scope": "mcp:read mcp:tools",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "kid-1"},
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get(settings.mcp_oauth_jwks_url).mock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(InvalidTokenError, match="jwks fetch failed"):
            await validate_bearer_token(token, settings)


@pytest.mark.asyncio
async def test_validate_malformed_token_header_raises() -> None:
    settings = reload_settings()
    with pytest.raises(InvalidTokenError, match="header"):
        await validate_bearer_token("not.a.jwt", settings)


@pytest.mark.asyncio
async def test_validate_hs256_with_no_dev_secret_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forging_settings = reload_settings()
    token = _hs256_token(forging_settings)
    # Realistic absence shape: blank placeholder in .env / env. ``delenv``
    # alone is not sufficient because pydantic-settings still reads ``.env``.
    monkeypatch.setenv("MCP_OAUTH_DEV_SECRET", "")
    settings = reload_settings()
    with pytest.raises(InvalidTokenError, match="MCP_OAUTH_DEV_SECRET"):
        await validate_bearer_token(token, settings)


@pytest.mark.asyncio
async def test_validate_accepts_list_form_scope_claim() -> None:
    settings = reload_settings()
    secret_obj = settings.mcp_oauth_dev_secret
    assert secret_obj is not None
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "u1",
            "aud": settings.mcp_oauth_audience,
            "iss": settings.mcp_oauth_issuer,
            "iat": now,
            "exp": now + 3600,
            "scopes": ["mcp:read", "mcp:tools"],
        },
        secret_obj.get_secret_value(),
        algorithm="HS256",
    )
    claims = await validate_bearer_token(token, settings)
    assert claims.scopes == ("mcp:read", "mcp:tools")


# ---------------------------------------------------------------------------
# issue_dev_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_dev_token_roundtrips() -> None:
    settings = reload_settings()
    token = await issue_dev_token("alice", settings=settings)
    claims = await validate_bearer_token(token, settings)
    assert claims.sub == "alice"
    assert set(claims.scopes) == set(settings.required_scopes_list)


@pytest.mark.asyncio
async def test_issue_dev_token_refuses_non_local_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_OAUTH_ISSUER", "https://prod.example.com")
    settings = reload_settings()
    with pytest.raises(RuntimeError, match="local"):
        await issue_dev_token(settings=settings)


@pytest.mark.asyncio
async def test_issue_dev_token_accepts_localhost_issuer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_OAUTH_ISSUER", "http://localhost:9000")
    settings = reload_settings()
    token = await issue_dev_token(settings=settings)
    assert isinstance(token, str)
    assert token.count(".") == 2


@pytest.mark.asyncio
async def test_issue_dev_token_requires_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Use ``setenv("")`` rather than ``delenv`` so the test also covers the
    # realistic case where ``.env`` carries a blank placeholder
    # (``MCP_OAUTH_DEV_SECRET=``).
    monkeypatch.setenv("MCP_OAUTH_DEV_SECRET", "")
    settings = reload_settings()
    with pytest.raises(RuntimeError, match="MCP_OAUTH_DEV_SECRET"):
        await issue_dev_token(settings=settings)


# ---------------------------------------------------------------------------
# oauth_dependency ASGI middleware
# ---------------------------------------------------------------------------


async def _drain_asgi(
    app: oauth_mod.ASGIApp, scope: dict[str, Any]
) -> tuple[int, dict[bytes, bytes], bytes]:
    """Drive an ASGI app once and capture status + headers + body."""
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await app(scope, receive, send)
    status = 0
    headers: dict[bytes, bytes] = {}
    body = b""
    for msg in sent:
        if msg["type"] == "http.response.start":
            status = int(msg["status"])
            headers = {k: v for k, v in msg.get("headers", [])}
        elif msg["type"] == "http.response.body":
            body += msg.get("body", b"")
    return status, headers, body


@pytest.mark.asyncio
async def test_oauth_dependency_passes_valid_request_through() -> None:
    settings = reload_settings()
    token = await issue_dev_token(settings=settings)

    inner_called: dict[str, Any] = {}

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        inner_called["scope"] = scope
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    middleware = oauth_dependency(settings)(inner)
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", f"Bearer {token}".encode("ascii"))],
    }
    status, _, body = await _drain_asgi(middleware, scope)
    assert status == 200
    assert body == b"ok"
    forwarded_claims = cast(TokenClaims, inner_called["scope"]["state"]["oauth_claims"])
    assert forwarded_claims.sub == "dev-user"


@pytest.mark.asyncio
async def test_oauth_dependency_rejects_missing_token_with_401() -> None:
    settings = reload_settings()

    async def inner(scope: Any, receive: Any, send: Any) -> None:  # pragma: no cover - not reached
        raise AssertionError("inner ASGI app should not be invoked when auth fails")

    middleware = oauth_dependency(settings)(inner)
    scope: dict[str, Any] = {"type": "http", "method": "POST", "path": "/mcp", "headers": []}
    status, headers, body = await _drain_asgi(middleware, scope)
    assert status == 401
    www = headers[b"www-authenticate"]
    assert www.startswith(b'Bearer error="invalid_token"')
    payload = json.loads(body)
    assert payload["error"] == "invalid_token"


@pytest.mark.asyncio
async def test_oauth_dependency_rejects_insufficient_scope_with_403() -> None:
    settings = reload_settings()
    token = _hs256_token(settings, scope="mcp:read")

    async def inner(scope: Any, receive: Any, send: Any) -> None:  # pragma: no cover - not reached
        raise AssertionError("inner ASGI app should not be invoked when scope check fails")

    middleware = oauth_dependency(settings)(inner)
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", f"Bearer {token}".encode("ascii"))],
    }
    status, headers, body = await _drain_asgi(middleware, scope)
    assert status == 403
    www = headers[b"www-authenticate"]
    assert www.startswith(b'Bearer error="insufficient_scope"')
    payload = json.loads(body)
    assert payload["error"] == "insufficient_scope"


@pytest.mark.asyncio
async def test_oauth_dependency_ignores_non_bearer_authorization() -> None:
    settings = reload_settings()

    async def inner(scope: Any, receive: Any, send: Any) -> None:  # pragma: no cover - not reached
        raise AssertionError("inner ASGI app should not be invoked when auth fails")

    middleware = oauth_dependency(settings)(inner)
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", b"Basic abc123")],
    }
    status, headers, _ = await _drain_asgi(middleware, scope)
    assert status == 401
    assert headers[b"www-authenticate"].startswith(b'Bearer error="invalid_token"')


@pytest.mark.asyncio
async def test_oauth_dependency_preserves_existing_scope_state() -> None:
    settings = reload_settings()
    token = await issue_dev_token(settings=settings)

    seen: dict[str, Any] = {}

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        seen["state"] = scope["state"]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    middleware = oauth_dependency(settings)(inner)
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", f"Bearer {token}".encode("ascii"))],
        "state": {"existing": "value"},
    }
    await _drain_asgi(middleware, scope)
    assert seen["state"]["existing"] == "value"
    assert isinstance(seen["state"]["oauth_claims"], TokenClaims)


@pytest.mark.asyncio
async def test_oauth_dependency_passes_non_http_scope_through() -> None:
    settings = reload_settings()
    captured: dict[str, Any] = {}

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        captured["scope"] = scope

    middleware = oauth_dependency(settings)(inner)
    lifespan_scope: dict[str, Any] = {"type": "lifespan"}

    async def receive() -> dict[str, Any]:
        return {"type": "lifespan.startup"}

    async def send(_: dict[str, Any]) -> None:
        return None

    await middleware(lifespan_scope, receive, send)
    assert captured["scope"]["type"] == "lifespan"


# ---------------------------------------------------------------------------
# CLI: ``python -m mcp_financial_data.auth.oauth dev-token``
# ---------------------------------------------------------------------------


def test_cli_dev_token_prints_a_jwt(capsys: pytest.CaptureFixture[str]) -> None:
    reload_settings()
    code = oauth_mod._cli_main(["dev-token", "--subject", "carol"])
    assert code == 0
    out = capsys.readouterr().out.strip()
    assert out.count(".") == 2
