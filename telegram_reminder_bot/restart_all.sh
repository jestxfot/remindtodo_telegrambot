#!/bin/bash

# Full restart of bot + webapp on VPS.
# Uses systemd when services are installed, otherwise falls back to local runs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$SCRIPT_DIR"
WEBAPP_DIR="$BOT_DIR/webapp"
VENV_PY="$BOT_DIR/venv/bin/python"
ENV_FILE="$BOT_DIR/.env"

BOT_SERVICE_PRIMARY="telegram-reminder-bot"
WEBAPP_SERVICE_PRIMARY="telegram-webapp"
TUNNEL_SERVICE_PRIMARY="telegram-tunnel"

service_exists() {
    systemctl list-unit-files "$1.service" --no-legend 2>/dev/null | grep -q "^$1\.service"
}

service_enabled() {
    local service_name="$1"
    [ -n "$service_name" ] && systemctl is-enabled "$service_name" >/dev/null 2>&1
}

first_existing_service() {
    local candidate
    for candidate in "$@"; do
        if service_exists "$candidate"; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

stop_service_if_present() {
    local service_name="$1"
    if [ -n "$service_name" ]; then
        sudo systemctl stop "$service_name" 2>/dev/null || true
    fi
}

start_service_if_present() {
    local service_name="$1"
    if [ -n "$service_name" ]; then
        sudo systemctl start "$service_name"
    fi
}

restart_service_if_present() {
    local service_name="$1"
    if [ -n "$service_name" ]; then
        sudo systemctl restart "$service_name"
    fi
}

BOT_SERVICE="$(first_existing_service "$BOT_SERVICE_PRIMARY")" || BOT_SERVICE=""
WEBAPP_SERVICE="$(first_existing_service "$WEBAPP_SERVICE_PRIMARY" "webapp")" || WEBAPP_SERVICE=""
TUNNEL_SERVICE="$(first_existing_service "$TUNNEL_SERVICE_PRIMARY" "cloudflared-tunnel")" || TUNNEL_SERVICE=""

echo "=========================================="
echo "FULL RESTART (Bot + WebApp)"
echo "=========================================="
echo "Bot dir:      $BOT_DIR"
echo "WebApp dir:   $WEBAPP_DIR"
echo "Python:       ${VENV_PY:-missing}"
echo "Bot service:  ${BOT_SERVICE:-manual}"
echo "Web service:  ${WEBAPP_SERVICE:-manual}"
echo "Tunnel svc:   ${TUNNEL_SERVICE:-not-found}"
echo "=========================================="

if [ ! -x "$VENV_PY" ]; then
    echo "ERROR: venv python not found at $VENV_PY"
    exit 1
fi

if [ ! -d "$WEBAPP_DIR" ]; then
    echo "ERROR: webapp directory not found at $WEBAPP_DIR"
    exit 1
fi

echo
echo "Stopping services..."
stop_service_if_present "$TUNNEL_SERVICE"
stop_service_if_present "$WEBAPP_SERVICE"
stop_service_if_present "$BOT_SERVICE"
sleep 2

echo
echo "Cleaning leftover processes..."
pkill -f "$BOT_DIR/bot.py" 2>/dev/null || true
pkill -f "$WEBAPP_DIR/server.py" 2>/dev/null || true
sleep 2

echo
echo "Freeing port 3000..."
sudo fuser -k 3000/tcp 2>/dev/null || true
sleep 2

if sudo lsof -i :3000 >/dev/null 2>&1; then
    echo "ERROR: port 3000 is still busy"
    sudo lsof -i :3000 -n -P
    exit 1
fi

echo
echo "Clearing Python cache..."
find "$BOT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BOT_DIR" -name "*.pyc" -delete 2>/dev/null || true

echo
echo "Rebuilding webapp..."
cd "$WEBAPP_DIR"
npm run build
cd "$BOT_DIR"

echo
echo "Running import smoke checks..."
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

"$VENV_PY" - <<'PY'
import sys
from pathlib import Path

bot_dir = Path.cwd()
sys.path.insert(0, str(bot_dir))

import config  # noqa: F401
import handlers.auth  # noqa: F401
import storage.sqlite_storage  # noqa: F401
import webapp.server as server

print("BOT_AVAILABLE =", server.BOT_AVAILABLE)
if not server.BOT_AVAILABLE:
    raise SystemExit("webapp auth integration is unavailable")
PY

echo
echo "Starting services..."
if [ -n "$WEBAPP_SERVICE" ]; then
    start_service_if_present "$WEBAPP_SERVICE"
else
    nohup "$VENV_PY" "$WEBAPP_DIR/server.py" > "$BOT_DIR/webapp.log" 2>&1 &
fi

sleep 3

if service_enabled "$TUNNEL_SERVICE"; then
    start_service_if_present "$TUNNEL_SERVICE"
elif [ -n "$TUNNEL_SERVICE" ]; then
    echo "Tunnel service is installed but disabled, skipping start"
fi

if [ -n "$BOT_SERVICE" ]; then
    start_service_if_present "$BOT_SERVICE"
else
    nohup "$VENV_PY" "$BOT_DIR/bot.py" > "$BOT_DIR/bot.log" 2>&1 &
fi

sleep 5

echo
echo "=========================================="
echo "FINAL STATUS"
echo "=========================================="

echo
echo "Bot:"
if [ -n "$BOT_SERVICE" ]; then
    if systemctl is-active --quiet "$BOT_SERVICE"; then
        echo "  OK: service $BOT_SERVICE is active"
    else
        echo "  FAIL: service $BOT_SERVICE is not active"
        sudo systemctl status "$BOT_SERVICE" --no-pager | head -20
    fi
else
    RUNNING_BOT="$(pgrep -f "$BOT_DIR/bot.py" 2>/dev/null | head -1)"
    if [ -n "$RUNNING_BOT" ]; then
        echo "  OK: running manually (PID: $RUNNING_BOT)"
    else
        echo "  FAIL: bot process not found"
        tail -n 20 "$BOT_DIR/bot.log" 2>/dev/null || true
    fi
fi

echo
echo "WebApp:"
if [ -n "$WEBAPP_SERVICE" ]; then
    if systemctl is-active --quiet "$WEBAPP_SERVICE"; then
        echo "  OK: service $WEBAPP_SERVICE is active"
    else
        echo "  FAIL: service $WEBAPP_SERVICE is not active"
        sudo systemctl status "$WEBAPP_SERVICE" --no-pager | head -20
    fi
else
    RUNNING_WEBAPP="$(pgrep -f "$WEBAPP_DIR/server.py" 2>/dev/null | head -1)"
    if [ -n "$RUNNING_WEBAPP" ]; then
        echo "  OK: running manually (PID: $RUNNING_WEBAPP)"
    else
        echo "  FAIL: webapp process not found"
        tail -n 20 "$BOT_DIR/webapp.log" 2>/dev/null || true
    fi
fi

if sudo lsof -i :3000 >/dev/null 2>&1; then
    echo "  OK: listening on port 3000"
else
    echo "  WARN: port 3000 is not listening yet"
fi

echo
echo "Recent webapp logs:"
if [ -n "$WEBAPP_SERVICE" ]; then
    sudo journalctl -u "$WEBAPP_SERVICE" -n 15 --no-pager || true
else
    tail -n 15 "$BOT_DIR/webapp.log" 2>/dev/null || true
fi

echo
echo "Recent bot logs:"
if [ -n "$BOT_SERVICE" ]; then
    sudo journalctl -u "$BOT_SERVICE" -n 15 --no-pager || true
else
    tail -n 15 "$BOT_DIR/bot.log" 2>/dev/null || true
fi

echo
echo "Restart complete."
