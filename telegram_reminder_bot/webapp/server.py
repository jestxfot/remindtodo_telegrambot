#!/usr/bin/env python3
"""
HTTP server for Mini App with full API for user data.
"""
import http.server
import socketserver
import os
import sys
import json
import hmac
import hashlib
import asyncio
import traceback
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from datetime import datetime
import uuid

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.timezone import parse_dt, now, normalize_dt_str

PORT = int(os.getenv('WEBAPP_PORT', 3000))
DIRECTORY = os.path.join(os.path.dirname(__file__), 'dist')

# Import bot modules
# If import fails, we must NOT call missing symbols (otherwise NameError).
BOT_AVAILABLE = False
create_user_password = None
authenticate_user = None
logout_user = None
get_crypto_for_user = None
is_authenticated = None
user_has_password = None
get_session_info_dict = None
update_session_duration = None

try:
    from config import BOT_TOKEN
    from storage.sqlite_storage import storage
    from handlers.auth import (
        get_crypto_for_user, is_authenticated, 
        user_has_password, authenticate_user, logout_user,
        create_user_password, get_session_info_dict, update_session_duration
    )
    BOT_AVAILABLE = True
except Exception as e:
    print(f"[CRITICAL] Bot modules not available: {e}")
    print(traceback.format_exc())
    BOT_AVAILABLE = False
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')

