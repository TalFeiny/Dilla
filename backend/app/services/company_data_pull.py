"""
company_data_pull — single source of truth for pulling company financials.

Replaces get_company_financials_snapshot() with a proper data pull that
preserves the full time series and computes derived metrics.

Every service that needs company data should use pull_company_data().
Each service takes what it needs from the result.
"""

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CompanyData:
    """Result of pulling company financials from fpa_actuals.

    Attributes:
        company_id:   The company UUID.
        time_series:  {category: {period: amount}} — full history, sums
                      multiple rows per category/period.
        latest:       {category: amount} — most recent period's value per
                      category, with computed fields filled in.
        periods:      Sorted list of all periods (YYYY-MM).
        metadata:     Row count, date range, categories present.
    """

    __slots__ = ("company_id", "time_series", "latest", "periods", "metadata")

    def __init__(
        self,
        company_id: str,
        time_series: Dict[str, Dict[str, float]],
        latest: Dict[str, float],
        periods: List[str],
        metadata: Dict[str, Any],
    ):
        self.company_id = company_id
        self.time_series = time_series
        self.latest = latest
        self.periods = periods
        self.metadata = metadata

    # -- convenience helpers for endpoints --

    def latest_with_overrides(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Return latest values with explicit overrides applied on top."""
        merged = {**self.latest, "company_id": self.company_id}
        merged.update(overrides)
        return merged

    def historical_values(self, category: str) -> List[Tuple[str, float]]:
        """Return sorted (period, amount) pairs for a category."""
        series = self.time_series.get(category, {})
        return sorted(series.items())

    def historical_variance(self, category: str) -> Optional[Dict[str, float]]:
        """Compute min/max fractional change from the mean for a category.

        Used by Monte Carlo to derive distributions from real data instead
        of hardcoded {"min": -0.15, "max": 0.25}.
        Returns None if fewer than 2 data points.
        """
        values = [v for _, v in self.historical_values(category) if v]
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        if not mean:
            return None
        deviations = [(v - mean) / abs(mean) for v in values]
        return {
            "min": round(min(deviations), 4),
            "max": round(max(deviations), 4),
            "mean": round(mean, 2),
            "n": len(values),
        }

    def by_period(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Transpose time_series to {period: {category: amount}}.

        Used by budget variance, rolling forecast — any service that
        iterates over periods rather than categories.
        Optional start/end filter periods (inclusive, YYYY-MM format).
        """
        periods = self.periods
        if start:
            periods = [p for p in periods if p >= start]
        if end:
            periods = [p for p in periods if p <= end]

        result: Dict[str, Dict[str, float]] = {}
        for period in periods:
            row: Dict[str, float] = {}
            for cat, series in self.time_series.items():
                if period in series:
                    row[cat] = series[period]
            if row:
                result[period] = row
        return result

    def category_latest_and_prev(self, category: str) -> Tuple[float, float]:
        """Return (latest_value, previous_value) for trend computation.

        Returns (0, 0) if category missing. Returns (latest, 0) if only
        one period.  Used by metrics/KPI endpoints.
        """
        series = self.time_series.get(category, {})
        if not series:
            return (0.0, 0.0)
        sorted_vals = [v for _, v in sorted(series.items())]
        latest_val = sorted_vals[-1] if sorted_vals else 0.0
        prev_val = sorted_vals[-2] if len(sorted_vals) >= 2 else 0.0
        return (latest_val, prev_val)

    def as_flat_dict(self) -> Dict[str, Any]:
        """Backward-compatible flat dict (same shape as old snapshot)."""
        return {**self.latest, "company_id": self.company_id}


# ---------------------------------------------------------------------------
# Core pull
# ---------------------------------------------------------------------------

def _normalize_period(raw: str) -> str:
    """Normalize period values to YYYY-MM format.

    Handles: '2026-01-01', '2026-01', '2026/01', '2026-1', 'Jan 2026', etc.
    """
    if not raw:
        return raw
    s = str(raw).strip()
    # ISO date: 2026-01-15 → 2026-01
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:7]
    # Already YYYY-MM
    if len(s) == 7 and s[4] == "-":
        return s
    # YYYY/MM
    if len(s) >= 6 and "/" in s:
        parts = s.split("/")
        if len(parts) >= 2 and len(parts[0]) == 4:
            return f"{parts[0]}-{parts[1].zfill(2)}"
    # YYYY-M (no leading zero)
    if len(s) == 6 and s[4] == "-":
        return f"{s[:5]}{s[5:].zfill(2)}"
    return s


