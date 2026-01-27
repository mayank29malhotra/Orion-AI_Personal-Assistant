import os
import gradio as gr
from core.agent import Orion
import json
from datetime import datetime

# Data directory - use ORION_DATA_DIR env var or default to ./data
DATA_DIR = os.getenv("ORION_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(f"{DATA_DIR}/sandbox", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/data", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/notes", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/tasks", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/temp", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/screenshots", exist_ok=True)
os.environ["ORION_DATA_DIR"] = DATA_DIR
print(f"🚀 Orion starting - Data dir: {DATA_DIR}")


# Store session statistics
session_stats = {
    "messages_sent": 0,
    "tools_used": 0,
    "session_start": None
}

# Default user ID for Gradio
DEFAULT_USER_ID = os.getenv("ORION_USER_ID", "gradio_user")


async def setup():
    try:
        orion = Orion()
        await orion.setup()
        session_stats["session_start"] = datetime.now()
        return orion, "✅ Orion initialized successfully", 0, 0
    except Exception as e:
        print(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Setup failed: {str(e)}", 0, 0


async def process_message(orion, message, success_criteria, history, upload_files):
    if orion is None:
        return [[message, "Error: Orion failed to initialize. Please check your API keys and network connection."]], None, session_stats["messages_sent"], session_stats["tools_used"]
    
    try:
        # Handle file uploads
        file_context = ""
        if upload_files:
            file_context = "\n\n📎 Uploaded files:\n"
            for file in upload_files:
                file_context += f"- {file.name}\n"
            message = message + file_context
        
        # Run with memory persistence
        results = await orion.run_superstep(
            message,
            success_criteria,
            history,
            user_id=DEFAULT_USER_ID,
            channel="gradio"
        )
        
        # Update statistics
        session_stats["messages_sent"] += 1
        session_stats["tools_used"] = orion.get_tool_usage_count()
        
        return results, orion, session_stats["messages_sent"], session_stats["tools_used"]
    except Exception as e:
        print(f"Process message failed: {e}")
        import traceback
        traceback.print_exc()
        return [[message, f"Error: {str(e)}"]], orion, session_stats["messages_sent"], session_stats["tools_used"]


async def reset():
    new_orion = Orion()
    await new_orion.setup()
    session_stats["messages_sent"] = 0
    session_stats["tools_used"] = 0
    session_stats["session_start"] = datetime.now()
    return "", "", None, new_orion, "🔄 Session reset", 0, 0


def export_conversation(history):
    """Export conversation history to JSON"""
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
        
        filepath = f"sandbox/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return f"✅ Conversation exported to {filepath}"
    except Exception as e:
        return f"❌ Failed to export conversation: {str(e)}"


def free_resources(orion):
    print("Cleaning up")
    try:
        if orion:
            orion.cleanup()
    except Exception as e:
        print(f"Exception during cleanup: {e}")


# Custom CSS for better UI
custom_css = """
.container {
    max-width: 1200px;
    margin: auto;
}
.stats-box {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 15px;
    border-radius: 10px;
    text-align: center;
    font-weight: bold;
}
.header-text {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5em;
    font-weight: bold;
    text-align: center;
    margin-bottom: 20px;
}
"""


with gr.Blocks(title="Orion AI Assistant", css=custom_css, theme=gr.themes.Soft(primary_hue="purple")) as ui:
    gr.HTML('<div class="header-text">🌟 Orion AI Personal Assistant 🌟</div>')
    gr.Markdown("""
    ### Your Enhanced AI Co-Worker with 35+ Tools
    📧 Email Management | 📅 Calendar | 📝 Notes & Tasks | 📄 PDF Processing | 🔍 OCR | 📊 Data Analysis | 🌐 Web Automation
    """)
    
    orion = gr.State(delete_callback=free_resources)
    
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="💬 Conversation",
                height=450,
                show_label=True,
                avatar_images=(None, "🤖")
            )
            
            with gr.Group():
                with gr.Row():
                    message = gr.Textbox(
                        show_label=False,
                        placeholder="💭 What would you like Orion to help you with?",
                        lines=2
                    )
                
                with gr.Row():
                    upload_files = gr.File(
                        label="📎 Attach Files (Optional)",
                        file_count="multiple",
                        file_types=[".pdf", ".csv", ".xlsx", ".json", ".txt", ".png", ".jpg", ".jpeg"]
                    )
                
                with gr.Row():
                    success_criteria = gr.Textbox(
                        show_label=False,
                        placeholder="🎯 Success criteria (optional): What would make this response perfect?",
                        lines=1
                    )
            
            with gr.Row():
                reset_button = gr.Button("🔄 Reset Session", variant="stop", size="sm")
                export_button = gr.Button("💾 Export Chat", variant="secondary", size="sm")
                go_button = gr.Button("🚀 Send", variant="primary", size="lg")
        
        with gr.Column(scale=1):
            gr.Markdown("### 📊 Session Statistics")
            status_box = gr.Textbox(
                label="Status",
                value="⏳ Initializing...",
                interactive=False
            )
            messages_count = gr.Number(
                label="💬 Messages Sent",
                value=0,
                interactive=False
            )
            tools_count = gr.Number(
                label="🔧 Tools Used",
                value=0,
                interactive=False
            )
            
            gr.Markdown("### 🎨 Available Tools")
            gr.Markdown("""
            **Productivity:**
            - 📧 Email (Send/Read)
            - 📅 Google Calendar
            - ✅ Tasks & Reminders
            - 📝 Notes
            - 📸 Screenshots
            
            **Document Processing:**
            - 📄 PDF Reader/Writer
            - 🔍 OCR (Image to Text)
            - 📊 CSV/Excel Reader
            - 📋 JSON Handler
            - 📝 Markdown Converter
            
            **Communication:**
            - 📱 Push Notifications
            - 🔲 QR Code Generator
            
            **Information:**
            - 🌐 Web Search
            - 🌍 Wikipedia
            - 🐍 Python Executor
            - 🌐 Browser Automation
            """)
            
            export_status = gr.Textbox(
                label="Export Status",
                value="",
                interactive=False,
                visible=False
            )
    
    # Event handlers
    ui.load(setup, [], [orion, status_box, messages_count, tools_count])
    
    message.submit(
        process_message,
        [orion, message, success_criteria, chatbot, upload_files],
        [chatbot, orion, messages_count, tools_count]
    )
    
    success_criteria.submit(
        process_message,
        [orion, message, success_criteria, chatbot, upload_files],
        [chatbot, orion, messages_count, tools_count]
    )
    
    go_button.click(
        process_message,
        [orion, message, success_criteria, chatbot, upload_files],
        [chatbot, orion, messages_count, tools_count]
    )
    
    reset_button.click(
        reset,
        [],
        [message, success_criteria, chatbot, orion, status_box, messages_count, tools_count]
    )
    
    export_button.click(
        export_conversation,
        [chatbot],
        [export_status]
    )


# Launch without authentication for HF Spaces (public access)
# Authentication is handled by HuggingFace if needed
if __name__ == "__main__":
    ui.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
else:
    # When imported (e.g., by HF Spaces)
    ui.launch()
