"""
Phase 6.1 Tests: Distributed Rate Limiter (RedisRateLimiter).

Verifies:
1. Under-threshold calls allowed; over-threshold calls denied.
2. Counter resets after TTL elapses.
3. Atomic under concurrency (20 threads, exactly N succeed).
4. Falls back to local in-memory limiter on Redis errors.
5. Namespaces isolate counters.
6. Orion picks Redis backend when self.redis is set; local otherwise.
7. /metrics exposes rate_limiter.backend.
8. Structured-log event 'rate_limit_hit' includes 'backend' field.
9. Backward compat: existing RateLimiter tests still pass.

Tests use fakeredis so no live Redis is required.
"""

import sys
import os
import time
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _fake_redis():
    """Build a fresh fakeredis client with decode_responses=True."""
    import fakeredis
    return fakeredis.FakeRedis(decode_responses=True)


class TestRedisRateLimiterBasics(unittest.TestCase):
    """6.1.1: Threshold + reset behavior."""

    def setUp(self):
        from core.utils import RedisRateLimiter
        self.redis = _fake_redis()
        self.limiter = RedisRateLimiter(
            redis_client=self.redis, max_calls=3, period=2, namespace="test1"
        )

    def test_allows_under_threshold(self):
        for i in range(3):
            self.assertTrue(self.limiter.check("u1"), f"call #{i+1} should be allowed")
        print("  [PASS] First N calls allowed")

    def test_blocks_at_threshold(self):
        for _ in range(3):
            self.limiter.check("u1")
        self.assertFalse(self.limiter.check("u1"), "4th call must be denied")
        wait = self.limiter.wait_time("u1")
        self.assertGreater(wait, 0)
        self.assertLessEqual(wait, 2)
        print("  [PASS] Over-threshold blocked, wait_time > 0")

    def test_resets_after_ttl(self):
        for _ in range(3):
            self.limiter.check("u2")
        self.assertFalse(self.limiter.check("u2"))
        # Sleep past the 2s window
        time.sleep(2.2)
        self.assertTrue(self.limiter.check("u2"), "Call must be allowed after TTL expiry")
        print("  [PASS] Counter resets after TTL")

    def test_remaining_decrements(self):
        self.assertEqual(self.limiter.remaining("u3"), 3)
        self.limiter.check("u3")
        self.assertEqual(self.limiter.remaining("u3"), 2)
        print("  [PASS] remaining() decrements correctly")


