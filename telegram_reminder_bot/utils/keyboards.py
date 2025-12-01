"""
Keyboard utilities for the bot
"""
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard"""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="📝 Задачи"),
        KeyboardButton(text="⏰ Напоминания")
    )
    builder.row(
        KeyboardButton(text="📝 Заметки"),
        KeyboardButton(text="🔐 Пароли")
    )
    builder.row(
        KeyboardButton(text="➕ Новая задача"),
        KeyboardButton(text="🔔 Новое напоминание")
    )
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="⚙️ Настройки")
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Get keyboard with cancel button"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def get_reminder_keyboard(reminder_id: str, is_active: bool = False) -> InlineKeyboardMarkup:
    """Get inline keyboard for reminder actions"""
    builder = InlineKeyboardBuilder()
    
    if is_active:
        # Active reminder - show snooze and complete options
        builder.row(
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"reminder_complete:{reminder_id}"),
            InlineKeyboardButton(text="⏸️ Отложить", callback_data=f"reminder_snooze_menu:{reminder_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🔇 Отключить звук", callback_data=f"reminder_mute:{reminder_id}")
        )
    else:
        # Regular reminder actions
        builder.row(
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"reminder_edit:{reminder_id}"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"reminder_delete:{reminder_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Повторять", callback_data=f"reminder_recurrence:{reminder_id}")
        )
    
    return builder.as_markup()


def get_snooze_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for snooze options"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="5 мин", callback_data=f"reminder_snooze:{reminder_id}:5"),
        InlineKeyboardButton(text="10 мин", callback_data=f"reminder_snooze:{reminder_id}:10"),
        InlineKeyboardButton(text="15 мин", callback_data=f"reminder_snooze:{reminder_id}:15")
    )
    builder.row(
        InlineKeyboardButton(text="30 мин", callback_data=f"reminder_snooze:{reminder_id}:30"),
        InlineKeyboardButton(text="1 час", callback_data=f"reminder_snooze:{reminder_id}:60"),
        InlineKeyboardButton(text="2 часа", callback_data=f"reminder_snooze:{reminder_id}:120")
    )
    builder.row(
        InlineKeyboardButton(text="Завтра", callback_data=f"reminder_snooze:{reminder_id}:tomorrow"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"reminder_snooze_back:{reminder_id}")
    )
    
    return builder.as_markup()


def get_recurrence_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for recurrence options"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="Без повтора", callback_data=f"recurrence_set:{reminder_id}:none"),
        InlineKeyboardButton(text="Ежедневно", callback_data=f"recurrence_set:{reminder_id}:daily")
    )
    builder.row(
        InlineKeyboardButton(text="Еженедельно", callback_data=f"recurrence_set:{reminder_id}:weekly"),
        InlineKeyboardButton(text="Ежемесячно", callback_data=f"recurrence_set:{reminder_id}:monthly")
    )
    builder.row(
        InlineKeyboardButton(text="Ежегодно", callback_data=f"recurrence_set:{reminder_id}:yearly")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"reminder_back:{reminder_id}")
    )
    
    return builder.as_markup()


def get_todo_keyboard(todo_id: str) -> InlineKeyboardMarkup:
    """Get inline keyboard for todo actions"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Готово", callback_data=f"todo_complete:{todo_id}"),
        InlineKeyboardButton(text="🔄 В работе", callback_data=f"todo_progress:{todo_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить", callback_data=f"todo_edit:{todo_id}"),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"todo_delete:{todo_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⏰ Дедлайн", callback_data=f"todo_deadline:{todo_id}"),
        InlineKeyboardButton(text="🎯 Приоритет", callback_data=f"todo_priority:{todo_id}")
    )
    
    return builder.as_markup()


def get_priority_keyboard(todo_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for priority selection"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🟢 Низкий", callback_data=f"priority_set:{todo_id}:low"),
        InlineKeyboardButton(text="🟡 Средний", callback_data=f"priority_set:{todo_id}:medium")
    )
    builder.row(
        InlineKeyboardButton(text="🟠 Высокий", callback_data=f"priority_set:{todo_id}:high"),
        InlineKeyboardButton(text="🔴 Срочный", callback_data=f"priority_set:{todo_id}:urgent")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"todo_back:{todo_id}")
    )
    
    return builder.as_markup()


def get_todos_list_keyboard(todos: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Get keyboard with list of todos"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_todos = todos[start:end]
    
    for todo in page_todos:
        status_emoji = todo.status_emoji
        priority_emoji = todo.priority_emoji
        title = todo.title[:30] + "..." if len(todo.title) > 30 else todo.title
        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {priority_emoji} {title}",
                callback_data=f"todo_view:{todo.id}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"todos_page:{page-1}"))
    if end < len(todos):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"todos_page:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="➕ Новая задача", callback_data="todo_new")
    )
    
    return builder.as_markup()


def get_reminders_list_keyboard(reminders: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Get keyboard with list of reminders"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_reminders = reminders[start:end]
    
    for reminder in page_reminders:
        status_icon = "🔔" if reminder.status == "pending" else "✅" if reminder.status == "completed" else "⏸️"
        recurrence_icon = "🔄" if reminder.is_recurring else ""
        title = reminder.title[:30] + "..." if len(reminder.title) > 30 else reminder.title
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon}{recurrence_icon} {title}",
                callback_data=f"reminder_view:{reminder.id}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"reminders_page:{page-1}"))
    if end < len(reminders):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"reminders_page:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔔 Новое напоминание", callback_data="reminder_new")
    )
    
    return builder.as_markup()


def get_confirmation_keyboard(action: str, item_id: str) -> InlineKeyboardMarkup:
    """Get confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"{action}_confirm:{item_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"{action}_cancel:{item_id}")
    )
    
    return builder.as_markup()


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Get settings menu keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="settings_timezone")
    )
    builder.row(
        InlineKeyboardButton(text="🔔 Интервал уведомлений", callback_data="settings_interval")
    )
    builder.row(
        InlineKeyboardButton(text="🔐 Экспорт данных", callback_data="settings_export")
    )
    
    return builder.as_markup()
