#!/usr/bin/env python3
"""
HTTP server for Calendar Web App with API for user data.
"""
import http.server
import socketserver
import os
import sys
import json
import hmac
import hashlib
from urllib.parse import parse_qs, urlparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

PORT = int(os.getenv('WEBAPP_PORT', 3000))
DIRECTORY = os.path.join(os.path.dirname(__file__), 'dist')

# Import bot modules
try:
    from config import BOT_TOKEN
    from storage.json_storage import storage
    from handlers.auth import get_crypto_for_user, is_authenticated
    BOT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Bot modules not available: {e}")
    BOT_AVAILABLE = False
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')


def verify_telegram_web_app_data(init_data: str) -> dict | None:
    """Verify Telegram Web App init data and return user info"""
    try:
        parsed = parse_qs(init_data)
        
        received_hash = parsed.get('hash', [None])[0]
        if not received_hash:
            return None
        
        # Build data check string
        data_check_arr = []
        for key, value in sorted(parsed.items()):
            if key != 'hash':
                data_check_arr.append(f"{key}={value[0]}")
        data_check_string = '\n'.join(data_check_arr)
        
        # Calculate hash
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
        
        # Parse user data
        user_data = parsed.get('user', [None])[0]
        if user_data:
            return json.loads(user_data)
        
        return None
        
    except Exception as e:
        print(f"Error verifying web app data: {e}")
        return None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Telegram-Init-Data')
    
    def end_headers(self):
        self.send_cors_headers()
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # API endpoint for events
        if parsed_path.path == '/api/events':
            self.handle_api_events()
            return
        
        # SPA fallback - serve index.html for routes
        file_path = os.path.join(DIRECTORY, parsed_path.path.lstrip('/'))
        if not os.path.exists(file_path) and not parsed_path.path.startswith('/assets'):
            self.path = '/index.html'
        
        return super().do_GET()
    
    def handle_api_events(self):
        """Handle API request for calendar events"""
        import asyncio
        
        # Get init data from header
        init_data = self.headers.get('X-Telegram-Init-Data', '')
        
        # Verify user
        user_data = verify_telegram_web_app_data(init_data)
        
        if not user_data and BOT_AVAILABLE:
            self.send_json_response({'error': 'Unauthorized', 'events': []}, 401)
            return
        
        if not BOT_AVAILABLE:
            self.send_json_response({'error': 'Bot not available', 'events': []}, 503)
            return
        
        user_id = user_data.get('id')
        
        # Check if user is authenticated
        if not is_authenticated(user_id):
            self.send_json_response({
                'error': 'Storage locked',
                'events': [],
                'message': 'Разблокируйте хранилище командой /unlock'
            }, 403)
            return
        
        # Get user storage
        crypto = get_crypto_for_user(user_id)
        if not crypto:
            self.send_json_response({'error': 'No crypto', 'events': []}, 403)
            return
        
        try:
            # Run async code
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            events = loop.run_until_complete(self.get_user_events(user_id, crypto))
            loop.close()
            
            self.send_json_response({'events': events})
            
        except Exception as e:
            print(f"Error getting events: {e}")
            self.send_json_response({'error': str(e), 'events': []}, 500)
    
    async def get_user_events(self, user_id: int, crypto):
        """Get events for user"""
        from datetime import datetime
        
        user_storage = await storage.get_user_storage(user_id, crypto)
        
        events = []
        
        # Get reminders
        reminders = await user_storage.get_reminders(include_completed=False)
        for r in reminders:
            try:
                remind_dt = datetime.fromisoformat(r.remind_at) if r.remind_at else None
                events.append({
                    'id': r.id,
                    'type': 'reminder',
                    'title': r.title,
                    'date': r.remind_at,
                    'time': remind_dt.strftime('%H:%M') if remind_dt else None,
                    'isRecurring': r.recurrence and r.recurrence != 'none',
                    'status': r.status
                })
            except Exception as e:
                print(f"Error processing reminder {r.id}: {e}")
        
        # Get todos
        todos = await user_storage.get_todos(include_completed=True)
        for t in todos:
            try:
                if t.deadline:
                    deadline_dt = datetime.fromisoformat(t.deadline)
                    events.append({
                        'id': t.id,
                        'type': 'todo',
                        'title': t.title,
                        'date': t.deadline,
                        'time': deadline_dt.strftime('%H:%M') if deadline_dt else None,
                        'priority': t.priority,
                        'completed': t.status == 'completed',
                        'isRecurring': t.recurrence and t.recurrence != 'none'
                    })
            except Exception as e:
                print(f"Error processing todo {t.id}: {e}")
        
        return events
    
    def send_json_response(self, data: dict, status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Log with timestamp"""
        print(f"{self.address_string()} - {format % args}")


if __name__ == '__main__':
    if not os.path.exists(DIRECTORY):
        print(f"Error: Build directory '{DIRECTORY}' not found!")
        print("Run 'npm run build' first.")
        sys.exit(1)
    
    print(f"🌐 Calendar Web App Server")
    print(f"📁 Static files: {DIRECTORY}")
    print(f"🔌 Port: {PORT}")
    print(f"🤖 Bot integration: {'✅ Available' if BOT_AVAILABLE else '❌ Not available'}")
    print(f"")
    print(f"Server running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")
