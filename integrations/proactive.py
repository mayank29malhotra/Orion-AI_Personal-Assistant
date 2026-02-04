"""
Proactive Notifications for Orion AI Assistant
Sends automatic updates to Telegram:
- Morning calendar digest
- Email notifications
- Upcoming event reminders

All times are in IST (Indian Standard Time)
"""
import os
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import imaplib
from email.header import decode_header
from email import policy
from email.parser import BytesParser

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config
from core.utils import Logger

logger = Logger().logger

# IST Timezone
IST = timezone(timedelta(hours=5, minutes=30))

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").split(",")[0].strip()

# Email config
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")

# Notification settings
MORNING_DIGEST_HOUR = int(os.getenv("MORNING_DIGEST_HOUR", "7"))  # 7 AM IST
EMAIL_CHECK_INTERVAL = int(os.getenv("EMAIL_NOTIFY_INTERVAL", "300"))  # 5 minutes

# Multi-level reminder times (in minutes before event)
REMINDER_TIMES = [30, 15, 5]  # 30 min, 15 min, 5 min before

# Track last notification times
last_email_check = datetime.min.replace(tzinfo=IST)
last_digest_date = None
# Track which events and reminder levels we've sent (event_id:minutes)
notified_events = {}  # {event_id: [30, 15, 5] - list of reminder times already sent}


async def send_telegram_message(message: str) -> bool:
    """Send a message to Telegram user"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_USER_ID:
        logger.warning("Telegram not configured for proactive notifications")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json={
                "chat_id": TELEGRAM_USER_ID,
                "text": message,
                "parse_mode": "HTML"
            })
            if response.status_code == 200:
                logger.info(f"Proactive notification sent to Telegram")
                return True
            else:
                logger.error(f"Failed to send Telegram message: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


def _get_proactive_calendar_service():
    """
    Get a standalone Google Calendar service for proactive notifications.
    Separate from LangChain tools to avoid deadlock issues.
    """
    try:
        import json
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = None
        
        token_path = 'google_cred/token.json'
        token_json_env = os.getenv("GOOGLE_CALENDAR_TOKEN_JSON")
        
        if token_json_env:
            token_data = json.loads(token_json_env)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        elif os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return None, "Calendar not configured"
        
        return build('calendar', 'v3', credentials=creds), None
    except Exception as e:
        return None, str(e)


def get_calendar_events_for_today() -> List[dict]:
    """Get today's calendar events"""
    try:
        service, error = _get_proactive_calendar_service()
        if error:
            logger.error(f"Calendar error: {error}")
            return []
        
        now = datetime.now(IST)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        return []


def get_upcoming_events(minutes_ahead: int = 35) -> List[dict]:
    """Get events starting in the next X minutes (default 35 to catch 30-min reminders)"""
    try:
        service, error = _get_proactive_calendar_service()
        if error:
            return []
        
        now = datetime.now(IST)
        soon = now + timedelta(minutes=minutes_ahead)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat(),
            timeMax=soon.isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    except Exception as e:
        logger.error(f"Error fetching upcoming events: {e}")
        return []


async def send_morning_digest():
    """Send morning calendar digest at 7 AM IST"""
    global last_digest_date
    
    now = datetime.now(IST)
    today = now.date()
    
    # Only send once per day
    if last_digest_date == today:
        return
    
    # Only send between 7:00 AM and 7:10 AM IST
    if now.hour != MORNING_DIGEST_HOUR or now.minute > 10:
        return
    
    events = get_calendar_events_for_today()
    
    # Build digest message
    message = f"🌅 <b>Good Morning!</b>\n"
    message += f"📅 <b>{now.strftime('%A, %B %d, %Y')}</b>\n\n"
    
    if events:
        message += "📋 <b>Today's Schedule:</b>\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', 'Untitled')
            
            # Parse start time
            if 'T' in start:
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    start_dt = start_dt.astimezone(IST)
                    time_str = start_dt.strftime('%I:%M %p')
                except:
                    time_str = start
            else:
                time_str = "All day"
            
            location = event.get('location', '')
            location_str = f" 📍 {location}" if location else ""
            
            message += f"• <b>{time_str}</b> - {title}{location_str}\n"
    else:
        message += "✨ No events scheduled for today. Enjoy your day!"
    
    message += "\n\n💡 <i>Reply with any task to get started!</i>"
    
    await send_telegram_message(message)
    last_digest_date = today
    logger.info("Morning digest sent")


