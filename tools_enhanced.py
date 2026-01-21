"""
Enhanced tools for Orion AI Personal Assistant
Organized by category with better error handling
"""
from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_core.tools.simple import Tool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_experimental.utilities import PythonREPL
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
import os
import json
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import qrcode
from io import BytesIO
import base64
from PIL import ImageGrab, Image
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from markdown import markdown
from html2text import html2text
from config import Config
from utils import logger, retry_on_error, safe_execute, cache


# Initialize configuration
Config.ensure_directories()


# ============================================================================
# BROWSER AUTOMATION TOOLS
# ============================================================================

async def playwright_tools():
    """Initialize Playwright browser toolkit"""
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
        logger.info("Playwright browser tools initialized successfully")
        return toolkit.get_tools(), browser, playwright
    except Exception as e:
        logger.error(f"Failed to initialize Playwright tools: {e}")
        return [], None, None


# ============================================================================
# EMAIL MANAGEMENT TOOLS
# ============================================================================

@retry_on_error(max_retries=3, delay=2.0)
def send_email(to: str, subject: str, body: str, attachment_path: str = None) -> str:
    """
    Send an email via SMTP
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body text
        attachment_path: Optional path to file attachment
    """
    try:
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


@retry_on_error(max_retries=3, delay=2.0)
def read_recent_emails(count: int = 5, unread_only: bool = False) -> str:
    """
    Read recent emails via IMAP
    Args:
        count: Number of recent emails to fetch (default 5)
        unread_only: If True, only fetch unread emails
    """
    try:
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


# ============================================================================
# CALENDAR INTEGRATION TOOLS
# ============================================================================

