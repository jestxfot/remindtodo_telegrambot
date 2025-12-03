"""
Password vault handlers - secure password management
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import datetime
import html
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.json_storage import storage
from handlers.auth import get_crypto_for_user
from crypto.encryption import SecurePasswordGenerator


async def get_user_storage(user_id: int):
    """Get user storage with authentication"""
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    return await storage.get_user_storage(user_id, crypto)
from utils.keyboards import get_main_keyboard, get_cancel_keyboard

router = Router()


class PasswordStates(StatesGroup):
    """States for password operations"""
    waiting_for_service = State()
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_url = State()
    waiting_for_2fa = State()
    waiting_for_recovery_codes = State()
    waiting_for_notes = State()
    searching = State()
    editing_password = State()
    editing_2fa = State()
    editing_recovery = State()
    confirming_delete = State()


def get_passwords_list_keyboard(passwords: list, page: int = 0, per_page: int = 5):
    """Get keyboard with list of passwords"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_passwords = passwords[start:end]
    
    for pwd in page_passwords:
        fav_icon = "⭐" if pwd.is_favorite else ""
        name = pwd.service_name[:25] + "..." if len(pwd.service_name) > 25 else pwd.service_name
        builder.row(
            InlineKeyboardButton(
                text=f"{fav_icon}🔑 {name}",
                callback_data=f"pwd_view:{pwd.id}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"pwd_page:{page-1}"))
    if end < len(passwords):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"pwd_page:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔑 Добавить пароль", callback_data="pwd_new"),
        InlineKeyboardButton(text="🔍 Поиск", callback_data="pwd_search")
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Генератор паролей", callback_data="pwd_generate")
    )
    
    return builder.as_markup()


def get_password_keyboard(password_id: str, has_2fa: bool = False, history_count: int = 0):
    """Get keyboard for password actions"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="👁️ Показать пароль", callback_data=f"pwd_show:{password_id}"),
        InlineKeyboardButton(text="📋 Копировать", callback_data=f"pwd_copy:{password_id}")
    )
    
    # 2FA row
    if has_2fa:
        builder.row(
            InlineKeyboardButton(text="🔐 Показать 2FA", callback_data=f"pwd_show2fa:{password_id}"),
            InlineKeyboardButton(text="✏️ Изменить 2FA", callback_data=f"pwd_edit2fa:{password_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="➕ Добавить 2FA", callback_data=f"pwd_add2fa:{password_id}")
        )
    
    # History row
    if history_count > 0:
        builder.row(
            InlineKeyboardButton(text=f"📜 История ({history_count})", callback_data=f"pwd_history:{password_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить", callback_data=f"pwd_edit:{password_id}"),
        InlineKeyboardButton(text="⭐ Избранное", callback_data=f"pwd_fav:{password_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"pwd_delete:{password_id}"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="pwd_list")
    )
    
    return builder.as_markup()


def get_generator_keyboard():
    """Get keyboard for password generator"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔄 Сгенерировать ещё", callback_data="pwd_gen_new"),
    )
    builder.row(
        InlineKeyboardButton(text="12 символов", callback_data="pwd_gen:12"),
        InlineKeyboardButton(text="16 символов", callback_data="pwd_gen:16"),
        InlineKeyboardButton(text="20 символов", callback_data="pwd_gen:20")
    )
    builder.row(
        InlineKeyboardButton(text="24 символа", callback_data="pwd_gen:24"),
        InlineKeyboardButton(text="32 символа", callback_data="pwd_gen:32")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад к паролям", callback_data="pwd_list")
    )
    
    return builder.as_markup()


async def show_passwords_list(message: Message):
    """Show list of user's passwords"""
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    passwords = await user_storage.get_passwords()
    
    if not passwords:
        text = (
            "🔐 <b>Хранилище паролей</b>\n\n"
            "У вас пока нет сохранённых паролей.\n\n"
            "🔒 Все пароли шифруются AES-256-GCM\n"
            "🔑 Только вы можете их расшифровать"
        )
    else:
        text = (
            f"🔐 <b>Хранилище паролей ({len(passwords)})</b>\n\n"
            f"🔒 Зашифровано AES-256-GCM"
        )
    
    await message.answer(
        text,
        reply_markup=get_passwords_list_keyboard(passwords),
        parse_mode="HTML"
    )


