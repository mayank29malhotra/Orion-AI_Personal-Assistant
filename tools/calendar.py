"""
Calendar Tools for Orion
Google Calendar integration for event management.
Works with HuggingFace Spaces via environment secrets.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger("Orion")

# HuggingFace Spaces detection
IS_HF_SPACE = os.path.exists("/data") or os.getenv("SPACE_ID")


def _get_google_service():
    """Get Google Calendar service. Supports both local files and HF Secrets."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = None
        
        # Paths for local development
        token_path = 'google_cred/token.json'
        creds_path = 'google_cred/credentials.json'
        
        # Check for token in environment (HuggingFace Secrets)
        token_json_env = os.getenv("GOOGLE_CALENDAR_TOKEN_JSON")
        
        if token_json_env:
            # Use token from HF Secrets
            logger.info("Using Google Calendar token from environment secret")
            token_data = json.loads(token_json_env)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        elif os.path.exists(token_path):
            # Use local token file
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed token
                if token_json_env:
                    logger.info("Token refreshed. Update GOOGLE_CALENDAR_TOKEN_JSON secret with new token.")
                else:
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
            else:
                # Need new authorization
                if IS_HF_SPACE:
                    return None, "❌ Google Calendar not configured. Add GOOGLE_CALENDAR_TOKEN_JSON secret in HF Space settings. Generate token locally first with: python -c 'from tools.calendar import generate_token; generate_token()'"
                
                if not os.path.exists(creds_path):
                    return None, "❌ Google credentials not found. Please add credentials.json to google_cred/"
                
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        
        return build('calendar', 'v3', credentials=creds), None
    
    except Exception as e:
        return None, f"❌ Google Calendar setup failed: {str(e)}"


def generate_token():
    """
    Generate Google Calendar token locally. 
    Run this once locally, then copy token.json content to HF Secrets.
    """
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds_path = 'google_cred/credentials.json'
    token_path = 'google_cred/token.json'
    
    if not os.path.exists(creds_path):
        print("❌ credentials.json not found in google_cred/")
        print("Download from: https://console.cloud.google.com/apis/credentials")
        return
    
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    
    print("✅ Token generated successfully!")
    print(f"\n📋 Copy this to HuggingFace Secret (GOOGLE_CALENDAR_TOKEN_JSON):\n")
    with open(token_path, 'r') as f:
        print(f.read())


@tool
def create_calendar_event(
    title: str,
    start_time: str,
    end_time: Optional[str] = None,
    description: str = "",
    location: str = ""
) -> str:
    """
    Create a Google Calendar event.
    
    Args:
        title: Event title
        start_time: Start time in ISO format (YYYY-MM-DDTHH:MM:SS) or natural language
        end_time: End time (optional, defaults to 1 hour after start)
        description: Event description
        location: Event location
    """
    try:
        service, error = _get_google_service()
        if error:
            return error
        
        # Parse start time
        try:
            start_dt = datetime.fromisoformat(start_time)
        except:
            # Try common formats
            start_dt = None
            for fmt in ["%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M"]:
                try:
                    start_dt = datetime.strptime(start_time, fmt)
                    break
                except:
                    continue
            if not start_dt:
                return f"❌ Could not parse start time: {start_time}. Use format: YYYY-MM-DDTHH:MM:SS"
        
        # Parse or calculate end time
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time)
            except:
                end_dt = start_dt + timedelta(hours=1)
        else:
            end_dt = start_dt + timedelta(hours=1)
        
        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        
        logger.info(f"Calendar event created: {title}")
        return f"✅ Event created: {title}\n🔗 Link: {event.get('htmlLink')}"
    
    except Exception as e:
        error_msg = f"Failed to create calendar event: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def list_calendar_events(days_ahead: int = 7, max_results: int = 10) -> str:
    """
    List upcoming calendar events.
    
    Args:
        days_ahead: Number of days to look ahead (default 7)
        max_results: Maximum number of events to return (default 10)
    """
    try:
        # Convert to int in case LLM passes strings
        days_ahead = int(days_ahead)
        max_results = int(max_results)
        
        service, error = _get_google_service()
        if error:
            return error
        
        now = datetime.utcnow()
        time_min = now.isoformat() + 'Z'
        time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"📅 No upcoming events in the next {days_ahead} days"
        
        events_text = [f"📅 Upcoming Events (next {days_ahead} days):"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', 'No title')
            location = event.get('location', '')
            
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                start_formatted = start_dt.strftime("%a %b %d, %Y at %I:%M %p")
            except:
                start_formatted = start
            
            event_str = f"\n🗓️ {title}\n   📍 When: {start_formatted}"
            if location:
                event_str += f"\n   📌 Where: {location}"
            events_text.append(event_str)
        
        logger.info(f"Retrieved {len(events)} calendar events")
        return "\n".join(events_text)
    
    except Exception as e:
        error_msg = f"Failed to list calendar events: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def delete_calendar_event(event_id: str) -> str:
    """
    Delete a calendar event by ID.
    
    Args:
        event_id: The Google Calendar event ID
    """
    try:
        service, error = _get_google_service()
        if error:
            return error
        
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        logger.info(f"Calendar event deleted: {event_id}")
        return f"✅ Event deleted successfully"
    
    except Exception as e:
        error_msg = f"Failed to delete event: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def get_calendar_tools():
    """Get all calendar-related tools."""
    return [
        create_calendar_event,
        list_calendar_events,
        delete_calendar_event,
    ]
