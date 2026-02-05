"""
Communication Agent for Orion
=============================

Specialized sub-agent for handling email and notification tasks.

Capabilities:
- Send emails via Gmail SMTP
- Read recent emails from inbox
- Handle notification requests
"""

from typing import List, Optional
from langchain_core.tools import tool, BaseTool

from agents.base_agent import BaseSubAgent


class CommunicationAgent(BaseSubAgent):
    """
    Communication Agent - handles email and notifications.
    
    This agent specializes in:
    - Sending emails with optional attachments
    - Reading and summarizing inbox emails
    - Composing professional email responses
    """
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        if tools is None:
            tools = get_communication_agent_tools()
        super().__init__(tools)
    
    def get_system_prompt(self) -> str:
        return """You are the Communication Agent, a specialized sub-agent of Orion AI.
Your expertise is in handling all communication-related tasks.

🎯 YOUR CAPABILITIES:
1. SEND EMAILS - Compose and send emails via Gmail
   - Professional formatting
   - Subject line optimization
   - Attachment support
   
2. READ EMAILS - Check and summarize inbox
   - Fetch recent emails
   - Filter unread messages
   - Summarize important emails

📧 EMAIL COMPOSITION GUIDELINES:
- Always use professional tone unless specified otherwise
- Keep subject lines concise but descriptive
- Structure body with proper greeting, content, and signature
- Ask for confirmation before sending important emails

🔧 AVAILABLE TOOLS:
- send_email: Send an email to specified recipient
- read_recent_emails: Fetch recent emails from inbox

⚠️ IMPORTANT:
- Never expose email credentials
- Confirm recipient address before sending
- For bulk emails, process one at a time
- Report delivery status clearly

Current timezone: IST (Indian Standard Time)
"""

    def get_capabilities(self) -> List[str]:
        return [
            "Send emails via Gmail SMTP",
            "Read recent emails from inbox",
            "Compose professional emails",
            "Handle email attachments",
            "Summarize inbox contents",
            "Filter unread emails"
        ]


# Import existing email tools
def get_communication_agent_tools() -> List[BaseTool]:
    """Get all tools for the Communication Agent."""
    from tools.email_tools import send_email, read_recent_emails
    
    return [
        send_email,
        read_recent_emails,
    ]


# Standalone tools that can be used without the full agent
@tool
def compose_email_draft(
    to: str,
    subject: str,
    key_points: str,
    tone: str = "professional"
) -> str:
    """
    Compose an email draft based on key points.
    
    Args:
        to: Recipient email address
        subject: Email subject
        key_points: Main points to include in the email (comma-separated)
        tone: Email tone - professional, casual, formal, friendly
        
    Returns:
        Formatted email draft ready for review
    """
    points = [p.strip() for p in key_points.split(',')]
    
    # Generate greeting based on tone
    greetings = {
        "professional": "Dear recipient,",
        "casual": "Hi there,",
        "formal": "Dear Sir/Madam,",
        "friendly": "Hey!"
    }
    
    closings = {
        "professional": "Best regards,",
        "casual": "Cheers,",
        "formal": "Yours faithfully,",
        "friendly": "Take care,"
    }
    
    greeting = greetings.get(tone, greetings["professional"])
    closing = closings.get(tone, closings["professional"])
    
    # Build email body
    body_points = "\n".join([f"• {point}" for point in points])
    
    draft = f"""
📧 EMAIL DRAFT
══════════════════════════════════════════

To: {to}
Subject: {subject}

{greeting}

{body_points}

{closing}
[Your name]

══════════════════════════════════════════
⚠️ Review and use send_email tool to send this draft.
"""
    return draft


@tool
def get_email_summary(email_count: int = 10) -> str:
    """
    Get a summary of recent emails without full content.
    
    Args:
        email_count: Number of emails to summarize (default 10)
        
    Returns:
        Summary of recent emails with sender, subject, and date
    """
    from tools.email_tools import read_recent_emails
    
    # Get emails
    result = read_recent_emails.invoke({"count": email_count})
    
    return f"""
📬 INBOX SUMMARY
══════════════════════════════════════════

{result}

══════════════════════════════════════════
💡 Use read_recent_emails for full content
"""


if __name__ == "__main__":
    # Test the agent
    agent = CommunicationAgent()
    print("Communication Agent initialized")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print(f"\nCapabilities:\n" + "\n".join(f"  • {c}" for c in agent.get_capabilities()))
