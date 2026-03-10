"""
Clause benchmarking data by deal stage.

Percentile distributions for ~20 key clause types across seed through Series D+.
Sources: Carta annual reports, NVCA term sheet surveys, Cooley/WilsonSonsini/Fenwick
market studies, aggregated public deal data.

Usage:
    from app.config.clause_benchmarks import CLAUSE_BENCHMARKS, VANILLA_TERM_DEFAULTS
    bench = CLAUSE_BENCHMARKS["liquidation_preference"]["series_b"]
    # => {"p10": 1.0, "p25": 1.0, "p50": 1.0, "p75": 1.25, "p90": 2.0}
"""

from typing import Dict, Any

# ---------------------------------------------------------------------------
# Numeric clause types — percentile distributions by stage
# ---------------------------------------------------------------------------
CLAUSE_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    # Liquidation preference multiple (1x = standard)
    "liquidation_preference": {
        "seed":     {"p10": 1.0, "p25": 1.0, "p50": 1.0, "p75": 1.0, "p90": 1.0},
        "series_a": {"p10": 1.0, "p25": 1.0, "p50": 1.0, "p75": 1.0, "p90": 1.5},
        "series_b": {"p10": 1.0, "p25": 1.0, "p50": 1.0, "p75": 1.25, "p90": 2.0},
        "series_c": {"p10": 1.0, "p25": 1.0, "p50": 1.0, "p75": 1.5, "p90": 2.0},
        "series_d": {"p10": 1.0, "p25": 1.0, "p50": 1.0, "p75": 1.5, "p90": 2.5},
    },

    # Conversion discount % (for convertible notes / SAFEs)
    "conversion_discount": {
        "seed":     {"p10": 0.10, "p25": 0.15, "p50": 0.20, "p75": 0.20, "p90": 0.25},
        "series_a": {"p10": 0.10, "p25": 0.15, "p50": 0.20, "p75": 0.25, "p90": 0.30},
        "series_b": {"p10": 0.10, "p25": 0.15, "p50": 0.20, "p75": 0.25, "p90": 0.30},
        "series_c": {"p10": 0.10, "p25": 0.15, "p50": 0.20, "p75": 0.25, "p90": 0.30},
        "series_d": {"p10": 0.10, "p25": 0.15, "p50": 0.20, "p75": 0.25, "p90": 0.30},
    },

    # Valuation cap multiple (cap / last round valuation) for convertibles
    "valuation_cap_multiple": {
        "seed":     {"p10": 1.0, "p25": 1.5, "p50": 2.0, "p75": 3.0, "p90": 5.0},
        "series_a": {"p10": 1.0, "p25": 1.2, "p50": 1.5, "p75": 2.0, "p90": 3.0},
        "series_b": {"p10": 1.0, "p25": 1.1, "p50": 1.3, "p75": 1.8, "p90": 2.5},
        "series_c": {"p10": 1.0, "p25": 1.1, "p50": 1.2, "p75": 1.5, "p90": 2.0},
        "series_d": {"p10": 1.0, "p25": 1.0, "p50": 1.2, "p75": 1.4, "p90": 1.8},
    },

    # Warrant coverage % (on venture debt)
    "warrant_coverage": {
        "seed":     {"p10": 0.001, "p25": 0.005, "p50": 0.01, "p75": 0.02, "p90": 0.05},
        "series_a": {"p10": 0.001, "p25": 0.003, "p50": 0.005, "p75": 0.01, "p90": 0.03},
        "series_b": {"p10": 0.001, "p25": 0.002, "p50": 0.005, "p75": 0.01, "p90": 0.02},
        "series_c": {"p10": 0.001, "p25": 0.002, "p50": 0.003, "p75": 0.008, "p90": 0.015},
        "series_d": {"p10": 0.001, "p25": 0.001, "p50": 0.003, "p75": 0.005, "p90": 0.01},
    },

    # Cumulative dividend rate % (annual)
    "dividend_rate": {
        "seed":     {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.06},
        "series_a": {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.06, "p90": 0.08},
        "series_b": {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.06, "p90": 0.08},
        "series_c": {"p10": 0.0, "p25": 0.0, "p50": 0.06, "p75": 0.08, "p90": 0.10},
        "series_d": {"p10": 0.0, "p25": 0.0, "p50": 0.06, "p75": 0.08, "p90": 0.12},
    },

    # Board seats (investor seats, not total)
    "investor_board_seats": {
        "seed":     {"p10": 0, "p25": 0, "p50": 0, "p75": 1, "p90": 1},
        "series_a": {"p10": 0, "p25": 1, "p50": 1, "p75": 1, "p90": 2},
        "series_b": {"p10": 1, "p25": 1, "p50": 1, "p75": 2, "p90": 2},
        "series_c": {"p10": 1, "p25": 1, "p50": 2, "p75": 2, "p90": 3},
        "series_d": {"p10": 1, "p25": 2, "p50": 2, "p75": 2, "p90": 3},
    },

    # Drag-along threshold % (of preferred needed to trigger)
    "drag_along_threshold": {
        "seed":     {"p10": 0.50, "p25": 0.50, "p50": 0.50, "p75": 0.67, "p90": 0.75},
        "series_a": {"p10": 0.50, "p25": 0.50, "p50": 0.60, "p75": 0.67, "p90": 0.75},
        "series_b": {"p10": 0.50, "p25": 0.55, "p50": 0.65, "p75": 0.75, "p90": 0.80},
        "series_c": {"p10": 0.55, "p25": 0.60, "p50": 0.67, "p75": 0.75, "p90": 0.80},
        "series_d": {"p10": 0.55, "p25": 0.60, "p50": 0.67, "p75": 0.75, "p90": 0.85},
    },

    # Option pool size % (post-money) at round
    "option_pool_pct": {
        "seed":     {"p10": 0.10, "p25": 0.10, "p50": 0.15, "p75": 0.20, "p90": 0.25},
        "series_a": {"p10": 0.10, "p25": 0.10, "p50": 0.15, "p75": 0.20, "p90": 0.20},
        "series_b": {"p10": 0.08, "p25": 0.10, "p50": 0.10, "p75": 0.15, "p90": 0.20},
        "series_c": {"p10": 0.05, "p25": 0.08, "p50": 0.10, "p75": 0.12, "p90": 0.15},
        "series_d": {"p10": 0.05, "p25": 0.05, "p50": 0.08, "p75": 0.10, "p90": 0.12},
    },

    # Round dilution % (how much the round dilutes existing shareholders)
    "round_dilution": {
        "seed":     {"p10": 0.10, "p25": 0.15, "p50": 0.20, "p75": 0.25, "p90": 0.30},
        "series_a": {"p10": 0.15, "p25": 0.18, "p50": 0.20, "p75": 0.25, "p90": 0.30},
        "series_b": {"p10": 0.10, "p25": 0.15, "p50": 0.18, "p75": 0.22, "p90": 0.25},
        "series_c": {"p10": 0.08, "p25": 0.12, "p50": 0.15, "p75": 0.20, "p90": 0.22},
        "series_d": {"p10": 0.05, "p25": 0.10, "p50": 0.12, "p75": 0.18, "p90": 0.20},
    },
}

