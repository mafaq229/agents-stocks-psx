"""Tests for core data models."""

import pytest
from datetime import datetime

from psx.core.models import (
    QuoteData,
    CompanyData,
    EquityData,
    FinancialRow,
    RatioRow,
    AnnouncementData,
    ReportData,
    DividendData,
    ScrapedData,
)


class TestQuoteData:
    """Test QuoteData dataclass."""

    def test_instantiation_with_defaults(self):
        """Test creating QuoteData with default values."""
        quote = QuoteData()
        assert quote.price is None
        assert quote.change is None
        assert quote.volume is None

    def test_instantiation_with_values(self):
        """Test creating QuoteData with all values."""
        quote = QuoteData(
            price=100.50,
            change=2.25,
            change_pct=2.29,
            volume=1000000,
            open=99.00,
            high=101.00,
            low=98.50,
            ldcp=98.25,
            week_52_high=120.00,
            week_52_low=80.00,
            pe_ratio=15.5,
            ytd_change_pct=25.0,
            year_change_pct=30.0,
        )
        assert quote.price == 100.50
        assert quote.pe_ratio == 15.5

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        quote = QuoteData(price=100.50, volume=1000)
        result = quote.to_dict()
        assert "price" in result
        assert "volume" in result
        assert "change" not in result  # None values excluded
        assert "pe_ratio" not in result

    def test_to_dict_includes_all_set_values(self):
        """Test to_dict includes all non-None values."""
        quote = QuoteData(price=50.0, change=-1.5, change_pct=-2.9)
        result = quote.to_dict()
        assert result["price"] == 50.0
        assert result["change"] == -1.5
        assert result["change_pct"] == -2.9


class TestCompanyData:
    """Test CompanyData dataclass."""

    def test_instantiation_required_field(self):
        """Test symbol is required."""
        company = CompanyData(symbol="OGDC")
        assert company.symbol == "OGDC"
        assert company.name is None

    def test_instantiation_all_fields(self):
        """Test all optional fields."""
        company = CompanyData(
            symbol="OGDC",
            name="Oil & Gas Development Company",
            sector="Oil & Gas",
            description="Energy company",
            ceo="John Doe",
            chairperson="Jane Smith",
            company_secretary="Bob Wilson",
            auditor="KPMG",
            registrar="CDC",
            fiscal_year_end="June",
            website="https://ogdc.com",
            address="Islamabad",
        )
        assert company.name == "Oil & Gas Development Company"
        assert company.sector == "Oil & Gas"
        assert company.ceo == "John Doe"

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        company = CompanyData(symbol="TEST", name="Test Company")
        result = company.to_dict()
        assert "symbol" in result
        assert "name" in result
        assert "ceo" not in result


class TestEquityData:
    """Test EquityData dataclass."""

    def test_instantiation_defaults(self):
        """Test default values."""
        equity = EquityData()
        assert equity.market_cap is None
        assert equity.shares_outstanding is None

    def test_instantiation_with_values(self):
        """Test with all values."""
        equity = EquityData(
            market_cap=1000000000.0,
            shares_outstanding=100000000,
            free_float_shares=60000000,
            free_float_pct=60.0,
        )
        assert equity.market_cap == 1000000000.0
        assert equity.free_float_pct == 60.0

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        equity = EquityData(market_cap=1000000.0)
        result = equity.to_dict()
        assert "market_cap" in result
        assert "shares_outstanding" not in result


