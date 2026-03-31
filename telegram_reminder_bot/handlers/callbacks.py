"""
Callback handlers for active reminders and settings
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.sqlite_storage import storage
from handlers.auth import get_crypto_for_user
from utils.keyboards import get_reminder_keyboard, get_snooze_keyboard, get_settings_keyboard
from utils.timezone import format_dt, now, now_str, tomorrow_at


async def get_user_storage(user_id: int):
    """Get user storage with authentication"""
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    return await storage.get_user_storage(user_id, crypto)
from utils.formatters import format_reminder

router = Router()


@router.callback_query(F.data.startswith("rmc:"))
async def cb_reminder_complete(callback: CallbackQuery):
    """Mark reminder as completed (rmc = reminder complete)"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    reminder, was_archived = await user_storage.complete_reminder(reminder_id)
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    await callback.answer("✅ Выполнено!")
    
    if was_archived:
        if reminder.is_recurring:
            # Повторяющееся напоминание завершено (достигнута дата окончания)
            await callback.message.edit_text(
                f"✅ <b>Напоминание завершено!</b>\n\n"
                f"📝 {reminder.title}\n"
                f"🔄 Выполнено раз: {reminder.recurrence_count}\n\n"
                f"📦 Перемещено в архив (достигнута дата окончания)",
                parse_mode="HTML"
            )
        else:
            # Неповторяющееся напоминание выполнено
            await callback.message.edit_text(
                f"✅ <b>Напоминание выполнено!</b>\n\n"
                f"📝 {reminder.title}\n\n"
                f"📦 Перемещено в архив",
                parse_mode="HTML"
            )
    elif reminder.is_recurring:
        from utils.formatters import format_reminder
        formatted = format_reminder(reminder, user_storage.user.timezone)
        await callback.message.edit_text(
            f"✅ <b>Выполнено! Следующее:</b>\n\n{formatted}",
            reply_markup=get_reminder_keyboard(reminder.id, is_recurring=True),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("rma:"))
