"""
User service for managing users
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.user import User
from config import DEFAULT_TIMEZONE


class UserService:
    """Service for managing users"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Get existing user or create new one"""
        user = await self.get_user_by_telegram_id(telegram_id)
        
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                timezone=DEFAULT_TIMEZONE
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        else:
            # Update user info if changed
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            
            if updated:
                await self.session.commit()
                await self.session.refresh(user)
        
        return user
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by internal ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_timezone(self, telegram_id: int, timezone: str) -> Optional[User]:
        """Update user timezone"""
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.timezone = timezone
            await self.session.commit()
            await self.session.refresh(user)
        return user
    
    async def deactivate_user(self, telegram_id: int) -> Optional[User]:
        """Deactivate a user"""
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.is_active = False
            await self.session.commit()
            await self.session.refresh(user)
        return user
