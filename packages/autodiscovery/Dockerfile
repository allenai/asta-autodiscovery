# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory at repo root
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv and set PATH
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"

# Copy workspace files needed for uv sync
COPY pyproject.toml uv.lock ./
COPY packages ./packages

# Install Python dependencies (all public PyPI packages)
RUN /root/.local/bin/uv sync --frozen --package autodiscovery

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default entry point - can be overridden
ENTRYPOINT ["/root/.local/bin/uv", "run", "python", "-m", "autodiscovery.run"]
