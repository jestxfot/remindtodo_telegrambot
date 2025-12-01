"""
Formatting utilities for displaying data
"""
from datetime import datetime
from typing import TYPE_CHECKING, List
import pytz
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TIMEZONE

if TYPE_CHECKING:
    from storage.models import Reminder, Todo


def format_datetime(dt_str: str, timezone: str = DEFAULT_TIMEZONE, include_time: bool = True) -> str:
    """Format datetime string for display"""
    if not dt_str:
        return "—"
    
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        tz = pytz.timezone(timezone)
        
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        
        local_dt = dt.astimezone(tz)
        
        if include_time:
            return local_dt.strftime("%d.%m.%Y %H:%M")
        return local_dt.strftime("%d.%m.%Y")
    except Exception:
        return dt_str[:16].replace('T', ' ')


def format_reminder(reminder: "Reminder", timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format reminder for display"""
    status_emoji = {
        "pending": "⏳",
        "active": "🔔",
        "snoozed": "⏸️",
        "completed": "✅",
        "cancelled": "❌"
    }
    
    recurrence_text = {
        "none": "",
        "daily": "🔄 Ежедневно",
        "weekly": "🔄 Еженедельно",
        "monthly": "🔄 Ежемесячно",
        "yearly": "🔄 Ежегодно",
        "custom": f"🔄 Каждые {reminder.recurrence_interval} мин" if reminder.recurrence_interval else "🔄 Повтор"
    }
    
    lines = [
        f"{status_emoji.get(reminder.status, '❓')} <b>{reminder.title}</b>",
        "",
        f"📅 {format_datetime(reminder.remind_at, timezone)}"
    ]
    
    if reminder.description:
        lines.insert(1, f"📝 {reminder.description}")
    
    if reminder.is_recurring:
        lines.append(recurrence_text.get(reminder.recurrence_type, ""))
    
    if reminder.is_persistent:
        lines.append(f"🔊 Постоянное уведомление (каждые {reminder.persistent_interval} сек)")
    
    if reminder.status == "snoozed" and reminder.snoozed_until:
        lines.append(f"⏸️ Отложено до {format_datetime(reminder.snoozed_until, timezone)}")
    
    if reminder.snooze_count > 0:
        lines.append(f"💤 Отложено раз: {reminder.snooze_count}")
    
    return "\n".join(lines)


def format_todo(todo: "Todo", timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format todo for display"""
    priority_text = {
        "low": "🟢 Низкий",
        "medium": "🟡 Средний",
        "high": "🟠 Высокий",
        "urgent": "🔴 Срочный"
    }
    
    status_text = {
        "pending": "⏳ Ожидает",
        "in_progress": "🔄 В работе",
        "completed": "✅ Выполнено",
        "cancelled": "❌ Отменено"
    }
    
    lines = [
        f"{todo.status_emoji} <b>{todo.title}</b>",
        "",
        f"📊 Статус: {status_text.get(todo.status, 'Неизвестно')}",
        f"🎯 Приоритет: {priority_text.get(todo.priority, 'Неизвестно')}"
    ]
    
    if todo.description:
        lines.insert(1, f"📝 {todo.description}")
    
    if todo.deadline:
        deadline_str = format_datetime(todo.deadline, timezone)
        if todo.is_overdue:
            lines.append(f"⚠️ <b>Просрочено!</b> Дедлайн: {deadline_str}")
        else:
            lines.append(f"📅 Дедлайн: {deadline_str}")
    
    if todo.completed_at:
        lines.append(f"✅ Завершено: {format_datetime(todo.completed_at, timezone)}")
    
    lines.append(f"\n🕐 Создано: {format_datetime(todo.created_at, timezone)}")
    
    return "\n".join(lines)


def format_todos_list(todos: List["Todo"], timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format list of todos for display"""
    if not todos:
        return "📋 Список задач пуст\n\nИспользуйте /newtodo для создания задачи"
    
    lines = ["📋 <b>Ваши задачи:</b>\n"]
    
    for i, todo in enumerate(todos, 1):
        status_emoji = todo.status_emoji
        priority_emoji = todo.priority_emoji
        
        title = todo.title[:40] + "..." if len(todo.title) > 40 else todo.title
        
        deadline_info = ""
        if todo.deadline:
            if todo.is_overdue:
                deadline_info = " ⚠️"
            else:
                deadline_info = f" 📅"
        
        lines.append(f"{i}. {status_emoji}{priority_emoji} {title}{deadline_info}")
    
    return "\n".join(lines)


def format_reminders_list(reminders: List["Reminder"], timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format list of reminders for display"""
    if not reminders:
        return "⏰ Напоминаний нет\n\nИспользуйте /newreminder для создания напоминания"
    
    lines = ["⏰ <b>Ваши напоминания:</b>\n"]
    
    for i, reminder in enumerate(reminders, 1):
        status_emoji = "🔔" if reminder.status == "pending" else "✅" if reminder.status == "completed" else "⏸️"
        recurrence_icon = "🔄" if reminder.is_recurring else ""
        
        title = reminder.title[:35] + "..." if len(reminder.title) > 35 else reminder.title
        time_str = format_datetime(reminder.remind_at, timezone)
        
        lines.append(f"{i}. {status_emoji}{recurrence_icon} {title}")
        lines.append(f"   📅 {time_str}")
    
    return "\n".join(lines)
