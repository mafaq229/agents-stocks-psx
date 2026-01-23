"""Tests for LLM client."""

import pytest
import json
from unittest.mock import patch, MagicMock

from psx.agents.llm import ToolCall, LLMResponse, Tool, LLMClient


class TestToolCall:
    """Test ToolCall dataclass."""

    def test_instantiation(self):
        """Test creating tool call."""
        tc = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"city": "Karachi", "unit": "celsius"},
        )
        assert tc.id == "call_123"
        assert tc.name == "get_weather"
        assert tc.arguments["city"] == "Karachi"


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_instantiation_basic(self):
        """Test creating basic response."""
        response = LLMResponse(content="Hello, world!")
        assert response.content == "Hello, world!"
        assert response.tool_calls == []
        assert response.finish_reason == "stop"

    def test_instantiation_with_tool_calls(self):
        """Test response with tool calls."""
        response = LLMResponse(
            content="",
            tool_calls=[
                ToolCall(id="1", name="func1", arguments={}),
                ToolCall(id="2", name="func2", arguments={}),
            ],
            finish_reason="tool_calls",
        )
        assert len(response.tool_calls) == 2
        assert response.finish_reason == "tool_calls"

    def test_has_tool_calls_true(self):
        """Test has_tool_calls property when tool calls present."""
        response = LLMResponse(
            content="",
            tool_calls=[ToolCall(id="1", name="func", arguments={})],
        )
        assert response.has_tool_calls is True

    def test_has_tool_calls_false(self):
        """Test has_tool_calls property when no tool calls."""
        response = LLMResponse(content="No tools")
        assert response.has_tool_calls is False

    def test_usage_tracking(self):
        """Test usage tracking."""
        response = LLMResponse(
            content="Test",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
        assert response.usage["prompt_tokens"] == 100
        assert response.usage["completion_tokens"] == 50


class TestTool:
    """Test Tool dataclass."""

    def test_instantiation(self):
        """Test creating tool definition."""
        tool = Tool(
            name="get_weather",
            description="Get weather for a city",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
            },
            function=lambda city: f"Weather in {city}",
        )
        assert tool.name == "get_weather"
        assert tool.description == "Get weather for a city"

    def test_to_openai_format(self):
        """Test conversion to OpenAI format."""
        tool = Tool(
            name="calculator",
            description="Perform calculations",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
            },
            function=lambda x: x,
        )
        openai_format = tool.to_openai_format()

        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "calculator"
        assert openai_format["function"]["description"] == "Perform calculations"
        assert "parameters" in openai_format["function"]

    def test_to_anthropic_format(self):
        """Test conversion to Anthropic format."""
        tool = Tool(
            name="calculator",
            description="Perform calculations",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
            },
            function=lambda x: x,
        )
        anthropic_format = tool.to_anthropic_format()

        assert anthropic_format["name"] == "calculator"
        assert anthropic_format["description"] == "Perform calculations"
        assert "input_schema" in anthropic_format


