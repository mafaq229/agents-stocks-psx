"""Accuracy calculation utilities for evaluations."""

from typing import Any, Optional


def calculate_accuracy(predictions: list[Any], ground_truth: list[Any]) -> float:
    """Calculate exact match accuracy.

    Args:
        predictions: List of predicted values
        ground_truth: List of ground truth values

    Returns:
        Accuracy score between 0.0 and 1.0
    """
    if not predictions or not ground_truth:
        return 0.0

    if len(predictions) != len(ground_truth):
        raise ValueError("Predictions and ground truth must have same length")

    correct = sum(1 for p, g in zip(predictions, ground_truth) if p == g)
    return correct / len(predictions)


def calculate_precision_recall(
    predictions: set[Any],
    ground_truth: set[Any],
) -> dict[str, float]:
    """Calculate precision and recall for set membership.

    Args:
        predictions: Set of predicted items
        ground_truth: Set of expected items

    Returns:
        Dict with precision, recall, and f1 scores
    """
    if not predictions and not ground_truth:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    if not predictions:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    if not ground_truth:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    true_positives = len(predictions & ground_truth)
    precision = true_positives / len(predictions) if predictions else 0.0
    recall = true_positives / len(ground_truth) if ground_truth else 0.0

    if precision + recall > 0:
        f1 = 2 * (precision * recall) / (precision + recall)
    else:
        f1 = 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def calculate_range_accuracy(
    value: Optional[float],
    expected_min: float,
    expected_max: float,
) -> bool:
    """Check if a value falls within expected range.

    Args:
        value: The value to check
        expected_min: Minimum acceptable value
        expected_max: Maximum acceptable value

    Returns:
        True if value is within range (inclusive)
    """
    if value is None:
        return False
    return expected_min <= value <= expected_max


def calculate_percentage_error(
    actual: Optional[float],
    expected: float,
) -> Optional[float]:
    """Calculate percentage error between actual and expected values.

    Args:
        actual: The actual value
        expected: The expected value

    Returns:
        Percentage error, or None if actual is None or expected is 0
    """
    if actual is None or expected == 0:
        return None
    return abs(actual - expected) / abs(expected) * 100


def calculate_completeness(data: dict[str, Any], required_fields: list[str]) -> float:
    """Calculate data completeness score.

    Args:
        data: Dictionary of data fields
        required_fields: List of field names that should be present and non-null

    Returns:
        Completeness score between 0.0 and 1.0
    """
    if not required_fields:
        return 1.0

    present = 0
    for field in required_fields:
        # Handle nested fields with dot notation
        value = data
        for key in field.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = None
                break

        if value is not None:
            present += 1

    return present / len(required_fields)
