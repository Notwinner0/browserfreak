"""
Browser management module for BrowserFreak
"""

import asyncio
import os
from typing import Any, Dict, Optional, Tuple, Union

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .config import settings
from .exceptions import BrowserError, BrowserTimeoutError, ElementNotFoundError
from .logging_config import log


async def create_browser_context(
    user_data_dir: Optional[str] = None,
) -> Tuple[Any, Union[Browser, BrowserContext], Optional[BrowserContext], Page]:
    """
    Create and return a browser context.

    Args:
        user_data_dir: Path to user data directory for persistent storage.
                      If None, creates a new temporary browser context.

    Returns:
        Tuple of (playwright, browser, context, page)

    Raises:
        BrowserError: If browser creation fails
        FileNotFoundError: If user_data_dir doesn't exist
    """
    try:
        log.debug("Starting Playwright...")
        playwright = await async_playwright().start()

        if user_data_dir is None:
            # Create a new temporary browser context
            log.info(
                f"Creating temporary browser context (headless={settings.browser.headless}, channel={settings.browser.channel})"
            )
            browser = await playwright.chromium.launch(
                headless=settings.browser.headless,
                channel=settings.browser.channel,
                slow_mo=settings.browser.slow_mo,
            )

            context = await browser.new_context()
            page = await context.new_page()

            log.info("Browser context created successfully")
            return playwright, browser, context, page
        else:
            # Use the specified user data directory for persistent context
            if not os.path.exists(user_data_dir):
                raise FileNotFoundError(f"User data directory not found at: {user_data_dir}")

            log.info(
                f"Creating persistent browser context at {user_data_dir} (headless={settings.browser.headless}, channel={settings.browser.channel})"
            )
            browser = await playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=settings.browser.headless,
                channel=settings.browser.channel,
                slow_mo=settings.browser.slow_mo,
            )

            page = browser.pages[0]
            log.info("Persistent browser context created successfully")
            return playwright, browser, None, page

    except Exception as e:
        log.error(f"Failed to create browser context: {e}")
        raise BrowserError(f"Browser context creation failed: {e}") from e


async def close_browser_context(
    context: Tuple[Any, Union[Browser, BrowserContext], Optional[BrowserContext], Page],
) -> None:
    """
    Close the browser context and cleanup resources.

    Args:
        context: Tuple from create_browser_context
    """
    try:
        log.debug("Closing browser context...")
        playwright, browser, context_obj, _ = context

        if context_obj:
            await context_obj.close()
            log.debug("Browser context closed")

        await browser.close()
        log.debug("Browser closed")

        await playwright.stop()
        log.info("Browser context cleanup completed")

    except Exception as e:
        log.error(f"Error during browser context cleanup: {e}")
        raise BrowserError(f"Browser cleanup failed: {e}") from e


async def navigate_to_url(
    context: Tuple[Any, Union[Browser, BrowserContext], Optional[BrowserContext], Page], url: str
) -> Page:
    """
    Navigate to the specified URL.

    Args:
        context: Tuple from create_browser_context
        url: URL to navigate to

    Returns:
        The page object after navigation

    Raises:
        BrowserError: If navigation fails
    """
    try:
        log.info(f"Navigating to URL: {url}")
        _, _, _, page = context

        await page.goto(url, timeout=settings.browser.page_load_timeout)
        await page.wait_for_load_state(
            "domcontentloaded", timeout=settings.browser.page_load_timeout
        )

        log.info(f"Successfully navigated to {url}")
        return page

    except Exception as e:
        log.error(f"Navigation to {url} failed: {e}")
        raise BrowserError(f"Navigation failed: {e}") from e


async def click_element(
    context: Tuple[Any, Union[Browser, BrowserContext], Optional[BrowserContext], Page],
    selector: str,
    max_retries: int = 3,
) -> bool:
    """
    Click on an element matching the CSS selector with retry logic.

    Args:
        context: Tuple from create_browser_context
        selector: CSS selector for the element to click
        max_retries: Maximum number of retry attempts

    Returns:
        True if click was successful, False otherwise

    Raises:
        ElementNotFoundError: If element is not found after all retries
        BrowserTimeoutError: If element doesn't become clickable after all retries
        BrowserError: For other browser-related errors
    """
    _, _, _, page = context

    for attempt in range(max_retries):
        try:
            log.debug(
                f"Attempting to click element: {selector} (attempt {attempt + 1}/{max_retries})"
            )

            # Wait for element to be visible and clickable
            await page.wait_for_selector(
                selector, state="visible", timeout=settings.browser.default_timeout
            )

            # Additional check: wait for element to be stable (not moving)
            await page.wait_for_function(
                f"""
                () => {{
                    const el = document.querySelector('{selector}');
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }}
                """,
                timeout=settings.browser.default_timeout,
            )

            await page.click(selector, timeout=settings.browser.default_timeout)

            log.info(f"Successfully clicked element: {selector}")
            return True

        except Exception as e:
            log.warning(f"Click attempt {attempt + 1} failed for '{selector}': {e}")

            if attempt == max_retries - 1:
                # Last attempt failed
                log.error(f"Failed to click element '{selector}' after {max_retries} attempts: {e}")
                if "Timeout" in str(e):
                    raise BrowserTimeoutError(
                        f"Element '{selector}' not clickable within timeout after {max_retries} attempts"
                    ) from e
                elif "not found" in str(e).lower():
                    raise ElementNotFoundError(
                        f"Element '{selector}' not found after {max_retries} attempts"
                    ) from e
                else:
                    raise BrowserError(
                        f"Click failed for element '{selector}' after {max_retries} attempts: {e}"
                    ) from e

            # Wait before retrying (exponential backoff)
            await asyncio.sleep(0.5 * (2**attempt))

    return False


