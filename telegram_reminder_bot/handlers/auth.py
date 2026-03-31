"""
Authentication handlers - Master password management with persistent sessions

Security flow:
1. First use: User creates master password
2. Every session: User enters password to unlock vault
3. Option to "Remember me" for longer sessions (up to 1 month)
4. Password is NEVER stored - only hash for verification
5. Session token stored encrypted for persistent login
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import datetime, timedelta
import hashlib
import secrets
import json
import os
import base64
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, SESSION_DURATIONS, DEFAULT_SESSION_DURATION
from crypto.encryption import CryptoManager, derive_key_from_password
from utils.keyboards import get_main_keyboard
from utils.timezone import format_dt, now, now_str, parse_dt

router = Router()

# Store active sessions (user_id -> session_data)
_active_sessions: dict = {}


class AuthStates(StatesGroup):
    """Authentication states"""
    creating_password = State()
    confirming_password = State()
    entering_password = State()
    changing_password = State()
    confirming_new_password = State()


def get_user_meta_file(user_id: int) -> Path:
    """Get path to user's metadata file"""
    data_dir = Path(DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f"user_{user_id}.meta.json"


def get_session_file(user_id: int) -> Path:
    """Get path to user's session file"""
    data_dir = Path(DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f"user_{user_id}.session.json"


def user_has_password(user_id: int) -> bool:
    """Check if user has set up a master password"""
    return get_user_meta_file(user_id).exists()


def save_password_hash(user_id: int, password: str) -> str:
    """Save password hash and salt"""
    salt = os.urandom(32)
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    ).hex()
    
    meta = {
        "version": "1.0",
        "created_at": now_str(),
        "password_hash": password_hash,
        "salt": salt_b64,
        "last_login": None
    }
    
    with open(get_user_meta_file(user_id), 'w') as f:
        json.dump(meta, f, indent=2)
    
    return salt_b64


def verify_password(user_id: int, password: str) -> tuple[bool, str | None]:
    """Verify password against stored hash"""
    meta_file = get_user_meta_file(user_id)
    if not meta_file.exists():
        return False, None
    
    with open(meta_file, 'r') as f:
        meta = json.load(f)
    
    salt = base64.b64decode(meta["salt"])
    stored_hash = meta["password_hash"]
    
    computed_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    ).hex()
    
    is_valid = secrets.compare_digest(stored_hash, computed_hash)
    
    if is_valid:
        meta["last_login"] = now_str()
        with open(meta_file, 'w') as f:
            json.dump(meta, f, indent=2)
    
    return is_valid, meta["salt"] if is_valid else None


def save_persistent_session(user_id: int, password: str, salt_b64: str, duration_key: str):
    """Save encrypted session for persistent login"""
    expires_at = now() + timedelta(minutes=SESSION_DURATIONS[duration_key])
    
    # Create session token
    session_token = secrets.token_hex(32)
    
    # Encrypt password with session token for later recovery
    # We use a derived key from the session token to encrypt the actual password
    session_key = hashlib.pbkdf2_hmac('sha256', session_token.encode(), salt_b64.encode(), 10000)
    
    from cryptography.fernet import Fernet
    fernet_key = base64.urlsafe_b64encode(session_key)
    fernet = Fernet(fernet_key)
    encrypted_password = fernet.encrypt(password.encode()).decode()
    
    session_data = {
        "version": "1.0",
        "session_token": session_token,
        "encrypted_password": encrypted_password,
        "salt": salt_b64,
        "duration": duration_key,
        "created_at": now_str(),
        "expires_at": format_dt(expires_at)
    }
    
    with open(get_session_file(user_id), 'w') as f:
        json.dump(session_data, f, indent=2)


def load_persistent_session(user_id: int) -> tuple[bool, str | None, str | None]:
    """
    Try to load persistent session
    Returns: (success, password, salt)
    """
    session_file = get_session_file(user_id)
    if not session_file.exists():
        return False, None, None
    
    try:
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        # Check expiration
        expires_at = parse_dt(session_data["expires_at"])
        if now() > expires_at:
            # Session expired, delete it
            os.remove(session_file)
            return False, None, None
        
        # Decrypt password
        session_token = session_data["session_token"]
        salt_b64 = session_data["salt"]
        
        session_key = hashlib.pbkdf2_hmac('sha256', session_token.encode(), salt_b64.encode(), 10000)
        
        from cryptography.fernet import Fernet
        fernet_key = base64.urlsafe_b64encode(session_key)
        fernet = Fernet(fernet_key)
        password = fernet.decrypt(session_data["encrypted_password"].encode()).decode()
        
        return True, password, salt_b64
        
    except Exception:
        # Invalid session, delete it
        if session_file.exists():
            os.remove(session_file)
        return False, None, None


