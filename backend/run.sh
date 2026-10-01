#!/usr/bin/env bash
# Start the backend. Creates the virtualenv and installs dependencies on first run.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment"
  "$PYTHON" -m venv .venv
  ./.venv/bin/python3 -m pip install --upgrade pip
  echo "==> Installing dependencies (this takes a few minutes the first time)"
  ./.venv/bin/python3 -m pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
  echo "!! backend/.env not found. Copying .env.example -- add your ANTHROPIC_API_KEY to it."
  cp .env.example .env
fi

echo "==> Starting API on http://localhost:8000  (docs at /docs)"
exec ./.venv/bin/python3 -m uvicorn app.main:app --reload --port 8000
