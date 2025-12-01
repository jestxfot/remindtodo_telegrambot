"""
Encrypted JSON Storage System with Master Password Protection

Security:
- All data encrypted with AES-256-GCM
- Encryption key derived from user's master password via PBKDF2
- Password NEVER stored - only hash for verification
- Each user has their own encrypted JSON file
"""
import os
import json
import asyncio
import aiofiles
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import uuid
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crypto.encryption import CryptoManager
from storage.models import User, Reminder, Todo, Note, Password, UserData
from config import DATA_DIR


class EncryptedJSONStorage:
    """
    Encrypted JSON file storage with master password protection
    
    All data is encrypted using AES-256-GCM.
    Key is derived from user's master password.
    """
    
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[int, asyncio.Lock] = {}
    
    def _get_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create lock for user"""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]
    
    def _get_user_file(self, user_id: int) -> Path:
        """Get path to user's encrypted data file"""
        return self.data_dir / f"user_{user_id}.encrypted.json"
    
    async def get_user_storage(self, user_id: int, crypto: CryptoManager) -> 'UserStorage':
        """Get user storage with provided crypto manager"""
        storage = UserStorage(self, user_id, crypto)
        await storage.load()
        return storage
    
    async def save_user_data(self, user_id: int, data: UserData, crypto: CryptoManager) -> None:
        """Save encrypted user data to file"""
        async with self._get_lock(user_id):
            filepath = self._get_user_file(user_id)
            
            # Encrypt the data
            encrypted_content = crypto.encrypt(data.to_dict())
            
            file_data = {
                "version": "2.0",
                "algorithm": "AES-256-GCM",
                "key_fingerprint": crypto.key_fingerprint,
                "user_id": user_id,
                "last_modified": datetime.utcnow().isoformat(),
                "data": encrypted_content
            }
            
            # Write atomically
            temp_path = filepath.with_suffix('.tmp')
            async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(file_data, ensure_ascii=False, indent=2))
            
            os.replace(temp_path, filepath)
    
    async def load_user_data(self, user_id: int, crypto: CryptoManager) -> Optional[UserData]:
        """Load and decrypt user data from file"""
        async with self._get_lock(user_id):
            filepath = self._get_user_file(user_id)
            
            if not filepath.exists():
                return None
            
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            file_data = json.loads(content)
            
            # Decrypt the data
            decrypted = crypto.decrypt_to_json(file_data["data"])
            return UserData.from_dict(decrypted)
    
    async def user_exists(self, user_id: int) -> bool:
        """Check if user data file exists"""
        return self._get_user_file(user_id).exists()
    
    async def get_all_user_ids(self) -> List[int]:
        """Get list of all user IDs with stored data"""
        user_ids = []
        for filepath in self.data_dir.glob("user_*.encrypted.json"):
            try:
                user_id = int(filepath.stem.split('_')[1].split('.')[0])
                user_ids.append(user_id)
            except (IndexError, ValueError):
                pass
        return user_ids


