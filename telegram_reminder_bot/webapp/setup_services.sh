#!/bin/bash
# Устанавливает systemd службы для webapp и туннеля

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP_DIR="$SCRIPT_DIR"
BOT_DIR="$(cd "$WEBAPP_DIR/.." && pwd)"
ENV_FILE="$BOT_DIR/.env"
PYTHON_BIN="$BOT_DIR/venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "ERROR: Python virtualenv not found at $PYTHON_BIN"
    exit 1
fi

echo "📦 Создание службы веб-сервера..."

sudo tee /etc/systemd/system/telegram-webapp.service > /dev/null << EOF
[Unit]
Description=Telegram Calendar Web App Server
After=network.target

[Service]
Type=simple
WorkingDirectory=$WEBAPP_DIR
EnvironmentFile=-$ENV_FILE
ExecStart=$PYTHON_BIN $WEBAPP_DIR/server.py
Restart=always
RestartSec=5
Environment=WEBAPP_PORT=3000

[Install]
WantedBy=multi-user.target
EOF

echo "🚇 Создание службы туннеля..."

sudo tee /etc/systemd/system/telegram-tunnel.service > /dev/null << TUNNELEOF
[Unit]
Description=Cloudflare Tunnel for Telegram Web App
After=network.target telegram-webapp.service
Requires=telegram-webapp.service

[Service]
Type=simple
WorkingDirectory=$WEBAPP_DIR
Environment=WEBAPP_DIR=$WEBAPP_DIR
Environment=BOT_ENV_FILE=$ENV_FILE
ExecStart=/bin/bash -c '/usr/local/bin/cloudflared tunnel --url http://localhost:3000 2>&1 | while read line; do echo "\$line"; if [[ "\$line" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then URL="\${BASH_REMATCH[1]}"; echo "\$URL" > "\$WEBAPP_DIR/tunnel_url.txt"; ENV_FILE="\$BOT_ENV_FILE"; if [ -f "\$ENV_FILE" ]; then grep -v "^WEBAPP_URL=" "\$ENV_FILE" > "\$ENV_FILE.tmp"; echo "WEBAPP_URL=\$URL" >> "\$ENV_FILE.tmp"; mv "\$ENV_FILE.tmp" "\$ENV_FILE"; systemctl restart telegram-reminder-bot || true; fi; fi; done'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
TUNNELEOF

echo "🔄 Перезагрузка systemd..."
sudo systemctl daemon-reload

echo "✅ Включение служб..."
sudo systemctl enable telegram-webapp telegram-tunnel

echo ""
echo "═══════════════════════════════════════════"
echo "✅ Службы установлены!"
echo ""
echo "Запуск:"
echo "  sudo systemctl start telegram-webapp telegram-tunnel"
echo ""
echo "Проверка:"
echo "  sudo systemctl status telegram-webapp"
echo "  sudo systemctl status telegram-tunnel"
echo ""
echo "Логи туннеля (там будет URL):"
echo "  sudo journalctl -u telegram-tunnel -f"
echo "═══════════════════════════════════════════"
