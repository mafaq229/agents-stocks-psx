"""Data Agent for retrieving stock information.

Responsible for fetching data from the PSX website and database.
"""

import asyncio
import json
import logging
import re
from typing import Any, Optional

from psx.agents.base import BaseAgent, AgentConfig
from psx.agents.llm import Tool
from psx.agents.schemas import DataAgentOutput
from psx.core.models import ScrapedData
from psx.core.config import get_config
from psx.storage.data_store import DataStore
from psx.scraper.psx_scraper import PSXScraper


logger = logging.getLogger(__name__)


# ========== HELPER FUNCTIONS ==========

def _get_data_store() -> DataStore:
    """Get or create DataStore instance."""
    return DataStore()


def _scrape_and_save(symbol: str, headless: bool = True) -> dict[str, Any]:
    """Internal helper to scrape company data and save to database.

    Args:
        symbol: Stock ticker symbol (e.g., OGDC)
        headless: Run browser in headless mode

    Returns:
        Dict with status info or error
    """
    symbol = symbol.upper()
    logger.info(f"Scraping data for {symbol}")

    try:
        scraper = PSXScraper(headless=headless)

        # Run async scraper
        loop = asyncio.new_event_loop()
        try:
            data: ScrapedData = loop.run_until_complete(scraper.scrape_company(symbol))
        finally:
            loop.close()

        # Save to database using consolidated method
        store = _get_data_store()
        company_id = store.save_scraped_data(data)

        if company_id:
            return {"status": "success", "symbol": symbol, "company_id": company_id}
        else:
            return {"error": f"Failed to save data for {symbol}", "symbol": symbol}

    except Exception as e:
        logger.error(f"Failed to scrape {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}


def _build_company_response(symbol: str, store: DataStore) -> dict[str, Any]:
    """Build full company data response from database.

    Args:
        symbol: Stock ticker symbol
        store: DataStore instance

    Returns:
        Dict with all company data
    """
    result: dict[str, Any] = {"symbol": symbol}

    company = store.get_company(symbol)
    if company:
        result["company"] = company.to_dict()
        result["sector"] = company.sector

    quote = store.get_latest_quote(symbol)
    if quote:
        result["quote"] = quote.to_dict()

    financials = store.get_financials(symbol)
    if financials:
        result["financials"] = [f.to_dict() for f in financials]

    ratios = store.get_ratios(symbol)
    if ratios:
        result["ratios"] = [r.to_dict() for r in ratios]

    reports = store.get_reports(symbol)
    if reports:
        result["reports"] = [r.to_dict() for r in reports]

    announcements = store.get_announcements(symbol)
    if announcements:
        result["announcements"] = [a.to_dict() for a in announcements]

    return result


def _get_market_cap(symbol: str, store: DataStore) -> Optional[float]:
    """Get market cap for a symbol from quotes table."""
    try:
        cursor = store.db.execute(
            """
            SELECT market_cap FROM quotes q
            JOIN companies c ON q.company_id = c.id
            WHERE c.symbol = ?
            ORDER BY q.date DESC LIMIT 1
            """,
            (symbol,),
        )
        row = cursor.fetchone()
        return row["market_cap"] if row else None
    except Exception:
        return None


def _get_latest_eps(symbol: str, store: DataStore) -> Optional[float]:
    """Get latest EPS from financials table."""
    try:
        financials = store.get_financials(symbol, period_type="annual", metrics=["EPS"])
        if financials:
            eps_rows = [f for f in financials if f.metric == "EPS"]
            if eps_rows:
                return eps_rows[0].value
    except Exception:
        pass
    return None


def _get_web_search_client():
    """Get Tavily search client if API key is available."""
    config = get_config()
    if config.tavily_api_key:
        from psx.tools.web_search import TavilySearch
        return TavilySearch(api_key=config.tavily_api_key)
    return None


def _discover_peers_from_web(
    company_name: str, sector: Optional[str] = None
) -> list[str]:
    """Discover peer symbols via web search.

    Args:
        company_name: Company name to find competitors for
        sector: Industry sector (optional, improves accuracy)

    Returns:
        List of discovered peer symbols
    """
    client = _get_web_search_client()
    if not client:
        logger.warning("Web search not available - TAVILY_API_KEY not set")
        return []

    try:
        response = client.search_competitors(company_name, sector)

        # Extract potential stock symbols from results
        # PSX symbols are typically 3-6 uppercase letters
        symbol_pattern = r'\b([A-Z]{3,6})\b'
        found_symbols = set()

        # Common words to exclude (not stock symbols)
        exclude_words = {
            "PSX", "KSE", "THE", "AND", "FOR", "CEO", "CFO", "LTD", "PVT",
            "INC", "LLP", "PKR", "USD", "EPS", "ROE", "ROI", "ETF", "IPO",
            "AGM", "EGM", "BOD", "PDF", "URL", "WWW", "COM",
            "NET", "ORG", "GOV", "EDU", "PAK", "PER", "YOY", "QOQ", "FY",
            "HY", "QTR", "MOM", "DAD", "JAN", "FEB", "MAR", "APR", "MAY",
            "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
        }

        # Search in answer
        if response.answer:
            matches = re.findall(symbol_pattern, response.answer)
            for m in matches:
                if m not in exclude_words and len(m) >= 3:
                    found_symbols.add(m)

        # NOTE: Search in results content (only if answer is insufficient)
        if not found_symbols:
            for result in response.results:
                if result.content:
                    matches = re.findall(symbol_pattern, result.content)
                    for m in matches:
                        if m not in exclude_words and len(m) >= 3:
                            found_symbols.add(m)

        logger.info(f"Discovered {len(found_symbols)} potential peer symbols from web")
        return list(found_symbols)

    except Exception as e:
        logger.error(f"Peer discovery search failed: {e}")
        return []


# ========== TOOL IMPLEMENTATIONS ==========

def get_company_data(symbol: str) -> dict[str, Any]:
    """Get company data from database. Auto-scrapes if not found.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dict with full company data (quote, financials, ratios, reports, announcements)
    """
    symbol = symbol.upper()
    store = _get_data_store()

    # Check if company exists in database
    company = store.get_company(symbol)

    if not company:
        # Auto-scrape if not in database
        logger.info(f"{symbol} not in database, scraping...")
        scrape_result = _scrape_and_save(symbol)

        if "error" in scrape_result:
            return {
                "symbol": symbol,
                "error": f"Company not in database and scrape failed: {scrape_result['error']}",
                "data_freshness": "scrape_failed",
            }

        # Data freshness indicator
        data = _build_company_response(symbol, store)
        data["data_freshness"] = "freshly_scraped"
        return data

    # Return from database
    data = _build_company_response(symbol, store)
    data["data_freshness"] = "from_database"
    return data


def get_sector_peers(
    symbol: str,
    max_peers: int = 5,
    auto_discover: bool = True,
    fetch_data: bool = True,
    include_sector_averages: bool = True,
) -> dict[str, Any]:
    """Get peer symbols, their financial data, and sector averages in one call.

    First checks database for peers. If none found and auto_discover=True,
    searches the web for competitor symbols. If fetch_data=True, automatically
    fetches financial data for all peers. If include_sector_averages=True,
    also returns sector benchmark metrics.

    Args:
        symbol: Stock ticker symbol
        max_peers: Maximum number of peers to return (default 5)
        auto_discover: If True, discover peers via web search when DB is empty
        fetch_data: If True, auto-fetch financial data for each peer (default True)
        include_sector_averages: If True, include sector average metrics (default True)

    Returns:
        Dict with sector, peer symbols, peer financial data, and sector averages
    """
    symbol = symbol.upper()
    store = _get_data_store()

    company = store.get_company(symbol)

    # Company must exist in DB - use get_company_data first
    if not company:
        return {
            "symbol": symbol,
            "error": f"{symbol} not in database. Call get_company_data first.",
        }

    sector = company.sector
    peer_symbols = []

    # Try to get peers from database first
    if sector:
        peers = store.get_companies_by_sector(sector)
        peer_symbols = [p.symbol for p in peers if p.symbol != symbol][:max_peers]

    result: dict[str, Any] = {
        "symbol": symbol,
        "sector": sector,
        "peers": peer_symbols,
        "peer_count": len(peer_symbols),
        "source": "database" if peer_symbols else None,
    }

    # If no peers in DB and auto_discover is enabled, search the web
    if not peer_symbols and auto_discover:
        logger.info(f"No peers in DB for {symbol}, discovering from web...")
        company_name = company.name or symbol
        discovered = _discover_peers_from_web(company_name, sector)

        if discovered:
            # Filter out the target symbol
            discovered = [s for s in discovered if s != symbol][:max_peers]
            result["peers"] = discovered
            result["peer_count"] = len(discovered)
            result["source"] = "web_discovery"
            logger.info(f"Discovered peers for {symbol}: {discovered}")
        else:
            result["note"] = "No peers found in database or via web search"

    # Auto-fetch peer data if requested and we have peers
    if fetch_data and result["peers"]:
        logger.info(f"Auto-fetching data for {len(result['peers'])} peers...")
        peer_data_list = []
        for peer_symbol in result["peers"]:
            try:
                peer_info = get_peer_data(peer_symbol)
                if "error" not in peer_info:
                    peer_data_list.append(peer_info)
                    logger.debug(f"Fetched peer data for {peer_symbol}")
                else:
                    logger.warning(f"Failed to get peer data for {peer_symbol}: {peer_info.get('error')}")
            except Exception as e:
                logger.warning(f"Error fetching peer data for {peer_symbol}: {e}")

        result["peer_data"] = peer_data_list
        result["peers_fetched"] = len(peer_data_list)

    # Include sector averages for benchmarking
    if include_sector_averages and sector:
        logger.debug(f"Fetching sector averages for {sector}")
        result["sector_averages"] = store.get_sector_averages(sector)

    return result


def get_peer_data(symbol: str) -> dict[str, Any]:
    """Get financial summary for a peer company. Auto-scrapes if not in DB.

    Use this to get financial data for peer comparison after discovering
    peer symbols via get_sector_peers or ResearchAgent.

    Args:
        symbol: Stock ticker symbol of the peer

    Returns:
        Dict with peer financial summary (price, P/E, market cap, EPS, etc.)
    """
    symbol = symbol.upper()
    store = _get_data_store()

    company = store.get_company(symbol)

    # Auto-scrape if not in database
    if not company:
        logger.info(f"Peer {symbol} not in database, scraping...")
        scrape_result = _scrape_and_save(symbol)

        if "error" in scrape_result:
            return {
                "symbol": symbol,
                "error": f"Failed to get peer data: {scrape_result['error']}",
            }

        company = store.get_company(symbol)
        if not company:
            return {"symbol": symbol, "error": f"Failed to get data for {symbol}"}

    # Build financial summary for peer comparison
    quote = store.get_latest_quote(symbol)

    result: dict[str, Any] = {
        "symbol": symbol,
        "name": company.name,
        "sector": company.sector,
    }

    if quote:
        result.update({
            "price": quote.price,
            "change_pct": quote.change_pct,
            "pe_ratio": quote.pe_ratio,
            "week_52_high": quote.week_52_high,
            "week_52_low": quote.week_52_low,
        })

    # Get market cap
    market_cap = _get_market_cap(symbol, store)
    if market_cap:
        result["market_cap"] = market_cap

    # Get EPS
    eps = _get_latest_eps(symbol, store)
    if eps:
        result["eps"] = eps

    # Get profit margin from ratios
    try:
        ratios = store.get_ratios(symbol)
        margin_rows = [r for r in ratios if "profit margin" in r.metric.lower()]
        if margin_rows:
            result["profit_margin"] = margin_rows[0].value
    except Exception:
        pass

    return result


def list_companies() -> dict[str, Any]:
    """List all companies in the database.

    Returns:
        Dict with list of company symbols
    """
    store = _get_data_store()
    symbols = store.list_companies()
    return {"companies": symbols, "count": len(symbols)}


# Tool definitions
DATA_AGENT_TOOLS = [
    Tool(
        name="get_company_data",
        description="Get full company data (quote, financials, ratios, reports, announcements). Auto-scrapes from PSX website if not in database.",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., OGDC, PPL, ENGRO)",
                },
            },
            "required": ["symbol"],
        },
        function=get_company_data,
    ),
    Tool(
        name="get_sector_peers",
        description="Get peer symbols, their financial data, AND sector averages in one call. Checks DB first, discovers via web search if empty, auto-fetches peer financials, and includes sector benchmarks. Returns peers, peer_data, and sector_averages.",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol",
                },
                "max_peers": {
                    "type": "integer",
                    "description": "Maximum number of peers to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["symbol"],
        },
        function=get_sector_peers,
    ),
    Tool(
        name="list_companies",
        description="List all companies available in the database.",
        parameters={
            "type": "object",
            "properties": {},
        },
        function=list_companies,
    ),
]


