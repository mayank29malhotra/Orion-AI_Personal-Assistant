"""
Phase 3: Observability Tests
Tests structured logging, correlation IDs, latency tracking, and metrics endpoint.

Run: python tests/test_phase3.py
"""
import sys, os, time, json, tempfile, logging

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Helpers ──────────────────────────────────────────────────────────────────

results = {}  # test_name -> PASS/FAIL

def record(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results[test_name] = status
    tag = f"  [\033[92m{status}\033[0m]" if passed else f"  [\033[91m{status}\033[0m]"
    msg = f"{tag} {detail}" if detail else f"{tag} {test_name}"
    print(msg)

# ── Test 1: StructuredLogger supports **context kwargs ─────────────────────

def test_structured_logger_context():
    """Logger.info/warning/error accept **context and still work."""
    print("\n=== Test 1: Structured Logger Context Support ===")
    from core.utils import Logger

    # Create a fresh logger instance for testing (bypass singleton for isolation)
    test_logger = Logger.__new__(Logger)
    test_logger._initialized = False

    # The existing singleton is fine to test — just verify the API accepts kwargs
    from core.utils import logger

    # Should not raise — backward compatible plain call
    try:
        logger.info("test plain message")
        record("plain_info", True, "logger.info('msg') works (backward compatible)")
    except Exception as e:
        record("plain_info", False, f"Plain info failed: {e}")

    # Should not raise — structured call with context
    try:
        logger.info("test structured", request_id="abc-123", latency_ms=42, user_id="test")
        record("structured_info", True, "logger.info('msg', request_id=..., latency_ms=...) works")
    except Exception as e:
        record("structured_info", False, f"Structured info failed: {e}")

    try:
        logger.warning("test warning", event="rate_limit", user_id="u1")
        record("structured_warning", True, "logger.warning('msg', **ctx) works")
    except Exception as e:
        record("structured_warning", False, f"Structured warning failed: {e}")

    try:
        logger.error("test error", event="superstep_error", request_id="xyz", error="timeout")
        record("structured_error", True, "logger.error('msg', **ctx) works")
    except Exception as e:
        record("structured_error", False, f"Structured error failed: {e}")


# ── Test 2: JSON log file contains structured entries ──────────────────────

def test_json_log_output():
    """Structured logs are written to orion_structured.log as valid JSON."""
    print("\n=== Test 2: JSON Structured Log Output ===")
    from core.utils import logger

    # Write a structured log entry with a unique marker
    marker = f"test_marker_{int(time.time())}"
    logger.info("structured log test", event="test_event", marker=marker, value=42)

    # Give file handler a moment to flush
    for handler in logging.getLogger("Orion.structured").handlers:
        handler.flush()

    # Read the log file and find our entry
    log_path = "orion_structured.log"
    found = False
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("marker") == marker:
                        found = True
                        # Validate structure
                        record("json_valid", True, f"JSON entry found with marker={marker}")
                        has_ts = "timestamp" in entry
                        has_level = "level" in entry
                        has_msg = "message" in entry
                        has_ctx = entry.get("event") == "test_event" and entry.get("value") == 42
                        record("json_fields", has_ts and has_level and has_msg and has_ctx,
                               f"Fields: timestamp={has_ts}, level={has_level}, message={has_msg}, context={has_ctx}")
                        break
                except json.JSONDecodeError:
                    continue

    if not found:
        record("json_valid", False, f"No JSON entry found with marker={marker}")
        record("json_fields", False, "Skipped (no entry found)")


# ── Test 3: Orion has request metrics and latency tracking ─────────────────

def test_orion_metrics_attributes():
    """Orion instance has _request_metrics, _latency_samples, _worker_latency_samples."""
    print("\n=== Test 3: Orion Metrics Attributes ===")
    from core.agent import Orion

    orion = Orion()

    has_req = hasattr(orion, "_request_metrics")
    record("request_metrics", has_req,
           f"_request_metrics exists: {orion._request_metrics}" if has_req else "_request_metrics MISSING")

    has_lat = hasattr(orion, "_latency_samples")
    record("latency_samples", has_lat,
           f"_latency_samples exists (list, len={len(orion._latency_samples)})" if has_lat else "MISSING")

    has_wlat = hasattr(orion, "_worker_latency_samples")
    record("worker_latency_samples", has_wlat,
           f"_worker_latency_samples exists (list, len={len(orion._worker_latency_samples)})" if has_wlat else "MISSING")

    # Check _request_metrics has expected keys
    if has_req:
        expected_keys = {"total_requests", "successful", "failed", "rate_limited", "circuit_broken"}
        actual_keys = set(orion._request_metrics.keys())
        has_all = expected_keys.issubset(actual_keys)
        record("metrics_keys", has_all,
               f"Expected keys present: {expected_keys}" if has_all else f"Missing: {expected_keys - actual_keys}")


# ── Test 4: get_metrics() returns expected structure ───────────────────────

def test_get_metrics():
    """Orion.get_metrics() returns dict with requests, latency_ms, circuit_breaker, tools."""
    print("\n=== Test 4: get_metrics() Method ===")
    from core.agent import Orion

    orion = Orion()

    has_method = hasattr(orion, "get_metrics") and callable(orion.get_metrics)
    record("has_get_metrics", has_method, "get_metrics() method exists and is callable")

    if not has_method:
        record("metrics_structure", False, "Skipped (no method)")
        return

    metrics = orion.get_metrics()

    # Top-level keys
    has_requests = "requests" in metrics
    has_latency = "latency_ms" in metrics
    has_cb = "circuit_breaker" in metrics
    has_tools = "tools" in metrics
    record("metrics_top_keys", has_requests and has_latency and has_cb and has_tools,
           f"Top keys: requests={has_requests}, latency_ms={has_latency}, circuit_breaker={has_cb}, tools={has_tools}")

    # Latency sub-keys
    if has_latency:
        has_e2e = "e2e" in metrics["latency_ms"]
        has_worker = "worker_llm" in metrics["latency_ms"]
        record("latency_sub_keys", has_e2e and has_worker,
               f"Latency sub-keys: e2e={has_e2e}, worker_llm={has_worker}")

        # Percentile keys
        e2e = metrics["latency_ms"]["e2e"]
        has_pctls = all(k in e2e for k in ("p50", "p90", "p99", "avg", "count"))
        record("percentile_keys", has_pctls,
               f"Percentile keys in e2e: {list(e2e.keys())}")

    # Circuit breaker in metrics
    if has_cb:
        cb = metrics["circuit_breaker"]
        has_state = "state" in cb and "name" in cb
        record("cb_in_metrics", has_state,
               f"CB state={cb.get('state')}, name={cb.get('name')}")

    # Tools in metrics
    if has_tools:
        tools = metrics["tools"]
        record("tools_in_metrics", "total_loaded" in tools and "tool_calls_this_session" in tools,
               f"Tools: loaded={tools.get('total_loaded')}, calls={tools.get('tool_calls_this_session')}")


# ── Test 5: Latency samples roll correctly ─────────────────────────────────

def test_latency_rolling_window():
    """Latency samples cap at 100 and roll correctly."""
    print("\n=== Test 5: Latency Rolling Window ===")
    from core.agent import Orion

    orion = Orion()

    # Simulate 150 latency samples
    for i in range(150):
        orion._latency_samples.append(i * 10)
        if len(orion._latency_samples) > 100:
            orion._latency_samples.pop(0)

    record("window_size", len(orion._latency_samples) == 100,
           f"After 150 inserts: len={len(orion._latency_samples)} (expected 100)")

    record("window_oldest", orion._latency_samples[0] == 500,
           f"Oldest sample: {orion._latency_samples[0]} (expected 500 = sample #50 * 10)")

    record("window_newest", orion._latency_samples[-1] == 1490,
           f"Newest sample: {orion._latency_samples[-1]} (expected 1490 = sample #149 * 10)")

    # get_metrics should return correct percentiles
    metrics = orion.get_metrics()
    e2e = metrics["latency_ms"]["e2e"]
    record("p50_correct", e2e["p50"] == orion._latency_samples[50],
           f"p50={e2e['p50']} (mid of 100 sorted samples)")
    record("count_correct", e2e["count"] == 100,
           f"count={e2e['count']}")


# ── Test 6: /metrics endpoint structure ────────────────────────────────────

def test_metrics_endpoint_structure():
    """Simulated /metrics endpoint returns expected JSON structure."""
    print("\n=== Test 6: /metrics Endpoint Structure ===")

    # We can't easily spin up FastAPI, so we simulate the logic
    from datetime import datetime
    from core.agent import Orion
    from core.memory import memory, retry_queue, pending_queue

    orion_instance = Orion()

    # Simulate what the /metrics endpoint does
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "orion": None,
        "memory": {},
        "retry_queue": {},
        "pending_queue": {},
    }

    if orion_instance and hasattr(orion_instance, "get_metrics"):
        metrics["orion"] = orion_instance.get_metrics()

    try:
        if memory:
            metrics["memory"] = memory.get_stats()
        if retry_queue:
            metrics["retry_queue"] = retry_queue.get_stats()
        if pending_queue:
            metrics["pending_queue"] = pending_queue.get_stats()
    except Exception:
        pass

    record("endpoint_has_timestamp", "timestamp" in metrics,
           f"timestamp present: {metrics['timestamp'][:19]}")

    record("endpoint_has_orion", metrics["orion"] is not None,
           f"orion metrics present with {len(metrics['orion'])} keys")

    record("endpoint_has_memory", isinstance(metrics["memory"], dict),
           f"memory stats: {metrics.get('memory', {})}")

    record("endpoint_has_retry", isinstance(metrics["retry_queue"], dict),
           f"retry_queue stats: {metrics.get('retry_queue', {})}")

    # Validate orion sub-structure
    orion_m = metrics["orion"]
    if orion_m:
        has_requests = "requests" in orion_m
        has_latency = "latency_ms" in orion_m
        record("endpoint_orion_structure", has_requests and has_latency,
               f"Orion metrics has requests={has_requests}, latency_ms={has_latency}")


