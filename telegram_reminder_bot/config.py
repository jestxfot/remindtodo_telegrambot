"""
Configuration settings for the Telegram Reminder Bot
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Data storage
DATA_DIR = os.getenv("DATA_DIR", str(BASE_DIR / "data"))

# Encryption settings
ENCRYPTION_ALGORITHM = "AES-256-GCM"
PBKDF2_ITERATIONS = 600000

# Reminder settings
PERSISTENT_REMINDER_INTERVAL = 60  # Seconds between persistent reminders
MAX_SNOOZE_TIMES = 10
DEFAULT_SNOOZE_MINUTES = 5

# Timezone
DEFAULT_TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# P2P Sync settings
P2P_ENABLED = os.getenv("P2P_ENABLED", "false").lower() == "true"
P2P_PORT = int(os.getenv("P2P_PORT", "8765"))
P2P_SECRET = os.getenv("P2P_SECRET", "")  # Shared secret for P2P auth

# Password vault settings
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_SPECIAL = True

# Session settings
SESSION_DURATIONS = {
    "30min": 30,           # 30 минут
    "2hours": 120,         # 2 часа
    "1day": 1440,          # 1 день
    "1week": 10080,        # 1 неделя
    "1month": 43200,       # 1 месяц
}
DEFAULT_SESSION_DURATION = "30min"
