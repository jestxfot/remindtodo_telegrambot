# Деплой Calendar Web App на VPS с Cloudflare Tunnel

## 1. Установка Node.js (если нет)

```bash
# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Проверка
node --version  # должно быть v20.x
npm --version
```

## 2. Установка Cloudflare Tunnel

```bash
# Скачиваем cloudflared
sudo wget -O /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
sudo chmod +x /usr/local/bin/cloudflared

# Проверка
cloudflared --version
```

## 3. Сборка Web App

```bash
cd /root/telegram_reminder_bot/webapp

# Установка зависимостей
npm install

# Сборка
npm run build
```

## 4. Запуск сервера

### Вариант A: Ручной запуск (для теста)

**Терминал 1 — HTTP сервер:**
```bash
cd /root/telegram_reminder_bot/webapp
python3 server.py
```

**Терминал 2 — Cloudflare Tunnel:**
```bash
cloudflared tunnel --url http://localhost:3000
```

Вы увидите что-то вроде:
```
Your quick tunnel has been created! Visit it at:
https://random-words-here.trycloudflare.com
```

Скопируйте этот URL!

### Вариант B: Systemd службы (для production)

**Создайте службу для веб-сервера:**

```bash
sudo nano /etc/systemd/system/telegram-webapp.service
```

```ini
[Unit]
Description=Telegram Calendar Web App
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/telegram_reminder_bot/webapp
ExecStart=/usr/bin/python3 /root/telegram_reminder_bot/webapp/server.py
Restart=always
RestartSec=10
Environment=WEBAPP_PORT=3000

[Install]
WantedBy=multi-user.target
```

**Создайте службу для Cloudflare Tunnel:**

```bash
sudo nano /etc/systemd/system/cloudflared-tunnel.service
```

```ini
[Unit]
Description=Cloudflare Tunnel for Web App
After=network.target telegram-webapp.service
Requires=telegram-webapp.service

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:3000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Запуск:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-webapp cloudflared-tunnel
sudo systemctl start telegram-webapp cloudflared-tunnel

# Проверка статуса
sudo systemctl status telegram-webapp
sudo systemctl status cloudflared-tunnel
```

**Получить URL туннеля:**
```bash
sudo journalctl -u cloudflared-tunnel -f
```

Найдите строку с URL: `https://xxx.trycloudflare.com`

## 5. Настройка бота

Добавьте URL в `.env` бота:

```bash
nano /root/telegram_reminder_bot/.env
```

```env
WEBAPP_URL=https://xxx.trycloudflare.com
```

Перезапустите бота:
```bash
sudo systemctl restart telegram-reminder-bot
```

## 6. Проверка

1. Откройте бота в Telegram
2. Нажмите "📅 Календарь"
3. Нажмите "📅 Открыть календарь"
4. Должен открыться Web App!

## ⚠️ Важно

- **URL меняется** при каждом перезапуске cloudflared (бесплатный режим)
- Для постоянного URL нужен аккаунт Cloudflare (бесплатно):
  ```bash
  cloudflared tunnel login
  cloudflared tunnel create mybot
  cloudflared tunnel route dns mybot calendar.yourdomain.com
  ```

## Обновление Web App

```bash
cd /root/telegram_reminder_bot/webapp
git pull  # или скопируйте новые файлы
npm install
npm run build
sudo systemctl restart telegram-webapp
```

## Логи

```bash
# Веб-сервер
sudo journalctl -u telegram-webapp -f

# Туннель
sudo journalctl -u cloudflared-tunnel -f
```

