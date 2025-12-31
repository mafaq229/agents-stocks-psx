"""PSX web scraper for company financial data.

Uses Playwright for browser automation to scrape dynamic content
from the Pakistan Stock Exchange website.
"""

import asyncio
import re
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Page

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
from psx.core.exceptions import ScraperError
from psx.utils.parsers import (
    parse_price,
    parse_number,
    parse_negative,
    parse_percent,
    parse_date,
    parse_volume,
    parse_change_with_percent,
    parse_52_week_range,
)
from psx.scraper import selectors


class PSXScraper:
    """Scraper for Pakistan Stock Exchange company data."""

    BASE_URL = "https://dps.psx.com.pk/company/"

    def __init__(self, headless: bool = True):
        """
        Initialize scraper.

        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless

    async def scrape_company(self, symbol: str) -> ScrapedData:
        """
        Scrape all data for a company.

        Args:
            symbol: Stock symbol (e.g., "LSECL")

        Returns:
            ScrapedData with all available data
        """
        url = f"{self.BASE_URL}{symbol}"
        start_time = time.time()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})

            try:
                response = await page.goto(url, timeout=60000)

                if response.status != 200:
                    raise ScraperError(
                        f"Failed to load page. Status: {response.status}",
                        symbol=symbol,
                        url=url,
                    )

                # Wait for page to load
                await page.wait_for_selector(selectors.QUOTE_PRICE, timeout=10000)

                # Scrape all sections
                quote = await self._scrape_quote(page)
                company = await self._scrape_company_info(page, symbol)
                equity = await self._scrape_equity(page)
                financials = await self._scrape_financials(page)
                ratios = await self._scrape_ratios(page)
                announcements = await self._scrape_announcements(page)
                reports = await self._scrape_reports(page)

                return ScrapedData(
                    symbol=symbol,
                    scraped_at=datetime.utcnow().isoformat() + "Z",
                    source_url=url,
                    quote=quote,
                    company=company,
                    equity=equity,
                    financials=financials,
                    ratios=ratios,
                    announcements=announcements,
                    reports=reports,
                )

            except Exception as e:
                raise ScraperError(str(e), symbol=symbol, url=url)

            finally:
                await browser.close()

    async def _scrape_quote(self, page: Page) -> QuoteData:
        """Scrape real-time quote data."""
        try:
            # Price
            price_el = await page.wait_for_selector(selectors.QUOTE_PRICE, timeout=5000)
            price_text = await price_el.inner_text() if price_el else ""
            price = parse_price(price_text)

            # Change
            change_el = await page.query_selector(selectors.QUOTE_CHANGE)
            change_text = await change_el.inner_text() if change_el else ""
            change, change_pct = parse_change_with_percent(change_text.replace("\n", " "))

            # Volume
            volume = None
            try:
                vol_el = page.locator(selectors.STATS_ITEM).filter(
                    has_text=re.compile("Volume", re.IGNORECASE)
                ).locator(selectors.STATS_VALUE)
                if await vol_el.count() > 0:
                    volume_text = await vol_el.first.inner_text()
                    volume = parse_volume(volume_text)
            except:
                pass

            # P/E Ratio
            pe_ratio = None
            try:
                pe_el = page.locator(selectors.STATS_ITEM).filter(
                    has_text=re.compile("P/E", re.IGNORECASE)
                ).locator(selectors.STATS_VALUE)
                if await pe_el.count() > 0:
                    pe_text = await pe_el.first.inner_text()
                    pe_ratio = parse_number(pe_text)
            except:
                pass

            # 52-week range
            week_52_low, week_52_high = None, None
            try:
                range_el = page.locator(selectors.STATS_ITEM).filter(
                    has_text=re.compile("52.*Week", re.IGNORECASE)
                ).locator(selectors.STATS_VALUE)
                if await range_el.count() > 0:
                    range_text = await range_el.first.inner_text()
                    week_52_low, week_52_high = parse_52_week_range(range_text)
            except:
                pass

            # YTD Change
            ytd_change_pct = None
            try:
                ytd_el = page.locator(selectors.STATS_ITEM).filter(
                    has_text=re.compile("YTD", re.IGNORECASE)
                ).locator(selectors.STATS_VALUE)
                if await ytd_el.count() > 0:
                    ytd_text = await ytd_el.first.inner_text()
                    ytd_change_pct = parse_percent(ytd_text)
            except:
                pass

            return QuoteData(
                price=price,
                change=change,
                change_pct=change_pct,
                volume=volume,
                pe_ratio=pe_ratio,
                week_52_high=week_52_high,
                week_52_low=week_52_low,
                ytd_change_pct=ytd_change_pct,
            )

        except Exception as e:
            print(f"Error scraping quote: {e}")
            return QuoteData()

    async def _scrape_company_info(self, page: Page, symbol: str) -> CompanyData:
        """Scrape company profile information."""
        try:
            # Description
            description = None
            try:
                desc_el = page.locator(selectors.PROFILE_DESCRIPTION).first
                if await desc_el.count() > 0:
                    description = await desc_el.inner_text()
                    description = description.strip()
            except:
                pass

            # Sector - look for sector info in profile
            sector = None
            try:
                # Sector is usually in profile section header or stats
                sector_el = page.locator("text=Sector").locator("xpath=following-sibling::*[1]")
                if await sector_el.count() > 0:
                    sector = await sector_el.inner_text()
            except:
                pass

            return CompanyData(
                symbol=symbol,
                description=description,
                sector=sector,
            )

        except Exception as e:
            print(f"Error scraping company info: {e}")
            return CompanyData(symbol=symbol)

    async def _scrape_equity(self, page: Page) -> EquityData:
        """Scrape equity/shareholding data."""
        try:
            values = await page.locator(selectors.EQUITY_STATS).all_inner_texts()

            market_cap = None
            shares = None

            if len(values) >= 1:
                market_cap = parse_number(values[0])
            if len(values) >= 2:
                shares = parse_volume(values[1])

            return EquityData(
                market_cap=market_cap,
                shares_outstanding=shares,
            )

        except Exception as e:
            print(f"Error scraping equity: {e}")
            return EquityData()

    async def _scrape_financials(self, page: Page) -> Dict[str, List[FinancialRow]]:
        """Scrape financial statements (annual and quarterly)."""
        financials = {}

        # Annual
        try:
            annual_rows = await self._scrape_table(page, selectors.ANNUAL_PANEL)
            if not annual_rows:
                annual_rows = await self._scrape_table(page, selectors.FINANCIALS_TABLE)

            if annual_rows:
                financials["annual"] = self._parse_financial_rows(annual_rows, "annual")
        except Exception as e:
            print(f"Error scraping annual financials: {e}")

        # Quarterly
        try:
            toggle = page.locator(selectors.QUARTERLY_TOGGLE)
            if await toggle.count() > 0:
                await toggle.click(force=True)
                await page.wait_for_timeout(1000)

                quarterly_rows = await self._scrape_table(page, selectors.QUARTERLY_PANEL)
                if quarterly_rows:
                    financials["quarterly"] = self._parse_financial_rows(quarterly_rows, "quarterly")
        except Exception as e:
            print(f"Error scraping quarterly financials: {e}")

        return financials

    async def _scrape_ratios(self, page: Page) -> List[RatioRow]:
        """Scrape financial ratios."""
        try:
            ratio_tab = page.locator(selectors.RATIOS_TAB)
            if await ratio_tab.count() > 0:
                await ratio_tab.first.click(force=True)
                await page.wait_for_timeout(1000)

            rows = await self._scrape_table(page, selectors.RATIOS_TABLE)
            return self._parse_ratio_rows(rows)

        except Exception as e:
            print(f"Error scraping ratios: {e}")
            return []

    async def _scrape_announcements(self, page: Page) -> Dict[str, List[AnnouncementData]]:
        """Scrape company announcements."""
        announcements = {}

        try:
            ann_tab = page.locator(selectors.ANNOUNCEMENTS_TAB)
            if await ann_tab.count() > 0:
                await ann_tab.first.click(force=True)
                await page.wait_for_timeout(1000)

            for tab in ["Financial Results", "Board Meetings", "Others"]:
                try:
                    sub_tab = page.locator(f"div.tabs__list__item[data-name='{tab}']")
                    if await sub_tab.count() > 0:
                        await sub_tab.click(force=True)
                        await page.wait_for_timeout(1000)

                        selector = f"div.tabs__panel[data-name='{tab}'] table"
                        items = await self._scrape_announcement_table(page, selector)

                        category = tab.lower().replace(" ", "_")
                        announcements[category] = [
                            AnnouncementData(
                                date=parse_date(item["date"]) or item["date"],
                                title=item["title"],
                                url=item.get("url"),
                                category=category,
                            )
                            for item in items
                        ]

                except Exception as e:
                    print(f"Skip announcement tab {tab}: {e}")

        except Exception as e:
            print(f"Error scraping announcements: {e}")

        return announcements

    async def _scrape_reports(self, page: Page) -> List[ReportData]:
        """Scrape financial reports (PDFs)."""
        try:
            rep_tab = page.locator(selectors.REPORTS_TAB)
            if await rep_tab.count() > 0:
                await rep_tab.first.click(force=True)
                await page.wait_for_timeout(1000)

            items = await self._scrape_announcement_table(page, selectors.REPORTS_TABLE)

            reports = []
            for item in items:
                report_type = "quarterly" if "Quarterly" in item.get("date", "") else "annual"
                reports.append(
                    ReportData(
                        report_type=report_type,
                        period=item.get("title", ""),
                        url=item.get("url", ""),
                    )
                )

            return reports

        except Exception as e:
            print(f"Error scraping reports: {e}")
            return []

    async def _scrape_table(self, page: Page, selector: str) -> List[Dict[str, str]]:
        """Generic table scraper."""
        data = []
        try:
            # Handle selector formatting
            if "table" not in selector and ".tbl" not in selector and "[" not in selector:
                selector += " table"

            rows = await page.locator(f"{selector} tr").all()
            if not rows:
                return []

            # Get headers
            header_cells = await rows[0].locator("th, td").all()
            headers = [await cell.inner_text() for cell in header_cells]

            if headers and headers[0].strip() == "":
                headers[0] = "Metric"

            # Get data rows
            for i in range(1, len(rows)):
                cells = await rows[i].locator("td").all()
                row_vals = [await cell.inner_text() for cell in cells]

                if len(row_vals) == len(headers):
                    data.append(dict(zip(headers, row_vals)))

        except Exception as e:
            pass

        return data

    async def _scrape_announcement_table(
        self, page: Page, selector: str = None
    ) -> List[Dict[str, str]]:
        """Scrape announcement/report tables."""
        data = []
        try:
            target_selector = selector or selectors.COMPANY_ANNOUNCEMENTS_TABLE
            rows = await page.locator(f"{target_selector} tr").all()

            for i in range(1, len(rows)):
                cells = await rows[i].locator("td").all()

                if len(cells) >= 2:
                    date = await cells[0].inner_text()
                    title = await cells[1].inner_text()

                    # Find PDF link
                    link = None
                    row_links = await rows[i].locator("a").all()

                    for lnk in reversed(row_links):
                        href = await lnk.get_attribute("href")
                        if href and (".pdf" in href or "DownloadPDF" in href):
                            link = href
                            break

                    if not link and row_links:
                        link = await row_links[-1].get_attribute("href")

                    if link and not link.startswith("http"):
                        link = "https://dps.psx.com.pk" + link

                    data.append({
                        "date": date.strip(),
                        "title": title.strip(),
                        "url": link,
                    })

        except Exception as e:
            print(f"Error scraping announcement table: {e}")

        return data

    def _parse_financial_rows(
        self, table_data: List[Dict[str, str]], period_type: str
    ) -> List[FinancialRow]:
        """Convert table data to FinancialRow objects."""
        rows = []

        for row_data in table_data:
            metric = row_data.get("Metric", "")
            if not metric:
                continue

            for key, value in row_data.items():
                if key == "Metric":
                    continue

                rows.append(
                    FinancialRow(
                        period=key,
                        period_type=period_type,
                        metric=metric,
                        value=parse_negative(value),
                        raw_value=value,
                    )
                )

        return rows

    def _parse_ratio_rows(self, table_data: List[Dict[str, str]]) -> List[RatioRow]:
        """Convert table data to RatioRow objects."""
        rows = []

        for row_data in table_data:
            metric = row_data.get("Metric", "")
            if not metric:
                continue

            for key, value in row_data.items():
                if key == "Metric":
                    continue

                rows.append(
                    RatioRow(
                        period=key,
                        metric=metric,
                        value=parse_percent(value),
                        raw_value=value,
                    )
                )

        return rows


async def scrape_companies(symbols: List[str], headless: bool = True) -> Dict[str, ScrapedData]:
    """
    Scrape multiple companies.

    Args:
        symbols: List of stock symbols
        headless: Run browser in headless mode

    Returns:
        Dict mapping symbol to ScrapedData
    """
    scraper = PSXScraper(headless=headless)
    results = {}

    for symbol in symbols:
        try:
            results[symbol] = await scraper.scrape_company(symbol)
        except Exception as e:
            print(f"Failed to scrape {symbol}: {e}")

    return results
