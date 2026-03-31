"""
Global Moscow timezone utilities.

All datetime operations should use these functions to ensure consistent MSK time.
"""
from datetime import datetime, timedelta
import pytz

# Moscow timezone - the only timezone used in this app
MSK = pytz.timezone("Europe/Moscow")


def now() -> datetime:
    """Get current time in Moscow timezone (aware datetime)"""
    return datetime.now(MSK)


def now_str() -> str:
    """Get current time in Moscow as ISO string (for storage)"""
    return datetime.now(MSK).strftime('%Y-%m-%dT%H:%M:%S')


def to_msk(dt: datetime) -> datetime:
    """Convert any datetime to Moscow timezone"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(MSK)
    else:
        # Assume naive datetime is already in MSK
        return MSK.localize(dt)


def parse_dt(dt_str: str) -> datetime:
    """Parse ISO datetime string and localize to MSK"""
    if not dt_str:
        return None
    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    return to_msk(dt)


def format_dt(dt: datetime) -> str:
    """Format datetime to ISO string for storage (without tz info)"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(MSK)
    return dt.strftime('%Y-%m-%dT%H:%M:%S')


def normalize_dt_str(dt_str: str | None) -> str | None:
    """
    Normalize an incoming ISO datetime string to MSK and storage format.

    - Accepts strings with/without timezone suffix (+03:00 / +00:00 / Z)
    - Returns '%Y-%m-%dT%H:%M:%S' (no tz suffix) or None
    """
    if not dt_str:
        return None
    try:
        return format_dt(parse_dt(dt_str))
    except Exception:
        return dt_str


def tomorrow_at(hour: int = 9, minute: int = 0) -> datetime:
    """Get tomorrow at a specific MSK time."""
    base = now() + timedelta(days=1)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)
