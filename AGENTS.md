# AGENTS

## Production

- Host: `84.54.30.233`
- SSH port: `10222`
- Environment: `prod`
- Repo clone path: `/root/telegram_reminder_bot_repo`
- Live runtime path: `/root/telegram_reminder_bot`

## Deployment flow

Local machine:

```bash
git add <files>
git commit -m "your message"
git push origin main
```

VPS:

```bash
cd /root/telegram_reminder_bot_repo
git pull --ff-only origin main
/root/telegram_reminder_bot/deploy_from_repo.sh
```

## Notes

- `84.54.30.233:10222` is the production server.
- Webapp and bot should run from the same virtualenv: `/root/telegram_reminder_bot/venv/bin/python`.
- Production Mini App URL: `https://todo.mycooltelegrambot.ru`.
- `WEBAPP_URL` in production should stay set to `https://todo.mycooltelegrambot.ru`.
- `telegram-tunnel` is disabled in production and should stay disabled unless there is an explicit migration back to Cloudflare Tunnel.
- `restart_all.sh` was updated so a disabled tunnel service is skipped instead of being started again.
- Before deploying, avoid committing secret `.env` changes.
- The live runtime directory `/root/telegram_reminder_bot` is not the git repo root. The repo root lives separately at `/root/telegram_reminder_bot_repo`, and deploys must sync `telegram_reminder_bot/` from that clone into the live directory.
- The production deploy helper is `/root/telegram_reminder_bot/deploy_from_repo.sh`. It preserves `.env`, `data/`, `venv/`, and logs, refreshes webapp dependencies, and then runs the full `restart_all.sh`.
- After each production deploy, restart all components via the deploy helper, which ends with the full `restart_all.sh`.
- Do not do a partial production restart unless the task explicitly requires it.
- The main production directory is `/root/telegram_reminder_bot`.
- The old nested duplicate `/root/telegram_reminder_bot/root/telegram-reminder-bot` was checked and removed after confirming no live references from systemd, nginx, cron, or runtime processes.
- If a nested duplicate path under `/root/telegram_reminder_bot/root/` appears again, treat it as a deployment artifact and verify references before deletion.
