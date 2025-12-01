"""
Basic command handlers
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.database import async_session
from services.user_service import UserService
from services.todo_service import TodoService
from services.reminder_service import ReminderService
from utils.keyboards import get_main_keyboard, get_settings_keyboard
from utils.formatters import format_statistics

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()
    
    async with async_session() as session:
        user_service = UserService(session)
        await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
    
    welcome_text = f"""👋 <b>Привет, {message.from_user.first_name or 'друг'}!</b>

Я бот для управления напоминаниями и задачами.

<b>🔔 Что я умею:</b>
• Создавать напоминания с точным временем
• Повторяющиеся напоминания (ежедневно, еженедельно и т.д.)
• Постоянные уведомления со звуком пока не отключишь
• Управление списком задач (TODO)

<b>📋 Команды:</b>
/newreminder - Новое напоминание
/reminders - Список напоминаний
/newtodo - Новая задача
/todos - Список задач
/stats - Статистика
/settings - Настройки
/help - Помощь

Выбери действие на клавиатуре ниже! 👇"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = """📚 <b>Справка по боту</b>

<b>🔔 Напоминания:</b>
• /newreminder - создать напоминание
• /reminders - список всех напоминаний

<b>Примеры создания напоминания:</b>
<code>Позвонить маме завтра в 10:00</code>
<code>Встреча через 2 часа</code>
<code>Оплатить счёт 15 января в 12:00</code>

<b>📋 Задачи (TODO):</b>
• /newtodo - создать задачу
• /todos - список всех задач

<b>Приоритеты задач:</b>
🟢 Низкий | 🟡 Средний | 🟠 Высокий | 🔴 Срочный

<b>🔄 Повторяющиеся напоминания:</b>
После создания напоминания можно настроить повторение:
• Ежедневно
• Еженедельно  
• Ежемесячно
• Ежегодно
• Или свой интервал

<b>🔊 Постоянные уведомления:</b>
Бот будет напоминать каждую минуту, пока вы не:
• Отметите выполненным ✅
• Отложите на время ⏸️
• Отключите звук 🔇

<b>⚙️ Настройки:</b>
/settings - настроить часовой пояс и интервал уведомлений"""
    
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handle /stats command"""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        
        if not user:
            await message.answer("Пользователь не найден. Используйте /start")
            return
        
        todo_service = TodoService(session)
        reminder_service = ReminderService(session)
        
        # Get todo stats
        todo_stats = await todo_service.get_statistics(user.id)
        
        # Get reminder stats
        all_reminders = await reminder_service.get_user_reminders(user.id, include_completed=True)
        from models.reminder import ReminderStatus
        active_reminders = len([r for r in all_reminders if r.status in [ReminderStatus.PENDING, ReminderStatus.ACTIVE]])
        completed_reminders = len([r for r in all_reminders if r.status == ReminderStatus.COMPLETED])
        
        stats_text = format_statistics(
            total_todos=todo_stats["total"],
            completed_todos=todo_stats["completed"],
            pending_todos=todo_stats["pending"] + todo_stats["in_progress"],
            overdue_todos=todo_stats["overdue"],
            total_reminders=len(all_reminders),
            active_reminders=active_reminders,
            completed_reminders=completed_reminders
        )
        
        await message.answer(stats_text, parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Handle /settings command"""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        
        timezone = user.timezone if user else "Europe/Moscow"
    
    settings_text = f"""⚙️ <b>Настройки</b>

🌍 Текущий часовой пояс: <code>{timezone}</code>

Выберите, что хотите изменить:"""
    
    await message.answer(
        settings_text,
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "📝 Задачи")
async def btn_todos(message: Message):
    """Handle Todos button"""
    from .todos import show_todos_list
    await show_todos_list(message)


@router.message(F.text == "⏰ Напоминания")
async def btn_reminders(message: Message):
    """Handle Reminders button"""
    from .reminders import show_reminders_list
    await show_reminders_list(message)


@router.message(F.text == "➕ Новая задача")
async def btn_new_todo(message: Message, state: FSMContext):
    """Handle New Todo button"""
    from .todos import start_create_todo
    await start_create_todo(message, state)


@router.message(F.text == "🔔 Новое напоминание")
async def btn_new_reminder(message: Message, state: FSMContext):
    """Handle New Reminder button"""
    from .reminders import start_create_reminder
    await start_create_reminder(message, state)


@router.message(F.text == "📊 Статистика")
async def btn_stats(message: Message):
    """Handle Statistics button"""
    await cmd_stats(message)


@router.message(F.text == "⚙️ Настройки")
async def btn_settings(message: Message):
    """Handle Settings button"""
    await cmd_settings(message)


@router.message(F.text == "❌ Отмена")
async def btn_cancel(message: Message, state: FSMContext):
    """Handle Cancel button"""
    await state.clear()
    await message.answer(
        "Действие отменено",
        reply_markup=get_main_keyboard()
    )
