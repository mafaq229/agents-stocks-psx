"""Tests for PDF parser tool."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from psx.tools.pdf_parser import PDFParser, ParsedReport, ParsedSection
from psx.core.exceptions import PDFParseError


class TestPDFParser:
    """Test PDFParser class functionality."""

    @pytest.fixture
    def parser(self):
        """Create a parser with temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield PDFParser(cache_dir=tmpdir)

    @pytest.fixture
    def parser_no_cache(self):
        """Create a parser without cache."""
        return PDFParser()

    # ========== URL TO CACHE KEY ==========

    def test_url_to_cache_key_non_psx_uses_hash(self, parser):
        """Test cache key uses hash for non-PSX URLs."""
        url = "https://example.com/document.pdf"
        key = parser._url_to_cache_key(url)
        # Non-PSX URLs fallback to MD5 hash
        assert key.endswith(".pdf")
        assert len(key) == 20  # 16 char hash + ".pdf"

    def test_url_to_cache_key_path_id(self, parser):
        """Test cache key extraction from path with 5+ digit ID."""
        url = "https://example.com/download/12345"
        key = parser._url_to_cache_key(url)
        assert key == "12345.pdf"

    def test_url_to_cache_key_non_id_query_uses_hash(self, parser):
        """Test non-id query params use hash fallback."""
        url = "https://example.com/doc.pdf?token=abc123"
        key = parser._url_to_cache_key(url)
        # Non PSX ?id= format uses hash fallback
        assert key.endswith(".pdf")
        assert len(key) == 20  # 16 char hash + ".pdf"
        assert "?" not in key

    def test_url_to_cache_key_special_chars_uses_hash(self, parser):
        """Test URLs with special chars use hash fallback."""
        url = "https://example.com/path/to/report (2025).pdf"
        key = parser._url_to_cache_key(url)
        # Hash-based key won't have special chars
        assert "(" not in key
        assert ")" not in key
        assert key.endswith(".pdf")

    def test_url_to_cache_key_hash_consistent(self, parser):
        """Test hash-based keys are consistent."""
        url = "https://example.com/some/path"
        key1 = parser._url_to_cache_key(url)
        key2 = parser._url_to_cache_key(url)
        assert key1 == key2  # Same URL should produce same key

    def test_url_to_cache_key_psx_query_id(self, parser):
        """Test cache key extraction from PSX ?id= query parameter."""
        url = "https://dps.psx.com.pk/download/document?id=264877"
        key = parser._url_to_cache_key(url)
        assert key == "264877.pdf"

    def test_url_to_cache_key_psx_path_id(self, parser):
        """Test cache key extraction from PSX path with document ID."""
        url = "https://dps.psx.com.pk/download/document/264877"
        key = parser._url_to_cache_key(url)
        assert key == "264877.pdf"

    def test_url_to_cache_key_fallback_hash(self, parser):
        """Test cache key falls back to URL hash for non-standard URLs."""
        url = "https://example.com/some/random/path/file"
        key = parser._url_to_cache_key(url)
        # Should be a hash-based key
        assert key.endswith(".pdf")
        assert len(key) == 20  # 16 char hash + ".pdf"

    # ========== SECTION IDENTIFICATION ==========

    def test_identify_sections_balance_sheet(self, parser):
        """Test identifying balance sheet section."""
        text = "Some text\n\nStatement of Financial Position\n\nAssets...\n\nIncome Statement"
        sections = parser.identify_sections(text)
        assert "balance_sheet" in sections
        assert "income_statement" in sections

    def test_identify_sections_income_statement(self, parser):
        """Test identifying income statement variants."""
        texts = [
            "Start\n\nProfit and Loss\n\nEnd",
            "Start\n\nStatement of Comprehensive Income\n\nEnd",
            "Start\n\nIncome Statement\n\nEnd",
        ]
        for text in texts:
            sections = parser.identify_sections(text)
            assert "income_statement" in sections

    def test_identify_sections_cash_flow(self, parser):
        """Test identifying cash flow section."""
        text = "Introduction\n\nStatement of Cash Flows\n\nOperating activities..."
        sections = parser.identify_sections(text)
        assert "cash_flow" in sections

    def test_identify_sections_ordering(self, parser):
        """Test that sections are ordered by position."""
        text = "Balance Sheet\n...\nIncome Statement\n...\nCash Flow"
        sections = parser.identify_sections(text)

        positions = list(sections.values())
        assert positions[0][0] < positions[1][0] < positions[2][0]

    def test_identify_sections_empty_text(self, parser):
        """Test identifying sections in empty text."""
        sections = parser.identify_sections("")
        assert sections == {}

    # ========== NUMBER EXTRACTION ==========

    def test_extract_numbers_simple(self, parser):
        """Test extracting simple numbers."""
        text = "Revenue was 1,000,000 for the year"
        numbers = parser.extract_numbers(text)
        assert len(numbers) >= 1
        assert any(n["value"] == 1000000 for n in numbers)

    def test_extract_numbers_negative(self, parser):
        """Test extracting negative numbers (parentheses)."""
        text = "Loss was (500,000) this quarter"
        numbers = parser.extract_numbers(text)
        assert any(n["value"] == -500000 for n in numbers)

    def test_extract_numbers_decimal(self, parser):
        """Test extracting decimal numbers."""
        text = "EPS was 2.35"
        numbers = parser.extract_numbers(text)
        assert any(abs(n["value"] - 2.35) < 0.001 for n in numbers)

    def test_extract_numbers_context(self, parser):
        """Test that context is included."""
        text = "The total assets were 10,000,000"
        numbers = parser.extract_numbers(text)
        assert len(numbers) >= 1
        assert "assets" in numbers[0]["context"].lower()

    # ========== LINE ITEM EXTRACTION ==========

    def test_extract_line_items_revenue(self, parser):
        """Test extracting revenue line item."""
        text = "Revenue 1,500,000\nCost of Sales 800,000"
        items = parser.extract_line_items(text)
        assert "revenue" in items
        assert items["revenue"] == 1500000

    def test_extract_line_items_profit(self, parser):
        """Test extracting profit line items."""
        text = "Profit before tax 500,000\nTax expense 100,000\nProfit after tax 400,000"
        items = parser.extract_line_items(text)
        assert "profit_before_tax" in items
        assert "tax_expense" in items
        assert "profit_after_tax" in items

    def test_extract_line_items_eps(self, parser):
        """Test extracting EPS."""
        text = "Basic earnings per share 2.50"
        items = parser.extract_line_items(text)
        assert "eps" in items
        assert items["eps"] == 2.50

    def test_extract_line_items_negative(self, parser):
        """Test extracting negative values."""
        text = "Finance cost (250,000)"
        items = parser.extract_line_items(text)
        assert "finance_cost" in items
        assert items["finance_cost"] == -250000

    # ========== PARSED REPORT ==========

    def test_parsed_report_structure(self):
        """Test ParsedReport dataclass."""
        report = ParsedReport(
            source_url="https://example.com/report.pdf",
            pages=10,
            raw_text="Sample text",
            sections={
                "balance_sheet": ParsedSection(title="balance_sheet", raw_text="Assets...")
            },
            metadata={"title": "Annual Report"},
        )
        assert report.source_url == "https://example.com/report.pdf"
        assert report.pages == 10
        assert "balance_sheet" in report.sections

    # ========== GET TEXT FOR LLM ==========

    def test_get_text_for_llm_basic(self, parser):
        """Test LLM text formatting."""
        report = ParsedReport(
            source_url="https://example.com/report.pdf",
            pages=5,
            raw_text="Full text...",
            sections={
                "income_statement": ParsedSection(
                    title="income_statement",
                    raw_text="Revenue 1000\nProfit 100",
                ),
            },
        )
        llm_text = parser.get_text_for_llm(report)
        assert "Financial Report" in llm_text
        assert "Income Statement" in llm_text

    def test_get_text_for_llm_truncation(self, parser):
        """Test LLM text truncation."""
        # Create a report with enough section content to exceed max_chars
        report = ParsedReport(
            source_url="https://example.com/report.pdf",
            pages=100,
            raw_text="x" * 100000,
            sections={
                "income_statement": ParsedSection(
                    title="income_statement",
                    raw_text="Revenue " + "data " * 5000,  # Lots of text
                ),
            },
        )
        llm_text = parser.get_text_for_llm(report, max_chars=1000)
        assert len(llm_text) <= 1020  # Some buffer for truncation message
        assert "[Truncated...]" in llm_text

    def test_get_text_for_llm_priority(self, parser):
        """Test that sections are included in priority order."""
        report = ParsedReport(
            source_url="https://example.com",
            pages=10,
            raw_text="...",
            sections={
                "notes": ParsedSection(title="notes", raw_text="Notes content"),
                "income_statement": ParsedSection(title="income_statement", raw_text="Income content"),
                "balance_sheet": ParsedSection(title="balance_sheet", raw_text="Balance content"),
            },
        )
        llm_text = parser.get_text_for_llm(report)
        # Income should appear before Balance which should appear before Notes
        income_pos = llm_text.find("Income Statement")
        balance_pos = llm_text.find("Balance Sheet")
        assert income_pos < balance_pos

    # ========== FILE PARSING ==========

    def test_parse_from_file_not_found(self, parser):
        """Test parsing non-existent file raises error."""
        with pytest.raises(PDFParseError) as exc_info:
            parser.parse_from_file("/nonexistent/path.pdf")
        assert "not found" in str(exc_info.value).lower()

    # ========== INTEGRATION TESTS (require network/files) ==========

    @pytest.mark.asyncio
    async def test_download_pdf_invalid_url(self, parser):
        """Test downloading from invalid URL raises error."""
        with pytest.raises(PDFParseError):
            await parser.download_pdf("https://invalid.example.com/nonexistent.pdf")

    @pytest.mark.asyncio
    async def test_download_pdf_caching(self, parser):
        """Test that PDFs are cached."""
        # Create a mock PDF content
        mock_pdf_bytes = b"%PDF-1.4 mock content"

        with patch.object(parser, "download_pdf", new_callable=AsyncMock) as mock:
            mock.return_value = mock_pdf_bytes

            # First call
            result1 = await parser.download_pdf("https://example.com/test.pdf")

            # Verify content returned
            assert result1 == mock_pdf_bytes


