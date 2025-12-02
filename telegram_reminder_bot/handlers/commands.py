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
from handlers.auth import get_crypto_for_user, is_authenticated
from utils.keyboards import get_main_keyboard, get_settings_keyboard

router = Router()


async def get_user_storage(user_id: int):
    """Get user storage with authentication"""
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    return await storage.get_user_storage(user_id, crypto)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()
    
    from handlers.auth import user_has_password
    
    if not user_has_password(message.from_user.id):
        welcome_text = f"""👋 <b>Привет, {message.from_user.first_name or 'друг'}!</b>

Я безопасный бот для управления задачами, напоминаниями, заметками и паролями.

<b>🔐 Безопасность:</b>
• Вы создаёте мастер-пароль
• Все данные шифруются AES-256-GCM
• Пароль нигде не хранится
• Только вы можете расшифровать данные

<b>Для начала работы создайте мастер-пароль:</b>

/unlock — создать пароль и начать"""
    else:
        if is_authenticated(message.from_user.id):
            welcome_text = f"""👋 <b>С возвращением, {message.from_user.first_name or 'друг'}!</b>

🔓 Хранилище разблокировано

Выбери действие на клавиатуре! 👇"""
            await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
            return
        else:
            welcome_text = f"""👋 <b>Привет, {message.from_user.first_name or 'друг'}!</b>

🔒 Хранилище заблокировано

/unlock — разблокировать"""
    
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = """📚 <b>Справка по боту</b>

<b>🔐 Безопасность:</b>
• /unlock — разблокировать хранилище
• /lock — заблокировать хранилище
• /session — настройки сессии
• /changepassword — сменить мастер-пароль

<b>🔔 Напоминания:</b>
• /newreminder — создать напоминание
• /reminders — список напоминаний
• 🔄 Повторение с датой окончания

<b>📋 Задачи:</b>
• /newtodo — создать задачу
• /todos — список задач
• 🔁 Повторяющиеся задачи

<b>📦 Архив:</b>
• /archive — просмотр архива
• Завершённые задачи не удаляются
• Можно восстановить из архива

<b>📝 Заметки (зашифрованы):</b>
• /newnote — создать заметку
• /notes — список заметок

<b>🔐 Пароли (зашифрованы):</b>
• /newpassword — добавить пароль
• /passwords — хранилище паролей
• 🔐 2FA и история паролей

<b>⏱️ Сессии:</b>
• Срок: 30 мин — 1 месяц
• /session — управление сессией

<b>⚠️ Важно:</b>
• Пароль восстановить невозможно!
• Шифрование AES-256-GCM"""
    
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handle /stats command"""
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    stats = await user_storage.get_statistics()
    todos = stats["todos"]
    reminders = stats["reminders"]
    
    completion_rate = (todos["completed"] / todos["total"] * 100) if todos["total"] > 0 else 0
    
    stats_text = f"""📊 <b>Ваша статистика</b>

<b>📋 Задачи:</b>
├ Всего: {todos["total"]}
├ Выполнено: {todos["completed"]} ✅
├ В работе: {todos["in_progress"]} 🔄
├ Просрочено: {todos["overdue"]} ⚠️
└ Выполнение: {completion_rate:.0f}%

<b>⏰ Напоминания:</b>
├ Активных: {reminders["pending"]} 🔔
└ Выполнено: {reminders["completed"]} ✅

<b>📝 Заметки:</b> {stats["notes"]} 🔐

<b>🔐 Пароли:</b> {stats["passwords"]} 🔒
"""
    
    await message.answer(stats_text, parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Handle /settings command"""
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    from handlers.auth import get_session_info
    session_info = get_session_info(message.from_user.id)
    
    settings_text = f"""⚙️ <b>Настройки</b>

🌍 Часовой пояс: <code>{user_storage.user.timezone}</code>
🔐 Шифрование: AES-256-GCM ✅
{session_info}

<b>Управление:</b>
/session — управление сессией
/changepassword — сменить мастер-пароль
/lock — заблокировать сейчас"""
    
    await message.answer(settings_text, reply_markup=get_settings_keyboard(), parse_mode="HTML")


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
    await message.answer("Действие отменено", reply_markup=get_main_keyboard())
