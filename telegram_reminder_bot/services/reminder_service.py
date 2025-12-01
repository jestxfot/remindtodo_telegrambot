"""
Reminder service for managing reminders
"""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import pytz
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.reminder import Reminder, ReminderStatus, RecurrenceType
from models.user import User
from config import DEFAULT_TIMEZONE


class ReminderService:
    """Service for managing reminders"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_reminder(
        self,
        user_id: int,
        title: str,
        remind_at: datetime,
        description: Optional[str] = None,
        is_persistent: bool = True,
        persistent_interval: int = 60,
        with_sound: bool = True,
        recurrence_type: RecurrenceType = RecurrenceType.NONE,
        recurrence_interval: Optional[int] = None,
        recurrence_end_date: Optional[datetime] = None
    ) -> Reminder:
        """Create a new reminder"""
        reminder = Reminder(
            user_id=user_id,
            title=title,
            description=description,
            remind_at=remind_at,
            is_persistent=is_persistent,
            persistent_interval=persistent_interval,
            with_sound=with_sound,
            recurrence_type=recurrence_type,
            recurrence_interval=recurrence_interval,
            recurrence_end_date=recurrence_end_date,
            status=ReminderStatus.PENDING
        )
        
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        
        return reminder
    
    async def get_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """Get reminder by ID"""
        result = await self.session.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_reminders(
        self,
        user_id: int,
        include_completed: bool = False
    ) -> List[Reminder]:
        """Get all reminders for a user"""
        query = select(Reminder).where(Reminder.user_id == user_id)
        
        if not include_completed:
            query = query.where(
                Reminder.status.not_in([ReminderStatus.COMPLETED, ReminderStatus.CANCELLED])
            )
        
        query = query.order_by(Reminder.remind_at)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_pending_reminders(self) -> List[Reminder]:
        """Get all pending reminders that should be triggered"""
        now = datetime.utcnow()
        
        result = await self.session.execute(
            select(Reminder).where(
                and_(
                    Reminder.status == ReminderStatus.PENDING,
                    Reminder.remind_at <= now
                )
            )
        )
        return list(result.scalars().all())
    
    async def get_active_reminders(self) -> List[Reminder]:
        """Get all active reminders that need persistent notifications"""
        now = datetime.utcnow()
        
        result = await self.session.execute(
            select(Reminder).where(
                and_(
                    Reminder.status == ReminderStatus.ACTIVE,
                    Reminder.is_persistent == True,
                    or_(
                        Reminder.last_notification_at == None,
                        Reminder.last_notification_at <= now - timedelta(seconds=30)
                    )
                )
            )
        )
        return list(result.scalars().all())
    
    async def get_snoozed_reminders(self) -> List[Reminder]:
        """Get snoozed reminders that should be reactivated"""
        now = datetime.utcnow()
        
        result = await self.session.execute(
            select(Reminder).where(
                and_(
                    Reminder.status == ReminderStatus.SNOOZED,
                    Reminder.snoozed_until <= now
                )
            )
        )
        return list(result.scalars().all())
    
    async def activate_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """Activate a pending reminder"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            reminder.status = ReminderStatus.ACTIVE
            reminder.last_notification_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(reminder)
        return reminder
    
    async def snooze_reminder(
        self,
        reminder_id: int,
        minutes: int
    ) -> Optional[Reminder]:
        """Snooze a reminder for specified minutes"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            reminder.status = ReminderStatus.SNOOZED
            reminder.snoozed_until = datetime.utcnow() + timedelta(minutes=minutes)
            reminder.snooze_count += 1
            await self.session.commit()
            await self.session.refresh(reminder)
        return reminder
    
    async def complete_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """Mark a reminder as completed"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            if reminder.is_recurring:
                # Create next occurrence
                next_time = reminder.get_next_occurrence()
                if next_time:
                    await self.create_reminder(
                        user_id=reminder.user_id,
                        title=reminder.title,
                        description=reminder.description,
                        remind_at=next_time,
                        is_persistent=reminder.is_persistent,
                        persistent_interval=reminder.persistent_interval,
                        with_sound=reminder.with_sound,
                        recurrence_type=reminder.recurrence_type,
                        recurrence_interval=reminder.recurrence_interval,
                        recurrence_end_date=reminder.recurrence_end_date
                    )
            
            reminder.status = ReminderStatus.COMPLETED
            await self.session.commit()
            await self.session.refresh(reminder)
        return reminder
    
    async def cancel_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """Cancel a reminder"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            reminder.status = ReminderStatus.CANCELLED
            await self.session.commit()
            await self.session.refresh(reminder)
        return reminder
    
    async def delete_reminder(self, reminder_id: int) -> bool:
        """Delete a reminder"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            await self.session.delete(reminder)
            await self.session.commit()
            return True
        return False
    
    async def update_last_notification(self, reminder_id: int) -> Optional[Reminder]:
        """Update last notification timestamp"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            reminder.last_notification_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(reminder)
        return reminder
    
    async def update_reminder(
        self,
        reminder_id: int,
        **kwargs
    ) -> Optional[Reminder]:
        """Update reminder fields"""
        reminder = await self.get_reminder(reminder_id)
        if reminder:
            for key, value in kwargs.items():
                if hasattr(reminder, key):
                    setattr(reminder, key, value)
            await self.session.commit()
            await self.session.refresh(reminder)
        return reminder
    
    async def set_recurrence(
        self,
        reminder_id: int,
        recurrence_type: RecurrenceType,
        interval: Optional[int] = None,
        end_date: Optional[datetime] = None
    ) -> Optional[Reminder]:
        """Set recurrence for a reminder"""
        return await self.update_reminder(
            reminder_id,
            recurrence_type=recurrence_type,
            recurrence_interval=interval,
            recurrence_end_date=end_date
        )
    
    async def mute_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """Disable sound for a reminder"""
        return await self.update_reminder(reminder_id, with_sound=False)
    
    async def disable_persistent(self, reminder_id: int) -> Optional[Reminder]:
        """Disable persistent notifications for a reminder"""
        return await self.update_reminder(reminder_id, is_persistent=False)
