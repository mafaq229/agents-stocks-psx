"""Tests for agent data schemas."""

import pytest
from datetime import datetime

from psx.agents.schemas import (
    PeerDataSnapshot,
    DataAgentOutput,
    ValuationDetail,
    PeerComparison,
    AnalystOutput,
    NewsItem,
    ResearchOutput,
    AnalysisState,
    AnalysisReport,
    ComparisonReport,
)
from psx.core.models import (
    QuoteData,
    CompanyData,
    FinancialRow,
    RatioRow,
    ReportData,
    AnnouncementData,
)


class TestPeerDataSnapshot:
    """Test PeerDataSnapshot dataclass."""

    def test_instantiation_minimal(self):
        """Test creating with minimal data."""
        peer = PeerDataSnapshot(symbol="OGDC")
        assert peer.symbol == "OGDC"
        assert peer.name is None
        assert peer.price is None

    def test_instantiation_full(self):
        """Test creating with all fields."""
        peer = PeerDataSnapshot(
            symbol="OGDC",
            name="Oil & Gas Development",
            sector="Oil & Gas",
            price=100.0,
            change_pct=2.5,
            pe_ratio=8.5,
            market_cap=500000000.0,
            eps=12.0,
            profit_margin=25.0,
            week_52_high=120.0,
            week_52_low=80.0,
        )
        assert peer.price == 100.0
        assert peer.pe_ratio == 8.5

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        peer = PeerDataSnapshot(symbol="TEST", price=50.0)
        result = peer.to_dict()
        assert "symbol" in result
        assert "price" in result
        assert "name" not in result


class TestDataAgentOutput:
    """Test DataAgentOutput dataclass."""

    def test_instantiation_minimal(self):
        """Test creating with minimal data."""
        output = DataAgentOutput(symbol="TEST")
        assert output.symbol == "TEST"
        assert output.quote is None
        assert output.financials == []
        assert output.peers == []

    def test_instantiation_full(self):
        """Test creating with full data."""
        output = DataAgentOutput(
            symbol="TEST",
            quote=QuoteData(price=100.0),
            company=CompanyData(symbol="TEST", name="Test Company"),
            financials=[FinancialRow(period="2025", period_type="annual", metric="Revenue", value=1000.0)],
            ratios=[RatioRow(period="2025", metric="PE", value=15.0)],
            reports=[ReportData(report_type="annual", period="2025", url="https://example.com")],
            announcements=[AnnouncementData(date="2025-01-15", title="Test")],
            peers=["PEER1", "PEER2"],
            peer_data=[PeerDataSnapshot(symbol="PEER1", price=50.0)],
            sector="Technology",
            sector_averages={"avg_pe": 20.0},
            data_gaps=["missing Q4 data"],
            data_freshness="2 hours ago",
        )
        assert output.quote.price == 100.0
        assert len(output.financials) == 1
        assert len(output.peers) == 2

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        output = DataAgentOutput(
            symbol="TEST",
            quote=QuoteData(price=100.0),
            peers=["PEER1"],
        )
        result = output.to_dict()
        assert result["symbol"] == "TEST"
        assert result["quote"]["price"] == 100.0
        assert result["peers"] == ["PEER1"]
        assert result["financials"] == []

    def test_to_context_string(self):
        """Test to_context_string generates readable output."""
        output = DataAgentOutput(
            symbol="TEST",
            quote=QuoteData(price=100.0, change=2.0, change_pct=2.0, pe_ratio=15.0),
            company=CompanyData(symbol="TEST", name="Test Company", sector="Tech"),
            peers=["PEER1", "PEER2"],
        )
        context = output.to_context_string()
        assert "TEST" in context
        assert "100" in context
        assert "Tech" in context
        assert "PEER1" in context


class TestValuationDetail:
    """Test ValuationDetail dataclass."""

    def test_instantiation(self):
        """Test creating valuation detail."""
        detail = ValuationDetail(
            method="P/E Valuation",
            value=120.0,
            inputs={"eps": 8.0, "pe_ratio": 15.0},
            notes="Based on sector average P/E",
        )
        assert detail.method == "P/E Valuation"
        assert detail.value == 120.0

    def test_to_dict(self):
        """Test to_dict returns all fields."""
        detail = ValuationDetail(method="Graham", value=100.0, inputs={})
        result = detail.to_dict()
        assert result["method"] == "Graham"
        assert result["value"] == 100.0


