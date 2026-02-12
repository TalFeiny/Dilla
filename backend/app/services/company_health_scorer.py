"""
Company Health Scorer & Analytics Engine
Computes rich analytical profiles per portfolio company:
- Growth trajectory with decay projections
- Burn & runway estimation
- Funding trajectory prediction
- Per-company return metrics (MOIC, IRR on actual dates)
- Benchmark comparisons (context, not pass/fail)
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.data_validator import (
    ensure_numeric,
    safe_divide,
    safe_get_value,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Benchmark data (mirrors intelligent_gap_filler STAGE_BENCHMARKS)
# ---------------------------------------------------------------------------
STAGE_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "Pre-seed": {
        "arr_median": 50_000,
        "growth_rate": 2.5,
        "burn_monthly": 75_000,
        "team_size": (2, 6),
        "runway_months": 18,
        "next_round_months": 12,
        "valuation_median": 5_000_000,
        "valuation_multiple": 25,
        "gross_margin": 0.65,
    },
    "Seed": {
        "arr_median": 250_000,
        "growth_rate": 3.0,
        "burn_monthly": 100_000,
        "team_size": (5, 12),
        "runway_months": 18,
        "next_round_months": 15,
        "valuation_median": 8_000_000,
        "valuation_multiple": 20,
        "ltv_cac_ratio": 2.5,
        "gross_margin": 0.70,
    },
    "Series A": {
        "arr_median": 2_000_000,
        "growth_rate": 2.5,
        "burn_monthly": 400_000,
        "team_size": (15, 35),
        "runway_months": 18,
        "next_round_months": 18,
        "valuation_median": 35_000_000,
        "valuation_multiple": 15,
        "ltv_cac_ratio": 3.0,
        "gross_margin": 0.75,
    },
    "Series B": {
        "arr_median": 8_000_000,
        "growth_rate": 1.5,
        "burn_monthly": 1_200_000,
        "team_size": (40, 100),
        "runway_months": 24,
        "next_round_months": 20,
        "valuation_median": 100_000_000,
        "valuation_multiple": 12,
        "ltv_cac_ratio": 3.5,
        "gross_margin": 0.78,
    },
    "Series C": {
        "arr_median": 25_000_000,
        "growth_rate": 1.0,
        "burn_monthly": 2_500_000,
        "team_size": (100, 300),
        "runway_months": 24,
        "next_round_months": 24,
        "valuation_median": 250_000_000,
        "valuation_multiple": 10,
        "ltv_cac_ratio": 4.0,
        "gross_margin": 0.80,
    },
    "Series D+": {
        "arr_median": 75_000_000,
        "growth_rate": 0.7,
        "burn_monthly": 3_500_000,
        "team_size": (300, 1000),
        "runway_months": 36,
        "next_round_months": 30,
        "valuation_median": 500_000_000,
        "valuation_multiple": 8,
        "ltv_cac_ratio": 5.0,
        "gross_margin": 0.82,
    },
}

STAGE_TYPICAL_ROUND: Dict[str, Dict[str, Any]] = {
    "Pre-seed": {"amount": 1_500_000, "dilution": 0.15},
    "Seed": {"amount": 3_000_000, "dilution": 0.15},
    "Series A": {"amount": 15_000_000, "dilution": 0.20},
    "Series B": {"amount": 50_000_000, "dilution": 0.15},
    "Series C": {"amount": 100_000_000, "dilution": 0.12},
    "Series D": {"amount": 200_000_000, "dilution": 0.10},
    "Series E": {"amount": 350_000_000, "dilution": 0.08},
    "Growth": {"amount": 500_000_000, "dilution": 0.07},
}

STAGE_SEQUENCE = [
    "Pre-seed", "Seed", "Series A", "Series B",
    "Series C", "Series D", "Series E", "Growth",
]

GEOGRAPHY_BURN_MULTIPLIER: Dict[str, float] = {
    "SF": 1.15, "San Francisco": 1.15, "NYC": 1.10, "New York": 1.10,
    "London": 1.05, "US": 1.0, "Europe": 0.85, "Asia": 0.80,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class CompanyAnalytics:
    """Rich analytical profile for a portfolio company."""

    # Identity
    company_id: str = ""
    company_name: str = ""
    stage: str = ""
    investment_date: Optional[datetime] = None
    months_since_investment: float = 0.0

    # Growth trajectory
    current_arr: float = 0.0
    arr_source: str = "inferred"  # "reported" | "inferred"
    growth_rate: float = 0.0
    growth_at_entry: float = 0.0
    growth_delta: float = 0.0
    growth_trend: str = "stable"  # "accelerating" | "stable" | "decelerating"
    projected_arr_12mo: float = 0.0
    projected_arr_24mo: float = 0.0
    projected_arr_36mo: float = 0.0

    # Burn & runway
    estimated_monthly_burn: float = 0.0
    estimated_cash_remaining: float = 0.0
    estimated_runway_months: float = 0.0
    burn_as_pct_of_arr: float = 0.0
    months_since_last_round: float = 0.0

    # Funding trajectory
    last_round_valuation: float = 0.0
    last_round_amount: float = 0.0
    rounds_raised: List[Dict[str, Any]] = field(default_factory=list)
    time_between_rounds: List[float] = field(default_factory=list)
    avg_step_up_multiple: float = 0.0
    predicted_next_round_months: float = 0.0
    predicted_next_round_stage: str = ""
    predicted_next_raise_amount: float = 0.0

    # Valuation context
    implied_current_valuation: float = 0.0
    valuation_direction: str = "flat"  # "up_round_likely" | "flat" | "down_round_risk"
    current_revenue_multiple: float = 0.0
    stage_benchmark_multiple: float = 0.0
    fair_value_basis: str = "model"  # "recent_transaction" | "comps" | "model"
    months_since_last_price: float = 0.0

    # Vs benchmarks (context, not pass/fail)
    vs_benchmark: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Signals (factual observations)
    signals: List[str] = field(default_factory=list)


@dataclass
class CompanyReturnMetrics:
    """Per-company return metrics using actual dated cash flows."""

    company_id: str = ""
    company_name: str = ""
    invested: float = 0.0
    ownership_pct: float = 0.0
    current_nav: float = 0.0
    moic: float = 0.0
    irr: float = 0.0  # annualised, as decimal (0.25 = 25%)
    holding_period_years: float = 0.0
    unrealized_gain: float = 0.0
    cost_basis_per_pct: float = 0.0


# ---------------------------------------------------------------------------
# IRR solver (Newton-Raphson on dated cash flows)
# ---------------------------------------------------------------------------
def _solve_irr(
    cash_flows: List[Tuple[float, datetime]],
    max_iterations: int = 200,
    tolerance: float = 1e-7,
) -> float:
    """Solve IRR for irregular cash flows using Newton-Raphson.

    Args:
        cash_flows: list of (amount, date) tuples. Negative = outflow.

    Returns:
        Annualised IRR as a decimal (0.25 = 25%).  Returns 0 if it cannot converge.
    """
    if not cash_flows or len(cash_flows) < 2:
        return 0.0

    # Normalise dates to year-fractions from the first cash flow
    base_date = cash_flows[0][1]
    cf_pairs = []
    for amount, dt in cash_flows:
        t = (dt - base_date).days / 365.25
        cf_pairs.append((amount, t))

    # Initial guess based on simple multiple
    total_in = sum(-a for a, _ in cf_pairs if a < 0) or 1.0
    total_out = sum(a for a, _ in cf_pairs if a > 0)
    max_t = max(t for _, t in cf_pairs) or 1.0
    if total_in > 0 and total_out > 0 and max_t > 0:
        guess = (total_out / total_in) ** (1 / max_t) - 1
    else:
        guess = 0.1

    rate = max(min(guess, 5.0), -0.5)

    for _ in range(max_iterations):
        npv = 0.0
        d_npv = 0.0
        for amount, t in cf_pairs:
            discount = (1 + rate) ** t
            if discount == 0:
                break
            npv += amount / discount
            if t != 0:
                d_npv -= t * amount / ((1 + rate) ** (t + 1))

        if abs(d_npv) < 1e-15:
            break

        new_rate = rate - npv / d_npv

        # Clamp to reasonable range
        new_rate = max(min(new_rate, 10.0), -0.99)

        if abs(new_rate - rate) < tolerance:
            return new_rate

        rate = new_rate

    return rate


# ---------------------------------------------------------------------------
# Growth-decay projection (mirrors intelligent_gap_filler lines 935-1016)
# ---------------------------------------------------------------------------
def _project_arr(
    current_arr: float,
    base_growth_rate: float,
    months_forward: int,
) -> float:
    """Project ARR forward using the existing decay model.

    Year 1: 100% of base growth rate
    Year 2: 70%
    Year 3: 50%
    Year 4+: 30%
    """
    if current_arr <= 0 or base_growth_rate <= 0:
        return current_arr

    arr = current_arr
    remaining = months_forward
    year_num = 1

    while remaining > 0:
        months_in_period = min(12, remaining)

        if year_num == 1:
            period_growth = base_growth_rate
        elif year_num == 2:
            period_growth = base_growth_rate * 0.7
        elif year_num == 3:
            period_growth = base_growth_rate * 0.5
        else:
            period_growth = base_growth_rate * 0.3

        monthly_growth = (1 + period_growth) ** (1 / 12) - 1
        period_multiple = (1 + monthly_growth) ** months_in_period
        arr *= period_multiple

        remaining -= months_in_period
        year_num += 1

    return arr


# ---------------------------------------------------------------------------
# Helper: resolve stage key to benchmarks
# ---------------------------------------------------------------------------
def _resolve_stage(stage_raw: str) -> Tuple[str, Dict[str, Any]]:
    """Normalise stage string and return (normalised_key, benchmarks_dict)."""
    if not stage_raw:
        return "Series A", STAGE_BENCHMARKS["Series A"]

    s = stage_raw.strip()
    # Direct match
    if s in STAGE_BENCHMARKS:
        return s, STAGE_BENCHMARKS[s]

    # Case-insensitive + partial matching
    lower = s.lower()
    for key, bench in STAGE_BENCHMARKS.items():
        if key.lower() == lower:
            return key, bench

    if "pre" in lower and "seed" in lower:
        return "Pre-seed", STAGE_BENCHMARKS["Pre-seed"]
    if "seed" in lower:
        return "Seed", STAGE_BENCHMARKS["Seed"]
    if "a" in lower and "series" in lower:
        return "Series A", STAGE_BENCHMARKS["Series A"]
    if "b" in lower and "series" in lower:
        return "Series B", STAGE_BENCHMARKS["Series B"]
    if "c" in lower and "series" in lower:
        return "Series C", STAGE_BENCHMARKS["Series C"]
    if any(x in lower for x in ["d", "e", "f", "growth", "late"]):
        return "Series D+", STAGE_BENCHMARKS["Series D+"]

    return "Series A", STAGE_BENCHMARKS["Series A"]


def _next_stage(current_stage: str) -> str:
    """Return the next stage in the sequence."""
    try:
        idx = STAGE_SEQUENCE.index(current_stage)
        if idx + 1 < len(STAGE_SEQUENCE):
            return STAGE_SEQUENCE[idx + 1]
    except ValueError:
        pass
    return current_stage


def _months_since(date_val: Any) -> float:
    """Return months between date_val and today. Returns 0 if unparsable."""
    if date_val is None:
        return 0.0
    if isinstance(date_val, datetime):
        delta = datetime.now() - date_val
        return max(delta.days / 30.44, 0.0)
    if isinstance(date_val, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                dt = datetime.strptime(date_val.split("+")[0].split("Z")[0], fmt)
                return max((datetime.now() - dt).days / 30.44, 0.0)
            except ValueError:
                continue
    return 0.0


# ---------------------------------------------------------------------------
# Main scorer class
# ---------------------------------------------------------------------------
class CompanyHealthScorer:
    """Produces CompanyAnalytics + CompanyReturnMetrics for portfolio companies."""

    def analyze_company(
        self,
        company: Dict[str, Any],
        fund_investment: Optional[Dict[str, Any]] = None,
    ) -> CompanyAnalytics:
        """Build a CompanyAnalytics profile from a company dict.

        ``company`` should contain at minimum:
            name, stage, funding_rounds (list of dicts with round/amount/date/investors),
            and optionally: revenue/arr, valuation, geography, growth_rate,
            investment_date, burn_rate, total_funding.

        ``fund_investment`` (optional):
            {amount, date, ownership_pct} — our investment details.
        """
        analytics = CompanyAnalytics()
        analytics.company_id = str(company.get("id", ""))
        analytics.company_name = str(company.get("name", "Unknown"))

        # --- Stage ---
        stage_raw = company.get("stage", "") or ""
        stage_key, benchmarks = _resolve_stage(stage_raw)
        analytics.stage = stage_key

        # --- Investment date ---
        inv_date = None
        if fund_investment and fund_investment.get("date"):
            inv_date = fund_investment["date"]
            if isinstance(inv_date, str):
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        inv_date = datetime.strptime(inv_date.split("+")[0].split("Z")[0], fmt)
                        break
                    except ValueError:
                        continue
        elif company.get("investment_date"):
            inv_date = company["investment_date"]
            if isinstance(inv_date, str):
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        inv_date = datetime.strptime(inv_date.split("+")[0].split("Z")[0], fmt)
                        break
                    except ValueError:
                        continue
        analytics.investment_date = inv_date if isinstance(inv_date, datetime) else None
        analytics.months_since_investment = _months_since(analytics.investment_date)

        # --- Funding rounds ---
        rounds = company.get("funding_rounds", []) or []
        analytics.rounds_raised = rounds

        # Time between rounds
        round_dates: List[datetime] = []
        for r in rounds:
            d = r.get("date")
            if d:
                ms = _months_since(d)
                round_dates.append(datetime.now() - timedelta(days=ms * 30.44))
        round_dates.sort()
        if len(round_dates) > 1:
            analytics.time_between_rounds = [
                (round_dates[i + 1] - round_dates[i]).days / 30.44
                for i in range(len(round_dates) - 1)
            ]

        # Last round info
        if rounds:
            last = rounds[-1] if isinstance(rounds[-1], dict) else {}
            analytics.last_round_amount = ensure_numeric(
                last.get("amount") or last.get("round_size"), 0
            )
            analytics.last_round_valuation = ensure_numeric(
                last.get("pre_money_valuation") or last.get("valuation"), 0
            )
            if analytics.last_round_valuation == 0 and analytics.last_round_amount > 0:
                # Estimate from typical dilution
                dilution = STAGE_TYPICAL_ROUND.get(stage_key, {}).get("dilution", 0.20)
                if dilution > 0:
                    analytics.last_round_valuation = analytics.last_round_amount / dilution - analytics.last_round_amount
            analytics.months_since_last_round = _months_since(last.get("date"))
        analytics.months_since_last_price = analytics.months_since_last_round

        # Step-up multiples
        valuations: List[float] = []
        for r in rounds:
            if isinstance(r, dict):
                v = ensure_numeric(r.get("pre_money_valuation") or r.get("valuation"), 0)
                if v > 0:
                    valuations.append(v)
        step_ups: List[float] = []
        for i in range(1, len(valuations)):
            if valuations[i - 1] > 0:
                step_ups.append(valuations[i] / valuations[i - 1])
        analytics.avg_step_up_multiple = (
            sum(step_ups) / len(step_ups) if step_ups else 0.0
        )

        # --- Revenue / ARR ---
        reported_arr = ensure_numeric(
            company.get("arr") or company.get("revenue") or company.get("annual_revenue"), 0
        )
        inferred_arr = ensure_numeric(company.get("inferred_revenue"), 0)

        if reported_arr > 0:
            analytics.current_arr = reported_arr
            analytics.arr_source = "reported"
        elif inferred_arr > 0:
            analytics.current_arr = inferred_arr
            analytics.arr_source = "inferred"
        else:
            analytics.current_arr = benchmarks.get("arr_median", 0)
            analytics.arr_source = "inferred"

        # --- Growth rate ---
        reported_growth = ensure_numeric(company.get("growth_rate"), 0)
        if reported_growth > 0:
            # Normalise: if given as %, convert to decimal multiplier (e.g. 150 → 1.5)
            analytics.growth_rate = reported_growth if reported_growth < 10 else reported_growth / 100
        else:
            analytics.growth_rate = benchmarks.get("growth_rate", 1.0)

        analytics.growth_at_entry = analytics.growth_rate  # best we have unless stored
        analytics.growth_delta = 0.0
        analytics.growth_trend = "stable"

        # --- Project ARR forward ---
        analytics.projected_arr_12mo = _project_arr(analytics.current_arr, analytics.growth_rate, 12)
        analytics.projected_arr_24mo = _project_arr(analytics.current_arr, analytics.growth_rate, 24)
        analytics.projected_arr_36mo = _project_arr(analytics.current_arr, analytics.growth_rate, 36)

        # --- Burn & runway ---
        reported_burn = ensure_numeric(company.get("burn_rate") or company.get("monthly_burn"), 0)
        if reported_burn > 0:
            analytics.estimated_monthly_burn = reported_burn
        else:
            base_burn = benchmarks.get("burn_monthly", 400_000)
            geo = str(company.get("geography") or company.get("headquarters") or "")
            geo_mult = 1.0
            for key, mult in GEOGRAPHY_BURN_MULTIPLIER.items():
                if key.lower() in geo.lower():
                    geo_mult = mult
                    break
            analytics.estimated_monthly_burn = base_burn * geo_mult

        # Estimate cash remaining
        total_funding = ensure_numeric(company.get("total_funding"), 0)
        if total_funding == 0:
            total_funding = sum(
                ensure_numeric(r.get("amount") or r.get("round_size"), 0)
                for r in rounds
                if isinstance(r, dict)
            )
        months_elapsed = analytics.months_since_last_round
        spent = analytics.estimated_monthly_burn * months_elapsed
        analytics.estimated_cash_remaining = max(total_funding - spent, 0)
        analytics.estimated_runway_months = (
            analytics.estimated_cash_remaining / analytics.estimated_monthly_burn
            if analytics.estimated_monthly_burn > 0
            else 0
        )
        analytics.burn_as_pct_of_arr = (
            (analytics.estimated_monthly_burn * 12) / analytics.current_arr * 100
            if analytics.current_arr > 0
            else 0
        )

        # --- Funding trajectory prediction ---
        benchmark_next_months = benchmarks.get("next_round_months", 18)
        # Adjust for growth: faster growth → raise sooner (leverage), slower → later
        growth_vs_bench = analytics.growth_rate / benchmarks.get("growth_rate", 1.0) if benchmarks.get("growth_rate", 1.0) > 0 else 1.0
        if growth_vs_bench > 1.2:
            timing_adj = 0.85  # raise sooner
        elif growth_vs_bench < 0.8:
            timing_adj = 1.2  # harder raise, later
        else:
            timing_adj = 1.0

        # Forced raise if runway < 9 months
        if 0 < analytics.estimated_runway_months < 9:
            predicted_months = min(analytics.estimated_runway_months - 3, benchmark_next_months * timing_adj)
            predicted_months = max(predicted_months, 1)
        else:
            predicted_months = benchmark_next_months * timing_adj

        analytics.predicted_next_round_months = max(
            predicted_months - analytics.months_since_last_round, 0
        )
        analytics.predicted_next_round_stage = _next_stage(stage_key)
        next_round_info = STAGE_TYPICAL_ROUND.get(analytics.predicted_next_round_stage, {})
        analytics.predicted_next_raise_amount = next_round_info.get("amount", 0)

        # --- Valuation context ---
        reported_valuation = ensure_numeric(
            company.get("valuation") or company.get("current_valuation_usd"), 0
        )
        stage_multiple = benchmarks.get("valuation_multiple", 10)
        analytics.stage_benchmark_multiple = stage_multiple

        if reported_valuation > 0 and analytics.months_since_last_price < 18:
            analytics.implied_current_valuation = reported_valuation
            analytics.fair_value_basis = "recent_transaction"
        elif analytics.current_arr > 0:
            analytics.implied_current_valuation = analytics.current_arr * stage_multiple
            analytics.fair_value_basis = "comps"
        else:
            analytics.implied_current_valuation = benchmarks.get("valuation_median", 0)
            analytics.fair_value_basis = "model"

        analytics.current_revenue_multiple = (
            analytics.implied_current_valuation / analytics.current_arr
            if analytics.current_arr > 0
            else 0
        )

        # Valuation direction
        if analytics.growth_rate > benchmarks.get("growth_rate", 1.0) * 1.1:
            analytics.valuation_direction = "up_round_likely"
        elif analytics.growth_rate < benchmarks.get("growth_rate", 1.0) * 0.6:
            analytics.valuation_direction = "down_round_risk"
        else:
            analytics.valuation_direction = "flat"

        # --- Benchmarks comparison ---
        analytics.vs_benchmark = self._build_benchmark_comparison(analytics, benchmarks)

        # --- Signals ---
        analytics.signals = self._compute_signals(analytics, benchmarks)

        return analytics

    def compute_return_metrics(
        self,
        company: Dict[str, Any],
        fund_investment: Dict[str, Any],
        analytics: Optional[CompanyAnalytics] = None,
    ) -> CompanyReturnMetrics:
        """Compute per-company return metrics.

        ``fund_investment`` must contain:
            amount (float), date (str|datetime), ownership_pct (float 0-100).
        Optionally: additional_tranches: [{amount, date}]

        ``analytics`` is used for current_nav if supplied (avoids re-computation).
        """
        metrics = CompanyReturnMetrics()
        metrics.company_id = str(company.get("id", ""))
        metrics.company_name = str(company.get("name", "Unknown"))

        # Total invested (including follow-on tranches)
        primary = ensure_numeric(fund_investment.get("amount"), 0)
        tranches = fund_investment.get("additional_tranches", []) or []
        follow_on = sum(ensure_numeric(t.get("amount"), 0) for t in tranches)
        metrics.invested = primary + follow_on

        # Ownership
        metrics.ownership_pct = ensure_numeric(fund_investment.get("ownership_pct"), 0)

        # Current NAV
        if analytics and analytics.implied_current_valuation > 0:
            valuation = analytics.implied_current_valuation
        else:
            valuation = ensure_numeric(
                company.get("valuation") or company.get("current_valuation_usd"), 0
            )
        metrics.current_nav = (metrics.ownership_pct / 100) * valuation

        # MOIC
        metrics.moic = metrics.current_nav / metrics.invested if metrics.invested > 0 else 0

        # Unrealized gain
        metrics.unrealized_gain = metrics.current_nav - metrics.invested

        # Cost basis per %
        metrics.cost_basis_per_pct = (
            metrics.invested / metrics.ownership_pct if metrics.ownership_pct > 0 else 0
        )

        # Holding period
        inv_date = fund_investment.get("date")
        if isinstance(inv_date, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    inv_date = datetime.strptime(inv_date.split("+")[0].split("Z")[0], fmt)
                    break
                except ValueError:
                    continue
        if isinstance(inv_date, datetime):
            metrics.holding_period_years = max(
                (datetime.now() - inv_date).days / 365.25, 0.01
            )
        else:
            metrics.holding_period_years = 1.0  # fallback

        # IRR via Newton-Raphson on actual cash flows
        cash_flows: List[Tuple[float, datetime]] = []

        # Primary investment
        primary_date = fund_investment.get("date")
        if isinstance(primary_date, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    primary_date = datetime.strptime(primary_date.split("+")[0].split("Z")[0], fmt)
                    break
                except ValueError:
                    continue
        if isinstance(primary_date, datetime):
            cash_flows.append((-primary, primary_date))
        else:
            # Fallback: assume 2 years ago
            cash_flows.append((-primary, datetime.now() - timedelta(days=730)))

        # Follow-on tranches
        for t in tranches:
            t_amount = ensure_numeric(t.get("amount"), 0)
            t_date = t.get("date")
            if isinstance(t_date, str):
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        t_date = datetime.strptime(t_date.split("+")[0].split("Z")[0], fmt)
                        break
                    except ValueError:
                        continue
            if isinstance(t_date, datetime) and t_amount > 0:
                cash_flows.append((-t_amount, t_date))

        # Terminal value (current NAV as of today)
        cash_flows.append((metrics.current_nav, datetime.now()))

        metrics.irr = _solve_irr(cash_flows)

        return metrics

    # ------------------------------------------------------------------
    # Batch methods for portfolio-level analysis
    # ------------------------------------------------------------------
    def analyze_portfolio(
        self,
        companies: List[Dict[str, Any]],
        fund_investments: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Analyze all companies in a portfolio.

        Args:
            companies: list of company dicts.
            fund_investments: optional map of company_id → investment dict.

        Returns:
            {
                "company_analytics": {company_id: CompanyAnalytics},
                "company_returns": {company_id: CompanyReturnMetrics},
                "fund_summary": {...aggregate metrics...},
            }
        """
        fund_investments = fund_investments or {}
        all_analytics: Dict[str, CompanyAnalytics] = {}
        all_returns: Dict[str, CompanyReturnMetrics] = {}

        for company in companies:
            cid = str(company.get("id", company.get("name", "")))
            inv = fund_investments.get(cid)

            analytics = self.analyze_company(company, inv)
            all_analytics[cid] = analytics

            if inv and ensure_numeric(inv.get("amount"), 0) > 0:
                returns = self.compute_return_metrics(company, inv, analytics)
                all_returns[cid] = returns

        # Fund-level aggregation
        total_invested = sum(r.invested for r in all_returns.values())
        total_nav = sum(r.current_nav for r in all_returns.values())
        total_gain = sum(r.unrealized_gain for r in all_returns.values())
        weighted_irr = 0.0
        if total_invested > 0:
            for r in all_returns.values():
                weighted_irr += r.irr * (r.invested / total_invested)

        fund_summary = {
            "total_invested": total_invested,
            "total_nav": total_nav,
            "total_unrealized_gain": total_gain,
            "portfolio_moic": total_nav / total_invested if total_invested > 0 else 0,
            "weighted_avg_irr": weighted_irr,
            "company_count": len(companies),
            "companies_with_investment": len(all_returns),
        }

        return {
            "company_analytics": all_analytics,
            "company_returns": all_returns,
            "fund_summary": fund_summary,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_benchmark_comparison(
        self, analytics: CompanyAnalytics, benchmarks: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        comparison: Dict[str, Dict[str, Any]] = {}

        bench_arr = benchmarks.get("arr_median", 0)
        if bench_arr > 0:
            comparison["arr"] = {
                "value": analytics.current_arr,
                "benchmark_median": bench_arr,
                "percentile": self._percentile_label(analytics.current_arr, bench_arr),
            }

        bench_growth = benchmarks.get("growth_rate", 0)
        if bench_growth > 0:
            comparison["growth"] = {
                "value": analytics.growth_rate,
                "benchmark_median": bench_growth,
                "percentile": self._percentile_label(analytics.growth_rate, bench_growth),
            }

        bench_burn = benchmarks.get("burn_monthly", 0)
        if bench_burn > 0:
            # For burn, lower is better — invert comparison
            comparison["burn"] = {
                "value": analytics.estimated_monthly_burn,
                "benchmark_median": bench_burn,
                "percentile": self._percentile_label(
                    bench_burn, analytics.estimated_monthly_burn
                ),
            }

        bench_margin = benchmarks.get("gross_margin", 0)
        if bench_margin > 0:
            reported_margin = ensure_numeric(
                analytics.vs_benchmark.get("gross_margin", {}).get("value"), 0
            )
            if reported_margin == 0:
                reported_margin = bench_margin  # use benchmark if unknown
            comparison["gross_margin"] = {
                "value": reported_margin,
                "benchmark_median": bench_margin,
                "percentile": self._percentile_label(reported_margin, bench_margin),
            }

        return comparison

    @staticmethod
    def _percentile_label(value: float, benchmark: float) -> str:
        if benchmark == 0:
            return "unknown"
        ratio = value / benchmark
        if ratio > 1.3:
            return "well_above_median"
        if ratio > 1.1:
            return "above_median"
        if ratio > 0.9:
            return "near_median"
        if ratio > 0.7:
            return "below_median"
        return "well_below_median"

    def _compute_signals(
        self, analytics: CompanyAnalytics, benchmarks: Dict[str, Any]
    ) -> List[str]:
        signals: List[str] = []

        # Growth deceleration
        if analytics.growth_delta < -0.2:
            signals.append(
                f"growth_decelerating_from_{int(analytics.growth_at_entry*100)}pct"
                f"_to_{int(analytics.growth_rate*100)}pct"
            )

        # Runway alerts
        if 0 < analytics.estimated_runway_months < 6:
            signals.append("runway_under_6_months_critical")
        elif 0 < analytics.estimated_runway_months < 12:
            signals.append("runway_under_12_months")

        # Long time since last round
        bench_next = benchmarks.get("next_round_months", 18)
        if analytics.months_since_last_round > bench_next * 1.5:
            signals.append(
                f"{int(analytics.months_since_last_round)}_months_since_last_round"
            )

        # Burn exceeds ARR
        annual_burn = analytics.estimated_monthly_burn * 12
        if analytics.current_arr > 0 and annual_burn > analytics.current_arr * 1.5:
            signals.append("burn_significantly_exceeds_arr")
        elif analytics.current_arr > 0 and annual_burn > analytics.current_arr:
            signals.append("burn_exceeds_arr")

        # ARR below stage minimum
        bench_arr = benchmarks.get("arr_median", 0)
        if analytics.current_arr > 0 and bench_arr > 0 and analytics.current_arr < bench_arr * 0.5:
            signals.append("arr_well_below_stage_benchmark")

        # Valuation step-ups declining
        if analytics.avg_step_up_multiple > 0 and analytics.avg_step_up_multiple < 1.5:
            signals.append("valuation_step_up_declining")

        # Stale pricing
        if analytics.months_since_last_price > 24:
            signals.append("stale_pricing_over_24_months")

        # Down round risk
        if analytics.valuation_direction == "down_round_risk":
            signals.append("down_round_risk")

        return signals
