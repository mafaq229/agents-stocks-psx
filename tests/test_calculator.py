"""Tests for financial calculation tools."""

import pytest
import math

from psx.tools.calculator import (
    ValuationResult,
    ValuationCalculator,
    RatioCalculator,
    detect_red_flags,
    detect_strengths,
)


class TestValuationResult:
    """Test ValuationResult dataclass."""

    def test_instantiation(self):
        """Test creating ValuationResult."""
        result = ValuationResult(
            method="P/E Valuation",
            value=100.0,
            inputs={"eps": 5.0, "pe_ratio": 20.0},
            notes="Test note",
        )
        assert result.method == "P/E Valuation"
        assert result.value == 100.0
        assert result.inputs["eps"] == 5.0
        assert result.notes == "Test note"

    def test_optional_notes(self):
        """Test notes is optional."""
        result = ValuationResult(
            method="Test",
            value=50.0,
            inputs={},
        )
        assert result.notes is None


class TestValuationCalculatorPE:
    """Test P/E valuation method."""

    def test_positive_eps(self):
        """Test P/E valuation with positive EPS."""
        result = ValuationCalculator.pe_valuation(eps=5.0, pe_ratio=20.0)
        assert result.value == 100.0
        assert result.method == "P/E Valuation"

    def test_fractional_eps(self):
        """Test with fractional EPS."""
        result = ValuationCalculator.pe_valuation(eps=2.5, pe_ratio=15.0)
        assert result.value == 37.5

    def test_zero_eps(self):
        """Test with zero EPS returns 0."""
        result = ValuationCalculator.pe_valuation(eps=0, pe_ratio=20.0)
        assert result.value == 0.0
        assert "not applicable" in result.notes

    def test_negative_eps(self):
        """Test with negative EPS returns 0."""
        result = ValuationCalculator.pe_valuation(eps=-2.0, pe_ratio=20.0)
        assert result.value == 0.0
        assert "negative" in result.notes

    def test_inputs_recorded(self):
        """Test inputs are recorded in result."""
        result = ValuationCalculator.pe_valuation(eps=3.0, pe_ratio=18.0)
        assert result.inputs["eps"] == 3.0
        assert result.inputs["pe_ratio"] == 18.0


class TestValuationCalculatorGraham:
    """Test Graham Number calculation."""

    def test_positive_values(self):
        """Test Graham Number with positive values."""
        # Graham = sqrt(22.5 * EPS * BVPS)
        result = ValuationCalculator.graham_number(eps=4.0, book_value_per_share=10.0)
        expected = math.sqrt(22.5 * 4.0 * 10.0)
        assert result.value == pytest.approx(expected, rel=0.01)
        assert result.method == "Graham Number"

    def test_zero_eps(self):
        """Test with zero EPS returns 0."""
        result = ValuationCalculator.graham_number(eps=0, book_value_per_share=10.0)
        assert result.value == 0.0

    def test_negative_book_value(self):
        """Test with negative book value returns 0."""
        result = ValuationCalculator.graham_number(eps=5.0, book_value_per_share=-10.0)
        assert result.value == 0.0

    def test_both_negative(self):
        """Test with both negative returns 0."""
        result = ValuationCalculator.graham_number(eps=-2.0, book_value_per_share=-5.0)
        assert result.value == 0.0


class TestValuationCalculatorBookValue:
    """Test Book Value valuation method."""

    def test_at_book_value(self):
        """Test valuation at book value (P/B = 1.0)."""
        result = ValuationCalculator.book_value_valuation(book_value_per_share=50.0)
        assert result.value == 50.0

    def test_with_pb_multiplier(self):
        """Test valuation with P/B multiplier."""
        result = ValuationCalculator.book_value_valuation(
            book_value_per_share=50.0, pb_ratio=1.5
        )
        assert result.value == 75.0

    def test_negative_book_value(self):
        """Test with negative book value."""
        result = ValuationCalculator.book_value_valuation(book_value_per_share=-20.0)
        assert result.value == -20.0  # Still calculates


