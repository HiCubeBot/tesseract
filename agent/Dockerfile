# syntax=docker/dockerfile:1
# Tesseract-Agent: läuft neben Caddy auf jedem weiteren Node (Build-Kontext: agent/)

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
COPY . ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.13-slim-bookworm
RUN groupadd --system agent && useradd --system --gid agent --home /app agent
WORKDIR /app
COPY --from=build --chown=agent:agent /app /app
RUN mkdir -p /data && chown agent:agent /data

ENV PATH="/app/.venv/bin:$PATH" \
    TESSERACT_AGENT_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

USER agent
VOLUME ["/data"]
# Tritt beim ersten Start mit TESSERACT_AGENT_JOIN_TOKEN bei und bleibt dann verbunden
CMD ["tesseract-agent", "run"]
