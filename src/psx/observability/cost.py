"""Cost calculation for LLM usage."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psx.observability.metrics import MetricsCollector

# Pricing per 1M tokens (as of January 2025)
# Sources: OpenAI and Anthropic pricing pages
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI models
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-2024-04-09": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
    # OpenAI o-series (reasoning models)
    "o1": {"input": 15.00, "output": 60.00},
    "o1-2024-12-17": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},
    "o1-mini-2024-09-12": {"input": 3.00, "output": 12.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    # Anthropic Claude models
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-opus-latest": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}

# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING = {"input": 5.00, "output": 15.00}


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Calculate cost in USD for token usage.

    Args:
        model: Model identifier
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


def calculate_total_cost(metrics: "MetricsCollector") -> float:
    """Calculate total cost from metrics collector.

    Args:
        metrics: MetricsCollector with logged LLM calls

    Returns:
        Total cost in USD
    """
    total = 0.0
    for call in metrics.llm_calls:
        total += calculate_cost(
            call.model,
            call.prompt_tokens,
            call.completion_tokens,
        )
    return total


def format_cost(cost: float) -> str:
    """Format cost for display.

    Args:
        cost: Cost in USD

    Returns:
        Formatted string (e.g., "$0.0842" or "$1.23")
    """
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1.00:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"
