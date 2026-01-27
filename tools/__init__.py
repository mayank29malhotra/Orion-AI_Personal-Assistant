"""
Orion AI Personal Assistant - Tools Package
Contains all agent tools organized by category.

Modules:
- browser: Playwright browser automation
- email_tools: SMTP/IMAP email operations
- calendar: Google Calendar integration
- tasks_notes: Task and note management
- documents: PDF, OCR, CSV, Excel, JSON, Markdown, QR
- search: Web search, Wikipedia, Python REPL
- utils: Screenshot, notifications, file operations
"""

from tools.loader import get_all_tools, get_all_tools_sync, list_available_tools

__all__ = [
    'get_all_tools',
    'get_all_tools_sync',
    'list_available_tools',
]
