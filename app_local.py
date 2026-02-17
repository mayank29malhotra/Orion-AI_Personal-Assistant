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


async def chat(message: str, history: list, success_criteria: str):
    """
    Process a user message through Orion.
    Uses Gradio's native async support — no asyncio.run() hacks.
    """
    global orion_instance

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
                    ["What's on my calendar today?"],
                    ["Search YouTube for Python async tutorials"],
                    ["Check PNR status 1234567890"],
                    ["Define the word 'serendipity'"],
                    ["Search GitHub for LangGraph projects"],
                    ["Create a note about today's standup"],
                    ["What flights go from Delhi to Mumbai?"],
                    ["Read my recent emails"],
                ],
                inputs=[msg],
                label="",
            )

    # ── Event Wiring ──
    send_args = dict(fn=chat, inputs=[msg, chatbot, criteria], outputs=[chatbot, stats_bar])
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
