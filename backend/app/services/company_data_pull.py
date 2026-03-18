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


# ---------------------------------------------------------------------------
# Growth-rate helpers (ported from actuals_ingestion)
# ---------------------------------------------------------------------------

def _trailing_growth_from_series(values: List[float]) -> float:
    """Trailing MoM growth from last 2 values, annualized."""
    if len(values) < 2:
        return 0.0
    prev, curr = values[-2], values[-1]
    if prev and prev != 0:
        mom = (curr - prev) / abs(prev)
        mom = max(-0.5, min(0.5, mom))
        return (1 + mom) ** 12 - 1
    return 0.0


def _trailing_growth_window_from_series(values: List[float], window: int = 3) -> float:
    """CAGR over *window* months, annualized."""
    if len(values) < window + 1:
        return 0.0
    start_val = values[-(window + 1)]
    end_val = values[-1]
    if start_val and start_val > 0 and end_val and end_val > 0:
        monthly = (end_val / start_val) ** (1 / window) - 1
        monthly = max(-0.5, min(0.5, monthly))
        return (1 + monthly) ** 12 - 1
    return 0.0


def _recommend_method(rev_months: int, has_driver_data: bool) -> str:
    """Recommend forecast method based on data availability."""
    if has_driver_data:
        return "driver_based"
    if rev_months >= 12:
        return "seasonal"
    if rev_months >= 6:
        return "regression"
    return "growth_rate"


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
        analytics:    Derived business metrics computed from time_series
                      (growth rates, burn, margin, runway, driver detection,
                      data quality scorecard).
    """

    __slots__ = ("company_id", "time_series", "latest", "periods", "metadata",
                 "analytics")

    def __init__(
        self,
        company_id: str,
        time_series: Dict[str, Dict[str, float]],
        latest: Dict[str, float],
        periods: List[str],
        metadata: Dict[str, Any],
        analytics: Optional[Dict[str, Any]] = None,
    ):
        self.company_id = company_id
        self.time_series = time_series
        self.latest = latest
        self.periods = periods
        self.metadata = metadata
        self.analytics = analytics or {}

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

    def sorted_amounts(self, category: str) -> List[float]:
        """Return chronologically sorted amounts for a category."""
        return [v for _, v in self.historical_values(category)]

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

    def to_forecast_seed(self) -> Dict[str, Any]:
        """Return flat dict matching seed_forecast_from_actuals shape.

        This is the migration bridge: callers that used to call
        seed_forecast_from_actuals() get the same dict shape, but
        computed from the full time_series instead of N separate queries.
        """
        a = self.analytics
        result: Dict[str, Any] = {
            "revenue": self.latest.get("revenue", 0),
            "growth_rate": a.get("growth_rate", 0.5),
            "burn_rate": a.get("burn_rate"),
            "net_burn": a.get("net_burn"),
            "cash_balance": self.latest.get("cash_balance"),
            "company_id": self.company_id,
        }
        # Optional fields — only include when present
        for key in ("gross_margin", "runway_months", "cost_per_head",
                     "headcount", "_trailing_growth_3m", "_trailing_growth_6m",
                     "_growth_trend", "_rd_spend", "_sm_spend", "_ga_spend",
                     "_detected_customer_count", "_detected_churn_rate",
                     "_detected_acv", "_data_quality"):
            val = a.get(key)
            if val is not None:
                result[key] = val
        return result


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


def _compute_analytics(
    time_series: Dict[str, Dict[str, float]],
    latest: Dict[str, float],
    periods: List[str],
) -> Dict[str, Any]:
    """Compute business metrics from full time series.

    Replaces the per-category queries in seed_forecast_from_actuals with
    analytics derived from the already-loaded time_series dict.
    """

    def _sorted_vals(cat: str) -> List[float]:
        series = time_series.get(cat, {})
        return [series[p] for p in sorted(series.keys()) if p in series]

    rev_vals = _sorted_vals("revenue")
    cogs_vals = _sorted_vals("cogs")
    opex_vals = _sorted_vals("opex_total")
    cash_vals = _sorted_vals("cash_balance")
    hc_vals = _sorted_vals("headcount")
    customer_vals = _sorted_vals("customers")
    arr_vals = _sorted_vals("arr")

    last_rev = rev_vals[-1] if rev_vals else 0
    last_cogs = cogs_vals[-1] if cogs_vals else 0
    last_opex = opex_vals[-1] if opex_vals else 0

    # -- Growth rates from full series --
    growth_rate = _trailing_growth_from_series(rev_vals) if len(rev_vals) >= 2 else 0.5

    analytics: Dict[str, Any] = {
        "growth_rate": growth_rate,
    }

    # -- Burn / margin / runway --
    burn_rate = (last_cogs + last_opex) if (cogs_vals or opex_vals) else None
    analytics["burn_rate"] = burn_rate

    net_burn = None
    if burn_rate is not None:
        net_burn = burn_rate - last_rev
    analytics["net_burn"] = net_burn

    if last_rev > 0 and cogs_vals:
        analytics["gross_margin"] = (last_rev - last_cogs) / last_rev

    cash_balance = cash_vals[-1] if cash_vals else None
    if cash_balance is not None and net_burn is not None and net_burn > 0:
        analytics["runway_months"] = cash_balance / net_burn

    # -- Headcount / cost per head --
    last_hc = hc_vals[-1] if hc_vals else None
    if last_hc is not None:
        analytics["headcount"] = last_hc
    if burn_rate is not None and last_hc and last_hc > 0:
        analytics["cost_per_head"] = burn_rate / last_hc

    # -- Trailing growth windows --
    if len(rev_vals) >= 4:
        tg3 = _trailing_growth_window_from_series(rev_vals, window=3)
        tg6 = (_trailing_growth_window_from_series(rev_vals, window=6)
               if len(rev_vals) >= 7 else growth_rate)
        analytics["_trailing_growth_3m"] = tg3
        analytics["_trailing_growth_6m"] = tg6
        analytics["_growth_trend"] = "accelerating" if tg3 > tg6 else "decelerating"

    # -- OpEx breakdown --
    for cat, key in [("opex_rd", "_rd_spend"), ("opex_sm", "_sm_spend"), ("opex_ga", "_ga_spend")]:
        vals = _sorted_vals(cat)
        if vals:
            analytics[key] = vals[-1]

    # -- Driver detection (customers, ARR, churn) --
    if customer_vals and len(customer_vals) >= 2:
        analytics["_detected_customer_count"] = customer_vals[-1]
        if customer_vals[-2] > 0 and customer_vals[-1] < customer_vals[-2]:
            analytics["_detected_churn_rate"] = (
                (customer_vals[-2] - customer_vals[-1]) / customer_vals[-2]
            )

    if arr_vals and customer_vals:
        last_arr = arr_vals[-1]
        last_cust = customer_vals[-1] if customer_vals else 0
        if last_cust and last_cust > 0:
            analytics["_detected_acv"] = last_arr / last_cust

    has_driver_data = bool(
        analytics.get("_detected_acv") and analytics.get("_detected_customer_count")
    )

    # -- Data quality scorecard --
    rd_vals = _sorted_vals("opex_rd")
    sm_vals = _sorted_vals("opex_sm")
    ga_vals = _sorted_vals("opex_ga")
    analytics["_data_quality"] = {
        "revenue_months": len(rev_vals),
        "has_opex_breakdown": bool(rd_vals or sm_vals or ga_vals),
        "has_customer_data": bool(customer_vals),
        "has_arr_data": bool(arr_vals),
        "has_cash_data": bool(cash_vals),
        "has_headcount": bool(hc_vals),
        "growth_trend": analytics.get("_growth_trend", "unknown"),
        "recommended_method": _recommend_method(len(rev_vals), has_driver_data),
    }

    return analytics


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

    # -- Analytics: business metrics from full time series --
    analytics = _compute_analytics(time_series, latest, periods)

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
        analytics=analytics,
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
                analytics=data.analytics,
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