class TestFinancialRow:
    """Test FinancialRow dataclass."""

    def test_instantiation(self):
        """Test creating financial row."""
        row = FinancialRow(
            period="2025",
            period_type="annual",
            metric="Revenue",
            value=1000000.0,
            raw_value="1,000,000",
        )
        assert row.period == "2025"
        assert row.period_type == "annual"
        assert row.metric == "Revenue"
        assert row.value == 1000000.0

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all fields (including None)."""
        row = FinancialRow(
            period="2025",
            period_type="annual",
            metric="EPS",
            value=2.50,
        )
        result = row.to_dict()
        assert result["period"] == "2025"
        assert result["period_type"] == "annual"
        assert result["metric"] == "EPS"
        assert result["value"] == 2.50
        assert result["raw_value"] is None  # Included even if None


class TestRatioRow:
    """Test RatioRow dataclass."""

    def test_instantiation(self):
        """Test creating ratio row."""
        row = RatioRow(
            period="2025",
            metric="Net Profit Margin",
            value=15.5,
        )
        assert row.period == "2025"
        assert row.metric == "Net Profit Margin"
        assert row.value == 15.5

    def test_to_dict(self):
        """Test to_dict returns all fields."""
        row = RatioRow(period="2024", metric="ROE", value=20.0, raw_value="20%")
        result = row.to_dict()
        assert result["period"] == "2024"
        assert result["metric"] == "ROE"
        assert result["value"] == 20.0
        assert result["raw_value"] == "20%"


class TestAnnouncementData:
    """Test AnnouncementData dataclass."""

    def test_instantiation(self):
        """Test creating announcement."""
        ann = AnnouncementData(
            date="2025-01-15",
            title="Board Meeting Notice",
            category="board_meetings",
            url="https://example.com/ann.pdf",
        )
        assert ann.date == "2025-01-15"
        assert ann.title == "Board Meeting Notice"
        assert ann.category == "board_meetings"

    def test_to_dict(self):
        """Test to_dict returns all fields."""
        ann = AnnouncementData(date="2025-01-15", title="Test")
        result = ann.to_dict()
        assert result["date"] == "2025-01-15"
        assert result["title"] == "Test"
        assert result["category"] is None
        assert result["url"] is None


class TestReportData:
    """Test ReportData dataclass."""

    def test_instantiation(self):
        """Test creating report."""
        report = ReportData(
            report_type="annual",
            period="2025",
            url="https://example.com/report.pdf",
        )
        assert report.report_type == "annual"
        assert report.period == "2025"
        assert report.is_downloaded is False
        assert report.is_parsed is False

    def test_to_dict(self):
        """Test to_dict returns all fields."""
        report = ReportData(
            report_type="quarterly",
            period="Q1 2025",
            url="https://example.com/q1.pdf",
            local_path="/data/q1.pdf",
            is_downloaded=True,
        )
        result = report.to_dict()
        assert result["report_type"] == "quarterly"
        assert result["is_downloaded"] is True
        assert result["is_parsed"] is False


class TestDividendData:
    """Test DividendData dataclass."""

    def test_instantiation_defaults(self):
        """Test default values."""
        div = DividendData()
        assert div.announcement_date is None
        assert div.amount is None

    def test_instantiation_with_values(self):
        """Test with values."""
        div = DividendData(
            announcement_date="2025-01-15",
            ex_date="2025-02-01",
            record_date="2025-02-03",
            payment_date="2025-02-15",
            dividend_type="cash",
            amount=5.0,
            percentage=25.0,
        )
        assert div.dividend_type == "cash"
        assert div.amount == 5.0

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        div = DividendData(amount=5.0, dividend_type="cash")
        result = div.to_dict()
        assert "amount" in result
        assert "dividend_type" in result
        assert "ex_date" not in result


class TestScrapedData:
    """Test ScrapedData dataclass."""

    def test_instantiation_minimal(self):
        """Test creating with minimal data."""
        data = ScrapedData(symbol="TEST")
        assert data.symbol == "TEST"
        assert data.scraped_at is not None  # Auto-generated
        assert data.quote is None
        assert data.company is None
        assert data.financials == {}
        assert data.ratios == []

    def test_instantiation_full(self):
        """Test creating with full data."""
        data = ScrapedData(
            symbol="TEST",
            source_url="https://dps.psx.com.pk/company/TEST",
            quote=QuoteData(price=100.0),
            company=CompanyData(symbol="TEST", name="Test Company"),
            equity=EquityData(market_cap=1000000.0),
            financials={
                "annual": [FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000.0)]
            },
            ratios=[RatioRow(period="2025", metric="PE", value=15.0)],
            announcements={
                "others": [AnnouncementData(date="2025-01-15", title="Test")]
            },
            reports=[ReportData(report_type="annual", period="2025", url="https://example.com/report.pdf")],
            dividends=[DividendData(amount=5.0)],
            risk_flags={"high_debt": True},
        )
        assert data.quote.price == 100.0
        assert data.company.name == "Test Company"
        assert len(data.financials["annual"]) == 1
        assert len(data.ratios) == 1

    def test_scraped_at_auto_generated(self):
        """Test scraped_at is auto-generated with ISO format."""
        data = ScrapedData(symbol="TEST")
        # Should be a valid ISO timestamp ending with Z
        assert data.scraped_at.endswith("Z")
        # Should be parseable
        datetime.fromisoformat(data.scraped_at.replace("Z", "+00:00"))

    def test_to_dict_structure(self):
        """Test to_dict returns correct structure."""
        data = ScrapedData(
            symbol="TEST",
            quote=QuoteData(price=100.0),
            company=CompanyData(symbol="TEST", name="Test Co"),
        )
        result = data.to_dict()

        # Check _meta section
        assert "_meta" in result
        assert result["_meta"]["symbol"] == "TEST"
        assert "scraped_at" in result["_meta"]

        # Check nested objects
        assert "quote" in result
        assert result["quote"]["price"] == 100.0

        assert "company" in result
        assert result["company"]["symbol"] == "TEST"
        assert result["company"]["name"] == "Test Co"

    def test_to_dict_nested_financials(self):
        """Test to_dict serializes nested financials correctly."""
        data = ScrapedData(
            symbol="TEST",
            financials={
                "annual": [
                    FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000.0),
                    FinancialRow(period="2024", period_type="annual", metric="Revenue", value=900.0),
                ],
                "quarterly": [
                    FinancialRow(period="Q1 2025", period_type="quarterly", metric="Revenue", value=250.0),
                ],
            },
        )
        result = data.to_dict()

        assert "financials" in result
        assert "annual" in result["financials"]
        assert "quarterly" in result["financials"]
        assert len(result["financials"]["annual"]) == 2
        assert result["financials"]["annual"][0]["metric"] == "Revenue"

    def test_to_dict_nested_announcements(self):
        """Test to_dict serializes nested announcements correctly."""
        data = ScrapedData(
            symbol="TEST",
            announcements={
                "board_meetings": [
                    AnnouncementData(date="2025-01-15", title="Board Meeting", category="board_meetings"),
                ],
                "financial_results": [
                    AnnouncementData(date="2025-01-20", title="Q4 Results", category="financial_results"),
                ],
            },
        )
        result = data.to_dict()

        assert "announcements" in result
        assert "board_meetings" in result["announcements"]
        assert "financial_results" in result["announcements"]
        assert result["announcements"]["board_meetings"][0]["title"] == "Board Meeting"

    def test_to_dict_empty_nested_objects(self):
        """Test to_dict handles empty nested objects."""
        data = ScrapedData(symbol="TEST")
        result = data.to_dict()

        assert result["quote"] == {}
        assert result["company"] == {}
        assert result["equity"] == {}
        assert result["financials"] == {}
        assert result["ratios"] == []
        assert result["announcements"] == {}
        assert result["reports"] == []
        assert result["dividends"] == []
        assert result["risk_flags"] == {}
