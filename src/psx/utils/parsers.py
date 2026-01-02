"""Number and data parsing utilities for PSX data normalization.

Converts formatted strings from PSX website to machine-readable values.
"""

import re
from typing import Optional, Tuple
from datetime import datetime


def parse_price(value: str) -> Optional[float]:
    """
    Parse price string to float.

    Examples:
        "Rs.5.17" -> 5.17
        "Rs. 5.17" -> 5.17
        "5.17" -> 5.17
        "" -> None
    """
    if not value or not value.strip():
        return None

    # Remove currency prefix and whitespace
    cleaned = re.sub(r"[Rr][Ss]\.?\s*", "", value.strip())
    cleaned = cleaned.replace(",", "").strip()

    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_number(value: str) -> Optional[float]:
    """
    Parse formatted number to float.

    Examples:
        "1,873,125.59" -> 1873125.59
        "18,570,325" -> 18570325.0
        "1873125.59" -> 1873125.59
        "" -> None
    """
    if not value or not value.strip():
        return None

    cleaned = value.replace(",", "").strip()

    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_negative(value: str) -> Optional[float]:
    """
    Parse accounting-style negative numbers (parentheses = negative).

    Examples:
        "(9,235)" -> -9235.0
        "9,235" -> 9235.0
        "(0.52)" -> -0.52
        "0.52" -> 0.52
        "" -> None
    """
    if not value or not value.strip():
        return None

    is_negative = "(" in value and ")" in value
    cleaned = re.sub(r"[(),\s]", "", value)

    try:
        result = float(cleaned)
        return -result if is_negative else result
    except ValueError:
        return None


def parse_percent(value: str) -> Optional[float]:
    """
    Parse percentage string to float.

    Examples:
        "-9.14%" -> -9.14
        "50.60%" -> 50.60
        "(50.43)" -> -50.43  (accounting style)
        "50.60" -> 50.60
        "" -> None
    """
    if not value or not value.strip():
        return None

    # Handle accounting negatives
    is_negative = "(" in value and ")" in value
    cleaned = re.sub(r"[()%,\s]", "", value)

    try:
        result = float(cleaned)
        return -result if is_negative else result
    except ValueError:
        return None


def parse_date(value: str) -> Optional[str]:
    """
    Normalize date to ISO format (YYYY-MM-DD).

    Examples:
        "Nov 10, 2025" -> "2025-11-10"
        "2025-09-30" -> "2025-09-30"
        "10 Nov 2025" -> "2025-11-10"
        "10/11/2025" -> "2025-11-10"
        "" -> None
    """
    if not value or not value.strip():
        return None

    formats = [
        "%b %d, %Y",  # Nov 10, 2025
        "%Y-%m-%d",  # 2025-09-30
        "%d %b %Y",  # 10 Nov 2025
        "%d/%m/%Y",  # 10/11/2025
        "%B %d, %Y",  # November 10, 2025
        "%d-%m-%Y",  # 10-11-2025
    ]

    cleaned = value.strip()

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Return original if unparseable
    return cleaned


def parse_52_week_range(value: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse 52-week range string.

    Examples:
        "3.91—10.23" -> (3.91, 10.23)
        "3.91-10.23" -> (3.91, 10.23)
        "3.91 - 10.23" -> (3.91, 10.23)
        "" -> (None, None)
    """
    if not value or not value.strip():
        return None, None

    # Split by various dash characters
    parts = re.split(r"[—\-–]", value)

    if len(parts) == 2:
        low = parse_number(parts[0])
        high = parse_number(parts[1])
        return low, high

    return None, None


def parse_change_with_percent(value: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse change string that includes both absolute and percentage.

    Examples:
        "-0.52 (-9.14%)" -> (-0.52, -9.14)
        "+1.23 (+5.67%)" -> (1.23, 5.67)
        "0.00 (0.00%)" -> (0.0, 0.0)
    """
    if not value or not value.strip():
        return None, None

    # Pattern: number followed by (percentage)
    match = re.match(r"([+-]?[\d,.]+)\s*\(([+-]?[\d,.]+)%?\)", value.strip())

    if match:
        change = parse_negative(match.group(1))
        change_pct = parse_percent(match.group(2))
        return change, change_pct

    return None, None


def parse_volume(value: str) -> Optional[int]:
    """
    Parse volume string to integer.

    Examples:
        "18,570,325" -> 18570325
        "18570325" -> 18570325
        "" -> None
    """
    if not value or not value.strip():
        return None

    cleaned = value.replace(",", "").strip()

    try:
        return int(float(cleaned))
    except ValueError:
        return None


def parse_shares(value: str) -> Optional[int]:
    """
    Parse shares count to integer.

    Examples:
        "362,306,690" -> 362306690
        "362306690" -> 362306690
        "" -> None
    """
    return parse_volume(value)


def parse_market_cap(value: str) -> Optional[float]:
    """
    Parse market cap to float (keeping in thousands if that's the unit).

    Examples:
        "1,873,125.59" -> 1873125.59
        "" -> None
    """
    return parse_number(value)
