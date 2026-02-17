"""Evaluator for DataAgent performance."""

import asyncio
import logging
from typing import Any, Optional

from evaluation.evals.base import BaseEvaluator, EvaluationResult
from evaluation.metrics.accuracy import calculate_completeness

logger = logging.getLogger(__name__)


class DataAgentEvaluator(BaseEvaluator):
    """Evaluates DataAgent data retrieval accuracy and completeness."""

    name = "DataAgent"

    def __init__(self, use_cache: bool = True, **kwargs):
        """Initialize evaluator.

        Args:
            use_cache: Use cached data instead of live scraping
        """
        super().__init__(**kwargs)
        self.use_cache = use_cache
        self._data_store: Optional[Any] = None

    @property
    def data_store(self):
        """Lazy-load data store."""
        if self._data_store is None:
            from psx.storage.data_store import DataStore
            self._data_store = DataStore()
        return self._data_store

    def evaluate_case(self, test_case: dict) -> EvaluationResult:
        """Evaluate data retrieval for a single symbol.

        Args:
            test_case: Test case with symbol and expected values

        Returns:
            EvaluationResult with completeness and accuracy metrics
        """
        symbol = test_case["symbol"]
        expected = test_case.get("expected", {})
        errors: list[str] = []
        metrics: dict[str, Any] = {"symbol": symbol}

        # Get cached data
        data = self.data_store.get_cache(symbol)

        if not data:
            return EvaluationResult(
                evaluator=self.name,
                test_case_id=test_case["id"],
                passed=False,
                score=0.0,
                metrics=metrics,
                errors=[f"No cached data for {symbol}. Run scraper first."],
            )

        # 1. Check data completeness
        completeness_config = expected.get("data_completeness", {})
        required_fields = completeness_config.get("required_fields", [])

        completeness_score = self._calculate_data_completeness(data, required_fields)
        metrics["completeness_score"] = completeness_score

        # 2. Check minimum row counts
        min_financials = completeness_config.get("min_financials_rows", 0)
        min_ratios = completeness_config.get("min_ratio_rows", 0)

        financials = data.get("financials", {})
        if isinstance(financials, dict):
            # Handle nested format: {"annual": [...], "quarterly": [...]}
            total_financials = sum(len(v) for v in financials.values() if isinstance(v, list))
        else:
            total_financials = len(financials) if financials else 0

        ratios = data.get("ratios", [])
        total_ratios = len(ratios) if ratios else 0

        metrics["financials_rows"] = total_financials
        metrics["ratio_rows"] = total_ratios

        financials_ok = total_financials >= min_financials
        ratios_ok = total_ratios >= min_ratios

        if not financials_ok:
            errors.append(f"Insufficient financials: {total_financials} < {min_financials}")
        if not ratios_ok:
            errors.append(f"Insufficient ratios: {total_ratios} < {min_ratios}")

        # 3. Validate quote data ranges
        valuation_ranges = expected.get("valuation_ranges", {})
        quote = data.get("quote", {})

        range_checks = 0
        range_passes = 0

        for field, (min_val, max_val) in valuation_ranges.items():
            value = quote.get(field)
            if value is not None:
                range_checks += 1
                if min_val <= value <= max_val:
                    range_passes += 1
                else:
                    errors.append(f"{field}={value} outside range [{min_val}, {max_val}]")

        range_score = range_passes / range_checks if range_checks > 0 else 1.0
        metrics["range_accuracy"] = range_score

        # 4. Check sector match
        expected_sector = test_case.get("sector")
        actual_sector = data.get("company", {}).get("sector")
        if expected_sector and actual_sector:
            # Fuzzy match (contains)
            sector_match = expected_sector.lower() in actual_sector.lower()
            metrics["sector_match"] = sector_match
            if not sector_match:
                errors.append(f"Sector mismatch: expected '{expected_sector}', got '{actual_sector}'")

        # Calculate overall score
        weights = {
            "completeness": 0.4,
            "financials": 0.2,
            "ratios": 0.2,
            "range": 0.2,
        }

        score = (
            weights["completeness"] * completeness_score +
            weights["financials"] * (1.0 if financials_ok else 0.5) +
            weights["ratios"] * (1.0 if ratios_ok else 0.5) +
            weights["range"] * range_score
        )

        # Pass if score >= 0.7 and no critical errors
        passed = score >= 0.7 and completeness_score >= 0.5

        return EvaluationResult(
            evaluator=self.name,
            test_case_id=test_case["id"],
            passed=passed,
            score=score,
            metrics=metrics,
            errors=errors,
        )

    def _calculate_data_completeness(
        self,
        data: dict,
        required_fields: list[str],
    ) -> float:
        """Calculate completeness score for data.

        Args:
            data: Data dictionary
            required_fields: List of dot-notation field paths

        Returns:
            Completeness score 0.0 to 1.0
        """
        if not required_fields:
            return 1.0

        present = 0
        for field_path in required_fields:
            value = data
            for key in field_path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    value = None
                    break

            # For lists/dicts, check if non-empty
            if isinstance(value, (list, dict)):
                if value:
                    present += 1
            elif value is not None:
                present += 1

        return present / len(required_fields)


def run_data_agent_eval(verbose: bool = True) -> dict:
    """Convenience function to run DataAgent evaluation.

    Args:
        verbose: Print progress

    Returns:
        Evaluation summary as dict
    """
    evaluator = DataAgentEvaluator()
    summary = evaluator.run_all(verbose=verbose)
    return summary.to_dict()