async def type_text(
    context: Tuple[Any, Union[Browser, BrowserContext], Optional[BrowserContext], Page],
    selector: str,
    text: str,
) -> bool:
    """
    Type text into an element matching the CSS selector.

    Args:
        context: Tuple from create_browser_context
        selector: CSS selector for the input element
        text: Text to type into the element

    Returns:
        True if typing was successful, False otherwise

    Raises:
        ElementNotFoundError: If element is not found
        BrowserTimeoutError: If element doesn't become available in time
        BrowserError: For other browser-related errors
    """
    try:
        log.debug(
            f"Typing text into element '{selector}': '{text[:50]}{'...' if len(text) > 50 else ''}'"
        )
        _, _, _, page = context

        # Wait for element to be visible
        await page.wait_for_selector(
            selector, state="visible", timeout=settings.browser.default_timeout
        )
        # Clear existing text and type new text
        await page.fill(selector, text, timeout=settings.browser.default_timeout)

        log.info(f"Successfully typed text into element: {selector}")
        return True

    except Exception as e:
        log.error(f"Failed to type text into element '{selector}': {e}")
        if "Timeout" in str(e):
            raise BrowserTimeoutError(
                f"Element '{selector}' not available for typing within timeout"
            ) from e
        elif "not found" in str(e).lower():
            raise ElementNotFoundError(f"Element '{selector}' not found") from e
        else:
            raise BrowserError(f"Typing failed for element '{selector}': {e}") from e


async def scroll_page(
    context: Tuple[Any, Union[Browser, BrowserContext], Optional[BrowserContext], Page],
    direction: str = "down",
    amount: int = 500,
    element_selector: Optional[str] = None,
    smooth: bool = False,
) -> bool:
    """
    Scroll the page or a specific element in the specified direction.

    Args:
        context: Tuple from create_browser_context
        direction: "up", "down", "left", or "right"
        amount: Pixels to scroll (positive number)
        element_selector: Optional CSS selector for element to scroll (defaults to page)
        smooth: Whether to use smooth scrolling animation

    Returns:
        True if scroll was successful, False otherwise

    Raises:
        BrowserError: If scrolling fails
        ElementNotFoundError: If element_selector is provided but element not found
    """
    try:
        log.debug(
            f"Scrolling {direction} by {amount} pixels{' on element ' + element_selector if element_selector else ''}"
        )
        _, _, _, page = context

        # Validate direction
        valid_directions = ["up", "down", "left", "right"]
        if direction.lower() not in valid_directions:
            raise ValueError(f"Invalid direction '{direction}'. Must be one of: {valid_directions}")

        if element_selector:
            # Scroll a specific element
            await page.wait_for_selector(
                element_selector, state="visible", timeout=settings.browser.default_timeout
            )
            scroll_js = f"""
            (function() {{
                const element = document.querySelector('{element_selector}');
                if (!element) return false;

                const scrollOptions = {{
                    behavior: '{'smooth' if smooth else 'auto'}',
                    {_get_scroll_property(direction)}: {amount}
                }};

                element.scrollBy(scrollOptions);
                return true;
            }})();
            """
        else:
            # Scroll the main page
            scroll_js = f"""
            (function() {{
                const scrollOptions = {{
                    behavior: '{'smooth' if smooth else 'auto'}',
                    {_get_scroll_property(direction)}: {amount}
                }};

                window.scrollBy(scrollOptions);
                return true;
            }})();
            """

        # Execute the scroll JavaScript
        result = await page.evaluate(scroll_js)
        if result:
            log.info(f"Successfully scrolled {direction} by {amount} pixels")
        else:
            log.warning(f"Scroll operation returned false for direction '{direction}'")
        return bool(result)

    except Exception as e:
        log.error(f"Failed to scroll {direction}: {e}")
        if "not found" in str(e).lower():
            raise ElementNotFoundError(
                f"Element '{element_selector}' not found for scrolling"
            ) from e
        else:
            raise BrowserError(f"Scroll failed: {e}") from e


def _get_scroll_property(direction: str) -> str:
    """Helper function to get the correct scroll property name."""
    direction = direction.lower()
    if direction in ["up", "down"]:
        return "top"
    elif direction in ["left", "right"]:
        return "left"
    else:
        return "top"  # default to vertical scrolling


