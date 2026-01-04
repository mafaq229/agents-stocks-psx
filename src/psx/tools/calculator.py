"""Financial calculation tools for stock valuation.

Provides valuation methods (DCF, Graham, P/E) and ratio calculations.
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValuationResult:
    """Result of a valuation calculation."""

    method: str
    value: float
    inputs: dict
    notes: Optional[str] = None


class ValuationCalculator:
    """Stock valuation calculations."""

    @staticmethod
    def pe_valuation(
        eps: float,
        pe_ratio: float,
    ) -> ValuationResult:
        """Calculate fair value using P/E ratio method.

        Args:
            eps: Earnings per share (TTM or forward)
            pe_ratio: Target P/E ratio (sector average or historical)

        Returns:
            ValuationResult with calculated fair value
        """
        if eps <= 0:
            return ValuationResult(
                method="P/E Valuation",
                value=0.0,
                inputs={"eps": eps, "pe_ratio": pe_ratio},
                notes="EPS is negative or zero, P/E valuation not applicable",
            )

        fair_value = eps * pe_ratio

        return ValuationResult(
            method="P/E Valuation",
            value=round(fair_value, 2),
            inputs={"eps": eps, "pe_ratio": pe_ratio},
            notes=f"Fair Value = EPS ({eps}) × P/E ({pe_ratio})",
        )

    @staticmethod
    def graham_number(
        eps: float,
        book_value_per_share: float,
    ) -> ValuationResult:
        """Calculate Graham Number (Benjamin Graham's intrinsic value formula).

        Formula: sqrt(22.5 × EPS × BVPS)
        - 22.5 = 15 (max P/E) × 1.5 (max P/B)

        Args:
            eps: Earnings per share
            book_value_per_share: Book value per share

        Returns:
            ValuationResult with Graham Number
        """
        if eps <= 0 or book_value_per_share <= 0:
            return ValuationResult(
                method="Graham Number",
                value=0.0,
                inputs={"eps": eps, "book_value_per_share": book_value_per_share},
                notes="EPS or Book Value is negative/zero, Graham formula not applicable",
            )

        graham_value = math.sqrt(22.5 * eps * book_value_per_share)

        return ValuationResult(
            method="Graham Number",
            value=round(graham_value, 2),
            inputs={"eps": eps, "book_value_per_share": book_value_per_share},
            notes=f"Graham Number = sqrt(22.5 × {eps} × {book_value_per_share})",
        )

    @staticmethod
    def book_value_valuation(
        book_value_per_share: float,
        pb_ratio: float = 1.0,
    ) -> ValuationResult:
        """Calculate fair value based on book value.

        Args:
            book_value_per_share: Book value per share
            pb_ratio: Target P/B ratio (default 1.0 = trading at book)

        Returns:
            ValuationResult with calculated value
        """
        fair_value = book_value_per_share * pb_ratio

        return ValuationResult(
            method="Book Value",
            value=round(fair_value, 2),
            inputs={"book_value_per_share": book_value_per_share, "pb_ratio": pb_ratio},
            notes=f"Fair Value = BVPS ({book_value_per_share}) × P/B ({pb_ratio})",
        )

    @staticmethod
    def dcf_valuation(
        free_cash_flows: list[float],
        discount_rate: float = 0.10,
        terminal_growth_rate: float = 0.03,
        shares_outstanding: Optional[int] = None,
    ) -> ValuationResult:
        """Calculate intrinsic value using Discounted Cash Flow model.

        Args:
            free_cash_flows: Projected FCF for next N years
            discount_rate: WACC or required return (default 10%)
            terminal_growth_rate: Perpetual growth rate (default 3%)
            shares_outstanding: Number of shares (for per-share value)

        Returns:
            ValuationResult with DCF value (total or per share)
        """
        if not free_cash_flows:
            return ValuationResult(
                method="DCF",
                value=0.0,
                inputs={
                    "free_cash_flows": free_cash_flows,
                    "discount_rate": discount_rate,
                    "terminal_growth_rate": terminal_growth_rate,
                },
                notes="No cash flow projections provided",
            )

        if terminal_growth_rate >= discount_rate:
            return ValuationResult(
                method="DCF",
                value=0.0,
                inputs={
                    "free_cash_flows": free_cash_flows,
                    "discount_rate": discount_rate,
                    "terminal_growth_rate": terminal_growth_rate,
                },
                notes="Terminal growth rate must be less than discount rate",
            )

        # Present value of projected cash flows
        pv_cash_flows = 0.0
        for i, fcf in enumerate(free_cash_flows, start=1):
            pv_cash_flows += fcf / ((1 + discount_rate) ** i)

        # Terminal value (Gordon Growth Model)
        last_fcf = free_cash_flows[-1]
        terminal_value = (last_fcf * (1 + terminal_growth_rate)) / (
            discount_rate - terminal_growth_rate
        )

        # Present value of terminal value
        n = len(free_cash_flows)
        pv_terminal = terminal_value / ((1 + discount_rate) ** n)

        # Total enterprise value
        enterprise_value = pv_cash_flows + pv_terminal

        # Per share value if shares provided
        if shares_outstanding and shares_outstanding > 0:
            per_share_value = enterprise_value / shares_outstanding
            return ValuationResult(
                method="DCF",
                value=round(per_share_value, 2),
                inputs={
                    "free_cash_flows": free_cash_flows,
                    "discount_rate": discount_rate,
                    "terminal_growth_rate": terminal_growth_rate,
                    "shares_outstanding": shares_outstanding,
                },
                notes=f"Per share value (Enterprise: {enterprise_value:,.0f})",
            )

        return ValuationResult(
            method="DCF",
            value=round(enterprise_value, 2),
            inputs={
                "free_cash_flows": free_cash_flows,
                "discount_rate": discount_rate,
                "terminal_growth_rate": terminal_growth_rate,
            },
            notes="Enterprise value (shares not provided)",
        )

    @staticmethod
    def margin_of_safety(
        intrinsic_value: float,
        current_price: float,
    ) -> dict:
        """Calculate margin of safety.

        Args:
            intrinsic_value: Calculated fair value
            current_price: Current market price

        Returns:
            Dict with margin of safety metrics
        """
        if intrinsic_value <= 0 or current_price <= 0:
            return {
                "margin_of_safety_pct": 0.0,
                "upside_potential_pct": 0.0,
                "is_undervalued": False,
                "notes": "Invalid intrinsic value or price",
            }

        margin = ((intrinsic_value - current_price) / intrinsic_value) * 100
        upside = ((intrinsic_value - current_price) / current_price) * 100

        return {
            "margin_of_safety_pct": round(margin, 2),
            "upside_potential_pct": round(upside, 2),
            "is_undervalued": current_price < intrinsic_value,
            "intrinsic_value": intrinsic_value,
            "current_price": current_price,
        }

    @staticmethod
    def composite_valuation(
        valuations: list[ValuationResult],
        weights: Optional[list[float]] = None,
    ) -> dict:
        """Calculate weighted average of multiple valuation methods.

        Args:
            valuations: List of ValuationResult from different methods
            weights: Optional weights (equal if not provided)

        Returns:
            Dict with composite value and breakdown
        """
        valid_valuations = [v for v in valuations if v.value > 0]

        if not valid_valuations:
            return {
                "composite_value": 0.0,
                "methods_used": 0,
                "breakdown": [],
                "notes": "No valid valuations available",
            }

        if weights is None:
            weights = [1.0 / len(valid_valuations)] * len(valid_valuations)
        else:
            # Normalize weights
            total = sum(weights)
            weights = [w / total for w in weights]

        composite = sum(v.value * w for v, w in zip(valid_valuations, weights))

        return {
            "composite_value": round(composite, 2),
            "methods_used": len(valid_valuations),
            "breakdown": [
                {"method": v.method, "value": v.value, "weight": w}
                for v, w in zip(valid_valuations, weights)
            ],
        }


class RatioCalculator:
    """Financial ratio calculations."""

    # Liquidity Ratios
    @staticmethod
    def current_ratio(current_assets: float, current_liabilities: float) -> float:
        """Current Assets / Current Liabilities"""
        if current_liabilities == 0:
            return float("inf")
        return round(current_assets / current_liabilities, 2)

    @staticmethod
    def quick_ratio(
        current_assets: float, inventory: float, current_liabilities: float
    ) -> float:
        """(Current Assets - Inventory) / Current Liabilities"""
        if current_liabilities == 0:
            return float("inf")
        return round((current_assets - inventory) / current_liabilities, 2)

    # Leverage Ratios
    @staticmethod
    def debt_to_equity(total_debt: float, total_equity: float) -> float:
        """Total Debt / Total Equity"""
        if total_equity == 0:
            return float("inf")
        return round(total_debt / total_equity, 2)

    @staticmethod
    def debt_to_assets(total_debt: float, total_assets: float) -> float:
        """Total Debt / Total Assets"""
        if total_assets == 0:
            return float("inf")
        return round(total_debt / total_assets, 2)

    @staticmethod
    def interest_coverage(ebit: float, interest_expense: float) -> float:
        """EBIT / Interest Expense"""
        if interest_expense == 0:
            return float("inf")
        return round(ebit / interest_expense, 2)

    # Profitability Ratios
    @staticmethod
    def return_on_equity(net_income: float, shareholder_equity: float) -> float:
        """Net Income / Shareholder Equity"""
        if shareholder_equity == 0:
            return 0.0
        return round((net_income / shareholder_equity) * 100, 2)

    @staticmethod
    def return_on_assets(net_income: float, total_assets: float) -> float:
        """Net Income / Total Assets"""
        if total_assets == 0:
            return 0.0
        return round((net_income / total_assets) * 100, 2)

    @staticmethod
    def profit_margin(net_income: float, revenue: float) -> float:
        """Net Income / Revenue (as percentage)"""
        if revenue == 0:
            return 0.0
        return round((net_income / revenue) * 100, 2)

    @staticmethod
    def operating_margin(operating_income: float, revenue: float) -> float:
        """Operating Income / Revenue (as percentage)"""
        if revenue == 0:
            return 0.0
        return round((operating_income / revenue) * 100, 2)

    @staticmethod
    def gross_margin(gross_profit: float, revenue: float) -> float:
        """Gross Profit / Revenue (as percentage)"""
        if revenue == 0:
            return 0.0
        return round((gross_profit / revenue) * 100, 2)

    # Efficiency Ratios
    @staticmethod
    def asset_turnover(revenue: float, total_assets: float) -> float:
        """Revenue / Total Assets"""
        if total_assets == 0:
            return 0.0
        return round(revenue / total_assets, 2)

    @staticmethod
    def inventory_turnover(cost_of_goods_sold: float, average_inventory: float) -> float:
        """COGS / Average Inventory"""
        if average_inventory == 0:
            return 0.0
        return round(cost_of_goods_sold / average_inventory, 2)

    # Market Ratios
    @staticmethod
    def price_to_earnings(price: float, eps: float) -> float:
        """Price / EPS"""
        if eps <= 0:
            return float("inf")
        return round(price / eps, 2)

    @staticmethod
    def price_to_book(price: float, book_value_per_share: float) -> float:
        """Price / Book Value per Share"""
        if book_value_per_share <= 0:
            return float("inf")
        return round(price / book_value_per_share, 2)

    @staticmethod
    def dividend_yield(annual_dividend: float, price: float) -> float:
        """Annual Dividend / Price (as percentage)"""
        if price == 0:
            return 0.0
        return round((annual_dividend / price) * 100, 2)

    @staticmethod
    def earnings_yield(eps: float, price: float) -> float:
        """EPS / Price (as percentage) - inverse of P/E"""
        if price == 0:
            return 0.0
        return round((eps / price) * 100, 2)


def detect_red_flags(
    current_ratio: Optional[float] = None,
    quick_ratio: Optional[float] = None,
    debt_to_equity: Optional[float] = None,
    interest_coverage: Optional[float] = None,
    profit_margin: Optional[float] = None,
    roe: Optional[float] = None,
    revenue_growth: Optional[float] = None,
    earnings_growth: Optional[float] = None,
) -> list[str]:
    """Detect financial red flags based on key ratios.

    Returns list of warning messages for concerning metrics.
    """
    flags = []

    # Liquidity concerns
    if current_ratio is not None and current_ratio < 1.0:
        flags.append(f"Low current ratio ({current_ratio}) - potential liquidity issues")

    if quick_ratio is not None and quick_ratio < 0.5:
        flags.append(f"Very low quick ratio ({quick_ratio}) - immediate liquidity risk")

    # Leverage concerns
    if debt_to_equity is not None and debt_to_equity > 2.0:
        flags.append(f"High debt-to-equity ({debt_to_equity}) - high financial leverage")

    if interest_coverage is not None and interest_coverage < 2.0:
        flags.append(
            f"Low interest coverage ({interest_coverage}) - may struggle with debt payments"
        )

    # Profitability concerns
    if profit_margin is not None and profit_margin < 0:
        flags.append(f"Negative profit margin ({profit_margin}%) - company is losing money")

    if roe is not None and roe < 5:
        flags.append(f"Low ROE ({roe}%) - poor return on shareholder equity")

    # Growth concerns
    if revenue_growth is not None and revenue_growth < -10:
        flags.append(f"Declining revenue ({revenue_growth}%) - shrinking business")

    if earnings_growth is not None and earnings_growth < -20:
        flags.append(f"Declining earnings ({earnings_growth}%) - profitability deteriorating")

    return flags


def detect_strengths(
    current_ratio: Optional[float] = None,
    debt_to_equity: Optional[float] = None,
    interest_coverage: Optional[float] = None,
    profit_margin: Optional[float] = None,
    roe: Optional[float] = None,
    revenue_growth: Optional[float] = None,
) -> list[str]:
    """Detect financial strengths based on key ratios.

    Returns list of positive observations.
    """
    strengths = []

    # Liquidity strengths
    if current_ratio is not None and current_ratio > 2.0:
        strengths.append(f"Strong current ratio ({current_ratio}) - good liquidity position")

    # Low leverage
    if debt_to_equity is not None and debt_to_equity < 0.5:
        strengths.append(f"Low debt-to-equity ({debt_to_equity}) - conservative capital structure")

    if interest_coverage is not None and interest_coverage > 10:
        strengths.append(
            f"Excellent interest coverage ({interest_coverage}) - easily services debt"
        )

    # Profitability strengths
    if profit_margin is not None and profit_margin > 15:
        strengths.append(f"High profit margin ({profit_margin}%) - strong profitability")

    if roe is not None and roe > 15:
        strengths.append(f"Strong ROE ({roe}%) - efficient use of equity")

    # Growth strengths
    if revenue_growth is not None and revenue_growth > 15:
        strengths.append(f"Strong revenue growth ({revenue_growth}%) - growing business")

    return strengths
