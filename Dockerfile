# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Additional dependencies
    libatspi2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files and README (required by hatchling build)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (including agents extras for LLM support)
RUN uv sync --frozen --no-dev --extra agents

# Install Playwright browsers
RUN uv run playwright install chromium

# Copy application code
COPY src/ src/
COPY data/migrations/ data/migrations/

# Create data directories
RUN mkdir -p data/db data/cache data/documents output logs

# Set default environment variables
ENV PSX_DATA_DIR=/app/data \
    PSX_DB_PATH=/app/data/db/psx.db \
    PSX_CACHE_DIR=/app/data/cache

# Default command
ENTRYPOINT ["uv", "run", "psx"]
CMD ["--help"]
