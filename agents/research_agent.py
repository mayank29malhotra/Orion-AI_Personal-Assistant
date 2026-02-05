"""
Research Agent for Orion
========================

Specialized sub-agent for web search, Wikipedia, and dictionary operations.

Capabilities:
- Web search (Google via Serper API)
- Wikipedia search
- Word definitions
- Synonyms and antonyms
- Word translation
"""

from typing import List, Optional
from langchain_core.tools import tool, BaseTool

from agents.base_agent import BaseSubAgent


class ResearchAgent(BaseSubAgent):
    """
    Research Agent - handles web search, Wikipedia, and dictionary tasks.
    
    This agent specializes in:
    - Web search via Google (Serper API)
    - Browser-based search fallback
    - Wikipedia article search
    - Word definitions and pronunciation
    - Synonyms, antonyms, translations
    """
    
    def __init__(self, tools: Optional[List[BaseTool]] = None):
        if tools is None:
            tools = get_research_agent_tools()
        super().__init__(tools)
    
    def get_system_prompt(self) -> str:
        return """You are the Research Agent, a specialized sub-agent of Orion AI.
Your expertise is in finding information from the web, Wikipedia, and dictionaries.

🎯 YOUR CAPABILITIES:

🔍 WEB SEARCH:
- Search Google via Serper API
- Browser-based search fallback
- Get latest news and information
- Find specific websites and resources

📚 WIKIPEDIA:
- Search Wikipedia articles
- Get article summaries
- Find related topics

📖 DICTIONARY:
- Word definitions with examples
- Pronunciation guides
- Part of speech information
- Etymology when available

🔤 LANGUAGE TOOLS:
- Find synonyms
- Find antonyms
- Word translations
- Language detection

💡 SEARCH STRATEGIES:
- Use specific keywords for better results
- Quote exact phrases for precise matches
- Add "site:" prefix to search specific websites
- Use "define:" for quick definitions
- Add year for time-sensitive queries

🔧 AVAILABLE TOOLS:
- web_search: Search Google via Serper
- browser_search: Browser-based search (fallback)
- wikipedia_search: Search Wikipedia
- fetch_webpage: Get webpage content
- define_word: Get word definition
- get_synonyms: Find synonyms
- get_antonyms: Find antonyms
- translate_word: Translate words

⚠️ BEST PRACTICES:
- Cite sources when providing information
- Indicate if information might be outdated
- Cross-reference multiple sources when possible
- Clearly state when information is uncertain
"""

    def get_capabilities(self) -> List[str]:
        return [
            "Web search via Google (Serper API)",
            "Browser-based search fallback",
            "Wikipedia article search",
            "Fetch and parse webpage content",
            "Word definitions with examples",
            "Find synonyms",
            "Find antonyms",
            "Word translations",
            "News search",
            "Fact-checking"
        ]


def get_research_agent_tools() -> List[BaseTool]:
    """Get all tools for the Research Agent."""
    tools = []
    
    # Search tools
    try:
        from tools.search import (
            web_search,
            browser_search,
            wikipedia_search,
            fetch_webpage
        )
        tools.extend([
            web_search,
            browser_search,
            wikipedia_search,
            fetch_webpage,
        ])
    except ImportError:
        pass
    
    # Dictionary tools
    try:
        from tools.dictionary import (
            define_word,
            get_synonyms,
            get_antonyms,
            translate_word
        )
        tools.extend([
            define_word,
            get_synonyms,
            get_antonyms,
            translate_word,
        ])
    except ImportError:
        pass
    
    return tools


