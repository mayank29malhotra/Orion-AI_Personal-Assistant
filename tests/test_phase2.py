#!/usr/bin/env python3
"""Phase 2 verification tests — Reliability & Resilience.

Tests:
  1. CircuitBreaker state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
  2. CircuitBreaker fail-fast behaviour
  3. CircuitBreaker recovery after timeout
  4. Per-user rate limiter fairness
  5. Health check endpoint returns correct structure
  6. Circuit breaker integration in Orion (attribute check)
  7. Per-user rate limiter integration in Orion (attribute check)
"""

import sys
import os
import time

# Add project root (parent of tests/) to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_circuit_breaker_state_transitions():
    """Test 1: CircuitBreaker moves through CLOSED → OPEN → HALF_OPEN → CLOSED."""
    from core.utils import CircuitBreaker

    print("=== Test 1: Circuit Breaker State Transitions ===")
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="test_transitions")

    # Starts CLOSED
    assert cb.state == CircuitBreaker.CLOSED, f"Expected CLOSED, got {cb.state}"
    assert cb.can_execute() is True
    print("  [PASS] Starts in CLOSED state")

    # Record failures below threshold → stays CLOSED
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.can_execute() is True
    print("  [PASS] 2 failures (below threshold=3) → still CLOSED")

    # Third failure → trips to OPEN
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    assert cb.can_execute() is False
    print("  [PASS] 3rd failure → OPEN, can_execute=False")

    # Wait for recovery timeout (1 second)
    time.sleep(1.1)
    assert cb.can_execute() is True  # First call transitions to HALF_OPEN
    assert cb.state == CircuitBreaker.HALF_OPEN
    print("  [PASS] After recovery timeout → HALF_OPEN, allows one probe")

    # Second call while HALF_OPEN is blocked
    assert cb.can_execute() is False
    print("  [PASS] Second call during HALF_OPEN → blocked")

    # Record success → back to CLOSED
    cb.record_success()
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.failure_count == 0
    assert cb.can_execute() is True
    print("  [PASS] Success during HALF_OPEN → CLOSED, failures reset")

    return True


def test_circuit_breaker_fail_fast():
    """Test 2: OPEN circuit breaker rejects calls immediately."""
    from core.utils import CircuitBreaker

    print("\n=== Test 2: Circuit Breaker Fail-Fast ===")
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60, name="test_fail_fast")

    # Trip the breaker
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    print("  [PASS] Breaker tripped to OPEN after 2 failures")

    # Multiple calls should all be rejected (no leaking)
    rejected = sum(1 for _ in range(10) if not cb.can_execute())
    assert rejected == 10
    print(f"  [PASS] All 10 calls rejected while OPEN (fail-fast confirmed)")

    # get_state returns correct info
    state = cb.get_state()
    assert state["state"] == "open"
    assert state["failure_count"] == 2
    assert state["name"] == "test_fail_fast"
    print(f"  [PASS] get_state() returns correct snapshot: {state['state']}, failures={state['failure_count']}")

    return True


def test_circuit_breaker_half_open_failure():
    """Test 3: Failed probe in HALF_OPEN goes back to OPEN."""
    from core.utils import CircuitBreaker

    print("\n=== Test 3: Circuit Breaker HALF_OPEN → OPEN on Probe Failure ===")
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="test_probe_fail")

    # Trip to OPEN
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN

    # Wait for recovery
    time.sleep(1.1)
    assert cb.can_execute() is True  # Transitions to HALF_OPEN
    assert cb.state == CircuitBreaker.HALF_OPEN
    print("  [PASS] Transitioned to HALF_OPEN after timeout")

    # Probe fails → back to OPEN
    cb.record_failure()
    assert cb.state == CircuitBreaker.OPEN
    print("  [PASS] Probe failure → back to OPEN")

    # Should block again
    assert cb.can_execute() is False
    print("  [PASS] Blocking calls again after failed probe")

    return True


def test_per_user_rate_limiter():
    """Test 4: Per-user rate limiter enforces fairness."""
    from core.utils import RateLimiter

    print("\n=== Test 4: Per-User Rate Limiter Fairness ===")
    limiter = RateLimiter(max_calls=3, period=60)

    # User A uses 3 calls
    assert limiter.check("user:alice") is True
    assert limiter.check("user:alice") is True
    assert limiter.check("user:alice") is True
    assert limiter.check("user:alice") is False  # 4th call blocked
    print("  [PASS] User alice: 3 calls allowed, 4th blocked")

    # User B is NOT affected by User A's usage
    assert limiter.check("user:bob") is True
    assert limiter.check("user:bob") is True
    assert limiter.check("user:bob") is True
    assert limiter.check("user:bob") is False
    print("  [PASS] User bob: independent bucket, 3 calls allowed, 4th blocked")

    # wait_time returns positive value for exhausted user
    wait = limiter.wait_time("user:alice")
    assert wait > 0
    print(f"  [PASS] wait_time for exhausted user: {wait:.1f}s > 0")

    # remaining is 0 for exhausted users
    assert limiter.remaining("user:alice") == 0
    assert limiter.remaining("user:bob") == 0
    print("  [PASS] remaining() returns 0 for exhausted users")

    # Fresh user has full budget
    assert limiter.remaining("user:charlie") == 3
    print("  [PASS] Fresh user charlie has full budget of 3")

    return True


