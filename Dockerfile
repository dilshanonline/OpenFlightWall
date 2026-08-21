# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install dependencies first (separate layer, cached as long as
# pyproject.toml/uv.lock don't change) before copying app source.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra server

COPY app.py ./
COPY templates/ ./templates/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra server


FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="OpenFlightWall" \
      org.opencontainers.image.description="Zero-cost flight-tracking dashboard in your browser" \
      org.opencontainers.image.source="https://github.com/dilshanonline/OpenFlightWall" \
      org.opencontainers.image.licenses="Apache-2.0"

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app.py ./
COPY --chown=app:app templates/ ./templates/

ENV PATH="/app/.venv/bin:${PATH}" \
    PORT=5000 \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/config', timeout=3)" || exit 1

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 30 app:app"]
