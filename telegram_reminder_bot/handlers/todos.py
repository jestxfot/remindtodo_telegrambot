"""
Todo handlers
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.json_storage import storage
from storage.models import TodoPriority, TodoStatus
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
    get_priority_keyboard
)
from utils.date_parser import parse_datetime
from utils.formatters import format_todo, format_todos_list

router = Router()


class TodoStates(StatesGroup):
    """States for todo creation"""
    waiting_for_title = State()
    setting_deadline = State()


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
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание задачи отменено", reply_markup=get_main_keyboard())
        return
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    todo = await user_storage.create_todo(title=text)
    
    await state.clear()
    
    formatted = format_todo(todo, user_storage.user.timezone)
    await message.answer(
        f"✅ Задача создана!\n\n{formatted}",
        reply_markup=get_todo_keyboard(todo.id),
        parse_mode="HTML"
    )
    
    await message.answer(
        "Используйте кнопки для настройки приоритета, дедлайна и т.д.",
        reply_markup=get_main_keyboard()
    )


@router.callback_query(F.data.startswith("todo_view:"))
async def cb_todo_view(callback: CallbackQuery):
    """View todo details"""
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
        reply_markup=get_todo_keyboard(todo.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("todo_complete:"))
async def cb_todo_complete(callback: CallbackQuery):
    """Mark todo as completed"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
    todo = await user_storage.update_todo(
        todo_id,
        status=TodoStatus.COMPLETED.value,
        completed_at=datetime.utcnow().isoformat()
    )
    
    if not todo:
        await callback.answer("Задача не найдена")
        return
    
    await callback.answer("✅ Задача выполнена!")
    
    formatted = format_todo(todo, user_storage.user.timezone)
    await callback.message.edit_text(
        formatted,
        reply_markup=get_todo_keyboard(todo.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("todo_progress:"))
async def cb_todo_progress(callback: CallbackQuery):
    """Set todo status to in progress"""
    todo_id = callback.data.split(":")[1]
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
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
        reply_markup=get_todo_keyboard(todo.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("todo_delete:"))
async def cb_todo_delete(callback: CallbackQuery):
    """Delete todo"""
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


@router.callback_query(F.data.startswith("todo_priority:"))
async def cb_todo_priority(callback: CallbackQuery):
    """Show priority selection"""
    todo_id = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        "🎯 <b>Выберите приоритет:</b>",
        reply_markup=get_priority_keyboard(todo_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("priority_set:"))
async def cb_priority_set(callback: CallbackQuery):
    """Set todo priority"""
    parts = callback.data.split(":")
    todo_id = parts[1]
    priority_str = parts[2]
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
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
        reply_markup=get_todo_keyboard(todo.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("todo_deadline:"))
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


@router.callback_query(F.data.startswith("todo_back:"))
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
        reply_markup=get_todo_keyboard(todo.id),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "todo_new")
async def cb_todo_new(callback: CallbackQuery, state: FSMContext):
    """Start creating new todo from callback"""
    await callback.message.delete()
    await start_create_todo(callback.message, state)


@router.callback_query(F.data.startswith("todos_page:"))
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
