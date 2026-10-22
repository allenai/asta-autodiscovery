# The HTML report every run writes is the web UI's run view, built from ui/ into
# package data (see ui/vite.report.config.ts and autodiscovery/report.py).
FROM node:24-slim AS report-viewer

WORKDIR /repo/ui

# Same toolchain as ui/Dockerfile: git for the @stdlib dependencies that resolve
# via git, and python3/make/g++ for node-gyp during yarn install.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

COPY ui/package.json ui/yarn.lock ./
RUN yarn install --frozen-lockfile

COPY ui/ ./
# Writes /repo/packages/autodiscovery/src/autodiscovery/report_viewer.
RUN yarn build:report

# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory at repo root
WORKDIR /app

# Install system dependencies (curl fetches the uv installer below).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv and set PATH
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"

# Copy workspace files needed for uv sync
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY --from=report-viewer /repo/packages/autodiscovery/src/autodiscovery/report_viewer \
    ./packages/autodiscovery/src/autodiscovery/report_viewer

# Install Python dependencies (all public PyPI packages)
RUN /root/.local/bin/uv sync --frozen --no-dev --package asta-autodiscovery

# Set environment variables
ENV PYTHONUNBUFFERED=1

# The run's data is mounted at /mnt/data by whichever job backend launched the
# container (a GCS volume on Cloud Run, a host bind mount under the docker
# backend); the job itself just reads and writes files there.
# --no-sync: a plain `uv run` targets the workspace root and its dev group, so it
# would re-sync (download ruff, pyright, ...) on every container start.
ENTRYPOINT ["/root/.local/bin/uv", "run", "--no-sync", "python", "-m", "autodiscovery.run"]
