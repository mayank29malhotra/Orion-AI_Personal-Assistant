# Redis Implementation Plan — Orion AI

> **Scope (locked 2026-04-30):** Only **Phase 6.0 (Foundation)**, **Phase 6.1 (Distributed Rate Limiter)**, and **Phase 6.2 (Distributed LangGraph Checkpoints)** are in scope. Other Redis candidates identified during analysis (cache, queues, conversation memory, distributed circuit breaker) are explicitly deferred and tracked in `/memories/session/plan.md`.

---

## 1. Why Redis (and Why Only These Two Features)

### What is broken / limited today

| Concern | Today's behavior | Limitation |
|---|---|---|
| **Per-user rate limiting** | `RateLimiter` in [core/utils.py](core/utils.py) keeps a `Dict[str, list[float]]` of timestamps in process memory. | Resets on every restart. Cannot be enforced across multiple Orion processes — each instance has its own counter, so a user could double their effective quota by hitting two instances. |
| **LangGraph thread state** | `MemorySaver()` in [core/agent.py](core/agent.py) holds checkpoints in a per-process dict. | All conversation context is lost on restart. Cannot be shared across instances — a user reconnecting to a different process starts a fresh thread. |

### What Redis adds

| Feature | Redis primitive | Improvement |
|---|---|---|
| Rate limiter | `INCR` + `EXPIRE` (atomic, server-side) | Single source of truth; survives restarts; correct under multi-instance and multi-thread concurrency. |
| Checkpoints | `langgraph-checkpoint-redis → RedisSaver` | Conversation threads survive restarts; any Orion instance can resume any user's thread; thread isolation invariant from Phase 1 (`{user_id}_{channel}`) preserved. |

### Why we are stopping at 6.2

- These two changes deliver the **strongest resume / interview signal per hour of work**: distributed rate limiting (~1 day) and horizontal-scale checkpointing (~2 hours).
- Both have **drop-in interfaces** — no changes to call sites, no behavior change when Redis is disabled.
- Other candidates (queues, hybrid memory, distributed CB) need bigger refactors and add more risk than reward right now.
- Single-instance correctness is already solid (Phase 2 circuit breaker, Phase 4 input validation, etc.). 6.1 + 6.2 is the smallest change that turns Orion from "single-process correct" into "designed for horizontal scaling."

### Cross-phase invariants (apply to every phase below)

1. **Optional infra.** Redis being down or `REDIS_ENABLED=false` must leave Orion fully functional — same behavior as today.
2. **No breaking changes.** All 82 existing tests in `tests/test_phase1.py` … `tests/test_phase4.py` must pass unchanged after every phase.
3. **Dual-mode by default.** Each Redis-backed component keeps an in-memory fallback alive. Tests must assert both paths.
4. **Observability.** Each phase updates `/health` and `/metrics` so the active backend is visible at runtime.
5. **Memory protocol.** After each phase, update `project_memory/SESSION_LOG.md`, `CURRENT_STATE.md`, `FILE_INDEX.md`, and `DECISIONS.md` (when a tradeoff was made), per `master_prompt.txt`.

---

## 2. Phase 6.0 — Foundation

> Prerequisite for 6.1 and 6.2. Adds Redis wiring with **zero behavior change** to the running system.

### What this does

- Adds an optional Redis client to Orion. If `REDIS_ENABLED=false` (default) or Redis is unreachable, `Orion.redis` is `None` and the system runs exactly as today.
- Surfaces Redis status in `/health` and `/metrics` so operators can see whether the optional dependency is connected.

### How it improves the system

- Establishes the **dual-mode pattern** every later phase depends on (try Redis → fall back to existing implementation).
- Validates Decision #19 (critical-vs-warning config validation): Redis is optional infra, so a missing/broken Redis URL is a warning, never a fatal startup error.

### Code changes

