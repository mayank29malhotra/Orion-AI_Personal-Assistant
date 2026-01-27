"""
Email Bot Integration for Orion AI Assistant
FREE - Uses your existing email account!

How it works:
1. Send an email to your own email with subject starting with "ORION:"
2. Bot checks inbox periodically
3. Processes the command and replies to the email

Setup:
1. Use your Gmail account
2. Enable IMAP and use App Password
3. Set EMAIL_BOT_CHECK_INTERVAL in .env (default: 60 seconds)
"""
import os
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import asyncio
from datetime import datetime
from typing import Optional, List, Tuple

# Add parent directory for core imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import Config
from core.agent import Orion
from core.utils import Logger
from core.memory import pending_queue

logger = Logger().logger

# Email Configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
CHECK_INTERVAL = int(os.getenv("EMAIL_BOT_CHECK_INTERVAL", "60"))  # seconds

# Command prefix - emails with this subject prefix are processed
COMMAND_PREFIX = "ORION:"

# Allowed senders (for security)
ALLOWED_SENDERS = os.getenv("EMAIL_BOT_ALLOWED_SENDERS", "")  # Comma-separated emails

# Global Orion instance
orion_instance: Optional[Orion] = None


def is_sender_allowed(sender_email: str) -> bool:
    """Check if email sender is allowed"""
    if not ALLOWED_SENDERS:
        # If not set, only allow emails from self
        return sender_email.lower() == EMAIL_ADDRESS.lower()
    
    allowed = [e.strip().lower() for e in ALLOWED_SENDERS.split(",")]
    return sender_email.lower() in allowed


async def get_orion() -> Orion:
    """Get or create Orion instance"""
    global orion_instance
    if orion_instance is None:
        orion_instance = Orion()
        await orion_instance.setup()
        logger.info("Email Bot: Orion initialized")
    return orion_instance


def decode_email_subject(subject) -> str:
    """Decode email subject"""
    if subject is None:
        return ""
    
    decoded_parts = decode_header(subject)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(encoding or 'utf-8', errors='ignore')
        else:
            result += part
    return result


def get_email_body(msg) -> str:
    """Extract email body from message"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(msg.get_payload())
    
    return body.strip()


def get_sender_email(msg) -> str:
    """Extract sender email address"""
    from_header = msg.get("From", "")
    # Extract email from "Name <email@example.com>" format
    if "<" in from_header:
        return from_header.split("<")[1].split(">")[0]
    return from_header


def check_for_commands() -> List[Tuple[str, str, str, str]]:
    """
    Check inbox for unread emails with ORION: prefix
    Returns: List of (message_id, sender, subject, body)
    """
    commands = []
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("INBOX")
        
        # Search for unread emails
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != "OK":
            return commands
        
        for msg_id in messages[0].split():
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            
            if status != "OK":
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            subject = decode_email_subject(msg.get("Subject", ""))
            
            # Check if it's an Orion command
            if subject.upper().startswith(COMMAND_PREFIX):
                sender = get_sender_email(msg)
                body = get_email_body(msg)
                
                # The command is either in subject (after prefix) or in body
                command = subject[len(COMMAND_PREFIX):].strip()
                if not command and body:
                    command = body
                
                if command:
                    commands.append((msg_id.decode(), sender, subject, command))
                    logger.info(f"Email command from {sender}: {command[:50]}...")
        
        mail.logout()
        
    except Exception as e:
        logger.error(f"Error checking emails: {e}")
    
    return commands


def send_reply(to_email: str, original_subject: str, response: str):
    """Send email reply with Orion's response"""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = f"Re: {original_subject}"
        
        body = f"""
🤖 Orion AI Response
━━━━━━━━━━━━━━━━━━━━

{response}

━━━━━━━━━━━━━━━━━━━━
Processed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Reply sent to {to_email}")
        
    except Exception as e:
        logger.error(f"Error sending reply: {e}")


async def process_command(sender: str, subject: str, command: str):
    """Process an email command through Orion"""
    try:
        # Security check
        if not is_sender_allowed(sender):
            logger.warning(f"🚫 Unauthorized email sender: {sender}")
            return
        
        logger.info(f"Processing email command: {command[:50]}...")
        
        orion = await get_orion()
        results = await orion.run_superstep(command, success_criteria="", history=[])
        
        if results and len(results) > 0:
            response = results[-1][1] if len(results[-1]) > 1 else "Task completed"
        else:
            response = "Task completed successfully"
        
        # Send reply
        send_reply(sender, subject, response)
        
        # Mark bot as online
        pending_queue.set_bot_status("online")
        
    except Exception as e:
        logger.error(f"Error processing email command: {e}")
        
        # Check if it's a critical error
        is_critical = any(err in str(e).lower() for err in ["rate limit", "timeout", "connection", "unavailable", "503", "502"])
        
        if is_critical:
            # Queue the request for later processing
            pending_queue.add_request(
                user_id=sender,
                channel="email",
                message=command,
                priority=1,
                metadata={"subject": subject}
            )
            pending_queue.set_bot_status("offline", str(e))
            
            send_reply(
                sender, 
                subject, 
                f"⏳ Request Queued\n\n"
                f"I'm experiencing some issues right now. Your request has been saved "
                f"and will be processed automatically when I'm back online.\n\n"
                f"📝 Request: {command[:200]}{'...' if len(command) > 200 else ''}"
            )
        else:
            send_reply(sender, subject, f"❌ Error: {str(e)}")


async def email_bot_loop():
    """Main loop - check for emails periodically"""
    logger.info(f"Email bot started. Checking every {CHECK_INTERVAL} seconds...")
    logger.info(f"Send emails with subject starting with '{COMMAND_PREFIX}' to trigger Orion")
    
    if not ALLOWED_SENDERS:
        logger.info(f"Only emails from {EMAIL_ADDRESS} will be processed")
    else:
        logger.info(f"Allowed senders: {ALLOWED_SENDERS}")
    
    while True:
        try:
            commands = check_for_commands()
            
            for msg_id, sender, subject, command in commands:
                await process_command(sender, subject, command)
            
        except Exception as e:
            logger.error(f"Email bot error: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)


def start_email_bot():
    """Start the email bot"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        logger.error("EMAIL_ADDRESS and EMAIL_PASSWORD must be set in .env")
        return
    
    asyncio.run(email_bot_loop())


if __name__ == "__main__":
    start_email_bot()
