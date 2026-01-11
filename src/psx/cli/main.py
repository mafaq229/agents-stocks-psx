"""Command-line interface for PSX Stock Analysis Platform."""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from psx.agents.supervisor import SupervisorAgent
from psx.scraper import PSXScraper
from psx.storage.data_store import DataStore
from psx.storage.database import init_database
from psx.tools.pdf_parser import PDFParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress noisy third-party loggers
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("pdfminer.psparser").setLevel(logging.WARNING)
logging.getLogger("pdfminer.pdfparser").setLevel(logging.WARNING)
logging.getLogger("pdfminer.pdfdocument").setLevel(logging.WARNING)
logging.getLogger("pdfminer.pdfpage").setLevel(logging.WARNING)
logging.getLogger("pdfminer.pdfinterp").setLevel(logging.WARNING)
logging.getLogger("pdfminer.converter").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def setup_file_logging(command: str, query: str = "") -> Path:
    """Set up file logging for verbose mode.

    Args:
        command: The CLI command being run (analyze, scrape, etc.)
        query: The query or symbols being analyzed

    Returns:
        Path to the log file
    """
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Create timestamped log file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = "".join(c if c.isalnum() else "_" for c in query[:30])
    log_file = logs_dir / f"{command}_{safe_query}_{timestamp}.log"

    # Set up file handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))

    # Add to root logger
    logging.getLogger().addHandler(file_handler)

    logger.info(f"Logging to file: {log_file}")
    return log_file


