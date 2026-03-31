"""
Data models for JSON storage
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json
from utils.timezone import MSK, now, now_str, parse_dt, format_dt


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
    """Convert datetime to storage ISO string (MSK, without tz info)."""
    return format_dt(dt) if dt else None


def str_to_datetime(s: Optional[str]) -> Optional[datetime]:
    """Convert ISO string (with/without tz) to aware datetime in MSK."""
    return parse_dt(s) if s else None


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
    reminder_interval_minutes: int = 5  # Persistent reminder interval in minutes
    bot_blocked_at: Optional[str] = None
    bot_block_reason: Optional[str] = None
    # Backup settings
    backup_enabled: bool = False  # Daily backup to Telegram
    backup_hour: int = 3  # Hour to send backup (0-23, default 3:00)
    last_backup_at: Optional[str] = None  # Last backup timestamp
    created_at: str = field(default_factory=now_str)
    updated_at: str = field(default_factory=now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        # Handle legacy data without backup fields
        if 'backup_enabled' not in data:
            data['backup_enabled'] = False
        if 'reminder_interval_minutes' not in data:
            data['reminder_interval_minutes'] = 5
        if 'bot_blocked_at' not in data:
            data['bot_blocked_at'] = None
        if 'bot_block_reason' not in data:
            data['bot_block_reason'] = None
        if 'backup_hour' not in data:
            data['backup_hour'] = 3
        if 'last_backup_at' not in data:
            data['last_backup_at'] = None
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
    recurrence_end_date: Optional[str] = None  # When recurring reminder ends
    recurrence_count: int = 0  # How many times reminder has triggered
    is_persistent: bool = True
    persistent_interval: int = 300
    with_sound: bool = True
    snooze_count: int = 0
    snoozed_until: Optional[str] = None
    last_notification_at: Optional[str] = None
    archived_at: Optional[str] = None  # When moved to archive
    attachments: List[Dict[str, Any]] = field(default_factory=list)  # List of Attachment dicts
    tags: List[str] = field(default_factory=list)  # Tags for categorization
    links: List[str] = field(default_factory=list)  # Clickable URLs
    created_at: str = field(default_factory=now_str)
    updated_at: str = field(default_factory=now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reminder':
        # Handle legacy data
        if 'recurrence_count' not in data:
            data['recurrence_count'] = 0
        if 'archived_at' not in data:
            data['archived_at'] = None
        if 'attachments' not in data:
            data['attachments'] = []
        if 'tags' not in data:
            data['tags'] = []
        if 'links' not in data:
            data['links'] = []
        return cls(**data)
    
    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0
    
    @property
    def has_links(self) -> bool:
        return len(self.links) > 0
    
    @property
    def is_recurring(self) -> bool:
        return self.recurrence_type != RecurrenceType.NONE.value
    
    @property
    def remind_at_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.remind_at)
    
    @property
    def snoozed_until_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.snoozed_until)
    
    @property
    def recurrence_end_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.recurrence_end_date)
    
    @property
    def is_recurrence_ended(self) -> bool:
        """Check if recurring reminder has reached its end date"""
        if not self.is_recurring or not self.recurrence_end_date:
            return False
        end_dt = self.recurrence_end_dt
        return bool(end_dt and now() > end_dt)


@dataclass
class Subtask:
    """Subtask model for Todo items"""
    id: str
    title: str
    completed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Todo:
    """Todo item model"""
    id: str
    user_id: int
    title: str
    description: Optional[str] = None
    status: str = TodoStatus.PENDING.value
    priority: str = TodoPriority.MEDIUM.value
    progress: int = 0  # 0-100 percent completion
    deadline: Optional[str] = None
    order: int = 0
    # Recurrence fields
    recurrence_type: str = RecurrenceType.NONE.value
    recurrence_interval: Optional[int] = None
    recurrence_end_date: Optional[str] = None  # When recurring todo ends
    recurrence_count: int = 0  # How many times todo was completed
    # Additional fields (like notes/reminders)
    subtasks: List[Dict[str, Any]] = field(default_factory=list)  # List of subtask dicts
    attachments: List[Dict[str, Any]] = field(default_factory=list)  # List of Attachment dicts
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    # Timestamps
    completed_at: Optional[str] = None
    archived_at: Optional[str] = None  # When moved to archive
    created_at: str = field(default_factory=now_str)
    updated_at: str = field(default_factory=now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Todo':
        # Handle legacy data
        if 'recurrence_type' not in data:
            data['recurrence_type'] = RecurrenceType.NONE.value
        if 'recurrence_interval' not in data:
            data['recurrence_interval'] = None
        if 'recurrence_end_date' not in data:
            data['recurrence_end_date'] = None
        if 'recurrence_count' not in data:
            data['recurrence_count'] = 0
        if 'progress' not in data:
            data['progress'] = 100 if data.get('status') == 'completed' else 0
        if 'archived_at' not in data:
            data['archived_at'] = None
        if 'subtasks' not in data:
            data['subtasks'] = []
        if 'attachments' not in data:
            data['attachments'] = []
        if 'tags' not in data:
            data['tags'] = []
        if 'links' not in data:
            data['links'] = []
        return cls(**data)
    
    @property
    def deadline_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.deadline)
    
    @property
    def recurrence_end_dt(self) -> Optional[datetime]:
        return str_to_datetime(self.recurrence_end_date)
    
    @property
    def is_recurring(self) -> bool:
        return self.recurrence_type != RecurrenceType.NONE.value
    
    @property
    def is_recurrence_ended(self) -> bool:
        """Check if recurring todo has reached its end date"""
        if not self.is_recurring or not self.recurrence_end_date:
            return False
        end_dt = self.recurrence_end_dt
        return bool(end_dt and now() > end_dt)

    @property
    def is_overdue(self) -> bool:
        if not self.deadline:
            return False
        deadline = self.deadline_dt
        return bool(
            deadline
            and now() > deadline
            and self.status not in [TodoStatus.COMPLETED.value, TodoStatus.CANCELLED.value]
        )
    
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
    
    @property
    def recurrence_emoji(self) -> str:
        if not self.is_recurring:
            return ""
        emojis = {
            RecurrenceType.DAILY.value: "🔄",
            RecurrenceType.WEEKLY.value: "📅",
            RecurrenceType.MONTHLY.value: "🗓️",
            RecurrenceType.YEARLY.value: "📆",
            RecurrenceType.CUSTOM.value: "⚙️"
        }
        return emojis.get(self.recurrence_type, "🔁")


@dataclass
class Attachment:
    """File attachment model"""
    id: str
    filename: str  # Original filename
    file_type: str  # mime type (image/jpeg, application/pdf, video/mp4)
    file_size: int  # Size in bytes
    file_path: str  # Path to encrypted file on disk
    thumbnail_path: Optional[str] = None  # Path to thumbnail for images/videos
    created_at: str = field(default_factory=now_str)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Attachment':
        return cls(**data)
    
    @property
    def is_image(self) -> bool:
        return self.file_type.startswith('image/')
    
    @property
    def is_video(self) -> bool:
        return self.file_type.startswith('video/')
    
    @property
    def is_pdf(self) -> bool:
        return self.file_type == 'application/pdf'
    
    @property
    def file_size_mb(self) -> float:
        return round(self.file_size / (1024 * 1024), 2)


class NoteStatus(str, Enum):
    """Status of a note"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


