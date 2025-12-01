"""
Todo model for storing todo items
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .database import Base

if TYPE_CHECKING:
    from .user import User


class TodoPriority(str, Enum):
    """Priority levels for todos"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TodoStatus(str, Enum):
    """Status of a todo item"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Todo(Base):
    """Todo item model"""
    __tablename__ = "todos"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Todo content
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Status and priority
    status: Mapped[TodoStatus] = mapped_column(
        SQLEnum(TodoStatus),
        default=TodoStatus.PENDING
    )
    priority: Mapped[TodoPriority] = mapped_column(
        SQLEnum(TodoPriority),
        default=TodoPriority.MEDIUM
    )
    
    # Optional deadline with reminder
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Link to reminder if deadline set
    
    # Ordering
    order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="todos")
    
    def __repr__(self) -> str:
        return f"<Todo(id={self.id}, title='{self.title}', status={self.status}, priority={self.priority})>"
    
    @property
    def is_overdue(self) -> bool:
        """Check if todo is overdue"""
        if not self.deadline:
            return False
        return datetime.utcnow() > self.deadline and self.status not in [TodoStatus.COMPLETED, TodoStatus.CANCELLED]
    
    @property
    def priority_emoji(self) -> str:
        """Get emoji for priority level"""
        emojis = {
            TodoPriority.LOW: "🟢",
            TodoPriority.MEDIUM: "🟡", 
            TodoPriority.HIGH: "🟠",
            TodoPriority.URGENT: "🔴"
        }
        return emojis.get(self.priority, "⚪")
    
    @property
    def status_emoji(self) -> str:
        """Get emoji for status"""
        emojis = {
            TodoStatus.PENDING: "⏳",
            TodoStatus.IN_PROGRESS: "🔄",
            TodoStatus.COMPLETED: "✅",
            TodoStatus.CANCELLED: "❌"
        }
        return emojis.get(self.status, "❓")
