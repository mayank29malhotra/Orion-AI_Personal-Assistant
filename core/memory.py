"""
Persistent Memory System for Orion AI Assistant
Stores conversation history and failed request queue with SQLite.
Works with Hugging Face Spaces persistent storage.
"""

import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import threading

logger = logging.getLogger("Orion")


def get_persistent_path() -> str:
    """
    Get the persistent storage path.
    - HuggingFace Spaces: /data
    - Local: sandbox/data
    """
    if os.path.exists("/data"):
        return "/data"
    return os.getenv("PERSISTENT_DIR", "sandbox/data")


class ConversationMemory:
    """
    Persistent conversation memory using SQLite.
    Stores conversation history per user/channel.
    Singleton pattern for consistent access.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.db_path = os.path.join(get_persistent_path(), "orion_memory.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        logger.info(f"ConversationMemory initialized at {self.db_path}")
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Conversations table - stores message history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # User context table - stores user preferences and context
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_context (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                preferences TEXT,
                last_seen DATETIME,
                total_messages INTEGER DEFAULT 0
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_timestamp ON conversations(timestamp)")
        
        conn.commit()
        conn.close()
    
    def add_message(self, user_id: str, channel: str, role: str, content: str, metadata: Dict = None):
        """Add a message to conversation history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (user_id, channel, role, content, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, channel, role, content, json.dumps(metadata or {})))
        
        # Update user context
        cursor.execute("""
            INSERT INTO user_context (user_id, last_seen, total_messages)
            VALUES (?, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen = CURRENT_TIMESTAMP,
                total_messages = total_messages + 1
        """, (user_id,))
        
        conn.commit()
        conn.close()
        logger.debug(f"Added {role} message for user {user_id} on {channel}")
    
    def get_history(self, user_id: str, channel: str = None, limit: int = 20) -> List[Dict]:
        """Get conversation history for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if channel:
            cursor.execute("""
                SELECT role, content, timestamp, metadata
                FROM conversations
                WHERE user_id = ? AND channel = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, channel, limit))
        else:
            cursor.execute("""
                SELECT role, content, timestamp, metadata
                FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Reverse to get chronological order
        messages = []
        for row in reversed(rows):
            messages.append({
                "role": row[0],
                "content": row[1],
                "timestamp": row[2],
                "metadata": json.loads(row[3]) if row[3] else {}
            })
        
        return messages
    
    def get_formatted_history(self, user_id: str, channel: str = None, limit: int = 10) -> List[Dict]:
        """Get history formatted for LLM context."""
        history = self.get_history(user_id, channel, limit)
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]
    
    def clear_history(self, user_id: str, channel: str = None):
        """Clear conversation history for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if channel:
            cursor.execute("DELETE FROM conversations WHERE user_id = ? AND channel = ?", (user_id, channel))
        else:
            cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"Cleared history for user {user_id}")
    
    def get_user_context(self, user_id: str) -> Optional[Dict]:
        """Get user context and preferences."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_context WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "user_id": row[0],
                "name": row[1],
                "preferences": json.loads(row[2]) if row[2] else {},
                "last_seen": row[3],
                "total_messages": row[4]
            }
        return None
    
    def set_user_name(self, user_id: str, name: str):
        """Set user's preferred name."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_context (user_id, name, last_seen)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET name = ?
        """, (user_id, name, name))
        
        conn.commit()
        conn.close()
    
    def prune_old_messages(self, days: int = 30):
        """Remove messages older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        cursor.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff.isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Pruned {deleted} messages older than {days} days")
        return deleted
    
    def get_stats(self, user_id: str = None) -> Dict:
        """Get memory statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM conversations")
        
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_context")
        total_users = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_messages": total_messages,
            "total_users": total_users
        }


class FailedRequestQueue:
    """
    Queue for failed requests that should be retried.
    Persists to SQLite for reliability.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.db_path = os.path.join(get_persistent_path(), "orion_retry_queue.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._retry_task = None
        logger.info(f"FailedRequestQueue initialized at {self.db_path}")
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                message TEXT NOT NULL,
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 2,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                next_retry DATETIME,
                status TEXT DEFAULT 'pending',
                metadata TEXT
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_retry_status ON failed_requests(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_retry_next ON failed_requests(next_retry)")
        
        conn.commit()
        conn.close()
    
    def add_failed_request(
        self,
        user_id: str,
        channel: str,
        message: str,
        error: str,
        metadata: Dict = None
    ) -> int:
        """Add a failed request to the retry queue."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Schedule first retry in 5 minutes
        next_retry = datetime.now() + timedelta(minutes=5)
        
        cursor.execute("""
            INSERT INTO failed_requests (user_id, channel, message, error, next_retry, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, channel, message, error, next_retry.isoformat(), json.dumps(metadata or {})))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Added failed request {request_id} to retry queue (next retry: {next_retry})")
        return request_id
    
    def get_pending_retries(self) -> List[Dict]:
        """Get requests that are due for retry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            SELECT id, user_id, channel, message, retry_count, max_retries, metadata
            FROM failed_requests
            WHERE status = 'pending' AND next_retry <= ?
        """, (now,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "id": row[0],
            "user_id": row[1],
            "channel": row[2],
            "message": row[3],
            "retry_count": row[4],
            "max_retries": row[5],
            "metadata": json.loads(row[6]) if row[6] else {}
        } for row in rows]
    
    def mark_retry_attempted(self, request_id: int, success: bool, error: str = None):
        """Mark a retry attempt as completed or schedule next retry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if success:
            cursor.execute("""
                UPDATE failed_requests
                SET status = 'completed'
                WHERE id = ?
            """, (request_id,))
            logger.info(f"Request {request_id} completed successfully on retry")
        else:
            # Get current retry count
            cursor.execute("SELECT retry_count, max_retries FROM failed_requests WHERE id = ?", (request_id,))
            row = cursor.fetchone()
            
            if row:
                retry_count, max_retries = row
                new_retry_count = retry_count + 1
                
                if new_retry_count >= max_retries:
                    # Max retries reached, mark as failed
                    cursor.execute("""
                        UPDATE failed_requests
                        SET status = 'failed', retry_count = ?, error = ?
                        WHERE id = ?
                    """, (new_retry_count, error, request_id))
                    logger.warning(f"Request {request_id} failed after {new_retry_count} retries")
                else:
                    # Schedule next retry in 5 minutes
                    next_retry = datetime.now() + timedelta(minutes=5)
                    cursor.execute("""
                        UPDATE failed_requests
                        SET retry_count = ?, next_retry = ?, error = ?
                        WHERE id = ?
                    """, (new_retry_count, next_retry.isoformat(), error, request_id))
                    logger.info(f"Request {request_id} retry {new_retry_count} failed, next retry at {next_retry}")
        
        conn.commit()
        conn.close()
    
    def get_failed_requests(self, user_id: str = None) -> List[Dict]:
        """Get requests that have permanently failed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT id, user_id, channel, message, error, created_at
                FROM failed_requests
                WHERE status = 'failed' AND user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, user_id, channel, message, error, created_at
                FROM failed_requests
                WHERE status = 'failed'
                ORDER BY created_at DESC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "id": row[0],
            "user_id": row[1],
            "channel": row[2],
            "message": row[3],
            "error": row[4],
            "created_at": row[5]
        } for row in rows]
    
    def clear_completed(self, days_old: int = 7):
        """Clear completed requests older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days_old)
        cursor.execute("""
            DELETE FROM failed_requests
            WHERE status IN ('completed', 'failed') AND created_at < ?
        """, (cutoff.isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_stats(self) -> Dict:
        """Get queue statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT status, COUNT(*) FROM failed_requests GROUP BY status")
        rows = cursor.fetchall()
        conn.close()
        
        return {row[0]: row[1] for row in rows}


