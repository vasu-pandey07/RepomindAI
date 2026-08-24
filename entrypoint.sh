#!/bin/bash
set -e

echo "========================================================"
echo " Starting RepoMind AI Monolithic Production Container  "
echo "========================================================"

BACKEND_PORT="${BACKEND_INTERNAL_PORT:-8000}"

# 1. Initialize Database Tables if needed
echo "[1/3] Checking and initializing database schema..."
cd /app/backend
python -c "
import os
try:
    from app.db.database import Base, engine
    import app.db.models
    Base.metadata.create_all(bind=engine)
    print('✅ Database schema verified.')
except Exception as e:
    print(f'⚠️ Notice during schema check: {e}')
" || true

# 2. Start FastAPI backend under a supervisor that AUTO-RESTARTS it if it
#    crashes or is OOM-killed. This is critical on Render's free tier (512MB
#    RAM): heavy embedding/indexing work can push memory over the limit and
#    the kernel kills uvicorn. Without a supervisor the backend stays dead and
#    every proxied request returns 502 "Backend service unavailable" until a
#    manual redeploy. The loop below brings it back within a few seconds.
echo "[2/3] Starting supervised FastAPI backend on 127.0.0.1:${BACKEND_PORT}..."
cd /app/backend
(
  # Do not let a single failed launch kill the supervisor subshell.
  set +e
  RESTARTS=0
  while true; do
    echo "[supervisor] Launching uvicorn backend (restart #${RESTARTS})..."
    python -m uvicorn app.main:app --host 127.0.0.1 --port "${BACKEND_PORT}"
    EXIT_CODE=$?
    RESTARTS=$((RESTARTS + 1))
    echo "[supervisor] ⚠️ Backend exited (code ${EXIT_CODE}). Restarting in 3s..."
    sleep 3
  done
) &
SUPERVISOR_PID=$!

# Wait for FastAPI to be responsive (model pre-warm can take a while on first boot)
echo "Waiting for FastAPI to respond..."
for i in $(seq 1 120); do
    if curl -s "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
        echo "✅ FastAPI is live and ready."
        break
    fi
    sleep 0.5
done

# 3. Start Next.js Frontend in the foreground on the public PORT
echo "[3/3] Starting Next.js frontend on 0.0.0.0:${PORT:-3000}..."
cd /app/frontend
export HOSTNAME="0.0.0.0"
export PORT="${PORT:-3000}"

# Graceful shutdown handler — stop the backend supervisor when Next.js exits
trap "kill -TERM ${SUPERVISOR_PID} 2>/dev/null || true" SIGINT SIGTERM EXIT

# Run Next.js server in the foreground
exec node server.js
