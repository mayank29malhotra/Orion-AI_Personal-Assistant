"""
Base Sub-Agent Class
====================

All sub-agents inherit from this base class.
Provides common functionality for LLM interaction and tool execution.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from core.utils import Logger

logger = Logger().logger


class BaseSubAgent(ABC):
    """Base class for all Orion sub-agents"""
    
    def __init__(self, name: str, description: str, tools: List[BaseTool] = None):
        self.name = name
        self.description = description
        self.tools = tools or []
        
        # Initialize LLM
        self.llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.3,
            max_tokens=4096
        )
        
        # Bind tools if available
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = self.llm
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this sub-agent"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of capabilities this agent has"""
        pass
    
    async def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        """
        Execute a query using this sub-agent.
        
        Args:
            query: The user's request
            context: Optional context (previous messages, user preferences, etc.)
            
        Returns:
            The agent's response
        """
        messages = [
            SystemMessage(content=self.get_system_prompt()),
            HumanMessage(content=query)
        ]
        
        try:
            # First call - may return tool calls
            response = self.llm_with_tools.invoke(messages)
            
            # If there are tool calls, execute them
            if hasattr(response, 'tool_calls') and response.tool_calls:
                messages.append(response)
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    
                    # Find and execute the tool
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if tool:
                        try:
                            result = tool.invoke(tool_args)
                            from langchain_core.messages import ToolMessage
                            messages.append(ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call['id']
                            ))
                        except Exception as e:
                            from langchain_core.messages import ToolMessage
                            messages.append(ToolMessage(
                                content=f"Error: {str(e)}",
                                tool_call_id=tool_call['id']
                            ))
                
                # Get final response
                response = self.llm_with_tools.invoke(messages)
            
            return response.content
            
        except Exception as e:
            logger.error(f"Sub-agent {self.name} error: {e}")
            return f"Error in {self.name}: {str(e)}"
    
    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"
