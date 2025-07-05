FROM python:3.11-slim

# Accept Railway environment variables as build arguments
ARG RAILWAY_ENVIRONMENT
ARG RAILWAY_SERVICE_NAME
ARG RAILWAY_PROJECT_ID
ARG PORT
ARG RAILWAY_PUBLIC_DOMAIN
ARG RAILWAY_PRIVATE_DOMAIN

# Make them available as environment variables during build
ENV RAILWAY_ENVIRONMENT=${RAILWAY_ENVIRONMENT}
ENV RAILWAY_SERVICE_NAME=${RAILWAY_SERVICE_NAME}
ENV RAILWAY_PROJECT_ID=${RAILWAY_PROJECT_ID}
ENV PORT=${PORT}
ENV RAILWAY_PUBLIC_DOMAIN=${RAILWAY_PUBLIC_DOMAIN}
ENV RAILWAY_PRIVATE_DOMAIN=${RAILWAY_PRIVATE_DOMAIN}

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Verify critical imports only (avoid importing main bot to prevent config errors)
RUN python -c "import pytz; print(f'pytz version: {pytz.__version__}')" && \
    python -c "import telegram; print('python-telegram-bot imported successfully')" && \
    python -c "import asyncpg; print('asyncpg imported successfully')" && \
    python -c "import sqlite3; print('sqlite3 imported successfully')" && \
    python -c "from database import initialize_db; print('Database module imported successfully')"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Command to run the application
CMD ["python", "bot_runner.py", "railway"]