def get_unread_emails() -> List[dict]:
    """Get unread emails from inbox"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return []
    
    emails = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("INBOX")
        
        # Search for unread emails
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != "OK":
            return emails
        
        for msg_id in messages[0].split()[:10]:  # Limit to 10 emails
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = msg_data[0][1]
                msg = BytesParser(policy=policy.compat32).parsebytes(raw_email)
                
                # Decode subject
                subject_raw = msg.get("Subject", "")
                decoded_parts = decode_header(subject_raw)
                subject = ""
                for part, encoding in decoded_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(encoding or 'utf-8', errors='ignore')
                    else:
                        subject += part
                
                # Get sender
                from_header = msg.get("From", "")
                if "<" in from_header:
                    sender = from_header.split("<")[1].split(">")[0]
                    sender_name = from_header.split("<")[0].strip().strip('"')
                else:
                    sender = from_header
                    sender_name = from_header
                
                emails.append({
                    'id': msg_id.decode(),
                    'subject': subject,
                    'sender': sender,
                    'sender_name': sender_name
                })
            except Exception as e:
                logger.debug(f"Error parsing email: {e}")
                continue
        
        # Don't logout to keep emails marked unread for email_bot to process
        mail.logout()
        
    except Exception as e:
        logger.error(f"Error checking emails: {e}")
    
    return emails


async def check_new_emails():
    """Check for new emails and notify via Telegram"""
    global last_email_check
    
    now = datetime.now(IST)
    
    # Rate limit email checks
    if (now - last_email_check).total_seconds() < EMAIL_CHECK_INTERVAL:
        return
    
    last_email_check = now
    
    emails = get_unread_emails()
    
    if not emails:
        return
    
    # Build notification
    if len(emails) == 1:
        email = emails[0]
        message = f"📧 <b>New Email</b>\n\n"
        message += f"<b>From:</b> {email['sender_name']}\n"
        message += f"<b>Subject:</b> {email['subject']}\n\n"
        message += f"💡 <i>Reply 'read emails' to see full content</i>"
    else:
        message = f"📧 <b>{len(emails)} New Emails</b>\n\n"
        for email in emails[:5]:
            message += f"• <b>{email['sender_name']}</b>: {email['subject'][:40]}...\n"
        if len(emails) > 5:
            message += f"\n... and {len(emails) - 5} more\n"
        message += f"\n💡 <i>Reply 'read emails' to see details</i>"
    
    await send_telegram_message(message)
    logger.info(f"Email notification sent: {len(emails)} new emails")


async def check_upcoming_events():
    """Send multi-level reminders for events (30 min, 15 min, 5 min before)"""
    global notified_events
    
    # Get events in the next 35 minutes (to catch 30-min reminders)
    events = get_upcoming_events(35)
    
    for event in events:
        event_id = event.get('id')
        title = event.get('summary', 'Untitled Event')
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        # Skip all-day events
        if 'T' not in start:
            continue
        
        # Parse start time
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            start_dt = start_dt.astimezone(IST)
            time_str = start_dt.strftime('%I:%M %p')
            
            # Calculate minutes until event
            now = datetime.now(IST)
            minutes_until = int((start_dt - now).total_seconds() / 60)
        except:
            continue
        
        # Initialize tracking for this event
        if event_id not in notified_events:
            notified_events[event_id] = []
        
        # Check each reminder threshold
        for reminder_mins in REMINDER_TIMES:
            # Skip if already sent this reminder level
            if reminder_mins in notified_events[event_id]:
                continue
            
            # Send reminder if event is within this threshold but not past it
            # e.g., for 30-min reminder: send if 25 < minutes_until <= 30
            lower_bound = reminder_mins - 5 if reminder_mins > 5 else 0
            if lower_bound < minutes_until <= reminder_mins:
                location = event.get('location', '')
                location_str = f"\n📍 {location}" if location else ""
                
                # Different urgency levels for different reminder times
                if reminder_mins == 30:
                    urgency = "📅"
                    urgency_text = "Coming up"
                elif reminder_mins == 15:
                    urgency = "⏰"
                    urgency_text = "Starting soon"
                else:  # 5 mins
                    urgency = "🚨"
                    urgency_text = "STARTING NOW"
                
                message = f"{urgency} <b>{urgency_text}!</b>\n\n"
                message += f"📌 <b>{title}</b>\n"
                message += f"🕐 In {minutes_until} minutes ({time_str}){location_str}"
                
                if reminder_mins == 5:
                    message += "\n\n⚡ <i>Time to prepare!</i>"
                
                await send_telegram_message(message)
                notified_events[event_id].append(reminder_mins)
                logger.info(f"Event reminder ({reminder_mins}min) sent: {title}")
                break  # Only send one reminder per check cycle
    
    # Clean up old events (keep last 50 event IDs)
    if len(notified_events) > 50:
        # Remove oldest entries
        keys_to_remove = list(notified_events.keys())[:-25]
        for key in keys_to_remove:
            del notified_events[key]


async def proactive_notifications_loop():
    """Main loop for proactive notifications"""
    logger.info("🔔 Proactive notifications started")
    
    while True:
        try:
            # Send morning digest at 7 AM (once per day)
            await send_morning_digest()
            
            # NOTE: Email notifications disabled - email_bot.py handles ORION: commands
            # Regular emails don't need notification, only ORION: commands get processed
            # await check_new_emails()
            
            # Check for upcoming events (15 min reminder)
            await check_upcoming_events()
            
        except Exception as e:
            logger.error(f"Proactive notification error: {e}")
        
        # Check every minute
        await asyncio.sleep(60)


def start_proactive_notifications():
    """Start the proactive notifications service"""
    asyncio.run(proactive_notifications_loop())


if __name__ == "__main__":
    start_proactive_notifications()