class TestPeerComparison:
    """Test PeerComparison dataclass."""

    def test_instantiation(self):
        """Test creating peer comparison."""
        peer = PeerComparison(
            symbol="PEER1",
            name="Peer Company",
            price=80.0,
            pe_ratio=12.0,
            pb_ratio=1.5,
            dividend_yield=4.0,
            market_cap=1000000.0,
            roe=18.0,
        )
        assert peer.symbol == "PEER1"
        assert peer.pe_ratio == 12.0

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        peer = PeerComparison(symbol="TEST", price=50.0)
        result = peer.to_dict()
        assert "symbol" in result
        assert "price" in result
        assert "pe_ratio" not in result


class TestAnalystOutput:
    """Test AnalystOutput dataclass."""

    def test_instantiation_defaults(self):
        """Test default values."""
        output = AnalystOutput(symbol="TEST")
        assert output.symbol == "TEST"
        assert output.health_score == 0.0
        assert output.recommendation == "HOLD"
        assert output.confidence == 0.5
        assert output.valuations == []

    def test_instantiation_full(self):
        """Test with all fields."""
        output = AnalystOutput(
            symbol="TEST",
            health_score=75.0,
            valuations=[ValuationDetail(method="PE", value=100.0, inputs={})],
            fair_value=105.0,
            current_price=95.0,
            margin_of_safety=10.5,
            red_flags=["High debt"],
            strengths=["Strong cash flow"],
            peer_comparison=[PeerComparison(symbol="PEER", price=80.0)],
            recommendation="BUY",
            confidence=0.75,
            reasoning="Undervalued with strong fundamentals",
        )
        assert output.health_score == 75.0
        assert output.recommendation == "BUY"
        assert len(output.valuations) == 1

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        output = AnalystOutput(
            symbol="TEST",
            health_score=80.0,
            valuations=[ValuationDetail(method="PE", value=100.0, inputs={})],
            red_flags=["High debt"],
        )
        result = output.to_dict()
        assert result["symbol"] == "TEST"
        assert result["health_score"] == 80.0
        assert len(result["valuations"]) == 1
        assert result["valuations"][0]["method"] == "PE"

    def test_to_context_string(self):
        """Test context string generation."""
        output = AnalystOutput(
            symbol="TEST",
            health_score=80.0,
            fair_value=100.0,
            current_price=90.0,
            recommendation="BUY",
            confidence=0.8,
            reasoning="Good value",
        )
        context = output.to_context_string()
        assert "TEST" in context
        assert "80" in context
        assert "BUY" in context


class TestNewsItem:
    """Test NewsItem dataclass."""

    def test_instantiation(self):
        """Test creating news item."""
        news = NewsItem(
            title="Company Reports Record Profits",
            url="https://example.com/news",
            source="Reuters",
            date="2025-01-15",
            summary="Company reported strong Q4 results",
        )
        assert news.title == "Company Reports Record Profits"
        assert news.source == "Reuters"

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        news = NewsItem(title="Test News", url="https://example.com")
        result = news.to_dict()
        assert "title" in result
        assert "url" in result
        assert "source" not in result


class TestResearchOutput:
    """Test ResearchOutput dataclass."""

    def test_instantiation_defaults(self):
        """Test default values."""
        output = ResearchOutput(symbol="TEST")
        assert output.symbol == "TEST"
        assert output.news_items == []
        assert output.key_events == []

    def test_instantiation_full(self):
        """Test with all fields."""
        output = ResearchOutput(
            symbol="TEST",
            news_items=[NewsItem(title="News", url="https://example.com")],
            key_events=["Q4 earnings release"],
            report_highlights=["Revenue up 20%"],
            management_commentary="CEO optimistic about growth",
            risks_identified=["Market volatility"],
            opportunities=["New product launch"],
            competitor_insights={"COMP1": "losing market share"},
        )
        assert len(output.news_items) == 1
        assert len(output.key_events) == 1

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        output = ResearchOutput(
            symbol="TEST",
            news_items=[NewsItem(title="News", url="https://example.com")],
            risks_identified=["Risk 1"],
        )
        result = output.to_dict()
        assert result["symbol"] == "TEST"
        assert len(result["news_items"]) == 1
        assert result["news_items"][0]["title"] == "News"

    def test_to_context_string(self):
        """Test context string generation."""
        output = ResearchOutput(
            symbol="TEST",
            news_items=[NewsItem(title="Big News", url="https://example.com")],
            key_events=["Q4 earnings"],
            risks_identified=["Debt concerns"],
        )
        context = output.to_context_string()
        assert "TEST" in context
        assert "Big News" in context


