"""
Basic command handlers - WebApp only mode
"""
from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from handlers.auth import is_authenticated, user_has_password
from config import WEBAPP_URL

router = Router()


def get_webapp_keyboard():
    """Get keyboard with Mini App button"""
    if WEBAPP_URL:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🚀 Открыть приложение",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )]
        ])
    return None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()
    
    webapp_kb = get_webapp_keyboard()
    
    if not webapp_kb:
        await message.answer(
            "⚠️ <b>Mini App не настроен</b>\n\n"
            "Установите WEBAPP_URL в настройках.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        return
    
    if not user_has_password(message.from_user.id):
        welcome_text = f"""👋 <b>Привет, {message.from_user.first_name or 'друг'}!</b>

Я безопасный бот для управления задачами, напоминаниями, заметками и паролями.

<b>🔐 Безопасность:</b>
• Все данные шифруются AES-256-GCM
• Мастер-пароль нигде не хранится
• Только вы имеете доступ к данным

👇 <b>Нажмите кнопку чтобы начать:</b>"""
    elif is_authenticated(message.from_user.id):
        welcome_text = f"""👋 <b>С возвращением, {message.from_user.first_name or 'друг'}!</b>

🔓 Хранилище разблокировано

👇 <b>Откройте приложение:</b>"""
    else:
        welcome_text = f"""👋 <b>Привет, {message.from_user.first_name or 'друг'}!</b>

🔒 Хранилище заблокировано

👇 <b>Откройте приложение для разблокировки:</b>"""
    
    await message.answer(
        welcome_text, 
        reply_markup=webapp_kb, 
        parse_mode="HTML"
    )


@router.message(Command("app"))
async def cmd_app(message: Message):
    """Open Mini App"""
    webapp_kb = get_webapp_keyboard()
    
    if webapp_kb:
        await message.answer(
            "🚀 <b>Откройте приложение</b>",
            reply_markup=webapp_kb,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "⚠️ Mini App не настроен.\n\n"
            "Установите WEBAPP_URL в настройках.",
            parse_mode="HTML"
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    webapp_kb = get_webapp_keyboard()
    
    help_text = """📚 <b>Справка по боту</b>

<b>📱 Всё управление через Mini App:</b>
• 📋 Задачи с приоритетами и дедлайнами
• 🔔 Напоминания с повторением
• 📝 Зашифрованные заметки
• 🔐 Менеджер паролей
• 📅 Календарь событий

<b>🔔 Уведомления:</b>
Бот отправит уведомление когда придёт время напоминания.
Вы сможете отметить выполненным или отложить.

<b>🔐 Безопасность:</b>
• Шифрование AES-256-GCM
• Мастер-пароль нигде не хранится
• Данные доступны только вам"""
    
    await message.answer(help_text, reply_markup=webapp_kb, parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Show auth status"""
    webapp_kb = get_webapp_keyboard()
    
    has_pwd = user_has_password(message.from_user.id)
    is_auth = is_authenticated(message.from_user.id)
    
    if not has_pwd:
        status = "🆕 Новый пользователь\n\nОткройте приложение для создания пароля."
    elif is_auth:
        status = "🔓 Хранилище разблокировано"
    else:
        status = "🔒 Хранилище заблокировано\n\nОткройте приложение для разблокировки."
    
    await message.answer(
        f"<b>Статус:</b>\n\n{status}",
        reply_markup=webapp_kb,
        parse_mode="HTML"
    )