@dataclass
class Note:
    """Encrypted note model"""
    id: str
    user_id: int
    title: str
    content: str  # Encrypted content
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)  # Clickable URLs
    status: str = NoteStatus.ACTIVE.value
    is_pinned: bool = False
    color: str = "default"
    attachments: List[Dict[str, Any]] = field(default_factory=list)  # List of Attachment dicts
    created_at: str = field(default_factory=now_str)
    updated_at: str = field(default_factory=now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Note':
        if 'attachments' not in data:
            data['attachments'] = []
        if 'links' not in data:
            data['links'] = []
        if 'status' not in data:
            data['status'] = NoteStatus.ACTIVE.value
        return cls(**data)
    
    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0
    
    @property
    def has_links(self) -> bool:
        return len(self.links) > 0


@dataclass
class PasswordHistoryEntry:
    """Entry in password history"""
    password: str  # Encrypted old password
    changed_at: str  # When it was changed
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PasswordHistoryEntry':
        return cls(**data)


@dataclass
class Password:
    """Encrypted password entry"""
    id: str
    user_id: int
    service_name: str  # Website/app name (title/name)
    username: str  # Login/email (encrypted)
    password: str  # Password (encrypted)
    url: Optional[str] = None
    notes: Optional[str] = None  # Encrypted notes
    totp_secret: Optional[str] = None  # 2FA TOTP secret (encrypted)
    recovery_codes: Optional[str] = None  # 2FA recovery codes (encrypted, comma-separated)
    category: str = "general"
    is_favorite: bool = False
    last_used: Optional[str] = None
    password_changed_at: Optional[str] = None
    password_history: List[Dict[str, str]] = field(default_factory=list)  # List of old passwords
    created_at: str = field(default_factory=now_str)
    updated_at: str = field(default_factory=now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Password':
        # Handle legacy data without new fields
        if 'totp_secret' not in data:
            data['totp_secret'] = None
        if 'recovery_codes' not in data:
            data['recovery_codes'] = None
        if 'password_history' not in data:
            data['password_history'] = []
        return cls(**data)
    
    @property
    def has_2fa(self) -> bool:
        return bool(self.totp_secret or self.recovery_codes)
    
    @property
    def history_count(self) -> int:
        return len(self.password_history)


@dataclass
class ArchivedItem:
    """Archived reminder or todo"""
    item_type: str  # "reminder" or "todo"
    data: Dict[str, Any]
    archived_at: str = field(default_factory=now_str)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArchivedItem':
        return cls(**data)


@dataclass
class UserData:
    """Complete user data structure for JSON storage"""
    user: User
    reminders: List[Reminder] = field(default_factory=list)
    todos: List[Todo] = field(default_factory=list)
    notes: List[Note] = field(default_factory=list)
    passwords: List[Password] = field(default_factory=list)
    archive: List[ArchivedItem] = field(default_factory=list)  # Archived items
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user": self.user.to_dict(),
            "reminders": [r.to_dict() for r in self.reminders],
            "todos": [t.to_dict() for t in self.todos],
            "notes": [n.to_dict() for n in self.notes],
            "passwords": [p.to_dict() for p in self.passwords],
            "archive": [a.to_dict() for a in self.archive]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserData':
        return cls(
            user=User.from_dict(data["user"]),
            reminders=[Reminder.from_dict(r) for r in data.get("reminders", [])],
            todos=[Todo.from_dict(t) for t in data.get("todos", [])],
            notes=[Note.from_dict(n) for n in data.get("notes", [])],
            passwords=[Password.from_dict(p) for p in data.get("passwords", [])],
            archive=[ArchivedItem.from_dict(a) for a in data.get("archive", [])]
        )
