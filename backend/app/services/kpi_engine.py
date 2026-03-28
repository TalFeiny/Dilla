"""KPI Compute Engine — adaptive, business-type-aware, time-series-native.

Pulls actuals from fpa_actuals, reads the company's business_model/sector,
and computes the right KPI profile with full period-over-period tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class KPIValue:
    """A single KPI for one period."""
    value: Optional[float]
    period: str  # "2025-01"
    formatted: Optional[str] = None  # "$1.2M", "34.5%", "6.2 months"


@dataclass
class KPIResult:
    """A computed KPI with its full time series and change metrics."""
    key: str
    label: str
    description: str
    category: str  # "profitability", "growth", "efficiency", "liquidity", "saas", "services", etc.
    format_type: str  # "currency", "percent", "ratio", "months", "number"
    current: Optional[KPIValue] = None
    series: List[KPIValue] = field(default_factory=list)
    # Period-over-period
    pop_change: Optional[float] = None  # absolute change
    pop_change_pct: Optional[float] = None  # % change
    trend: Optional[str] = None  # "improving", "declining", "stable"
    # Multi-period trend
    periods_improving: int = 0
    periods_declining: int = 0


@dataclass
class KPISnapshot:
    """All KPIs for a company at a point in time."""
    company_id: str
    business_type: str  # resolved profile name
    as_of: str
    periods_available: int
    kpis: List[KPIResult] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)  # categories we needed but didn't have


# ---------------------------------------------------------------------------
# KPI definitions — declarative
# ---------------------------------------------------------------------------

@dataclass
class KPIDef:
    """Declarative KPI definition."""
    key: str
    label: str
    description: str
    category: str
    format_type: str
    requires: List[str]  # actuals categories needed
    compute: Callable  # (actuals_by_cat: dict[str, dict[str, float]]) -> Optional[float]
    higher_is_better: bool = True


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _get(actuals: Dict[str, Dict[str, float]], cat: str, period: str) -> Optional[float]:
    return actuals.get(cat, {}).get(period)


# ---------------------------------------------------------------------------
# Universal KPIs — computed for any business type
# ---------------------------------------------------------------------------

UNIVERSAL_KPIS: List[KPIDef] = [
    KPIDef(
        key="revenue_growth_mom",
        label="Revenue Growth (MoM)",
        description="Month-over-month revenue growth rate",
        category="growth",
        format_type="percent",
        requires=["revenue"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "revenue", p) or 0) - (_get(a, "revenue", pp) or 0),
            _get(a, "revenue", pp) or 0,
        ) if pp else None,
    ),
    KPIDef(
        key="gross_margin",
        label="Gross Margin",
        description="(Revenue - COGS) / Revenue",
        category="profitability",
        format_type="percent",
        requires=["revenue", "cogs"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "revenue", p) or 0) - (_get(a, "cogs", p) or 0),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="ebitda_margin",
        label="EBITDA Margin",
        description="EBITDA / Revenue",
        category="profitability",
        format_type="percent",
        requires=["revenue", "ebitda"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "ebitda", p),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="opex_ratio",
        label="OpEx Ratio",
        description="Operating expenses as % of revenue",
        category="efficiency",
        format_type="percent",
        requires=["revenue", "opex_total"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "opex_total", p),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="net_burn",
        label="Net Burn",
        description="Total expenses minus revenue (positive = burning cash)",
        category="liquidity",
        format_type="currency",
        requires=["revenue"],
        higher_is_better=False,
        compute=lambda a, p, pp: (
            (_get(a, "cogs", p) or 0) + (_get(a, "opex_total", p) or 0) - (_get(a, "revenue", p) or 0)
        ) if (_get(a, "cogs", p) is not None or _get(a, "opex_total", p) is not None) else None,
    ),
    KPIDef(
        key="runway_months",
        label="Runway",
        description="Months of cash remaining at current burn rate",
        category="liquidity",
        format_type="months",
        requires=["cash_balance"],
        higher_is_better=True,
        compute=lambda a, p, pp: (
            _safe_div(
                _get(a, "cash_balance", p),
                max((_get(a, "cogs", p) or 0) + (_get(a, "opex_total", p) or 0) - (_get(a, "revenue", p) or 0), 0.01),
            )
            if (_get(a, "cash_balance", p) is not None
                and ((_get(a, "cogs", p) or 0) + (_get(a, "opex_total", p) or 0) - (_get(a, "revenue", p) or 0)) > 0)
            else None
        ),
    ),
    KPIDef(
        key="cost_per_head",
        label="Cost per Head",
        description="Total expenses / headcount",
        category="efficiency",
        format_type="currency",
        requires=["headcount"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "cogs", p) or 0) + (_get(a, "opex_total", p) or 0),
            _get(a, "headcount", p),
        ) if (_get(a, "cogs", p) is not None or _get(a, "opex_total", p) is not None) else None,
    ),
    KPIDef(
        key="revenue_per_head",
        label="Revenue per Head",
        description="Revenue / headcount",
        category="efficiency",
        format_type="currency",
        requires=["revenue", "headcount"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "revenue", p),
            _get(a, "headcount", p),
        ),
    ),
    KPIDef(
        key="headcount_growth",
        label="Headcount Growth (MoM)",
        description="Month-over-month headcount change",
        category="growth",
        format_type="percent",
        requires=["headcount"],
        higher_is_better=True,  # context-dependent, but default
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "headcount", p) or 0) - (_get(a, "headcount", pp) or 0),
            _get(a, "headcount", pp),
        ) if pp else None,
    ),
    KPIDef(
        key="cash_balance",
        label="Cash Balance",
        description="Current cash position",
        category="liquidity",
        format_type="currency",
        requires=["cash_balance"],
        higher_is_better=True,
        compute=lambda a, p, pp: _get(a, "cash_balance", p),
    ),
]


# ---------------------------------------------------------------------------
# Business-type-specific KPIs
# ---------------------------------------------------------------------------

SAAS_KPIS: List[KPIDef] = [
    KPIDef(
        key="arr_growth_mom",
        label="ARR Growth (MoM)",
        description="Month-over-month ARR growth",
        category="saas",
        format_type="percent",
        requires=["arr"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "arr", p) or 0) - (_get(a, "arr", pp) or 0),
            _get(a, "arr", pp),
        ) if pp else None,
    ),
    KPIDef(
        key="arr",
        label="ARR",
        description="Annual Recurring Revenue",
        category="saas",
        format_type="currency",
        requires=["arr"],
        higher_is_better=True,
        compute=lambda a, p, pp: _get(a, "arr", p),
    ),
    KPIDef(
        key="mrr",
        label="MRR",
        description="Monthly Recurring Revenue",
        category="saas",
        format_type="currency",
        requires=["mrr"],
        higher_is_better=True,
        compute=lambda a, p, pp: _get(a, "mrr", p),
    ),
    KPIDef(
        key="burn_multiple",
        label="Burn Multiple",
        description="Net Burn / Net New ARR — efficiency of growth spend",
        category="saas",
        format_type="ratio",
        requires=["arr"],
        higher_is_better=False,
        compute=lambda a, p, pp: (
            _safe_div(
                (_get(a, "cogs", p) or 0) + (_get(a, "opex_total", p) or 0) - (_get(a, "revenue", p) or 0),
                (_get(a, "arr", p) or 0) - (_get(a, "arr", pp) or 0),
            )
            if pp and ((_get(a, "arr", p) or 0) - (_get(a, "arr", pp) or 0)) > 0
            else None
        ),
    ),
    KPIDef(
        key="rule_of_40",
        label="Rule of 40",
        description="Revenue Growth % + EBITDA Margin %",
        category="saas",
        format_type="percent",
        requires=["revenue", "ebitda"],
        higher_is_better=True,
        compute=lambda a, p, pp: (
            (
                (_safe_div(
                    (_get(a, "revenue", p) or 0) - (_get(a, "revenue", pp) or 0),
                    _get(a, "revenue", pp),
                ) or 0)
                + (_safe_div(_get(a, "ebitda", p), _get(a, "revenue", p)) or 0)
            )
            if pp else None
        ),
    ),
    KPIDef(
        key="nrr_approx",
        label="Net Revenue Retention (approx)",
        description="ARR end-of-period / ARR start-of-period",
        category="saas",
        format_type="percent",
        requires=["arr"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "arr", p),
            _get(a, "arr", pp),
        ) if pp else None,
    ),
    KPIDef(
        key="revenue_per_customer",
        label="Revenue per Customer",
        description="Revenue / number of customers",
        category="saas",
        format_type="currency",
        requires=["revenue", "customers"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "revenue", p),
            _get(a, "customers", p),
        ),
    ),
]

SERVICES_KPIS: List[KPIDef] = [
    KPIDef(
        key="utilization_rate",
        label="Utilization Rate",
        description="Revenue / (headcount × cost_per_head) — proxy for billable utilization",
        category="services",
        format_type="percent",
        requires=["revenue", "headcount"],
        higher_is_better=True,
        compute=lambda a, p, pp: (
            _safe_div(
                _get(a, "revenue", p),
                (_get(a, "headcount", p) or 0) * (
                    _safe_div(
                        (_get(a, "cogs", p) or 0) + (_get(a, "opex_total", p) or 0),
                        _get(a, "headcount", p),
                    ) or 1
                ),
            )
        ) if _get(a, "headcount", p) else None,
    ),
    KPIDef(
        key="revenue_per_employee",
        label="Revenue per Employee",
        description="Total revenue / headcount",
        category="services",
        format_type="currency",
        requires=["revenue", "headcount"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "revenue", p),
            _get(a, "headcount", p),
        ),
    ),
    KPIDef(
        key="gross_profit_per_head",
        label="Gross Profit per Head",
        description="(Revenue - COGS) / headcount",
        category="services",
        format_type="currency",
        requires=["revenue", "cogs", "headcount"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "revenue", p) or 0) - (_get(a, "cogs", p) or 0),
            _get(a, "headcount", p),
        ),
    ),
    KPIDef(
        key="employee_cost_ratio",
        label="Employee Cost Ratio",
        description="Total payroll cost / revenue",
        category="services",
        format_type="percent",
        requires=["revenue", "cogs"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "cogs", p),
            _get(a, "revenue", p),
        ),
    ),
]

ECOMMERCE_KPIS: List[KPIDef] = [
    KPIDef(
        key="revenue_per_customer",
        label="Revenue per Customer (AOV proxy)",
        description="Revenue / customers — proxy for average order value",
        category="ecommerce",
        format_type="currency",
        requires=["revenue", "customers"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "revenue", p),
            _get(a, "customers", p),
        ),
    ),
    KPIDef(
        key="customer_growth",
        label="Customer Growth (MoM)",
        description="Month-over-month customer count change",
        category="ecommerce",
        format_type="percent",
        requires=["customers"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "customers", p) or 0) - (_get(a, "customers", pp) or 0),
            _get(a, "customers", pp),
        ) if pp else None,
    ),
    KPIDef(
        key="cogs_ratio",
        label="COGS Ratio",
        description="Cost of goods sold as % of revenue",
        category="ecommerce",
        format_type="percent",
        requires=["revenue", "cogs"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "cogs", p),
            _get(a, "revenue", p),
        ),
    ),
]

MANUFACTURING_KPIS: List[KPIDef] = [
    KPIDef(
        key="cogs_ratio",
        label="COGS Ratio",
        description="Cost of goods / revenue — production cost efficiency",
        category="manufacturing",
        format_type="percent",
        requires=["revenue", "cogs"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "cogs", p),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="gross_profit",
        label="Gross Profit",
        description="Revenue - COGS",
        category="manufacturing",
        format_type="currency",
        requires=["revenue", "cogs"],
        higher_is_better=True,
        compute=lambda a, p, pp: (
            (_get(a, "revenue", p) or 0) - (_get(a, "cogs", p) or 0)
            if _get(a, "revenue", p) is not None else None
        ),
    ),
    KPIDef(
        key="opex_per_unit_revenue",
        label="OpEx per Unit Revenue",
        description="Operating expenses per dollar of revenue",
        category="manufacturing",
        format_type="ratio",
        requires=["revenue", "opex_total"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "opex_total", p),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="output_per_head",
        label="Output per Head",
        description="Revenue / headcount — labor productivity",
        category="manufacturing",
        format_type="currency",
        requires=["revenue", "headcount"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "revenue", p),
            _get(a, "headcount", p),
        ),
    ),
]


# ---------------------------------------------------------------------------
# PE operating KPIs — leverage, coverage, FCF conversion
# ---------------------------------------------------------------------------

PE_OPERATING_KPIS: List[KPIDef] = [
    KPIDef(
        key="leverage_ratio",
        label="Net Leverage",
        description="Net Debt / LTM EBITDA",
        category="leverage",
        format_type="ratio",
        requires=["ebitda"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "total_debt", p) or 0) - (_get(a, "cash_balance", p) or 0),
            _get(a, "ebitda", p) * 12 if _get(a, "ebitda", p) else None,
        ),
    ),
    KPIDef(
        key="interest_coverage",
        label="Interest Coverage",
        description="LTM EBITDA / LTM Interest Expense",
        category="leverage",
        format_type="ratio",
        requires=["ebitda", "interest_expense"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "ebitda", p),
            _get(a, "interest_expense", p),
        ),
    ),
    KPIDef(
        key="dscr",
        label="Debt Service Coverage",
        description="(EBITDA - CapEx) / Debt Service",
        category="leverage",
        format_type="ratio",
        requires=["ebitda"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "ebitda", p) or 0) - (_get(a, "capex", p) or 0),
            _get(a, "debt_service", p),
        ),
    ),
    KPIDef(
        key="fcf_conversion",
        label="FCF Conversion",
        description="FCF / EBITDA",
        category="profitability",
        format_type="percent",
        requires=["ebitda", "fcf"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "fcf", p),
            _get(a, "ebitda", p),
        ),
    ),
    KPIDef(
        key="capex_ratio",
        label="CapEx Ratio",
        description="CapEx / Revenue",
        category="efficiency",
        format_type="percent",
        requires=["revenue", "capex"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "capex", p),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="nwc_days",
        label="Net Working Capital Days",
        description="Working Capital / Revenue × 30",
        category="efficiency",
        format_type="number",
        requires=["revenue"],
        higher_is_better=False,
        compute=lambda a, p, pp: (
            _safe_div(_get(a, "working_capital", p), _get(a, "revenue", p)) * 30
            if _get(a, "revenue", p) and _get(a, "working_capital", p) is not None
            else None
        ),
    ),
    KPIDef(
        key="operating_margin",
        label="Operating Margin",
        description="Operating Income / Revenue",
        category="profitability",
        format_type="percent",
        requires=["revenue", "operating_income"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "operating_income", p),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="net_margin",
        label="Net Margin",
        description="Net Income / Revenue",
        category="profitability",
        format_type="percent",
        requires=["revenue", "net_income"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "net_income", p),
            _get(a, "revenue", p),
        ),
    ),
]


# ---------------------------------------------------------------------------
# Insurance vertical KPIs
# ---------------------------------------------------------------------------

INSURANCE_KPIS: List[KPIDef] = [
    KPIDef(
        key="loss_ratio",
        label="Loss Ratio",
        description="Claims / Earned Premiums",
        category="insurance",
        format_type="percent",
        requires=["revenue", "cogs"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "cogs", p),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="combined_ratio",
        label="Combined Ratio",
        description="(Claims + OpEx) / Earned Premiums — below 100% = underwriting profit",
        category="insurance",
        format_type="percent",
        requires=["revenue", "cogs", "opex_total"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            (_get(a, "cogs", p) or 0) + (_get(a, "opex_total", p) or 0),
            _get(a, "revenue", p),
        ),
    ),
    KPIDef(
        key="revenue_per_policy",
        label="Revenue per Policy",
        description="Premium income / number of policies (uses customer_count as proxy)",
        category="insurance",
        format_type="currency",
        requires=["revenue", "customers"],
        higher_is_better=True,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "revenue", p),
            _get(a, "customers", p),
        ),
    ),
    KPIDef(
        key="expense_ratio",
        label="Expense Ratio",
        description="Operating expenses / Earned Premiums",
        category="insurance",
        format_type="percent",
        requires=["revenue", "opex_total"],
        higher_is_better=False,
        compute=lambda a, p, pp: _safe_div(
            _get(a, "opex_total", p),
            _get(a, "revenue", p),
        ),
    ),
]


# ---------------------------------------------------------------------------
# Profile registry — maps business_model / sector to KPI list
# ---------------------------------------------------------------------------

KPI_PROFILES: Dict[str, List[KPIDef]] = {
    "saas": SAAS_KPIS,
    "subscription": SAAS_KPIS,
    "services": SERVICES_KPIS,
    "consulting": SERVICES_KPIS,
    "agency": SERVICES_KPIS,
    "professional_services": SERVICES_KPIS,
    "ecommerce": ECOMMERCE_KPIS,
    "marketplace": ECOMMERCE_KPIS,
    "d2c": ECOMMERCE_KPIS,
    "manufacturing": MANUFACTURING_KPIS,
    "hardware": MANUFACTURING_KPIS,
    "industrial": MANUFACTURING_KPIS,
    # Insurance verticals (company business types, not fund types)
    "insurance": INSURANCE_KPIS,
    "insurance_brokerage": INSURANCE_KPIS,
    "brokerage": INSURANCE_KPIS,
    "underwriting": INSURANCE_KPIS,
}


def _resolve_profile(
    business_model: Optional[str],
    sector: Optional[str],
    fund_type: Optional[str] = None,
) -> Tuple[str, List[KPIDef]]:
    """Resolve which KPI profile to use. Returns (profile_name, extra_kpis).

    When the company sits in a PE/growth fund, PE_OPERATING_KPIS (leverage,
    coverage, FCF conversion) are merged as a baseline on top of whatever
    vertical profile matches the company's actual business type.
    """
    is_pe_fund = fund_type in ("private_equity", "growth")

    # Match on company's actual business model / sector
    for candidate in [business_model, sector]:
        if candidate:
            key = candidate.lower().strip().replace(" ", "_").replace("-", "_")
            if key in KPI_PROFILES:
                profile_kpis = KPI_PROFILES[key]
                if is_pe_fund:
                    # Merge PE operating baseline with vertical-specific KPIs
                    pe_keys = {k.key for k in PE_OPERATING_KPIS}
                    merged = list(PE_OPERATING_KPIS) + [k for k in profile_kpis if k.key not in pe_keys]
                    return key, merged
                return key, profile_kpis

    # No vertical match — PE fund companies still get PE operating KPIs
    if is_pe_fund:
        return "pe_operating", PE_OPERATING_KPIS

    return "universal", []


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_value(value: Optional[float], fmt: str) -> Optional[str]:
    if value is None:
        return None
    if fmt == "percent":
        return f"{value * 100:.1f}%"
    if fmt == "currency":
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1_000_000_000:
            return f"{sign}${abs_v / 1_000_000_000:.1f}B"
        if abs_v >= 1_000_000:
            return f"{sign}${abs_v / 1_000_000:.1f}M"
        if abs_v >= 1_000:
            return f"{sign}${abs_v / 1_000:.1f}K"
        return f"{sign}${abs_v:,.0f}"
    if fmt == "months":
        return f"{value:.1f} months"
    if fmt == "ratio":
        return f"{value:.2f}x"
    if fmt == "number":
        return f"{value:,.0f}"
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Time series helpers
# ---------------------------------------------------------------------------

def _prev_period(period: str, all_periods: List[str]) -> Optional[str]:
    """Get the previous period in the sorted list."""
    try:
        idx = all_periods.index(period)
        return all_periods[idx - 1] if idx > 0 else None
    except ValueError:
        return None


def _compute_trend(series: List[KPIValue], higher_is_better: bool) -> Tuple[Optional[str], int, int]:
    """Determine trend from a series of KPI values."""
    values = [v.value for v in series if v.value is not None]
    if len(values) < 2:
        return None, 0, 0

    improving = 0
    declining = 0
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        if higher_is_better:
            if diff > 0:
                improving += 1
            elif diff < 0:
                declining += 1
        else:
            if diff < 0:
                improving += 1
            elif diff > 0:
                declining += 1

    if improving > declining:
        trend = "improving"
    elif declining > improving:
        trend = "declining"
    else:
        trend = "stable"
    return trend, improving, declining


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class KPIEngine:
    """Compute KPIs from fpa_actuals, adapting to business type."""

    def compute(
        self,
        company_id: str,
        as_of: Optional[str] = None,
        periods: int = 12,
    ) -> KPISnapshot:
        """Compute all applicable KPIs with full time series.

        Args:
            company_id: Company UUID.
            as_of: Optional end period ("2025-06"). Defaults to latest available.
            periods: Number of trailing periods to include in series.
        """
        # 1. Fetch company metadata for profile resolution
        business_model, sector, fund_type = self._get_company_type(company_id)
        profile_name, extra_kpis = _resolve_profile(business_model, sector, fund_type)

        # 2. Fetch all actuals
        actuals_by_cat = self._fetch_actuals(company_id)
        if not actuals_by_cat:
            return KPISnapshot(
                company_id=company_id,
                business_type=profile_name,
                as_of=as_of or "unknown",
                periods_available=0,
                missing_data=["No actuals data found"],
            )

        # 3. Build sorted period list
        all_periods: set = set()
        for cat_data in actuals_by_cat.values():
            all_periods.update(cat_data.keys())
        sorted_periods = sorted(all_periods)

        if as_of:
            sorted_periods = [p for p in sorted_periods if p <= as_of]
        if not sorted_periods:
            return KPISnapshot(
                company_id=company_id,
                business_type=profile_name,
                as_of=as_of or "unknown",
                periods_available=0,
                missing_data=["No periods in range"],
            )

        # Limit to trailing N periods
        display_periods = sorted_periods[-periods:]

        # 4. Determine available categories
        available_cats = set(actuals_by_cat.keys())

        # 5. Compute KPIs — universal + profile-specific
        all_defs = UNIVERSAL_KPIS + extra_kpis
        results: List[KPIResult] = []
        missing: List[str] = []

        for kpi_def in all_defs:
            # Check if we have the required data
            missing_reqs = [r for r in kpi_def.requires if r not in available_cats]
            if missing_reqs:
                missing.extend(missing_reqs)
                continue

            # Compute for each period
            series: List[KPIValue] = []
            for period in display_periods:
                prev = _prev_period(period, sorted_periods)
                value = kpi_def.compute(actuals_by_cat, period, prev)
                series.append(KPIValue(
                    value=value,
                    period=period,
                    formatted=_format_value(value, kpi_def.format_type),
                ))

            # Period-over-period change (last two non-null values)
            non_null = [v for v in series if v.value is not None]
            pop_change = None
            pop_change_pct = None
            if len(non_null) >= 2:
                curr_val = non_null[-1].value
                prev_val = non_null[-2].value
                pop_change = curr_val - prev_val
                if prev_val and prev_val != 0:
                    pop_change_pct = pop_change / abs(prev_val)

            trend, improving, declining = _compute_trend(series, kpi_def.higher_is_better)

            results.append(KPIResult(
                key=kpi_def.key,
                label=kpi_def.label,
                description=kpi_def.description,
                category=kpi_def.category,
                format_type=kpi_def.format_type,
                current=non_null[-1] if non_null else None,
                series=series,
                pop_change=pop_change,
                pop_change_pct=pop_change_pct,
                trend=trend,
                periods_improving=improving,
                periods_declining=declining,
            ))

        return KPISnapshot(
            company_id=company_id,
            business_type=profile_name,
            as_of=display_periods[-1],
            periods_available=len(display_periods),
            kpis=results,
            missing_data=sorted(set(missing)),
        )

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def _get_company_type(self, company_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Fetch business_model, sector, and fund_type for a company."""
        try:
            from app.core.supabase_client import get_supabase_client

            sb = get_supabase_client()
            if not sb:
                return None, None, None
            result = (
                sb.table("companies")
                .select("revenue_model, sector, fund_id")
                .eq("id", company_id)
                .limit(1)
                .execute()
            )
            if result.data:
                row = result.data[0]
                fund_type = None
                fund_id = row.get("fund_id")
                if fund_id:
                    fund_result = (
                        sb.table("funds")
                        .select("fund_type")
                        .eq("id", fund_id)
                        .limit(1)
                        .execute()
                    )
                    if fund_result.data:
                        fund_type = fund_result.data[0].get("fund_type")
                return row.get("revenue_model"), row.get("sector"), fund_type
        except Exception as e:
            logger.warning(f"[KPI] Failed to fetch company type: {e}")
        return None, None, None

    def _fetch_actuals(self, company_id: str) -> Dict[str, Dict[str, float]]:
        """Fetch all actuals as {category: {period: amount}}."""
        try:
            from app.services.company_data_pull import pull_company_data
            return pull_company_data(company_id).time_series
        except Exception as e:
            logger.warning(f"[KPI] Failed to fetch actuals: {e}")
            return {}