async def start_create_password(message: Message, state: FSMContext):
    """Start password creation process"""
    await state.set_state(PasswordStates.waiting_for_service)
    
    await message.answer(
        "🔑 <b>Новый пароль</b>\n\n"
        "Введите название сервиса (сайта/приложения):\n\n"
        "<i>Например: Gmail, Instagram, Банк</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("passwords"))
async def cmd_passwords(message: Message):
    """Handle /passwords command"""
    await show_passwords_list(message)


@router.message(Command("newpassword"))
async def cmd_new_password(message: Message, state: FSMContext):
    """Handle /newpassword command"""
    await start_create_password(message, state)


@router.message(F.text == "🔐 Пароли")
async def btn_passwords(message: Message):
    """Handle Passwords button"""
    await show_passwords_list(message)


@router.message(PasswordStates.waiting_for_service)
async def process_service_name(message: Message, state: FSMContext):
    """Process service name input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание пароля отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(service_name=text)
    await state.set_state(PasswordStates.waiting_for_username)
    
    await message.answer(
        f"🔑 Сервис: <b>{text}</b>\n\n"
        "Введите логин/email:",
        parse_mode="HTML"
    )


@router.message(PasswordStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    """Process username input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание пароля отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(username=text)
    await state.set_state(PasswordStates.waiting_for_password)
    
    # Generate a suggested password
    suggested = SecurePasswordGenerator.generate(length=16)
    
    await message.answer(
        f"👤 Логин: <b>{text}</b>\n\n"
        f"Введите пароль или используйте сгенерированный:\n\n"
        f"<code>{suggested}</code>\n\n"
        "<i>Нажмите на код чтобы скопировать</i>",
        parse_mode="HTML"
    )


@router.message(PasswordStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Process password input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание пароля отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(password=text)
    await state.set_state(PasswordStates.waiting_for_url)
    
    # Delete the message with password for security
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(
        "🔒 Пароль сохранён\n\n"
        "Введите URL сайта (необязательно):\n\n"
        "<i>Напишите /skip чтобы пропустить</i>",
        parse_mode="HTML"
    )


@router.message(PasswordStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    """Process URL input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание пароля отменено", reply_markup=get_main_keyboard())
        return
    
    url = None if text == "/skip" else text
    await state.update_data(url=url)
    await state.set_state(PasswordStates.waiting_for_2fa)
    
    await message.answer(
        "🔐 <b>Двухфакторная аутентификация (2FA)</b>\n\n"
        "Введите TOTP-секрет (обычно начинается с букв и цифр):\n\n"
        "<i>Например: JBSWY3DPEHPK3PXP</i>\n\n"
        "<i>Напишите /skip если 2FA не используется</i>",
        parse_mode="HTML"
    )


@router.message(PasswordStates.waiting_for_2fa)
async def process_2fa(message: Message, state: FSMContext):
    """Process 2FA TOTP secret input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание пароля отменено", reply_markup=get_main_keyboard())
        return
    
    totp_secret = None if text == "/skip" else text
    await state.update_data(totp_secret=totp_secret)
    
    # Delete the message with secret for security
    try:
        await message.delete()
    except:
        pass
    
    if totp_secret:
        await state.set_state(PasswordStates.waiting_for_recovery_codes)
        await message.answer(
            "🔑 <b>Коды восстановления 2FA</b>\n\n"
            "Введите резервные коды через запятую или пробел:\n\n"
            "<i>Например: ABC123, DEF456, GHI789</i>\n\n"
            "<i>Напишите /skip чтобы пропустить</i>",
            parse_mode="HTML"
        )
    else:
        await state.set_state(PasswordStates.waiting_for_notes)
        await message.answer(
            "📝 Добавьте заметку (необязательно):\n\n"
            "<i>Например: рабочий аккаунт, ПИН-код и т.д.</i>\n\n"
            "<i>Напишите /skip чтобы пропустить</i>",
            parse_mode="HTML"
        )


@router.message(PasswordStates.waiting_for_recovery_codes)
async def process_recovery_codes(message: Message, state: FSMContext):
    """Process 2FA recovery codes input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание пароля отменено", reply_markup=get_main_keyboard())
        return
    
    recovery_codes = None if text == "/skip" else text
    await state.update_data(recovery_codes=recovery_codes)
    
    # Delete the message with codes for security
    try:
        await message.delete()
    except:
        pass
    
    await state.set_state(PasswordStates.waiting_for_notes)
    
    await message.answer(
        "📝 Добавьте заметку (необязательно):\n\n"
        "<i>Например: рабочий аккаунт, ПИН-код и т.д.</i>\n\n"
        "<i>Напишите /skip чтобы пропустить</i>",
        parse_mode="HTML"
    )


@router.message(PasswordStates.waiting_for_notes)
async def process_notes(message: Message, state: FSMContext):
    """Process notes input and save password"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание пароля отменено", reply_markup=get_main_keyboard())
        return
    
    notes = None if text == "/skip" else text
    
    data = await state.get_data()
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    pwd = await user_storage.create_password(
        service_name=data["service_name"],
        username=data["username"],
        password=data["password"],
        url=data.get("url"),
        notes=notes,
        totp_secret=data.get("totp_secret"),
        recovery_codes=data.get("recovery_codes")
    )
    
    await state.clear()
    
    has_2fa = bool(data.get("totp_secret") or data.get("recovery_codes"))
    fa_text = "\n🔐 2FA: Сохранено ✅" if has_2fa else ""
    
    await message.answer(
        f"✅ <b>Пароль сохранён!</b>\n\n"
        f"🔑 {pwd.service_name}{fa_text}\n\n"
        f"🔐 Данные надёжно зашифрованы AES-256-GCM",
        reply_markup=get_password_keyboard(pwd.id, has_2fa=has_2fa),
        parse_mode="HTML"
    )
    
    await message.answer("Вернуться в меню:", reply_markup=get_main_keyboard())


@router.callback_query(F.data == "pwd_list")
async def cb_pwd_list(callback: CallbackQuery):
    """Show passwords list"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    passwords = await user_storage.get_passwords()
    
    if not passwords:
        text = "🔐 <b>Хранилище паролей</b>\n\nУ вас пока нет сохранённых паролей."
    else:
        text = f"🔐 <b>Хранилище паролей ({len(passwords)})</b>\n\n🔒 Зашифровано AES-256-GCM"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_passwords_list_keyboard(passwords),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_page:"))
async def cb_pwd_page(callback: CallbackQuery):
    """Handle password pagination"""
    page = int(callback.data.split(":")[1])
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    passwords = await user_storage.get_passwords()
    
    text = f"🔐 <b>Хранилище паролей ({len(passwords)})</b>"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_passwords_list_keyboard(passwords, page),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_view:"))
async def cb_pwd_view(callback: CallbackQuery):
    """View password entry (without showing password)"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    pwd_data = await user_storage.get_password_decrypted(pwd_id)
    
    if not pwd_data:
        await callback.answer("Запись не найдена")
        return
    
    fav_icon = "⭐ " if pwd_data["is_favorite"] else ""
    
    text = (
        f"{fav_icon}🔑 <b>{pwd_data['service_name']}</b>\n\n"
        f"👤 Логин: <code>{pwd_data['username']}</code>\n"
        f"🔒 Пароль: ••••••••••\n"
    )
    
    if pwd_data.get("url"):
        text += f"🔗 URL: {pwd_data['url']}\n"
    
    # 2FA status
    if pwd_data.get("has_2fa"):
        text += f"🔐 2FA: Настроено ✅\n"
    
    if pwd_data.get("notes"):
        text += f"📝 Заметка: {pwd_data['notes']}\n"
    
    # Dates
    created = pwd_data.get('created_at', '')[:10]
    changed = pwd_data.get('password_changed_at', '')[:10]
    
    text += f"\n📅 Создан: {created}"
    if changed and changed != created:
        text += f"\n✏️ Пароль изменён: {changed}"
    
    if pwd_data.get("history_count", 0) > 0:
        text += f"\n📜 История: {pwd_data['history_count']} паролей"
    
    # Mark as used
    await user_storage.mark_password_used(pwd_id)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_password_keyboard(
            pwd_id, 
            has_2fa=pwd_data.get("has_2fa", False),
            history_count=pwd_data.get("history_count", 0)
        ),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_show:"))
async def cb_pwd_show(callback: CallbackQuery):
    """Show password (temporary display)"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    pwd_data = await user_storage.get_password_decrypted(pwd_id)
    
    if not pwd_data:
        await callback.answer("Запись не найдена")
        return
    
    # Show password in popup (disappears automatically)
    await callback.answer(
        f"🔑 {pwd_data['password']}",
        show_alert=True
    )


@router.callback_query(F.data.startswith("pwd_show2fa:"))
async def cb_pwd_show_2fa(callback: CallbackQuery):
    """Show 2FA secret and recovery codes"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    pwd_data = await user_storage.get_password_decrypted(pwd_id)
    
    if not pwd_data:
        await callback.answer("Запись не найдена")
        return
    
    text = f"🔐 <b>2FA для {pwd_data['service_name']}</b>\n\n"
    
    if pwd_data.get("totp_secret"):
        text += f"🔑 TOTP-секрет:\n<code>{pwd_data['totp_secret']}</code>\n\n"
    
    if pwd_data.get("recovery_codes"):
        text += f"🔑 Коды восстановления:\n<code>{pwd_data['recovery_codes']}</code>\n\n"
    
    text += "⚡ Нажмите на код чтобы скопировать\n⏱️ Сообщение удалится через 30 секунд"
    
    msg = await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
    
    # Delete message after 30 seconds
    import asyncio
    await asyncio.sleep(30)
    try:
        await msg.delete()
    except:
        pass


@router.callback_query(F.data.startswith("pwd_add2fa:"))
async def cb_pwd_add_2fa(callback: CallbackQuery, state: FSMContext):
    """Add 2FA to existing password"""
    pwd_id = callback.data.split(":")[1]
    
    await state.set_state(PasswordStates.editing_2fa)
    await state.update_data(editing_pwd_id=pwd_id, adding_2fa=True)
    
    await callback.message.edit_text(
        "🔐 <b>Добавление 2FA</b>\n\n"
        "Введите TOTP-секрет:\n\n"
        "<i>Обычно это длинный код из букв и цифр, "
        "который показывают при настройке 2FA</i>\n\n"
        "/cancel — отмена",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_edit2fa:"))
async def cb_pwd_edit_2fa(callback: CallbackQuery, state: FSMContext):
    """Edit existing 2FA"""
    pwd_id = callback.data.split(":")[1]
    
    await state.set_state(PasswordStates.editing_2fa)
    await state.update_data(editing_pwd_id=pwd_id, adding_2fa=False)
    
    await callback.message.edit_text(
        "🔐 <b>Изменение 2FA</b>\n\n"
        "Введите новый TOTP-секрет:\n\n"
        "<i>Напишите /clear чтобы удалить 2FA</i>\n"
        "<i>Напишите /cancel чтобы отменить</i>",
        parse_mode="HTML"
    )


@router.message(PasswordStates.editing_2fa)
async def process_edit_2fa(message: Message, state: FSMContext):
    """Process 2FA editing"""
    text = message.text.strip()
    
    if text == "/cancel":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    pwd_id = data.get("editing_pwd_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте: /unlock")
        return
    
    # Delete the message with secret for security
    try:
        await message.delete()
    except:
        pass
    
    if text == "/clear":
        await user_storage.update_password(pwd_id, totp_secret="", recovery_codes="")
        await state.clear()
        await message.answer("✅ 2FA удалён", reply_markup=get_main_keyboard())
        return
    
    await user_storage.update_password(pwd_id, totp_secret=text)
    
    # Ask for recovery codes
    await state.set_state(PasswordStates.editing_recovery)
    await message.answer(
        "✅ TOTP-секрет сохранён\n\n"
        "Введите коды восстановления (через запятую):\n\n"
        "<i>Напишите /skip чтобы пропустить</i>",
        parse_mode="HTML"
    )


@router.message(PasswordStates.editing_recovery)
async def process_edit_recovery(message: Message, state: FSMContext):
    """Process recovery codes editing"""
    text = message.text.strip()
    
    data = await state.get_data()
    pwd_id = data.get("editing_pwd_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте: /unlock")
        return
    
    # Delete the message with codes for security
    try:
        await message.delete()
    except:
        pass
    
    if text != "/skip":
        await user_storage.update_password(pwd_id, recovery_codes=text)
    
    await state.clear()
    await message.answer("✅ 2FA настроен!", reply_markup=get_main_keyboard())


@router.callback_query(F.data.startswith("pwd_history:"))
async def cb_pwd_history(callback: CallbackQuery):
    """Show password history"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    history = await user_storage.get_password_history(pwd_id)
    pwd_data = await user_storage.get_password_decrypted(pwd_id)
    
    if not history:
        await callback.answer("История пуста")
        return
    
    text = f"📜 <b>История паролей: {pwd_data['service_name']}</b>\n\n"
    
    for i, entry in enumerate(reversed(history), 1):
        date = entry["changed_at"][:10]
        text += f"{i}. <code>{entry['password']}</code> ({date})\n"
    
    text += "\n⚡ Нажмите на пароль чтобы скопировать\n⏱️ Сообщение удалится через 60 секунд"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"pwd_view:{pwd_id}")
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    # Auto-delete after 60 seconds
    import asyncio
    await asyncio.sleep(60)
    try:
        # Restore original view
        pwd_data = await user_storage.get_password_decrypted(pwd_id)
        if pwd_data:
            fav_icon = "⭐ " if pwd_data["is_favorite"] else ""
            restored_text = (
                f"{fav_icon}🔑 <b>{pwd_data['service_name']}</b>\n\n"
                f"👤 Логин: <code>{pwd_data['username']}</code>\n"
                f"🔒 Пароль: ••••••••••"
            )
            await callback.message.edit_text(
                restored_text,
                reply_markup=get_password_keyboard(
                    pwd_id, 
                    has_2fa=pwd_data.get("has_2fa", False),
                    history_count=pwd_data.get("history_count", 0)
                ),
                parse_mode="HTML"
            )
    except:
        pass


@router.callback_query(F.data.startswith("pwd_copy:"))
async def cb_pwd_copy(callback: CallbackQuery):
    """Copy password to clipboard hint"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    pwd_data = await user_storage.get_password_decrypted(pwd_id)
    
    if not pwd_data:
        await callback.answer("Запись не найдена")
        return
    
    # Send temporary message with password for copying
    msg = await callback.message.answer(
        f"<code>{pwd_data['password']}</code>\n\n"
        "⚡ Нажмите на пароль чтобы скопировать\n"
        "⏱️ Сообщение удалится через 30 секунд",
        parse_mode="HTML"
    )
    
    await callback.answer("Пароль отправлен ниже")
    
    # Delete message after 30 seconds
    import asyncio
    await asyncio.sleep(30)
    try:
        await msg.delete()
    except:
        pass


@router.callback_query(F.data.startswith("pwd_fav:"))
async def cb_pwd_fav(callback: CallbackQuery):
    """Toggle favorite status"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    pwd = await user_storage.get_password(pwd_id)
    
    if pwd:
        await user_storage.update_password(pwd_id, is_favorite=not pwd.is_favorite)
        status = "⭐ Добавлено в избранное" if not pwd.is_favorite else "Убрано из избранного"
        await callback.answer(status)
        
        # Refresh view
        pwd_data = await user_storage.get_password_decrypted(pwd_id)
        if pwd_data:
            fav_icon = "⭐ " if pwd_data["is_favorite"] else ""
            text = (
                f"{fav_icon}🔑 <b>{pwd_data['service_name']}</b>\n\n"
                f"👤 Логин: <code>{pwd_data['username']}</code>\n"
                f"🔒 Пароль: ••••••••••"
            )
            if pwd_data.get("has_2fa"):
                text += "\n🔐 2FA: Настроено ✅"
            
            await callback.message.edit_text(
                text,
                reply_markup=get_password_keyboard(
                    pwd_id,
                    has_2fa=pwd_data.get("has_2fa", False),
                    history_count=pwd_data.get("history_count", 0)
                ),
                parse_mode="HTML"
            )


@router.callback_query(F.data.startswith("pwd_delete:"))
async def cb_pwd_delete(callback: CallbackQuery):
    """Delete password"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    deleted = await user_storage.delete_password(pwd_id)
    
    if deleted:
        await callback.answer("🗑️ Пароль удалён")
        
        # Show passwords list
        passwords = await user_storage.get_passwords()
        text = f"🔐 <b>Хранилище паролей ({len(passwords)})</b>" if passwords else "🔐 <b>Хранилище паролей</b>\n\nПусто"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_passwords_list_keyboard(passwords),
            parse_mode="HTML"
        )
    else:
        await callback.answer("Пароль не найден")


@router.callback_query(F.data.startswith("pwd_edit:"))
async def cb_pwd_edit(callback: CallbackQuery, state: FSMContext):
    """Edit password entry"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    
    pwd_data = await user_storage.get_password_decrypted(pwd_id)
    if not pwd_data:
        await callback.answer("Запись не найдена")
        return
    
    # Show edit menu
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Изменить логин", callback_data=f"pwd_editlogin:{pwd_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔑 Изменить пароль", callback_data=f"pwd_editpwd:{pwd_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Изменить URL", callback_data=f"pwd_editurl:{pwd_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Изменить заметку", callback_data=f"pwd_editnotes:{pwd_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"pwd_view:{pwd_id}")
    )
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование: {pwd_data['service_name']}</b>\n\n"
        "Выберите что изменить:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_editlogin:"))
async def cb_pwd_editlogin(callback: CallbackQuery, state: FSMContext):
    """Start editing login"""
    pwd_id = callback.data.split(":")[1]
    await state.set_state(PasswordStates.editing_password)
    await state.update_data(editing_pwd_id=pwd_id, edit_field="login")
    
    await callback.message.edit_text(
        "👤 <b>Изменение логина</b>\n\n"
        "Введите новый логин:\n\n"
        "/cancel — отмена",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_editpwd:"))
async def cb_pwd_editpwd(callback: CallbackQuery, state: FSMContext):
    """Start editing password"""
    pwd_id = callback.data.split(":")[1]
    await state.set_state(PasswordStates.editing_password)
    await state.update_data(editing_pwd_id=pwd_id, edit_field="password")
    
    suggested = SecurePasswordGenerator.generate(length=16)
    
    await callback.message.edit_text(
        "🔑 <b>Изменение пароля</b>\n\n"
        "Введите новый пароль или используйте сгенерированный:\n\n"
        f"<code>{suggested}</code>\n\n"
        "⚠️ Старый пароль будет сохранён в истории\n\n"
        "/cancel — отмена",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_editurl:"))
async def cb_pwd_editurl(callback: CallbackQuery, state: FSMContext):
    """Start editing URL"""
    pwd_id = callback.data.split(":")[1]
    await state.set_state(PasswordStates.editing_password)
    await state.update_data(editing_pwd_id=pwd_id, edit_field="url")
    
    await callback.message.edit_text(
        "🔗 <b>Изменение URL</b>\n\n"
        "Введите новый URL:\n\n"
        "/clear — очистить URL\n"
        "/cancel — отмена",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_editnotes:"))
async def cb_pwd_editnotes(callback: CallbackQuery, state: FSMContext):
    """Start editing notes"""
    pwd_id = callback.data.split(":")[1]
    await state.set_state(PasswordStates.editing_password)
    await state.update_data(editing_pwd_id=pwd_id, edit_field="notes")
    
    await callback.message.edit_text(
        "📝 <b>Изменение заметки</b>\n\n"
        "Введите новую заметку:\n\n"
        "/clear — очистить заметку\n"
        "/cancel — отмена",
        parse_mode="HTML"
    )


@router.message(PasswordStates.editing_password)
async def process_edit_field(message: Message, state: FSMContext):
    """Process field editing"""
    text = message.text.strip()
    
    if text == "/cancel":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    pwd_id = data.get("editing_pwd_id")
    edit_field = data.get("edit_field")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте: /unlock")
        return
    
    # Delete the message with sensitive data for security
    try:
        await message.delete()
    except:
        pass
    
    if edit_field == "login":
        await user_storage.update_password(pwd_id, username=text)
        result = "✅ Логин изменён"
    elif edit_field == "password":
        # Password history is automatically saved in update_password
        await user_storage.update_password(pwd_id, password=text)
        result = "✅ Пароль изменён (старый сохранён в истории)"
    elif edit_field == "url":
        url = None if text == "/clear" else text
        await user_storage.update_password(pwd_id, url=url)
        result = "✅ URL изменён" if url else "✅ URL очищен"
    elif edit_field == "notes":
        notes = "" if text == "/clear" else text
        await user_storage.update_password(pwd_id, notes=notes)
        result = "✅ Заметка изменена" if notes else "✅ Заметка очищена"
    else:
        result = "❌ Ошибка"
    
    await state.clear()
    await message.answer(result, reply_markup=get_main_keyboard())


@router.callback_query(F.data == "pwd_new")
async def cb_pwd_new(callback: CallbackQuery, state: FSMContext):
    """Start creating new password"""
    await callback.message.delete()
    await start_create_password(callback.message, state)


@router.callback_query(F.data == "pwd_generate")
async def cb_pwd_generate(callback: CallbackQuery):
    """Show password generator"""
    password = SecurePasswordGenerator.generate(length=16)
    safe_password = html.escape(password)  # Экранируем HTML-сущности
    
    await callback.message.edit_text(
        f"🎲 <b>Генератор паролей</b>\n\n"
        f"<code>{safe_password}</code>\n\n"
        f"📊 Длина: 16 символов\n"
        f"✅ Буквы, цифры, спецсимволы\n\n"
        f"<i>Нажмите на пароль чтобы скопировать</i>",
        reply_markup=get_generator_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pwd_gen_new")
async def cb_pwd_gen_new(callback: CallbackQuery):
    """Generate new password"""
    password = SecurePasswordGenerator.generate(length=16)
    safe_password = html.escape(password)  # Экранируем HTML-сущности
    
    await callback.message.edit_text(
        f"🎲 <b>Генератор паролей</b>\n\n"
        f"<code>{safe_password}</code>\n\n"
        f"📊 Длина: 16 символов\n"
        f"✅ Буквы, цифры, спецсимволы\n\n"
        f"<i>Нажмите на пароль чтобы скопировать</i>",
        reply_markup=get_generator_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("🔄 Новый пароль сгенерирован")


@router.callback_query(F.data.startswith("pwd_gen:"))
async def cb_pwd_gen_length(callback: CallbackQuery):
    """Generate password with specific length"""
    length = int(callback.data.split(":")[1])
    password = SecurePasswordGenerator.generate(length=length)
    safe_password = html.escape(password)  # Экранируем HTML-сущности
    
    await callback.message.edit_text(
        f"🎲 <b>Генератор паролей</b>\n\n"
        f"<code>{safe_password}</code>\n\n"
        f"📊 Длина: {length} символов\n"
        f"✅ Буквы, цифры, спецсимволы\n\n"
        f"<i>Нажмите на пароль чтобы скопировать</i>",
        reply_markup=get_generator_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer(f"🔄 Сгенерирован пароль {length} символов")


@router.callback_query(F.data == "pwd_search")
async def cb_pwd_search(callback: CallbackQuery, state: FSMContext):
    """Start password search"""
    await state.set_state(PasswordStates.searching)
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пароля</b>\n\n"
        "Введите название сервиса для поиска:\n\n"
        "<i>/cancel - отмена</i>",
        parse_mode="HTML"
    )


@router.message(PasswordStates.searching)
async def process_search(message: Message, state: FSMContext):
    """Process password search"""
    text = message.text.strip()
    
    if text == "/cancel":
        await state.clear()
        await show_passwords_list(message)
        return
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    passwords = await user_storage.search_passwords(text)
    
    await state.clear()
    
    if not passwords:
        await message.answer(
            f"🔍 По запросу «{text}» ничего не найдено",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            f"🔍 <b>Результаты поиска ({len(passwords)})</b>",
            reply_markup=get_passwords_list_keyboard(passwords),
            parse_mode="HTML"
        )