def delete_persistent_session(user_id: int):
    """Delete persistent session file"""
    session_file = get_session_file(user_id)
    if session_file.exists():
        os.remove(session_file)


def create_session(user_id: int, password: str, salt_b64: str, duration_key: str = DEFAULT_SESSION_DURATION):
    """Create authenticated session with encryption key"""
    salt = base64.b64decode(salt_b64)
    key, _ = derive_key_from_password(password, salt)
    
    crypto = CryptoManager(master_key=key)
    crypto._salt = salt
    
    expires_at = now() + timedelta(minutes=SESSION_DURATIONS[duration_key])
    
    _active_sessions[user_id] = {
        "crypto": crypto,
        "created_at": now(),
        "last_activity": now(),
        "expires_at": expires_at,
        "duration_key": duration_key
    }


def get_session(user_id: int) -> CryptoManager | None:
    """Get active session's crypto manager"""
    session = _active_sessions.get(user_id)
    
    if not session:
        # Try to restore from persistent session
        success, password, salt = load_persistent_session(user_id)
        if success and password and salt:
            # Restore session
            # Get duration from session file
            session_file = get_session_file(user_id)
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            duration_key = session_data.get("duration", DEFAULT_SESSION_DURATION)
            
            create_session(user_id, password, salt, duration_key)
            return _active_sessions[user_id]["crypto"]
        return None
    
    # Check if session expired
    if now() > session["expires_at"]:
        del _active_sessions[user_id]
        delete_persistent_session(user_id)
        return None
    
    # Update last activity
    session["last_activity"] = now()
    return session["crypto"]


def is_authenticated(user_id: int) -> bool:
    """Check if user has active session"""
    return get_session(user_id) is not None


def logout(user_id: int):
    """Clear user session"""
    if user_id in _active_sessions:
        del _active_sessions[user_id]
    delete_persistent_session(user_id)


def get_crypto_for_user(user_id: int) -> CryptoManager | None:
    """Get crypto manager for authenticated user"""
    return get_session(user_id)


def logout_user(user_id: int):
    """Logout user (WebApp compatibility wrapper)"""
    logout(user_id)


async def authenticate_user(user_id: int, password: str, duration_key: str = None) -> bool:
    """Authenticate user with password (for WebApp API)"""
    is_valid, salt_b64 = verify_password(user_id, password)

    if not is_valid:
        return False

    duration = duration_key if duration_key in SESSION_DURATIONS else DEFAULT_SESSION_DURATION
    create_session(user_id, password, salt_b64, duration)
    save_persistent_session(user_id, password, salt_b64, duration)
    return True


async def create_user_password(user_id: int, password: str, duration_key: str = None) -> bool:
    """Create password for new user (for WebApp API)"""
    if user_has_password(user_id):
        return False

    if len(password) < 4:
        return False

    salt_b64 = save_password_hash(user_id, password)
    duration = duration_key if duration_key in SESSION_DURATIONS else DEFAULT_SESSION_DURATION
    create_session(user_id, password, salt_b64, duration)
    save_persistent_session(user_id, password, salt_b64, duration)
    return True


def get_session_info_dict(user_id: int) -> dict:
    """Get session info as dictionary (for WebApp API)"""
    session = _active_sessions.get(user_id)
    if not session:
        return {"active": False}

    duration_labels = {
        "30min": "30 минут",
        "2hours": "2 часа",
        "1day": "1 день",
        "1week": "1 неделя",
        "1month": "1 месяц",
    }

    expires = session["expires_at"]
    remaining = expires - now()
    remaining_minutes = max(0, int(remaining.total_seconds() / 60))

    return {
        "active": True,
        "duration_key": session["duration_key"],
        "duration_label": duration_labels.get(session["duration_key"], "?"),
        "expires_at": format_dt(expires),
        "remaining_minutes": remaining_minutes,
        "available_durations": [
            {"key": "30min", "label": "30 минут"},
            {"key": "2hours", "label": "2 часа"},
            {"key": "1day", "label": "1 день"},
            {"key": "1week", "label": "1 неделя"},
            {"key": "1month", "label": "1 месяц"},
        ],
    }