def create_calendar_event(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """
    Create a Google Calendar event
    Args:
        summary: Event title
        start_time: Start time in format 'YYYY-MM-DD HH:MM'
        end_time: End time in format 'YYYY-MM-DD HH:MM'
        description: Event description
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = None
        
        # Token file to store user's access and refresh tokens
        token_path = Config.GOOGLE_CALENDAR_TOKEN
        creds_path = Config.GOOGLE_CALENDAR_CREDENTIALS
        
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif os.path.exists(creds_path):
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                return "❌ Google Calendar credentials not found. Please set up credentials.json"
            
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        service = build('calendar', 'v3', credentials=creds)
        
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': datetime.strptime(start_time, '%Y-%m-%d %H:%M').isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': datetime.strptime(end_time, '%Y-%m-%d %H:%M').isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Calendar event created: {summary}")
        return f"✅ Calendar event created: {summary}\n🔗 Link: {event.get('htmlLink')}"
    
    except Exception as e:
        error_msg = f"Failed to create calendar event: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def list_calendar_events(days_ahead: int = 7) -> str:
    """
    List upcoming calendar events
    Args:
        days_ahead: Number of days to look ahead (default 7)
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        token_path = Config.GOOGLE_CALENDAR_TOKEN
        
        if not os.path.exists(token_path):
            return "❌ Google Calendar not authenticated. Create an event first to authenticate."
        
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/calendar'])
        service = build('calendar', 'v3', credentials=creds)
        
        now = datetime.utcnow()
        time_max = now + timedelta(days=days_ahead)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=time_max.isoformat() + 'Z',
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"📅 No upcoming events in the next {days_ahead} days"
        
        events_text = [f"📅 Upcoming Events (next {days_ahead} days):"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'No Title')
            events_text.append(f"  • {start}: {summary}")
        
        logger.info(f"Retrieved {len(events)} calendar events")
        return "\n".join(events_text)
    
    except Exception as e:
        error_msg = f"Failed to list calendar events: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# TASK & NOTE MANAGEMENT TOOLS
# ============================================================================

def create_task(task: str, due_date: str = None, priority: str = "medium") -> str:
    """
    Create a task/reminder
    Args:
        task: Task description
        due_date: Due date in format 'YYYY-MM-DD' (optional)
        priority: Task priority (low/medium/high)
    """
    try:
        tasks_file = os.path.join(Config.TASKS_DIR, 'tasks.json')
        
        # Load existing tasks
        tasks = []
        if os.path.exists(tasks_file):
            with open(tasks_file, 'r') as f:
                tasks = json.load(f)
        
        # Create new task
        new_task = {
            'id': len(tasks) + 1,
            'task': task,
            'due_date': due_date,
            'priority': priority,
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'completed': False
        }
        
        tasks.append(new_task)
        
        # Save tasks
        with open(tasks_file, 'w') as f:
            json.dump(tasks, f, indent=2)
        
        logger.info(f"Task created: {task}")
        return f"✅ Task #{new_task['id']} created: {task}\n📅 Due: {due_date or 'Not set'}\n⚡ Priority: {priority}"
    
    except Exception as e:
        error_msg = f"Failed to create task: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def list_tasks(show_completed: bool = False) -> str:
    """
    List all tasks
    Args:
        show_completed: If True, include completed tasks
    """
    try:
        tasks_file = os.path.join(Config.TASKS_DIR, 'tasks.json')
        
        if not os.path.exists(tasks_file):
            return "📋 No tasks found"
        
        with open(tasks_file, 'r') as f:
            tasks = json.load(f)
        
        if not tasks:
            return "📋 No tasks found"
        
        filtered_tasks = tasks if show_completed else [t for t in tasks if not t['completed']]
        
        if not filtered_tasks:
            return "📋 No pending tasks"
        
        tasks_text = ["📋 Tasks:"]
        for task in filtered_tasks:
            status = "✅" if task['completed'] else "⬜"
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task['priority'], "⚪")
            due = f"📅 {task['due_date']}" if task['due_date'] else ""
            tasks_text.append(f"{status} #{task['id']} {priority_emoji} {task['task']} {due}")
        
        return "\n".join(tasks_text)
    
    except Exception as e:
        error_msg = f"Failed to list tasks: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def complete_task(task_id: int) -> str:
    """Mark a task as completed"""
    try:
        tasks_file = os.path.join(Config.TASKS_DIR, 'tasks.json')
        
        if not os.path.exists(tasks_file):
            return "❌ No tasks found"
        
        with open(tasks_file, 'r') as f:
            tasks = json.load(f)
        
        for task in tasks:
            if task['id'] == task_id:
                task['completed'] = True
                task['completed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                with open(tasks_file, 'w') as f:
                    json.dump(tasks, f, indent=2)
                
                logger.info(f"Task #{task_id} marked as completed")
                return f"✅ Task #{task_id} marked as completed!"
        
        return f"❌ Task #{task_id} not found"
    
    except Exception as e:
        error_msg = f"Failed to complete task: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def create_note(title: str, content: str, tags: str = "") -> str:
    """
    Create a note
    Args:
        title: Note title
        content: Note content
        tags: Comma-separated tags
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{title.replace(' ', '_')}.md"
        filepath = os.path.join(Config.NOTES_DIR, filename)
        
        note_content = f"""# {title}

**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Tags:** {tags}

---

{content}
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        logger.info(f"Note created: {title}")
        return f"✅ Note created: {title}\n📁 Location: {filepath}"
    
    except Exception as e:
        error_msg = f"Failed to create note: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def search_notes(query: str) -> str:
    """Search notes by title or content"""
    try:
        notes_dir = Config.NOTES_DIR
        
        if not os.path.exists(notes_dir):
            return "📝 No notes found"
        
        matching_notes = []
        for filename in os.listdir(notes_dir):
            if filename.endswith('.md'):
                filepath = os.path.join(notes_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if query.lower() in content.lower():
                        # Extract title (first line)
                        title = content.split('\n')[0].replace('#', '').strip()
                        matching_notes.append(f"📝 {title} ({filename})")
        
        if not matching_notes:
            return f"📝 No notes found matching '{query}'"
        
        return "📝 Matching notes:\n" + "\n".join(matching_notes)
    
    except Exception as e:
        error_msg = f"Failed to search notes: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# SCREENSHOT TOOL
# ============================================================================

def take_screenshot(filename: str = None) -> str:
    """
    Capture a screenshot
    Args:
        filename: Optional filename (will auto-generate if not provided)
    """
    try:
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"screenshot_{timestamp}.png"
        
        if not filename.endswith('.png'):
            filename += '.png'
        
        filepath = os.path.join(Config.SCREENSHOTS_DIR, filename)
        
        screenshot = ImageGrab.grab()
        screenshot.save(filepath)
        
        logger.info(f"Screenshot saved: {filepath}")
        return f"✅ Screenshot saved: {filepath}"
    
    except Exception as e:
        error_msg = f"Failed to take screenshot: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# PDF TOOLS
# ============================================================================

def read_pdf(filepath: str, page_numbers: str = "all") -> str:
    """
    Read text from a PDF file
    Args:
        filepath: Path to PDF file
        page_numbers: Page numbers to read (e.g., "1,3,5" or "all")
    """
    try:
        if not os.path.exists(filepath):
            return f"❌ File not found: {filepath}"
        
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            # Determine which pages to read
            if page_numbers == "all":
                pages_to_read = range(total_pages)
            else:
                pages_to_read = [int(p.strip()) - 1 for p in page_numbers.split(',')]
            
            text_content = []
            for page_num in pages_to_read:
                if 0 <= page_num < total_pages:
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    text_content.append(f"--- Page {page_num + 1} ---\n{text}\n")
            
            full_text = "\n".join(text_content)
            logger.info(f"Read {len(pages_to_read)} pages from PDF: {filepath}")
            return full_text
    
    except Exception as e:
        error_msg = f"Failed to read PDF: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def create_pdf(text: str, output_path: str) -> str:
    """
    Create a PDF from text
    Args:
        text: Text content
        output_path: Output PDF path
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        
        if not output_path.endswith('.pdf'):
            output_path += '.pdf'
        
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        # Simple text wrapping
        y_position = height - inch
        for line in text.split('\n'):
            if y_position < inch:
                c.showPage()
                y_position = height - inch
            c.drawString(inch, y_position, line[:80])  # Limit line length
            y_position -= 15
        
        c.save()
        
        logger.info(f"PDF created: {output_path}")
        return f"✅ PDF created: {output_path}"
    
    except Exception as e:
        error_msg = f"Failed to create PDF: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# OCR (TEXT EXTRACTION FROM IMAGES)
# ============================================================================

def extract_text_from_image(image_path: str) -> str:
    """
    Extract text from an image using OCR
    Args:
        image_path: Path to image file
    """
    try:
        if not os.path.exists(image_path):
            return f"❌ Image not found: {image_path}"
        
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        
        if not text.strip():
            return "⚠️ No text found in image"
        
        logger.info(f"Extracted text from image: {image_path}")
        return f"📝 Extracted text:\n\n{text}"
    
    except Exception as e:
        error_msg = f"Failed to extract text from image: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# JSON/CSV/EXCEL TOOLS
# ============================================================================

def read_csv(filepath: str, rows: int = 10) -> str:
    """
    Read a CSV file
    Args:
        filepath: Path to CSV file
        rows: Number of rows to display (default 10)
    """
    try:
        if not os.path.exists(filepath):
            return f"❌ File not found: {filepath}"
        
        df = pd.read_csv(filepath)
        
        info = f"📊 CSV File: {filepath}\n"
        info += f"📏 Shape: {df.shape[0]} rows × {df.shape[1]} columns\n"
        info += f"📋 Columns: {', '.join(df.columns.tolist())}\n\n"
        info += f"🔍 First {min(rows, len(df))} rows:\n"
        info += df.head(rows).to_string()
        
        logger.info(f"Read CSV file: {filepath}")
        return info
    
    except Exception as e:
        error_msg = f"Failed to read CSV: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def read_excel(filepath: str, sheet_name: str = None, rows: int = 10) -> str:
    """
    Read an Excel file
    Args:
        filepath: Path to Excel file
        sheet_name: Sheet name (optional, reads first sheet if not provided)
        rows: Number of rows to display
    """
    try:
        if not os.path.exists(filepath):
            return f"❌ File not found: {filepath}"
        
        df = pd.read_excel(filepath, sheet_name=sheet_name or 0)
        
        info = f"📊 Excel File: {filepath}\n"
        if sheet_name:
            info += f"📑 Sheet: {sheet_name}\n"
        info += f"📏 Shape: {df.shape[0]} rows × {df.shape[1]} columns\n"
        info += f"📋 Columns: {', '.join(df.columns.tolist())}\n\n"
        info += f"🔍 First {min(rows, len(df))} rows:\n"
        info += df.head(rows).to_string()
        
        logger.info(f"Read Excel file: {filepath}")
        return info
    
    except Exception as e:
        error_msg = f"Failed to read Excel: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def read_json_file(filepath: str) -> str:
    """Read and pretty-print a JSON file"""
    try:
        if not os.path.exists(filepath):
            return f"❌ File not found: {filepath}"
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        pretty_json = json.dumps(data, indent=2)
        logger.info(f"Read JSON file: {filepath}")
        return f"📄 JSON Content:\n\n{pretty_json}"
    
    except Exception as e:
        error_msg = f"Failed to read JSON: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def write_json_file(filepath: str, data: str) -> str:
    """
    Write data to a JSON file
    Args:
        filepath: Output file path
        data: JSON string or dict
    """
    try:
        # Parse if string
        if isinstance(data, str):
            data = json.loads(data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Written JSON file: {filepath}")
        return f"✅ JSON file saved: {filepath}"
    
    except Exception as e:
        error_msg = f"Failed to write JSON: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def csv_to_json(csv_path: str, json_path: str) -> str:
    """Convert CSV to JSON"""
    try:
        df = pd.read_csv(csv_path)
        data = df.to_dict(orient='records')
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Converted CSV to JSON: {csv_path} -> {json_path}")
        return f"✅ Converted {csv_path} to {json_path}"
    
    except Exception as e:
        error_msg = f"Failed to convert CSV to JSON: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# MARKDOWN TOOLS
# ============================================================================

def markdown_to_html(markdown_text: str) -> str:
    """Convert Markdown to HTML"""
    try:
        html = markdown(markdown_text)
        logger.info("Converted Markdown to HTML")
        return f"✅ HTML:\n\n{html}"
    except Exception as e:
        error_msg = f"Failed to convert Markdown to HTML: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def html_to_markdown(html_text: str) -> str:
    """Convert HTML to Markdown"""
    try:
        md = html2text(html_text)
        logger.info("Converted HTML to Markdown")
        return f"✅ Markdown:\n\n{md}"
    except Exception as e:
        error_msg = f"Failed to convert HTML to Markdown: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# QR CODE GENERATOR
# ============================================================================

def generate_qr_code(data: str, filename: str = None) -> str:
    """
    Generate a QR code
    Args:
        data: Data to encode in QR code (URL, text, etc.)
        filename: Optional filename for saving
    """
    try:
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"qrcode_{timestamp}.png"
        
        if not filename.endswith('.png'):
            filename += '.png'
        
        filepath = os.path.join(Config.TEMP_DIR, filename)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filepath)
        
        logger.info(f"QR code generated: {filepath}")
        return f"✅ QR code generated: {filepath}\n📝 Data: {data}"
    
    except Exception as e:
        error_msg = f"Failed to generate QR code: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============================================================================
# EXISTING TOOLS
# ============================================================================

def push_notification(text: str) -> str:
    """Send a push notification to the user"""
    try:
        if not Config.PUSHOVER_TOKEN or not Config.PUSHOVER_USER:
            return "❌ Pushover not configured"
        
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": Config.PUSHOVER_TOKEN,
                "user": Config.PUSHOVER_USER,
                "message": text
            }
        )
        logger.info(f"Push notification sent: {text[:50]}...")
        return "✅ Push notification sent"
    except Exception as e:
        error_msg = f"Failed to send push notification: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def get_file_tools():
    """Get file management toolkit"""
    toolkit = FileManagementToolkit(root_dir=Config.SANDBOX_DIR)
    return toolkit.get_tools()


# ============================================================================
# TOOL ASSEMBLY
# ============================================================================

async def get_all_tools():
    """Assemble all tools with proper categorization and error handling"""
    
    # Browser tools
    browser_tools, browser, playwright = await playwright_tools()
    
    # File management tools
    file_tools = get_file_tools()
    
    # Email tools
    email_send_tool = Tool(
        name="send_email",
        func=send_email,
        description="Send an email. Args: to (email address), subject (email subject), body (email body), attachment_path (optional file path)"
    )
    
    email_read_tool = Tool(
        name="read_recent_emails",
        func=read_recent_emails,
        description="Read recent emails. Args: count (number of emails, default 5), unread_only (True/False)"
    )
    
    # Calendar tools
    calendar_create_tool = Tool(
        name="create_calendar_event",
        func=create_calendar_event,
        description="Create a Google Calendar event. Args: summary (title), start_time (YYYY-MM-DD HH:MM), end_time (YYYY-MM-DD HH:MM), description (optional)"
    )
    
    calendar_list_tool = Tool(
        name="list_calendar_events",
        func=list_calendar_events,
        description="List upcoming calendar events. Args: days_ahead (number of days, default 7)"
    )
    
    # Task tools
    task_create_tool = Tool(
        name="create_task",
        func=create_task,
        description="Create a task/reminder. Args: task (description), due_date (YYYY-MM-DD, optional), priority (low/medium/high)"
    )
    
    task_list_tool = Tool(
        name="list_tasks",
        func=list_tasks,
        description="List all tasks. Args: show_completed (True/False)"
    )
    
    task_complete_tool = Tool(
        name="complete_task",
        func=complete_task,
        description="Mark a task as completed. Args: task_id (task number)"
    )
    
    # Note tools
    note_create_tool = Tool(
        name="create_note",
        func=create_note,
        description="Create a note. Args: title (note title), content (note content), tags (comma-separated tags)"
    )
    
    note_search_tool = Tool(
        name="search_notes",
        func=search_notes,
        description="Search notes by keyword. Args: query (search query)"
    )
    
    # Screenshot tool
    screenshot_tool = Tool(
        name="take_screenshot",
        func=take_screenshot,
        description="Capture a screenshot. Args: filename (optional, will auto-generate if not provided)"
    )
    
    # PDF tools
    pdf_read_tool = Tool(
        name="read_pdf",
        func=read_pdf,
        description="Read text from a PDF file. Args: filepath (path to PDF), page_numbers (e.g., '1,3,5' or 'all')"
    )
    
    pdf_create_tool = Tool(
        name="create_pdf",
        func=create_pdf,
        description="Create a PDF from text. Args: text (content), output_path (output file path)"
    )
    
    # OCR tool
    ocr_tool = Tool(
        name="extract_text_from_image",
        func=extract_text_from_image,
        description="Extract text from an image using OCR. Args: image_path (path to image file)"
    )
    
    # Data file tools
    csv_read_tool = Tool(
        name="read_csv",
        func=read_csv,
        description="Read a CSV file. Args: filepath (path to CSV), rows (number of rows to display, default 10)"
    )
    
    excel_read_tool = Tool(
        name="read_excel",
        func=read_excel,
        description="Read an Excel file. Args: filepath (path to Excel file), sheet_name (optional), rows (number of rows)"
    )
    
    json_read_tool = Tool(
        name="read_json_file",
        func=read_json_file,
        description="Read and display a JSON file. Args: filepath (path to JSON file)"
    )
    
    json_write_tool = Tool(
        name="write_json_file",
        func=write_json_file,
        description="Write data to a JSON file. Args: filepath (output path), data (JSON string or dict)"
    )
    
    csv_to_json_tool = Tool(
        name="csv_to_json",
        func=csv_to_json,
        description="Convert CSV to JSON. Args: csv_path (input CSV), json_path (output JSON)"
    )
    
    # Markdown tools
    md_to_html_tool = Tool(
        name="markdown_to_html",
        func=markdown_to_html,
        description="Convert Markdown to HTML. Args: markdown_text (markdown content)"
    )
    
    html_to_md_tool = Tool(
        name="html_to_markdown",
        func=html_to_markdown,
        description="Convert HTML to Markdown. Args: html_text (HTML content)"
    )
    
    # QR code tool
    qr_tool = Tool(
        name="generate_qr_code",
        func=generate_qr_code,
        description="Generate a QR code. Args: data (data to encode), filename (optional)"
    )
    
    # Push notification
    push_tool = Tool(
        name="send_push_notification",
        func=push_notification,
        description="Send a push notification to the user. Args: text (notification message)"
    )
    
    # Web search
    serper = GoogleSerperAPIWrapper()
    search_tool = Tool(
        name="search",
        func=serper.run,
        description="Search the web for information. Args: query (search query)"
    )
    
    # Wikipedia
    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)
    
    # Python REPL
    python_repl = PythonREPL()
    python_repl_tool = Tool(
        name="python_repl",
        func=python_repl.run,
        description="Execute Python code. Args: command (Python code to execute). Use print() to see output."
    )
    
    # Combine all tools
    all_tools = (
        browser_tools +
        file_tools +
        [
            # Productivity
            email_send_tool,
            email_read_tool,
            calendar_create_tool,
            calendar_list_tool,
            task_create_tool,
            task_list_tool,
            task_complete_tool,
            note_create_tool,
            note_search_tool,
            screenshot_tool,
            # Document Processing
            pdf_read_tool,
            pdf_create_tool,
            ocr_tool,
            csv_read_tool,
            excel_read_tool,
            json_read_tool,
            json_write_tool,
            csv_to_json_tool,
            md_to_html_tool,
            html_to_md_tool,
            # Communication
            qr_tool,
            push_tool,
            # Information
            search_tool,
            wiki_tool,
            python_repl_tool,
        ]
    )
    
    logger.info(f"Initialized {len(all_tools)} tools")
    return all_tools, browser, playwright
