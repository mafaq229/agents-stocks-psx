"""Analyst Agent for financial analysis and valuation.

Responsible for calculating valuations, detecting red flags, and making recommendations.
"""

import json
import logging
from typing import Any, Optional

from psx.agents.base import BaseAgent, AgentConfig
from psx.agents.llm import Tool
from psx.agents.schemas import AnalystOutput, ValuationDetail, PeerComparison
from psx.tools.calculator import (
    ValuationCalculator,
    RatioCalculator,
    detect_red_flags,
    detect_strengths,
)


logger = logging.getLogger(__name__)


# Tool implementations
def calculate_pe_valuation(eps: float, sector_pe: float) -> dict[str, Any]:
    """Calculate fair value using P/E ratio method.

    Args:
        eps: Earnings per share
        sector_pe: Sector average P/E ratio

    Returns:
        Valuation result
    """
    result = ValuationCalculator.pe_valuation(eps, sector_pe)
    return {
        "method": result.method,
        "fair_value": result.value,
        "inputs": result.inputs,
        "notes": result.notes,
    }


def calculate_graham_number(eps: float, book_value_per_share: float) -> dict[str, Any]:
    """Calculate Graham Number (Benjamin Graham's intrinsic value formula).

    Args:
        eps: Earnings per share
        book_value_per_share: Book value per share

    Returns:
        Valuation result
    """
    result = ValuationCalculator.graham_number(eps, book_value_per_share)
    return {
        "method": result.method,
        "fair_value": result.value,
        "inputs": result.inputs,
        "notes": result.notes,
    }


def calculate_book_value(
    book_value_per_share: float, pb_ratio: float = 1.0
) -> dict[str, Any]:
    """Calculate fair value based on book value.

    Args:
        book_value_per_share: Book value per share
        pb_ratio: Target P/B ratio

    Returns:
        Valuation result
    """
    result = ValuationCalculator.book_value_valuation(book_value_per_share, pb_ratio)
    return {
        "method": result.method,
        "fair_value": result.value,
        "inputs": result.inputs,
        "notes": result.notes,
    }


def calculate_dcf(
    free_cash_flows: list[float],
    discount_rate: float = 0.10,
    terminal_growth_rate: float = 0.03,
    shares_outstanding: Optional[int] = None,
) -> dict[str, Any]:
    """Calculate intrinsic value using DCF model.

    Args:
        free_cash_flows: Projected FCF for next N years
        discount_rate: WACC or required return
        terminal_growth_rate: Perpetual growth rate
        shares_outstanding: Number of shares (for per-share value)

    Returns:
        Valuation result
    """
    result = ValuationCalculator.dcf_valuation(
        free_cash_flows, discount_rate, terminal_growth_rate, shares_outstanding
    )
    return {
        "method": result.method,
        "fair_value": result.value,
        "inputs": result.inputs,
        "notes": result.notes,
    }


def calculate_margin_of_safety(
    intrinsic_value: float, current_price: float
) -> dict[str, Any]:
    """Calculate margin of safety.

    Args:
        intrinsic_value: Calculated fair value
        current_price: Current market price

    Returns:
        Margin of safety metrics
    """
    return ValuationCalculator.margin_of_safety(intrinsic_value, current_price)


def calculate_financial_ratios(
    current_assets: Optional[float] = None,
    current_liabilities: Optional[float] = None,
    total_debt: Optional[float] = None,
    total_equity: Optional[float] = None,
    net_income: Optional[float] = None,
    revenue: Optional[float] = None,
    total_assets: Optional[float] = None,
    ebit: Optional[float] = None,
    interest_expense: Optional[float] = None,
) -> dict[str, Any]:
    """Calculate multiple financial ratios from provided data.

    Args:
        Various financial statement items

    Returns:
        Dict with calculated ratios
    """
    ratios = {}

    if current_assets and current_liabilities:
        ratios["current_ratio"] = RatioCalculator.current_ratio(
            current_assets, current_liabilities
        )

    if total_debt is not None and total_equity:
        ratios["debt_to_equity"] = RatioCalculator.debt_to_equity(
            total_debt, total_equity
        )

    if total_debt is not None and total_assets:
        ratios["debt_to_assets"] = RatioCalculator.debt_to_assets(
            total_debt, total_assets
        )

    if net_income is not None and total_equity:
        ratios["roe"] = RatioCalculator.return_on_equity(net_income, total_equity)

    if net_income is not None and total_assets:
        ratios["roa"] = RatioCalculator.return_on_assets(net_income, total_assets)

    if net_income is not None and revenue:
        ratios["profit_margin"] = RatioCalculator.profit_margin(net_income, revenue)

    if ebit and interest_expense:
        ratios["interest_coverage"] = RatioCalculator.interest_coverage(
            ebit, interest_expense
        )

    return ratios


