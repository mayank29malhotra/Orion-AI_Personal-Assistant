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

from agents.travel_agent import TravelAgent, get_travel_agent_tools
from agents.base_agent import BaseSubAgent
from agents.router import (
    AgentCategory,
    classify_intent,
    get_agent_for_query,
    list_all_capabilities
)

__all__ = [
    'TravelAgent',
    'BaseSubAgent',
    'AgentCategory',
    'classify_intent',
    'get_agent_for_query',
    'list_all_capabilities',
    'get_travel_agent_tools'
]
