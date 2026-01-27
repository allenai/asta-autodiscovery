FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY packages/ packages/
COPY scripts/ scripts/

# Install dependencies (including workspace packages)
RUN uv sync --all-packages --no-dev

# No default CMD - specify the maintenance script when running the container
# Example: docker run <image> uv run python scripts/cleanup_old_datasets.py --dry-run
