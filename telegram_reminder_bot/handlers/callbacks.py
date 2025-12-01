"""
Callback handlers for active reminders and settings
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.json_storage import storage
from handlers.auth import get_crypto_for_user
from utils.keyboards import get_reminder_keyboard, get_snooze_keyboard, get_settings_keyboard


async def get_user_storage(user_id: int):
    """Get user storage with authentication"""
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    return await storage.get_user_storage(user_id, crypto)
from utils.formatters import format_reminder

router = Router()


@router.callback_query(F.data.startswith("reminder_complete:"))
async def cb_reminder_complete(callback: CallbackQuery):
    """Mark reminder as completed"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    reminder = await user_storage.update_reminder(reminder_id, status="completed")
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    await callback.answer("✅ Выполнено!")
    
    if reminder.is_recurring:
        await callback.message.edit_text(
            f"✅ <b>Напоминание выполнено!</b>\n\n"
            f"📝 {reminder.title}\n\n"
            f"🔄 Следующее повторение будет создано автоматически.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"✅ <b>Напоминание выполнено!</b>\n\n"
            f"📝 {reminder.title}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("reminder_snooze_menu:"))
async def cb_reminder_snooze_menu(callback: CallbackQuery):
    """Show snooze options"""
    reminder_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "⏸️ <b>Отложить напоминание</b>\n\n"
        "На сколько отложить?",
        reply_markup=get_snooze_keyboard(reminder_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("reminder_snooze:"))
async def cb_reminder_snooze(callback: CallbackQuery):
    """Snooze reminder for specified time"""
    parts = callback.data.split(":")
    reminder_id = parts[1]
    snooze_value = parts[2]
    
    # Calculate snooze duration
    if snooze_value == "tomorrow":
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        tomorrow_9am = tomorrow.replace(hour=6, minute=0, second=0, microsecond=0)
        snoozed_until = tomorrow_9am.isoformat()
        snooze_text = "до завтра"
    else:
        minutes = int(snooze_value)
        snoozed_until = (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()
        if minutes < 60:
            snooze_text = f"на {minutes} мин"
        else:
            snooze_text = f"на {minutes // 60} ч"
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
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
    
    reminder = await user_storage.get_reminder(reminder_id)
    formatted = format_reminder(reminder, user_storage.user.timezone)
    await callback.message.edit_text(
        f"⏸️ <b>Напоминание отложено</b>\n\n{formatted}",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("reminder_snooze_back:"))
async def cb_reminder_snooze_back(callback: CallbackQuery):
    """Go back from snooze menu"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    reminder = await user_storage.get_reminder(reminder_id)
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    is_active = reminder.status == "active"
    formatted = format_reminder(reminder, user_storage.user.timezone)
    
    await callback.message.edit_text(
        formatted,
        reply_markup=get_reminder_keyboard(reminder.id, is_active=is_active),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("reminder_mute:"))
async def cb_reminder_mute(callback: CallbackQuery):
    """Mute reminder"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    reminder = await user_storage.update_reminder(reminder_id, with_sound=False)
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    await callback.answer("🔇 Звук отключен")
    
    formatted = format_reminder(reminder, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_reminder_keyboard(reminder.id, is_active=True),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_timezone")
async def cb_settings_timezone(callback: CallbackQuery):
    """Show timezone settings"""
    timezones = [
        ("Europe/Moscow", "🇷🇺 Москва (UTC+3)"),
        ("Europe/Kaliningrad", "🇷🇺 Калининград (UTC+2)"),
        ("Europe/Samara", "🇷🇺 Самара (UTC+4)"),
        ("Asia/Yekaterinburg", "🇷🇺 Екатеринбург (UTC+5)"),
        ("Asia/Novosibirsk", "🇷🇺 Новосибирск (UTC+7)"),
        ("Asia/Vladivostok", "🇷🇺 Владивосток (UTC+10)"),
        ("Europe/Kiev", "🇺🇦 Киев (UTC+2)"),
        ("Europe/Minsk", "🇧🇾 Минск (UTC+3)"),
        ("Asia/Almaty", "🇰🇿 Алматы (UTC+6)"),
    ]
    
    builder = InlineKeyboardBuilder()
    for tz_code, tz_name in timezones:
        builder.row(
            InlineKeyboardButton(text=tz_name, callback_data=f"set_timezone:{tz_code}")
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back")
    )
    
    await callback.message.edit_text(
        "🌍 <b>Выберите часовой пояс:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_timezone:"))
async def cb_set_timezone(callback: CallbackQuery):
    """Set user timezone"""
    timezone = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    await user_storage.update_user(timezone=timezone)
    
    await callback.answer(f"✅ Часовой пояс: {timezone}")
    await callback.message.edit_text(
        f"✅ Часовой пояс изменен на <code>{timezone}</code>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_back")
async def cb_settings_back(callback: CallbackQuery):
    """Go back to settings"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"🌍 Часовой пояс: <code>{user_storage.user.timezone}</code>\n"
        f"🔐 Шифрование: AES-256-GCM ✅\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_interval")
async def cb_settings_interval(callback: CallbackQuery):
    """Show notification interval settings"""
    builder = InlineKeyboardBuilder()
    intervals = [
        ("30 секунд", "30"),
        ("1 минута", "60"),
        ("2 минуты", "120"),
        ("5 минут", "300"),
    ]
    
    for name, value in intervals:
        builder.row(
            InlineKeyboardButton(text=name, callback_data=f"set_interval:{value}")
        )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back")
    )
    
    await callback.message.edit_text(
        "🔔 <b>Интервал уведомлений</b>\n\n"
        "Как часто повторять напоминание:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_interval:"))
async def cb_set_interval(callback: CallbackQuery):
    """Set notification interval"""
    interval = int(callback.data.split(":")[1])
    await callback.answer(f"✅ Интервал: {interval} сек")
    await callback.message.edit_text(
        f"✅ Интервал уведомлений: <b>{interval} секунд</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_export")
async def cb_settings_export(callback: CallbackQuery):
    """Export user data info"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    stats = await user_storage.get_statistics()
    
    await callback.message.edit_text(
        f"🔐 <b>Экспорт данных</b>\n\n"
        f"Ваши данные хранятся в зашифрованном JSON файле:\n"
        f"<code>data/user_{callback.from_user.id}.encrypted.json</code>\n\n"
        f"📊 Содержимое:\n"
        f"• Задачи: {stats['todos']['total']}\n"
        f"• Напоминания: {stats['reminders']['total']}\n"
        f"• Заметки: {stats['notes']}\n"
        f"• Пароли: {stats['passwords']}\n\n"
        f"🔒 Шифрование: AES-256-GCM\n"
        f"🔑 Ключ привязан к вашему Telegram ID",
        parse_mode="HTML"
    )
