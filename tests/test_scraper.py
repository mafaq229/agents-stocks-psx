"""Tests for PSX web scraper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from psx.scraper.psx_scraper import PSXScraper
from psx.core.models import QuoteData, CompanyData, EquityData, FinancialRow, RatioRow
from psx.core.exceptions import ScraperError


class TestPSXScraper:
    """Test PSXScraper class."""

    def test_instantiation_defaults(self):
        """Test scraper instantiation with default values."""
        scraper = PSXScraper()
        assert scraper.headless is True

    def test_instantiation_headless_false(self):
        """Test scraper instantiation with headless=False."""
        scraper = PSXScraper(headless=False)
        assert scraper.headless is False

    def test_base_url(self):
        """Test base URL is correct."""
        assert PSXScraper.BASE_URL == "https://dps.psx.com.pk/company/"


class TestParseFinancialRows:
    """Test _parse_financial_rows helper method."""

    def test_parse_annual_rows(self):
        """Test parsing annual financial data."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "Revenue", "2025": "1,000,000", "2024": "900,000"},
            {"Metric": "Profit", "2025": "100,000", "2024": "80,000"},
        ]
        rows = scraper._parse_financial_rows(table_data, "annual")

        assert len(rows) == 4  # 2 metrics × 2 periods
        assert all(r.period_type == "annual" for r in rows)
        assert any(r.metric == "Revenue" and r.period == "2025" for r in rows)

    def test_parse_quarterly_rows(self):
        """Test parsing quarterly financial data."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "Revenue", "Q1 2025": "250,000", "Q4 2024": "200,000"},
        ]
        rows = scraper._parse_financial_rows(table_data, "quarterly")

        assert len(rows) == 2
        assert all(r.period_type == "quarterly" for r in rows)

    def test_parse_negative_values(self):
        """Test parsing negative values in parentheses."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "Loss", "2025": "(500,000)"},
        ]
        rows = scraper._parse_financial_rows(table_data, "annual")

        assert len(rows) == 1
        assert rows[0].value == -500000.0

    def test_skip_empty_metric(self):
        """Test rows with empty metric are skipped."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "", "2025": "100"},
            {"Metric": "Revenue", "2025": "200"},
        ]
        rows = scraper._parse_financial_rows(table_data, "annual")

        assert len(rows) == 1
        assert rows[0].metric == "Revenue"


class TestParseRatioRows:
    """Test _parse_ratio_rows helper method."""

    def test_parse_ratio_rows(self):
        """Test parsing ratio data."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "ROE", "2025": "15.5%", "2024": "12.3%"},
            {"Metric": "Profit Margin", "2025": "10%", "2024": "8%"},
        ]
        rows = scraper._parse_ratio_rows(table_data)

        assert len(rows) == 4  # 2 metrics × 2 periods
        assert any(r.metric == "ROE" and r.period == "2025" for r in rows)

    def test_parse_ratio_decimal(self):
        """Test parsing decimal ratio values."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "EPS Growth", "2025": "25.75%"},
        ]
        rows = scraper._parse_ratio_rows(table_data)

        assert len(rows) == 1
        assert rows[0].value == pytest.approx(25.75)


class TestScraperError:
    """Test scraper error handling."""

    def test_scraper_error_with_context(self):
        """Test ScraperError includes context."""
        error = ScraperError(
            "Failed to load",
            symbol="OGDC",
            url="https://dps.psx.com.pk/company/OGDC",
        )
        assert error.symbol == "OGDC"
        assert error.url == "https://dps.psx.com.pk/company/OGDC"
        assert "Failed to load" in str(error)


class TestScrapeCompanyMocked:
    """Test scrape_company with mocked Playwright."""

    @pytest.mark.asyncio
    async def test_scrape_company_page_not_found(self):
        """Test scrape_company raises error on 404."""
        scraper = PSXScraper()

        # Create mock response
        mock_response = MagicMock()
        mock_response.status = 404

        # Create mock page
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=mock_response)

        # Create mock browser
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()

        # Create mock playwright context
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch("psx.scraper.psx_scraper.async_playwright") as mock_ap:
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_playwright)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            mock_ap.return_value = mock_context_manager

            with pytest.raises(ScraperError) as exc_info:
                await scraper.scrape_company("INVALID")

            assert "404" in str(exc_info.value) or "Failed" in str(exc_info.value)


class TestScraperHelperMethods:
    """Test scraper helper methods that don't require browser."""

    def test_parse_financial_rows_preserves_raw(self):
        """Test raw_value is preserved."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "Revenue", "2025": "1,234,567"},
        ]
        rows = scraper._parse_financial_rows(table_data, "annual")

        assert rows[0].raw_value == "1,234,567"

    def test_parse_ratio_rows_preserves_raw(self):
        """Test raw_value is preserved in ratios."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "PE Ratio", "2025": "15.5%"},
        ]
        rows = scraper._parse_ratio_rows(table_data)

        assert rows[0].raw_value == "15.5%"

    def test_parse_financial_rows_multiple_periods(self):
        """Test parsing multiple time periods."""
        scraper = PSXScraper()
        table_data = [
            {"Metric": "Revenue", "2025": "100", "2024": "90", "2023": "80", "2022": "70"},
        ]
        rows = scraper._parse_financial_rows(table_data, "annual")

        assert len(rows) == 4
        periods = [r.period for r in rows]
        assert "2025" in periods
        assert "2024" in periods
        assert "2023" in periods
        assert "2022" in periods
