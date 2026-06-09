# Architecture — mcp-financial-data

This is the deeper architectural overview. The README has the elevator pitch
and the Mermaid diagram; this file expands the boxes.

## 1. Component model

```mermaid
flowchart TB
    subgraph clients [MCP Clients]
        ClaudeDesktop[Claude Desktop]
        Cursor[Cursor]
        Goose[Block Goose]
    end

    subgraph idp [External IdP]
        Auth0[Auth0 / Authentik / Keycloak]
        JWKS[JWKS endpoint]
    end

    subgraph server [mcp-financial-data process]
        FastMCP[FastMCP HTTP server]
        OAuthRS[OAuth 2.1 resource server]
        EdgarClient[EDGAR async client]
        FredClient[FRED async client]
        PolygonClient[Polygon async client]
        Extractor["10-K extractor (Claude Sonnet 4.6)"]
        EvalHarness[Eval harness (Claude Opus 4.7 judge)]
        Apps[MCP Apps UI registry]
    end

    subgraph external [External services]
        SEC[SEC EDGAR]
        FRED[FRED API]
        Polygon[Polygon.io]
        Anthropic["Anthropic Messages API"]
    end

    Cache[(SQLite response cache 24h TTL)]

    clients -->|OAuth 2.1 + PKCE bearer| FastMCP
    Auth0 -->|JWT mint| clients
    Auth0 --> JWKS
    FastMCP --> OAuthRS
    OAuthRS -->|JWKS rotate| JWKS

    FastMCP --> EdgarClient --> SEC
    FastMCP --> FredClient --> FRED
    FastMCP --> PolygonClient --> Polygon
    FastMCP --> Extractor -->|"Citations API"| Anthropic
    FastMCP --> EvalHarness -->|"LLM judge"| Anthropic
    FastMCP --> Apps

    EdgarClient --> Cache
    FredClient --> Cache
    PolygonClient --> Cache
    Extractor --> Cache
```

## 2. Request lifecycle

1. MCP client sends `Authorization: Bearer <jwt>` over streamable HTTP.
2. `auth/oauth.py::validate_bearer_token` validates against the cached JWKS:
   signature, issuer, audience, exp, required scopes.
3. Tool dispatcher in `server.py` routes to the matching async tool.
4. Tool fetches via the cache; on miss, fetches from origin, applies the
   24-hour TTL, returns.
5. Structlog emits `tool.start` and `tool.end` with token + cost counters.
6. The extractor adds Anthropic Citations API result mapping into
   `CitedClaim` objects. Uncited spans are demoted to `notes`.
7. Response is rendered as the matching pydantic model and serialized by
   FastMCP. If the tool's MCP App registration fires, an inline UI envelope
   ships alongside the data response.

## 3. Trust boundaries

| Boundary | Enforced by | What's NOT allowed across it |
| --- | --- | --- |
| Client → Server | OAuth 2.1 JWT validation | Unsigned / wrong-aud / expired tokens. |
| Server → External APIs | HTTPS + per-API auth header | Cross-API leakage of credentials. |
| Server → Anthropic | API key + spend cap counter | Free-form tool-output to Anthropic without review. |
| Cache → Origin | 24h TTL, no PII in keys | Stale-while-revalidate (we revalidate). |

## 4. Reproducibility

Per master rule §8:

- Docker base image pinned by `sha256` digest.
- All Python deps pinned in `uv.lock`, committed.
- `PYTHONHASHSEED=0` in the Dockerfile and CI.
- Eval results record git SHA, model id, judge model id, harness version,
  host info, wall-clock, token counts, $ cost.

## 5. Failure modes & recovery

| Failure | Detection | Recovery |
| --- | --- | --- |
| EDGAR 429 | `tenacity` backoff (3 retries, ≤ 8s) | Retry; on persistent fail surface to client. |
| Anthropic 429 / 5xx | Counter + `tenacity` retry (≤ 3) | Retry once; otherwise return cached result if any, else error. |
| JWT signature invalid | `validate_bearer_token` raises | Return RFC 6750 `WWW-Authenticate` with `error="invalid_token"`. |
| Spend cap hit | Counter check before each Anthropic call | Raise `ExtractorSpendCapError`; never call the model. |
| Eval fixture missing (offline) | `KeyError` in harness | Mark case `success=false`; CI exits non-zero. |

## 6. Out-of-scope (deferred to follow-on projects)

- Multi-tenant rate limits per `sub` claim (P7 fsi-compliance-agent).
- WORM audit trail of every tool call (P7).
- Solidity-side compliance hooks (P8 defi-compliance-agent).
- Multi-cloud IaC (P9 terraform-ai-deploy).
