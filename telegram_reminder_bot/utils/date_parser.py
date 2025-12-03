"""
Date and time parsing utilities
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta
import pytz
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TIMEZONE
from storage.models import RecurrenceType


# Russian month names
MONTHS_RU = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4,
    'май': 5, 'июн': 6, 'июл': 7, 'авг': 8,
    'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}

# Russian day names
DAYS_RU = {
    'понедельник': 0, 'вторник': 1, 'среда': 2, 'среду': 2,
    'четверг': 3, 'пятница': 4, 'пятницу': 4,
    'суббота': 5, 'субботу': 5, 'воскресенье': 6,
    'пн': 0, 'вт': 1, 'ср': 2, 'чт': 3, 'пт': 4, 'сб': 5, 'вс': 6
}

# Relative time patterns
RELATIVE_PATTERNS = {
    r'через\s+(\d+)\s*мин': lambda m: timedelta(minutes=int(m.group(1))),
    r'через\s+(\d+)\s*час': lambda m: timedelta(hours=int(m.group(1))),
    r'через\s+(\d+)\s*день': lambda m: timedelta(days=int(m.group(1))),
    r'через\s+(\d+)\s*дн': lambda m: timedelta(days=int(m.group(1))),
    r'через\s+(\d+)\s*недел': lambda m: timedelta(weeks=int(m.group(1))),
    r'через\s+(\d+)\s*месяц': lambda m: relativedelta(months=int(m.group(1))),
    r'через\s+полчаса': lambda m: timedelta(minutes=30),
    r'через\s+час': lambda m: timedelta(hours=1),
}

# Special time keywords
SPECIAL_TIMES = {
    'сейчас': lambda now: now,
    'сегодня': lambda now: now.replace(hour=12, minute=0, second=0, microsecond=0),
    'завтра': lambda now: (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
    'послезавтра': lambda now: (now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0),
    'утром': lambda now: now.replace(hour=9, minute=0, second=0, microsecond=0),
    'днем': lambda now: now.replace(hour=13, minute=0, second=0, microsecond=0),
    'днём': lambda now: now.replace(hour=13, minute=0, second=0, microsecond=0),
    'вечером': lambda now: now.replace(hour=19, minute=0, second=0, microsecond=0),
    'ночью': lambda now: now.replace(hour=23, minute=0, second=0, microsecond=0),
}


def parse_datetime(text: str, timezone: str = DEFAULT_TIMEZONE) -> Optional[datetime]:
    """
    Parse datetime from Russian text input
    
    Supported formats:
    - "через 5 минут", "через 2 часа", "через 3 дня"
    - "завтра", "послезавтра", "сегодня"
    - "завтра в 10:00", "сегодня в 18:30"
    - "15 января в 12:00"
    - "10.01.2024 14:30"
    - "2024-01-10 14:30"
    """
    text = text.lower().strip()
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    
    # Try relative patterns first
    for pattern, delta_func in RELATIVE_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            delta = delta_func(match)
            if isinstance(delta, relativedelta):
                return now + delta
            return now + delta
    
    # Try special times with optional time specification
    for keyword, time_func in SPECIAL_TIMES.items():
        if keyword in text:
            base_time = time_func(now)
            # Look for time specification like "в 10:00"
            time_match = re.search(r'в\s*(\d{1,2})[:\.](\d{2})', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                base_time = base_time.replace(hour=hour, minute=minute)
            
            # Handle "завтра" combined with other keywords
            if keyword != 'завтра' and 'завтра' in text:
                base_time = base_time + timedelta(days=1)
                
            return base_time
    
    # Try day of week
    for day_name, day_num in DAYS_RU.items():
        if day_name in text:
            days_ahead = day_num - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            target_date = now + timedelta(days=days_ahead)
            
            # Look for time
            time_match = re.search(r'в\s*(\d{1,2})[:\.](\d{2})', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                target_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                target_date = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            return target_date
    
    # Try Russian date format (15 января)
    for month_name, month_num in MONTHS_RU.items():
        pattern = rf'(\d{{1,2}})\s*{month_name}'
        match = re.search(pattern, text)
        if match:
            day = int(match.group(1))
            year = now.year
            
            # Check if date is in the past, move to next year
            try:
                target_date = datetime(year, month_num, day, tzinfo=tz)
                if target_date < now:
                    target_date = datetime(year + 1, month_num, day, tzinfo=tz)
            except ValueError:
                continue
            
            # Look for time
            time_match = re.search(r'в\s*(\d{1,2})[:\.](\d{2})', text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                target_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                target_date = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            return target_date
    
    # Try standard date formats
    # DD.MM.YYYY HH:MM or DD.MM.YYYY
    date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})(?:\s+(\d{1,2})[:\.](\d{2}))?', text)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3))
        if year < 100:
            year += 2000
        
        hour = int(date_match.group(4)) if date_match.group(4) else 9
        minute = int(date_match.group(5)) if date_match.group(5) else 0
        
        try:
            return datetime(year, month, day, hour, minute, tzinfo=tz)
        except ValueError:
            pass
    
    # Try just time (assume today or tomorrow if time passed)
    time_only_match = re.search(r'^(\d{1,2})[:\.](\d{2})$', text.strip())
    if time_only_match:
        hour = int(time_only_match.group(1))
        minute = int(time_only_match.group(2))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target < now:
            target += timedelta(days=1)
        return target
    
    # Last resort: try dateutil parser
    try:
        parsed = dateutil_parser.parse(text, fuzzy=True)
        if parsed.tzinfo is None:
            parsed = tz.localize(parsed)
        return parsed
    except (ValueError, TypeError):
        pass
    
    return None


def parse_recurrence(text: str) -> Tuple[RecurrenceType, Optional[int]]:
    """
    Parse recurrence pattern from text
    
    Returns tuple of (RecurrenceType, custom_interval_minutes)
    """
    text = text.lower().strip()
    
    if any(word in text for word in ['ежедневно', 'каждый день', 'каждые сутки']):
        return RecurrenceType.DAILY, None
    
    if any(word in text for word in ['еженедельно', 'каждую неделю', 'раз в неделю']):
        return RecurrenceType.WEEKLY, None
    
    if any(word in text for word in ['ежемесячно', 'каждый месяц', 'раз в месяц']):
        return RecurrenceType.MONTHLY, None
    
    if any(word in text for word in ['ежегодно', 'каждый год', 'раз в год']):
        return RecurrenceType.YEARLY, None
    
    # Custom intervals
    interval_patterns = [
        (r'каждые?\s+(\d+)\s*мин', lambda m: int(m.group(1))),
        (r'каждые?\s+(\d+)\s*час', lambda m: int(m.group(1)) * 60),
        (r'каждые?\s+(\d+)\s*дн', lambda m: int(m.group(1)) * 60 * 24),
        (r'раз\s+в\s+(\d+)\s*мин', lambda m: int(m.group(1))),
        (r'раз\s+в\s+(\d+)\s*час', lambda m: int(m.group(1)) * 60),
        (r'раз\s+в\s+(\d+)\s*дн', lambda m: int(m.group(1)) * 60 * 24),
    ]
    
    for pattern, interval_func in interval_patterns:
        match = re.search(pattern, text)
        if match:
            return RecurrenceType.CUSTOM, interval_func(match)
    
    return RecurrenceType.NONE, None


def extract_title_and_datetime(text: str, timezone: str = DEFAULT_TIMEZONE) -> Tuple[str, Optional[datetime], Optional[Tuple[RecurrenceType, Optional[int]]]]:
    """
    Extract clean title, datetime, and recurrence from natural language text.
    
    Example: "Ногти сегодня в 23:00" -> ("Ногти", datetime, None)
    Example: "Купить молоко завтра" -> ("Купить молоко", datetime, None)
    Example: "Пить воду каждые 2 часа" -> ("Пить воду", None, (CUSTOM, 120))
    
    Returns: (title, datetime, recurrence_tuple)
    """
    original_text = text.strip()
    text_lower = text.lower().strip()
    
    # Patterns to remove from title (will be used for datetime parsing)
    datetime_patterns = [
        # Time patterns
        r'\s+в\s+\d{1,2}[:\.\s]\d{2}',  # "в 10:00", "в 10.00", "в 10 00"
        r'\s+\d{1,2}[:\.\s]\d{2}',  # "10:00" at end
        # Relative patterns
        r'\s+через\s+\d+\s*(мин|час|дн|день|дней|недел|месяц)\w*',
        r'\s+через\s+полчаса',
        r'\s+через\s+час',
        # Date patterns  
        r'\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}(\s+\d{1,2}[:\.\s]\d{2})?',  # 15.01.2025 14:00
        r'\s+\d{1,2}\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\w*(\s+в\s+\d{1,2}[:\.\s]\d{2})?',
        # Day names
        r'\s+(в\s+)?(понедельник|вторник|сред[у|а]|четверг|пятниц[у|а]|суббот[у|а]|воскресенье)',
        # Special keywords  
        r'\s+сегодня',
        r'\s+завтра',
        r'\s+послезавтра',
        r'\s+утром',
        r'\s+днём',
        r'\s+днем',
        r'\s+вечером',
        r'\s+ночью',
    ]
    
    # Recurrence patterns to remove
    recurrence_patterns = [
        r'\s+ежедневно',
        r'\s+еженедельно',
        r'\s+ежемесячно',
        r'\s+ежегодно',
        r'\s+каждый\s+день',
        r'\s+каждую\s+неделю',
        r'\s+каждый\s+месяц',
        r'\s+каждый\s+год',
        r'\s+каждые?\s+\d+\s*(мин|час|дн|день|дней|недел)\w*',
        r'\s+раз\s+в\s+\d+\s*(мин|час|дн|день|дней|недел)\w*',
        r'\s+раз\s+в\s+(неделю|месяц|год)',
    ]
    
    # Parse datetime first
    parsed_dt = parse_datetime(text_lower, timezone)
    
    # Parse recurrence
    recurrence = parse_recurrence(text_lower)
    recurrence_tuple = recurrence if recurrence[0] != RecurrenceType.NONE else None
    
    # Extract clean title by removing datetime and recurrence patterns
    clean_title = original_text
    
    # Remove recurrence patterns first (case insensitive)
    for pattern in recurrence_patterns:
        clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
    
    # Remove datetime patterns (case insensitive)
    for pattern in datetime_patterns:
        clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    
    # If title is empty or too short, use original (but still clean common words)
    if len(clean_title) < 2:
        clean_title = original_text
        # Just remove very obvious time markers
        clean_title = re.sub(r'\s+в\s+\d{1,2}:\d{2}', '', clean_title)
        clean_title = re.sub(r'\s+сегодня', '', clean_title, flags=re.IGNORECASE)
        clean_title = re.sub(r'\s+завтра', '', clean_title, flags=re.IGNORECASE)
        clean_title = clean_title.strip()
    
    # Capitalize first letter
    if clean_title:
        clean_title = clean_title[0].upper() + clean_title[1:] if len(clean_title) > 1 else clean_title.upper()
    
    return clean_title, parsed_dt, recurrence_tuple


def format_relative_time(dt: datetime, timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format datetime as relative time string"""
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    
    diff = dt - now
    
    if diff.total_seconds() < 0:
        return "просрочено"
    
    seconds = int(diff.total_seconds())
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    if minutes < 1:
        return "менее минуты"
    elif minutes < 60:
        return f"через {minutes} мин"
    elif hours < 24:
        return f"через {hours} ч {minutes % 60} мин"
    elif days < 7:
        return f"через {days} дн"
    else:
        return dt.strftime("%d.%m.%Y %H:%M")
