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
        KeyboardButton(text="📅 Календарь"),
        KeyboardButton(text="📊 Статистика")
    )
    builder.row(
        KeyboardButton(text="⚙️ Настройки")
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Get keyboard with cancel button"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def get_reminder_keyboard(reminder_id: str, is_active: bool = False, is_recurring: bool = False) -> InlineKeyboardMarkup:
    """Get inline keyboard for reminder actions
    Shortened callback_data: rmc=complete, rsm=snooze_menu, rmm=mute, rme=edit, rmr=recurrence, rma=archive, rmd=delete
    """
    builder = InlineKeyboardBuilder()
    
    if is_active:
        # Active reminder - show snooze and complete options
        builder.row(
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"rmc:{reminder_id}"),
            InlineKeyboardButton(text="⏸️ Отложить", callback_data=f"rsm:{reminder_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🔇 Отключить звук", callback_data=f"rmm:{reminder_id}")
        )
    else:
        # Regular reminder actions
        builder.row(
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"rmc:{reminder_id}"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"rme:{reminder_id}")
        )
        builder.row(
            InlineKeyboardButton(
                text="🔄 Повторение" if not is_recurring else "🔄 Повторение ✓",
                callback_data=f"rmr:{reminder_id}")
        )
        builder.row(
            InlineKeyboardButton(text="📦 В архив", callback_data=f"rma:{reminder_id}"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"rmd:{reminder_id}")
        )
    
    return builder.as_markup()


def get_snooze_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for snooze options (rs=snooze, rsb=snooze_back)"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="5 мин", callback_data=f"rs:{reminder_id}:5"),
        InlineKeyboardButton(text="10 мин", callback_data=f"rs:{reminder_id}:10"),
        InlineKeyboardButton(text="15 мин", callback_data=f"rs:{reminder_id}:15")
    )
    builder.row(
        InlineKeyboardButton(text="30 мин", callback_data=f"rs:{reminder_id}:30"),
        InlineKeyboardButton(text="1 час", callback_data=f"rs:{reminder_id}:60"),
        InlineKeyboardButton(text="2 часа", callback_data=f"rs:{reminder_id}:120")
    )
    builder.row(
        InlineKeyboardButton(text="Завтра", callback_data=f"rs:{reminder_id}:tomorrow"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"rsb:{reminder_id}")
    )
    
    return builder.as_markup()


def get_recurrence_keyboard(reminder_id: str, item_type: str = "reminder") -> InlineKeyboardMarkup:
    """Get keyboard for recurrence options (rcs=reminder recurrence set, trs=todo recurrence set)"""
    builder = InlineKeyboardBuilder()
    # Shortened: rcs=recurrence_set (reminder), trs=todo_recurrence_set
    prefix = "rcs" if item_type == "reminder" else "trs"
    back_action = "rmb" if item_type == "reminder" else "tb"
    
    builder.row(
        InlineKeyboardButton(text="❌ Без повтора", callback_data=f"{prefix}:{reminder_id}:none"),
        InlineKeyboardButton(text="📆 Ежедневно", callback_data=f"{prefix}:{reminder_id}:daily")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Еженедельно", callback_data=f"{prefix}:{reminder_id}:weekly"),
        InlineKeyboardButton(text="🗓️ Ежемесячно", callback_data=f"{prefix}:{reminder_id}:monthly")
    )
    builder.row(
        InlineKeyboardButton(text="📆 Ежегодно", callback_data=f"{prefix}:{reminder_id}:yearly")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Свой интервал...", callback_data=f"recurrence_custom:{reminder_id}:{item_type}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{back_action}:{reminder_id}")
    )
    
    return builder.as_markup()


