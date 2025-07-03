FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Verify installations
RUN python -c "import pytz; print(f'pytz version: {pytz.__version__}')" && \
    python -c "from telegram_bot import TradingBot; print('Bot imports verified')"

EXPOSE 8000

CMD ["python", "bot_runner.py", "railway"]