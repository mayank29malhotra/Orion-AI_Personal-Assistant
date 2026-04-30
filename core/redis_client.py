"""Optional Redis client for Orion AI (Phase 6.0).

Redis is OPTIONAL infrastructure. Every caller of `get_redis_client()` MUST handle
a `None` return value and fall back to its in-memory or SQLite implementation.

Contract
--------
- If `Config.REDIS_ENABLED` is False                  → returns None.
- If `Config.REDIS_URL` is empty                      → returns None (with warning).
- If the URL is unreachable / the PING fails          → returns None (with warning).
- Otherwise                                            → returns a connected `redis.Redis`
  instance configured with `decode_responses=True` so all string ops return `str`.

The factory caches the client at module level so repeated calls are cheap. Use
`reset_redis_client()` in tests to swap the cached instance (e.g. with fakeredis).

Health
------
`is_available()` performs a cached PING (5-second TTL on the result) so health and
metrics endpoints can be polled at any frequency without hammering Redis.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.config import Config

logger = logging.getLogger("Orion")

# Module-level singletons. `_client` may be a real `redis.Redis`, a fakeredis
# instance (in tests), or None when Redis is disabled/unreachable.
_client: Optional[object] = None
_initialized: bool = False
_last_ping_ok: bool = False
_last_ping_at: float = 0.0
_PING_CACHE_SECONDS = 5.0


def get_redis_client() -> Optional[object]:
    """Return a connected Redis client, or None if Redis is disabled/unreachable.

    Idempotent: subsequent calls return the cached instance. Use
    `reset_redis_client()` to clear the cache (primarily for tests).
    """
    global _client, _initialized

    if _initialized:
        return _client

    _initialized = True

    if not Config.REDIS_ENABLED:
        logger.info("Redis disabled (REDIS_ENABLED=false) — running in local-only mode")
        _client = None
        return None

    if not Config.REDIS_URL:
        logger.warning("REDIS_ENABLED=true but REDIS_URL is empty — Redis features disabled")
        _client = None
        return None

    try:
        import redis  # Local import so the dependency is only required when used.

        client = redis.Redis.from_url(
            Config.REDIS_URL,
            socket_timeout=Config.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=Config.REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
        # Verify connectivity at startup so failures surface in logs immediately
        # rather than on the first hot-path call.
        client.ping()
        logger.info(f"Redis connected (url={_redact_url(Config.REDIS_URL)})")
        _client = client
        return client
    except Exception as exc:  # ConnectionError, TimeoutError, ImportError, AuthenticationError, ...
        logger.warning(
            f"Redis unavailable, falling back to local-only mode: "
            f"{type(exc).__name__}: {exc}"
        )
        _client = None
        return None


def is_available() -> bool:
    """Cheap, cached liveness check used by /health and /metrics.

    Uses a 5-second cache so polling endpoints don't generate excess PING traffic.
    Returns False if Redis is disabled, unreachable, or the last PING failed.
    """
    global _last_ping_ok, _last_ping_at

    client = get_redis_client()
    if client is None:
        return False

    now = time.time()
    if now - _last_ping_at < _PING_CACHE_SECONDS:
        return _last_ping_ok

    try:
        client.ping()
        _last_ping_ok = True
    except Exception:
        _last_ping_ok = False
    _last_ping_at = now
    return _last_ping_ok


def get_status() -> dict:
    """Return a dict suitable for /health and /metrics.

    Keys:
      enabled    — whether Config.REDIS_ENABLED is true
      connected  — whether the cached client is non-None and PING succeeds
      mode       — "enabled" | "disabled" | "unreachable"
      latency_ms — last successful PING round-trip in milliseconds, or None
    """
    enabled = bool(Config.REDIS_ENABLED)
    if not enabled:
        return {"enabled": False, "connected": False, "mode": "disabled", "latency_ms": None}

    client = get_redis_client()
    if client is None:
        return {"enabled": True, "connected": False, "mode": "unreachable", "latency_ms": None}

    try:
        start = time.time()
        client.ping()
        latency_ms = int((time.time() - start) * 1000)
        return {"enabled": True, "connected": True, "mode": "enabled", "latency_ms": latency_ms}
    except Exception:
        return {"enabled": True, "connected": False, "mode": "unreachable", "latency_ms": None}


def reset_redis_client(client: Optional[object] = None) -> None:
    """Clear the cached client, optionally injecting a replacement (for tests).

    Pass `client=fakeredis.FakeRedis(decode_responses=True)` to make every
    subsequent `get_redis_client()` call return that instance.
    """
    global _client, _initialized, _last_ping_ok, _last_ping_at
    _client = client
    _initialized = client is not None
    _last_ping_ok = False
    _last_ping_at = 0.0


def _redact_url(url: str) -> str:
    """Strip credentials from a redis:// URL for safe logging."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1) if "://" in url else ("redis", url)
    _, host_part = rest.rsplit("@", 1)
    return f"{scheme}://***@{host_part}"
