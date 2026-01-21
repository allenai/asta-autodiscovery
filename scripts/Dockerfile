FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY packages/ packages/
COPY scripts/ scripts/

# Install dependencies
RUN uv sync --no-dev

# Default command runs the cleanup script
CMD ["uv", "run", "python", "scripts/cleanup_old_datasets.py"]
