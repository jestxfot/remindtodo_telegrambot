"""
Calendar handlers and API for Web App
"""
import json
import hmac
import hashlib
from urllib.parse import parse_qs
from datetime import timedelta
from aiohttp import web
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, WebAppInfo
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BOT_TOKEN, WEBAPP_URL
from storage.json_storage import storage
from handlers.auth import get_crypto_for_user, is_authenticated
from utils.timezone import format_dt, now, parse_dt

router = Router()


def verify_telegram_web_app_data(init_data: str, bot_token: str) -> dict | None:
    """
    Verify Telegram Web App init data
    Returns user data if valid, None otherwise
    """
    try:
        parsed = parse_qs(init_data)
        
        # Extract hash
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
            bot_token.encode(),
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


async def get_user_storage(user_id: int):
    """Get storage for authenticated user"""
    if not is_authenticated(user_id):
        return None
    
    crypto = get_crypto_for_user(user_id)
    if not crypto:
        return None
    
    return await storage.get_user_storage(user_id, crypto)


async def handle_api_events(request: web.Request) -> web.Response:
    """API endpoint to get events for calendar"""
    try:
        # Get init data from header
        init_data = request.headers.get('X-Telegram-Init-Data', '')
        
        # Verify and get user
        user_data = verify_telegram_web_app_data(init_data, BOT_TOKEN)
        
        if not user_data:
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        user_id = user_data.get('id')
        if not user_id:
            return web.json_response({'error': 'Invalid user'}, status=400)
        
        # Get user storage
        user_storage = await get_user_storage(user_id)
        if not user_storage:
            return web.json_response({'error': 'Storage locked'}, status=403)
        
        # Get date range from query params
        start_date = request.query.get('start')
        end_date = request.query.get('end')
        
        # Default to current month
        current_time = now()
        if not start_date:
            start_date = format_dt(current_time - timedelta(days=30))
        if not end_date:
            end_date = format_dt(current_time + timedelta(days=60))
        
        # Get reminders
        reminders = await user_storage.get_reminders(include_completed=False)
        
        # Get todos
        todos = await user_storage.get_todos(include_completed=True)
        
        # Format events for calendar
        events = []
        
        for reminder in reminders:
            events.append({
                'id': reminder.id,
                'type': 'reminder',
                'title': reminder.title,
                'date': reminder.remind_at,
                'time': parse_dt(reminder.remind_at).strftime('%H:%M') if reminder.remind_at else None,
                'isRecurring': reminder.recurrence_type != 'none',
                'status': reminder.status
            })
        
        for todo in todos:
            if todo.deadline:
                events.append({
                    'id': todo.id,
                    'type': 'todo',
                    'title': todo.title,
                    'date': todo.deadline,
                    'priority': todo.priority,
                    'completed': todo.status == 'completed',
                    'isRecurring': todo.recurrence_type != 'none'
                })
        
        return web.json_response({
            'events': events,
            'timezone': user_storage.user.timezone
        })
        
    except Exception as e:
        print(f"API error: {e}")
        return web.json_response({'error': str(e)}, status=500)


def create_api_app() -> web.Application:
    """Create aiohttp application for API"""
    app = web.Application()
    
    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            response = await handler(request)
        
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Telegram-Init-Data'
        return response
    
    app.middlewares.append(cors_middleware)
    
    # Routes
    app.router.add_get('/api/events', handle_api_events)
    app.router.add_options('/api/events', lambda r: web.Response())
    
    return app


