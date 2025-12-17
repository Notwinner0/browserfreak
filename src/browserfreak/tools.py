"""
Browser automation tools for BrowserFreak
"""

from typing import Any, Dict, List, Optional, Tuple

from .browser_manager import (
    click_element,
    get_interactive_elements,
    navigate_to_url,
    scroll_page,
    type_text,
)
from .logging_config import log

# Browser context type alias
BrowserContext = Tuple[Any, Any, Optional[Any], Any]


async def click_element_wrapper(context: Optional[BrowserContext], selector: str) -> bool:
    """Click on an element matching the CSS selector"""
    if not context:
        log.debug(f"Mock clicking element: {selector}")
        return True

    try:
        return await click_element(context, selector)
    except Exception as e:
        log.error(f"Failed to click element '{selector}': {e}")
        return False


async def type_text_wrapper(context: Optional[BrowserContext], selector: str, text: str) -> bool:
    """Type text into an element matching the CSS selector"""
    if not context:
        log.debug(f"Mock typing '{text[:50]}' into element: {selector}")
        return True

    try:
        return await type_text(context, selector, text)
    except Exception as e:
        log.error(f"Failed to type text into element '{selector}': {e}")
        return False


async def get_page_state_wrapper(context: Optional[BrowserContext]) -> str:
    """Get the current page state and DOM representation"""
    if not context:
        return "<html><body><button>Submit</button></body></html>"

    try:
        result = await get_interactive_elements(context)
        return result.get("cleaned_html", "<html><body><button>Submit</button></body></html>")
    except Exception as e:
        log.error(f"Failed to get page state: {e}")
        return "<html><body><button>Submit</button></body></html>"


async def scroll_page_wrapper(
    context: Optional[BrowserContext],
    direction: str = "down",
    amount: int = 500,
    element_selector: Optional[str] = None,
    smooth: bool = False,
) -> bool:
    """Scroll the page or a specific element in the specified direction"""
    if not context:
        log.debug(f"Mock scrolling {direction} by {amount} pixels")
        return True

    try:
        return await scroll_page(context, direction, amount, element_selector, smooth)
    except Exception as e:
        log.error(f"Failed to scroll {direction}: {e}")
        return False


async def navigate_to_website_wrapper(context: Optional[BrowserContext], website_name: str) -> bool:
    """Navigate to a website using its name"""
    if not context:
        log.debug(f"Mock navigating to website: {website_name}")
        return True

    try:
        # Basic URL resolution - could be enhanced with AI
        base_url = f"https://www.{website_name.lower().replace(' ', '')}.com"
        await navigate_to_url(context, base_url)
        return True
    except Exception as e:
        log.error(f"Failed to navigate to website '{website_name}': {e}")
        return False


def get_browser_tools() -> List[Dict[str, Any]]:
    """Get the list of available browser automation tools"""
    return [
        {
            "name": "click_element",
            "description": "Click on an element using CSS selector. Use this when you need to interact with buttons, links, or other clickable elements on a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the element to click",
                    }
                },
                "required": ["selector"],
            },
        },
        {
            "name": "type_text",
            "description": "Type text into an input field using CSS selector. Use this when you need to fill out forms or input text into text fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the input element",
                    },
                    "text": {"type": "string", "description": "Text to type into the element"},
                },
                "required": ["selector", "text"],
            },
        },
        {
            "name": "get_page_state",
            "description": "Get current page state and DOM representation. Use this to analyze the current webpage structure and content before deciding on actions.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "scroll_page",
            "description": "Scroll the page or a specific element in the specified direction. Use this when you need to access content that's not currently visible on the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Direction to scroll: 'up', 'down', 'left', or 'right'",
                        "enum": ["up", "down", "left", "right"],
                    },
                    "amount": {
                        "type": "number",
                        "description": "Number of pixels to scroll (positive number)",
                        "default": 500,
                    },
                    "element_selector": {
                        "type": "string",
                        "description": "Optional CSS selector for a specific element to scroll. If not provided, scrolls the main page.",
                    },
                    "smooth": {
                        "type": "boolean",
                        "description": "Whether to use smooth scrolling animation",
                        "default": False,
                    },
                },
                "required": ["direction"],
            },
        },
        {
            "name": "navigate_to_website",
            "description": "Navigate to a website using its name. The AI will use its knowledge to determine the correct URL. Use this when the user mentions a website by name like 'amazon', 'google', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "website_name": {
                        "type": "string",
                        "description": "Name of the website to navigate to (e.g., 'amazon', 'google', 'youtube')",
                    }
                },
                "required": ["website_name"],
            },
        },
    ]


async def execute_tool(
    tool_name: str, tool_args: Dict[str, Any], context: Optional[BrowserContext] = None
) -> Any:
    """
    Execute a tool with the given arguments

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool
        context: Browser context (optional for mock mode)

    Returns:
        Tool execution result
    """
    log.debug(f"Executing tool: {tool_name} with args: {tool_args}")

    try:
        if tool_name == "click_element":
            return await click_element_wrapper(context, **tool_args)
        elif tool_name == "type_text":
            return await type_text_wrapper(context, **tool_args)
        elif tool_name == "get_page_state":
            return await get_page_state_wrapper(context)
        elif tool_name == "scroll_page":
            return await scroll_page_wrapper(context, **tool_args)
        elif tool_name == "navigate_to_website":
            return await navigate_to_website_wrapper(context, **tool_args)
        else:
            log.warning(f"Unknown tool: {tool_name}")
            return False
    except Exception as e:
        log.error(f"Tool execution failed for {tool_name}: {e}")
        return False
