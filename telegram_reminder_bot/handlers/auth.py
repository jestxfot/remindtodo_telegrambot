"""
Authentication handlers - Master password management

Security flow:
1. First use: User creates master password
2. Every session: User enters password to unlock vault
3. Password is NEVER stored - only hash for verification
4. Encryption key is derived from password using PBKDF2
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, AUTO_LOCK_MINUTES
from crypto.encryption import CryptoManager, derive_key_from_password
from utils.keyboards import get_main_keyboard

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
    """Get path to user's metadata file (contains password hash, salt)"""
    data_dir = Path(DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f"user_{user_id}.meta.json"


def user_has_password(user_id: int) -> bool:
    """Check if user has set up a master password"""
    meta_file = get_user_meta_file(user_id)
    return meta_file.exists()


def save_password_hash(user_id: int, password: str) -> str:
    """
    Save password hash and salt (NOT the password itself!)
    Returns the salt for key derivation
    """
    import base64
    
    # Generate salt for PBKDF2
    salt = os.urandom(32)
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    
    # Create password hash for verification (different from encryption key!)
    # Using SHA-256 with salt for password verification
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000  # iterations for hash verification
    ).hex()
    
    meta = {
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat(),
        "password_hash": password_hash,
        "salt": salt_b64,
        "last_login": None
    }
    
    meta_file = get_user_meta_file(user_id)
    with open(meta_file, 'w') as f:
        json.dump(meta, f, indent=2)
    
    return salt_b64


def verify_password(user_id: int, password: str) -> tuple[bool, str | None]:
    """
    Verify password against stored hash
    Returns: (is_valid, salt_b64)
    """
    import base64
    
    meta_file = get_user_meta_file(user_id)
    if not meta_file.exists():
        return False, None
    
    with open(meta_file, 'r') as f:
        meta = json.load(f)
    
    salt = base64.b64decode(meta["salt"])
    stored_hash = meta["password_hash"]
    
    # Compute hash of provided password
    computed_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    ).hex()
    
    # Constant-time comparison
    is_valid = hmac_compare(stored_hash, computed_hash)
    
    if is_valid:
        # Update last login
        meta["last_login"] = datetime.utcnow().isoformat()
        with open(meta_file, 'w') as f:
            json.dump(meta, f, indent=2)
    
    return is_valid, meta["salt"] if is_valid else None


def hmac_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks"""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def create_session(user_id: int, password: str, salt_b64: str):
    """Create authenticated session with encryption key"""
    import base64
    
    salt = base64.b64decode(salt_b64)
    
    # Derive encryption key from password
    key, _ = derive_key_from_password(password, salt)
    
    # Create crypto manager
    crypto = CryptoManager(master_key=key)
    crypto._salt = salt
    
    _active_sessions[user_id] = {
        "crypto": crypto,
        "created_at": datetime.utcnow(),
        "last_activity": datetime.utcnow()
    }


def get_session(user_id: int) -> CryptoManager | None:
    """Get active session's crypto manager"""
    session = _active_sessions.get(user_id)
    
    if not session:
        return None
    
    # Check if session expired
    if datetime.utcnow() - session["last_activity"] > timedelta(minutes=AUTO_LOCK_MINUTES):
        del _active_sessions[user_id]
        return None
    
    # Update last activity
    session["last_activity"] = datetime.utcnow()
    return session["crypto"]


def is_authenticated(user_id: int) -> bool:
    """Check if user has active session"""
    return get_session(user_id) is not None


def logout(user_id: int):
    """Clear user session"""
    if user_id in _active_sessions:
        del _active_sessions[user_id]


def get_crypto_for_user(user_id: int) -> CryptoManager | None:
    """Get crypto manager for authenticated user"""
    return get_session(user_id)


# === Handlers ===

@router.message(Command("unlock"))
async def cmd_unlock(message: Message, state: FSMContext):
    """Unlock the vault with password"""
    if is_authenticated(message.from_user.id):
        await message.answer(
            "🔓 Хранилище уже разблокировано!\n\n"
            "Используйте /lock для блокировки",
            reply_markup=get_main_keyboard()
        )
        return
    
    if not user_has_password(message.from_user.id):
        # First time user - create password
        await state.set_state(AuthStates.creating_password)
        await message.answer(
            "🔐 <b>Создание мастер-пароля</b>\n\n"
            "Это ваш первый вход. Создайте мастер-пароль для защиты данных.\n\n"
            "⚠️ <b>ВАЖНО:</b>\n"
            "• Запомните пароль — восстановить его невозможно!\n"
            "• Минимум 8 символов\n"
            "• Используйте буквы, цифры и символы\n\n"
            "Введите мастер-пароль:",
            parse_mode="HTML"
        )
    else:
        # Existing user - enter password
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
    
    # Delete message with password for security
    try:
        await message.delete()
    except:
        pass
    
    # Validate password
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
    
    # Save password hash and create session
    salt_b64 = save_password_hash(message.from_user.id, password)
    create_session(message.from_user.id, password, salt_b64)
    
    await state.clear()
    
    await message.answer(
        "✅ <b>Мастер-пароль создан!</b>\n\n"
        "🔓 Хранилище разблокировано\n\n"
        "⚠️ Запомните пароль — восстановить его невозможно!\n\n"
        "Теперь вы можете использовать бота.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


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
        # User wants to change password
        await state.set_state(AuthStates.changing_password)
        await state.update_data(old_password=password, salt=salt_b64)
        await message.answer(
            "✅ Пароль верный\n\n"
            "Введите новый мастер-пароль:"
        )
        return
    
    # Normal login
    create_session(message.from_user.id, password, salt_b64)
    await state.clear()
    
    await message.answer(
        "🔓 <b>Хранилище разблокировано!</b>\n\n"
        f"⏱️ Автоблокировка через {AUTO_LOCK_MINUTES} минут неактивности",
        reply_markup=get_main_keyboard(),
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
    
    # TODO: Re-encrypt all data with new key
    # For now, just update the password hash
    salt_b64 = save_password_hash(message.from_user.id, password)
    create_session(message.from_user.id, password, salt_b64)
    
    await state.clear()
    
    await message.answer(
        "✅ <b>Пароль изменён!</b>\n\n"
        "🔓 Хранилище разблокировано",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
