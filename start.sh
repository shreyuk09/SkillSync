#!/usr/bin/env bash
# Start the backend and the frontend together.
#
#   ./start.sh
#
# Backend  -> http://localhost:8000  (API docs at /docs)
# Frontend -> http://localhost:5173
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
PYTHON="${PYTHON:-python3}"

# ---------------------------------------------------------------- checks ----
if ! command -v "$PYTHON" >/dev/null; then
  echo "!! $PYTHON not found. Install Python 3.10 or newer." >&2
  exit 1
fi

if ! command -v node >/dev/null; then
  echo "!! node not found. Install Node 18 or newer." >&2
  exit 1
fi

# --------------------------------------------------------------- backend ----
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
  echo "==> Creating the Python virtual environment"
  "$PYTHON" -m venv .venv
  ./.venv/bin/python3 -m pip install --quiet --upgrade pip
  echo "==> Installing backend dependencies (a few minutes the first time)"
  ./.venv/bin/python3 -m pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "!! Created backend/.env from the example."
  echo "!! Add your ANTHROPIC_API_KEY to it, then restart."
fi

echo "==> Starting the API on http://localhost:8000"
./.venv/bin/python3 -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# -------------------------------------------------------------- frontend ----
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
  echo "==> Installing frontend dependencies"
  npm install
fi

echo "==> Starting the UI on http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

cleanup() {
  echo
  echo "==> Shutting down"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
