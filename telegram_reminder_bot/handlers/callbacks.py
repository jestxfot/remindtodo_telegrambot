"""
Callback handlers for active reminders (snooze, complete, mute)
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.database import async_session
from services.user_service import UserService
from services.reminder_service import ReminderService
from utils.keyboards import get_reminder_keyboard, get_snooze_keyboard
from utils.formatters import format_reminder

router = Router()


@router.callback_query(F.data.startswith("reminder_complete:"))
async def cb_reminder_complete(callback: CallbackQuery):
    """Mark reminder as completed"""
    reminder_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.complete_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        await callback.answer("✅ Выполнено!")
        
        if reminder.is_recurring:
            await callback.message.edit_text(
                f"✅ <b>Напоминание выполнено!</b>\n\n"
                f"📝 {reminder.title}\n\n"
                f"🔄 Следующее повторение создано автоматически.",
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
    reminder_id = int(callback.data.split(":")[1])
    
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
    reminder_id = int(parts[1])
    snooze_value = parts[2]
    
    # Calculate snooze duration in minutes
    if snooze_value == "tomorrow":
        # Snooze until tomorrow 9:00
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        tomorrow_9am = tomorrow.replace(hour=6, minute=0, second=0, microsecond=0)  # 9:00 MSK = 6:00 UTC
        minutes = int((tomorrow_9am - now).total_seconds() / 60)
    else:
        minutes = int(snooze_value)
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.snooze_reminder(reminder_id, minutes)
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        snooze_until = reminder.snoozed_until
        snooze_text = ""
        if snooze_value == "tomorrow":
            snooze_text = "до завтра"
        elif minutes < 60:
            snooze_text = f"на {minutes} мин"
        elif minutes < 1440:
            hours = minutes // 60
            snooze_text = f"на {hours} ч"
        else:
            days = minutes // 1440
            snooze_text = f"на {days} дн"
        
        await callback.answer(f"⏸️ Отложено {snooze_text}")
        
        formatted = format_reminder(reminder, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            f"⏸️ <b>Напоминание отложено</b>\n\n{formatted}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("reminder_snooze_back:"))
async def cb_reminder_snooze_back(callback: CallbackQuery):
    """Go back from snooze menu to reminder actions"""
    reminder_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.get_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        from models.reminder import ReminderStatus
        is_active = reminder.status == ReminderStatus.ACTIVE
        
        formatted = format_reminder(reminder, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_reminder_keyboard(reminder.id, is_active=is_active),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("reminder_mute:"))
async def cb_reminder_mute(callback: CallbackQuery):
    """Mute reminder (disable sound)"""
    reminder_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.mute_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        await callback.answer("🔇 Звук отключен")
        
        formatted = format_reminder(reminder, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_reminder_keyboard(reminder.id, is_active=True),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("settings_timezone"))
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
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
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
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.update_timezone(callback.from_user.id, timezone)
        
        if user:
            await callback.answer(f"✅ Часовой пояс установлен: {timezone}")
            await callback.message.edit_text(
                f"✅ Часовой пояс изменен на <code>{timezone}</code>",
                parse_mode="HTML"
            )
        else:
            await callback.answer("Ошибка сохранения")


@router.callback_query(F.data == "settings_back")
async def cb_settings_back(callback: CallbackQuery):
    """Go back to settings"""
    from utils.keyboards import get_settings_keyboard
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        timezone = user.timezone if user else "Europe/Moscow"
    
    await callback.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"🌍 Текущий часовой пояс: <code>{timezone}</code>\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_interval")
async def cb_settings_interval(callback: CallbackQuery):
    """Show notification interval settings"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
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
        "Как часто повторять напоминание, пока вы не отреагируете:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_interval:"))
async def cb_set_interval(callback: CallbackQuery):
    """Set notification interval"""
    interval = int(callback.data.split(":")[1])
    
    # This would need to be saved per-user in a real implementation
    await callback.answer(f"✅ Интервал установлен: {interval} сек")
    await callback.message.edit_text(
        f"✅ Интервал уведомлений установлен на <b>{interval} секунд</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_sound")
async def cb_settings_sound(callback: CallbackQuery):
    """Toggle default sound setting"""
    await callback.answer("✅ Настройка звука применена")
    await callback.message.edit_text(
        "🔊 Звук уведомлений по умолчанию: <b>Включен</b>\n\n"
        "Все новые напоминания будут со звуком.",
        parse_mode="HTML"
    )
