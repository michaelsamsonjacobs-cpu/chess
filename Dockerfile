FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install Stockfish chess engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

ENV STOCKFISH_PATH=/usr/games/stockfish

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