| File | Change |
|---|---|
| `requirements.txt` | Add `redis>=5.0.0`. Add `fakeredis>=2.20` under a dev/test section (used by 6.1 and 6.2 tests). |
| `core/config.py` | Add fields: `REDIS_URL` (default `""`), `REDIS_ENABLED` (default `False`), `REDIS_NAMESPACE` (default `"orion"`), `REDIS_SOCKET_TIMEOUT` (default `2.0`). Extend `Config.validate()` so that `REDIS_ENABLED=true` with empty `REDIS_URL` produces a non-fatal warning. `validate_or_fail()` must NOT raise on Redis issues. |
| `core/redis_client.py` *(new)* | `get_redis_client()` singleton factory: returns a connected `redis.Redis(decode_responses=True, socket_timeout=…, socket_connect_timeout=…)` or `None` on `ConnectionError` / `TimeoutError` / disabled. Exposes `is_available()` (PING with a 5-second cached result) for cheap health checks. |
| `core/agent.py` → `Orion.setup()` | After `Config.validate_or_fail()`, set `self.redis = get_redis_client()`. Log the chosen mode at startup: `redis_mode=enabled \| disabled \| unavailable`. No other changes in this phase. |
| `integrations/telegram.py` → `/health` | Add a `redis` subsystem block with `connected \| disabled \| unreachable`. Redis being unreachable does NOT cause a 503 (it's optional). |
| `integrations/telegram.py` → `/metrics` | Add `redis.enabled`, `redis.connected`, `redis.latency_ms` (from cached PING). |

### Tests — `tests/test_phase6_foundation.py` *(new)*

1. `test_config_has_redis_fields` — `REDIS_URL`, `REDIS_ENABLED`, `REDIS_NAMESPACE`, `REDIS_SOCKET_TIMEOUT` are present on `Config`.
2. `test_validate_warns_on_redis_enabled_without_url` — non-fatal warning; `validate_or_fail()` does not raise.
3. `test_get_redis_client_returns_none_when_disabled` — `REDIS_ENABLED=False` → returns `None`.
4. `test_get_redis_client_returns_none_on_unreachable_url` — bad URL → returns `None`, no exception bubbles up.
5. `test_get_redis_client_returns_client_when_available` — uses `fakeredis` to confirm a working client is returned and `is_available()` is `True`.
6. `test_orion_setup_works_without_redis` — `Orion.setup()` succeeds with `self.redis is None`; full `run_superstep()` still works end-to-end.
7. `test_health_endpoint_includes_redis_subsystem` — `/health` JSON has a `redis` key with the expected status field.
8. `test_metrics_endpoint_includes_redis_block` — `/metrics` JSON has `redis.enabled`, `redis.connected`, `redis.latency_ms`.

**Regression suite:** all 82 tests from Phases 1–4 must pass with no edits.

### Documentation & comments to update

| File | Update |
|---|---|
| `README.md` | New "Optional Dependencies → Redis" subsection in the configuration/setup area: explain it is optional, list the four env vars, link to Phase 6.0 commit. Update env-var table to include `REDIS_URL`, `REDIS_ENABLED`, `REDIS_NAMESPACE`, `REDIS_SOCKET_TIMEOUT`. |
| `ARCHITECTURE.md` | New "Optional Redis Layer" section under the runtime architecture diagram. State the dual-mode contract (Redis present → distributed; absent → current behavior). |
| `SETUP.md` | Add a "Local Redis (optional)" block: `docker run -p 6379:6379 redis:7-alpine` and the env vars to set. Note: not required to run Orion. |
| `.env.example` *(if present, else create entry in README)* | Add the four Redis env vars commented out with defaults. |
| `core/config.py` | Inline docstrings on each new Redis field describing default and effect when unset. |
| `core/redis_client.py` | Module docstring explaining the dual-mode contract; per-function docstrings for `get_redis_client()` and `is_available()`. |
| `project_memory/SESSION_LOG.md` | Append a 6.0 entry in the standard format from `master_prompt.txt` (timestamp, request, analysis, action, files, outcome, next steps). |
| `project_memory/CURRENT_STATE.md` | Add an "Optional Redis Layer (Phase 6.0)" subsection under "What Exists Now" describing the wiring and that no behavior changes by default. |
| `project_memory/FILE_INDEX.md` | Add `core/redis_client.py` (🆕). Mark `core/config.py`, `core/agent.py`, `integrations/telegram.py`, `requirements.txt` (✏️) with the Phase 6.0 change description. |
| `project_memory/DECISIONS.md` | Add **Decision 22: Redis as optional infra (warning, not fatal)** — restates Decision #19's pattern applied to Redis. Add **Decision 23: dual-mode contract** — Redis-backed components must keep their in-memory fallback alive and tested. |
| `SDE2_UPGRADE_PLAN.md` | Add Phase 6 section with the locked scope (6.0 + 6.1 + 6.2 only) and the explicit deferral of 6.3–6.6 with rationale. |
| `project_memory/TASK_TRACKER.md` | Add Phase 6 rows for 6.0, 6.1, 6.2 with status `In Progress` / `Not Started`. |

### Acceptance criteria for 6.0

- All 82 prior tests pass with no edits.
- All 8 new foundation tests pass.
- With `REDIS_ENABLED=false`, startup log shows `redis_mode=disabled` and Orion behaves exactly as before.
- With `REDIS_ENABLED=true` and a reachable `REDIS_URL`, `/health` shows `redis.status=connected` and `/metrics` shows non-null `redis.latency_ms`.
- With `REDIS_ENABLED=true` and a bogus URL, Orion still starts; `/health` shows `redis.status=unreachable`; HTTP status remains 200.

---

## 3. Phase 6.1 — Distributed Rate Limiter

> Replaces in-process rate limiter dict with atomic Redis sliding-window when Redis is available.

### What this does

- Adds `RedisRateLimiter` next to the existing `RateLimiter` in [core/utils.py](core/utils.py) with the **same `.check(key) -> (allowed, wait_seconds)` interface**.
- `Orion.setup()` selects the Redis-backed limiter when `self.redis` is available, otherwise keeps today's in-memory `RateLimiter`.
- The call site in `run_superstep()` does **not** change — it still calls `self.user_rate_limiter.check(...)`.

### How it improves the system

| Aspect | Before (in-memory dict) | After (Redis `INCR` + `EXPIRE`) |
|---|---|---|
| Restart resilience | Counter resets to zero — user can replay quota immediately. | Counter and TTL persist in Redis. |
| Multi-instance correctness | Each instance has its own counter; user can multiply quota by N. | Single shared counter; quota enforced globally. |
| Concurrency safety | List append is GIL-atomic but the read-then-trim sequence is racy. | `INCR` is server-side atomic; no race regardless of caller threads/processes. |
| Failure behavior | None — limiter cannot fail. | Redis error → falls back to local in-memory limiter; logs `backend=local` for that call; never blocks request flow. |
| Observability | None. | `rate_limit_exceeded` log event includes `backend=redis\|local`; `/metrics` exposes `orion.rate_limiter.backend`. |

### Algorithm choice

Fixed-window via `INCR` + `EXPIRE` (the canonical Redis recipe):

```
val = INCR rate:{namespace}:{key}
if val == 1:
    EXPIRE rate:{namespace}:{key} period_seconds
if val > max_calls:
    ttl = TTL rate:{namespace}:{key}
    return (False, max(ttl, 1))
return (True, 0)
```

This is the documented Redis pattern; correctness rests on `INCR` atomicity. We are deliberately not using sorted-set sliding windows — at 10 req/min scale the extra precision is not worth the extra commands.

### Code changes

| File | Change |
|---|---|
| `core/utils.py` | New `RedisRateLimiter` class (~80 lines). Same constructor signature as `RateLimiter` plus `redis`, `namespace`, and a `fallback: RateLimiter` instance kept alive. `check(key)` runs the `INCR/EXPIRE` recipe inside `try/except (ConnectionError, TimeoutError, RedisError)`; on error logs structured event `rate_limiter_fallback` and delegates to `fallback.check(key)`. |
| `core/agent.py` → `Orion.setup()` | When `self.redis` is not None: `self.user_rate_limiter = RedisRateLimiter(redis=self.redis, namespace=Config.REDIS_NAMESPACE, max_calls=Config.USER_REQUESTS_PER_MINUTE, period=60, fallback=in_memory_limiter)`. Else: keep current behavior. The variable name `self.user_rate_limiter` stays the same. |
| `core/agent.py` → existing rate-limit log call in `run_superstep()` | Add `backend=self.user_rate_limiter.backend_name` to the structured log context. (Property returns `"redis"` or `"local"`.) |
| `core/agent.py` → `get_metrics()` | Add `orion.rate_limiter.backend` field. |

### Tests — `tests/test_phase6_ratelimiter.py` *(new)*

Use `fakeredis` for the Redis-backed cases so CI does not require a live server.

1. `test_redis_limiter_allows_under_threshold` — 9 calls below limit of 10 → all allowed.
2. `test_redis_limiter_blocks_at_threshold` — 11th call → `(False, wait > 0)`.
3. `test_redis_limiter_resets_after_ttl` — advance fake clock past `period` → call allowed again.
4. `test_redis_limiter_atomic_under_concurrency` — 20 threads firing simultaneously against the same key, exactly 10 succeed.
5. `test_redis_limiter_falls_back_when_redis_raises` — patch the client to raise `ConnectionError`; result still sensible; fallback path exercised.
6. `test_redis_limiter_separates_namespaces` — two limiters with different namespaces do not interfere.
7. `test_orion_uses_redis_limiter_when_redis_available` — `self.redis` is a fakeredis client → `Orion.user_rate_limiter` is `RedisRateLimiter`.
8. `test_orion_uses_local_limiter_when_redis_none` — `self.redis is None` → `Orion.user_rate_limiter` is `RateLimiter`.
9. `test_metrics_exposes_rate_limiter_backend` — `/metrics` includes `orion.rate_limiter.backend`.
10. `test_log_event_includes_backend_field` — captured structured-log record on rate-limit hit contains `backend` key.

**Regression suite:** all 82 prior tests, plus the 8 new tests from 6.0, must pass with no edits. Phase 2 rate-limiter tests (test 11 and 14 in `test_phase2.py`) must pass against both backends.

### Documentation & comments to update

| File | Update |
|---|---|
| `README.md` | In the rate-limiting bullet: append "When Redis is enabled, rate limiting is enforced atomically across instances." Add row to env-var table for `REDIS_NAMESPACE` if not already added in 6.0. |
| `ARCHITECTURE.md` | Add a "Distributed Rate Limiting" subsection under the rate-limiter section, describing the `INCR` + `EXPIRE` recipe and the fallback contract. Update the rate-limiting diagram (or text) to show optional Redis. |
| `core/utils.py` | Class docstring on `RedisRateLimiter` explaining the algorithm, atomicity guarantee, and fallback semantics. Inline comment on the `INCR` + conditional `EXPIRE` lines. |
| `core/agent.py` | Update the migration-path comment near the existing rate-limiter construction to record that the migration is now done; reference Phase 6.1. |
| `project_memory/SESSION_LOG.md` | Append 6.1 entry in the master-prompt format. |
| `project_memory/CURRENT_STATE.md` | Update item 8 (Per-User Rate Limiting) to describe both backends and the selection rule. Add the `INCR` + `EXPIRE` recipe in one line. |
| `project_memory/FILE_INDEX.md` | Mark `core/utils.py`, `core/agent.py` (✏️) with the 6.1 change description; add `tests/test_phase6_ratelimiter.py` (🆕). |
| `project_memory/DECISIONS.md` | Add **Decision 24: Fixed-window `INCR`+`EXPIRE` over sliding-window sorted set** — record the tradeoff (simpler, atomic, sufficient at 10 req/min). Add **Decision 25: Keep local fallback alive** — Redis errors must never block requests. |
| `SDE2_UPGRADE_PLAN.md` | Mark Phase 6.1 complete with date; cross-reference the resume bullet. |
| `project_memory/TASK_TRACKER.md` | Move 6.1 to ✅ Complete with date. |

### Acceptance criteria for 6.1

- All 82 prior tests + 8 foundation tests pass with no edits.
- All 10 new rate-limiter tests pass.
- With Redis enabled, fakeredis or live Redis confirms a single 10-req/min budget across processes (verified by the concurrency test).
- With Redis disabled, behavior is bit-for-bit identical to today's `RateLimiter`.
- With Redis enabled then forcibly broken mid-run, requests are not blocked: limiter falls back to local and logs `rate_limiter_fallback`.

---

## 4. Phase 6.2 — Distributed LangGraph Checkpoints

> Swaps `MemorySaver` for `RedisSaver` when Redis is available. ~2 hours of work, large scaling and continuity story.

### What this does

- Adds `langgraph-checkpoint-redis` and uses its `RedisSaver` (which implements LangGraph's `BaseCheckpointSaver` — same interface as `MemorySaver`) as the checkpointer when `self.redis` is available.
- No graph logic changes. The thread-isolation invariant from Phase 1 (`thread_id = f"{user_id}_{channel}"`) is preserved.

### How it improves the system

| Aspect | Before (`MemorySaver`) | After (`RedisSaver`) |
|---|---|---|
| Restart continuity | All thread state discarded on process exit. | Threads survive restarts; user resumes exactly where they left off. |
| Multi-instance | Each process owns its own checkpoint dict; users routed to a different instance start a fresh thread. | Any instance can resume any user's thread because checkpoints live in Redis. |
| Operational impact | A redeploy or crash silently wipes context. | Redeploy/scale-up is non-destructive to user conversations. |
| Failure behavior | N/A. | Redis unavailable at startup → falls back to `MemorySaver` and logs the choice; no runtime failure. |

### Code changes

| File | Change |
|---|---|
| `requirements.txt` | Add `langgraph-checkpoint-redis` (pinned to a known-good version after a quick install test). |
| `core/agent.py` → `Orion.setup()` | Replace the single line `self.memory = MemorySaver()` with: if `self.redis is not None`, attempt `self.memory = RedisSaver(redis_client=self.redis)` inside `try/except`; on any exception, log a warning and fall back to `MemorySaver()`. Log `checkpointer=redis\|memory`. |
| `core/agent.py` → `get_metrics()` | Add `orion.checkpointer` field (`"redis"` or `"memory"`). |
| `integrations/telegram.py` → `/health` | Include `checkpointer` field in the response (does not affect status code). |

### Tests — `tests/test_phase6_checkpoints.py` *(new)*

1. `test_uses_memory_saver_when_redis_disabled` — `Orion.setup()` with `self.redis is None` → `isinstance(orion.memory, MemorySaver)`.
2. `test_uses_redis_saver_when_redis_available` — `self.redis = fakeredis client` → `isinstance(orion.memory, RedisSaver)`.
3. `test_falls_back_to_memory_saver_if_redis_saver_fails` — patch `RedisSaver.__init__` to raise → graceful fallback to `MemorySaver`, warning logged, no startup error.
4. `test_checkpoint_persists_across_orion_restarts` — invoke graph for `thread_id="user1_telegram"`, build a fresh `Orion` instance using the same fakeredis backend, invoke again with the same `thread_id`, assert prior state is visible.
5. `test_thread_isolation_holds_under_redis_saver` — re-runs Phase 1's thread-isolation invariant (different `user_id`/`channel` combos do not bleed) against `RedisSaver`.
6. `test_metrics_exposes_checkpointer` — `/metrics` includes `orion.checkpointer`.
7. `test_health_exposes_checkpointer` — `/health` includes `checkpointer`.

**Regression suite:** all 82 prior tests + 8 from 6.0 + 10 from 6.1 must pass with no edits. Phase 1 thread-isolation tests must pass under both checkpointers.

### Documentation & comments to update

| File | Update |
|---|---|
| `README.md` | New bullet under "Reliability" or wherever memory is described: "Conversation thread state can be persisted to Redis (`RedisSaver`) for restart continuity and multi-instance scaling. Falls back to in-memory `MemorySaver` when Redis is disabled." |
| `ARCHITECTURE.md` | In the LangGraph section, replace any mention of "MemorySaver only" with the dual-mode description. Add a short paragraph describing the `RedisSaver` swap and that the graph and `thread_id` scheme are unchanged. |
| `core/agent.py` | Update the migration-path comment near checkpointer construction: previously planned, now done. Reference Phase 6.2. |
| `project_memory/SESSION_LOG.md` | Append 6.2 entry in the master-prompt format. |
| `project_memory/CURRENT_STATE.md` | Update item 6 (Memory) and item describing thread isolation: the checkpointer is now `RedisSaver` or `MemorySaver` depending on Redis availability. |
| `project_memory/FILE_INDEX.md` | Mark `core/agent.py` (✏️), `integrations/telegram.py` (✏️), `requirements.txt` (✏️) for Phase 6.2; add `tests/test_phase6_checkpoints.py` (🆕). |
| `project_memory/DECISIONS.md` | Add **Decision 26: `RedisSaver` for horizontal scaling and restart continuity** — note the drop-in interface, the fallback contract, and the explicit non-decision (we did NOT add AOF/RDB persistence requirements; checkpoints are recoverable but not durable). |
| `SDE2_UPGRADE_PLAN.md` | Mark Phase 6.2 complete with date. |
| `project_memory/TASK_TRACKER.md` | Move 6.2 to ✅ Complete with date. |

### Acceptance criteria for 6.2

- All prior tests pass with no edits.
- All 7 new checkpoint tests pass.
- Manual smoke (Redis enabled): send 2 messages on Telegram, kill the process, restart it, send a 3rd message — the assistant has continuity (only verifiable end-to-end, not in unit tests).
- With Redis disabled, behavior is bit-for-bit identical to today's `MemorySaver`.

---

## 5. Master Documentation Pass (after 6.0 + 6.1 + 6.2)

A final, single editing pass across the docs once all three phases land. This avoids three back-to-back doc churns.

### Files to touch

| File | Final update |
|---|---|
| `README.md` | (a) New top-of-file feature bullet: "Optional Redis backend for distributed rate limiting and durable LangGraph checkpoints." (b) Updated env-var table with all four Redis vars. (c) Updated test count to **82 + 25 = 107**. (d) Updated "Tech Tradeoffs" section to mention Redis as opt-in horizontal-scale layer. |
| `ARCHITECTURE.md` | (a) New top-level diagram annotation: "Optional Redis layer." (b) Two new architecture subsections: "Distributed Rate Limiting" and "Distributed Checkpoints." (c) Update the test-suite table at the bottom (107 tests). (d) Update the "Scaling Decision Matrix" rows that previously called rate-limit and checkpoints out as future work — mark them as done. |
| `SETUP.md` | Add an "Optional: Run Redis locally" block (Docker one-liner + env vars). State explicitly that Orion runs without it. |
| `SDE2_UPGRADE_PLAN.md` | Phase 6 section finalized: 6.0/6.1/6.2 marked ✅ with dates; 6.3–6.6 listed as deliberately deferred with one-line rationale each. |
| `CHANGES.md` *(if present)* | Append a Phase 6 entry summarizing the three subphases. |
| `project_memory/SESSION_LOG.md` | One consolidating "Phase 6 complete" entry summarizing the three subphases and pointing to the per-phase entries. |
| `project_memory/CURRENT_STATE.md` | Regenerate the snapshot per master-prompt rule 7 (state-snapshot rule at end of major features). New "Optional Redis Layer" section listing the two integrations and the fallback contract. |
| `project_memory/ARCHITECTURE.md` | Add the same two new subsections as the public `ARCHITECTURE.md`. Bump milestones table with a 2026-04-30 / Phase-6 entry. |
| `project_memory/DECISIONS.md` | Verify decisions 22–26 are present and consistent. |
| `project_memory/FILE_INDEX.md` | Final pass — confirm every changed/added file from Phase 6 is listed with an accurate purpose line. |
| `project_memory/TASK_TRACKER.md` | Phase 6 row totals: 3 / 3 complete. Update grand totals. |
| `master_prompt.txt` | No edit needed — protocol stays as-is. |

### Code-comment audit

- [core/utils.py](core/utils.py) — `RedisRateLimiter` and any modified parts of `RateLimiter` carry docstrings explaining algorithm, atomicity, fallback.
- [core/agent.py](core/agent.py) — migration-path comments replaced with "Done in Phase 6.x" notes; any TODOs about Redis removed.
- [core/redis_client.py](core/redis_client.py) — module + function docstrings finalized.
- [core/config.py](core/config.py) — every Redis field has a docstring.
- All new test files have a top-of-file docstring stating which phase and which acceptance criterion they cover.

---

## 6. Sequencing & Stop Conditions

```
6.0 Foundation  ──►  6.1 Rate Limiter  ──►  6.2 Checkpoints  ──►  Master Doc Pass
   ~½ day              ~1 day                ~2 hours              ~½ day
```

Hard stop conditions (do not advance past a phase if any of these are true):

- Any prior test fails after the phase's edits.
- The new tests for the phase do not all pass.
- Acceptance criteria for the phase are not met.
- A code-review pass surfaces a place where Redis being down could block a request.

---

## 7. Out-of-Scope (Explicitly Deferred)

Tracked in `/memories/session/plan.md` for a future session:

- 6.3 Distributed cache for `web_search` / `wikipedia_search`.
- 6.4 `FailedRequestQueue` / `PendingRequestQueue` → Redis Streams.
- 6.5 Hybrid `ConversationMemory` (Redis hot, SQLite archive).
- 6.6 Distributed circuit breaker.

Each will be revisited only if the deployment model changes (e.g., true multi-instance) or a specific user-facing problem appears.