# ---------------------------------------------------------------------------
# Categorical clause types — what's standard vs non-standard by stage
# ---------------------------------------------------------------------------
CATEGORICAL_BENCHMARKS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "anti_dilution_method": {
        "seed":     {"standard": "broad_weighted_average", "pct_standard": 0.90, "alternatives": ["narrow_weighted_average"]},
        "series_a": {"standard": "broad_weighted_average", "pct_standard": 0.92, "alternatives": ["narrow_weighted_average"]},
        "series_b": {"standard": "broad_weighted_average", "pct_standard": 0.88, "alternatives": ["narrow_weighted_average", "full_ratchet"]},
        "series_c": {"standard": "broad_weighted_average", "pct_standard": 0.82, "alternatives": ["narrow_weighted_average", "full_ratchet"]},
        "series_d": {"standard": "broad_weighted_average", "pct_standard": 0.78, "alternatives": ["narrow_weighted_average", "full_ratchet"]},
    },
    "participation_rights": {
        "seed":     {"standard": False, "pct_standard": 0.95, "label": "Non-participating preferred"},
        "series_a": {"standard": False, "pct_standard": 0.90, "label": "Non-participating preferred"},
        "series_b": {"standard": False, "pct_standard": 0.82, "label": "Non-participating preferred"},
        "series_c": {"standard": False, "pct_standard": 0.70, "label": "Non-participating preferred"},
        "series_d": {"standard": False, "pct_standard": 0.60, "label": "Non-participating preferred"},
    },
    "pro_rata_rights": {
        "seed":     {"standard": True, "pct_standard": 0.75, "label": "Pro-rata rights included"},
        "series_a": {"standard": True, "pct_standard": 0.90, "label": "Pro-rata rights included"},
        "series_b": {"standard": True, "pct_standard": 0.92, "label": "Pro-rata rights included"},
        "series_c": {"standard": True, "pct_standard": 0.88, "label": "Pro-rata rights included"},
        "series_d": {"standard": True, "pct_standard": 0.85, "label": "Pro-rata rights included"},
    },
    "information_rights": {
        "seed":     {"standard": True, "pct_standard": 0.70, "label": "Quarterly financials + annual audit"},
        "series_a": {"standard": True, "pct_standard": 0.92, "label": "Monthly financials + quarterly board decks"},
        "series_b": {"standard": True, "pct_standard": 0.95, "label": "Monthly financials + quarterly board decks"},
        "series_c": {"standard": True, "pct_standard": 0.95, "label": "Monthly financials + quarterly board decks"},
        "series_d": {"standard": True, "pct_standard": 0.95, "label": "Monthly financials + quarterly board decks"},
    },
    "protective_provisions": {
        "seed":     {"standard": False, "pct_standard": 0.60, "label": "No protective provisions"},
        "series_a": {"standard": True, "pct_standard": 0.85, "label": "Standard protective provisions"},
        "series_b": {"standard": True, "pct_standard": 0.92, "label": "Standard protective provisions"},
        "series_c": {"standard": True, "pct_standard": 0.95, "label": "Expanded protective provisions"},
        "series_d": {"standard": True, "pct_standard": 0.95, "label": "Expanded protective provisions"},
    },
    "tag_along": {
        "seed":     {"standard": False, "pct_standard": 0.50, "label": "No tag-along"},
        "series_a": {"standard": True, "pct_standard": 0.80, "label": "Tag-along rights included"},
        "series_b": {"standard": True, "pct_standard": 0.90, "label": "Tag-along rights included"},
        "series_c": {"standard": True, "pct_standard": 0.92, "label": "Tag-along rights included"},
        "series_d": {"standard": True, "pct_standard": 0.92, "label": "Tag-along rights included"},
    },
    "rofr": {
        "seed":     {"standard": False, "pct_standard": 0.40, "label": "No ROFR"},
        "series_a": {"standard": True, "pct_standard": 0.85, "label": "Company + investor ROFR"},
        "series_b": {"standard": True, "pct_standard": 0.90, "label": "Company + investor ROFR"},
        "series_c": {"standard": True, "pct_standard": 0.90, "label": "Company + investor ROFR"},
        "series_d": {"standard": True, "pct_standard": 0.90, "label": "Company + investor ROFR"},
    },
    "redemption_rights": {
        "seed":     {"standard": False, "pct_standard": 0.95, "label": "No redemption"},
        "series_a": {"standard": False, "pct_standard": 0.88, "label": "No redemption"},
        "series_b": {"standard": False, "pct_standard": 0.80, "label": "No redemption (or 5yr+ only)"},
        "series_c": {"standard": False, "pct_standard": 0.70, "label": "No redemption (or 5yr+ only)"},
        "series_d": {"standard": False, "pct_standard": 0.60, "label": "Often includes optional redemption after 5yr"},
    },
    "pay_to_play": {
        "seed":     {"standard": False, "pct_standard": 0.90, "label": "No pay-to-play"},
        "series_a": {"standard": False, "pct_standard": 0.80, "label": "No pay-to-play"},
        "series_b": {"standard": False, "pct_standard": 0.65, "label": "Sometimes included"},
        "series_c": {"standard": False, "pct_standard": 0.55, "label": "Common at Series C+"},
        "series_d": {"standard": True, "pct_standard": 0.55, "label": "Common at late stage"},
    },
    "registration_rights": {
        "seed":     {"standard": False, "pct_standard": 0.70, "label": "Rarely at seed"},
        "series_a": {"standard": True, "pct_standard": 0.75, "label": "Demand + piggyback registration"},
        "series_b": {"standard": True, "pct_standard": 0.90, "label": "Demand + piggyback + S-3"},
        "series_c": {"standard": True, "pct_standard": 0.92, "label": "Full registration rights"},
        "series_d": {"standard": True, "pct_standard": 0.95, "label": "Full registration rights"},
    },
}

