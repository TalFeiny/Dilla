"""
Driver Registry
Static definition of all drivers that feed the projection engine.

28 core drivers + 15 subcategory drivers (active only when department-level data exists).

Each driver maps to an existing branch assumption key and carries metadata
for the agent (nl_hint, range, ripple chain) and the UI (label, unit, level).

Not stored in DB — versioned with code.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional, Tuple


DriverLevel = Literal["revenue", "opex", "workforce", "capital", "unit_economics"]
DriverHow = Literal["set", "shift", "scale", "computed", "list"]
DriverUnit = Literal["%", "$", "headcount", "months", "days", "multiplier", "ratio"]


@dataclass(frozen=True)
class DriverDef:
    id: str
    label: str
    level: DriverLevel
    unit: DriverUnit
    how: DriverHow
    assumption_key: str
    ripple: List[str]
    nl_hint: str
    scope: str = "company"
    range: Optional[Tuple[float, float]] = None
    computed: bool = False


# ---------------------------------------------------------------------------
# Full registry — 28 drivers
# ---------------------------------------------------------------------------

_DRIVERS: Dict[str, DriverDef] = {}


def _r(d: DriverDef) -> DriverDef:
    _DRIVERS[d.id] = d
    return d


# ── Revenue Level ──────────────────────────────────────────────────────────

_r(DriverDef(
    id="revenue_growth",
    label="Revenue Growth Rate",
    level="revenue", unit="%", how="set",
    assumption_key="revenue_growth_override",
    ripple=["gross_profit", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Annual revenue growth rate as decimal (0.50 = 50%)",
    range=(-1.0, 10.0),
))

_r(DriverDef(
    id="revenue_override",
    label="Revenue (absolute)",
    level="revenue", unit="$", how="set",
    assumption_key="revenue_override",
    ripple=["gross_profit", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Override annual revenue to an absolute dollar amount",
    range=(0, 1e12),
))

_r(DriverDef(
    id="gross_margin",
    label="Gross Margin",
    level="revenue", unit="%", how="set",
    assumption_key="gross_margin_override",
    ripple=["gross_profit", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Gross margin as decimal (0.70 = 70%)",
    range=(0.0, 1.0),
))

_r(DriverDef(
    id="churn_rate",
    label="Customer Churn Rate",
    level="revenue", unit="%", how="set",
    assumption_key="churn_rate",
    ripple=["net_revenue", "gross_profit", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Monthly customer churn rate as decimal (0.05 = 5%/mo)",
    range=(0.0, 1.0),
))

_r(DriverDef(
    id="nrr",
    label="Net Revenue Retention",
    level="revenue", unit="%", how="set",
    assumption_key="nrr",
    ripple=["net_revenue", "gross_profit", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Net revenue retention as decimal (1.20 = 120% NRR)",
    range=(0.5, 2.0),
))

_r(DriverDef(
    id="pricing_change",
    label="Pricing Change",
    level="revenue", unit="%", how="scale",
    assumption_key="pricing_pct_change",
    ripple=["revenue", "gross_profit", "ebitda", "cash_balance"],
    nl_hint="Percentage pricing change applied to existing revenue (0.10 = +10%)",
    range=(-0.5, 1.0),
))

_r(DriverDef(
    id="new_customer_growth",
    label="New Customer Growth",
    level="revenue", unit="%", how="set",
    assumption_key="new_customer_growth_rate",
    ripple=["revenue", "gross_profit", "ebitda", "cash_balance"],
    nl_hint="Monthly new-customer growth rate as decimal",
    range=(0.0, 5.0),
))

_r(DriverDef(
    id="avg_contract_value",
    label="Average Contract Value",
    level="revenue", unit="$", how="set",
    assumption_key="acv_override",
    ripple=["revenue", "gross_profit", "ebitda", "cash_balance"],
    nl_hint="Average annual contract value in dollars",
    range=(0, 10_000_000),
))

_r(DriverDef(
    id="growth_by_month",
    label="Per-Month Growth Overrides",
    level="revenue", unit="%", how="set",
    assumption_key="growth_overrides_by_month",
    ripple=["revenue"],
    nl_hint="Dict of YYYY-MM → annual growth rate override for that month",
))

# ── OpEx Level ─────────────────────────────────────────────────────────────

_r(DriverDef(
    id="rd_pct",
    label="R&D Spend",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.rd_pct_delta",
    ripple=["total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="R&D spending change as decimal (-0.30 = cut 30%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="sm_pct",
    label="Sales & Marketing Spend",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.sm_pct_delta",
    ripple=["total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="S&M spending change as decimal (-0.30 = cut 30%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="ga_pct",
    label="G&A Spend",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.ga_pct_delta",
    ripple=["total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="G&A spending change as decimal (-0.30 = cut 30%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="cac",
    label="Customer Acquisition Cost",
    level="opex", unit="$", how="set",
    assumption_key="cac_override",
    ripple=["sm_spend", "total_opex", "ebitda", "cash_balance"],
    nl_hint="Cost to acquire one new customer in dollars",
    range=(0, 1_000_000),
))

_r(DriverDef(
    id="sales_cycle",
    label="Sales Cycle Length",
    level="opex", unit="months", how="set",
    assumption_key="sales_cycle_months",
    ripple=["revenue_timing", "cash_timing"],
    nl_hint="Average months from lead to closed deal",
    range=(0, 36),
))

# ── Workforce Level ────────────────────────────────────────────────────────

_r(DriverDef(
    id="headcount_change",
    label="Headcount Change",
    level="workforce", unit="headcount", how="shift",
    assumption_key="headcount_change",
    ripple=["burn_rate", "total_opex", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Net change in headcount (+5 = hire 5, -3 = cut 3)",
    range=(-500, 500),
))

_r(DriverDef(
    id="payroll_cost_per_head",
    label="Fully Loaded Cost/Head",
    level="workforce", unit="$", how="set",
    assumption_key="cost_per_head",
    ripple=["burn_rate", "total_opex", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Monthly fully-loaded cost per employee in dollars (default $15,000)",
    range=(1_000, 100_000),
))

_r(DriverDef(
    id="hiring_plan",
    label="Net New Hires/Period",
    level="workforce", unit="headcount", how="shift",
    assumption_key="hiring_plan_monthly",
    ripple=["burn_rate", "total_opex", "ebitda", "cash_balance", "runway_months"],
    nl_hint="Number of new hires per month (time-distributed headcount additions)",
    range=(0, 100),
))

# ── Capital Level ──────────────────────────────────────────────────────────

_r(DriverDef(
    id="funding_injection",
    label="Funding Injection",
    level="capital", unit="$", how="shift",
    assumption_key="funding_injection",
    ripple=["cash_balance", "runway_months", "dilution", "ownership", "bs_cash", "bs_share_capital", "bs_apic"],
    nl_hint="One-time cash injection in dollars (e.g. fundraise amount)",
    range=(0, 1e12),
))

_r(DriverDef(
    id="burn_rate",
    label="Monthly Burn Rate",
    level="capital", unit="$", how="set",
    assumption_key="burn_rate_override",
    ripple=["cash_balance", "runway_months"],
    nl_hint="Monthly burn rate override in dollars. Also supports delta and pct_change.",
))

_r(DriverDef(
    id="cash_override",
    label="Cash Balance",
    level="capital", unit="$", how="set",
    assumption_key="cash_override",
    ripple=["runway_months"],
    nl_hint="Override current cash balance to an absolute dollar amount",
    range=(0, 1e12),
))

_r(DriverDef(
    id="capex",
    label="Capital Expenditure",
    level="capital", unit="$", how="set",
    assumption_key="capex_override",
    ripple=["free_cash_flow", "cash_balance", "runway_months", "bs_ppe", "bs_cash"],
    nl_hint="Monthly capital expenditure in absolute dollars",
    range=(0, 100_000_000),
))

_r(DriverDef(
    id="debt_service",
    label="Debt Service / Loan Payments",
    level="capital", unit="$", how="set",
    assumption_key="debt_service_monthly",
    ripple=["free_cash_flow", "cash_balance", "runway_months", "bs_lt_debt", "bs_cash", "net_debt"],
    nl_hint="Monthly debt/loan principal payment in dollars",
    range=(0, 100_000_000),
))

_r(DriverDef(
    id="interest_rate",
    label="Interest Rate on Debt",
    level="capital", unit="%", how="set",
    assumption_key="interest_rate",
    ripple=["debt_service", "free_cash_flow", "cash_balance", "bs_interest_payable"],
    nl_hint="Annual interest rate on outstanding debt as decimal (0.08 = 8%)",
    range=(0.0, 1.0),
))

_r(DriverDef(
    id="tax_rate",
    label="Effective Tax Rate",
    level="capital", unit="%", how="set",
    assumption_key="tax_rate",
    ripple=["net_income", "cash_balance"],
    nl_hint="Effective tax rate as decimal (0.25 = 25%)",
    range=(0.0, 0.6),
))

_r(DriverDef(
    id="working_capital_days",
    label="Working Capital Cycle",
    level="capital", unit="days", how="set",
    assumption_key="working_capital_days",
    ripple=["cash_timing", "bs_receivables", "bs_payables", "bs_inventory", "working_capital", "bs_cash"],
    nl_hint="Net working capital cycle in days (positive = cash tied up)",
    range=(-180, 365),
))

_r(DriverDef(
    id="one_time_costs",
    label="One-Time Costs",
    level="capital", unit="$", how="list",
    assumption_key="one_time_costs",
    ripple=["ebitda", "cash_balance", "runway_months"],
    nl_hint="List of {period: 'YYYY-MM', amount: $, label: str} one-time cost events",
))

# ── Balance Sheet Drivers ─────────────────────────────────────────────────

_r(DriverDef(
    id="dso_days",
    label="Days Sales Outstanding",
    level="capital", unit="days", how="set",
    assumption_key="dso_days",
    ripple=["bs_receivables", "working_capital", "bs_cash"],
    nl_hint="Days sales outstanding — drives accounts receivable (45 = 1.5 months of revenue in AR)",
    range=(0, 180),
))

_r(DriverDef(
    id="dpo_days",
    label="Days Payable Outstanding",
    level="capital", unit="days", how="set",
    assumption_key="dpo_days",
    ripple=["bs_payables", "working_capital", "bs_cash"],
    nl_hint="Days payable outstanding — drives accounts payable (30 = 1 month of COGS in AP)",
    range=(0, 180),
))

_r(DriverDef(
    id="dio_days",
    label="Days Inventory Outstanding",
    level="capital", unit="days", how="set",
    assumption_key="dio_days",
    ripple=["bs_inventory", "working_capital", "bs_cash"],
    nl_hint="Days inventory outstanding — drives inventory balance. 0 for services/SaaS.",
    range=(0, 365),
))

_r(DriverDef(
    id="debt_drawdown",
    label="Debt Drawdown / New Borrowing",
    level="capital", unit="$", how="shift",
    assumption_key="debt_drawdown",
    ripple=["bs_lt_debt", "bs_cash", "cash_balance", "net_debt"],
    nl_hint="New debt drawn in dollars (e.g. term loan, venture debt)",
    range=(0, 1e12),
))

_r(DriverDef(
    id="deferred_revenue_change",
    label="Deferred Revenue Change",
    level="revenue", unit="$", how="shift",
    assumption_key="deferred_revenue_delta",
    ripple=["bs_deferred_revenue", "revenue", "bs_cash"],
    nl_hint="Monthly change in deferred revenue (positive = more prepaid contracts)",
    range=(-100_000_000, 100_000_000),
))

_r(DriverDef(
    id="depreciation_monthly",
    label="Monthly Depreciation",
    level="capital", unit="$", how="set",
    assumption_key="depreciation_monthly",
    ripple=["bs_ppe", "ebitda", "free_cash_flow"],
    nl_hint="Monthly depreciation amount in dollars (reduces PP&E)",
    range=(0, 10_000_000),
))

# ── OpEx Subcategory Level (active only when subcategory data exists) ──────
# These let scenario branches override at department granularity:
# "Cut cloud spend by 30%" instead of just "Cut R&D by 20%"

# R&D subcategories
_r(DriverDef(
    id="opex_rd_engineering",
    label="R&D: Engineering Salaries",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.rd_engineering_salaries_delta",
    ripple=["rd_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Engineering salary spend change as decimal (-0.20 = cut 20%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_rd_infra",
    label="R&D: Cloud / Infra",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.rd_infra_cloud_delta",
    ripple=["rd_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Cloud/infra spend change as decimal (-0.30 = cut 30%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_rd_tools",
    label="R&D: Tools & Licenses",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.rd_tools_licenses_delta",
    ripple=["rd_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Tools/licenses spend change as decimal (-0.50 = cut 50%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_rd_contractor",
    label="R&D: Contractors",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.rd_contractor_delta",
    ripple=["rd_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Contractor spend change as decimal (-1.0 = eliminate contractors)",
    range=(-1.0, 2.0),
))

# Sales & Marketing subcategories
_r(DriverDef(
    id="opex_sm_paid",
    label="S&M: Paid Acquisition",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.sm_paid_acquisition_delta",
    ripple=["sm_spend", "cac", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Paid acquisition spend change as decimal (-0.40 = cut 40%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_sm_content",
    label="S&M: Content Marketing",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.sm_content_marketing_delta",
    ripple=["sm_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Content marketing spend change as decimal",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_sm_sales_salaries",
    label="S&M: Sales Salaries",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.sm_sales_salaries_delta",
    ripple=["sm_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Sales team salary spend change as decimal",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_sm_events",
    label="S&M: Events",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.sm_events_delta",
    ripple=["sm_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Events spend change as decimal (-1.0 = cancel all events)",
    range=(-1.0, 2.0),
))

# G&A subcategories
_r(DriverDef(
    id="opex_ga_finance_legal",
    label="G&A: Finance & Legal",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.ga_finance_legal_delta",
    ripple=["ga_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Finance/legal spend change as decimal",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_ga_office",
    label="G&A: Office",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.ga_office_delta",
    ripple=["ga_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Office spend change as decimal (-1.0 = go fully remote)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="opex_ga_admin_salaries",
    label="G&A: Admin Salaries",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.ga_admin_salaries_delta",
    ripple=["ga_spend", "total_opex", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Admin salary spend change as decimal",
    range=(-1.0, 2.0),
))

# COGS subcategories
_r(DriverDef(
    id="cogs_hosting",
    label="COGS: Hosting",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.cogs_hosting_delta",
    ripple=["cogs", "gross_profit", "gross_margin", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Hosting cost change as decimal (-0.25 = cut hosting 25%)",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="cogs_support",
    label="COGS: Support Salaries",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.cogs_support_salaries_delta",
    ripple=["cogs", "gross_profit", "gross_margin", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Support team salary change as decimal",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="cogs_payment_processing",
    label="COGS: Payment Processing",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.cogs_payment_processing_delta",
    ripple=["cogs", "gross_profit", "gross_margin", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Payment processing cost change as decimal",
    range=(-1.0, 2.0),
))

_r(DriverDef(
    id="cogs_third_party_apis",
    label="COGS: Third-Party APIs",
    level="opex", unit="%", how="scale",
    assumption_key="opex_adjustments.cogs_third_party_apis_delta",
    ripple=["cogs", "gross_profit", "gross_margin", "ebitda", "free_cash_flow", "cash_balance", "runway_months"],
    nl_hint="Third-party API cost change as decimal",
    range=(-1.0, 2.0),
))


# ── Unit Economics Level (computed, read-only) ─────────────────────────────

_r(DriverDef(
    id="ltv",
    label="Customer Lifetime Value",
    level="unit_economics", unit="$", how="computed",
    assumption_key="",
    ripple=[],
    nl_hint="Computed: ACV * gross_margin / churn_rate. Read-only output.",
    computed=True,
))

_r(DriverDef(
    id="ltv_cac_ratio",
    label="LTV/CAC Ratio",
    level="unit_economics", unit="ratio", how="computed",
    assumption_key="",
    ripple=[],
    nl_hint="Computed: LTV / CAC. Read-only output. Healthy > 3x.",
    computed=True,
))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_driver(driver_id: str) -> Optional[DriverDef]:
    return _DRIVERS.get(driver_id)


def get_all_drivers() -> Dict[str, DriverDef]:
    return dict(_DRIVERS)


def get_drivers_by_level(level: DriverLevel) -> Dict[str, DriverDef]:
    return {k: v for k, v in _DRIVERS.items() if v.level == level}


def get_registry_schema() -> List[Dict[str, Any]]:
    """Full registry as JSON-serializable list for API responses."""
    out = []
    for d in _DRIVERS.values():
        entry = asdict(d)
        entry["range"] = list(d.range) if d.range else None
        out.append(entry)
    return out


# Subcategory driver IDs — used to filter which drivers are active
_SUBCATEGORY_DRIVER_IDS = {
    # R&D
    "opex_rd_engineering", "opex_rd_infra", "opex_rd_tools", "opex_rd_contractor",
    # S&M
    "opex_sm_paid", "opex_sm_content", "opex_sm_sales_salaries", "opex_sm_events",
    # G&A
    "opex_ga_finance_legal", "opex_ga_office", "opex_ga_admin_salaries",
    # COGS
    "cogs_hosting", "cogs_support", "cogs_payment_processing", "cogs_third_party_apis",
}

# Map subcategory driver → parent aggregate driver
_SUBCATEGORY_TO_PARENT_DRIVER = {
    "opex_rd_engineering": "rd_pct", "opex_rd_infra": "rd_pct",
    "opex_rd_tools": "rd_pct", "opex_rd_contractor": "rd_pct",
    "opex_sm_paid": "sm_pct", "opex_sm_content": "sm_pct",
    "opex_sm_sales_salaries": "sm_pct", "opex_sm_events": "sm_pct",
    "opex_ga_finance_legal": "ga_pct", "opex_ga_office": "ga_pct",
    "opex_ga_admin_salaries": "ga_pct",
    "cogs_hosting": "gross_margin", "cogs_support": "gross_margin",
    "cogs_payment_processing": "gross_margin", "cogs_third_party_apis": "gross_margin",
}


def get_active_subcategory_drivers(
    available_subcategories: Optional[List[str]] = None,
) -> Dict[str, DriverDef]:
    """Return only subcategory drivers for which data actually exists.

    If *available_subcategories* is None, returns ALL subcategory drivers
    (useful when caller doesn't know what data exists yet).

    Called by the orchestrator/agent to decide which fine-grained cost
    levers to offer the user.
    """
    if available_subcategories is None:
        return {k: v for k, v in _DRIVERS.items() if k in _SUBCATEGORY_DRIVER_IDS}

    # Map actuals subcategory names → driver IDs
    from app.services.actuals_ingestion import SUBCATEGORY_TO_PARENT

    active: Dict[str, DriverDef] = {}
    for sub_name in available_subcategories:
        if sub_name not in SUBCATEGORY_TO_PARENT:
            continue
        # Convention: driver ID is "{parent_prefix}_{subcategory_name}"
        # e.g., subcategory "engineering_salaries" in parent "opex_rd" → "opex_rd_engineering"
        # Match by checking if any registered subcategory driver's assumption_key
        # contains this subcategory name.
        for did in _SUBCATEGORY_DRIVER_IDS:
            d = _DRIVERS.get(did)
            if d and sub_name in d.assumption_key:
                active[did] = d

    return active


def get_parent_driver_for_subcategory(driver_id: str) -> Optional[str]:
    """Return the aggregate parent driver ID for a subcategory driver."""
    return _SUBCATEGORY_TO_PARENT_DRIVER.get(driver_id)


def is_subcategory_driver(driver_id: str) -> bool:
    """Check if a driver is a subcategory-level driver."""
    return driver_id in _SUBCATEGORY_DRIVER_IDS


# ---------------------------------------------------------------------------
# Conversion: driver values <-> branch assumption dicts
# ---------------------------------------------------------------------------

def driver_to_assumption(driver_id: str, value: Any) -> Dict[str, Any]:
    """
    Convert a single driver + value into the assumption dict shape
    that ScenarioBranchService expects.

    Handles dot-notation keys (opex_adjustments.rd_pct_delta) and
    special cases like burn_rate (which supports override/delta/pct_change).
    """
    d = _DRIVERS.get(driver_id)
    if not d or d.computed:
        return {}

    key = d.assumption_key
    if not key:
        return {}

    # Dot-notation: "opex_adjustments.rd_pct_delta" → nested dict
    if "." in key:
        parts = key.split(".", 1)
        return {parts[0]: {parts[1]: value}}

    return {key: value}


def drivers_to_assumptions(drivers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a dict of {driver_id: value} into a merged assumption dict.
    Handles nested opex_adjustments merging.
    """
    merged: Dict[str, Any] = {}

    for driver_id, value in drivers.items():
        single = driver_to_assumption(driver_id, value)
        for k, v in single.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k].update(v)
            else:
                merged[k] = v

    return merged


