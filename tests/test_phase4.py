"""
Phase 4 Tests: Hardening (Input Validation, Config Validation, Graceful Shutdown)

Tests cover:
1. ChatRequest Pydantic model — valid/invalid inputs, sanitization, edge cases
2. Config.validate() — expanded checks for numeric bounds, model names, ports
3. Config.validate_or_fail() — fail-fast on missing GROQ_API_KEY, warnings for others
4. Orion input validation integration — run_superstep rejects bad input before LLM
5. Graceful shutdown attributes — _shutting_down, _in_flight_requests, _in_flight_lock
6. Graceful shutdown method — exists, sets flag, in_flight tracking
7. Shutdown rejection — requests rejected when _shutting_down is True
8. Metrics include shutdown state — get_metrics() returns shutdown sub-object
"""

import sys
import os
import unittest
import threading

# Ensure project root is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestChatRequestModel(unittest.TestCase):
    """Test 4.1: Pydantic input validation model."""
    
    def test_valid_request(self):
        """Valid ChatRequest should pass all fields through."""
        from core.models import ChatRequest
        req = ChatRequest(
            message="What's the weather?",
            user_id="user123",
            channel="telegram",
            success_criteria="Be accurate",
        )
        self.assertEqual(req.message, "What's the weather?")
        self.assertEqual(req.user_id, "user123")
        self.assertEqual(req.channel, "telegram")
        self.assertEqual(req.success_criteria, "Be accurate")
        print("  [PASS] Valid ChatRequest accepted")
    
    def test_default_values(self):
        """ChatRequest should have sensible defaults for optional fields."""
        from core.models import ChatRequest
        req = ChatRequest(message="hello")
        self.assertEqual(req.user_id, "anonymous")
        self.assertEqual(req.channel, "default")
        self.assertIn("clear and accurate", req.success_criteria)
        print("  [PASS] Default values applied correctly")
    
    def test_empty_message_rejected(self):
        """Empty string message should be rejected."""
        from core.models import ChatRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ChatRequest(message="")
        print("  [PASS] Empty message rejected")
    
    def test_whitespace_message_rejected(self):
        """Whitespace-only message should be rejected."""
        from core.models import ChatRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ChatRequest(message="   \n\t  ")
        print("  [PASS] Whitespace-only message rejected")

    def test_message_stripped(self):
        """Messages with leading/trailing whitespace should be stripped."""
        from core.models import ChatRequest
        req = ChatRequest(message="  hello world  ")
        self.assertEqual(req.message, "hello world")
        print("  [PASS] Message whitespace stripped")

    def test_too_long_message_rejected(self):
        """Messages exceeding max_length should be rejected."""
        from core.models import ChatRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ChatRequest(message="x" * 10001)
        print("  [PASS] Overly long message rejected")

    def test_channel_invalid_chars_rejected(self):
        """Channel names with special characters should be rejected."""
        from core.models import ChatRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ChatRequest(message="hello", channel="tele gram!")
        with self.assertRaises(ValidationError):
            ChatRequest(message="hello", channel="my/channel")
        print("  [PASS] Invalid channel characters rejected")

    def test_channel_normalized_lowercase(self):
        """Channel names should be normalized to lowercase."""
        from core.models import ChatRequest
        req = ChatRequest(message="hello", channel="Telegram")
        self.assertEqual(req.channel, "telegram")
        print("  [PASS] Channel normalized to lowercase")

    def test_user_id_stripped(self):
        """User ID whitespace should be stripped."""
        from core.models import ChatRequest
        req = ChatRequest(message="hello", user_id="  user123  ")
        self.assertEqual(req.user_id, "user123")
        print("  [PASS] User ID whitespace stripped")

    def test_valid_channels(self):
        """Common channel names should all pass validation."""
        from core.models import ChatRequest
        for ch in ["telegram", "gradio", "email", "api", "test-channel", "my_channel"]:
            req = ChatRequest(message="hello", channel=ch)
            self.assertIsNotNone(req)
        print("  [PASS] All valid channel names accepted")


