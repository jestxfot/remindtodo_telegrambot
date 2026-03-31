#!/bin/bash
# Скрипт для перезапуска бота и туннеля с автоматическим обновлением URL

set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$BOT_DIR/.env"

echo "🔄 Перезапуск системы..."
echo ""

# 1. Останавливаем всё
echo "⏹️ Остановка служб..."
sudo systemctl stop telegram-reminder-bot 2>/dev/null
sudo systemctl stop telegram-tunnel 2>/dev/null
sudo systemctl stop telegram-webapp 2>/dev/null
sudo fuser -k 3000/tcp 2>/dev/null
sleep 3

# 2. Запускаем веб-сервер
echo "🌐 Запуск веб-сервера..."
sudo systemctl start telegram-webapp
sleep 3

# Проверяем
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Веб-сервер работает"
else
    echo "⚠️ Веб-сервер не отвечает (может заработать позже)"
fi

# 3. Запускаем туннель напрямую и ловим URL
echo "🚇 Запуск туннеля и получение URL..."
echo ""

# Запускаем cloudflared в фоне и пишем вывод в файл
TUNNEL_LOG="/tmp/tunnel_output.log"
rm -f "$TUNNEL_LOG"

cloudflared tunnel --url http://localhost:3000 > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

# Ждём URL (до 30 секунд)
URL=""
for i in {1..30}; do
    sleep 1
    if [ -f "$TUNNEL_LOG" ]; then
        URL=$(grep -oE "https://[a-zA-Z0-9-]+\.trycloudflare\.com" "$TUNNEL_LOG" | head -1)
        if [ -n "$URL" ]; then
            break
        fi
    fi
    echo -n "."
done
echo ""

# Останавливаем временный туннель
kill $TUNNEL_PID 2>/dev/null
sleep 2

if [ -z "$URL" ]; then
    echo "❌ Не удалось получить URL!"
    echo "Лог туннеля:"
    cat "$TUNNEL_LOG"
    exit 1
fi

echo "✅ Получен URL: $URL"

# 4. Обновляем .env
echo ""
echo "📝 Обновление .env..."

# Удаляем старые WEBAPP_URL и добавляем новый
if [ -f "$ENV_FILE" ]; then
    grep -v "^WEBAPP_URL" "$ENV_FILE" > "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
fi
echo "WEBAPP_URL=$URL" >> "$ENV_FILE"

echo "Проверка:"
grep "WEBAPP_URL" "$ENV_FILE"

# 5. Запускаем туннель через systemd (с новым URL)
echo ""
echo "🚇 Запуск туннеля через systemd..."
sudo systemctl start telegram-tunnel
sleep 3

# 6. Запускаем бота
echo ""
echo "🤖 Запуск бота..."
sudo systemctl start telegram-reminder-bot
sleep 2

# 7. Финальная проверка
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Готово!"
echo ""
echo "🔗 URL календаря: $URL"
echo ""
echo "Статус служб:"
systemctl is-active telegram-webapp >/dev/null && echo "  ✅ telegram-webapp" || echo "  ❌ telegram-webapp"
systemctl is-active telegram-tunnel >/dev/null && echo "  ✅ telegram-tunnel" || echo "  ❌ telegram-tunnel"
systemctl is-active telegram-reminder-bot >/dev/null && echo "  ✅ telegram-reminder-bot" || echo "  ❌ telegram-reminder-bot"
echo ""
echo "Откройте в браузере: $URL"
echo "═══════════════════════════════════════════════════════════"
