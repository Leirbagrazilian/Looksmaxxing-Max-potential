#!/usr/bin/env bash
# One-click start for macOS / Linux: creates a virtual environment on first run,
# installs dependencies, and opens Ascend in your browser.
# Add --phone to make it reachable from your phone on the same Wi-Fi.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  echo "First run: setting up (takes a few minutes)..."
  "$PY" -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt
fi
HOST=127.0.0.1
if [ "$1" = "--phone" ]; then
  HOST=0.0.0.0
  IP=$( (ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}') )
  echo "On your phone, open: http://${IP}:8000"
fi
( sleep 3; (open "http://127.0.0.1:8000" 2>/dev/null || xdg-open "http://127.0.0.1:8000" 2>/dev/null) ) &
exec .venv/bin/python -m looksmax.web --host "$HOST" --port 8000
