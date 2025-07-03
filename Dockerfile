FROM python:3.11-slim

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