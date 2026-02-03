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
from datetime import datetime

from core.config import Config
from core.utils import logger, RateLimiter, async_retry_on_error

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
        self.worker_llm_with_tools = None
        self.evaluator_llm_with_output = None
        self.tools = None
        self.llm_with_tools = None
        self.graph = None
        self.orion_id = str(uuid.uuid4())
        self.memory = MemorySaver()
        self.browser = None
        self.playwright = None
        self.tool_usage_count = 0
        
        # Rate limiting for LLM calls (protect free tier limits)
        self.llm_rate_limiter = RateLimiter(
            max_calls=Config.LLM_REQUESTS_PER_MINUTE,
            period=60
        )
        self.last_llm_call = 0
        
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

        worker_llm = ChatOpenAI(
            model=Config.WORKER_MODEL,
            base_url=GROQ_BASE_URL,
            api_key=Config.GROQ_API_KEY,
            http_client=http_client,
            http_async_client=async_http_client,
            max_retries=2
        )
        logger.info("Worker LLM initialized")
        self.worker_llm_with_tools = worker_llm.bind_tools(self.tools)

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

    def worker(self, state: State) -> Dict[str, Any]:
        """Worker node: processes tasks using tools."""
        # Get current IST time
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(IST)
        
        system_message = f"""You are Orion, a helpful personal AI assistant that can use tools to complete tasks.
You keep working on a task until either you have a question or clarification for the user, or the success criteria is met.

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
• For calendar events, always use IST times

⏰ REMINDER BEHAVIOR:
• When user says "set a reminder", "remind me", or "reminder for" → CREATE A GOOGLE CALENDAR EVENT
• Use `create_calendar_event` tool for ALL reminders
• Include the reminder text as the event title
• Set appropriate time based on user's request
• Example: "Remind me to call mom at 5pm" → Create calendar event titled "Call mom" at 5:00 PM IST

📍 LOCATION PARSING (understand these formats):
• Google Maps links: Extract coordinates from URLs like maps.google.com/?q=lat,lng
• Plus codes: e.g., "7JVW+HG Delhi"
• Area/Locality names: e.g., "Connaught Place, Delhi" or "Koramangala, Bangalore"
• Landmark references: e.g., "near India Gate" or "opposite City Mall"
• Telegram location shares: Parse latitude/longitude from shared locations
• Pin codes: Indian postal codes (6 digits)
• If no location specified, assume general India context

═══════════════════════════════════════════════════════════════════

You have access to 50+ powerful tools across multiple categories:

📧 Communication:
- Email Management: Send and read emails

📅 Productivity:
- Calendar: Create and manage Google Calendar events  
- Tasks & Reminders: Create, list, and complete tasks
- Notes: Create and search notes

📸 Media & Documents:
- Screenshots: Capture screenshots
- PDF: Read and create PDF files
- OCR: Extract text from images
- Data: Read/write CSV, Excel, JSON files
- Markdown: Convert between Markdown and HTML
- QR Codes: Generate QR codes

🌐 Web & Research:
- Web: Browse websites, search, Wikipedia
- YouTube: Get video transcripts, info, and search
- Dictionary: Word definitions, synonyms, antonyms, translations

💻 System:
- Python: Execute Python code
- Files: Full file management
- GitHub: Repository management

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
        
        # Invoke the LLM with tools
        try:
            response = self.worker_llm_with_tools.invoke(messages)
            
            # Track tool usage
            if hasattr(response, "tool_calls") and response.tool_calls:
                self.tool_usage_count += len(response.tool_calls)
                logger.info(f"Worker invoked {len(response.tool_calls)} tools")
            
            return {"messages": [response]}
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
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

        eval_result = self.evaluator_llm_with_output.invoke(evaluator_messages)
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
        config = {"configurable": {"thread_id": self.orion_id}}

        state = {
            "messages": message,
            "success_criteria": success_criteria or "The answer should be clear and accurate",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }
        
        try:
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
            
            logger.info("Superstep completed successfully")
            # Return in tuple format: (user_message, assistant_message)
            return history + [[message, assistant_message]]
        except Exception as e:
            logger.error(f"Error in run_superstep: {str(e)}")
            
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
    
    def get_conversation_history(self, user_id: str, channel: str = None, limit: int = None) -> List[Dict]:
        """Get persistent conversation history for a user."""
        if not self.conversation_memory:
            return []
        
        limit = limit or Config.MEMORY_HISTORY_LIMIT
        return self.conversation_memory.get_formatted_history(user_id, channel, limit)
    
    def get_tool_usage_count(self) -> int:
        """Get the number of tools used in this session."""
        return self.tool_usage_count

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