def save_output(command: str, query: str, report, output_format: str = "json") -> Path:
    """Save analysis output to file.

    Args:
        command: The CLI command (analyze, scrape, etc.)
        query: The query or symbols analyzed
        report: The report object with to_dict() and to_markdown() methods
        output_format: Format to save ("json" or "markdown")

    Returns:
        Path to the saved file
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = "".join(c if c.isalnum() else "_" for c in query[:30])

    # Always save JSON for traceability
    json_path = output_dir / f"{command}_{safe_query}_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)

    # Optionally save markdown
    if output_format == "markdown":
        md_path = output_dir / f"{command}_{safe_query}_{timestamp}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())
        return md_path

    return json_path


def setup_paths():
    """Add src to path for development mode."""
    src_path = Path(__file__).parent.parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


setup_paths()


async def scrape_command(args):
    """Handle scrape command."""
    # Initialize database
    logger.info("Initializing database...")
    init_database()

    # Initialize scraper and data store
    scraper = PSXScraper(headless=args.headless)
    store = DataStore()

    symbols = args.symbols

    for symbol in symbols:
        logger.info(f"Scraping {symbol}...")

        try:
            # Scrape data
            data = await scraper.scrape_company(symbol)

            if data.company:
                # Save to database
                company_id = store.save_company(data.company)

                if data.quote:
                    store.save_quote(company_id, data.quote, data.equity)

                if data.financials:
                    for period_type, rows in data.financials.items():
                        store.save_financials(company_id, rows)

                if data.ratios:
                    store.save_ratios(company_id, data.ratios)

                if data.announcements:
                    for category, anns in data.announcements.items():
                        for ann in anns:
                            store.save_announcement(company_id, ann)

                if data.reports:
                    for report in data.reports:
                        store.save_report(company_id, report)

                # Save cache
                cache_path = store.save_cache(symbol, data)
                logger.info(f"Data saved to {cache_path}")

                # Log success
                store.log_scrape(symbol, data.source_url or "", "success")

                # Print summary
                print_summary(data)

            else:
                logger.error(f"Failed to scrape {symbol}")
                store.log_scrape(symbol, "", "error", "No data returned")

        except Exception as e:
            logger.exception(f"Error scraping {symbol}: {e}")
            store.log_scrape(symbol, "", "error", str(e))


def print_summary(data):
    """Print scrape summary to console."""
    print("\n" + "=" * 50)
    print(f" REPORT: {data.symbol}")
    print("=" * 50)

    if data.company:
        print(f"\n[Company]")
        print(f"  Sector: {data.company.sector or 'N/A'}")
        if data.company.description:
            print(f"  Description: {data.company.description[:100]}...")

    if data.quote:
        print(f"\n[Quote]")
        print(f"  Price: {data.quote.price}")
        print(f"  Change: {data.quote.change} ({data.quote.change_pct}%)")
        print(f"  Volume: {data.quote.volume}")
        if data.quote.pe_ratio:
            print(f"  P/E Ratio: {data.quote.pe_ratio}")

    if data.equity:
        print(f"\n[Equity]")
        print(f"  Market Cap: {data.equity.market_cap}")
        print(f"  Shares: {data.equity.shares_outstanding}")

    if data.financials:
        print(f"\n[Financials]")
        for period_type, rows in data.financials.items():
            print(f"  {period_type.title()}: {len(rows)} metrics")

    if data.ratios:
        print(f"\n[Ratios]")
        print(f"  {len(data.ratios)} ratio entries")

    if data.announcements:
        print(f"\n[Announcements]")
        for category, anns in data.announcements.items():
            print(f"  {category}: {len(anns)} items")

    if data.reports:
        print(f"\n[Reports]")
        print(f"  {len(data.reports)} financial reports")

    print("\n" + "=" * 50)


def list_command(args):
    """Handle list command."""
    init_database()
    store = DataStore()

    companies = store.list_companies()

    if not companies:
        print("No companies in database. Run 'psx scrape <SYMBOL>' first.")
        return

    print(f"\nCompanies ({len(companies)}):")
    for symbol in companies:
        company = store.get_company(symbol)
        print(f"  {symbol}: {company.name or 'N/A'} ({company.sector or 'N/A'})")


def show_command(args):
    """Handle show command."""
    init_database()
    store = DataStore()

    data = store.get_cache(args.symbol)

    if not data:
        print(f"No data found for {args.symbol}. Run 'psx scrape {args.symbol}' first.")
        return

    print(json.dumps(data, indent=2))


def analyze_command(args):
    """Handle analyze command."""
    init_database()

    # Set logging level and file logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log_file = setup_file_logging("analyze", args.query)
        print(f"📝 Verbose logs saved to: {log_file}\n")

    print(f"Analyzing {args.query}...")
    print("This may take a few minutes as agents gather and analyze data.\n")

    supervisor = SupervisorAgent()
    report = supervisor.analyze(args.query)

    # Save output to file
    output_path = save_output("analyze", args.query, report, args.output)
    print(f"📁 Report saved to: {output_path}\n")

    # Output based on format
    if args.output == "json":
        print(json.dumps(report.to_dict(), indent=2, default=str))
    elif args.output == "markdown":
        print(report.to_markdown())
    else:
        # Default: summary view
        print("\n" + "=" * 60)
        print(f" ANALYSIS REPORT: {', '.join(report.symbols)}")
        print("=" * 60)

        # Business overview
        if report.business_overview:
            print(f"\n[Business Overview]")
            print(f"  {report.business_overview[:300]}...")

        # Recommendation
        print(f"\n[Recommendation]")
        print(f"  {report.recommendation} (Confidence: {report.confidence:.0%})")

        # Reasoning
        if report.reasoning:
            print(f"\n[Investment Thesis]")
            print(f"  {report.reasoning}")

        # Valuation
        if report.fair_value:
            print(f"\n[Valuation]")
            print(f"  Fair Value: Rs. {report.fair_value:,.2f}")
            if report.margin_of_safety is not None:
                status = "undervalued" if report.margin_of_safety > 0 else "overvalued"
                print(f"  Margin of Safety: {report.margin_of_safety:.1f}% ({status})")

        # Strengths
        if report.strengths:
            print(f"\n[Strengths]")
            for s in report.strengths[:3]:
                if isinstance(s, dict):
                    print(f"  • {s.get('point', s)}")
                else:
                    print(f"  • {s}")

        # Risks
        if report.risks:
            print(f"\n[Risks]")
            for r in report.risks[:3]:
                if isinstance(r, dict):
                    print(f"  • {r.get('point', r)}")
                else:
                    print(f"  • {r}")

        # Suggested action
        if report.entry_price or report.target_price:
            print(f"\n[Suggested Action]")
            if report.entry_price:
                print(f"  Entry Price: Rs. {report.entry_price:,.2f}")
            if report.target_price:
                print(f"  Target Price: Rs. {report.target_price:,.2f}")
            if report.stop_loss:
                print(f"  Stop-Loss: Rs. {report.stop_loss:,.2f}")

        print("\n" + "=" * 60)
        print("Run with --output markdown for detailed 7-section report")


async def parse_pdf_command(args):
    """Handle parse-pdf command."""
    parser = PDFParser(cache_dir="data/cache/pdfs")

    try:
        if args.url.startswith("http"):
            logger.info(f"Downloading and parsing: {args.url}")
            report = await parser.parse_from_url(args.url)
        else:
            logger.info(f"Parsing local file: {args.url}")
            report = parser.parse_from_file(args.url)

        print(f"\n✓ Successfully parsed PDF")
        print(f"  Pages: {report.pages}")
        print(f"  Text length: {len(report.raw_text)} chars")
        print(f"  Sections found: {list(report.sections.keys())}")

        if args.text:
            # Output raw text
            print("\n--- Extracted Text ---")
            print(report.raw_text[:args.max_chars] if args.max_chars else report.raw_text)
        elif args.llm:
            # Output LLM-formatted text
            print("\n--- LLM-Formatted Text ---")
            print(parser.get_text_for_llm(report, max_chars=args.max_chars or 50000))
        else:
            # Output structured data
            print("\n--- Sections ---")
            for section_name, section in report.sections.items():
                print(f"\n[{section_name}]")
                if section.data:
                    for k, v in section.data.items():
                        if v is not None:
                            print(f"  {k}: {v}")
                else:
                    print("  (no line items extracted)")

    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PSX Stock Analysis Platform",
        prog="psx",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape company data from PSX")
    scrape_parser.add_argument(
        "symbols",
        nargs="+",
        help="Stock symbols to scrape (e.g., LSECL GHNI ENGRO)",
    )
    scrape_parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        default=True,
        help="Run browser in visible mode",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List scraped companies")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show company data")
    show_parser.add_argument("symbol", help="Stock symbol")

    # Parse PDF command
    pdf_parser = subparsers.add_parser("parse-pdf", help="Parse a financial report PDF")
    pdf_parser.add_argument("url", help="URL or local path to PDF")
    pdf_parser.add_argument(
        "--text",
        action="store_true",
        help="Output raw extracted text",
    )
    pdf_parser.add_argument(
        "--llm",
        action="store_true",
        help="Output LLM-formatted text (prioritizes financial sections)",
    )
    pdf_parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Maximum characters to output",
    )

    # Analyze command (multi-agent analysis)
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a stock using multi-agent system",
    )
    analyze_parser.add_argument(
        "query",
        help="Analysis query (e.g., 'OGDC', 'Should I buy PPL?')",
    )
    analyze_parser.add_argument(
        "--output",
        choices=["summary", "json", "markdown"],
        default="summary",
        help="Output format (default: summary)",
    )
    analyze_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.command == "scrape":
        asyncio.run(scrape_command(args))
    elif args.command == "list":
        list_command(args)
    elif args.command == "show":
        show_command(args)
    elif args.command == "parse-pdf":
        asyncio.run(parse_pdf_command(args))
    elif args.command == "analyze":
        analyze_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