class TestAnalysisState:
    """Test AnalysisState dataclass."""

    def test_instantiation_defaults(self):
        """Test default values."""
        state = AnalysisState(query="Should I buy OGDC?")
        assert state.query == "Should I buy OGDC?"
        assert state.symbols == []
        assert state.iteration == 0
        assert state.max_iterations == 10

    def test_instantiation_full(self):
        """Test with all fields."""
        state = AnalysisState(
            query="Compare OGDC and PPL",
            symbols=["OGDC", "PPL"],
            data={"OGDC": DataAgentOutput(symbol="OGDC")},
            research={"OGDC": ResearchOutput(symbol="OGDC")},
            analysis={"OGDC": AnalystOutput(symbol="OGDC")},
            iteration=3,
            max_iterations=10,
            errors=["API timeout"],
        )
        assert len(state.symbols) == 2
        assert "OGDC" in state.data
        assert state.iteration == 3

    def test_started_at_auto_generated(self):
        """Test started_at is auto-generated."""
        state = AnalysisState(query="test")
        # Should be a valid ISO timestamp
        datetime.fromisoformat(state.started_at)

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        state = AnalysisState(
            query="test",
            symbols=["TEST"],
            errors=["error1"],
        )
        result = state.to_dict()
        assert result["query"] == "test"
        assert result["symbols"] == ["TEST"]
        assert result["errors"] == ["error1"]

    def test_to_context_string(self):
        """Test context string generation."""
        state = AnalysisState(
            query="Analyze TEST",
            symbols=["TEST"],
            iteration=2,
            max_iterations=10,
        )
        context = state.to_context_string()
        assert "TEST" in context
        assert "2/10" in context


