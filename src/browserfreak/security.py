"""
Security module for BrowserFreak - handles destructive action detection and approval
"""

from typing import Any, Dict

from .config import settings


class SecurityManager:
    """Manages security checks for browser automation actions"""

    def __init__(self):
        self._destructive_keywords = [
            "pay",
            "delete",
            "checkout",
            "purchase",
            "buy",
            "submit payment",
            "confirm order",
            "transfer",
            "send money",
            "authorize payment",
            "complete transaction",
            "finalize purchase",
        ]

    def is_destructive_action(self, action_description: str) -> bool:
        """
        Check if an action contains destructive keywords

        Args:
            action_description: Description of the action to check

        Returns:
            True if the action is considered destructive
        """
        if not settings.agent.enable_security_checks:
            return False

        action_lower = action_description.lower()
        return any(keyword in action_lower for keyword in self._destructive_keywords)

    def should_require_approval(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """
        Determine if a tool execution requires human approval

        Args:
            tool_name: Name of the tool being executed
            tool_args: Arguments for the tool

        Returns:
            True if human approval is required
        """
        if not settings.agent.enable_security_checks:
            return False

        # Check tool-specific destructive actions
        if tool_name == "click_element":
            selector = tool_args.get("selector", "").lower()
            # Check for payment-related selectors
            if any(keyword in selector for keyword in ["pay", "checkout", "purchase", "submit"]):
                return True

        elif tool_name == "type_text":
            text = tool_args.get("text", "").lower()
            # Check for sensitive information
            if any(keyword in text for keyword in ["password", "credit", "card", "ssn", "social"]):
                return True

        # Check action description
        action_description = f"{tool_name} {str(tool_args)}"
        return self.is_destructive_action(action_description)

    def get_approval_message(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """
        Generate a human-readable approval message

        Args:
            tool_name: Name of the tool requiring approval
            tool_args: Arguments for the tool

        Returns:
            Approval message for human review
        """
        if tool_name == "click_element":
            selector = tool_args.get("selector", "unknown element")
            return f"Click on element: {selector}"
        elif tool_name == "type_text":
            selector = tool_args.get("selector", "unknown field")
            text_preview = tool_args.get("text", "")[:50]
            return f"Type text into {selector}: '{text_preview}...'"
        elif tool_name == "navigate_to_website":
            website = tool_args.get("website_name", "unknown website")
            return f"Navigate to website: {website}"
        else:
            return f"Execute {tool_name} with args: {tool_args}"


# Global security manager instance
security_manager = SecurityManager()
