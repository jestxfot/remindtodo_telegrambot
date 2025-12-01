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
from storage.json_storage import storage
from utils.keyboards import get_main_keyboard, get_settings_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()
    
    # Initialize user storage (creates encrypted file if needed)
    user_storage = await storage.get_user_storage(message.from_user.id)
    await user_storage.update_user(
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    welcome_text = f"""👋 <b>Привет, {message.from_user.first_name or 'друг'}!</b>

Я бот для управления задачами, напоминаниями, заметками и паролями.

<b>🔐 Безопасность:</b>
• Все данные шифруются AES-256-GCM
• Пароли и заметки хранятся зашифрованными
• Только вы можете расшифровать данные

<b>📋 Возможности:</b>
• ⏰ Напоминания с постоянными уведомлениями
• 📝 Зашифрованные заметки
• 🔐 Безопасное хранилище паролей
• ✅ Список задач с приоритетами

<b>📋 Команды:</b>
/reminders - Напоминания
/todos - Задачи  
/notes - Заметки 🔐
/passwords - Пароли 🔐
/stats - Статистика
/settings - Настройки

Выбери действие на клавиатуре! 👇"""
    
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
• /reminders - список напоминаний
Постоянные уведомления пока не отреагируете!

<b>📋 Задачи (TODO):</b>
• /newtodo - создать задачу
• /todos - список задач
Приоритеты: 🟢🟡🟠🔴

<b>📝 Заметки:</b>
• /newnote - создать заметку
• /notes - список заметок
🔐 Все заметки зашифрованы!

<b>🔐 Пароли:</b>
• /newpassword - добавить пароль
• /passwords - хранилище паролей
🔒 AES-256-GCM шифрование

<b>🎲 Генератор паролей:</b>
В разделе паролей можно сгенерировать
надёжный случайный пароль

<b>🔄 Синхронизация:</b>
Данные автоматически сохраняются
в зашифрованном JSON файле"""
    
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handle /stats command"""
    user_storage = await storage.get_user_storage(message.from_user.id)
    stats = await user_storage.get_statistics()
    
    todos = stats["todos"]
    reminders = stats["reminders"]
    
    completion_rate = (todos["completed"] / todos["total"] * 100) if todos["total"] > 0 else 0
    
    stats_text = f"""📊 <b>Ваша статистика</b>

<b>📋 Задачи:</b>
├ Всего: {todos["total"]}
├ Выполнено: {todos["completed"]} ✅
├ В ожидании: {todos["pending"]} ⏳
├ В работе: {todos["in_progress"]} 🔄
├ Просрочено: {todos["overdue"]} ⚠️
└ Процент выполнения: {completion_rate:.1f}%

<b>⏰ Напоминания:</b>
├ Всего: {reminders["total"]}
├ Ожидают: {reminders["pending"]} 🔔
├ Активных: {reminders["active"]} 🔊
└ Выполнено: {reminders["completed"]} ✅

<b>📝 Заметки:</b> {stats["notes"]} 🔐

<b>🔐 Пароли:</b> {stats["passwords"]} 🔒
"""
    
    await message.answer(stats_text, parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Handle /settings command"""
    user_storage = await storage.get_user_storage(message.from_user.id)
    user = user_storage.user
    
    settings_text = f"""⚙️ <b>Настройки</b>

🌍 Часовой пояс: <code>{user.timezone}</code>

🔐 Шифрование: AES-256-GCM ✅
💾 Формат данных: JSON (зашифрованный)

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


@router.message(F.text == "📝 Заметки")
async def btn_notes(message: Message):
    """Handle Notes button"""
    from .notes import show_notes_list
    await show_notes_list(message)


@router.message(F.text == "🔐 Пароли")
async def btn_passwords(message: Message):
    """Handle Passwords button"""
    from .passwords import show_passwords_list
    await show_passwords_list(message)


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
