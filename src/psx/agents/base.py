"""Base agent class with tool execution support.

Provides the foundation for all specialized agents.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from psx.agents.llm import LLMClient, Tool, ToolCall
from psx.core.config import get_config, LLMProvider


logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    description: str
    system_prompt: str
    max_iterations: int = 5
    temperature: float = 0.0


class BaseAgent:
    """Base class for all agents with tool execution support.

    Implements the ReAct pattern: Reason → Act → Observe → Repeat
    """

    def __init__(
        self,
        config: AgentConfig,
        tools: list[Tool],
        llm_provider: Optional[LLMProvider] = None,
        llm_model: Optional[str] = None,
    ):
        """Initialize the agent.

        Args:
            config: Agent configuration
            tools: List of tools available to this agent
            llm_provider: Override default LLM provider
            llm_model: Override default LLM model
        """
        self.config = config
        self.tools = {tool.name: tool for tool in tools}
        self.tool_list = tools

        # Initialize LLM client
        app_config = get_config()
        self.llm = LLMClient(
            provider=llm_provider or app_config.llm.provider,
            model=llm_model or app_config.llm.model,
            temperature=config.temperature,
        )

        self.max_iterations = config.max_iterations

    def run(
        self,
        task: str,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute the agent on a task.

        Args:
            task: The task description
            context: Optional context dict to include

        Returns:
            Dict with agent output
        """
        logger.info(f"Agent '{self.config.name}' starting task: {task[:100]}...")
        logger.debug(f"[{self.config.name}] Full task: {task}")
        logger.debug(f"[{self.config.name}] Available tools: {list(self.tools.keys())}")

        # Build initial messages
        messages: list[dict[str, Any]] = []

        # Add context if provided
        if context:
            context_str = self._format_context(context)
            messages.append({
                "role": "user",
                "content": f"Context:\n{context_str}",
            })
            logger.debug(f"[{self.config.name}] Context provided with keys: {list(context.keys())}")

        # Add the task
        messages.append({
            "role": "user",
            "content": task,
        })

        # Agent loop
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.debug(f"[{self.config.name}] === Iteration {iteration}/{self.max_iterations} ===")

            # Get LLM response
            response = self.llm.chat(
                messages=messages,
                tools=self.tool_list if self.tool_list else None,
                system=self.config.system_prompt,
            )

            # Log LLM reasoning if present
            if response.content:
                preview = response.content[:500] + "..." if len(response.content) > 500 else response.content
                logger.debug(f"[{self.config.name}] LLM reasoning: {preview}")

            # Check if we have tool calls to execute
            if response.has_tool_calls:
                logger.debug(f"[{self.config.name}] Tool calls requested: {[tc.name for tc in response.tool_calls]}")

                # Add assistant message with tool calls
                messages.append(
                    self.llm.format_assistant_message_with_tool_calls(
                        response.content, response.tool_calls
                    )
                )

                # Execute each tool call
                for tool_call in response.tool_calls:
                    logger.info(f"[{self.config.name}] 🔧 Calling tool: {tool_call.name}")
                    logger.debug(f"[{self.config.name}]    Arguments: {json.dumps(tool_call.arguments, default=str)[:500]}")

                    result = self._execute_tool(tool_call)

                    # Log result preview
                    result_preview = result[:1000] + "..." if len(result) > 1000 else result
                    logger.debug(f"[{self.config.name}]    Result: {result_preview}")

                    # Add tool result message
                    messages.append(
                        self.llm.format_tool_result_message(
                            tool_call.id, result
                        )
                    )
            else:
                # No tool calls - agent is done
                logger.info(f"Agent '{self.config.name}' completed in {iteration} iterations")
                output_preview = response.content[:500] + "..." if len(response.content) > 500 else response.content
                logger.debug(f"[{self.config.name}] Final output: {output_preview}")
                return self._parse_output(response.content)

        # Max iterations reached
        logger.warning(f"Agent '{self.config.name}' reached max iterations")
        return {
            "error": "Max iterations reached",
            "partial_output": response.content if response else None,
        }

    def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a single tool call.

        Args:
            tool_call: The tool call to execute

        Returns:
            String result of the tool execution
        """
        tool_name = tool_call.name
        arguments = tool_call.arguments

        logger.debug(f"Executing tool: {tool_name} with args: {arguments}")

        if tool_name not in self.tools:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        tool = self.tools[tool_name]

        try:
            result = tool.function(**arguments)

            # Convert result to string
            if isinstance(result, dict):
                return json.dumps(result, default=str)
            elif isinstance(result, list):
                return json.dumps(result, default=str)
            elif hasattr(result, "to_dict"):
                return json.dumps(result.to_dict(), default=str)
            else:
                return str(result)

        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return json.dumps({"error": str(e)})

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dict for LLM.

        Args:
            context: Context dictionary

        Returns:
            Formatted string
        """
        lines = []
        for key, value in context.items():
            if hasattr(value, "to_context_string"):
                lines.append(f"{key}:\n{value.to_context_string()}")
            elif isinstance(value, dict):
                lines.append(f"{key}: {json.dumps(value, default=str)}")
            else:
                lines.append(f"{key}: {value}")
        return "\n\n".join(lines)

    def _parse_output(self, content: str) -> dict[str, Any]:
        """Parse LLM output into structured format.

        Override in subclasses for custom parsing.

        Args:
            content: Raw LLM output

        Returns:
            Parsed output dict
        """
        # Try to parse as JSON first
        try:
            # Look for JSON block in content
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
                return json.loads(json_str)
            elif content.strip().startswith("{"):
                return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Return as raw output
        return {"output": content}


def create_tool(
    name: str,
    description: str,
    function: Callable[..., Any],
    parameters: Optional[dict[str, Any]] = None,
) -> Tool:
    """Helper to create a Tool from a function.

    Args:
        name: Tool name
        description: Tool description
        function: The function to call
        parameters: JSON Schema for parameters (auto-generated if not provided)

    Returns:
        Tool instance
    """
    if parameters is None:
        # Auto-generate from function signature
        import inspect

        sig = inspect.signature(function)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"

            properties[param_name] = {"type": param_type}

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    return Tool(
        name=name,
        description=description,
        parameters=parameters,
        function=function,
    )


# Common tool schemas for reuse
SYMBOL_PARAMETER = {
    "type": "object",
    "properties": {
        "symbol": {
            "type": "string",
            "description": "Stock ticker symbol (e.g., OGDC, PPL)",
        },
    },
    "required": ["symbol"],
}

SYMBOLS_PARAMETER = {
    "type": "object",
    "properties": {
        "symbols": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of stock ticker symbols",
        },
    },
    "required": ["symbols"],
}
