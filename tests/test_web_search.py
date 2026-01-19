"""Tests for web search tool."""

import pytest
from unittest.mock import patch, MagicMock

from psx.tools.web_search import (
    SearchResult,
    SearchResponse,
    TavilySearch,
    format_search_for_llm,
)


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_instantiation(self):
        """Test creating search result."""
        result = SearchResult(
            title="Test Article",
            url="https://example.com/article",
            content="This is the article content.",
            score=0.95,
            published_date="2025-01-15",
        )
        assert result.title == "Test Article"
        assert result.score == 0.95

    def test_default_values(self):
        """Test default values."""
        result = SearchResult(
            title="Test",
            url="https://example.com",
            content="Content",
        )
        assert result.score == 0.0
        assert result.published_date is None

    def test_to_dict(self):
        """Test to_dict includes all fields."""
        result = SearchResult(
            title="Test",
            url="https://example.com",
            content="Content",
            score=0.8,
            published_date="2025-01-15",
        )
        d = result.to_dict()
        assert d["title"] == "Test"
        assert d["url"] == "https://example.com"
        assert d["content"] == "Content"
        assert d["score"] == 0.8
        assert d["published_date"] == "2025-01-15"


class TestSearchResponse:
    """Test SearchResponse dataclass."""

    def test_instantiation(self):
        """Test creating search response."""
        response = SearchResponse(
            query="test query",
            results=[
                SearchResult(title="R1", url="https://1.com", content="C1"),
                SearchResult(title="R2", url="https://2.com", content="C2"),
            ],
            answer="This is the AI-generated answer.",
            search_time=1.5,
        )
        assert response.query == "test query"
        assert len(response.results) == 2
        assert response.answer is not None

    def test_default_values(self):
        """Test default values."""
        response = SearchResponse(query="test")
        assert response.results == []
        assert response.answer is None
        assert response.search_time == 0.0

    def test_to_dict(self):
        """Test to_dict returns correct structure."""
        response = SearchResponse(
            query="test",
            results=[SearchResult(title="R1", url="https://1.com", content="C1")],
            answer="Answer",
            search_time=0.5,
        )
        d = response.to_dict()
        assert d["query"] == "test"
        assert len(d["results"]) == 1
        assert d["results"][0]["title"] == "R1"
        assert d["answer"] == "Answer"
        assert d["result_count"] == 1


