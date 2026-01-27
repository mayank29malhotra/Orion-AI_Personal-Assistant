"""
Orion AI Personal Assistant - Core Package
Contains the main agent, configuration, utilities, and memory management.
"""

from core.config import Config
from core.utils import logger, cache, rate_limiter, Logger, Cache, RateLimiter
from core.memory import (
    ConversationMemory,
    FailedRequestQueue,
    NotificationManager,
    PendingRequestQueue,
    memory,
    retry_queue,
    notification_manager,
    pending_queue,
    process_retry_queue,
    process_pending_queue
)

# Lazy import for Orion to avoid circular imports
def get_orion():
    """Get the Orion agent class (lazy import)."""
    from core.agent import Orion
    return Orion

__all__ = [
    'get_orion',
    'Config',
    'ConversationMemory',
    'FailedRequestQueue',
    'NotificationManager',
    'PendingRequestQueue',
    'memory',
    'retry_queue',
    'notification_manager',
    'pending_queue',
    'process_retry_queue',
    'process_pending_queue',
    'logger',
    'cache',
    'rate_limiter',
    'Logger',
    'Cache',
    'RateLimiter',
]
