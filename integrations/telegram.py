"""
Telegram Integration for Orion AI Assistant
Uses FastAPI webhook to receive Telegram messages and Bot API to send responses.
Designed for deployment on free cloud tiers (HuggingFace Spaces, Oracle Cloud, etc.)
"""
import os
import json
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
import httpx
import asyncio
from typing import Optional
import logging

from core.config import Config
from core.agent import Orion
from core.memory import memory, retry_queue, pending_queue, process_retry_queue

logger = logging.getLogger("Orion")

# Telegram Configuration
BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
ALLOWED_USER_ID = Config.TELEGRAM_ALLOWED_USER_ID

# Telegram API base URL
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None

# Database for storing pending tasks
DB_PATH = os.path.join(Config.PERSISTENT_DIR, "telegram_tasks.db")

# Global Orion instance (reused across requests)
orion_instance: Optional[Orion] = None


def init_database():
    """Initialize SQLite database for task storage."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            result TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Telegram task database initialized")


def save_task(chat_id: str, user_id: str, message: str) -> int:
    """Save a task to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pending_tasks (chat_id, user_id, message, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (chat_id, user_id, message, datetime.now().isoformat()))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    logger.info(f"Task saved to database: ID={task_id}, ChatID={chat_id}")
    return task_id


def log_message(chat_id: str, direction: str, message: str):
    """Log a message for history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO message_log (chat_id, direction, message, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (chat_id, direction, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_pending_tasks():
    """Get all pending tasks from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, chat_id, user_id, message, timestamp 
        FROM pending_tasks 
        WHERE status = 'pending'
        ORDER BY timestamp ASC
    ''')
    tasks = cursor.fetchall()
    conn.close()
    return tasks


def update_task_status(task_id: int, status: str, result: str = None):
    """Update task status in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pending_tasks 
        SET status = ?, result = ?
        WHERE id = ?
    ''', (status, result, task_id))
    conn.commit()
    conn.close()
    logger.info(f"Task {task_id} updated: {status}")


async def send_telegram_message(chat_id: str, message: str, parse_mode: str = "Markdown"):
    """Send a message via Telegram Bot API."""
    if not TG_API:
        logger.error("Telegram Bot Token not configured")
        return False
    
    try:
        # Split long messages (Telegram limit is 4096 characters)
        max_length = 4000
        messages = [message[i:i+max_length] for i in range(0, len(message), max_length)]
        
        async with httpx.AsyncClient() as client:
            for msg in messages:
                response = await client.post(
                    f"{TG_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": parse_mode
                    }
                )
                if response.status_code != 200:
                    # Try without parse_mode if markdown fails
                    response = await client.post(
                        f"{TG_API}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": msg
                        }
                    )
                    
        logger.info(f"Telegram message sent to {chat_id}")
        log_message(chat_id, "outgoing", message[:500])
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        return False


async def send_typing_action(chat_id: str):
    """Send typing indicator to show bot is processing."""
    if not TG_API:
        return
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TG_API}/sendChatAction",
                json={
                    "chat_id": chat_id,
                    "action": "typing"
                }
            )
    except Exception:
        pass


def is_user_allowed(user_id: int) -> bool:
    """
    STRICT SECURITY: Check if user is allowed to use the bot.
    BLOCKS EVERYONE by default if TELEGRAM_ALLOWED_USER_ID is not set.
    """
    if not ALLOWED_USER_ID:
        logger.error(f"🚫 SECURITY: Access DENIED for user {user_id} - No TELEGRAM_ALLOWED_USER_ID configured!")
        return False
    
    try:
        allowed_ids = [int(uid.strip()) for uid in ALLOWED_USER_ID.split(",")]
        is_allowed = user_id in allowed_ids
        
        if not is_allowed:
            logger.warning(f"🚫 SECURITY: Unauthorized access attempt from user {user_id}")
        
        return is_allowed
    except ValueError as e:
        logger.error(f"Invalid TELEGRAM_ALLOWED_USER_ID format: {e}")
        return False


async def get_orion_instance() -> Orion:
    """Get or create Orion instance."""
    global orion_instance
    if orion_instance is None:
        orion_instance = Orion()
        await orion_instance.setup()
        logger.info("Orion instance initialized")
    return orion_instance


