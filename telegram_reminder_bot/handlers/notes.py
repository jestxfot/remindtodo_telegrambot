"""
Note handlers - encrypted notes management
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.json_storage import storage
from handlers.auth import get_crypto_for_user
from utils.keyboards import get_main_keyboard, get_cancel_keyboard


async def get_user_storage(user_id: int):
    """Get user storage with authentication"""
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    return await storage.get_user_storage(user_id, crypto)

router = Router()


class NoteStates(StatesGroup):
    """States for note operations"""
    waiting_for_title = State()
    waiting_for_content = State()
    editing_title = State()
    editing_content = State()
    searching = State()


def get_notes_list_keyboard(notes: list, page: int = 0, per_page: int = 5):
    """Get keyboard with list of notes"""
    builder = InlineKeyboardBuilder()
    
    start = page * per_page
    end = start + per_page
    page_notes = notes[start:end]
    
    for note in page_notes:
        pin_icon = "📌" if note.is_pinned else ""
        title = note.title[:30] + "..." if len(note.title) > 30 else note.title
        builder.row(
            InlineKeyboardButton(
                text=f"{pin_icon}📝 {title}",
                callback_data=f"note_view:{note.id}"
            )
        )
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"notes_page:{page-1}"))
    if end < len(notes):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"notes_page:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(
        InlineKeyboardButton(text="📝 Новая заметка", callback_data="note_new"),
        InlineKeyboardButton(text="🔍 Поиск", callback_data="note_search")
    )
    
    return builder.as_markup()


def get_note_keyboard(note_id: str):
    """Get keyboard for note actions"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"note_edit:{note_id}"),
        InlineKeyboardButton(text="📌 Закрепить", callback_data=f"note_pin:{note_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"note_delete:{note_id}"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="notes_list")
    )
    
    return builder.as_markup()


async def show_notes_list(message: Message):
    """Show list of user's notes"""
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    notes = await user_storage.get_notes()
    
    if not notes:
        text = "📝 <b>Заметки</b>\n\nУ вас пока нет заметок.\n\nСоздайте первую заметку - она будет надёжно зашифрована! 🔐"
    else:
        text = f"📝 <b>Ваши заметки ({len(notes)})</b>\n\n🔐 Все заметки зашифрованы AES-256-GCM"
    
    await message.answer(
        text,
        reply_markup=get_notes_list_keyboard(notes),
        parse_mode="HTML"
    )


async def start_create_note(message: Message, state: FSMContext):
    """Start note creation process"""
    await state.set_state(NoteStates.waiting_for_title)
    
    await message.answer(
        "📝 <b>Новая заметка</b>\n\n"
        "Введите заголовок заметки:\n\n"
        "🔐 Заметка будет зашифрована AES-256-GCM",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("notes"))
async def cmd_notes(message: Message):
    """Handle /notes command"""
    await show_notes_list(message)


@router.message(Command("newnote"))
async def cmd_new_note(message: Message, state: FSMContext):
    """Handle /newnote command"""
    await start_create_note(message, state)


