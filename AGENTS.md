# AGENTS

## Production

- Host: `84.54.30.233`
- SSH port: `10222`
- Environment: `prod`
- Deploy path: `/root/telegram_reminder_bot`

## Deployment flow

Local machine:

```bash
git add <files>
git commit -m "your message"
git push origin cursor/telegram-bot-for-reminders-and-tasks-claude-4.5-opus-high-thinking-bfb8
```

VPS:

```bash
cd /root/telegram_reminder_bot
git fetch origin
git checkout cursor/telegram-bot-for-reminders-and-tasks-claude-4.5-opus-high-thinking-bfb8
git pull --ff-only origin cursor/telegram-bot-for-reminders-and-tasks-claude-4.5-opus-high-thinking-bfb8
./restart_all.sh
```

## Notes

- `84.54.30.233:10222` is the production server.
- Webapp and bot should run from the same virtualenv: `/root/telegram_reminder_bot/venv/bin/python`.
- Before deploying, avoid committing secret `.env` changes.
