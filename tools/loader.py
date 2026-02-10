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
from tools.github import get_github_tools
from tools.audio import get_audio_tools
from tools.youtube import get_youtube_tools
from tools.dictionary import get_dictionary_tools
from tools.indian_railways import (
    check_pnr_status, get_train_status, search_trains, get_station_code
)
from tools.flights import (
    get_flight_status, get_flight_by_route, get_airport_info, track_flight_live
)


def get_railway_tools():
    """Get Indian Railways tools"""
    return [check_pnr_status, get_train_status, search_trains, get_station_code]


def get_flight_tools():
    """Get Flight tracking tools"""
    return [get_flight_status, get_flight_by_route, get_airport_info, track_flight_live]


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
    - Search (web search, browser search, Wikipedia, fetch webpage)
    - GitHub (repos, issues, PRs)
    - Audio (transcription via Whisper)
    - Python REPL
    - System utilities (screenshot, notifications, file operations)
    """
    tools = []
    browser = None
    playwright = None
    
    # Browser tools (async - Playwright)
    # Skip browser tools in container/headless mode to avoid Playwright issues
    import os
    skip_browser = os.getenv('SKIP_BROWSER_TOOLS', 'false').lower() == 'true'
    
    if not skip_browser:
        try:
            browser_tools, browser, playwright = await get_browser_tools()
            tools.extend(browser_tools)
        except Exception as e:
            import logging
            logging.getLogger("Orion").warning(f"Browser tools failed to load: {e}")
    else:
        import logging
        logging.getLogger("Orion").info("Browser tools skipped (SKIP_BROWSER_TOOLS=true)")
    
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
    
    # GitHub tools
    tools.extend(get_github_tools())
    
    # Audio/Voice tools
    tools.extend(get_audio_tools())
    
    # YouTube tools (transcript, video info, search)
    tools.extend(get_youtube_tools())
    
    # Dictionary tools (define, synonyms, antonyms, translate)
    tools.extend(get_dictionary_tools())
    
    # Indian Railways tools (PNR status, train running status, search)
    tools.extend(get_railway_tools())
    
    # Flight tools (flight status, live tracking)
    tools.extend(get_flight_tools())
    
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
    tools.extend(get_github_tools())
    tools.extend(get_audio_tools())
    tools.extend(get_youtube_tools())
    tools.extend(get_dictionary_tools())
    tools.extend(get_railway_tools())
    tools.extend(get_flight_tools())
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
        'GitHub': ['github_list_repos', 'github_list_issues', 'github_create_issue', 'github_search_repos'],
        'YouTube': ['get_youtube_transcript', 'get_youtube_video_info', 'search_youtube'],
        'Dictionary': ['define_word', 'get_synonyms', 'get_antonyms', 'translate_word'],
        'Indian Railways': ['check_pnr_status', 'get_train_status', 'search_trains', 'get_station_code'],
        'Flights': ['get_flight_status', 'get_flight_by_route', 'get_airport_info', 'track_flight_live'],
        'Location': ['parse_location', 'get_distance'],
        'Audio': ['transcribe_audio'],
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
