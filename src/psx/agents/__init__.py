"""AI agents for stock analysis.

Multi-agent system for fundamental analysis of PSX stocks.
"""

from psx.agents.base import BaseAgent, AgentConfig, Tool, create_tool
from psx.agents.llm import LLMClient, LLMResponse, ToolCall
from psx.agents.schemas import (
    DataAgentOutput,
    AnalystOutput,
    ResearchOutput,
    AnalysisState,
    AnalysisReport,
    ComparisonReport,
    ValuationDetail,
    PeerComparison,
    NewsItem,
)
from psx.agents.data_agent import DataAgent
from psx.agents.analyst_agent import AnalystAgent
from psx.agents.research_agent import ResearchAgent
from psx.agents.supervisor import SupervisorAgent, analyze_stock, compare_stocks


__all__ = [
    # Base classes
    "BaseAgent",
    "AgentConfig",
    "Tool",
    "create_tool",
    # LLM
    "LLMClient",
    "LLMResponse",
    "ToolCall",
    # Schemas
    "DataAgentOutput",
    "AnalystOutput",
    "ResearchOutput",
    "AnalysisState",
    "AnalysisReport",
    "ComparisonReport",
    "ValuationDetail",
    "PeerComparison",
    "NewsItem",
    # Agents
    "DataAgent",
    "AnalystAgent",
    "ResearchAgent",
    "SupervisorAgent",
    # Convenience functions
    "analyze_stock",
    "compare_stocks",
]
