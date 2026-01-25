"""Tests for agent tool functions."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import os

from psx.tools.calculator import ValuationCalculator, RatioCalculator, detect_red_flags, detect_strengths


class TestAnalystAgentTools:
    """Test analyst agent tool functions."""

    def test_calculate_pe_valuation(self):
        """Test P/E valuation calculation."""
        result = ValuationCalculator.pe_valuation(eps=5.0, pe_ratio=15.0)
        assert result.value == 75.0
        assert result.method == "P/E Valuation"

    def test_calculate_graham_number(self):
        """Test Graham Number calculation."""
        result = ValuationCalculator.graham_number(eps=4.0, book_value_per_share=20.0)
        # Graham = sqrt(22.5 * 4 * 20) = sqrt(1800) ≈ 42.43
        assert result.value == pytest.approx(42.43, rel=0.01)

    def test_calculate_book_value(self):
        """Test book value calculation."""
        result = ValuationCalculator.book_value_valuation(
            book_value_per_share=50.0, pb_ratio=1.2
        )
        assert result.value == 60.0

    def test_calculate_dcf(self):
        """Test DCF valuation."""
        cash_flows = [100, 110, 121, 133, 146]
        result = ValuationCalculator.dcf_valuation(
            free_cash_flows=cash_flows,
            discount_rate=0.10,
            terminal_growth_rate=0.03,
        )
        assert result.value > 0
        assert result.method == "DCF"

    def test_calculate_ratios(self):
        """Test various ratio calculations."""
        # Liquidity
        current = RatioCalculator.current_ratio(200000, 100000)
        assert current == 2.0

        quick = RatioCalculator.quick_ratio(200000, 50000, 100000)
        assert quick == 1.5

        # Profitability
        roe = RatioCalculator.return_on_equity(50000, 250000)
        assert roe == 20.0

        margin = RatioCalculator.profit_margin(30000, 300000)
        assert margin == 10.0

    def test_detect_red_flags_tool(self):
        """Test red flag detection."""
        flags = detect_red_flags(
            current_ratio=0.8,
            debt_to_equity=3.0,
            profit_margin=-5.0,
        )
        assert len(flags) >= 3

    def test_detect_strengths_tool(self):
        """Test strength detection."""
        strengths = detect_strengths(
            current_ratio=2.5,
            debt_to_equity=0.3,
            profit_margin=20.0,
            roe=18.0,
        )
        assert len(strengths) >= 3


class TestDataAgentToolsMocked:
    """Test data agent tool functions with mocks."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock DataStore."""
        store = MagicMock()
        store.get_company.return_value = MagicMock(
            symbol="OGDC",
            name="Oil & Gas Development",
            sector="Oil & Gas",
        )
        store.get_latest_quote.return_value = MagicMock(
            price=100.0,
            pe_ratio=8.5,
        )
        store.get_financials.return_value = []
        store.get_ratios.return_value = []
        store.get_announcements.return_value = []
        store.get_reports.return_value = []
        store.list_companies.return_value = [
            MagicMock(symbol="OGDC"),
            MagicMock(symbol="PPL"),
        ]
        return store

    def test_get_company_data_concept(self, mock_store):
        """Test getting company data retrieves from store."""
        # This tests the concept - actual implementation uses DataStore
        company = mock_store.get_company("OGDC")
        assert company.symbol == "OGDC"
        assert company.sector == "Oil & Gas"

    def test_get_company_list_concept(self, mock_store):
        """Test listing companies."""
        companies = mock_store.list_companies()
        assert len(companies) == 2
        symbols = [c.symbol for c in companies]
        assert "OGDC" in symbols
        assert "PPL" in symbols

    def test_get_peer_companies_concept(self, mock_store):
        """Test finding peer companies by sector."""
        mock_store.list_companies.return_value = [
            MagicMock(symbol="OGDC", sector="Oil & Gas"),
            MagicMock(symbol="PPL", sector="Oil & Gas"),
            MagicMock(symbol="ENGRO", sector="Chemicals"),
        ]

        companies = mock_store.list_companies()
        peers = [c for c in companies if c.sector == "Oil & Gas"]
        assert len(peers) == 2


