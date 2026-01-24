# Dockerfile for devtools (replay job)
FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY packages ./packages

# Install dependencies (including workspace packages)
RUN uv sync --package devtools --no-dev

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default entry point - replay module
# Override with args: --source=gs://... --target=gs://... --time-scale=0.1
ENTRYPOINT ["uv", "run", "python", "-m", "devtools.replay"]