DATA_AGENT_SYSTEM_PROMPT = """You are a Data Agent specialized in retrieving stock market data for Pakistan Stock Exchange (PSX) companies.

Your responsibilities:
1. Fetch company data using get_company_data (auto-scrapes if not in DB)
2. Get peers, their data, AND sector averages using get_sector_peers (all in one call)
3. Report any data gaps or issues

WORKFLOW (only 2 tool calls needed):
1. Call get_company_data(symbol) - returns full company data, auto-scrapes if needed
2. Call get_sector_peers(symbol) - returns peers, peer_data, AND sector_averages in one call

IMPORTANT: get_sector_peers now includes EVERYTHING:
- Peer discovery (from DB or web search)
- Peer financial data (auto-fetched)
- Sector averages (for benchmarking)

Guidelines:
- get_company_data auto-scrapes if company not in database
- get_sector_peers returns peers + peer_data + sector_averages in one response
- Report any missing data fields as "data_gaps"

When you have gathered all necessary data, respond with a JSON object containing:
{
    "symbol": "...",
    "quote": {...},
    "company": {...},
    "financials": [...],
    "ratios": [...],
    "reports": [...],
    "announcements": [...],
    "sector": "...",
    "peers": [...],
    "peer_data": [{"symbol": "...", "price": ..., "pe_ratio": ..., "market_cap": ...}, ...],
    "sector_averages": {"avg_pe": ..., "avg_market_cap": ..., ...},
    "data_gaps": [...],
    "data_freshness": "from_database" or "freshly_scraped"
}

Be efficient - only 2 tool calls are needed for complete data gathering."""


