"""
Orion AI Agent - Core Agent Module
LangGraph-based agent with worker-evaluator pattern.
"""

# Disable SSL warnings and LangSmith tracing before imports
import os
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['NO_PROXY'] = 'api.groq.com,generativelanguage.googleapis.com'

import warnings
import urllib3
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)

from typing import Annotated, List, Any, Optional, Dict
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
import uuid
import asyncio
import time
import threading
from datetime import datetime

from core.config import Config
from core.utils import logger, RateLimiter, CircuitBreaker, async_retry_on_error
from core.models import ChatRequest
from agents.router import classify_intent, get_agent_for_query, AgentCategory, TOOL_CATEGORIES, ROUTER_SYSTEM_PROMPT, RouterClassification

load_dotenv(override=True)


class State(TypedDict):
    """Agent state for LangGraph workflow."""
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool


class EvaluatorOutput(BaseModel):
    """Structured output from the evaluator LLM."""
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(
        description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
    )


class Orion:
    """
    Main Orion AI Agent.
    Uses a worker-evaluator pattern with LangGraph for robust task completion.
    """
    
    def __init__(self):
        self.worker_llm = None              # Unbound worker LLM (for dynamic tool binding)
        self.worker_llm_with_tools = None    # Worker LLM bound to ALL tools (fallback)
        self.evaluator_llm_with_output = None
        self.router_llm = None               # Lightweight LLM for intent classification
        self.tools = None
        self.llm_with_tools = None
        self.graph = None
        self.orion_id = str(uuid.uuid4())
        # Checkpoint storage — currently in-memory via MemorySaver.
        # Migration path: swap to RedisSaver/PostgresSaver for horizontal scaling.
        # Same BaseCheckpointSaver interface — zero code changes in graph logic.
        self.memory = MemorySaver()
        self.browser = None
        self.playwright = None
        self.tool_usage_count = 0
        
        # Router: tool index by category for focused tool selection
        self._tool_index = {}  # {AgentCategory: [tool_objects]}
        
        # Rate limiting for LLM calls (protect free tier limits)
        self.llm_rate_limiter = RateLimiter(
            max_calls=Config.LLM_REQUESTS_PER_MINUTE,
            period=60
        )
        self.last_llm_call = 0
        
        # Circuit breaker: fail fast when Groq is down instead of burning retries.
        # Already user-agnostic — works identically for 1 or N users.
        self.llm_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            name="groq_llm"
        )
        
        # Per-user rate limiter: prevents one noisy user from starving others.
        # Currently in-memory dict. Migration path: Redis INCR with TTL for
        # distributed rate limiting across multiple Orion instances.
        self.user_rate_limiter = RateLimiter(
            max_calls=Config.USER_REQUESTS_PER_MINUTE,
            period=60
        )
        
        # --- Observability: request metrics + latency samples (Phase 3) ---
        self._request_metrics = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "rate_limited": 0,
            "circuit_broken": 0,
        }
        self._latency_samples = []       # Rolling window of last 100 e2e latencies (ms)
        self._worker_latency_samples = [] # Rolling window of last 100 worker LLM latencies (ms)
        
        # --- Graceful shutdown + in-flight tracking (Phase 4) ---
        self._shutting_down = False
        self._in_flight_requests = 0
        self._in_flight_lock = threading.Lock()
        
        # Conversation memory (persistent)
        self.conversation_memory = None
        
        logger.info(f"Orion instance created with ID: {self.orion_id}")

    @async_retry_on_error(max_retries=2, delay=1.0)
    async def setup(self):
        """Initialize Orion with LLMs, tools, and graph."""
        import ssl
        import httpx
        from tools import get_all_tools
        from core.memory import ConversationMemory
        
        logger.info("Starting Orion setup...")
        
        # --- Phase 4: Fail-fast config validation before any heavy initialization ---
        config_warnings = Config.validate_or_fail()  # Raises ConfigValidationError on critical issues
        if config_warnings:
            logger.warning(f"Config validation: {len(config_warnings)} warning(s) at startup")
        
        # Initialize persistent conversation memory
        self.conversation_memory = ConversationMemory()
        logger.info("Persistent memory initialized")
        
        # Ensure required directories exist
        Config.ensure_directories()
        
        # Get proxy settings from environment if available
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        # Create HTTP client with SSL verification completely disabled
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Configure httpx clients with disabled verification and no redirects
        http_client = httpx.Client(
            verify=False, 
            timeout=60.0,
            follow_redirects=False,
            proxy=https_proxy
        )
        async_http_client = httpx.AsyncClient(
            verify=False, 
            timeout=60.0,
            follow_redirects=False,
            proxy=https_proxy
        )
        
        # Initialize all tools
        self.tools, self.browser, self.playwright = await get_all_tools()
        logger.info(f"Loaded {len(self.tools)} tools")
        
        GROQ_BASE_URL = "https://api.groq.com/openai/v1"

        self.worker_llm = ChatOpenAI(
            model=Config.WORKER_MODEL,
            base_url=GROQ_BASE_URL,
            api_key=Config.GROQ_API_KEY,
            http_client=http_client,
            http_async_client=async_http_client,
            max_retries=2
        )
        logger.info("Worker LLM initialized")
        self.worker_llm_with_tools = self.worker_llm.bind_tools(self.tools)
        
        # Build tool index for router-based focused tool selection
        self._build_tool_index()

        # Initialize lightweight router LLM for intent classification
        # Uses llama-3.1-8b-instant: 14,400 RPD (separate quota from worker)
        router_base_llm = ChatOpenAI(
            model=Config.ROUTER_MODEL,
            base_url=GROQ_BASE_URL,
            api_key=Config.GROQ_API_KEY,
            http_client=http_client,
            http_async_client=async_http_client,
            max_retries=1,
            temperature=0,  # Deterministic classification
        )
        self.router_llm = router_base_llm.with_structured_output(
            RouterClassification
        )
        logger.info(f"Router LLM initialized ({Config.ROUTER_MODEL})")

        evaluator_llm = ChatOpenAI(
            model=Config.EVALUATOR_MODEL,
            base_url=GROQ_BASE_URL,
            api_key=Config.GROQ_API_KEY,
            http_client=http_client,
            http_async_client=async_http_client,
            max_retries=2
        )
        self.evaluator_llm_with_output = evaluator_llm.with_structured_output(EvaluatorOutput)
        logger.info("Evaluator LLM initialized")
        
        await self.build_graph()
        logger.info("Orion setup completed successfully")

    def _build_tool_index(self):
        """Build an index mapping AgentCategory → list of tool objects.
        
        Uses TOOL_CATEGORIES from agents/router.py to map tool names to categories,
        then resolves tool names to actual tool objects from self.tools.
        This enables the router to select focused tool subsets per query.
        """
        self._tool_index = {cat: [] for cat in AgentCategory}
        
        # Build a name→tool lookup from loaded tools
        tool_by_name = {tool.name: tool for tool in self.tools}
        
        # Map each tool to its category
        categorized_tool_names = set()
        for tool_name, category in TOOL_CATEGORIES.items():
            if tool_name in tool_by_name:
                self._tool_index[category].append(tool_by_name[tool_name])
                categorized_tool_names.add(tool_name)
        
        # Any tool not in TOOL_CATEGORIES goes into GENERAL (catch-all)
        for tool in self.tools:
            if tool.name not in categorized_tool_names:
                self._tool_index[AgentCategory.GENERAL].append(tool)
        
        # Log the index
        for cat, cat_tools in self._tool_index.items():
            if cat_tools:
                logger.info(f"Router index: {cat.value} → {len(cat_tools)} tools")
        
        logger.info(f"Tool index built: {len(self.tools)} tools across {sum(1 for t in self._tool_index.values() if t)} categories")

    def _get_tools_for_category(self, category: AgentCategory) -> list:
        """Get focused tool set for a category.
        
        Returns the category-specific tools PLUS research tools (web_search, wikipedia)
        as universal fallbacks. This ensures the LLM always has a search escape hatch
        even when routed to a specialized category.
        
        Args:
            category: The classified AgentCategory
            
        Returns:
            List of tool objects for this category
        """
        focused_tools = list(self._tool_index.get(category, []))
        
        # Always include research tools as fallback (web_search, wikipedia_search)
        # This ensures the agent can always search for info it doesn't have a tool for
        if category != AgentCategory.RESEARCH:
            research_tools = self._tool_index.get(AgentCategory.RESEARCH, [])
            for tool in research_tools:
                if tool not in focused_tools:
                    focused_tools.append(tool)
        
        # If somehow we ended up with very few tools, fall back to all
        if len(focused_tools) < 3:
            return list(self.tools)
        
        return focused_tools

    def worker(self, state: State) -> Dict[str, Any]:
        """Worker node: processes tasks using tools."""
        # Get current IST time
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(IST)
        
        system_message = f"""You are Orion, a personal AI assistant. You MUST use your tools to complete tasks.

🚨 CRITICAL RULES - READ FIRST:
1. ALWAYS USE TOOLS to complete tasks. NEVER give manual instructions.
2. For reminders/calendar/events → ALWAYS call `create_calendar_event` tool
3. For emails → ALWAYS call `send_email` or `read_recent_emails` tools
4. For tasks/notes → ALWAYS call the appropriate tool
5. DO NOT say "I cannot directly..." - you CAN by using tools!
6. DO NOT give step-by-step instructions for users to do manually.

⚠️⚠️⚠️ RULE #7 - ABSOLUTELY CRITICAL FOR TOOL RESPONSES:
After receiving tool results, you MUST respond with PLAIN TEXT ONLY - NO markdown formatting!
• DO NOT use **bold**, *italics*, headers (##), or numbered lists (1., 2., 3.)
• DO NOT start with "Here are...", "Here is...", "I found..."
• JUST state the information directly in plain conversational text
• Example WRONG: "Here are some YouTube videos:\n\n1. **Video Title**..."
• Example RIGHT: "I found several Python tutorials. The top one is Video Title by Creator, about 30 minutes long."
Failing to follow this rule causes API errors!

🌐 WEB SEARCH FALLBACK - USE FOR ANY INFO NOT COVERED BY SPECIFIC TOOLS:
When you need information but don't have a dedicated tool, USE `web_search` tool:
• Weather queries → call `web_search` with "weather in [city]"
• News/current events → call `web_search` with the query
• Product prices → call `web_search` with the query
• Sports scores → call `web_search` with the query
• Stock prices → call `web_search` with the query
• Any real-time information → call `web_search`

📚 WIKIPEDIA - USE `wikipedia_search` TOOL:
• For definitions, biographies, history → call `wikipedia_search` tool
• For summaries of topics, places, people → call `wikipedia_search` tool
• DO NOT say "I don't have Wikipedia access" - you DO have `wikipedia_search` tool!
• IMPORTANT: The `sentences` parameter MUST be an INTEGER (e.g., 5), NOT a string (NOT "5")

💻 GITHUB - USE GITHUB TOOLS FOR:
• `github_search_repos` → Search for repositories (e.g., "AI projects", "langchain")
• `github_list_repos` → List user's repositories  
• `github_get_repo_info` → Get details about a specific repo
• `github_list_issues` → List issues in a repository
• `github_create_issue` → Create a new issue
• `github_list_pull_requests` → List PRs in a repository
DO NOT say "I cannot access GitHub" - you HAVE GitHub tools!

═══════════════════════════════════════════════════════════════════
📍 USER CONTEXT (IMPORTANT - USE THIS FOR ALL RESPONSES)
═══════════════════════════════════════════════════════════════════
• Location: India (default for all geo-related queries)
• Timezone: IST (Indian Standard Time, UTC+5:30)
• Current Date: {now_ist.strftime("%A, %B %d, %Y")}
• Current Time: {now_ist.strftime("%I:%M %p IST")}
• Week Number: {now_ist.strftime("%W")}

📐 DEFAULT UNITS (use these unless user specifies otherwise):
• Temperature: Celsius (°C)
• Distance: Kilometers (km), meters (m)
• Weight: Kilograms (kg), grams (g)
• Volume: Liters (L), milliliters (mL)
• Currency: Indian Rupees (₹ / INR)
• Date Format: DD/MM/YYYY
• Time Format: 12-hour with AM/PM

📅 RELATIVE DATE/TIME UNDERSTANDING:
• "today" = {now_ist.strftime("%A, %B %d, %Y")}
• "tomorrow" = {(now_ist + timedelta(days=1)).strftime("%A, %B %d, %Y")}
• "yesterday" = {(now_ist - timedelta(days=1)).strftime("%A, %B %d, %Y")}
• "day after tomorrow" = {(now_ist + timedelta(days=2)).strftime("%A, %B %d, %Y")}
• "next week" = week starting {(now_ist + timedelta(days=(7 - now_ist.weekday()))).strftime("%B %d")}

⏰ REMINDER & CALENDAR - MANDATORY TOOL USAGE:
When user says ANY of these, you MUST call `create_calendar_event` tool:
• "set a reminder" / "remind me" / "reminder for"
• "add to calendar" / "schedule" / "book"
• "create event" / "meeting at" / "appointment"
• "birthday on" / "anniversary"

HOW TO CALL create_calendar_event:
  start_time: "{now_ist.strftime('%Y-%m-%d')}T19:30:00" (REQUIRED - use ISO format)
  title: "The reminder/event name" (ALWAYS include a descriptive title!)

EXAMPLE: User says "Set a reminder for 7:30 PM today"
→ Call create_calendar_event(start_time="{now_ist.strftime('%Y-%m-%d')}T19:30:00", title="Reminder")

EXAMPLE: User says "Remind me to call mom at 8 PM"  
→ Call create_calendar_event(start_time="{now_ist.strftime('%Y-%m-%d')}T20:00:00", title="Call mom")

📍 LOCATION PARSING (understand these formats):
• Google Maps links: Extract coordinates from URLs like maps.google.com/?q=lat,lng
• Plus codes: e.g., "7JVW+HG Delhi"
• Area/Locality names: e.g., "Connaught Place, Delhi" or "Koramangala, Bangalore"
• Landmark references: e.g., "near India Gate" or "opposite City Mall"
• Telegram location shares: Parse latitude/longitude from shared locations
• Pin codes: Indian postal codes (6 digits)
• If no location specified, assume general India context

═══════════════════════════════════════════════════════════════════

You have access to 60+ powerful tools across multiple categories:

📧 Communication:
- `send_email` - Send emails
- `read_recent_emails` - Read recent emails

📅 Productivity:
- `create_calendar_event` - Create Google Calendar events/reminders
- `list_calendar_events` - List upcoming events
- `create_task`, `list_tasks`, `complete_task` - Task management
- `create_note`, `list_notes`, `read_note`, `search_notes` - Note management

📸 Media & Documents:
- `take_screenshot` - Capture screenshots
- `read_pdf`, `create_pdf` - PDF handling
- `ocr_image` - Extract text from images
- `read_csv`, `read_excel`, `read_json` - Read data files
- `generate_qr` - Generate QR codes

🌐 Web & Research (IMPORTANT - USE THESE!):
- `web_search` - Google search via Serper (USE FOR WEATHER, NEWS, PRICES, etc.)
- `browser_search` - Browser-based search fallback
- `fetch_webpage` - Fetch and read webpage content
- `wikipedia_search` - Search Wikipedia (USE FOR DEFINITIONS, HISTORY, BIOGRAPHIES!)

🎬 YouTube:
- `search_youtube` - Search YouTube videos
- `get_youtube_transcript` - Get video transcripts
- `get_youtube_video_info` - Get video metadata

💻 GitHub (REQUIRES GITHUB_TOKEN):
- `github_search_repos` - Search repositories
- `github_list_repos` - List user's repos
- `github_get_repo_info` - Get repo details
- `github_list_issues`, `github_create_issue` - Issue management
- `github_list_pull_requests` - List PRs

📖 Dictionary:
- `define_word` - Word definitions
- `get_synonyms`, `get_antonyms` - Synonyms/antonyms
- `translate_text` - Translations

🚂 Indian Railways:
- `check_pnr_status` - Check booking status with 10-digit PNR number
- `get_train_status` - Live running status, delays, and current location
- `search_trains` - Find trains between stations by date
- `get_station_code` - Get railway station codes for any city

✈️ Flights:
- `get_flight_status` - Check live status by flight number (e.g., AI101, 6E2123)
- `get_flight_by_route` - Find flights between cities
- `get_airport_info` - Get airport details, terminals, metro connections
- `track_flight_live` - Get real-time aircraft position and tracking links

💻 System:
- `python_repl` - Execute Python code for calculations, data processing
- File management tools for reading/writing files

⚠️ IMPORTANT REMINDERS:
1. For WEATHER → Use `web_search` with "weather in [city]"
2. For WIKIPEDIA info → Use `wikipedia_search` tool
3. For YOUTUBE → Use `search_youtube` tool
4. For GITHUB → Use `github_search_repos` or other GitHub tools
5. ALWAYS call a tool - NEVER just describe what you would do!
6. If a tool fails, try `web_search` as fallback for information queries.

This is the success criteria:
{state["success_criteria"]}
You should reply either with a question for the user about this assignment, or with your final response.
If you have a question for the user, you need to reply by clearly stating your question. An example might be:

Question: please clarify whether you want a summary or a detailed answer

If you've finished, reply with the final answer, and don't ask a question; simply reply with the answer.
"""

        if state.get("feedback_on_work"):
            system_message += f"""
Previously you thought you completed the assignment, but your reply was rejected because the success criteria was not met.
Here is the feedback on why this was rejected:
{state["feedback_on_work"]}
With this feedback, please continue the assignment, ensuring that you meet the success criteria or have a question for the user."""

        # Add in the system message
        found_system_message = False
        messages = state["messages"]
        for message in messages:
            if isinstance(message, SystemMessage):
                message.content = system_message
                found_system_message = True

        if not found_system_message:
            messages = [SystemMessage(content=system_message)] + messages

        # Rate limiting: wait if needed to avoid hitting free tier limits
        self._apply_rate_limit_sync()
        
        # --- ROUTER: Classify intent and select focused tool set ---
        # Extract the user's message text for classification
        user_text = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_text = msg.content
                break
        
        # Route to focused tools or use all tools as fallback
        routing = get_agent_for_query(user_text, router_llm=self.router_llm) if user_text else None
        
        if routing and routing["should_delegate"]:
            category = routing["category"]
            focused_tools = self._get_tools_for_category(category)
            llm_to_use = self.worker_llm.bind_tools(focused_tools)
            logger.info(
                f"Router: {routing['agent']['icon']} {routing['agent']['name']} "
                f"(confidence: {routing['confidence']:.2f}, tools: {len(focused_tools)}/{len(self.tools)})"
            )
        else:
            llm_to_use = self.worker_llm_with_tools  # All tools (fallback)
            logger.info(f"Router: 🤖 General Orion (all {len(self.tools)} tools)")
        
        # Invoke the LLM with selected tools
        if not self.llm_circuit_breaker.can_execute():
            cb_state = self.llm_circuit_breaker.get_state()
            wait_hint = max(0, self.llm_circuit_breaker.recovery_timeout - (time.time() - self.llm_circuit_breaker.last_failure_time))
            logger.warning(f"Circuit breaker OPEN -- failing fast (retry in {wait_hint:.0f}s)")
            return {
                "messages": [AIMessage(content=(
                    "I'm temporarily unable to process requests. The LLM service appears to be down. "
                    f"Please try again in about {int(wait_hint)} seconds."
                ))]
            }
        
        worker_start = time.time()
        try:
            response = llm_to_use.invoke(messages)
            self.llm_circuit_breaker.record_success()
            worker_ms = int((time.time() - worker_start) * 1000)
            
            # Track worker latency
            self._worker_latency_samples.append(worker_ms)
            if len(self._worker_latency_samples) > 100:
                self._worker_latency_samples.pop(0)
            
            # Track tool usage
            if hasattr(response, "tool_calls") and response.tool_calls:
                self.tool_usage_count += len(response.tool_calls)
                logger.info(f"Worker invoked {len(response.tool_calls)} tools in {worker_ms}ms",
                            event="worker_tool_calls", tool_count=len(response.tool_calls), latency_ms=worker_ms)
            else:
                logger.info(f"Worker LLM call completed in {worker_ms}ms",
                            event="worker_llm_call", latency_ms=worker_ms)
            
            return {"messages": [response]}
        except Exception as e:
            self.llm_circuit_breaker.record_failure()
            worker_ms = int((time.time() - worker_start) * 1000)
            logger.error(f"Worker error: {str(e)}", event="worker_error", latency_ms=worker_ms)
            error_message = AIMessage(content=f"I encountered an error: {str(e)}")
            return {"messages": [error_message]}

    def worker_router(self, state: State) -> str:
        """Route worker output to tools or evaluator."""
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        else:
            return "evaluator"

    def format_conversation(self, messages: List[Any]) -> str:
        """Format conversation history for evaluator."""
        conversation = "Conversation history:\n\n"
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                text = message.content or "[Tools use]"
                conversation += f"Assistant: {text}\n"
        return conversation

    def evaluator(self, state: State) -> State:
        """Evaluator node: assesses if task is complete."""
        last_response = state["messages"][-1].content

        system_message = """You are an evaluator that determines if a task has been completed successfully by an Assistant.
Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
and whether more input is needed from the user."""

        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

