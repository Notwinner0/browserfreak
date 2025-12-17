"""
Decision engine for BrowserFreak - handles AI and fallback decision making
"""

import re
from typing import Any, Dict, List

from .anthropic_client import anthropic_client
from .exceptions import ValidationError
from .logging_config import log
from .tools import get_browser_tools


class DecisionEngine:
    """Handles decision making for browser automation tasks"""

    def __init__(self):
        self._tools = get_browser_tools()
        self._patterns = self._initialize_patterns()

    def _initialize_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize regex patterns for fallback decision making"""
        return {
            "submit_click": re.compile(
                r"\b(click|press|tap).*\b(submit|send|confirm)\b", re.IGNORECASE
            ),
            "payment_action": re.compile(
                r"\b(pay|purchase|buy|checkout|complete.*order)\b", re.IGNORECASE
            ),
            "text_input": re.compile(
                r"\b(type|enter|fill.*in|input|write)\b.*\b(text|information|data)\b", re.IGNORECASE
            ),
            "finish_task": re.compile(r"\b(finish|complete|done|end|stop)\b", re.IGNORECASE),
            "navigate_action": re.compile(
                r"\b(navigate|go.*to|open|visit)\b.*\b(page|url|link|website)\b", re.IGNORECASE
            ),
            "search_action": re.compile(r"\b(search|find|look.*for)\b", re.IGNORECASE),
            "scroll_action": re.compile(
                r"\b(scroll|move.*down|move.*up|go.*down|go.*up|page.*down|page.*up)\b",
                re.IGNORECASE,
            ),
            "website_mention": re.compile(
                r"\b(amazon|google|youtube|facebook|twitter|netflix|ebay|reddit|linkedin|instagram|wikipedia|github|stackoverflow|microsoft|apple)\b",
                re.IGNORECASE,
            ),
        }

    def _validate_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Validate message structure"""
        if not messages:
            raise ValidationError("Messages list cannot be empty")

        if not isinstance(messages, list):
            raise ValidationError("Messages must be a list")

        if len(messages) == 0:
            raise ValidationError("At least one message is required")

        last_message = messages[-1]
        if not isinstance(last_message, dict) or "content" not in last_message:
            raise ValidationError("Last message must be a dict with 'content' key")

        if not isinstance(last_message["content"], str):
            raise ValidationError("Message content must be a string")

        content = last_message["content"].strip()
        if not content:
            raise ValidationError("Empty message received. Please provide a valid instruction.")

    async def make_decision(
        self, messages: List[Dict[str, Any]], page_context: str
    ) -> Dict[str, Any]:
        """
        Make a decision using AI or fallback logic

        Args:
            messages: Conversation history
            page_context: Current page context

        Returns:
            Decision result with tool_calls or content
        """
        # Validate input
        self._validate_messages(messages)

        # Try AI decision first
        if anthropic_client.is_available:
            try:
                log.debug("Using Anthropic API for decision making")
                return await anthropic_client.make_decision(messages, page_context, self._tools)
            except Exception as e:
                log.warning(
                    f"Anthropic API failed, falling back to functional decision making: {e}"
                )

        # Fallback to functional decision making
        log.debug("Using fallback functional decision making")
        return await self._make_fallback_decision(messages, page_context)

    async def _make_fallback_decision(
        self, messages: List[Dict[str, Any]], page_context: str
    ) -> Dict[str, Any]:
        """Fallback functional decision making when AI is not available"""
        last_message = messages[-1]
        content = last_message["content"].strip().lower()

        # Get original user message for website detection
        original_user_message = None
        for message in messages:
            if message.get("role") == "user":
                original_user_message = message["content"].strip()
                break

        # Analyze page context
        page_has_forms = "form" in page_context.lower() if page_context else False
        page_has_inputs = "input" in page_context.lower() if page_context else False
        page_has_buttons = "button" in page_context.lower() if page_context else False

        log.debug(
            f"Page analysis - Forms: {page_has_forms}, Inputs: {page_has_inputs}, Buttons: {page_has_buttons}"
        )

        # Check for website mentions in original message
        if original_user_message:
            website_match = self._patterns["website_mention"].search(original_user_message)
            if website_match:
                website_name = website_match.group(0)
                log.debug(f"Detected website mention: {website_name}")
                return {
                    "tool_calls": [
                        {"name": "navigate_to_website", "args": {"website_name": website_name}}
                    ]
                }

        # Pattern-based decision making
        if self._patterns["finish_task"].search(content):
            log.debug("Detected completion request")
            return {"content": "FINISH"}

        elif self._patterns["submit_click"].search(content):
            log.debug("Detected submit click request")
            selector = "button[type='submit']" if page_has_forms else "button"
            return {"tool_calls": [{"name": "click_element", "args": {"selector": selector}}]}

        elif self._patterns["payment_action"].search(content):
            log.debug("Detected payment action request")
            selector = "button.pay-now, button.checkout, button#purchase"
            return {"tool_calls": [{"name": "click_element", "args": {"selector": selector}}]}

        elif self._patterns["text_input"].search(content):
            log.debug("Detected text input request")
            text_to_input = "test data"

            # Extract text from message
            text_match = re.search(
                r'(type|enter|fill).*["\']?(.*?)["\']?.*(into|in)', content, re.IGNORECASE
            )
            if text_match and len(text_match.groups()) > 1:
                text_to_input = text_match.group(2) or "test data"

            selector = (
                "input[type='text'], input:not([type]), textarea" if page_has_inputs else "input"
            )
            return {
                "tool_calls": [
                    {"name": "type_text", "args": {"selector": selector, "text": text_to_input}}
                ]
            }

        elif self._patterns["scroll_action"].search(content):
            log.debug("Detected scroll action request")
            direction = "down"
            amount = 500

            if "up" in content:
                direction = "up"
            elif "down" in content:
                direction = "down"
            elif "left" in content:
                direction = "left"
            elif "right" in content:
                direction = "right"

            # Extract amount
            amount_match = re.search(r"\b(\d+)\s*(pixels?|px)\b", content, re.IGNORECASE)
            if amount_match:
                amount = int(amount_match.group(1))

            return {
                "tool_calls": [
                    {"name": "scroll_page", "args": {"direction": direction, "amount": amount}}
                ]
            }

        elif self._patterns["navigate_action"].search(content) or self._patterns[
            "search_action"
        ].search(content):
            log.debug("Detected navigation/search request - suggesting page analysis first")
            return {"tool_calls": [{"name": "get_page_state", "args": {}}]}

        elif self._patterns["website_mention"].search(content):
            website_match = self._patterns["website_mention"].search(content)
            if website_match:
                website_name = website_match.group(0)
                log.debug(f"Detected website mention: {website_name}")
                return {
                    "tool_calls": [
                        {"name": "navigate_to_website", "args": {"website_name": website_name}}
                    ]
                }

        # Check original content for website mentions
        original_content = last_message["content"].strip()
        website_match = self._patterns["website_mention"].search(original_content)
        if website_match:
            website_name = website_match.group(0)
            log.debug(f"Detected website mention in original content: {website_name}")
            return {
                "tool_calls": [
                    {"name": "navigate_to_website", "args": {"website_name": website_name}}
                ]
            }

        # For unrecognized tasks, provide a helpful response and suggest finishing
        # This prevents infinite loops in the workflow
        response = "I understand your request, but I need more specific instructions to complete this task."

        suggestions = []
        if page_has_forms:
            suggestions.append("I see forms on this page")
        if page_has_inputs:
            suggestions.append("there are input fields available")
        if page_has_buttons:
            suggestions.append("clickable buttons are present")

        if suggestions:
            response += " " + ", ".join(suggestions) + "."

        response += (
            " Please provide more specific instructions or say 'finish' to complete the task."
        )

        log.debug(f"Default response: {response}")
        return {"content": response}


# Global decision engine instance
decision_engine = DecisionEngine()