class DataAgent(BaseAgent):
    """Agent for retrieving stock data."""

    def __init__(self, **kwargs):
        config = AgentConfig(
            name="DataAgent",
            description="Retrieves stock data from PSX website and database",
            system_prompt=DATA_AGENT_SYSTEM_PROMPT,
            max_iterations=5,
            max_tokens=6144,  # Moderate output for JSON with company data
        )
        super().__init__(config=config, tools=DATA_AGENT_TOOLS, **kwargs)

    def run(self, task: str, context: Optional[dict[str, Any]] = None) -> DataAgentOutput:
        """Run the data agent and return structured output.

        Args:
            task: Task description (usually includes symbol)
            context: Optional context

        Returns:
            DataAgentOutput with retrieved data
        """
        result = super().run(task, context)

        # Parse result into DataAgentOutput
        return self._parse_to_output(result)

    def _parse_to_output(self, result: dict[str, Any]) -> DataAgentOutput:
        """Convert agent result to DataAgentOutput."""
        from psx.core.models import (
            QuoteData,
            CompanyData,
            FinancialRow,
            RatioRow,
            ReportData,
            AnnouncementData,
        )

        # Handle nested output
        if "output" in result:
            # Try to parse JSON from output string
            try:
                if isinstance(result["output"], str):
                    import re
                    # Find JSON in output
                    json_match = re.search(r'\{[\s\S]*\}', result["output"])
                    if json_match:
                        parsed = json.loads(json_match.group())
                        # Only use parsed result if it's a dict
                        if isinstance(parsed, dict):
                            result = parsed
            except json.JSONDecodeError:
                pass

        # Extract symbol from multiple possible locations
        symbol = result.get("symbol")
        if not symbol or symbol == "UNKNOWN":
            # Try _meta.symbol (from scraped data)
            if "_meta" in result and isinstance(result["_meta"], dict):
                symbol = result["_meta"].get("symbol")
            # Try company.symbol
            if not symbol and "company" in result and isinstance(result["company"], dict):
                symbol = result["company"].get("symbol")
        symbol = symbol or "UNKNOWN"

        # Parse quote
        quote = None
        if "quote" in result and result["quote"]:
            q = result["quote"]
            quote = QuoteData(
                price=q.get("price"),
                change=q.get("change"),
                change_pct=q.get("change_pct"),
                volume=q.get("volume"),
                open=q.get("open"),
                high=q.get("high"),
                low=q.get("low"),
                ldcp=q.get("ldcp"),
                week_52_high=q.get("week_52_high"),
                week_52_low=q.get("week_52_low"),
                pe_ratio=q.get("pe_ratio"),
            )

        # Parse company
        company = None
        if "company" in result and result["company"]:
            c = result["company"]
            company = CompanyData(
                symbol=c.get("symbol", symbol),
                name=c.get("name"),
                sector=c.get("sector"),
                description=c.get("description"),
                ceo=c.get("ceo"),
            )

        # Parse financials - handle both flat list (from DB) and dict by period_type (from cache)
        financials = []
        if "financials" in result:
            fin_data = result.get("financials", [])
            if isinstance(fin_data, dict):
                # Cache format: {"annual": [...], "quarterly": [...]}
                for period_type, items in fin_data.items():
                    for f in items:
                        financials.append(FinancialRow(
                            period=f.get("period", ""),
                            period_type=period_type,
                            metric=f.get("metric", ""),
                            value=f.get("value"),
                        ))
            else:
                # Database format: flat list
                for f in fin_data:
                    financials.append(FinancialRow(
                        period=f.get("period", ""),
                        period_type=f.get("period_type", "annual"),
                        metric=f.get("metric", ""),
                        value=f.get("value"),
                    ))

        # Parse ratios
        ratios = []
        if "ratios" in result:
            for r in result.get("ratios", []):
                ratios.append(RatioRow(
                    period=r.get("period", ""),
                    metric=r.get("metric", ""),
                    value=r.get("value"),
                ))

        # Parse reports
        reports = []
        if "reports" in result:
            for r in result.get("reports", []):
                reports.append(ReportData(
                    report_type=r.get("report_type", ""),
                    period=r.get("period", ""),
                    url=r.get("url", ""),
                ))

        # Parse announcements - include URL for PDF parsing
        # Handle both flat list (from DB) and dict by category (from cache)
        announcements = []
        if "announcements" in result:
            ann_data = result.get("announcements", [])
            if isinstance(ann_data, dict):
                # Cache format: {"financial_results": [...], "board_meetings": [...], "others": [...]}
                for category, items in ann_data.items():
                    for a in items:
                        announcements.append(AnnouncementData(
                            date=a.get("date", ""),
                            title=a.get("title", ""),
                            category=category,
                            url=a.get("url"),
                        ))
            else:
                # Database format: flat list
                for a in ann_data:
                    announcements.append(AnnouncementData(
                        date=a.get("date", ""),
                        title=a.get("title", ""),
                        category=a.get("category"),
                        url=a.get("url"),
                    ))

        # Parse peer_data into PeerDataSnapshot objects
        from psx.agents.schemas import PeerDataSnapshot
        peer_data = []
        if "peer_data" in result and result["peer_data"]:
            for p in result["peer_data"]:
                peer_data.append(PeerDataSnapshot(
                    symbol=p.get("symbol", ""),
                    name=p.get("name"),
                    sector=p.get("sector"),
                    price=p.get("price"),
                    change_pct=p.get("change_pct"),
                    pe_ratio=p.get("pe_ratio"),
                    market_cap=p.get("market_cap"),
                    eps=p.get("eps"),
                    profit_margin=p.get("profit_margin"),
                    week_52_high=p.get("week_52_high"),
                    week_52_low=p.get("week_52_low"),
                ))

        # Get sector from company if not at top level
        sector = result.get("sector")
        if not sector and company:
            sector = company.sector

        return DataAgentOutput(
            symbol=symbol,
            quote=quote,
            company=company,
            financials=financials,
            ratios=ratios,
            reports=reports,
            announcements=announcements,
            peers=result.get("peers", []),
            peer_data=peer_data,
            sector=sector,
            sector_averages=result.get("sector_averages"),
            data_gaps=result.get("data_gaps", []),
            data_freshness=result.get("data_freshness"),
        )
