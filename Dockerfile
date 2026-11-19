# syntax=docker/dockerfile:1

# ---------- 1. Frontend bauen ----------
# Debian statt Alpine: Rollups nativer Parser scheitert an musls kleinem Thread-Stack
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Python-Abhängigkeiten mit uv ----------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS backend
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---------- 3. Laufzeit ----------
FROM python:3.13-slim-bookworm
# git + ssh für den Git-Spiegel der Configs
RUN apt-get update     && apt-get install -y --no-install-recommends git openssh-client     && rm -rf /var/lib/apt/lists/*
RUN groupadd --system tesseract && useradd --system --gid tesseract --home /app tesseract
WORKDIR /app
COPY --from=backend --chown=tesseract:tesseract /app /app
COPY --from=frontend --chown=tesseract:tesseract /app/frontend/dist /app/static
RUN mkdir -p /data && chown tesseract:tesseract /data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_HOST=0.0.0.0 \
    TESSERACT_PORT=8000 \
    TESSERACT_DATA_DIR=/data \
    TESSERACT_STATIC_DIR=/app/static

USER tesseract
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status == 200 else 1)"
CMD ["tesseract"]
