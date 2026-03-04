"""
Budget Variance Service

Compares actuals against budget. Supports two budget sources:
  1. Legacy budget_lines table (manually entered m1..m12 columns)
  2. Approved scenario branch projection (the real system)

Features:
  - YTD variance (Jan through current month)
  - Cross-year support (arbitrary date ranges)
  - Department/category rollup
  - Per-month trend detection (getting worse or better)
  - Approved branch as budget source
"""

from datetime import date
from typing import Any, Dict, List, Literal, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

BudgetSource = Literal["branch", "budget_lines"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_variance_report(
    company_id: str,
    budget_id: Optional[str] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    source: BudgetSource = "branch",
) -> Dict[str, Any]:
    """
    Full variance report: actuals vs budget.

    If source="branch", finds the approved branch for the company and
    uses its projection as the budget. Falls back to budget_lines if
    no approved branch exists or source="budget_lines".

    Returns:
        {
            "source": "branch" | "budget_lines",
            "period_start": "2025-01-01",
            "period_end": "2025-06-30",
            "summary": { total_actual, total_budget, total_variance, total_variance_pct },
            "by_category": [ ... per-category rows sorted by |variance_pct| ... ],
            "monthly_trend": [ ... per-month totals for trend detection ... ],
        }
    """
    today = date.today()
    if not period_start:
        period_start = date(today.year, 1, 1)
    if not period_end:
        period_end = today.replace(day=1)  # first of current month

    actuals_monthly = _get_actuals_monthly(company_id, period_start, period_end)

    # Try approved branch first, fall back to budget_lines
    budget_monthly: Dict[str, Dict[str, float]] = {}
    used_source: BudgetSource = source

    if source == "branch":
        budget_monthly = _get_budget_from_approved_branch(company_id, period_start, period_end)
        if not budget_monthly:
            logger.info("No approved branch found for %s, falling back to budget_lines", company_id)
            if budget_id:
                budget_monthly = _get_budget_from_lines(budget_id, period_start, period_end)
                used_source = "budget_lines"
    else:
        if budget_id:
            budget_monthly = _get_budget_from_lines(budget_id, period_start, period_end)

    if not actuals_monthly and not budget_monthly:
        return {
            "source": used_source,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "summary": {},
            "by_category": [],
            "monthly_trend": [],
        }

    by_category = _compute_category_variance(actuals_monthly, budget_monthly)
    monthly_trend = _compute_monthly_trend(actuals_monthly, budget_monthly)
    summary = _compute_summary(by_category)

    return {
        "source": used_source,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "summary": summary,
        "by_category": by_category,
        "monthly_trend": monthly_trend,
    }


def get_ytd_variance(
    company_id: str,
    budget_id: Optional[str] = None,
    source: BudgetSource = "branch",
) -> Dict[str, Any]:
    """Convenience: YTD variance from Jan 1 through today."""
    today = date.today()
    return get_variance_report(
        company_id=company_id,
        budget_id=budget_id,
        period_start=date(today.year, 1, 1),
        period_end=today,
        source=source,
    )


def get_department_drilldown(
    company_id: str,
    category: str,
    budget_id: Optional[str] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    source: BudgetSource = "branch",
) -> Dict[str, Any]:
    """
    Month-by-month drill-down for a single category.
    Shows each month's actual vs budget and trend direction.
    """
    today = date.today()
    if not period_start:
        period_start = date(today.year, 1, 1)
    if not period_end:
        period_end = today

    actuals_monthly = _get_actuals_monthly(company_id, period_start, period_end)
    if source == "branch":
        budget_monthly = _get_budget_from_approved_branch(company_id, period_start, period_end)
        if not budget_monthly and budget_id:
            budget_monthly = _get_budget_from_lines(budget_id, period_start, period_end)
    else:
        budget_monthly = _get_budget_from_lines(budget_id, period_start, period_end) if budget_id else {}

    months = sorted(set(list(actuals_monthly.keys()) + list(budget_monthly.keys())))
    rows = []
    prev_variance_pct = None

    for period in months:
        actual = actuals_monthly.get(period, {}).get(category, 0)
        budget = budget_monthly.get(period, {}).get(category, 0)
        variance = actual - budget
        variance_pct = (variance / budget * 100) if budget else None

        trend = "flat"
        if prev_variance_pct is not None:
            if variance_pct > prev_variance_pct + 2:
                trend = "worsening"
            elif variance_pct < prev_variance_pct - 2:
                trend = "improving"

        rows.append({
            "period": period,
            "actual": round(actual, 2),
            "budget": round(budget, 2),
            "variance": round(variance, 2),
            "variance_pct": round(variance_pct, 1),
            "trend": trend,
        })
        prev_variance_pct = variance_pct

    # Consecutive overrun/underrun streak
    streak = 0
    streak_direction = None
    for row in reversed(rows):
        if row["variance"] > 0:
            if streak_direction is None or streak_direction == "over":
                streak += 1
                streak_direction = "over"
            else:
                break
        elif row["variance"] < 0:
            if streak_direction is None or streak_direction == "under":
                streak += 1
                streak_direction = "under"
            else:
                break
        else:
            break

    return {
        "category": category,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "months": rows,
        "streak": streak,
        "streak_direction": streak_direction,
    }


# ---------------------------------------------------------------------------
# Budget from approved scenario branch
# ---------------------------------------------------------------------------


def _get_budget_from_approved_branch(
    company_id: str,
    period_start: date,
    period_end: date,
) -> Dict[str, Dict[str, float]]:
    """
    Find the approved/locked branch for this company, execute its
    projection, and reshape into {period: {category: amount}}.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return {}

    result = (
        sb.table("scenario_branches")
        .select("id")
        .eq("company_id", company_id)
        .in_("status", ["approved", "locked"])
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return {}

    branch_id = result.data[0]["id"]

    from app.services.scenario_branch_service import ScenarioBranchService
    sbs = ScenarioBranchService()
    exec_result = sbs.execute_branch(
        branch_id=branch_id,
        company_id=company_id,
        forecast_months=24,
    )

    forecast = exec_result.get("forecast", [])
    if not forecast:
        return {}

    # Reshape forecast into {period: {category: amount}}
    budget: Dict[str, Dict[str, float]] = {}
    for month in forecast:
        period = month.get("period", "")[:7]  # "2025-01"
        if not period:
            continue

        # Filter to requested range
        try:
            y, m = int(period[:4]), int(period[5:7])
            period_date = date(y, m, 1)
        except (ValueError, IndexError):
            continue

        if period_date < period_start.replace(day=1) or period_date > period_end:
            continue

        budget[period] = {
            "revenue": month.get("revenue", 0),
            "cogs": month.get("cogs", 0),
            "gross_profit": month.get("gross_profit", 0),
            "rd_spend": month.get("rd_spend", 0),
            "sm_spend": month.get("sm_spend", 0),
            "ga_spend": month.get("ga_spend", 0),
            "total_opex": month.get("total_opex", 0),
            "ebitda": month.get("ebitda", 0),
            "free_cash_flow": month.get("free_cash_flow", 0),
            "cash_balance": month.get("cash_balance", 0),
        }

    return budget


# ---------------------------------------------------------------------------
# Budget from legacy budget_lines table
# ---------------------------------------------------------------------------


def _get_budget_from_lines(
    budget_id: str,
    period_start: date,
    period_end: date,
) -> Dict[str, Dict[str, float]]:
    """
    Pull budget_lines and reshape into {period: {category: amount}}.
    Handles cross-year by iterating month-by-month through the range.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return {}

    rows = (
        sb.table("budget_lines")
        .select("*")
        .eq("budget_id", budget_id)
        .execute()
        .data
    )
    if not rows:
        return {}

    # budget_lines has m1..m12 columns for a single year
    # We need to figure out which year the budget covers
    budget_meta = (
        sb.table("budgets")
        .select("year")
        .eq("id", budget_id)
        .limit(1)
        .execute()
    )
    budget_year = (budget_meta.data[0].get("year") if budget_meta.data else period_start.year)

    budget: Dict[str, Dict[str, float]] = {}
    cur = date(max(period_start.year, budget_year), period_start.month, 1)
    end = period_end

    while cur <= end:
        if cur.year == budget_year:
            month_key = f"m{cur.month}"
            period_key = f"{cur.year}-{cur.month:02d}"
            cats: Dict[str, float] = {}
            for line in rows:
                val = line.get(month_key, 0)
                if val:
                    cats[line["category"]] = float(val)
            if cats:
                budget[period_key] = cats

        # Advance month
        m = cur.month + 1
        y = cur.year
        if m > 12:
            m = 1
            y += 1
        cur = date(y, m, 1)

    return budget


# ---------------------------------------------------------------------------
# Actuals loading
# ---------------------------------------------------------------------------


def _get_actuals_monthly(
    company_id: str,
    period_start: date,
    period_end: date,
) -> Dict[str, Dict[str, float]]:
    """
    Pull fpa_actuals and group into {period: {category: amount}}.
    Handles arbitrary date ranges.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return {}

    result = (
        sb.table("fpa_actuals")
        .select("category, amount, period")
        .eq("company_id", company_id)
        .gte("period", period_start.isoformat())
        .lte("period", period_end.isoformat())
        .execute()
    )

    by_period: Dict[str, Dict[str, float]] = {}
    for row in result.data or []:
        period = row["period"][:7]
        by_period.setdefault(period, {})
        cat = row["category"]
        by_period[period][cat] = by_period[period].get(cat, 0) + float(row["amount"])

    return by_period


# ---------------------------------------------------------------------------
# Variance computation
# ---------------------------------------------------------------------------


def _compute_category_variance(
    actuals: Dict[str, Dict[str, float]],
    budget: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    """Aggregate across all months, compute variance per category."""
    all_categories: set = set()
    for cats in actuals.values():
        all_categories.update(cats.keys())
    for cats in budget.values():
        all_categories.update(cats.keys())

    results = []
    for category in all_categories:
        actual_total = sum(
            cats.get(category, 0) for cats in actuals.values()
        )
        budget_total = sum(
            cats.get(category, 0) for cats in budget.values()
        )

        if budget_total == 0 and actual_total == 0:
            continue

        variance = actual_total - budget_total
        variance_pct = (variance / budget_total * 100) if budget_total else 0

        # Trend: compare last 3 months variance direction
        trend = _detect_trend(actuals, budget, category)

        if abs(variance_pct) > 15:
            status = "critical"
        elif abs(variance_pct) > 5:
            status = "over" if variance > 0 else "under"
        else:
            status = "on_track"

        results.append({
            "category": category,
            "actual": round(actual_total, 2),
            "budget": round(budget_total, 2),
            "variance": round(variance, 2),
            "variance_pct": round(variance_pct, 1),
            "status": status,
            "trend": trend,
        })

    return sorted(results, key=lambda r: abs(r["variance_pct"]), reverse=True)


def _detect_trend(
    actuals: Dict[str, Dict[str, float]],
    budget: Dict[str, Dict[str, float]],
    category: str,
) -> str:
    """
    Look at last 3 months of variance for a category.
    Returns: "worsening", "improving", "stable", or "insufficient_data".
    """
    all_periods = sorted(set(list(actuals.keys()) + list(budget.keys())))
    recent = all_periods[-3:] if len(all_periods) >= 3 else all_periods

    if len(recent) < 2:
        return "insufficient_data"

    variances = []
    for period in recent:
        a = actuals.get(period, {}).get(category, 0)
        b = budget.get(period, {}).get(category, 0)
        pct = ((a - b) / b * 100) if b else 0
        variances.append(pct)

    # Track signed variance direction — worsening = moving further from budget
    if len(variances) >= 2:
        if variances[-1] > variances[0] + 2:
            return "worsening"  # overspend increasing or under-revenue growing
        elif variances[-1] < variances[0] - 2:
            return "improving"  # converging toward budget
    return "stable"


def _compute_monthly_trend(
    actuals: Dict[str, Dict[str, float]],
    budget: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    """Per-month aggregate totals for charting."""
    all_periods = sorted(set(list(actuals.keys()) + list(budget.keys())))
    rows = []

    for period in all_periods:
        a_total = sum(actuals.get(period, {}).values())
        b_total = sum(budget.get(period, {}).values())
        variance = a_total - b_total
        variance_pct = (variance / b_total * 100) if b_total else 0

        rows.append({
            "period": period,
            "actual_total": round(a_total, 2),
            "budget_total": round(b_total, 2),
            "variance": round(variance, 2),
            "variance_pct": round(variance_pct, 1),
        })

    return rows


def _compute_summary(by_category: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll up category-level variance into a single summary."""
    total_actual = sum(r["actual"] for r in by_category)
    total_budget = sum(r["budget"] for r in by_category)
    total_variance = total_actual - total_budget
    total_variance_pct = (total_variance / total_budget * 100) if total_budget else 0

    critical_count = sum(1 for r in by_category if r["status"] == "critical")
    over_count = sum(1 for r in by_category if r["status"] == "over")

    return {
        "total_actual": round(total_actual, 2),
        "total_budget": round(total_budget, 2),
        "total_variance": round(total_variance, 2),
        "total_variance_pct": round(total_variance_pct, 1),
        "categories_critical": critical_count,
        "categories_over": over_count,
        "categories_total": len(by_category),
    }
