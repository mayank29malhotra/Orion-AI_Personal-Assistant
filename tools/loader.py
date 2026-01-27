"""
Tool Loader - Aggregates all tools from different modules.
"""

from tools.browser import get_browser_tools
from tools.email_tools import get_email_tools
from tools.calendar import get_calendar_tools
from tools.tasks_notes import get_task_tools, get_note_tools
from tools.documents import get_document_tools
from tools.search import get_search_tools, get_repl_tools
from tools.utils import get_utility_tools


async def get_all_tools():
    """
    Get all available tools from all categories.
    
    Returns:
        Tuple of (tools_list, browser_instance, playwright_instance)
        
    Tools included:
    - Browser automation (navigate, click, type, screenshot, etc.)
    - Email (send, read)
    - Calendar (create event, list events, delete)
    - Tasks (create, list, complete, delete)
    - Notes (create, list, read, search, delete)
    - Documents (PDF, OCR, CSV, Excel, JSON, Markdown, QR code)
    - Search (web search, Wikipedia, fetch webpage)
    - Python REPL
    - System utilities (screenshot, notifications, file operations)
    """
    tools = []
    browser = None
    playwright = None
    
    # Browser tools (async - Playwright)
    try:
        browser_tools, browser, playwright = await get_browser_tools()
        tools.extend(browser_tools)
    except Exception as e:
        import logging
        logging.getLogger("Orion").warning(f"Browser tools failed to load: {e}")
    
    # Email tools
    tools.extend(get_email_tools())
    
    # Calendar tools
    tools.extend(get_calendar_tools())
    
    # Task & Note tools
    tools.extend(get_task_tools())
    tools.extend(get_note_tools())
    
    # Document tools (PDF, OCR, CSV, Excel, JSON, Markdown, QR)
    tools.extend(get_document_tools())
    
    # Search & Web tools
    tools.extend(get_search_tools())
    
    # Python REPL
    tools.extend(get_repl_tools())
    
    # System utilities (screenshot, notifications, file ops)
    tools.extend(get_utility_tools())
    
    return tools, browser, playwright


def get_all_tools_sync():
    """
    Synchronous version to get all non-async tools.
    Browser tools excluded (require async initialization).
    """
    tools = []
    
    tools.extend(get_email_tools())
    tools.extend(get_calendar_tools())
    tools.extend(get_task_tools())
    tools.extend(get_note_tools())
    tools.extend(get_document_tools())
    tools.extend(get_search_tools())
    tools.extend(get_repl_tools())
    tools.extend(get_utility_tools())
    
    return tools


def list_available_tools():
    """
    List all available tool names and descriptions.
    Useful for debugging and documentation.
    """
    tools = get_all_tools_sync()
    
    output = []
    output.append(f"📋 Available Tools ({len(tools)} total):\n")
    
    categories = {
        'Email': ['send_email', 'read_recent_emails'],
        'Calendar': ['create_calendar_event', 'list_calendar_events', 'delete_calendar_event'],
        'Tasks': ['create_task', 'list_tasks', 'complete_task', 'delete_task'],
        'Notes': ['create_note', 'list_notes', 'read_note', 'search_notes', 'delete_note'],
        'PDF': ['extract_pdf_text', 'create_pdf'],
        'OCR': ['ocr_image'],
        'CSV': ['read_csv', 'write_csv'],
        'Excel': ['read_excel', 'write_excel'],
        'JSON': ['read_json', 'write_json'],
        'Markdown': ['markdown_to_html'],
        'QR Code': ['generate_qr_code'],
        'Search': ['web_search', 'fetch_webpage', 'wikipedia_search'],
        'Python': ['python_repl'],
        'System': ['take_screenshot', 'send_push_notification', 'get_system_info', 
                   'list_directory', 'read_file', 'write_file'],
    }
    
    for category, tool_names in categories.items():
        output.append(f"\n🔧 {category}:")
        for name in tool_names:
            tool = next((t for t in tools if t.name == name), None)
            if tool:
                output.append(f"  • {name}: {tool.description[:60]}...")
    
    output.append("\n🌐 Browser tools (async, not listed here)")
    
    return "\n".join(output)
