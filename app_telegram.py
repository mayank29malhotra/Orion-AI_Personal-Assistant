"""
HuggingFace Spaces Entry Point for Telegram Bot
Runs Telegram bot in polling mode on HF Spaces.
"""
import os
import sys
import asyncio
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OrionHF")

# HuggingFace Spaces detection and setup
IS_HF_SPACE = os.path.exists("/data") or os.getenv("SPACE_ID")

if IS_HF_SPACE:
    # Configure paths for HF Spaces persistent storage
    DATA_DIR = "/data"
    os.makedirs(f"{DATA_DIR}/sandbox", exist_ok=True)
    os.makedirs(f"{DATA_DIR}/sandbox/data", exist_ok=True)
    os.makedirs(f"{DATA_DIR}/sandbox/notes", exist_ok=True)
    os.makedirs(f"{DATA_DIR}/sandbox/tasks", exist_ok=True)
    os.makedirs(f"{DATA_DIR}/sandbox/temp", exist_ok=True)
    os.makedirs(f"{DATA_DIR}/sandbox/screenshots", exist_ok=True)
    os.environ["ORION_DATA_DIR"] = DATA_DIR
    logger.info(f"🚀 Running on HuggingFace Spaces - Data dir: {DATA_DIR}")

# Import after setting up paths
from integrations.telegram import main as telegram_main

if __name__ == "__main__":
    logger.info("🤖 Starting Orion Telegram Bot on HuggingFace Spaces...")
    logger.info("📱 Using polling mode (no webhook needed)")
    
    # Run telegram bot
    asyncio.run(telegram_main())