class TestValuationCalculatorDCF:
    """Test DCF valuation method."""

    def test_basic_dcf(self):
        """Test basic DCF calculation."""
        cash_flows = [100, 110, 120, 130, 140]
        result = ValuationCalculator.dcf_valuation(
            free_cash_flows=cash_flows,
            discount_rate=0.10,
            terminal_growth_rate=0.03,
        )
        assert result.value > 0
        assert result.method == "DCF"

    def test_dcf_per_share(self):
        """Test DCF per share value."""
        cash_flows = [1000000, 1100000, 1200000]
        result = ValuationCalculator.dcf_valuation(
            free_cash_flows=cash_flows,
            discount_rate=0.10,
            terminal_growth_rate=0.03,
            shares_outstanding=100000,
        )
        assert result.value > 0
        assert "Per share" in result.notes

    def test_empty_cash_flows(self):
        """Test with empty cash flows returns 0."""
        result = ValuationCalculator.dcf_valuation(free_cash_flows=[])
        assert result.value == 0.0
        assert "No cash flow" in result.notes

    def test_terminal_rate_exceeds_discount(self):
        """Test terminal rate >= discount rate returns 0."""
        result = ValuationCalculator.dcf_valuation(
            free_cash_flows=[100, 110],
            discount_rate=0.05,
            terminal_growth_rate=0.05,  # Equal to discount
        )
        assert result.value == 0.0

    def test_terminal_rate_greater_than_discount(self):
        """Test terminal rate > discount rate returns 0."""
        result = ValuationCalculator.dcf_valuation(
            free_cash_flows=[100, 110],
            discount_rate=0.05,
            terminal_growth_rate=0.10,  # Greater than discount
        )
        assert result.value == 0.0


class TestValuationCalculatorMarginOfSafety:
    """Test margin of safety calculation."""

    def test_undervalued_stock(self):
        """Test margin of safety for undervalued stock."""
        result = ValuationCalculator.margin_of_safety(
            intrinsic_value=100.0, current_price=80.0
        )
        assert result["margin_of_safety_pct"] == 20.0
        assert result["upside_potential_pct"] == 25.0
        assert result["is_undervalued"] is True

    def test_overvalued_stock(self):
        """Test margin of safety for overvalued stock."""
        result = ValuationCalculator.margin_of_safety(
            intrinsic_value=80.0, current_price=100.0
        )
        assert result["margin_of_safety_pct"] == -25.0
        assert result["upside_potential_pct"] == -20.0
        assert result["is_undervalued"] is False

    def test_fairly_valued(self):
        """Test when price equals intrinsic value."""
        result = ValuationCalculator.margin_of_safety(
            intrinsic_value=100.0, current_price=100.0
        )
        assert result["margin_of_safety_pct"] == 0.0
        assert result["upside_potential_pct"] == 0.0

    def test_invalid_intrinsic_value(self):
        """Test with zero or negative intrinsic value."""
        result = ValuationCalculator.margin_of_safety(
            intrinsic_value=0, current_price=50.0
        )
        assert result["margin_of_safety_pct"] == 0.0
        assert result["is_undervalued"] is False


class TestValuationCalculatorComposite:
    """Test composite valuation method."""

    def test_equal_weights(self):
        """Test composite with equal weights."""
        valuations = [
            ValuationResult(method="PE", value=100.0, inputs={}),
            ValuationResult(method="Graham", value=120.0, inputs={}),
            ValuationResult(method="BV", value=80.0, inputs={}),
        ]
        result = ValuationCalculator.composite_valuation(valuations)
        assert result["composite_value"] == 100.0  # Average
        assert result["methods_used"] == 3

    def test_custom_weights(self):
        """Test composite with custom weights."""
        valuations = [
            ValuationResult(method="PE", value=100.0, inputs={}),
            ValuationResult(method="Graham", value=200.0, inputs={}),
        ]
        result = ValuationCalculator.composite_valuation(
            valuations, weights=[0.75, 0.25]
        )
        assert result["composite_value"] == 125.0  # 100*0.75 + 200*0.25

    def test_excludes_zero_values(self):
        """Test that zero values are excluded."""
        valuations = [
            ValuationResult(method="PE", value=100.0, inputs={}),
            ValuationResult(method="Graham", value=0.0, inputs={}),  # Excluded
        ]
        result = ValuationCalculator.composite_valuation(valuations)
        assert result["composite_value"] == 100.0
        assert result["methods_used"] == 1

    def test_all_invalid_valuations(self):
        """Test with all zero valuations."""
        valuations = [
            ValuationResult(method="PE", value=0.0, inputs={}),
            ValuationResult(method="Graham", value=0.0, inputs={}),
        ]
        result = ValuationCalculator.composite_valuation(valuations)
        assert result["composite_value"] == 0.0
        assert result["methods_used"] == 0


