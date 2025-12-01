"""
Formatting utilities for displaying data
"""
from datetime import datetime
from typing import TYPE_CHECKING
import pytz
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TIMEZONE

if TYPE_CHECKING:
    from models.reminder import Reminder
    from models.todo import Todo


def format_datetime(dt: datetime, timezone: str = DEFAULT_TIMEZONE, include_time: bool = True) -> str:
    """Format datetime for display"""
    tz = pytz.timezone(timezone)
    
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    local_dt = dt.astimezone(tz)
    
    if include_time:
        return local_dt.strftime("%d.%m.%Y %H:%M")
    return local_dt.strftime("%d.%m.%Y")


def format_reminder(reminder: "Reminder", timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format reminder for display"""
    from models.reminder import ReminderStatus, RecurrenceType
    
    status_emoji = {
        ReminderStatus.PENDING: "⏳",
        ReminderStatus.ACTIVE: "🔔",
        ReminderStatus.SNOOZED: "⏸️",
        ReminderStatus.COMPLETED: "✅",
        ReminderStatus.CANCELLED: "❌"
    }
    
    recurrence_text = {
        RecurrenceType.NONE: "",
        RecurrenceType.DAILY: "🔄 Ежедневно",
        RecurrenceType.WEEKLY: "🔄 Еженедельно",
        RecurrenceType.MONTHLY: "🔄 Ежемесячно",
        RecurrenceType.YEARLY: "🔄 Ежегодно",
        RecurrenceType.CUSTOM: f"🔄 Каждые {reminder.recurrence_interval} мин" if reminder.recurrence_interval else "🔄 Повтор"
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
    
    if reminder.status == ReminderStatus.SNOOZED and reminder.snoozed_until:
        lines.append(f"⏸️ Отложено до {format_datetime(reminder.snoozed_until, timezone)}")
    
    if reminder.snooze_count > 0:
        lines.append(f"💤 Отложено раз: {reminder.snooze_count}")
    
    return "\n".join(lines)


def format_todo(todo: "Todo", timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format todo for display"""
    from models.todo import TodoStatus, TodoPriority
    
    priority_text = {
        TodoPriority.LOW: "🟢 Низкий",
        TodoPriority.MEDIUM: "🟡 Средний",
        TodoPriority.HIGH: "🟠 Высокий",
        TodoPriority.URGENT: "🔴 Срочный"
    }
    
    status_text = {
        TodoStatus.PENDING: "⏳ Ожидает",
        TodoStatus.IN_PROGRESS: "🔄 В работе",
        TodoStatus.COMPLETED: "✅ Выполнено",
        TodoStatus.CANCELLED: "❌ Отменено"
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


def format_todos_list(todos: list, timezone: str = DEFAULT_TIMEZONE) -> str:
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


def format_reminders_list(reminders: list, timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format list of reminders for display"""
    if not reminders:
        return "⏰ Напоминаний нет\n\nИспользуйте /newreminder для создания напоминания"
    
    lines = ["⏰ <b>Ваши напоминания:</b>\n"]
    
    for i, reminder in enumerate(reminders, 1):
        from models.reminder import ReminderStatus
        
        status_emoji = "🔔" if reminder.status == ReminderStatus.PENDING else "✅" if reminder.status == ReminderStatus.COMPLETED else "⏸️"
        recurrence_icon = "🔄" if reminder.is_recurring else ""
        
        title = reminder.title[:35] + "..." if len(reminder.title) > 35 else reminder.title
        time_str = format_datetime(reminder.remind_at, timezone)
        
        lines.append(f"{i}. {status_emoji}{recurrence_icon} {title}")
        lines.append(f"   📅 {time_str}")
    
    return "\n".join(lines)


def format_statistics(
    total_todos: int,
    completed_todos: int,
    pending_todos: int,
    overdue_todos: int,
    total_reminders: int,
    active_reminders: int,
    completed_reminders: int
) -> str:
    """Format statistics for display"""
    completion_rate = (completed_todos / total_todos * 100) if total_todos > 0 else 0
    
    return f"""📊 <b>Ваша статистика</b>

<b>📋 Задачи:</b>
├ Всего: {total_todos}
├ Выполнено: {completed_todos} ✅
├ В ожидании: {pending_todos} ⏳
├ Просрочено: {overdue_todos} ⚠️
└ Процент выполнения: {completion_rate:.1f}%

<b>⏰ Напоминания:</b>
├ Всего: {total_reminders}
├ Активных: {active_reminders} 🔔
└ Выполнено: {completed_reminders} ✅
"""
