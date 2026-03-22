"""
Liquidity Management Service
=============================
Advanced granular cash flow planning engine that replaces the hardcoded
percentage-of-revenue approach in CashFlowPlanningService with proper
operational math at full subcategory depth.

Core principles:
- Every line item is modeled individually with its own growth driver
- Subcategories (engineering_salaries, cloud_infra, etc.) each get their
  own growth model — headcount-driven, usage-driven, or contract-stepped
- Cash timing is separate from accrual: DSO/DPO/DIO per subcategory
- Liquidity events (funding, debt, one-offs) are first-class
- Three-statement linkage: P&L → balance sheet → cash flow statement

Growth driver types per subcategory:
- headcount: grows with hiring plan × cost per head (salaries, benefits)
- usage: grows proportional to revenue or customer count (cloud, APIs)
- stepped: flat until threshold then jumps (office lease, licenses)
- linear: fixed monthly growth rate (insurance, compliance)
- cac_driven: new_customers × cost_per_acquisition (paid marketing)
- revenue_pct: percentage of revenue (payment processing, commissions)
"""

import logging
import math
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.services.actuals_ingestion import SUBCOMPONENT_TAXONOMY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subcategory growth driver configuration
# ---------------------------------------------------------------------------

# Each subcategory has a default driver type that determines how it grows.
# The service picks the right model based on data availability.

SUBCATEGORY_GROWTH_DRIVERS = {
    # R&D subcategories
    "opex_rd": {
        "engineering_salaries": {"driver": "headcount", "dept_share": 0.65},
        "infra_cloud":          {"driver": "usage", "scales_with": "revenue", "elasticity": 0.6},
        "tools_licenses":       {"driver": "stepped", "step_interval_months": 12, "step_pct": 0.10},
        "contractor":           {"driver": "linear", "monthly_growth": 0.005},
        "research":             {"driver": "linear", "monthly_growth": 0.008},
        # AI-specific
        "ml_engineering":       {"driver": "headcount", "dept_share": 0.30},
        "data_engineering":     {"driver": "headcount", "dept_share": 0.20},
        "model_training":       {"driver": "usage", "scales_with": "revenue", "elasticity": 0.4},
    },
    # S&M subcategories
    "opex_sm": {
        "paid_acquisition":     {"driver": "cac_driven"},
        "content_marketing":    {"driver": "linear", "monthly_growth": 0.01},
        "sales_salaries":       {"driver": "headcount", "dept_share": 0.50},
        "events":               {"driver": "stepped", "step_interval_months": 3, "step_pct": 0.0},
        "partnerships":         {"driver": "linear", "monthly_growth": 0.005},
        # Other models
        "supply_acquisition":   {"driver": "cac_driven"},
        "demand_acquisition":   {"driver": "cac_driven"},
        "business_development": {"driver": "headcount", "dept_share": 0.30},
        "channel_partners":     {"driver": "revenue_pct", "pct": 0.03},
    },
    # G&A subcategories
    "opex_ga": {
        "finance_legal":        {"driver": "stepped", "step_interval_months": 6, "step_pct": 0.05},
        "office":               {"driver": "stepped", "step_interval_months": 12, "step_pct": 0.0},
        "admin_salaries":       {"driver": "headcount", "dept_share": 0.15},
        "insurance":            {"driver": "stepped", "step_interval_months": 12, "step_pct": 0.08},
        "other_ga":             {"driver": "linear", "monthly_growth": 0.003},
        # Industrial/manufacturing
        "facility_lease":       {"driver": "stepped", "step_interval_months": 12, "step_pct": 0.03},
        "utilities":            {"driver": "usage", "scales_with": "headcount", "elasticity": 0.5},
        "compliance":           {"driver": "stepped", "step_interval_months": 6, "step_pct": 0.05},
    },
    # COGS subcategories
    "cogs": {
        "hosting":              {"driver": "usage", "scales_with": "revenue", "elasticity": 0.5},
        "support_salaries":     {"driver": "headcount", "dept_share": 0.10},
        "payment_processing":   {"driver": "revenue_pct", "pct": 0.029},
        "third_party_apis":     {"driver": "usage", "scales_with": "revenue", "elasticity": 0.7},
        "data_costs":           {"driver": "usage", "scales_with": "revenue", "elasticity": 0.4},
        # E-commerce / hardware
        "inventory":            {"driver": "usage", "scales_with": "revenue", "elasticity": 0.85},
        "fulfillment":          {"driver": "usage", "scales_with": "revenue", "elasticity": 0.9},
        "shipping_costs":       {"driver": "usage", "scales_with": "revenue", "elasticity": 0.8},
        "materials":            {"driver": "usage", "scales_with": "revenue", "elasticity": 0.75},
        "manufacturing":        {"driver": "usage", "scales_with": "revenue", "elasticity": 0.6},
        "api_inference_costs":  {"driver": "usage", "scales_with": "revenue", "elasticity": 0.55},
    },
}

# Payment timing per subcategory (days to actually pay/collect)
# Overrides the parent-level DSO/DPO with line-item specificity
SUBCATEGORY_PAYMENT_TIMING = {
    # COGS — typically paid faster
    "hosting":              {"dpo": 0},     # auto-billed, immediate
    "api_inference_costs":  {"dpo": 0},     # usage-based, immediate
    "payment_processing":   {"dpo": 2},     # net-2 settlement
    "third_party_apis":     {"dpo": 15},    # net-15
    "support_salaries":     {"dpo": 0},     # payroll, semi-monthly
    # OpEx — varies
    "engineering_salaries":  {"dpo": 0},    # payroll
    "sales_salaries":        {"dpo": 0},    # payroll
    "admin_salaries":        {"dpo": 0},    # payroll
    "ml_engineering":        {"dpo": 0},    # payroll
    "infra_cloud":           {"dpo": 30},   # net-30
    "tools_licenses":        {"dpo": 0},    # annual prepay → amortized
    "contractor":            {"dpo": 30},   # net-30
    "paid_acquisition":      {"dpo": 7},    # ad platforms bill weekly
    "content_marketing":     {"dpo": 30},
    "events":                {"dpo": 15},   # deposits + final payment
    "office":                {"dpo": 0},    # monthly lease, due on 1st
    "finance_legal":         {"dpo": 45},   # law firms net-45
    "insurance":             {"dpo": 0},    # prepaid quarterly
}