class TestRatioCalculatorLiquidity:
    """Test liquidity ratio calculations."""

    def test_current_ratio(self):
        """Test current ratio calculation."""
        ratio = RatioCalculator.current_ratio(
            current_assets=200000, current_liabilities=100000
        )
        assert ratio == 2.0

    def test_current_ratio_zero_liabilities(self):
        """Test current ratio with zero liabilities."""
        ratio = RatioCalculator.current_ratio(
            current_assets=100000, current_liabilities=0
        )
        assert ratio == float("inf")

    def test_quick_ratio(self):
        """Test quick ratio calculation."""
        ratio = RatioCalculator.quick_ratio(
            current_assets=200000, inventory=50000, current_liabilities=100000
        )
        assert ratio == 1.5

    def test_quick_ratio_zero_liabilities(self):
        """Test quick ratio with zero liabilities."""
        ratio = RatioCalculator.quick_ratio(
            current_assets=100000, inventory=20000, current_liabilities=0
        )
        assert ratio == float("inf")


class TestRatioCalculatorLeverage:
    """Test leverage ratio calculations."""

    def test_debt_to_equity(self):
        """Test debt to equity calculation."""
        ratio = RatioCalculator.debt_to_equity(total_debt=500000, total_equity=1000000)
        assert ratio == 0.5

    def test_debt_to_equity_zero_equity(self):
        """Test debt to equity with zero equity."""
        ratio = RatioCalculator.debt_to_equity(total_debt=500000, total_equity=0)
        assert ratio == float("inf")

    def test_debt_to_assets(self):
        """Test debt to assets calculation."""
        ratio = RatioCalculator.debt_to_assets(total_debt=400000, total_assets=1000000)
        assert ratio == 0.4

    def test_interest_coverage(self):
        """Test interest coverage calculation."""
        ratio = RatioCalculator.interest_coverage(ebit=200000, interest_expense=50000)
        assert ratio == 4.0

    def test_interest_coverage_zero_expense(self):
        """Test interest coverage with zero interest."""
        ratio = RatioCalculator.interest_coverage(ebit=200000, interest_expense=0)
        assert ratio == float("inf")


class TestRatioCalculatorProfitability:
    """Test profitability ratio calculations."""

    def test_return_on_equity(self):
        """Test ROE calculation."""
        ratio = RatioCalculator.return_on_equity(
            net_income=100000, shareholder_equity=500000
        )
        assert ratio == 20.0  # 20%

    def test_return_on_equity_zero_equity(self):
        """Test ROE with zero equity."""
        ratio = RatioCalculator.return_on_equity(net_income=100000, shareholder_equity=0)
        assert ratio == 0.0

    def test_return_on_assets(self):
        """Test ROA calculation."""
        ratio = RatioCalculator.return_on_assets(net_income=100000, total_assets=1000000)
        assert ratio == 10.0  # 10%

    def test_profit_margin(self):
        """Test profit margin calculation."""
        ratio = RatioCalculator.profit_margin(net_income=50000, revenue=500000)
        assert ratio == 10.0  # 10%

    def test_profit_margin_zero_revenue(self):
        """Test profit margin with zero revenue."""
        ratio = RatioCalculator.profit_margin(net_income=50000, revenue=0)
        assert ratio == 0.0

    def test_operating_margin(self):
        """Test operating margin calculation."""
        ratio = RatioCalculator.operating_margin(operating_income=75000, revenue=500000)
        assert ratio == 15.0  # 15%

    def test_gross_margin(self):
        """Test gross margin calculation."""
        ratio = RatioCalculator.gross_margin(gross_profit=200000, revenue=500000)
        assert ratio == 40.0  # 40%


class TestRatioCalculatorEfficiency:
    """Test efficiency ratio calculations."""

    def test_asset_turnover(self):
        """Test asset turnover calculation."""
        ratio = RatioCalculator.asset_turnover(revenue=2000000, total_assets=1000000)
        assert ratio == 2.0

    def test_asset_turnover_zero_assets(self):
        """Test asset turnover with zero assets."""
        ratio = RatioCalculator.asset_turnover(revenue=2000000, total_assets=0)
        assert ratio == 0.0

    def test_inventory_turnover(self):
        """Test inventory turnover calculation."""
        ratio = RatioCalculator.inventory_turnover(
            cost_of_goods_sold=600000, average_inventory=100000
        )
        assert ratio == 6.0