class TestConfigValidation(unittest.TestCase):
    """Test 4.2: Config.validate() expanded checks."""
    
    def test_validate_returns_list(self):
        """validate() should return a list of errors (possibly empty)."""
        from core.config import Config
        errors = Config.validate()
        self.assertIsInstance(errors, list)
        print("  [PASS] validate() returns list")
    
    def test_validate_checks_numeric_bounds(self):
        """validate() should catch negative/zero numeric values."""
        from core.config import Config
        
        original = Config.LLM_REQUESTS_PER_MINUTE
        try:
            Config.LLM_REQUESTS_PER_MINUTE = -1
            errors = Config.validate()
            has_llm_rate_error = any("LLM_REQUESTS_PER_MINUTE" in e for e in errors)
            self.assertTrue(has_llm_rate_error, f"Expected LLM_REQUESTS_PER_MINUTE error, got: {errors}")
        finally:
            Config.LLM_REQUESTS_PER_MINUTE = original
        print("  [PASS] Negative numeric values caught")

    def test_validate_checks_model_names(self):
        """validate() should catch empty model names."""
        from core.config import Config
        
        original = Config.WORKER_MODEL
        try:
            Config.WORKER_MODEL = ""
            errors = Config.validate()
            has_model_error = any("WORKER_MODEL" in e for e in errors)
            self.assertTrue(has_model_error, f"Expected WORKER_MODEL error, got: {errors}")
        finally:
            Config.WORKER_MODEL = original
        print("  [PASS] Empty model names caught")

    def test_validate_checks_port_range(self):
        """validate() should catch invalid port numbers."""
        from core.config import Config
        
        original = Config.SMTP_PORT
        try:
            Config.SMTP_PORT = 99999
            errors = Config.validate()
            has_port_error = any("SMTP_PORT" in e for e in errors)
            self.assertTrue(has_port_error, f"Expected SMTP_PORT error, got: {errors}")
        finally:
            Config.SMTP_PORT = original
        print("  [PASS] Invalid port numbers caught")

    def test_validate_or_fail_exists(self):
        """validate_or_fail() should exist as a classmethod."""
        from core.config import Config
        self.assertTrue(hasattr(Config, 'validate_or_fail'))
        self.assertTrue(callable(Config.validate_or_fail))
        print("  [PASS] validate_or_fail() exists")

    def test_validate_or_fail_raises_on_missing_groq_key(self):
        """validate_or_fail() should raise ConfigValidationError when GROQ_API_KEY is None."""
        from core.config import Config, ConfigValidationError
        
        original = Config.GROQ_API_KEY
        try:
            Config.GROQ_API_KEY = None
            with self.assertRaises(ConfigValidationError) as ctx:
                Config.validate_or_fail()
            self.assertIn("GROQ_API_KEY", str(ctx.exception))
        finally:
            Config.GROQ_API_KEY = original
        print("  [PASS] Missing GROQ_API_KEY raises ConfigValidationError")

    def test_config_validation_error_is_exception(self):
        """ConfigValidationError should be a proper Exception subclass."""
        from core.config import ConfigValidationError
        self.assertTrue(issubclass(ConfigValidationError, Exception))
        err = ConfigValidationError("test error")
        self.assertEqual(str(err), "test error")
        print("  [PASS] ConfigValidationError is proper Exception subclass")

    def test_validate_or_fail_passes_with_valid_config(self):
        """validate_or_fail() should not raise when GROQ_API_KEY is set."""
        from core.config import Config
        
        original = Config.GROQ_API_KEY
        try:
            Config.GROQ_API_KEY = "test_key_1234"
            # Should not raise
            result = Config.validate_or_fail()
            self.assertIsInstance(result, list)
        finally:
            Config.GROQ_API_KEY = original
        print("  [PASS] Valid config passes validate_or_fail()")


class TestOrionInputValidation(unittest.TestCase):
    """Test 4.1 integration: Orion.run_superstep validates inputs."""
    
    def test_orion_imports_chat_request(self):
        """core.agent should import ChatRequest from core.models."""
        import core.agent as agent_module
        self.assertTrue(hasattr(agent_module, 'ChatRequest'))
        print("  [PASS] ChatRequest imported in agent module")

    def test_run_superstep_has_validation(self):
        """run_superstep source should contain 'ChatRequest' for input validation."""
        import inspect
        from core.agent import Orion
        source = inspect.getsource(Orion.run_superstep)
        self.assertIn("ChatRequest", source)
        self.assertIn("ValidationError", source)
        print("  [PASS] run_superstep contains input validation code")

    def test_run_superstep_has_shutdown_check(self):
        """run_superstep should check _shutting_down flag."""
        import inspect
        from core.agent import Orion
        source = inspect.getsource(Orion.run_superstep)
        self.assertIn("_shutting_down", source)
        self.assertIn("shutting down", source.lower())
        print("  [PASS] run_superstep checks shutdown flag")


