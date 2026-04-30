"""
Phase 6.0 Tests: Optional Redis Foundation.

Verifies that:
1. Config exposes Redis fields with sensible defaults.
2. Config.validate() warns (does NOT fail) on bad/missing Redis settings.
3. core.redis_client.get_redis_client() returns None when disabled or unreachable.
4. core.redis_client.get_redis_client() returns a working client when fakeredis is injected.
5. core.redis_client.get_status() returns the expected shape for /health and /metrics.
6. Telegram /health endpoint includes a `redis` subsystem block.
7. Telegram /metrics endpoint includes a `redis` block.

Tests use `fakeredis` so no live Redis server is required in CI.
"""

import sys
import os
import unittest

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestRedisConfigFields(unittest.TestCase):
    """Test 6.0.1: Config exposes Redis fields."""

    def test_config_has_redis_fields(self):
        from core.config import Config
        for attr in ("REDIS_ENABLED", "REDIS_URL", "REDIS_NAMESPACE", "REDIS_SOCKET_TIMEOUT"):
            self.assertTrue(hasattr(Config, attr), f"Config is missing {attr}")
        # Defaults
        self.assertIsInstance(Config.REDIS_ENABLED, bool)
        self.assertIsInstance(Config.REDIS_URL, str)
        self.assertIsInstance(Config.REDIS_NAMESPACE, str)
        self.assertIsInstance(Config.REDIS_SOCKET_TIMEOUT, float)
        self.assertGreater(Config.REDIS_SOCKET_TIMEOUT, 0)
        print("  [PASS] Config exposes REDIS_* fields with correct types")

    def test_validate_warns_on_redis_enabled_without_url(self):
        """REDIS_ENABLED=true with empty URL must produce a warning, NOT raise."""
        from core.config import Config
        original_enabled = Config.REDIS_ENABLED
        original_url = Config.REDIS_URL
        try:
            Config.REDIS_ENABLED = True
            Config.REDIS_URL = ""
            errors = Config.validate()
            self.assertTrue(
                any("REDIS_URL" in e for e in errors),
                f"Expected a warning about empty REDIS_URL, got: {errors}"
            )
            # Must NOT raise — Redis is optional infra
            Config.validate_or_fail()
            print("  [PASS] Bad Redis config produces warning, not fatal error")
        finally:
            Config.REDIS_ENABLED = original_enabled
            Config.REDIS_URL = original_url


class TestRedisClientFactory(unittest.TestCase):
    """Test 6.0.2: get_redis_client() handles all paths gracefully."""

    def setUp(self):
        # Reset cached client between tests
        from core.redis_client import reset_redis_client
        reset_redis_client(None)

    def test_returns_none_when_disabled(self):
        from core import redis_client
        from core.config import Config
        original = Config.REDIS_ENABLED
        try:
            Config.REDIS_ENABLED = False
            redis_client.reset_redis_client(None)
            self.assertIsNone(redis_client.get_redis_client())
            print("  [PASS] Returns None when REDIS_ENABLED=false")
        finally:
            Config.REDIS_ENABLED = original
            redis_client.reset_redis_client(None)

    def test_returns_none_when_url_empty(self):
        from core import redis_client
        from core.config import Config
        original_enabled = Config.REDIS_ENABLED
        original_url = Config.REDIS_URL
        try:
            Config.REDIS_ENABLED = True
            Config.REDIS_URL = ""
            redis_client.reset_redis_client(None)
            self.assertIsNone(redis_client.get_redis_client())
            print("  [PASS] Returns None when REDIS_URL is empty")
        finally:
            Config.REDIS_ENABLED = original_enabled
            Config.REDIS_URL = original_url
            redis_client.reset_redis_client(None)

    def test_returns_none_on_unreachable_url(self):
        """Bad URL must not raise — must log warning and return None."""
        from core import redis_client
        from core.config import Config
        original_enabled = Config.REDIS_ENABLED
        original_url = Config.REDIS_URL
        try:
            Config.REDIS_ENABLED = True
            # Port 1 is reserved/unbound on virtually every system
            Config.REDIS_URL = "redis://127.0.0.1:1/0"
            redis_client.reset_redis_client(None)
            result = redis_client.get_redis_client()
            self.assertIsNone(result, "Unreachable Redis must yield None, not raise")
            print("  [PASS] Returns None on unreachable URL (no exception)")
        finally:
            Config.REDIS_ENABLED = original_enabled
            Config.REDIS_URL = original_url
            redis_client.reset_redis_client(None)

    def test_returns_client_when_fakeredis_injected(self):
        """Inject fakeredis via reset_redis_client() and confirm round-trip."""
        try:
            import fakeredis
        except ImportError:
            self.skipTest("fakeredis not installed")
        from core import redis_client

        fake = fakeredis.FakeRedis(decode_responses=True)
        redis_client.reset_redis_client(fake)
        client = redis_client.get_redis_client()
        self.assertIsNotNone(client)
        client.set("orion:phase6:test", "ok")
        self.assertEqual(client.get("orion:phase6:test"), "ok")
        self.assertTrue(redis_client.is_available())
        print("  [PASS] Returns working client when fakeredis injected")
        redis_client.reset_redis_client(None)


