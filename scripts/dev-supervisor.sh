#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR=/tmp/traininghub
mkdir -p "$LOG_DIR"

start_api() {
  if ! pgrep -f "gunicorn --bind 0.0.0.0:5000" >/dev/null 2>&1; then
    cd "$ROOT"
    nohup gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 60 app:app \
      >> "$LOG_DIR/api.log" 2>&1 &
    echo $! > "$LOG_DIR/api.pid"
  fi
}

start_vite() {
  if ! pgrep -f "vite.*0.0.0.0" >/dev/null 2>&1; then
    cd "$ROOT/frontend"
    if [ ! -d node_modules ]; then
      npm install >> "$LOG_DIR/vite.log" 2>&1
    fi
    nohup npm run dev -- --host 0.0.0.0 \
      >> "$LOG_DIR/vite.log" 2>&1 &
    echo $! > "$LOG_DIR/vite.pid"
  fi
}

while true; do
  start_api
  start_vite
  sleep 10
done