def assumptions_to_drivers(assumptions: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Reverse: given a branch assumptions dict, return driver-format entries
    with metadata for each recognized key.

    Returns {driver_id: {**driver_metadata, "value": <the value>}}.
    """
    # Build reverse lookup: assumption_key → driver_id
    reverse: Dict[str, str] = {}
    for d in _DRIVERS.values():
        if d.assumption_key and not d.computed:
            reverse[d.assumption_key] = d.id

    result: Dict[str, Dict[str, Any]] = {}

    for key, value in assumptions.items():
        # Check flat keys first
        if key in reverse:
            did = reverse[key]
            d = _DRIVERS[did]
            result[did] = {
                "id": d.id,
                "label": d.label,
                "level": d.level,
                "unit": d.unit,
                "how": d.how,
                "value": value,
            }
        # Check nested keys (opex_adjustments)
        elif isinstance(value, dict):
            for sub_key, sub_val in value.items():
                full_key = f"{key}.{sub_key}"
                if full_key in reverse:
                    did = reverse[full_key]
                    d = _DRIVERS[did]
                    result[did] = {
                        "id": d.id,
                        "label": d.label,
                        "level": d.level,
                        "unit": d.unit,
                        "how": d.how,
                        "value": sub_val,
                    }

    return result


# ---------------------------------------------------------------------------
# Macro → Micro bridge: world model impact factors → driver IDs
# ---------------------------------------------------------------------------

# Maps NL world model factor names to the micro drivers they affect.
# Each entry: (driver_id, direction_multiplier)
#   direction_multiplier > 0 means the macro event pushes the driver UP
#   direction_multiplier < 0 means the macro event pushes it DOWN

MACRO_TO_MICRO: Dict[str, List[Tuple[str, float]]] = {
    "growth_rate":          [("revenue_growth", 1.0)],
    "revenue":              [("revenue_growth", 0.5), ("new_customer_growth", 0.3)],
    "revenue_projection":   [("revenue_growth", 0.7)],
    "burn_rate":            [("burn_rate", 1.0)],
    "runway":               [("burn_rate", -0.5), ("cash_override", 0.3)],
    "valuation":            [],  # valuation is an output, not a driver
    "competitive_position": [("pricing_change", 0.1), ("churn_rate", -0.2)],
    "market_sentiment":     [("new_customer_growth", 0.2)],
    "market_share":         [("revenue_growth", 0.3), ("churn_rate", -0.15)],
    "execution_quality":    [("gross_margin", 0.1)],
    "team_quality":         [("payroll_cost_per_head", 0.1)],
    "exit_value":           [],  # output
    "dpi":                  [],  # output
    "tvpi":                 [],  # output
    "operational_efficiency": [("gross_margin", 0.15), ("ga_pct", -0.1)],
}


def macro_to_drivers(
    impact_factor: str,
    magnitude: float = 0.1,
) -> Dict[str, float]:
    """Convert a macro impact factor + magnitude into driver deltas.

    Returns {driver_id: delta_value} for each micro driver affected.
    magnitude is the raw event strength (e.g. 0.2 = 20% change).
    The direction_multiplier in MACRO_TO_MICRO scales + directs it.
    """
    entries = MACRO_TO_MICRO.get(impact_factor, [])
    result: Dict[str, float] = {}
    for driver_id, direction in entries:
        d = _DRIVERS.get(driver_id)
        if d and not d.computed:
            result[driver_id] = round(magnitude * direction, 4)
    return result