@router.message(NoteStates.waiting_for_title)
async def process_note_title(message: Message, state: FSMContext):
    """Process note title input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание заметки отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(title=text)
    await state.set_state(NoteStates.waiting_for_content)
    
    await message.answer(
        f"📝 Заголовок: <b>{text}</b>\n\n"
        "Теперь введите содержимое заметки:\n\n"
        "<i>Можете использовать несколько сообщений - напишите /done когда закончите</i>",
        parse_mode="HTML"
    )


@router.message(NoteStates.waiting_for_content)
async def process_note_content(message: Message, state: FSMContext):
    """Process note content input"""
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Создание заметки отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    title = data.get("title", "Заметка")
    
    # Get or append content
    current_content = data.get("content", "")
    
    if text == "/done":
        if not current_content:
            await message.answer("Введите содержимое заметки или нажмите ❌ Отмена")
            return
        
        # Create note
        user_storage = await get_user_storage(message.from_user.id)
        if not user_storage:
            await message.answer("🔒 Разблокируйте хранилище: /unlock")
            return
        note = await user_storage.create_note(
            title=title,
            content=current_content
        )
        
        await state.clear()
        
        await message.answer(
            f"✅ <b>Заметка создана!</b>\n\n"
            f"📝 {note.title}\n\n"
            f"🔐 Содержимое надёжно зашифровано",
            reply_markup=get_note_keyboard(note.id),
            parse_mode="HTML"
        )
        
        await message.answer("Вернуться в меню:", reply_markup=get_main_keyboard())
    else:
        # Append to content
        if current_content:
            current_content += "\n" + text
        else:
            current_content = text
        
        await state.update_data(content=current_content)
        await message.answer(
            "✓ Добавлено. Продолжайте или напишите /done для сохранения"
        )


@router.callback_query(F.data == "notes_list")
async def cb_notes_list(callback: CallbackQuery):
    """Show notes list"""
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    notes = await user_storage.get_notes()
    
    if not notes:
        text = "📝 <b>Заметки</b>\n\nУ вас пока нет заметок."
    else:
        text = f"📝 <b>Ваши заметки ({len(notes)})</b>\n\n🔐 Все заметки зашифрованы"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_notes_list_keyboard(notes),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("notes_page:"))
async def cb_notes_page(callback: CallbackQuery):
    """Handle notes pagination"""
    page = int(callback.data.split(":")[1])
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    notes = await user_storage.get_notes()
    
    text = f"📝 <b>Ваши заметки ({len(notes)})</b>\n\n🔐 Все заметки зашифрованы"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_notes_list_keyboard(notes, page),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("note_view:"))
async def cb_note_view(callback: CallbackQuery):
    """View note with decrypted content"""
    note_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    result = await user_storage.get_note_decrypted(note_id)
    
    if not result:
        await callback.answer("Заметка не найдена")
        return
    
    note, content = result
    pin_icon = "📌 " if note.is_pinned else ""
    
    # Truncate content if too long
    display_content = content[:3000] + "..." if len(content) > 3000 else content
    
    text = (
        f"{pin_icon}📝 <b>{note.title}</b>\n\n"
        f"{display_content}\n\n"
        f"<i>🕐 Обновлено: {note.updated_at[:16].replace('T', ' ')}</i>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_note_keyboard(note_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("note_pin:"))
async def cb_note_pin(callback: CallbackQuery):
    """Toggle note pin status"""
    note_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    note = await user_storage.get_note(note_id)
    
    if note:
        await user_storage.update_note(note_id, is_pinned=not note.is_pinned)
        status = "📌 Закреплено" if not note.is_pinned else "Откреплено"
        await callback.answer(status)
        
        # Refresh view
        result = await user_storage.get_note_decrypted(note_id)
        if result:
            note, content = result
            pin_icon = "📌 " if note.is_pinned else ""
            display_content = content[:3000] + "..." if len(content) > 3000 else content
            
            text = (
                f"{pin_icon}📝 <b>{note.title}</b>\n\n"
                f"{display_content}\n\n"
                f"<i>🕐 Обновлено: {note.updated_at[:16].replace('T', ' ')}</i>"
            )
            
            await callback.message.edit_text(
                text,
                reply_markup=get_note_keyboard(note_id),
                parse_mode="HTML"
            )


@router.callback_query(F.data.startswith("note_delete:"))
async def cb_note_delete(callback: CallbackQuery):
    """Delete note"""
    note_id = callback.data.split(":")[1]
    
    user_storage = await get_user_storage(callback.from_user.id)
    if not user_storage:
        await callback.answer("🔒 Разблокируйте: /unlock", show_alert=True)
        return
    deleted = await user_storage.delete_note(note_id)
    
    if deleted:
        await callback.answer("🗑️ Заметка удалена")
        
        # Show notes list
        notes = await user_storage.get_notes()
        if not notes:
            text = "📝 <b>Заметки</b>\n\nУ вас пока нет заметок."
        else:
            text = f"📝 <b>Ваши заметки ({len(notes)})</b>"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_notes_list_keyboard(notes),
            parse_mode="HTML"
        )
    else:
        await callback.answer("Заметка не найдена")


@router.callback_query(F.data == "note_new")
async def cb_note_new(callback: CallbackQuery, state: FSMContext):
    """Start creating new note"""
    await callback.message.delete()
    await start_create_note(callback.message, state)


@router.callback_query(F.data.startswith("note_edit:"))
async def cb_note_edit(callback: CallbackQuery, state: FSMContext):
    """Start editing note"""
    note_id = callback.data.split(":")[1]
    
    await state.set_state(NoteStates.editing_content)
    await state.update_data(note_id=note_id)
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование заметки</b>\n\n"
        "Введите новое содержимое заметки.\n"
        "Предыдущее содержимое будет полностью заменено.\n\n"
        "Напишите /cancel для отмены",
        parse_mode="HTML"
    )


@router.message(NoteStates.editing_content)
async def process_edit_content(message: Message, state: FSMContext):
    """Process note content edit"""
    text = message.text.strip()
    
    if text == "/cancel":
        await state.clear()
        await message.answer("Редактирование отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    note_id = data.get("note_id")
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    note = await user_storage.update_note(note_id, content=text)
    
    await state.clear()
    
    if note:
        await message.answer(
            "✅ Заметка обновлена!",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "❌ Ошибка обновления заметки",
            reply_markup=get_main_keyboard()
        )
