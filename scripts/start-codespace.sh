#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p /tmp/traininghub

# Stop stale processes/supervisors from a previous session.
pkill -f "scripts/dev-supervisor.sh" 2>/dev/null || true
pkill -f "gunicorn --bind 0.0.0.0:5000" 2>/dev/null || true
pkill -f "vite.*0.0.0.0" 2>/dev/null || true

# Ensure frontend dependencies are present.
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  (cd "$ROOT/frontend" && npm install)
fi

# Start a lightweight supervisor that keeps both services alive.
nohup bash "$ROOT/scripts/dev-supervisor.sh" \
  > /tmp/traininghub/supervisor.log 2>&1 &
echo $! > /tmp/traininghub/supervisor.pid

sleep 3

echo "TrainingHub development supervisor started"
echo "  Python API: http://127.0.0.1:5000"
echo "  React UI:   http://127.0.0.1:5173"
echo "  Supervisor: /tmp/traininghub/supervisor.log"
echo "  API log:    /tmp/traininghub/api.log"
echo "  Vite log:   /tmp/traininghub/vite.log"