async def get_interactive_elements(
    context: Tuple[Any, Union[Browser, BrowserContext], Optional[BrowserContext], Page],
) -> Dict[str, Any]:
    """
    Get information about interactive elements on the current page.

    This function analyzes the page and returns both interactive element data
    and cleaned HTML content for processing by the agent.

    Args:
        context: Tuple from create_browser_context

    Returns:
        Dictionary with 'interactive_elements' and 'cleaned_html' keys

    Raises:
        BrowserError: If page analysis fails
    """
    try:
        log.debug("Analyzing interactive elements on page")
        _, _, _, page = context

        # Get the current page HTML for BeautifulSoup processing
        html_content = await page.content()

        # Use BeautifulSoup to clean and parse the HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Clean the output by removing scripts, styles, etc.
        for script in soup(["script", "style", "noscript", "meta", "link"]):
            script.decompose()

        cleaned_html = str(soup)

        # Find all interactive elements using BeautifulSoup
        interactive_selectors = [
            "button",
            "input",
            "select",
            "textarea",
            "a[href]",
            "[onclick]",
            '[role="button"]',
            "[tabindex]",
        ]

        elements = []
        for selector in interactive_selectors:
            try:
                found_elements = soup.select(selector)
                elements.extend(found_elements)
            except Exception as e:
                log.warning(f"Failed to select elements with selector '{selector}': {e}")

        # Remove duplicates while preserving order
        seen = set()
        unique_elements = []
        for element in elements:
            element_id = id(element)  # Use object id for uniqueness
            if element_id not in seen:
                seen.add(element_id)
                unique_elements.append(element)

        # Extract element information
        interactive_elements = []
        for index, element in enumerate(unique_elements):
            try:
                # Get element text content
                text = element.get_text(strip=True)
                if not text:
                    text = element.get("value", "") or element.get("placeholder", "")

                # Get element attributes for better identification
                tag_name = element.name
                element_id = element.get("id", "")
                classes = element.get("class", [])
                name = element.get("name", "")

                # Create a more specific selector
                selector_parts = [tag_name]
                if element_id:
                    selector_parts.append(f"#{element_id}")
                elif name:
                    selector_parts.append(f"[name='{name}']")
                elif classes:
                    selector_parts.append(f".{'.'.join(classes)}")

                selector = "".join(selector_parts)

                element_info = {
                    "index": index + 1,
                    "selector": selector,
                    "tag": tag_name,
                    "text": text[:100] if text else "",  # Limit text length
                    "id": element_id,
                    "name": name,
                    "classes": classes,
                    "href": element.get("href", ""),
                    "type": element.get("type", ""),
                    "placeholder": element.get("placeholder", ""),
                }

                interactive_elements.append(element_info)

            except Exception as e:
                log.warning(f"Failed to extract info from element {index}: {e}")
                continue

        log.info(f"Found {len(interactive_elements)} interactive elements on page")
        return {"interactive_elements": interactive_elements, "cleaned_html": cleaned_html}

    except Exception as e:
        log.error(f"Failed to get interactive elements: {e}")
        raise BrowserError(f"Page analysis failed: {e}") from e


# Health check function for production monitoring
async def health_check() -> Dict[str, Any]:
    """
    Perform a health check on the browser automation system.

    Returns:
        Dictionary with health status information
    """
    health_status = {
        "service": "BrowserFreak Browser Manager",
        "status": "healthy",
        "timestamp": None,
        "checks": {},
    }

    try:
        # Check if we can create a browser context
        log.debug("Performing browser manager health check")
        start_time = asyncio.get_event_loop().time()

        context = await create_browser_context()
        health_status["checks"]["browser_creation"] = "pass"

        # Try to navigate to a simple page
        try:
            await navigate_to_url(context, "about:blank")
            health_status["checks"]["navigation"] = "pass"
        except Exception as e:
            health_status["checks"]["navigation"] = f"fail: {str(e)}"

        # Clean up
        await close_browser_context(context)
        health_status["checks"]["browser_cleanup"] = "pass"

        end_time = asyncio.get_event_loop().time()
        health_status["response_time"] = round(end_time - start_time, 2)

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        log.error(f"Health check failed: {e}")

    # Check all individual checks
    all_checks_pass = all(
        status == "pass"
        for status in health_status["checks"].values()
        if isinstance(status, str) and not status.startswith("fail")
    )

    if not all_checks_pass:
        health_status["status"] = "degraded"

    health_status["timestamp"] = asyncio.get_event_loop().time()
    return health_status


# Example usage
async def main():
    """Example usage of the browser manager"""
    # Create a new browser context
    context = await create_browser_context()

    try:
        # Example: Navigate to a website
        await navigate_to_url(context, "https://example.com/")

        # Example: Get interactive elements
        elements = await get_interactive_elements(context)
        log.info(f"Found {len(elements['interactive_elements'])} interactive elements")

        # Keep browser open for inspection
        await asyncio.sleep(5)

    finally:
        # Clean up browser resources
        await close_browser_context(context)


if __name__ == "__main__":
    asyncio.run(main())
