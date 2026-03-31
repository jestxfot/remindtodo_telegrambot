"""
Telegram Reminder Bot - WebApp Only Mode

All data management through Mini App.
Bot only handles:
- Welcome messages
- Reminder notifications
- Complete/Snooze callbacks

Security Features:
- Master password protection (via WebApp)
- AES-256-GCM encryption for all data
- Password derived key (PBKDF2 with 600,000 iterations)
"""
import asyncio
import logging
import hashlib
import os
from pathlib import Path
import fcntl
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN, DATA_DIR
from storage.models import now
from storage.json_storage import storage
from handlers import commands_router, notifications_router
from handlers.auth import is_authenticated, get_crypto_for_user
from utils.keyboards import get_reminder_notification_keyboard
from utils.timezone import to_msk, parse_dt, format_dt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Include routers
dp.include_router(commands_router)
dp.include_router(notifications_router)

_bot_lock_fh = None


def _acquire_single_instance_lock() -> None:
    """
    Prevent running multiple long-polling instances locally.

    Telegram enforces a single active getUpdates consumer per bot token; starting a
    second instance causes TelegramConflictError spam and a non-working bot.
    """
    global _bot_lock_fh
    token_fingerprint = hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()[:12]
    lock_path = Path(os.getenv("BOT_LOCK_PATH", f"/tmp/remindtodo_bot_{token_fingerprint}.lock"))
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    fh = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.error("Another bot instance is already running (lock: %s). Exiting.", lock_path)
        raise SystemExit(1)

    fh.write(str(os.getpid()))
    fh.flush()
    _bot_lock_fh = fh


async def check_reminders():
    """Check and trigger due reminders for authenticated users"""
    check_count = 0
    while True:
        try:
            user_ids = await storage.get_all_user_ids()
            current_time = now()  # Moscow time with timezone
            check_count += 1
            
            # Debug log every 30 checks (~5 min)
            if check_count % 30 == 1:
                logger.info(f"[Checker] Checking {len(user_ids)} users at {current_time.isoformat()}")
            
            for user_id in user_ids:
                if not is_authenticated(user_id):
                    if check_count % 30 == 1:
                        logger.debug(f"[Checker] User {user_id} not authenticated, skipping")
                    continue
                
                crypto = get_crypto_for_user(user_id)
                if not crypto:
                    continue
                
                try:
                    user_storage = await storage.get_user_storage(user_id, crypto)
                    reminders = await user_storage.get_reminders()
                    
                    if check_count % 30 == 1 and reminders:
                        logger.info(f"[Checker] User {user_id}: {len(reminders)} reminders")
                    
                    for reminder in reminders:
                        remind_at = to_msk(reminder.remind_at_dt)
                        snoozed_until = to_msk(reminder.snoozed_until_dt)
                        
                        # Debug: log reminder status
                        if check_count % 30 == 1:
                            logger.debug(f"[Checker] Reminder {reminder.id[:8]}: status={reminder.status}, remind_at={remind_at}, now={current_time}")

                        if reminder.status == "pending" and remind_at:
                            if remind_at <= current_time:
                                logger.info(f"[Checker] Triggering reminder {reminder.id[:8]} for user {user_id}")
                                await user_storage.update_reminder(
                                    reminder.id,
                                    status="active",
                                    last_notification_at=format_dt(current_time)
                                )
                                await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=True)

                        elif reminder.status == "active" and reminder.is_persistent:
                            if reminder.last_notification_at:
                                last_notif = parse_dt(reminder.last_notification_at)
                                if (current_time - last_notif).total_seconds() >= reminder.persistent_interval:
                                    await user_storage.update_reminder(
                                        reminder.id,
                                        last_notification_at=format_dt(current_time)
                                    )
                                    await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=False)

                        elif reminder.status == "snoozed" and snoozed_until:
                            if snoozed_until <= current_time:
                                await user_storage.update_reminder(
                                    reminder.id,
                                    status="active",
                                    last_notification_at=format_dt(current_time)
                                )
                                await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=True)
                
                except ValueError as e:
                    logger.warning(f"Could not load storage for user {user_id}: {e}")
                except Exception as e:
                    logger.error(f"Error checking reminders for user {user_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in reminder check loop: {e}")
        
        await asyncio.sleep(10)


async def send_reminder_notification(user_id: int, reminder, timezone: str, is_initial: bool = True):
    """Send reminder notification to user"""
    try:
        from utils.formatters import format_datetime
        
        if is_initial:
            remind_time = format_datetime(reminder.remind_at, timezone)
            text = f"🔔 <b>НАПОМИНАНИЕ!</b>\n\n📝 {reminder.title}\n⏰ {remind_time}"
        else:
            text = f"🔔 <b>Напоминание активно!</b>\n\n📝 {reminder.title}\n\n<i>Отметьте выполненным или отложите</i>"
        
        disable_notification = not reminder.with_sound if not is_initial else False
        
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=get_reminder_notification_keyboard(reminder.id),
            disable_notification=disable_notification
        )
        
        logger.info(f"Sent notification for reminder {reminder.id} to user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send reminder notification: {e}")


async def set_bot_commands():
    """Set bot commands for the menu"""
    commands = [
        BotCommand(command="start", description="🚀 Начать работу"),
        BotCommand(command="app", description="📱 Открыть приложение"),
        BotCommand(command="status", description="📊 Статус"),
        BotCommand(command="help", description="📚 Справка"),
    ]
    await bot.set_my_commands(commands)


async def on_startup():
    """Startup tasks"""
    logger.info("Starting bot...")
    logger.info(f"🔐 Security: Master password protection enabled")
    logger.info(f"🔒 Encryption: AES-256-GCM")
    logger.info(f"📱 Mode: WebApp only")
    
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    logger.info(f"Data directory: {DATA_DIR}")
    
    await set_bot_commands()
    logger.info("Bot commands set")
    
    asyncio.create_task(check_reminders())
    logger.info("Reminder checker started")
    
    logger.info("Bot started successfully!")


async def on_shutdown():
    """Shutdown tasks"""
    logger.info("Shutting down...")
    await bot.session.close()
    logger.info("Bot stopped")


async def main():
    """Main function to run the bot"""
    _acquire_single_instance_lock()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        # Safety: ensure no webhook is set (polling mode only).
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
