"""
Configuration settings for the Telegram Reminder Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./reminder_bot.db")

# Reminder settings
PERSISTENT_REMINDER_INTERVAL = 60  # Seconds between persistent reminders
MAX_SNOOZE_TIMES = 10  # Maximum number of snooze attempts
DEFAULT_SNOOZE_MINUTES = 5  # Default snooze duration in minutes

# Timezone (default Moscow)
DEFAULT_TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
