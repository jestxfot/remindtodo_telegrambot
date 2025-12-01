"""
Command handlers for the bot
"""
from .auth import router as auth_router
from .commands import router as commands_router
from .reminders import router as reminders_router
from .todos import router as todos_router
from .notes import router as notes_router
from .passwords import router as passwords_router
from .callbacks import router as callbacks_router

__all__ = [
    "auth_router",
    "commands_router",
    "reminders_router", 
    "todos_router",
    "notes_router",
    "passwords_router",
    "callbacks_router"
]
