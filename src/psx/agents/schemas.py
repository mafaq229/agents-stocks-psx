"""Data schemas for agent inputs and outputs.

These dataclasses define the structured data passed between agents.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional, Literal

from psx.core.models import (
    QuoteData,
    CompanyData,
    FinancialRow,
    RatioRow,
    ReportData,
    AnnouncementData,
)


# Type aliases
Recommendation = Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]


@dataclass
class PeerDataSnapshot:
    """Quick snapshot of peer company data for comparison."""

    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    pe_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    eps: Optional[float] = None
    profit_margin: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class DataAgentOutput:
    """Output from the Data Agent."""

    symbol: str
    quote: Optional[QuoteData] = None
    company: Optional[CompanyData] = None
    financials: list[FinancialRow] = field(default_factory=list)
    ratios: list[RatioRow] = field(default_factory=list)
    reports: list[ReportData] = field(default_factory=list)
    announcements: list[AnnouncementData] = field(default_factory=list)
    peers: list[str] = field(default_factory=list)
    peer_data: list[PeerDataSnapshot] = field(default_factory=list)  # Rich peer data
    sector: Optional[str] = None
    sector_averages: Optional[dict[str, Any]] = None  # Sector benchmarks
    data_gaps: list[str] = field(default_factory=list)
    data_freshness: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quote": self.quote.to_dict() if self.quote else None,
            "company": self.company.to_dict() if self.company else None,
            "financials": [f.to_dict() for f in self.financials],
            "ratios": [r.to_dict() for r in self.ratios],
            "reports": [r.to_dict() for r in self.reports],
            "announcements": [a.to_dict() for a in self.announcements],
            "peers": self.peers,
            "peer_data": [p.to_dict() for p in self.peer_data],
            "sector": self.sector,
            "sector_averages": self.sector_averages,
            "data_gaps": self.data_gaps,
            "data_freshness": self.data_freshness,
        }

    def to_context_string(self) -> str:
        """Convert to a string suitable for LLM context."""
        lines = [f"=== Data for {self.symbol} ==="]

        if self.quote:
            lines.append(f"\nCurrent Price: Rs. {self.quote.price}")
            if self.quote.change:
                lines.append(f"Change: {self.quote.change} ({self.quote.change_pct}%)")
            if self.quote.pe_ratio:
                lines.append(f"P/E Ratio: {self.quote.pe_ratio}")
            if self.quote.week_52_high and self.quote.week_52_low:
                lines.append(f"52-Week Range: {self.quote.week_52_low} - {self.quote.week_52_high}")

        if self.company:
            lines.append(f"\nCompany: {self.company.name}")
            lines.append(f"Sector: {self.company.sector}")
            if self.company.description:
                lines.append(f"Description: {self.company.description[:300]}...")

        # Include actual financials data
        if self.financials:
            lines.append(f"\n--- Financials ({len(self.financials)} rows) ---")
            for f in self.financials[:16]:  # Recent periods
                lines.append(f"  {f.period} {f.metric}: {f.value}")

        # Include actual ratios data
        if self.ratios:
            lines.append(f"\n--- Ratios ({len(self.ratios)} metrics) ---")
            for r in self.ratios[:12]:
                lines.append(f"  {r.period} {r.metric}: {r.value}")

        # Include report URLs for PDF parsing - CRITICAL for ResearchAgent
        if self.reports:
            lines.append(f"\n--- Available Reports (PDFs to parse) ---")
            for r in self.reports[:6]:  # Latest reports
                lines.append(f"  [{r.report_type.upper()}] {r.period}: {r.url}")

        # Include announcement URLs with PDFs
        if self.announcements:
            lines.append(f"\n--- Recent Announcements ({len(self.announcements)} items) ---")
            for a in self.announcements[:15]:
                lines.append(f"  [{a.date}] {a.title}")
                if a.url and 'javascript' not in a.url:
                    lines.append(f"    PDF: {a.url}")

        if self.peers:
            lines.append(f"\nPeers: {', '.join(self.peers)}")

        # Include peer financial data for comparison
        if self.peer_data:
            lines.append(f"\n--- Peer Comparison Data ({len(self.peer_data)} peers) ---")
            for p in self.peer_data:
                peer_line = f"  {p.symbol}: Price={p.price}"
                if p.pe_ratio:
                    peer_line += f", P/E={p.pe_ratio}"
                if p.market_cap:
                    peer_line += f", MCap={p.market_cap}"
                if p.eps:
                    peer_line += f", EPS={p.eps}"
                lines.append(peer_line)

        # Include sector benchmarks
        if self.sector_averages:
            lines.append(f"\n--- Sector Averages ---")
            for key, value in self.sector_averages.items():
                if value is not None:
                    lines.append(f"  {key}: {value}")

        if self.data_gaps:
            lines.append(f"\nData Gaps: {', '.join(self.data_gaps)}")

        return "\n".join(lines)


@dataclass
class ValuationDetail:
    """Single valuation method result."""

    method: str
    value: float
    inputs: dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeerComparison:
    """Comparison with a peer company."""

    symbol: str
    name: Optional[str] = None
    price: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    roe: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AnalystOutput:
    """Output from the Analyst Agent."""

    symbol: str
    health_score: float = 0.0  # 0-100
    valuations: list[ValuationDetail] = field(default_factory=list)
    fair_value: Optional[float] = None
    current_price: Optional[float] = None
    margin_of_safety: Optional[float] = None
    red_flags: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    peer_comparison: list[PeerComparison] = field(default_factory=list)
    recommendation: Recommendation = "HOLD"
    confidence: float = 0.5  # 0-1
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "health_score": self.health_score,
            "valuations": [v.to_dict() for v in self.valuations],
            "fair_value": self.fair_value,
            "current_price": self.current_price,
            "margin_of_safety": self.margin_of_safety,
            "red_flags": self.red_flags,
            "strengths": self.strengths,
            "peer_comparison": [p.to_dict() for p in self.peer_comparison],
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }

    def to_context_string(self) -> str:
        """Convert to a string suitable for LLM context."""
        lines = [f"=== Analysis for {self.symbol} ==="]

        lines.append(f"\nHealth Score: {self.health_score}/100")
        lines.append(f"Recommendation: {self.recommendation} (Confidence: {self.confidence:.0%})")

        if self.fair_value and self.current_price:
            lines.append(f"\nFair Value: Rs. {self.fair_value}")
            lines.append(f"Current Price: Rs. {self.current_price}")
            if self.margin_of_safety:
                lines.append(f"Margin of Safety: {self.margin_of_safety:.1f}%")

        if self.valuations:
            lines.append("\nValuation Methods:")
            for v in self.valuations:
                lines.append(f"  - {v.method}: Rs. {v.value}")

        if self.strengths:
            lines.append(f"\nStrengths: {', '.join(self.strengths[:3])}")

        if self.red_flags:
            lines.append(f"Red Flags: {', '.join(self.red_flags[:3])}")

        lines.append(f"\nReasoning: {self.reasoning[:200]}...")

        return "\n".join(lines)


@dataclass
class NewsItem:
    """Single news item."""

    title: str
    url: str
    source: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[float] = None  # -1 to 1

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ResearchOutput:
    """Output from the Research Agent."""

    symbol: str
    news_items: list[NewsItem] = field(default_factory=list)
    sentiment_score: float = 0.0  # -1 to 1
    sentiment_label: str = "neutral"  # positive, negative, neutral
    key_events: list[str] = field(default_factory=list)
    report_highlights: list[str] = field(default_factory=list)
    risks_identified: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    competitor_insights: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "news_items": [n.to_dict() for n in self.news_items],
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "key_events": self.key_events,
            "report_highlights": self.report_highlights,
            "risks_identified": self.risks_identified,
            "opportunities": self.opportunities,
            "competitor_insights": self.competitor_insights,
        }

    def to_context_string(self) -> str:
        """Convert to a string suitable for LLM context."""
        lines = [f"=== Research for {self.symbol} ==="]

        lines.append(f"\nSentiment: {self.sentiment_label} ({self.sentiment_score:+.2f})")

        if self.news_items:
            lines.append(f"\nRecent News ({len(self.news_items)} items):")
            for news in self.news_items[:3]:
                lines.append(f"  - {news.title}")

        if self.key_events:
            lines.append(f"\nKey Events: {', '.join(self.key_events[:3])}")

        if self.report_highlights:
            lines.append(f"\nReport Highlights: {', '.join(self.report_highlights[:3])}")

        if self.risks_identified:
            lines.append(f"\nRisks: {', '.join(self.risks_identified[:3])}")

        return "\n".join(lines)


@dataclass
class AnalysisState:
    """State maintained by the Supervisor during analysis."""

    query: str
    symbols: list[str] = field(default_factory=list)
    data: dict[str, DataAgentOutput] = field(default_factory=dict)
    research: dict[str, ResearchOutput] = field(default_factory=dict)
    analysis: dict[str, AnalystOutput] = field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 10
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "symbols": self.symbols,
            "data": {k: v.to_dict() for k, v in self.data.items()},
            "research": {k: v.to_dict() for k, v in self.research.items()},
            "analysis": {k: v.to_dict() for k, v in self.analysis.items()},
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "started_at": self.started_at,
            "errors": self.errors,
        }

    def to_context_string(self) -> str:
        """Convert current state to context for LLM."""
        lines = [f"=== Analysis State ==="]
        lines.append(f"Query: {self.query}")
        lines.append(f"Symbols: {', '.join(self.symbols)}")
        lines.append(f"Iteration: {self.iteration}/{self.max_iterations}")

        if self.data:
            lines.append(f"\nData collected for: {', '.join(self.data.keys())}")
        if self.research:
            lines.append(f"Research done for: {', '.join(self.research.keys())}")
        if self.analysis:
            lines.append(f"Analysis done for: {', '.join(self.analysis.keys())}")

        if self.errors:
            lines.append(f"\nErrors: {', '.join(self.errors[:3])}")

        return "\n".join(lines)


@dataclass
class AnalysisReport:
    """Final analysis report produced by Supervisor."""

    query: str
    symbols: list[str]
    summary: str
    recommendation: Recommendation
    confidence: float
    data: dict[str, DataAgentOutput] = field(default_factory=dict)
    research: dict[str, ResearchOutput] = field(default_factory=dict)
    analysis: dict[str, AnalystOutput] = field(default_factory=dict)
    key_findings: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "symbols": self.symbols,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "data": {k: v.to_dict() for k, v in self.data.items()},
            "research": {k: v.to_dict() for k, v in self.research.items()},
            "analysis": {k: v.to_dict() for k, v in self.analysis.items()},
            "key_findings": self.key_findings,
            "risks": self.risks,
            "generated_at": self.generated_at,
        }

    def to_markdown(self) -> str:
        """Convert to markdown report."""
        lines = [f"# Stock Analysis Report"]
        lines.append(f"\n**Query:** {self.query}")
        lines.append(f"**Generated:** {self.generated_at}")

        lines.append(f"\n## Summary")
        lines.append(self.summary)

        lines.append(f"\n## Recommendation")
        lines.append(f"**{self.recommendation}** (Confidence: {self.confidence:.0%})")

        if self.key_findings:
            lines.append(f"\n## Key Findings")
            for finding in self.key_findings:
                lines.append(f"- {finding}")

        if self.risks:
            lines.append(f"\n## Risks")
            for risk in self.risks:
                lines.append(f"- {risk}")

        for symbol in self.symbols:
            lines.append(f"\n## {symbol}")

            if symbol in self.analysis:
                a = self.analysis[symbol]
                lines.append(f"\n### Valuation")
                if a.fair_value:
                    lines.append(f"- Fair Value: Rs. {a.fair_value}")
                if a.current_price:
                    lines.append(f"- Current Price: Rs. {a.current_price}")
                if a.margin_of_safety:
                    lines.append(f"- Margin of Safety: {a.margin_of_safety:.1f}%")

                if a.strengths:
                    lines.append(f"\n### Strengths")
                    for s in a.strengths:
                        lines.append(f"- {s}")

                if a.red_flags:
                    lines.append(f"\n### Red Flags")
                    for r in a.red_flags:
                        lines.append(f"- {r}")

        return "\n".join(lines)


@dataclass
class ComparisonReport:
    """Report comparing multiple stocks."""

    query: str
    symbols: list[str]
    summary: str
    winner: Optional[str] = None
    rankings: list[dict[str, Any]] = field(default_factory=list)
    comparison_table: dict[str, dict[str, Any]] = field(default_factory=dict)
    analysis: dict[str, AnalystOutput] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "symbols": self.symbols,
            "summary": self.summary,
            "winner": self.winner,
            "rankings": self.rankings,
            "comparison_table": self.comparison_table,
            "analysis": {k: v.to_dict() for k, v in self.analysis.items()},
            "generated_at": self.generated_at,
        }

    def to_markdown(self) -> str:
        """Convert to markdown comparison report."""
        lines = [f"# Stock Comparison Report"]
        lines.append(f"\n**Comparing:** {', '.join(self.symbols)}")
        lines.append(f"**Generated:** {self.generated_at}")

        lines.append(f"\n## Summary")
        lines.append(self.summary)

        if self.winner:
            lines.append(f"\n**Best Pick: {self.winner}**")

        if self.rankings:
            lines.append(f"\n## Rankings")
            for i, r in enumerate(self.rankings, 1):
                symbol = r.get("symbol", "")
                score = r.get("score", 0)
                lines.append(f"{i}. {symbol} (Score: {score})")

        if self.comparison_table:
            lines.append(f"\n## Comparison Table")
            lines.append(f"\n| Metric | {' | '.join(self.symbols)} |")
            lines.append(f"|--------|{'|'.join(['--------'] * len(self.symbols))}|")

            # Get all metrics
            all_metrics = set()
            for data in self.comparison_table.values():
                all_metrics.update(data.keys())

            for metric in sorted(all_metrics):
                values = []
                for symbol in self.symbols:
                    v = self.comparison_table.get(symbol, {}).get(metric, "N/A")
                    values.append(str(v))
                lines.append(f"| {metric} | {' | '.join(values)} |")

        return "\n".join(lines)
