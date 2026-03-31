"""
Notification handlers - callbacks for reminder notifications
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.sqlite_storage import storage
from handlers.auth import get_crypto_for_user
from utils.keyboards import get_snooze_keyboard
from utils.timezone import format_dt, now, tomorrow_at

router = Router()


async def get_user_storage(user_id: int):
    """Get user storage with authentication"""
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    try:
        return await storage.get_user_storage(user_id, crypto)
    except ValueError as e:
        print(f"[ERROR] Failed to load storage for user {user_id}: {e}")
        return None


@router.callback_query(F.data.startswith("rmc:"))
async def cb_reminder_complete(callback: CallbackQuery):
    """Mark reminder as completed"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Откройте приложение для разблокировки", show_alert=True)
        return
    
    reminder, was_archived = await user_storage.complete_reminder(reminder_id)
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    await callback.answer("✅ Выполнено!")
    
    if was_archived:
        await callback.message.edit_text(
            f"✅ <b>Выполнено!</b>\n\n"
            f"📝 {reminder.title}\n\n"
            f"📦 Перемещено в архив",
            parse_mode="HTML"
        )
    elif reminder.is_recurring:
        from utils.formatters import format_datetime
        next_time = format_datetime(reminder.remind_at, user_storage.user.timezone)
        await callback.message.edit_text(
            f"✅ <b>Выполнено!</b>\n\n"
            f"📝 {reminder.title}\n"
            f"🔄 Следующее: {next_time}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("rsm:"))
async def cb_reminder_snooze_menu(callback: CallbackQuery):
    """Show snooze options"""
    reminder_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "⏸️ <b>На сколько отложить?</b>",
        reply_markup=get_snooze_keyboard(reminder_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rs:"))
async def cb_reminder_snooze(callback: CallbackQuery):
    """Snooze reminder"""
    parts = callback.data.split(":")
    reminder_id = parts[1]
    snooze_value = parts[2]

    # Calculate snooze duration in Moscow timezone
    current_time = now()
    if snooze_value == "tomorrow":
        snoozed_until = format_dt(tomorrow_at(9, 0))
        snooze_text = "до завтра"
    else:
        minutes = int(snooze_value)
        snoozed_until = format_dt(current_time + timedelta(minutes=minutes))
        if minutes < 60:
            snooze_text = f"на {minutes} мин"
        else:
            snooze_text = f"на {minutes // 60} ч"
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Откройте приложение для разблокировки", show_alert=True)
        return
    
    reminder = await user_storage.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    await user_storage.update_reminder(
        reminder_id,
        status="snoozed",
        snoozed_until=snoozed_until,
        snooze_count=reminder.snooze_count + 1
    )
    
    await callback.answer(f"⏸️ Отложено {snooze_text}")
    await callback.message.edit_text(
        f"⏸️ <b>Отложено {snooze_text}</b>\n\n"
        f"📝 {reminder.title}",
        parse_mode="HTML"
    )
