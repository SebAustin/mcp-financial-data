# syntax=docker/dockerfile:1.7
# Pinned by sha256 digest per master .cursorrules §8 (Reproducibility).
# Re-pin weekly: `docker buildx imagetools inspect python:3.12-slim`.
FROM python:3.12-slim@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

# uv from official distroless image (digest-pinned upstream).
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

WORKDIR /app

# Layer 1: dependency manifests only — maximizes cache reuse.
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Layer 2: source.
COPY src ./src
COPY evals ./evals

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Non-root runtime user.
RUN useradd --system --no-create-home --uid 10001 mcp
USER mcp

EXPOSE 8765
ENV PATH="/app/.venv/bin:${PATH}"

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx, os; httpx.get(f'http://127.0.0.1:{os.environ.get(\"MCP_PORT\",\"8765\")}/healthz', timeout=2).raise_for_status()" || exit 1

CMD ["python", "-m", "mcp_financial_data.server"]
