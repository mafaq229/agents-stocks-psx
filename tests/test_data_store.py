"""Tests for DataStore class."""

import pytest
import tempfile
import os
import json
from pathlib import Path
from datetime import date

from psx.storage.data_store import DataStore
from psx.storage.database import init_database
from psx.core.models import (
    CompanyData,
    QuoteData,
    EquityData,
    FinancialRow,
    RatioRow,
    AnnouncementData,
    ReportData,
    ScrapedData,
)


class TestDataStore:
    """Test DataStore class functionality."""

    @pytest.fixture
    def store(self):
        """Create a DataStore with temporary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "db", "test.db")
            cache_dir = os.path.join(tmpdir, "cache")
            docs_dir = os.path.join(tmpdir, "documents")
            migrations_dir = Path(__file__).parent.parent / "data" / "migrations"

            # Initialize database with migrations
            if migrations_dir.exists():
                init_database(db_path, str(migrations_dir))

            # Reset global db state for clean tests
            import psx.storage.database as db_module
            db_module._db = None

            store = DataStore(
                db_path=db_path,
                cache_dir=cache_dir,
                documents_dir=docs_dir,
            )
            yield store
            store.db.close()
            db_module._db = None

    # ========== COMPANY OPERATIONS ==========

    def test_save_company(self, store):
        """Test saving a company."""
        company = CompanyData(
            symbol="TEST",
            name="Test Company",
            sector="Technology",
            description="A test company",
        )
        company_id = store.save_company(company)
        assert company_id is not None
        assert company_id > 0

    def test_save_company_upsert(self, store):
        """Test that saving same company updates it."""
        company1 = CompanyData(symbol="TEST", name="Original Name")
        id1 = store.save_company(company1)

        company2 = CompanyData(symbol="TEST", name="Updated Name")
        id2 = store.save_company(company2)

        assert id1 == id2

        retrieved = store.get_company("TEST")
        assert retrieved.name == "Updated Name"

    def test_get_company(self, store):
        """Test retrieving a company."""
        company = CompanyData(
            symbol="TEST",
            name="Test Company",
            sector="Finance",
            ceo="John Doe",
        )
        store.save_company(company)

        retrieved = store.get_company("TEST")
        assert retrieved is not None
        assert retrieved.symbol == "TEST"
        assert retrieved.name == "Test Company"
        assert retrieved.sector == "Finance"
        assert retrieved.ceo == "John Doe"

    def test_get_company_not_found(self, store):
        """Test retrieving non-existent company returns None."""
        result = store.get_company("NONEXISTENT")
        assert result is None

    def test_get_company_id(self, store):
        """Test getting company ID by symbol."""
        company = CompanyData(symbol="TEST")
        expected_id = store.save_company(company)

        actual_id = store.get_company_id("TEST")
        assert actual_id == expected_id

    def test_get_company_id_not_found(self, store):
        """Test getting company ID for non-existent company."""
        result = store.get_company_id("NONEXISTENT")
        assert result is None

    def test_list_companies(self, store):
        """Test listing all companies."""
        store.save_company(CompanyData(symbol="AAA"))
        store.save_company(CompanyData(symbol="BBB"))
        store.save_company(CompanyData(symbol="CCC"))

        symbols = store.list_companies()
        assert symbols == ["AAA", "BBB", "CCC"]  # Should be sorted

    def test_list_companies_empty(self, store):
        """Test listing companies when none exist."""
        symbols = store.list_companies()
        assert symbols == []

    def test_get_companies_by_sector(self, store):
        """Test getting companies by sector."""
        store.save_company(CompanyData(symbol="A1", sector="Tech"))
        store.save_company(CompanyData(symbol="A2", sector="Tech"))
        store.save_company(CompanyData(symbol="B1", sector="Finance"))

        tech_companies = store.get_companies_by_sector("Tech")
        assert len(tech_companies) == 2
        assert all(c.sector == "Tech" for c in tech_companies)

    # ========== QUOTE OPERATIONS ==========

    def test_save_quote(self, store):
        """Test saving a quote."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        quote = QuoteData(price=10.50, change=0.25, change_pct=2.5, volume=1000000)

        # Should not raise
        store.save_quote(company_id, quote)

    def test_save_quote_with_equity(self, store):
        """Test saving quote with equity data."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        quote = QuoteData(price=10.50)
        equity = EquityData(market_cap=1000000000, shares_outstanding=100000000)

        store.save_quote(company_id, quote, equity)

        # Verify by getting latest quote
        latest = store.get_latest_quote("TEST")
        assert latest.price == 10.50

    def test_save_quote_specific_date(self, store):
        """Test saving quote for specific date."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        quote = QuoteData(price=10.50)

        store.save_quote(company_id, quote, quote_date=date(2025, 1, 15))

    def test_save_quote_upsert(self, store):
        """Test that saving quote for same date updates it."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        today = date.today()

        quote1 = QuoteData(price=10.00)
        store.save_quote(company_id, quote1, quote_date=today)

        quote2 = QuoteData(price=11.00)
        store.save_quote(company_id, quote2, quote_date=today)

        latest = store.get_latest_quote("TEST")
        assert latest.price == 11.00

    def test_get_latest_quote(self, store):
        """Test getting latest quote."""
        company_id = store.save_company(CompanyData(symbol="TEST"))

        # Save multiple quotes
        store.save_quote(
            company_id, QuoteData(price=10.00), quote_date=date(2025, 1, 1)
        )
        store.save_quote(
            company_id, QuoteData(price=11.00), quote_date=date(2025, 1, 2)
        )
        store.save_quote(
            company_id, QuoteData(price=12.00), quote_date=date(2025, 1, 3)
        )

        latest = store.get_latest_quote("TEST")
        assert latest.price == 12.00

    def test_get_latest_quote_not_found(self, store):
        """Test getting latest quote for company with no quotes."""
        store.save_company(CompanyData(symbol="TEST"))
        result = store.get_latest_quote("TEST")
        assert result is None

    # ========== FINANCIAL OPERATIONS ==========

    def test_save_financials(self, store):
        """Test saving financial rows."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        financials = [
            FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000000),
            FinancialRow(period="2025", period_type="annual", metric="Profit", value=100000),
        ]

        store.save_financials(company_id, financials)

    def test_save_financials_upsert(self, store):
        """Test that saving financials updates existing rows."""
        company_id = store.save_company(CompanyData(symbol="TEST"))

        row1 = [FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000)]
        store.save_financials(company_id, row1)

        row2 = [FinancialRow(period="2025", period_type="annual", metric="Revenue", value=2000)]
        store.save_financials(company_id, row2)

        rows = store.get_financials("TEST")
        assert len(rows) == 1
        assert rows[0].value == 2000

    def test_get_financials(self, store):
        """Test getting all financials."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        financials = [
            FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000),
            FinancialRow(period="2024", period_type="annual", metric="Revenue", value=900),
        ]
        store.save_financials(company_id, financials)

        retrieved = store.get_financials("TEST")
        assert len(retrieved) == 2

    def test_get_financials_by_period_type(self, store):
        """Test filtering financials by period type."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        financials = [
            FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000),
            FinancialRow(period="Q1 2025", period_type="quarterly", metric="Revenue", value=250),
        ]
        store.save_financials(company_id, financials)

        annual = store.get_financials("TEST", period_type="annual")
        assert len(annual) == 1
        assert annual[0].period_type == "annual"

        quarterly = store.get_financials("TEST", period_type="quarterly")
        assert len(quarterly) == 1
        assert quarterly[0].period_type == "quarterly"

    def test_get_financials_by_metrics(self, store):
        """Test filtering financials by metric names."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        financials = [
            FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000),
            FinancialRow(period="2025", period_type="annual", metric="Profit", value=100),
            FinancialRow(period="2025", period_type="annual", metric="EPS", value=1.5),
        ]
        store.save_financials(company_id, financials)

        filtered = store.get_financials("TEST", metrics=["Revenue", "EPS"])
        assert len(filtered) == 2
        metrics = {r.metric for r in filtered}
        assert metrics == {"Revenue", "EPS"}

    # ========== RATIO OPERATIONS ==========

    def test_save_ratios(self, store):
        """Test saving ratio rows."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        ratios = [
            RatioRow(period="2025", metric="PE Ratio", value=15.5),
            RatioRow(period="2025", metric="ROE", value=12.3),
        ]

        store.save_ratios(company_id, ratios)

    def test_get_ratios(self, store):
        """Test getting ratios."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        ratios = [
            RatioRow(period="2025", metric="PE Ratio", value=15.5),
            RatioRow(period="2024", metric="PE Ratio", value=14.0),
        ]
        store.save_ratios(company_id, ratios)

        retrieved = store.get_ratios("TEST")
        assert len(retrieved) == 2

    # ========== ANNOUNCEMENT OPERATIONS ==========

    def test_save_announcement(self, store):
        """Test saving an announcement."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        ann = AnnouncementData(
            date="2025-01-15",
            title="Board Meeting Notice",
            category="board_meetings",
            url="https://example.com/ann.pdf",
        )

        store.save_announcement(company_id, ann)

    def test_save_announcement_deduplication(self, store):
        """Test that duplicate announcements are not saved."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        ann = AnnouncementData(
            date="2025-01-15",
            title="Board Meeting Notice",
            category="board_meetings",
            url="https://example.com/ann.pdf",
        )

        store.save_announcement(company_id, ann)
        store.save_announcement(company_id, ann)  # Duplicate

        retrieved = store.get_announcements("TEST")
        assert len(retrieved) == 1

    def test_get_announcements(self, store):
        """Test getting announcements."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        for i in range(5):
            ann = AnnouncementData(
                date=f"2025-01-{i+10}",
                title=f"Announcement {i}",
                category="others",
            )
            store.save_announcement(company_id, ann)

        retrieved = store.get_announcements("TEST")
        assert len(retrieved) == 5

    def test_get_announcements_by_category(self, store):
        """Test filtering announcements by category."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        store.save_announcement(
            company_id,
            AnnouncementData(date="2025-01-15", title="A1", category="financial_results"),
        )
        store.save_announcement(
            company_id,
            AnnouncementData(date="2025-01-16", title="A2", category="board_meetings"),
        )

        financial = store.get_announcements("TEST", category="financial_results")
        assert len(financial) == 1
        assert financial[0].category == "financial_results"

    def test_get_announcements_date_range(self, store):
        """Test filtering announcements by date range."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        dates = ["2025-01-01", "2025-01-15", "2025-02-01"]
        for d in dates:
            store.save_announcement(
                company_id,
                AnnouncementData(date=d, title=f"Ann {d}"),
            )

        filtered = store.get_announcements(
            "TEST", start_date="2025-01-10", end_date="2025-01-20"
        )
        assert len(filtered) == 1
        assert filtered[0].date == "2025-01-15"

    def test_get_announcements_limit(self, store):
        """Test limiting announcements."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        for i in range(10):
            store.save_announcement(
                company_id,
                AnnouncementData(date=f"2025-01-{i+10}", title=f"Ann {i}"),
            )

        limited = store.get_announcements("TEST", limit=5)
        assert len(limited) == 5

    # ========== REPORT OPERATIONS ==========

    def test_save_report(self, store):
        """Test saving a report."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        report = ReportData(
            report_type="annual",
            period="2025",
            url="https://example.com/report.pdf",
        )

        report_id = store.save_report(company_id, report)
        assert report_id > 0

    def test_save_report_upsert(self, store):
        """Test that saving same report updates it."""
        company_id = store.save_company(CompanyData(symbol="TEST"))

        report1 = ReportData(
            report_type="annual",
            period="2025",
            url="https://example.com/v1.pdf",
        )
        store.save_report(company_id, report1)

        report2 = ReportData(
            report_type="annual",
            period="2025",
            url="https://example.com/v2.pdf",
        )
        store.save_report(company_id, report2)

        reports = store.get_reports("TEST")
        assert len(reports) == 1
        assert reports[0].url == "https://example.com/v2.pdf"

    def test_get_reports(self, store):
        """Test getting reports."""
        company_id = store.save_company(CompanyData(symbol="TEST"))
        store.save_report(
            company_id,
            ReportData(report_type="annual", period="2025", url="url1"),
        )
        store.save_report(
            company_id,
            ReportData(report_type="quarterly", period="Q1 2025", url="url2"),
        )

        reports = store.get_reports("TEST")
        assert len(reports) == 2

    # ========== CACHE OPERATIONS ==========

    def test_save_cache(self, store):
        """Test saving to cache."""
        data = ScrapedData(
            symbol="TEST",
            quote=QuoteData(price=10.50),
            company=CompanyData(symbol="TEST", name="Test Co"),
        )

        path = store.save_cache("TEST", data)
        assert path.exists()
        assert path.name == "latest.json"

    def test_get_cache(self, store):
        """Test getting from cache."""
        data = ScrapedData(
            symbol="TEST",
            quote=QuoteData(price=10.50),
        )
        store.save_cache("TEST", data)

        cached = store.get_cache("TEST")
        assert cached is not None
        assert cached["quote"]["price"] == 10.50

    def test_get_cache_not_found(self, store):
        """Test getting non-existent cache."""
        result = store.get_cache("NONEXISTENT")
        assert result is None

    def test_cache_structure(self, store):
        """Test that cache has expected structure."""
        data = ScrapedData(
            symbol="TEST",
            quote=QuoteData(price=10.50),
            company=CompanyData(symbol="TEST"),
            financials={"annual": [FinancialRow(period="2025", period_type="annual", metric="EPS", value=1.5)]},
        )
        store.save_cache("TEST", data)

        cached = store.get_cache("TEST")
        assert "_meta" in cached
        assert cached["_meta"]["symbol"] == "TEST"
        assert "quote" in cached
        assert "company" in cached
        assert "financials" in cached

    # ========== SCRAPE LOG ==========

    def test_log_scrape(self, store):
        """Test logging a scrape."""
        store.save_company(CompanyData(symbol="TEST"))
        # Should not raise
        store.log_scrape("TEST", "https://example.com", "success")

    def test_log_scrape_with_error(self, store):
        """Test logging a failed scrape."""
        store.save_company(CompanyData(symbol="TEST"))
        store.log_scrape(
            "TEST",
            "https://example.com",
            "error",
            error_message="Connection timeout",
            duration_ms=5000,
        )

    def test_log_scrape_unknown_symbol(self, store):
        """Test logging scrape for unknown symbol (company_id will be None)."""
        # Should not raise even without company
        store.log_scrape("UNKNOWN", "https://example.com", "error", "Company not found")

    # ========== AGGREGATE QUERIES ==========

    def test_get_sector_averages(self, store):
        """Test getting sector averages."""
        # Create companies in same sector
        c1_id = store.save_company(CompanyData(symbol="A1", sector="Tech"))
        c2_id = store.save_company(CompanyData(symbol="A2", sector="Tech"))

        store.save_quote(c1_id, QuoteData(price=100, pe_ratio=20), EquityData(market_cap=1000000))
        store.save_quote(c2_id, QuoteData(price=200, pe_ratio=30), EquityData(market_cap=2000000))

        averages = store.get_sector_averages("Tech")
        assert averages["avg_pe"] == pytest.approx(25.0)
        assert averages["avg_price"] == pytest.approx(150.0)
        assert averages["avg_market_cap"] == pytest.approx(1500000.0)

    def test_get_sector_averages_empty(self, store):
        """Test getting sector averages for non-existent sector."""
        averages = store.get_sector_averages("NonExistent")
        assert averages["avg_pe"] is None
        assert averages["avg_price"] is None

    def test_get_sector_averages_all_fields(self, store):
        """Test that get_sector_averages returns all expected fields."""
        # Create companies in same sector
        c1_id = store.save_company(CompanyData(symbol="T1", sector="Energy"))
        c2_id = store.save_company(CompanyData(symbol="T2", sector="Energy"))

        store.save_quote(c1_id, QuoteData(price=50, pe_ratio=10, change_pct=2.0, ytd_change_pct=15.0), EquityData(market_cap=500000))
        store.save_quote(c2_id, QuoteData(price=100, pe_ratio=20, change_pct=4.0, ytd_change_pct=25.0), EquityData(market_cap=1000000))

        averages = store.get_sector_averages("Energy")

        # Check all expected fields are present
        assert "sector" in averages
        assert averages["sector"] == "Energy"
        assert "company_count" in averages
        assert averages["company_count"] == 2
        assert "avg_pe" in averages
        assert averages["avg_pe"] == pytest.approx(15.0)
        assert "min_pe" in averages
        assert averages["min_pe"] == pytest.approx(10.0)
        assert "max_pe" in averages
        assert averages["max_pe"] == pytest.approx(20.0)
        assert "avg_price" in averages
        assert "avg_market_cap" in averages
        assert "avg_change_pct" in averages
        assert "avg_ytd_change" in averages

    # ========== CONSOLIDATED SAVE OPERATIONS ==========

    def test_save_scraped_data(self, store):
        """Test saving all scraped data in one operation."""
        data = ScrapedData(
            symbol="TEST",
            quote=QuoteData(price=10.50, change=0.25, volume=1000000),
            company=CompanyData(symbol="TEST", name="Test Company", sector="Tech"),
            equity=EquityData(market_cap=1000000000),
            financials={"annual": [FinancialRow(period="2025", period_type="annual", metric="Revenue", value=500000)]},
            ratios=[RatioRow(period="2025", metric="PE Ratio", value=15.5)],
            announcements={"others": [AnnouncementData(date="2025-01-15", title="Test Ann")]},
            reports=[ReportData(report_type="annual", period="2025", url="https://example.com/report.pdf")],
        )

        company_id = store.save_scraped_data(data)
        assert company_id is not None
        assert company_id > 0

        # Verify data was saved
        company = store.get_company("TEST")
        assert company is not None
        assert company.name == "Test Company"

        quote = store.get_latest_quote("TEST")
        assert quote is not None
        assert quote.price == 10.50

        financials = store.get_financials("TEST")
        assert len(financials) == 1

        ratios = store.get_ratios("TEST")
        assert len(ratios) == 1

        announcements = store.get_announcements("TEST")
        assert len(announcements) == 1

        reports = store.get_reports("TEST")
        assert len(reports) == 1

        # Verify cache was created
        cached = store.get_cache("TEST")
        assert cached is not None

    def test_save_scraped_data_no_company(self, store):
        """Test save_scraped_data returns None without company data."""
        data = ScrapedData(
            symbol="TEST",
            quote=QuoteData(price=10.50),
            company=None,
        )

        result = store.save_scraped_data(data)
        assert result is None

    def test_save_scraped_data_with_dict_financials(self, store):
        """Test save_scraped_data with dict format financials (standard format)."""
        data = ScrapedData(
            symbol="TEST",
            company=CompanyData(symbol="TEST", name="Test"),
            financials={
                "annual": [
                    FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000),
                    FinancialRow(period="2025", period_type="annual", metric="Profit", value=100),
                ]
            },
        )

        company_id = store.save_scraped_data(data)
        assert company_id is not None

        financials = store.get_financials("TEST")
        assert len(financials) == 2

    def test_save_scraped_data_with_dict_announcements(self, store):
        """Test save_scraped_data with dict format announcements (standard format)."""
        data = ScrapedData(
            symbol="TEST",
            company=CompanyData(symbol="TEST", name="Test"),
            announcements={
                "others": [
                    AnnouncementData(date="2025-01-15", title="Ann 1"),
                    AnnouncementData(date="2025-01-16", title="Ann 2"),
                ]
            },
        )

        company_id = store.save_scraped_data(data)
        assert company_id is not None

        announcements = store.get_announcements("TEST")
        assert len(announcements) == 2
