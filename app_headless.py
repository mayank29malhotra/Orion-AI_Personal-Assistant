"""
Orion AI Assistant - Headless Mode
Runs Telegram Bot, Email Bot, and Scheduler without Gradio UI
"""

import os
import sys
import signal
import asyncio
import logging
import threading

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - Orion - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Data directory setup
DATA_DIR = os.environ.get("ORION_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(f"{DATA_DIR}/sandbox", exist_ok=True)
os.makedirs(f"{DATA_DIR}/notes", exist_ok=True)
os.makedirs(f"{DATA_DIR}/tasks", exist_ok=True)
os.makedirs(f"{DATA_DIR}/screenshots", exist_ok=True)
os.makedirs(f"{DATA_DIR}/temp", exist_ok=True)

# Import components
from core.agent import OrionAgent
from integrations.scheduler import TaskScheduler

# Check for Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ENABLED = bool(TELEGRAM_TOKEN)

# Check for Email
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_ENABLED = bool(EMAIL_ADDRESS and EMAIL_PASSWORD)

# Global instances
telegram_bot = None
email_bot = None
scheduler = None
orion_agent = None
shutdown_event = threading.Event()


def create_agent():
    """Create a fresh Orion agent instance"""
    return OrionAgent(sandbox_path=f"{DATA_DIR}/sandbox")


def start_telegram():
    """Start Telegram bot in a separate thread"""
    global telegram_bot
    if not TELEGRAM_ENABLED:
        logger.warning("⚠️ Telegram disabled - TELEGRAM_BOT_TOKEN not set")
        return
    
    try:
        from integrations.telegram import TelegramBot
        telegram_bot = TelegramBot(agent_factory=create_agent)
        
        def run_telegram():
            asyncio.run(telegram_bot.start())
        
        thread = threading.Thread(target=run_telegram, daemon=True)
        thread.start()
        logger.info("🤖 Telegram bot started")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {e}")


def start_email():
    """Start Email bot in a separate thread"""
    global email_bot
    if not EMAIL_ENABLED:
        logger.warning("⚠️ Email bot disabled - EMAIL_ADDRESS/EMAIL_PASSWORD not set")
        return
    
    try:
        from integrations.email_bot import EmailBot
        email_bot = EmailBot(agent_factory=create_agent)
        email_bot.start()
        logger.info("📧 Email bot started")
    except Exception as e:
        logger.error(f"Failed to start Email bot: {e}")


def start_scheduler():
    """Start task scheduler"""
    global scheduler
    try:
        scheduler = TaskScheduler(agent_factory=create_agent)
        scheduler.start()
        logger.info("⏰ Scheduler started")
    except Exception as e:
        logger.error(f"Failed to start Scheduler: {e}")


def shutdown_handler(signum, frame):
    """Handle graceful shutdown"""
    logger.info("🛑 Shutdown signal received...")
    shutdown_event.set()
    
    if telegram_bot:
        try:
            telegram_bot.stop()
        except:
            pass
    
    if email_bot:
        try:
            email_bot.stop()
        except:
            pass
    
    if scheduler:
        try:
            scheduler.stop()
        except:
            pass
    
    logger.info("👋 Orion shutdown complete")
    sys.exit(0)


def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("🚀 Starting Orion AI Assistant (Headless Mode)")
    logger.info("=" * 50)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Start services
    services_started = []
    
    if TELEGRAM_ENABLED:
        start_telegram()
        services_started.append("Telegram")
    
    if EMAIL_ENABLED:
        start_email()
        services_started.append("Email")
    
    start_scheduler()
    services_started.append("Scheduler")
    
    if not services_started:
        logger.error("❌ No services could be started! Check your environment variables.")
        sys.exit(1)
    
    logger.info(f"✅ Active services: {', '.join(services_started)}")
    logger.info("=" * 50)
    logger.info("Orion is running. Press Ctrl+C to stop.")
    logger.info("=" * 50)
    
    # Keep main thread alive
    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1)
    except KeyboardInterrupt:
        shutdown_handler(None, None)


if __name__ == "__main__":
    main()
