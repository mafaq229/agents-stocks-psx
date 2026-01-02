"""Data models for PSX Stock Analysis Platform.

Uses dataclasses for type safety and easy serialization.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class QuoteData:
    """Real-time market quote data."""

    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    ldcp: Optional[float] = None  # Last Day Close Price
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    pe_ratio: Optional[float] = None
    ytd_change_pct: Optional[float] = None
    year_change_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class CompanyData:
    """Company profile and reference data."""

    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    ceo: Optional[str] = None
    chairperson: Optional[str] = None
    company_secretary: Optional[str] = None
    auditor: Optional[str] = None
    registrar: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class EquityData:
    """Equity/shareholding data."""

    market_cap: Optional[float] = None
    shares_outstanding: Optional[int] = None
    free_float_shares: Optional[int] = None
    free_float_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class FinancialRow:
    """Single row from financial statements."""

    period: str  # "2025", "Q1 2026"
    period_type: str  # "annual", "quarterly"
    metric: str  # "Profit after Taxation", "EPS"
    value: Optional[float] = None
    raw_value: Optional[str] = None  # Original string

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RatioRow:
    """Single row from financial ratios."""

    period: str
    metric: str  # "Net Profit Margin", "EPS Growth"
    value: Optional[float] = None
    raw_value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnnouncementData:
    """Company announcement/news item."""

    date: str  # ISO format: "2025-11-10"
    title: str
    category: Optional[str] = None  # "financial_results", "board_meetings", "others"
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReportData:
    """Financial report (PDF) reference."""

    report_type: str  # "annual", "quarterly"
    period: str  # "2025", "2025-09-30"
    url: str
    local_path: Optional[str] = None
    text_path: Optional[str] = None
    is_downloaded: bool = False
    is_parsed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DividendData:
    """Dividend/payout information."""

    announcement_date: Optional[str] = None
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payment_date: Optional[str] = None
    dividend_type: Optional[str] = None  # "cash", "stock", "bonus"
    amount: Optional[float] = None
    percentage: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ScrapedData:
    """Complete scraped data for a company."""

    symbol: str
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_url: Optional[str] = None

    quote: Optional[QuoteData] = None
    company: Optional[CompanyData] = None
    equity: Optional[EquityData] = None
    financials: Dict[str, List[FinancialRow]] = field(default_factory=dict)  # annual, quarterly
    ratios: List[RatioRow] = field(default_factory=list)
    announcements: Dict[str, List[AnnouncementData]] = field(default_factory=dict)
    reports: List[ReportData] = field(default_factory=list)
    dividends: List[DividendData] = field(default_factory=list)
    risk_flags: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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
            "financials": {
                k: [row.to_dict() for row in v] for k, v in self.financials.items()
            },
            "ratios": [row.to_dict() for row in self.ratios],
            "announcements": {
                k: [ann.to_dict() for ann in v] for k, v in self.announcements.items()
            },
            "reports": [r.to_dict() for r in self.reports],
            "dividends": [d.to_dict() for d in self.dividends],
            "risk_flags": self.risk_flags,
        }
        return result
