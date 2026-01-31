"""Metrics collection for agent runs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import time


@dataclass
class LLMCallMetrics:
    """Metrics for a single LLM call."""

    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        """Total tokens for this call."""
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ToolCallMetrics:
    """Metrics for a single tool call."""

    agent: str
    tool_name: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Collects and aggregates metrics during analysis runs."""

    def __init__(self):
        self.llm_calls: list[LLMCallMetrics] = []
        self.tool_calls: list[ToolCallMetrics] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def start_run(self):
        """Mark the start of an analysis run."""
        self.start_time = time.time()
        self.llm_calls = []
        self.tool_calls = []
        self.end_time = None

    def end_run(self):
        """Mark the end of an analysis run."""
        self.end_time = time.time()

    def log_llm_call(
        self,
        agent: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ):
        """Log an LLM API call.

        Args:
            agent: Name of the agent making the call
            model: Model identifier used
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            latency_ms: Time taken in milliseconds
        """
        self.llm_calls.append(
            LLMCallMetrics(
                agent=agent,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
            )
        )

    def log_tool_call(
        self,
        agent: str,
        tool_name: str,
        success: bool,
        latency_ms: float,
        error: Optional[str] = None,
    ):
        """Log a tool call.

        Args:
            agent: Name of the agent making the call
            tool_name: Name of the tool called
            success: Whether the tool call succeeded
            latency_ms: Time taken in milliseconds
            error: Error message if failed
        """
        self.tool_calls.append(
            ToolCallMetrics(
                agent=agent,
                tool_name=tool_name,
                success=success,
                latency_ms=latency_ms,
                error=error,
            )
        )

    @property
    def total_tokens(self) -> int:
        """Total tokens used across all LLM calls."""
        return sum(c.prompt_tokens + c.completion_tokens for c in self.llm_calls)

    @property
    def total_prompt_tokens(self) -> int:
        """Total input tokens."""
        return sum(c.prompt_tokens for c in self.llm_calls)

    @property
    def total_completion_tokens(self) -> int:
        """Total output tokens."""
        return sum(c.completion_tokens for c in self.llm_calls)

    @property
    def total_latency_seconds(self) -> float:
        """Total wall-clock time for the run."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0.0

    @property
    def llm_latency_seconds(self) -> float:
        """Total time spent waiting for LLM responses."""
        return sum(c.latency_ms for c in self.llm_calls) / 1000

    @property
    def tool_success_rate(self) -> float:
        """Percentage of successful tool calls."""
        if not self.tool_calls:
            return 1.0
        return sum(1 for c in self.tool_calls if c.success) / len(self.tool_calls)

    @property
    def failed_tools(self) -> list[ToolCallMetrics]:
        """List of failed tool calls."""
        return [c for c in self.tool_calls if not c.success]

    def by_agent(self) -> dict[str, dict]:
        """Breakdown of metrics by agent.

        Returns:
            Dict mapping agent name to metrics summary
        """
        agents = set(c.agent for c in self.llm_calls)
        agents.update(c.agent for c in self.tool_calls)

        result = {}
        for agent in agents:
            agent_llm_calls = [c for c in self.llm_calls if c.agent == agent]
            agent_tool_calls = [c for c in self.tool_calls if c.agent == agent]

            result[agent] = {
                "llm_calls": len(agent_llm_calls),
                "tokens": sum(c.total_tokens for c in agent_llm_calls),
                "prompt_tokens": sum(c.prompt_tokens for c in agent_llm_calls),
                "completion_tokens": sum(c.completion_tokens for c in agent_llm_calls),
                "tool_calls": len(agent_tool_calls),
                "tool_failures": sum(1 for c in agent_tool_calls if not c.success),
                "llm_latency_ms": sum(c.latency_ms for c in agent_llm_calls),
            }

        return result

    def to_dict(self) -> dict:
        """Export metrics as dictionary.

        Returns:
            Dict containing all metrics
        """
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_latency_seconds": round(self.total_latency_seconds, 2),
            "llm_latency_seconds": round(self.llm_latency_seconds, 2),
            "llm_call_count": len(self.llm_calls),
            "tool_call_count": len(self.tool_calls),
            "tool_success_rate": round(self.tool_success_rate, 3),
            "by_agent": self.by_agent(),
        }

    def summary_line(self) -> str:
        """Generate a one-line summary for CLI output.

        Returns:
            Formatted summary string
        """
        from psx.observability.cost import calculate_total_cost

        cost = calculate_total_cost(self)
        return (
            f"Tokens: {self.total_tokens:,} | "
            f"Cost: ${cost:.4f} | "
            f"Time: {self.total_latency_seconds:.1f}s"
        )


# Global metrics collector (singleton pattern)
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get or create the global metrics collector.

    Returns:
        The global MetricsCollector instance
    """
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def reset_metrics() -> MetricsCollector:
    """Reset metrics for a new run.

    Returns:
        Fresh MetricsCollector instance
    """
    global _metrics
    _metrics = MetricsCollector()
    return _metrics
