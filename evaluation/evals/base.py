"""Base evaluator class."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result from a single evaluation."""

    evaluator: str
    test_case_id: str
    passed: bool
    score: float  # 0.0 to 1.0
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "evaluator": self.evaluator,
            "test_case_id": self.test_case_id,
            "passed": self.passed,
            "score": round(self.score, 4),
            "metrics": self.metrics,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


@dataclass
class EvaluatorSummary:
    """Summary of all evaluation results for an evaluator."""

    evaluator: str
    total_cases: int
    passed_cases: int
    average_score: float
    results: list[EvaluationResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed_cases / self.total_cases

    def to_dict(self) -> dict:
        return {
            "evaluator": self.evaluator,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "average_score": round(self.average_score, 4),
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp,
        }


class BaseEvaluator(ABC):
    """Base class for all evaluators."""

    name: str = "BaseEvaluator"

    def __init__(self, golden_set_path: Optional[Path] = None):
        """Initialize evaluator.

        Args:
            golden_set_path: Path to golden dataset JSON file
        """
        self.golden_set_path = golden_set_path or (
            Path(__file__).parent.parent / "datasets" / "golden_set.json"
        )
        self._golden_set: Optional[dict] = None

    @property
    def golden_set(self) -> dict:
        """Lazy-load golden dataset."""
        if self._golden_set is None:
            with open(self.golden_set_path) as f:
                self._golden_set = json.load(f)
        return self._golden_set

    def get_test_cases(self) -> list[dict]:
        """Get test cases relevant to this evaluator.

        Override in subclasses to filter test cases.
        """
        return self.golden_set.get("test_cases", [])

    @abstractmethod
    def evaluate_case(self, test_case: dict) -> EvaluationResult:
        """Evaluate a single test case.

        Args:
            test_case: Test case from golden dataset

        Returns:
            EvaluationResult with pass/fail and metrics
        """
        pass

    def run_all(self, verbose: bool = False) -> EvaluatorSummary:
        """Run all test cases and return summary.

        Args:
            verbose: Log progress for each case

        Returns:
            EvaluatorSummary with all results
        """
        test_cases = self.get_test_cases()
        results: list[EvaluationResult] = []

        for case in test_cases:
            if verbose:
                logger.info(f"[{self.name}] Evaluating: {case.get('id', 'unknown')}")

            try:
                result = self.evaluate_case(case)
                results.append(result)

                if verbose:
                    status = "PASS" if result.passed else "FAIL"
                    logger.info(f"  {status} (score: {result.score:.2f})")

            except Exception as e:
                logger.error(f"[{self.name}] Error evaluating {case.get('id')}: {e}")
                results.append(EvaluationResult(
                    evaluator=self.name,
                    test_case_id=case.get("id", "unknown"),
                    passed=False,
                    score=0.0,
                    errors=[str(e)],
                ))

        # Calculate summary
        passed = sum(1 for r in results if r.passed)
        avg_score = sum(r.score for r in results) / len(results) if results else 0.0

        return EvaluatorSummary(
            evaluator=self.name,
            total_cases=len(results),
            passed_cases=passed,
            average_score=avg_score,
            results=results,
        )