async def process_telegram_task(chat_id: str, message: str, task_id: int = None):
    """Process a Telegram task using Orion."""
    try:
        logger.info(f"Processing Telegram task from {chat_id}: {message[:50]}...")
        
        await send_typing_action(chat_id)
        
        orion = await get_orion_instance()
        
        # Process the message with user_id for memory persistence
        results = await orion.run_superstep(
            message,
            success_criteria="",
            history=[],
            user_id=chat_id,
            channel="telegram"
        )
        
        # Extract the final response
        if results and len(results) > 0:
            final_response = results[-1][1] if len(results[-1]) > 1 else "Task completed"
        else:
            final_response = "Task completed successfully"
        
        # Send response back via Telegram
        response_msg = f"✅ *Task completed!*\n\n{final_response}"
        await send_telegram_message(chat_id, response_msg)
        
        # Update task status if it was from database
        if task_id:
            update_task_status(task_id, "completed", final_response[:1000])
        
        logger.info(f"Task completed for {chat_id}")
        
    except Exception as e:
        error_msg = f"❌ Error processing task: {str(e)}"
        logger.error(f"Telegram task failed: {str(e)}")
        
        # Check if it's a critical error that means bot is unavailable
        is_critical = any(err in str(e).lower() for err in ["rate limit", "timeout", "connection", "unavailable", "503", "502"])
        
        if is_critical:
            # Queue the request for later processing
            pending_queue.add_request(
                user_id=chat_id,
                channel="telegram",
                message=message,
                priority=1,
                metadata={"task_id": task_id}
            )
            pending_queue.set_bot_status("offline", str(e))
            
            await send_telegram_message(
                chat_id, 
                "⏳ *Request Queued*\n\n"
                "I'm experiencing some issues right now. Your request has been saved "
                "and will be processed automatically when I'm back online.\n\n"
                f"📝 Request: {message[:100]}{'...' if len(message) > 100 else ''}"
            )
        else:
            await send_telegram_message(chat_id, error_msg)
        
        if task_id:
            update_task_status(task_id, "failed", str(e))


async def handle_command(chat_id: str, command: str, args: str = ""):
    """Handle special bot commands."""
    if command == "/start":
        welcome = """
🤖 *Welcome to Orion AI Assistant!*

I'm your personal AI agent that can help you with:
• 📧 Email management
• 📅 Calendar & scheduling  
• 🔍 Web search & research
• 📝 Note-taking & task management
• 🌐 Web browsing & automation
• And much more!

Just send me a message with what you need, and I'll handle it.

*Commands:*
/status - Check bot status
/history - View conversation history
/clear - Clear conversation memory
/help - Show this help message
        """
        await send_telegram_message(chat_id, welcome)
        
    elif command == "/status":
        # Get user stats
        user_context = memory.get_user_context(chat_id)
        pending_retries = len([r for r in retry_queue.get_pending_retries() if r["user_id"] == chat_id])
        failed_requests = len(retry_queue.get_failed_requests(chat_id))
        
        # Get pending queue stats
        pending_requests = pending_queue.get_user_pending_requests(chat_id, "telegram")
        bot_status = pending_queue.get_bot_status()
        
        total_msgs = user_context.get("total_messages", 0) if user_context else 0
        
        status_emoji = "✅" if bot_status.get("status") == "online" else "⚠️"
        
        status = f"""
📊 *Orion Status*

{status_emoji} Bot: {bot_status.get('status', 'Unknown').title()}
✅ Orion Agent: Ready
✅ Database: Connected

📝 *Your Stats:*
• Total messages: {total_msgs}
• Queued requests: {len(pending_requests)}
• Pending retries: {pending_retries}
• Failed requests: {failed_requests}
        """
        await send_telegram_message(chat_id, status)
    
    elif command == "/history":
        history = memory.get_history(chat_id, "telegram", limit=10)
        
        if not history:
            await send_telegram_message(chat_id, "📜 No conversation history yet.")
            return
        
        history_text = "📜 *Recent Conversation History:*\n\n"
        for msg in history[-10:]:
            role = "👤 You" if msg["role"] == "user" else "🤖 Orion"
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            history_text += f"{role}: {content}\n\n"
        
        await send_telegram_message(chat_id, history_text)
    
    elif command == "/clear":
        memory.clear_history(chat_id, "telegram")
        await send_telegram_message(chat_id, "🗑️ Conversation history cleared!")
        
    elif command == "/help":
        help_text = """
🆘 *Orion Help*

Just send me natural language requests like:
• "Check my emails"
• "What's on my calendar today?"
• "Search the web for Python tutorials"
• "Create a note about project ideas"
• "Set a reminder for 3 PM"

*Commands:*
/status - Check bot and memory status
/history - View recent conversation history
/clear - Clear your conversation memory
/help - Show this help message

💡 I remember our previous conversations!
        """
        await send_telegram_message(chat_id, help_text)
        
    else:
        await send_telegram_message(chat_id, f"Unknown command: {command}")


