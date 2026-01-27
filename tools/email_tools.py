"""
Email Tools for Orion
Send and read emails via SMTP/IMAP.
"""

import os
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

import logging

logger = logging.getLogger("Orion")


def _get_config():
    """Lazy import to avoid circular dependencies."""
    from core.config import Config
    return Config


@tool
def send_email(to: str, subject: str, body: str, attachment_path: Optional[str] = None) -> str:
    """
    Send an email via SMTP.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
        attachment_path: Optional path to file attachment
    """
    try:
        Config = _get_config()
        
        if not Config.EMAIL_ADDRESS or not Config.EMAIL_PASSWORD:
            return "❌ Email not configured. Please set EMAIL_ADDRESS and EMAIL_PASSWORD in .env"
        
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_ADDRESS
        msg['To'] = to
        msg['Subject'] = subject
        msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename={os.path.basename(attachment_path)}'
                )
                msg.attach(part)
        
        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to}")
        return f"✅ Email sent successfully to {to}"
    
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def read_recent_emails(count: int = 5, unread_only: bool = False) -> str:
    """
    Read recent emails via IMAP.
    
    Args:
        count: Number of recent emails to fetch (default 5)
        unread_only: If True, only fetch unread emails
    """
    try:
        Config = _get_config()
        
        if not Config.EMAIL_ADDRESS or not Config.EMAIL_PASSWORD:
            return "❌ Email not configured. Please set EMAIL_ADDRESS and EMAIL_PASSWORD in .env"
        
        mail = imaplib.IMAP4_SSL(Config.IMAP_SERVER, Config.IMAP_PORT)
        mail.login(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
        mail.select('inbox')
        
        search_criteria = 'UNSEEN' if unread_only else 'ALL'
        _, message_numbers = mail.search(None, search_criteria)
        
        if not message_numbers[0]:
            mail.logout()
            return "📭 No emails found"
        
        email_ids = message_numbers[0].split()
        recent_ids = email_ids[-count:][::-1]  # Get last N, reverse for newest first
        
        emails_text = []
        for num in recent_ids:
            _, msg_data = mail.fetch(num, '(RFC822)')
            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)
            
            subject = email_message['subject']
            from_ = email_message['from']
            date = email_message['date']
            
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = email_message.get_payload(decode=True).decode()
            
            # Truncate body to 200 chars
            body_preview = body[:200] + "..." if len(body) > 200 else body
            
            emails_text.append(f"""
📧 From: {from_}
📅 Date: {date}
📝 Subject: {subject}
💬 Body Preview: {body_preview}
---""")
        
        mail.logout()
        logger.info(f"Retrieved {len(emails_text)} emails")
        return "\n".join(emails_text)
    
    except Exception as e:
        error_msg = f"Failed to read emails: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def get_email_tools():
    """Get all email-related tools."""
    return [
        send_email,
        read_recent_emails,
    ]
