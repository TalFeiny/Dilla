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

def _trailing_growth_from_series(values: List[float]) -> Optional[float]:
    """Compute annualized growth rate from the full revenue series.

    Uses the best window available:
    - 12+ months: YoY CAGR (most stable, smooths seasonality)
    - 6-11 months: 6-month CAGR annualized
    - 3-5 months: 3-month CAGR annualized
    - 2 months: single MoM annualized (least reliable)
    Returns None if insufficient data or zero/negative start values.
    """
    if len(values) < 2:
        return None

    # Pick the longest reliable window
    if len(values) >= 13:
        window = 12
    elif len(values) >= 7:
        window = 6
    elif len(values) >= 4:
        window = 3
    else:
        window = 1  # fallback to last 2 values

    start_val = values[-(window + 1)]
    end_val = values[-1]
    if not start_val or start_val <= 0 or not end_val or end_val <= 0:
        return None

    monthly = (end_val / start_val) ** (1 / window) - 1
    monthly = max(-0.5, min(0.5, monthly))
    return (1 + monthly) ** 12 - 1


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

        # Subcategory proportions — enables decomposition of parent
        # OpEx/COGS into individually adjustable line items.
        try:
            from app.services.actuals_ingestion import get_subcategory_proportions
            subcat_props: Dict[str, Dict[str, float]] = {}
            for parent in ("opex_rd", "opex_sm", "opex_ga", "cogs"):
                props = get_subcategory_proportions(self.company_id, parent)
                if props:
                    subcat_props[parent] = props
            if subcat_props:
                result["_subcategory_proportions"] = subcat_props
        except Exception:
            pass  # Subcategory data is optional

        return result


# ---------------------------------------------------------------------------
# Core pull
# ---------------------------------------------------------------------------

