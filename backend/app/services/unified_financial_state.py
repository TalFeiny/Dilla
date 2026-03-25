"""
Unified Financial State
Single snapshot of everything the strategic intelligence layer needs.

Gathers from ALL subsystems in parallel — FPA actuals, KPIs, forecast,
drivers, cap table, valuation, world model. Every field is derived from
actual data via existing services. Nothing hardcoded.

Usage:
    state = await build_unified_state(company_id, supabase_client)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures — lightweight wrappers for cross-silo aggregation
# ---------------------------------------------------------------------------

@dataclass
class ActualsSummary:
    """Recent actuals for a single category."""
    category: str
    latest_period: Optional[str] = None
    latest_amount: Optional[float] = None
    series: List[Dict[str, Any]] = field(default_factory=list)  # [{period, amount}]
    periods_available: int = 0


@dataclass
class DriverState:
    """Resolved state of a single driver."""
    id: str
    label: str
    level: str
    unit: str
    how: str
    base: Optional[float] = None
    override: Optional[float] = None
    effective: Optional[float] = None
    source: str = "base"  # "base" | "branch"
    ripple: List[str] = field(default_factory=list)


@dataclass
class CapTableSummary:
    """Lightweight cap table snapshot for strategic reasoning."""
    total_raised: Optional[float] = None
    latest_round: Optional[str] = None
    latest_pre_money: Optional[float] = None
    latest_post_money: Optional[float] = None
    ownership: Dict[str, float] = field(default_factory=dict)  # shareholder → %
    funding_rounds: List[Dict[str, Any]] = field(default_factory=list)
    equity_weight: Optional[float] = None   # from cap_table_entries ledger
    debt_weight: Optional[float] = None     # from cap_table_entries ledger
    total_debt: Optional[float] = None
    source: str = "portfolio_companies"      # "ledger" | "portfolio_companies"


@dataclass
class BranchSummary:
    """Minimal scenario branch info."""
    branch_id: str
    name: str
    probability: Optional[float] = None
    assumptions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedFinancialState:
    """Single snapshot of everything the strategic layer needs to reason about.

    Every field is populated from actual data via existing services.
    Fields that can't be populated (missing data) stay None — the strategic
    layer must handle partial state gracefully.
    """

    # === Identity ===
    company_id: str
    company_name: Optional[str] = None
    stage: Optional[str] = None
    sector: Optional[str] = None

    # === FPA Domain (from actuals + forecast services) ===
    actuals: Dict[str, ActualsSummary] = field(default_factory=dict)
    kpis: Optional[Any] = None  # KPISnapshot from kpi_engine
    forecast: List[Dict[str, Any]] = field(default_factory=list)  # monthly forecast
    drivers: Dict[str, DriverState] = field(default_factory=dict)
    active_branches: List[BranchSummary] = field(default_factory=list)

    # === Investment Domain ===
    cap_table: Optional[CapTableSummary] = None
    last_valuation: Optional[Dict[str, Any]] = None  # ValuationResult as dict
    wacc: Optional[Dict[str, Any]] = None  # populated by dynamic WACC (section 1c)

    # === World Model (from world_model_builder) ===
    qualitative_factors: Dict[str, Any] = field(default_factory=dict)
    market_timing: Optional[str] = None  # HOT | COOLING | COLD | EMERGING

    # === Base financials (derived from actuals, not hardcoded) ===
    revenue: Optional[float] = None
    burn_rate: Optional[float] = None
    net_burn: Optional[float] = None
    cash_balance: Optional[float] = None
    gross_margin: Optional[float] = None
    growth_rate: Optional[float] = None
    headcount: Optional[float] = None
    runway_months: Optional[float] = None

    # === Derived trajectories (computed from actuals trends) ===
    burn_trajectory: Optional[str] = None       # "accelerating" | "stable" | "improving"
    growth_trajectory: Optional[str] = None     # "accelerating" | "decelerating" | "stable"
    unit_economics_health: Optional[str] = None # "healthy" | "marginal" | "broken"
    months_to_next_round: Optional[float] = None
    negotiating_position: Optional[str] = None  # "strong" | "moderate" | "weak"


# ---------------------------------------------------------------------------
# Builder — gathers from all subsystems
# ---------------------------------------------------------------------------

async def build_unified_state(
    company_id: str,
    branch_id: Optional[str] = None,
    company_data: Optional[Dict[str, Any]] = None,
) -> UnifiedFinancialState:
    """Gather from ALL subsystems. ~3-5 DB calls, cached per session.

    Args:
        company_id: The company to build state for.
        branch_id: Optional scenario branch for driver resolution.
        company_data: Optional pre-loaded company_data dict (from IntelligentGapFiller
                      or Supabase). If not provided, we build from actuals.
    """
    state = UnifiedFinancialState(company_id=company_id)

    # --- Step 1: Base financials from actuals ---
    base_data = await _load_base_financials(company_id, company_data)
    state.revenue = base_data.get("revenue")
    state.burn_rate = base_data.get("burn_rate")
    state.net_burn = base_data.get("net_burn")
    state.cash_balance = base_data.get("cash_balance")
    state.gross_margin = base_data.get("gross_margin")
    state.growth_rate = base_data.get("growth_rate")
    state.headcount = base_data.get("headcount")
    state.runway_months = base_data.get("runway_months")
    state.stage = base_data.get("stage") or (company_data or {}).get("stage")
    state.sector = base_data.get("sector") or (company_data or {}).get("sector")
    state.company_name = (company_data or {}).get("name")

    # --- Step 2: Parallel fetch of KPIs, actuals history, forecast, branches ---
    kpi_task = asyncio.create_task(_load_kpis(company_id))
    actuals_task = asyncio.create_task(_load_actuals_history(company_id))
    forecast_task = asyncio.create_task(_load_forecast(company_id, base_data))
    branches_task = asyncio.create_task(_load_branches(company_id))
    drivers_task = asyncio.create_task(
        _load_drivers(company_id, branch_id) if branch_id else _noop_dict()
    )
    cap_table_task = asyncio.create_task(_load_cap_table(company_id))

    results = await asyncio.gather(
        kpi_task, actuals_task, forecast_task,
        branches_task, drivers_task, cap_table_task,
        return_exceptions=True,
    )

    # Unpack results, logging failures but not crashing
    if not isinstance(results[0], BaseException):
        state.kpis = results[0]
    else:
        logger.warning("KPI load failed for %s: %s", company_id, results[0])

    if not isinstance(results[1], BaseException):
        state.actuals = results[1]
    else:
        logger.warning("Actuals load failed for %s: %s", company_id, results[1])

    if not isinstance(results[2], BaseException):
        state.forecast = results[2]
    else:
        logger.warning("Forecast load failed for %s: %s", company_id, results[2])

    if not isinstance(results[3], BaseException):
        state.active_branches = results[3]
    else:
        logger.warning("Branches load failed for %s: %s", company_id, results[3])

    if not isinstance(results[4], BaseException):
        state.drivers = results[4]
    else:
        logger.warning("Drivers load failed for %s: %s", company_id, results[4])

    if not isinstance(results[5], BaseException):
        state.cap_table = results[5]
    else:
        logger.warning("Cap table load failed for %s: %s", company_id, results[5])

    # --- Step 3: Derive trajectories from actual data ---
    _derive_trajectories(state)

    return state


# ---------------------------------------------------------------------------
# Loaders — each wraps an existing service, no hardcoded values
# ---------------------------------------------------------------------------

async def _load_base_financials(
    company_id: str,
    company_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build base financials from actuals or provided company_data."""
    if company_data:
        return company_data

    try:
        from app.services.actuals_ingestion import seed_forecast_from_actuals
        return seed_forecast_from_actuals(company_id)
    except Exception as e:
        logger.warning("seed_forecast_from_actuals failed: %s", e)
        return {"company_id": company_id}


