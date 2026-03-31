"""
Keyboard utilities for the bot - minimal version for notifications only
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_reminder_notification_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for reminder notification (complete/snooze)"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Выполнено", callback_data=f"rmc:{reminder_id}"),
        InlineKeyboardButton(text="⏸️ Отложить", callback_data=f"rsm:{reminder_id}")
    )
    
    return builder.as_markup()


def get_snooze_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for snooze options"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="5 мин", callback_data=f"rs:{reminder_id}:5"),
        InlineKeyboardButton(text="15 мин", callback_data=f"rs:{reminder_id}:15"),
        InlineKeyboardButton(text="30 мин", callback_data=f"rs:{reminder_id}:30")
    )
    builder.row(
        InlineKeyboardButton(text="1 час", callback_data=f"rs:{reminder_id}:60"),
        InlineKeyboardButton(text="Завтра", callback_data=f"rs:{reminder_id}:tomorrow")
    )
    
    return builder.as_markup()