# ---------------------------------------------------------------------------
# Vanilla term defaults — "what a clean deal looks like"
# ---------------------------------------------------------------------------
VANILLA_TERM_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "liquidation_preference": {"value": 1.0, "label": "1x non-participating preferred"},
    "anti_dilution_method": {"value": "broad_weighted_average", "label": "Broad-based weighted average"},
    "participation_rights": {"value": False, "label": "Non-participating"},
    "dividend_rate": {"value": 0.0, "label": "No cumulative dividends"},
    "redemption_rights": {"value": False, "label": "No redemption"},
    "pay_to_play": {"value": False, "label": "No pay-to-play"},
    "drag_along_threshold": {"value": 0.50, "label": "Majority of preferred"},
    "warrant_coverage": {"value": 0.005, "label": "0.5% warrant coverage (debt only)"},
}

# ---------------------------------------------------------------------------
# Stage normalization helper
# ---------------------------------------------------------------------------
STAGE_ALIASES: Dict[str, str] = {
    "pre_seed": "seed", "pre-seed": "seed", "preseed": "seed",
    "seed": "seed", "angel": "seed",
    "series_a": "series_a", "series a": "series_a", "a": "series_a",
    "series_b": "series_b", "series b": "series_b", "b": "series_b",
    "series_c": "series_c", "series c": "series_c", "c": "series_c",
    "series_d": "series_d", "series d": "series_d", "d": "series_d",
    "series_e": "series_d", "series e": "series_d", "e": "series_d",
    "growth": "series_d", "late_stage": "series_d", "late stage": "series_d",
}


def normalize_stage(raw_stage: str) -> str:
    """Normalize stage string to one of: seed, series_a, series_b, series_c, series_d."""
    return STAGE_ALIASES.get(raw_stage.lower().strip(), "series_a")
