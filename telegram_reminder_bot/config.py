"""
Configuration settings for the Telegram Reminder Bot.

The project is deployed in a few different ways:
- bot via systemd
- webapp via systemd from ``webapp/``
- ad-hoc manual runs from the repository root

Because of that, we resolve the environment file and data directory relative to
this file instead of relying on the current working directory.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency fallback
    load_dotenv = None

# Base directory
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"

if load_dotenv and ENV_FILE.exists():
    load_dotenv(ENV_FILE)
elif load_dotenv:
    load_dotenv()


def _normalize_path(path_value: str, default_path: Path) -> str:
    """
    Normalize project paths so they stay stable after restarts.

    Supported cases:
    - absolute paths: returned as-is
    - ``./data`` or ``data``: resolved relative to the repo root
    - accidentally missing leading slash, e.g. ``root/telegram_reminder_bot/data``:
      treated as ``/root/telegram_reminder_bot/data``
    """
    if not path_value:
        return str(default_path)

    expanded = Path(path_value).expanduser()
    if expanded.is_absolute():
        return str(expanded)

    if path_value.startswith(("root/", "home/")):
        return f"/{path_value.lstrip('/')}"

    return str((BASE_DIR / expanded).resolve())

# Bot settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Data storage
DATA_DIR = _normalize_path(os.getenv("DATA_DIR", ""), BASE_DIR / "data")

# Encryption settings
ENCRYPTION_ALGORITHM = "AES-256-GCM"
PBKDF2_ITERATIONS = 600000

# Reminder settings
PERSISTENT_REMINDER_INTERVAL = 300  # Seconds between persistent reminders (default 5 min)
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

# Web App settings
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # URL for Telegram Web App calendar
API_PORT = int(os.getenv("API_PORT", "8080"))  # Port for API server
API_ENABLED = os.getenv("API_ENABLED", "false").lower() == "true"
