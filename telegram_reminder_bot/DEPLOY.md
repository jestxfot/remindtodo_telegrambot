# 🚀 Бесплатный хостинг для Telegram бота

## Лучшие бесплатные варианты

| Платформа | Бесплатно | Сложность | Рекомендация |
|-----------|-----------|-----------|--------------|
| **Railway** | 500 часов/мес | ⭐ Легко | ✅ Лучший выбор |
| **Render** | Бесплатно | ⭐ Легко | ✅ Надёжный |
| **Fly.io** | 3 VMs бесплатно | ⭐⭐ Средне | ✅ Хороший |
| **Koyeb** | 1 сервис | ⭐ Легко | ✅ Простой |
| **Replit** | Бесплатно | ⭐ Легко | ⚠️ Засыпает |

---

## 1️⃣ Railway.app (Рекомендую!)

**Бесплатно:** 500 часов/месяц (≈20 дней 24/7)

### Шаги:

1. Зарегистрируйтесь на https://railway.app (через GitHub)

2. Нажмите **"New Project"** → **"Deploy from GitHub repo"**

3. Выберите ваш репозиторий с ботом

4. Добавьте переменные окружения:
   - Нажмите на сервис → **Variables**
   - Добавьте:
     ```
     BOT_TOKEN=ваш_токен_от_BotFather
     DATA_DIR=/app/data
     TIMEZONE=Europe/Moscow
     ```

5. Бот запустится автоматически! 🎉

### Команды (если через CLI):
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

---

## 2️⃣ Render.com

**Бесплатно:** Background Worker бесплатно навсегда

### Шаги:

1. Зарегистрируйтесь на https://render.com

2. Нажмите **"New +"** → **"Background Worker"**

3. Подключите GitHub репозиторий

4. Настройки:
   - **Name:** telegram-reminder-bot
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`

5. Добавьте **Environment Variables**:
   ```
   BOT_TOKEN=ваш_токен
   DATA_DIR=./data
   TIMEZONE=Europe/Moscow
   ```

6. Нажмите **"Create Background Worker"**

⚠️ **Важно:** Бесплатный tier на Render засыпает при неактивности. Для бота-напоминаний лучше Railway.

---

## 3️⃣ Fly.io

**Бесплатно:** 3 маленьких VM, 3GB storage

### Шаги:

1. Установите flyctl:
```bash
# Linux/macOS
curl -L https://fly.io/install.sh | sh

# Windows
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

2. Регистрация и вход:
```bash
fly auth signup
# или
fly auth login
```

3. Запуск бота:
```bash
cd telegram_reminder_bot

# Создать приложение
fly launch

# Добавить токен
fly secrets set BOT_TOKEN=ваш_токен

# Создать volume для данных
fly volumes create bot_data --size 1

# Деплой
fly deploy
```

4. Проверка:
```bash
fly logs
```

---

## 4️⃣ Koyeb.com

**Бесплатно:** 1 сервис, 512MB RAM

### Шаги:

1. Зарегистрируйтесь на https://koyeb.com

2. **Create App** → **GitHub**

3. Выберите репозиторий

4. Настройки:
   - **Instance type:** Free
   - **Builder:** Dockerfile

5. Environment variables:
   ```
   BOT_TOKEN=ваш_токен
   ```

6. Deploy!

---

## 5️⃣ Replit.com (Простой, но засыпает)

**Бесплатно:** Навсегда, но засыпает без активности

### Шаги:

1. Зайдите на https://replit.com

2. **Create Repl** → **Import from GitHub**

3. Вставьте URL репозитория

4. В **Secrets** добавьте:
   - `BOT_TOKEN` = ваш токен

5. Нажмите **Run**

### Чтобы не засыпал:
Создайте файл `keep_alive.py`:
```python
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
```

И добавьте в `bot.py`:
```python
from keep_alive import keep_alive
keep_alive()
```

Затем используйте https://uptimerobot.com для пинга каждые 5 минут.

---

## 📋 Подготовка репозитория

1. Создайте репозиторий на GitHub

2. Загрузите файлы бота:
```bash
cd telegram_reminder_bot
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ВАШ_USERNAME/telegram-reminder-bot.git
git push -u origin main
```

3. **Важно:** НЕ загружайте `.env` файл с токеном!

Добавьте `.gitignore`:
```
.env
__pycache__/
*.pyc
data/
*.db
```

---

## 🔑 Получение токена бота

