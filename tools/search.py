"""
Search & Web Tools for Orion
Web search, Wikipedia, and Python REPL.
"""

import os
import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger("Orion")

# Check for Serper API key
SERPER_API_KEY = os.getenv("SERPER_API_KEY")


# ============ WEB SEARCH ============

@tool
def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web for information using Google via Serper API.
    
    Args:
        query: Search query
        num_results: Number of results (default 5)
    """
    if not SERPER_API_KEY:
        return "❌ SERPER_API_KEY not configured. Please set it in your environment variables."
    
    try:
        import httpx
        
        response = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num_results},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        results = data.get("organic", [])
        if not results:
            return f"🔍 No results found for: {query}. Try using browser_search for more comprehensive results."
        
        output = [f"🔍 Google search results for: {query}\n"]
        for i, result in enumerate(results[:num_results], 1):
            output.append(f"{i}. **{result.get('title', 'No title')}**")
            output.append(f"   🔗 {result.get('link', 'No URL')}")
            output.append(f"   {result.get('snippet', 'No description')[:200]}")
            output.append("")
        
        logger.info(f"Google search (Serper): {query} ({len(results)} results)")
        return "\n".join(output)
        
    except Exception as e:
        error_msg = f"Web search failed: {str(e)}. Try using browser_search for a fallback."
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
def browser_search(query: str) -> str:
    """
    Search the web using a real browser (Playwright). Use this as fallback when web_search fails,
    or when you need to access dynamic content that requires JavaScript.
    
    Args:
        query: Search query
    """
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Use Google search
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            page.goto(search_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            
            # Extract search results
            results = []
            search_results = page.query_selector_all("div.g")[:5]
            
            for result in search_results:
                try:
                    title_el = result.query_selector("h3")
                    link_el = result.query_selector("a")
                    snippet_el = result.query_selector("div[data-sncf]") or result.query_selector("span")
                    
                    title = title_el.inner_text() if title_el else "No title"
                    link = link_el.get_attribute("href") if link_el else "No URL"
                    snippet = snippet_el.inner_text()[:200] if snippet_el else "No description"
                    
                    results.append({"title": title, "link": link, "snippet": snippet})
                except:
                    continue
            
            browser.close()
            
            if not results:
                return f"🔍 No results found for: {query}"
            
            output = [f"🌐 Browser search results for: {query}\n"]
            for i, result in enumerate(results, 1):
                output.append(f"{i}. **{result['title']}**")
                output.append(f"   🔗 {result['link']}")
                output.append(f"   {result['snippet']}")
                output.append("")
            
            logger.info(f"Browser search: {query} ({len(results)} results)")
            return "\n".join(output)
            
    except Exception as e:
        error_msg = f"Browser search failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


@tool
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

@tool
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

@tool
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
        web_search,
        browser_search,
        fetch_webpage,
        wikipedia_search,
    ]


def get_repl_tools():
    """Get Python REPL tool."""
    return [
        python_repl,
    ]
