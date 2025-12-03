"""
Telegram Reminder Bot with Master Password Protection

Security Features:
- Master password protection (user-defined)
- AES-256-GCM encryption for all data
- Password derived key (PBKDF2 with 600,000 iterations)
- Auto-lock after inactivity
- Password NEVER stored - only hash
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN, PERSISTENT_REMINDER_INTERVAL, P2P_ENABLED, P2P_PORT, DATA_DIR, SESSION_DURATIONS, DEFAULT_SESSION_DURATION
from storage.json_storage import storage
from middleware.auth_middleware import AuthMiddleware
from handlers import (
    auth_router,
    commands_router,
    reminders_router,
    todos_router,
    notes_router,
    passwords_router,
    callbacks_router
)
from handlers.auth import is_authenticated, get_crypto_for_user
from utils.keyboards import get_reminder_keyboard
from utils.formatters import format_reminder

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

# Add authentication middleware
dp.message.middleware(AuthMiddleware())
dp.callback_query.middleware(AuthMiddleware())

# Include routers (auth first!)
dp.include_router(auth_router)
dp.include_router(commands_router)
dp.include_router(reminders_router)
dp.include_router(todos_router)
dp.include_router(notes_router)
dp.include_router(passwords_router)
dp.include_router(callbacks_router)


async def check_reminders():
    """Check and trigger due reminders for authenticated users"""
    while True:
        try:
            user_ids = await storage.get_all_user_ids()
            now = datetime.utcnow()
            
            for user_id in user_ids:
                # Only check for authenticated users
                if not is_authenticated(user_id):
                    continue
                
                crypto = get_crypto_for_user(user_id)
                if not crypto:
                    continue
                
                try:
                    user_storage = await storage.get_user_storage(user_id, crypto)
                    reminders = await user_storage.get_reminders()
                    
                    for reminder in reminders:
                        if reminder.status == "pending" and reminder.remind_at_dt:
                            if reminder.remind_at_dt <= now:
                                await user_storage.update_reminder(
                                    reminder.id,
                                    status="active",
                                    last_notification_at=now.isoformat()
                                )
                                await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=True)
                        
                        elif reminder.status == "active" and reminder.is_persistent:
                            if reminder.last_notification_at:
                                last_notif = datetime.fromisoformat(reminder.last_notification_at)
                                if (now - last_notif).total_seconds() >= reminder.persistent_interval:
                                    await user_storage.update_reminder(
                                        reminder.id,
                                        last_notification_at=now.isoformat()
                                    )
                                    await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=False)
                        
                        elif reminder.status == "snoozed" and reminder.snoozed_until_dt:
                            if reminder.snoozed_until_dt <= now:
                                await user_storage.update_reminder(
                                    reminder.id,
                                    status="active",
                                    last_notification_at=now.isoformat()
                                )
                                await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=True)
                
                except Exception as e:
                    logger.error(f"Error checking reminders for user {user_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in reminder check loop: {e}")
        
        await asyncio.sleep(10)


async def send_reminder_notification(user_id: int, reminder, timezone: str, is_initial: bool = True):
    """Send reminder notification to user"""
    try:
        if is_initial:
            text = f"🔔 <b>НАПОМИНАНИЕ!</b>\n\n{format_reminder(reminder, timezone)}"
        else:
            text = f"🔔 <b>Напоминание активно!</b>\n\n📝 {reminder.title}\n\nОтметьте выполненным или отложите."
        
        disable_notification = not reminder.with_sound if not is_initial else False
        
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=get_reminder_keyboard(reminder.id, is_active=True),
            disable_notification=disable_notification
        )
        
        logger.info(f"Sent notification for reminder {reminder.id} to user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send reminder notification: {e}")


async def set_bot_commands():
    """Set bot commands for the menu"""
    commands = [
        BotCommand(command="start", description="🚀 Начать работу"),
        BotCommand(command="unlock", description="🔓 Разблокировать хранилище"),
        BotCommand(command="lock", description="🔒 Заблокировать"),
        BotCommand(command="help", description="📚 Справка"),
        BotCommand(command="newreminder", description="🔔 Новое напоминание"),
        BotCommand(command="reminders", description="📋 Напоминания"),
        BotCommand(command="newtodo", description="📝 Новая задача"),
        BotCommand(command="todos", description="✅ Задачи"),
        BotCommand(command="newnote", description="📝 Новая заметка"),
        BotCommand(command="notes", description="📝 Заметки"),
        BotCommand(command="newpassword", description="🔐 Новый пароль"),
        BotCommand(command="passwords", description="🔐 Пароли"),
        BotCommand(command="archive", description="📦 Архив"),
        BotCommand(command="migrate_completed", description="📦 Перенести выполненные в архив"),
        BotCommand(command="stats", description="📊 Статистика"),
        BotCommand(command="session", description="⏱️ Управление сессией"),
        BotCommand(command="changepassword", description="🔑 Сменить пароль"),
    ]
    await bot.set_my_commands(commands)


async def on_startup():
    """Startup tasks"""
    logger.info("Starting bot...")
    logger.info(f"🔐 Security: Master password protection enabled")
    logger.info(f"🔒 Encryption: AES-256-GCM")
    logger.info(f"⏱️ Session durations: {list(SESSION_DURATIONS.keys())}")
    
    # Create data directory
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    logger.info(f"Data directory: {DATA_DIR}")
    
    # Set bot commands
    await set_bot_commands()
    logger.info("Bot commands set")
    
    # Start reminder checker
    asyncio.create_task(check_reminders())
    logger.info("Reminder checker started")
    
    # Start P2P server if enabled
    if P2P_ENABLED:
        from p2p.sync_server import P2PSyncServer
        p2p_server = P2PSyncServer(port=P2P_PORT)
        asyncio.create_task(p2p_server.start())
        logger.info(f"P2P sync server started on port {P2P_PORT}")
    
    logger.info("Bot started successfully!")


async def on_shutdown():
    """Shutdown tasks"""
    logger.info("Shutting down...")
    await bot.session.close()
    logger.info("Bot stopped")


async def main():
    """Main function to run the bot"""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