def _compute_derived(values: Dict[str, float]) -> Dict[str, float]:
    """Fill in computed P&L fields if not explicitly present.

    Computes: gross_profit, opex_total, ebitda.
    Missing categories default to 0 so downstream services never get
    KeyErrors — they just see 0.
    """
    result = dict(values)

    rev = result.get("revenue", 0) or 0
    cogs = result.get("cogs", 0) or 0

    if "gross_profit" not in result:
        result["gross_profit"] = rev - cogs

    rd = result.get("opex_rd", 0) or 0
    sm = result.get("opex_sm", 0) or 0
    ga = result.get("opex_ga", 0) or 0
    if "opex_total" not in result:
        result["opex_total"] = rd + sm + ga
    opex = result["opex_total"] or 0

    gp = result.get("gross_profit", rev - cogs)
    if "ebitda" not in result:
        result["ebitda"] = gp - opex

    return result


def pull_company_data(company_id: str) -> CompanyData:
    """Pull all fpa_actuals rows for a company and build a CompanyData object.

    This is the ONLY function that should query fpa_actuals for service
    consumption.  No limit — pulls everything so callers get full history.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    empty = CompanyData(
        company_id=company_id,
        time_series={},
        latest={},
        periods=[],
        metadata={"row_count": 0},
    )
    if not sb:
        return empty

    rows = (
        sb.table("fpa_actuals")
        .select("category, subcategory, amount, period")
        .eq("company_id", company_id)
        .order("period", desc=False)
        .execute()
        .data
    )
    if not rows:
        return empty

    # -- Build time_series: {category: {period: summed_amount}} --
    time_series: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    all_periods: set = set()

    for row in rows:
        cat = row.get("category")
        raw_period = row.get("period")
        amount = row.get("amount")
        if not cat or raw_period is None or amount is None:
            continue
        period = _normalize_period(str(raw_period))
        time_series[cat][period] += float(amount)
        all_periods.add(period)

    # Freeze defaultdicts to regular dicts
    time_series = {cat: dict(periods) for cat, periods in time_series.items()}

    # -- Sorted periods --
    periods = sorted(all_periods)

    # -- Latest: most recent period's value per category --
    latest_raw: Dict[str, float] = {}
    if periods:
        last_period = periods[-1]
        for cat, series in time_series.items():
            if last_period in series:
                latest_raw[cat] = series[last_period]
            else:
                # Fall back to most recent available period for this category
                cat_periods = sorted(series.keys())
                if cat_periods:
                    latest_raw[cat] = series[cat_periods[-1]]

    # -- Compute derived fields on latest --
    latest = _compute_derived(latest_raw)

    # -- Metadata --
    metadata = {
        "row_count": len(rows),
        "period_range": [periods[0], periods[-1]] if periods else [],
        "period_count": len(periods),
        "categories": sorted(time_series.keys()),
    }

    logger.info(
        "[DATA_PULL] company=%s rows=%d periods=%d categories=%d",
        company_id,
        len(rows),
        len(periods),
        len(time_series),
    )

    return CompanyData(
        company_id=company_id,
        time_series=time_series,
        latest=latest,
        periods=periods,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Branch overrides (shared across all endpoints)
# ---------------------------------------------------------------------------

def apply_branch_overrides(data: CompanyData, branch_id: Optional[str]) -> CompanyData:
    """Apply scenario branch assumption overrides to latest values.

    Returns a new CompanyData with updated latest values.  time_series
    is NOT modified — branch overrides are point-in-time assumptions,
    not historical rewrites.
    """
    if not branch_id:
        return data
    try:
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return data
        row = (
            sb.table("scenario_branches")
            .select("assumptions")
            .eq("id", branch_id)
            .single()
            .execute()
        )
        if row.data:
            assumptions = row.data.get("assumptions", "{}")
            if isinstance(assumptions, str):
                assumptions = json.loads(assumptions)
            # Re-derive computed fields after applying overrides
            updated_latest = _compute_derived({**data.latest, **assumptions})
            return CompanyData(
                company_id=data.company_id,
                time_series=data.time_series,
                latest=updated_latest,
                periods=data.periods,
                metadata=data.metadata,
            )
    except Exception as e:
        logger.warning("Failed to load branch overrides: %s", e)
    return data


# ---------------------------------------------------------------------------
# One-call convenience (pull + branch override + caller overrides)
# ---------------------------------------------------------------------------

def resolve_company_financials(
    company_id: Optional[str],
    branch_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Optional[CompanyData]]:
    """Pull company data, apply branch + caller overrides, return flat dict.

    Returns (merged_dict, company_data_or_None).  The second value lets
    callers access time_series / historical_variance if they need it.

    If company_id is None, returns (overrides or {}, None).
    """
    if not company_id:
        return (overrides or {}, None)

    data = pull_company_data(company_id)
    data = apply_branch_overrides(data, branch_id)
    merged = data.latest_with_overrides(overrides or {})
    return (merged, data)
