"""
Productivity Agent for Orion
============================

Specialized sub-agent for calendar, tasks, notes, and reminders.

Capabilities:
- Google Calendar event management
- Task creation and tracking
- Note-taking and search
- Reminder scheduling
"""

from typing import List, Optional
from langchain_core.tools import tool, BaseTool

from agents.base_agent import BaseSubAgent


class ProductivityAgent(BaseSubAgent):
    """
    Productivity Agent - handles calendar, tasks, notes, and reminders.
    
    This agent specializes in:
    - Creating and managing Google Calendar events
    - Task management with priorities and due dates
    - Note-taking with markdown support
    - Setting up reminders
    """
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        if tools is None:
            tools = get_productivity_agent_tools()
        super().__init__(tools)
    
    def get_system_prompt(self) -> str:
        return """You are the Productivity Agent, a specialized sub-agent of Orion AI.
Your expertise is in managing calendar events, tasks, notes, and reminders.

🎯 YOUR CAPABILITIES:

📅 CALENDAR MANAGEMENT:
- Create events with title, date/time, description, location
- List upcoming events for any time range
- Delete or modify calendar events
- Handle recurring events
- Set reminders (30/15/5 minutes before)

✅ TASK MANAGEMENT:
- Create tasks with title, description, due date, priority
- List all tasks or filter by status/priority
- Mark tasks as complete
- Delete tasks
- Priority levels: low (🟢), medium (🟡), high (🔴)

📝 NOTE MANAGEMENT:
- Create notes with markdown formatting
- List all notes
- Read specific notes
- Search notes by content
- Delete notes

⏰ TIME HANDLING:
- Current timezone: IST (Indian Standard Time, UTC+5:30)
- When user says "tomorrow", calculate the actual date
- When user says "5 PM", interpret as 17:00 IST
- For calendar events, always use ISO format: YYYY-MM-DDTHH:MM:SS

💡 BEST PRACTICES:
- Confirm event details before creating
- Suggest appropriate priorities for tasks
- Keep note titles descriptive
- For recurring events, clarify the frequency

🔧 AVAILABLE TOOLS:
- create_calendar_event: Create a new calendar event
- list_calendar_events: List upcoming events
- delete_calendar_event: Delete an event by ID
- create_task: Create a new task
- list_tasks: View all tasks
- complete_task: Mark task as done
- delete_task: Remove a task
- create_note: Save a new note
- list_notes: View all notes
- read_note: Read note content
- search_notes: Find notes by keyword
- delete_note: Remove a note
"""

    def get_capabilities(self) -> List[str]:
        return [
            "Create Google Calendar events",
            "List upcoming calendar events",
            "Delete calendar events",
            "Create tasks with priorities",
            "List and filter tasks",
            "Complete tasks",
            "Delete tasks",
            "Create markdown notes",
            "List all notes",
            "Read note content",
            "Search notes by keyword",
            "Delete notes",
            "Schedule reminders"
        ]


def get_productivity_agent_tools() -> List[BaseTool]:
    """Get all tools for the Productivity Agent."""
    from tools.calendar import (
        create_calendar_event,
        list_calendar_events,
        delete_calendar_event
    )
    from tools.tasks_notes import (
        create_task,
        list_tasks,
        complete_task,
        delete_task,
        create_note,
        list_notes,
        read_note,
        search_notes,
        delete_note
    )
    
    return [
        # Calendar tools
        create_calendar_event,
        list_calendar_events,
        delete_calendar_event,
        # Task tools
        create_task,
        list_tasks,
        complete_task,
        delete_task,
        # Note tools
        create_note,
        list_notes,
        read_note,
        search_notes,
        delete_note,
    ]


# Additional productivity tools
@tool
def get_daily_summary() -> str:
    """
    Get a summary of today's events and pending tasks.
    
    Returns:
        Combined summary of calendar events and tasks for today
    """
    from datetime import datetime, timedelta
    from tools.calendar import list_calendar_events
    from tools.tasks_notes import list_tasks
    
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Get today's events
    events_result = list_calendar_events.invoke({
        "days": 1,
        "max_results": 10
    })
    
    # Get pending tasks
    tasks_result = list_tasks.invoke({
        "show_completed": False
    })
    
    summary = f"""
📊 DAILY SUMMARY - {today}
══════════════════════════════════════════

📅 TODAY'S EVENTS:
{events_result}

✅ PENDING TASKS:
{tasks_result}

══════════════════════════════════════════
💡 Have a productive day!
"""
    return summary


@tool
def quick_reminder(reminder_text: str, minutes_from_now: int = 30) -> str:
    """
    Set a quick reminder for the near future.
    
    Args:
        reminder_text: What to remind about
        minutes_from_now: Minutes from now (default 30)
        
    Returns:
        Confirmation of reminder setup
    """
    from datetime import datetime, timedelta
    from tools.calendar import create_calendar_event
    
    # Calculate reminder time
    reminder_time = datetime.now() + timedelta(minutes=minutes_from_now)
    start_time = reminder_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_time = (reminder_time + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%S")
    
    result = create_calendar_event.invoke({
        "summary": f"⏰ Reminder: {reminder_text}",
        "start_time": start_time,
        "end_time": end_time,
        "description": f"Quick reminder set via Orion\n\nReminder: {reminder_text}"
    })
    
    return f"""
⏰ REMINDER SET
══════════════════════════════════════════

📝 Reminder: {reminder_text}
⏰ Time: {reminder_time.strftime("%I:%M %p")} ({minutes_from_now} minutes from now)

{result}
"""


@tool
def create_meeting(
    title: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    attendees: str = "",
    location: str = ""
) -> str:
    """
    Create a meeting event with common defaults.
    
    Args:
        title: Meeting title
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format (24-hour)
        duration_minutes: Meeting duration (default 60)
        attendees: Comma-separated list of attendee emails
        location: Meeting location or video link
        
    Returns:
        Confirmation of meeting creation
    """
    from datetime import datetime, timedelta
    from tools.calendar import create_calendar_event
    
    # Parse and format times
    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    
    start_time = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    end_time = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
    
    # Build description
    description_parts = [f"Meeting: {title}"]
    if attendees:
        description_parts.append(f"Attendees: {attendees}")
    if location:
        description_parts.append(f"Location: {location}")
    
    result = create_calendar_event.invoke({
        "summary": f"📅 {title}",
        "start_time": start_time,
        "end_time": end_time,
        "description": "\n".join(description_parts),
        "location": location
    })
    
    return f"""
📅 MEETING SCHEDULED
══════════════════════════════════════════

📌 Title: {title}
📆 Date: {start_dt.strftime("%A, %B %d, %Y")}
⏰ Time: {start_dt.strftime("%I:%M %p")} - {end_dt.strftime("%I:%M %p")}
⏱️ Duration: {duration_minutes} minutes
{f"📍 Location: {location}" if location else ""}
{f"👥 Attendees: {attendees}" if attendees else ""}

{result}
"""


if __name__ == "__main__":
    # Test the agent
    agent = ProductivityAgent()
    print("Productivity Agent initialized")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print(f"\nCapabilities:\n" + "\n".join(f"  • {c}" for c in agent.get_capabilities()))