def verify_telegram_web_app_data(init_data: str) -> dict | None:
    """Verify Telegram Web App init data and return user info"""
    if not init_data:
        return None
    try:
        parsed = parse_qs(init_data)
        
        received_hash = parsed.get('hash', [None])[0]
        if not received_hash:
            return None
        
        data_check_arr = []
        for key, value in sorted(parsed.items()):
            if key != 'hash':
                data_check_arr.append(f"{key}={value[0]}")
        data_check_string = '\n'.join(data_check_arr)
        
        secret_key = hmac.new(
            b'WebAppData',
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != received_hash:
            return None
        
        user_data = parsed.get('user', [None])[0]
        if user_data:
            return json.loads(user_data)
        
        return None
        
    except Exception as e:
        print(f"Error verifying web app data: {e}")
        return None


class APIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Telegram-Init-Data')
    
    def end_headers(self):
        self.send_cors_headers()
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def get_user_from_request(self):
        """Get verified user from request headers"""
        init_data = self.headers.get('X-Telegram-Init-Data', '')
        return verify_telegram_web_app_data(init_data)
    
    def get_request_body(self):
        """Get JSON body from request"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length:
                body = self.rfile.read(content_length)
                return json.loads(body.decode('utf-8'))
        except:
            pass
        return {}
    
    def send_json(self, data: dict, status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def ensure_bot_available(self) -> bool:
        """Ensure bot modules imported successfully"""
        if not BOT_AVAILABLE or not create_user_password or not authenticate_user:
            self.send_json({'success': False, 'message': 'Auth module unavailable on server'}, 500)
            return False
        return True
    
    def run_async(self, coro):
        """Run async coroutine"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API Routes
        if path == '/api/auth/status':
            return self.handle_auth_status()
        elif path == '/api/health':
            return self.handle_health()
        elif path == '/api/events':
            return self.handle_get_events()
        elif path == '/api/todos':
            return self.handle_get_todos()
        elif path == '/api/reminders':
            return self.handle_get_reminders()
        elif path == '/api/notes':
            return self.handle_get_notes()
        elif path == '/api/passwords':
            return self.handle_get_passwords()
        elif path == '/api/settings':
            return self.handle_get_settings()
        elif path == '/api/stats':
            return self.handle_get_stats()
        elif path == '/api/session':
            return self.handle_get_session()
        elif path == '/api/archive':
            return self.handle_get_archive()
        elif path.startswith('/api/attachments/'):
            return self.handle_get_attachment(path.split('/')[3])
        
        # SPA fallback
        file_path = os.path.join(DIRECTORY, path.lstrip('/'))
        if not os.path.exists(file_path) and not path.startswith('/assets'):
            self.path = '/index.html'
        
        return super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/api/auth/create':
            if not self.ensure_bot_available():
                return
            return self.handle_auth_create()
        elif path == '/api/auth/unlock':
            if not self.ensure_bot_available():
                return
            return self.handle_auth_unlock()
        elif path == '/api/auth/lock':
            return self.handle_auth_lock()
        elif path == '/api/session/duration':
            if not self.ensure_bot_available():
                return
            return self.handle_update_session_duration()
        elif path == '/api/settings':
            return self.handle_update_settings()
        elif path == '/api/todos':
            return self.handle_create_todo()
        elif path == '/api/reminders':
            return self.handle_create_reminder()
        elif path == '/api/notes':
            return self.handle_create_note()
        elif path == '/api/passwords':
            return self.handle_create_password()
        elif path.startswith('/api/todos/') and path.endswith('/complete'):
            return self.handle_complete_todo(path.split('/')[3])
        elif path.startswith('/api/reminders/') and path.endswith('/complete'):
            return self.handle_complete_reminder(path.split('/')[3])
        elif path == '/api/archive/restore':
            return self.handle_restore_from_archive()
        elif path == '/api/archive/delete':
            return self.handle_delete_from_archive()
        elif path == '/api/archive/clear':
            return self.handle_clear_archive()
        elif path.startswith('/api/notes/') and path.endswith('/attachments'):
            note_id = path.split('/')[3]
            return self.handle_upload_note_attachment(note_id)
        elif path.startswith('/api/reminders/') and path.endswith('/attachments'):
            reminder_id = path.split('/')[3]
            return self.handle_upload_reminder_attachment(reminder_id)
        elif path.startswith('/api/todos/') and path.endswith('/attachments'):
            todo_id = path.split('/')[3]
            return self.handle_upload_todo_attachment(todo_id)
        
        self.send_json({'error': 'Not found'}, 404)
    
    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path.startswith('/api/todos/'):
            return self.handle_update_todo(path.split('/')[3])
        elif path.startswith('/api/reminders/'):
            return self.handle_update_reminder(path.split('/')[3])
        elif path.startswith('/api/notes/'):
            return self.handle_update_note(path.split('/')[3])
        elif path.startswith('/api/passwords/'):
            return self.handle_update_password(path.split('/')[3])
        
        self.send_json({'error': 'Not found'}, 404)
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        parts = path.split('/')
        
        # Check for attachment deletion: /api/notes/<id>/attachments/<att_id>
        if len(parts) == 6 and parts[2] == 'notes' and parts[4] == 'attachments':
            return self.handle_delete_note_attachment(parts[3], parts[5])
        elif len(parts) == 6 and parts[2] == 'reminders' and parts[4] == 'attachments':
            return self.handle_delete_reminder_attachment(parts[3], parts[5])
        elif len(parts) == 6 and parts[2] == 'todos' and parts[4] == 'attachments':
            return self.handle_delete_todo_attachment(parts[3], parts[5])
        elif path.startswith('/api/todos/'):
            return self.handle_delete_todo(parts[3])
        elif path.startswith('/api/reminders/'):
            return self.handle_delete_reminder(parts[3])
        elif path.startswith('/api/notes/'):
            return self.handle_delete_note(parts[3])
        elif path.startswith('/api/passwords/'):
            return self.handle_delete_password(parts[3])
        
        self.send_json({'error': 'Not found'}, 404)
    
    # ============ AUTH ============
    
    def handle_auth_status(self):
        user = self.get_user_from_request()
        if not user:
            return self.send_json({
                'authenticated': False,
                'has_password': False,
                'auth_available': BOT_AVAILABLE
            })
        
        user_id = user.get('id')
        has_pwd = user_has_password(user_id) if BOT_AVAILABLE else False
        authenticated = is_authenticated(user_id) if BOT_AVAILABLE else False
        
        return self.send_json({
            'authenticated': authenticated,
            'has_password': has_pwd,
            'auth_available': BOT_AVAILABLE
        })

    def handle_health(self):
        return self.send_json({
            'ok': True,
            'auth_available': BOT_AVAILABLE,
            'port': PORT,
            'static_dir_exists': os.path.exists(DIRECTORY),
        })
    
    def handle_auth_create(self):
        user = self.get_user_from_request()
        if not user:
            return self.send_json({'success': False, 'message': 'Unauthorized'}, 401)
        
        body = self.get_request_body()
        password = body.get('password', '')
        duration = body.get('duration', '1day')
        
        if len(password) < 4:
            return self.send_json({'success': False, 'message': 'Пароль слишком короткий'})
        
        try:
            success = self.run_async(create_user_password(user['id'], password, duration))
            if success:
                return self.send_json({'success': True})
            else:
                return self.send_json({'success': False, 'message': 'Ошибка создания'})
        except Exception as e:
            return self.send_json({'success': False, 'message': str(e)})
    
    def handle_auth_unlock(self):
        user = self.get_user_from_request()
        if not user:
            return self.send_json({'success': False, 'message': 'Unauthorized'}, 401)
        
        body = self.get_request_body()
        password = body.get('password', '')
        duration = body.get('duration', '30min')
        
        try:
            success = self.run_async(authenticate_user(user['id'], password, duration))
            if success:
                return self.send_json({'success': True})
            else:
                return self.send_json({'success': False, 'message': 'Неверный пароль'})
        except Exception as e:
            return self.send_json({'success': False, 'message': str(e)})
    
    def handle_auth_lock(self):
        user = self.get_user_from_request()
        if not user:
            return self.send_json({'success': False}, 401)
        
        logout_user(user['id'])
        return self.send_json({'success': True})
    
    # ============ HELPERS ============
    
    def get_user_storage(self, user):
        """Get authenticated user storage"""
        if not user or not BOT_AVAILABLE:
            return None
        
        user_id = user.get('id')
        if not is_authenticated(user_id):
            print(f"[WARN] User {user_id} not authenticated")
            return None
        
        crypto = get_crypto_for_user(user_id)
        if not crypto:
            print(f"[WARN] No crypto for user {user_id}")
            return None
        
        try:
            return self.run_async(storage.get_user_storage(user_id, crypto))
        except ValueError as e:
            # Critical error - decryption failed, don't allow writing
            print(f"[CRITICAL] Storage load failed for user {user_id}: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] Unexpected error loading storage for user {user_id}: {e}")
            return None
    
    def require_auth(self):
        """Check auth and return user_storage or send error"""
        if not self.ensure_bot_available():
            return None, None
        
        user = self.get_user_from_request()
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return None, None
        
        user_id = user.get('id')
        
        # Check if user is authenticated
        if not is_authenticated(user_id):
            self.send_json({
                'error': 'Storage locked', 
                'message': 'Сессия истекла. Разблокируйте хранилище через бота (/unlock)'
            }, 403)
            return None, None
        
        user_storage = self.get_user_storage(user)
        if not user_storage:
            self.send_json({
                'error': 'Storage error', 
                'message': 'Ошибка загрузки данных. Попробуйте перезайти через бота (/lock, затем /unlock)'
            }, 500)
            return None, None

        if not user_storage.user.is_active:
            self.run_async(user_storage.update_user(
                is_active=True,
                bot_blocked_at=None,
                bot_block_reason=None
            ))
        
        return user, user_storage
    
    # ============ TODOS ============
    
    def handle_get_todos(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        todos = self.run_async(user_storage.get_todos(include_completed=True))
        return self.send_json({
            'todos': [t.to_dict() for t in todos]
        })
    
    def handle_create_todo(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        deadline = normalize_dt_str(body.get('deadline'))
        todo = self.run_async(user_storage.create_todo(
            title=body.get('title', 'Задача'),
            description=body.get('description'),
            priority=body.get('priority', 'medium'),
            deadline=deadline,
            recurrence_type=body.get('recurrence_type', 'none'),
            progress=body.get('progress', 0),
            status=body.get('status', 'pending'),
            tags=body.get('tags', []),
            links=body.get('links', []),
            subtasks=body.get('subtasks', [])
        ))
        return self.send_json({'success': True, 'todo': todo.to_dict()})
    
    def handle_update_todo(self, todo_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        if 'deadline' in body:
            body['deadline'] = normalize_dt_str(body.get('deadline'))
        if 'recurrence_end_date' in body:
            body['recurrence_end_date'] = normalize_dt_str(body.get('recurrence_end_date'))
        if 'completed_at' in body:
            body['completed_at'] = normalize_dt_str(body.get('completed_at'))
        todo = self.run_async(user_storage.update_todo(todo_id, **body))
        if todo:
            return self.send_json({'success': True, 'todo': todo.to_dict()})
        return self.send_json({'success': False, 'message': 'Not found'}, 404)
    
    def handle_delete_todo(self, todo_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        success = self.run_async(user_storage.delete_todo(todo_id))
        return self.send_json({'success': success})
    
    def handle_complete_todo(self, todo_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        todo, _was_archived = self.run_async(user_storage.complete_todo(todo_id))
        if todo:
            return self.send_json({'success': True})
        return self.send_json({'success': False}, 404)
    
    # ============ REMINDERS ============
    
    def handle_get_reminders(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        reminders = self.run_async(user_storage.get_reminders(include_completed=False))
        return self.send_json({
            'reminders': [r.to_dict() for r in reminders]
        })
    
    def handle_create_reminder(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        remind_at = normalize_dt_str(body.get('remind_at'))
        recurrence_end_date = normalize_dt_str(body.get('recurrence_end_date'))
        interval_seconds = int(getattr(user_storage.user, 'reminder_interval_minutes', 5)) * 60
        reminder = self.run_async(user_storage.create_reminder(
            title=body.get('title', 'Напоминание'),
            description=body.get('description'),
            remind_at=remind_at,
            is_persistent=body.get('is_persistent', True),
            persistent_interval=body.get('persistent_interval', interval_seconds),
            recurrence_type=body.get('recurrence_type', 'none'),
            recurrence_interval=body.get('recurrence_interval'),
            recurrence_end_date=recurrence_end_date,
            tags=body.get('tags', []),
            links=body.get('links', [])
        ))
        return self.send_json({'success': True, 'reminder': reminder.to_dict()})
    
    def handle_update_reminder(self, reminder_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        if 'remind_at' in body:
            body['remind_at'] = normalize_dt_str(body.get('remind_at'))
        if 'recurrence_end_date' in body:
            body['recurrence_end_date'] = normalize_dt_str(body.get('recurrence_end_date'))
        if 'snoozed_until' in body:
            body['snoozed_until'] = normalize_dt_str(body.get('snoozed_until'))
        if 'last_notification_at' in body:
            body['last_notification_at'] = normalize_dt_str(body.get('last_notification_at'))
        reminder = self.run_async(user_storage.update_reminder(reminder_id, **body))
        if reminder:
            return self.send_json({'success': True, 'reminder': reminder.to_dict()})
        return self.send_json({'success': False, 'message': 'Not found'}, 404)
    
    def handle_delete_reminder(self, reminder_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        success = self.run_async(user_storage.delete_reminder(reminder_id))
        return self.send_json({'success': success})
    
    def handle_complete_reminder(self, reminder_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        reminder, _was_archived = self.run_async(user_storage.complete_reminder(reminder_id))
        if reminder:
            return self.send_json({'success': True})
        return self.send_json({'success': False}, 404)
    
    # ============ NOTES ============
    
    def handle_get_notes(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        # Get decrypted notes
        notes = self.run_async(user_storage.get_notes_decrypted())
        return self.send_json({
            'notes': notes
        })
    
    def handle_create_note(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        note = self.run_async(user_storage.create_note(
            title=body.get('title', 'Заметка'),
            content=body.get('content', ''),
            is_pinned=body.get('is_pinned', False),
            tags=body.get('tags', []),
            links=body.get('links', []),
            status=body.get('status', 'active')
        ))
        return self.send_json({'success': True, 'note': note.to_dict()})
    
    def handle_update_note(self, note_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        note = self.run_async(user_storage.update_note(note_id, **body))
        if note:
            return self.send_json({'success': True, 'note': note.to_dict()})
        return self.send_json({'success': False, 'message': 'Not found'}, 404)
    
    def handle_delete_note(self, note_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        success = self.run_async(user_storage.delete_note(note_id))
        return self.send_json({'success': success})
    
    # ============ PASSWORDS ============
    
    def handle_get_passwords(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        # Get decrypted passwords
        passwords = self.run_async(user_storage.get_passwords_decrypted())
        return self.send_json({
            'passwords': passwords
        })
    
    def handle_create_password(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        password = self.run_async(user_storage.create_password(
            service_name=body.get('service_name', 'Сервис'),
            username=body.get('username', ''),
            password=body.get('password', ''),
            url=body.get('url'),
            notes=body.get('notes')
        ))
        return self.send_json({'success': True, 'password': password.to_dict()})
    
    def handle_update_password(self, password_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        password = self.run_async(user_storage.update_password(password_id, **body))
        if password:
            return self.send_json({'success': True, 'password': password.to_dict()})
        return self.send_json({'success': False, 'message': 'Not found'}, 404)
    
    def handle_delete_password(self, password_id):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        success = self.run_async(user_storage.delete_password(password_id))
        return self.send_json({'success': success})
    
    # ============ EVENTS / SETTINGS / STATS ============
    
    def handle_get_events(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        events = []
        
        # Get reminders
        reminders = self.run_async(user_storage.get_reminders(include_completed=False))
        for r in reminders:
            try:
                remind_dt = parse_dt(r.remind_at) if r.remind_at else None
                events.append({
                    'id': r.id,
                    'type': 'reminder',
                    'title': r.title,
                    'date': r.remind_at,
                    'time': remind_dt.strftime('%H:%M') if remind_dt else None,
                    'isRecurring': r.recurrence_type and r.recurrence_type != 'none',
                    'status': r.status
                })
            except Exception as e:
                print(f"Error processing reminder: {e}")
        
        # Get todos with deadlines
        todos = self.run_async(user_storage.get_todos(include_completed=True))
        for t in todos:
            try:
                if t.deadline:
                    deadline_dt = parse_dt(t.deadline)
                    events.append({
                        'id': t.id,
                        'type': 'todo',
                        'title': t.title,
                        'date': t.deadline,
                        'time': deadline_dt.strftime('%H:%M'),
                        'priority': t.priority,
                        'completed': t.status == 'completed',
                        'isRecurring': t.recurrence_type and t.recurrence_type != 'none'
                    })
            except Exception as e:
                print(f"Error processing todo: {e}")
        
        return self.send_json({'events': events})
    
    def handle_get_settings(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        return self.send_json({
            'timezone': user_storage.user.timezone,
            'backup_enabled': user_storage.user.backup_enabled,
            'reminder_interval_minutes': getattr(user_storage.user, 'reminder_interval_minutes', 5),
            'is_active': user_storage.user.is_active,
            'bot_blocked_at': getattr(user_storage.user, 'bot_blocked_at', None),
            'bot_block_reason': getattr(user_storage.user, 'bot_block_reason', None),
        })

    def handle_update_settings(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return

        body = self.get_request_body()
        update_fields = {}

        if 'reminder_interval_minutes' in body:
            try:
                interval_minutes = int(body.get('reminder_interval_minutes'))
            except (TypeError, ValueError):
                return self.send_json({'error': 'Invalid reminder interval'}, 400)

            if interval_minutes < 1:
                return self.send_json({'error': 'Reminder interval must be at least 1 minute'}, 400)

            update_fields['reminder_interval_minutes'] = interval_minutes
            self.run_async(user_storage.update_persistent_reminder_interval(interval_minutes * 60))

        if 'backup_enabled' in body:
            update_fields['backup_enabled'] = bool(body.get('backup_enabled'))

        if not update_fields:
            return self.send_json({'error': 'No supported settings provided'}, 400)

        self.run_async(user_storage.update_user(**update_fields))
        return self.handle_get_settings()
    
    def handle_get_session(self):
        """Get session info"""
        user = self.get_user_from_request()
        if not user:
            return self.send_json({'error': 'Unauthorized'}, 401)
        
        user_id = user.get('id')
        if not user_id:
            return self.send_json({'error': 'No user id'}, 400)
        
        session_info = get_session_info_dict(user_id)
        return self.send_json(session_info)
    
    def handle_update_session_duration(self):
        """Update session duration"""
        user = self.get_user_from_request()
        if not user:
            return self.send_json({'error': 'Unauthorized'}, 401)
        
        user_id = user.get('id')
        if not user_id:
            return self.send_json({'error': 'No user id'}, 400)
        
        body = self.get_request_body()
        duration_key = body.get('duration')
        
        if not duration_key:
            return self.send_json({'error': 'Missing duration'}, 400)
        
        success = update_session_duration(user_id, duration_key)
        
        if success:
            session_info = get_session_info_dict(user_id)
            return self.send_json({'success': True, 'session': session_info})
        else:
            return self.send_json({'error': 'Failed to update session'}, 400)
    
    def handle_get_stats(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        stats = self.run_async(user_storage.get_statistics())
        return self.send_json(stats)
    
    # ============ ARCHIVE ============
    
    def handle_get_archive(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        archive = self.run_async(user_storage.get_archive())
        return self.send_json({
            'archive': [a.to_dict() for a in archive]
        })
    
    def handle_restore_from_archive(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        archived_at = body.get('archived_at')
        
        if not archived_at:
            return self.send_json({'error': 'Missing archived_at'}, 400)
        
        success = self.run_async(user_storage.restore_from_archive(archived_at))
        return self.send_json({'success': success})
    
    def handle_delete_from_archive(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        archived_at = body.get('archived_at')
        
        if not archived_at:
            return self.send_json({'error': 'Missing archived_at'}, 400)
        
        success = self.run_async(user_storage.delete_from_archive(archived_at))
        return self.send_json({'success': success})
    
    def handle_clear_archive(self):
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        body = self.get_request_body()
        item_type = body.get('item_type')  # None = clear all
        
        deleted = self.run_async(user_storage.clear_archive(item_type))
        return self.send_json({'success': True, 'deleted': deleted})
    
    # ============ ATTACHMENTS ============
    
    def handle_get_attachment(self, attachment_id):
        """Get attachment file data"""
        # For media files, auth comes from query param since headers don't work
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        
        # Try header first, then query param
        init_data = self.headers.get('X-Telegram-Init-Data', '')
        if not init_data and 'init_data' in query:
            init_data = query['init_data'][0]
        
        user = verify_telegram_web_app_data(init_data)
        if not user:
            return self.send_json({'error': 'Unauthorized'}, 401)
        
        user_id = user.get('id')
        crypto = get_crypto_for_user(user_id)
        if not crypto:
            return self.send_json({'error': 'Not authenticated'}, 401)
        
        user_storage = self.run_async(storage.get_user_storage(user_id, crypto))
        if not user_storage:
            return self.send_json({'error': 'Storage not available'}, 500)
        
        # Find attachment in notes or reminders
        file_path = None
        file_type = 'application/octet-stream'
        filename = 'file'
        
        # Search in notes
        notes = self.run_async(user_storage.get_notes())
        for note in notes:
            for att in note.attachments:
                if att.get('id') == attachment_id:
                    file_path = att.get('file_path')
                    file_type = att.get('file_type', 'application/octet-stream')
                    filename = att.get('filename', 'file')
                    break
        
        # Search in reminders if not found
        if not file_path:
            reminders = self.run_async(user_storage.get_reminders(include_completed=True))
            for reminder in reminders:
                for att in reminder.attachments:
                    if att.get('id') == attachment_id:
                        file_path = att.get('file_path')
                        file_type = att.get('file_type', 'application/octet-stream')
                        filename = att.get('filename', 'file')
                        break
        
        if not file_path:
            return self.send_json({'error': 'Attachment not found'}, 404)
        
        # Get decrypted data
        data = self.run_async(user_storage.get_attachment_data(file_path))
        if not data:
            return self.send_json({'error': 'Could not read attachment'}, 500)
        
        # Send file
        self.send_response(200)
        self.send_header('Content-Type', file_type)
        self.send_header('Content-Length', len(data))
        self.send_header('Content-Disposition', f'inline; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)
    
    def handle_upload_note_attachment(self, note_id):
        """Upload attachment to note"""
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        # Parse multipart form data
        file_data, filename, file_type = self.parse_multipart_file()
        if not file_data:
            return self.send_json({'error': 'No file provided'}, 400)
        
        try:
            attachment = self.run_async(user_storage.save_attachment(file_data, filename, file_type))
            success = self.run_async(user_storage.add_attachment_to_note(note_id, attachment))
            
            if success:
                return self.send_json({'success': True, 'attachment': attachment.to_dict()})
            else:
                return self.send_json({'error': 'Note not found'}, 404)
        except ValueError as e:
            return self.send_json({'error': str(e)}, 400)
    
    def handle_upload_reminder_attachment(self, reminder_id):
        """Upload attachment to reminder"""
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        file_data, filename, file_type = self.parse_multipart_file()
        if not file_data:
            return self.send_json({'error': 'No file provided'}, 400)
        
        try:
            attachment = self.run_async(user_storage.save_attachment(file_data, filename, file_type))
            success = self.run_async(user_storage.add_attachment_to_reminder(reminder_id, attachment))
            
            if success:
                return self.send_json({'success': True, 'attachment': attachment.to_dict()})
            else:
                return self.send_json({'error': 'Reminder not found'}, 404)
        except ValueError as e:
            return self.send_json({'error': str(e)}, 400)
    
    def handle_delete_note_attachment(self, note_id, attachment_id):
        """Delete attachment from note"""
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        success = self.run_async(user_storage.remove_attachment_from_note(note_id, attachment_id))
        return self.send_json({'success': success})
    
    def handle_delete_reminder_attachment(self, reminder_id, attachment_id):
        """Delete attachment from reminder"""
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        success = self.run_async(user_storage.remove_attachment_from_reminder(reminder_id, attachment_id))
        return self.send_json({'success': success})
    
    def handle_upload_todo_attachment(self, todo_id):
        """Upload attachment to todo"""
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        try:
            body = self.get_request_body()
            filename = body.get('filename', 'file')
            file_data = body.get('data', '')  # Base64 encoded
            file_type = body.get('file_type', 'application/octet-stream')
            
            attachment = self.run_async(user_storage.add_attachment_to_todo(
                todo_id, filename, file_data, file_type
            ))
            
            if attachment:
                return self.send_json({'success': True, 'attachment': attachment})
            return self.send_json({'error': 'Failed to save attachment'}, 400)
        except Exception as e:
            return self.send_json({'error': str(e)}, 400)
    
    def handle_delete_todo_attachment(self, todo_id, attachment_id):
        """Delete attachment from todo"""
        user, user_storage = self.require_auth()
        if not user_storage:
            return
        
        success = self.run_async(user_storage.remove_attachment_from_todo(todo_id, attachment_id))
        return self.send_json({'success': success})
    
    def parse_multipart_file(self):
        """Parse multipart/form-data and extract file"""
        content_type = self.headers.get('Content-Type', '')
        
        if 'multipart/form-data' not in content_type:
            # Try JSON with base64
            body = self.get_request_body()
            if body and 'file_data' in body:
                import base64
                file_data = base64.b64decode(body['file_data'])
                filename = body.get('filename', 'file')
                file_type = body.get('file_type', 'application/octet-stream')
                return file_data, filename, file_type
            return None, None, None
        
        # Parse multipart
        try:
            import cgi
            from io import BytesIO
            
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Parse boundary
            boundary = content_type.split('boundary=')[1].encode()
            parts = body.split(b'--' + boundary)
            
            for part in parts:
                if b'filename=' in part:
                    # Extract filename
                    header_end = part.find(b'\r\n\r\n')
                    header = part[:header_end].decode()
                    data = part[header_end + 4:]
                    
                    # Remove trailing boundary markers
                    if data.endswith(b'--\r\n'):
                        data = data[:-4]
                    elif data.endswith(b'\r\n'):
                        data = data[:-2]
                    
                    # Get filename
                    import re
                    filename_match = re.search(r'filename="([^"]+)"', header)
                    filename = filename_match.group(1) if filename_match else 'file'
                    
                    # Get content type
                    ct_match = re.search(r'Content-Type:\s*([^\r\n]+)', header)
                    file_type = ct_match.group(1).strip() if ct_match else 'application/octet-stream'
                    
                    return data, filename, file_type
        except Exception as e:
            print(f"Error parsing multipart: {e}")
        
        return None, None, None
    
    def log_message(self, format, *args):
        print(f"[{now().strftime('%H:%M:%S')}] {self.address_string()} - {format % args}")


class ReusableTCPServer(socketserver.TCPServer):
    # Allow immediate rebinding to the same port after restart
    allow_reuse_address = True


if __name__ == '__main__':
    if not os.path.exists(DIRECTORY):
        print(f"Warning: Build directory '{DIRECTORY}' not found!")
        print("Run 'npm run build' first, or use dev server.")
    
    print(f"🚀 Mini App API Server")
    print(f"📁 Static files: {DIRECTORY}")
    print(f"🔌 Port: {PORT}")
    print(f"🤖 Bot integration: {'✅ Available' if BOT_AVAILABLE else '❌ Not available'}")
    print(f"")
    print(f"Server running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    
    with ReusableTCPServer(("", PORT), APIHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")
