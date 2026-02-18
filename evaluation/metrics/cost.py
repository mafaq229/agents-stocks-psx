"""Cost tracking for evaluation runs."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CostTracker:
    """Track costs during evaluation runs."""

    total_tokens: int = 0
    total_cost_usd: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    latency_seconds: float = 0.0

    # Breakdown by component
    by_component: dict[str, dict] = field(default_factory=dict)

    def add_run(
        self,
        component: str,
        tokens: int,
        cost: float,
        latency: float,
        llm_calls: int = 1,
        tool_calls: int = 0,
    ):
        """Add metrics from a single run.

        Args:
            component: Component name (e.g., "DataAgent", "PDFParser")
            tokens: Tokens used
            cost: Cost in USD
            latency: Latency in seconds
            llm_calls: Number of LLM API calls
            tool_calls: Number of tool calls
        """
        self.total_tokens += tokens
        self.total_cost_usd += cost
        self.latency_seconds += latency
        self.llm_calls += llm_calls
        self.tool_calls += tool_calls

        if component not in self.by_component:
            self.by_component[component] = {
                "tokens": 0,
                "cost": 0.0,
                "latency": 0.0,
                "runs": 0,
            }

        self.by_component[component]["tokens"] += tokens
        self.by_component[component]["cost"] += cost
        self.by_component[component]["latency"] += latency
        self.by_component[component]["runs"] += 1

    def to_dict(self) -> dict:
        """Export tracker data as dictionary."""
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "latency_seconds": round(self.latency_seconds, 2),
            "by_component": self.by_component,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        return (
            f"Tokens: {self.total_tokens:,} | "
            f"Cost: ${self.total_cost_usd:.4f} | "
            f"Time: {self.latency_seconds:.1f}s | "
            f"LLM calls: {self.llm_calls}"
        )
