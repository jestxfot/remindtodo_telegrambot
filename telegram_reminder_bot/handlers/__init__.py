"""
Handler routers - WebApp only mode
"""
from .commands import router as commands_router
from .notifications import router as notifications_router

__all__ = [
    'commands_router',
    'notifications_router',
]
