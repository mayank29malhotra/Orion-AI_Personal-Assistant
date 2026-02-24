# Orion AI — Router & Multi-Agent Architecture

> Technical documentation for the intent-routing system, confidence scoring algorithm,   
> tool-index architecture, and per-user thread isolation.

---

## Table of Contents

1. [High-Level Design (HLD)](#high-level-design)
2. [Low-Level Design (LLD)](#low-level-design)
3. [Confidence Scoring Algorithm](#confidence-scoring-algorithm)
4. [Tool Index & Focused Selection](#tool-index--focused-selection)
5. [Per-User Thread Isolation](#per-user-thread-isolation)
6. [Data Flow — End to End](#data-flow--end-to-end)
7. [Fallback Safety Net](#fallback-safety-net)
8. [Circuit Breaker](#circuit-breaker)
9. [Per-User Rate Limiting](#per-user-rate-limiting)
10. [Health Check Endpoint](#health-check-endpoint)
11. [Structured Logging & Correlation IDs](#structured-logging--correlation-ids)
12. [Metrics Endpoint & Latency Tracking](#metrics-endpoint--latency-tracking)
13. [Input Validation](#input-validation)
14. [Config Validation](#config-validation)
15. [Graceful Shutdown](#graceful-shutdown)
16. [Test Suite](#test-suite)
17. [Scaling Decision Matrix](#scaling-decision-matrix)

---

## High-Level Design

### System Architecture

```
User Message
     │
     ▼
┌───────────────────────────────────────┐
│     LLM Intent Router                  │
│  (llama-3.1-8b-instant via Groq)       │
│  Structured output → category +        │
│  confidence score                      │
│                                        │
│  "Send email to boss" →               │
│    category: COMMUNICATION             │
│    confidence: 0.95                    │
│    should_delegate: true               │
│                                        │
│  Falls back to keyword scoring if      │
│  Groq API is unreachable              │
└───────────────┬───────────────────────┘
                │
       ┌────────┴──────────┐
       │                    │
  confidence > 0.5     confidence ≤ 0.5
  (clear intent)       (ambiguous)
       │                    │
       ▼                    ▼
┌──────────────┐   ┌──────────────────┐
│ Focused LLM  │   │ Full LLM         │
│ 8-15 tools   │   │ All 60 tools     │
│ (category +  │   │                  │
│  research    │   │ Ensures no       │
│  fallback)   │   │ capability lost  │
│              │   │                  │
│ Faster,      │   │                  │
│ cheaper,     │   │                  │
│ more accurate│   │                  │
└──────┬───────┘   └────────┬─────────┘
       │                    │
       └────────┬───────────┘
                │
                ▼
        Tool Execution → Evaluator → END
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| LLM router using `llama-3.1-8b-instant` | Understands natural language context — catches queries keywords miss (e.g., "Check PNR status"). 14,400 RPD free tier = separate quota from the worker model. |
| Separate model from worker | Router uses `llama-3.1-8b` (14.4K RPD), worker uses `llama-4-scout` (1K RPD). No quota conflict. |
| Keyword fallback on LLM failure | If Groq API is down, rate-limited, or slow — keyword classification fires automatically. Zero downtime. |
| Router is an optimization, NOT a gate | Low-confidence queries get all 60 tools. Nothing is ever blocked. |
| Research tools always included | Every focused set includes `web_search`, `wikipedia_search`, etc. The LLM always has a search escape hatch. |
| Same evaluator loop for both paths | The LangGraph worker→tools→evaluator loop is unchanged. Router only affects which tools the worker sees. |
| Tool index built once at startup | `_build_tool_index()` runs during `Orion.setup()`. No per-query overhead. |
| Structured output via Pydantic | `RouterClassification` model ensures the LLM returns valid JSON with category + confidence + reasoning. |

---

## Low-Level Design

### Files & Responsibilities

```
agents/router.py          ← Intent classification engine
  ├── AgentCategory        (Enum: 9 categories)
  ├── AGENT_KEYWORDS       (Dict: category → keyword list — fallback only)
  ├── TOOL_CATEGORIES      (Dict: tool_name → category)
  ├── RouterClassification (Pydantic: category + confidence + reasoning)
  ├── ROUTER_SYSTEM_PROMPT (System prompt for the classification LLM)
  ├── classify_intent_llm()    (LLM-based: query → (category, confidence))
  ├── classify_intent_keywords() (Keyword-based fallback)
  ├── classify_intent()    (Dispatcher: tries LLM first, falls back to keywords)
  └── get_agent_for_query()  (Query → routing decision)

core/agent.py             ← Orion class: main agent with all Phase 1-4 features
  ├── router_llm           (ChatOpenAI: llama-3.1-8b-instant with structured output)
  ├── _build_tool_index()  (Build category → [tool_objects] map)
  ├── _get_tools_for_category()  (Get focused tool set + fallbacks)
  ├── worker()             (Classify via LLM → select tools → invoke worker LLM)
  ├── llm_circuit_breaker  (CircuitBreaker: wraps worker + evaluator LLM calls)
  ├── user_rate_limiter    (RateLimiter: per-user fairness enforcement)
  ├── _request_metrics     (Dict: total/successful/failed/rate_limited/circuit_broken)
  ├── _latency_samples     (Rolling window: 100 e2e latencies)
  ├── _worker_latency_samples (Rolling window: 100 worker LLM latencies)
  ├── get_metrics()        (Aggregate all metrics for /metrics endpoint)
  ├── _shutting_down       (Flag: reject new requests during shutdown)
  ├── _in_flight_requests  (Counter: active requests, thread-safe via Lock)
  └── graceful_shutdown()  (Async: set flag → drain in-flight → cleanup)

core/config.py            ← Configuration with validation
  ├── Config               (Class: all env-loaded settings)
  ├── ROUTER_MODEL         (Default: "llama-3.1-8b-instant")
  ├── USER_REQUESTS_PER_MINUTE  (Default: 10)
  ├── validate()           (11 validation checks returning error list)
  ├── validate_or_fail()   (Raises ConfigValidationError on critical issues)
  └── ConfigValidationError (Exception for startup failure)

core/models.py            ← Pydantic input/output validation models
  ├── ChatRequest          (Input validation: message, user_id, channel, success_criteria)
  ├── HealthResponse       (API contract for /health)
  └── MetricsResponse      (API contract for /metrics)

core/utils.py             ← Utility classes
  ├── Logger               (Dual-output: console + JSON file, **context kwargs)
  ├── Cache                (In-memory TTL cache)
  ├── RateLimiter          (Per-key rate limiting with sliding window)
  └── CircuitBreaker       (CLOSED/OPEN/HALF_OPEN state machine, thread-safe)

integrations/telegram.py  ← Telegram bot + HTTP endpoints
  ├── /health              (GET: 200 healthy / 503 degraded with subsystem checks)
  ├── /metrics             (GET: request counts, latency percentiles, CB state)
  └── lifespan             (Startup/shutdown handler using graceful_shutdown())
```

### Class Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                            Orion                                    │
├────────────────────────────────────────────────────────────────────┤
│ worker_llm: ChatOpenAI              # Unbound (no tools)           │
│ worker_llm_with_tools: ChatOpenAI   # Bound to ALL tools           │
│ router_llm: ChatOpenAI              # llama-3.1-8b-instant         │
│                                       + RouterClassification       │
│ tools: List[BaseTool]               # All 60 tools                 │
│ _tool_index: Dict[AgentCat, List[BaseTool]]                        │
│                                                                     │
│ # Phase 2: Reliability                                              │
│ llm_circuit_breaker: CircuitBreaker # 5 failures / 60s recovery    │
│ user_rate_limiter: RateLimiter      # 10 req/min per user          │
│ llm_rate_limiter: RateLimiter       # Global API key protection    │
│                                                                     │
│ # Phase 3: Observability                                            │
│ _request_metrics: Dict              # total/successful/failed/...  │
│ _latency_samples: List[float]       # Rolling 100 e2e latencies    │
│ _worker_latency_samples: List[float]# Rolling 100 worker latencies │
│                                                                     │
│ # Phase 4: Hardening                                                │
│ _shutting_down: bool                # Reject new requests flag     │
│ _in_flight_requests: int            # Active request counter       │
│ _in_flight_lock: threading.Lock     # Thread-safe counter access   │
├────────────────────────────────────────────────────────────────────┤
│ setup()                                                             │
│   ├── Config.validate_or_fail()       # Fail fast on bad config    │
│   ├── _build_tool_index()             # One-time at startup        │
│   └── init router_llm                 # Separate 8B LLM           │
│                                                                     │
│ worker(state)                                                       │
│   ├── get_agent_for_query()           # LLM classifies intent      │
│   ├── llm_circuit_breaker.can_execute()  # Fail fast if OPEN      │
│   ├── _get_tools_for_category()       # Get focused tools          │
│   ├── worker_llm.bind_tools()         # Dynamic binding            │
│   └── llm.invoke(messages)            # Execute worker LLM         │
│                                                                     │
│ evaluator(state)                                                    │
│   ├── llm_circuit_breaker.can_execute()  # Skip eval if OPEN      │
│   └── Assess task completion              # END or feedback        │
│                                                                     │
│ run_superstep(message, user_id, channel)                            │
│   ├── ChatRequest(message, user_id, channel)  # Input validation   │
│   ├── _shutting_down check                    # Reject if stopping │
│   ├── user_rate_limiter.check(user_id)        # Per-user fairness  │
│   ├── request_id = uuid4()[:8]                # Correlation ID     │
│   ├── _in_flight_requests++                   # Track active       │
│   ├── graph.ainvoke(state, config)            # Run LangGraph      │
│   ├── Record latency + metrics                # Observability      │
│   └── _in_flight_requests--  (finally)        # Always decrement   │
│                                                                     │
│ get_metrics() → dict                    # Aggregate all metrics    │
│ graceful_shutdown(timeout=30) → dict    # Drain + cleanup          │
│ _percentiles(samples) → dict            # p50/p90/p99/avg/count   │
└────────────────────────────────────────────────────────────────────┘
           │ uses
           ▼
┌─────────────────────────────────────────────────────────┐
│                  agents/router.py                        │
├─────────────────────────────────────────────────────────┤
│ AgentCategory (Enum: 9 categories)                       │
│ RouterClassification (Pydantic BaseModel)                │
│   category: str, confidence: float, reasoning: str       │
├─────────────────────────────────────────────────────────┤
│ classify_intent(query, router_llm?)                      │
│   → LLM path: classify_intent_llm(query, llm)           │
│   → Fallback: classify_intent_keywords(query)            │
│                                                          │
│ get_agent_for_query(query, router_llm?)                  │
│   → {category, confidence, agent, should_delegate}       │
└─────────────────────────────────────────────────────────┘
```

### Method Details

#### `_build_tool_index()` — Called once during `setup()`

```
Input:  self.tools (60 loaded tool objects)
        TOOL_CATEGORIES (dict: tool_name → AgentCategory)

Process:
  1. Create empty dict: {category: []} for all 9 AgentCategory values
  2. For each (tool_name → category) in TOOL_CATEGORIES:
       If tool_name exists in loaded tools → add to that category's list
  3. Any tool NOT in TOOL_CATEGORIES → add to GENERAL (catch-all)
  4. Log the distribution

Output: self._tool_index = {
    TRAVEL: [check_pnr_status, get_train_status, ...],        # 10 tools
    COMMUNICATION: [send_email, read_recent_emails],           # 2 tools
    PRODUCTIVITY: [create_calendar_event, list_tasks, ...],    # 12 tools
    DEVELOPER: [github_list_repos, python_repl, ...],          # 7 tools
    MEDIA: [search_youtube, read_csv, ocr_image, ...],         # 15 tools
    RESEARCH: [web_search, wikipedia_search, ...],             # 8 tools
    SYSTEM: [take_screenshot, send_push_notification, ...],    # 4 tools
    BROWSER: [navigate_browser, click_element, ...],           # 7 (0 if Playwright skipped)
    GENERAL: [read_file_content, write_file_content],          # 2 tools (catch-all)
}
```

#### `_get_tools_for_category(category)` — Called per query

```
Input:  AgentCategory (e.g., TRAVEL)

Process:
  1. Get tools for that category from _tool_index
  2. If category ≠ RESEARCH: append all RESEARCH tools (web_search, etc.)
  3. If result < 3 tools: return ALL tools (safety net)

Output: List of 8-22 tool objects (vs 60 if no routing)

Example for TRAVEL:
  [check_pnr_status, get_train_status, search_trains,     ← 8 travel tools
   get_station_code, get_flight_status, get_flight_by_route,
   get_airport_info, track_flight_live,
   web_search, fetch_webpage, wikipedia_search,            ← 7 research fallback
   define_word, get_synonyms, get_antonyms, translate_word]
  Total: 15 tools (vs 60)
```

---

## Confidence Scoring Algorithm

### Primary: LLM-Based Classification

The router now uses **`llama-3.1-8b-instant`** (Groq free tier) for intent classification. The LLM receives the user query and returns structured output via a Pydantic model:

```python
class RouterClassification(BaseModel):
    category: str    # One of 9 AgentCategory values
    confidence: float  # 0.0 to 1.0
    reasoning: str    # One-sentence explanation
```

#### How It Works

```
User: "Check PNR status 1234567890"
  │
  ▼
┌─────────────────────────────────────────────────────┐
│  System Prompt: "You are an intent classifier for   │
│  Orion. Categories: TRAVEL, COMMUNICATION, ..."      │
│                                                      │
│  User Message: 'Classify this user query:            │
│  "Check PNR status 1234567890"'                      │
│                                                      │
│  LLM Response (structured output):                   │
│  {                                                   │
│    "category": "TRAVEL",                             │
│    "confidence": 0.95,                               │
│    "reasoning": "PNR status is an Indian Railways    │
│                  travel feature"                     │
│  }                                                   │
└─────────────────────────────────────────────────────┘
```

The LLM understands **context** that keywords miss:
- `"Check PNR status 1234567890"` → TRAVEL (keywords only see 1 match, score too low)
- `"Convert this image to text using OCR"` → MEDIA (keywords miss this too)
- `"What should I pack for Goa?"` → TRAVEL (no travel keywords at all, but LLM gets it)

#### Model Selection: Why `llama-3.1-8b-instant`

| Model | RPD | TPD | Speed | Why / Why Not |
|-------|-----|-----|-------|---------------|
| **llama-3.1-8b-instant** | **14,400** | **500K** | 560 tps | **Winner**: Best daily quota by 14x, fast, enough for classification |
| llama-3.3-70b-versatile | 1,000 | 100K | 280 tps | Overkill for routing, low RPD |
| llama-4-scout-17b (worker) | 1,000 | 500K | 750 tps | Same model = shared quota conflict |
| qwen/qwen3-32b | 1,000 | 500K | 400 tps | Preview model, low RPD |

Key tradeoff: 8B is more than enough for "classify into 1 of 9 categories". Using a separate model means **zero quota conflict** with the worker.

#### Delegation Threshold

```python
# In get_agent_for_query():
should_delegate = confidence > 0.5 and category != GENERAL
```

- **confidence > 0.5**: LLM is at least moderately sure → route to focused tools
- **confidence ≤ 0.5**: Ambiguous → fall back to all 60 tools (safe)
- **GENERAL**: Greetings, chitchat → always all 60 tools

### Fallback: Keyword-Based Classification

If the Groq API is unreachable (proxy, rate-limit, network error), `classify_intent_llm` catches the exception and automatically falls back to `classify_intent_keywords`:

```python
def classify_intent_llm(query, router_llm):
    try:
        result = router_llm.invoke(messages)  # LLM call
        return category, confidence
    except Exception as e:
        logger.warning(f"LLM router failed: {e} — falling back to keywords")
        return classify_intent_keywords(query)  # Keyword fallback
```

Keyword scoring counts keyword matches per category; multi-word keywords score higher, confidence = max_score / total_score. Two thresholds: `max_score >= 2` and `confidence >= 0.3`.

### Classification Comparison

| Query | LLM Result | Keyword Result | Winner |
|-------|-----------|---------------|--------|
| `"Find cheapest flight from Delhi to Mumbai"` | TRAVEL (0.95) | TRAVEL (0.88) | Both correct |
| `"Send email to john@example.com"` | COMMUNICATION (0.95) | COMMUNICATION (1.00) | Both correct |
| `"Check PNR status 1234567890"` | **TRAVEL (0.95)** | GENERAL (0.00) | **LLM wins** — understands PNR is travel |
| `"Convert this image to text using OCR"` | **MEDIA (0.90)** | GENERAL (0.00) | **LLM wins** — understands OCR context |
| `"What should I pack for Goa?"` | **TRAVEL (0.85)** | GENERAL (0.00) | **LLM wins** — no travel keywords at all |
| `"Hello how are you?"` | GENERAL (0.00) | GENERAL (0.00) | Both correct |

---

## Tool Index & Focused Selection

### Tool Distribution Across Categories

```
Category        Tools  Examples
─────────────────────────────────────────────────────────
TRAVEL           10    check_pnr_status, get_flight_status, search_trains,
                       parse_location, get_distance
COMMUNICATION     2    send_email, read_recent_emails
PRODUCTIVITY     12    create_calendar_event, create_task, create_note
DEVELOPER         7    github_list_repos, github_create_issue, python_repl,
                       github_get_repo_info, github_list_pull_requests
MEDIA            15    search_youtube, read_csv, ocr_image, create_pdf
RESEARCH          8    web_search, wikipedia_search, define_word,
                       browser_search
SYSTEM            4    take_screenshot, send_push_notification
BROWSER           7    navigate_browser, click_element, get_elements,
                       current_webpage, extract_text, extract_hyperlinks,
                       fill_text (loaded via Playwright, 0 if skipped)
GENERAL           2    read_file_content, write_file_content (catch-all)
─────────────────────────────────────────────────────────
TOTAL         60-67    (60 sync + up to 7 Playwright browser tools)
```

### What the LLM Receives Per Category

Every focused set = category tools + RESEARCH tools (always included):

```
Category        Own Tools  + Research  = Total    Savings vs All 60
──────────────────────────────────────────────────────────────────
TRAVEL             10         +8         18        70% fewer tools
COMMUNICATION       2         +8         10        83% fewer tools
PRODUCTIVITY       12         +8         20        67% fewer tools
DEVELOPER           7         +8         15        75% fewer tools
MEDIA              15         +8         23        62% fewer tools
RESEARCH            8          —          8        87% fewer tools
SYSTEM              4         +8         12        80% fewer tools
BROWSER             7         +8         15        75% fewer tools
GENERAL          (all 60)      —         60        0% (full fallback)
```

### Token Usage

Each tool schema is roughly 50-100 tokens for the LLM to parse. With focused tool selection, token usage per category:

- **TRAVEL**: ~900-1800 tokens (18 tools)
- **COMMUNICATION**: ~500-1000 tokens (10 tools)
- **BROWSER**: ~750-1500 tokens (15 tools)
- **Full fallback (GENERAL)**: ~3000-6000 tokens (all 60 tools)

Focused selection reduces tool-description token usage by 60-87% per query, resulting in **faster responses** and **lower cost per query**.

---

## Per-User Thread Isolation

### How It Works

LangGraph's `MemorySaver` checkpointer stores state keyed by `thread_id`. Each user × channel combination gets its own isolated thread:

```python
# core/agent.py — run_superstep()
thread_id = f"{user_id}_{channel}" if user_id else self.orion_id
config = {"configurable": {"thread_id": thread_id}}
```

This ensures:
- Each user has their own conversation state per channel
- No cross-contamination of messages, tool results, or evaluator feedback between users
- Anonymous CLI users fall back to `self.orion_id` (a process-level UUID)

### Thread ID Examples

```
User A (Telegram):  "telegram:42_telegram"
User B (Telegram):  "telegram:99_telegram"
User A (Email):     "telegram:42_email"
User A (Gradio):    "telegram:42_gradio"
Anonymous (CLI):    "26ce9863-7567-43b5-..." (orion_id)
```

Each thread gets its own LangGraph checkpoint — messages, tool results, evaluator feedback are all isolated.

---

## Data Flow — End to End

### Complete Request Lifecycle

```
1. User sends: "Find flights from Delhi to Mumbai tomorrow"
                │
2. run_superstep()
   │  thread_id = "telegram:42_telegram"  ← per-user isolation
   │  Save to ConversationMemory
   │
3. LangGraph invokes worker(state)
   │
   ├─ 4a. Extract user text from messages
   │       user_text = "Find flights from Delhi to Mumbai tomorrow"
   │
   ├─ 4b. get_agent_for_query(user_text, router_llm=self.router_llm)
   │       └── classify_intent_llm(user_text, router_llm)
   │             LLM (llama-3.1-8b-instant) structured output:
   │             {category: "TRAVEL", confidence: 0.95,
   │              reasoning: "Flight search between cities"}
   │           Return: (TRAVEL, 0.95)
   │
   ├─ 4c. should_delegate = 0.95 > 0.5 = True
   │
   ├─ 4d. _get_tools_for_category(TRAVEL)
   │       10 travel tools + 8 research tools = 18 tools
   │
   ├─ 4e. worker_llm.bind_tools(focused_tools)
   │       Dynamic binding: LLM now sees 18 tools (not 60)
   │
   └─ 4f. llm.invoke(messages)
          LLM picks: get_flight_by_route("DEL", "BOM", "2026-02-18")
                │
5. LangGraph routes to ToolNode
   │  Executes get_flight_by_route
   │  Returns flight data
   │
6. LangGraph routes back to worker
   │  Worker summarizes flight data in plain text
   │  No tool_calls → routes to evaluator
   │
7. Evaluator checks: success_criteria_met?
   │  Response contains flight info → YES
   │  Return: success_criteria_met = True
   │
8. LangGraph routes to END
   │
9. run_superstep() extracts assistant reply
   │  Saves to ConversationMemory
   │  Returns: history + [[user_msg, assistant_reply]]
```

---

## Fallback Safety Net

The router is designed with a "fail-open" philosophy — when in doubt, it gives the LLM MORE tools, not fewer.

### Three Layers of Safety

```
Layer 1: LLM → Keyword Fallback
  └── If Groq API fails (rate-limit, proxy, network) →
      classify_intent_llm catches exception → classify_intent_keywords fires
      Zero downtime, automatic, no user-visible error

Layer 2: Confidence Threshold
  └── confidence ≤ 0.5 → ALL 60 tools (no routing)

Layer 3: Research Fallback Injection  
  └── Every focused set includes web_search, wikipedia_search, etc.
      The LLM can always "escape" to a web search if its tools don't cover the query.

Layer 4: Minimum Tool Count
  └── If _get_tools_for_category returns < 3 tools → ALL 60 tools
      Prevents edge cases where a category has 0 mapped tools (e.g., BROWSER when disabled).
```

### When Routing Does NOT Happen

| Scenario | Reason | What Happens |
|----------|--------|--------------|
| "Hello!" | No keywords match | GENERAL → all 60 tools |
| "Check PNR" | 1 keyword, score < 2 | GENERAL → all 60 tools |
| "Book a flight and send email" | TRAVEL=3, COMM=3, confidence=0.5 | GENERAL → all 60 tools |
| "What's the weather?" | RESEARCH keywords but "weather" isn't one | GENERAL → all 60 tools |
| First-time category with no tools | < 3 focused tools | Falls back to all 60 |

In all these cases, Orion uses the full 60-tool set. The router is an optimization, not a gate — **zero capability loss** on ambiguous queries.

---

## Circuit Breaker

> Phase 2: Prevents cascading failures when Groq LLM is down.

### State Machine

```
                  success
            ┌─────────────────┐
            │                 │
            ▼                 │
     ┌──────────┐     ┌──────────────┐
     │  CLOSED  │────▶│    OPEN      │
     │ (normal) │     │ (fail fast)  │
     └──────────┘     └──────┬───────┘
         ▲  5 consecutive       │
         │  failures            │ 60s elapsed
         │                      ▼
         │              ┌──────────────┐
         └──────────────│  HALF_OPEN   │
            success     │ (probe one)  │──── failure ──▶ OPEN
                        └──────────────┘
```

### How It Works

| State | Behavior | User Experience |
|-------|----------|-----------------|
| **CLOSED** | All LLM calls pass through normally. Failures counted. | Normal operation |
| **OPEN** | All LLM calls rejected immediately (fail fast). Returns "service temporarily unavailable" | Instant response instead of 15s timeout |
| **HALF_OPEN** | One probe call allowed through. Success → CLOSED, failure → OPEN | Testing if Groq is back up |

### Implementation

```python
# core/utils.py — CircuitBreaker class
self.llm_circuit_breaker = CircuitBreaker(
    failure_threshold=5,     # 5 consecutive failures → OPEN
    recovery_timeout=60,     # Wait 60s before probing
    name="groq_llm"
)

# core/agent.py — worker()
if not self.llm_circuit_breaker.can_execute():
    self._request_metrics["circuit_broken"] += 1
    return {"messages": [AIMessage(content="Service temporarily unavailable...")]}

try:
    response = llm.invoke(messages)
    self.llm_circuit_breaker.record_success()
except Exception:
    self.llm_circuit_breaker.record_failure()
    raise
```

### Design Decisions
- **Thread-safe** via `threading.Lock` — safe for concurrent Telegram/Gradio requests
- **Wraps both worker and evaluator** — evaluator skips evaluation when OPEN (returns worker output directly)
- **Serializable state** via `get_state()` — exposed in `/health` and `/metrics` endpoints
- **5 failures threshold** — tolerates transient errors (network blips), trips on sustained outages
- **60s recovery** — matches Groq's rate limiter reset window

---

## Per-User Rate Limiting

> Phase 2: Prevents one noisy user from exhausting the shared Groq API quota.

### Architecture

```
                    ┌─────────────────────────────────────┐
                    │         run_superstep()              │
                    │                                      │
User A (10 req) ───▶│  user_rate_limiter.check("user:A") │──▶ PASS (< 10/min)
                    │              │                        │
User B (15 req) ───▶│  user_rate_limiter.check("user:B") │──▶ REJECT at 11th
                    │              │                        │    "Please wait 42s"
                    │              ▼                        │
                    │  llm_rate_limiter.check("llm")      │──▶ Global API protection
                    └─────────────────────────────────────┘
```

### Configuration

| Setting | Default | Env Variable | Purpose |
|---------|---------|-------------|---------|
| Per-user limit | 10 req/min | `USER_REQUESTS_PER_MINUTE` | Fairness — no single user monopolizes |
| Global LLM limit | 30 req/min | `LLM_REQUESTS_PER_MINUTE` | Protect Groq API key across all users |

### Two Separate Concerns
1. **`user_rate_limiter`**: Checked first in `run_superstep()`. Each user gets an independent bucket. Returns friendly wait time message.
2. **`llm_rate_limiter`**: Global API key protection. Prevents exceeding Groq's free tier limits regardless of how many users are active.

---

## Health Check Endpoint

> Phase 2: `/health` for load balancers and monitoring tools.

### Endpoint: `GET /health`

**Healthy (200)**:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-23T10:00:00",
  "orion_ready": true,
  "memory_db": true,
  "retry_queue": true,
  "llm_circuit_breaker": {"state": "closed", "failure_count": 0}
}
```

**Degraded (503)**:
```json
{
  "status": "degraded",
  "timestamp": "2026-02-23T10:00:00",
  "orion_ready": true,
  "memory_db": true,
  "retry_queue": true,
  "llm_circuit_breaker": {"state": "open", "failure_count": 5}
}
```

### Status Codes
| Code | Condition | Use Case |
|------|-----------|----------|
| **200** | All subsystems healthy, CB is CLOSED | Load balancer routes traffic here |
| **503** | Orion not ready OR circuit breaker OPEN | Load balancer routes traffic elsewhere |

---

## Structured Logging & Correlation IDs

> Phase 3: Debug any request end-to-end with structured JSON logs.

### Dual-Output Architecture

```
logger.info("worker_llm_call", request_id="a1b2c3d4", latency_ms=1200, tools=15)
    │
    ├──▶ Console + orion.log:     "2026-02-23 10:00:01 - Orion - INFO - worker_llm_call"
    │    (human-readable, backward compatible)
    │
    └──▶ orion_structured.log:    {"timestamp": "2026-02-23T10:00:01", "level": "INFO",
         (JSON, machine-parseable)   "message": "worker_llm_call", "request_id": "a1b2c3d4",
                                     "latency_ms": 1200, "tools": 15}
```

### Correlation ID Flow

Every request gets a unique `request_id` (8-char UUID prefix: `str(uuid.uuid4())[:8]`) that traces through the entire pipeline:

```
superstep_start     → request_id=a1b2c3d4, user_id=42, channel=telegram
  worker_llm_call   → request_id=a1b2c3d4, category=TRAVEL, tools=18, latency_ms=1200
  worker_tool_calls  → request_id=a1b2c3d4, tools_used=["get_flight_by_route"]
  evaluator_complete → request_id=a1b2c3d4, result=success
superstep_complete  → request_id=a1b2c3d4, latency_ms=3200
```

### Usage

```bash
# Filter all events for a specific request
grep "a1b2c3d4" orion_structured.log | jq .

# Find slow requests (> 5 seconds)
cat orion_structured.log | jq 'select(.latency_ms > 5000)'

# Count requests by category
cat orion_structured.log | jq 'select(.message == "worker_llm_call") | .category' | sort | uniq -c
```

### Implementation
- **Zero new dependencies** — extends existing `Logger` class in `core/utils.py`
- **Backward compatible** — `logger.info("msg")` works unchanged; `logger.info("msg", key=val)` adds JSON
- **`propagate=False`** on structured logger prevents JSON duplication in console
- **`try/except` in `_emit_json()`** — structured logging never breaks the application

---

## Metrics Endpoint & Latency Tracking

> Phase 3: Operational visibility via `/metrics` and percentile computation.

### Endpoint: `GET /metrics`

```json
{
  "timestamp": "2026-02-23T10:00:00",
  "orion": {
    "requests": {
      "total_requests": 150,
      "successful": 140,
      "failed": 5,
      "rate_limited": 3,
      "circuit_broken": 2
    },
    "latency_ms": {
      "e2e": {"p50": 2100, "p90": 4500, "p99": 8200, "avg": 2800, "count": 100},
      "worker_llm": {"p50": 1200, "p90": 3000, "p99": 5500, "avg": 1600, "count": 100}
    },
    "circuit_breaker": {"state": "closed", "failure_count": 0, "recovery_timeout_s": 60},
    "tools": 60,
    "shutdown": {"shutting_down": false, "in_flight_requests": 1}
  },
  "memory": {"total_messages": 500, "total_users": 3},
  "retry_queue": {"pending": 0, "completed": 12, "failed": 1}
}
```

### Latency Rolling Windows

```python
# Rolling window of 100 samples (oldest evicted first)
self._latency_samples = []         # e2e latencies
self._worker_latency_samples = []  # worker LLM latencies

# Percentile computation via _percentiles() helper
def _percentiles(samples):
    sorted_s = sorted(samples)
    n = len(sorted_s)
    return {
        "p50": sorted_s[n // 2],
        "p90": sorted_s[int(n * 0.9)],
        "p99": sorted_s[int(n * 0.99)],
        "avg": round(sum(sorted_s) / n, 1),
        "count": n
    }
```

At 100 samples: p50 = median, p90 = 10th highest, p99 = 1st highest. Naturally ages out old data as new requests arrive.

---

## Input Validation

> Phase 4: Reject bad input before it reaches the LLM (saves tokens).

### ChatRequest Model (`core/models.py`)

```python
class ChatRequest(BaseModel):
    message: str      # 1-10000 chars, stripped, non-blank
    user_id: str      # Default "anonymous", stripped whitespace
    channel: str      # Default "default", alphanumeric + underscore/hyphen, normalized to lowercase
    success_criteria: str  # Max 2000 chars
```

### Validation Pipeline

```
User Input → ChatRequest(message, user_id, channel, success_criteria)
                │
                ├── message blank?        → "Message cannot be blank"
                ├── message > 10000 chars? → "Max length 10000"
                ├── channel = "te$t"?     → "Invalid characters"
                └── Valid → use validated values downstream
                    (message stripped, channel lowercase, user_id trimmed)
```

### Why Pydantic
- **Already a dependency** (LangChain requires it) — zero new deps
- **Validates before LLM call** — saves tokens on malformed input
- **Consistent across channels** — Telegram, Gradio, Email all use the same model
- **Auto-generates error messages** — user-friendly validation errors

---

## Config Validation

> Phase 4: Fail fast at startup instead of discovering bad config mid-request.

### 11 Validation Checks

| Check | Type | What |
|-------|------|------|
| GROQ_API_KEY | Critical | Required for all LLM calls |
| GEMINI_API_KEY | Warning | Required for fallback (non-blocking) |
| LLM_REQUESTS_PER_MINUTE > 0 | Warning | Numeric bounds |
| USER_REQUESTS_PER_MINUTE > 0 | Warning | Numeric bounds |
| LLM_COOLDOWN_SECONDS >= 0 | Warning | Numeric bounds |
| MEMORY_HISTORY_LIMIT > 0 | Warning | Numeric bounds |
| MAX_RETRY_ATTEMPTS >= 0 | Warning | Numeric bounds |
| RETRY_DELAY_MINUTES >= 0 | Warning | Numeric bounds |
| WORKER/EVALUATOR/ROUTER_MODEL | Warning | Non-empty model names |
| SMTP_PORT 1-65535 | Warning | Port range |
| IMAP_PORT 1-65535 | Warning | Port range |

### Critical vs. Warning Separation

```python
Config.validate_or_fail()  # Called at top of Orion.setup()
    │
    ├── GROQ_API_KEY missing? → raise ConfigValidationError (startup blocked)
    │
    └── Everything else → logger.warning("Config warning: ...") (non-blocking)
```

Only GROQ_API_KEY is a hard blocker — without it, every LLM call fails. Other issues degrade gracefully or have sensible defaults.

---

## Graceful Shutdown

> Phase 4: Drain in-flight requests cleanly before process exit.

### Shutdown Sequence

```
Signal received (SIGTERM / lifespan shutdown)
    │
    ▼
graceful_shutdown(timeout=30)
    │
    ├── 1. Set _shutting_down = True
    │      → run_superstep() rejects new requests immediately
    │
    ├── 2. Poll _in_flight_requests every 0.5s
    │      → Wait for active requests to complete naturally
    │
    ├── 3. Timeout reached?
    │      ├── No: All drained cleanly ✅
    │      └── Yes: Force proceed (log warning) ⚠️
    │
    └── 4. Call cleanup() — close browser, release resources
           Return stats: {requests_drained, forced, in_flight_at_shutdown, elapsed_s}
```

### Thread Safety

```python
# threading.Lock protects the counter (not asyncio.Lock — worker/evaluator are sync)
self._in_flight_lock = threading.Lock()

# run_superstep():
with self._in_flight_lock:
    self._in_flight_requests += 1
try:
    # ... process request ...
finally:
    with self._in_flight_lock:
        self._in_flight_requests -= 1
```

### Integration
- **Telegram**: `lifespan` handler calls `graceful_shutdown(timeout=30)` instead of direct `cleanup()`
- **Metrics**: `get_metrics()` includes `"shutdown": {"shutting_down": bool, "in_flight_requests": int}`
- **Cross-platform**: Uses polling (0.5s interval), not OS signals — works on Windows, Linux, Docker

---

## Test Suite

**82 automated pytest functions across 4 test files — all passing.**

All tests are in the `tests/` directory:

```
tests/
├── __init__.py              # Package marker
├── test_phase1.py           # Router + thread isolation (7 tests)
├── test_phase2.py           # Circuit breaker + rate limiter + health check (7 tests)
├── test_phase3.py           # Logging + metrics + latency + correlation IDs (36 tests)
├── test_phase4.py           # Input validation + config + graceful shutdown (32 tests)
├── test_setup.py            # Environment & dependency checks
└── test_local.py            # Interactive/batch Orion testing via CLI
```

### Running Tests

```bash
# Run all 82 tests
python -m pytest tests/ -v

# Run by phase
python -m pytest tests/test_phase1.py -v
python -m pytest tests/test_phase2.py -v
python -m pytest tests/test_phase3.py -v
python -m pytest tests/test_phase4.py -v

# Interactive Orion testing
python tests/test_local.py -i        # Interactive mode
python tests/test_local.py -q        # Quick 5-test batch
python tests/test_local.py -a        # Full 20-test batch
python tests/test_local.py -t "query" # Single query test
```

### Test Coverage by Phase

#### Phase 1: Router + Thread Isolation (7 tests)

| Test | What It Validates |
|------|-------------------|
| Keyword Classification (fallback) | 7 queries correctly classify via keyword scoring |
| Keyword Delegation | High-confidence queries delegate; low-confidence and greetings do not |
| Orion Import + Init | Orion class initializes with `worker_llm`, `router_llm`, `_tool_index` attributes |
| Tool Index Building | All 60 tools are indexed; every tool lands in exactly one category |
| Focused Tool Selection | TRAVEL gets 18 tools (10+8), which is fewer than 60; research tools always present |
| Thread Isolation | Different users get different `thread_id`s; same user on different channels gets different threads |
| LLM Router Classification | 10 queries classified via Groq LLM; if API unreachable, validates keyword fallback resilience (≥8/10) |

#### Phase 2: Reliability (7 tests)

| Test | What It Validates |
|------|-------------------|
| CB State Transitions | CLOSED → OPEN → HALF_OPEN → CLOSED lifecycle |
| CB Fail-Fast | OPEN state rejects all calls immediately |
| CB Probe Failure | HALF_OPEN → OPEN when probe call fails |
| Per-User Rate Limiter | Independent buckets, fairness enforcement |
| Health Check Structure | JSON structure, degraded detection with 503 |
| Orion Has CB | `llm_circuit_breaker` attribute + config (threshold=5, timeout=60) |
| Orion Has User Limiter | `user_rate_limiter` attribute + config (max_calls matching config) |

#### Phase 3: Observability (36 tests)

| Test Group | Count | What It Validates |
|-----------|-------|-------------------|
| Logger Context | 4 | Plain info, structured info/warning/error with `**context` kwargs |
| JSON Log Output | 2 | Valid JSON in structured log, correct fields (timestamp, level, message) |
| Orion Metrics Attrs | 4 | `_request_metrics`, `_latency_samples`, `_worker_latency_samples`, expected keys |
| get_metrics() | 6 | Method exists, top keys, latency sub-keys, percentile keys, CB in metrics, tools in metrics |
| Latency Rolling Window | 5 | 100-cap, oldest/newest preserved, p50/count correctness |
| /metrics Endpoint | 5 | timestamp, orion, memory, retry_queue, orion sub-structure |
| Correlation IDs | 5 | Format (8-char), request_id in source, e2e timing, start/complete events |
| Worker/Evaluator Instr. | 5 | worker_start, worker event, worker latency, eval_start, evaluator event |

#### Phase 4: Hardening (32 tests)

| Test Group | Count | What It Validates |
|-----------|-------|-------------------|
| ChatRequest Model | 10 | Valid/invalid inputs, defaults, length limits, channel chars, whitespace strip |
| Config Validation | 8 | Numeric bounds, model names, port range, validate_or_fail, ConfigValidationError |
| Orion Input Integration | 3 | ChatRequest import, validation in run_superstep, shutdown check |
| Graceful Shutdown | 6 | `_shutting_down` flag, in_flight counter, lock, async method, flag setting, result dict |
| Metrics Shutdown | 2 | shutdown key in get_metrics(), correct sub-fields |
| In-Flight Tracking | 2 | increment/decrement in run_superstep source, finally block |
| Lifespan Integration | 1 | telegram.py lifespan calls graceful_shutdown |

---

## Scaling Decision Matrix

> Orion is designed as a single-user personal assistant. Multi-user isolation patterns (per-user threads, per-user rate limits) are built in as **correctness requirements**, not scaling features. The table below documents what would change — and the specific trigger for each change — when scaling beyond a single user.

| Concern | Current Design (1 user) | Trigger to Change | Migration Path | Why Not Now |
|---------|------------------------|-------------------|----------------|-------------|
| **DB Concurrency** | SQLite (WAL mode, single-writer) | >10 concurrent writers causing lock contention | Swap to Postgres + connection pool. Interface is already query-based — no ORM, no schema change | Single-writer lock is zero-contention at scale=1. Postgres adds connection management overhead with no benefit |
| **Rate Limit State** | In-memory `Dict[str, list]` in `RateLimiter` | Multi-process or multi-node deployment | Redis `INCR` with `EXPIRE` (TTL-based sliding window). Same key format (`user:{id}`) | In-process dict is zero-latency, zero-dependency. Adding Redis requires a running Redis instance |
| **Session / Checkpoint State** | LangGraph `MemorySaver` (in-memory dict) | Horizontal scaling (multiple Orion instances) | `RedisSaver` or `PostgresSaver` from `langgraph-checkpoint-*`. Drop-in replacements — same `BaseCheckpointSaver` interface | MemorySaver is correct for single-process. Distributed state needs shared storage |
| **Authentication** | Telegram-provided (`chat_id` = user identity) | API gateway / multi-channel without built-in auth | JWT with refresh tokens via FastAPI `Depends()`. Bearer token in `Authorization` header | Redundant when Telegram already authenticates. Adding auth to a personal bot = security theater |
| **Message Broker** | SQLite `FailedRequestQueue` (retry queue) | >100 messages/sec throughput, or multi-consumer processing | Redis Streams or AWS SQS. Queue interface (`push`, `pop`, `ack`) stays the same | SQLite queue handles personal-assistant load (~5 msg/min). Kafka/SQS minimum overhead ≫ benefit at this scale |
| **API Key Management** | Single Groq key in `.env` | Multiple users each bringing their own API keys | Encrypted per-user key vault (AWS KMS / HashiCorp Vault), key rotation lifecycle | One user = one key. Key management infra is pure overhead with no user benefit |
| **Observability** | Console logs + JSON structured log file | Multi-instance, team debugging | OpenTelemetry SDK → Jaeger/Zipkin for distributed tracing, Prometheus for metrics aggregation | Single-process tracing is fully captured in structured logs. OTel adds SDK dependency + collector infra |

### Design Philosophy

The abstractions are built so that scaling is a **backend swap, not an architecture rewrite**:

```
RateLimiter(key="user:123")     →  Same interface, swap dict for Redis INCR
MemorySaver()                   →  Same interface, swap for RedisSaver()
SQLite retry queue              →  Same push/pop interface, swap for Redis Streams
thread_id = f"{user_id}_{ch}"   →  Already multi-user aware, no change needed
CircuitBreaker()                →  Already user-agnostic, no change needed
```

This is intentional: **build the seams where multi-tenancy plugs in, don't build the multi-tenancy you don't need yet.**
