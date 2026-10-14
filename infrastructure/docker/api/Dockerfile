FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
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

# Install API app
COPY apps/api/ ./apps/api/
RUN pip install -e apps/api/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
