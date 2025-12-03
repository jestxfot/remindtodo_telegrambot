# Telegram Calendar Web App

Интерактивный календарь для просмотра задач и напоминаний в Telegram.

## Функции

- 📅 **День** — детальный вид на один день с таймлайном
- 📆 **Неделя** — обзор недели с событиями
- 📆 **Месяц** — календарная сетка с индикаторами событий

## Установка

```bash
cd telegram_reminder_bot/webapp
npm install
```

## Разработка

```bash
npm run dev
```

Откройте http://localhost:3000

## Сборка

```bash
npm run build
```

## Деплой на GitHub Pages

1. Включите GitHub Pages в настройках репозитория
2. Выберите источник: GitHub Actions
3. Push в main ветку автоматически запустит деплой

## Настройка бота

После деплоя получите URL вида:
```
https://username.github.io/remindtodo_telegrambot/
```

Добавьте в `.env` бота:
```
WEBAPP_URL=https://username.github.io/remindtodo_telegrambot/
API_ENABLED=true
API_PORT=8080
```

## Технологии

- React 18
- Vite
- Telegram Web App SDK
- date-fns

