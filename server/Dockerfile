FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install Stockfish
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

# Set Stockfish path for the application
ENV STOCKFISH_PATH=/usr/games/stockfish

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy trained ML model
COPY ../models/xgb_cheat_model.joblib /app/models/xgb_cheat_model.joblib

ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
