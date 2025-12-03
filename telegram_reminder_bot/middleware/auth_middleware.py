"""
Authentication Middleware

Checks if user is authenticated before accessing protected features.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AuthMiddleware(BaseMiddleware):
    """
    Middleware to check authentication for protected commands
    """
    
    # Commands that don't require authentication
    PUBLIC_COMMANDS = {'/start', '/help', '/unlock', '/lock', '/session'}
    
    # Callback prefixes that don't require auth
    PUBLIC_CALLBACKS = {'settings_', 'session_dur:', 'session_menu', 'session_change:', 'session_back', 'session_logout'}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        from handlers.auth import is_authenticated, user_has_password
        
        # Get user_id from event
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text or ""
            
            # Check if public command
            if any(text.startswith(cmd) for cmd in self.PUBLIC_COMMANDS):
                return await handler(event, data)
            
            # Check if in any FSM state (user is in the middle of some action)
            # This includes TodoStates, ReminderStates, NoteStates, PasswordStates, AuthStates, etc.
            state = data.get("state")
            if state:
                current_state = await state.get_state()
                if current_state:
                    # If user is in any state, they're already authenticated
                    # (they couldn't have entered the state without being authenticated)
                    # OR they're in AuthStates which is always allowed
                    if current_state.startswith("AuthStates:"):
                        return await handler(event, data)
                    # For all other states, verify user is still authenticated
                    if is_authenticated(user_id):
                        return await handler(event, data)
        
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            callback_data = event.data or ""
            
            # Check if public callback
            if any(callback_data.startswith(prefix) for prefix in self.PUBLIC_CALLBACKS):
                return await handler(event, data)
        
        # Check authentication
        if user_id:
            if not user_has_password(user_id):
                # New user - redirect to setup
                if isinstance(event, Message):
                    await event.answer(
                        "🔐 <b>Добро пожаловать!</b>\n\n"
                        "Для начала работы создайте мастер-пароль.\n\n"
                        "Используйте /unlock",
                        parse_mode="HTML"
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer("🔐 Сначала создайте пароль: /unlock", show_alert=True)
                return
            
            if not is_authenticated(user_id):
                # Not logged in
                if isinstance(event, Message):
                    await event.answer(
                        "🔒 Хранилище заблокировано\n\n"
                        "Используйте /unlock для разблокировки"
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer("🔒 Разблокируйте: /unlock", show_alert=True)
                return
        
        return await handler(event, data)
