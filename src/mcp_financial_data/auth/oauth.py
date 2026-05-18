"""OAuth 2.1 resource-server primitives for the MCP server.

Per MCP spec 2025-11-25 §authorization, an MCP server that requires OAuth
acts as a *resource server*: it validates JWTs minted by an external IdP
(Auth0, Authentik, Keycloak, ...). This module is intentionally minimal —
the real implementation lands in ``prompts/01_oauth_resource_server.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from mcp_financial_data.settings import Settings, get_settings

WWW_AUTHENTICATE_HEADER: Final[str] = "WWW-Authenticate"


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


@dataclass(frozen=True, slots=True)
class JwksCache:
    """In-memory cache of JWKS public keys with a TTL.

    Real implementation in ``prompts/01_oauth_resource_server.md``.
    """

    ttl_seconds: int = 3600


async def validate_bearer_token(token: str, settings: Settings | None = None) -> TokenClaims:
    """Validate a Bearer JWT against the configured JWKS and return its claims.

    Raises:
        InvalidTokenError: token is missing, malformed, expired, or signed by
            a key not in the JWKS, or audience/issuer mismatch.
        InsufficientScopeError: token is structurally valid but missing one
            or more required scopes from ``settings.required_scopes_list``.

    See ``prompts/01_oauth_resource_server.md``.
    """
    _ = settings or get_settings()
    _ = token
    raise NotImplementedError("see prompts/01_oauth_resource_server.md")


async def issue_dev_token(subject: str = "dev-user") -> str:
    """Mint a dev-only HS256 JWT for local CLI testing. NEVER used in prod.

    Output is a JWT with the configured audience/issuer and the full set of
    required scopes, expiring in 60 minutes. Implementation lives in
    ``prompts/01_oauth_resource_server.md``.
    """
    _ = subject
    raise NotImplementedError("see prompts/01_oauth_resource_server.md")


def build_www_authenticate(error: str, error_description: str) -> str:
    """Build an RFC 6750 ``WWW-Authenticate`` header value.

    Example::

        build_www_authenticate("invalid_token", "Token expired") ->
            'Bearer error="invalid_token", error_description="Token expired"'
    """
    if '"' in error or '"' in error_description:
        raise ValueError("error and error_description must not contain double quotes")
    return f'Bearer error="{error}", error_description="{error_description}"'