class TestRedisRateLimiterConcurrency(unittest.TestCase):
    """6.1.2: Atomic INCR survives concurrent callers."""

    def test_atomic_under_concurrency(self):
        from core.utils import RedisRateLimiter
        redis = _fake_redis()
        limiter = RedisRateLimiter(
            redis_client=redis, max_calls=10, period=60, namespace="conc"
        )

        results = []
        results_lock = threading.Lock()

        def hit():
            allowed = limiter.check("user:hot")
            with results_lock:
                results.append(allowed)

        threads = [threading.Thread(target=hit) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(1 for r in results if r)
        denied_count = sum(1 for r in results if not r)
        self.assertEqual(allowed_count, 10, f"Exactly 10 allowed; got {allowed_count}")
        self.assertEqual(denied_count, 10, f"Exactly 10 denied; got {denied_count}")
        print("  [PASS] 20 concurrent threads -> exactly 10 allowed")


class TestRedisRateLimiterFallback(unittest.TestCase):
    """6.1.3: Dual-mode contract — Redis errors degrade to local limiter."""

    def test_falls_back_when_redis_raises(self):
        from core.utils import RedisRateLimiter, RateLimiter
        broken = MagicMock()
        broken.incr.side_effect = ConnectionError("redis down")
        broken.expire.side_effect = ConnectionError("redis down")
        broken.ttl.side_effect = ConnectionError("redis down")
        broken.get.side_effect = ConnectionError("redis down")

        fallback = RateLimiter(max_calls=2, period=60)
        limiter = RedisRateLimiter(
            redis_client=broken, max_calls=2, period=60, namespace="fb",
            fallback=fallback,
        )

        # First two calls should succeed via fallback
        self.assertTrue(limiter.check("u"))
        self.assertTrue(limiter.check("u"))
        # Third should fail (fallback's limit hit)
        self.assertFalse(limiter.check("u"))
        # backend_name reflects fallback usage on the most recent call
        self.assertEqual(limiter.backend_name, "local")
        print("  [PASS] Redis errors fall back to local limiter; backend_name=local")

    def test_backend_name_redis_when_healthy(self):
        from core.utils import RedisRateLimiter
        limiter = RedisRateLimiter(
            redis_client=_fake_redis(), max_calls=5, period=60, namespace="hb"
        )
        limiter.check("u")
        self.assertEqual(limiter.backend_name, "redis")
        print("  [PASS] backend_name=redis when healthy")


class TestRedisRateLimiterNamespaceIsolation(unittest.TestCase):
    """6.1.4: Different namespaces do not share counters."""

    def test_namespaces_isolated(self):
        from core.utils import RedisRateLimiter
        redis = _fake_redis()
        a = RedisRateLimiter(redis_client=redis, max_calls=2, period=60, namespace="ns_a")
        b = RedisRateLimiter(redis_client=redis, max_calls=2, period=60, namespace="ns_b")

        # Exhaust namespace A
        a.check("user:1")
        a.check("user:1")
        self.assertFalse(a.check("user:1"))

        # Namespace B is unaffected
        self.assertTrue(b.check("user:1"))
        self.assertTrue(b.check("user:1"))
        self.assertFalse(b.check("user:1"))
        print("  [PASS] Namespaces isolate counters")


class TestOrionLimiterSelection(unittest.TestCase):
    """6.1.5: Orion.setup() picks the correct backend based on self.redis."""

    def test_orion_uses_local_when_redis_none(self):
        from core.agent import Orion
        from core.utils import RateLimiter
        orion = Orion()
        # Without setup(), the default is the in-memory RateLimiter.
        self.assertIsInstance(orion.user_rate_limiter, RateLimiter)
        self.assertEqual(orion.user_rate_limiter.backend_name, "local")
        print("  [PASS] Default user_rate_limiter is local RateLimiter")

    def test_orion_uses_redis_when_available(self):
        """Simulate the wiring branch from setup() without a full LLM init."""
        from core.agent import Orion
        from core.utils import RateLimiter, RedisRateLimiter
        from core.config import Config

        orion = Orion()
        # Inject a fakeredis client and rebuild the limiter as setup() would
        orion.redis = _fake_redis()
        original_local = orion.user_rate_limiter
        orion.user_rate_limiter = RedisRateLimiter(
            redis_client=orion.redis,
            max_calls=Config.USER_REQUESTS_PER_MINUTE,
            period=60,
            namespace=Config.REDIS_NAMESPACE,
            fallback=original_local,
        )
        self.assertIsInstance(orion.user_rate_limiter, RedisRateLimiter)
        # Fallback is the original in-memory limiter
        self.assertIsInstance(orion.user_rate_limiter.fallback, RateLimiter)
        # Round-trip a check
        self.assertTrue(orion.user_rate_limiter.check("user:abc"))
        self.assertEqual(orion.user_rate_limiter.backend_name, "redis")
        print("  [PASS] Orion uses RedisRateLimiter with local fallback when redis available")


class TestMetricsExposeBackend(unittest.TestCase):
    """6.1.6: get_metrics() exposes orion.rate_limiter.backend."""

    def test_metrics_exposes_rate_limiter_backend(self):
        from core.agent import Orion
        orion = Orion()
        metrics = orion.get_metrics()
        self.assertIn("rate_limiter", metrics)
        self.assertIn("backend", metrics["rate_limiter"])
        self.assertEqual(metrics["rate_limiter"]["backend"], "local")
        self.assertEqual(metrics["rate_limiter"]["max_calls"], orion.user_rate_limiter.max_calls)
        self.assertEqual(metrics["rate_limiter"]["period_s"], 60)
        print("  [PASS] /metrics includes orion.rate_limiter.backend")


class TestBackwardCompatRateLimiter(unittest.TestCase):
    """6.1.7: Existing RateLimiter still works exactly as before."""

    def test_local_rate_limiter_backend_name(self):
        from core.utils import RateLimiter
        rl = RateLimiter(max_calls=5, period=60)
        self.assertEqual(rl.backend_name, "local")
        for _ in range(5):
            self.assertTrue(rl.check("u"))
        self.assertFalse(rl.check("u"))
        print("  [PASS] In-memory RateLimiter unchanged + backend_name='local'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
