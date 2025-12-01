"""
Command handlers for the bot
"""
from .commands import router as commands_router
from .reminders import router as reminders_router
from .todos import router as todos_router
from .callbacks import router as callbacks_router

__all__ = ["commands_router", "reminders_router", "todos_router", "callbacks_router"]
