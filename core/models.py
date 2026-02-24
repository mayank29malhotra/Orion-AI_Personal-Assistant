"""
Orion AI — Input Validation Models (Phase 4: Hardening)

Pydantic models for all external inputs. Every request that enters Orion
passes through these models for validation before touching any business logic.

Why Pydantic:
- Already a dependency (used by LangGraph, LangChain, FastAPI)
- Zero new deps, type-safe, auto-generates error messages
- Consistent validation across Telegram, Gradio, Email, and future channels
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re


class ChatRequest(BaseModel):
    """Validated input for Orion chat requests.
    
    Used in run_superstep() to validate all incoming messages regardless
    of channel (Telegram, Gradio, Email, API). Rejects malformed input
    before any LLM call is made — saves tokens and prevents unexpected errors.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User message text"
    )
    user_id: str = Field(
        default="anonymous",
        min_length=1,
        max_length=200,
        description="User identifier"
    )
    channel: str = Field(
        default="default",
        min_length=1,
        max_length=50,
        description="Channel name (telegram, gradio, email, api, etc.)"
    )
    success_criteria: str = Field(
        default="The answer should be clear and accurate",
        max_length=2000,
        description="Criteria for evaluating response quality"
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        """Reject whitespace-only messages."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be blank or whitespace-only")
        return stripped

    @field_validator("channel")
    @classmethod
    def channel_safe_chars(cls, v: str) -> str:
        """Channel names must be alphanumeric + underscore/hyphen (safe for thread IDs)."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError(
                f"Channel name '{v}' contains invalid characters. "
                "Only letters, numbers, underscores, and hyphens are allowed."
            )
        return v.lower()

    @field_validator("user_id")
    @classmethod
    def user_id_sanitized(cls, v: str) -> str:
        """Strip whitespace from user_id."""
        return v.strip()


class HealthResponse(BaseModel):
    """Structured response for /health endpoint."""
    status: str = Field(description="healthy or degraded")
    service: str = Field(default="Orion AI")
    timestamp: str = Field(description="ISO format timestamp")
    checks: dict = Field(default_factory=dict, description="Subsystem health checks")


class MetricsResponse(BaseModel):
    """Structured response for /metrics endpoint."""
    timestamp: str = Field(description="ISO format timestamp")
    orion: Optional[dict] = Field(default=None, description="Orion agent metrics")
    memory: dict = Field(default_factory=dict, description="Memory subsystem stats")
    retry_queue: dict = Field(default_factory=dict, description="Retry queue stats")
    pending_queue: dict = Field(default_factory=dict, description="Pending queue stats")