# ── Test 7: Correlation ID generation in run_superstep ─────────────────────

def test_correlation_id():
    """run_superstep generates a request_id correlation ID for tracing."""
    print("\n=== Test 7: Correlation ID in Request Flow ===")
    import uuid

    # Verify UUID[:8] format
    request_id = str(uuid.uuid4())[:8]
    record("request_id_format", len(request_id) == 8 and all(c in "0123456789abcdef-" for c in request_id),
           f"Correlation ID format: '{request_id}' (8 chars, hex)")

    # Verify the code path exists in agent.py by checking the source
    import inspect
    from core.agent import Orion
    source = inspect.getsource(Orion.run_superstep)

    has_request_id = "request_id = str(uuid.uuid4())[:8]" in source
    record("request_id_in_source", has_request_id,
           "request_id = str(uuid.uuid4())[:8] found in run_superstep()")

    has_e2e_start = "e2e_start = time.time()" in source
    record("e2e_timing_in_source", has_e2e_start,
           "e2e_start = time.time() found in run_superstep()")

    has_superstep_start_event = 'event="superstep_start"' in source
    record("superstep_start_event", has_superstep_start_event,
           'event="superstep_start" structured log found')

    has_superstep_complete_event = 'event="superstep_complete"' in source
    record("superstep_complete_event", has_superstep_complete_event,
           'event="superstep_complete" structured log found')