The entire conversation with the assistant, with the user's original request and all replies, is:
{self.format_conversation(state["messages"])}

The success criteria for this assignment is:
{state["success_criteria"]}

And the final response from the Assistant that you are evaluating is:
{last_response}

Respond with your feedback, and decide if the success criteria is met by this response.
Also, decide if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help.

The Assistant has access to a tool to write files. If the Assistant says they have written a file, then you can assume they have done so.
Overall you should give the Assistant the benefit of the doubt if they say they've done something. But you should reject if you feel that more work should go into this.

"""
        if state["feedback_on_work"]:
            user_message += f"Also, note that in a prior attempt from the Assistant, you provided this feedback: {state['feedback_on_work']}\n"
            user_message += "If you're seeing the Assistant repeating the same mistakes, then consider responding that user input is required."

        evaluator_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        # Circuit breaker check for evaluator LLM call
        if not self.llm_circuit_breaker.can_execute():
            logger.warning("Circuit breaker OPEN -- skipping evaluator, treating as success")
            return {
                "messages": [{"role": "assistant", "content": "Evaluator skipped (LLM temporarily unavailable)"}],
                "feedback_on_work": "",
                "success_criteria_met": True,
                "user_input_needed": False,
            }

        eval_start = time.time()
        try:
            eval_result = self.evaluator_llm_with_output.invoke(evaluator_messages)
            self.llm_circuit_breaker.record_success()
            eval_ms = int((time.time() - eval_start) * 1000)
            logger.info(f"Evaluator completed in {eval_ms}ms (met={eval_result.success_criteria_met})",
                        event="evaluator_complete", latency_ms=eval_ms,
                        success_criteria_met=eval_result.success_criteria_met)
        except Exception as e:
            self.llm_circuit_breaker.record_failure()
            eval_ms = int((time.time() - eval_start) * 1000)
            logger.error(f"Evaluator error: {str(e)} -- treating as success",
                         event="evaluator_error", latency_ms=eval_ms)
            return {
                "messages": [{"role": "assistant", "content": f"Evaluator error: {str(e)}"}],
                "feedback_on_work": "",
                "success_criteria_met": True,
                "user_input_needed": False,
            }

        new_state = {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Evaluator Feedback on this answer: {eval_result.feedback}",
                }
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }
        return new_state

    def route_based_on_evaluation(self, state: State) -> str:
        """Route based on evaluator decision."""
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        else:
            return "worker"

    async def build_graph(self):
        """Build the LangGraph workflow."""
        graph_builder = StateGraph(State)

        # Add nodes
        graph_builder.add_node("worker", self.worker)
        graph_builder.add_node("tools", ToolNode(tools=self.tools))
        graph_builder.add_node("evaluator", self.evaluator)

        # Add edges
        graph_builder.add_conditional_edges(
            "worker", self.worker_router, {"tools": "tools", "evaluator": "evaluator"}
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator", self.route_based_on_evaluation, {"worker": "worker", "END": END}
        )
        graph_builder.add_edge(START, "worker")

        # Compile the graph
        self.graph = graph_builder.compile(checkpointer=self.memory)

    def _apply_rate_limit_sync(self):
        """Apply rate limiting to protect free tier LLM limits (sync version)."""
        # Check if we need to wait based on rate limiter
        if not self.llm_rate_limiter.check("llm"):
            wait_time = self.llm_rate_limiter.wait_time("llm")
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        # Also apply minimum cooldown between calls
        elapsed = time.time() - self.last_llm_call
        if elapsed < Config.LLM_COOLDOWN_SECONDS:
            wait = Config.LLM_COOLDOWN_SECONDS - elapsed
            logger.debug(f"Cooldown: waiting {wait:.1f}s before next LLM call")
            time.sleep(wait)
        
        self.last_llm_call = time.time()

    async def _apply_rate_limit(self):
        """Apply rate limiting to protect free tier LLM limits (async version)."""
        # Check if we need to wait based on rate limiter
        if not self.llm_rate_limiter.check("llm"):
            wait_time = self.llm_rate_limiter.wait_time("llm")
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
        
        # Also apply minimum cooldown between calls
        elapsed = time.time() - self.last_llm_call
        if elapsed < Config.LLM_COOLDOWN_SECONDS:
            wait = Config.LLM_COOLDOWN_SECONDS - elapsed
            logger.debug(f"Cooldown: waiting {wait:.1f}s before next LLM call")
            await asyncio.sleep(wait)
        
        self.last_llm_call = time.time()

    async def run_superstep(
        self,
        message: str,
        success_criteria: str,
        history: List,
        user_id: str = None,
        channel: str = "default"
    ):
        """
        Run a superstep with optional memory persistence.
        
        Args:
            message: The user's message
            success_criteria: Criteria for evaluating success
            history: Conversation history
            user_id: Optional user ID for persistent memory
            channel: Channel name (telegram, email, api, etc.)
        """
        # --- Phase 4: Input validation (fail early before any LLM work) ---
        from pydantic import ValidationError
        try:
            validated = ChatRequest(
                message=message,
                user_id=user_id or "anonymous",
                channel=channel,
                success_criteria=success_criteria or "The answer should be clear and accurate",
            )
            # Use validated (sanitized) values downstream
            message = validated.message
            user_id = validated.user_id if user_id else None
            channel = validated.channel
            success_criteria = validated.success_criteria
        except ValidationError as e:
            error_details = "; ".join(
                f"{err['loc'][-1]}: {err['msg']}" for err in e.errors()
            )
            logger.warning(f"Input validation failed: {error_details}",
                           event="input_validation_error", errors=error_details)
            self._request_metrics["failed"] += 1
            return history + [[message, f"Invalid request: {error_details}"]]

        # --- Phase 4: Reject requests during graceful shutdown ---
        if self._shutting_down:
            logger.warning("Request rejected: system is shutting down",
                           event="shutdown_reject", user_id=user_id)
            return history + [[message, "The system is shutting down. Please try again shortly."]]

        # Per-user thread isolation: each user x channel gets its own LangGraph checkpoint.
        # This prevents User B from seeing User A's in-flight state.
        # Already multi-user aware -- no changes needed when scaling to N users.
        thread_id = f"{user_id}_{channel}" if user_id else self.orion_id
        config = {"configurable": {"thread_id": thread_id}}
        
        # --- Per-user rate limiting: fairness guard ---
        if user_id and not self.user_rate_limiter.check(f"user:{user_id}"):
            wait = self.user_rate_limiter.wait_time(f"user:{user_id}")
            logger.warning(f"Per-user rate limit hit for {user_id}",
                           event="rate_limit_hit", user_id=user_id, wait_seconds=int(wait))
            self._request_metrics["rate_limited"] += 1
            return history + [[message, (
                f"You're sending requests too quickly. "
                f"Please wait about {int(wait)} seconds before trying again."
            )]]

        # --- Generate correlation ID for request tracing (Phase 3) ---
        request_id = str(uuid.uuid4())[:8]
        e2e_start = time.time()
        self._request_metrics["total_requests"] += 1
        
        logger.info(f"Superstep start [{request_id}] for: {message[:50]}...",
                    event="superstep_start", request_id=request_id,
                    user_id=user_id, channel=channel,
                    message_preview=message[:80])

        state = {
            "messages": message,
            "success_criteria": success_criteria or "The answer should be clear and accurate",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }
        
        try:
            # --- Phase 4: Track in-flight requests for graceful shutdown ---
            with self._in_flight_lock:
                self._in_flight_requests += 1

            logger.info(f"Running superstep for message: {message[:50]}...")
            
            # Save user message to persistent memory if user_id provided
            if user_id and self.conversation_memory:
                self.conversation_memory.add_message(
                    user_id=user_id,
                    channel=channel,
                    role="user",
                    content=message
                )
            
            result = await self.graph.ainvoke(state, config=config)
            
            # Extract the assistant's reply from the result
            assistant_message = result["messages"][-2].content if len(result["messages"]) >= 2 else "No response"
            
            # Save assistant response to persistent memory
            if user_id and self.conversation_memory:
                self.conversation_memory.add_message(
                    user_id=user_id,
                    channel=channel,
                    role="assistant",
                    content=assistant_message
                )
            
            # --- Latency tracking (Phase 3) ---
            e2e_ms = int((time.time() - e2e_start) * 1000)
            self._latency_samples.append(e2e_ms)
            if len(self._latency_samples) > 100:
                self._latency_samples.pop(0)
            self._request_metrics["successful"] += 1
            
            logger.info(f"Superstep complete [{request_id}] in {e2e_ms}ms",
                        event="superstep_complete", request_id=request_id,
                        user_id=user_id, channel=channel, latency_ms=e2e_ms)
            
            # Return in tuple format: (user_message, assistant_message)
            return history + [[message, assistant_message]]
        except Exception as e:
            e2e_ms = int((time.time() - e2e_start) * 1000)
            self._request_metrics["failed"] += 1
            logger.error(f"Error in run_superstep [{request_id}]: {str(e)}",
                         event="superstep_error", request_id=request_id,
                         user_id=user_id, latency_ms=e2e_ms, error=str(e))
            
            # Add to retry queue if user_id is provided
            if user_id:
                from core.memory import retry_queue
                retry_queue.add_failed_request(
                    user_id=user_id,
                    channel=channel,
                    message=message,
                    error=str(e)
                )
                error_msg = f"I encountered an error and will retry in {Config.RETRY_DELAY_MINUTES} minutes. Error: {str(e)}"
            else:
                error_msg = f"I apologize, but I encountered an error: {str(e)}"
            
            return history + [[message, error_msg]]
        finally:
            # Always decrement in-flight counter (Phase 4: graceful shutdown)
            with self._in_flight_lock:
                self._in_flight_requests -= 1
    
    def get_metrics(self) -> dict:
        """Return observability metrics for the /metrics endpoint.
        
        Includes request counts, latency percentiles, circuit breaker state,
        and tool usage stats. Designed for JSON serialization.
        """
        import statistics
        
        # Compute latency percentiles from rolling samples
        def _percentiles(samples):
            if not samples:
                return {"p50": 0, "p90": 0, "p99": 0, "avg": 0, "count": 0}
            sorted_s = sorted(samples)
            n = len(sorted_s)
            return {
                "p50": sorted_s[n // 2],
                "p90": sorted_s[int(n * 0.9)] if n >= 10 else sorted_s[-1],
                "p99": sorted_s[int(n * 0.99)] if n >= 100 else sorted_s[-1],
                "avg": int(statistics.mean(sorted_s)),
                "count": n,
            }
        
        return {
            "requests": dict(self._request_metrics),
            "latency_ms": {
                "e2e": _percentiles(self._latency_samples),
                "worker_llm": _percentiles(self._worker_latency_samples),
            },
            "circuit_breaker": self.llm_circuit_breaker.get_state(),
            "tools": {
                "total_loaded": len(self.tools) if self.tools else 0,
                "tool_calls_this_session": self.tool_usage_count,
            },
            "shutdown": {
                "shutting_down": self._shutting_down,
                "in_flight_requests": self._in_flight_requests,
            },
        }

    def get_conversation_history(self, user_id: str, channel: str = None, limit: int = None) -> List[Dict]:
        """Get persistent conversation history for a user."""
        if not self.conversation_memory:
            return []
        
        limit = limit or Config.MEMORY_HISTORY_LIMIT
        return self.conversation_memory.get_formatted_history(user_id, channel, limit)
    
    def get_tool_usage_count(self) -> int:
        """Get the number of tools used in this session."""
        return self.tool_usage_count

    async def graceful_shutdown(self, timeout: int = 30):
        """Graceful shutdown: stop accepting new requests, wait for in-flight to finish.
        
        Phase 4 Hardening: prevents data loss from abrupt termination.
        
        Args:
            timeout: Maximum seconds to wait for in-flight requests before force-closing.
        
        Returns:
            dict with shutdown stats (requests_drained, forced, elapsed_s)
        """
        logger.info("Initiating graceful shutdown...",
                     event="shutdown_start", timeout_s=timeout,
                     in_flight=self._in_flight_requests)
        
        # 1. Stop accepting new requests (run_superstep checks this flag)
        self._shutting_down = True
        
        # 2. Wait for in-flight requests to complete (with timeout)
        start = time.time()
        poll_interval = 0.5
        while self._in_flight_requests > 0:
            elapsed = time.time() - start
            if elapsed >= timeout:
                logger.warning(
                    f"Shutdown timeout after {timeout}s with {self._in_flight_requests} request(s) still in-flight",
                    event="shutdown_timeout",
                    in_flight=self._in_flight_requests)
                break
            logger.info(f"Waiting for {self._in_flight_requests} in-flight request(s)... ({elapsed:.0f}s/{timeout}s)")
            await asyncio.sleep(poll_interval)
        
        elapsed = round(time.time() - start, 1)
        forced = self._in_flight_requests > 0
        
        # 3. Clean up resources
        self.cleanup()
        
        result = {
            "requests_drained": not forced,
            "forced": forced,
            "in_flight_at_shutdown": self._in_flight_requests,
            "elapsed_s": elapsed,
        }
        logger.info(f"Graceful shutdown complete in {elapsed}s (forced={forced})",
                     event="shutdown_complete", **result)
        return result

    def cleanup(self):
        """Clean up resources (browser, playwright)."""
        logger.info("Cleaning up Orion resources...")
        if self.browser:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.browser.close())
                if self.playwright:
                    loop.create_task(self.playwright.stop())
            except RuntimeError:
                # If no loop is running, do a direct run
                asyncio.run(self.browser.close())
                if self.playwright:
                    asyncio.run(self.playwright.stop())
        logger.info("Cleanup completed")
