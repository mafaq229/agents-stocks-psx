"""Research Agent for news search and report analysis.

Responsible for gathering external information about companies.
"""

import json
import logging
from typing import Any, Optional

from psx.agents.base import BaseAgent, AgentConfig
from psx.agents.llm import Tool
from psx.agents.schemas import ResearchOutput, NewsItem
from psx.tools.web_search import TavilySearch
from psx.tools.pdf_parser import PDFParser
from psx.core.config import get_config


logger = logging.getLogger(__name__)


# Tool implementations
def _get_search_client() -> Optional[TavilySearch]:
    """Get Tavily search client if API key is available."""
    config = get_config()
    if config.tavily_api_key:
        return TavilySearch(api_key=config.tavily_api_key)
    return None


def search_news(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search for recent news about a company or topic.

    Args:
        query: Search query (e.g., "OGDC Pakistan stock news")
        max_results: Maximum number of results

    Returns:
        Dict with search results
    """
    client = _get_search_client()
    if not client:
        return {"error": "Web search not available. TAVILY_API_KEY not set."}

    try:
        response = client.search_news(query, max_results=max_results)
        return {
            "query": query,
            "results": [r.to_dict() for r in response.results],
            "answer": response.answer,
            "result_count": len(response.results),
        }
    except Exception as e:
        logger.error(f"News search failed: {e}")
        return {"error": str(e)}


def search_company_info(
    company_name: str, symbol: Optional[str] = None
) -> dict[str, Any]:
    """Search for general information about a company.

    Args:
        company_name: Company name
        symbol: Stock symbol (optional)

    Returns:
        Dict with search results
    """
    client = _get_search_client()
    if not client:
        return {"error": "Web search not available. TAVILY_API_KEY not set."}

    try:
        response = client.search_company_info(company_name, symbol)
        return {
            "query": f"{company_name} {symbol or ''}",
            "results": [r.to_dict() for r in response.results],
            "answer": response.answer,
            "result_count": len(response.results),
        }
    except Exception as e:
        logger.error(f"Company info search failed: {e}")
        return {"error": str(e)}


def search_competitors(
    company_name: str, sector: Optional[str] = None
) -> dict[str, Any]:
    """Search for competitor information.

    Args:
        company_name: Company name
        sector: Industry sector (optional)

    Returns:
        Dict with competitor information
    """
    client = _get_search_client()
    if not client:
        return {"error": "Web search not available. TAVILY_API_KEY not set."}

    try:
        response = client.search_competitors(company_name, sector)
        return {
            "query": f"{company_name} competitors",
            "results": [r.to_dict() for r in response.results],
            "answer": response.answer,
            "result_count": len(response.results),
        }
    except Exception as e:
        logger.error(f"Competitor search failed: {e}")
        return {"error": str(e)}


PDF_SUMMARIZER_SYSTEM = """You are a document analyst. Extract key information from documents and return valid JSON only.

The document could be a financial report, board meeting minutes, announcement, or news article.

Extract and return a JSON object with these fields (include only what's found, skip empty fields):

{
    "document_type": "financial_report|board_meeting|announcement|news|other",
    "title": "Document title or subject",
    "date": "Date mentioned (YYYY-MM-DD if possible)",
    "company": "Company name if mentioned",
    "key_points": ["Most important point 1", "Point 2", ...],
    "financial_data": {
        "revenue": "Amount if mentioned",
        "profit": "Amount if mentioned",
        "eps": "EPS if mentioned",
        "other_metrics": {}
    },
    "decisions": ["Any decisions or resolutions made"],
    "announcements": ["Any announcements or disclosures"],
    "future_outlook": "Management outlook or future plans if mentioned",
    "risks": ["Any risks or concerns mentioned"],
    "action_items": ["Any action items or next steps"]
}

Only include fields that have actual content. Be concise but capture all important information."""


def get_report_text_for_llm(url: str, max_chars: int = 50000) -> dict[str, Any]:
    """Get PDF report summarized by LLM for efficient context.

    Uses a cheap/fast LLM model to extract key information from PDF,
    returning a structured summary instead of raw text.

    Args:
        url: URL of the PDF report
        max_chars: Maximum characters to process (default 50000)

    Returns:
        Dict with structured summary of PDF content
    """
    import asyncio
    import json
    import re
    from psx.agents.llm import LLMClient

    try:
        parser = PDFParser(cache_dir="data/cache/pdfs")

        # Run async method synchronously
        loop = asyncio.new_event_loop()
        try:
            report = loop.run_until_complete(parser.parse_from_url(url))
        finally:
            loop.close()

        # Get text for processing
        text = parser.get_text_for_llm(report, max_chars=max_chars)

        if not text or len(text.strip()) < 100:
            return {
                "url": url,
                "error": "PDF text too short or empty",
                "pages": report.pages,
            }

        # Use cheap model for summarization
        config = get_config()
        summarizer_model = config.get_model_for_agent("pdf_summarizer")

        llm = LLMClient(
            provider=config.llm.provider,
            model=summarizer_model,
            temperature=0.0,
            max_tokens=10000,
        )

        logger.info(f"[PDFSummarizer] Summarizing PDF with {summarizer_model} ({len(text)} chars)")

        response = llm.chat(
            messages=[{
                "role": "user",
                "content": text[:max_chars],
            }],
            system=PDF_SUMMARIZER_SYSTEM,
        )

        # Parse the summary JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                summary = json.loads(json_match.group())
            else:
                summary = {"raw_summary": response.content}
        except json.JSONDecodeError:
            summary = {"raw_summary": response.content}

        return {
            "url": url,
            "pages": report.pages,
            "char_count": len(text),
            "model_used": summarizer_model,
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"PDF summarization failed: {e}")
        return {"error": str(e), "url": url}

# Tool definitions
RESEARCH_AGENT_TOOLS = [
    Tool(
        name="search_news",
        description="Search for recent news about a company or topic. Returns news articles from major sources.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., 'OGDC Pakistan stock news')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        function=search_news,
    ),
    Tool(
        name="search_company_info",
        description="Search for general information about a company.",
        parameters={
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Company name",
                },
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (optional)",
                },
            },
            "required": ["company_name"],
        },
        function=search_company_info,
    ),
    Tool(
        name="get_report_text_for_llm",
        description="Parse a PDF document and get a structured summary. Works with financial reports, board meetings, announcements, etc. Returns JSON with document_type, key_points, financial_data, decisions, announcements, and risks.",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the PDF document",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to process (default 50000)",
                    "default": 50000,
                },
            },
            "required": ["url"],
        },
        function=get_report_text_for_llm,
    ),
]


RESEARCH_AGENT_SYSTEM_PROMPT = """You are a Research Agent specialized in gathering qualitative information about Pakistan Stock Exchange (PSX) companies.

RESPONSIBILITIES:
1. Parse and analyze financial reports (PDFs)
2. Search for recent news and developments
3. Review company announcements
4. Identify risks and opportunities

PDF PARSING:
When report URLs are provided in context, use get_report_text_for_llm to get structured summaries:
- Returns: document_type, key_points, financial_data, decisions, announcements, risks
- Prioritize: Latest QUARTERLY report, Latest ANNUAL report, recent Board meetings and other announcements.

WORKFLOW:
Plan tool calls up front. In the first batch, call search_news, search_company_info, and get_report_text_for_llm for the latest QUARTERLY report, latest ANNUAL report, and recent board meetings/announcements/others. Then make only additional calls to fill gaps or finish.

GUIDELINES:
- Focus on material news affecting stock prices
- Look for: earnings, dividends, acquisitions, management changes
- Extract specific numbers from report summaries
- Identify risks and opportunities
- Plan tool calls up front; make most in one batch, then use additional calls only to fill gaps or finish.

RESPONSE FORMAT:
When complete, respond with JSON:
{
    "symbol": "...",
    "news_items": [{"title": "...", "url": "...", "date": "...", "summary": "..."}],
    "key_events": ["..."],
    "report_highlights": ["Revenue: Rs. X", "Profit: Rs. Y", "EPS: Rs. Z", ...],
    "management_commentary": "Key strategic insights from reports",
    "risks_identified": ["..."],
    "opportunities": ["..."],
    "competitor_insights": {...}
}"""


class ResearchAgent(BaseAgent):
    """Agent for research and news gathering."""

    def __init__(self, **kwargs):
        config = AgentConfig(
            name="ResearchAgent",
            description="Gathers news and parses financial reports",
            system_prompt=RESEARCH_AGENT_SYSTEM_PROMPT,
            max_iterations=7,
            max_tokens=8192,  # Large output for detailed JSON with news/reports
        )
        super().__init__(config=config, tools=RESEARCH_AGENT_TOOLS, **kwargs)

    def run(self, task: str, context: Optional[dict[str, Any]] = None) -> ResearchOutput:
        """Run the research agent and return structured output.

        Args:
            task: Research task description
            context: Optional context

        Returns:
            ResearchOutput with research results
        """
        result = super().run(task, context)
        return self._parse_to_output(result)

    def _parse_to_output(self, result: dict[str, Any]) -> ResearchOutput:
        """Convert agent result to ResearchOutput."""
        import re

        # Handle nested output
        if "output" in result:
            try:
                if isinstance(result["output"], str):
                    json_match = re.search(r'\{[\s\S]*\}', result["output"])
                    if json_match:
                        result = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Parse news items
        news_items = []
        for n in result.get("news_items", []):
            news_items.append(NewsItem(
                title=n.get("title", ""),
                url=n.get("url", ""),
                source=n.get("source"),
                date=n.get("date"),
                summary=n.get("summary"),
            ))

        return ResearchOutput(
            symbol=result.get("symbol", "UNKNOWN"),
            news_items=news_items,
            key_events=result.get("key_events", []),
            report_highlights=result.get("report_highlights", []),
            management_commentary=result.get("management_commentary", ""),
            risks_identified=result.get("risks_identified", []),
            opportunities=result.get("opportunities", []),
            competitor_insights=result.get("competitor_insights", {}),
        )