# ---------------------------------------------------------------------------
# Serialization — for tool output
# ---------------------------------------------------------------------------

def snapshot_to_dict(snap: KPISnapshot) -> Dict[str, Any]:
    """Convert KPISnapshot to JSON-serializable dict for agent consumption."""
    kpis = []
    for k in snap.kpis:
        kpi_dict: Dict[str, Any] = {
            "key": k.key,
            "label": k.label,
            "description": k.description,
            "category": k.category,
            "format_type": k.format_type,
            "trend": k.trend,
            "periods_improving": k.periods_improving,
            "periods_declining": k.periods_declining,
        }
        if k.current:
            kpi_dict["current"] = {
                "value": k.current.value,
                "period": k.current.period,
                "formatted": k.current.formatted,
            }
        if k.pop_change is not None:
            kpi_dict["pop_change"] = round(k.pop_change, 4)
        if k.pop_change_pct is not None:
            kpi_dict["pop_change_pct"] = round(k.pop_change_pct, 4)
            kpi_dict["pop_change_pct_formatted"] = f"{k.pop_change_pct * 100:+.1f}%"
        if k.series:
            kpi_dict["series"] = [
                {"period": v.period, "value": v.value, "formatted": v.formatted}
                for v in k.series
            ]
        kpis.append(kpi_dict)

    return {
        "company_id": snap.company_id,
        "business_type": snap.business_type,
        "as_of": snap.as_of,
        "periods_available": snap.periods_available,
        "kpis": kpis,
        "missing_data": snap.missing_data,
    }
