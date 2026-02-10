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
    try:
        from playwright.async_api import async_playwright
        from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
        import os
        
        playwright = await async_playwright().start()
        
        # Container/server-safe browser launch args
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox', 
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--single-process',
        ]
        
        browser = await playwright.chromium.launch(
            headless=True,
            args=browser_args
        )
        toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
        logger.info("Playwright browser tools initialized successfully")
        return toolkit.get_tools(), browser, playwright
    except ImportError as e:
        logger.warning(f"Browser tools not available (missing dependency): {e}")
        return [], None, None
    except Exception as e:
        logger.error(f"Failed to initialize Playwright tools: {e}")
        return [], None, None
