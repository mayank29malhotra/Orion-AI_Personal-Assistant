"""
Orion Agent Router
==================

Routes user requests to the appropriate sub-agent based on intent classification.
This is the orchestration layer that Orion uses to delegate specialized tasks.

Category Mapping:
=================

┌────────────────────────────────────────────────────────────────────────────┐
│                        ORION CAPABILITIES BY CATEGORY                       │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  🧳 TRAVEL AGENT                        📧 COMMUNICATION AGENT              │
│  ├─ search_flights_all_platforms        ├─ send_email                      │
│  ├─ search_trains_all_platforms         ├─ read_recent_emails              │
│  ├─ find_cheapest_travel_option         └─ (Telegram handled separately)   │
│  ├─ get_travel_deals_and_coupons                                           │
│  ├─ check_pnr_status                    📅 PRODUCTIVITY AGENT               │
│  ├─ get_train_status                    ├─ create_calendar_event           │
│  ├─ search_trains                       ├─ list_calendar_events            │
│  ├─ get_station_code                    ├─ delete_calendar_event           │
│  ├─ get_flight_status                   ├─ create_task                     │
│  ├─ get_flight_by_route                 ├─ list_tasks                      │
│  ├─ get_airport_info                    ├─ complete_task                   │
│  └─ track_flight_live                   ├─ delete_task                     │
│                                         ├─ create_note                     │
│  💻 DEVELOPER AGENT                      ├─ list_notes                      │
│  ├─ github_list_repos                   ├─ read_note                       │
│  ├─ github_list_issues                  ├─ search_notes                    │
│  ├─ github_create_issue                 └─ delete_note                     │
│  ├─ github_search_repos                                                    │
│  └─ python_repl                         🔍 RESEARCH AGENT                   │
│                                         ├─ web_search                      │
│  🎬 MEDIA AGENT                          ├─ fetch_webpage                   │
│  ├─ get_youtube_transcript              ├─ wikipedia_search                │
│  ├─ get_youtube_video_info              ├─ define_word                     │
│  ├─ search_youtube                      ├─ get_synonyms                    │
│  ├─ transcribe_audio                    ├─ get_antonyms                    │
│  ├─ extract_pdf_text                    └─ translate_word                  │
│  ├─ create_pdf                                                             │
│  ├─ ocr_image                           🖥️ SYSTEM AGENT                     │
│  ├─ read_csv / write_csv                ├─ take_screenshot                 │
│  ├─ read_excel / write_excel            ├─ send_push_notification          │
│  ├─ read_json / write_json              ├─ get_system_info                 │
│  ├─ markdown_to_html                    ├─ list_directory                  │
│  └─ generate_qr_code                    ├─ read_file                       │
│                                         └─ write_file                      │
│                                                                            │
│  🌐 BROWSER AGENT (when available)                                         │
│  ├─ navigate_to_url                                                        │
│  ├─ click_element                                                          │
│  ├─ type_text                                                              │
│  ├─ take_browser_screenshot                                                │
│  └─ get_page_content                                                       │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum
import re


class AgentCategory(Enum):
    """Categories of sub-agents"""
    TRAVEL = "travel"
    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    DEVELOPER = "developer"
    MEDIA = "media"
    RESEARCH = "research"
    SYSTEM = "system"
    BROWSER = "browser"
    GENERAL = "general"  # Handled by main Orion


# Keywords that indicate which agent should handle the request
AGENT_KEYWORDS = {
    AgentCategory.TRAVEL: [
        "flight", "flights", "fly", "flying", "airline", "airport", "plane",
        "train", "trains", "railway", "rail", "irctc", "pnr", "station",
        "travel", "trip", "journey", "book", "booking", "ticket", "tickets",
        "cheapest", "cheap", "price", "fare", "bus", "buses",
        "makemytrip", "goibibo", "cleartrip", "ixigo", "redbus",
        "mumbai to", "delhi to", "bangalore to", "chennai to", "from delhi",
        "from mumbai", "vande bharat", "rajdhani", "shatabdi", "duronto",
        "indigo", "spicejet", "air india", "vistara", "akasa",
        "departure", "arrival", "schedule", "route", "distance",
    ],
    AgentCategory.COMMUNICATION: [
        "email", "mail", "send email", "read email", "inbox", "compose",
        "message", "notify", "notification",
    ],
    AgentCategory.PRODUCTIVITY: [
        "calendar", "event", "meeting", "appointment", "schedule",
        "reminder", "remind", "alarm",
        "task", "todo", "to-do", "tasks",
        "note", "notes", "write down", "remember",
    ],
    AgentCategory.DEVELOPER: [
        "github", "repo", "repository", "code", "coding", "program",
        "python", "script", "execute", "run code", "programming",
        "issue", "pull request", "pr", "commit", "branch",
        "debug", "error", "bug", "fix",
    ],
    AgentCategory.MEDIA: [
        "youtube", "video", "transcript", "watch", "channel",
        "audio", "transcribe", "speech", "voice", "recording",
        "pdf", "document", "doc", "ocr", "scan", "image text",
        "excel", "csv", "spreadsheet", "json", "data",
        "qr", "qr code", "markdown",
    ],
    AgentCategory.RESEARCH: [
        "search", "google", "find", "look up", "lookup",
        "wikipedia", "wiki", "define", "definition", "meaning",
        "synonym", "antonym", "translate", "translation",
        "what is", "who is", "when did", "where is", "how to",
        "explain", "information", "info", "learn", "research",
    ],
    AgentCategory.SYSTEM: [
        "screenshot", "screen", "capture",
        "file", "folder", "directory", "save", "open", "delete file",
        "system", "computer", "disk", "memory", "cpu",
    ],
    AgentCategory.BROWSER: [
        "browse", "website", "webpage", "web page", "navigate",
        "click", "scroll", "open website", "go to",
    ],
}


# Tool name to category mapping
TOOL_CATEGORIES = {
    # Travel
    "search_flights_all_platforms": AgentCategory.TRAVEL,
    "search_trains_all_platforms": AgentCategory.TRAVEL,
    "find_cheapest_travel_option": AgentCategory.TRAVEL,
    "get_travel_deals_and_coupons": AgentCategory.TRAVEL,
    "check_pnr_status": AgentCategory.TRAVEL,
    "get_train_status": AgentCategory.TRAVEL,
    "search_trains": AgentCategory.TRAVEL,
    "get_station_code": AgentCategory.TRAVEL,
    "get_flight_status": AgentCategory.TRAVEL,
    "get_flight_by_route": AgentCategory.TRAVEL,
    "get_airport_info": AgentCategory.TRAVEL,
    "track_flight_live": AgentCategory.TRAVEL,
    
    # Communication
    "send_email": AgentCategory.COMMUNICATION,
    "read_recent_emails": AgentCategory.COMMUNICATION,
    
    # Productivity
    "create_calendar_event": AgentCategory.PRODUCTIVITY,
    "list_calendar_events": AgentCategory.PRODUCTIVITY,
    "delete_calendar_event": AgentCategory.PRODUCTIVITY,
    "create_task": AgentCategory.PRODUCTIVITY,
    "list_tasks": AgentCategory.PRODUCTIVITY,
    "complete_task": AgentCategory.PRODUCTIVITY,
    "delete_task": AgentCategory.PRODUCTIVITY,
    "create_note": AgentCategory.PRODUCTIVITY,
    "list_notes": AgentCategory.PRODUCTIVITY,
    "read_note": AgentCategory.PRODUCTIVITY,
    "search_notes": AgentCategory.PRODUCTIVITY,
    "delete_note": AgentCategory.PRODUCTIVITY,
    
    # Developer
    "github_list_repos": AgentCategory.DEVELOPER,
    "github_list_issues": AgentCategory.DEVELOPER,
    "github_create_issue": AgentCategory.DEVELOPER,
    "github_search_repos": AgentCategory.DEVELOPER,
    "python_repl": AgentCategory.DEVELOPER,
    
    # Media
    "get_youtube_transcript": AgentCategory.MEDIA,
    "get_youtube_video_info": AgentCategory.MEDIA,
    "search_youtube": AgentCategory.MEDIA,
    "transcribe_audio": AgentCategory.MEDIA,
    "extract_pdf_text": AgentCategory.MEDIA,
    "create_pdf": AgentCategory.MEDIA,
    "ocr_image": AgentCategory.MEDIA,
    "read_csv": AgentCategory.MEDIA,
    "write_csv": AgentCategory.MEDIA,
    "read_excel": AgentCategory.MEDIA,
    "write_excel": AgentCategory.MEDIA,
    "read_json": AgentCategory.MEDIA,
    "write_json": AgentCategory.MEDIA,
    "markdown_to_html": AgentCategory.MEDIA,
    "generate_qr_code": AgentCategory.MEDIA,
    
    # Research
    "web_search": AgentCategory.RESEARCH,
    "fetch_webpage": AgentCategory.RESEARCH,
    "wikipedia_search": AgentCategory.RESEARCH,
    "define_word": AgentCategory.RESEARCH,
    "get_synonyms": AgentCategory.RESEARCH,
    "get_antonyms": AgentCategory.RESEARCH,
    "translate_word": AgentCategory.RESEARCH,
    
    # System
    "take_screenshot": AgentCategory.SYSTEM,
    "send_push_notification": AgentCategory.SYSTEM,
    "get_system_info": AgentCategory.SYSTEM,
    "list_directory": AgentCategory.SYSTEM,
    "read_file": AgentCategory.SYSTEM,
    "write_file": AgentCategory.SYSTEM,
}


def classify_intent(query: str) -> Tuple[AgentCategory, float]:
    """
    Classify user query to determine which agent should handle it.
    
    Args:
        query: User's message
        
    Returns:
        Tuple of (AgentCategory, confidence_score)
    """
    query_lower = query.lower()
    
    # Count keyword matches for each category
    scores = {cat: 0 for cat in AgentCategory}
    
    for category, keywords in AGENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                # Longer keywords get higher scores
                scores[category] += len(keyword.split())
    
    # Find the highest scoring category
    max_category = max(scores, key=scores.get)
    max_score = scores[max_category]
    
    # Calculate confidence (0-1)
    total_score = sum(scores.values())
    confidence = max_score / total_score if total_score > 0 else 0
    
    # If no clear winner, return GENERAL
    if max_score < 2 or confidence < 0.3:
        return AgentCategory.GENERAL, 0.0
    
    return max_category, confidence


def get_agent_for_query(query: str) -> Dict:
    """
    Determine which agent should handle a query and return routing info.
    
    Args:
        query: User's message
        
    Returns:
        Dict with agent info and routing decision
    """
    category, confidence = classify_intent(query)
    
    agent_info = {
        AgentCategory.TRAVEL: {
            "name": "TravelAgent",
            "description": "Handles flights, trains, travel planning, price comparison",
            "icon": "🧳"
        },
        AgentCategory.COMMUNICATION: {
            "name": "CommunicationAgent",
            "description": "Handles emails and notifications",
            "icon": "📧"
        },
        AgentCategory.PRODUCTIVITY: {
            "name": "ProductivityAgent",
            "description": "Handles calendar, tasks, notes, reminders",
            "icon": "📅"
        },
        AgentCategory.DEVELOPER: {
            "name": "DeveloperAgent",
            "description": "Handles GitHub, coding, Python execution",
            "icon": "💻"
        },
        AgentCategory.MEDIA: {
            "name": "MediaAgent",
            "description": "Handles YouTube, audio, documents, data files",
            "icon": "🎬"
        },
        AgentCategory.RESEARCH: {
            "name": "ResearchAgent",
            "description": "Handles web search, Wikipedia, dictionary",
            "icon": "🔍"
        },
        AgentCategory.SYSTEM: {
            "name": "SystemAgent",
            "description": "Handles files, screenshots, system operations",
            "icon": "🖥️"
        },
        AgentCategory.BROWSER: {
            "name": "BrowserAgent",
            "description": "Handles web browsing and automation",
            "icon": "🌐"
        },
        AgentCategory.GENERAL: {
            "name": "Orion",
            "description": "Main agent - handles general queries",
            "icon": "🤖"
        },
    }
    
    return {
        "category": category,
        "confidence": confidence,
        "agent": agent_info.get(category, agent_info[AgentCategory.GENERAL]),
        "should_delegate": confidence > 0.5 and category != AgentCategory.GENERAL
    }


def list_all_capabilities() -> str:
    """
    Return a formatted string of all Orion capabilities organized by category.
    """
    output = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                          ORION AI CAPABILITIES                                ║
╠══════════════════════════════════════════════════════════════════════════════╣

🧳 TRAVEL AGENT
   • Search flights across MakeMyTrip, Goibibo, Cleartrip, ixigo
   • Search trains on IRCTC, ixigo Trains, Paytm, ConfirmTkt
   • Compare prices across all travel modes (flight/train/bus)
   • Find cheapest travel option for any route
   • Get current deals, coupons, and discount codes
   • Check PNR status with confirmation probability
   • Track live train running status
   • Track live flight status and location
   • Get airport/station information

📧 COMMUNICATION AGENT
   • Send emails via Gmail
   • Read recent emails from inbox
   • Email notifications via proactive module

📅 PRODUCTIVITY AGENT
   • Create/list/delete Google Calendar events
   • Multi-level reminders (30/15/5 min before)
   • Create/list/complete/delete tasks
   • Create/list/read/search/delete notes
   • Morning digest with daily schedule

💻 DEVELOPER AGENT
   • List GitHub repositories
   • Search GitHub repos
   • Create/view GitHub issues
   • Execute Python code (REPL)
   • Code assistance and debugging

🎬 MEDIA AGENT
   • Get YouTube video transcripts
   • Search YouTube videos
   • Get video information
   • Transcribe audio files (Whisper)
   • Extract text from PDF
   • Create PDF documents
   • OCR: Extract text from images
   • Read/write CSV files
   • Read/write Excel files
   • Read/write JSON files
   • Convert Markdown to HTML
   • Generate QR codes

🔍 RESEARCH AGENT
   • Web search (Google, DuckDuckGo)
   • Fetch and parse webpages
   • Wikipedia search
   • Word definitions
   • Synonyms and antonyms
   • Word translation

🖥️ SYSTEM AGENT
   • Take screenshots
   • Send push notifications
   • Get system information
   • List directories
   • Read/write files

🌐 BROWSER AGENT (when available)
   • Navigate to URLs
   • Click elements
   • Type text
   • Take browser screenshots
   • Get page content

╚══════════════════════════════════════════════════════════════════════════════╝
"""
    return output


if __name__ == "__main__":
    # Test classification
    test_queries = [
        "Find cheapest flight from Delhi to Mumbai tomorrow",
        "Send an email to john@example.com",
        "Set a reminder for 5 PM today",
        "Search GitHub for Python projects",
        "Get the transcript of this YouTube video",
        "What is the meaning of serendipity?",
        "Take a screenshot",
        "What's the weather today?",
        "Check PNR status 1234567890",
        "Compare train and flight prices to Bangalore"
    ]
    
    print("Testing Intent Classification:\n")
    for query in test_queries:
        result = get_agent_for_query(query)
        print(f"Query: {query}")
        print(f"  -> {result['agent']['icon']} {result['agent']['name']} (confidence: {result['confidence']:.2f})")
        print(f"  -> Delegate: {result['should_delegate']}")
        print()
