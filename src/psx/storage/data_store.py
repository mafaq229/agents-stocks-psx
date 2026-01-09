"""Unified data access layer for all agents.

Abstracts SQLite and file system operations behind a clean API.
"""

import json
import hashlib
from pathlib import Path
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from psx.storage.database import Database, get_database
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
from psx.core.exceptions import DatabaseError


class DataStore:
    """
    Unified data access layer for all agents.
    Handles SQLite operations and file system caching.
    """

    def __init__(
        self,
        db_path: str = "data/db/psx.db",
        cache_dir: str = "data/cache",
        documents_dir: str = "data/documents",
    ):
        """
        Initialize data store.

        Args:
            db_path: Path to SQLite database
            cache_dir: Directory for JSON cache files
            documents_dir: Directory for PDF documents
        """
        self.db = get_database(db_path)
        self.cache_dir = Path(cache_dir)
        self.documents_dir = Path(documents_dir)

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    # ========== COMPANY OPERATIONS ==========

    def save_company(self, data: CompanyData) -> int:
        """
        Save or update company profile.

        Returns:
            company_id
        """
        cursor = self.db.execute(
            """
            INSERT INTO companies (
                symbol, name, sector, description, ceo, chairperson,
                company_secretary, auditor, registrar, fiscal_year_end,
                website, address, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                sector = excluded.sector,
                description = excluded.description,
                ceo = excluded.ceo,
                chairperson = excluded.chairperson,
                company_secretary = excluded.company_secretary,
                auditor = excluded.auditor,
                registrar = excluded.registrar,
                fiscal_year_end = excluded.fiscal_year_end,
                website = excluded.website,
                address = excluded.address,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                data.symbol,
                data.name,
                data.sector,
                data.description,
                data.ceo,
                data.chairperson,
                data.company_secretary,
                data.auditor,
                data.registrar,
                data.fiscal_year_end,
                data.website,
                data.address,
            ),
        )
        self.db.commit()

        # Get the company_id
        cursor = self.db.execute(
            "SELECT id FROM companies WHERE symbol = ?", (data.symbol,)
        )
        row = cursor.fetchone()
        return row["id"]

    def get_company(self, symbol: str) -> Optional[CompanyData]:
        """Get company by symbol."""
        cursor = self.db.execute(
            "SELECT * FROM companies WHERE symbol = ?", (symbol,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return CompanyData(
            symbol=row["symbol"],
            name=row["name"],
            sector=row["sector"],
            description=row["description"],
            ceo=row["ceo"],
            chairperson=row["chairperson"],
            company_secretary=row["company_secretary"],
            auditor=row["auditor"],
            registrar=row["registrar"],
            fiscal_year_end=row["fiscal_year_end"],
            website=row["website"],
            address=row["address"],
        )

    def get_company_id(self, symbol: str) -> Optional[int]:
        """Get company ID by symbol."""
        cursor = self.db.execute(
            "SELECT id FROM companies WHERE symbol = ?", (symbol,)
        )
        row = cursor.fetchone()
        return row["id"] if row else None

    def get_companies_by_sector(self, sector: str) -> List[CompanyData]:
        """Get all companies in a sector."""
        cursor = self.db.execute(
            "SELECT * FROM companies WHERE sector = ?", (sector,)
        )

        return [
            CompanyData(
                symbol=row["symbol"],
                name=row["name"],
                sector=row["sector"],
                description=row["description"],
                ceo=row["ceo"],
                chairperson=row["chairperson"],
                company_secretary=row["company_secretary"],
                auditor=row["auditor"],
                registrar=row["registrar"],
                fiscal_year_end=row["fiscal_year_end"],
                website=row["website"],
                address=row["address"],
            )
            for row in cursor.fetchall()
        ]

    def list_companies(self) -> List[str]:
        """List all company symbols."""
        cursor = self.db.execute("SELECT symbol FROM companies ORDER BY symbol")
        return [row["symbol"] for row in cursor.fetchall()]

    # ========== QUOTE OPERATIONS ==========

    def save_quote(
        self,
        company_id: int,
        quote: QuoteData,
        equity: Optional[EquityData] = None,
        quote_date: Optional[date] = None,
    ) -> None:
        """Save daily quote data."""
        quote_date = quote_date or date.today()

        self.db.execute(
            """
            INSERT INTO quotes (
                company_id, date, price, change, change_pct, open, high, low,
                volume, ldcp, week_52_high, week_52_low, pe_ratio,
                ytd_change_pct, year_change_pct, market_cap,
                shares_outstanding, free_float_shares, free_float_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, date) DO UPDATE SET
                price = excluded.price,
                change = excluded.change,
                change_pct = excluded.change_pct,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                volume = excluded.volume,
                ldcp = excluded.ldcp,
                week_52_high = excluded.week_52_high,
                week_52_low = excluded.week_52_low,
                pe_ratio = excluded.pe_ratio,
                ytd_change_pct = excluded.ytd_change_pct,
                year_change_pct = excluded.year_change_pct,
                market_cap = excluded.market_cap,
                shares_outstanding = excluded.shares_outstanding,
                free_float_shares = excluded.free_float_shares,
                free_float_pct = excluded.free_float_pct
            """,
            (
                company_id,
                quote_date.isoformat(),
                quote.price,
                quote.change,
                quote.change_pct,
                quote.open,
                quote.high,
                quote.low,
                quote.volume,
                quote.ldcp,
                quote.week_52_high,
                quote.week_52_low,
                quote.pe_ratio,
                quote.ytd_change_pct,
                quote.year_change_pct,
                equity.market_cap if equity else None,
                equity.shares_outstanding if equity else None,
                equity.free_float_shares if equity else None,
                equity.free_float_pct if equity else None,
            ),
        )
        self.db.commit()

    def get_latest_quote(self, symbol: str) -> Optional[QuoteData]:
        """Get most recent quote for a company."""
        cursor = self.db.execute(
            """
            SELECT q.* FROM quotes q
            JOIN companies c ON q.company_id = c.id
            WHERE c.symbol = ?
            ORDER BY q.date DESC LIMIT 1
            """,
            (symbol,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return QuoteData(
            price=row["price"],
            change=row["change"],
            change_pct=row["change_pct"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            volume=row["volume"],
            ldcp=row["ldcp"],
            week_52_high=row["week_52_high"],
            week_52_low=row["week_52_low"],
            pe_ratio=row["pe_ratio"],
            ytd_change_pct=row["ytd_change_pct"],
            year_change_pct=row["year_change_pct"],
        )

    # ========== FINANCIAL OPERATIONS ==========

    def save_financials(
        self, company_id: int, rows: List[FinancialRow]
    ) -> None:
        """Save financial statement rows."""
        for row in rows:
            self.db.execute(
                """
                INSERT INTO financials (
                    company_id, period, period_type, metric, value, raw_value
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, period, period_type, metric) DO UPDATE SET
                    value = excluded.value,
                    raw_value = excluded.raw_value
                """,
                (
                    company_id,
                    row.period,
                    row.period_type,
                    row.metric,
                    row.value,
                    row.raw_value,
                ),
            )
        self.db.commit()

    def get_financials(
        self,
        symbol: str,
        period_type: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> List[FinancialRow]:
        """Get financial data with optional filters."""
        sql = """
            SELECT f.* FROM financials f
            JOIN companies c ON f.company_id = c.id
            WHERE c.symbol = ?
        """
        params: List[Any] = [symbol]

        if period_type:
            sql += " AND f.period_type = ?"
            params.append(period_type)

        if metrics:
            placeholders = ",".join("?" * len(metrics))
            sql += f" AND f.metric IN ({placeholders})"
            params.extend(metrics)

        sql += " ORDER BY f.period DESC, f.metric"

        cursor = self.db.execute(sql, tuple(params))

        return [
            FinancialRow(
                period=row["period"],
                period_type=row["period_type"],
                metric=row["metric"],
                value=row["value"],
                raw_value=row["raw_value"],
            )
            for row in cursor.fetchall()
        ]

    # ========== RATIO OPERATIONS ==========

    def save_ratios(self, company_id: int, rows: List[RatioRow]) -> None:
        """Save financial ratio rows."""
        for row in rows:
            self.db.execute(
                """
                INSERT INTO ratios (
                    company_id, period, metric, value, raw_value
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(company_id, period, metric) DO UPDATE SET
                    value = excluded.value,
                    raw_value = excluded.raw_value
                """,
                (
                    company_id,
                    row.period,
                    row.metric,
                    row.value,
                    row.raw_value,
                ),
            )
        self.db.commit()

    def get_ratios(self, symbol: str) -> List[RatioRow]:
        """Get all ratios for a company."""
        cursor = self.db.execute(
            """
            SELECT r.* FROM ratios r
            JOIN companies c ON r.company_id = c.id
            WHERE c.symbol = ?
            ORDER BY r.period DESC, r.metric
            """,
            (symbol,),
        )

        return [
            RatioRow(
                period=row["period"],
                metric=row["metric"],
                value=row["value"],
                raw_value=row["raw_value"],
            )
            for row in cursor.fetchall()
        ]

    # ========== ANNOUNCEMENT OPERATIONS ==========

    def _hash_announcement(self, ann: AnnouncementData) -> str:
        """Create hash for announcement deduplication."""
        content = f"{ann.date}|{ann.title}|{ann.url}"
        return hashlib.md5(content.encode()).hexdigest()

    def save_announcement(
        self, company_id: int, ann: AnnouncementData
    ) -> None:
        """Save announcement (with deduplication)."""
        content_hash = self._hash_announcement(ann)

        self.db.execute(
            """
            INSERT INTO announcements (
                company_id, date, title, category, url, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, content_hash) DO NOTHING
            """,
            (
                company_id,
                ann.date,
                ann.title,
                ann.category,
                ann.url,
                content_hash,
            ),
        )
        self.db.commit()

    def get_announcements(
        self,
        symbol: str,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> List[AnnouncementData]:
        """Get announcements with filters."""
        sql = """
            SELECT a.* FROM announcements a
            JOIN companies c ON a.company_id = c.id
            WHERE c.symbol = ?
        """
        params: List[Any] = [symbol]

        if category:
            sql += " AND a.category = ?"
            params.append(category)

        if start_date:
            sql += " AND a.date >= ?"
            params.append(start_date)

        if end_date:
            sql += " AND a.date <= ?"
            params.append(end_date)

        sql += " ORDER BY a.date DESC LIMIT ?"
        params.append(limit)

        cursor = self.db.execute(sql, tuple(params))

        return [
            AnnouncementData(
                date=row["date"],
                title=row["title"],
                category=row["category"],
                url=row["url"],
            )
            for row in cursor.fetchall()
        ]

    # ========== REPORT OPERATIONS ==========

    def save_report(self, company_id: int, report: ReportData) -> int:
        """Save report metadata."""
        cursor = self.db.execute(
            """
            INSERT INTO reports (
                company_id, report_type, period, url, local_path,
                text_path, is_downloaded, is_parsed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, report_type, period) DO UPDATE SET
                url = excluded.url,
                local_path = excluded.local_path,
                text_path = excluded.text_path,
                is_downloaded = excluded.is_downloaded,
                is_parsed = excluded.is_parsed
            """,
            (
                company_id,
                report.report_type,
                report.period,
                report.url,
                report.local_path,
                report.text_path,
                report.is_downloaded,
                report.is_parsed,
            ),
        )
        self.db.commit()

        cursor = self.db.execute(
            """
            SELECT id FROM reports
            WHERE company_id = ? AND report_type = ? AND period = ?
            """,
            (company_id, report.report_type, report.period),
        )
        return cursor.fetchone()["id"]

    def get_reports(self, symbol: str) -> List[ReportData]:
        """Get all reports for a company."""
        cursor = self.db.execute(
            """
            SELECT r.* FROM reports r
            JOIN companies c ON r.company_id = c.id
            WHERE c.symbol = ?
            ORDER BY r.period DESC
            """,
            (symbol,),
        )

        return [
            ReportData(
                report_type=row["report_type"],
                period=row["period"],
                url=row["url"],
                local_path=row["local_path"],
                text_path=row["text_path"],
                is_downloaded=bool(row["is_downloaded"]),
                is_parsed=bool(row["is_parsed"]),
            )
            for row in cursor.fetchall()
        ]

    # ========== CACHE OPERATIONS ==========

    def save_cache(self, symbol: str, data: ScrapedData) -> Path:
        """Save scraped data to JSON cache."""
        cache_path = self.cache_dir / symbol
        cache_path.mkdir(exist_ok=True)

        file_path = cache_path / "latest.json"
        with open(file_path, "w") as f:
            json.dump(data.to_dict(), f, indent=2)

        return file_path

    def get_cache(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached data for a company."""
        file_path = self.cache_dir / symbol / "latest.json"

        if not file_path.exists():
            return None

        with open(file_path) as f:
            return json.load(f)

    # ========== SCRAPE LOG ==========

    def log_scrape(
        self,
        symbol: str,
        source_url: str,
        status: str,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Log a scrape attempt."""
        company_id = self.get_company_id(symbol)

        self.db.execute(
            """
            INSERT INTO scrape_log (
                company_id, symbol, source_url, status, error_message, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (company_id, symbol, source_url, status, error_message, duration_ms),
        )
        self.db.commit()

    # ========== AGGREGATE QUERIES ==========
    # TODO: look into the calculation (see which info is useful for comparison analysis). also accuracy of output
    def get_sector_averages(self, sector: str) -> Dict[str, Any]:
        """Get comprehensive average metrics for a sector.

        Returns averages, min/max ranges, and company count for sector benchmarking.
        """
        # Get quote-based metrics
        cursor = self.db.execute(
            """
            SELECT
                COUNT(DISTINCT c.symbol) as company_count,
                AVG(q.pe_ratio) as avg_pe,
                MIN(q.pe_ratio) as min_pe,
                MAX(q.pe_ratio) as max_pe,
                AVG(q.price) as avg_price,
                AVG(q.market_cap) as avg_market_cap,
                AVG(q.change_pct) as avg_change_pct,
                AVG(q.ytd_change_pct) as avg_ytd_change
            FROM quotes q
            JOIN companies c ON q.company_id = c.id
            WHERE c.sector = ?
            AND q.date = (SELECT MAX(date) FROM quotes WHERE company_id = q.company_id)
            """,
            (sector,),
        )

        row = cursor.fetchone()

        result = {
            "sector": sector,
            "company_count": row["company_count"] or 0,
            "avg_pe": row["avg_pe"],
            "min_pe": row["min_pe"],
            "max_pe": row["max_pe"],
            "avg_price": row["avg_price"],
            "avg_market_cap": row["avg_market_cap"],
            "avg_change_pct": row["avg_change_pct"],
            "avg_ytd_change": row["avg_ytd_change"],
        }

        # Get profit margin averages from ratios table
        try:
            margin_cursor = self.db.execute(
                """
                SELECT AVG(r.value) as avg_profit_margin
                FROM ratios r
                JOIN companies c ON r.company_id = c.id
                WHERE c.sector = ?
                AND r.metric LIKE '%Profit Margin%'
                AND r.period = (
                    SELECT MAX(r2.period) FROM ratios r2
                    WHERE r2.company_id = r.company_id AND r2.metric = r.metric
                )
                """,
                (sector,),
            )
            margin_row = margin_cursor.fetchone()
            if margin_row and margin_row["avg_profit_margin"]:
                result["avg_profit_margin"] = margin_row["avg_profit_margin"]
        except Exception:
            pass

        # Get EPS growth averages from ratios
        try:
            eps_cursor = self.db.execute(
                """
                SELECT AVG(r.value) as avg_eps_growth
                FROM ratios r
                JOIN companies c ON r.company_id = c.id
                WHERE c.sector = ?
                AND r.metric LIKE '%EPS Growth%'
                AND r.period = (
                    SELECT MAX(r2.period) FROM ratios r2
                    WHERE r2.company_id = r.company_id AND r2.metric = r.metric
                )
                """,
                (sector,),
            )
            eps_row = eps_cursor.fetchone()
            if eps_row and eps_row["avg_eps_growth"]:
                result["avg_eps_growth"] = eps_row["avg_eps_growth"]
        except Exception:
            pass

        return result

    # ========== CONSOLIDATED SAVE OPERATIONS ==========

    def save_scraped_data(self, data: ScrapedData) -> Optional[int]:
        """Save all scraped data for a company in one operation.

        Consolidates saving company, quote, financials, ratios,
        announcements, reports, and cache.

        Args:
            data: ScrapedData object containing all scraped info

        Returns:
            company_id if successful, None if no company data
        """
        if not data.company:
            return None

        # Save company and get ID
        company_id = self.save_company(data.company)

        # Save quote with equity data
        if data.quote:
            self.save_quote(company_id, data.quote, data.equity)

        # Save financials (handle dict format: {period_type: [rows]})
        if data.financials:
            if isinstance(data.financials, dict):
                for period_type, rows in data.financials.items():
                    self.save_financials(company_id, rows)
            else:
                # Handle list format
                self.save_financials(company_id, data.financials)

        # Save ratios
        if data.ratios:
            self.save_ratios(company_id, data.ratios)

        # Save announcements (handle dict format: {category: [anns]})
        if data.announcements:
            if isinstance(data.announcements, dict):
                for category, anns in data.announcements.items():
                    for ann in anns:
                        self.save_announcement(company_id, ann)
            else:
                # Handle list format
                for ann in data.announcements:
                    self.save_announcement(company_id, ann)

        # Save reports
        if data.reports:
            for report in data.reports:
                self.save_report(company_id, report)

        # Save to JSON cache
        self.save_cache(data.company.symbol, data)

        return company_id
