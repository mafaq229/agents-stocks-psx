"""Tests for number parsing utilities."""

import pytest

from psx.utils.parsers import (
    parse_price,
    parse_number,
    parse_negative,
    parse_percent,
    parse_date,
    parse_52_week_range,
    parse_change_with_percent,
    parse_volume,
    parse_shares,
    parse_market_cap,
)


class TestParsePrice:
    """Test parse_price function."""

    def test_simple_price(self):
        assert parse_price("5.17") == 5.17

    def test_price_with_rs_prefix(self):
        assert parse_price("Rs.5.17") == 5.17

    def test_price_with_rs_space(self):
        assert parse_price("Rs. 5.17") == 5.17

    def test_price_with_commas(self):
        assert parse_price("1,234.56") == 1234.56

    def test_price_with_rs_and_commas(self):
        assert parse_price("Rs.1,234.56") == 1234.56

    def test_price_empty_string(self):
        assert parse_price("") is None

    def test_price_whitespace(self):
        assert parse_price("   ") is None

    def test_price_none(self):
        assert parse_price(None) is None

    def test_price_invalid(self):
        assert parse_price("abc") is None

    def test_price_lowercase_rs(self):
        assert parse_price("rs.10.00") == 10.00


class TestParseNumber:
    """Test parse_number function."""

    def test_simple_number(self):
        assert parse_number("1234") == 1234.0

    def test_number_with_commas(self):
        assert parse_number("1,873,125.59") == 1873125.59

    def test_number_with_decimal(self):
        assert parse_number("18570325") == 18570325.0

    def test_number_large(self):
        assert parse_number("1,000,000,000") == 1000000000.0

    def test_number_empty(self):
        assert parse_number("") is None

    def test_number_whitespace(self):
        assert parse_number("  1,000  ") == 1000.0

    def test_number_invalid(self):
        assert parse_number("not a number") is None


class TestParseNegative:
    """Test parse_negative function for accounting-style negatives."""

    def test_positive_number(self):
        assert parse_negative("9,235") == 9235.0

    def test_negative_parentheses(self):
        assert parse_negative("(9,235)") == -9235.0

    def test_negative_decimal(self):
        assert parse_negative("(0.52)") == -0.52

    def test_positive_decimal(self):
        assert parse_negative("0.52") == 0.52

    def test_large_negative(self):
        assert parse_negative("(1,234,567.89)") == -1234567.89

    def test_empty_string(self):
        assert parse_negative("") is None

    def test_whitespace(self):
        assert parse_negative("  (100)  ") == -100.0


class TestParsePercent:
    """Test parse_percent function."""

    def test_positive_percent(self):
        assert parse_percent("50.60%") == 50.60

    def test_negative_percent(self):
        assert parse_percent("-9.14%") == -9.14

    def test_accounting_negative(self):
        assert parse_percent("(50.43)") == -50.43

    def test_percent_no_sign(self):
        assert parse_percent("50.60") == 50.60

    def test_zero_percent(self):
        assert parse_percent("0%") == 0.0

    def test_empty_string(self):
        assert parse_percent("") is None

    def test_with_commas(self):
        assert parse_percent("1,234.56%") == 1234.56


class TestParseDate:
    """Test parse_date function."""

    def test_format_mmm_dd_yyyy(self):
        assert parse_date("Nov 10, 2025") == "2025-11-10"

    def test_format_yyyy_mm_dd(self):
        assert parse_date("2025-09-30") == "2025-09-30"

    def test_format_dd_mmm_yyyy(self):
        assert parse_date("10 Nov 2025") == "2025-11-10"

    def test_format_dd_mm_yyyy_slash(self):
        assert parse_date("10/11/2025") == "2025-11-10"

    def test_format_full_month(self):
        assert parse_date("November 10, 2025") == "2025-11-10"

    def test_format_dd_mm_yyyy_dash(self):
        assert parse_date("10-11-2025") == "2025-11-10"

    def test_empty_string(self):
        assert parse_date("") is None

    def test_whitespace(self):
        assert parse_date("   Nov 10, 2025   ") == "2025-11-10"

    def test_unparseable_returns_original(self):
        assert parse_date("Q1 2025") == "Q1 2025"


class TestParse52WeekRange:
    """Test parse_52_week_range function."""

    def test_em_dash_separator(self):
        low, high = parse_52_week_range("3.91—10.23")
        assert low == 3.91
        assert high == 10.23

    def test_hyphen_separator(self):
        low, high = parse_52_week_range("3.91-10.23")
        assert low == 3.91
        assert high == 10.23

    def test_spaced_separator(self):
        low, high = parse_52_week_range("3.91 - 10.23")
        assert low == 3.91
        assert high == 10.23

    def test_large_numbers(self):
        low, high = parse_52_week_range("100.50—200.75")
        assert low == 100.50
        assert high == 200.75

    def test_empty_string(self):
        low, high = parse_52_week_range("")
        assert low is None
        assert high is None

    def test_invalid_format(self):
        low, high = parse_52_week_range("not a range")
        assert low is None
        assert high is None

    def test_en_dash_separator(self):
        low, high = parse_52_week_range("50.00–100.00")
        assert low == 50.00
        assert high == 100.00


class TestParseChangeWithPercent:
    """Test parse_change_with_percent function."""

    def test_negative_change(self):
        change, pct = parse_change_with_percent("-0.52 (-9.14%)")
        assert change == -0.52
        assert pct == -9.14

    def test_positive_change(self):
        change, pct = parse_change_with_percent("+1.23 (+5.67%)")
        assert change == 1.23
        assert pct == 5.67

    def test_zero_change(self):
        change, pct = parse_change_with_percent("0.00 (0.00%)")
        assert change == 0.0
        assert pct == 0.0

    def test_without_plus_sign(self):
        change, pct = parse_change_with_percent("1.23 (5.67%)")
        assert change == 1.23
        assert pct == 5.67

    def test_empty_string(self):
        change, pct = parse_change_with_percent("")
        assert change is None
        assert pct is None

    def test_invalid_format(self):
        change, pct = parse_change_with_percent("not a change")
        assert change is None
        assert pct is None

    def test_large_numbers(self):
        change, pct = parse_change_with_percent("-10,000.50 (-25.5%)")
        # Note: parse_change_with_percent uses parse_negative which handles commas
        assert pct == -25.5


class TestParseVolume:
    """Test parse_volume function."""

    def test_simple_volume(self):
        assert parse_volume("18570325") == 18570325

    def test_volume_with_commas(self):
        assert parse_volume("18,570,325") == 18570325

    def test_large_volume(self):
        assert parse_volume("1,000,000,000") == 1000000000

    def test_empty_string(self):
        assert parse_volume("") is None

    def test_whitespace(self):
        assert parse_volume("  1,000,000  ") == 1000000

    def test_decimal_truncation(self):
        # Volume should be integer, decimals truncated
        assert parse_volume("1000.5") == 1000


class TestParseShares:
    """Test parse_shares function."""

    def test_simple_shares(self):
        assert parse_shares("362306690") == 362306690

    def test_shares_with_commas(self):
        assert parse_shares("362,306,690") == 362306690

    def test_empty_string(self):
        assert parse_shares("") is None


class TestParseMarketCap:
    """Test parse_market_cap function."""

    def test_simple_market_cap(self):
        assert parse_market_cap("1873125.59") == 1873125.59

    def test_market_cap_with_commas(self):
        assert parse_market_cap("1,873,125.59") == 1873125.59

    def test_empty_string(self):
        assert parse_market_cap("") is None

    def test_large_market_cap(self):
        assert parse_market_cap("1,000,000,000,000") == 1000000000000.0
