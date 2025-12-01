"""
Scheduler service for managing reminder notifications
"""
import asyncio
from datetime import datetime
from typing import Callable, Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PERSISTENT_REMINDER_INTERVAL

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for scheduling reminder notifications"""
    
    _instance = None
    _scheduler: Optional[AsyncIOScheduler] = None
    _notification_callback: Optional[Callable] = None
    _bot = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler()
            self._active_reminders: Dict[int, str] = {}  # reminder_id -> job_id
    
    def set_bot(self, bot):
        """Set bot instance for sending notifications"""
        self._bot = bot
    
    def set_notification_callback(self, callback: Callable):
        """Set the callback function for sending notifications"""
        self._notification_callback = callback
    
    def start(self):
        """Start the scheduler"""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def schedule_reminder_check(self, interval_seconds: int = 10):
        """Schedule periodic check for due reminders"""
        self._scheduler.add_job(
            self._check_reminders,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id="reminder_check",
            replace_existing=True
        )
        logger.info(f"Scheduled reminder check every {interval_seconds} seconds")
    
    def schedule_persistent_notifications(self, interval_seconds: int = PERSISTENT_REMINDER_INTERVAL):
        """Schedule periodic persistent notifications for active reminders"""
        self._scheduler.add_job(
            self._send_persistent_notifications,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id="persistent_notifications",
            replace_existing=True
        )
        logger.info(f"Scheduled persistent notifications every {interval_seconds} seconds")
    
    def schedule_snoozed_check(self, interval_seconds: int = 30):
        """Schedule check for snoozed reminders that should be reactivated"""
        self._scheduler.add_job(
            self._check_snoozed_reminders,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id="snoozed_check",
            replace_existing=True
        )
        logger.info(f"Scheduled snoozed reminder check every {interval_seconds} seconds")
    
    def add_one_time_job(self, func: Callable, run_date: datetime, job_id: str, **kwargs):
        """Add a one-time job"""
        self._scheduler.add_job(
            func,
            trigger=DateTrigger(run_date=run_date),
            id=job_id,
            replace_existing=True,
            **kwargs
        )
    
    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        try:
            self._scheduler.remove_job(job_id)
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")
    
    async def _check_reminders(self):
        """Check for reminders that should be triggered"""
        if not self._notification_callback:
            return
        
        try:
            from models.database import async_session
            from services.reminder_service import ReminderService
            
            async with async_session() as session:
                service = ReminderService(session)
                pending_reminders = await service.get_pending_reminders()
                
                for reminder in pending_reminders:
                    # Activate the reminder
                    await service.activate_reminder(reminder.id)
                    
                    # Send notification
                    await self._notification_callback(reminder, is_initial=True)
                    
                    logger.info(f"Triggered reminder {reminder.id}: {reminder.title}")
        except Exception as e:
            logger.error(f"Error checking reminders: {e}")
    
    async def _send_persistent_notifications(self):
        """Send persistent notifications for active reminders"""
        if not self._notification_callback:
            return
        
        try:
            from models.database import async_session
            from services.reminder_service import ReminderService
            
            async with async_session() as session:
                service = ReminderService(session)
                active_reminders = await service.get_active_reminders()
                
                for reminder in active_reminders:
                    # Check if enough time has passed since last notification
                    if reminder.last_notification_at:
                        seconds_since_last = (datetime.utcnow() - reminder.last_notification_at).total_seconds()
                        if seconds_since_last < reminder.persistent_interval:
                            continue
                    
                    # Update last notification time
                    await service.update_last_notification(reminder.id)
                    
                    # Send notification
                    await self._notification_callback(reminder, is_initial=False)
                    
                    logger.debug(f"Sent persistent notification for reminder {reminder.id}")
        except Exception as e:
            logger.error(f"Error sending persistent notifications: {e}")
    
    async def _check_snoozed_reminders(self):
        """Check for snoozed reminders that should be reactivated"""
        if not self._notification_callback:
            return
        
        try:
            from models.database import async_session
            from services.reminder_service import ReminderService
            
            async with async_session() as session:
                service = ReminderService(session)
                snoozed_reminders = await service.get_snoozed_reminders()
                
                for reminder in snoozed_reminders:
                    # Reactivate the reminder
                    await service.activate_reminder(reminder.id)
                    
                    # Send notification
                    await self._notification_callback(reminder, is_initial=True)
                    
                    logger.info(f"Reactivated snoozed reminder {reminder.id}")
        except Exception as e:
            logger.error(f"Error checking snoozed reminders: {e}")


# Global scheduler instance
scheduler = SchedulerService()