1. Откройте Telegram
2. Найдите @BotFather
3. Отправьте `/newbot`
4. Введите имя бота
5. Введите username бота (должен заканчиваться на `bot`)
6. Скопируйте токен (выглядит как `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

---

## ❓ Какой выбрать?

### Для бота-напоминаний рекомендую:

1. **Railway** — лучший баланс простоты и надёжности
2. **Fly.io** — если нужен постоянный storage для данных
3. **Render** — если бот не критичен к засыпанию

### Для 24/7 работы бесплатно:
- **Oracle Cloud Free Tier** — бесплатный VPS навсегда (сложнее настроить)
- **Google Cloud Free Tier** — бесплатный e2-micro

---

## 6️⃣ VPS с systemd (Полный контроль)

**Для:** Собственный VPS/Dedicated сервер (DigitalOcean, Hetzner, Timeweb, и др.)

### Требования:
- Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- Python 3.10+
- SSH доступ с правами sudo

### Шаг 1: Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Python и pip
sudo apt install python3 python3-pip python3-venv git -y

# Создаём пользователя для бота (безопасность)
sudo useradd -r -s /bin/false telegrambot
```

### Шаг 2: Установка бота

```bash
# Создаём директорию
sudo mkdir -p root/telegram_reminder_bot
cd root/telegram_reminder_bot

# Клонируем репозиторий (или копируем файлы)
sudo git clone https://github.com/YOUR_USERNAME/telegram-reminder-bot.git .
# ИЛИ копируем файлы через scp:
# scp -r telegram_reminder_bot/* user@server:root/telegram_reminder_bot/

# Создаём виртуальное окружение
sudo python3 -m venv venv

# Устанавливаем зависимости
sudo ./venv/bin/pip install -r requirements.txt
```

### Шаг 3: Настройка окружения

```bash
# Создаём файл конфигурации
sudo nano /root/telegram_reminder_bot/.env
```

Содержимое `.env`:
```env
BOT_TOKEN=ваш_токен_от_BotFather
DATA_DIR=/root/telegram_reminder_bot/data
TIMEZONE=Europe/Moscow
```

```bash
# Создаём директорию для данных
sudo mkdir -p /root/telegram_reminder_bot/data

# Устанавливаем права доступа
sudo chown -R telegrambot:telegrambot /root/telegram_reminder_bot
sudo chmod 600 /root/telegram_reminder_bot/.env
```

### Шаг 4: Создание systemd службы

```bash
sudo nano /etc/systemd/system/telegram-reminder-bot.service
```

Содержимое файла службы:
```ini
[Unit]
Description=Telegram Reminder Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/telegram_reminder_bot
EnvironmentFile=/root/telegram_reminder_bot/.env
ExecStart=/root/telegram_reminder_bot/venv/bin/python /root/telegram_reminder_bot/bot.py
Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=telegram-bot

[Install]
WantedBy=multi-user.target
```

### Шаг 5: Запуск службы

```bash
# Перезагружаем конфигурацию systemd
sudo systemctl daemon-reload

# Включаем автозапуск при загрузке системы
sudo systemctl enable telegram-reminder-bot

# Запускаем бота
sudo systemctl start telegram-reminder-bot

# Проверяем статус
sudo systemctl status telegram-reminder-bot
```

### Полезные команды

```bash
# Посмотреть статус
sudo systemctl status telegram-reminder-bot

# Перезапустить бота
sudo systemctl restart telegram-reminder-bot

# Остановить бота
sudo systemctl stop telegram-reminder-bot

# Просмотр логов (последние 100 строк)
sudo journalctl -u telegram-reminder-bot -n 100

# Логи в реальном времени
sudo journalctl -u telegram-reminder-bot -f

# Логи за сегодня
sudo journalctl -u telegram-reminder-bot --since today
```

### Обновление бота

```bash
cd root/telegram_reminder_bot

# Останавливаем бота
sudo systemctl stop telegram-reminder-bot

# Получаем обновления
sudo git pull origin main

# Обновляем зависимости (если изменились)
sudo ./venv/bin/pip install -r requirements.txt

# Возвращаем права
sudo chown -R telegrambot:telegrambot root/telegram_reminder_bot

# Запускаем бота
sudo systemctl start telegram-reminder-bot
```

### Автоматический перезапуск при падении

Служба уже настроена на автоматический перезапуск (`Restart=always`). Для дополнительной защиты можно настроить watchdog:

```bash
# Редактируем службу
sudo nano /etc/systemd/system/telegram-reminder-bot.service
```

Добавляем в секцию `[Service]`:
```ini
WatchdogSec=60
```

### Резервное копирование данных

```bash
# Создаём скрипт резервного копирования
sudo nano root/telegram_reminder_bot/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backups/telegram-bot"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/data_$DATE.tar.gz -C root/telegram_reminder_bot data/
# Удаляем бэкапы старше 7 дней
find $BACKUP_DIR -name "data_*.tar.gz" -mtime +7 -delete
```

```bash
# Делаем скрипт исполняемым
sudo chmod +x root/telegram_reminder_bot/backup.sh

# Добавляем в cron (каждый день в 3:00)
sudo crontab -e
# Добавить строку:
# 0 3 * * * root/telegram_reminder_bot/backup.sh
```

---

## 💡 Советы

1. **Сохраняйте данные в облаке** — используйте volume/persistent storage
2. **Логируйте ошибки** — `fly logs` или dashboard платформы
3. **Используйте webhook** вместо polling для экономии ресурсов
4. **Мониторьте бота** — UptimeRobot или аналоги
5. **На VPS** — используйте fail2ban и настройте firewall для безопасности
