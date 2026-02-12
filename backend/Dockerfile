# Multi-stage build for FastAPI + Celery application
# Uses uv for fast dependency installation

# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen lockfile, no dev dependencies)
RUN uv sync --frozen --no-dev

# Stage 2: Runtime image
FROM python:3.13-slim

# Install curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose FastAPI port
EXPOSE 8000

# Default command (can be overridden for worker containers)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
