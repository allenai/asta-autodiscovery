FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files (including the lockfile so the build is reproducible)
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY scripts/ scripts/

# Install dependencies (including workspace packages) exactly as locked.
# Without --frozen, uv re-resolves from PyPI at build time and can pick up a
# release that has no wheel yet for this platform.
RUN uv sync --all-packages --no-dev --frozen

# No default CMD - specify the maintenance script when running the container
# Example: docker run <image> uv run python scripts/cleanup_old_datasets.py --dry-run