class TestAnalysisReport:
    """Test AnalysisReport dataclass."""

    def test_instantiation_minimal(self):
        """Test creating with minimal data."""
        report = AnalysisReport(
            query="Analyze OGDC",
            symbols=["OGDC"],
            recommendation="HOLD",
            confidence=0.6,
        )
        assert report.symbols == ["OGDC"]
        assert report.recommendation == "HOLD"

    def test_instantiation_full(self):
        """Test with all sections."""
        report = AnalysisReport(
            query="Analyze TEST",
            symbols=["TEST"],
            recommendation="BUY",
            confidence=0.85,
            business_overview="A leading technology company",
            industry_context="Growing sector",
            ownership_structure={"promoter": "60%", "public": "40%"},
            management_notes=["Strong leadership"],
            financial_snapshot={"revenue": "1B", "profit_margin": "15%"},
            valuation_table=[{"method": "PE", "value": 100.0, "inputs": ""}],
            fair_value=100.0,
            margin_of_safety=15.0,
            peer_comparison_table=[{"symbol": "PEER", "pe": 12.0}],
            relative_position="Trades at premium",
            strengths=[{"point": "Strong brand", "reasoning": "Market leader"}],
            risks=[{"point": "Debt levels", "reasoning": "Higher than peers"}],
            recent_developments=["New product launch"],
            reasoning="Undervalued with good growth",
            entry_price=90.0,
            target_price=120.0,
            stop_loss=80.0,
        )
        assert report.fair_value == 100.0
        assert len(report.strengths) == 1

    def test_generated_at_auto_generated(self):
        """Test generated_at is auto-generated."""
        report = AnalysisReport(query="test", symbols=["TEST"], recommendation="HOLD", confidence=0.5)
        # Should be parseable ISO timestamp
        datetime.fromisoformat(report.generated_at)

    def test_to_dict(self):
        """Test to_dict returns all fields."""
        report = AnalysisReport(
            query="test",
            symbols=["TEST"],
            recommendation="BUY",
            confidence=0.7,
            fair_value=100.0,
            strengths=[{"point": "Growth"}],
        )
        result = report.to_dict()
        assert result["recommendation"] == "BUY"
        assert result["fair_value"] == 100.0
        assert len(result["strengths"]) == 1

    def test_to_markdown_structure(self):
        """Test to_markdown generates proper markdown."""
        report = AnalysisReport(
            query="Analyze TEST",
            symbols=["TEST"],
            recommendation="BUY",
            confidence=0.8,
            business_overview="A tech company",
            fair_value=100.0,
            margin_of_safety=20.0,
            strengths=[{"point": "Growth", "reasoning": "Strong revenue growth"}],
            risks=[{"point": "Competition", "reasoning": "Many competitors"}],
            reasoning="Good value stock",
        )
        markdown = report.to_markdown()

        # Check section headers
        assert "# Investment Analysis: TEST" in markdown
        assert "## 1. Business Overview" in markdown
        assert "## 2. Ownership & Management" in markdown
        assert "## 3. Financial Snapshot" in markdown
        assert "## 4. Valuation" in markdown
        assert "## 5. Peer Comparison" in markdown
        assert "## 6. Investment Thesis" in markdown
        assert "## 7. Recommendation" in markdown

        # Check content
        assert "BUY" in markdown
        assert "A tech company" in markdown
        assert "Growth" in markdown

    def test_to_markdown_with_valuation_table(self):
        """Test markdown includes valuation table."""
        report = AnalysisReport(
            query="test",
            symbols=["TEST"],
            recommendation="HOLD",
            confidence=0.5,
            valuation_table=[
                {"method": "P/E", "value": 100, "inputs": "EPS=5, PE=20"},
                {"method": "Graham", "value": 95, "inputs": "EPS=5, BVPS=40"},
            ],
        )
        markdown = report.to_markdown()
        assert "| Method | Fair Value | Key Inputs |" in markdown
        assert "P/E" in markdown
        assert "Graham" in markdown


class TestComparisonReport:
    """Test ComparisonReport dataclass."""

    def test_instantiation_minimal(self):
        """Test creating with minimal data."""
        report = ComparisonReport(
            query="Compare A and B",
            symbols=["A", "B"],
            summary="A is better than B",
        )
        assert report.symbols == ["A", "B"]
        assert report.summary == "A is better than B"

    def test_instantiation_full(self):
        """Test with all fields."""
        report = ComparisonReport(
            query="Compare A and B",
            symbols=["A", "B"],
            summary="A is the winner",
            winner="A",
            rankings=[{"symbol": "A", "score": 85}, {"symbol": "B", "score": 70}],
            comparison_table={
                "A": {"pe": 15, "roe": 20},
                "B": {"pe": 18, "roe": 15},
            },
            analysis={
                "A": AnalystOutput(symbol="A", recommendation="BUY"),
                "B": AnalystOutput(symbol="B", recommendation="HOLD"),
            },
        )
        assert report.winner == "A"
        assert len(report.rankings) == 2

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        report = ComparisonReport(
            query="test",
            symbols=["A", "B"],
            summary="test summary",
            winner="A",
        )
        result = report.to_dict()
        assert result["winner"] == "A"
        assert result["symbols"] == ["A", "B"]

    def test_to_markdown(self):
        """Test markdown generation."""
        report = ComparisonReport(
            query="Compare A and B",
            symbols=["A", "B"],
            summary="A is the better pick",
            winner="A",
            rankings=[{"symbol": "A", "score": 85}, {"symbol": "B", "score": 70}],
            comparison_table={
                "A": {"pe": 15, "roe": 20},
                "B": {"pe": 18, "roe": 15},
            },
        )
        markdown = report.to_markdown()

        assert "Stock Comparison Report" in markdown
        assert "A, B" in markdown
        assert "Best Pick: A" in markdown
        assert "Rankings" in markdown
        assert "Comparison Table" in markdown
