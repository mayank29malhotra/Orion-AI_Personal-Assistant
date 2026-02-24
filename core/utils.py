"""
Utility functions for Orion AI Personal Assistant
Includes logging, caching, rate limiting, and error handling.
"""
import logging
import time
import json
import threading
import functools
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import traceback


class Logger:
    """
    Structured logging system with dual output:
    - Console + orion.log: human-readable format (same as before)
    - orion_structured.log: JSON-structured logs with correlation IDs, latency, etc.
    
    Singleton pattern for consistent logging across modules.
    
    Usage:
        logger.info("message")                           # Plain log (backward compatible)
        logger.info("event", request_id="abc", ms=120)   # Structured log with context
    """
    
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
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
        
        # Console handler (human-readable)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        
        # File handler (human-readable, detailed)
        file_handler = logging.FileHandler('orion.log')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        
        # Structured JSON logger (separate logger to avoid duplicate console output)
        self._structured_logger = logging.getLogger("Orion.structured")
        self._structured_logger.setLevel(logging.DEBUG)
        self._structured_logger.propagate = False  # Don't bubble up to parent "Orion" logger
        
        try:
            json_handler = logging.FileHandler('orion_structured.log', encoding='utf-8')
            json_handler.setLevel(logging.DEBUG)
            json_handler.setFormatter(logging.Formatter('%(message)s'))
            self._structured_logger.addHandler(json_handler)
            self._json_enabled = True
        except Exception:
            self._json_enabled = False
    
    def _emit_json(self, level: str, message: str, context: dict):
        """Emit a JSON-structured log entry to orion_structured.log."""
        if not self._json_enabled:
            return
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message,
                **context,
            }
            self._structured_logger.info(json.dumps(entry, default=str))
        except Exception:
            pass  # Never let structured logging break the application
    
    def info(self, message: str, **context):
        self.logger.info(message)
        if context:
            self._emit_json("INFO", message, context)
    
    def error(self, message: str, exc_info=None, **context):
        if exc_info:
            self.logger.error(message, exc_info=True)
        else:
            self.logger.error(message)
        self._emit_json("ERROR", message, context)
    
    def warning(self, message: str, **context):
        self.logger.warning(message)
        if context:
            self._emit_json("WARNING", message, context)
    
    def debug(self, message: str, **context):
        self.logger.debug(message)
        if context:
            self._emit_json("DEBUG", message, context)
    
    def critical(self, message: str, **context):
        self.logger.critical(message)
        self._emit_json("CRITICAL", message, context)


# Global logger instance
logger = Logger()


class Cache:
    """Simple in-memory cache with TTL."""
    
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
    
    def delete(self, key: str):
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        self.cache.clear()
    
    def size(self) -> int:
        return len(self.cache)


class RateLimiter:
    """Rate limiting for API calls."""
    
    def __init__(self, max_calls: int = 60, period: int = 60):
        self.max_calls = max_calls
        self.period = period
        self.calls: Dict[str, list] = defaultdict(list)
    
    def check(self, key: str = "default") -> bool:
        """Check if rate limit is exceeded."""
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
        """Get wait time in seconds before next call is allowed."""
        if not self.calls[key]:
            return 0.0
        
        oldest_call = min(self.calls[key])
        time_passed = time.time() - oldest_call
        
        if time_passed >= self.period:
            return 0.0
        
        return self.period - time_passed
    
    def remaining(self, key: str = "default") -> int:
        """Get remaining calls allowed in current period."""
        now = time.time()
        self.calls[key] = [
            call_time for call_time in self.calls[key]
            if now - call_time < self.period
        ]
        return max(0, self.max_calls - len(self.calls[key]))


class CircuitBreaker:
    """Circuit breaker for external service calls.
    
    Prevents cascading failures by failing fast when an upstream service
    (e.g., Groq LLM) is consistently failing.
    
    States:
        CLOSED  — Normal operation. Calls pass through.
        OPEN    — Service is down. Calls are rejected immediately (fail fast).
        HALF_OPEN — Recovery probe. One test call is allowed through.
    
    Transitions:
        CLOSED → OPEN:       After `failure_threshold` consecutive failures.
        OPEN → HALF_OPEN:    After `recovery_timeout` seconds elapse.
        HALF_OPEN → CLOSED:  If the test call succeeds.
        HALF_OPEN → OPEN:    If the test call fails.
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, name: str = "default"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0
        self.last_state_change: float = time.time()
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """Check if the circuit allows a call through."""
        with self._lock:
            if self.state == self.CLOSED:
                return True
            elif self.state == self.OPEN:
                # Check if recovery timeout has elapsed → transition to HALF_OPEN
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = self.HALF_OPEN
                    self.last_state_change = time.time()
                    logger.info(f"Circuit breaker '{self.name}' -> HALF_OPEN (testing recovery)")
                    return True  # Allow one probe call
                return False
            elif self.state == self.HALF_OPEN:
                # Only one probe call at a time; block others while probe is in flight
                return False
        return False

    def record_success(self):
        """Record a successful call. Resets failure count and closes the circuit."""
        with self._lock:
            old_state = self.state
            self.failure_count = 0
            self.success_count += 1
            self.state = self.CLOSED
            self.last_state_change = time.time()
            if old_state != self.CLOSED:
                logger.info(f"Circuit breaker '{self.name}' -> CLOSED (recovered after success)")

    def record_failure(self):
        """Record a failed call. May trip the circuit to OPEN."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == self.HALF_OPEN:
                # Probe call failed → back to OPEN
                self.state = self.OPEN
                self.last_state_change = time.time()
                logger.warning(f"Circuit breaker '{self.name}' -> OPEN (probe failed, {self.failure_count} failures)")
            elif self.failure_count >= self.failure_threshold:
                self.state = self.OPEN
                self.last_state_change = time.time()
                logger.warning(
                    f"Circuit breaker '{self.name}' -> OPEN after {self.failure_count} consecutive failures. "
                    f"Will retry in {self.recovery_timeout}s."
                )

    def get_state(self) -> dict:
        """Return a serializable snapshot of the circuit breaker state."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_s": self.recovery_timeout,
                "seconds_since_last_failure": round(time.time() - self.last_failure_time, 1) if self.last_failure_time else None,
            }


# Global cache and rate limiter
cache = Cache(ttl_seconds=300)
rate_limiter = RateLimiter(max_calls=60, period=60)


def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying functions on error."""
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
    """Decorator for retrying async functions on error."""
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
    """Safely execute a function and return (success, result_or_error)."""
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_msg = f"Error in {func.__name__}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, str(e)


async def async_safe_execute(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """Safely execute an async function and return (success, result_or_error)."""
    try:
        result = await func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_msg = f"Error in {func.__name__}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, str(e)


def format_error_message(error: Exception, context: str = "") -> str:
    """Format error message for user display."""
    error_type = type(error).__name__
    error_msg = str(error)
    
    if context:
        return f"❌ Error in {context}: {error_type} - {error_msg}"
    return f"❌ {error_type}: {error_msg}"


def format_timestamp(dt: datetime = None) -> str:
    """Format datetime for display."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