class TestRedisStatusShape(unittest.TestCase):
    """Test 6.0.3: get_status() returns dicts with expected keys."""

    def setUp(self):
        from core.redis_client import reset_redis_client
        reset_redis_client(None)

    def test_status_when_disabled(self):
        from core import redis_client
        from core.config import Config
        original = Config.REDIS_ENABLED
        try:
            Config.REDIS_ENABLED = False
            redis_client.reset_redis_client(None)
            status = redis_client.get_status()
            self.assertEqual(status["enabled"], False)
            self.assertEqual(status["connected"], False)
            self.assertEqual(status["mode"], "disabled")
            self.assertIsNone(status["latency_ms"])
            print("  [PASS] get_status() shape correct when disabled")
        finally:
            Config.REDIS_ENABLED = original
            redis_client.reset_redis_client(None)

    def test_status_when_connected(self):
        try:
            import fakeredis
        except ImportError:
            self.skipTest("fakeredis not installed")
        from core import redis_client
        from core.config import Config
        original = Config.REDIS_ENABLED
        try:
            Config.REDIS_ENABLED = True
            redis_client.reset_redis_client(fakeredis.FakeRedis(decode_responses=True))
            status = redis_client.get_status()
            self.assertTrue(status["enabled"])
            self.assertTrue(status["connected"])
            self.assertEqual(status["mode"], "enabled")
            self.assertIsInstance(status["latency_ms"], int)
            self.assertGreaterEqual(status["latency_ms"], 0)
            print("  [PASS] get_status() shape correct when connected")
        finally:
            Config.REDIS_ENABLED = original
            redis_client.reset_redis_client(None)


class TestOrionStartsWithoutRedis(unittest.TestCase):
    """Test 6.0.4: Orion class exposes self.redis attribute (default None)."""

    def test_orion_has_redis_attribute_default_none(self):
        from core.agent import Orion
        from core.redis_client import reset_redis_client
        reset_redis_client(None)
        # Construct without running async setup() — just verify attribute exists
        orion = Orion()
        self.assertTrue(hasattr(orion, "redis"), "Orion must expose self.redis")
        self.assertIsNone(orion.redis, "Orion.redis defaults to None until setup()")
        print("  [PASS] Orion.redis attribute exists and defaults to None")


class TestHealthAndMetricsEndpoints(unittest.TestCase):
    """Test 6.0.5 + 6.0.6: /health and /metrics include `redis` block."""

    def test_health_includes_redis_subsystem(self):
        from fastapi.testclient import TestClient
        from integrations.telegram import app
        from core.redis_client import reset_redis_client
        reset_redis_client(None)

        client = TestClient(app)
        resp = client.get("/health")
        # Endpoint returns 503 when orion_instance is None (test environment),
        # but the JSON body must still include the redis subsystem.
        self.assertIn(resp.status_code, (200, 503))
        body = resp.json()
        self.assertIn("checks", body)
        self.assertIn("redis", body["checks"], "/health must expose checks.redis")
        redis_block = body["checks"]["redis"]
        self.assertIn("enabled", redis_block)
        self.assertIn("connected", redis_block)
        self.assertIn("mode", redis_block)
        print("  [PASS] /health includes redis subsystem block")

    def test_metrics_includes_redis_block(self):
        from fastapi.testclient import TestClient
        from integrations.telegram import app
        from core.redis_client import reset_redis_client
        reset_redis_client(None)

        client = TestClient(app)
        resp = client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("redis", body, "/metrics must expose top-level `redis` key")
        self.assertIn("enabled", body["redis"])
        self.assertIn("connected", body["redis"])
        self.assertIn("mode", body["redis"])
        print("  [PASS] /metrics includes redis block")


if __name__ == "__main__":
    unittest.main(verbosity=2)
