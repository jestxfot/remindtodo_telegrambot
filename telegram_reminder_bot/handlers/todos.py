"""
Todo handlers
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.database import async_session
from models.todo import TodoPriority, TodoStatus
from services.user_service import UserService
from services.todo_service import TodoService
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
    waiting_for_description = State()
    waiting_for_deadline = State()
    editing_title = State()
    editing_description = State()
    setting_deadline = State()


async def show_todos_list(message: Message):
    """Show list of user's todos"""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        
        if not user:
            await message.answer("Пользователь не найден. Используйте /start")
            return
        
        todo_service = TodoService(session)
        todos = await todo_service.get_user_todos(user.id)
        
        text = format_todos_list(todos, user.timezone)
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
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        
        if not user:
            await message.answer("Ошибка: пользователь не найден")
            return
        
        todo_service = TodoService(session)
        todo = await todo_service.create_todo(
            user_id=user.id,
            title=text
        )
        
        await state.clear()
        
        formatted = format_todo(todo, user.timezone)
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
    todo_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        todo_service = TodoService(session)
        todo = await todo_service.get_todo(todo_id)
        
        if not todo:
            await callback.answer("Задача не найдена")
            return
        
        formatted = format_todo(todo, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_todo_keyboard(todo.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("todo_complete:"))
async def cb_todo_complete(callback: CallbackQuery):
    """Mark todo as completed"""
    todo_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        todo_service = TodoService(session)
        todo = await todo_service.complete_todo(todo_id)
        
        if not todo:
            await callback.answer("Задача не найдена")
            return
        
        await callback.answer("✅ Задача выполнена!")
        
        formatted = format_todo(todo, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_todo_keyboard(todo.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("todo_progress:"))
async def cb_todo_progress(callback: CallbackQuery):
    """Set todo status to in progress"""
    todo_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        todo_service = TodoService(session)
        todo = await todo_service.set_in_progress(todo_id)
        
        if not todo:
            await callback.answer("Задача не найдена")
            return
        
        await callback.answer("🔄 Задача в работе!")
        
        formatted = format_todo(todo, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_todo_keyboard(todo.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("todo_delete:"))
async def cb_todo_delete(callback: CallbackQuery):
    """Delete todo"""
    todo_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        todo_service = TodoService(session)
        deleted = await todo_service.delete_todo(todo_id)
        
        if deleted:
            await callback.answer("🗑️ Задача удалена")
            await callback.message.edit_text("Задача удалена")
        else:
            await callback.answer("Задача не найдена")


@router.callback_query(F.data.startswith("todo_priority:"))
async def cb_todo_priority(callback: CallbackQuery):
    """Show priority selection"""
    todo_id = int(callback.data.split(":")[1])
    
    await callback.message.edit_text(
        "🎯 <b>Выберите приоритет:</b>",
        reply_markup=get_priority_keyboard(todo_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("priority_set:"))
async def cb_priority_set(callback: CallbackQuery):
    """Set todo priority"""
    parts = callback.data.split(":")
    todo_id = int(parts[1])
    priority_str = parts[2]
    
    priority_map = {
        "low": TodoPriority.LOW,
        "medium": TodoPriority.MEDIUM,
        "high": TodoPriority.HIGH,
        "urgent": TodoPriority.URGENT
    }
    
    priority = priority_map.get(priority_str, TodoPriority.MEDIUM)
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        todo_service = TodoService(session)
        todo = await todo_service.set_priority(todo_id, priority)
        
        if not todo:
            await callback.answer("Задача не найдена")
            return
        
        priority_names = {
            TodoPriority.LOW: "Низкий",
            TodoPriority.MEDIUM: "Средний",
            TodoPriority.HIGH: "Высокий",
            TodoPriority.URGENT: "Срочный"
        }
        
        await callback.answer(f"✅ Приоритет: {priority_names.get(priority, 'установлен')}")
        
        formatted = format_todo(todo, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_todo_keyboard(todo.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("todo_deadline:"))
async def cb_todo_deadline(callback: CallbackQuery, state: FSMContext):
    """Start deadline setting"""
    todo_id = int(callback.data.split(":")[1])
    
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
    
    if text in ["нет", "без дедлайна", "убрать", "удалить"]:
        async with async_session() as session:
            user_service = UserService(session)
            user = await user_service.get_user_by_telegram_id(message.from_user.id)
            
            todo_service = TodoService(session)
            todo = await todo_service.set_deadline(todo_id, None)
            
            await state.clear()
            
            if todo:
                formatted = format_todo(todo, user.timezone if user else "Europe/Moscow")
                await message.answer(
                    f"✅ Дедлайн убран\n\n{formatted}",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await message.answer("Задача не найдена", reply_markup=get_main_keyboard())
        return
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        timezone = user.timezone if user else "Europe/Moscow"
    
    deadline = parse_datetime(text, timezone)
    
    if not deadline:
        await message.answer(
            "⚠️ Не удалось распознать дату.\n\n"
            "Попробуйте указать в формате:\n"
            "• <code>завтра в 18:00</code>\n"
            "• <code>15.01.2025 12:00</code>",
            parse_mode="HTML"
        )
        return
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        
        todo_service = TodoService(session)
        todo = await todo_service.set_deadline(todo_id, deadline)
        
        await state.clear()
        
        if todo:
            formatted = format_todo(todo, user.timezone if user else "Europe/Moscow")
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
    todo_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        todo_service = TodoService(session)
        todo = await todo_service.get_todo(todo_id)
        
        if not todo:
            await callback.answer("Задача не найдена")
            return
        
        formatted = format_todo(todo, user.timezone if user else "Europe/Moscow")
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
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден")
            return
        
        todo_service = TodoService(session)
        todos = await todo_service.get_user_todos(user.id)
        
        text = format_todos_list(todos, user.timezone)
        keyboard = get_todos_list_keyboard(todos, page)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