class NotificationManager:
    """
    Send notifications across all access channels.
    Used to notify user of failed requests and important events.
    """
    
    def __init__(self):
        self.channels = {}
    
    async def notify_all_channels(self, user_id: str, message: str):
        """Send notification to all configured channels for a user."""
        results = {}
        
        # Try Telegram
        telegram_result = await self._notify_telegram(user_id, message)
        if telegram_result:
            results["telegram"] = telegram_result
        
        # Try Email
        email_result = await self._notify_email(user_id, message)
        if email_result:
            results["email"] = email_result
        
        # Log notification
        logger.info(f"Sent notifications to user {user_id}: {list(results.keys())}")
        
        return results
    
    async def _notify_telegram(self, user_id: str, message: str) -> bool:
        """Send Telegram notification."""
        try:
            import httpx
            from core.config import Config
            
            if not Config.TELEGRAM_BOT_TOKEN:
                return False
            
            # Use the user_id as chat_id for Telegram
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": user_id,
                        "text": f"🔔 Orion Notification:\n\n{message}",
                        "parse_mode": "HTML"
                    }
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
    
    async def _notify_email(self, user_id: str, message: str) -> bool:
        """Send email notification (if email is configured)."""
        try:
            from core.config import Config
            import smtplib
            from email.mime.text import MIMEText
            
            if not Config.EMAIL_ADDRESS or not Config.EMAIL_PASSWORD:
                return False
            
            # For email, user_id might be an email address
            if "@" not in user_id:
                # If user_id is not an email, try to get from user context
                memory = ConversationMemory()
                context = memory.get_user_context(user_id)
                if not context or "email" not in context.get("preferences", {}):
                    return False
                user_id = context["preferences"]["email"]
            
            msg = MIMEText(f"Orion Notification:\n\n{message}")
            msg["Subject"] = "🔔 Orion AI Assistant Notification"
            msg["From"] = Config.EMAIL_ADDRESS
            msg["To"] = user_id
            
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


