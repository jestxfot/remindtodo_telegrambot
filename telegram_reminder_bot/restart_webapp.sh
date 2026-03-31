#!/bin/bash

# Quick restart of webapp only (without rebuild).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$SCRIPT_DIR"
WEBAPP_DIR="$BOT_DIR/webapp"
VENV_PY="$BOT_DIR/venv/bin/python"

service_exists() {
    systemctl list-unit-files "$1.service" --no-legend 2>/dev/null | grep -q "^$1\.service"
}

WEBAPP_SERVICE="telegram-webapp"
if ! service_exists "$WEBAPP_SERVICE"; then
    WEBAPP_SERVICE="webapp"
fi

echo "Quick restart webapp..."
echo "Bot dir:     $BOT_DIR"
echo "Web service: $WEBAPP_SERVICE"

if [ ! -x "$VENV_PY" ]; then
    echo "ERROR: venv python not found at $VENV_PY"
    exit 1
fi

sudo systemctl stop "$WEBAPP_SERVICE" 2>/dev/null || true
pkill -f "$WEBAPP_DIR/server.py" 2>/dev/null || true
sudo fuser -k 3000/tcp 2>/dev/null || true
sleep 2

find "$BOT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

if service_exists "$WEBAPP_SERVICE"; then
    sudo systemctl start "$WEBAPP_SERVICE"
else
    nohup "$VENV_PY" "$WEBAPP_DIR/server.py" > "$BOT_DIR/webapp.log" 2>&1 &
fi

sleep 3

echo
if sudo lsof -i :3000 >/dev/null 2>&1; then
    echo "OK: WebApp is listening on port 3000"
    sudo lsof -i :3000 -n -P
else
    echo "FAIL: WebApp did not start correctly"
    if service_exists "$WEBAPP_SERVICE"; then
        sudo journalctl -u "$WEBAPP_SERVICE" -n 30 --no-pager
    else
        tail -n 30 "$BOT_DIR/webapp.log" 2>/dev/null || true
    fi
    exit 1
fi
