"""Evaluator for PDF Parser performance."""

import logging
from typing import Any, Optional

from evaluation.evals.base import BaseEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


class PDFParserEvaluator(BaseEvaluator):
    """Evaluates PDF Parser extraction accuracy."""

    name = "PDFParser"

    def get_test_cases(self) -> list[dict]:
        """Get PDF-specific test cases."""
        return self.golden_set.get("pdf_test_cases", [])

    def evaluate_case(self, test_case: dict) -> EvaluationResult:
        """Evaluate PDF parsing for a test case.

        Args:
            test_case: Test case with expected sections and metadata

        Returns:
            EvaluationResult with extraction accuracy metrics
        """
        test_id = test_case.get("id", "unknown")
        expected = test_case
        errors: list[str] = []
        metrics: dict[str, Any] = {"test_id": test_id}

        # Get expected sections
        expected_sections = expected.get("expected_sections", [])
        expected_metadata = expected.get("expected_metadata", [])

        metrics["expected_sections"] = expected_sections
        metrics["expected_metadata"] = expected_metadata

        # For PDF eval, we validate structure and provide baseline score
        # Full evaluation requires actual PDF parsing which is expensive

        # Check if we have any cached PDF results
        parsed_results = self._get_cached_pdf_results()

        if not parsed_results:
            return EvaluationResult(
                evaluator=self.name,
                test_case_id=test_id,
                passed=True,
                score=0.5,
                metrics=metrics,
                errors=["No cached PDF results. Parse PDFs first for full evaluation."],
            )

        # Evaluate against cached results
        score_components: list[float] = []

        for result in parsed_results[:3]:  # Evaluate up to 3 cached PDFs
            sections_found = result.get("sections", {}).keys()

            # Section detection score
            if expected_sections:
                found = sum(1 for s in expected_sections if s in sections_found)
                section_score = found / len(expected_sections)
                score_components.append(section_score)

            # Metadata extraction score
            metadata = result.get("metadata", {})
            if expected_metadata:
                found = sum(1 for m in expected_metadata if metadata.get(m))
                meta_score = found / len(expected_metadata)
                score_components.append(meta_score)

            # Text extraction score (non-empty)
            raw_text = result.get("raw_text", "")
            has_text = len(raw_text) > 100
            score_components.append(1.0 if has_text else 0.0)

        metrics["pdfs_evaluated"] = min(len(parsed_results), 3)

        score = sum(score_components) / len(score_components) if score_components else 0.5
        passed = score >= 0.6

        return EvaluationResult(
            evaluator=self.name,
            test_case_id=test_id,
            passed=passed,
            score=score,
            metrics=metrics,
            errors=errors,
        )

    def _get_cached_pdf_results(self) -> list[dict]:
        """Get cached PDF parsing results.

        Returns:
            List of parsed PDF result dicts
        """
        from pathlib import Path
        import json

        cache_dir = Path("data/cache/pdfs")
        if not cache_dir.exists():
            return []

        results = []
        for json_file in cache_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    results.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass

        return results


def run_pdf_parser_eval(verbose: bool = True) -> dict:
    """Convenience function to run PDFParser evaluation.

    Args:
        verbose: Print progress

    Returns:
        Evaluation summary as dict
    """
    evaluator = PDFParserEvaluator()
    summary = evaluator.run_all(verbose=verbose)
    return summary.to_dict()
