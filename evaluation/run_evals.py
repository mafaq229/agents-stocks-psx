#!/usr/bin/env python
"""
Evaluation runner for PSX multi-agent system.

Usage:
    uv run python -m evaluation.run_evals --all
    uv run python -m evaluation.run_evals --eval data_agent
    uv run python -m evaluation.run_evals --eval scraper --verbose
    uv run python -m evaluation.run_evals --list
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.evals.base import EvaluatorSummary
from evaluation.evals.data_agent_eval import DataAgentEvaluator
from evaluation.evals.analyst_agent_eval import AnalystAgentEvaluator
from evaluation.evals.research_agent_eval import ResearchAgentEvaluator
from evaluation.evals.pdf_parser_eval import PDFParserEvaluator
from evaluation.evals.scraper_eval import ScraperEvaluator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Registry of all evaluators
EVALUATORS = {
    "data_agent": DataAgentEvaluator,
    "analyst_agent": AnalystAgentEvaluator,
    "research_agent": ResearchAgentEvaluator,
    "pdf_parser": PDFParserEvaluator,
    "scraper": ScraperEvaluator,
}


def run_evaluations(
    evaluator_names: Optional[list[str]] = None,
    verbose: bool = False,
) -> dict:
    """Run specified evaluations and return results.

    Args:
        evaluator_names: List of evaluator names to run (None = all)
        verbose: Print detailed progress

    Returns:
        Dict with evaluation results
    """
    if evaluator_names is None:
        evaluator_names = list(EVALUATORS.keys())

    results = {
        "timestamp": datetime.now().isoformat(),
        "evaluations": {},
        "summary": {
            "total_evaluators": 0,
            "total_test_cases": 0,
            "total_passed": 0,
            "overall_score": 0.0,
        },
    }

    all_scores: list[float] = []

    for name in evaluator_names:
        if name not in EVALUATORS:
            logger.warning(f"Unknown evaluator: {name}")
            continue

        logger.info(f"Running evaluator: {name}")
        evaluator_class = EVALUATORS[name]
        evaluator = evaluator_class()

        try:
            summary = evaluator.run_all(verbose=verbose)
            results["evaluations"][name] = summary.to_dict()

            results["summary"]["total_evaluators"] += 1
            results["summary"]["total_test_cases"] += summary.total_cases
            results["summary"]["total_passed"] += summary.passed_cases
            all_scores.append(summary.average_score)

            # Print summary for this evaluator
            print(f"\n{'='*60}")
            print(f"  {name.upper()}")
            print(f"{'='*60}")
            print(f"  Pass Rate: {summary.pass_rate:.1%} ({summary.passed_cases}/{summary.total_cases})")
            print(f"  Average Score: {summary.average_score:.2f}")

        except Exception as e:
            logger.error(f"Error running {name}: {e}")
            results["evaluations"][name] = {
                "error": str(e),
                "evaluator": name,
            }

    # Calculate overall score
    if all_scores:
        results["summary"]["overall_score"] = sum(all_scores) / len(all_scores)

    return results


def print_summary(results: dict):
    """Print formatted evaluation summary."""
    summary = results["summary"]

    print("\n" + "=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Timestamp: {results['timestamp']}")
    print(f"  Evaluators: {summary['total_evaluators']}")
    print(f"  Test Cases: {summary['total_test_cases']}")
    print(f"  Passed: {summary['total_passed']}")
    print(f"  Overall Score: {summary['overall_score']:.2f}")
    print("=" * 60)

    # Print per-evaluator summary table
    print("\n  Component Results:")
    print("  " + "-" * 50)
    print(f"  {'Component':<20} {'Pass Rate':<15} {'Score':<10}")
    print("  " + "-" * 50)

    for name, eval_result in results["evaluations"].items():
        if "error" in eval_result:
            print(f"  {name:<20} {'ERROR':<15} {'-':<10}")
        else:
            pass_rate = eval_result.get("pass_rate", 0) * 100
            score = eval_result.get("average_score", 0)
            print(f"  {name:<20} {pass_rate:>6.1f}%        {score:>6.2f}")

    print("  " + "-" * 50)


def save_results(results: dict, output_path: Path):
    """Save evaluation results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Results saved to: {output_path}")


def generate_markdown_report(results: dict) -> str:
    """Generate markdown-formatted evaluation report."""
    lines = [
        "# PSX Evaluation Results",
        "",
        f"**Generated:** {results['timestamp']}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Evaluators Run | {results['summary']['total_evaluators']} |",
        f"| Total Test Cases | {results['summary']['total_test_cases']} |",
        f"| Passed | {results['summary']['total_passed']} |",
        f"| Overall Score | {results['summary']['overall_score']:.2f} |",
        "",
        "## Component Results",
        "",
        "| Component | Pass Rate | Score |",
        "|-----------|-----------|-------|",
    ]

    for name, eval_result in results["evaluations"].items():
        if "error" in eval_result:
            lines.append(f"| {name} | ERROR | - |")
        else:
            pass_rate = eval_result.get("pass_rate", 0) * 100
            score = eval_result.get("average_score", 0)
            lines.append(f"| {name} | {pass_rate:.1f}% | {score:.2f} |")

    lines.extend([
        "",
        "## Details",
        "",
    ])

    for name, eval_result in results["evaluations"].items():
        if "error" not in eval_result:
            lines.append(f"### {name}")
            lines.append("")

            for result in eval_result.get("results", []):
                status = "PASS" if result["passed"] else "FAIL"
                lines.append(f"- **{result['test_case_id']}**: {status} (score: {result['score']:.2f})")

                if result.get("errors"):
                    for error in result["errors"]:
                        lines.append(f"  - {error}")

            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Run PSX evaluation suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python -m evaluation.run_evals --all
  uv run python -m evaluation.run_evals --eval data_agent --verbose
  uv run python -m evaluation.run_evals --eval scraper --eval pdf_parser
        """,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all evaluations",
    )
    parser.add_argument(
        "--eval",
        action="append",
        dest="evals",
        choices=list(EVALUATORS.keys()),
        help="Run specific evaluation (can be repeated)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available evaluators",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("evaluation/results/latest.json"),
        help="Output file path (default: evaluation/results/latest.json)",
    )
    parser.add_argument(
        "--markdown",
        "-m",
        action="store_true",
        help="Also generate markdown report",
    )

    args = parser.parse_args()

    if args.list:
        print("Available evaluators:")
        for name, cls in EVALUATORS.items():
            print(f"  - {name}: {cls.name}")
        return

    if not args.all and not args.evals:
        parser.print_help()
        return

    # Determine which evaluators to run
    evaluator_names = list(EVALUATORS.keys()) if args.all else args.evals

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run evaluations
    results = run_evaluations(evaluator_names, verbose=args.verbose)

    # Print summary
    print_summary(results)

    # Save results
    save_results(results, args.output)

    # Generate markdown if requested
    if args.markdown:
        md_path = args.output.with_suffix(".md")
        md_content = generate_markdown_report(results)
        md_path.write_text(md_content)
        logger.info(f"Markdown report saved to: {md_path}")


if __name__ == "__main__":
    main()
