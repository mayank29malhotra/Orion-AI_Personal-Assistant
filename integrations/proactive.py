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
CALENDAR_REMINDER_MINUTES = int(os.getenv("CALENDAR_REMINDER_MINUTES", "15"))  # 15 min before event

# Track last notification times
last_email_check = datetime.min.replace(tzinfo=IST)
last_digest_date = None
notified_events = set()  # Track which events we've already sent reminders for


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


def get_calendar_events_for_today() -> List[dict]:
    """Get today's calendar events"""
    try:
        from tools.calendar import _get_google_service
        
        service, error = _get_google_service()
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


def get_upcoming_events(minutes_ahead: int = 15) -> List[dict]:
    """Get events starting in the next X minutes"""
    try:
        from tools.calendar import _get_google_service
        
        service, error = _get_google_service()
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
    """Send morning calendar digest"""
    global last_digest_date
    
    now = datetime.now(IST)
    today = now.date()
    
    # Only send once per day, at the configured hour
    if last_digest_date == today:
        return
    
    if now.hour < MORNING_DIGEST_HOUR:
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
    """Send reminders for events starting soon"""
    global notified_events
    
    events = get_upcoming_events(CALENDAR_REMINDER_MINUTES)
    
    for event in events:
        event_id = event.get('id')
        if event_id in notified_events:
            continue
        
        title = event.get('summary', 'Untitled Event')
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        # Parse start time
        if 'T' in start:
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                start_dt = start_dt.astimezone(IST)
                time_str = start_dt.strftime('%I:%M %p')
                
                # Calculate minutes until event
                now = datetime.now(IST)
                minutes_until = int((start_dt - now).total_seconds() / 60)
            except:
                time_str = start
                minutes_until = CALENDAR_REMINDER_MINUTES
        else:
            continue  # Skip all-day events for reminders
        
        location = event.get('location', '')
        location_str = f"\n📍 {location}" if location else ""
        
        message = f"⏰ <b>Upcoming Event!</b>\n\n"
        message += f"📌 <b>{title}</b>\n"
        message += f"🕐 Starting in {minutes_until} minutes ({time_str}){location_str}"
        
        await send_telegram_message(message)
        notified_events.add(event_id)
        logger.info(f"Event reminder sent: {title}")
    
    # Clean up old event IDs (keep last 100)
    if len(notified_events) > 100:
        notified_events = set(list(notified_events)[-50:])


async def proactive_notifications_loop():
    """Main loop for proactive notifications"""
    logger.info("🔔 Proactive notifications started")
    
    while True:
        try:
            # Send morning digest (once per day)
            await send_morning_digest()
            
            # Check for new emails
            await check_new_emails()
            
            # Check for upcoming events
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