def analyze_financial_health(
    current_ratio: Optional[float] = None,
    quick_ratio: Optional[float] = None,
    debt_to_equity: Optional[float] = None,
    interest_coverage: Optional[float] = None,
    profit_margin: Optional[float] = None,
    roe: Optional[float] = None,
    revenue_growth: Optional[float] = None,
    earnings_growth: Optional[float] = None,
) -> dict[str, Any]:
    """Analyze financial health and detect red flags and strengths.

    Args:
        Key financial ratios

    Returns:
        Dict with red flags, strengths, and health score
    """
    red_flags = detect_red_flags(
        current_ratio=current_ratio,
        quick_ratio=quick_ratio,
        debt_to_equity=debt_to_equity,
        interest_coverage=interest_coverage,
        profit_margin=profit_margin,
        roe=roe,
        revenue_growth=revenue_growth,
        earnings_growth=earnings_growth,
    )

    strengths = detect_strengths(
        current_ratio=current_ratio,
        debt_to_equity=debt_to_equity,
        interest_coverage=interest_coverage,
        profit_margin=profit_margin,
        roe=roe,
        revenue_growth=revenue_growth,
    )

    # Calculate health score (0-100)
    score = 50  # Start neutral

    # Deduct for red flags
    score -= len(red_flags) * 10

    # Add for strengths
    score += len(strengths) * 10

    # Bound to 0-100
    score = max(0, min(100, score))

    return {
        "red_flags": red_flags,
        "strengths": strengths,
        "health_score": score,
    }


def compare_with_sector(
    company_pe: float,
    sector_pe: float,
    company_pb: Optional[float] = None,
    sector_pb: Optional[float] = None,
    company_roe: Optional[float] = None,
    sector_roe: Optional[float] = None,
) -> dict[str, Any]:
    """Compare company metrics with sector averages.

    Args:
        Company and sector metrics

    Returns:
        Comparison analysis
    """
    comparison = {}

    # P/E comparison
    if sector_pe and sector_pe > 0:
        pe_discount = ((sector_pe - company_pe) / sector_pe) * 100
        comparison["pe_vs_sector"] = {
            "company": company_pe,
            "sector": sector_pe,
            "discount_pct": round(pe_discount, 2),
            "is_undervalued": company_pe < sector_pe,
        }

    # P/B comparison
    if company_pb and sector_pb and sector_pb > 0:
        pb_discount = ((sector_pb - company_pb) / sector_pb) * 100
        comparison["pb_vs_sector"] = {
            "company": company_pb,
            "sector": sector_pb,
            "discount_pct": round(pb_discount, 2),
            "is_undervalued": company_pb < sector_pb,
        }

    # ROE comparison
    if company_roe and sector_roe:
        comparison["roe_vs_sector"] = {
            "company": company_roe,
            "sector": sector_roe,
            "outperforms": company_roe > sector_roe,
        }

    return comparison


