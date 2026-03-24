FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files needed for uv sync
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY api/ api/

# Install Python dependencies using the lock file
RUN uv sync --frozen --package api --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

WORKDIR /app/api
ENTRYPOINT ["/app/api/dev.sh"]
