"""
Clause benchmarking service — data-driven comparison of clause terms against
market standards by deal stage.

Replaces LLM-driven "above_market" vibes with quantitative percentile analysis.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.config.clause_benchmarks import (
    CATEGORICAL_BENCHMARKS,
    CLAUSE_BENCHMARKS,
    VANILLA_TERM_DEFAULTS,
    normalize_stage,
)


@dataclass
class ClauseBenchmarkResult:
    """Result of benchmarking a clause value against market data."""
    clause_type: str
    stage: str
    value: Any
    percentile: Optional[float]          # 0.0–1.0 for numeric clauses
    is_standard: bool                     # within p25–p75 range
    is_above_market: bool                 # above p75
    is_below_market: bool                 # below p25
    market_range: Optional[str]           # "1.0x – 1.5x for Series B"
    comparison: str                       # human-readable summary
    pct_deals_with_standard: Optional[float]  # for categorical: % of deals using standard term


def benchmark_clause(
    clause_type: str,
    value: Any,
    stage: str,
) -> ClauseBenchmarkResult:
    """
    Benchmark a clause value against market data for the given stage.

    Handles both numeric (percentile-based) and categorical (standard/non-standard) clauses.
    """
    normalized_stage = normalize_stage(stage)

    # Try numeric benchmark first
    if clause_type in CLAUSE_BENCHMARKS:
        return _benchmark_numeric(clause_type, value, normalized_stage)

    # Try categorical benchmark
    if clause_type in CATEGORICAL_BENCHMARKS:
        return _benchmark_categorical(clause_type, value, normalized_stage)

    # Unknown clause type — return neutral result
    return ClauseBenchmarkResult(
        clause_type=clause_type,
        stage=normalized_stage,
        value=value,
        percentile=None,
        is_standard=True,  # assume standard if we don't have benchmark data
        is_above_market=False,
        is_below_market=False,
        market_range=None,
        comparison=f"No benchmark data available for {clause_type} at {normalized_stage}.",
        pct_deals_with_standard=None,
    )


def benchmark_all_clauses(
    resolved_params: Dict[str, Any],
    stage: str,
) -> List[ClauseBenchmarkResult]:
    """Benchmark all clause parameters at once. Returns list of results."""
    results = []
    for clause_type, value in resolved_params.items():
        # Skip non-benchmarkable fields
        if clause_type in ("source", "effective_date", "document_id"):
            continue
        # Extract value if it's a dict with a "value" key
        actual_value = value.get("value") if isinstance(value, dict) else value
        if actual_value is not None:
            results.append(benchmark_clause(clause_type, actual_value, stage))
    return results


def _benchmark_numeric(
    clause_type: str, value: Any, stage: str
) -> ClauseBenchmarkResult:
    """Benchmark a numeric clause using percentile distributions."""
    benchmarks = CLAUSE_BENCHMARKS[clause_type]
    stage_data = benchmarks.get(stage)
    if not stage_data:
        stage_data = benchmarks.get("series_a", {})  # fallback

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return ClauseBenchmarkResult(
            clause_type=clause_type, stage=stage, value=value,
            percentile=None, is_standard=True,
            is_above_market=False, is_below_market=False,
            market_range=None,
            comparison=f"Cannot benchmark non-numeric value for {clause_type}.",
            pct_deals_with_standard=None,
        )

    # Compute approximate percentile via linear interpolation
    percentile = _interpolate_percentile(numeric_value, stage_data)

    p25 = stage_data.get("p25", 0)
    p50 = stage_data.get("p50", 0)
    p75 = stage_data.get("p75", 0)

    is_above = numeric_value > p75
    is_below = numeric_value < p25
    is_standard = p25 <= numeric_value <= p75

    # Format the range string
    fmt = _format_value(clause_type)
    market_range = f"{fmt(p25)} – {fmt(p75)} for {_stage_label(stage)}"

    # Build human-readable comparison
    if is_standard:
        comparison = f"Market standard — {_ordinal_pct(percentile)} for {_stage_label(stage)}. Median is {fmt(p50)}."
    elif is_above:
        comparison = f"Above market — {_ordinal_pct(percentile)} for {_stage_label(stage)}. Market range: {market_range}."
    else:
        comparison = f"Below market — {_ordinal_pct(percentile)} for {_stage_label(stage)}. Market range: {market_range}."

    return ClauseBenchmarkResult(
        clause_type=clause_type,
        stage=stage,
        value=numeric_value,
        percentile=percentile,
        is_standard=is_standard,
        is_above_market=is_above,
        is_below_market=is_below,
        market_range=market_range,
        comparison=comparison,
        pct_deals_with_standard=None,
    )


def _benchmark_categorical(
    clause_type: str, value: Any, stage: str
) -> ClauseBenchmarkResult:
    """Benchmark a categorical clause (e.g., anti-dilution method, participation)."""
    benchmarks = CATEGORICAL_BENCHMARKS[clause_type]
    stage_data = benchmarks.get(stage)
    if not stage_data:
        stage_data = benchmarks.get("series_a", {})

    standard_value = stage_data.get("standard")
    pct_standard = stage_data.get("pct_standard", 0.5)
    label = stage_data.get("label", "")

    # Normalize comparison
    is_match = _values_match(value, standard_value)
    is_standard = is_match

    if is_standard:
        comparison = f"Market standard for {_stage_label(stage)} ({pct_standard:.0%} of deals). {label}."
    else:
        comparison = (
            f"Non-standard for {_stage_label(stage)}. "
            f"Standard is {standard_value!r} ({pct_standard:.0%} of deals). "
            f"Your term: {value!r}."
        )

    return ClauseBenchmarkResult(
        clause_type=clause_type,
        stage=stage,
        value=value,
        percentile=None,
        is_standard=is_standard,
        is_above_market=not is_standard,  # non-standard = investor-favorable assumed
        is_below_market=False,
        market_range=None,
        comparison=comparison,
        pct_deals_with_standard=pct_standard,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _interpolate_percentile(value: float, stage_data: Dict[str, float]) -> float:
    """Linear interpolation between known percentile breakpoints."""
    breakpoints = [(0.10, stage_data.get("p10", 0)),
                   (0.25, stage_data.get("p25", 0)),
                   (0.50, stage_data.get("p50", 0)),
                   (0.75, stage_data.get("p75", 0)),
                   (0.90, stage_data.get("p90", 0))]

    if value <= breakpoints[0][1]:
        return 0.05  # below p10
    if value >= breakpoints[-1][1]:
        return 0.95  # above p90

    for i in range(len(breakpoints) - 1):
        pct_lo, val_lo = breakpoints[i]
        pct_hi, val_hi = breakpoints[i + 1]
        if val_lo <= value <= val_hi:
            if val_hi == val_lo:
                return pct_lo  # flat segment
            fraction = (value - val_lo) / (val_hi - val_lo)
            return pct_lo + fraction * (pct_hi - pct_lo)

    return 0.50  # fallback


def _values_match(a: Any, b: Any) -> bool:
    """Compare clause values, handling string normalization."""
    if isinstance(a, str) and isinstance(b, str):
        return a.lower().replace("-", "_").replace(" ", "_") == b.lower().replace("-", "_").replace(" ", "_")
    return a == b


def _ordinal_pct(percentile: Optional[float]) -> str:
    if percentile is None:
        return "unknown percentile"
    p = int(percentile * 100)
    return f"{p}th percentile"


def _stage_label(stage: str) -> str:
    labels = {
        "seed": "Seed", "series_a": "Series A", "series_b": "Series B",
        "series_c": "Series C", "series_d": "Series D+",
    }
    return labels.get(stage, stage.replace("_", " ").title())


def _format_value(clause_type: str):
    """Return a formatter function appropriate for the clause type."""
    pct_types = {"conversion_discount", "warrant_coverage", "dividend_rate",
                 "option_pool_pct", "round_dilution", "drag_along_threshold"}
    if clause_type in pct_types:
        return lambda v: f"{v:.0%}" if v < 1 else f"{v:.1f}%"
    multiplier_types = {"liquidation_preference", "valuation_cap_multiple"}
    if clause_type in multiplier_types:
        return lambda v: f"{v:.1f}x" if v != int(v) else f"{int(v)}x"
    return lambda v: str(v)