# Additional research tools
@tool
def quick_fact_check(claim: str) -> str:
    """
    Quick fact-check a claim by searching multiple sources.
    
    Args:
        claim: The claim or statement to fact-check
        
    Returns:
        Summary of findings from multiple sources
    """
    from tools.search import web_search, wikipedia_search
    
    results = []
    
    # Search Google
    try:
        google_results = web_search.invoke({
            "query": f"is it true that {claim}",
            "num_results": 3
        })
        results.append(f"🔍 **Google Results:**\n{google_results}")
    except:
        results.append("🔍 Google search unavailable")
    
    # Search Wikipedia
    try:
        # Extract key terms for Wikipedia
        wiki_results = wikipedia_search.invoke({
            "query": claim[:50]  # First 50 chars as search term
        })
        results.append(f"\n📚 **Wikipedia:**\n{wiki_results}")
    except:
        results.append("📚 Wikipedia search unavailable")
    
    return f"""
🔎 FACT CHECK: {claim}
══════════════════════════════════════════

{chr(10).join(results)}

══════════════════════════════════════════
⚠️ Note: This is an automated search, not a formal fact-check.
   Please verify important claims with authoritative sources.
"""


@tool
def get_word_details(word: str) -> str:
    """
    Get comprehensive details about a word (definition, synonyms, antonyms).
    
    Args:
        word: The word to look up
        
    Returns:
        Complete word information
    """
    from tools.dictionary import define_word, get_synonyms, get_antonyms
    
    # Get definition
    definition = define_word.invoke({"word": word})
    
    # Get synonyms
    synonyms = get_synonyms.invoke({"word": word})
    
    # Get antonyms
    antonyms = get_antonyms.invoke({"word": word})
    
    return f"""
📖 WORD DETAILS: {word.upper()}
══════════════════════════════════════════

{definition}

══════════════════════════════════════════

✅ SYNONYMS:
{synonyms}

❌ ANTONYMS:
{antonyms}

══════════════════════════════════════════
"""


@tool
def research_topic(topic: str, depth: str = "summary") -> str:
    """
    Research a topic comprehensively using multiple sources.
    
    Args:
        topic: The topic to research
        depth: Research depth - "quick", "summary", or "detailed"
        
    Returns:
        Research findings from multiple sources
    """
    from tools.search import web_search, wikipedia_search
    
    results = []
    
    # Wikipedia first for foundational info
    try:
        wiki = wikipedia_search.invoke({"query": topic})
        results.append(f"📚 **Wikipedia Summary:**\n{wiki}\n")
    except:
        pass
    
    if depth in ["summary", "detailed"]:
        # Recent news/updates
        try:
            news = web_search.invoke({
                "query": f"{topic} latest news 2024 2025",
                "num_results": 3
            })
            results.append(f"📰 **Recent Updates:**\n{news}\n")
        except:
            pass
    
    if depth == "detailed":
        # Expert opinions
        try:
            expert = web_search.invoke({
                "query": f"{topic} expert analysis research",
                "num_results": 3
            })
            results.append(f"🎓 **Expert Analysis:**\n{expert}\n")
        except:
            pass
    
    depth_emoji = {"quick": "⚡", "summary": "📋", "detailed": "🔬"}
    
    return f"""
🔬 RESEARCH: {topic}
══════════════════════════════════════════
{depth_emoji.get(depth, "📋")} Depth: {depth.title()}

{chr(10).join(results)}

══════════════════════════════════════════
💡 Need more details? Ask for a deeper research!
"""


@tool
def compare_topics(topic1: str, topic2: str) -> str:
    """
    Compare two topics/concepts by searching for their differences.
    
    Args:
        topic1: First topic
        topic2: Second topic
        
    Returns:
        Comparison information
    """
    from tools.search import web_search
    
    # Search for comparison
    comparison = web_search.invoke({
        "query": f"{topic1} vs {topic2} difference comparison",
        "num_results": 5
    })
    
    return f"""
⚖️ COMPARISON: {topic1} vs {topic2}
══════════════════════════════════════════

🔍 Search Results:
{comparison}

══════════════════════════════════════════
💡 Ask follow-up questions for specific aspects!
"""


if __name__ == "__main__":
    # Test the agent
    agent = ResearchAgent()
    print("Research Agent initialized")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print(f"\nCapabilities:\n" + "\n".join(f"  • {c}" for c in agent.get_capabilities()))
