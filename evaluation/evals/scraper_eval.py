"""Evaluator for PSX Scraper performance."""

import logging
from typing import Any, Optional

from evaluation.evals.base import BaseEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


class ScraperEvaluator(BaseEvaluator):
    """Evaluates PSX Scraper data extraction accuracy."""

    name = "Scraper"

    def get_test_cases(self) -> list[dict]:
        """Get scraper-specific test cases."""
        return self.golden_set.get("scraper_test_cases", [])

    def evaluate_case(self, test_case: dict) -> EvaluationResult:
        """Evaluate scraper extraction for a test case type.

        Args:
            test_case: Test case with extraction requirements

        Returns:
            EvaluationResult with extraction success metrics
        """
        test_id = test_case.get("id", "unknown")
        errors: list[str] = []
        metrics: dict[str, Any] = {"test_id": test_id}

        required_fields = test_case.get("required_fields", [])
        optional_fields = test_case.get("optional_fields", [])
        min_periods = test_case.get("min_periods", 0)
        required_metrics = test_case.get("required_metrics", [])

        # Get all cached company data
        cached_data = self._get_all_cached_data()

        if not cached_data:
            return EvaluationResult(
                evaluator=self.name,
                test_case_id=test_id,
                passed=True,
                score=0.5,
                metrics=metrics,
                errors=["No cached data. Run scraper first for full evaluation."],
            )

        # Evaluate across all cached companies
        company_scores: list[float] = []

        for symbol, data in cached_data.items():
            company_metrics = self._evaluate_company_data(
                data,
                required_fields,
                optional_fields,
                min_periods,
                required_metrics,
            )
            company_scores.append(company_metrics["score"])
            metrics[f"{symbol}_score"] = company_metrics["score"]

        metrics["companies_evaluated"] = len(cached_data)
        metrics["average_score"] = sum(company_scores) / len(company_scores) if company_scores else 0.0

        score = metrics["average_score"]
        passed = score >= 0.7

        return EvaluationResult(
            evaluator=self.name,
            test_case_id=test_id,
            passed=passed,
            score=score,
            metrics=metrics,
            errors=errors,
        )

    def _evaluate_company_data(
        self,
        data: dict,
        required_fields: list[str],
        optional_fields: list[str],
        min_periods: int,
        required_metrics: list[str],
    ) -> dict:
        """Evaluate scraped data for a single company.

        Returns:
            Dict with score and field-level metrics
        """
        result = {"score": 0.0, "fields": {}}

        # Check required fields in quote
        quote = data.get("quote", {})
        required_present = 0
        for field in required_fields:
            value = quote.get(field)
            present = value is not None
            result["fields"][field] = present
            if present:
                required_present += 1

        required_score = required_present / len(required_fields) if required_fields else 1.0

        # Check optional fields
        optional_present = 0
        for field in optional_fields:
            value = quote.get(field)
            if value is not None:
                optional_present += 1

        optional_score = optional_present / len(optional_fields) if optional_fields else 1.0

        # Check financial periods
        financials = data.get("financials", {})
        if isinstance(financials, dict):
            # Count unique periods across all categories
            periods = set()
            for category_data in financials.values():
                if isinstance(category_data, list):
                    for item in category_data:
                        period = item.get("period")
                        if period:
                            periods.add(period)
            period_count = len(periods)
        else:
            period_count = 0

        period_score = min(period_count / max(min_periods, 1), 1.0) if min_periods else 1.0

        # Check required metrics in financials
        metric_score = 1.0
        if required_metrics and isinstance(financials, dict):
            found_metrics = set()
            for category_data in financials.values():
                if isinstance(category_data, list):
                    for item in category_data:
                        metric = item.get("metric", "").lower()
                        found_metrics.add(metric)

            found = sum(
                1 for m in required_metrics
                if any(m.lower() in fm for fm in found_metrics)
            )
            metric_score = found / len(required_metrics)

        # Weighted average
        result["score"] = (
            0.4 * required_score +
            0.2 * optional_score +
            0.2 * period_score +
            0.2 * metric_score
        )

        return result

    def _get_all_cached_data(self) -> dict[str, dict]:
        """Get all cached company data.

        Returns:
            Dict mapping symbol to cached data
        """
        from pathlib import Path
        import json

        cache_dir = Path("data/cache")
        if not cache_dir.exists():
            return {}

        results = {}
        for company_dir in cache_dir.iterdir():
            if company_dir.is_dir() and company_dir.name != "pdfs":
                latest_file = company_dir / "latest.json"
                if latest_file.exists():
                    try:
                        with open(latest_file) as f:
                            results[company_dir.name] = json.load(f)
                    except (json.JSONDecodeError, IOError):
                        pass

        return results


def run_scraper_eval(verbose: bool = True) -> dict:
    """Convenience function to run Scraper evaluation.

    Args:
        verbose: Print progress

    Returns:
        Evaluation summary as dict
    """
    evaluator = ScraperEvaluator()
    summary = evaluator.run_all(verbose=verbose)
    return summary.to_dict()
