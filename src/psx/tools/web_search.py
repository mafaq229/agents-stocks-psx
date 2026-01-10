"""Web search tool using Tavily API.

Provides search capabilities for news and general web content.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from psx.core.config import get_config


@dataclass
class SearchResult:
    """Single search result."""

    title: str
    url: str
    content: str
    score: float = 0.0
    published_date: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": self.score,
            "published_date": self.published_date,
        }


@dataclass
class SearchResponse:
    """Complete search response."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    answer: Optional[str] = None  # Tavily's AI-generated answer
    search_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "answer": self.answer,
            "search_time": self.search_time,
            "result_count": len(self.results),
        }


class TavilySearch:
    """Web search using Tavily API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Tavily search client.

        Args:
            api_key: Tavily API key. If not provided, reads from config/env.
        """
        config = get_config()
        self.api_key = api_key or config.tavily_api_key

        if not self.api_key:
            raise ValueError(
                "Tavily API key not set. Set TAVILY_API_KEY environment variable."
            )

        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create Tavily client."""
        if self._client is None:
            try:
                from tavily import TavilyClient
            except ImportError:
                raise ImportError(
                    "Tavily package not installed. Run: uv add tavily-python"
                )
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
    ) -> SearchResponse:
        """Perform a web search.

        Args:
            query: Search query
            max_results: Maximum number of results (1-10)
            search_depth: "basic" or "advanced" (more thorough but slower)
            include_answer: Include AI-generated answer summary
            include_domains: Only search these domains
            exclude_domains: Exclude these domains from results

        Returns:
            SearchResponse with results
        """
        client = self._get_client()

        start_time = datetime.now()

        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": min(max_results, 10),
            "search_depth": search_depth,
            "include_answer": include_answer,
        }

        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains

        response = client.search(**kwargs)

        elapsed = (datetime.now() - start_time).total_seconds()

        # TODO: investigate this score parameter further
        results = []
        for item in response.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                    published_date=item.get("published_date"),
                )
            )

        return SearchResponse(
            query=query,
            results=results,
            answer=response.get("answer"),
            search_time=elapsed,
        )

    def search_news(
        self,
        query: str,
        max_results: int = 5,
    ) -> SearchResponse:
        """Search for recent news.

        Args:
            query: Search query
            max_results: Maximum number of results
            days: Only include news from last N days

        Returns:
            SearchResponse with news results
        """
        # Add news-specific terms to query
        news_query = f"{query} news latest"

        return self.search(
            query=news_query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=True
        )

    def search_company_info(
        self,
        company_name: str,
        symbol: Optional[str] = None,
        max_results: int = 5,
    ) -> SearchResponse:
        """Search for company information.

        Args:
            company_name: Company name
            symbol: Stock symbol (optional, adds context)
            max_results: Maximum number of results

        Returns:
            SearchResponse with company info
        """
        query = company_name
        if symbol:
            query = f"{company_name} {symbol} Pakistan stock exchange. Search for information about the company business, operations, financial performance and future plans."
        else:
            query = f"{company_name} Pakistan company"

        return self.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=True,
        )

    def search_competitors(
        self,
        company_name: str,
        sector: Optional[str] = None,
        max_results: int = 5,
    ) -> SearchResponse:
        """Search for competitor information.

        Args:
            company_name: Company name
            sector: Industry sector (optional)
            max_results: Maximum number of results

        Returns:
            SearchResponse with competitor info
        """
        query = f"what are PSX stock symbols of competitors of {company_name} in {sector} sector. Write only the stock symbols separated by commas."

        return self.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=True,
        )


def format_search_for_llm(response: SearchResponse) -> str:
    """Format search response for LLM consumption.

    Args:
        response: SearchResponse object

    Returns:
        Formatted string for LLM context
    """
    lines = [f"Search Query: {response.query}"]

    if response.answer:
        lines.append(f"\nSummary: {response.answer}")

    lines.append(f"\nSearch Results ({len(response.results)}):")

    for i, result in enumerate(response.results, 1):
        lines.append(f"\n{i}. {result.title}")
        lines.append(f"   URL: {result.url}")
        if result.published_date:
            lines.append(f"   Date: {result.published_date}")
        lines.append(f"   {result.content[:300]}...")

    return "\n".join(lines)
