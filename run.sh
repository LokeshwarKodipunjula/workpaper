#!/usr/bin/env bash
# One-shot setup and run on macOS/Linux (needs Python 3.11+ and Node 20+ installed).
set -e
cd "$(dirname "$0")"
echo "[1/3] Installing backend dependencies..."
python3 -m pip install -r backend/requirements.txt
echo "[2/3] Building the UI..."
(cd frontend && npm install && npm run build)
echo "[3/3] Starting the server at http://localhost:8000  (Ctrl+C to stop)"
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
