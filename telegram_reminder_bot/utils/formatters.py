"""
Formatting utilities for displaying data
"""
from typing import TYPE_CHECKING, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_TIMEZONE
from utils.timezone import parse_dt

if TYPE_CHECKING:
    from storage.models import Reminder, Todo


def format_datetime(dt_str: str, timezone: str = DEFAULT_TIMEZONE, include_time: bool = True) -> str:
    """Format datetime string for display (time stored in MSK, no conversion needed)"""
    if not dt_str:
        return "—"
    
    try:
        # Time is stored/normalized as MSK, parse consistently.
        dt = parse_dt(dt_str)
        
        if include_time:
            return dt.strftime("%d.%m.%Y %H:%M")
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return dt_str[:16].replace('T', ' ')


def format_interval(days: int) -> str:
    """Format custom recurrence interval in days to human-readable string."""
    if not days:
        return "Повтор"

    if days == 1:
        return "ежедневно"
    if days == 7:
        return "еженедельно"
    if days == 14:
        return "каждые 2 недели"
    if days == 21:
        return "каждые 3 недели"
    if days == 30:
        return "ежемесячно"

    if days < 7:
        if days in [2, 3, 4]:
            return f"каждые {days} дня"
        return f"каждые {days} дней"

    weeks = days // 7
    if days % 7 == 0 and weeks > 0:
        if weeks == 1:
            return "еженедельно"
        if weeks in [2, 3, 4]:
            return f"каждые {weeks} недели"
        return f"каждые {weeks} недель"

    return f"каждые {days} дн."


def format_reminder(reminder: "Reminder", timezone: str = DEFAULT_TIMEZONE) -> str:
    """Format reminder for display"""
    status_emoji = {
        "pending": "⏳",
        "active": "🔔",
        "snoozed": "⏸️",
        "completed": "✅",
        "cancelled": "❌"
    }
    
    # Формируем текст повторения
    recurrence_text = {
        "none": "",
        "daily": "🔄 Ежедневно",
        "weekly": "🔄 Еженедельно",
        "monthly": "🔄 Ежемесячно",
        "yearly": "🔄 Ежегодно",
    }
    
    if reminder.recurrence_type == "custom" and reminder.recurrence_interval:
        recurrence_text["custom"] = f"🔄 {format_interval(reminder.recurrence_interval).capitalize()}"
    else:
        recurrence_text["custom"] = "🔄 Повтор"
    
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
    
    recurrence_text = {
        "none": "",
        "daily": "🔁 Ежедневно",
        "weekly": "🔁 Еженедельно",
        "monthly": "🔁 Ежемесячно",
        "yearly": "🔁 Ежегодно",
    }
    
    # Добавляем кастомный интервал для задач
    if hasattr(todo, 'recurrence_type') and todo.recurrence_type == "custom":
        interval = getattr(todo, 'recurrence_interval', None)
        if interval:
            recurrence_text["custom"] = f"🔁 {format_interval(interval).capitalize()}"
        else:
            recurrence_text["custom"] = "🔁 Повтор"
    
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
    
    # Show recurrence info
    if hasattr(todo, 'is_recurring') and todo.is_recurring:
        rec_type = getattr(todo, 'recurrence_type', 'none')
        rec_line = recurrence_text.get(rec_type, "🔁 Повторяется")
        
        if hasattr(todo, 'recurrence_end_date') and todo.recurrence_end_date:
            end_str = format_datetime(todo.recurrence_end_date, timezone, include_time=False)
            rec_line += f" до {end_str}"
        else:
            rec_line += " (бессрочно)"
        
        lines.append(rec_line)
        
        if hasattr(todo, 'recurrence_count') and todo.recurrence_count > 0:
            lines.append(f"✅ Выполнено раз: {todo.recurrence_count}")
    
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
        
        # Recurrence icon
        recurrence_icon = ""
        if hasattr(todo, 'is_recurring') and todo.is_recurring:
            recurrence_icon = "🔁"
        
        title = todo.title[:35] + "..." if len(todo.title) > 35 else todo.title
        
        deadline_info = ""
        if todo.deadline:
            if todo.is_overdue:
                deadline_info = " ⚠️"
            else:
                deadline_info = f" 📅"
        
        lines.append(f"{i}. {status_emoji}{priority_emoji}{recurrence_icon} {title}{deadline_info}")
    
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
