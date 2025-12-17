"""
Custom exceptions for BrowserFreak
"""


class BrowserFreakError(Exception):
    """Base exception for BrowserFreak"""

    pass


class ConfigurationError(BrowserFreakError):
    """Configuration-related errors"""

    pass


class BrowserError(BrowserFreakError):
    """Browser operation errors"""

    pass


class BrowserTimeoutError(BrowserError):
    """Browser operation timeout errors"""

    pass


class ElementNotFoundError(BrowserError):
    """Element not found errors"""

    pass


class AgentError(BrowserFreakError):
    """Agent-related errors"""

    pass


class SecurityError(AgentError):
    """Security violation errors"""

    pass


class APIError(BrowserFreakError):
    """API-related errors"""

    pass


class AnthropicAPIError(APIError):
    """Anthropic API errors"""

    pass


class ValidationError(BrowserFreakError):
    """Input validation errors"""

    pass