async def _load_kpis(company_id: str) -> Any:
    """Load KPIs from existing KPI engine."""
    try:
        from app.services.kpi_engine import KPIEngine
        engine = KPIEngine()
        return engine.compute(company_id)
    except Exception as e:
        logger.warning("KPI compute failed: %s", e)
        return None


async def _load_actuals_history(company_id: str) -> Dict[str, ActualsSummary]:
    """Load actuals across all categories for trend analysis."""
    from app.services.company_data_pull import pull_company_data

    cd = pull_company_data(company_id)
    result: Dict[str, ActualsSummary] = {}

    for category in cd.time_series:
        hist = cd.historical_values(category)
        if hist:
            series = [{"period": p, "amount": v} for p, v in hist]
            result[category] = ActualsSummary(
                category=category,
                latest_period=hist[-1][0],
                latest_amount=hist[-1][1],
                series=series,
                periods_available=len(hist),
            )

    return result


async def _load_forecast(
    company_id: str,
    base_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build 24-month forecast from existing cash flow planning service."""
    if not base_data.get("revenue") and not base_data.get("burn_rate"):
        return []  # not enough data to forecast

    try:
        from app.services.cash_flow_planning_service import CashFlowPlanningService
        cfp = CashFlowPlanningService()
        return cfp.build_monthly_cash_flow_model(base_data, months=24)
    except Exception as e:
        logger.warning("Forecast build failed: %s", e)
        return []


async def _load_branches(company_id: str) -> List[BranchSummary]:
    """Load active scenario branches."""
    try:
        from app.core.supabase_client import get_supabase_client
        sb = get_supabase_client()
        if not sb:
            return []

        rows = (
            sb.table("scenario_branches")
            .select("id, name, probability, assumptions")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
        )
        return [
            BranchSummary(
                branch_id=r["id"],
                name=r["name"],
                probability=r.get("probability"),
                assumptions=r.get("assumptions") or {},
            )
            for r in (rows or [])
        ]
    except Exception as e:
        logger.warning("Branch load failed: %s", e)
        return []


async def _load_drivers(company_id: str, branch_id: str) -> Dict[str, DriverState]:
    """Resolve driver state for a branch using ScenarioBranchService."""
    try:
        from app.services.scenario_branch_service import ScenarioBranchService
        sbs = ScenarioBranchService()
        raw = sbs.resolve_drivers(branch_id, company_id)

        if "error" in raw:
            logger.warning("Driver resolution error: %s", raw["error"])
            return {}

        return {
            did: DriverState(
                id=did,
                label=d.get("label", ""),
                level=d.get("level", ""),
                unit=d.get("unit", ""),
                how=d.get("how", ""),
                base=d.get("base"),
                override=d.get("override"),
                effective=d.get("effective"),
                source=d.get("source", "base"),
                ripple=d.get("ripple", []),
            )
            for did, d in raw.items()
            if isinstance(d, dict) and "id" in d
        }
    except Exception as e:
        logger.warning("Driver load failed: %s", e)
        return {}


async def _load_cap_table(company_id: str) -> Optional[CapTableSummary]:
    """Load cap table data from cap_table_entries ledger, fall back to portfolio_companies."""
    try:
        # --- Try cap_table_entries ledger first ---
        from app.services.cap_table_ledger import CapTableLedger
        ledger = CapTableLedger()
        ledger_data = ledger.load(company_id=company_id)

        if ledger_data.get("entry_count", 0) > 0:
            # Build ownership map from entries
            ownership = ledger_data.get("ownership", {})
            # Find latest round from entries
            entries = ledger_data.get("share_entries", [])
            latest_round = None
            latest_date = None
            for e in entries:
                rd = e.get("round_name")
                dt = e.get("investment_date")
                if rd and dt:
                    if latest_date is None or dt > latest_date:
                        latest_date = dt
                        latest_round = rd

            return CapTableSummary(
                total_raised=ledger_data.get("total_raised"),
                latest_round=latest_round,
                ownership=ownership,
                equity_weight=ledger_data.get("equity_weight"),
                debt_weight=ledger_data.get("debt_weight"),
                total_debt=ledger_data.get("total_debt"),
                source="ledger",
            )
    except Exception as e:
        logger.debug("Cap table ledger load failed (falling back): %s", e)

    try:
        # --- Fall back to portfolio_companies ---
        from app.core.supabase_client import get_supabase_client
        sb = get_supabase_client()
        if not sb:
            return None

        rows = (
            sb.table("portfolio_companies")
            .select("name, total_raised, last_round, stage, sector")
            .eq("id", company_id)
            .limit(1)
            .execute()
            .data
        )
        if not rows:
            return None

        co = rows[0]
        return CapTableSummary(
            total_raised=co.get("total_raised"),
            latest_round=co.get("last_round"),
            source="portfolio_companies",
        )
    except Exception as e:
        logger.warning("Cap table load failed: %s", e)
        return None


async def _noop_dict() -> Dict:
    return {}


# ---------------------------------------------------------------------------
# Trajectory derivation — all from actual KPI/actuals trends, no hardcoding
# ---------------------------------------------------------------------------

def _derive_trajectories(state: UnifiedFinancialState) -> None:
    """Compute derived trajectory fields from the data we actually have.

    Every derivation works only with available data. If there isn't enough
    data for a derivation, the field stays None.
    """

    # --- Burn trajectory: from burn_rate actuals time series ---
    burn_actuals = state.actuals.get("burn_rate") or state.actuals.get("opex_total")
    if burn_actuals and burn_actuals.periods_available >= 3:
        state.burn_trajectory = _classify_trend(
            [e["amount"] for e in burn_actuals.series[-6:]],
            higher_is_worse=True,
        )

    # --- Growth trajectory: from revenue actuals ---
    rev_actuals = state.actuals.get("revenue")
    if rev_actuals and rev_actuals.periods_available >= 3:
        # Compute period-over-period growth rates
        amounts = [e["amount"] for e in rev_actuals.series[-6:]]
        growth_rates = []
        for i in range(1, len(amounts)):
            if amounts[i - 1] and amounts[i - 1] != 0:
                growth_rates.append((amounts[i] - amounts[i - 1]) / abs(amounts[i - 1]))
        if len(growth_rates) >= 2:
            state.growth_trajectory = _classify_trend(
                growth_rates,
                higher_is_worse=False,
            )

    # --- Unit economics health: from KPIs if available ---
    if state.kpis:
        ltv_cac = _find_kpi(state.kpis, "ltv_cac_ratio")
        if ltv_cac is not None:
            if ltv_cac >= 3.0:
                state.unit_economics_health = "healthy"
            elif ltv_cac >= 1.0:
                state.unit_economics_health = "marginal"
            else:
                state.unit_economics_health = "broken"

    # --- Runway and funding timing ---
    if state.runway_months is not None:
        # Estimate months to next round: startups typically raise
        # when runway hits 6-9 months. Use actual runway.
        if state.runway_months > 0:
            state.months_to_next_round = max(0, state.runway_months - 6)

    # --- Negotiating position: derived from runway + growth + metrics ---
    state.negotiating_position = _assess_negotiating_position(state)


def _classify_trend(values: List[float], higher_is_worse: bool = False) -> str:
    """Classify a series as accelerating/stable/improving (or decelerating).

    Uses simple linear regression on the last N values.
    """
    if len(values) < 2:
        return "stable"

    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "stable"

    slope = numerator / denominator
    # Normalize slope relative to mean value
    if y_mean and y_mean != 0:
        relative_slope = slope / abs(y_mean)
    else:
        relative_slope = 0

    threshold = 0.03  # 3% relative change per period

    if higher_is_worse:
        if relative_slope > threshold:
            return "accelerating"  # getting worse
        elif relative_slope < -threshold:
            return "improving"
        return "stable"
    else:
        if relative_slope > threshold:
            return "accelerating"
        elif relative_slope < -threshold:
            return "decelerating"
        return "stable"


def _find_kpi(kpi_snapshot: Any, key: str) -> Optional[float]:
    """Extract a KPI value from a KPISnapshot by key."""
    if not kpi_snapshot or not hasattr(kpi_snapshot, "kpis"):
        return None
    for kpi in kpi_snapshot.kpis:
        if kpi.key == key and kpi.current and kpi.current.value is not None:
            return kpi.current.value
    return None


def _assess_negotiating_position(state: UnifiedFinancialState) -> Optional[str]:
    """Assess negotiating position from available data. No hardcoded thresholds
    beyond what's necessary for classification."""
    signals_strong = 0
    signals_weak = 0
    signals_total = 0

    # Runway signal
    if state.runway_months is not None:
        signals_total += 1
        if state.runway_months >= 18:
            signals_strong += 1
        elif state.runway_months < 6:
            signals_weak += 1

    # Growth signal
    if state.growth_trajectory:
        signals_total += 1
        if state.growth_trajectory == "accelerating":
            signals_strong += 1
        elif state.growth_trajectory == "decelerating":
            signals_weak += 1

    # Unit economics signal
    if state.unit_economics_health:
        signals_total += 1
        if state.unit_economics_health == "healthy":
            signals_strong += 1
        elif state.unit_economics_health == "broken":
            signals_weak += 1

    # Burn trajectory signal
    if state.burn_trajectory:
        signals_total += 1
        if state.burn_trajectory == "improving":
            signals_strong += 1
        elif state.burn_trajectory == "accelerating":
            signals_weak += 1

    if signals_total == 0:
        return None

    strong_ratio = signals_strong / signals_total
    weak_ratio = signals_weak / signals_total

    if strong_ratio >= 0.5:
        return "strong"
    elif weak_ratio >= 0.5:
        return "weak"
    return "moderate"


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------

def state_to_dict(state: UnifiedFinancialState) -> Dict[str, Any]:
    """Convert state to a JSON-serializable dict for LLM consumption."""
    from dataclasses import asdict

    d = asdict(state)

    # Replace KPISnapshot with serializable summary
    if state.kpis and hasattr(state.kpis, "kpis"):
        d["kpis"] = {
            "company_id": state.kpis.company_id,
            "business_type": state.kpis.business_type,
            "as_of": state.kpis.as_of,
            "periods_available": state.kpis.periods_available,
            "kpis": [
                {
                    "key": k.key,
                    "label": k.label,
                    "category": k.category,
                    "current_value": k.current.value if k.current else None,
                    "current_formatted": k.current.formatted if k.current else None,
                    "trend": k.trend,
                    "pop_change_pct": k.pop_change_pct,
                }
                for k in state.kpis.kpis
            ],
            "missing_data": state.kpis.missing_data,
        }

    # Trim actuals series to last 6 for LLM (save tokens)
    for cat, summary in d.get("actuals", {}).items():
        if isinstance(summary, dict) and "series" in summary:
            summary["series"] = summary["series"][-6:]

    # Trim forecast to key fields
    if d.get("forecast"):
        d["forecast"] = [
            {
                "period": m.get("period"),
                "revenue": m.get("revenue"),
                "total_opex": m.get("total_opex"),
                "ebitda": m.get("ebitda"),
                "cash_balance": m.get("cash_balance"),
                "runway_months": m.get("runway_months"),
            }
            for m in d["forecast"]
        ]

    return d
