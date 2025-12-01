"""
Data models for JSON storage
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class RecurrenceType(str, Enum):
    """Types of recurring reminders"""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class ReminderStatus(str, Enum):
    """Status of a reminder"""
    PENDING = "pending"
    ACTIVE = "active"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoStatus(str, Enum):
    """Status of a todo item"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    """Priority levels for todos"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


def datetime_to_str(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO string"""
    return dt.isoformat() if dt else None


def str_to_datetime(s: Optional[str]) -> Optional[datetime]:
    """Convert ISO string to datetime"""
    return datetime.fromisoformat(s) if s else None


@dataclass
class User:
    """User model"""
    id: int  # Telegram ID
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: str = "Europe/Moscow"
    master_password_hash: Optional[str] = None  # For password vault
    encryption_salt: Optional[str] = None
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        return cls(**data)


@dataclass
class Reminder:
    """Reminder model"""
    id: str
    user_id: int
    title: str
    description: Optional[str] = None
    remind_at: str = ""  # ISO datetime
    status: str = ReminderStatus.PENDING.value
    recurrence_type: str = RecurrenceType.NONE.value
    recurrence_interval: Optional[int] = None
    recurrence_end_date: Optional[str] = None
    is_persistent: bool = True
    persistent_interval: int = 60
    with_sound: bool = True
    snooze_count: int = 0
    snoozed_until: Optional[str] = None
    last_notification_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reminder':
        return cls(**data)
    
    @property
    def is_recurring(self) -> bool:
        return self.recurrence_type != RecurrenceType.NONE.value
    
    @property
    def remind_at_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.remind_at)
    
    @property
    def snoozed_until_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.snoozed_until)


@dataclass
class Todo:
    """Todo item model"""
    id: str
    user_id: int
    title: str
    description: Optional[str] = None
    status: str = TodoStatus.PENDING.value
    priority: str = TodoPriority.MEDIUM.value
    deadline: Optional[str] = None
    order: int = 0
    completed_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Todo':
        return cls(**data)
    
    @property
    def deadline_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.deadline)
    
    @property
    def is_overdue(self) -> bool:
        if not self.deadline:
            return False
        deadline = str_to_datetime(self.deadline)
        return deadline and datetime.utcnow() > deadline and self.status not in [TodoStatus.COMPLETED.value, TodoStatus.CANCELLED.value]
    
    @property
    def priority_emoji(self) -> str:
        emojis = {
            TodoPriority.LOW.value: "🟢",
            TodoPriority.MEDIUM.value: "🟡",
            TodoPriority.HIGH.value: "🟠",
            TodoPriority.URGENT.value: "🔴"
        }
        return emojis.get(self.priority, "⚪")
    
    @property
    def status_emoji(self) -> str:
        emojis = {
            TodoStatus.PENDING.value: "⏳",
            TodoStatus.IN_PROGRESS.value: "🔄",
            TodoStatus.COMPLETED.value: "✅",
            TodoStatus.CANCELLED.value: "❌"
        }
        return emojis.get(self.status, "❓")


@dataclass
class Note:
    """Encrypted note model"""
    id: str
    user_id: int
    title: str
    content: str  # Encrypted content
    tags: List[str] = field(default_factory=list)
    is_pinned: bool = False
    color: str = "default"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Note':
        return cls(**data)


@dataclass
class Password:
    """Encrypted password entry"""
    id: str
    user_id: int
    service_name: str  # Website/app name
    username: str  # Login/email (encrypted)
    password: str  # Password (encrypted)
    url: Optional[str] = None
    notes: Optional[str] = None  # Encrypted notes
    category: str = "general"
    is_favorite: bool = False
    last_used: Optional[str] = None
    password_changed_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Password':
        return cls(**data)


@dataclass
class UserData:
    """Complete user data structure for JSON storage"""
    user: User
    reminders: List[Reminder] = field(default_factory=list)
    todos: List[Todo] = field(default_factory=list)
    notes: List[Note] = field(default_factory=list)
    passwords: List[Password] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user": self.user.to_dict(),
            "reminders": [r.to_dict() for r in self.reminders],
            "todos": [t.to_dict() for t in self.todos],
            "notes": [n.to_dict() for n in self.notes],
            "passwords": [p.to_dict() for p in self.passwords]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserData':
        return cls(
            user=User.from_dict(data["user"]),
            reminders=[Reminder.from_dict(r) for r in data.get("reminders", [])],
            todos=[Todo.from_dict(t) for t in data.get("todos", [])],
            notes=[Note.from_dict(n) for n in data.get("notes", [])],
            passwords=[Password.from_dict(p) for p in data.get("passwords", [])]
        )