def update_session_duration(user_id: int, new_duration_key: str) -> bool:
    """Update session duration (for WebApp API)"""
    if new_duration_key not in SESSION_DURATIONS:
        return False

    session = _active_sessions.get(user_id)
    if not session:
        return False

    success, password, salt = load_persistent_session(user_id)
    if not success or not password or not salt:
        return False

    create_session(user_id, password, salt, new_duration_key)
    save_persistent_session(user_id, password, salt, new_duration_key)
    return True


def get_session_duration_keyboard(for_login: bool = True) -> InlineKeyboardBuilder:
    """Get keyboard for selecting session duration"""
    builder = InlineKeyboardBuilder()
    
    durations = [
        ("30 мин", "30min"),
        ("2 часа", "2hours"),
        ("1 день", "1day"),
        ("1 неделя", "1week"),
        ("1 месяц", "1month"),
    ]
    
    prefix = "session_dur" if for_login else "session_change"
    
    builder.row(
        InlineKeyboardButton(text=durations[0][0], callback_data=f"{prefix}:{durations[0][1]}"),
        InlineKeyboardButton(text=durations[1][0], callback_data=f"{prefix}:{durations[1][1]}")
    )
    builder.row(
        InlineKeyboardButton(text=durations[2][0], callback_data=f"{prefix}:{durations[2][1]}"),
        InlineKeyboardButton(text=durations[3][0], callback_data=f"{prefix}:{durations[3][1]}")
    )
    builder.row(
        InlineKeyboardButton(text=durations[4][0], callback_data=f"{prefix}:{durations[4][1]}")
    )
    
    return builder


def get_session_info(user_id: int) -> str:
    """Get session info string"""
    session = _active_sessions.get(user_id)
    if not session:
        return "Нет активной сессии"
    
    duration_names = {
        "30min": "30 минут",
        "2hours": "2 часа",
        "1day": "1 день",
        "1week": "1 неделя",
        "1month": "1 месяц"
    }
    
    expires = session["expires_at"]
    remaining = expires - now()
    
    if remaining.days > 0:
        remaining_str = f"{remaining.days} дн"
    elif remaining.seconds > 3600:
        remaining_str = f"{remaining.seconds // 3600} ч"
    else:
        remaining_str = f"{remaining.seconds // 60} мин"
    
    return f"⏱️ Сессия: {duration_names.get(session['duration_key'], '?')}\n⏳ Осталось: {remaining_str}"


# === Handlers ===

@router.message(Command("unlock"))
async def cmd_unlock(message: Message, state: FSMContext):
    """Unlock the vault with password"""
    if is_authenticated(message.from_user.id):
        session_info = get_session_info(message.from_user.id)
        await message.answer(
            f"🔓 Хранилище уже разблокировано!\n\n{session_info}\n\n"
            "Используйте /lock для блокировки",
            reply_markup=get_main_keyboard()
        )
        return
    
    if not user_has_password(message.from_user.id):
        await state.set_state(AuthStates.creating_password)
        await message.answer(
            "🔐 <b>Создание мастер-пароля</b>\n\n"
            "Это ваш первый вход. Создайте мастер-пароль для защиты данных.\n\n"
            "⚠️ <b>ВАЖНО:</b>\n"
            "• Запомните пароль — восстановить невозможно!\n"
            "• Минимум 8 символов\n"
            "• Используйте буквы, цифры и символы\n\n"
            "Введите мастер-пароль:",
            parse_mode="HTML"
        )
    else:
        await state.set_state(AuthStates.entering_password)
        await message.answer(
            "🔐 <b>Разблокировка хранилища</b>\n\n"
            "Введите ваш мастер-пароль:",
            parse_mode="HTML"
        )


@router.message(Command("lock"))
async def cmd_lock(message: Message):
    """Lock the vault"""
    logout(message.from_user.id)
    await message.answer(
        "🔒 Хранилище заблокировано\n\n"
        "Используйте /unlock для разблокировки"
    )