# Bot handlers
@router.message(Command("calendar"))
async def cmd_calendar(message: Message):
    """Show calendar Web App button"""
    webapp_url = WEBAPP_URL
    
    if not webapp_url:
        # Fallback to text calendar
        await show_text_calendar(message)
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📅 Открыть календарь",
            web_app=WebAppInfo(url=webapp_url)
        )
    )
    builder.row(
        InlineKeyboardButton(text="📆 Вид на неделю", callback_data="cal_week"),
        InlineKeyboardButton(text="📅 Вид на месяц", callback_data="cal_month")
    )
    
    await message.answer(
        "📅 <b>Календарь</b>\n\n"
        "Откройте интерактивный календарь для просмотра всех задач и напоминаний.\n\n"
        "<i>Или выберите текстовый вид ниже:</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


async def show_text_calendar(message: Message, view: str = 'week'):
    """Show text-based calendar when Web App is not available"""
    from utils.formatters import format_datetime
    
    user_storage = await get_user_storage(message.from_user.id)
    if not user_storage:
        await message.answer("🔒 Разблокируйте хранилище: /unlock")
        return
    
    current_time = now()
    timezone = user_storage.user.timezone
    
    # Get events
    reminders = await user_storage.get_reminders(include_completed=False)
    todos = await user_storage.get_todos(include_completed=True)
    
    text = ""
    
    if view == 'week':
        text = "📅 <b>Неделя</b>\n\n"
        
        # Show 7 days
        for i in range(7):
            day = current_time + timedelta(days=i)
            day_str = day.strftime('%d.%m')
            day_name = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][day.weekday()]
            
            day_events = []
            
            # Find reminders for this day
            for r in reminders:
                r_date = parse_dt(r.remind_at)
                if r_date and r_date.date() == day.date():
                    time_str = r_date.strftime('%H:%M')
                    day_events.append(f"🔔 {time_str} {r.title}")
            
            # Find todos for this day
            for t in todos:
                if t.deadline:
                    t_date = parse_dt(t.deadline)
                    if t_date and t_date.date() == day.date():
                        status = "✅" if t.status == 'completed' else "📋"
                        day_events.append(f"{status} {t.title}")
            
            is_today = day.date() == current_time.date()
            day_header = f"{'▶️ ' if is_today else ''}<b>{day_name} {day_str}</b>"
            
            if day_events:
                events_str = '\n    '.join(day_events)
                text += f"{day_header}\n    {events_str}\n\n"
            else:
                text += f"{day_header}\n    <i>—</i>\n\n"
    
    else:  # month view
        text = f"📆 <b>{current_time.strftime('%B %Y')}</b>\n\n"
        text += "<code>Пн Вт Ср Чт Пт Сб Вс</code>\n<code>"
        
        # Get first day of month
        first_day = current_time.replace(day=1)
        
        # Padding for first week
        weekday = first_day.weekday()
        text += "   " * weekday
        
        # Count events per day
        events_by_day = {}
        for r in reminders:
                r_date = parse_dt(r.remind_at)
                if r_date and r_date.month == current_time.month:
                    events_by_day[r_date.day] = events_by_day.get(r_date.day, 0) + 1
        for t in todos:
            if t.deadline:
                t_date = parse_dt(t.deadline)
                if t_date and t_date.month == current_time.month:
                    events_by_day[t_date.day] = events_by_day.get(t_date.day, 0) + 1
        
        # Days of month
        import calendar
        days_in_month = calendar.monthrange(current_time.year, current_time.month)[1]
        
        for day in range(1, days_in_month + 1):
            date = current_time.replace(day=day)
            
            if day in events_by_day:
                text += f"{day:2}•"
            elif day == current_time.day:
                text += f"[{day:2}]"
            else:
                text += f"{day:2} "
            
            if date.weekday() == 6:
                text += "\n"
        
        text += "</code>\n\n<i>• = есть события</i>"
    
    builder = InlineKeyboardBuilder()
    if view == 'week':
        builder.row(
            InlineKeyboardButton(text="📆 Месяц", callback_data="cal_month")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="📅 Неделя", callback_data="cal_week")
        )
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "cal_week")
async def cb_calendar_week(callback: CallbackQuery):
    """Show week view"""
    await callback.message.delete()
    await show_text_calendar(callback.message, 'week')
    await callback.answer()


@router.callback_query(F.data == "cal_month")
async def cb_calendar_month(callback: CallbackQuery):
    """Show month view"""
    await callback.message.delete()
    await show_text_calendar(callback.message, 'month')
    await callback.answer()
