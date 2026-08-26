#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p /tmp/traininghub

# Stop stale development processes from an earlier Codespace session.
pkill -f "gunicorn --bind 0.0.0.0:5000" 2>/dev/null || true
pkill -f "vite.*0.0.0.0" 2>/dev/null || true

# Make sure frontend dependencies exist after a rebuild or branch change.
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  (cd "$ROOT/frontend" && npm install)
fi

nohup gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 60 app:app \
  > /tmp/traininghub/api.log 2>&1 &
echo $! > /tmp/traininghub/api.pid

(
  cd "$ROOT/frontend"
  nohup npm run dev -- --host 0.0.0.0 \
    > /tmp/traininghub/vite.log 2>&1 &
  echo $! > /tmp/traininghub/vite.pid
)

sleep 2

echo "TrainingHub development services started"
echo "  Python API: http://127.0.0.1:5000"
echo "  React UI:   http://127.0.0.1:5173"
echo "  API log:    /tmp/traininghub/api.log"
echo "  Vite log:   /tmp/traininghub/vite.log"
