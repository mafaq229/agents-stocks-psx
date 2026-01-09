"""Model-agnostic LLM client with tool calling support.

Provides a unified interface for OpenAI and Anthropic APIs.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Literal

from psx.core.config import get_config, LLMProvider


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class Tool:
    """Tool definition for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    function: Callable[..., Any]

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class LLMClient:
    """Model-agnostic LLM client supporting OpenAI and Anthropic."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ):
        config = get_config()
        self.provider = provider or config.llm.provider
        self.model = model or config.llm.model
        self.api_key = api_key or config.get_api_key(self.provider)
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Lazy-load clients
        self._openai_client: Any = None
        self._anthropic_client: Any = None

    def _get_openai_client(self) -> Any:
        """Get or create OpenAI client."""
        if self._openai_client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "OpenAI package not installed. Run: uv add openai"
                )
            self._openai_client = OpenAI(api_key=self.api_key)
        return self._openai_client

    def _get_anthropic_client(self) -> Any:
        """Get or create Anthropic client."""
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "Anthropic package not installed. Run: uv add anthropic"
                )
            self._anthropic_client = Anthropic(api_key=self.api_key)
        return self._anthropic_client

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[Tool]] = None,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of Tool objects for function calling
            system: Optional system prompt (will be prepended to messages for OpenAI)

        Returns:
            LLMResponse with content and any tool calls
        """
        if self.provider == "openai":
            return self._chat_openai(messages, tools, system)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, tools, system)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[Tool]] = None,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """OpenAI chat completion."""
        client = self._get_openai_client()

        # Starting with system prompt
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        # Build request
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": all_messages,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_tokens,
        }
        # TODO: investigate other args
        if tools:
            kwargs["tools"] = [t.to_openai_format() for t in tools]
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        # Parse tool calls
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )

    def _chat_anthropic(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[Tool]] = None,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """Anthropic chat completion."""
        client = self._get_anthropic_client()

        # Build request
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages_for_anthropic(messages),
            "max_tokens": self.max_tokens,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = [t.to_anthropic_format() for t in tools]

        response = client.messages.create(**kwargs)

        # Parse response
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "stop",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
        )

    def _convert_messages_for_anthropic(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert messages to Anthropic format, handling tool results."""
        converted = []

        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            # TODO: investigate how?
            # Skip system messages (handled separately in Anthropic)
            if role == "system":
                continue

            # Handle tool results
            if role == "tool":
                # Anthropic expects tool_result as a content block
                tool_call_id = msg.get("tool_call_id", "")
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": content,
                        }
                    ],
                })
            elif role == "assistant" and "tool_calls" in msg:
                # Convert assistant message with tool calls
                content_blocks = []
                if content:
                    content_blocks.append({"type": "text", "text": content})

                for tc in msg["tool_calls"]:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    })

                converted.append({"role": "assistant", "content": content_blocks})
            else:
                converted.append({"role": role, "content": content})

        return converted

    def format_tool_result_message(
        self, tool_call_id: str, result: str
    ) -> dict[str, Any]:
        """Format a tool result message for the conversation."""
        if self.provider == "openai":
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
        else:  # anthropic
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }

    def format_assistant_message_with_tool_calls(
        self, content: str, tool_calls: list[ToolCall]
    ) -> dict[str, Any]:
        """Format an assistant message that includes tool calls."""
        if self.provider == "openai":
            # OpenAI requires type: "function" and function wrapper with stringified arguments
            return {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in tool_calls
                ],
            }
        else:
            # Anthropic format (converted in _convert_messages_for_anthropic)
            return {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in tool_calls
                ],
            }
