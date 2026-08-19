#!/bin/bash
set -e

echo "========================================================"
echo " Starting RepoMind AI Monolithic Production Container  "
echo "========================================================"

# 1. Initialize Database Tables if needed
echo "[1/3] Checking and initializing database schema..."
cd /app/backend
python -c "
import os
try:
    from app.db.database import Base, engine
    Base.metadata.create_all(bind=engine)
    print('✅ Database schema verified.')
except Exception as e:
    print(f'⚠️ Notice during schema check: {e}')
" || true

# 2. Start FastAPI Backend in the background
echo "[2/3] Starting FastAPI backend on 127.0.0.1:${BACKEND_INTERNAL_PORT:-8000}..."
cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port "${BACKEND_INTERNAL_PORT:-8000}" &
BACKEND_PID=$!

# Wait for FastAPI to be ready
echo "Waiting for FastAPI to respond..."
for i in $(seq 1 30); do
    if curl -s "http://127.0.0.1:${BACKEND_INTERNAL_PORT:-8000}/health" >/dev/null 2>&1; then
        echo "✅ FastAPI is live and ready."
        break
    fi
    sleep 0.5
done

# 3. Start Next.js Frontend in the foreground on the public PORT
echo "[3/3] Starting Next.js frontend on 0.0.0.0:${PORT:-3000}..."
cd /app/frontend
HOSTNAME="0.0.0.0" PORT="${PORT:-3000}" node server.js &
FRONTEND_PID=$!

# Graceful shutdown handler
trap "kill -TERM $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" SIGINT SIGTERM

# Wait for either process to exit
wait -n $BACKEND_PID $FRONTEND_PID