def get_custom_recurrence_keyboard(item_id: str, item_type: str = "reminder") -> InlineKeyboardMarkup:
    """Get keyboard for custom recurrence interval selection"""
    builder = InlineKeyboardBuilder()
    # Сокращённый формат: rc:{id}:{t}:{val}:{u}
    # t: r=reminder, t=todo
    # u: d=days, w=weeks, m=months
    t = "r" if item_type == "reminder" else "t"
    
    # Дни
    builder.row(
        InlineKeyboardButton(text="Каждые 2 дня", callback_data=f"rc:{item_id}:{t}:2:d"),
        InlineKeyboardButton(text="Каждые 3 дня", callback_data=f"rc:{item_id}:{t}:3:d")
    )
    builder.row(
        InlineKeyboardButton(text="Каждые 4 дня", callback_data=f"rc:{item_id}:{t}:4:d"),
        InlineKeyboardButton(text="Каждые 5 дней", callback_data=f"rc:{item_id}:{t}:5:d")
    )
    # Недели
    builder.row(
        InlineKeyboardButton(text="Раз в 2 недели", callback_data=f"rc:{item_id}:{t}:2:w"),
        InlineKeyboardButton(text="Раз в 3 недели", callback_data=f"rc:{item_id}:{t}:3:w")
    )
    # Месяцы
    builder.row(
        InlineKeyboardButton(text="Раз в 2 месяца", callback_data=f"rc:{item_id}:{t}:2:m"),
        InlineKeyboardButton(text="Раз в 3 месяца", callback_data=f"rc:{item_id}:{t}:3:m")
    )
    builder.row(
        InlineKeyboardButton(text="Раз в 6 месяцев", callback_data=f"rc:{item_id}:{t}:6:m")
    )
    # Ввод вручную
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"ri:{item_id}:{t}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"rb:{item_id}:{t}")
    )
    
    return builder.as_markup()


def get_todo_keyboard(todo_id: str, is_recurring: bool = False) -> InlineKeyboardMarkup:
    """Get inline keyboard for todo actions
    Shortened: tc=complete, tp=progress, tdl=deadline, tpr=priority, tr=recurrence, ta=archive, tdd=delete
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Готово", callback_data=f"tc:{todo_id}"),
        InlineKeyboardButton(text="🔄 В работе", callback_data=f"tp:{todo_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⏰ Дедлайн", callback_data=f"tdl:{todo_id}"),
        InlineKeyboardButton(text="🎯 Приоритет", callback_data=f"tpr:{todo_id}")
    )
    builder.row(
        InlineKeyboardButton(
            text="🔁 Повторение" if not is_recurring else "🔁 Повторение ✓",
            callback_data=f"tr:{todo_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📦 В архив", callback_data=f"ta:{todo_id}"),
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"tdd:{todo_id}")
    )
    
    return builder.as_markup()


def get_priority_keyboard(todo_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for priority selection (ps=priority_set, tb=todo_back)"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🟢 Низкий", callback_data=f"ps:{todo_id}:low"),
        InlineKeyboardButton(text="🟡 Средний", callback_data=f"ps:{todo_id}:medium")
    )
    builder.row(
        InlineKeyboardButton(text="🟠 Высокий", callback_data=f"ps:{todo_id}:high"),
        InlineKeyboardButton(text="🔴 Срочный", callback_data=f"ps:{todo_id}:urgent")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"tb:{todo_id}")
    )
    
    return builder.as_markup()


def get_todos_list_keyboard(todos: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Get keyboard with list of todos (tv=view, tpg=page)"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_todos = todos[start:end]
    
    for todo in page_todos:
        status_emoji = todo.status_emoji
        priority_emoji = todo.priority_emoji
        recurrence_emoji = todo.recurrence_emoji if hasattr(todo, 'recurrence_emoji') else ""
        title = todo.title[:25] + "..." if len(todo.title) > 25 else todo.title
        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {priority_emoji}{recurrence_emoji} {title}",
                callback_data=f"tv:{todo.id}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"tpg:{page-1}"))
    if end < len(todos):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"tpg:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="➕ Новая задача", callback_data="tn"),
        InlineKeyboardButton(text="📦 Архив", callback_data="tar")
    )
    
    return builder.as_markup()


def get_reminders_list_keyboard(reminders: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Get keyboard with list of reminders (rmv=view, rpg=page, rn=new)"""
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
                callback_data=f"rmv:{reminder.id}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"rpg:{page-1}"))
    if end < len(reminders):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"rpg:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="🔔 Новое напоминание", callback_data="rn")
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
        InlineKeyboardButton(text="💾 Ежедневные бэкапы", callback_data="settings_backup")
    )
    builder.row(
        InlineKeyboardButton(text="🔐 Экспорт данных", callback_data="settings_export")
    )
    
    return builder.as_markup()
