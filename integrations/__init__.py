"""
Multi-Channel Integration Hub for Orion AI Assistant
Provides unified access from multiple platforms.

Supported Channels:
1. Telegram Bot - Mobile/Desktop messaging
2. Email Bot - Send commands via email
3. Scheduled Tasks - Automated recurring tasks
4. Gradio UI - Web interface
"""
import os
import asyncio
import logging
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING
from datetime import datetime
from abc import ABC, abstractmethod

from core.config import Config

# Lazy import to avoid circular dependencies and missing module errors
if TYPE_CHECKING:
    from core.agent import Orion

logger = logging.getLogger("Orion")


def get_orion_class():
    """Lazy import of Orion to avoid circular imports."""
    from core.agent import Orion
    return Orion


class ChannelHandler(ABC):
    """Abstract base class for all channel handlers."""
    
    def __init__(self, name: str):
        self.name = name
        self.orion = None
        self.enabled = False
    
    async def initialize(self):
        """Initialize Orion instance."""
        if self.orion is None:
            Orion = get_orion_class()
            self.orion = Orion()
            await self.orion.setup()
            logger.info(f"[{self.name}] Orion initialized")
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Process a message through Orion."""
        try:
            await self.initialize()
            results = await self.orion.run_superstep(message, success_criteria="", history=[])
            
            if results and len(results) > 0:
                return results[-1][1] if len(results[-1]) > 1 else "Task completed"
            return "Task completed successfully"
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return f"Error: {str(e)}"
    
    @abstractmethod
    async def start(self):
        """Start the channel handler"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the channel handler"""
        pass


class IntegrationHub:
    """
    Central hub for managing all Orion integrations
    """
    
    def __init__(self):
        self.channels: Dict[str, ChannelHandler] = {}
        self.orion = None
        
    async def initialize_orion(self):
        """Initialize shared Orion instance"""
        if self.orion is None:
            Orion = get_orion_class()
            self.orion = Orion()
            await self.orion.setup()
            logger.info("Integration Hub: Orion initialized")
    
    def register_channel(self, channel: ChannelHandler):
        """Register a new channel handler"""
        self.channels[channel.name] = channel
        logger.info(f"Registered channel: {channel.name}")
    
    async def start_all(self):
        """Start all registered channels"""
        await self.initialize_orion()
        for name, channel in self.channels.items():
            try:
                channel.orion = self.orion  # Share Orion instance
                await channel.start()
                logger.info(f"Started channel: {name}")
            except Exception as e:
                logger.error(f"Failed to start {name}: {e}")
    
    async def stop_all(self):
        """Stop all channels"""
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped channel: {name}")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")


# ============================================================
# FREE INTEGRATION OPTIONS
# ============================================================

FREE_INTEGRATIONS = """
╔══════════════════════════════════════════════════════════════╗
║           ORION AI - FREE INTEGRATION OPTIONS                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📱 MESSAGING PLATFORMS (Free Forever)                       ║
║  ─────────────────────────────────────                       ║
║  ✅ Telegram Bot      - Mobile + Desktop + Web               ║
║                                                              ║
║  🌐 WEB ACCESS (Free Forever)                                ║
║  ─────────────────────────────────────                       ║
║  ✅ Gradio UI         - Web interface (already included)     ║
║  ✅ REST API          - Custom integrations                  ║
║  ✅ CLI               - Terminal access                      ║
║                                                              ║
║  📧 EMAIL (Free Forever)                                     ║
║  ─────────────────────────────────────                       ║
║  ✅ Email Bot         - Send tasks via email                 ║
║                                                              ║
║  ⏰ AUTOMATION (Free Forever)                                ║
║  ─────────────────────────────────────                       ║
║  ✅ Scheduled Tasks   - Cron-like automation                 ║
║  ✅ File Watcher      - React to file changes                ║
║  ✅ Webhook Receiver  - Trigger from external services       ║
║                                                              ║
║  🎤 VOICE (Free Forever)                                     ║
║  ─────────────────────────────────────                       ║
║  ✅ Telegram Voice    - Voice notes via Telegram             ║
║  ✅ Local Speech      - Mic input (requires local run)       ║
║                                                              ║
║  ❌ NOT FREE (Avoid)                                         ║
║  ─────────────────────────────────────                       ║
║  ❌ WhatsApp          - Requires paid Business API           ║
║  ❌ SMS/Twilio        - Per-message charges                  ║
║  ❌ Phone Calls       - Per-minute charges                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

def show_integration_options():
    """Display available integration options"""
    print(FREE_INTEGRATIONS)


if __name__ == "__main__":
    show_integration_options()
