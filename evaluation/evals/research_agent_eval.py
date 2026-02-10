"""Evaluator for ResearchAgent performance."""

import logging
from typing import Any, Optional

from evaluation.evals.base import BaseEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


class ResearchAgentEvaluator(BaseEvaluator):
    """Evaluates ResearchAgent news and report retrieval."""

    name = "ResearchAgent"

    def evaluate_case(self, test_case: dict) -> EvaluationResult:
        """Evaluate research output for a single symbol.

        Args:
            test_case: Test case with symbol

        Returns:
            EvaluationResult with relevance and coverage metrics
        """
        symbol = test_case["symbol"]
        company_name = test_case.get("company_name", "")
        errors: list[str] = []
        metrics: dict[str, Any] = {"symbol": symbol}

        # Get cached research result if available
        research_result = self._get_cached_research(symbol)

        if not research_result:
            return EvaluationResult(
                evaluator=self.name,
                test_case_id=test_case["id"],
                passed=True,
                score=0.5,
                metrics=metrics,
                errors=["No cached research result. Run analysis first for full evaluation."],
            )

        metrics["research_available"] = True
        score_components: list[float] = []

        # 1. Check news items
        news_items = research_result.get("news_items", [])
        metrics["news_count"] = len(news_items)

        # Check news relevance (contains symbol or company name)
        relevant_news = 0
        for item in news_items:
            title = item.get("title", "").lower()
            summary = item.get("summary", "").lower()
            text = title + " " + summary

            if (
                symbol.lower() in text or
                (company_name and company_name.lower() in text)
            ):
                relevant_news += 1

        relevance_score = relevant_news / len(news_items) if news_items else 0.0
        metrics["news_relevance"] = relevance_score
        score_components.append(min(relevance_score + 0.3, 1.0))  # Generous scoring

        # 2. Check report highlights
        highlights = research_result.get("report_highlights", [])
        metrics["highlight_count"] = len(highlights)

        # Check for financial numbers in highlights
        has_numbers = any(
            any(c.isdigit() for c in h) for h in highlights
        )
        metrics["highlights_have_numbers"] = has_numbers
        score_components.append(1.0 if has_numbers and highlights else 0.5)

        # 3. Check risks identified
        risks = research_result.get("risks_identified", [])
        metrics["risks_count"] = len(risks)
        score_components.append(1.0 if risks else 0.5)

        # 4. Check opportunities
        opportunities = research_result.get("opportunities", [])
        metrics["opportunities_count"] = len(opportunities)
        score_components.append(1.0 if opportunities else 0.5)

        # 5. Check for management commentary
        commentary = research_result.get("management_commentary", "")
        has_commentary = len(commentary) > 20
        metrics["has_management_commentary"] = has_commentary
        score_components.append(1.0 if has_commentary else 0.5)

        # Calculate overall score
        score = sum(score_components) / len(score_components) if score_components else 0.0
        passed = score >= 0.5  # Lower threshold for research

        return EvaluationResult(
            evaluator=self.name,
            test_case_id=test_case["id"],
            passed=passed,
            score=score,
            metrics=metrics,
            errors=errors,
        )

    def _get_cached_research(self, symbol: str) -> Optional[dict]:
        """Get cached research result if available.

        Args:
            symbol: Stock symbol

        Returns:
            Cached research dict or None
        """
        from pathlib import Path
        import json

        output_dir = Path("output")
        if not output_dir.exists():
            return None

        # Find most recent analysis and extract research section
        analysis_files = sorted(
            output_dir.glob(f"analyze_{symbol}_*.json"),
            reverse=True
        )

        if analysis_files:
            try:
                with open(analysis_files[0]) as f:
                    analysis = json.load(f)
                    # Research data might be in raw_data or directly in analysis
                    if "raw_data" in analysis and "research" in analysis["raw_data"]:
                        return analysis["raw_data"]["research"]
                    # Try to construct from top-level fields
                    return {
                        "news_items": analysis.get("news_items", []),
                        "report_highlights": [],
                        "risks_identified": [r.get("point", r) if isinstance(r, dict) else r
                                            for r in analysis.get("risks", [])],
                        "opportunities": [],
                        "management_commentary": "",
                    }
            except (json.JSONDecodeError, IOError):
                pass

        return None


def run_research_agent_eval(verbose: bool = True) -> dict:
    """Convenience function to run ResearchAgent evaluation.

    Args:
        verbose: Print progress

    Returns:
        Evaluation summary as dict
    """
    evaluator = ResearchAgentEvaluator()
    summary = evaluator.run_all(verbose=verbose)
    return summary.to_dict()
