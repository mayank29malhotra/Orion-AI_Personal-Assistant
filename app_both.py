"""
Orion AI Assistant - Main Entry Point
Runs ALL Integrations: Gradio UI + Telegram Bot + Email Bot + Scheduler
"""
import os
import sys
import asyncio
import threading
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Orion")

# Data directory - use ORION_DATA_DIR env var or default to ./data
DATA_DIR = os.getenv("ORION_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(f"{DATA_DIR}/sandbox", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/data", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/notes", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/tasks", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/temp", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/screenshots", exist_ok=True)
os.environ["ORION_DATA_DIR"] = DATA_DIR
logger.info(f"🚀 Orion starting - Data dir: {DATA_DIR}")


# ============ Background Services ============

def run_telegram_bot():
    """Run Telegram bot in a separate thread with its own event loop."""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        allowed_users = os.getenv("TELEGRAM_ALLOWED_USER_ID")
        
        if not bot_token or not allowed_users:
            logger.warning("⚠️ Telegram not configured")
            return
        
        logger.info("🤖 Starting Telegram bot in background...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from integrations.telegram import main as telegram_main
        loop.run_until_complete(telegram_main())
        
    except Exception as e:
        logger.error(f"❌ Telegram bot error: {e}")


def run_email_bot():
    """Run Email bot in a separate thread."""
    try:
        email_address = os.getenv("EMAIL_ADDRESS")
        email_password = os.getenv("EMAIL_PASSWORD")
        
        if not email_address or not email_password:
            logger.warning("⚠️ Email bot not configured")
            return
        
        logger.info("📬 Starting Email bot in background...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from integrations.email_bot import email_bot_loop
        loop.run_until_complete(email_bot_loop())
        
    except Exception as e:
        logger.error(f"❌ Email bot error: {e}")


def run_scheduler():
    """Run Scheduler in a separate thread."""
    try:
        logger.info("⏰ Starting Scheduler in background...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from integrations.scheduler import start_scheduler_loop
        loop.run_until_complete(start_scheduler_loop())
        
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")


# ============ Start Background Services ============

services_status = {
    "telegram": False,
    "email_bot": False,
    "scheduler": False
}

# Start Telegram
telegram_configured = os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_ALLOWED_USER_ID")
if telegram_configured:
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()
    services_status["telegram"] = True
    logger.info("✅ Telegram bot started")

# Start Email Bot
email_configured = os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_PASSWORD")
if email_configured:
    email_thread = threading.Thread(target=run_email_bot, daemon=True)
    email_thread.start()
    services_status["email_bot"] = True
    logger.info("✅ Email bot started")

# Start Scheduler
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()
services_status["scheduler"] = True
logger.info("✅ Scheduler started")


# Import and run Gradio UI (this blocks)
import gradio as gr
from core.agent import Orion
import json
from datetime import datetime

# Session statistics
session_stats = {
    "messages_sent": 0,
    "tools_used": 0,
    "session_start": None
}

DEFAULT_USER_ID = os.getenv("ORION_USER_ID", "gradio_user")


async def setup():
    try:
        logger.info("Gradio: Initializing Orion instance...")
        orion = Orion()
        await orion.setup()
        session_stats["session_start"] = datetime.now()
        logger.info("Gradio: Orion instance ready!")
        
        # Build status message
        status_parts = ["✅ Orion initialized"]
        if services_status["telegram"]:
            status_parts.append("📱 Telegram")
        if services_status["email_bot"]:
            status_parts.append("📬 Email Bot")
        if services_status["scheduler"]:
            status_parts.append("⏰ Scheduler")
        
        return orion, " | ".join(status_parts), 0, 0
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Setup failed: {str(e)}", 0, 0


async def process_message(orion, message, success_criteria, history, upload_files):
    if orion is None:
        # Try to initialize on-demand if setup failed
        logger.warning("Orion is None, attempting on-demand initialization...")
        try:
            orion = Orion()
            await orion.setup()
            logger.info("On-demand Orion initialization successful!")
        except Exception as e:
            logger.error(f"On-demand initialization failed: {e}")
            return [[message, f"Error: Orion failed to initialize. Please refresh the page. ({str(e)})"]], None, session_stats["messages_sent"], session_stats["tools_used"]
    
    try:
        file_context = ""
        if upload_files:
            file_context = "\n\n📎 Uploaded files:\n"
            for file in upload_files:
                file_context += f"- {file.name}\n"
            message = message + file_context
        
        results = await orion.run_superstep(
            message,
            success_criteria,
            history,
            user_id=DEFAULT_USER_ID,
            channel="gradio"
        )
        
        session_stats["messages_sent"] += 1
        session_stats["tools_used"] = orion.get_tool_usage_count()
        
        return results, orion, session_stats["messages_sent"], session_stats["tools_used"]
    except Exception as e:
        logger.error(f"Process message failed: {e}")
        return [[message, f"Error: {str(e)}"]], orion, session_stats["messages_sent"], session_stats["tools_used"]


async def reset():
    new_orion = Orion()
    await new_orion.setup()
    session_stats["messages_sent"] = 0
    session_stats["tools_used"] = 0
    session_stats["session_start"] = datetime.now()
    return "", "", None, new_orion, "🔄 Session reset", 0, 0


def export_conversation(history):
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"orion_conversation_{timestamp}.json"
        
        export_data = {
            "export_date": datetime.now().isoformat(),
            "session_start": session_stats["session_start"].isoformat() if session_stats["session_start"] else None,
            "messages_count": session_stats["messages_sent"],
            "tools_used": session_stats["tools_used"],
            "conversation": history
        }
        
        base_dir = "/data/sandbox" if IS_HF_SPACE else "sandbox"
        filepath = f"{base_dir}/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return f"✅ Exported to {filepath}"
    except Exception as e:
        return f"❌ Export failed: {str(e)}"


def free_resources(orion):
    try:
        if orion:
            orion.cleanup()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


# Build Gradio UI
custom_css = """
.header-text {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5em;
    font-weight: bold;
    text-align: center;
}
"""

with gr.Blocks(title="Orion AI Assistant", css=custom_css, theme=gr.themes.Soft(primary_hue="purple")) as ui:
    gr.HTML('<div class="header-text">🌟 Orion AI Personal Assistant 🌟</div>')
    
    # Build service status
    active_services = []
    if services_status["telegram"]:
        active_services.append("📱 Telegram")
    if services_status["email_bot"]:
        active_services.append("📬 Email Bot")
    if services_status["scheduler"]:
        active_services.append("⏰ Scheduler")
    
    services_text = " | ".join(active_services) if active_services else "No background services"
    
    gr.Markdown(f"""
    ### Your AI Co-Worker with 35+ Tools
    📧 Email | 📅 Calendar | 📝 Notes & Tasks | 📄 PDF | 🔍 OCR | 📊 Data | 🌐 Web
    
    **Active Services:** {services_text}
    """)
    
    orion = gr.State(delete_callback=free_resources)
    
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="💬 Conversation", height=400, type="tuples")
            
            with gr.Group():
                message = gr.Textbox(placeholder="💭 What would you like help with?", lines=2, show_label=False)
                upload_files = gr.File(label="📎 Attach Files", file_count="multiple", file_types=[".pdf", ".csv", ".xlsx", ".json", ".txt", ".png", ".jpg"])
                success_criteria = gr.Textbox(placeholder="🎯 Success criteria (optional)", lines=1, show_label=False)
            
            with gr.Row():
                reset_button = gr.Button("🔄 Reset", variant="stop", size="sm")
                export_button = gr.Button("💾 Export", variant="secondary", size="sm")
                go_button = gr.Button("🚀 Send", variant="primary", size="lg")
        
        with gr.Column(scale=1):
            status_box = gr.Textbox(label="Status", value="⏳ Initializing...", interactive=False)
            messages_count = gr.Number(label="💬 Messages", value=0, interactive=False)
            tools_count = gr.Number(label="🔧 Tools Used", value=0, interactive=False)
            export_status = gr.Textbox(label="Export Status", value="", interactive=False, visible=False)
    
    # Events
    ui.load(setup, [], [orion, status_box, messages_count, tools_count])
    message.submit(process_message, [orion, message, success_criteria, chatbot, upload_files], [chatbot, orion, messages_count, tools_count])
    go_button.click(process_message, [orion, message, success_criteria, chatbot, upload_files], [chatbot, orion, messages_count, tools_count])
    reset_button.click(reset, [], [message, success_criteria, chatbot, orion, status_box, messages_count, tools_count])
    export_button.click(export_conversation, [chatbot], [export_status])


# Launch
if __name__ == "__main__":
    ui.launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True)
else:
    ui.launch()