@router.message(Command("session"))
async def cmd_session(message: Message):
    """Show session info"""
    if not is_authenticated(message.from_user.id):
        await message.answer("🔒 Хранилище заблокировано. /unlock")
        return
    
    session_info = get_session_info(message.from_user.id)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Изменить срок", callback_data="session_menu")
    )
    builder.row(
        InlineKeyboardButton(text="🔒 Выйти", callback_data="session_logout")
    )
    
    await message.answer(
        f"🔐 <b>Информация о сессии</b>\n\n{session_info}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.message(Command("changepassword"))
async def cmd_change_password(message: Message, state: FSMContext):
    """Change master password"""
    if not is_authenticated(message.from_user.id):
        await message.answer("🔒 Сначала разблокируйте хранилище: /unlock")
        return
    
    await state.set_state(AuthStates.entering_password)
    await state.update_data(changing_password=True)
    await message.answer(
        "🔐 <b>Смена мастер-пароля</b>\n\n"
        "Введите текущий пароль:",
        parse_mode="HTML"
    )


@router.message(AuthStates.creating_password)
async def process_create_password(message: Message, state: FSMContext):
    """Process new password creation"""
    password = message.text.strip()
    
    try:
        await message.delete()
    except:
        pass
    
    if len(password) < 8:
        await message.answer(
            "⚠️ Пароль слишком короткий!\n"
            "Минимум 8 символов. Попробуйте ещё раз:"
        )
        return
    
    await state.update_data(new_password=password)
    await state.set_state(AuthStates.confirming_password)
    
    await message.answer(
        "✅ Пароль принят\n\n"
        "Введите пароль ещё раз для подтверждения:"
    )


@router.message(AuthStates.confirming_password)
async def process_confirm_password(message: Message, state: FSMContext):
    """Confirm new password"""
    password = message.text.strip()
    
    try:
        await message.delete()
    except:
        pass
    
    data = await state.get_data()
    original_password = data.get("new_password")
    
    if password != original_password:
        await state.set_state(AuthStates.creating_password)
        await message.answer(
            "❌ Пароли не совпадают!\n\n"
            "Введите мастер-пароль заново:"
        )
        return
    
    # Save password hash
    salt_b64 = save_password_hash(message.from_user.id, password)
    
    # Ask for session duration
    await state.update_data(password=password, salt=salt_b64)
    
    builder = get_session_duration_keyboard()
    
    await message.answer(
        "✅ <b>Мастер-пароль создан!</b>\n\n"
        "Выберите, как долго хранить сессию:\n\n"
        "💡 Чем дольше сессия, тем реже нужно вводить пароль",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    await state.clear()
    await state.update_data(pending_login=True, password=password, salt=salt_b64)


@router.message(AuthStates.entering_password)
async def process_enter_password(message: Message, state: FSMContext):
    """Process password entry"""
    password = message.text.strip()
    
    try:
        await message.delete()
    except:
        pass
    
    is_valid, salt_b64 = verify_password(message.from_user.id, password)
    
    if not is_valid:
        await message.answer(
            "❌ Неверный пароль!\n\n"
            "Попробуйте ещё раз:"
        )
        return
    
    data = await state.get_data()
    
    if data.get("changing_password"):
        await state.set_state(AuthStates.changing_password)
        await state.update_data(old_password=password, salt=salt_b64)
        await message.answer(
            "✅ Пароль верный\n\n"
            "Введите новый мастер-пароль:"
        )
        return
    
    # Ask for session duration
    await state.clear()
    await state.update_data(pending_login=True, password=password, salt=salt_b64)
    
    builder = get_session_duration_keyboard()
    
    await message.answer(
        "✅ Пароль верный!\n\n"
        "Выберите срок сессии:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("session_dur:"))
async def cb_session_duration(callback: CallbackQuery, state: FSMContext):
    """Handle session duration selection"""
    duration_key = callback.data.split(":")[1]
    
    data = await state.get_data()
    
    if not data.get("pending_login"):
        await callback.answer("Сессия истекла, введите пароль заново")
        return
    
    password = data.get("password")
    salt_b64 = data.get("salt")
    
    if not password or not salt_b64:
        await callback.answer("Ошибка, попробуйте /unlock")
        return
    
    # Create session
    create_session(callback.from_user.id, password, salt_b64, duration_key)
    
    # Save persistent session
    save_persistent_session(callback.from_user.id, password, salt_b64, duration_key)
    
    await state.clear()
    
    duration_names = {
        "30min": "30 минут",
        "2hours": "2 часа",
        "1day": "1 день",
        "1week": "1 неделю",
        "1month": "1 месяц"
    }
    
    await callback.message.edit_text(
        f"🔓 <b>Хранилище разблокировано!</b>\n\n"
        f"⏱️ Сессия сохранена на {duration_names.get(duration_key, duration_key)}\n\n"
        f"Теперь вам не нужно вводить пароль при каждом сообщении.",
        parse_mode="HTML"
    )
    
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )


@router.callback_query(F.data == "session_menu")
async def cb_session_menu(callback: CallbackQuery):
    """Show session duration change menu"""
    builder = get_session_duration_keyboard(for_login=False)
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="session_back")
    )
    
    await callback.message.edit_text(
        "🔄 <b>Изменить срок сессии</b>\n\n"
        "Выберите новый срок:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("session_change:"))
async def cb_session_change(callback: CallbackQuery):
    """Change session duration"""
    if not is_authenticated(callback.from_user.id):
        await callback.answer("🔒 Сессия истекла", show_alert=True)
        return
    
    duration_key = callback.data.split(":")[1]
    session = _active_sessions.get(callback.from_user.id)
    
    if session:
        # Update session
        new_expires = now() + timedelta(minutes=SESSION_DURATIONS[duration_key])
        session["expires_at"] = new_expires
        session["duration_key"] = duration_key
        
        # Update persistent session if exists
        session_file = get_session_file(callback.from_user.id)
        if session_file.exists():
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            session_data["expires_at"] = format_dt(new_expires)
            session_data["duration"] = duration_key
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
    
    duration_names = {
        "30min": "30 минут",
        "2hours": "2 часа",
        "1day": "1 день",
        "1week": "1 неделю",
        "1month": "1 месяц"
    }
    
    await callback.answer(f"✅ Сессия продлена на {duration_names.get(duration_key)}")
    
    session_info = get_session_info(callback.from_user.id)
    await callback.message.edit_text(
        f"🔐 <b>Сессия обновлена</b>\n\n{session_info}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "session_back")
async def cb_session_back(callback: CallbackQuery):
    """Go back to session info"""
    session_info = get_session_info(callback.from_user.id)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Изменить срок", callback_data="session_menu")
    )
    builder.row(
        InlineKeyboardButton(text="🔒 Выйти", callback_data="session_logout")
    )
    
    await callback.message.edit_text(
        f"🔐 <b>Информация о сессии</b>\n\n{session_info}",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "session_logout")
async def cb_session_logout(callback: CallbackQuery):
    """Logout from session"""
    logout(callback.from_user.id)
    await callback.message.edit_text(
        "🔒 <b>Вы вышли из системы</b>\n\n"
        "Используйте /unlock для входа",
        parse_mode="HTML"
    )


@router.message(AuthStates.changing_password)
async def process_new_password(message: Message, state: FSMContext):
    """Process new password when changing"""
    password = message.text.strip()
    
    try:
        await message.delete()
    except:
        pass
    
    if len(password) < 8:
        await message.answer(
            "⚠️ Пароль слишком короткий!\n"
            "Минимум 8 символов. Попробуйте ещё раз:"
        )
        return
    
    await state.update_data(new_password=password)
    await state.set_state(AuthStates.confirming_new_password)
    
    await message.answer("Подтвердите новый пароль:")


@router.message(AuthStates.confirming_new_password)
async def process_confirm_new_password(message: Message, state: FSMContext):
    """Confirm new password when changing"""
    password = message.text.strip()
    
    try:
        await message.delete()
    except:
        pass
    
    data = await state.get_data()
    
    if password != data.get("new_password"):
        await state.set_state(AuthStates.changing_password)
        await message.answer(
            "❌ Пароли не совпадают!\n\n"
            "Введите новый пароль:"
        )
        return
    
    # Update password
    salt_b64 = save_password_hash(message.from_user.id, password)
    
    # Re-create session with new password
    session = _active_sessions.get(message.from_user.id)
    duration_key = session["duration_key"] if session else DEFAULT_SESSION_DURATION
    
    create_session(message.from_user.id, password, salt_b64, duration_key)
    save_persistent_session(message.from_user.id, password, salt_b64, duration_key)
    
    await state.clear()
    
    await message.answer(
        "✅ <b>Пароль изменён!</b>\n\n"
        "🔓 Хранилище разблокировано",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
