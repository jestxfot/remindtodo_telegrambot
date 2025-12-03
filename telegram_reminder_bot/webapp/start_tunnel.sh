#!/bin/bash
# Запускает Cloudflare Quick Tunnel и сохраняет URL в файл

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
URL_FILE="$SCRIPT_DIR/tunnel_url.txt"
LOG_FILE="$SCRIPT_DIR/tunnel.log"

echo "🚀 Запуск Cloudflare Quick Tunnel..."

# Запускаем cloudflared и парсим URL
cloudflared tunnel --url http://localhost:3000 2>&1 | tee "$LOG_FILE" | while read line; do
    # Ищем URL в выводе
    if [[ "$line" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then
        URL="${BASH_REMATCH[1]}"
        echo "$URL" > "$URL_FILE"
        echo ""
        echo "✅ Туннель запущен!"
        echo "🔗 URL: $URL"
        echo ""
        echo "URL сохранён в: $URL_FILE"
        
        # Обновляем .env бота если он существует
        BOT_ENV="$SCRIPT_DIR/../.env"
        if [ -f "$BOT_ENV" ]; then
            # Удаляем старый WEBAPP_URL и добавляем новый
            grep -v "^WEBAPP_URL=" "$BOT_ENV" > "$BOT_ENV.tmp"
            echo "WEBAPP_URL=$URL" >> "$BOT_ENV.tmp"
            mv "$BOT_ENV.tmp" "$BOT_ENV"
            echo "📝 Обновлён .env бота"
            
            # Перезапускаем бота если systemd
            if systemctl is-active --quiet telegram-reminder-bot 2>/dev/null; then
                echo "🔄 Перезапуск бота..."
                sudo systemctl restart telegram-reminder-bot
                echo "✅ Бот перезапущен с новым URL!"
            fi
        fi
    fi
done

