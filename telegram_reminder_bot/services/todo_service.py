"""
Todo service for managing todo items
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.todo import Todo, TodoStatus, TodoPriority
from models.user import User


class TodoService:
    """Service for managing todo items"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_todo(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        priority: TodoPriority = TodoPriority.MEDIUM,
        deadline: Optional[datetime] = None
    ) -> Todo:
        """Create a new todo item"""
        # Get max order for user
        result = await self.session.execute(
            select(func.max(Todo.order)).where(Todo.user_id == user_id)
        )
        max_order = result.scalar() or 0
        
        todo = Todo(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            deadline=deadline,
            order=max_order + 1,
            status=TodoStatus.PENDING
        )
        
        self.session.add(todo)
        await self.session.commit()
        await self.session.refresh(todo)
        
        return todo
    
    async def get_todo(self, todo_id: int) -> Optional[Todo]:
        """Get todo by ID"""
        result = await self.session.execute(
            select(Todo).where(Todo.id == todo_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_todos(
        self,
        user_id: int,
        include_completed: bool = False,
        status: Optional[TodoStatus] = None,
        priority: Optional[TodoPriority] = None
    ) -> List[Todo]:
        """Get all todos for a user with optional filters"""
        query = select(Todo).where(Todo.user_id == user_id)
        
        if not include_completed and status is None:
            query = query.where(
                Todo.status.not_in([TodoStatus.COMPLETED, TodoStatus.CANCELLED])
            )
        
        if status:
            query = query.where(Todo.status == status)
        
        if priority:
            query = query.where(Todo.priority == priority)
        
        # Order by priority (urgent first), then by order
        query = query.order_by(
            Todo.priority.desc(),
            Todo.order
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_overdue_todos(self, user_id: int) -> List[Todo]:
        """Get all overdue todos for a user"""
        now = datetime.utcnow()
        
        result = await self.session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == user_id,
                    Todo.deadline < now,
                    Todo.status.not_in([TodoStatus.COMPLETED, TodoStatus.CANCELLED])
                )
            ).order_by(Todo.deadline)
        )
        return list(result.scalars().all())
    
    async def complete_todo(self, todo_id: int) -> Optional[Todo]:
        """Mark a todo as completed"""
        todo = await self.get_todo(todo_id)
        if todo:
            todo.status = TodoStatus.COMPLETED
            todo.completed_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(todo)
        return todo
    
    async def set_in_progress(self, todo_id: int) -> Optional[Todo]:
        """Set todo status to in progress"""
        todo = await self.get_todo(todo_id)
        if todo:
            todo.status = TodoStatus.IN_PROGRESS
            await self.session.commit()
            await self.session.refresh(todo)
        return todo
    
    async def cancel_todo(self, todo_id: int) -> Optional[Todo]:
        """Cancel a todo"""
        todo = await self.get_todo(todo_id)
        if todo:
            todo.status = TodoStatus.CANCELLED
            await self.session.commit()
            await self.session.refresh(todo)
        return todo
    
    async def delete_todo(self, todo_id: int) -> bool:
        """Delete a todo"""
        todo = await self.get_todo(todo_id)
        if todo:
            await self.session.delete(todo)
            await self.session.commit()
            return True
        return False
    
    async def update_todo(
        self,
        todo_id: int,
        **kwargs
    ) -> Optional[Todo]:
        """Update todo fields"""
        todo = await self.get_todo(todo_id)
        if todo:
            for key, value in kwargs.items():
                if hasattr(todo, key):
                    setattr(todo, key, value)
            await self.session.commit()
            await self.session.refresh(todo)
        return todo
    
    async def set_priority(
        self,
        todo_id: int,
        priority: TodoPriority
    ) -> Optional[Todo]:
        """Set todo priority"""
        return await self.update_todo(todo_id, priority=priority)
    
    async def set_deadline(
        self,
        todo_id: int,
        deadline: Optional[datetime]
    ) -> Optional[Todo]:
        """Set todo deadline"""
        return await self.update_todo(todo_id, deadline=deadline)
    
    async def reorder_todo(
        self,
        todo_id: int,
        new_order: int
    ) -> Optional[Todo]:
        """Reorder a todo"""
        return await self.update_todo(todo_id, order=new_order)
    
    async def get_statistics(self, user_id: int) -> dict:
        """Get todo statistics for a user"""
        todos = await self.get_user_todos(user_id, include_completed=True)
        
        total = len(todos)
        completed = len([t for t in todos if t.status == TodoStatus.COMPLETED])
        pending = len([t for t in todos if t.status == TodoStatus.PENDING])
        in_progress = len([t for t in todos if t.status == TodoStatus.IN_PROGRESS])
        overdue = len([t for t in todos if t.is_overdue])
        
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "in_progress": in_progress,
            "overdue": overdue
        }
