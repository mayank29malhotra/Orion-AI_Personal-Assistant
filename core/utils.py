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
        self._structured_logger.propagate = False  # Don't send messages to parent "Orion" logger
        
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
            self.logger.error(message, exc_info=True) # detailed human-readable log with stack trace
        else:
            self.logger.error(message)  # only msg in human-readable log
        self._emit_json("ERROR", message, context) # always emit structured log for errors, even if context is empty
    
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
    """Simple in-memory cache with TTL.

    Stats counters (`_hits`, `_misses`) and `backend_name` were added in
    Phase 6.3 to give the in-memory cache parity with `RedisCache` for the
    `/metrics` surface. Existing callers using only `.get()`/`.set()` are
    unaffected.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
        self._sets = 0
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                self._hits += 1
                return value
            else:
                del self.cache[key]
        self._misses += 1
        return None
    
    def set(self, key: str, value: Any):
        self.cache[key] = (value, time.time())
        self._sets += 1
    
    def delete(self, key: str):
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        self.cache.clear()
    
    def size(self) -> int:
        return len(self.cache)

    @property
    def backend_name(self) -> str:
        """Backend identifier for /metrics. In-memory cache always returns 'local'."""
        return "local"

    def get_stats(self) -> Dict[str, Any]:
        """Stats dict consumed by /metrics. Mirror of RedisCache.get_stats()."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total else 0.0
        return {
            "backend": self.backend_name,
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "size": self.size(),
            "hit_rate": round(hit_rate, 3),
        }


class RedisCache:
    """Distributed key-value cache backed by Redis (Phase 6.3).

    Drop-in replacement for ``Cache`` (same ``.get()`` / ``.set()`` interface)
    used to share idempotent search results across Orion instances and to
    survive process restarts.

    Storage:
        SET cache:{namespace}:{key} <json-or-str>  EX <ttl_seconds>
        GET cache:{namespace}:{key}

    Values are JSON-encoded so any JSON-serializable Python object round-trips.
    Strings are stored directly (no JSON wrapping) for the common search-tool
    case where the cached value is already a formatted string.

    Failure handling — dual-mode (Decision 23, generalized to caches):
        Any Redis exception is caught and the call is delegated to
        ``self.fallback`` (a live in-memory ``Cache``). The system never raises
        on a cache lookup. ``backend_name`` reflects the backend used by the
        most recent ``get()`` so /metrics shows the active mode.
    """

    def __init__(
        self,
        redis_client: Any,
        ttl_seconds: int = 600,
        namespace: str = "orion",
        fallback: Optional["Cache"] = None,
    ):
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.namespace = namespace
        self.fallback = fallback if fallback is not None else Cache(ttl_seconds=ttl_seconds)
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._errors = 0
        self._last_backend = "redis"

    def _redis_key(self, key: str) -> str:
        return f"{self.namespace}:cache:{key}"

    def get(self, key: str) -> Optional[Any]:
        rkey = self._redis_key(key)
        try:
            raw = self.redis.get(rkey)
            self._last_backend = "redis"
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            # Try JSON decode; fall back to raw string for non-JSON values.
            import json as _json
            try:
                return _json.loads(raw)
            except (ValueError, TypeError):
                return raw
        except Exception as exc:
            self._errors += 1
            self._last_backend = "local"
            logger.warning(
                f"RedisCache get falling back to local for key={key}",
                event="search_cache_fallback",
                error=f"{type(exc).__name__}: {exc}",
                op="get",
            )
            return self.fallback.get(key)

    def set(self, key: str, value: Any):
        rkey = self._redis_key(key)
        try:
            import json as _json
            if isinstance(value, str):
                payload = value
            else:
                payload = _json.dumps(value, default=str)
            # SET with EX is atomic; the key always carries its TTL.
            self.redis.set(rkey, payload, ex=self.ttl)
            self._sets += 1
            self._last_backend = "redis"
        except Exception as exc:
            self._errors += 1
            self._last_backend = "local"
            logger.warning(
                f"RedisCache set falling back to local for key={key}",
                event="search_cache_fallback",
                error=f"{type(exc).__name__}: {exc}",
                op="set",
            )
            self.fallback.set(key, value)

    def delete(self, key: str):
        try:
            self.redis.delete(self._redis_key(key))
        except Exception:
            pass
        self.fallback.delete(key)

    def size(self) -> int:
        # Best-effort: Redis SCAN would be needed for an exact count; return
        # the fallback's size which is a reasonable lower bound.
        return self.fallback.size()

    @property
    def backend_name(self) -> str:
        return self._last_backend

    def get_stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total else 0.0
        return {
            "backend": self.backend_name,
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "errors": self._errors,
            "size": self.size(),
            "hit_rate": round(hit_rate, 3),
        }


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

    @property
    def backend_name(self) -> str:
        """Backend identifier for /metrics and structured logs."""
        return "local"