# FastAPI App with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Security check
    if not ALLOWED_USER_ID:
        logger.error("=" * 60)
        logger.error("🚨 SECURITY ERROR: TELEGRAM_ALLOWED_USER_ID is not set!")
        logger.error("The bot will BLOCK ALL users until you configure this.")
        logger.error("=" * 60)
    else:
        logger.info(f"🔒 Security: Bot restricted to user ID(s): {ALLOWED_USER_ID}")
    
    if not BOT_TOKEN:
        logger.error("🚨 ERROR: TELEGRAM_BOT_TOKEN is not set!")
    
    # Startup
    init_database()
    logger.info("Telegram bot starting...")
    
    # Start retry queue processor in background
    retry_task = None
    try:
        orion = await get_orion_instance()
        retry_task = asyncio.create_task(process_retry_queue(orion))
        logger.info("🔄 Retry queue processor started")
    except Exception as e:
        logger.warning(f"Could not start retry queue processor: {e}")
    
    yield
    
    # Shutdown
    if retry_task:
        retry_task.cancel()
        try:
            await retry_task
        except asyncio.CancelledError:
            pass
    
    global orion_instance
    if orion_instance:
        try:
            orion_instance.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    logger.info("Telegram bot shutdown complete")


app = FastAPI(title="Orion Telegram Bot", lifespan=lifespan)


@app.post("/telegram/webhook")
async def telegram_webhook(req: Request):
    """Webhook endpoint for receiving Telegram messages."""
    try:
        data = await req.json()
        
        if "message" not in data:
            return {"ok": True}
        
        message_data = data["message"]
        chat_id = str(message_data["chat"]["id"])
        user_id = message_data["from"]["id"]
        
        # Security check
        if not is_user_allowed(user_id):
            return {"ok": True}
        
        text = message_data.get("text", "")
        if not text:
            await send_telegram_message(chat_id, "Please send a text message.")
            return {"ok": True}
        
        logger.info(f"Received message from {user_id}: {text[:50]}...")
        log_message(chat_id, "incoming", text[:500])
        
        # Handle commands
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            await handle_command(chat_id, command, args)
            return {"ok": True}
        
        # Save task and process
        task_id = save_task(chat_id, str(user_id), text)
        await send_telegram_message(chat_id, "📝 *Processing your request...*")
        asyncio.create_task(process_telegram_task(chat_id, text, task_id))
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Orion Telegram Integration",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Orion Telegram Bot is running!", "docs": "/docs"}


async def set_webhook(webhook_url: str):
    """Register webhook with Telegram."""
    if not TG_API:
        logger.error("Bot token not configured")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TG_API}/setWebhook",
                json={"url": webhook_url}
            )
            result = response.json()
            
            if result.get("ok"):
                logger.info(f"Webhook set successfully: {webhook_url}")
                return True
            else:
                logger.error(f"Failed to set webhook: {result}")
                return False
                
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return False


def start_telegram_server(host="0.0.0.0", port=8000):
    """Start the Telegram webhook server."""
    import uvicorn
    
    logger.info(f"Starting Telegram bot server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Orion Telegram Bot")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--set-webhook", help="Set webhook URL")
    
    args = parser.parse_args()
    
    if args.set_webhook:
        asyncio.run(set_webhook(args.set_webhook))
    else:
        start_telegram_server(args.host, args.port)