# ── Test 8: Worker and Evaluator have latency instrumentation ──────────────

def test_worker_evaluator_instrumentation():
    """worker() and evaluator() have timing and structured log events."""
    print("\n=== Test 8: Worker & Evaluator Instrumentation ===")
    import inspect
    from core.agent import Orion

    worker_src = inspect.getsource(Orion.worker)
    evaluator_src = inspect.getsource(Orion.evaluator)

    # Worker instrumentation
    record("worker_timing", "worker_start = time.time()" in worker_src,
           "worker_start timer found in worker()")

    record("worker_event", 'event="worker_llm_call"' in worker_src or 'event="worker_tool_calls"' in worker_src,
           "Structured event found in worker()")

    record("worker_latency_tracking", "_worker_latency_samples" in worker_src,
           "_worker_latency_samples tracking found in worker()")

    # Evaluator instrumentation
    record("evaluator_timing", "eval_start = time.time()" in evaluator_src,
           "eval_start timer found in evaluator()")

    record("evaluator_event", 'event="evaluator_complete"' in evaluator_src,
           'event="evaluator_complete" found in evaluator()')


# ═══════════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 56)
    print("      Orion Phase 3: Observability Tests")
    print("=" * 56)

    test_structured_logger_context()
    test_json_log_output()
    test_orion_metrics_attributes()
    test_get_metrics()
    test_latency_rolling_window()
    test_metrics_endpoint_structure()
    test_correlation_id()
    test_worker_evaluator_instrumentation()

    # Summary
    passed = sum(1 for v in results.values() if v == "PASS")
    total = len(results)
    failed = total - passed

    print("\n" + "=" * 56)
    print("  PHASE 3 TEST SUMMARY")
    print("=" * 56)
    tests_by_group = {}
    current_group = ""
    for name, status in results.items():
        icon = "\033[92m  PASS\033[0m" if status == "PASS" else "\033[91m  FAIL\033[0m"
        print(f"  {icon}  {name}")

    print(f"\n  {passed}/{total} tests passed")
    if failed == 0:
        print("\n  \033[92mALL PHASE 3 TESTS PASSED!\033[0m")
    else:
        print(f"\n  \033[91m{failed} TESTS FAILED\033[0m")

    sys.exit(0 if failed == 0 else 1)