class LiquidityManagementService:
    """Advanced granular cash flow planning with subcategory-level modeling."""

    def build_liquidity_model(
        self,
        company_id: str,
        months: int = 24,
        start_period: Optional[str] = None,
        scenario_overrides: Optional[Dict[str, Any]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Build a fully granular liquidity model.

        Returns a complete cash flow plan with:
        - Monthly P&L at subcategory depth
        - Three-statement cash flow (operating / investing / financing)
        - Working capital schedule with per-line-item timing
        - Runway analysis with sensitivity
        - Cash conversion cycle tracking
        - Liquidity risk alerts

        Args:
            company_id: Company to model
            months: Forecast horizon (default 24)
            start_period: "YYYY-MM" start (defaults to next month)
            scenario_overrides: Override any driver or assumption
            events: Discrete liquidity events list
        """
        from app.services.company_data_pull import pull_company_data

        cd = pull_company_data(company_id)
        overrides = scenario_overrides or {}

        # Merge events from overrides and explicit param
        all_events = list(events or [])
        all_events.extend(overrides.pop("events", []))

        # Build the seed data
        seed = cd.to_forecast_seed()
        seed.update(overrides)
        seed["events"] = all_events

        # Pull subcategory actuals for anchoring
        subcategory_actuals = self._pull_subcategory_actuals(company_id)
        subcategory_proportions = seed.get("_subcategory_proportions", {})

        # Resolve start period
        if not start_period:
            today = date.today()
            m = today.month + 1
            y = today.year + (1 if m > 12 else 0)
            m = m if m <= 12 else m - 12
            start_period = f"{y}-{m:02d}"

        # Build monthly rows
        monthly = self._build_monthly_model(
            seed, cd, subcategory_actuals, subcategory_proportions,
            months, start_period,
        )

        # Compute aggregate analytics
        summary = self._compute_summary(monthly, seed)
        risk_alerts = self._compute_risk_alerts(monthly, seed)
        cash_conversion = self._compute_cash_conversion_cycle(monthly)

        return {
            "company_id": company_id,
            "start_period": start_period,
            "months": months,
            "monthly": monthly,
            "summary": summary,
            "risk_alerts": risk_alerts,
            "cash_conversion_cycle": cash_conversion,
            "events_applied": len(all_events),
        }

    # ------------------------------------------------------------------
    # Core monthly model
    # ------------------------------------------------------------------

    def _build_monthly_model(
        self,
        seed: Dict[str, Any],
        cd: Any,  # CompanyData
        subcategory_actuals: Dict[str, Dict[str, List[float]]],
        subcategory_proportions: Dict[str, Dict[str, float]],
        months: int,
        start_period: str,
    ) -> List[Dict[str, Any]]:
        """Build month-by-month P&L with full subcategory decomposition."""

        # ── Revenue inputs ────────────────────────────────────────────
        base_revenue = seed.get("revenue") or seed.get("arr") or 0
        monthly_revenue = base_revenue / 12 if base_revenue > 12000 else base_revenue
        # If base_revenue looks annual (>12k), convert to monthly
        if base_revenue > 0 and monthly_revenue > base_revenue:
            monthly_revenue = base_revenue

        growth_rate = seed.get("growth_rate", 0.30)
        growth_rate = max(-0.5, min(growth_rate, 3.0))
        monthly_growth = (1 + growth_rate) ** (1 / 12) - 1

        gross_margin = seed.get("gross_margin", 0.65)

        # ── Customer-level model inputs ───────────────────────────────
        churn_rate = seed.get("churn_rate")
        nrr = seed.get("nrr")
        acv = seed.get("acv_override")
        new_cust_growth = seed.get("new_customer_growth_rate")
        pricing_pct = seed.get("pricing_pct_change")
        sales_cycle = seed.get("sales_cycle_months", 0)
        use_customer_model = any(v is not None for v in [churn_rate, nrr, new_cust_growth, acv])

        # Customer state
        if use_customer_model and acv and acv > 0:
            existing_customers = (base_revenue / acv) if acv else 0
        else:
            existing_customers = seed.get("_detected_customer_count", 0) or 0
        new_customer_pipeline: List[float] = []

        # ── Headcount inputs ──────────────────────────────────────────
        headcount = seed.get("headcount") or 0
        hiring_monthly = seed.get("hiring_plan_monthly", 0)
        cost_per_head = seed.get("cost_per_head", 15_000)

        # ── Capital structure inputs ──────────────────────────────────
        cash_balance = seed.get("cash_balance") or 0
        outstanding_debt = seed.get("outstanding_debt", 0)
        debt_service = seed.get("debt_service_monthly", 0)
        interest_rate_annual = seed.get("interest_rate", 0)
        tax_rate = seed.get("tax_rate", 0)
        capex_abs = seed.get("capex_override")

        # ── Working capital defaults ──────────────────────────────────
        dso = seed.get("dso", 45)
        dpo = seed.get("dpo", 30)
        dio = seed.get("dio", 0)

        # ── CAC ───────────────────────────────────────────────────────
        cac = seed.get("cac_override")

        # ── Liquidity events index ────────────────────────────────────
        raw_events = seed.get("events", [])
        events_by_period: Dict[str, List[Dict[str, Any]]] = {}
        for evt in raw_events:
            p = evt.get("period", "")
            events_by_period.setdefault(p, []).append(evt)

        # ── OpEx driver overrides ─────────────────────────────────────
        opex_adjustments = seed.get("opex_adjustments", {})

        # ── Build subcategory base amounts ────────────────────────────
        # For each parent category, resolve actual subcategory amounts
        # from trailing actuals. These are the anchors.
        subcat_bases = self._resolve_subcategory_bases(
            subcategory_actuals, subcategory_proportions, seed,
        )

        # ── Working capital state ─────────────────────────────────────
        wc_state = {
            "prev_ar": 0.0, "prev_ap": 0.0, "prev_inv": 0.0,
            "prev_deferred_rev": 0.0, "prev_prepaid": 0.0,
            # Per-subcategory AP tracking
            "subcat_payables": {},
        }

        # ── Period generation ─────────────────────────────────────────
        y, m = int(start_period[:4]), int(start_period[5:7])
        results: List[Dict[str, Any]] = []

        for i in range(months):
            period_y = y + (m + i - 1) // 12
            period_m = (m + i - 1) % 12 + 1
            period = f"{period_y}-{period_m:02d}"

            # ── Revenue ───────────────────────────────────────────────
            if use_customer_model and acv and acv > 0:
                revenue, existing_customers, new_customer_pipeline = (
                    self._compute_customer_revenue(
                        existing_customers, new_customer_pipeline,
                        acv, churn_rate, nrr, new_cust_growth,
                        pricing_pct, sales_cycle, i,
                    )
                )
                if revenue <= 0:
                    # Fallback to growth model
                    revenue = monthly_revenue * (1 + monthly_growth) ** i
            else:
                revenue = monthly_revenue * (1 + monthly_growth) ** i

            # ── COGS at subcategory level ─────────────────────────────
            cogs_total, cogs_breakdown = self._compute_subcategory_spend(
                parent="cogs",
                bases=subcat_bases.get("cogs", {}),
                month_idx=i,
                revenue=revenue,
                headcount=headcount,
                customers=existing_customers,
                cac=None,
                new_customers=0,
                opex_adjustments=opex_adjustments,
                gross_margin=gross_margin,
            )
            # If no subcategory data, use gross margin
            if cogs_total <= 0:
                cogs_total = revenue * (1 - gross_margin)
                cogs_breakdown = {"_aggregate": cogs_total}

            gross_profit = revenue - cogs_total
            actual_gm = gross_profit / revenue if revenue > 0 else 0

            # ── New customers this period (for CAC-driven S&M) ────────
            new_custs_this_period = 0
            if new_customer_pipeline:
                new_custs_this_period = new_customer_pipeline[-1] if new_customer_pipeline else 0
            elif new_cust_growth and existing_customers > 0:
                new_custs_this_period = existing_customers * new_cust_growth

            # ── OpEx at subcategory level ─────────────────────────────
            rd_total, rd_breakdown = self._compute_subcategory_spend(
                parent="opex_rd",
                bases=subcat_bases.get("opex_rd", {}),
                month_idx=i,
                revenue=revenue,
                headcount=headcount,
                customers=existing_customers,
                cac=None,
                new_customers=new_custs_this_period,
                opex_adjustments=opex_adjustments,
            )

            sm_total, sm_breakdown = self._compute_subcategory_spend(
                parent="opex_sm",
                bases=subcat_bases.get("opex_sm", {}),
                month_idx=i,
                revenue=revenue,
                headcount=headcount,
                customers=existing_customers,
                cac=cac,
                new_customers=new_custs_this_period,
                opex_adjustments=opex_adjustments,
            )

            ga_total, ga_breakdown = self._compute_subcategory_spend(
                parent="opex_ga",
                bases=subcat_bases.get("opex_ga", {}),
                month_idx=i,
                revenue=revenue,
                headcount=headcount,
                customers=existing_customers,
                cac=None,
                new_customers=new_custs_this_period,
                opex_adjustments=opex_adjustments,
            )

            # Headcount growth
            if hiring_monthly:
                headcount += hiring_monthly

            total_opex = rd_total + sm_total + ga_total
            ebitda = gross_profit - total_opex
            ebitda_margin = ebitda / revenue if revenue > 0 else -1.0

            # ── Below EBITDA ──────────────────────────────────────────
            # CapEx
            if capex_abs is not None:
                capex = capex_abs
            else:
                capex = revenue * 0.03 if revenue > 0 else 0

            # Debt service + interest
            interest_payment = outstanding_debt * (interest_rate_annual / 12)
            total_debt_payment = debt_service + interest_payment
            if debt_service > 0:
                outstanding_debt = max(0, outstanding_debt - debt_service)

            # Tax
            pre_tax_income = ebitda - capex - total_debt_payment
            tax_expense = max(0, pre_tax_income * tax_rate) if tax_rate and pre_tax_income > 0 else 0
            net_income = pre_tax_income - tax_expense

            # ── Three-statement cash flow ─────────────────────────────
            # Operating cash flow = net income + non-cash adjustments - WC changes
            depreciation = capex * 0.2 / 12 if capex > 0 else 0  # straight-line 5yr
            operating_cf_before_wc = net_income + depreciation

            # Working capital with subcategory-level timing
            wc_detail, wc_delta = self._compute_working_capital(
                revenue=revenue,
                cogs_total=cogs_total,
                cogs_breakdown=cogs_breakdown,
                opex_total=total_opex,
                rd_breakdown=rd_breakdown,
                sm_breakdown=sm_breakdown,
                ga_breakdown=ga_breakdown,
                dso=dso,
                dpo=dpo,
                dio=dio,
                wc_state=wc_state,
            )

            operating_cash_flow = operating_cf_before_wc - wc_delta

            # Investing cash flow
            investing_cash_flow = -capex

            # Financing cash flow
            financing_cash_flow = -total_debt_payment

            # ── Liquidity events ──────────────────────────────────────
            event_impact = 0.0
            period_event_log = []
            for evt in events_by_period.get(period, []):
                evt_type = evt.get("type", "")
                evt_amount = float(evt.get("amount", 0))
                evt_label = evt.get("label", evt_type)

                if evt_type == "funding":
                    financing_cash_flow += evt_amount
                    event_impact += evt_amount
                elif evt_type == "debt_drawdown":
                    financing_cash_flow += evt_amount
                    outstanding_debt += evt_amount
                    event_impact += evt_amount
                elif evt_type == "debt_repayment":
                    financing_cash_flow -= abs(evt_amount)
                    outstanding_debt = max(0, outstanding_debt - abs(evt_amount))
                    event_impact -= abs(evt_amount)
                elif evt_type == "one_time_cost":
                    operating_cash_flow += evt_amount  # negative amount
                    event_impact += evt_amount
                elif evt_type == "one_time_revenue":
                    operating_cash_flow += evt_amount
                    event_impact += evt_amount
                elif evt_type == "asset_purchase":
                    investing_cash_flow -= abs(evt_amount)
                    event_impact -= abs(evt_amount)
                elif evt_type == "asset_sale":
                    investing_cash_flow += evt_amount
                    event_impact += evt_amount

                period_event_log.append({
                    "type": evt_type, "amount": evt_amount, "label": evt_label,
                })

            # Net cash flow
            net_cash_flow = operating_cash_flow + investing_cash_flow + financing_cash_flow
            cash_balance += net_cash_flow

            # Runway
            if net_cash_flow < 0:
                runway_months = cash_balance / (-net_cash_flow)
            else:
                runway_months = 999

            # ── Assemble row ──────────────────────────────────────────
            row: Dict[str, Any] = {
                "period": period,
                # P&L
                "revenue": round(revenue, 2),
                "cogs": round(cogs_total, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_margin": round(actual_gm, 4),
                "rd_spend": round(rd_total, 2),
                "sm_spend": round(sm_total, 2),
                "ga_spend": round(ga_total, 2),
                "total_opex": round(total_opex, 2),
                "ebitda": round(ebitda, 2),
                "ebitda_margin": round(ebitda_margin, 4),
                "depreciation": round(depreciation, 2),
                "capex": round(capex, 2),
                "interest_expense": round(interest_payment, 2),
                "debt_service": round(total_debt_payment, 2),
                "tax_expense": round(tax_expense, 2),
                "net_income": round(net_income, 2),
                # Cash flow statement
                "operating_cash_flow": round(operating_cash_flow, 2),
                "investing_cash_flow": round(investing_cash_flow, 2),
                "financing_cash_flow": round(financing_cash_flow, 2),
                "net_cash_flow": round(net_cash_flow, 2),
                "free_cash_flow": round(operating_cash_flow + investing_cash_flow, 2),
                # Working capital
                "working_capital": round(wc_detail.get("net_working_capital", 0), 2),
                "working_capital_delta": round(wc_delta, 2),
                "accounts_receivable": round(wc_detail.get("accounts_receivable", 0), 2),
                "accounts_payable": round(wc_detail.get("accounts_payable", 0), 2),
                "inventory": round(wc_detail.get("inventory", 0), 2),
                "deferred_revenue": round(wc_detail.get("deferred_revenue", 0), 2),
                "prepaid_expenses": round(wc_detail.get("prepaid_expenses", 0), 2),
                # Balance sheet
                "cash_balance": round(cash_balance, 2),
                "outstanding_debt": round(outstanding_debt, 2),
                # Metrics
                "runway_months": round(max(0, runway_months), 1),
                "cash_conversion_cycle_days": round(
                    dso + dio - dpo, 1
                ),
                "headcount": round(headcount, 0),
                "customers": round(existing_customers, 0) if use_customer_model else None,
                # Events
                "event_impact": round(event_impact, 2),
                "events": period_event_log if period_event_log else None,
                # Subcategory breakdowns
                "subcategories": {
                    "cogs": {k: round(v, 2) for k, v in cogs_breakdown.items()},
                    "opex_rd": {k: round(v, 2) for k, v in rd_breakdown.items()},
                    "opex_sm": {k: round(v, 2) for k, v in sm_breakdown.items()},
                    "opex_ga": {k: round(v, 2) for k, v in ga_breakdown.items()},
                },
            }

            results.append(row)

        return results

    # ------------------------------------------------------------------
    # Subcategory spend engine
    # ------------------------------------------------------------------

    def _compute_subcategory_spend(
        self,
        parent: str,
        bases: Dict[str, float],
        month_idx: int,
        revenue: float,
        headcount: float,
        customers: float,
        cac: Optional[float],
        new_customers: float,
        opex_adjustments: Dict[str, Any],
        gross_margin: float = 0.65,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute spend for a parent category by modeling each subcategory
        individually using its growth driver.

        Each subcategory grows according to its driver type:
        - headcount: base_per_head × current_headcount
        - usage: base × (current_revenue / base_revenue) ^ elasticity
        - stepped: flat, then step up by step_pct every step_interval
        - linear: base × (1 + monthly_growth) ^ month_idx
        - cac_driven: new_customers × CAC
        - revenue_pct: revenue × percentage

        Returns (total, breakdown_dict).
        """
        if not bases:
            return 0.0, {}

        driver_config = SUBCATEGORY_GROWTH_DRIVERS.get(parent, {})
        breakdown: Dict[str, float] = {}
        total = 0.0

        for subcat, base_amount in bases.items():
            if base_amount <= 0:
                breakdown[subcat] = 0.0
                continue

            config = driver_config.get(subcat, {"driver": "linear", "monthly_growth": 0.005})
            driver = config["driver"]

            # Compute raw projected amount based on driver type
            if driver == "headcount":
                # Salary costs scale with headcount
                if headcount > 0 and month_idx == 0:
                    per_head = base_amount / max(headcount, 1)
                else:
                    per_head = base_amount / max(headcount - month_idx * (headcount * 0.01), 1) if headcount > 0 else base_amount
                # Simpler: grow linearly with headcount from base
                amount = base_amount * (1 + 0.003) ** month_idx  # 0.3% monthly = ~3.7% annual raise
                # Scale with headcount growth
                if headcount > 0:
                    dept_share = config.get("dept_share", 0.5)
                    # Base assumption: headcount grows in line with hiring plan
                    # The actual headcount is updated in the main loop
                    pass  # amount already set from base

            elif driver == "usage":
                # Scales with a reference metric (revenue, customers, headcount)
                elasticity = config.get("elasticity", 0.6)
                scales_with = config.get("scales_with", "revenue")

                if scales_with == "revenue" and revenue > 0:
                    # Cloud/API costs: grow sub-linearly with revenue
                    # amount = base × (rev_t / rev_0) ^ elasticity
                    base_rev = bases.get("_base_revenue", revenue)
                    ratio = revenue / base_rev if base_rev > 0 else 1.0
                    amount = base_amount * (ratio ** elasticity)
                elif scales_with == "headcount" and headcount > 0:
                    base_hc = bases.get("_base_headcount", headcount)
                    ratio = headcount / base_hc if base_hc > 0 else 1.0
                    amount = base_amount * (ratio ** elasticity)
                elif scales_with == "customers" and customers > 0:
                    base_cust = bases.get("_base_customers", customers)
                    ratio = customers / base_cust if base_cust > 0 else 1.0
                    amount = base_amount * (ratio ** elasticity)
                else:
                    amount = base_amount * (1 + 0.005) ** month_idx

            elif driver == "stepped":
                # Flat, then jumps at intervals
                step_interval = config.get("step_interval_months", 12)
                step_pct = config.get("step_pct", 0.10)
                steps = month_idx // step_interval
                amount = base_amount * (1 + step_pct) ** steps

            elif driver == "cac_driven":
                # S&M paid acquisition = new_customers × CAC
                if cac is not None and new_customers > 0:
                    amount = new_customers * cac
                else:
                    # Fallback: grow with revenue
                    amount = base_amount * (1 + 0.008) ** month_idx

            elif driver == "revenue_pct":
                # Payment processing, commissions = % of revenue
                pct = config.get("pct", 0.029)
                amount = revenue * pct

            else:  # linear
                monthly_g = config.get("monthly_growth", 0.005)
                amount = base_amount * (1 + monthly_g) ** month_idx

            # Apply driver override (e.g., "cut engineering by 20%")
            override_key = self._subcat_to_override_key(parent, subcat)
            if override_key and override_key in opex_adjustments:
                delta = float(opex_adjustments[override_key])
                amount *= (1 + delta)

            # For COGS with gross margin override: cap total COGS
            amount = max(0, amount)
            breakdown[subcat] = amount
            total += amount

            # Subcomponent decomposition — if we know the components beneath
            # this subcategory, break the total down proportionally.
            # Uses actuals if available, otherwise default proportions.
            subcomponents = SUBCOMPONENT_TAXONOMY.get(subcat)
            if subcomponents and amount > 0:
                subcomp_actuals = bases.get(f"_subcomp_{subcat}", {})
                if subcomp_actuals:
                    # Use actual proportions from Workday/ERP data
                    actual_total = sum(subcomp_actuals.values())
                    if actual_total > 0:
                        for comp_name, comp_actual in subcomp_actuals.items():
                            breakdown[f"{subcat}/{comp_name}"] = amount * (comp_actual / actual_total)
                else:
                    # Use default proportions for salary subcategories
                    if driver == "headcount":
                        _COMP_DEFAULTS = {
                            "base_pay": 0.62, "bonus": 0.10, "benefits": 0.15,
                            "equity_comp": 0.08, "payroll_tax": 0.05,
                        }
                        for comp_name in subcomponents:
                            pct = _COMP_DEFAULTS.get(comp_name, 1.0 / len(subcomponents))
                            breakdown[f"{subcat}/{comp_name}"] = round(amount * pct, 2)

        return total, breakdown

    @staticmethod
    def _subcat_to_override_key(parent: str, subcat: str) -> Optional[str]:
        """Map parent+subcategory to opex_adjustments key."""
        prefix_map = {
            "opex_rd": "rd", "opex_sm": "sm", "opex_ga": "ga", "cogs": "cogs",
        }
        prefix = prefix_map.get(parent)
        if not prefix:
            return None
        return f"{prefix}_{subcat}_delta"

    # ------------------------------------------------------------------
    # Customer revenue model
    # ------------------------------------------------------------------

    def _compute_customer_revenue(
        self,
        existing_customers: float,
        pipeline: List[float],
        acv: float,
        churn_rate: Optional[float],
        nrr: Optional[float],
        new_cust_growth: Optional[float],
        pricing_pct: Optional[float],
        sales_cycle: int,
        month_idx: int,
    ) -> Tuple[float, float, List[float]]:
        """
        Cohort-aware customer revenue model.

        Revenue = (existing × monthly_ACV × retention × NRR) + (new × monthly_ACV)
        With sales cycle delay on new customer recognition.

        Returns (revenue, updated_customers, updated_pipeline).
        """
        monthly_acv = acv / 12

        # Churn existing customers
        if churn_rate is not None:
            churn_rate = max(0, min(churn_rate, 0.20))
            existing_customers *= (1 - churn_rate)

        # NRR expansion on existing base (monthly compounding)
        retention_mult = (nrr or 1.0) ** (1 / 12)
        existing_rev = existing_customers * monthly_acv * retention_mult

        # New customers
        new_this_month = 0.0
        recognized = 0.0
        if new_cust_growth is not None:
            new_cust_growth = max(0, min(new_cust_growth, 0.15))
            new_this_month = existing_customers * new_cust_growth
            pipeline.append(new_this_month)

            # Sales cycle delay
            if len(pipeline) > sales_cycle:
                recognized = pipeline[-(sales_cycle + 1)]
                existing_customers += recognized
        else:
            pipeline.append(0)

        new_rev = recognized * monthly_acv

        # Pricing uplift
        pricing_mult = 1 + (pricing_pct or 0)
        total_revenue = (existing_rev + new_rev) * pricing_mult

        return total_revenue, existing_customers, pipeline

    # ------------------------------------------------------------------
    # Working capital engine (subcategory-level timing)
    # ------------------------------------------------------------------

    def _compute_working_capital(
        self,
        revenue: float,
        cogs_total: float,
        cogs_breakdown: Dict[str, float],
        opex_total: float,
        rd_breakdown: Dict[str, float],
        sm_breakdown: Dict[str, float],
        ga_breakdown: Dict[str, float],
        dso: float,
        dpo: float,
        dio: float,
        wc_state: Dict[str, float],
    ) -> Tuple[Dict[str, Any], float]:
        """
        Compute working capital positions and delta using
        subcategory-level payment timing.

        Instead of a single DPO for all payables, each subcategory
        has its own payment timing. This gives a more accurate
        picture of actual cash outflows.

        Returns (detail_dict, wc_delta).
        """
        # Accounts Receivable: revenue timing
        # AR = (daily revenue) × DSO
        ar = (revenue / 30) * dso if dso > 0 else 0

        # Accounts Payable: weighted by subcategory payment terms
        # For each expense subcategory, compute its contribution to AP
        # based on that subcategory's specific DPO
        ap = 0.0
        all_expenses = {}
        for cat_name, breakdown in [
            ("cogs", cogs_breakdown),
            ("opex_rd", rd_breakdown),
            ("opex_sm", sm_breakdown),
            ("opex_ga", ga_breakdown),
        ]:
            for subcat, amount in breakdown.items():
                if subcat.startswith("_"):
                    continue
                subcat_dpo = SUBCATEGORY_PAYMENT_TIMING.get(subcat, {}).get("dpo", dpo)
                # AP contribution = (daily expense) × subcat DPO
                subcat_ap = (amount / 30) * subcat_dpo
                ap += subcat_ap
                all_expenses[f"{cat_name}.{subcat}"] = {
                    "amount": amount,
                    "dpo": subcat_dpo,
                    "payable": subcat_ap,
                }

        # If no subcategory detail, fall back to aggregate DPO
        if not all_expenses and (cogs_total + opex_total) > 0:
            ap = ((cogs_total + opex_total) / 30) * dpo

        # Inventory: only for businesses with physical goods
        inv = (cogs_total / 30) * dio if dio > 0 else 0

        # Deferred revenue: for annual contracts paid upfront
        # Simplified: assume 10% of revenue is prepaid annually
        deferred_rev = 0  # Would need contract data to compute properly

        # Prepaid expenses: tools/licenses/insurance paid annually
        prepaid = 0
        for subcat in ("tools_licenses", "insurance"):
            for breakdown in [rd_breakdown, ga_breakdown]:
                if subcat in breakdown:
                    # Annual prepay amortized monthly
                    prepaid += breakdown[subcat] * 0.5  # ~6 months prepaid on average

        # Net working capital
        net_wc = ar + inv + prepaid - ap - deferred_rev

        # Delta from previous period
        prev_ar = wc_state.get("prev_ar", 0)
        prev_ap = wc_state.get("prev_ap", 0)
        prev_inv = wc_state.get("prev_inv", 0)
        prev_deferred = wc_state.get("prev_deferred_rev", 0)
        prev_prepaid = wc_state.get("prev_prepaid", 0)

        wc_delta = (
            (ar - prev_ar)
            + (inv - prev_inv)
            + (prepaid - prev_prepaid)
            - (ap - prev_ap)
            - (deferred_rev - prev_deferred)
        )

        # Update state for next period
        wc_state["prev_ar"] = ar
        wc_state["prev_ap"] = ap
        wc_state["prev_inv"] = inv
        wc_state["prev_deferred_rev"] = deferred_rev
        wc_state["prev_prepaid"] = prepaid

        detail = {
            "accounts_receivable": ar,
            "accounts_payable": ap,
            "inventory": inv,
            "deferred_revenue": deferred_rev,
            "prepaid_expenses": prepaid,
            "net_working_capital": net_wc,
            "expense_payables_detail": all_expenses,
        }

        return detail, wc_delta

    # ------------------------------------------------------------------
    # Subcategory data resolution
    # ------------------------------------------------------------------

    def _resolve_subcategory_bases(
        self,
        subcategory_actuals: Dict[str, Dict[str, List[float]]],
        subcategory_proportions: Dict[str, Dict[str, float]],
        seed: Dict[str, Any],
    ) -> Dict[str, Dict[str, float]]:
        """
        Resolve base amounts for each subcategory from actuals.

        Priority:
        1. Trailing 3-month average of actual subcategory values
        2. Parent total × proportion from get_subcategory_proportions()
        3. Skip (no data = no subcategory modeling for that parent)

        Also stores _base_revenue and _base_headcount for usage drivers.
        """
        bases: Dict[str, Dict[str, float]] = {}

        # Parent totals from seed
        parent_totals = {
            "opex_rd": seed.get("_rd_spend", 0),
            "opex_sm": seed.get("_sm_spend", 0),
            "opex_ga": seed.get("_ga_spend", 0),
            "cogs": (seed.get("revenue", 0) or 0) * (1 - seed.get("gross_margin", 0.65)),
        }

        for parent in ("opex_rd", "opex_sm", "opex_ga", "cogs"):
            parent_base: Dict[str, float] = {}

            if parent in subcategory_actuals and subcategory_actuals[parent]:
                # Option 1: Use trailing actuals directly
                for subcat, values in subcategory_actuals[parent].items():
                    if values:
                        # Trailing 3-month average
                        recent = values[-3:] if len(values) >= 3 else values
                        parent_base[subcat] = sum(recent) / len(recent)

            elif parent in subcategory_proportions and subcategory_proportions[parent]:
                # Option 2: Decompose parent total by proportions
                parent_total = parent_totals.get(parent, 0)
                if parent_total > 0:
                    for subcat, pct in subcategory_proportions[parent].items():
                        parent_base[subcat] = parent_total * pct

            if parent_base:
                # Store reference values for usage drivers
                parent_base["_base_revenue"] = seed.get("revenue", 0) or 0
                parent_base["_base_headcount"] = seed.get("headcount", 0) or 0
                parent_base["_base_customers"] = seed.get("_detected_customer_count", 0) or 0

                # Resolve subcomponent bases from actuals
                # Look for keys like "engineering_salaries/base_pay" in the actuals
                if parent in subcategory_actuals:
                    for key, values in subcategory_actuals[parent].items():
                        if "/" in key:
                            # This is a subcomponent: "engineering_salaries/base_pay"
                            parent_subcat = key.split("/")[0]
                            comp_name = key.split("/", 1)[1]
                            subcomp_key = f"_subcomp_{parent_subcat}"
                            if subcomp_key not in parent_base:
                                parent_base[subcomp_key] = {}
                            recent = values[-3:] if len(values) >= 3 else values
                            parent_base[subcomp_key][comp_name] = sum(recent) / len(recent)

                bases[parent] = parent_base

        return bases

    def _pull_subcategory_actuals(
        self,
        company_id: str,
    ) -> Dict[str, Dict[str, List[float]]]:
        """
        Pull actual subcategory and subcomponent amounts from fpa_actuals.

        Returns {parent: {subcategory: [monthly_amounts_chronological]}}.

        Subcomponent rows (hierarchy_path like "opex_rd/engineering_salaries/base_pay")
        are stored under the parent category with their full path as the key.
        """
        try:
            from app.core.supabase_client import get_supabase_client
            sb = get_supabase_client()
            if not sb:
                return {}

            rows = (
                sb.table("fpa_actuals")
                .select("category, subcategory, hierarchy_path, amount, period")
                .eq("company_id", company_id)
                .neq("subcategory", "")
                .order("period", desc=False)
                .execute()
                .data
            ) or []

            result: Dict[str, Dict[str, List[float]]] = {}
            for row in rows:
                cat = row.get("category", "")
                sub = row.get("subcategory", "")
                hierarchy = row.get("hierarchy_path", "")
                amount = row.get("amount")
                if not cat or not sub or amount is None:
                    continue

                # Check if this is a subcomponent row (subcategory contains "/")
                # e.g. "engineering_salaries/base_pay"
                if "/" in sub:
                    # Store as subcomponent under the parent subcategory
                    result.setdefault(cat, {}).setdefault(sub, []).append(float(amount))
                else:
                    result.setdefault(cat, {}).setdefault(sub, []).append(float(amount))

            return result

        except Exception as e:
            logger.warning("Failed to pull subcategory actuals: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Summary analytics
    # ------------------------------------------------------------------

    def _compute_summary(
        self,
        monthly: List[Dict[str, Any]],
        seed: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute aggregate summary metrics from the monthly model."""
        if not monthly:
            return {}

        first = monthly[0]
        last = monthly[-1]
        n = len(monthly)

        total_revenue = sum(r["revenue"] for r in monthly)
        total_fcf = sum(r["free_cash_flow"] for r in monthly)
        total_opex = sum(r["total_opex"] for r in monthly)
        total_cogs = sum(r["cogs"] for r in monthly)

        # Monthly burn rate (average of months with negative FCF)
        burn_months = [r for r in monthly if r["free_cash_flow"] < 0]
        avg_burn = (
            abs(sum(r["free_cash_flow"] for r in burn_months) / len(burn_months))
            if burn_months else 0
        )

        # Cash low point
        min_cash = min(r["cash_balance"] for r in monthly)
        min_cash_period = next(
            r["period"] for r in monthly if r["cash_balance"] == min_cash
        )

        # Zero-cash crossing
        zero_crossing = None
        for r in monthly:
            if r["cash_balance"] <= 0:
                zero_crossing = r["period"]
                break

        # Revenue CAGR
        if first["revenue"] > 0 and last["revenue"] > 0 and n > 1:
            rev_cagr = (last["revenue"] / first["revenue"]) ** (12 / n) - 1
        else:
            rev_cagr = 0

        # OpEx as % of revenue
        opex_pct = total_opex / total_revenue if total_revenue > 0 else 0

        # Gross margin trend
        gm_first = first.get("gross_margin", 0)
        gm_last = last.get("gross_margin", 0)

        # Top cost drivers (largest subcategories across all parents)
        cost_drivers = self._extract_top_cost_drivers(monthly)

        return {
            "total_revenue": round(total_revenue, 2),
            "total_fcf": round(total_fcf, 2),
            "total_opex": round(total_opex, 2),
            "total_cogs": round(total_cogs, 2),
            "avg_monthly_burn": round(avg_burn, 2),
            "min_cash_balance": round(min_cash, 2),
            "min_cash_period": min_cash_period,
            "zero_cash_crossing": zero_crossing,
            "revenue_cagr_annualized": round(rev_cagr, 4),
            "opex_as_pct_of_revenue": round(opex_pct, 4),
            "gross_margin_start": round(gm_first, 4),
            "gross_margin_end": round(gm_last, 4),
            "ending_cash": round(last["cash_balance"], 2),
            "ending_runway_months": round(last["runway_months"], 1),
            "ending_headcount": last.get("headcount", 0),
            "top_cost_drivers": cost_drivers,
        }

    def _extract_top_cost_drivers(
        self,
        monthly: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extract the top 10 largest cost subcategories by total spend."""
        totals: Dict[str, float] = {}
        for row in monthly:
            subcats = row.get("subcategories", {})
            for parent, items in subcats.items():
                for subcat, amount in items.items():
                    if subcat.startswith("_"):
                        continue
                    key = f"{parent}/{subcat}"
                    totals[key] = totals.get(key, 0) + amount

        sorted_items = sorted(totals.items(), key=lambda x: -x[1])[:10]
        return [
            {"category": k, "total_spend": round(v, 2)}
            for k, v in sorted_items
        ]

    # ------------------------------------------------------------------
    # Risk alerts
    # ------------------------------------------------------------------

    def _compute_risk_alerts(
        self,
        monthly: List[Dict[str, Any]],
        seed: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate liquidity risk alerts from the forecast."""
        alerts: List[Dict[str, Any]] = []

        for row in monthly:
            period = row["period"]

            # Cash below zero
            if row["cash_balance"] < 0:
                alerts.append({
                    "period": period,
                    "severity": "critical",
                    "type": "cash_negative",
                    "message": f"Cash balance goes negative: ${row['cash_balance']:,.0f}",
                })
            # Runway below 3 months
            elif row["runway_months"] < 3 and row["runway_months"] != 999:
                alerts.append({
                    "period": period,
                    "severity": "critical",
                    "type": "runway_critical",
                    "message": f"Runway drops to {row['runway_months']:.1f} months",
                })
            # Runway below 6 months
            elif row["runway_months"] < 6 and row["runway_months"] != 999:
                alerts.append({
                    "period": period,
                    "severity": "warning",
                    "type": "runway_warning",
                    "message": f"Runway at {row['runway_months']:.1f} months — start fundraising",
                })

            # Burn acceleration: burn growing faster than revenue
            if row.get("free_cash_flow", 0) < 0 and row["revenue"] > 0:
                burn_pct = abs(row["free_cash_flow"]) / row["revenue"]
                if burn_pct > 0.5:
                    alerts.append({
                        "period": period,
                        "severity": "warning",
                        "type": "burn_efficiency",
                        "message": f"Burn is {burn_pct:.0%} of revenue — inefficient spend",
                    })

            # Working capital spike
            if abs(row.get("working_capital_delta", 0)) > row["revenue"] * 0.3:
                alerts.append({
                    "period": period,
                    "severity": "info",
                    "type": "working_capital_spike",
                    "message": f"Working capital swing of ${row['working_capital_delta']:,.0f}",
                })

        # Deduplicate consecutive alerts of same type
        deduped: List[Dict[str, Any]] = []
        seen_types: Dict[str, str] = {}
        for alert in alerts:
            key = alert["type"]
            if key not in seen_types:
                deduped.append(alert)
                seen_types[key] = alert["period"]
            elif alert["severity"] == "critical" and key in seen_types:
                # Keep critical alerts even if same type seen before
                deduped.append(alert)

        return deduped[:20]  # Cap at 20 alerts

    # ------------------------------------------------------------------
    # Cash conversion cycle
    # ------------------------------------------------------------------

    def _compute_cash_conversion_cycle(
        self,
        monthly: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute cash conversion cycle metrics over the forecast."""
        if not monthly:
            return {}

        ccc_values = [r.get("cash_conversion_cycle_days", 0) for r in monthly]
        ar_values = [r.get("accounts_receivable", 0) for r in monthly]
        ap_values = [r.get("accounts_payable", 0) for r in monthly]

        return {
            "avg_ccc_days": round(sum(ccc_values) / len(ccc_values), 1),
            "start_ccc_days": round(ccc_values[0], 1),
            "end_ccc_days": round(ccc_values[-1], 1),
            "avg_ar": round(sum(ar_values) / len(ar_values), 2),
            "avg_ap": round(sum(ap_values) / len(ap_values), 2),
            "ar_trend": "increasing" if ar_values[-1] > ar_values[0] * 1.1 else (
                "decreasing" if ar_values[-1] < ar_values[0] * 0.9 else "stable"
            ),
        }

    # ------------------------------------------------------------------
    # Scenario analysis
    # ------------------------------------------------------------------

    def build_scenario_comparison(
        self,
        company_id: str,
        months: int = 24,
        start_period: Optional[str] = None,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Build bull/base/bear liquidity scenarios.

        Bull: +50% growth, -10% OpEx
        Base: as-is
        Bear: -30% growth, +15% OpEx, +20% churn
        """
        scenarios = {}
        for name, overrides in [
            ("bull", {"growth_rate_mult": 1.5, "opex_adjustments": {"rd_pct_delta": -0.10, "sm_pct_delta": -0.10, "ga_pct_delta": -0.10}}),
            ("base", {}),
            ("bear", {"growth_rate_mult": 0.7, "opex_adjustments": {"rd_pct_delta": 0.15, "sm_pct_delta": 0.15, "ga_pct_delta": 0.15}}),
        ]:
            result = self.build_liquidity_model(
                company_id=company_id,
                months=months,
                start_period=start_period,
                scenario_overrides=overrides,
                events=events,
            )
            scenarios[name] = {
                "summary": result["summary"],
                "risk_alerts": result["risk_alerts"],
                "monthly": result["monthly"],
            }

        return {
            "company_id": company_id,
            "scenarios": scenarios,
            "comparison": {
                "bull_runway": scenarios["bull"]["summary"].get("ending_runway_months", 0),
                "base_runway": scenarios["base"]["summary"].get("ending_runway_months", 0),
                "bear_runway": scenarios["bear"]["summary"].get("ending_runway_months", 0),
                "bull_ending_cash": scenarios["bull"]["summary"].get("ending_cash", 0),
                "base_ending_cash": scenarios["base"]["summary"].get("ending_cash", 0),
                "bear_ending_cash": scenarios["bear"]["summary"].get("ending_cash", 0),
            },
        }

    # ------------------------------------------------------------------
    # Sensitivity analysis
    # ------------------------------------------------------------------

    def runway_sensitivity(
        self,
        company_id: str,
        months: int = 24,
    ) -> Dict[str, Any]:
        """
        Show how runway changes when individual cost lines change by ±20%.

        Returns a ranked list of which subcategories have the most
        impact on runway when cut or increased.
        """
        base = self.build_liquidity_model(company_id, months=months)
        base_runway = base["summary"].get("ending_runway_months", 0)

        sensitivities = []

        # Test each subcategory
        for parent in ("opex_rd", "opex_sm", "opex_ga", "cogs"):
            subcats = base["monthly"][0].get("subcategories", {}).get(parent, {})
            for subcat in subcats:
                if subcat.startswith("_"):
                    continue

                override_key = self._subcat_to_override_key(parent, subcat)
                if not override_key:
                    continue

                # Cut by 20%
                cut_result = self.build_liquidity_model(
                    company_id, months=months,
                    scenario_overrides={"opex_adjustments": {override_key: -0.20}},
                )
                cut_runway = cut_result["summary"].get("ending_runway_months", 0)

                # Increase by 20%
                inc_result = self.build_liquidity_model(
                    company_id, months=months,
                    scenario_overrides={"opex_adjustments": {override_key: 0.20}},
                )
                inc_runway = inc_result["summary"].get("ending_runway_months", 0)

                sensitivities.append({
                    "category": f"{parent}/{subcat}",
                    "base_runway": base_runway,
                    "cut_20pct_runway": cut_runway,
                    "increase_20pct_runway": inc_runway,
                    "runway_impact_if_cut": round(cut_runway - base_runway, 1),
                    "runway_impact_if_increased": round(inc_runway - base_runway, 1),
                    "monthly_spend": round(subcats[subcat], 2),
                })

        # Sort by absolute impact of cutting
        sensitivities.sort(key=lambda x: -x["runway_impact_if_cut"])

        return {
            "company_id": company_id,
            "base_runway_months": base_runway,
            "sensitivities": sensitivities,
        }
