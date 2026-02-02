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

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - Orion - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Data directory setup
DATA_DIR = os.environ.get("ORION_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(f"{DATA_DIR}/sandbox", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/data", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/notes", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/tasks", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/screenshots", exist_ok=True)
os.makedirs(f"{DATA_DIR}/sandbox/temp", exist_ok=True)
os.environ["ORION_DATA_DIR"] = DATA_DIR

logger.info(f"🚀 Orion Headless starting - Data dir: {DATA_DIR}")
sys.stdout.flush()

# Global shutdown event
shutdown_event = threading.Event()


def run_telegram_bot():
    """Run Telegram bot in a separate thread with its own event loop."""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        allowed_users = os.getenv("TELEGRAM_ALLOWED_USER_ID")
        
        if not bot_token or not allowed_users:
            logger.warning("⚠️ Telegram not configured")
            return
        
        logger.info("🤖 Starting Telegram bot...")
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
        
        logger.info("📬 Starting Email bot...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from integrations.email_bot import email_bot_loop
        loop.run_until_complete(email_bot_loop())
        
    except Exception as e:
        logger.error(f"❌ Email bot error: {e}")


def run_scheduler():
    """Run Scheduler in a separate thread."""
    try:
        logger.info("⏰ Starting Scheduler...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from integrations.scheduler import start_scheduler_loop
        loop.run_until_complete(start_scheduler_loop())
        
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")


def shutdown_handler(signum, frame):
    """Handle graceful shutdown"""
    logger.info("🛑 Shutdown signal received...")
    shutdown_event.set()
    logger.info("👋 Orion shutdown complete")
    sys.exit(0)


def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("🚀 Orion AI Assistant (Headless Mode)")
    logger.info("=" * 50)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    services_started = []
    
    # Start Telegram
    telegram_configured = os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_ALLOWED_USER_ID")
    if telegram_configured:
        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()
        services_started.append("📱 Telegram")
        logger.info("✅ Telegram bot started")
    
    # Start Email Bot
    email_configured = os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_PASSWORD")
    if email_configured:
        email_thread = threading.Thread(target=run_email_bot, daemon=True)
        email_thread.start()
        services_started.append("📬 Email Bot")
        logger.info("✅ Email bot started")
    
    # Start Scheduler
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    services_started.append("⏰ Scheduler")
    logger.info("✅ Scheduler started")
    
    if not services_started:
        logger.error("❌ No services could be started! Check your environment variables.")
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info(f"Active services: {' | '.join(services_started)}")
    logger.info("Orion is running. Press Ctrl+C to stop.")
    logger.info("=" * 50)
    sys.stdout.flush()
    
    # Keep main thread alive
    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1)
    except KeyboardInterrupt:
        shutdown_handler(None, None)


if __name__ == "__main__":
    main()
