"""
Orion Sub-Agents Module
=======================

This module contains specialized sub-agents that work under the main Orion agent.
Each sub-agent is an expert in its domain and can be invoked by the main agent.

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                      ORION (Main Orchestrator)                   │
│              Routes requests to specialized agents               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
  ┌──────────┬──────────┬───┴───┬──────────┬──────────┬──────────┐
  │          │          │       │          │          │          │
┌─▼──┐   ┌───▼───┐  ┌───▼───┐ ┌─▼──┐   ┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│Travel│  │Comms  │  │Produc │ │Dev │   │Media  │  │Research│ │System │
│Agent │  │Agent  │  │Agent  │ │Agent│  │Agent  │  │Agent   │ │Agent  │
└──────┘  └───────┘  └───────┘ └────┘   └───────┘  └────────┘ └───────┘

Sub-Agents:
- TravelAgent: Flights, trains, hotels, cabs, price comparison
- CommunicationAgent: Email, Telegram, notifications
- ProductivityAgent: Calendar, tasks, notes, reminders
- DeveloperAgent: GitHub, Python REPL, code assistance
- MediaAgent: YouTube, audio transcription, documents
- ResearchAgent: Web search, Wikipedia, dictionary
- SystemAgent: File operations, screenshots, system info
"""

# Base class
from agents.base_agent import BaseSubAgent

# Router
from agents.router import (
    AgentCategory,
    classify_intent,
    get_agent_for_query,
    list_all_capabilities
)

# All Sub-Agents
from agents.travel_agent import TravelAgent, get_travel_agent_tools
from agents.communication_agent import CommunicationAgent, get_communication_agent_tools
from agents.productivity_agent import ProductivityAgent, get_productivity_agent_tools
from agents.developer_agent import DeveloperAgent, get_developer_agent_tools
from agents.media_agent import MediaAgent, get_media_agent_tools
from agents.research_agent import ResearchAgent, get_research_agent_tools
from agents.system_agent import SystemAgent, get_system_agent_tools

__all__ = [
    # Base
    'BaseSubAgent',
    
    # Router
    'AgentCategory',
    'classify_intent',
    'get_agent_for_query',
    'list_all_capabilities',
    
    # Sub-Agents
    'TravelAgent',
    'CommunicationAgent',
    'ProductivityAgent',
    'DeveloperAgent',
    'MediaAgent',
    'ResearchAgent',
    'SystemAgent',
    
    # Tool getters
    'get_travel_agent_tools',
    'get_communication_agent_tools',
    'get_productivity_agent_tools',
    'get_developer_agent_tools',
    'get_media_agent_tools',
    'get_research_agent_tools',
    'get_system_agent_tools',
]


def get_all_agents():
    """Get instances of all sub-agents."""
    return {
        'travel': TravelAgent(),
        'communication': CommunicationAgent(),
        'productivity': ProductivityAgent(),
        'developer': DeveloperAgent(),
        'media': MediaAgent(),
        'research': ResearchAgent(),
        'system': SystemAgent(),
    }


def get_agent_by_category(category: AgentCategory):
    """Get the appropriate agent for a category."""
    agent_map = {
        AgentCategory.TRAVEL: TravelAgent,
        AgentCategory.COMMUNICATION: CommunicationAgent,
        AgentCategory.PRODUCTIVITY: ProductivityAgent,
        AgentCategory.DEVELOPER: DeveloperAgent,
        AgentCategory.MEDIA: MediaAgent,
        AgentCategory.RESEARCH: ResearchAgent,
        AgentCategory.SYSTEM: SystemAgent,
    }
    agent_class = agent_map.get(category)
    return agent_class() if agent_class else None