class TestLLMClient:
    """Test LLMClient class."""

    def test_init_from_config(self):
        """Test initialization from config."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "openai"
            mock_config.return_value.llm.model = "gpt-4"
            mock_config.return_value.get_api_key.return_value = "test-key"

            client = LLMClient()

            assert client.provider == "openai"
            assert client.model == "gpt-4"

    def test_init_with_overrides(self):
        """Test initialization with explicit parameters."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "openai"
            mock_config.return_value.llm.model = "gpt-4"
            mock_config.return_value.get_api_key.return_value = "config-key"

            client = LLMClient(
                provider="anthropic",
                model="claude-3",
                api_key="explicit-key",
                temperature=0.5,
                max_tokens=2000,
            )

            assert client.provider == "anthropic"
            assert client.model == "claude-3"
            assert client.api_key == "explicit-key"
            assert client.temperature == 0.5
            assert client.max_tokens == 2000

    def test_format_tool_result_openai(self):
        """Test formatting tool result for OpenAI."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "openai"
            mock_config.return_value.llm.model = "gpt-4"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient()
            msg = client.format_tool_result_message("call_123", "Result data")

            assert msg["role"] == "tool"
            assert msg["tool_call_id"] == "call_123"
            assert msg["content"] == "Result data"

    def test_format_tool_result_anthropic(self):
        """Test formatting tool result for Anthropic."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "anthropic"
            mock_config.return_value.llm.model = "claude"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient(provider="anthropic")
            msg = client.format_tool_result_message("call_123", "Result data")

            assert msg["role"] == "tool"
            assert msg["tool_call_id"] == "call_123"

    def test_format_assistant_message_openai(self):
        """Test formatting assistant message with tool calls for OpenAI."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "openai"
            mock_config.return_value.llm.model = "gpt-4"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient()
            tool_calls = [
                ToolCall(id="call_1", name="func1", arguments={"arg": "value"}),
            ]
            msg = client.format_assistant_message_with_tool_calls("Thinking...", tool_calls)

            assert msg["role"] == "assistant"
            assert msg["content"] == "Thinking..."
            assert len(msg["tool_calls"]) == 1
            assert msg["tool_calls"][0]["type"] == "function"
            assert msg["tool_calls"][0]["function"]["name"] == "func1"

    def test_format_assistant_message_anthropic(self):
        """Test formatting assistant message with tool calls for Anthropic."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "anthropic"
            mock_config.return_value.llm.model = "claude"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient(provider="anthropic")
            tool_calls = [
                ToolCall(id="call_1", name="func1", arguments={"arg": "value"}),
            ]
            msg = client.format_assistant_message_with_tool_calls("Thinking...", tool_calls)

            assert msg["role"] == "assistant"
            assert len(msg["tool_calls"]) == 1
            assert msg["tool_calls"][0]["name"] == "func1"


class TestLLMClientMessageConversion:
    """Test message conversion methods."""

    def test_convert_messages_for_anthropic_basic(self):
        """Test basic message conversion for Anthropic."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "anthropic"
            mock_config.return_value.llm.model = "claude"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient(provider="anthropic")

            messages = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
            converted = client._convert_messages_for_anthropic(messages)

            assert len(converted) == 2
            assert converted[0]["role"] == "user"
            assert converted[1]["role"] == "assistant"

    def test_convert_messages_skips_system(self):
        """Test system messages are skipped (handled separately)."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "anthropic"
            mock_config.return_value.llm.model = "claude"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient(provider="anthropic")

            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ]
            converted = client._convert_messages_for_anthropic(messages)

            assert len(converted) == 1
            assert converted[0]["role"] == "user"

    def test_convert_tool_result_messages(self):
        """Test tool result messages are converted correctly."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "anthropic"
            mock_config.return_value.llm.model = "claude"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient(provider="anthropic")

            messages = [
                {"role": "tool", "tool_call_id": "call_123", "content": "Result"},
            ]
            converted = client._convert_messages_for_anthropic(messages)

            assert len(converted) == 1
            assert converted[0]["role"] == "user"
            assert converted[0]["content"][0]["type"] == "tool_result"
            assert converted[0]["content"][0]["tool_use_id"] == "call_123"

    def test_convert_assistant_with_tool_calls(self):
        """Test assistant messages with tool calls are converted."""
        with patch("psx.agents.llm.get_config") as mock_config:
            mock_config.return_value.llm.provider = "anthropic"
            mock_config.return_value.llm.model = "claude"
            mock_config.return_value.get_api_key.return_value = "key"

            client = LLMClient(provider="anthropic")

            messages = [
                {
                    "role": "assistant",
                    "content": "Let me check",
                    "tool_calls": [
                        {"id": "call_1", "name": "search", "arguments": {"q": "test"}},
                    ],
                },
            ]
            converted = client._convert_messages_for_anthropic(messages)

            assert len(converted) == 1
            assert converted[0]["role"] == "assistant"
            # Content should be list of blocks
            assert isinstance(converted[0]["content"], list)
