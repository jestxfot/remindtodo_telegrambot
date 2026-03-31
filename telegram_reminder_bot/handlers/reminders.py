"""
Reminder handlers
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.json_storage import storage
from storage.models import RecurrenceType, ReminderStatus
from handlers.auth import get_crypto_for_user


async def get_user_storage(user_id: int):
    """Get user storage with authentication"""
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    return await storage.get_user_storage(user_id, crypto)
from utils.keyboards import (
    get_main_keyboard, 
    get_cancel_keyboard,
    get_reminder_keyboard,
    get_reminders_list_keyboard,
    get_recurrence_keyboard,
    get_custom_recurrence_keyboard
)
from utils.formatters import format_interval
from utils.date_parser import parse_datetime
from utils.formatters import format_reminder, format_reminders_list
from utils.timezone import format_dt

router = Router()


class ReminderStates(StatesGroup):
    """States for reminder creation and editing"""
    waiting_for_text = State()
    waiting_for_time = State()
    waiting_for_custom_interval = State()
    editing_title = State()
    editing_time = State()


async def show_reminders_list(message: Message):
    """Show list of user's reminders"""
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    reminders = await user_storage.get_reminders()
    
    text = format_reminders_list(reminders, user_storage.user.timezone)
    keyboard = get_reminders_list_keyboard(reminders)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def start_create_reminder(message: Message, state: FSMContext):
    """Start reminder creation process"""
    await state.set_state(ReminderStates.waiting_for_text)
    
    await message.answer(
        "🔔 <b>Новое напоминание</b>\n\n"
        "Напишите текст напоминания и время.\n\n"
        "<b>Примеры:</b>\n"
        "• <code>Позвонить маме завтра в 10:00</code>\n"
        "• <code>Встреча через 2 часа</code>\n"
        "• <code>Оплатить счёт 15.01 в 12:00</code>\n\n"
        "Или просто напишите текст, а время укажите следующим сообщением.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("newreminder"))
async def cmd_new_reminder(message: Message, state: FSMContext):
    """Handle /newreminder command"""
    await start_create_reminder(message, state)


@router.message(Command("reminders"))
async def cmd_reminders(message: Message):
    """Handle /reminders command"""
    await show_reminders_list(message)


@router.message(ReminderStates.waiting_for_text)
async def process_reminder_text(message: Message, state: FSMContext):
    """Process reminder text input"""
    from utils.date_parser import extract_title_and_datetime
    
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание напоминания отменено", reply_markup=get_main_keyboard())
        return
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    timezone = user_storage.user.timezone
    
    # Extract clean title and datetime from natural language
    clean_title, remind_at, recurrence_tuple = extract_title_and_datetime(text, timezone)
    
    if remind_at:
        # Successfully parsed datetime from text
        recurrence_type = None
        recurrence_interval = None
        
        if recurrence_tuple:
            recurrence_type = recurrence_tuple[0].value
            recurrence_interval = recurrence_tuple[1]
        
        reminder = await user_storage.create_reminder(
            title=clean_title,
            remind_at=format_dt(remind_at),
            is_persistent=True,
            with_sound=True,
            recurrence_type=recurrence_type if recurrence_type else "none",
            recurrence_interval=recurrence_interval
        )
        
        await state.clear()
        
        formatted = format_reminder(reminder, timezone)
        await message.answer(
            f"✅ Напоминание создано!\n\n{formatted}",
            reply_markup=get_reminder_keyboard(reminder.id),
            parse_mode="HTML"
        )
        
        await message.answer(
            "Используйте кнопки для настройки повторения.",
            reply_markup=get_main_keyboard()
        )
    else:
        # Could not parse datetime, ask for it separately
        await state.update_data(title=clean_title)
        await state.set_state(ReminderStates.waiting_for_time)
        
        await message.answer(
            f"📝 Текст: <b>{clean_title}</b>\n\n"
            "Теперь укажите время напоминания:\n\n"
            "<b>Примеры:</b>\n"
            "• <code>завтра в 10:00</code>\n"
            "• <code>через 30 минут</code>\n"
            "• <code>15.01.2025 14:00</code>",
            parse_mode="HTML"
        )


@router.message(ReminderStates.waiting_for_time)
async def process_reminder_time(message: Message, state: FSMContext):
    """Process reminder time input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание напоминания отменено", reply_markup=get_main_keyboard())
        return
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    timezone = user_storage.user.timezone
    
    remind_at = parse_datetime(text, timezone)
    
    if not remind_at:
        await message.answer(
            "⚠️ Не удалось распознать время.\n\n"
            "Попробуйте указать время в одном из форматов:\n"
            "• <code>завтра в 10:00</code>\n"
            "• <code>через 2 часа</code>\n"
            "• <code>15.01.2025 14:00</code>",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    title = data.get("title", "Напоминание")
    
    reminder = await user_storage.create_reminder(
        title=title,
        remind_at=format_dt(remind_at),
        is_persistent=True,
        with_sound=True
    )
    
    await state.clear()
    
    formatted = format_reminder(reminder, timezone)
    await message.answer(
        f"✅ Напоминание создано!\n\n{formatted}",
        reply_markup=get_reminder_keyboard(reminder.id),
        parse_mode="HTML"
    )
    
    await message.answer(
        "Используйте кнопки для настройки повторения.",
        reply_markup=get_main_keyboard()
    )


@router.callback_query(F.data.startswith("rmv:"))
async def cb_reminder_view(callback: CallbackQuery):
    """View reminder details (rmv = reminder view)"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    reminder = await user_storage.get_reminder(reminder_id)
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    formatted = format_reminder(reminder, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_reminder_keyboard(reminder.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rmr:"))
async def cb_reminder_recurrence(callback: CallbackQuery):
    """Show recurrence options (rmr = reminder recurrence)"""
    reminder_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "🔄 <b>Настройка повторения</b>\n\n"
        "Выберите как часто повторять напоминание:",
        reply_markup=get_recurrence_keyboard(reminder_id, "reminder"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rme:"))
async def cb_reminder_edit(callback: CallbackQuery):
    """Show edit options for reminder (rme = reminder edit)"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    reminder_id = callback.data.split(":")[1]
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Изменить текст", callback_data=f"rmet:{reminder_id}"),
        InlineKeyboardButton(text="🕐 Изменить время", callback_data=f"rmeti:{reminder_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"rmv:{reminder_id}")
    )
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование напоминания</b>\n\n"
        "Что хотите изменить?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rmet:"))
async def cb_reminder_edit_title(callback: CallbackQuery, state: FSMContext):
    """Start editing reminder title (rmet = reminder edit title)"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    reminder = await user_storage.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    await state.update_data(editing_reminder_id=reminder_id)
    await state.set_state(ReminderStates.editing_title)
    
    await callback.message.edit_text(
        f"📝 <b>Редактирование текста</b>\n\n"
        f"Текущий текст:\n<code>{reminder.title}</code>\n\n"
        f"Введите новый текст или /cancel для отмены:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rmeti:"))
async def cb_reminder_edit_time(callback: CallbackQuery, state: FSMContext):
    """Start editing reminder time (rmeti = reminder edit time)"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    reminder = await user_storage.get_reminder(reminder_id)
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    await state.update_data(editing_reminder_id=reminder_id)
    await state.set_state(ReminderStates.editing_time)
    
    from utils.formatters import format_datetime
    current_time = format_datetime(reminder.remind_at, user_storage.user.timezone)
    
    await callback.message.edit_text(
        f"🕐 <b>Редактирование времени</b>\n\n"
        f"Текущее время: <code>{current_time}</code>\n\n"
        f"Введите новое время:\n"
        f"• <code>завтра в 10:00</code>\n"
        f"• <code>через 2 часа</code>\n"
        f"• <code>15.01.2025 14:00</code>\n\n"
        f"Или /cancel для отмены",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ReminderStates.editing_title)
async def process_edit_title(message: Message, state: FSMContext):
    """Process new title for reminder"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Редактирование отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    reminder_id = data.get("editing_reminder_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    reminder = await user_storage.update_reminder(reminder_id, title=message.text.strip())
    await state.clear()
    
    if reminder:
        formatted = format_reminder(reminder, user_storage.user.timezone)
        await message.answer(
            f"✅ Текст обновлён!\n\n{formatted}",
            reply_markup=get_reminder_keyboard(reminder.id),
            parse_mode="HTML"
        )
    else:
        await message.answer("Напоминание не найдено", reply_markup=get_main_keyboard())


@router.message(ReminderStates.editing_time)
async def process_edit_time(message: Message, state: FSMContext):
    """Process new time for reminder"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Редактирование отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    reminder_id = data.get("editing_reminder_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    new_time = parse_datetime(message.text, user_storage.user.timezone)
    
    if not new_time:
        await message.answer(
            "⚠️ Не удалось распознать время.\n\n"
            "Попробуйте:\n"
            "• <code>завтра в 10:00</code>\n"
            "• <code>через 2 часа</code>",
            parse_mode="HTML"
        )
        return
    
    reminder = await user_storage.update_reminder(reminder_id, remind_at=format_dt(new_time))
    await state.clear()
    
    if reminder:
        formatted = format_reminder(reminder, user_storage.user.timezone)
        await message.answer(
            f"✅ Время обновлено!\n\n{formatted}",
            reply_markup=get_reminder_keyboard(reminder.id),
            parse_mode="HTML"
        )
    else:
        await message.answer("Напоминание не найдено", reply_markup=get_main_keyboard())


@router.callback_query(F.data.startswith("recurrence_custom:"))
async def cb_recurrence_custom(callback: CallbackQuery):
    """Show custom recurrence interval options"""
    parts = callback.data.split(":")
    item_id = parts[1]
    item_type = parts[2] if len(parts) > 2 else "reminder"
    
    await callback.message.edit_text(
        "⚙️ <b>Свой интервал повторения</b>\n\n"
        "Выберите как часто повторять или введите вручную:",
        reply_markup=get_custom_recurrence_keyboard(item_id, item_type),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rc:"))
async def cb_recurrence_custom_set(callback: CallbackQuery):
    """Set custom recurrence interval from predefined options"""
    # Format: rc:item_id:t:value:unit (t=r/t, unit=d/w/m)
    parts = callback.data.split(":")
    item_id = parts[1]
    item_type = "reminder" if parts[2] == "r" else "todo"
    value = int(parts[3])
    unit = parts[4]
    
    # Конвертируем в минуты
    if unit == "d":  # days
        interval_minutes = value * 1440
    elif unit == "w":  # weeks
        interval_minutes = value * 10080
    elif unit == "m":  # months
        interval_minutes = value * 43200
    elif unit == "h":  # hours
        interval_minutes = value * 60
    else:
        interval_minutes = value
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    if item_type == "reminder":
        reminder = await user_storage.update_reminder(
            item_id,
            recurrence_type="custom",
            recurrence_interval=interval_minutes
        )
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        await callback.answer(f"✅ Повторение: {format_interval(interval_minutes)}")
        
        formatted = format_reminder(reminder, user_storage.user.timezone)
        await callback.message.edit_text(
            formatted,
            reply_markup=get_reminder_keyboard(reminder.id, is_recurring=True),
            parse_mode="HTML"
        )
    else:
        # Для задач - обрабатывается в todos.py
        await callback.answer("Интервал установлен")


@router.callback_query(F.data.startswith("ri:"))
async def cb_recurrence_input(callback: CallbackQuery, state: FSMContext):
    """Start custom interval input (ri = recurrence input)"""
    parts = callback.data.split(":")
    item_id = parts[1]
    item_type = "reminder" if parts[2] == "r" else "todo"
    
    await state.update_data(recurrence_item_id=item_id, recurrence_item_type=item_type)
    await state.set_state(ReminderStates.waiting_for_custom_interval)
    
    await callback.message.edit_text(
        "✏️ <b>Введите интервал повторения</b>\n\n"
        "Примеры:\n"
        "• <code>2 дня</code>\n"
        "• <code>3 недели</code>\n"
        "• <code>2 месяца</code>\n"
        "• <code>4 часа</code>\n"
        "• <code>90 минут</code>\n\n"
        "Или отправьте /cancel для отмены",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rb:"))
async def cb_recurrence_back(callback: CallbackQuery):
    """Go back to recurrence menu (rb = recurrence back)"""
    parts = callback.data.split(":")
    item_id = parts[1]
    item_type = "reminder" if parts[2] == "r" else "todo"
    
    await callback.message.edit_text(
        "🔄 <b>Настройка повторения</b>\n\n"
        "Выберите как часто повторять:",
        reply_markup=get_recurrence_keyboard(item_id, item_type),
        parse_mode="HTML"
    )


@router.message(ReminderStates.waiting_for_custom_interval)
async def process_custom_interval(message: Message, state: FSMContext):
    """Process custom interval input"""
    import re
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_keyboard())
        return
    
    text = message.text.lower().strip()
    
    # Парсим интервал
    patterns = [
        (r'(\d+)\s*(?:мин|минут)', lambda m: int(m.group(1))),
        (r'(\d+)\s*(?:час|часа|часов)', lambda m: int(m.group(1)) * 60),
        (r'(\d+)\s*(?:день|дня|дней|дн)', lambda m: int(m.group(1)) * 1440),
        (r'(\d+)\s*(?:недел|нед)', lambda m: int(m.group(1)) * 10080),
        (r'(\d+)\s*(?:месяц|месяца|месяцев|мес)', lambda m: int(m.group(1)) * 43200),
    ]
    
    interval_minutes = None
    for pattern, calc in patterns:
        match = re.search(pattern, text)
        if match:
            interval_minutes = calc(match)
            break
    
    if not interval_minutes:
        await message.answer(
            "⚠️ Не удалось распознать интервал.\n\n"
            "Примеры: <code>2 дня</code>, <code>3 недели</code>, <code>4 часа</code>",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    item_id = data.get("recurrence_item_id")
    item_type = data.get("recurrence_item_type", "reminder")
    
    await state.clear()
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    if item_type == "reminder":
        reminder = await user_storage.update_reminder(
            item_id,
            recurrence_type="custom",
            recurrence_interval=interval_minutes
        )
        
        if not reminder:
            await message.answer("Напоминание не найдено", reply_markup=get_main_keyboard())
            return
        
        formatted = format_reminder(reminder, user_storage.user.timezone)
        await message.answer(
            f"✅ Повторение установлено: {format_interval(interval_minutes)}\n\n{formatted}",
            reply_markup=get_reminder_keyboard(reminder.id, is_recurring=True),
            parse_mode="HTML"
        )
    
    await message.answer("Готово!", reply_markup=get_main_keyboard())


@router.callback_query(F.data.startswith("rcs:"))
async def cb_recurrence_set(callback: CallbackQuery):
    """Set recurrence for reminder"""
    parts = callback.data.split(":")
    reminder_id = parts[1]
    recurrence_str = parts[2]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    reminder = await user_storage.update_reminder(
        reminder_id, 
        recurrence_type=recurrence_str
    )
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    recurrence_names = {
        "none": "без повторения",
        "daily": "ежедневно",
        "weekly": "еженедельно",
        "monthly": "ежемесячно",
        "yearly": "ежегодно"
    }
    
    await callback.answer(f"✅ Повторение: {recurrence_names.get(recurrence_str, 'установлено')}")
    
    formatted = format_reminder(reminder, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_reminder_keyboard(reminder.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rmd:"))
async def cb_reminder_delete(callback: CallbackQuery):
    """Delete reminder (rmd = reminder delete)"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    deleted = await user_storage.delete_reminder(reminder_id)
    
    if deleted:
        await callback.answer("🗑️ Напоминание удалено")
        await callback.message.edit_text("Напоминание удалено")
    else:
        await callback.answer("Напоминание не найдено")


@router.callback_query(F.data.startswith("rmb:"))
async def cb_reminder_back(callback: CallbackQuery):
    """Go back to reminder view (rmb = reminder back)"""
    reminder_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    reminder = await user_storage.get_reminder(reminder_id)
    
    if not reminder:
        await callback.answer("Напоминание не найдено")
        return
    
    formatted = format_reminder(reminder, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_reminder_keyboard(reminder.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "rn")
async def cb_reminder_new(callback: CallbackQuery, state: FSMContext):
    """Start creating new reminder from callback (rn = reminder new)"""
    await callback.message.delete()
    await start_create_reminder(callback.message, state)


@router.callback_query(F.data.startswith("rpg:"))
async def cb_reminders_page(callback: CallbackQuery):
    """Handle reminders pagination (rpg = reminders page)"""
    page = int(callback.data.split(":")[1])
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    reminders = await user_storage.get_reminders()
    
    text = format_reminders_list(reminders, user_storage.user.timezone)
    keyboard = get_reminders_list_keyboard(reminders, page)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