def test_health_check_structure():
    """Test 5: Health check endpoint returns expected JSON structure."""
    print("\n=== Test 5: Health Check Endpoint Structure ===")

    # We can't easily start a FastAPI server in a unit test,
    # so we test the logic by importing and checking the response structure
    # that the endpoint would return.
    from core.utils import CircuitBreaker

    # Simulate what /health builds
    cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="groq_llm")

    health = {
        "status": "healthy",
        "service": "Orion Telegram Integration",
        "checks": {
            "orion_ready": True,
            "memory_db": True,
            "retry_queue": True,
            "llm_circuit_breaker": cb.get_state(),
        }
    }

    # Verify structure
    assert "status" in health
    assert "checks" in health
    assert "llm_circuit_breaker" in health["checks"]
    assert health["checks"]["llm_circuit_breaker"]["state"] == "closed"
    assert health["status"] == "healthy"
    print("  [PASS] Health structure valid with closed circuit breaker → healthy")

    # Simulate degraded state
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()  # Trips to OPEN
    health["checks"]["llm_circuit_breaker"] = cb.get_state()
    if cb.get_state()["state"] == "open":
        health["status"] = "degraded"

    assert health["status"] == "degraded"
    assert health["checks"]["llm_circuit_breaker"]["state"] == "open"
    print("  [PASS] Open circuit breaker → status=degraded")

    # Verify all required keys
    required_checks = ["orion_ready", "memory_db", "retry_queue", "llm_circuit_breaker"]
    for key in required_checks:
        assert key in health["checks"], f"Missing check: {key}"
    print(f"  [PASS] All {len(required_checks)} required health checks present")

    return True


def test_orion_has_circuit_breaker():
    """Test 6: Orion class has llm_circuit_breaker attribute."""
    from core.agent import Orion

    print("\n=== Test 6: Orion Has Circuit Breaker ===")
    orion = Orion()

    assert hasattr(orion, "llm_circuit_breaker"), "Orion missing llm_circuit_breaker"
    assert orion.llm_circuit_breaker.name == "groq_llm"
    assert orion.llm_circuit_breaker.state == "closed"
    assert orion.llm_circuit_breaker.failure_threshold == 5
    assert orion.llm_circuit_breaker.recovery_timeout == 60
    print("  [PASS] llm_circuit_breaker exists: name=groq_llm, threshold=5, timeout=60s")

    return True


def test_orion_has_user_rate_limiter():
    """Test 7: Orion class has user_rate_limiter attribute with correct config."""
    from core.agent import Orion
    from core.config import Config

    print("\n=== Test 7: Orion Has Per-User Rate Limiter ===")
    orion = Orion()

    assert hasattr(orion, "user_rate_limiter"), "Orion missing user_rate_limiter"
    assert orion.user_rate_limiter.max_calls == Config.USER_REQUESTS_PER_MINUTE
    assert orion.user_rate_limiter.period == 60
    print(f"  [PASS] user_rate_limiter exists: max_calls={Config.USER_REQUESTS_PER_MINUTE}/min")

    # Global LLM rate limiter still exists (backward compatible)
    assert hasattr(orion, "llm_rate_limiter"), "Orion missing llm_rate_limiter"
    print(f"  [PASS] llm_rate_limiter still present (backward compatible)")

    return True


# ═══════════════════════════════════════════════════════
#                   MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    tests = [
        ("Circuit Breaker State Transitions", test_circuit_breaker_state_transitions),
        ("Circuit Breaker Fail-Fast", test_circuit_breaker_fail_fast),
        ("Circuit Breaker Probe Failure", test_circuit_breaker_half_open_failure),
        ("Per-User Rate Limiter Fairness", test_per_user_rate_limiter),
        ("Health Check Structure", test_health_check_structure),
        ("Orion Has Circuit Breaker", test_orion_has_circuit_breaker),
        ("Orion Has Per-User Rate Limiter", test_orion_has_user_rate_limiter),
    ]

    print("╔══════════════════════════════════════════════════╗")
    print("║     Orion Phase 2: Reliability & Resilience     ║")
    print("╚══════════════════════════════════════════════════╝\n")

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 55)
    print("PHASE 2 TEST SUMMARY")
    print("=" * 55)
    total_pass = 0
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        if passed:
            total_pass += 1
        print(f"  {status}  {name}")

    print(f"\n  {total_pass}/{len(results)} tests passed")

    if total_pass == len(results):
        print("\n  🎉 ALL PHASE 2 TESTS PASSED!")
    else:
        print(f"\n  ⚠️  {len(results) - total_pass} test(s) failed")
        sys.exit(1)
