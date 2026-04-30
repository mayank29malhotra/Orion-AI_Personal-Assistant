"""
Phase 6.3 Tests: Distributed Search Cache (RedisCache + tool integration).

Verifies:
1. In-memory Cache stats parity (hits/misses/hit_rate, backend_name='local').
2. RedisCache stores via SET EX and reads back through GET (fakeredis).
3. RedisCache returns None on miss; falls back to local cache on Redis errors.
4. RedisCache JSON-encodes non-string values; round-trips dict/list.
5. Backend name reflects the most recent op (redis vs. local after error).
6. tools.search.web_search hits the cache on the second call (httpx mocked).
7. tools.search.wikipedia_search hits the cache on the second call (wikipedia mocked).
8. Cache disabled via Config.SEARCH_CACHE_ENABLED=False short-circuits lookups.
9. /metrics exposes orion.search_cache block with required keys.
10. Cache key derivation is deterministic and arg-sensitive.

Tests use fakeredis so no live Redis is required.
"""

import os
import sys
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _fake_redis():
    import fakeredis
    return fakeredis.FakeRedis(decode_responses=True)


class TestInMemoryCacheStats(unittest.TestCase):
    """6.3.1: In-memory Cache exposes stats parity for /metrics."""

    def test_hit_miss_counters(self):
        from core.utils import Cache
        c = Cache(ttl_seconds=60)
        self.assertIsNone(c.get("k"))  # miss
        c.set("k", "v")
        self.assertEqual(c.get("k"), "v")  # hit
        self.assertEqual(c.get("k"), "v")  # hit
        stats = c.get_stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["sets"], 1)
        self.assertEqual(stats["backend"], "local")
        self.assertAlmostEqual(stats["hit_rate"], 2 / 3, places=2)
        print("  [PASS] In-memory Cache stats track hits/misses/sets/hit_rate")


class TestRedisCacheBasics(unittest.TestCase):
    """6.3.2: RedisCache get/set round-trip via SET EX."""

    def test_set_then_get_string(self):
        from core.utils import RedisCache
        r = _fake_redis()
        cache = RedisCache(redis_client=r, ttl_seconds=60, namespace="t")
        self.assertIsNone(cache.get("k"))
        cache.set("k", "hello")
        self.assertEqual(cache.get("k"), "hello")
        # TTL was applied
        ttl = r.ttl("t:cache:k")
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 60)
        print("  [PASS] RedisCache string round-trip with TTL")

    def test_set_then_get_dict_json(self):
        from core.utils import RedisCache
        cache = RedisCache(redis_client=_fake_redis(), ttl_seconds=60, namespace="t2")
        payload = {"items": [1, 2, 3], "meta": {"q": "x"}}
        cache.set("k", payload)
        self.assertEqual(cache.get("k"), payload)
        print("  [PASS] RedisCache JSON-round-trips dict values")

    def test_miss_returns_none(self):
        from core.utils import RedisCache
        cache = RedisCache(redis_client=_fake_redis(), ttl_seconds=60, namespace="t3")
        self.assertIsNone(cache.get("missing"))
        stats = cache.get_stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hits"], 0)
        print("  [PASS] RedisCache miss returns None and increments miss counter")


class TestRedisCacheFallback(unittest.TestCase):
    """6.3.3: RedisCache falls back to local cache on Redis errors."""

    def test_get_falls_back_on_redis_error(self):
        from core.utils import RedisCache, Cache
        broken = MagicMock()
        broken.get = MagicMock(side_effect=ConnectionError("boom"))
        broken.set = MagicMock(side_effect=ConnectionError("boom"))

        local = Cache(ttl_seconds=60)
        local.set("k", "from-local")
        cache = RedisCache(redis_client=broken, ttl_seconds=60, namespace="x", fallback=local)

        # get() should delegate to fallback after the redis error
        self.assertEqual(cache.get("k"), "from-local")
        self.assertEqual(cache.backend_name, "local")
        self.assertGreaterEqual(cache.get_stats()["errors"], 1)
        print("  [PASS] RedisCache.get falls back to local Cache on Redis error")

    def test_set_falls_back_on_redis_error(self):
        from core.utils import RedisCache, Cache
        broken = MagicMock()
        broken.set = MagicMock(side_effect=ConnectionError("boom"))
        local = Cache(ttl_seconds=60)
        cache = RedisCache(redis_client=broken, ttl_seconds=60, namespace="x", fallback=local)

        cache.set("k", "v")  # should not raise
        # Stored in fallback
        self.assertEqual(local.get("k"), "v")
        self.assertEqual(cache.backend_name, "local")
        print("  [PASS] RedisCache.set falls back to local Cache on Redis error")


