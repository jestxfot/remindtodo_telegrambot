"""
Authentication system - WebApp only

Security flow:
1. First use: User creates master password via WebApp
2. Every session: User enters password in WebApp to unlock vault
3. Password is NEVER stored - only hash for verification
4. Session token stored encrypted for persistent login
"""
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
from utils.timezone import now, parse_dt

# Store active sessions (user_id -> session_data)
_active_sessions: dict = {}


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
        "created_at": now().isoformat(),
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
        meta["last_login"] = now().isoformat()
        with open(meta_file, 'w') as f:
            json.dump(meta, f, indent=2)
    
    return is_valid, meta["salt"] if is_valid else None


def save_persistent_session(user_id: int, password: str, salt_b64: str, duration_key: str):
    """Save encrypted session for persistent login"""
    expires_at = now() + timedelta(minutes=SESSION_DURATIONS[duration_key])
    
    # Create session token
    session_token = secrets.token_hex(32)
    
    # Encrypt password with session token for later recovery
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
        "created_at": now().isoformat(),
        "expires_at": expires_at.isoformat()
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
    """Logout user (for WebApp)"""
    logout(user_id)


async def authenticate_user(user_id: int, password: str, duration_key: str = None) -> bool:
    """Authenticate user with password (for WebApp)"""
    is_valid, salt_b64 = verify_password(user_id, password)
    
    if not is_valid:
        return False
    
    # Use provided duration or default
    duration = duration_key if duration_key in SESSION_DURATIONS else DEFAULT_SESSION_DURATION
    
    # Create session with specified duration
    create_session(user_id, password, salt_b64, duration)
    save_persistent_session(user_id, password, salt_b64, duration)
    
    return True


async def create_user_password(user_id: int, password: str, duration_key: str = None) -> bool:
    """Create password for new user (for WebApp)"""
    if user_has_password(user_id):
        return False
    
    if len(password) < 4:
        return False
    
    # Save password hash
    salt_b64 = save_password_hash(user_id, password)
    
    # Use provided duration or default
    duration = duration_key if duration_key in SESSION_DURATIONS else DEFAULT_SESSION_DURATION
    
    # Create session
    create_session(user_id, password, salt_b64, duration)
    save_persistent_session(user_id, password, salt_b64, duration)
    
    return True


def get_session_info_dict(user_id: int) -> dict:
    """Get session info as dictionary (for WebApp)"""
    session = _active_sessions.get(user_id)
    if not session:
        return {"active": False}
    
    duration_labels = {
        "30min": "30 минут",
        "2hours": "2 часа",
        "1day": "1 день",
        "1week": "1 неделя",
        "1month": "1 месяц"
    }
    
    expires = session["expires_at"]
    remaining = expires - now()
    remaining_minutes = max(0, int(remaining.total_seconds() / 60))
    
    return {
        "active": True,
        "duration_key": session["duration_key"],
        "duration_label": duration_labels.get(session["duration_key"], "?"),
        "expires_at": expires.isoformat(),
        "remaining_minutes": remaining_minutes,
        "available_durations": [
            {"key": "30min", "label": "30 минут"},
            {"key": "2hours", "label": "2 часа"},
            {"key": "1day", "label": "1 день"},
            {"key": "1week", "label": "1 неделя"},
            {"key": "1month", "label": "1 месяц"},
        ]
    }


def update_session_duration(user_id: int, new_duration_key: str) -> bool:
    """Update session duration (for WebApp)"""
    if new_duration_key not in SESSION_DURATIONS:
        return False
    
    session = _active_sessions.get(user_id)
    if not session:
        return False
    
    # Get password from persistent session
    success, password, salt = load_persistent_session(user_id)
    if not success or not password or not salt:
        return False
    
    # Recreate session with new duration
    create_session(user_id, password, salt, new_duration_key)
    save_persistent_session(user_id, password, salt, new_duration_key)
    
    return True
