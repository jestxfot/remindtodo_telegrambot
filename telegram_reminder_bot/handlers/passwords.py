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
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.json_storage import storage
from crypto.encryption import SecurePasswordGenerator
from utils.keyboards import get_main_keyboard, get_cancel_keyboard

router = Router()


class PasswordStates(StatesGroup):
    """States for password operations"""
    waiting_for_service = State()
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_url = State()
    waiting_for_notes = State()
    searching = State()
    editing_password = State()
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


def get_password_keyboard(password_id: str):
    """Get keyboard for password actions"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="👁️ Показать пароль", callback_data=f"pwd_show:{password_id}"),
        InlineKeyboardButton(text="📋 Копировать", callback_data=f"pwd_copy:{password_id}")
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
    user_storage = await storage.get_user_storage(message.from_user.id)
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
    
    user_storage = await storage.get_user_storage(message.from_user.id)
    pwd = await user_storage.create_password(
        service_name=data["service_name"],
        username=data["username"],
        password=data["password"],
        url=data.get("url"),
        notes=notes
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Пароль сохранён!</b>\n\n"
        f"🔑 {pwd.service_name}\n\n"
        f"🔐 Данные надёжно зашифрованы AES-256-GCM",
        reply_markup=get_password_keyboard(pwd.id),
        parse_mode="HTML"
    )
    
    await message.answer("Вернуться в меню:", reply_markup=get_main_keyboard())


@router.callback_query(F.data == "pwd_list")
async def cb_pwd_list(callback: CallbackQuery):
    """Show passwords list"""
    user_storage = await storage.get_user_storage(callback.from_user.id)
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
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
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
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
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
    
    if pwd_data.get("notes"):
        text += f"📝 Заметка: {pwd_data['notes']}\n"
    
    text += f"\n<i>Изменён: {pwd_data.get('password_changed_at', '')[:10]}</i>"
    
    # Mark as used
    await user_storage.mark_password_used(pwd_id)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_password_keyboard(pwd_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pwd_show:"))
async def cb_pwd_show(callback: CallbackQuery):
    """Show password (temporary display)"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
    pwd_data = await user_storage.get_password_decrypted(pwd_id)
    
    if not pwd_data:
        await callback.answer("Запись не найдена")
        return
    
    # Show password in popup (disappears automatically)
    await callback.answer(
        f"🔑 {pwd_data['password']}",
        show_alert=True
    )


@router.callback_query(F.data.startswith("pwd_copy:"))
async def cb_pwd_copy(callback: CallbackQuery):
    """Copy password to clipboard hint"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
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
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
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
            await callback.message.edit_text(
                text,
                reply_markup=get_password_keyboard(pwd_id),
                parse_mode="HTML"
            )


@router.callback_query(F.data.startswith("pwd_delete:"))
async def cb_pwd_delete(callback: CallbackQuery):
    """Delete password"""
    pwd_id = callback.data.split(":")[1]
    
    user_storage = await storage.get_user_storage(callback.from_user.id)
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


@router.callback_query(F.data == "pwd_new")
async def cb_pwd_new(callback: CallbackQuery, state: FSMContext):
    """Start creating new password"""
    await callback.message.delete()
    await start_create_password(callback.message, state)


@router.callback_query(F.data == "pwd_generate")
async def cb_pwd_generate(callback: CallbackQuery):
    """Show password generator"""
    password = SecurePasswordGenerator.generate(length=16)
    
    await callback.message.edit_text(
        f"🎲 <b>Генератор паролей</b>\n\n"
        f"<code>{password}</code>\n\n"
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
    
    await callback.message.edit_text(
        f"🎲 <b>Генератор паролей</b>\n\n"
        f"<code>{password}</code>\n\n"
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
    
    await callback.message.edit_text(
        f"🎲 <b>Генератор паролей</b>\n\n"
        f"<code>{password}</code>\n\n"
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
    
    user_storage = await storage.get_user_storage(message.from_user.id)
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
