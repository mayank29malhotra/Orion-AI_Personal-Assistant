"""
Utility functions for Orion AI Personal Assistant
Includes logging, caching, rate limiting, and error handling
"""
import logging
import time
import functools
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import traceback


class Logger:
    """Enhanced logging system"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.logger = logging.getLogger("Orion")
        self.logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        
        # File handler
        file_handler = logging.FileHandler('orion.log')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def error(self, message: str, exc_info=None):
        if exc_info:
            self.logger.error(message, exc_info=True)
        else:
            self.logger.error(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def debug(self, message: str):
        self.logger.debug(message)


# Global logger instance
logger = Logger()


class Cache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        self.cache[key] = (value, time.time())
    
    def clear(self):
        self.cache.clear()


class RateLimiter:
    """Rate limiting for API calls"""
    
    def __init__(self, max_calls: int = 60, period: int = 60):
        self.max_calls = max_calls
        self.period = period
        self.calls: Dict[str, list] = defaultdict(list)
    
    def check(self, key: str = "default") -> bool:
        """Check if rate limit is exceeded"""
        now = time.time()
        # Remove old calls
        self.calls[key] = [
            call_time for call_time in self.calls[key]
            if now - call_time < self.period
        ]
        
        if len(self.calls[key]) >= self.max_calls:
            return False
        
        self.calls[key].append(now)
        return True
    
    def wait_time(self, key: str = "default") -> float:
        """Get wait time in seconds before next call is allowed"""
        if not self.calls[key]:
            return 0.0
        
        oldest_call = min(self.calls[key])
        time_passed = time.time() - oldest_call
        
        if time_passed >= self.period:
            return 0.0
        
        return self.period - time_passed


# Global cache and rate limiter
cache = Cache(ttl_seconds=300)
rate_limiter = RateLimiter(max_calls=60, period=60)


def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying functions on error"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {retries}/{max_retries}): {str(e)}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator


def async_retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying async functions on error"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio
            retries = 0
            current_delay = delay
            
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Async function {func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    logger.warning(f"Async function {func.__name__} failed (attempt {retries}/{max_retries}): {str(e)}. Retrying in {current_delay}s...")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator


def safe_execute(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """
    Safely execute a function and return (success, result_or_error)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_msg = f"Error in {func.__name__}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, str(e)


async def async_safe_execute(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """
    Safely execute an async function and return (success, result_or_error)
    """
    try:
        result = await func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_msg = f"Error in {func.__name__}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, str(e)


def format_error_message(error: Exception, context: str = "") -> str:
    """Format error message for user display"""
    error_type = type(error).__name__
    error_msg = str(error)
    
    if context:
        return f"❌ Error in {context}: {error_type} - {error_msg}"
    return f"❌ {error_type}: {error_msg}"
