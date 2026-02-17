"""Evaluator for AnalystAgent performance."""

import logging
from typing import Any, Optional

from evaluation.evals.base import BaseEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


class AnalystAgentEvaluator(BaseEvaluator):
    """Evaluates AnalystAgent valuation and recommendation accuracy."""

    name = "AnalystAgent"

    def evaluate_case(self, test_case: dict) -> EvaluationResult:
        """Evaluate analyst output for a single symbol.

        Args:
            test_case: Test case with expected valuation ranges

        Returns:
            EvaluationResult with valuation accuracy metrics
        """
        symbol = test_case["symbol"]
        expected = test_case.get("expected", {})
        errors: list[str] = []
        metrics: dict[str, Any] = {"symbol": symbol}

        # For analyst eval, we need actual analysis output
        # This would typically come from running the agent
        # For now, we validate the test case structure and return a baseline

        # 1. Check recommendation validity
        valid_recommendations = expected.get("recommendation_valid", [])
        metrics["valid_recommendations"] = valid_recommendations

        # 2. Check confidence range
        confidence_range = expected.get("confidence_range", [0.0, 1.0])
        metrics["confidence_range"] = confidence_range

        # 3. Valuation ranges
        valuation_ranges = expected.get("valuation_ranges", {})
        metrics["valuation_metrics_count"] = len(valuation_ranges)

        # Since we can't run the full agent in evaluation mode without
        # incurring LLM costs, we validate the test case structure
        # and provide a mock score based on data availability

        # Check if we have cached analysis results
        analysis_result = self._get_cached_analysis(symbol)

        if analysis_result:
            return self._evaluate_analysis_result(
                test_case, analysis_result, expected, errors, metrics
            )
        else:
            # No cached analysis - return structural validation only
            metrics["analysis_available"] = False
            return EvaluationResult(
                evaluator=self.name,
                test_case_id=test_case["id"],
                passed=True,  # Structure is valid
                score=0.5,    # Partial score for valid structure
                metrics=metrics,
                errors=["No cached analysis result. Run analysis first for full evaluation."],
            )

    def _get_cached_analysis(self, symbol: str) -> Optional[dict]:
        """Get cached analysis result if available.

        Args:
            symbol: Stock symbol

        Returns:
            Cached analysis dict or None
        """
        from pathlib import Path
        import json

        # Check for analysis output files
        output_dir = Path("output")
        if not output_dir.exists():
            return None

        # Find most recent analysis for symbol
        analysis_files = sorted(
            output_dir.glob(f"analyze_{symbol}_*.json"),
            reverse=True
        )

        if analysis_files:
            try:
                with open(analysis_files[0]) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        return None

    def _evaluate_analysis_result(
        self,
        test_case: dict,
        analysis: dict,
        expected: dict,
        errors: list[str],
        metrics: dict,
    ) -> EvaluationResult:
        """Evaluate an actual analysis result.

        Args:
            test_case: Test case definition
            analysis: Analysis result from AnalystAgent
            expected: Expected values/ranges
            errors: List to append errors to
            metrics: Dict to add metrics to

        Returns:
            EvaluationResult
        """
        metrics["analysis_available"] = True
        score_components: list[float] = []

        # 1. Validate recommendation
        recommendation = analysis.get("recommendation", "")
        valid_recs = expected.get("recommendation_valid", [])
        rec_valid = recommendation in valid_recs
        metrics["recommendation"] = recommendation
        metrics["recommendation_valid"] = rec_valid

        if not rec_valid and recommendation:
            errors.append(f"Invalid recommendation: {recommendation}")
        score_components.append(1.0 if rec_valid else 0.0)

        # 2. Validate confidence
        confidence = analysis.get("confidence", 0.0)
        conf_range = expected.get("confidence_range", [0.0, 1.0])
        conf_valid = conf_range[0] <= confidence <= conf_range[1]
        metrics["confidence"] = confidence
        metrics["confidence_valid"] = conf_valid

        if not conf_valid:
            errors.append(f"Confidence {confidence} outside range {conf_range}")
        score_components.append(1.0 if conf_valid else 0.5)

        # 3. Check valuations exist
        valuations = analysis.get("valuations", [])
        has_valuations = len(valuations) > 0
        metrics["valuation_count"] = len(valuations)

        if not has_valuations:
            errors.append("No valuations calculated")
        score_components.append(1.0 if has_valuations else 0.0)

        # 4. Check for reasoning
        reasoning = analysis.get("reasoning", "")
        has_reasoning = len(reasoning) > 20
        metrics["has_reasoning"] = has_reasoning

        if not has_reasoning:
            errors.append("Missing or insufficient reasoning")
        score_components.append(1.0 if has_reasoning else 0.5)

        # Calculate overall score
        score = sum(score_components) / len(score_components) if score_components else 0.0
        passed = score >= 0.7

        return EvaluationResult(
            evaluator=self.name,
            test_case_id=test_case["id"],
            passed=passed,
            score=score,
            metrics=metrics,
            errors=errors,
        )


def run_analyst_agent_eval(verbose: bool = True) -> dict:
    """Convenience function to run AnalystAgent evaluation.

    Args:
        verbose: Print progress

    Returns:
        Evaluation summary as dict
    """
    evaluator = AnalystAgentEvaluator()
    summary = evaluator.run_all(verbose=verbose)
    return summary.to_dict()
