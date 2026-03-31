"""
User-scoped encrypted storage operations.
"""
import base64
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from config import DATA_DIR
from utils.timezone import format_dt, normalize_dt_str, now, now_str, parse_dt

from .models import (
    ArchivedItem,
    Attachment,
    Note,
    Password,
    RecurrenceType,
    Reminder,
    Todo,
    User,
    UserData,
)


class UserStorage:
    """
    User-specific storage handler with encryption.

    Requires authenticated crypto manager from user's session.
    """

    def __init__(self, storage: Any, user_id: int, crypto: Any):
        self.storage = storage
        self.user_id = user_id
        self._crypto = crypto
        self._data: Optional[UserData] = None
        self._auto_save = True

    async def load(self) -> None:
        """Load user data from storage."""
        data_exists = await self.storage.user_exists(self.user_id)

        try:
            self._data = await self.storage.load_user_data(self.user_id, self._crypto)
        except Exception as exc:
            # If data exists but decryption failed, do not create an empty dataset.
            if data_exists:
                print(f"[CRITICAL] Failed to decrypt data for user {self.user_id}: {exc}")
                raise ValueError(
                    "Failed to decrypt existing data. Wrong key or corrupted file."
                ) from exc
            self._data = None

        if self._data is None:
            if data_exists:
                raise ValueError(
                    "Encrypted user data exists but could not be loaded. Refusing to overwrite."
                )
            print(f"[INFO] Creating new storage for user {self.user_id}")
            self._data = UserData(user=User(id=self.user_id))

    async def save(self) -> None:
        """Save user data to storage."""
        if self._data and self._crypto:
            if await self.storage.user_exists(self.user_id):
                total_items = (
                    len(self._data.reminders)
                    + len(self._data.todos)
                    + len(self._data.notes)
                    + len(self._data.passwords)
                )
                if total_items == 0:
                    print(
                        f"[WARN] Saving empty data for user {self.user_id} while stored data exists"
                    )

            self._data.user.updated_at = now_str()
            await self.storage.save_user_data(self.user_id, self._data, self._crypto)

    async def _auto_save_if_enabled(self) -> None:
        """Auto-save if enabled."""
        if self._auto_save:
            await self.save()

    @property
    def user(self) -> User:
        return self._data.user

    async def update_user(self, **kwargs) -> User:
        """Update user fields."""
        for key, value in kwargs.items():
            if hasattr(self._data.user, key):
                setattr(self._data.user, key, value)
        self._data.user.updated_at = now_str()
        await self._auto_save_if_enabled()
        return self._data.user

    async def create_reminder(self, **kwargs) -> Reminder:
        """Create a new reminder."""
        if "remind_at" in kwargs:
            kwargs["remind_at"] = normalize_dt_str(kwargs.get("remind_at"))
        if "recurrence_end_date" in kwargs:
            kwargs["recurrence_end_date"] = normalize_dt_str(
                kwargs.get("recurrence_end_date")
            )
        if "snoozed_until" in kwargs:
            kwargs["snoozed_until"] = normalize_dt_str(kwargs.get("snoozed_until"))
        if "last_notification_at" in kwargs:
            kwargs["last_notification_at"] = normalize_dt_str(
                kwargs.get("last_notification_at")
            )
        reminder = Reminder(id=str(uuid.uuid4()), user_id=self.user_id, **kwargs)
        self._data.reminders.append(reminder)
        await self._auto_save_if_enabled()
        return reminder

    async def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Get reminder by ID."""
        for reminder in self._data.reminders:
            if reminder.id == reminder_id:
                return reminder
        return None

    async def get_reminders(self, include_completed: bool = False) -> List[Reminder]:
        """Get all reminders."""
        if include_completed:
            return self._data.reminders.copy()
        return [
            reminder
            for reminder in self._data.reminders
            if reminder.status not in ["completed", "cancelled"]
        ]

    async def update_persistent_reminder_interval(self, interval_seconds: int) -> int:
        """Update persistent interval for all persistent reminders."""
        updated = 0
        for reminder in self._data.reminders:
            if reminder.is_persistent:
                reminder.persistent_interval = interval_seconds
                reminder.updated_at = now_str()
                updated += 1
        if updated:
            await self._auto_save_if_enabled()
        return updated

    async def update_reminder(self, reminder_id: str, **kwargs) -> Optional[Reminder]:
        """Update a reminder."""
        if "remind_at" in kwargs:
            kwargs["remind_at"] = normalize_dt_str(kwargs.get("remind_at"))
        if "recurrence_end_date" in kwargs:
            kwargs["recurrence_end_date"] = normalize_dt_str(
                kwargs.get("recurrence_end_date")
            )
        if "snoozed_until" in kwargs:
            kwargs["snoozed_until"] = normalize_dt_str(kwargs.get("snoozed_until"))
        if "last_notification_at" in kwargs:
            kwargs["last_notification_at"] = normalize_dt_str(
                kwargs.get("last_notification_at")
            )

        reminder = await self.get_reminder(reminder_id)
        if reminder:
            for key, value in kwargs.items():
                if hasattr(reminder, key):
                    setattr(reminder, key, value)
            reminder.updated_at = now_str()
            await self._auto_save_if_enabled()
        return reminder

    async def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder."""
        for index, reminder in enumerate(self._data.reminders):
            if reminder.id == reminder_id:
                self._data.reminders.pop(index)
                await self._auto_save_if_enabled()
                return True
        return False

    async def create_todo(self, **kwargs) -> Todo:
        """Create a new todo."""
        if "deadline" in kwargs:
            kwargs["deadline"] = normalize_dt_str(kwargs.get("deadline"))
        if "recurrence_end_date" in kwargs:
            kwargs["recurrence_end_date"] = normalize_dt_str(
                kwargs.get("recurrence_end_date")
            )
        if "completed_at" in kwargs:
            kwargs["completed_at"] = normalize_dt_str(kwargs.get("completed_at"))

        max_order = max([todo.order for todo in self._data.todos], default=0)
        todo = Todo(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            order=max_order + 1,
            **kwargs,
        )
        self._data.todos.append(todo)
        await self._auto_save_if_enabled()
        return todo

    async def get_todo(self, todo_id: str) -> Optional[Todo]:
        """Get todo by ID."""
        for todo in self._data.todos:
            if todo.id == todo_id:
                return todo
        return None

    async def get_todos(self, include_completed: bool = False) -> List[Todo]:
        """Get all todos."""
        todos = self._data.todos.copy()
        if not include_completed:
            todos = [todo for todo in todos if todo.status not in ["completed", "cancelled"]]
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        todos.sort(key=lambda todo: (priority_order.get(todo.priority, 2), todo.order))
        return todos

    async def update_todo(self, todo_id: str, **kwargs) -> Optional[Todo]:
        """Update a todo."""
        if "deadline" in kwargs:
            kwargs["deadline"] = normalize_dt_str(kwargs.get("deadline"))
        if "recurrence_end_date" in kwargs:
            kwargs["recurrence_end_date"] = normalize_dt_str(
                kwargs.get("recurrence_end_date")
            )
        if "completed_at" in kwargs:
            kwargs["completed_at"] = normalize_dt_str(kwargs.get("completed_at"))

        todo = await self.get_todo(todo_id)
        if todo:
            for key, value in kwargs.items():
                if hasattr(todo, key):
                    setattr(todo, key, value)
            todo.updated_at = now_str()
            await self._auto_save_if_enabled()
        return todo

    async def complete_todo(self, todo_id: str) -> tuple[Optional[Todo], bool]:
        """
        Complete a todo.

        For recurring todos, calculate the next deadline from the current deadline
        and keep incrementing until it lands in the future.
        """
        from datetime import timedelta

        from dateutil.relativedelta import relativedelta

        todo = await self.get_todo(todo_id)
        if not todo:
            return None, False

        current_time = now()
        todo.completed_at = format_dt(current_time)
        todo.recurrence_count += 1

        if todo.is_recurring:
            if todo.recurrence_end_date:
                end_dt = parse_dt(todo.recurrence_end_date)
                if current_time >= end_dt:
                    todo.status = "completed"
                    await self._auto_save_if_enabled()
                    await self.archive_todo(todo_id)
                    return todo, True

            interval = todo.recurrence_interval or 1
            base_time = parse_dt(todo.deadline) if todo.deadline else current_time

            if todo.recurrence_type == RecurrenceType.DAILY.value:
                delta = relativedelta(days=interval)
            elif todo.recurrence_type == RecurrenceType.WEEKLY.value:
                delta = relativedelta(weeks=interval)
            elif todo.recurrence_type == RecurrenceType.MONTHLY.value:
                delta = relativedelta(months=interval)
            elif todo.recurrence_type == RecurrenceType.YEARLY.value:
                delta = relativedelta(years=interval)
            elif todo.recurrence_type == RecurrenceType.CUSTOM.value:
                delta = timedelta(days=interval)
            else:
                delta = relativedelta(days=interval)

            next_deadline = base_time + delta
            while next_deadline <= current_time:
                next_deadline = next_deadline + delta
                if (next_deadline - current_time).days > 365 * 10:
                    break

            if todo.recurrence_end_date:
                end_dt = parse_dt(todo.recurrence_end_date)
                if next_deadline > end_dt:
                    todo.status = "completed"
                    await self._auto_save_if_enabled()
                    await self.archive_todo(todo_id)
                    return todo, True

            todo.deadline = format_dt(next_deadline)
            todo.status = "pending"
            todo.completed_at = None
            await self._auto_save_if_enabled()
            return todo, False

        todo.status = "completed"
        await self._auto_save_if_enabled()
        await self.archive_todo(todo_id)
        return todo, True

    async def complete_reminder(self, reminder_id: str) -> tuple[Optional[Reminder], bool]:
        """
        Complete a reminder.

        For recurring reminders, calculate the next remind_at from the current
        scheduled reminder time rather than from snooze values.
        """
        from datetime import timedelta

        from dateutil.relativedelta import relativedelta

        reminder = await self.get_reminder(reminder_id)
        if not reminder:
            return None, False

        current_time = now()
        reminder.recurrence_count += 1

        if reminder.is_recurring:
            if reminder.recurrence_end_date:
                end_dt = parse_dt(reminder.recurrence_end_date)
                if current_time >= end_dt:
                    reminder.status = "completed"
                    await self._auto_save_if_enabled()
                    await self.archive_reminder(reminder_id)
                    return reminder, True

            current_remind = parse_dt(reminder.remind_at)
            interval = reminder.recurrence_interval or 1

            if reminder.recurrence_type == RecurrenceType.DAILY.value:
                delta = relativedelta(days=interval)
            elif reminder.recurrence_type == RecurrenceType.WEEKLY.value:
                delta = relativedelta(weeks=interval)
            elif reminder.recurrence_type == RecurrenceType.MONTHLY.value:
                delta = relativedelta(months=interval)
            elif reminder.recurrence_type == RecurrenceType.YEARLY.value:
                delta = relativedelta(years=interval)
            elif reminder.recurrence_type == RecurrenceType.CUSTOM.value:
                delta = timedelta(days=interval)
            else:
                delta = relativedelta(days=interval)

            next_remind = current_remind + delta
            while next_remind <= current_time:
                next_remind = next_remind + delta
                if (next_remind - current_time).days > 365 * 10:
                    break

            if reminder.recurrence_end_date:
                end_dt = parse_dt(reminder.recurrence_end_date)
                if next_remind > end_dt:
                    reminder.status = "completed"
                    await self._auto_save_if_enabled()
                    await self.archive_reminder(reminder_id)
                    return reminder, True

            reminder.remind_at = format_dt(next_remind)
            reminder.status = "pending"
            reminder.last_notification_at = None
            reminder.snooze_count = 0
            reminder.snoozed_until = None
            await self._auto_save_if_enabled()
            return reminder, False

        reminder.status = "completed"
        await self._auto_save_if_enabled()
        await self.archive_reminder(reminder_id)
        return reminder, True

    async def delete_todo(self, todo_id: str) -> bool:
        """Delete a todo."""
        for index, todo in enumerate(self._data.todos):
            if todo.id == todo_id:
                self._data.todos.pop(index)
                await self._auto_save_if_enabled()
                return True
        return False

    async def archive_todo(self, todo_id: str) -> bool:
        """Archive a todo instead of deleting it."""
        for index, todo in enumerate(self._data.todos):
            if todo.id == todo_id:
                archived_todo = self._data.todos.pop(index)
                archived = ArchivedItem(
                    item_type="todo",
                    data=archived_todo.to_dict(),
                    archived_at=now_str(),
                )
                self._data.archive.append(archived)
                await self._auto_save_if_enabled()
                return True
        return False

    async def archive_reminder(self, reminder_id: str) -> bool:
        """Archive a reminder instead of deleting it."""
        for index, reminder in enumerate(self._data.reminders):
            if reminder.id == reminder_id:
                archived_reminder = self._data.reminders.pop(index)
                archived = ArchivedItem(
                    item_type="reminder",
                    data=archived_reminder.to_dict(),
                    archived_at=now_str(),
                )
                self._data.archive.append(archived)
                await self._auto_save_if_enabled()
                return True
        return False

    async def get_archive(self, item_type: Optional[str] = None) -> List[ArchivedItem]:
        """Get archived items, optionally filtered by type."""
        archive = self._data.archive.copy()
        if item_type:
            archive = [item for item in archive if item.item_type == item_type]
        archive.sort(key=lambda item: item.archived_at, reverse=True)
        return archive

    async def restore_from_archive(self, archived_at: str) -> bool:
        """Restore item from archive."""
        for index, item in enumerate(self._data.archive):
            if item.archived_at == archived_at:
                archived = self._data.archive.pop(index)

                if archived.item_type == "todo":
                    todo = Todo.from_dict(archived.data)
                    todo.status = "pending"
                    todo.archived_at = None
                    self._data.todos.append(todo)
                elif archived.item_type == "reminder":
                    reminder = Reminder.from_dict(archived.data)
                    reminder.status = "pending"
                    reminder.archived_at = None
                    self._data.reminders.append(reminder)

                await self._auto_save_if_enabled()
                return True
        return False

    async def delete_from_archive(self, archived_at: str) -> bool:
        """Permanently delete an archived item."""
        for index, item in enumerate(self._data.archive):
            if item.archived_at == archived_at:
                self._data.archive.pop(index)
                await self._auto_save_if_enabled()
                return True
        return False

    async def clear_archive(self, item_type: Optional[str] = None) -> int:
        """Clear archive and return the number of deleted items."""
        if item_type:
            original_len = len(self._data.archive)
            self._data.archive = [
                item for item in self._data.archive if item.item_type != item_type
            ]
            deleted = original_len - len(self._data.archive)
        else:
            deleted = len(self._data.archive)
            self._data.archive = []

        if deleted > 0:
            await self._auto_save_if_enabled()
        return deleted

    async def migrate_completed_to_archive(self) -> dict:
        """Migrate all completed reminders and todos to archive."""
        migrated = {"reminders": 0, "todos": 0}

        reminders_to_archive = [r.id for r in self._data.reminders if r.status == "completed"]
        for reminder_id in reminders_to_archive:
            if await self.archive_reminder(reminder_id):
                migrated["reminders"] += 1

        todos_to_archive = [t.id for t in self._data.todos if t.status == "completed"]
        for todo_id in todos_to_archive:
            if await self.archive_todo(todo_id):
                migrated["todos"] += 1

        return migrated

    async def create_note(self, title: str, content: str, **kwargs) -> Note:
        """Create a new encrypted note."""
        encrypted_content = self._crypto.encrypt(content)
        note = Note(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            title=title,
            content=encrypted_content,
            **kwargs,
        )
        self._data.notes.append(note)
        await self._auto_save_if_enabled()
        return note

    async def get_note(self, note_id: str) -> Optional[Note]:
        """Get note by ID."""
        for note in self._data.notes:
            if note.id == note_id:
                return note
        return None

    async def get_note_decrypted(self, note_id: str) -> Optional[tuple[Note, str]]:
        """Get note with decrypted content."""
        note = await self.get_note(note_id)
        if note:
            decrypted_content = self._crypto.decrypt_to_string(note.content)
            return note, decrypted_content
        return None

    async def get_notes(self) -> List[Note]:
        """Get all notes."""
        notes = self._data.notes.copy()
        notes.sort(key=lambda note: (not note.is_pinned, note.updated_at), reverse=True)
        return notes

    async def get_notes_decrypted(self) -> List[Dict[str, Any]]:
        """Get all notes with decrypted content."""
        notes = await self.get_notes()
        decrypted_notes = []
        for note in notes:
            try:
                decrypted_content = self._crypto.decrypt_to_string(note.content)
            except Exception:
                decrypted_content = note.content

            decrypted_notes.append(
                {
                    "id": note.id,
                    "title": note.title,
                    "content": decrypted_content,
                    "is_pinned": note.is_pinned,
                    "tags": note.tags,
                    "links": note.links,
                    "status": note.status,
                    "color": note.color,
                    "attachments": note.attachments,
                    "created_at": note.created_at,
                    "updated_at": note.updated_at,
                }
            )
        return decrypted_notes

    async def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        **kwargs,
    ) -> Optional[Note]:
        """Update a note."""
        note = await self.get_note(note_id)
        if note:
            if title:
                note.title = title
            if content:
                note.content = self._crypto.encrypt(content)
            for key, value in kwargs.items():
                if hasattr(note, key) and key not in ["title", "content"]:
                    setattr(note, key, value)
            note.updated_at = now_str()
            await self._auto_save_if_enabled()
        return note

    async def delete_note(self, note_id: str) -> bool:
        """Delete a note and its attachments."""
        for index, note in enumerate(self._data.notes):
            if note.id == note_id:
                for attachment in note.attachments:
                    await self._delete_attachment_file(attachment.get("file_path"))
                    if attachment.get("thumbnail_path"):
                        await self._delete_attachment_file(attachment.get("thumbnail_path"))
                self._data.notes.pop(index)
                await self._auto_save_if_enabled()
                return True
        return False

    def _get_attachments_dir(self) -> Path:
        """Get directory for storing encrypted attachments."""
        attachments_dir = Path(DATA_DIR) / "attachments" / str(self.user_id)
        attachments_dir.mkdir(parents=True, exist_ok=True)
        return attachments_dir

    async def save_attachment(
        self, file_data: bytes, filename: str, file_type: str
    ) -> Attachment:
        """Save an encrypted file attachment."""
        max_size = 50 * 1024 * 1024
        if len(file_data) > max_size:
            raise ValueError(
                f"File too large. Max size is 50MB, got {len(file_data) / (1024 * 1024):.1f}MB"
            )

        attachment_id = str(uuid.uuid4())
        attachments_dir = self._get_attachments_dir()

        encrypted_data = self._crypto.encrypt_bytes(file_data)
        file_path = attachments_dir / f"{attachment_id}.enc"
        async with aiofiles.open(file_path, "wb") as file_handle:
            await file_handle.write(encrypted_data)

        thumbnail_path = None
        if file_type.startswith("image/"):
            try:
                thumbnail_path = await self._create_thumbnail(
                    file_data, attachment_id, attachments_dir
                )
            except Exception:
                thumbnail_path = None

        return Attachment(
            id=attachment_id,
            filename=filename,
            file_type=file_type,
            file_size=len(file_data),
            file_path=str(file_path),
            thumbnail_path=thumbnail_path,
        )

    async def _create_thumbnail(
        self, image_data: bytes, attachment_id: str, attachments_dir: Path
    ) -> Optional[str]:
        """Create an encrypted thumbnail for an image."""
        try:
            import io

            from PIL import Image

            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((200, 200))

            thumb_bytes = io.BytesIO()
            image.save(thumb_bytes, format="JPEG", quality=70)
            thumb_data = thumb_bytes.getvalue()

            encrypted_thumb = self._crypto.encrypt_bytes(thumb_data)
            thumb_path = attachments_dir / f"{attachment_id}_thumb.enc"
            async with aiofiles.open(thumb_path, "wb") as file_handle:
                await file_handle.write(encrypted_thumb)

            return str(thumb_path)
        except ImportError:
            return None
        except Exception:
            return None

    async def get_attachment_data(self, file_path: str) -> Optional[bytes]:
        """Read and decrypt attachment file."""
        try:
            path = Path(file_path)
            if not path.exists():
                return None

            async with aiofiles.open(path, "rb") as file_handle:
                encrypted_data = await file_handle.read()

            return self._crypto.decrypt_bytes(encrypted_data)
        except Exception:
            return None

    async def _delete_attachment_file(self, file_path: Optional[str]) -> None:
        """Delete attachment file from disk."""
        if not file_path:
            return
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
        except Exception:
            pass

    async def add_attachment_to_note(self, note_id: str, attachment: Attachment) -> bool:
        """Add attachment to a note."""
        note = await self.get_note(note_id)
        if not note:
            return False

        note.attachments.append(attachment.to_dict())
        note.updated_at = now_str()
        await self._auto_save_if_enabled()
        return True

    async def remove_attachment_from_note(self, note_id: str, attachment_id: str) -> bool:
        """Remove attachment from a note."""
        note = await self.get_note(note_id)
        if not note:
            return False

        for index, attachment in enumerate(note.attachments):
            if attachment.get("id") == attachment_id:
                await self._delete_attachment_file(attachment.get("file_path"))
                await self._delete_attachment_file(attachment.get("thumbnail_path"))
                note.attachments.pop(index)
                note.updated_at = now_str()
                await self._auto_save_if_enabled()
                return True
        return False

    async def add_attachment_to_reminder(
        self, reminder_id: str, attachment: Attachment
    ) -> bool:
        """Add attachment to a reminder."""
        reminder = await self.get_reminder(reminder_id)
        if not reminder:
            return False

        reminder.attachments.append(attachment.to_dict())
        reminder.updated_at = now_str()
        await self._auto_save_if_enabled()
        return True

    async def remove_attachment_from_reminder(
        self, reminder_id: str, attachment_id: str
    ) -> bool:
        """Remove attachment from a reminder."""
        reminder = await self.get_reminder(reminder_id)
        if not reminder:
            return False

        for index, attachment in enumerate(reminder.attachments):
            if attachment.get("id") == attachment_id:
                await self._delete_attachment_file(attachment.get("file_path"))
                await self._delete_attachment_file(attachment.get("thumbnail_path"))
                reminder.attachments.pop(index)
                reminder.updated_at = now_str()
                await self._auto_save_if_enabled()
                return True
        return False

    async def add_attachment_to_todo(
        self, todo_id: str, filename: str, file_data: str, file_type: str
    ) -> Optional[Dict[str, Any]]:
        """Add attachment to a todo."""
        todo = await self.get_todo(todo_id)
        if not todo:
            return None

        attachment = await self.save_attachment(
            base64.b64decode(file_data), filename, file_type
        )
        attachment_dict = attachment.to_dict()
        todo.attachments.append(attachment_dict)
        todo.updated_at = now_str()
        await self._auto_save_if_enabled()
        return attachment_dict

    async def remove_attachment_from_todo(self, todo_id: str, attachment_id: str) -> bool:
        """Remove attachment from a todo."""
        todo = await self.get_todo(todo_id)
        if not todo:
            return False

        for index, attachment in enumerate(todo.attachments):
            if attachment.get("id") == attachment_id:
                await self._delete_attachment_file(attachment.get("file_path"))
                await self._delete_attachment_file(attachment.get("thumbnail_path"))
                todo.attachments.pop(index)
                todo.updated_at = now_str()
                await self._auto_save_if_enabled()
                return True
        return False

    async def create_password(
        self,
        service_name: str,
        username: str,
        password: str,
        url: Optional[str] = None,
        notes: Optional[str] = None,
        totp_secret: Optional[str] = None,
        recovery_codes: Optional[str] = None,
        **kwargs,
    ) -> Password:
        """Create a new encrypted password entry."""
        encrypted_username = self._crypto.encrypt(username)
        encrypted_password = self._crypto.encrypt(password)
        encrypted_notes = self._crypto.encrypt(notes) if notes else None
        encrypted_totp = self._crypto.encrypt(totp_secret) if totp_secret else None
        encrypted_recovery = (
            self._crypto.encrypt(recovery_codes) if recovery_codes else None
        )

        password_entry = Password(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            service_name=service_name,
            username=encrypted_username,
            password=encrypted_password,
            url=url,
            notes=encrypted_notes,
            totp_secret=encrypted_totp,
            recovery_codes=encrypted_recovery,
            password_changed_at=now_str(),
            password_history=[],
            **kwargs,
        )
        self._data.passwords.append(password_entry)
        await self._auto_save_if_enabled()
        return password_entry

    async def get_password(self, password_id: str) -> Optional[Password]:
        """Get password entry by ID."""
        for password_entry in self._data.passwords:
            if password_entry.id == password_id:
                return password_entry
        return None

    async def get_password_decrypted(self, password_id: str) -> Optional[Dict[str, Any]]:
        """Get password with decrypted fields."""
        password_entry = await self.get_password(password_id)
        if password_entry:
            decrypted_history = []
            for entry in password_entry.password_history:
                decrypted_history.append(
                    {
                        "password": self._crypto.decrypt_to_string(entry["password"]),
                        "changed_at": entry["changed_at"],
                    }
                )

            return {
                "id": password_entry.id,
                "service_name": password_entry.service_name,
                "username": self._crypto.decrypt_to_string(password_entry.username),
                "password": self._crypto.decrypt_to_string(password_entry.password),
                "url": password_entry.url,
                "notes": self._crypto.decrypt_to_string(password_entry.notes)
                if password_entry.notes
                else None,
                "totp_secret": self._crypto.decrypt_to_string(password_entry.totp_secret)
                if password_entry.totp_secret
                else None,
                "recovery_codes": self._crypto.decrypt_to_string(
                    password_entry.recovery_codes
                )
                if password_entry.recovery_codes
                else None,
                "has_2fa": password_entry.has_2fa,
                "category": password_entry.category,
                "is_favorite": password_entry.is_favorite,
                "last_used": password_entry.last_used,
                "password_changed_at": password_entry.password_changed_at,
                "password_history": decrypted_history,
                "history_count": password_entry.history_count,
                "created_at": password_entry.created_at,
            }
        return None

    async def get_passwords(self) -> List[Password]:
        """Get all password entries."""
        passwords = self._data.passwords.copy()
        passwords.sort(key=lambda item: (not item.is_favorite, item.service_name.lower()))
        return passwords

    async def get_passwords_decrypted(self) -> List[Dict[str, Any]]:
        """Get all passwords with decrypted fields."""
        passwords = await self.get_passwords()
        decrypted_passwords = []
        for password_entry in passwords:
            try:
                decrypted_passwords.append(
                    {
                        "id": password_entry.id,
                        "service_name": password_entry.service_name,
                        "username": self._crypto.decrypt_to_string(password_entry.username),
                        "password": self._crypto.decrypt_to_string(password_entry.password),
                        "url": password_entry.url,
                        "notes": self._crypto.decrypt_to_string(password_entry.notes)
                        if password_entry.notes
                        else None,
                        "totp_secret": self._crypto.decrypt_to_string(
                            password_entry.totp_secret
                        )
                        if password_entry.totp_secret
                        else None,
                        "has_2fa": password_entry.has_2fa,
                        "category": password_entry.category,
                        "is_favorite": password_entry.is_favorite,
                        "created_at": password_entry.created_at,
                        "updated_at": password_entry.updated_at,
                    }
                )
            except Exception:
                decrypted_passwords.append(
                    {
                        "id": password_entry.id,
                        "service_name": password_entry.service_name,
                        "username": "***",
                        "password": "***",
                        "url": password_entry.url,
                        "notes": None,
                        "has_2fa": password_entry.has_2fa,
                        "category": password_entry.category,
                        "is_favorite": password_entry.is_favorite,
                        "created_at": password_entry.created_at,
                        "updated_at": password_entry.updated_at,
                    }
                )
        return decrypted_passwords

    async def search_passwords(self, query: str) -> List[Password]:
        """Search passwords by service name."""
        query = query.lower()
        return [
            password_entry
            for password_entry in self._data.passwords
            if query in password_entry.service_name.lower()
        ]

    async def update_password(
        self,
        password_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        notes: Optional[str] = None,
        totp_secret: Optional[str] = None,
        recovery_codes: Optional[str] = None,
        save_to_history: bool = True,
        **kwargs,
    ) -> Optional[Password]:
        """Update a password entry with history tracking."""
        password_entry = await self.get_password(password_id)
        if password_entry:
            if username:
                password_entry.username = self._crypto.encrypt(username)
            if password:
                if save_to_history and password_entry.password:
                    history_entry = {
                        "password": password_entry.password,
                        "changed_at": password_entry.password_changed_at or now_str(),
                    }
                    if password_entry.password_history is None:
                        password_entry.password_history = []
                    password_entry.password_history.append(history_entry)
                    if len(password_entry.password_history) > 10:
                        password_entry.password_history = password_entry.password_history[-10:]

                password_entry.password = self._crypto.encrypt(password)
                password_entry.password_changed_at = now_str()

            if notes is not None:
                password_entry.notes = self._crypto.encrypt(notes) if notes else None
            if totp_secret is not None:
                password_entry.totp_secret = (
                    self._crypto.encrypt(totp_secret) if totp_secret else None
                )
            if recovery_codes is not None:
                password_entry.recovery_codes = (
                    self._crypto.encrypt(recovery_codes) if recovery_codes else None
                )

            for key, value in kwargs.items():
                if hasattr(password_entry, key) and key not in [
                    "username",
                    "password",
                    "notes",
                    "totp_secret",
                    "recovery_codes",
                ]:
                    setattr(password_entry, key, value)
            password_entry.updated_at = now_str()
            await self._auto_save_if_enabled()
        return password_entry

    async def get_password_history(self, password_id: str) -> List[Dict[str, str]]:
        """Get decrypted password history."""
        password_entry = await self.get_password(password_id)
        if password_entry and password_entry.password_history:
            history = []
            for entry in password_entry.password_history:
                history.append(
                    {
                        "password": self._crypto.decrypt_to_string(entry["password"]),
                        "changed_at": entry["changed_at"],
                    }
                )
            return history
        return []

    async def delete_password(self, password_id: str) -> bool:
        """Delete a password entry."""
        for index, password_entry in enumerate(self._data.passwords):
            if password_entry.id == password_id:
                self._data.passwords.pop(index)
                await self._auto_save_if_enabled()
                return True
        return False

    async def mark_password_used(self, password_id: str) -> Optional[Password]:
        """Mark password as used."""
        return await self.update_password(password_id, last_used=now_str())

    async def get_statistics(self) -> Dict[str, Any]:
        """Get user statistics."""
        todos = self._data.todos
        reminders = self._data.reminders

        return {
            "todos": {
                "total": len(todos),
                "completed": len([todo for todo in todos if todo.status == "completed"]),
                "pending": len([todo for todo in todos if todo.status == "pending"]),
                "in_progress": len(
                    [todo for todo in todos if todo.status == "in_progress"]
                ),
                "overdue": len([todo for todo in todos if todo.is_overdue]),
            },
            "reminders": {
                "total": len(reminders),
                "pending": len(
                    [reminder for reminder in reminders if reminder.status == "pending"]
                ),
                "active": len(
                    [reminder for reminder in reminders if reminder.status == "active"]
                ),
                "completed": len(
                    [reminder for reminder in reminders if reminder.status == "completed"]
                ),
            },
            "notes": len(self._data.notes),
            "passwords": len(self._data.passwords),
        }
