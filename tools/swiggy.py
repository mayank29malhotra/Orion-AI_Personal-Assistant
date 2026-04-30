"""
Swiggy MCP Integration (Phase 8 — FOOD domain)
==============================================

Loads Swiggy Builders Club MCP tools (Food, Dineout) into Orion as
LangChain `BaseTool` instances using the `langchain-mcp-adapters` package.

Two remote MCP servers, both over streamable HTTP, OAuth 2.1 + PKCE:
  - https://mcp.swiggy.com/food      (14 tools — restaurant discovery, ordering)
  - https://mcp.swiggy.com/dineout   ( 8 tools — table reservations)

(Swiggy also publishes an `/im` Instamart server, but Orion intentionally
scopes the FOOD domain to *food ordering* + *table booking* only — the
grocery surface is out of scope for the personal-assistant use case.)

Auth model
----------
Swiggy MCP requires a per-user OAuth 2.1 + PKCE bearer token (no static API key).
For Orion's single-user / personal-assistant model, we accept a pre-fetched
bearer token via the `SWIGGY_ACCESS_TOKEN` env var. The user must run the
OAuth flow once (e.g. via Claude Desktop, mcp-remote, or a custom helper) and
paste the resulting bearer into `.env`. Tokens last 5 days; refresh-token
issuance is not yet wired in v1.0 of Swiggy MCP, so on 401 the user re-runs
the auth flow.

Graceful degradation
--------------------
If `SWIGGY_ACCESS_TOKEN` is missing/empty, this loader returns `[]` and logs
a single info-level message — same pattern as `GITHUB_TOKEN` in `tools/github.py`.
Orion keeps running with its other tools and the FOOD category gracefully
reports "not configured" via the router fallback chain.

Tool naming
-----------
Swiggy uses the same tool name across servers in some cases (`get_addresses`,
`report_error`). To avoid collisions inside Orion's flat tool registry, every
tool is renamed with a server-specific prefix:

  - Food      → `swiggy_food_<name>`     (e.g. `swiggy_food_search_restaurants`)
  - Dineout   → `swiggy_dineout_<name>`  (e.g. `swiggy_dineout_book_table`)

The original tool name is preserved on a `.original_name` attribute for
debugging. Argument schema is left untouched — the underlying MCP client
forwards args verbatim to the upstream server.

References
----------
- Swiggy Builders Club docs: https://mcp.swiggy.com/builders/docs/
- Auth flow: https://mcp.swiggy.com/builders/docs/start/authenticate.md
- Tool catalogue: https://mcp.swiggy.com/builders/docs/reference/
- LangGraph integration recipe (header-based bearer auth):
  https://mcp.swiggy.com/builders/docs/start/developer/build-an-agent.md#langgraph
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger("orion.swiggy")


# Default endpoints (can be overridden via env for staging)
DEFAULT_FOOD_URL = "https://mcp.swiggy.com/food"
DEFAULT_DINEOUT_URL = "https://mcp.swiggy.com/dineout"


def _get_token() -> Optional[str]:
    """Bearer token from env. Pre-fetched by user via OAuth 2.1 + PKCE flow."""
    token = os.getenv("SWIGGY_ACCESS_TOKEN", "").strip()
    return token or None


def _server_config(token: str) -> dict:
    """Build the MultiServerMCPClient config dict.

    Each server gets its own bearer-header connection. A single OAuth token
    works across both servers since auth is shared. Individual servers can
    be disabled via `SWIGGY_<SERVER>_ENABLED=false`.
    """
    auth_headers = {"Authorization": f"Bearer {token}"}

    config: dict = {}

    if os.getenv("SWIGGY_FOOD_ENABLED", "true").lower() == "true":
        config["swiggy-food"] = {
            "url": os.getenv("SWIGGY_FOOD_URL", DEFAULT_FOOD_URL),
            "transport": "streamable_http",
            "headers": auth_headers,
        }
    if os.getenv("SWIGGY_DINEOUT_ENABLED", "true").lower() == "true":
        config["swiggy-dineout"] = {
            "url": os.getenv("SWIGGY_DINEOUT_URL", DEFAULT_DINEOUT_URL),
            "transport": "streamable_http",
            "headers": auth_headers,
        }

    return config


# Map MCP-client server-key → Orion tool-name prefix
_SERVER_PREFIX = {
    "swiggy-food": "swiggy_food_",
    "swiggy-dineout": "swiggy_dineout_",
}


def _prefix_tool(tool, server_key: str):
    """Rename a loaded MCP tool with the server-specific prefix.

    `langchain-mcp-adapters` returns `StructuredTool` instances (Pydantic-v2
    `BaseTool`). Rename in place to keep the underlying MCP transport closure
    intact — the tool's `coroutine`/`func` already binds the server endpoint.
    """
    prefix = _SERVER_PREFIX.get(server_key, "swiggy_")
    original = tool.name
    if not original.startswith(prefix):
        try:
            # Pydantic v2 model fields are mutable on instance assignment.
            tool.name = f"{prefix}{original}"
            tool.original_name = original  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning(f"Could not rename Swiggy tool {original!r}: {e}")
    return tool


async def get_swiggy_tools() -> List:
    """Load Swiggy MCP tools across all enabled servers.

    Loads automatically when `SWIGGY_ACCESS_TOKEN` is set in the environment
    (same model as `GITHUB_TOKEN` for GitHub tools). Returns `[]` and logs
    info when no token is configured, when the package is missing, or when
    the upstream servers are unreachable. Never raises.
    """
    token = _get_token()
    if not token:
        logger.info(
            "SWIGGY_ACCESS_TOKEN not set — Swiggy MCP tools (food ordering + "
            "table booking) will not load. Run the OAuth flow at "
            "https://mcp.swiggy.com/auth/authorize and paste the bearer "
            "token into .env to enable."
        )
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning(
            "langchain-mcp-adapters not installed — Swiggy MCP tools unavailable. "
            "Install with: pip install langchain-mcp-adapters"
        )
        return []

    cfg = _server_config(token)
    if not cfg:
        logger.info("All Swiggy servers disabled via env flags — skipping FOOD tools")
        return []

    try:
        client = MultiServerMCPClient(cfg)
        tools = await client.get_tools()
    except Exception as e:
        # Common failures: 401 (token expired/invalid), network down, MCP handshake failure.
        # Treat all as soft errors — Orion keeps running without FOOD tools.
        logger.warning(
            f"Failed to load Swiggy MCP tools: {type(e).__name__}: {e}. "
            f"FOOD domain will be unavailable. Re-run OAuth if you see 401."
        )
        return []

    # The adapter returns tools un-namespaced; re-prefix per-server. We don't
    # have a clean back-reference from a tool to its source server in older
    # versions, so we re-iterate per server key.
    prefixed: List = []
    for server_key in cfg.keys():
        try:
            server_tools = await client.get_tools(server_name=server_key)
        except TypeError:
            # Older adapter versions don't accept server_name; skip server-scoped reload
            # and prefix everything we already loaded with the first matching server.
            server_tools = tools
            tools = []  # consume once
        for t in server_tools:
            prefixed.append(_prefix_tool(t, server_key))

    if prefixed:
        logger.info(
            f"Swiggy MCP loaded: {len(prefixed)} tools across "
            f"{len(cfg)} server(s) ({', '.join(cfg.keys())})"
        )
    return prefixed


# Static catalogue of expected tool names (prefixed) — used by router for
# pre-classification even when the live MCP client hasn't loaded yet.
# Mirrors the Food + Dineout subset of the v1.0 Swiggy MCP tool list (22 tools).
SWIGGY_FOOD_TOOLS = [
    "swiggy_food_get_addresses",
    "swiggy_food_search_restaurants",
    "swiggy_food_search_menu",
    "swiggy_food_get_restaurant_menu",
    "swiggy_food_update_food_cart",
    "swiggy_food_get_food_cart",
    "swiggy_food_flush_food_cart",
    "swiggy_food_fetch_food_coupons",
    "swiggy_food_apply_food_coupon",
    "swiggy_food_place_food_order",
    "swiggy_food_get_food_orders",
    "swiggy_food_get_food_order_details",
    "swiggy_food_track_food_order",
    "swiggy_food_report_error",
]

SWIGGY_DINEOUT_TOOLS = [
    "swiggy_dineout_get_saved_locations",
    "swiggy_dineout_search_restaurants_dineout",
    "swiggy_dineout_get_restaurant_details",
    "swiggy_dineout_get_available_slots",
    "swiggy_dineout_create_cart",
    "swiggy_dineout_book_table",
    "swiggy_dineout_get_booking_status",
    "swiggy_dineout_report_error",
]

ALL_SWIGGY_TOOL_NAMES = SWIGGY_FOOD_TOOLS + SWIGGY_DINEOUT_TOOLS
