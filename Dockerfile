FROM python:3.14-slim AS base

WORKDIR /app

# System dependencies for scylla-driver, docling, and general build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev deps, frozen lockfile)
RUN uv sync --frozen --no-install-project

# Copy application code
COPY app/ app/
COPY main.py .

# Default host to 0.0.0.0 so the container is reachable
ENV HOST=0.0.0.0
ENV PORT=8065
# SERVICE_MODE: "api" (default) or "worker"
ENV SERVICE_MODE=api

EXPOSE 8065

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
