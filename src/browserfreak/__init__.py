"""
BrowserFreak - AI-powered browser automation framework

This package provides browser automation capabilities with AI-powered decision making
using Anthropic's Claude models.
"""

from .anthropic_client import anthropic_client
from .browser_agent import AgentState, is_destructive_action, run_agent_workflow
from .browser_manager import (
    click_element,
    close_browser_context,
    create_browser_context,
    get_interactive_elements,
    health_check,
    navigate_to_url,
    scroll_page,
    type_text,
)
from .config import settings
from .decision_engine import decision_engine
from .exceptions import (
    AgentError,
    AnthropicAPIError,
    APIError,
    BrowserError,
    BrowserFreakError,
    BrowserTimeoutError,
    ConfigurationError,
    ElementNotFoundError,
    SecurityError,
    ValidationError,
)
from .logging_config import log
from .security import security_manager
from .tools import get_browser_tools

__version__ = "1.0.0"
__author__ = "BrowserFreak Team"
__all__ = [
    # Core functionality
    "run_agent_workflow",
    "is_destructive_action",
    "AgentState",
    # Configuration and logging
    "settings",
    "log",
    # Exceptions
    "BrowserFreakError",
    "ConfigurationError",
    "BrowserError",
    "BrowserTimeoutError",
    "ElementNotFoundError",
    "AgentError",
    "SecurityError",
    "APIError",
    "AnthropicAPIError",
    "ValidationError",
    # Browser management
    "create_browser_context",
    "close_browser_context",
    "navigate_to_url",
    "click_element",
    "type_text",
    "scroll_page",
    "get_interactive_elements",
    "health_check",
    # Advanced components
    "anthropic_client",
    "decision_engine",
    "security_manager",
    "get_browser_tools",
]
