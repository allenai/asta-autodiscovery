# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory at repo root
WORKDIR /app

# Install system dependencies. gcsfuse + fuse let the container self-mount the
# GCS bucket at /mnt/gcs when run under the local Docker job backend (on Cloud
# Run the platform provides that mount instead). Images are built for
# linux/amd64 (see Makefile), so the amd64 gcsfuse release is used.
ARG GCSFUSE_VERSION=2.4.0
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    fuse3 \
    && curl -fsSL -o /tmp/gcsfuse.deb \
        "https://github.com/GoogleCloudPlatform/gcsfuse/releases/download/v${GCSFUSE_VERSION}/gcsfuse_${GCSFUSE_VERSION}_amd64.deb" \
    && apt-get install -y /tmp/gcsfuse.deb \
    && rm -f /tmp/gcsfuse.deb \
    && rm -rf /var/lib/apt/lists/*

# Install uv and set PATH
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"

# Copy workspace files needed for uv sync
COPY pyproject.toml uv.lock ./
COPY packages ./packages

# Install Python dependencies (all public PyPI packages)
RUN /root/.local/bin/uv sync --frozen --package asta-autodiscovery

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Entrypoint wrapper: optionally gcsfuse-mounts /mnt/gcs (when GCSFUSE_BUCKET is
# set), then runs the AD job with the provided args.
COPY packages/autodiscovery/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
