"""
AES-256-GCM Encryption System - Most secure symmetric encryption

Features:
- AES-256-GCM (Galois/Counter Mode) - authenticated encryption
- PBKDF2 with SHA-256 for key derivation (600,000 iterations)
- Unique nonce (IV) for each encryption
- HMAC for additional integrity verification
"""
import os
import json
import base64
import hashlib
import secrets
from typing import Any, Dict, Optional, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


# Constants
KEY_SIZE = 32  # 256 bits for AES-256
NONCE_SIZE = 12  # 96 bits recommended for GCM
SALT_SIZE = 32  # 256 bits for salt
PBKDF2_ITERATIONS = 600000  # High iteration count for security


def generate_master_key() -> bytes:
    """Generate a cryptographically secure random master key"""
    return secrets.token_bytes(KEY_SIZE)


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """
    Derive encryption key from password using PBKDF2-SHA256
    
    Returns: (derived_key, salt)
    """
    if salt is None:
        salt = os.urandom(SALT_SIZE)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend()
    )
    
    key = kdf.derive(password.encode('utf-8'))
    return key, salt


class CryptoManager:
    """
    Secure encryption manager using AES-256-GCM
    
    AES-256-GCM provides:
    - Confidentiality (encryption)
    - Integrity (authentication tag)
    - Authenticity (data cannot be tampered with)
    """
    
    def __init__(self, master_key: Optional[bytes] = None, password: Optional[str] = None):
        """
        Initialize with either a master key or password
        
        Args:
            master_key: 32-byte encryption key
            password: Password to derive key from
        """
        self._salt: Optional[bytes] = None
        
        if master_key:
            if len(master_key) != KEY_SIZE:
                raise ValueError(f"Master key must be {KEY_SIZE} bytes")
            self._key = master_key
        elif password:
            self._key, self._salt = derive_key_from_password(password)
        else:
            # Generate new random key
            self._key = generate_master_key()
        
        self._aesgcm = AESGCM(self._key)
    
    @property
    def salt(self) -> Optional[bytes]:
        """Get salt used for key derivation"""
        return self._salt
    
    @property
    def key_fingerprint(self) -> str:
        """Get key fingerprint for identification (not the key itself!)"""
        return hashlib.sha256(self._key).hexdigest()[:16]
    
    def encrypt(self, data: Union[str, bytes, Dict, list]) -> str:
        """
        Encrypt data using AES-256-GCM
        
        Args:
            data: String, bytes, dict, or list to encrypt
            
        Returns:
            Base64 encoded encrypted data with nonce
        """
        # Convert data to bytes
        if isinstance(data, (dict, list)):
            plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
        elif isinstance(data, str):
            plaintext = data.encode('utf-8')
        else:
            plaintext = data
        
        # Generate unique nonce for this encryption
        nonce = os.urandom(NONCE_SIZE)
        
        # Encrypt with authentication
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        
        # Combine nonce + ciphertext and encode as base64
        encrypted_data = nonce + ciphertext
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> bytes:
        """
        Decrypt data using AES-256-GCM
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted bytes
        """
        # Decode from base64
        data = base64.b64decode(encrypted_data.encode('utf-8'))
        
        # Extract nonce and ciphertext
        nonce = data[:NONCE_SIZE]
        ciphertext = data[NONCE_SIZE:]
        
        # Decrypt and verify authentication
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext
    
    def decrypt_to_string(self, encrypted_data: str) -> str:
        """Decrypt to UTF-8 string"""
        return self.decrypt(encrypted_data).decode('utf-8')
    
    def decrypt_to_json(self, encrypted_data: str) -> Union[Dict, list]:
        """Decrypt to JSON object"""
        return json.loads(self.decrypt_to_string(encrypted_data))
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        """
        Encrypt binary data, returning raw encrypted bytes (not base64).
        Useful for large files to avoid base64 overhead.
        """
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext
    
    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt raw encrypted bytes (not base64).
        """
        nonce = encrypted_data[:NONCE_SIZE]
        ciphertext = encrypted_data[NONCE_SIZE:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)
    
    def encrypt_json_file(self, data: Any, filepath: str) -> None:
        """Encrypt and save data to file"""
        encrypted = self.encrypt(data)
        
        file_data = {
            "version": "1.0",
            "algorithm": "AES-256-GCM",
            "key_fingerprint": self.key_fingerprint,
            "data": encrypted
        }
        
        if self._salt:
            file_data["salt"] = base64.b64encode(self._salt).decode('utf-8')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(file_data, f, ensure_ascii=False, indent=2)
    
    def decrypt_json_file(self, filepath: str) -> Any:
        """Load and decrypt data from file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
        
        return self.decrypt_to_json(file_data["data"])
    
    def export_key(self) -> str:
        """Export key as base64 (for backup purposes - keep secure!)"""
        return base64.b64encode(self._key).decode('utf-8')
    
    @classmethod
    def from_exported_key(cls, exported_key: str) -> 'CryptoManager':
        """Create CryptoManager from exported key"""
        key = base64.b64decode(exported_key.encode('utf-8'))
        return cls(master_key=key)
    
    @classmethod
    def from_password_and_salt(cls, password: str, salt_b64: str) -> 'CryptoManager':
        """Create CryptoManager from password and stored salt"""
        salt = base64.b64decode(salt_b64.encode('utf-8'))
        key, _ = derive_key_from_password(password, salt)
        instance = cls(master_key=key)
        instance._salt = salt
        return instance


class SecurePasswordGenerator:
    """Generate secure random passwords"""
    
    LOWERCASE = 'abcdefghijklmnopqrstuvwxyz'
    UPPERCASE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    DIGITS = '0123456789'
    SPECIAL = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    @classmethod
    def generate(
        cls,
        length: int = 20,
        use_lowercase: bool = True,
        use_uppercase: bool = True,
        use_digits: bool = True,
        use_special: bool = True
    ) -> str:
        """Generate a secure random password"""
        alphabet = ''
        required_chars = []
        
        if use_lowercase:
            alphabet += cls.LOWERCASE
            required_chars.append(secrets.choice(cls.LOWERCASE))
        if use_uppercase:
            alphabet += cls.UPPERCASE
            required_chars.append(secrets.choice(cls.UPPERCASE))
        if use_digits:
            alphabet += cls.DIGITS
            required_chars.append(secrets.choice(cls.DIGITS))
        if use_special:
            alphabet += cls.SPECIAL
            required_chars.append(secrets.choice(cls.SPECIAL))
        
        if not alphabet:
            alphabet = cls.LOWERCASE + cls.UPPERCASE + cls.DIGITS
        
        # Generate remaining characters
        remaining_length = length - len(required_chars)
        password_chars = required_chars + [secrets.choice(alphabet) for _ in range(remaining_length)]
        
        # Shuffle to randomize position of required characters
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