class RedisRateLimiter:
    """Distributed fixed-window rate limiter backed by Redis (Phase 6.1).

    Same public interface as `RateLimiter` (`check`, `wait_time`, `remaining`,
    `backend_name`) so it is a drop-in replacement at the call site.

    Algorithm — canonical Redis recipe:
        val = INCR  rate:{namespace}:{key}
        if val == 1:
            EXPIRE rate:{namespace}:{key} period_seconds
        if val > max_calls:
            return False  (denied; wait_time() returns remaining TTL)
        return True

    Correctness rests on `INCR` being atomic on the Redis server. This is the
    standard fixed-window algorithm; we do NOT use sorted-set sliding windows
    because at 10 req/min scale the extra precision is not worth the extra
    commands (see Decision 24 in project_memory/DECISIONS.md).

    Failure handling — dual-mode (Decision 23):
        Any Redis exception (ConnectionError, TimeoutError, RedisError, ...) is
        caught, logged via `logger.warning(event="rate_limiter_fallback", ...)`,
        and the call is delegated to `self.fallback` (a live in-memory
        `RateLimiter`). The system never raises and never blocks user requests
        on Redis problems. `backend_name` reflects the backend used by the
        most recent `check()` call so /metrics shows the active mode.
    """

    def __init__(
        self,
        redis_client: Any,
        max_calls: int = 60,
        period: int = 60,
        namespace: str = "orion",
        fallback: Optional["RateLimiter"] = None,
    ):
        self.redis = redis_client
        self.max_calls = max_calls
        self.period = period
        self.namespace = namespace
        # Live fallback kept hot so any Redis blip is invisible to callers.
        self.fallback = fallback if fallback is not None else RateLimiter(
            max_calls=max_calls, period=period
        )
        self._last_backend = "redis"

    def _redis_key(self, key: str) -> str:
        return f"{self.namespace}:rate:{key}"

    def check(self, key: str = "default") -> bool:
        """Atomically increment the counter and return whether the call is allowed.

        On any Redis error, falls back to the in-memory limiter so that callers
        never see Redis failures.
        """
        rkey = self._redis_key(key)
        try:
            # Atomic on the server side; safe under any number of concurrent callers.
            val = self.redis.incr(rkey)
            if val == 1:
                # First hit in this window — install the TTL.
                self.redis.expire(rkey, self.period)
            self._last_backend = "redis"
            return val <= self.max_calls
        except Exception as exc:
            # Decision 23: dual-mode. Log and delegate; never raise.
            logger.warning(
                f"RedisRateLimiter falling back to local for key={key}",
                event="rate_limiter_fallback",
                error=f"{type(exc).__name__}: {exc}",
                key=key,
            )
            self._last_backend = "local"
            return self.fallback.check(key)

    def wait_time(self, key: str = "default") -> float:
        """Seconds until the current window expires (capped at `period`)."""
        rkey = self._redis_key(key)
        try:
            ttl = self.redis.ttl(rkey)
            if ttl is None or ttl < 0:
                # -1 = no expiry, -2 = key missing → no wait needed
                return 0.0
            return float(min(ttl, self.period))
        except Exception:
            # Mirror check()'s fallback behavior so /metrics stays consistent.
            return self.fallback.wait_time(key)

    def remaining(self, key: str = "default") -> int:
        """Best-effort remaining calls in the current window."""
        rkey = self._redis_key(key)
        try:
            val_raw = self.redis.get(rkey)
            used = int(val_raw) if val_raw is not None else 0
            return max(0, self.max_calls - used)
        except Exception:
            return self.fallback.remaining(key)

    @property
    def backend_name(self) -> str:
        """Backend used by the most recent check() — 'redis' or 'local'."""
        return self._last_backend


#study
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


def retry_on_error(max_retries=3, delay=1.0, backoff=2.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1

                    if retries == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed ({retries}/{max_retries}). "
                        f"Retrying in {current_delay}s..."
                    )

                    time.sleep(current_delay)
                    current_delay *= backoff

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
