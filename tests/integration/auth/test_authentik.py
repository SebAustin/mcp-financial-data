"""Authentik OAuth 2.1 round-trip integration test.

Skipped by default. Run with ``make test-int`` after bringing up a local
Authentik stack via Docker compose. Authentik is OSS and matches ADR 0004's
"external IdP" stance without committing the repo to Auth0 / Okta.

## How to run locally

1. Bring up Authentik per the official compose recipe
   (https://goauthentik.io/docs/installation/docker-compose).
2. Create a Provider of type "OAuth2/OpenID Provider" with:
   - Client type: ``Confidential``
   - Audience: ``mcp-financial-data``
   - Signing key: an RSA key.
   - Scopes: ``mcp:read`` and ``mcp:tools``.
3. Create an Application bound to the provider, and a test User.
4. Export env vars used by this test:
   - ``AUTHENTIK_TOKEN_URL``  (e.g. ``https://idp.local.test/application/o/token/``)
   - ``AUTHENTIK_CLIENT_ID``
   - ``AUTHENTIK_CLIENT_SECRET``
   - ``AUTHENTIK_USERNAME`` + ``AUTHENTIK_PASSWORD``
   - ``MCP_OAUTH_ISSUER``    matching the provider's issuer URL.
   - ``MCP_OAUTH_JWKS_URL``  matching ``${issuer}/jwks/``.
   - ``MCP_OAUTH_AUDIENCE``  = ``mcp-financial-data``.
   - ``MCP_OAUTH_REQUIRED_SCOPES`` = ``mcp:read mcp:tools``.
5. Run ``make test-int``.
"""

from __future__ import annotations

import os

import httpx
import pytest

from mcp_financial_data.auth.oauth import validate_bearer_token
from mcp_financial_data.settings import reload_settings

pytestmark = pytest.mark.integration


_REQUIRED_ENV = (
    "AUTHENTIK_TOKEN_URL",
    "AUTHENTIK_CLIENT_ID",
    "AUTHENTIK_CLIENT_SECRET",
    "AUTHENTIK_USERNAME",
    "AUTHENTIK_PASSWORD",
)


def _missing_env() -> tuple[str, ...]:
    return tuple(name for name in _REQUIRED_ENV if not os.environ.get(name))


@pytest.mark.asyncio
async def test_authentik_password_grant_roundtrip() -> None:
    """Mint a real RS256 token via Authentik and validate it with our resource server."""
    missing = _missing_env()
    if missing:
        pytest.skip(f"missing env: {', '.join(missing)} (see module docstring)")

    token_url = os.environ["AUTHENTIK_TOKEN_URL"]
    payload = {
        "grant_type": "password",
        "client_id": os.environ["AUTHENTIK_CLIENT_ID"],
        "client_secret": os.environ["AUTHENTIK_CLIENT_SECRET"],
        "username": os.environ["AUTHENTIK_USERNAME"],
        "password": os.environ["AUTHENTIK_PASSWORD"],
        "scope": "mcp:read mcp:tools",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(token_url, data=payload)
        resp.raise_for_status()
        access_token = resp.json()["access_token"]

    settings = reload_settings()
    claims = await validate_bearer_token(access_token, settings)
    assert claims.aud == settings.mcp_oauth_audience
    assert "mcp:read" in claims.scopes
    assert "mcp:tools" in claims.scopes