class UserStorage:
    """
    User-specific storage handler with encryption
    
    Requires authenticated crypto manager from user's session.
    """
    
    def __init__(self, storage: EncryptedJSONStorage, user_id: int, crypto: CryptoManager):
        self.storage = storage
        self.user_id = user_id
        self._crypto = crypto
        self._data: Optional[UserData] = None
        self._auto_save = True
    
    async def load(self) -> None:
        """Load user data from storage"""
        try:
            self._data = await self.storage.load_user_data(self.user_id, self._crypto)
        except Exception:
            self._data = None
        
        # Initialize empty data if needed
        if self._data is None:
            self._data = UserData(
                user=User(id=self.user_id)
            )
    
    async def save(self) -> None:
        """Save user data to storage"""
        if self._data and self._crypto:
            self._data.user.updated_at = datetime.utcnow().isoformat()
            await self.storage.save_user_data(self.user_id, self._data, self._crypto)
    
    async def _auto_save_if_enabled(self) -> None:
        """Auto-save if enabled"""
        if self._auto_save:
            await self.save()
    
    # User methods
    @property
    def user(self) -> User:
        return self._data.user
    
    async def update_user(self, **kwargs) -> User:
        """Update user fields"""
        for key, value in kwargs.items():
            if hasattr(self._data.user, key):
                setattr(self._data.user, key, value)
        self._data.user.updated_at = datetime.utcnow().isoformat()
        await self._auto_save_if_enabled()
        return self._data.user
    
    # Reminder methods
    async def create_reminder(self, **kwargs) -> Reminder:
        """Create a new reminder"""
        reminder = Reminder(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            **kwargs
        )
        self._data.reminders.append(reminder)
        await self._auto_save_if_enabled()
        return reminder
    
    async def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Get reminder by ID"""
        for r in self._data.reminders:
            if r.id == reminder_id:
                return r
        return None
    
    async def get_reminders(self, include_completed: bool = False) -> List[Reminder]:
        """Get all reminders"""
        if include_completed:
            return self._data.reminders.copy()
        return [r for r in self._data.reminders if r.status not in ['completed', 'cancelled']]
    
    async def update_reminder(self, reminder_id: str, **kwargs) -> Optional[Reminder]:
        """Update a reminder"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            for key, value in kwargs.items():
                if hasattr(reminder, key):
                    setattr(reminder, key, value)
            reminder.updated_at = datetime.utcnow().isoformat()
            await self._auto_save_if_enabled()
        return reminder
    
    async def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder"""
        for i, r in enumerate(self._data.reminders):
            if r.id == reminder_id:
                self._data.reminders.pop(i)
                await self._auto_save_if_enabled()
                return True
        return False
    
    # Todo methods
    async def create_todo(self, **kwargs) -> Todo:
        """Create a new todo"""
        max_order = max([t.order for t in self._data.todos], default=0)
        todo = Todo(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            order=max_order + 1,
            **kwargs
        )
        self._data.todos.append(todo)
        await self._auto_save_if_enabled()
        return todo
    
    async def get_todo(self, todo_id: str) -> Optional[Todo]:
        """Get todo by ID"""
        for t in self._data.todos:
            if t.id == todo_id:
                return t
        return None
    
    async def get_todos(self, include_completed: bool = False) -> List[Todo]:
        """Get all todos"""
        todos = self._data.todos.copy()
        if not include_completed:
            todos = [t for t in todos if t.status not in ['completed', 'cancelled']]
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        todos.sort(key=lambda t: (priority_order.get(t.priority, 2), t.order))
        return todos
    
    async def update_todo(self, todo_id: str, **kwargs) -> Optional[Todo]:
        """Update a todo"""
        todo = await self.get_todo(todo_id)
        if todo:
            for key, value in kwargs.items():
                if hasattr(todo, key):
                    setattr(todo, key, value)
            todo.updated_at = datetime.utcnow().isoformat()
            await self._auto_save_if_enabled()
        return todo
    
    async def delete_todo(self, todo_id: str) -> bool:
        """Delete a todo"""
        for i, t in enumerate(self._data.todos):
            if t.id == todo_id:
                self._data.todos.pop(i)
                await self._auto_save_if_enabled()
                return True
        return False
    
    # Note methods
    async def create_note(self, title: str, content: str, **kwargs) -> Note:
        """Create a new encrypted note"""
        encrypted_content = self._crypto.encrypt(content)
        
        note = Note(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            title=title,
            content=encrypted_content,
            **kwargs
        )
        self._data.notes.append(note)
        await self._auto_save_if_enabled()
        return note
    
    async def get_note(self, note_id: str) -> Optional[Note]:
        """Get note by ID"""
        for n in self._data.notes:
            if n.id == note_id:
                return n
        return None
    
    async def get_note_decrypted(self, note_id: str) -> Optional[tuple[Note, str]]:
        """Get note with decrypted content"""
        note = await self.get_note(note_id)
        if note:
            decrypted_content = self._crypto.decrypt_to_string(note.content)
            return note, decrypted_content
        return None
    
    async def get_notes(self) -> List[Note]:
        """Get all notes"""
        notes = self._data.notes.copy()
        notes.sort(key=lambda n: (not n.is_pinned, n.updated_at), reverse=True)
        return notes
    
    async def update_note(self, note_id: str, title: Optional[str] = None, content: Optional[str] = None, **kwargs) -> Optional[Note]:
        """Update a note"""
        note = await self.get_note(note_id)
        if note:
            if title:
                note.title = title
            if content:
                note.content = self._crypto.encrypt(content)
            for key, value in kwargs.items():
                if hasattr(note, key) and key not in ['title', 'content']:
                    setattr(note, key, value)
            note.updated_at = datetime.utcnow().isoformat()
            await self._auto_save_if_enabled()
        return note
    
    async def delete_note(self, note_id: str) -> bool:
        """Delete a note"""
        for i, n in enumerate(self._data.notes):
            if n.id == note_id:
                self._data.notes.pop(i)
                await self._auto_save_if_enabled()
                return True
        return False
    
    # Password methods
    async def create_password(
        self,
        service_name: str,
        username: str,
        password: str,
        url: Optional[str] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> Password:
        """Create a new encrypted password entry"""
        encrypted_username = self._crypto.encrypt(username)
        encrypted_password = self._crypto.encrypt(password)
        encrypted_notes = self._crypto.encrypt(notes) if notes else None
        
        pwd = Password(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            service_name=service_name,
            username=encrypted_username,
            password=encrypted_password,
            url=url,
            notes=encrypted_notes,
            password_changed_at=datetime.utcnow().isoformat(),
            **kwargs
        )
        self._data.passwords.append(pwd)
        await self._auto_save_if_enabled()
        return pwd
    
    async def get_password(self, password_id: str) -> Optional[Password]:
        """Get password entry by ID"""
        for p in self._data.passwords:
            if p.id == password_id:
                return p
        return None
    
    async def get_password_decrypted(self, password_id: str) -> Optional[Dict[str, Any]]:
        """Get password with decrypted fields"""
        pwd = await self.get_password(password_id)
        if pwd:
            return {
                "id": pwd.id,
                "service_name": pwd.service_name,
                "username": self._crypto.decrypt_to_string(pwd.username),
                "password": self._crypto.decrypt_to_string(pwd.password),
                "url": pwd.url,
                "notes": self._crypto.decrypt_to_string(pwd.notes) if pwd.notes else None,
                "category": pwd.category,
                "is_favorite": pwd.is_favorite,
                "last_used": pwd.last_used,
                "password_changed_at": pwd.password_changed_at,
                "created_at": pwd.created_at
            }
        return None
    
    async def get_passwords(self) -> List[Password]:
        """Get all password entries"""
        passwords = self._data.passwords.copy()
        passwords.sort(key=lambda p: (not p.is_favorite, p.service_name.lower()))
        return passwords
    
    async def search_passwords(self, query: str) -> List[Password]:
        """Search passwords by service name"""
        query = query.lower()
        return [p for p in self._data.passwords if query in p.service_name.lower()]
    
    async def update_password(
        self,
        password_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> Optional[Password]:
        """Update a password entry"""
        pwd = await self.get_password(password_id)
        if pwd:
            if username:
                pwd.username = self._crypto.encrypt(username)
            if password:
                pwd.password = self._crypto.encrypt(password)
                pwd.password_changed_at = datetime.utcnow().isoformat()
            if notes is not None:
                pwd.notes = self._crypto.encrypt(notes) if notes else None
            for key, value in kwargs.items():
                if hasattr(pwd, key) and key not in ['username', 'password', 'notes']:
                    setattr(pwd, key, value)
            pwd.updated_at = datetime.utcnow().isoformat()
            await self._auto_save_if_enabled()
        return pwd
    
    async def delete_password(self, password_id: str) -> bool:
        """Delete a password entry"""
        for i, p in enumerate(self._data.passwords):
            if p.id == password_id:
                self._data.passwords.pop(i)
                await self._auto_save_if_enabled()
                return True
        return False
    
    async def mark_password_used(self, password_id: str) -> Optional[Password]:
        """Mark password as used"""
        return await self.update_password(password_id, last_used=datetime.utcnow().isoformat())
    
    # Statistics
    async def get_statistics(self) -> Dict[str, Any]:
        """Get user statistics"""
        todos = self._data.todos
        reminders = self._data.reminders
        
        return {
            "todos": {
                "total": len(todos),
                "completed": len([t for t in todos if t.status == 'completed']),
                "pending": len([t for t in todos if t.status == 'pending']),
                "in_progress": len([t for t in todos if t.status == 'in_progress']),
                "overdue": len([t for t in todos if t.is_overdue])
            },
            "reminders": {
                "total": len(reminders),
                "pending": len([r for r in reminders if r.status == 'pending']),
                "active": len([r for r in reminders if r.status == 'active']),
                "completed": len([r for r in reminders if r.status == 'completed'])
            },
            "notes": len(self._data.notes),
            "passwords": len(self._data.passwords)
        }


# Global storage instance
storage = EncryptedJSONStorage()
