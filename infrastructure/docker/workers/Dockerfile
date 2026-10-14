FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy root requirements
COPY pyproject.toml ./
COPY packages/ ./packages/

# Install Python packages
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

# Install shared packages
RUN for pkg in packages/*/; do \
        if [ -f "$pkg/pyproject.toml" ]; then \
            pip install -e "$pkg"; \
        fi; \
    done

# Install workers app
COPY apps/workers/ ./apps/workers/
RUN pip install -e apps/workers/

# Run the worker
CMD ["celery", "-A", "apps.workers.main", "worker", "--loglevel=info"]