class TestRedisCacheBackendName(unittest.TestCase):
    """6.3.4: backend_name tracks most recent op."""

    def test_backend_switches_on_error(self):
        from core.utils import RedisCache, Cache
        # Use a real fakeredis for the success path, then break it.
        r = _fake_redis()
        cache = RedisCache(redis_client=r, ttl_seconds=60, namespace="n")
        cache.set("k", "v")
        cache.get("k")
        self.assertEqual(cache.backend_name, "redis")

        # Break by replacing get to raise once.
        cache.redis = MagicMock()
        cache.redis.get = MagicMock(side_effect=TimeoutError("slow"))
        cache.get("anything")
        self.assertEqual(cache.backend_name, "local")
        print("  [PASS] backend_name flips redis -> local after a Redis error")


class TestSearchToolWebSearchCache(unittest.TestCase):
    """6.3.5: tools.search.web_search uses the cache on the second call."""

    def setUp(self):
        # Reset module-level cache singleton so each test gets a fresh one.
        from tools.search import reset_search_cache
        reset_search_cache()

    def test_web_search_caches_response(self):
        from tools import search as search_mod
        from tools.search import reset_search_cache

        # Force cache to be a fresh in-memory Cache (cheap, no Redis needed).
        from core.utils import Cache
        search_mod._search_cache = Cache(ttl_seconds=60)
        search_mod._search_cache._enabled = True  # type: ignore[attr-defined]

        # Stub SERPER key + httpx.post
        with patch.object(search_mod, "SERPER_API_KEY", "test-key"):
            fake_resp = MagicMock()
            fake_resp.json.return_value = {
                "organic": [
                    {"title": "T1", "link": "https://e.com/1", "snippet": "snip1"}
                ]
            }
            fake_resp.raise_for_status = MagicMock()

            with patch("httpx.post", return_value=fake_resp) as mock_post:
                # First call -> hits httpx, populates cache
                r1 = search_mod.web_search.invoke({"query": "python", "num_results": 3})
                # Second identical call -> cache hit, no httpx call
                r2 = search_mod.web_search.invoke({"query": "python", "num_results": 3})

        self.assertEqual(r1, r2)
        self.assertEqual(mock_post.call_count, 1, "second call must hit cache, not API")

        stats = search_mod._search_cache.get_stats()
        self.assertEqual(stats["sets"], 1)
        self.assertEqual(stats["hits"], 1)
        reset_search_cache()
        print("  [PASS] web_search second identical call served from cache")


class TestSearchToolWikipediaCache(unittest.TestCase):
    """6.3.6: wikipedia_search uses the cache."""

    def setUp(self):
        from tools.search import reset_search_cache
        reset_search_cache()

    def test_wikipedia_search_caches_response(self):
        from tools import search as search_mod
        from tools.search import reset_search_cache
        from core.utils import Cache

        search_mod._search_cache = Cache(ttl_seconds=60)
        search_mod._search_cache._enabled = True  # type: ignore[attr-defined]

        # Build a stub wikipedia module
        fake_page = MagicMock(title="Python (programming language)", url="https://en.wikipedia.org/wiki/Python_(programming_language)")
        fake_wiki = MagicMock()
        fake_wiki.search = MagicMock(return_value=["Python (programming language)", "Python"])
        fake_wiki.summary = MagicMock(return_value="Python is a high-level language.")
        fake_wiki.page = MagicMock(return_value=fake_page)
        # Ensure DisambiguationError attribute exists for the except clause
        class _NotRaised(Exception):
            options = []
        fake_wiki.DisambiguationError = _NotRaised

        with patch.dict(sys.modules, {"wikipedia": fake_wiki}):
            r1 = search_mod.wikipedia_search.invoke({"query": "python", "sentences": 2})
            r2 = search_mod.wikipedia_search.invoke({"query": "python", "sentences": 2})

        self.assertEqual(r1, r2)
        # API hit only on the first call
        self.assertEqual(fake_wiki.search.call_count, 1)
        self.assertEqual(fake_wiki.summary.call_count, 1)

        stats = search_mod._search_cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["sets"], 1)
        reset_search_cache()
        print("  [PASS] wikipedia_search second identical call served from cache")