async def cb_reminder_archive(callback: CallbackQuery):
    """Archive reminder (rma = reminder archive)"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    reminder = await user_storage.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    archived = await user_storage.archive_reminder(reminder_id)
    
    if archived:
        await callback.answer("📦 Напоминание перемещено в архив")
        await callback.message.edit_text(
            f"📦 Напоминание «{reminder.title}» перемещено в архив\n\n"
            "Используйте /archive для просмотра"
        )
    else:
        await callback.answer("Ошибка архивирования")


@router.callback_query(F.data.startswith("rsm:"))
async def cb_reminder_snooze_menu(callback: CallbackQuery):
    """Show snooze options (rsm = reminder snooze menu)"""
    reminder_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "⏸️ <b>Отложить напоминание</b>\n\n"
        "На сколько отложить?",
        reply_markup=get_snooze_keyboard(reminder_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rs:"))
async def cb_reminder_snooze(callback: CallbackQuery):
    """Snooze reminder (rs = reminder snooze)"""
    parts = callback.data.split(":")
    reminder_id = parts[1]
    snooze_value = parts[2]
    
    # Calculate snooze duration
    if snooze_value == "tomorrow":
        snoozed_until = format_dt(tomorrow_at(9, 0))
        snooze_text = "до завтра"
    else:
        minutes = int(snooze_value)
        snoozed_until = format_dt(now() + timedelta(minutes=minutes))
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


@router.callback_query(F.data.startswith("rsb:"))
async def cb_reminder_snooze_back(callback: CallbackQuery):
    """Go back from snooze menu (rsb = reminder snooze back)"""
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


@router.callback_query(F.data.startswith("rmm:"))
async def cb_reminder_mute(callback: CallbackQuery):
    """Mute reminder (rmm = reminder mute)"""
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
        ("1 минута", "1"),
        ("5 минут", "5"),
        ("10 минут", "10"),
        ("30 минут", "30"),
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
        "Как часто повторять постоянные напоминания:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("set_interval:"))
async def cb_set_interval(callback: CallbackQuery):
    """Set notification interval"""
    interval_minutes = int(callback.data.split(":")[1])
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return

    await user_storage.update_user(reminder_interval_minutes=interval_minutes)
    await user_storage.update_persistent_reminder_interval(interval_minutes * 60)
    await callback.answer(f"✅ Интервал: {interval_minutes} мин")
    await callback.message.edit_text(
        f"✅ Интервал уведомлений: <b>{interval_minutes} минут</b>",
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
        f"Ваши данные хранятся в зашифрованной SQLite базе:\n"
        f"<code>data/storage.sqlite3</code>\n\n"
        f"Для переноса и резервной копии используется зашифрованный JSON-экспорт.\n\n"
        f"📊 Содержимое:\n"
        f"• Задачи: {stats['todos']['total']}\n"
        f"• Напоминания: {stats['reminders']['total']}\n"
        f"• Заметки: {stats['notes']}\n"
        f"• Пароли: {stats['passwords']}\n\n"
        f"🔒 Шифрование: AES-256-GCM\n"
        f"🔑 Доступ защищён вашим мастер-паролем",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_backup")
async def cb_settings_backup(callback: CallbackQuery):
    """Show backup settings"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    user = user_storage.user
    backup_enabled = getattr(user, 'backup_enabled', False)
    backup_hour = getattr(user, 'backup_hour', 3)
    last_backup = getattr(user, 'last_backup_at', None)
    
    status = "✅ Включено" if backup_enabled else "❌ Выключено"
    last_backup_str = last_backup[:10] if last_backup else "никогда"
    
    builder = InlineKeyboardBuilder()
    
    if backup_enabled:
        builder.row(
            InlineKeyboardButton(text="❌ Выключить бэкапы", callback_data="backup_toggle:off")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="✅ Включить бэкапы", callback_data="backup_toggle:on")
        )
    
    builder.row(
        InlineKeyboardButton(text="🕐 Время отправки", callback_data="backup_time")
    )
    builder.row(
        InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="backup_now")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_back")
    )
    
    await callback.message.edit_text(
        f"💾 <b>Ежедневные бэкапы</b>\n\n"
        f"Статус: {status}\n"
        f"🕐 Время отправки: {backup_hour:02d}:00 МСК\n"
        f"📅 Последний бэкап: {last_backup_str}\n\n"
        f"Бэкап — зашифрованный файл с вашими данными,\n"
        f"который бот отправляет вам раз в день.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("backup_toggle:"))
async def cb_backup_toggle(callback: CallbackQuery):
    """Toggle backup on/off"""
    action = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    enabled = action == "on"
    await user_storage.update_user(backup_enabled=enabled)
    
    if enabled:
        await callback.answer("✅ Ежедневные бэкапы включены!")
    else:
        await callback.answer("❌ Ежедневные бэкапы выключены")
    
    # Refresh settings page
    await cb_settings_backup(callback)


@router.callback_query(F.data == "backup_time")
async def cb_backup_time(callback: CallbackQuery):
    """Show backup time selection"""
    builder = InlineKeyboardBuilder()
    
    # Hours grouped
    for row_start in range(0, 24, 4):
        row_buttons = []
        for h in range(row_start, min(row_start + 4, 24)):
            row_buttons.append(
                InlineKeyboardButton(text=f"{h:02d}:00", callback_data=f"backup_hour:{h}")
            )
        builder.row(*row_buttons)
    
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="settings_backup")
    )
    
    await callback.message.edit_text(
        "🕐 <b>Выберите время отправки бэкапа</b>\n\n"
        "Время указано в МСК.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("backup_hour:"))
async def cb_backup_hour_set(callback: CallbackQuery):
    """Set backup hour"""
    hour = int(callback.data.split(":")[1])
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    await user_storage.update_user(backup_hour=hour)
    await callback.answer(f"✅ Время бэкапа: {hour:02d}:00 МСК")
    
    # Return to backup settings
    await cb_settings_backup(callback)


@router.callback_query(F.data == "backup_now")
async def cb_backup_now(callback: CallbackQuery):
    """Send backup right now"""
    from aiogram.types import BufferedInputFile
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    await callback.answer("📤 Создаю бэкап...")
    
    try:
        stats = await user_storage.get_statistics()
        user_id = callback.from_user.id

        encrypted_content = storage.export_data(user_id)
        if not encrypted_content:
            await callback.message.answer("❌ Данные пользователя не найдены")
            return

        file_bytes = encrypted_content.encode('utf-8')
        date_str = now().strftime("%Y-%m-%d_%H-%M")
        filename = f"backup_{user_id}_{date_str}.json"
        
        input_file = BufferedInputFile(file_bytes, filename=filename)
        
        await callback.message.answer_document(
            document=input_file,
            caption=(
                f"📦 <b>Ваш бэкап</b>\n\n"
                f"📅 Дата: {date_str}\n"
                f"📊 Задач: {stats['todos']['total']}\n"
                f"🔔 Напоминаний: {stats['reminders']['total']}\n"
                f"📝 Заметок: {stats['notes']}\n"
                f"🔐 Паролей: {stats['passwords']}\n\n"
                f"<i>Файл зашифрован AES-256-GCM.\n"
                f"Сохраните его в надёжном месте.</i>"
            ),
            parse_mode="HTML"
        )
        
        await user_storage.update_user(last_backup_at=now_str())
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка создания бэкапа: {e}")
