"""PDF parser tool for extracting data from PSX financial reports.

This tool is designed to be called by agents for on-demand PDF analysis.
It handles downloading, text extraction, and structured data parsing.
"""

import re
import io
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pdfplumber
from pypdf import PdfReader

from psx.core.exceptions import PDFParseError

logger = logging.getLogger(__name__)


@dataclass
class ParsedSection:
    """A parsed section from a financial report."""

    title: str
    data: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


@dataclass
class ParsedReport:
    """Complete parsed financial report."""

    source_url: str
    pages: int
    raw_text: str
    sections: Dict[str, ParsedSection] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)


class PDFParser:
    """Tool for extracting and parsing PSX financial report PDFs.

    Designed for agent use - provides both raw text for LLM analysis
    and structured extraction for common financial statement formats.

    Example usage:
        parser = PDFParser()
        report = await parser.parse_from_url("https://dps.psx.com.pk/...")

        # For LLM agent - get raw text
        text = report.raw_text

        # For structured data
        balance_sheet = report.sections.get("balance_sheet")
    """

    # Common section headers in PSX reports
    SECTION_PATTERNS = {
        "balance_sheet": [
            r"(?i)balance\s*sheet",
            r"(?i)statement\s+of\s+financial\s+position",
            r"(?i)assets\s+and\s+liabilities",
        ],
        "income_statement": [
            r"(?i)income\s*statement",
            r"(?i)profit\s*(?:and|&)\s*loss",
            r"(?i)statement\s+of\s+(?:comprehensive\s+)?income",
            r"(?i)statement\s+of\s+profit\s+or\s+loss",
        ],
        "cash_flow": [
            r"(?i)cash\s*flow",
            r"(?i)statement\s+of\s+cash\s*flows?",
        ],
        "notes": [
            r"(?i)notes\s+to\s+(?:the\s+)?financial\s+statements?",
        ],
        "auditor_report": [
            r"(?i)auditor['']?s?\s+report",
            r"(?i)independent\s+auditor",
        ],
        "directors_report": [
            r"(?i)director['']?s?\s+report",
            r"(?i)board\s+of\s+directors",
        ],
    }

    # Common line item patterns for financial statements
    LINE_ITEM_PATTERNS = {
        # Balance Sheet items
        "total_assets": r"(?i)total\s+assets",
        "total_liabilities": r"(?i)total\s+liabilities",
        "total_equity": r"(?i)total\s+(?:shareholders?['']?\s+)?equity",
        "current_assets": r"(?i)(?:total\s+)?current\s+assets",
        "non_current_assets": r"(?i)(?:total\s+)?non[- ]current\s+assets",
        "current_liabilities": r"(?i)(?:total\s+)?current\s+liabilities",
        "non_current_liabilities": r"(?i)(?:total\s+)?non[- ]current\s+liabilities",
        "cash_and_equivalents": r"(?i)cash\s+(?:and\s+)?(?:cash\s+)?equivalents?",
        "trade_receivables": r"(?i)trade\s+(?:and\s+other\s+)?receivables?",
        "inventories": r"(?i)inventor(?:y|ies)",
        "property_plant_equipment": r"(?i)property[,]?\s+plant\s+(?:and|&)\s+equipment",
        "intangible_assets": r"(?i)intangible\s+assets?",
        "trade_payables": r"(?i)trade\s+(?:and\s+other\s+)?payables?",
        "borrowings": r"(?i)(?:short|long)[- ]term\s+borrowings?",
        "share_capital": r"(?i)(?:issued\s+)?share\s+capital",
        "retained_earnings": r"(?i)(?:un)?retained\s+(?:earnings?|profits?)",

        # Income Statement items
        "revenue": r"(?i)(?:net\s+)?(?:revenue|sales|turnover)",
        "cost_of_sales": r"(?i)cost\s+of\s+(?:sales|goods\s+sold|revenue)",
        "gross_profit": r"(?i)gross\s+profit",
        "operating_profit": r"(?i)(?:operating|profit\s+from\s+operations?)\s*(?:profit)?",
        "finance_cost": r"(?i)finance\s+cost",
        "profit_before_tax": r"(?i)profit\s+before\s+tax(?:ation)?",
        "tax_expense": r"(?i)(?:income\s+)?tax(?:ation)?\s*(?:expense)?",
        "profit_after_tax": r"(?i)profit\s+(?:after\s+tax|for\s+the\s+(?:year|period))",
        "eps": r"(?i)(?:basic\s+)?earnings?\s+per\s+share",

        # Cash Flow items
        "operating_cash_flow": r"(?i)(?:net\s+)?cash\s+(?:from|(?:used\s+)?in)\s+operating",
        "investing_cash_flow": r"(?i)(?:net\s+)?cash\s+(?:from|(?:used\s+)?in)\s+investing",
        "financing_cash_flow": r"(?i)(?:net\s+)?cash\s+(?:from|(?:used\s+)?in)\s+financing",
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize PDF parser.

        Args:
            cache_dir: Optional directory to cache downloaded PDFs
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def download_pdf(self, url: str) -> bytes:
        """
        Download PDF from URL.

        Args:
            url: URL to download PDF from

        Returns:
            PDF file bytes

        Raises:
            PDFParseError: If download fails
        """
        # Check cache first
        if self.cache_dir:
            cache_key = self._url_to_cache_key(url)
            cache_path = self.cache_dir / cache_key
            if cache_path.exists():
                logger.info(f"Using cached PDF: {cache_path}")
                return cache_path.read_bytes()

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                content = response.content

                # Cache if enabled
                if self.cache_dir:
                    cache_path.write_bytes(content)
                    logger.info(f"Cached PDF to: {cache_path}")

                return content

        except httpx.HTTPError as e:
            raise PDFParseError(f"Failed to download PDF: {e}", url=url)

    def extract_text(self, pdf_bytes: bytes) -> str:
        """
        Extract all text from PDF using pdfplumber (better than pypdf for most PDFs).

        Args:
            pdf_bytes: PDF file content as bytes

        Returns:
            Extracted text from all pages
        """
        try:
            text_parts = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")

            # Fallback to pypdf if pdfplumber returns nothing
            if not text_parts:
                logger.info("pdfplumber returned no text, trying pypdf fallback")
                reader = PdfReader(io.BytesIO(pdf_bytes))
                for page_num, page in enumerate(reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")

            return "\n\n".join(text_parts)

        except Exception as e:
            raise PDFParseError(f"Failed to extract text from PDF: {e}")

    def extract_text_by_page(self, pdf_bytes: bytes) -> List[str]:
        """
        Extract text from PDF, returning list of page texts.

        Args:
            pdf_bytes: PDF file content as bytes

        Returns:
            List of text strings, one per page
        """
        try:
            pages = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")

            # Fallback to pypdf if pdfplumber returns nothing
            if not any(pages):
                logger.info("pdfplumber returned no text, trying pypdf fallback")
                reader = PdfReader(io.BytesIO(pdf_bytes))
                pages = [page.extract_text() or "" for page in reader.pages]

            return pages

        except Exception as e:
            raise PDFParseError(f"Failed to extract text from PDF: {e}")

    def get_metadata(self, pdf_bytes: bytes) -> Dict[str, str]:
        """
        Extract PDF metadata.

        Args:
            pdf_bytes: PDF file content as bytes

        Returns:
            Dictionary of metadata fields
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            meta = reader.metadata or {}

            return {
                "title": meta.get("/Title", ""),
                "author": meta.get("/Author", ""),
                "creator": meta.get("/Creator", ""),
                "producer": meta.get("/Producer", ""),
                "creation_date": str(meta.get("/CreationDate", "")),
                "pages": str(len(reader.pages)),
            }

        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")
            return {}

    def identify_sections(self, text: str) -> Dict[str, tuple]:
        """
        Identify financial statement sections in text.

        Args:
            text: Full document text

        Returns:
            Dict mapping section name to (start_pos, end_pos) tuple
        """
        sections = {}

        for section_name, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    sections[section_name] = match.start()
                    break

        # Sort by position
        sorted_sections = sorted(sections.items(), key=lambda x: x[1])

        # Calculate end positions (start of next section)
        result = {}
        for i, (name, start) in enumerate(sorted_sections):
            if i + 1 < len(sorted_sections):
                end = sorted_sections[i + 1][1]
            else:
                end = len(text)
            result[name] = (start, end)

        return result

    def extract_numbers(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract number values with context from text.

        Useful for agents to identify key financial figures.

        Args:
            text: Text to parse

        Returns:
            List of dicts with 'value', 'context', 'position'
        """
        # Pattern for numbers (with commas, decimals, parentheses for negatives)
        number_pattern = r"[\(\-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?[\)]?"

        results = []
        for match in re.finditer(number_pattern, text):
            value_str = match.group()

            # Parse the number
            is_negative = "(" in value_str or value_str.startswith("-")
            cleaned = re.sub(r"[(),\-\s]", "", value_str)

            try:
                value = float(cleaned)
                if is_negative:
                    value = -value
            except ValueError:
                continue

            # Get context (surrounding text)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 20)
            context = text[start:end].replace("\n", " ").strip()

            results.append({
                "value": value,
                "raw": value_str,
                "context": context,
                "position": match.start(),
            })

        return results

    def extract_line_items(self, text: str) -> Dict[str, Optional[float]]:
        """
        Extract known financial line items from text.

        Args:
            text: Text to parse (ideally a specific section)

        Returns:
            Dict mapping line item names to extracted values
        """
        results = {}

        for item_name, pattern in self.LINE_ITEM_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                # Look for number after the match
                after_text = text[match.end():match.end() + 100]
                numbers = re.findall(r"[\(\-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?[\)]?", after_text)

                if numbers:
                    # Take first number found
                    value_str = numbers[0]
                    is_negative = "(" in value_str or value_str.startswith("-")
                    cleaned = re.sub(r"[(),\-\s]", "", value_str)

                    try:
                        value = float(cleaned)
                        if is_negative:
                            value = -value
                        results[item_name] = value
                    except ValueError:
                        results[item_name] = None
                else:
                    results[item_name] = None

        return results

    async def parse_from_url(self, url: str) -> ParsedReport:
        """
        Download and parse a PDF from URL.

        Main entry point for agents.

        Args:
            url: URL to PDF

        Returns:
            ParsedReport with all extracted data
        """
        pdf_bytes = await self.download_pdf(url)
        return self.parse_from_bytes(pdf_bytes, source_url=url)

    def parse_from_bytes(self, pdf_bytes: bytes, source_url: str = "") -> ParsedReport:
        """
        Parse PDF from bytes.

        Args:
            pdf_bytes: PDF content
            source_url: Original URL for reference

        Returns:
            ParsedReport with all extracted data
        """
        # Extract text
        raw_text = self.extract_text(pdf_bytes)
        pages = self.extract_text_by_page(pdf_bytes)
        metadata = self.get_metadata(pdf_bytes)

        # Identify sections
        section_positions = self.identify_sections(raw_text)

        # Parse each section
        sections = {}
        for section_name, (start, end) in section_positions.items():
            section_text = raw_text[start:end]
            line_items = self.extract_line_items(section_text)

            sections[section_name] = ParsedSection(
                title=section_name,
                data=line_items,
                raw_text=section_text,
            )

        return ParsedReport(
            source_url=source_url,
            pages=len(pages),
            raw_text=raw_text,
            sections=sections,
            metadata=metadata,
        )

    def parse_from_file(self, file_path: str) -> ParsedReport:
        """
        Parse PDF from local file.

        Args:
            file_path: Path to PDF file

        Returns:
            ParsedReport with all extracted data
        """
        path = Path(file_path)
        if not path.exists():
            raise PDFParseError(f"File not found: {file_path}")

        pdf_bytes = path.read_bytes()
        return self.parse_from_bytes(pdf_bytes, source_url=f"file://{path.absolute()}")

    def get_text_for_llm(self, report: ParsedReport, max_chars: int = 50000) -> str:
        """
        Get formatted text suitable for LLM context.

        Truncates if necessary, prioritizing financial statements.

        Args:
            report: Parsed report
            max_chars: Maximum characters to return

        Returns:
            Formatted text for LLM analysis
        """
        priority_sections = [
            "income_statement",
            "balance_sheet",
            "cash_flow",
            "auditor_report",
            "directors_report",
            "notes",
        ]

        parts = [f"# Financial Report\nSource: {report.source_url}\nPages: {report.pages}\n"]

        # Add sections in priority order
        for section_name in priority_sections:
            if section_name in report.sections:
                section = report.sections[section_name]
                parts.append(f"\n## {section_name.replace('_', ' ').title()}\n")
                parts.append(section.raw_text[:10000])  # Limit per section

        result = "\n".join(parts)

        if len(result) > max_chars:
            result = result[:max_chars] + "\n\n[Truncated...]"

        return result

    def _url_to_cache_key(self, url: str) -> str:
        """Convert URL to safe cache filename."""
        # Extract meaningful parts from URL
        filename = url.split("/")[-1]
        # Remove query params and existing extension
        filename = filename.split("?")[0]
        if filename.endswith(".pdf"):
            filename = filename[:-4]
        safe_chars = re.sub(r"[^\w\-.]", "_", filename)
        return safe_chars[:100] + ".pdf"
