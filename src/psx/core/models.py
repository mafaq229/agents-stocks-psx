"""Data models for PSX Stock Analysis Platform.

Uses dataclasses for type safety and easy serialization.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class QuoteData:
    """Real-time market quote data."""

    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    ldcp: float | None = None  # Last Day Close Price
    week_52_high: float | None = None
    week_52_low: float | None = None
    pe_ratio: float | None = None
    ytd_change_pct: float | None = None
    year_change_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CompanyData:
    """Company profile and reference data."""

    symbol: str
    name: str | None = None
    sector: str | None = None
    description: str | None = None
    ceo: str | None = None
    chairperson: str | None = None
    company_secretary: str | None = None
    auditor: str | None = None
    registrar: str | None = None
    fiscal_year_end: str | None = None
    website: str | None = None
    address: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class EquityData:
    """Equity/shareholding data."""

    market_cap: float | None = None
    shares_outstanding: int | None = None
    free_float_shares: int | None = None
    free_float_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class FinancialRow:
    """Single row from financial statements."""

    period: str  # "2025", "Q1 2026"
    period_type: str  # "annual", "quarterly"
    metric: str  # "Profit after Taxation", "EPS"
    value: float | None = None
    raw_value: str | None = None  # Original string

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RatioRow:
    """Single row from financial ratios."""

    period: str
    metric: str  # "Net Profit Margin", "EPS Growth"
    value: float | None = None
    raw_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnnouncementData:
    """Company announcement/news item."""

    date: str  # ISO format: "2025-11-10"
    title: str
    category: str | None = None  # "financial_results", "board_meetings", "others"
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportData:
    """Financial report (PDF) reference."""

    report_type: str  # "annual", "quarterly"
    period: str  # "2025", "2025-09-30"
    url: str
    local_path: str | None = None
    text_path: str | None = None
    is_downloaded: bool = False
    is_parsed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DividendData:
    """Dividend/payout information."""

    announcement_date: str | None = None
    ex_date: str | None = None
    record_date: str | None = None
    payment_date: str | None = None
    dividend_type: str | None = None  # "cash", "stock", "bonus"
    amount: float | None = None
    percentage: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ScrapedData:
    """Complete scraped data for a company."""

    symbol: str
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_url: str | None = None

    quote: QuoteData | None = None
    company: CompanyData | None = None
    equity: EquityData | None = None
    financials: dict[str, list[FinancialRow]] = field(default_factory=dict)  # annual, quarterly
    ratios: list[RatioRow] = field(default_factory=list)
    announcements: dict[str, list[AnnouncementData]] = field(default_factory=dict)
    reports: list[ReportData] = field(default_factory=list)
    dividends: list[DividendData] = field(default_factory=list)
    risk_flags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "_meta": {
                "symbol": self.symbol,
                "scraped_at": self.scraped_at,
                "source_url": self.source_url,
            },
            "quote": self.quote.to_dict() if self.quote else {},
            "company": self.company.to_dict() if self.company else {},
            "equity": self.equity.to_dict() if self.equity else {},
            "financials": {k: [row.to_dict() for row in v] for k, v in self.financials.items()},
            "ratios": [row.to_dict() for row in self.ratios],
            "announcements": {
                k: [ann.to_dict() for ann in v] for k, v in self.announcements.items()
            },
            "reports": [r.to_dict() for r in self.reports],
            "dividends": [d.to_dict() for d in self.dividends],
            "risk_flags": self.risk_flags,
        }
        return result
