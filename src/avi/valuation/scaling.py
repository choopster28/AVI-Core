from __future__ import annotations

from math import isfinite
from statistics import quantiles


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def percentile_score(value: float, field: list[float]) -> float:
    clean = sorted(x for x in field if isfinite(x))
    if not clean:
        raise ValueError("Field cannot be empty.")
    below = sum(1 for x in clean if x < value)
    equal = sum(1 for x in clean if x == value)
    return 100.0 * (below + 0.5 * equal) / len(clean)


def replacement_adjusted_score(
    value: float,
    field: list[float],
    replacement_value: float,
) -> float:
    clean = sorted(x for x in field if isfinite(x))
    if len(clean) < 2:
        raise ValueError("Field requires at least two values.")
    q95 = quantiles(clean, n=20, method="inclusive")[18]
    if q95 <= replacement_value:
        return 0.0
    return clamp((value - replacement_value) / (q95 - replacement_value) * 100.0)


def field_score(
    value: float,
    field: list[float],
    replacement_value: float,
) -> float:
    return clamp(
        0.60 * percentile_score(value, field)
        + 0.40 * replacement_adjusted_score(
            value,
            field,
            replacement_value,
        )
    )
