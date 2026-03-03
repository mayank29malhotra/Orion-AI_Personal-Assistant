#!/usr/bin/env python3
"""
Orion AI Assistant - Local Gradio UI for Testing
=================================================
A clean Gradio web interface for testing Orion locally.

Usage:
    python app_local.py
    # Opens at http://localhost:7860
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment
from dotenv import load_dotenv
load_dotenv(override=True)

import gradio as gr

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OrionUI")

# Suppress noisy HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ── Global State ────────────────────────────────────────────────────────────

orion_instance = None
session_stats = {
    "messages_sent": 0,
    "tools_used": 0,
    "session_start": None,
    "last_agent": "N/A",
    "errors": 0,
}


# ── Core Functions ──────────────────────────────────────────────────────────

async def initialize_orion():
    """Initialize Orion agent (called once on startup)."""
    global orion_instance
    try:
        from core.agent import Orion
        from core.config import Config

        Config.ensure_directories()
        orion_instance = Orion()
        await orion_instance.setup()
        session_stats["session_start"] = datetime.now()
        logger.info("Orion initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Orion: {e}")
        import traceback; traceback.print_exc()
        return False


async def chat(message: str, history: list, success_criteria: str, upload_files=None):
    """
    Process a user message through Orion.
    Uses Gradio's native async support — no asyncio.run() hacks.
    """
    global orion_instance

    # If files were uploaded, append their paths to the message so Orion can reference them
    if upload_files:
        paths = []
        for f in upload_files:
            # Gradio gives a tempfile path
            paths.append(f.name if hasattr(f, 'name') else str(f))
        files_str = "\n\nAttached files: " + ", ".join(paths)
        message = (message or "") + files_str

    if not message.strip():
        yield history, stats_text()
        return

    # Lazy-init Orion on first message
    if orion_instance is None:
        yield history + [[message, "⏳ Initializing Orion (first message takes ~10s)..."]], stats_text()
        ok = await initialize_orion()
        if not ok:
            yield history + [[message, "❌ Failed to initialize Orion. Check your API keys in `.env`."]], stats_text()
            return

    # Classify intent (for display only)
    try:
        from agents.router import get_agent_for_query
        routing = get_agent_for_query(message)
        agent_name = routing["agent"]["icon"] + " " + routing["agent"]["name"]
        session_stats["last_agent"] = agent_name
    except Exception:
        session_stats["last_agent"] = "🤖 Orion"

    # Show "thinking" state
    yield history + [[message, "🤔 Thinking..."]], stats_text()

    try:
        # Convert Gradio history → Orion format
        orion_history = []
        for h in (history or []):
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                orion_history.append([h[0], h[1]])

        results = await orion_instance.run_superstep(
            message,
            success_criteria=success_criteria or "The answer should be clear and accurate",
            history=orion_history,
            user_id="local_user",
            channel="gradio_local",
        )

        # Extract assistant reply
        if results and len(results) > 0:
            last = results[-1]
            if isinstance(last, (list, tuple)) and len(last) > 1:
                response = last[1]
            else:
                response = str(last)

        # Post-process response to linkify file paths / attachments
        import re
        def linkify(text: str) -> str:
            # find paths ending with common extensions
            pattern = r"((?:[A-Za-z]:\\|/)?(?:[\w\-./ ]+)[\\/][\w\-./ ]+\.(?:png|jpg|jpeg|gif|pdf|txt|html))"
            def repl(m):
                path = m.group(1)
                esc = path.replace('\\', '/')
                if esc.lower().endswith(('.png','.jpg','.jpeg','.gif')):
                    return f"![{os.path.basename(path)}](file://{esc})"
                else:
                    return f"[{os.path.basename(path)}](file://{esc})"
            return re.sub(pattern, repl, text)
        try:
            response = linkify(response)
        except Exception:
            pass
        else:
            response = "Processed but no response generated."

        session_stats["messages_sent"] += 1
        session_stats["tools_used"] = orion_instance.get_tool_usage_count()

        yield history + [[message, response]], stats_text()

    except Exception as e:
        session_stats["errors"] += 1
        logger.error(f"Error: {e}")
        import traceback; traceback.print_exc()
        yield history + [[message, f"❌ Error: {str(e)}"]], stats_text()


def stats_text() -> str:
    """Format session statistics for display."""
    uptime = ""
    if session_stats["session_start"]:
        delta = datetime.now() - session_stats["session_start"]
        mins = int(delta.total_seconds() // 60)
        uptime = f"{mins}m" if mins > 0 else "<1m"

    return (
        f"💬 Messages: {session_stats['messages_sent']}  |  "
        f"🔧 Tools: {session_stats['tools_used']}  |  "
        f"🤖 Agent: {session_stats['last_agent']}  |  "
        f"❌ Errors: {session_stats['errors']}  |  "
        f"⏱️ Uptime: {uptime or 'N/A'}"
    )


async def reset_session():
    """Reset Orion and clear history."""
    global orion_instance
    if orion_instance:
        try:
            orion_instance.cleanup()
        except Exception:
            pass
    orion_instance = None
    session_stats.update({"messages_sent": 0, "tools_used": 0, "errors": 0, "session_start": None, "last_agent": "N/A"})
    return [], "", stats_text()


def export_chat(history):
    """Export conversation to JSON file."""
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"sandbox/chat_export_{ts}.json"
        os.makedirs("sandbox", exist_ok=True)
        data = {
            "exported_at": datetime.now().isoformat(),
            "messages": session_stats["messages_sent"],
            "tools_used": session_stats["tools_used"],
            "conversation": history,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return f"✅ Saved to {path}"
    except Exception as e:
        return f"❌ Export failed: {e}"


# ── Gradio UI ───────────────────────────────────────────────────────────────

CSS = """
.header { text-align:center; margin-bottom:10px; }
.header h1 { background: linear-gradient(135deg,#667eea,#764ba2);
             -webkit-background-clip:text; -webkit-text-fill-color:transparent;
             font-size:2.2em; margin:0; }
.stat-bar { background: linear-gradient(135deg,#667eea22,#764ba222);
            border-radius:8px; padding:8px 16px; font-size:0.9em; }
footer { display:none !important; }
"""

with gr.Blocks(
    title="Orion AI - Local Test",
    css=CSS,
    theme=gr.themes.Soft(primary_hue="purple"),
) as demo:

    # ── Header ──
    gr.HTML('<div class="header"><h1>🌟 Orion AI Personal Assistant</h1></div>')
    gr.Markdown("**Local Test Mode** — all tools available, no Telegram needed.", elem_classes=["header"])

    # ── Stats bar ──
    stats_bar = gr.Markdown(stats_text(), elem_classes=["stat-bar"])

    # ── Main layout ──
    with gr.Row():
        # Left: Chat
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="Chat",
                height=520,
                show_copy_button=True,
                type="tuples",
            )

            with gr.Group():
                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Ask Orion anything… (Enter to send)",
                        show_label=False,
                        lines=2,
                        scale=8,
                    )
                    upload_files = gr.File(label="📎 Attach Files", file_count="multiple", file_types=[".pdf", ".csv", ".xlsx", ".json", ".txt", ".png", ".jpg"])
                    send_btn = gr.Button("🚀 Send", variant="primary", scale=1)

                criteria = gr.Textbox(
                    placeholder="🎯 Optional success criteria (what makes a perfect answer?)",
                    show_label=False,
                    lines=1,
                )

            with gr.Row():
                reset_btn = gr.Button("🔄 Reset", variant="stop", size="sm")
                export_btn = gr.Button("💾 Export", variant="secondary", size="sm")
                export_status = gr.Textbox(show_label=False, interactive=False, scale=2)

        # Right: Info panel
        with gr.Column(scale=1, min_width=260):
            gr.Markdown("### 🛠️ Available Tools")
            with gr.Accordion("Productivity", open=False):
                gr.Markdown("📧 Email (Send/Read)\n📅 Google Calendar\n✅ Tasks & Reminders\n📝 Notes")
            with gr.Accordion("Documents", open=False):
                gr.Markdown("📄 PDF Read/Write\n🔍 OCR\n📊 CSV/Excel\n📋 JSON\n📝 Markdown\n🔲 QR Codes")
            with gr.Accordion("Research", open=False):
                gr.Markdown("🌐 Web Search\n📖 Wikipedia\n📚 Dictionary\n🌍 Webpage Fetch")
            with gr.Accordion("Media", open=False):
                gr.Markdown("🎬 YouTube Search/Transcript\n🎙️ Audio Transcription")
            with gr.Accordion("Developer", open=False):
                gr.Markdown("💻 GitHub (Repos/Issues/PRs)\n🐍 Python REPL")
            with gr.Accordion("Travel", open=False):
                gr.Markdown("✈️ Flight Status/Tracking\n🚂 Indian Railways (PNR/Status)\n🔍 Route Search")
            with gr.Accordion("System", open=False):
                gr.Markdown("📸 Screenshots\n📱 Push Notifications\n🌐 Browser Automation\n📂 File Operations")

            gr.Markdown("---")
            gr.Markdown("### 💡 Try These")
            gr.Examples(
                examples=[
                    ["Send an email to test@example.com with subject 'Hello' and body 'This is a test'."],
                    ["Create a Google Calendar event for tomorrow at 10am titled 'Standup'."],
                    ["List my upcoming calendar events."],
                    ["Create a task to 'Buy groceries'."],
                    ["List my tasks."],
                    ["Mark the task 'Buy groceries' as complete."],
                    ["Create a note saying 'Meeting notes: Discuss project alpha'."],
                    ["List my notes."],
                    ["Read the note titled 'Meeting notes: Discuss project alpha'."],
                    ["Search my notes for the word 'project'."],
                    ["Read my recent emails."],
                    ["Read the PDF file sample.pdf."],
                    ["Create a PDF document containing the text 'Hello from Orion'."],
                    ["Perform OCR on the image sample.jpg."],
                    ["Read the CSV file data.csv."],
                    ["Read the Excel file workbook.xlsx."],
                    ["Read the JSON file config.json."],
                    ["Convert this markdown to HTML: '# Title\nThis is a test'."],
                    ["Generate a QR code for the text 'https://example.com'."],
                    ["Search the web for 'latest artificial intelligence news'."],
                    ["Fetch the webpage https://example.com and summarize it."],
                    ["Search Wikipedia for 'Python (programming language)'."],
                    ["Define the word 'serendipity'."],
                    ["Give me synonyms for 'happy'."],
                    ["Translate 'hello' into Spanish."],
                    ["Search YouTube for 'python tutorial'."],
                    ["Get the transcript of the YouTube video https://www.youtube.com/watch?v=dQw4w9WgXcQ."],
                    ["Get information about the YouTube video with ID dQw4w9WgXcQ."],
                    ["Transcribe this audio file sample.mp3."],
                    ["List my GitHub repositories."],
                    ["Search GitHub for repositories about 'langchain'."],
                    ["List issues in the repository copilot/orion."],
                    ["Create a GitHub issue in copilot/orion titled 'Test issue' with body 'This is a test'."],
                    ["Execute python code: print('Hello from Python')"],
                    ["Check PNR status 1234567890."],
                    ["Get current train status for train 12345."],
                    ["Search trains from Delhi to Mumbai tomorrow."],
                    ["Get station code for New Delhi."],
                    ["Get flight status for AI101."],
                    ["Find flights from New York to London on 2026-04-01."],
                    ["Get airport information for JFK."],
                    ["Track flight live for AI101."],
                    ["Take a screenshot."],
                    ["Send a push notification with message 'Test notification'."],
                    ["Get system information."],
                    ["List the directory contents of sandbox."],
                    ["Read the file sandbox/test_note.md."],
                    ["Write a file sandbox/hello.txt with content 'Hello world'."],
                    ["Browse to https://example.com and take a screenshot."],
                    ["Click the element with id 'login' on the current page."],
                ],
                inputs=[msg],
                label="",
            )

    # ── Event Wiring ──
    send_args = dict(fn=chat, inputs=[msg, chatbot, criteria, upload_files], outputs=[chatbot, stats_bar])
    msg.submit(**send_args).then(lambda: "", outputs=[msg])
    send_btn.click(**send_args).then(lambda: "", outputs=[msg])
    reset_btn.click(reset_session, outputs=[chatbot, msg, stats_bar])
    export_btn.click(export_chat, inputs=[chatbot], outputs=[export_status])


# ── Launch ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Orion Local Gradio UI")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true", help="Create public link")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🌟  ORION AI PERSONAL ASSISTANT - LOCAL TEST MODE")
    print("=" * 60)
    print(f"🌐  Open http://localhost:{args.port}")
    print("📝  Orion initializes on your FIRST message (saves startup time)")
    print("=" * 60 + "\n")

    demo.launch(
        server_name="127.0.0.1",
        server_port=args.port,
        share=args.share,
        show_error=True,
    )
