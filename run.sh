#!/bin/bash
# InvestRight — local development startup script
# For production use docker-compose.yml instead.

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$ROOT_DIR/.venv"

echo "=== InvestRight Startup ==="

# 1. Virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "[setup] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# 2. Install / update dependencies
echo "[setup] Installing dependencies..."
pip install -q -r "$BACKEND_DIR/requirements.txt"

# 3. Initialise database (idempotent — safe to run every time)
echo "[setup] Initialising database..."
cd "$BACKEND_DIR"
python db/init_db.py && echo "[setup] Database ready."

# 4. Start backend
echo "[backend] Starting Flask API on port 5001..."
python main.py &
BACKEND_PID=$!

# 5. Start scheduler (trading pipeline — runs every 15 min during market hours)
echo "[scheduler] Starting trading scheduler..."
python scheduler.py &
SCHEDULER_PID=$!

# 6. Start frontend static server
echo "[frontend] Serving SPA on http://localhost:8080"
cd "$FRONTEND_DIR"
python -m http.server 8080 &
FRONTEND_PID=$!

echo ""
echo "  Backend   → http://localhost:5001"
echo "  Scheduler → running (every 5 min during market hours)"
echo "  Frontend  → http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop all services."

# Cleanup on exit
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $SCHEDULER_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