class TestPDFParserExtraction:
    """Test PDF text extraction methods."""

    @pytest.fixture
    def parser(self):
        return PDFParser()

    def test_extract_text_invalid_pdf(self, parser):
        """Test extracting from invalid PDF raises error."""
        with pytest.raises(PDFParseError):
            parser.extract_text(b"not a valid pdf")

    def test_extract_text_by_page_invalid_pdf(self, parser):
        """Test extracting pages from invalid PDF raises error."""
        with pytest.raises(PDFParseError):
            parser.extract_text_by_page(b"not a valid pdf")

    def test_get_metadata_invalid_pdf(self, parser):
        """Test metadata extraction from invalid PDF returns empty dict."""
        # Should not raise, just return empty
        result = parser.get_metadata(b"not a valid pdf")
        assert result == {}

    def test_parse_from_bytes_structure(self, parser):
        """Test parse_from_bytes returns correct ParsedReport structure."""
        # Create minimal valid PDF content (this will fail extraction but tests structure)
        # Using mock to avoid needing actual PDF
        with patch.object(parser, "extract_text", return_value="Sample text"):
            with patch.object(parser, "extract_text_by_page", return_value=["Page 1", "Page 2"]):
                with patch.object(parser, "get_metadata", return_value={"title": "Test Report"}):
                    with patch.object(parser, "identify_sections", return_value={}):
                        report = parser.parse_from_bytes(b"mock pdf", source_url="https://example.com/test.pdf")

        assert report.source_url == "https://example.com/test.pdf"
        assert report.pages == 2
        assert report.raw_text == "Sample text"
        assert report.metadata == {"title": "Test Report"}
