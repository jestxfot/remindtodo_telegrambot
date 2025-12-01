"""
Main bot module - Telegram Reminder Bot with TODO and Recurring Tasks
"""
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN, PERSISTENT_REMINDER_INTERVAL
from models.database import init_db, async_session
from models.reminder import Reminder, ReminderStatus
from services.scheduler_service import scheduler
from services.user_service import UserService
from handlers import commands_router, reminders_router, todos_router, callbacks_router
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

# Include routers
dp.include_router(commands_router)
dp.include_router(reminders_router)
dp.include_router(todos_router)
dp.include_router(callbacks_router)


async def send_reminder_notification(reminder: Reminder, is_initial: bool = True):
    """Send reminder notification to user"""
    try:
        async with async_session() as session:
            user_service = UserService(session)
            user = await user_service.get_user(reminder.user_id)
            
            if not user:
                logger.warning(f"User not found for reminder {reminder.id}")
                return
            
            timezone = user.timezone
            telegram_id = user.telegram_id
        
        # Format the message
        if is_initial:
            text = f"🔔 <b>НАПОМИНАНИЕ!</b>\n\n{format_reminder(reminder, timezone)}"
        else:
            text = f"🔔 <b>Напоминание всё ещё активно!</b>\n\n📝 {reminder.title}\n\nОтметьте выполненным или отложите."
        
        # Determine if we should send with notification sound
        disable_notification = not reminder.with_sound if not is_initial else False
        
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=get_reminder_keyboard(reminder.id, is_active=True),
            disable_notification=disable_notification
        )
        
        logger.info(f"Sent notification for reminder {reminder.id} to user {telegram_id}")
        
    except Exception as e:
        logger.error(f"Failed to send reminder notification: {e}")


async def set_bot_commands():
    """Set bot commands for the menu"""
    commands = [
        BotCommand(command="start", description="🚀 Начать работу"),
        BotCommand(command="help", description="📚 Справка"),
        BotCommand(command="newreminder", description="🔔 Новое напоминание"),
        BotCommand(command="reminders", description="📋 Список напоминаний"),
        BotCommand(command="newtodo", description="📝 Новая задача"),
        BotCommand(command="todos", description="✅ Список задач"),
        BotCommand(command="stats", description="📊 Статистика"),
        BotCommand(command="settings", description="⚙️ Настройки"),
    ]
    await bot.set_my_commands(commands)


async def on_startup():
    """Startup tasks"""
    logger.info("Starting bot...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Set bot commands
    await set_bot_commands()
    logger.info("Bot commands set")
    
    # Configure scheduler
    scheduler.set_bot(bot)
    scheduler.set_notification_callback(send_reminder_notification)
    scheduler.schedule_reminder_check(interval_seconds=10)
    scheduler.schedule_persistent_notifications(interval_seconds=PERSISTENT_REMINDER_INTERVAL)
    scheduler.schedule_snoozed_check(interval_seconds=30)
    scheduler.start()
    logger.info("Scheduler started")
    
    logger.info("Bot started successfully!")


async def on_shutdown():
    """Shutdown tasks"""
    logger.info("Shutting down...")
    scheduler.shutdown()
    await bot.session.close()
    logger.info("Bot stopped")


async def main():
    """Main function to run the bot"""
    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