# Tool definitions
ANALYST_AGENT_TOOLS = [
    Tool(
        name="calculate_pe_valuation",
        description="Calculate fair value using P/E ratio method. Requires EPS and sector P/E.",
        parameters={
            "type": "object",
            "properties": {
                "eps": {
                    "type": "number",
                    "description": "Earnings per share (TTM or forward)",
                },
                "sector_pe": {
                    "type": "number",
                    "description": "Sector average P/E ratio",
                },
            },
            "required": ["eps", "sector_pe"],
        },
        function=calculate_pe_valuation,
    ),
    Tool(
        name="calculate_graham_number",
        description="Calculate Graham Number - Benjamin Graham's intrinsic value formula. Conservative estimate.",
        parameters={
            "type": "object",
            "properties": {
                "eps": {
                    "type": "number",
                    "description": "Earnings per share",
                },
                "book_value_per_share": {
                    "type": "number",
                    "description": "Book value per share",
                },
            },
            "required": ["eps", "book_value_per_share"],
        },
        function=calculate_graham_number,
    ),
    Tool(
        name="calculate_book_value",
        description="Calculate fair value based on book value with P/B multiple.",
        parameters={
            "type": "object",
            "properties": {
                "book_value_per_share": {
                    "type": "number",
                    "description": "Book value per share",
                },
                "pb_ratio": {
                    "type": "number",
                    "description": "Target P/B ratio (default 1.0)",
                    "default": 1.0,
                },
            },
            "required": ["book_value_per_share"],
        },
        function=calculate_book_value,
    ),
    Tool(
        name="calculate_dcf",
        description="Calculate intrinsic value using Discounted Cash Flow model.",
        parameters={
            "type": "object",
            "properties": {
                "free_cash_flows": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Projected free cash flows for next N years",
                },
                "discount_rate": {
                    "type": "number",
                    "description": "Discount rate (WACC), default 0.10",
                    "default": 0.10,
                },
                "terminal_growth_rate": {
                    "type": "number",
                    "description": "Terminal growth rate, default 0.03",
                    "default": 0.03,
                },
                "shares_outstanding": {
                    "type": "integer",
                    "description": "Number of shares for per-share value",
                },
            },
            "required": ["free_cash_flows"],
        },
        function=calculate_dcf,
    ),
    Tool(
        name="calculate_margin_of_safety",
        description="Calculate margin of safety between intrinsic value and current price.",
        parameters={
            "type": "object",
            "properties": {
                "intrinsic_value": {
                    "type": "number",
                    "description": "Calculated fair value",
                },
                "current_price": {
                    "type": "number",
                    "description": "Current market price",
                },
            },
            "required": ["intrinsic_value", "current_price"],
        },
        function=calculate_margin_of_safety,
    ),
    Tool(
        name="calculate_financial_ratios",
        description="Calculate financial ratios from balance sheet and income statement data.",
        parameters={
            "type": "object",
            "properties": {
                "current_assets": {"type": "number"},
                "current_liabilities": {"type": "number"},
                "total_debt": {"type": "number"},
                "total_equity": {"type": "number"},
                "net_income": {"type": "number"},
                "revenue": {"type": "number"},
                "total_assets": {"type": "number"},
                "ebit": {"type": "number"},
                "interest_expense": {"type": "number"},
            },
            "required": [],
        },
        function=calculate_financial_ratios,
    ),
    Tool(
        name="analyze_financial_health",
        description="Analyze financial health, detect red flags and strengths.",
        parameters={
            "type": "object",
            "properties": {
                "current_ratio": {"type": "number"},
                "quick_ratio": {"type": "number"},
                "debt_to_equity": {"type": "number"},
                "interest_coverage": {"type": "number"},
                "profit_margin": {"type": "number"},
                "roe": {"type": "number"},
                "revenue_growth": {"type": "number"},
                "earnings_growth": {"type": "number"},
            },
            "required": [],
        },
        function=analyze_financial_health,
    ),
    Tool(
        name="compare_with_sector",
        description="Compare company metrics with sector averages to assess relative valuation.",
        parameters={
            "type": "object",
            "properties": {
                "company_pe": {"type": "number"},
                "sector_pe": {"type": "number"},
                "company_pb": {"type": "number"},
                "sector_pb": {"type": "number"},
                "company_roe": {"type": "number"},
                "sector_roe": {"type": "number"},
            },
            "required": ["company_pe", "sector_pe"],
        },
        function=compare_with_sector,
    ),
]