def _normalize_period(raw: str) -> str:
    """Normalize DB period values to YYYY-MM.

    DB returns ISO dates (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) — just slice.
    """
    from app.core.date_utils import normalize_period
    return normalize_period(raw)


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

    # -- Growth rates from full series (None when insufficient data) --
    growth_rate = _trailing_growth_from_series(rev_vals) if len(rev_vals) >= 2 else None

    analytics: Dict[str, Any] = {}
    if growth_rate is not None:
        analytics["growth_rate"] = growth_rate

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

    # -- PE / operating metrics --
    gross_profit = last_rev - last_cogs if (rev_vals and cogs_vals) else None
    ebitda = (gross_profit - last_opex) if gross_profit is not None and opex_vals else None

    if ebitda is not None and last_rev > 0:
        analytics["ebitda_margin"] = ebitda / last_rev
    if last_rev > 0 and (cogs_vals or opex_vals):
        analytics["operating_margin"] = (last_rev - last_cogs - last_opex) / last_rev
    if ebitda is not None:
        analytics["ebitda"] = ebitda

    # -- Capex, FCF, interest, debt metrics --
    capex_vals = _sorted_vals("capex")
    interest_vals = _sorted_vals("interest_expense")
    debt_service_vals = _sorted_vals("debt_service")
    total_debt_vals = _sorted_vals("total_debt")
    tax_vals = _sorted_vals("tax_expense")
    wc_vals = _sorted_vals("working_capital")

    last_capex = capex_vals[-1] if capex_vals else 0
    last_interest = interest_vals[-1] if interest_vals else 0
    last_debt_service = debt_service_vals[-1] if debt_service_vals else 0
    last_total_debt = total_debt_vals[-1] if total_debt_vals else None
    last_tax = tax_vals[-1] if tax_vals else 0
    last_wc = wc_vals[-1] if wc_vals else None

    if capex_vals:
        analytics["capex"] = last_capex
    if ebitda is not None and capex_vals:
        analytics["fcf"] = ebitda - last_capex
        if last_rev > 0:
            analytics["fcf_margin"] = (ebitda - last_capex) / last_rev
    if ebitda is not None and last_rev > 0 and capex_vals:
        analytics["capex_ratio"] = last_capex / last_rev

    # Leverage and coverage ratios
    if last_total_debt is not None and ebitda and ebitda > 0:
        analytics["leverage_ratio"] = last_total_debt / ebitda
    if ebitda and last_interest and last_interest > 0:
        analytics["interest_coverage"] = ebitda / last_interest
    if ebitda and last_debt_service and last_debt_service > 0:
        analytics["debt_service_coverage"] = ebitda / last_debt_service

    # Net income (approximate)
    if ebitda is not None:
        net_income = ebitda - last_interest - last_tax
        analytics["net_income"] = net_income
        if last_rev > 0:
            analytics["net_margin"] = net_income / last_rev

    # -- Headcount / cost per head --
    last_hc = hc_vals[-1] if hc_vals else None
    if last_hc is not None:
        analytics["headcount"] = last_hc
    if burn_rate is not None and last_hc and last_hc > 0:
        analytics["cost_per_head"] = burn_rate / last_hc
    if last_rev > 0 and last_hc and last_hc > 0:
        analytics["revenue_per_employee"] = last_rev / last_hc
    if ebitda is not None and last_hc and last_hc > 0:
        analytics["ebitda_per_employee"] = ebitda / last_hc

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
        sub = row.get("subcategory") or ""
        raw_period = row.get("period")
        amount = row.get("amount")
        if not cat or raw_period is None or amount is None:
            continue
        period = _normalize_period(str(raw_period))
        if not period:
            continue
        if sub:
            # Include subcategory as separate key (e.g. "opex_rd:engineering_salaries")
            # so downstream services can forecast each line item independently.
            time_series[f"{cat}:{sub}"][period] += float(amount)
        else:
            # Parent rows (subcategory="") contain the aggregated total.
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
    all_keys = sorted(time_series.keys())
    subcategory_keys = [k for k in all_keys if ":" in k]
    metadata = {
        "row_count": len(rows),
        "period_range": [periods[0], periods[-1]] if periods else [],
        "period_count": len(periods),
        "categories": all_keys,
        "has_subcategories": bool(subcategory_keys),
        "subcategory_keys": subcategory_keys,
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
# Batch pull: all companies in a fund
# ---------------------------------------------------------------------------

class FundCompanies:
    """Result of pulling all companies for a fund.

    Attributes:
        company_data:  {company_id: CompanyData} — full financials per company.
        investments:   {company_id: {amount, ownership_pct, date, status}} — fund investment info.
        names:         {company_id: company_name} — display names.
        company_ids:   Ordered list of company UUIDs.
    """

    __slots__ = ("fund_id", "company_data", "investments", "names", "company_ids")

    def __init__(
        self,
        fund_id: str,
        company_data: Dict[str, "CompanyData"],
        investments: Dict[str, Dict[str, Any]],
        names: Dict[str, str],
        company_ids: List[str],
    ):
        self.fund_id = fund_id
        self.company_data = company_data
        self.investments = investments
        self.names = names
        self.company_ids = company_ids

    def iter_companies(self):
        """Yield (company_id, name, CompanyData, investment_dict) for each company."""
        for cid in self.company_ids:
            yield (
                cid,
                self.names.get(cid, "Unknown"),
                self.company_data.get(cid),
                self.investments.get(cid, {}),
            )

    def to_dicts(self) -> List[Dict[str, Any]]:
        """Return list of flat dicts (forecast_seed + analytics + investment + name).

        This is the replacement for looping over gridSnapshot rows and scraping cells.
        """
        result = []
        for cid, name, cd, inv in self.iter_companies():
            if cd and cd.metadata.get("row_count", 0) > 0:
                d = cd.to_forecast_seed()
                d.update(cd.analytics)
                d["name"] = name
            else:
                d = {"company_id": cid, "name": name}
            d["id"] = cid
            d["company_id"] = cid
            if inv:
                d["invested_amount"] = inv.get("amount")
                d["ownership_pct"] = inv.get("ownership_pct")
                d["investment_date"] = inv.get("date")
                d["investment_status"] = inv.get("status")
            result.append(d)
        return result

    @property
    def count(self) -> int:
        return len(self.company_ids)

    @property
    def empty(self) -> bool:
        return len(self.company_ids) == 0


def pull_fund_companies(fund_id: str) -> FundCompanies:
    """Pull ALL companies in a fund with their full financials in a single batch.

    1. Query companies table by fund_id for all company ids + names.
    2. Batch query fpa_actuals for ALL those company_ids.
    3. Group by company_id, build a CompanyData per company.
    4. Return FundCompanies with everything.

    This avoids N+1 queries — one batch for all companies.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    empty = FundCompanies(
        fund_id=fund_id,
        company_data={},
        investments={},
        names={},
        company_ids=[],
    )
    if not sb or not fund_id:
        return empty

    # --- Step 1: Get companies directly (companies table has fund_id) ---
    try:
        pc_rows = (
            sb.table("companies")
            .select("id, name, current_valuation_usd, last_valuation_usd, total_funding_usd, stage, sector, current_arr_usd")
            .eq("fund_id", fund_id)
            .execute()
            .data
        ) or []
    except Exception as e:
        logger.warning("[FUND_PULL] companies query failed: %s", e)
        return empty

    if not pc_rows:
        logger.info("[FUND_PULL] No companies found for fund=%s", fund_id)
        return empty

    company_ids: List[str] = []
    investments: Dict[str, Dict[str, Any]] = {}
    names: Dict[str, str] = {}

    for pc in pc_rows:
        cid = pc.get("id")
        if not cid:
            continue
        company_ids.append(cid)
        names[cid] = pc.get("name", "")
        # Investment data from company record
        inv_amount = pc.get("total_funding_usd")
        investments[cid] = {
            "amount": inv_amount,
            "ownership_pct": None,
            "date": None,
            "status": pc.get("stage"),
        }

    if not company_ids:
        return empty

    # --- Step 2: Batch query fpa_actuals for ALL company_ids ---
    try:
        actuals_rows = (
            sb.table("fpa_actuals")
            .select("company_id, category, subcategory, amount, period")
            .in_("company_id", company_ids)
            .order("period", desc=False)
            .execute()
            .data
        ) or []
    except Exception as e:
        logger.warning("[FUND_PULL] fpa_actuals batch query failed: %s", e)
        actuals_rows = []

    # --- Step 3: Group by company_id and build CompanyData per company ---
    from collections import defaultdict as _dd

    # {company_id: [(category, subcategory, amount, period), ...]}
    grouped: Dict[str, list] = {cid: [] for cid in company_ids}
    for row in actuals_rows:
        cid = row.get("company_id")
        if cid and cid in grouped:
            grouped[cid].append(row)

    company_data: Dict[str, CompanyData] = {}
    for cid in company_ids:
        rows = grouped.get(cid, [])
        if not rows:
            company_data[cid] = CompanyData(
                company_id=cid,
                time_series={},
                latest={},
                periods=[],
                metadata={"row_count": 0},
            )
            continue

        # Build time_series: {category: {period: summed_amount}}
        ts: Dict[str, Dict[str, float]] = _dd(lambda: _dd(float))
        all_periods: set = set()

        for r in rows:
            cat = r.get("category")
            sub = r.get("subcategory") or ""
            raw_period = r.get("period")
            amount = r.get("amount")
            if not cat or raw_period is None or amount is None:
                continue
            period = _normalize_period(str(raw_period))
            if not period:
                continue
            if sub:
                ts[f"{cat}:{sub}"][period] += float(amount)
            else:
                ts[cat][period] += float(amount)
            all_periods.add(period)

        ts_frozen = {cat: dict(periods) for cat, periods in ts.items()}
        periods = sorted(all_periods)

        # Latest values
        latest_raw: Dict[str, float] = {}
        if periods:
            last_period = periods[-1]
            for cat, series in ts_frozen.items():
                if last_period in series:
                    latest_raw[cat] = series[last_period]
                else:
                    cat_periods = sorted(series.keys())
                    if cat_periods:
                        latest_raw[cat] = series[cat_periods[-1]]

        latest = _compute_derived(latest_raw)
        analytics = _compute_analytics(ts_frozen, latest, periods)

        company_data[cid] = CompanyData(
            company_id=cid,
            time_series=ts_frozen,
            latest=latest,
            periods=periods,
            metadata={
                "row_count": len(rows),
                "period_range": [periods[0], periods[-1]] if periods else [],
                "period_count": len(periods),
                "categories": sorted(ts_frozen.keys()),
            },
            analytics=analytics,
        )

    logger.info(
        "[FUND_PULL] fund=%s companies=%d actuals_rows=%d",
        fund_id, len(company_ids), len(actuals_rows),
    )

    return FundCompanies(
        fund_id=fund_id,
        company_data=company_data,
        investments=investments,
        names=names,
        company_ids=company_ids,
    )


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