class TestCacheDisabled(unittest.TestCase):
    """6.3.7: SEARCH_CACHE_ENABLED=False disables lookups."""

    def test_disabled_cache_short_circuits(self):
        from tools import search as search_mod
        from tools.search import reset_search_cache
        from core.config import Config

        reset_search_cache()
        original = Config.SEARCH_CACHE_ENABLED
        try:
            Config.SEARCH_CACHE_ENABLED = False
            cache = search_mod._get_search_cache()
            # When disabled the helper still returns a Cache, but tags it _enabled=False
            self.assertFalse(getattr(cache, "_enabled", True))

            # web_search must NOT use cache when disabled — verify by mocking httpx
            # twice; both calls must hit the API.
            with patch.object(search_mod, "SERPER_API_KEY", "test-key"):
                fake_resp = MagicMock()
                fake_resp.json.return_value = {
                    "organic": [{"title": "T", "link": "x", "snippet": "s"}]
                }
                fake_resp.raise_for_status = MagicMock()
                with patch("httpx.post", return_value=fake_resp) as mock_post:
                    search_mod.web_search.invoke({"query": "q1"})
                    search_mod.web_search.invoke({"query": "q1"})
            self.assertEqual(mock_post.call_count, 2, "Both calls must hit API when cache disabled")
        finally:
            Config.SEARCH_CACHE_ENABLED = original
            reset_search_cache()
        print("  [PASS] Disabled cache bypasses lookup; both calls hit API")


class TestMetricsExposeSearchCache(unittest.TestCase):
    """6.3.8: /metrics includes orion.search_cache."""

    def test_get_metrics_has_search_cache(self):
        from core.agent import Orion
        from tools.search import reset_search_cache
        reset_search_cache()
        orion = Orion()
        metrics = orion.get_metrics()
        self.assertIn("search_cache", metrics)
        block = metrics["search_cache"]
        for key in ("backend", "hits", "misses", "sets", "size", "hit_rate"):
            self.assertIn(key, block, f"search_cache must include {key}")
        print("  [PASS] /metrics exposes orion.search_cache with required keys")


class TestCacheKeyDeterminism(unittest.TestCase):
    """6.3.9: cache key is deterministic and arg-sensitive."""

    def test_same_args_same_key_different_args_different_key(self):
        from tools.search import _make_cache_key
        a = _make_cache_key("web_search", "python", 5)
        b = _make_cache_key("web_search", "python", 5)
        c = _make_cache_key("web_search", "python", 10)
        d = _make_cache_key("wikipedia_search", "python", 5)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        # All keys are short and prefixed by tool name
        for k in (a, b, c, d):
            self.assertLess(len(k), 64)
        self.assertTrue(a.startswith("web_search:"))
        self.assertTrue(d.startswith("wikipedia_search:"))
        print("  [PASS] Cache key deterministic + arg-sensitive + short")


class TestRedisCacheNamespace(unittest.TestCase):
    """6.3.10: namespaces isolate caches sharing one Redis."""

    def test_different_namespaces_dont_collide(self):
        from core.utils import RedisCache
        r = _fake_redis()
        a = RedisCache(redis_client=r, ttl_seconds=60, namespace="ns_a")
        b = RedisCache(redis_client=r, ttl_seconds=60, namespace="ns_b")
        a.set("k", "from-a")
        b.set("k", "from-b")
        self.assertEqual(a.get("k"), "from-a")
        self.assertEqual(b.get("k"), "from-b")
        print("  [PASS] RedisCache namespace isolation works")


if __name__ == "__main__":
    unittest.main(verbosity=2)