ANALYST_AGENT_SYSTEM_PROMPT = """You are a Financial Analyst Agent specialized in fundamental analysis of Pakistan Stock Exchange (PSX) stocks.

Your responsibilities:
1. Calculate multiple valuations using different methods (P/E, Graham, Book Value, DCF)
2. Analyze financial health and detect red flags
3. Compare company metrics with sector averages
4. Provide buy/sell/hold recommendations with reasoning

Guidelines:
- Be conservative in your estimates - it's better to underestimate value
- Use multiple valuation methods and take the average or most appropriate
- Compare valuation of industry peers and competitors as well
- Always consider the margin of safety
- Clearly explain your reasoning and any assumptions
- If data is insufficient, note what's missing

Recommendation scale:
- STRONG_BUY: Significantly undervalued (>30% margin of safety) with strong fundamentals
- BUY: Undervalued (15-30% margin of safety) with good fundamentals
- HOLD: Fairly valued or mixed signals
- SELL: Overvalued (negative margin of safety) with weak fundamentals
- STRONG_SELL: Significantly overvalued with serious red flags

When you have completed your analysis, respond with a JSON object:
{
    "symbol": "...",
    "health_score": 0-100,
    "valuations": [{"method": "...", "value": ...}, ...],
    "fair_value": ...,
    "current_price": ...,
    "margin_of_safety": ...,
    "red_flags": [...],
    "strengths": [...],
    "peer_comparison": {...},
    "recommendation": "BUY/HOLD/SELL/...",
    "confidence": 0.0-1.0,
    "reasoning": "..."
}"""


class AnalystAgent(BaseAgent):
    """Agent for financial analysis and valuation."""

    def __init__(self, **kwargs):
        config = AgentConfig(
            name="AnalystAgent",
            description="Performs financial analysis and stock valuation",
            system_prompt=ANALYST_AGENT_SYSTEM_PROMPT,
            max_iterations=8,
            max_tokens=8192,  # Large output for detailed valuation analysis
        )
        super().__init__(config=config, tools=ANALYST_AGENT_TOOLS, **kwargs)

    def run(self, task: str, context: Optional[dict[str, Any]] = None) -> AnalystOutput:
        """Run the analyst agent and return structured output.

        Args:
            task: Analysis task description
            context: Optional context (should include DataAgentOutput)

        Returns:
            AnalystOutput with analysis results
        """
        result = super().run(task, context)
        return self._parse_to_output(result)

    def _parse_to_output(self, result: dict[str, Any]) -> AnalystOutput:
        """Convert agent result to AnalystOutput."""
        import re

        # Handle nested output
        if "output" in result:
            try:
                if isinstance(result["output"], str):
                    json_match = re.search(r'\{[\s\S]*\}', result["output"])
                    if json_match:
                        result = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Parse valuations
        valuations = []
        for v in result.get("valuations", []):
            valuations.append(ValuationDetail(
                method=v.get("method", "Unknown"),
                value=v.get("value", 0),
                inputs=v.get("inputs", {}),
                notes=v.get("notes"),
            ))

        # Parse peer comparison
        peer_comparison = []
        if "peer_comparison" in result and isinstance(result["peer_comparison"], list):
            for p in result["peer_comparison"]:
                peer_comparison.append(PeerComparison(
                    symbol=p.get("symbol", ""),
                    name=p.get("name"),
                    price=p.get("price"),
                    pe_ratio=p.get("pe_ratio"),
                ))

        # Determine recommendation
        recommendation = result.get("recommendation", "HOLD")
        if recommendation not in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"):
            recommendation = "HOLD"

        return AnalystOutput(
            symbol=result.get("symbol", "UNKNOWN"),
            health_score=result.get("health_score", 50),
            valuations=valuations,
            fair_value=result.get("fair_value"),
            current_price=result.get("current_price"),
            margin_of_safety=result.get("margin_of_safety"),
            red_flags=result.get("red_flags", []),
            strengths=result.get("strengths", []),
            peer_comparison=peer_comparison,
            recommendation=recommendation,
            confidence=result.get("confidence", 0.5),
            reasoning=result.get("reasoning", ""),
        )
