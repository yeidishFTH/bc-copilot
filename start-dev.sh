#!/usr/bin/env bash

set -e

PROJECT_DIR="$HOME/bitcoinchange/bc-copilot"

cleanup() {
  echo
  echo "Stopping Bitcoin Change Copilot..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

cd "$PROJECT_DIR/backend"
source .venv/bin/activate
fastapi dev app/main.py --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo
echo "======================================================"
echo "Bitcoin Change Copilot is starting"
echo
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "======================================================"
echo
echo "Press Ctrl+C to stop both servers."

wait
