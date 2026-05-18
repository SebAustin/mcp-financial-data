"""Tests for ``mcp_financial_data.auth.oauth`` stubs."""

from __future__ import annotations

import pytest

from mcp_financial_data.auth.oauth import (
    InsufficientScopeError,
    InvalidTokenError,
    OAuthError,
    TokenClaims,
    build_www_authenticate,
    issue_dev_token,
    validate_bearer_token,
)


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


@pytest.mark.asyncio
async def test_validate_bearer_token_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/01_oauth_resource_server\.md"):
        await validate_bearer_token("not-a-real-token")


@pytest.mark.asyncio
async def test_issue_dev_token_is_stub() -> None:
    with pytest.raises(NotImplementedError, match=r"prompts/01_oauth_resource_server\.md"):
        await issue_dev_token()
