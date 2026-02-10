"""
Browser Automation Tools for Orion
Provides web browsing and automation capabilities using Playwright.
"""

import logging

logger = logging.getLogger("Orion")


async def get_browser_tools():
    """
    Initialize Playwright browser toolkit.
    Returns: (tools_list, browser_instance, playwright_instance)
    """
    import asyncio
    
    async def init_browser():
        from playwright.async_api import async_playwright
        from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
        
        playwright = await async_playwright().start()
        
        # Container/server-safe browser launch args (memory optimized)
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox', 
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--single-process',
            '--no-zygote',
            '--disable-extensions',
            '--disable-background-networking',
            '--disable-sync',
            '--disable-translate',
            '--metrics-recording-only',
            '--no-first-run',
        ]
        
        browser = await playwright.chromium.launch(
            headless=True,
            args=browser_args
        )
        toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
        return toolkit.get_tools(), browser, playwright
    
    try:
        # Timeout after 8 seconds to prevent blocking
        tools, browser, playwright = await asyncio.wait_for(init_browser(), timeout=8.0)
        logger.info("Playwright browser tools initialized successfully")
        return tools, browser, playwright
    except asyncio.TimeoutError:
        logger.warning("Browser tools initialization timed out - skipping")
        return [], None, None
    except ImportError as e:
        logger.warning(f"Browser tools not available (missing dependency): {e}")
        return [], None, None
    except Exception as e:
        logger.warning(f"Browser tools failed to initialize: {e}")
        return [], None, None