class TestRatioCalculatorMarket:
    """Test market ratio calculations."""

    def test_price_to_earnings(self):
        """Test P/E ratio calculation."""
        ratio = RatioCalculator.price_to_earnings(price=100.0, eps=5.0)
        assert ratio == 20.0

    def test_price_to_earnings_zero_eps(self):
        """Test P/E with zero or negative EPS."""
        ratio = RatioCalculator.price_to_earnings(price=100.0, eps=0)
        assert ratio == float("inf")

    def test_price_to_book(self):
        """Test P/B ratio calculation."""
        ratio = RatioCalculator.price_to_book(price=60.0, book_value_per_share=40.0)
        assert ratio == 1.5

    def test_dividend_yield(self):
        """Test dividend yield calculation."""
        ratio = RatioCalculator.dividend_yield(annual_dividend=4.0, price=100.0)
        assert ratio == 4.0  # 4%

    def test_earnings_yield(self):
        """Test earnings yield calculation."""
        ratio = RatioCalculator.earnings_yield(eps=5.0, price=100.0)
        assert ratio == 5.0  # 5%


class TestDetectRedFlags:
    """Test red flag detection."""

    def test_low_current_ratio(self):
        """Test low current ratio is flagged."""
        flags = detect_red_flags(current_ratio=0.8)
        assert any("current ratio" in f.lower() for f in flags)

    def test_low_quick_ratio(self):
        """Test very low quick ratio is flagged."""
        flags = detect_red_flags(quick_ratio=0.4)
        assert any("quick ratio" in f.lower() for f in flags)

    def test_high_debt_to_equity(self):
        """Test high debt to equity is flagged."""
        flags = detect_red_flags(debt_to_equity=2.5)
        assert any("debt-to-equity" in f.lower() for f in flags)

    def test_low_interest_coverage(self):
        """Test low interest coverage is flagged."""
        flags = detect_red_flags(interest_coverage=1.5)
        assert any("interest coverage" in f.lower() for f in flags)

    def test_negative_profit_margin(self):
        """Test negative profit margin is flagged."""
        flags = detect_red_flags(profit_margin=-5.0)
        assert any("profit margin" in f.lower() for f in flags)

    def test_low_roe(self):
        """Test low ROE is flagged."""
        flags = detect_red_flags(roe=3.0)
        assert any("roe" in f.lower() for f in flags)

    def test_declining_revenue(self):
        """Test declining revenue is flagged."""
        flags = detect_red_flags(revenue_growth=-15.0)
        assert any("revenue" in f.lower() for f in flags)

    def test_declining_earnings(self):
        """Test declining earnings is flagged."""
        flags = detect_red_flags(earnings_growth=-25.0)
        assert any("earnings" in f.lower() for f in flags)

    def test_healthy_metrics_no_flags(self):
        """Test healthy metrics produce no flags."""
        flags = detect_red_flags(
            current_ratio=2.0,
            quick_ratio=1.5,
            debt_to_equity=0.5,
            interest_coverage=10.0,
            profit_margin=15.0,
            roe=20.0,
            revenue_growth=10.0,
            earnings_growth=15.0,
        )
        assert len(flags) == 0


class TestDetectStrengths:
    """Test strength detection."""

    def test_strong_current_ratio(self):
        """Test strong current ratio is detected."""
        strengths = detect_strengths(current_ratio=2.5)
        assert any("current ratio" in s.lower() for s in strengths)

    def test_low_debt(self):
        """Test low debt is detected."""
        strengths = detect_strengths(debt_to_equity=0.3)
        assert any("debt-to-equity" in s.lower() for s in strengths)

    def test_excellent_interest_coverage(self):
        """Test excellent interest coverage is detected."""
        strengths = detect_strengths(interest_coverage=15.0)
        assert any("interest coverage" in s.lower() for s in strengths)

    def test_high_profit_margin(self):
        """Test high profit margin is detected."""
        strengths = detect_strengths(profit_margin=20.0)
        assert any("profit margin" in s.lower() for s in strengths)

    def test_strong_roe(self):
        """Test strong ROE is detected."""
        strengths = detect_strengths(roe=20.0)
        assert any("roe" in s.lower() for s in strengths)

    def test_strong_revenue_growth(self):
        """Test strong revenue growth is detected."""
        strengths = detect_strengths(revenue_growth=20.0)
        assert any("revenue growth" in s.lower() for s in strengths)

    def test_weak_metrics_no_strengths(self):
        """Test weak metrics produce no strengths."""
        strengths = detect_strengths(
            current_ratio=1.0,
            debt_to_equity=1.0,
            interest_coverage=5.0,
            profit_margin=5.0,
            roe=10.0,
            revenue_growth=5.0,
        )
        assert len(strengths) == 0
