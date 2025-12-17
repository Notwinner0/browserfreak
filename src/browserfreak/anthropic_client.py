"""
Anthropic API client wrapper for BrowserFreak
"""

import asyncio
from typing import Any, Dict, List, Optional, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .config import settings
from .exceptions import AnthropicAPIError, ConfigurationError
from .logging_config import log


class AnthropicClient:
    """Wrapper for Anthropic API interactions"""

    def __init__(self):
        self._client: Optional[ChatAnthropic] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Anthropic client with proper error handling"""
        try:
            if not settings.anthropic.is_available or settings.anthropic.api_key is None:
                log.warning("Anthropic API key not configured - using fallback mode")
                return

            self._client = ChatAnthropic(
                model_name=settings.anthropic.model,
                temperature=settings.anthropic.temperature,
                api_key=settings.anthropic.api_key,
                timeout=None,
                stop=None,
            )
            log.info(f"Anthropic client initialized with model: {settings.anthropic.model}")

        except Exception as e:
            log.error(f"Failed to initialize Anthropic client: {e}")
            self._client = None
            raise ConfigurationError(f"Anthropic client initialization failed: {e}") from e

    @property
    def is_available(self) -> bool:
        """Check if the Anthropic client is properly configured"""
        return self._client is not None

    def _convert_messages_to_langchain(self, messages: List[Dict[str, Any]]) -> List[Any]:
        """Convert internal message format to LangChain format"""
        langchain_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                if "tool_calls" in msg:
                    # Tool call message
                    additional_kwargs = {"tool_calls": msg["tool_calls"]}
                    langchain_messages.append(
                        AIMessage(content="", additional_kwargs=additional_kwargs)
                    )
                else:
                    langchain_messages.append(AIMessage(content=content))
            elif role == "tool":
                tool_call_id = msg.get("tool_call_id", "1")
                langchain_messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))

        return langchain_messages

    async def make_decision(
        self, messages: List[Dict[str, Any]], page_context: str, tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Make a decision using Anthropic API

        Args:
            messages: Conversation history
            page_context: Current page context
            tools: Available tools

        Returns:
            Decision result with tool_calls or content
        """
        if not self.is_available:
            raise AnthropicAPIError("Anthropic client not available")

        try:
            # Convert messages to LangChain format
            langchain_messages = self._convert_messages_to_langchain(messages)

            # Create system prompt
            system_prompt = f"""You are a browser automation assistant. Your task is to help users interact with web pages.

Current page context:
{page_context[:2000] if page_context else 'No page context available'}

Instructions:
1. Analyze the user's request and current page context
2. Use available tools to complete tasks
3. For destructive actions, be cautious
4. Respond with 'FINISH' when the task is complete

Available tools will be provided separately."""

            # Create prompt template
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )

            # Bind tools to the model
            tool_llm = cast(ChatAnthropic, self._client).bind_tools(tools)

            # Create the chain
            chain = prompt | tool_llm

            # Make the API call
            log.debug("Making Anthropic API call")
            response = await asyncio.get_event_loop().run_in_executor(
                None, chain.invoke, {"messages": langchain_messages}
            )

            # Process response
            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_calls = []
                for tool_call in response.tool_calls:
                    tool_calls.append({"name": tool_call["name"], "args": tool_call["args"]})
                return {"tool_calls": tool_calls}
            else:
                content = str(getattr(response, "content", ""))
                if "FINISH" in content.upper():
                    return {"content": "FINISH"}
                return {"content": content}

        except Exception as e:
            log.error(f"Anthropic API call failed: {e}")
            raise AnthropicAPIError(f"API call failed: {e}") from e


# Global client instance
anthropic_client = AnthropicClient()
