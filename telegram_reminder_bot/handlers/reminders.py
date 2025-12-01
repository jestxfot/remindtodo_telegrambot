"""
Reminder handlers
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.database import async_session
from models.reminder import RecurrenceType
from services.user_service import UserService
from services.reminder_service import ReminderService
from utils.keyboards import (
    get_main_keyboard, 
    get_cancel_keyboard,
    get_reminder_keyboard,
    get_reminders_list_keyboard,
    get_recurrence_keyboard
)
from utils.date_parser import parse_datetime, parse_recurrence
from utils.formatters import format_reminder, format_reminders_list

router = Router()


class ReminderStates(StatesGroup):
    """States for reminder creation"""
    waiting_for_text = State()
    waiting_for_time = State()
    waiting_for_recurrence = State()
    editing_title = State()
    editing_time = State()


async def show_reminders_list(message: Message):
    """Show list of user's reminders"""
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        
        if not user:
            await message.answer("Пользователь не найден. Используйте /start")
            return
        
        reminder_service = ReminderService(session)
        reminders = await reminder_service.get_user_reminders(user.id)
        
        text = format_reminders_list(reminders, user.timezone)
        keyboard = get_reminders_list_keyboard(reminders)
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def start_create_reminder(message: Message, state: FSMContext):
    """Start reminder creation process"""
    await state.set_state(ReminderStates.waiting_for_text)
    
    await message.answer(
        "🔔 <b>Новое напоминание</b>\n\n"
        "Напишите текст напоминания и время.\n\n"
        "<b>Примеры:</b>\n"
        "• <code>Позвонить маме завтра в 10:00</code>\n"
        "• <code>Встреча через 2 часа</code>\n"
        "• <code>Оплатить счёт 15.01 в 12:00</code>\n"
        "• <code>Забрать посылку в пятницу</code>\n\n"
        "Или просто напишите текст, а время укажите следующим сообщением.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("newreminder"))
async def cmd_new_reminder(message: Message, state: FSMContext):
    """Handle /newreminder command"""
    await start_create_reminder(message, state)


@router.message(Command("reminders"))
async def cmd_reminders(message: Message):
    """Handle /reminders command"""
    await show_reminders_list(message)


@router.message(ReminderStates.waiting_for_text)
async def process_reminder_text(message: Message, state: FSMContext):
    """Process reminder text input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание напоминания отменено", reply_markup=get_main_keyboard())
        return
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        timezone = user.timezone if user else "Europe/Moscow"
    
    # Try to parse datetime from the text
    remind_at = parse_datetime(text, timezone)
    
    if remind_at:
        # Successfully parsed datetime from text
        # Extract title (remove time-related words)
        title = text
        
        async with async_session() as session:
            user_service = UserService(session)
            user = await user_service.get_user_by_telegram_id(message.from_user.id)
            
            if not user:
                await message.answer("Ошибка: пользователь не найден")
                return
            
            reminder_service = ReminderService(session)
            reminder = await reminder_service.create_reminder(
                user_id=user.id,
                title=title,
                remind_at=remind_at,
                is_persistent=True,
                with_sound=True
            )
            
            await state.clear()
            
            formatted = format_reminder(reminder, user.timezone)
            await message.answer(
                f"✅ Напоминание создано!\n\n{formatted}",
                reply_markup=get_reminder_keyboard(reminder.id),
                parse_mode="HTML"
            )
            
            await message.answer(
                "Используйте кнопки для настройки повторения или других параметров.",
                reply_markup=get_main_keyboard()
            )
    else:
        # Could not parse datetime, ask for it separately
        await state.update_data(title=text)
        await state.set_state(ReminderStates.waiting_for_time)
        
        await message.answer(
            f"📝 Текст: <b>{text}</b>\n\n"
            "Теперь укажите время напоминания:\n\n"
            "<b>Примеры:</b>\n"
            "• <code>завтра в 10:00</code>\n"
            "• <code>через 30 минут</code>\n"
            "• <code>15.01.2025 14:00</code>\n"
            "• <code>в понедельник в 9:00</code>",
            parse_mode="HTML"
        )


@router.message(ReminderStates.waiting_for_time)
async def process_reminder_time(message: Message, state: FSMContext):
    """Process reminder time input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание напоминания отменено", reply_markup=get_main_keyboard())
        return
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        timezone = user.timezone if user else "Europe/Moscow"
    
    remind_at = parse_datetime(text, timezone)
    
    if not remind_at:
        await message.answer(
            "⚠️ Не удалось распознать время.\n\n"
            "Попробуйте указать время в одном из форматов:\n"
            "• <code>завтра в 10:00</code>\n"
            "• <code>через 2 часа</code>\n"
            "• <code>15.01.2025 14:00</code>",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    title = data.get("title", "Напоминание")
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        
        if not user:
            await message.answer("Ошибка: пользователь не найден")
            return
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.create_reminder(
            user_id=user.id,
            title=title,
            remind_at=remind_at,
            is_persistent=True,
            with_sound=True
        )
        
        await state.clear()
        
        formatted = format_reminder(reminder, user.timezone)
        await message.answer(
            f"✅ Напоминание создано!\n\n{formatted}",
            reply_markup=get_reminder_keyboard(reminder.id),
            parse_mode="HTML"
        )
        
        await message.answer(
            "Используйте кнопки для настройки повторения.",
            reply_markup=get_main_keyboard()
        )


@router.callback_query(F.data.startswith("reminder_view:"))
async def cb_reminder_view(callback: CallbackQuery):
    """View reminder details"""
    reminder_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.get_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        formatted = format_reminder(reminder, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_reminder_keyboard(reminder.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("reminder_recurrence:"))
async def cb_reminder_recurrence(callback: CallbackQuery):
    """Show recurrence options"""
    reminder_id = int(callback.data.split(":")[1])
    
    await callback.message.edit_text(
        "🔄 <b>Настройка повторения</b>\n\n"
        "Выберите как часто повторять напоминание:",
        reply_markup=get_recurrence_keyboard(reminder_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("recurrence_set:"))
async def cb_recurrence_set(callback: CallbackQuery):
    """Set recurrence for reminder"""
    parts = callback.data.split(":")
    reminder_id = int(parts[1])
    recurrence_str = parts[2]
    
    recurrence_map = {
        "none": RecurrenceType.NONE,
        "daily": RecurrenceType.DAILY,
        "weekly": RecurrenceType.WEEKLY,
        "monthly": RecurrenceType.MONTHLY,
        "yearly": RecurrenceType.YEARLY
    }
    
    recurrence_type = recurrence_map.get(recurrence_str, RecurrenceType.NONE)
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.set_recurrence(reminder_id, recurrence_type)
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        recurrence_names = {
            RecurrenceType.NONE: "без повторения",
            RecurrenceType.DAILY: "ежедневно",
            RecurrenceType.WEEKLY: "еженедельно",
            RecurrenceType.MONTHLY: "ежемесячно",
            RecurrenceType.YEARLY: "ежегодно"
        }
        
        await callback.answer(f"✅ Повторение: {recurrence_names.get(recurrence_type, 'установлено')}")
        
        formatted = format_reminder(reminder, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_reminder_keyboard(reminder.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("reminder_delete:"))
async def cb_reminder_delete(callback: CallbackQuery):
    """Delete reminder"""
    reminder_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        reminder_service = ReminderService(session)
        deleted = await reminder_service.delete_reminder(reminder_id)
        
        if deleted:
            await callback.answer("🗑️ Напоминание удалено")
            await callback.message.edit_text("Напоминание удалено")
        else:
            await callback.answer("Напоминание не найдено")


@router.callback_query(F.data.startswith("reminder_back:"))
async def cb_reminder_back(callback: CallbackQuery):
    """Go back to reminder view"""
    reminder_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        reminder_service = ReminderService(session)
        reminder = await reminder_service.get_reminder(reminder_id)
        
        if not reminder:
            await callback.answer("Напоминание не найдено")
            return
        
        formatted = format_reminder(reminder, user.timezone if user else "Europe/Moscow")
        await callback.message.edit_text(
            formatted,
            reply_markup=get_reminder_keyboard(reminder.id),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "reminder_new")
async def cb_reminder_new(callback: CallbackQuery, state: FSMContext):
    """Start creating new reminder from callback"""
    await callback.message.delete()
    await start_create_reminder(callback.message, state)


@router.callback_query(F.data.startswith("reminders_page:"))
async def cb_reminders_page(callback: CallbackQuery):
    """Handle reminders pagination"""
    page = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        if not user:
            await callback.answer("Пользователь не найден")
            return
        
        reminder_service = ReminderService(session)
        reminders = await reminder_service.get_user_reminders(user.id)
        
        text = format_reminders_list(reminders, user.timezone)
        keyboard = get_reminders_list_keyboard(reminders, page)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
