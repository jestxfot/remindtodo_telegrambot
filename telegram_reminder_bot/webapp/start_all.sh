#!/bin/bash
# Запускает веб-сервер и туннель вместе

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$BOT_DIR/venv/bin/python"
cd "$SCRIPT_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "❌ Не найден Python из venv: $PYTHON_BIN"
    exit 1
fi

# Проверяем что билд существует
if [ ! -d "dist" ]; then
    echo "❌ Папка dist не найдена!"
    echo "Сначала выполните: npm run build"
    exit 1
fi

echo "🌐 Запуск веб-сервера на порту 3000..."
"$PYTHON_BIN" server.py &
SERVER_PID=$!

# Ждём запуска сервера
sleep 2

echo "🚇 Запуск Cloudflare Tunnel..."
echo ""

# Функция для остановки при Ctrl+C
cleanup() {
    echo ""
    echo "⏹️ Остановка..."
    kill $SERVER_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Запускаем туннель и парсим URL
cloudflared tunnel --url http://localhost:3000 2>&1 | while read line; do
    echo "$line"
    
    if [[ "$line" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then
        URL="${BASH_REMATCH[1]}"
        
        echo ""
        echo "═══════════════════════════════════════════"
        echo "✅ ТУННЕЛЬ ЗАПУЩЕН!"
        echo "🔗 URL: $URL"
        echo "═══════════════════════════════════════════"
        echo ""
        
        # Сохраняем URL
        echo "$URL" > tunnel_url.txt
        
        # Обновляем .env бота
        BOT_ENV="$SCRIPT_DIR/../.env"
        if [ -f "$BOT_ENV" ]; then
            grep -v "^WEBAPP_URL=" "$BOT_ENV" > "$BOT_ENV.tmp"
            echo "WEBAPP_URL=$URL" >> "$BOT_ENV.tmp"
            mv "$BOT_ENV.tmp" "$BOT_ENV"
            echo "📝 .env обновлён"
            
            # Перезапуск бота
            if systemctl is-active --quiet telegram-reminder-bot 2>/dev/null; then
                sudo systemctl restart telegram-reminder-bot
                echo "🤖 Бот перезапущен!"
            else
                echo "⚠️ Перезапустите бота вручную:"
                echo "   sudo systemctl restart telegram-reminder-bot"
            fi
        else
            echo "⚠️ Добавьте в .env бота:"
            echo "   WEBAPP_URL=$URL"
        fi
        echo ""
    fi
done

# Ждём завершения
wait
