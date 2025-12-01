"""
Reminder model for storing reminder data
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import BigInteger, String, DateTime, Boolean, Integer, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional

from .database import Base

if TYPE_CHECKING:
    from .user import User


class RecurrenceType(str, Enum):
    """Types of recurring reminders"""
    NONE = "none"           # One-time reminder
    DAILY = "daily"         # Every day
    WEEKLY = "weekly"       # Every week
    MONTHLY = "monthly"     # Every month
    YEARLY = "yearly"       # Every year
    CUSTOM = "custom"       # Custom interval in minutes


class ReminderStatus(str, Enum):
    """Status of a reminder"""
    PENDING = "pending"         # Waiting to be triggered
    ACTIVE = "active"           # Currently sending notifications
    SNOOZED = "snoozed"         # Temporarily snoozed
    COMPLETED = "completed"     # Marked as done
    CANCELLED = "cancelled"     # Cancelled by user


class Reminder(Base):
    """Reminder model"""
    __tablename__ = "reminders"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Reminder content
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timing
    remind_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Status
    status: Mapped[ReminderStatus] = mapped_column(
        SQLEnum(ReminderStatus),
        default=ReminderStatus.PENDING
    )
    
    # Recurrence settings
    recurrence_type: Mapped[RecurrenceType] = mapped_column(
        SQLEnum(RecurrenceType),
        default=RecurrenceType.NONE
    )
    recurrence_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)  # For custom recurrence (in minutes)
    recurrence_end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Persistent notification settings
    is_persistent: Mapped[bool] = mapped_column(Boolean, default=True)  # Send repeated notifications
    persistent_interval: Mapped[int] = mapped_column(Integer, default=60)  # Seconds between persistent notifications
    snooze_count: Mapped[int] = mapped_column(Integer, default=0)  # How many times snoozed
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_notification_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Sound notification
    with_sound: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="reminders")
    
    def __repr__(self) -> str:
        return f"<Reminder(id={self.id}, title='{self.title}', remind_at={self.remind_at}, status={self.status})>"
    
    @property
    def is_recurring(self) -> bool:
        """Check if reminder is recurring"""
        return self.recurrence_type != RecurrenceType.NONE
    
    def get_next_occurrence(self) -> Optional[datetime]:
        """Calculate next occurrence for recurring reminders"""
        from dateutil.relativedelta import relativedelta
        
        if not self.is_recurring:
            return None
            
        base_time = self.remind_at
        
        if self.recurrence_type == RecurrenceType.DAILY:
            next_time = base_time + relativedelta(days=1)
        elif self.recurrence_type == RecurrenceType.WEEKLY:
            next_time = base_time + relativedelta(weeks=1)
        elif self.recurrence_type == RecurrenceType.MONTHLY:
            next_time = base_time + relativedelta(months=1)
        elif self.recurrence_type == RecurrenceType.YEARLY:
            next_time = base_time + relativedelta(years=1)
        elif self.recurrence_type == RecurrenceType.CUSTOM and self.recurrence_interval:
            next_time = base_time + relativedelta(minutes=self.recurrence_interval)
        else:
            return None
        
        # Check if within end date
        if self.recurrence_end_date and next_time > self.recurrence_end_date:
            return None
            
        return next_time
