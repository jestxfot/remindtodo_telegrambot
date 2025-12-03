"""
Todo handlers with archive support
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.json_storage import storage
from storage.models import TodoPriority, TodoStatus, RecurrenceType
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
    get_todo_keyboard,
    get_todos_list_keyboard,
    get_priority_keyboard,
    get_recurrence_keyboard,
    get_custom_recurrence_keyboard
)
from utils.date_parser import parse_datetime
from utils.formatters import format_todo, format_todos_list, format_interval

router = Router()


class TodoStates(StatesGroup):
    """States for todo creation"""
    waiting_for_title = State()
    setting_deadline = State()
    setting_recurrence = State()
    setting_recurrence_end = State()
    waiting_for_custom_interval = State()


async def show_todos_list(message: Message):
    """Show list of user's todos"""
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    todos = await user_storage.get_todos()
    
    text = format_todos_list(todos, user_storage.user.timezone)
    keyboard = get_todos_list_keyboard(todos)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def start_create_todo(message: Message, state: FSMContext):
    """Start todo creation process"""
    await state.set_state(TodoStates.waiting_for_title)
    
    await message.answer(
        "📝 <b>Новая задача</b>\n\n"
        "Напишите название задачи:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("newtodo"))
async def cmd_new_todo(message: Message, state: FSMContext):
    """Handle /newtodo command"""
    await start_create_todo(message, state)


@router.message(Command("todos"))
async def cmd_todos(message: Message):
    """Handle /todos command"""
    await show_todos_list(message)


@router.message(TodoStates.waiting_for_title)
async def process_todo_title(message: Message, state: FSMContext):
    """Process todo title input"""
    from utils.date_parser import extract_title_and_datetime
    
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание задачи отменено", reply_markup=get_main_keyboard())
        return
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    timezone = user_storage.user.timezone
    
    # Extract clean title and datetime from natural language
    clean_title, deadline, recurrence_tuple = extract_title_and_datetime(text, timezone)
    
    # Prepare recurrence settings
    recurrence_type = None
    recurrence_interval = None
    if recurrence_tuple:
        recurrence_type = recurrence_tuple[0].value
        recurrence_interval = recurrence_tuple[1]
    
    # Create todo with extracted data
    todo = await user_storage.create_todo(
        title=clean_title,
        deadline=deadline.isoformat() if deadline else None,
        recurrence=recurrence_type,
        recurrence_interval=recurrence_interval
    )
    
    await state.clear()
    
    formatted = format_todo(todo, timezone)
    await message.answer(
        f"✅ Задача создана!\n\n{formatted}",
        reply_markup=get_todo_keyboard(todo.id, is_recurring=todo.is_recurring),
        parse_mode="HTML"
    )
    
    await message.answer(
        "Используйте кнопки для настройки приоритета, дедлайна и т.д.",
        reply_markup=get_main_keyboard()
    )


@router.callback_query(F.data.startswith("tv:"))
async def cb_todo_view(callback: CallbackQuery):
    """View todo details (tv = todo view)"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    todo = await user_storage.get_todo(todo_id)
    
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    formatted = format_todo(todo, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_todo_keyboard(todo.id, is_recurring=todo.is_recurring),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tc:"))
async def cb_todo_complete(callback: CallbackQuery):
    """Mark todo as completed (tc = todo complete)"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    todo, was_archived = await user_storage.complete_todo(todo_id)
    
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    if was_archived:
        await callback.answer("✅ Задача завершена и перемещена в архив!")
        await callback.message.edit_text(
            "✅ Повторяющаяся задача завершена!\n\n"
            f"📋 {todo.title}\n"
            f"🔄 Выполнено раз: {todo.recurrence_count}\n\n"
            "Задача перемещена в архив.",
            parse_mode="HTML"
        )
    elif todo.is_recurring:
        await callback.answer("✅ Выполнено! Создана следующая итерация.")
        formatted = format_todo(todo, user_storage.user.timezone)
        await callback.message.edit_text(
            f"✅ Выполнено! Следующая итерация:\n\n{formatted}",
            reply_markup=get_todo_keyboard(todo.id, is_recurring=True),
            parse_mode="HTML"
        )
    else:
        await callback.answer("✅ Задача выполнена!")
        formatted = format_todo(todo, user_storage.user.timezone)
        await callback.message.edit_text(
            formatted,
            reply_markup=get_todo_keyboard(todo.id, is_recurring=False),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("tp:"))
async def cb_todo_progress(callback: CallbackQuery):
    """Set todo status to in progress (tp = todo progress)"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    todo = await user_storage.update_todo(
        todo_id,
        status=TodoStatus.IN_PROGRESS.value
    )
    
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    await callback.answer("🔄 Задача в работе!")
    
    formatted = format_todo(todo, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_todo_keyboard(todo.id, is_recurring=todo.is_recurring),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tdd:"))
async def cb_todo_delete(callback: CallbackQuery):
    """Delete todo (tdd = todo delete)"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    deleted = await user_storage.delete_todo(todo_id)
    
    if deleted:
        await callback.answer("🗑️ Задача удалена")
        await callback.message.edit_text("Задача удалена")
    else:
        await callback.answer("Задача не найдена")


@router.callback_query(F.data.startswith("ta:"))
async def cb_todo_archive(callback: CallbackQuery):
    """Archive todo (ta = todo archive)"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    todo = await user_storage.get_todo(todo_id)
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    archived = await user_storage.archive_todo(todo_id)
    
    if archived:
        await callback.answer("📦 Задача перемещена в архив")
        await callback.message.edit_text(
            f"📦 Задача «{todo.title}» перемещена в архив\n\n"
            "Используйте /archive для просмотра архива"
        )
    else:
        await callback.answer("Ошибка архивирования")


@router.callback_query(F.data.startswith("tr:"))
async def cb_todo_recurrence(callback: CallbackQuery, state: FSMContext):
    """Set todo recurrence"""
    todo_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "🔁 <b>Настройка повторения задачи</b>\n\n"
        "Выберите интервал повторения:",
        reply_markup=get_recurrence_keyboard(todo_id, "todo"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("trs:"))
async def cb_todo_recurrence_set_new(callback: CallbackQuery, state: FSMContext):
    """Set recurrence type from new keyboard"""
    parts = callback.data.split(":")
    todo_id = parts[1]
    rec_type = parts[2]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    todo = await user_storage.get_todo(todo_id)
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    if rec_type == "none":
        await user_storage.update_todo(
            todo_id,
            recurrence_type=RecurrenceType.NONE.value,
            recurrence_interval=None,
            recurrence_end_date=None
        )
        await callback.answer("Повторение отключено")
        
        todo = await user_storage.get_todo(todo_id)
        formatted = format_todo(todo, user_storage.user.timezone)
        await callback.message.edit_text(
            formatted,
            reply_markup=get_todo_keyboard(todo.id, is_recurring=False),
            parse_mode="HTML"
        )
        return
    
    # Check if todo has deadline - required for recurring tasks
    if not todo.deadline:
        from datetime import datetime, timedelta
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_9am = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        await user_storage.update_todo(todo_id, deadline=tomorrow_9am.isoformat())
    
    # Set recurrence type
    await user_storage.update_todo(
        todo_id,
        recurrence_type=rec_type,
        recurrence_interval=1
    )
    
    await state.set_state(TodoStates.setting_recurrence_end)
    await state.update_data(todo_id=todo_id, rec_type=rec_type)
    
    rec_names = {
        "daily": "ежедневно",
        "weekly": "еженедельно",
        "monthly": "ежемесячно",
        "yearly": "ежегодно"
    }
    
    await callback.message.edit_text(
        f"🔁 Повторение: <b>{rec_names.get(rec_type, rec_type)}</b>\n\n"
        "📅 Укажите дату окончания повторения:\n\n"
        "<b>Примеры:</b>\n"
        "• <code>через месяц</code>\n"
        "• <code>31.12.2025</code>\n"
        "• <code>через год</code>\n\n"
        "Или напишите <code>нет</code> для бессрочного повторения.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("trs2:"))
async def cb_todo_recurrence_set(callback: CallbackQuery, state: FSMContext):
    """Set recurrence type (legacy)"""
    parts = callback.data.split(":")
    todo_id = parts[1]
    rec_type = parts[2]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    todo = await user_storage.get_todo(todo_id)
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    if rec_type == "none":
        await user_storage.update_todo(
            todo_id,
            recurrence_type=RecurrenceType.NONE.value,
            recurrence_interval=None,
            recurrence_end_date=None
        )
        await callback.answer("Повторение отключено")
        
        todo = await user_storage.get_todo(todo_id)
        formatted = format_todo(todo, user_storage.user.timezone)
        await callback.message.edit_text(
            formatted,
            reply_markup=get_todo_keyboard(todo.id, is_recurring=False),
            parse_mode="HTML"
        )
        return
    
    # Check if todo has deadline - required for recurring tasks
    if not todo.deadline:
        from datetime import datetime, timedelta
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_9am = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        await user_storage.update_todo(todo_id, deadline=tomorrow_9am.isoformat())
    
    # Set recurrence type
    await user_storage.update_todo(
        todo_id,
        recurrence_type=rec_type,
        recurrence_interval=1
    )
    
    await state.set_state(TodoStates.setting_recurrence_end)
    await state.update_data(todo_id=todo_id, rec_type=rec_type)
    
    rec_names = {
        "daily": "ежедневно",
        "weekly": "еженедельно",
        "monthly": "ежемесячно",
        "yearly": "ежегодно"
    }
    
    await callback.message.edit_text(
        f"🔁 Повторение: <b>{rec_names.get(rec_type, rec_type)}</b>\n\n"
        "📅 Укажите дату окончания повторения:\n\n"
        "<b>Примеры:</b>\n"
        "• <code>через месяц</code>\n"
        "• <code>31.12.2025</code>\n"
        "• <code>через год</code>\n\n"
        "Или напишите <code>нет</code> для бессрочного повторения.",
        parse_mode="HTML"
    )


# ============ CUSTOM RECURRENCE FOR TODOS ============

@router.callback_query(F.data.startswith("recurrence_custom:") & F.data.contains(":todo"))
async def cb_todo_custom_recurrence(callback: CallbackQuery):
    """Show custom recurrence options for todo"""
    parts = callback.data.split(":")
    todo_id = parts[1]
    
    await callback.message.edit_text(
        "⚙️ <b>Свой интервал повторения</b>\n\n"
        "Выберите как часто повторять задачу или введите вручную:",
        reply_markup=get_custom_recurrence_keyboard(todo_id, "todo"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rc:") & F.data.contains(":t:"))
async def cb_todo_custom_set(callback: CallbackQuery, state: FSMContext):
    """Set custom recurrence for todo"""
    # Format: rc:item_id:t:value:unit (t=todo, unit=d/w/m)
    parts = callback.data.split(":")
    todo_id = parts[1]
    value = int(parts[3])
    unit = parts[4]
    
    # Конвертируем в минуты
    if unit == "d":
        interval_minutes = value * 1440
    elif unit == "w":
        interval_minutes = value * 10080
    elif unit == "m":
        interval_minutes = value * 43200
    elif unit == "h":
        interval_minutes = value * 60
    else:
        interval_minutes = value
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    todo = await user_storage.get_todo(todo_id)
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    # Set deadline if not set
    if not todo.deadline:
        from datetime import datetime, timedelta
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_9am = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        await user_storage.update_todo(todo_id, deadline=tomorrow_9am.isoformat())
    
    await user_storage.update_todo(
        todo_id,
        recurrence_type="custom",
        recurrence_interval=interval_minutes
    )
    
    await state.set_state(TodoStates.setting_recurrence_end)
    await state.update_data(todo_id=todo_id, rec_type="custom", interval=interval_minutes)
    
    await callback.answer(f"✅ Повторение: {format_interval(interval_minutes)}")
    
    await callback.message.edit_text(
        f"🔁 Повторение: <b>{format_interval(interval_minutes)}</b>\n\n"
        "📅 Укажите дату окончания повторения:\n\n"
        "<b>Примеры:</b>\n"
        "• <code>через месяц</code>\n"
        "• <code>31.12.2025</code>\n\n"
        "Или напишите <code>нет</code> для бессрочного повторения.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ri:") & F.data.endswith(":t"))
async def cb_todo_recurrence_input(callback: CallbackQuery, state: FSMContext):
    """Start custom interval input for todo (ri = recurrence input)"""
    parts = callback.data.split(":")
    todo_id = parts[1]
    
    await state.update_data(recurrence_item_id=todo_id, recurrence_item_type="todo")
    await state.set_state(TodoStates.waiting_for_custom_interval)
    
    await callback.message.edit_text(
        "✏️ <b>Введите интервал повторения</b>\n\n"
        "Примеры:\n"
        "• <code>2 дня</code>\n"
        "• <code>3 недели</code>\n"
        "• <code>2 месяца</code>\n"
        "• <code>4 часа</code>\n\n"
        "Или отправьте /cancel для отмены",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rb:") & F.data.endswith(":t"))
async def cb_todo_recurrence_back(callback: CallbackQuery):
    """Go back to todo recurrence menu (rb = recurrence back)"""
    parts = callback.data.split(":")
    todo_id = parts[1]
    
    await callback.message.edit_text(
        "🔁 <b>Настройка повторения задачи</b>\n\n"
        "Выберите интервал повторения:",
        reply_markup=get_recurrence_keyboard(todo_id, "todo"),
        parse_mode="HTML"
    )


@router.message(TodoStates.waiting_for_custom_interval)
async def process_todo_custom_interval(message: Message, state: FSMContext):
    """Process custom interval input for todo"""
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
    todo_id = data.get("recurrence_item_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    todo = await user_storage.get_todo(todo_id)
    if not todo:
        await state.clear()
        await message.answer("Задача не найдена", reply_markup=get_main_keyboard())
        return
    
    # Set deadline if not set
    if not todo.deadline:
        from datetime import datetime, timedelta
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_9am = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        await user_storage.update_todo(todo_id, deadline=tomorrow_9am.isoformat())
    
    await user_storage.update_todo(
        todo_id,
        recurrence_type="custom",
        recurrence_interval=interval_minutes
    )
    
    await state.set_state(TodoStates.setting_recurrence_end)
    await state.update_data(todo_id=todo_id, rec_type="custom", interval=interval_minutes)
    
    await message.answer(
        f"🔁 Повторение: <b>{format_interval(interval_minutes)}</b>\n\n"
        "📅 Укажите дату окончания повторения:\n\n"
        "<b>Примеры:</b>\n"
        "• <code>через месяц</code>\n"
        "• <code>31.12.2025</code>\n\n"
        "Или напишите <code>нет</code> для бессрочного повторения.",
        parse_mode="HTML"
    )


@router.message(TodoStates.setting_recurrence_end)
async def process_recurrence_end(message: Message, state: FSMContext):
    """Process recurrence end date"""
    text = message.text.strip().lower()
    
    data = await state.get_data()
    todo_id = data.get("todo_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    if text in ["нет", "без даты", "бессрочно", "навсегда"]:
        await user_storage.update_todo(todo_id, recurrence_end_date=None)
        await state.clear()
        
        todo = await user_storage.get_todo(todo_id)
        rec_names = {
            "daily": "Ежедневно",
            "weekly": "Еженедельно",
            "monthly": "Ежемесячно",
            "yearly": "Ежегодно"
        }
        formatted = format_todo(todo, user_storage.user.timezone)
        await message.answer(
            f"✅ <b>Повторение настроено!</b>\n\n"
            f"🔁 {rec_names.get(todo.recurrence_type, 'Повтор')} (бессрочно)\n\n"
            f"{formatted}",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    end_date = parse_datetime(text, user_storage.user.timezone)
    
    if not end_date:
        await message.answer(
            "⚠️ Не удалось распознать дату.\n\n"
            "Попробуйте указать в формате:\n"
            "• <code>через месяц</code>\n"
            "• <code>31.12.2025</code>",
            parse_mode="HTML"
        )
        return
    
    await user_storage.update_todo(todo_id, recurrence_end_date=end_date.isoformat())
    await state.clear()
    
    todo = await user_storage.get_todo(todo_id)
    rec_names = {
        "daily": "Ежедневно",
        "weekly": "Еженедельно",
        "monthly": "Ежемесячно",
        "yearly": "Ежегодно"
    }
    formatted = format_todo(todo, user_storage.user.timezone)
    await message.answer(
        f"✅ <b>Повторение настроено!</b>\n\n"
        f"🔁 {rec_names.get(todo.recurrence_type, 'Повтор')} до {end_date.strftime('%d.%m.%Y')}\n\n"
        f"{formatted}",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tpr:"))
async def cb_todo_priority(callback: CallbackQuery):
    """Show priority selection"""
    todo_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "🎯 <b>Выберите приоритет:</b>",
        reply_markup=get_priority_keyboard(todo_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ps:"))
async def cb_priority_set(callback: CallbackQuery):
    """Set todo priority"""
    parts = callback.data.split(":")
    todo_id = parts[1]
    priority_str = parts[2]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    todo = await user_storage.update_todo(todo_id, priority=priority_str)
    
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    priority_names = {
        "low": "Низкий",
        "medium": "Средний",
        "high": "Высокий",
        "urgent": "Срочный"
    }
    
    await callback.answer(f"✅ Приоритет: {priority_names.get(priority_str, 'установлен')}")
    
    formatted = format_todo(todo, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_todo_keyboard(todo.id, is_recurring=todo.is_recurring),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tdl:"))
async def cb_todo_deadline(callback: CallbackQuery, state: FSMContext):
    """Start deadline setting"""
    todo_id = callback.data.split(":")[1]
    
    await state.set_state(TodoStates.setting_deadline)
    await state.update_data(todo_id=todo_id)
    
    await callback.message.edit_text(
        "📅 <b>Установка дедлайна</b>\n\n"
        "Укажите дату и время дедлайна:\n\n"
        "<b>Примеры:</b>\n"
        "• <code>завтра в 18:00</code>\n"
        "• <code>15.01.2025 12:00</code>\n"
        "• <code>через 3 дня</code>\n\n"
        "Или напишите <code>нет</code> чтобы убрать дедлайн.",
        parse_mode="HTML"
    )


@router.message(TodoStates.setting_deadline)
async def process_deadline(message: Message, state: FSMContext):
    """Process deadline input"""
    text = message.text.strip().lower()
    
    data = await state.get_data()
    todo_id = data.get("todo_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    if text in ["нет", "без дедлайна", "убрать", "удалить"]:
        todo = await user_storage.update_todo(todo_id, deadline=None)
        await state.clear()
        
        if todo:
            formatted = format_todo(todo, user_storage.user.timezone)
            await message.answer(
                f"✅ Дедлайн убран\n\n{formatted}",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer("Задача не найдена", reply_markup=get_main_keyboard())
        return
    
    deadline = parse_datetime(text, user_storage.user.timezone)
    
    if not deadline:
        await message.answer(
            "⚠️ Не удалось распознать дату.\n\n"
            "Попробуйте указать в формате:\n"
            "• <code>завтра в 18:00</code>\n"
            "• <code>15.01.2025 12:00</code>",
            parse_mode="HTML"
        )
        return
    
    todo = await user_storage.update_todo(todo_id, deadline=deadline.isoformat())
    await state.clear()
    
    if todo:
        formatted = format_todo(todo, user_storage.user.timezone)
        await message.answer(
            f"✅ Дедлайн установлен!\n\n{formatted}",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer("Задача не найдена", reply_markup=get_main_keyboard())


@router.callback_query(F.data.startswith("tb:"))
async def cb_todo_back(callback: CallbackQuery):
    """Go back to todo view"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    todo = await user_storage.get_todo(todo_id)
    
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    formatted = format_todo(todo, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_todo_keyboard(todo.id, is_recurring=todo.is_recurring),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "tn")
async def cb_todo_new(callback: CallbackQuery, state: FSMContext):
    """Start creating new todo from callback"""
    await callback.message.delete()
    await start_create_todo(callback.message, state)


@router.callback_query(F.data.startswith("tpg:"))
async def cb_todos_page(callback: CallbackQuery):
    """Handle todos pagination"""
    page = int(callback.data.split(":")[1])
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    todos = await user_storage.get_todos()
    
    text = format_todos_list(todos, user_storage.user.timezone)
    keyboard = get_todos_list_keyboard(todos, page)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ============ ARCHIVE ============

def get_archive_keyboard(archive: list, item_type: str = None, page: int = 0, per_page: int = 5):
    """Get keyboard for archive view"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_items = archive[start:end]
    
    for item in page_items:
        data = item.data
        title = data.get("title", "Без названия")[:25]
        icon = "📋" if item.item_type == "todo" else "🔔"
        date = item.archived_at[:10]
        
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {title} ({date})",
                callback_data=f"archive_view:{item.archived_at[:26]}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"archive_page:{page-1}"))
    if end < len(archive):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"archive_page:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Filters
    builder.row(
        InlineKeyboardButton(text="📋 Только задачи", callback_data="archive_filter:todo"),
        InlineKeyboardButton(text="🔔 Только напоминания", callback_data="archive_filter:reminder")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Все", callback_data="archive_filter:all")
    )
    
    if archive:
        builder.row(
            InlineKeyboardButton(text="🗑️ Очистить архив", callback_data="archive_clear")
        )
    
    return builder.as_markup()


@router.message(Command("archive"))
async def cmd_archive(message: Message):
    """Show archive"""
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    archive = await user_storage.get_archive()
    
    if not archive:
        await message.answer(
            "📦 <b>Архив</b>\n\n"
            "Архив пуст.\n\n"
            "Завершённые повторяющиеся задачи и напоминания "
            "автоматически перемещаются сюда.",
            parse_mode="HTML"
        )
        return
    
    todos_count = len([a for a in archive if a.item_type == "todo"])
    reminders_count = len([a for a in archive if a.item_type == "reminder"])
    
    await message.answer(
        f"📦 <b>Архив</b>\n\n"
        f"📋 Задач: {todos_count}\n"
        f"🔔 Напоминаний: {reminders_count}\n\n"
        f"Всего: {len(archive)} записей",
        reply_markup=get_archive_keyboard(archive),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("archive_page:"))
async def cb_archive_page(callback: CallbackQuery):
    """Handle archive pagination"""
    page = int(callback.data.split(":")[1])
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    archive = await user_storage.get_archive()
    
    await callback.message.edit_reply_markup(
        reply_markup=get_archive_keyboard(archive, page=page)
    )


@router.callback_query(F.data.startswith("archive_filter:"))
async def cb_archive_filter(callback: CallbackQuery):
    """Filter archive by type"""
    filter_type = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    if filter_type == "all":
        archive = await user_storage.get_archive()
    else:
        archive = await user_storage.get_archive(item_type=filter_type)
    
    if not archive:
        await callback.answer("Нет записей")
        return
    
    filter_names = {"todo": "задачи", "reminder": "напоминания", "all": "все"}
    
    await callback.message.edit_text(
        f"📦 <b>Архив: {filter_names.get(filter_type, 'все')}</b>\n\n"
        f"Найдено: {len(archive)} записей",
        reply_markup=get_archive_keyboard(archive),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("archive_view:"))
async def cb_archive_view(callback: CallbackQuery):
    """View archived item"""
    archived_at = callback.data.split(":", 1)[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    archive = await user_storage.get_archive()
    item = None
    for a in archive:
        if a.archived_at.startswith(archived_at):
            item = a
            break
    
    if not item:
        await callback.answer("Запись не найдена")
        return
    
    data = item.data
    icon = "📋" if item.item_type == "todo" else "🔔"
    type_name = "Задача" if item.item_type == "todo" else "Напоминание"
    
    text = (
        f"{icon} <b>{type_name}: {data.get('title', 'Без названия')}</b>\n\n"
    )
    
    if data.get("description"):
        text += f"📝 {data['description']}\n\n"
    
    if data.get("recurrence_count", 0) > 0:
        text += f"🔄 Выполнено раз: {data['recurrence_count']}\n"
    
    text += f"📅 Создано: {data.get('created_at', '')[:10]}\n"
    text += f"📦 Архивировано: {item.archived_at[:10]}\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="♻️ Восстановить", callback_data=f"archive_restore:{archived_at}"),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"archive_delete:{archived_at}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="archive_back")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("archive_restore:"))
async def cb_archive_restore(callback: CallbackQuery):
    """Restore item from archive"""
    archived_at = callback.data.split(":", 1)[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    # Find full archived_at
    archive = await user_storage.get_archive()
    full_archived_at = None
    for a in archive:
        if a.archived_at.startswith(archived_at):
            full_archived_at = a.archived_at
            break
    
    if not full_archived_at:
        await callback.answer("Запись не найдена")
        return
    
    restored = await user_storage.restore_from_archive(full_archived_at)
    
    if restored:
        await callback.answer("♻️ Запись восстановлена!")
        
        archive = await user_storage.get_archive()
        if archive:
            await callback.message.edit_text(
                f"📦 <b>Архив</b>\n\n"
                f"Записей: {len(archive)}",
                reply_markup=get_archive_keyboard(archive),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("📦 Архив пуст")
    else:
        await callback.answer("Ошибка восстановления")


@router.callback_query(F.data.startswith("archive_delete:"))
async def cb_archive_delete(callback: CallbackQuery):
    """Delete item from archive permanently"""
    archived_at = callback.data.split(":", 1)[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    # Find full archived_at
    archive = await user_storage.get_archive()
    full_archived_at = None
    for a in archive:
        if a.archived_at.startswith(archived_at):
            full_archived_at = a.archived_at
            break
    
    if not full_archived_at:
        await callback.answer("Запись не найдена")
        return
    
    deleted = await user_storage.delete_from_archive(full_archived_at)
    
    if deleted:
        await callback.answer("🗑️ Запись удалена навсегда")
        
        archive = await user_storage.get_archive()
        if archive:
            await callback.message.edit_text(
                f"📦 <b>Архив</b>\n\n"
                f"Записей: {len(archive)}",
                reply_markup=get_archive_keyboard(archive),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("📦 Архив пуст")
    else:
        await callback.answer("Ошибка удаления")


@router.callback_query(F.data == "archive_back")
async def cb_archive_back(callback: CallbackQuery):
    """Go back to archive list"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    archive = await user_storage.get_archive()
    
    if archive:
        await callback.message.edit_text(
            f"📦 <b>Архив</b>\n\n"
            f"Записей: {len(archive)}",
            reply_markup=get_archive_keyboard(archive),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("📦 Архив пуст")


@router.callback_query(F.data == "archive_clear")
async def cb_archive_clear(callback: CallbackQuery):
    """Clear all archive"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, очистить", callback_data="archive_clear_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="archive_back")
    )
    
    await callback.message.edit_text(
        "⚠️ <b>Очистка архива</b>\n\n"
        "Все записи будут удалены навсегда!\n\n"
        "Вы уверены?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "archive_clear_confirm")
async def cb_archive_clear_confirm(callback: CallbackQuery):
    """Confirm archive clear"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    deleted = await user_storage.clear_archive()
    
    await callback.answer(f"🗑️ Удалено: {deleted} записей")
    await callback.message.edit_text("📦 Архив очищен")


@router.callback_query(F.data == "tar")
async def cb_todos_archive(callback: CallbackQuery):
    """Show archive from todos list"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    archive = await user_storage.get_archive()
    
    if not archive:
        await callback.answer("Архив пуст")
        return
    
    todos_count = len([a for a in archive if a.item_type == "todo"])
    reminders_count = len([a for a in archive if a.item_type == "reminder"])
    
    await callback.message.edit_text(
        f"📦 <b>Архив</b>\n\n"
        f"📋 Задач: {todos_count}\n"
        f"🔔 Напоминаний: {reminders_count}\n\n"
        f"Всего: {len(archive)} записей",
        reply_markup=get_archive_keyboard(archive),
        parse_mode="HTML"
    )