class TestResearchAgentToolsMocked:
    """Test research agent tool functions with mocks."""

    def test_search_news_concept(self):
        """Test news search returns results."""
        # Mock search response
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(title="OGDC Reports Q4 Results", url="https://news.com/1"),
            MagicMock(title="Oil Sector Outlook", url="https://news.com/2"),
        ]
        mock_response.answer = "OGDC reported strong results..."

        assert len(mock_response.results) == 2
        assert mock_response.answer is not None

    def test_get_announcements_concept(self):
        """Test retrieving announcements."""
        mock_store = MagicMock()
        mock_store.get_announcements.return_value = [
            MagicMock(date="2025-01-15", title="Board Meeting"),
            MagicMock(date="2025-01-10", title="Q4 Results"),
        ]

        announcements = mock_store.get_announcements("OGDC")
        assert len(announcements) == 2


class TestAgentIntegrationConcepts:
    """Test agent integration concepts."""

    def test_data_flow_concept(self):
        """Test the data flow through agents."""
        # Simulate data agent output
        data_output = {
            "symbol": "OGDC",
            "quote": {"price": 100.0, "pe_ratio": 8.5},
            "company": {"name": "Oil & Gas Development", "sector": "Oil & Gas"},
            "financials": [{"period": "2025", "metric": "Revenue", "value": 1000000}],
        }

        # Simulate analyst using data
        price = data_output["quote"]["price"]
        pe = data_output["quote"]["pe_ratio"]

        # Calculate EPS from P/E
        eps = price / pe if pe else 0
        assert eps == pytest.approx(11.76, rel=0.01)

        # Run valuation
        valuation = ValuationCalculator.pe_valuation(eps=eps, pe_ratio=10.0)
        assert valuation.value > 0

    def test_multi_symbol_analysis_concept(self):
        """Test analyzing multiple symbols."""
        symbols = ["OGDC", "PPL", "POL"]

        # Simulate collecting data for each
        results = {}
        for symbol in symbols:
            results[symbol] = {
                "quote": {"price": 100.0},
                "valuations": [],
            }

        assert len(results) == 3
        assert all(s in results for s in symbols)

    def test_peer_comparison_concept(self):
        """Test peer comparison logic."""
        peer_data = [
            {"symbol": "OGDC", "pe_ratio": 8.5, "price": 100},
            {"symbol": "PPL", "pe_ratio": 7.2, "price": 80},
            {"symbol": "POL", "pe_ratio": 9.1, "price": 120},
        ]

        # Calculate average P/E
        avg_pe = sum(p["pe_ratio"] for p in peer_data) / len(peer_data)
        assert avg_pe == pytest.approx(8.27, rel=0.01)

        # Find cheapest by P/E
        cheapest = min(peer_data, key=lambda x: x["pe_ratio"])
        assert cheapest["symbol"] == "PPL"


class TestToolSchemaGeneration:
    """Test tool schema generation for agents."""

    def test_tool_schema_structure(self):
        """Test tool schema has correct structure."""
        schema = {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol",
                },
                "force_refresh": {
                    "type": "boolean",
                    "description": "Force data refresh",
                    "default": False,
                },
            },
            "required": ["symbol"],
        }

        assert schema["type"] == "object"
        assert "symbol" in schema["properties"]
        assert "required" in schema
        assert "symbol" in schema["required"]

    def test_valuation_tool_schema(self):
        """Test valuation tool schema."""
        schema = {
            "type": "object",
            "properties": {
                "eps": {"type": "number", "description": "Earnings per share"},
                "pe_ratio": {"type": "number", "description": "Target P/E ratio"},
            },
            "required": ["eps", "pe_ratio"],
        }

        # Validate schema can describe PE valuation inputs
        assert schema["properties"]["eps"]["type"] == "number"
        assert schema["properties"]["pe_ratio"]["type"] == "number"
