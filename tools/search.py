"""
Search & Web Tools for Orion
Web search, Wikipedia, and Python REPL.
"""

import logging
from typing import Optional

from langchain_core.tools.simple import Tool

logger = logging.getLogger("Orion")


# ============ WEB SEARCH ============

def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: Search query
        num_results: Number of results (default 5)
    """
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
        
        if not results:
            return f"🔍 No results found for: {query}"
        
        output = [f"🔍 Search results for: {query}\n"]
        for i, result in enumerate(results, 1):
            output.append(f"{i}. **{result.get('title', 'No title')}**")
            output.append(f"   🔗 {result.get('href', 'No URL')}")
            output.append(f"   {result.get('body', 'No description')[:200]}...")
            output.append("")
        
        logger.info(f"Web search: {query} ({len(results)} results)")
        return "\n".join(output)
    
    except ImportError:
        return "❌ duckduckgo_search not installed. Install with: pip install duckduckgo-search"
    except Exception as e:
        error_msg = f"Web search failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def fetch_webpage(url: str) -> str:
    """
    Fetch and extract text content from a webpage.
    
    Args:
        url: URL of the webpage to fetch
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text
        text = soup.get_text(separator='\n', strip=True)
        
        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = '\n'.join(lines)
        
        if len(text) > 8000:
            text = text[:8000] + "\n\n... (truncated)"
        
        logger.info(f"Webpage fetched: {url}")
        return f"🌐 Content from: {url}\n\n{text}"
    
    except ImportError:
        return "❌ httpx/beautifulsoup4 not installed. Install with: pip install httpx beautifulsoup4"
    except Exception as e:
        error_msg = f"Failed to fetch webpage: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ WIKIPEDIA ============

def wikipedia_search(query: str, sentences: int = 5) -> str:
    """
    Search Wikipedia and get a summary.
    
    Args:
        query: Search query
        sentences: Number of sentences in summary (default 5)
    """
    try:
        import wikipedia
        
        # Search for pages
        search_results = wikipedia.search(query, results=3)
        
        if not search_results:
            return f"📚 No Wikipedia articles found for: {query}"
        
        # Try to get summary
        try:
            summary = wikipedia.summary(search_results[0], sentences=sentences)
            page = wikipedia.page(search_results[0])
            
            result = f"📚 **{page.title}**\n\n{summary}\n\n🔗 {page.url}"
            
            if len(search_results) > 1:
                result += f"\n\n📖 Related: {', '.join(search_results[1:])}"
            
            logger.info(f"Wikipedia search: {query}")
            return result
        
        except wikipedia.DisambiguationError as e:
            options = e.options[:5]
            return f"📚 Multiple results for '{query}':\n" + "\n".join(f"  • {opt}" for opt in options)
    
    except ImportError:
        return "❌ wikipedia not installed. Install with: pip install wikipedia"
    except Exception as e:
        error_msg = f"Wikipedia search failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


# ============ PYTHON REPL ============

def python_repl(code: str) -> str:
    """
    Execute Python code and return the result.
    WARNING: This runs arbitrary code. Use with caution.
    
    Args:
        code: Python code to execute
    """
    import io
    import sys
    import traceback
    
    # Capture stdout
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    
    result = None
    error = None
    
    try:
        # Create execution namespace
        namespace = {
            '__builtins__': __builtins__,
            'datetime': __import__('datetime'),
            'math': __import__('math'),
            'json': __import__('json'),
            're': __import__('re'),
            'os': __import__('os'),
        }
        
        # Try exec first (for statements)
        exec(code, namespace)
        
        # Get stdout
        stdout_val = sys.stdout.getvalue()
        stderr_val = sys.stderr.getvalue()
        
        output_parts = []
        if stdout_val:
            output_parts.append(stdout_val)
        if stderr_val:
            output_parts.append(f"stderr: {stderr_val}")
        
        result = '\n'.join(output_parts) if output_parts else "✅ Code executed successfully (no output)"
        
    except SyntaxError:
        # Try eval for expressions
        try:
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            namespace = {'__builtins__': __builtins__}
            value = eval(code, namespace)
            result = str(value) if value is not None else "✅ Expression evaluated (None)"
        except Exception as e:
            error = f"❌ Error: {traceback.format_exc()}"
    
    except Exception as e:
        error = f"❌ Error: {traceback.format_exc()}"
    
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    
    final_result = error if error else result
    logger.info(f"Python REPL executed: {code[:50]}...")
    
    return final_result


# ============ TOOL EXPORTS ============

def get_search_tools():
    """Get all search-related tools."""
    return [
        Tool(
            name="web_search",
            func=web_search,
            description="Search the web using DuckDuckGo. Args: query, num_results (optional, default 5)"
        ),
        Tool(
            name="fetch_webpage",
            func=fetch_webpage,
            description="Fetch and extract text from a webpage. Args: url"
        ),
        Tool(
            name="wikipedia_search",
            func=wikipedia_search,
            description="Search Wikipedia for information. Args: query, sentences (optional, default 5)"
        ),
    ]


def get_repl_tools():
    """Get Python REPL tool."""
    return [
        Tool(
            name="python_repl",
            func=python_repl,
            description="Execute Python code. Args: code (Python code string). Returns output or error."
        ),
    ]