class TestGracefulShutdownAttributes(unittest.TestCase):
    """Test 4.3: Graceful shutdown fields on Orion."""
    
    def test_shutting_down_flag(self):
        """Orion should have _shutting_down = False by default."""
        from core.agent import Orion
        orion = Orion()
        self.assertFalse(orion._shutting_down)
        print("  [PASS] _shutting_down defaults to False")

    def test_in_flight_requests_counter(self):
        """Orion should have _in_flight_requests = 0 by default."""
        from core.agent import Orion
        orion = Orion()
        self.assertEqual(orion._in_flight_requests, 0)
        print("  [PASS] _in_flight_requests defaults to 0")

    def test_in_flight_lock_exists(self):
        """Orion should have a threading.Lock for in-flight tracking."""
        from core.agent import Orion
        orion = Orion()
        self.assertIsInstance(orion._in_flight_lock, type(threading.Lock()))
        print("  [PASS] _in_flight_lock is a threading.Lock")

    def test_graceful_shutdown_method_exists(self):
        """Orion should have a graceful_shutdown() async method."""
        import asyncio
        from core.agent import Orion
        orion = Orion()
        self.assertTrue(hasattr(orion, 'graceful_shutdown'))
        self.assertTrue(asyncio.iscoroutinefunction(orion.graceful_shutdown))
        print("  [PASS] graceful_shutdown() is async method")

    def test_shutdown_sets_flag(self):
        """Calling graceful_shutdown() should set _shutting_down to True."""
        import asyncio
        from core.agent import Orion
        orion = Orion()
        
        # Run the shutdown (no in-flight requests, so it completes immediately)
        asyncio.run(orion.graceful_shutdown(timeout=2))
        self.assertTrue(orion._shutting_down)
        print("  [PASS] graceful_shutdown() sets _shutting_down flag")

    def test_shutdown_returns_result(self):
        """graceful_shutdown() should return a dict with stats."""
        import asyncio
        from core.agent import Orion
        orion = Orion()
        
        result = asyncio.run(orion.graceful_shutdown(timeout=2))
        self.assertIsInstance(result, dict)
        self.assertIn("requests_drained", result)
        self.assertIn("forced", result)
        self.assertIn("elapsed_s", result)
        self.assertTrue(result["requests_drained"])
        self.assertFalse(result["forced"])
        print("  [PASS] graceful_shutdown() returns expected stats dict")


class TestMetricsIncludeShutdown(unittest.TestCase):
    """Test that get_metrics() includes shutdown state."""
    
    def test_metrics_has_shutdown_key(self):
        """get_metrics() should include 'shutdown' key."""
        from core.agent import Orion
        orion = Orion()
        metrics = orion.get_metrics()
        self.assertIn("shutdown", metrics)
        print("  [PASS] get_metrics() includes 'shutdown' key")
    
    def test_metrics_shutdown_fields(self):
        """Shutdown metrics should contain shutting_down and in_flight_requests."""
        from core.agent import Orion
        orion = Orion()
        metrics = orion.get_metrics()
        shutdown = metrics["shutdown"]
        self.assertIn("shutting_down", shutdown)
        self.assertIn("in_flight_requests", shutdown)
        self.assertFalse(shutdown["shutting_down"])
        self.assertEqual(shutdown["in_flight_requests"], 0)
        print("  [PASS] Shutdown metrics have correct fields and defaults")


class TestInFlightTracking(unittest.TestCase):
    """Test that in-flight request counting works in run_superstep source."""
    
    def test_run_superstep_increments_in_flight(self):
        """run_superstep source should increment _in_flight_requests."""
        import inspect
        from core.agent import Orion
        source = inspect.getsource(Orion.run_superstep)
        self.assertIn("_in_flight_requests += 1", source)
        print("  [PASS] run_superstep increments in-flight counter")

    def test_run_superstep_decrements_in_finally(self):
        """run_superstep should decrement _in_flight_requests in a finally block."""
        import inspect
        from core.agent import Orion
        source = inspect.getsource(Orion.run_superstep)
        self.assertIn("_in_flight_requests -= 1", source)
        self.assertIn("finally:", source)
        print("  [PASS] run_superstep decrements in-flight in finally block")


class TestLifespanShutdownIntegration(unittest.TestCase):
    """Test that telegram.py lifespan uses graceful_shutdown."""
    
    def test_lifespan_calls_graceful_shutdown(self):
        """telegram.py lifespan should call graceful_shutdown."""
        import inspect
        from integrations.telegram import lifespan
        source = inspect.getsource(lifespan)
        self.assertIn("graceful_shutdown", source)
        print("  [PASS] Lifespan handler calls graceful_shutdown")


# =====================================================
# Test Runner
# =====================================================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PHASE 4 TESTS: Hardening")
    print("=" * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    test_classes = [
        TestChatRequestModel,
        TestConfigValidation,
        TestOrionInputValidation,
        TestGracefulShutdownAttributes,
        TestMetricsIncludeShutdown,
        TestInFlightTracking,
        TestLifespanShutdownIntegration,
    ]
    
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    
    total = suite.countTestCases()
    print(f"\nRunning {total} tests across {len(test_classes)} test classes...\n")
    
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    print(f"\n{'=' * 60}")
    passed = total - len(result.failures) - len(result.errors)
    print(f"RESULTS: {passed}/{total} passed")
    if result.failures:
        print(f"  FAILURES: {len(result.failures)}")
        for test, traceback in result.failures:
            print(f"    - {test}: {traceback.split(chr(10))[-2]}")
    if result.errors:
        print(f"  ERRORS: {len(result.errors)}")
        for test, traceback in result.errors:
            print(f"    - {test}: {traceback.split(chr(10))[-2]}")
    print("=" * 60)
    
    sys.exit(0 if result.wasSuccessful() else 1)
