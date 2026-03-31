#!/bin/bash

# Production deploy helper for the split repo/live-directory layout.
#
# Repo clone:
#   /root/telegram_reminder_bot_repo
# Live runtime directory:
#   /root/telegram_reminder_bot
#
# The live directory is not a git checkout because the repository root contains
# one extra nesting level: telegram_reminder_bot/. This script syncs the tracked
# app files from the repo clone into the live directory, preserves runtime-only
# state (.env, data, venv, logs), refreshes webapp dependencies, and then runs
# the full restart flow.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIVE_DIR="$SCRIPT_DIR"
REPO_ROOT="${DEPLOY_REPO_ROOT:-/root/telegram_reminder_bot_repo}"
SOURCE_DIR="$REPO_ROOT/telegram_reminder_bot"
BACKUP_ROOT="${DEPLOY_BACKUP_ROOT:-/root/deploy_backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_ROOT/telegram_reminder_bot_code_$TIMESTAMP.tar.gz"

echo "=========================================="
echo "DEPLOY FROM REPO"
echo "=========================================="
echo "Repo root:   $REPO_ROOT"
echo "Source dir:  $SOURCE_DIR"
echo "Live dir:    $LIVE_DIR"
echo "Backup file: $BACKUP_FILE"
echo "=========================================="

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: source app directory not found: $SOURCE_DIR"
    exit 1
fi

if [ ! -f "$SOURCE_DIR/restart_all.sh" ]; then
    echo "ERROR: source app directory looks incomplete: $SOURCE_DIR"
    exit 1
fi

mkdir -p "$BACKUP_ROOT"

echo
echo "Creating code-only backup..."
tar \
    --exclude="./.env" \
    --exclude="./data" \
    --exclude="./venv" \
    --exclude="./bot.log" \
    --exclude="./webapp.log" \
    --exclude="./webapp/node_modules" \
    --exclude="./webapp/dist" \
    --exclude="./__pycache__" \
    -czf "$BACKUP_FILE" \
    -C "$LIVE_DIR" .

echo
echo "Syncing tracked app files into live directory..."
rsync -a --delete \
    --exclude ".env" \
    --exclude "data/" \
    --exclude "venv/" \
    --exclude "bot.log" \
    --exclude "webapp.log" \
    --exclude "__pycache__/" \
    --exclude "webapp/node_modules/" \
    --exclude "webapp/dist/" \
    "$SOURCE_DIR/" "$LIVE_DIR/"

echo
echo "Refreshing shell script permissions..."
find "$LIVE_DIR" -maxdepth 1 -type f -name "*.sh" -exec chmod 755 {} +
find "$LIVE_DIR/webapp" -maxdepth 1 -type f -name "*.sh" -exec chmod 755 {} +

echo
echo "Installing webapp dependencies..."
cd "$LIVE_DIR/webapp"
npm ci
cd "$LIVE_DIR"

echo
echo "Running full restart..."
bash "$LIVE_DIR/restart_all.sh"
