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
import aiofiles
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN, PERSISTENT_REMINDER_INTERVAL, P2P_ENABLED, P2P_PORT, DATA_DIR, SESSION_DURATIONS, DEFAULT_SESSION_DURATION, API_ENABLED, API_PORT
from storage.json_storage import storage
from middleware.auth_middleware import AuthMiddleware
from handlers import (
    auth_router,
    commands_router,
    reminders_router,
    todos_router,
    notes_router,
    passwords_router,
    callbacks_router,
    calendar_router
)
from handlers.auth import is_authenticated, get_crypto_for_user
from utils.keyboards import get_reminder_keyboard
from utils.formatters import format_reminder
from utils.timezone import now, now_str, parse_dt

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
dp.include_router(calendar_router)

async def check_reminders():
    """Check and trigger due reminders for authenticated users"""
    while True:
        try:
            user_ids = await storage.get_all_user_ids()
            current_time = now()
            
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
                        remind_at = reminder.remind_at_dt
                        snoozed_until = reminder.snoozed_until_dt
                        
                        if reminder.status == "pending" and remind_at:
                            if remind_at <= current_time:
                                await user_storage.update_reminder(
                                    reminder.id,
                                    status="active",
                                    last_notification_at=now_str()
                                )
                                await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=True)
                        
                        elif reminder.status == "active" and reminder.is_persistent:
                            if reminder.last_notification_at:
                                last_notif = parse_dt(reminder.last_notification_at)
                                if last_notif and (current_time - last_notif).total_seconds() >= reminder.persistent_interval:
                                    await user_storage.update_reminder(
                                        reminder.id,
                                        last_notification_at=now_str()
                                    )
                                    await send_reminder_notification(user_id, reminder, user_storage.user.timezone, is_initial=False)
                        
                        elif reminder.status == "snoozed" and snoozed_until:
                            if snoozed_until <= current_time:
                                await user_storage.update_reminder(
                                    reminder.id,
                                    status="active",
                                    last_notification_at=now_str()
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
        BotCommand(command="calendar", description="📅 Календарь"),
        BotCommand(command="session", description="⏱️ Управление сессией"),
        BotCommand(command="changepassword", description="🔑 Сменить пароль"),
    ]
    await bot.set_my_commands(commands)


async def check_and_send_backups():
    """Check and send daily backups to users who enabled them"""
    import json
    import io
    from aiogram.types import BufferedInputFile
    
    while True:
        try:
            user_ids = await storage.get_all_user_ids()
            current_time = now()
            current_hour = current_time.hour
            
            for user_id in user_ids:
                # Only for authenticated users
                if not is_authenticated(user_id):
                    continue
                
                crypto = get_crypto_for_user(user_id)
                if not crypto:
                    continue
                
                try:
                    user_storage = await storage.get_user_storage(user_id, crypto)
                    user = user_storage.user
                    
                    # Check if backup enabled
                    if not getattr(user, 'backup_enabled', False):
                        continue
                    
                    # Check if it's backup hour
                    backup_hour = getattr(user, 'backup_hour', 3)
                    if current_hour != backup_hour:
                        continue
                    
                    # Check if already backed up today
                    last_backup = getattr(user, 'last_backup_at', None)
                    if last_backup:
                        last_backup_dt = parse_dt(last_backup)
                        if last_backup_dt and last_backup_dt.date() == current_time.date():
                            continue
                    
                    # Create backup
                    stats = await user_storage.get_statistics()
                    backup_data = {
                        "backup_date": now_str(),
                        "user_id": user_id,
                        "timezone": user.timezone,
                        "statistics": stats,
                        "note": "This is encrypted backup. Import it using /restore command."
                    }
                    
                    # Get encrypted file path
                    backup_file = Path(DATA_DIR) / f"user_{user_id}.encrypted.json"
                    if backup_file.exists():
                        async with aiofiles.open(backup_file, 'r') as f:
                            encrypted_content = await f.read()
                        
                        # Send backup file
                        file_bytes = encrypted_content.encode('utf-8')
                        date_str = current_time.strftime("%Y-%m-%d")
                        filename = f"backup_{user_id}_{date_str}.json"
                        
                        input_file = BufferedInputFile(file_bytes, filename=filename)
                        
                        await bot.send_document(
                            chat_id=user_id,
                            document=input_file,
                            caption=(
                                f"📦 <b>Ежедневный бэкап</b>\n\n"
                                f"📅 Дата: {date_str}\n"
                                f"📊 Задач: {stats['todos']['total']}\n"
                                f"🔔 Напоминаний: {stats['reminders']['total']}\n"
                                f"📝 Заметок: {stats['notes']}\n"
                                f"🔐 Паролей: {stats['passwords']}\n\n"
                                f"<i>Файл зашифрован. Сохраните его в надёжном месте.</i>"
                            ),
                            parse_mode="HTML"
                        )
                        
                        # Update last backup time
                        await user_storage.update_user(last_backup_at=now_str())
                        logger.info(f"Backup sent to user {user_id}")
                
                except Exception as e:
                    logger.error(f"Error sending backup to user {user_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error in backup check loop: {e}")
        
        # Check every hour
        await asyncio.sleep(3600)


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
    
    # Start backup checker
    asyncio.create_task(check_and_send_backups())
    logger.info("Backup checker started")
    
    # Start P2P server if enabled
    if P2P_ENABLED:
        from p2p.sync_server import P2PSyncServer
        p2p_server = P2PSyncServer(port=P2P_PORT)
        asyncio.create_task(p2p_server.start())
        logger.info(f"P2P sync server started on port {P2P_PORT}")
    
    # Start API server for Web App if enabled
    if API_ENABLED:
        from aiohttp import web
        from handlers.calendar import create_api_app
        api_app = create_api_app()
        runner = web.AppRunner(api_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', API_PORT)
        await site.start()
        logger.info(f"API server started on port {API_PORT}")
    
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