class TestTavilySearch:
    """Test TavilySearch class."""

    def test_init_missing_api_key_raises(self):
        """Test initialization raises without API key."""
        with patch("psx.tools.web_search.get_config") as mock_config:
            mock_config.return_value.tavily_api_key = None
            with pytest.raises(ValueError, match="Tavily API key"):
                TavilySearch()

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        with patch("psx.tools.web_search.get_config") as mock_config:
            mock_config.return_value.tavily_api_key = None
            search = TavilySearch(api_key="test-key")
            assert search.api_key == "test-key"

    def test_init_from_config(self):
        """Test initialization from config."""
        with patch("psx.tools.web_search.get_config") as mock_config:
            mock_config.return_value.tavily_api_key = "config-key"
            search = TavilySearch()
            assert search.api_key == "config-key"

    def test_search_mocked(self):
        """Test search method with mocked client."""
        with patch("psx.tools.web_search.get_config") as mock_config:
            mock_config.return_value.tavily_api_key = "test-key"

            # Create mock Tavily client
            mock_client = MagicMock()
            mock_client.search.return_value = {
                "results": [
                    {
                        "title": "Test Result",
                        "url": "https://example.com",
                        "content": "Test content",
                        "score": 0.9,
                    }
                ],
                "answer": "AI answer",
            }

            search = TavilySearch()
            search._client = mock_client

            response = search.search("test query")

            assert response.query == "test query"
            assert len(response.results) == 1
            assert response.results[0].title == "Test Result"
            assert response.answer == "AI answer"

    def test_search_news_mocked(self):
        """Test search_news method."""
        with patch("psx.tools.web_search.get_config") as mock_config:
            mock_config.return_value.tavily_api_key = "test-key"

            mock_client = MagicMock()
            mock_client.search.return_value = {
                "results": [
                    {
                        "title": "News Article",
                        "url": "https://news.com",
                        "content": "News content",
                        "score": 0.85,
                        "published_date": "2025-01-15",
                    }
                ],
                "answer": "News summary",
            }

            search = TavilySearch()
            search._client = mock_client

            response = search.search_news("OGDC stock")

            # Verify search was called with news-specific query
            call_args = mock_client.search.call_args
            assert "news" in call_args.kwargs["query"].lower()

    def test_search_company_info_mocked(self):
        """Test search_company_info method."""
        with patch("psx.tools.web_search.get_config") as mock_config:
            mock_config.return_value.tavily_api_key = "test-key"

            mock_client = MagicMock()
            mock_client.search.return_value = {
                "results": [],
                "answer": "Company info",
            }

            search = TavilySearch()
            search._client = mock_client

            search.search_company_info("Oil & Gas Development", symbol="OGDC")

            # Verify search was called with company-specific query
            call_args = mock_client.search.call_args
            assert "OGDC" in call_args.kwargs["query"]

    def test_search_competitors_mocked(self):
        """Test search_competitors method."""
        with patch("psx.tools.web_search.get_config") as mock_config:
            mock_config.return_value.tavily_api_key = "test-key"

            mock_client = MagicMock()
            mock_client.search.return_value = {
                "results": [],
                "answer": "PPL, POL, MARI",
            }

            search = TavilySearch()
            search._client = mock_client

            search.search_competitors("OGDC", sector="Oil & Gas")

            call_args = mock_client.search.call_args
            assert "competitors" in call_args.kwargs["query"].lower()


class TestFormatSearchForLLM:
    """Test format_search_for_llm function."""

    def test_format_basic(self):
        """Test basic formatting."""
        response = SearchResponse(
            query="test query",
            results=[
                SearchResult(
                    title="Result 1",
                    url="https://example.com/1",
                    content="Content for result 1",
                )
            ],
        )
        formatted = format_search_for_llm(response)

        assert "test query" in formatted
        assert "Result 1" in formatted
        assert "https://example.com/1" in formatted

    def test_format_with_answer(self):
        """Test formatting includes AI answer."""
        response = SearchResponse(
            query="test",
            results=[],
            answer="This is the AI-generated summary.",
        )
        formatted = format_search_for_llm(response)

        assert "Summary:" in formatted
        assert "AI-generated summary" in formatted

    def test_format_multiple_results(self):
        """Test formatting multiple results."""
        response = SearchResponse(
            query="test",
            results=[
                SearchResult(title=f"R{i}", url=f"https://{i}.com", content=f"C{i}")
                for i in range(3)
            ],
        )
        formatted = format_search_for_llm(response)

        assert "1. R0" in formatted
        assert "2. R1" in formatted
        assert "3. R2" in formatted

    def test_format_with_date(self):
        """Test formatting includes published date."""
        response = SearchResponse(
            query="test",
            results=[
                SearchResult(
                    title="News",
                    url="https://news.com",
                    content="Content",
                    published_date="2025-01-15",
                )
            ],
        )
        formatted = format_search_for_llm(response)

        assert "Date:" in formatted
        assert "2025-01-15" in formatted

    def test_format_truncates_content(self):
        """Test content is truncated."""
        long_content = "x" * 500
        response = SearchResponse(
            query="test",
            results=[
                SearchResult(
                    title="Test",
                    url="https://test.com",
                    content=long_content,
                )
            ],
        )
        formatted = format_search_for_llm(response)

        # Should truncate to 300 chars + "..."
        assert "..." in formatted
        assert len(formatted) < len(long_content) + 200