# Global singletons
memory = ConversationMemory()
retry_queue = FailedRequestQueue()
notification_manager = NotificationManager()


class PendingRequestQueue:
    """
    Queue for storing incoming requests when the bot is unavailable.
    Automatically processes pending requests when bot comes back online.
    Persists to SQLite for reliability across restarts.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.db_path = os.path.join(get_persistent_path(), "orion_pending_queue.db")
        self.bot_status = "unknown"  # unknown, online, offline
        self._processing = False
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        logger.info(f"PendingRequestQueue initialized at {self.db_path}")
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                message TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                processed_at DATETIME,
                response TEXT,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                status TEXT DEFAULT 'unknown',
                last_check DATETIME,
                last_online DATETIME,
                error_message TEXT
            )
        """)
        
        # Insert default status if not exists
        cursor.execute("INSERT OR IGNORE INTO bot_status (id, status) VALUES (1, 'unknown')")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_requests(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_created ON pending_requests(created_at)")
        
        conn.commit()
        conn.close()
    
    def set_bot_status(self, status: str, error_message: str = None):
        """Update bot status (online, offline, unknown)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        if status == "online":
            cursor.execute("""
                UPDATE bot_status SET status = ?, last_check = ?, last_online = ?, error_message = NULL
                WHERE id = 1
            """, (status, now, now))
        else:
            cursor.execute("""
                UPDATE bot_status SET status = ?, last_check = ?, error_message = ?
                WHERE id = 1
            """, (status, now, error_message))
        
        conn.commit()
        conn.close()
        
        self.bot_status = status
        logger.info(f"Bot status updated: {status}")
    
    def get_bot_status(self) -> Dict:
        """Get current bot status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT status, last_check, last_online, error_message FROM bot_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "status": row[0],
                "last_check": row[1],
                "last_online": row[2],
                "error_message": row[3]
            }
        return {"status": "unknown", "last_check": None, "last_online": None}
    
    def add_request(
        self,
        user_id: str,
        channel: str,
        message: str,
        priority: int = 0,
        metadata: Dict = None
    ) -> int:
        """Add a pending request to the queue."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO pending_requests (user_id, channel, message, priority, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, channel, message, priority, json.dumps(metadata or {})))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Added pending request {request_id} from {channel} user {user_id}")
        return request_id
    
    def get_pending_requests(self, limit: int = 50) -> List[Dict]:
        """Get all pending requests, ordered by priority and creation time."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, user_id, channel, message, priority, created_at, metadata
            FROM pending_requests
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "id": row[0],
            "user_id": row[1],
            "channel": row[2],
            "message": row[3],
            "priority": row[4],
            "created_at": row[5],
            "metadata": json.loads(row[6]) if row[6] else {}
        } for row in rows]
    
    def get_pending_count(self) -> int:
        """Get count of pending requests."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM pending_requests WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def mark_processed(self, request_id: int, response: str = None):
        """Mark a request as processed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE pending_requests
            SET status = 'processed', processed_at = ?, response = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), response, request_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Marked request {request_id} as processed")
    
    def mark_failed(self, request_id: int, error: str):
        """Mark a request as failed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE pending_requests
            SET status = 'failed', response = ?
            WHERE id = ?
        """, (f"Error: {error}", request_id))
        
        conn.commit()
        conn.close()
        logger.warning(f"Marked request {request_id} as failed: {error}")
    
    def get_user_pending_requests(self, user_id: str, channel: str = None) -> List[Dict]:
        """Get pending requests for a specific user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if channel:
            cursor.execute("""
                SELECT id, message, created_at FROM pending_requests
                WHERE user_id = ? AND channel = ? AND status = 'pending'
                ORDER BY created_at ASC
            """, (user_id, channel))
        else:
            cursor.execute("""
                SELECT id, message, created_at FROM pending_requests
                WHERE user_id = ? AND status = 'pending'
                ORDER BY created_at ASC
            """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{"id": row[0], "message": row[1], "created_at": row[2]} for row in rows]
    
    def clear_old_requests(self, days: int = 7):
        """Clear processed/failed requests older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        cursor.execute("""
            DELETE FROM pending_requests
            WHERE status IN ('processed', 'failed') AND created_at < ?
        """, (cutoff.isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleared {deleted} old requests")
        return deleted
    
    def get_stats(self) -> Dict:
        """Get queue statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT status, COUNT(*) FROM pending_requests GROUP BY status")
        rows = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM pending_requests WHERE status = 'pending'")
        pending_users = cursor.fetchone()[0]
        
        conn.close()
        
        stats = {row[0]: row[1] for row in rows}
        stats["pending_users"] = pending_users
        return stats


# Add pending queue to singletons
pending_queue = PendingRequestQueue()


async def process_pending_queue(orion_instance):
    """
    Process pending requests when bot comes back online.
    Should be called when bot status changes to online.
    """
    pending = pending_queue.get_pending_requests()
    
    if not pending:
        logger.info("No pending requests to process")
        return
    
    logger.info(f"Processing {len(pending)} pending requests...")
    
    for request in pending:
        try:
            logger.info(f"Processing pending request {request['id']} from {request['channel']}")
            
            # Process through Orion
            results = await orion_instance.run_superstep(
                request["message"],
                success_criteria="",
                history=[]
            )
            
            # Get response
            response = results[-1][1] if results and len(results[-1]) > 1 else "Request completed"
            
            # Mark as processed
            pending_queue.mark_processed(request["id"], response[:1000])
            
            # Notify user
            await notification_manager.notify_all_channels(
                request["user_id"],
                f"✅ Your queued request has been processed:\n\n"
                f"📝 Request: {request['message'][:100]}{'...' if len(request['message']) > 100 else ''}\n\n"
                f"💬 Response: {response[:500]}"
            )
            
            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Failed to process pending request {request['id']}: {e}")
            pending_queue.mark_failed(request["id"], str(e))
            
            # Notify user of failure
            await notification_manager.notify_all_channels(
                request["user_id"],
                f"❌ Failed to process your queued request:\n\n"
                f"📝 Request: {request['message'][:100]}...\n\n"
                f"Error: {str(e)}"
            )
    
    logger.info("Finished processing pending queue")


async def process_retry_queue(orion_instance):
    """
    Background task to process the retry queue.
    Should be started when the application starts.
    """
    while True:
        try:
            pending = retry_queue.get_pending_retries()
            
            for request in pending:
                logger.info(f"Retrying request {request['id']} for user {request['user_id']}")
                
                try:
                    # Process the request through Orion
                    results = await orion_instance.run_superstep(
                        request["message"],
                        success_criteria="",
                        history=[]
                    )
                    
                    # Mark as successful
                    retry_queue.mark_retry_attempted(request["id"], success=True)
                    
                    # Notify user of success
                    response = results[-1].content if results else "Request completed"
                    await notification_manager.notify_all_channels(
                        request["user_id"],
                        f"✅ Your earlier request has been processed:\n\n"
                        f"Request: {request['message'][:100]}...\n\n"
                        f"Response: {response[:500]}"
                    )
                    
                except Exception as e:
                    error = str(e)
                    retry_queue.mark_retry_attempted(request["id"], success=False, error=error)
                    
                    # If this was the final retry, notify user of failure
                    if request["retry_count"] + 1 >= request["max_retries"]:
                        await notification_manager.notify_all_channels(
                            request["user_id"],
                            f"❌ Failed to process your request after multiple attempts:\n\n"
                            f"Request: {request['message'][:100]}...\n\n"
                            f"Error: {error}\n\n"
                            f"Please try again later or rephrase your request."
                        )
        
        except Exception as e:
            logger.error(f"Error in retry queue processor: {e}")
        
        # Check every minute
        await asyncio.sleep(60)
