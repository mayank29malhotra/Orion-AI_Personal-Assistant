"""
Gradio Web UI Integration for Orion
A beautiful web-based chat interface that's free to deploy.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
from core.agent import Orion
from core.memory import pending_queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global Orion instance
orion_instance = None


async def get_orion():
    """Get or create Orion instance."""
    global orion_instance
    if orion_instance is None:
        orion_instance = Orion()
        await orion_instance.setup()
        logger.info("Orion initialized for Gradio UI")
    return orion_instance


async def process_message(message: str, history: list, user_id: str = "gradio_user") -> str:
    """Process a message through Orion and return the response."""
    if not message.strip():
        return "Please enter a message."
    
    try:
        orion = await get_orion()
        
        # Convert Gradio history format to our format
        orion_history = []
        for h in history:
            if len(h) >= 2:
                orion_history.append({"role": "user", "content": h[0]})
                orion_history.append({"role": "assistant", "content": h[1]})
        
        logger.info(f"Processing message: {message[:100]}...")
        
        # Run Orion with memory persistence
        results = await orion.run_superstep(
            message,
            success_criteria="",
            history=orion_history,
            user_id=user_id,
            channel="gradio"
        )
        
        # Extract response
        if results and len(results) > 0:
            last_result = results[-1]
            if isinstance(last_result, (list, tuple)) and len(last_result) > 1:
                response = last_result[1]
            elif hasattr(last_result, 'content'):
                response = last_result.content
            elif isinstance(last_result, dict):
                response = last_result.get('content', str(last_result))
            else:
                response = str(last_result)
        else:
            response = "I processed your request but have no specific response."
        
        logger.info(f"Response generated: {response[:100]}...")
        
        # Mark bot as online
        pending_queue.set_bot_status("online")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        
        # Check if it's a critical error
        is_critical = any(err in str(e).lower() for err in ["rate limit", "timeout", "connection", "unavailable", "503", "502"])
        
        if is_critical:
            # Queue the request for later processing
            pending_queue.add_request(
                user_id=user_id,
                channel="gradio",
                message=message,
                priority=1
            )
            pending_queue.set_bot_status("offline", str(e))
            
            return (
                "⏳ **Request Queued**\n\n"
                "I'm experiencing some issues right now. Your request has been saved "
                "and will be processed automatically when I'm back online.\n\n"
                f"📝 Request: {message[:100]}{'...' if len(message) > 100 else ''}"
            )
        
        return f"Error: {str(e)}"


def sync_process_message(message: str, history: list) -> str:
    """Synchronous wrapper for async process_message."""
    return asyncio.run(process_message(message, history))


def create_gradio_interface():
    """Create the Gradio chat interface."""
    
    # Custom CSS for better styling
    custom_css = """
    .gradio-container {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .chat-message {
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
    }
    """
    
    with gr.Blocks(
        title="Orion - Personal AI Assistant",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
        css=custom_css
    ) as interface:
        
        gr.Markdown("""
        # 🌟 Orion - Personal AI Assistant
        
        Your intelligent personal assistant with access to:
        - 📧 Email (send, read, search)
        - 📅 Calendar (events, scheduling)
        - ✅ Tasks & Notes
        - 🔍 Web Search
        - 🌐 Browser Automation
        - 📄 PDF & Document Processing
        - 🐍 Python Code Execution
        - And much more!
        
        ---
        """)
        
        chatbot = gr.Chatbot(
            label="Chat with Orion",
            height=500,
            show_label=False,
            avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=orion"),
            bubble_full_width=False,
        )
        
        with gr.Row():
            msg = gr.Textbox(
                label="Your message",
                placeholder="Ask me anything... (e.g., 'Check my emails', 'Search for Python tutorials', 'Create a task')",
                lines=2,
                scale=9,
                show_label=False,
            )
            submit_btn = gr.Button("Send", variant="primary", scale=1)
        
        with gr.Row():
            clear_btn = gr.Button("🗑️ Clear Chat", size="sm")
            examples_btn = gr.Button("💡 Show Examples", size="sm")
        
        # Example queries accordion
        with gr.Accordion("Example Queries", open=False) as examples_accordion:
            gr.Markdown("""
            **Email:**
            - "Check my unread emails"
            - "Send an email to john@example.com about the meeting"
            
            **Calendar:**
            - "What's on my calendar today?"
            - "Schedule a meeting tomorrow at 3pm"
            
            **Search:**
            - "Search for the latest AI news"
            - "Find information about Python async programming"
            
            **Tasks:**
            - "Create a task to review the project proposal"
            - "Show my pending tasks"
            
            **Browser:**
            - "Go to github.com and take a screenshot"
            - "Navigate to weather.com and tell me the forecast"
            
            **Code:**
            - "Calculate the factorial of 10 using Python"
            - "Generate a random password"
            """)
        
        # Status indicator
        with gr.Row():
            status = gr.Markdown("*Ready to help!*")
        
        def respond(message, chat_history):
            """Handle user message and update chat."""
            if not message.strip():
                return "", chat_history
            
            # Add user message to history
            chat_history = chat_history + [[message, None]]
            
            # Get response from Orion
            response = sync_process_message(message, chat_history[:-1])
            
            # Update with response
            chat_history[-1][1] = response
            
            return "", chat_history
        
        def clear_chat():
            """Clear the chat history."""
            return [], "*Chat cleared. Ready to help!*"
        
        # Event handlers
        msg.submit(respond, [msg, chatbot], [msg, chatbot])
        submit_btn.click(respond, [msg, chatbot], [msg, chatbot])
        clear_btn.click(clear_chat, outputs=[chatbot, status])
    
    return interface


def main():
    """Main entry point for Gradio UI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Orion Gradio Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=7860, help="Port to run on")
    parser.add_argument("--share", action="store_true", help="Create a public Gradio link")
    parser.add_argument("--auth", help="Username:password for authentication (e.g., admin:secret)")
    
    args = parser.parse_args()
    
    # Parse authentication if provided
    auth = None
    if args.auth:
        try:
            username, password = args.auth.split(":", 1)
            auth = (username, password)
            logger.info(f"Authentication enabled for user: {username}")
        except ValueError:
            logger.warning("Invalid auth format. Use username:password")
    
    logger.info(f"Starting Orion Gradio UI on {args.host}:{args.port}")
    
    interface = create_gradio_interface()
    
    interface.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        auth=auth,
        show_error=True,
    )


if __name__ == "__main__":
    main()
