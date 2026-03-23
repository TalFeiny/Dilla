"""
Cash Flow Planning Service
Composes existing services into a full P&L per year for a company,
including runway calculation and funding gap analysis.

Supports three granularities via build_projection():
- monthly: default for operational planning, runway, cash burn (12-24 month horizon)
- quarterly: board decks, investor updates, QoQ tracking
- annual: long-range strategic planning, 3-5 year models

Data sources:
- RevenueProjectionService: forward revenue with decay + gross margins
- IntelligentGapFiller: burn rate decomposition, stage benchmarks
- CATEGORY_MARGINS from revenue_projection_service
"""

import hashlib
import logging
import math
from datetime import date
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

# Type alias for granularity parameter
Granularity = Literal["monthly", "quarterly", "annual"]


# ---------------------------------------------------------------------------
# OpEx benchmarks by stage (% of revenue)
# Derived from gap_filler burn rate decomposition
# ---------------------------------------------------------------------------

OPEX_BENCHMARKS = {
    "Pre-seed": {
        "rd_pct": 0.80,    # R&D heavy, pre-revenue
        "sm_pct": 0.10,    # minimal sales
        "ga_pct": 0.10,    # minimal G&A
        "capex_pct": 0.02,
    },
    "Seed": {
        "rd_pct": 0.60,
        "sm_pct": 0.20,
        "ga_pct": 0.15,
        "capex_pct": 0.03,
    },
    "Series A": {
        "rd_pct": 0.40,
        "sm_pct": 0.35,
        "ga_pct": 0.15,
        "capex_pct": 0.05,
    },
    "Series B": {
        "rd_pct": 0.30,
        "sm_pct": 0.40,
        "ga_pct": 0.15,
        "capex_pct": 0.05,
    },
    "Series C": {
        "rd_pct": 0.25,
        "sm_pct": 0.40,
        "ga_pct": 0.15,
        "capex_pct": 0.05,
    },
    "Series D": {
        "rd_pct": 0.20,
        "sm_pct": 0.35,
        "ga_pct": 0.15,
        "capex_pct": 0.05,
    },
}

# Stage-based monthly burn estimates for when we have no revenue
STAGE_BURN_MONTHLY = {
    "Pre-seed": 75_000,
    "Seed": 150_000,
    "Series A": 400_000,
    "Series B": 800_000,
    "Series C": 1_500_000,
    "Series D": 2_500_000,
}

# OpEx efficiency improvement per year (costs grow slower than revenue as company scales)
OPEX_EFFICIENCY_RATE = 0.03  # 3% efficiency gain per year


class CashFlowPlanningService:
    """Builds full P&L / cash flow models for companies."""

    def build_cash_flow_model(
        self,
        company_data: Dict[str, Any],
        years: int = 5,
        growth_overrides: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a year-by-year cash flow / P&L model.

        Args:
            company_data: {revenue, arr, inferred_revenue, stage, sector,
                          investor_quality, geography, total_raised, burn_rate,
                          gross_margin, ...}
            years: projection horizon
            growth_overrides: optional per-year growth rates [0.5, 0.4, 0.3, ...]
                              (from scenario tree or user input)

        Returns:
            List of per-year dicts with full P&L breakdown.
        """
        from app.services.revenue_projection_service import RevenueProjectionService

        # Resolve base revenue
        base_revenue = (
            company_data.get("revenue")
            or company_data.get("arr")
            or company_data.get("inferred_revenue")
            or 0
        )

        stage = company_data.get("stage", "Series A")
        sector = company_data.get("sector", "saas")
        growth_rate = company_data.get("growth_rate") or company_data.get("inferred_growth_rate") or 0.30
        growth_rate = max(0.0, min(growth_rate, 3.0))  # Cap to 0-300%

        # Get revenue projections from RevenueProjectionService
        if growth_overrides:
            # Build projections manually using the overrides
            projections = self._build_projections_with_overrides(
                base_revenue, growth_overrides, stage, sector, company_data
            )
        else:
            raw = RevenueProjectionService.project_revenue_with_decay(
                base_revenue=base_revenue,
                initial_growth=growth_rate,
                years=years,
                stage=stage,
                sector=sector,
                investor_quality=company_data.get("investor_quality"),
                geography=company_data.get("geography"),
                market_size_tam=company_data.get("market_size_tam"),
                return_projections=True,
            )
            projections = raw if isinstance(raw, list) else []

        # Analytical metrics (burn_rate, gross_margin, etc.) are computed
        # upstream — by the agent, matrix cells, or seed_forecast_from_actuals.
        # This service is a consumer; it uses what it's given.
        total_raised = company_data.get("total_raised") or 0
        burn_estimated = False
        burn_monthly = company_data.get("burn_rate")
        if not burn_monthly:
            burn_monthly = STAGE_BURN_MONTHLY.get(stage, 400_000)
            burn_estimated = True
            logger.warning(
                "burn_rate not provided for %s — using stage default $%s/mo. "
                "Compute upstream via seed_forecast_from_actuals or suggestions.",
                company_data.get("company_id", "unknown"), f"{burn_monthly:,.0f}",
            )
        cash_balance = company_data.get("cash_balance") or max(0, total_raised - burn_monthly * 6)

        opex_bench = OPEX_BENCHMARKS.get(stage, OPEX_BENCHMARKS["Series A"])
        override_margin = company_data.get("gross_margin")

        results: List[Dict[str, Any]] = []

        for i, proj in enumerate(projections[:years]):
            year = proj.get("year", i + 1)
            revenue = proj.get("revenue", 0)
            proj_growth = proj.get("growth_rate", 0)
            gross_margin = override_margin or proj.get("gross_margin", 0.65)

            cogs = revenue * (1 - gross_margin)
            gross_profit = revenue * gross_margin

            # OpEx with compounding efficiency improvement over time
            eff = (1 - OPEX_EFFICIENCY_RATE) ** i
            rd_spend = revenue * opex_bench["rd_pct"] * eff if revenue > 0 else burn_monthly * 12 * opex_bench["rd_pct"]
            sm_spend = revenue * opex_bench["sm_pct"] * eff if revenue > 0 else burn_monthly * 12 * opex_bench["sm_pct"]
            ga_spend = revenue * opex_bench["ga_pct"] * eff if revenue > 0 else burn_monthly * 12 * opex_bench["ga_pct"]
            total_opex = rd_spend + sm_spend + ga_spend

            ebitda = gross_profit - total_opex
            ebitda_margin = ebitda / revenue if revenue > 0 else -1.0

            capex = revenue * opex_bench.get("capex_pct", 0.05) if revenue > 0 else burn_monthly * 12 * 0.05
            free_cash_flow = ebitda - capex

            cash_balance += free_cash_flow
            runway_months = (cash_balance / (-free_cash_flow / 12)) if free_cash_flow < 0 else 999

            entry = {
                "year": year,
                "revenue": round(revenue, 2),
                "growth_rate": round(proj_growth, 4),
                "cogs": round(cogs, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_margin": round(gross_margin, 4),
                "rd_spend": round(rd_spend, 2),
                "sm_spend": round(sm_spend, 2),
                "ga_spend": round(ga_spend, 2),
                "total_opex": round(total_opex, 2),
                "ebitda": round(ebitda, 2),
                "ebitda_margin": round(ebitda_margin, 4),
                "capex": round(capex, 2),
                "free_cash_flow": round(free_cash_flow, 2),
                "cash_balance": round(cash_balance, 2),
                "runway_months": round(max(0, runway_months), 1),
                "funding_gap": round(max(0, -cash_balance), 2) if cash_balance < 0 else 0,
            }
            if burn_estimated and revenue == 0:
                entry["_warning"] = f"OpEx derived from stage-default burn (${burn_monthly:,.0f}/mo) — no actuals available"
            results.append(entry)

        return results

    def calculate_runway(self, cash_flow_model: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate months until cash balance hits 0."""
        for entry in cash_flow_model:
            if entry["cash_balance"] <= 0:
                return {
                    "runs_out_year": entry["year"],
                    "runway_months": entry.get("runway_months", 0),
                    "funding_gap": entry.get("funding_gap", 0),
                    "status": "needs_funding",
                }

        last = cash_flow_model[-1] if cash_flow_model else {}
        return {
            "runs_out_year": None,
            "runway_months": last.get("runway_months", 999),
            "funding_gap": 0,
            "status": "sufficient_runway",
        }

    def calculate_funding_gap(
        self,
        cash_flow_model: List[Dict[str, Any]],
        target_runway_months: int = 18,
    ) -> Dict[str, Any]:
        """How much needs to be raised and when to maintain target runway."""
        gaps = []
        for entry in cash_flow_model:
            if entry["runway_months"] < target_runway_months and entry["free_cash_flow"] < 0:
                monthly_burn = -entry["free_cash_flow"] / 12
                needed = monthly_burn * target_runway_months - max(0, entry["cash_balance"])
                gaps.append({
                    "year": entry["year"],
                    "amount_needed": round(max(0, needed), 2),
                    "monthly_burn": round(monthly_burn, 2),
                    "current_cash": round(entry["cash_balance"], 2),
                })

        return {
            "needs_funding": len(gaps) > 0,
            "gaps": gaps,
            "total_funding_needed": sum(g["amount_needed"] for g in gaps),
            "earliest_need_year": gaps[0]["year"] if gaps else None,
        }

    def to_waterfall_chart_data(self, cash_flow_year: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a single year's P&L to waterfall chart data."""
        return {
            "type": "cash_flow_waterfall",
            "data": [
                {"name": "Revenue", "value": cash_flow_year["revenue"]},
                {"name": "COGS", "value": -cash_flow_year["cogs"]},
                {"name": "Gross Profit", "value": cash_flow_year["gross_profit"], "isSubtotal": True},
                {"name": "R&D", "value": -cash_flow_year["rd_spend"]},
                {"name": "Sales & Marketing", "value": -cash_flow_year["sm_spend"]},
                {"name": "G&A", "value": -cash_flow_year["ga_spend"]},
                {"name": "EBITDA", "value": cash_flow_year["ebitda"], "isSubtotal": True},
                {"name": "CapEx", "value": -cash_flow_year["capex"]},
                {"name": "Free Cash Flow", "value": cash_flow_year["free_cash_flow"], "isSubtotal": True},
            ],
        }

    def to_memo_sections(
        self,
        company_name: str,
        cash_flow_model: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate memo sections from cash flow model."""
        runway = self.calculate_runway(cash_flow_model)
        funding_gap = self.calculate_funding_gap(cash_flow_model)

        # Summary
        first = cash_flow_model[0] if cash_flow_model else {}
        last = cash_flow_model[-1] if cash_flow_model else {}

        summary_lines = [
            f"Revenue grows from ${first.get('revenue', 0)/1e6:.1f}M to ${last.get('revenue', 0)/1e6:.1f}M over {len(cash_flow_model)} years.",
            f"EBITDA margin improves from {first.get('ebitda_margin', 0):.0%} to {last.get('ebitda_margin', 0):.0%}.",
        ]

        if runway["status"] == "needs_funding":
            summary_lines.append(
                f"Cash runs out in Year {runway['runs_out_year']} — funding gap of ${runway['funding_gap']/1e6:.1f}M."
            )
        else:
            summary_lines.append("Sufficient runway across projection period.")

        if funding_gap["needs_funding"]:
            summary_lines.append(
                f"Total funding needed: ${funding_gap['total_funding_needed']/1e6:.1f}M (earliest: Year {funding_gap['earliest_need_year']})."
            )

        # Waterfall for last projected year
        waterfall = self.to_waterfall_chart_data(last) if last else None

        sections = [
            {"type": "heading2", "content": f"Cash Flow Model: {company_name}"},
            {"type": "paragraph", "content": "\n".join(summary_lines)},
            {
                "type": "table",
                "table": {
                    "headers": ["Year", "Revenue", "Gross Margin", "EBITDA", "EBITDA Margin", "FCF", "Cash", "Runway"],
                    "rows": [
                        [
                            f"Y{e['year']}",
                            f"${e['revenue']/1e6:.1f}M",
                            f"{e['gross_margin']:.0%}",
                            f"${e['ebitda']/1e6:.1f}M",
                            f"{e['ebitda_margin']:.0%}",
                            f"${e['free_cash_flow']/1e6:.1f}M",
                            f"${e['cash_balance']/1e6:.1f}M",
                            f"{e['runway_months']:.0f}mo" if e['runway_months'] < 999 else "∞",
                        ]
                        for e in cash_flow_model
                    ],
                },
            },
        ]

        if waterfall:
            sections.append({"type": "chart", "chart": waterfall})

        return sections

    def build_monthly_cash_flow_model(
        self,
        company_data: Dict[str, Any],
        months: int = 24,
        monthly_overrides: Optional[Dict[str, float]] = None,
        start_period: Optional[str] = None,
        revenue_trajectory: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a month-by-month P&L / cash flow model.

        Same logic as build_cash_flow_model but at monthly granularity.
        Uses RevenueProjectionService.project_revenue_monthly() for revenue,
        then applies OpEx benchmarks and computes EBITDA/FCF/runway per month.

        When revenue_trajectory is provided, those revenue values are used
        directly instead of computing from growth rates. This allows
        regression-fitted revenue (gompertz, logistic, etc.) to cascade
        through the full P&L.

        Driver-engine extensions (read from company_data):
        - churn_rate / nrr / pricing_pct_change / new_customer_growth_rate / acv_override:
          Customer-level revenue model layered on top of growth-rate model.
        - cac_override: Derives S&M spend from new_customers * CAC.
        - sales_cycle_months: Delays new-customer revenue recognition by N months.
        - cost_per_head: Replaces hardcoded COST_PER_HEAD_MONTHLY.
        - hiring_plan_monthly: Time-distributed headcount additions.
        - capex_override: Absolute $ capex instead of % of revenue.
        - debt_service_monthly / interest_rate / outstanding_debt: Debt line below EBITDA.
        - tax_rate: net_income = ebitda * (1 - tax_rate).
        - dso / dpo / dio: Cash conversion cycle (replaces working_capital_days).
          DSO = days sales outstanding, DPO = days payable, DIO = days inventory.
        - events: List[Dict] — discrete liquidity events injected at specific periods:
          [{"period": "YYYY-MM", "type": "funding|debt_drawdown|one_time_cost|one_time_revenue",
            "amount": float, "label": str}]

        Args:
            company_data: same shape as build_cash_flow_model, plus new driver keys
            months: projection horizon in months
            monthly_overrides: {"YYYY-MM": annual_growth_rate} overrides
            start_period: "YYYY-MM" start month (defaults to next month)
            revenue_trajectory: optional list of {"period": "YYYY-MM", "revenue": float}
                                dicts from regression. When provided, overrides
                                the growth-rate model for revenue.

        Returns:
            List of per-month dicts with full P&L breakdown.
        """
        from app.services.revenue_projection_service import RevenueProjectionService

        base_revenue = (
            company_data.get("revenue")
            or company_data.get("arr")
            or company_data.get("inferred_revenue")
            or 0
        )

        stage = company_data.get("stage", "Series A")
        growth_rate = company_data.get("growth_rate") or company_data.get("inferred_growth_rate") or 0.30
        # Cap initial growth rate to prevent runaway forecasts
        growth_rate = max(0.0, min(growth_rate, 3.0))  # 0% to 300% max

        # If regression-fitted revenue trajectory is provided, build period
        # stubs from it instead of the growth-rate model
        if revenue_trajectory:
            rev_projections = []
            for entry in revenue_trajectory[:months]:
                rev_projections.append({
                    "period": entry.get("period", f"M{len(rev_projections)+1}"),
                    "revenue": entry["revenue"],
                    "gross_margin": company_data.get("gross_margin", 0.65),
                    "growth_rate_annual": 0,  # not meaningful for regression
                })
            # Pad if trajectory is shorter than requested months
            if len(rev_projections) < months:
                last_rev = rev_projections[-1]["revenue"] if rev_projections else 0
                last_period = rev_projections[-1]["period"] if rev_projections else start_period or "2025-01"
                from dateutil.relativedelta import relativedelta
                from app.core.date_utils import parse_period_to_date
                last_dt = parse_period_to_date(last_period)
                for i in range(len(rev_projections), months):
                    next_dt = last_dt + relativedelta(months=i - len(revenue_trajectory) + 1)
                    rev_projections.append({
                        "period": next_dt.strftime("%Y-%m"),
                        "revenue": last_rev,  # flat beyond trajectory
                        "gross_margin": company_data.get("gross_margin", 0.65),
                        "growth_rate_annual": 0,
                    })
        else:
            # Get monthly revenue projections (growth-rate model)
            rev_projections = RevenueProjectionService.project_revenue_monthly(
                base_revenue_annual=base_revenue,
                initial_growth=growth_rate,
                months=months,
                stage=stage,
                sector=company_data.get("sector", "saas"),
                investor_quality=company_data.get("investor_quality"),
                geography=company_data.get("geography"),
                monthly_overrides=monthly_overrides,
                start_period=start_period,
            )

        # Analytical metrics are computed upstream (see annual model comment).
        total_raised = company_data.get("total_raised") or 0
        burn_monthly = company_data.get("burn_rate")
        if not burn_monthly:
            burn_monthly = STAGE_BURN_MONTHLY.get(stage, 400_000)
            logger.warning(
                "burn_rate not provided for %s (monthly model) — using stage default $%s/mo.",
                company_data.get("company_id", "unknown"), f"{burn_monthly:,.0f}",
            )
        cash_balance = company_data.get("cash_balance") or max(0, total_raised - burn_monthly * 6)

        opex_bench = dict(OPEX_BENCHMARKS.get(stage, OPEX_BENCHMARKS["Series A"]))

        # ── Actuals-anchored OpEx engine ─────────────────────────────
        # When trailing actuals exist, use absolute monthly amounts as
        # the forecast base and grow them at a dampened rate (operating
        # leverage: OpEx grows slower than revenue). Only fall back to
        # stage-benchmark percentages when zero actuals are available.
        actual_rd = company_data.get("_rd_spend")
        actual_sm = company_data.get("_sm_spend")
        actual_ga = company_data.get("_ga_spend")
        _opex_from_actuals = any(
            v is not None and v > 0 for v in [actual_rd, actual_sm, actual_ga]
        )
        if _opex_from_actuals:
            _actual_rd_base = actual_rd or 0
            _actual_sm_base = actual_sm or 0
            _actual_ga_base = actual_ga or 0
            # OpEx grows at 70% of revenue growth rate (operating leverage)
            _opex_growth_monthly = (growth_rate * 0.7) / 12
        else:
            _actual_rd_base = _actual_sm_base = _actual_ga_base = 0
            _opex_growth_monthly = 0

        override_margin = company_data.get("gross_margin")

        # ── New driver inputs (with bounds validation) ─────────────────
        churn_rate = company_data.get("churn_rate")              # monthly churn
        nrr = company_data.get("nrr")                            # e.g. 1.10
        pricing_pct = company_data.get("pricing_pct_change")     # e.g. 0.10
        new_cust_growth = company_data.get("new_customer_growth_rate")
        acv = company_data.get("acv_override")

        # Validate driver inputs to prevent runaway forecasts
        if churn_rate is not None:
            churn_rate = max(0.0, min(churn_rate, 0.20))  # 0-20% monthly churn
        if nrr is not None:
            nrr = max(0.50, min(nrr, 1.60))  # 50%-160% NRR (160% = best-in-class like Snowflake)
        if pricing_pct is not None:
            pricing_pct = max(-0.20, min(pricing_pct, 0.30))  # -20% to +30% annual pricing change
        if new_cust_growth is not None:
            new_cust_growth = max(0.0, min(new_cust_growth, 0.15))  # 0-15% monthly new customer growth
        cac = company_data.get("cac_override")
        sales_cycle = company_data.get("sales_cycle_months") or 0
        cost_per_head = company_data.get("cost_per_head") or 15_000
        hiring_monthly = company_data.get("hiring_plan_monthly") or 0
        capex_abs = company_data.get("capex_override")
        debt_service = company_data.get("debt_service_monthly") or 0
        interest_rate_annual = company_data.get("interest_rate") or 0
        outstanding_debt = company_data.get("outstanding_debt") or 0
        tax_rate = company_data.get("tax_rate") or 0
        # ── Working capital timing (DSO/DPO/DIO) ────────────────────
        # Replace the single wc_days param with proper cash conversion
        # cycle drivers. DSO/DPO/DIO already exist in driver_registry.py
        # but weren't wired through to cash flow. Falls back to wc_days
        # for backward compatibility.
        dso = company_data.get("dso") or company_data.get("working_capital_days") or 0
        dpo = company_data.get("dpo") or 0
        dio = company_data.get("dio") or 0

        # Customer-level revenue model state (only active when drivers set)
        use_customer_model = any(v is not None for v in [churn_rate, nrr, new_cust_growth, acv])
        if use_customer_model and acv and acv > 0:
            existing_customers = (base_revenue / 12) / (acv / 12) if acv else 0
        else:
            existing_customers = 0
        new_customers_pipeline: List[float] = []  # queue for sales_cycle delay
        cumulative_headcount_delta = 0
        # Working capital state (AR/AP/Inventory)
        prev_ar = 0.0
        prev_ap = 0.0
        prev_inv = 0.0

        # ── Liquidity events index ───────────────────────────────────
        # Events inject funding, debt drawdowns, or one-time costs at
        # specific periods instead of everything being a smooth formula.
        _events: List[Dict[str, Any]] = company_data.get("events") or []
        _events_by_period: Dict[str, List[Dict[str, Any]]] = {}
        for evt in _events:
            p = evt.get("period", "")
            _events_by_period.setdefault(p, []).append(evt)

        results: List[Dict[str, Any]] = []

        for i, proj in enumerate(rev_projections):
            revenue = proj.get("revenue", 0)
            gross_margin = override_margin or proj.get("gross_margin", 0.65)

            # ── Customer-level revenue overlay ─────────────────────────
            if use_customer_model and acv and acv > 0:
                monthly_acv = acv / 12

                # Existing customer revenue (churn + NRR)
                if churn_rate is not None:
                    existing_customers *= (1 - churn_rate)
                retention_mult = (nrr or 1.0) ** (1 / 12)  # monthly compounding
                existing_rev = existing_customers * monthly_acv * retention_mult

                # New customers this month
                new_this_month = 0.0
                if new_cust_growth is not None:
                    new_this_month = existing_customers * new_cust_growth
                    new_customers_pipeline.append(new_this_month)
                    # Sales cycle delay: only recognize revenue after N months
                    if len(new_customers_pipeline) > sales_cycle:
                        recognized = new_customers_pipeline[-(sales_cycle + 1)]
                        existing_customers += recognized
                    else:
                        recognized = 0
                elif i == 0:
                    new_customers_pipeline.append(0)

                new_rev = recognized * monthly_acv if new_cust_growth is not None else 0

                # Pricing uplift on all revenue
                pricing_mult = 1 + (pricing_pct or 0)
                customer_revenue = (existing_rev + new_rev) * pricing_mult

                # Use customer model revenue if it's non-zero, else fallback
                if customer_revenue > 0:
                    revenue = customer_revenue

            cogs = revenue * (1 - gross_margin)
            gross_profit = revenue * gross_margin

            # ── OpEx with compounding efficiency improvement ────────────
            # Compound decay instead of linear: costs as % of revenue shrink
            # geometrically, allowing EBITDA to turn positive at scale
            eff = (1 - OPEX_EFFICIENCY_RATE) ** (i / 12.0)

            # Deterministic per-month variance so OpEx doesn't look like a
            # smooth straight line.  Uses a hash of (company_id, month_index,
            # category) to produce a stable jitter of +/- ~5 %.
            def _opex_jitter(cat: str, month_idx: int) -> float:
                seed = hashlib.md5(f"{company_data.get('company_id','')}-{month_idx}-{cat}".encode()).hexdigest()
                # Map first 8 hex chars to [-0.05, +0.05]
                norm = int(seed[:8], 16) / 0xFFFFFFFF  # 0..1
                return 1.0 + (norm - 0.5) * 0.10  # 0.95..1.05

            # CAC-driven S&M: if CAC is set, derive from new_customers * CAC
            if cac is not None and new_customers_pipeline:
                raw_new = new_customers_pipeline[-1] if new_customers_pipeline else 0
                sm_spend_computed = raw_new * cac
            else:
                sm_spend_computed = None

            if _opex_from_actuals:
                # Actuals-anchored: grow absolute base at dampened rate
                opex_growth = (1 + _opex_growth_monthly) ** i
                rd_spend = _actual_rd_base * opex_growth * _opex_jitter("rd", i)
                sm_spend = (sm_spend_computed if sm_spend_computed is not None
                            else _actual_sm_base * opex_growth * _opex_jitter("sm", i))
                ga_spend = _actual_ga_base * opex_growth * _opex_jitter("ga", i)
            elif revenue > 0:
                # No actuals: fall back to stage-benchmark percentages
                rd_spend = revenue * opex_bench["rd_pct"] * eff * _opex_jitter("rd", i)
                sm_spend = sm_spend_computed if sm_spend_computed is not None else revenue * opex_bench["sm_pct"] * eff * _opex_jitter("sm", i)
                ga_spend = revenue * opex_bench["ga_pct"] * eff * _opex_jitter("ga", i)
            else:
                rd_spend = burn_monthly * opex_bench["rd_pct"] * _opex_jitter("rd", i)
                sm_spend = sm_spend_computed if sm_spend_computed is not None else burn_monthly * opex_bench["sm_pct"] * _opex_jitter("sm", i)
                ga_spend = burn_monthly * opex_bench["ga_pct"] * _opex_jitter("ga", i)

            # Hiring plan: time-distributed headcount additions
            if hiring_monthly:
                cumulative_headcount_delta += hiring_monthly
                rd_spend += cumulative_headcount_delta * cost_per_head * opex_bench["rd_pct"]

            total_opex = rd_spend + sm_spend + ga_spend

            ebitda = gross_profit - total_opex
            ebitda_margin = ebitda / revenue if revenue > 0 else -1.0

            # ── Capex (absolute override or % of revenue) ─────────────
            if capex_abs is not None:
                capex = capex_abs
            else:
                capex = revenue * opex_bench.get("capex_pct", 0.05) if revenue > 0 else burn_monthly * 0.05

            # ── Debt service + interest ────────────────────────────────
            interest_payment = outstanding_debt * (interest_rate_annual / 12)
            total_debt_payment = debt_service + interest_payment
            if debt_service > 0:
                outstanding_debt = max(0, outstanding_debt - debt_service)

            # ── Tax ────────────────────────────────────────────────────
            pre_tax_income = ebitda - capex - total_debt_payment
            tax_expense = max(0, pre_tax_income * tax_rate) if tax_rate and pre_tax_income > 0 else 0
            net_income = pre_tax_income - tax_expense

            free_cash_flow = net_income

            # ── Working capital via DSO/DPO/DIO cash conversion cycle ────
            # DSO: revenue tied up in receivables (delays cash collection)
            # DPO: expenses deferred via payables (delays cash outflow)
            # DIO: COGS tied up in inventory (ties up cash)
            # Net WC delta = change in (AR + Inventory - AP)
            ar = (revenue / 30) * dso if dso else 0
            ap = ((cogs + total_opex) / 30) * dpo if dpo else 0
            inv = (cogs / 30) * dio if dio else 0
            wc_delta = (ar - prev_ar) + (inv - prev_inv) - (ap - prev_ap)
            prev_ar, prev_ap, prev_inv = ar, ap, inv
            free_cash_flow -= wc_delta

            cash_balance += free_cash_flow

            # ── Liquidity events layer ───────────────────────────────────
            # Inject discrete events (funding rounds, debt drawdowns,
            # one-time costs/revenue) at specific periods instead of
            # everything being a smooth formula.
            current_period = proj.get("period", "")
            period_events = _events_by_period.get(current_period, [])
            event_impact = 0.0
            for evt in period_events:
                evt_type = evt.get("type", "")
                evt_amount = float(evt.get("amount", 0))
                evt_label = evt.get("label", evt_type)
                if evt_type == "funding":
                    cash_balance += evt_amount
                    event_impact += evt_amount
                    logger.info("Liquidity event [%s]: %s +$%s", current_period, evt_label, f"{evt_amount:,.0f}")
                elif evt_type == "debt_drawdown":
                    cash_balance += evt_amount
                    outstanding_debt += evt_amount
                    event_impact += evt_amount
                    logger.info("Liquidity event [%s]: %s +$%s (debt)", current_period, evt_label, f"{evt_amount:,.0f}")
                elif evt_type in ("one_time_cost", "one_time_revenue"):
                    cash_balance += evt_amount  # negative for costs
                    event_impact += evt_amount
                    logger.info("Liquidity event [%s]: %s $%s", current_period, evt_label, f"{evt_amount:,.0f}")

            runway_months = (cash_balance / (-free_cash_flow)) if free_cash_flow < 0 else 999

            results.append({
                "period": proj.get("period", f"M{i+1}"),
                "revenue": round(revenue, 2),
                "growth_rate_annual": proj.get("growth_rate_annual", 0),
                "cogs": round(cogs, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_margin": round(gross_margin, 4),
                "rd_spend": round(rd_spend, 2),
                "sm_spend": round(sm_spend, 2),
                "ga_spend": round(ga_spend, 2),
                "total_opex": round(total_opex, 2),
                "ebitda": round(ebitda, 2),
                "ebitda_margin": round(ebitda_margin, 4),
                "capex": round(capex, 2),
                "debt_service": round(total_debt_payment, 2),
                "tax_expense": round(tax_expense, 2),
                "net_income": round(net_income, 2),
                "free_cash_flow": round(free_cash_flow, 2),
                # Working capital breakdown (DSO/DPO/DIO)
                "accounts_receivable": round(ar, 2),
                "accounts_payable": round(ap, 2),
                "inventory": round(inv, 2),
                "working_capital_delta": round(wc_delta, 2),
                # Liquidity events
                "event_impact": round(event_impact, 2),
                "cash_balance": round(cash_balance, 2),
                "runway_months": round(max(0, runway_months), 1),
            })

        # ── Subcategory decomposition with driver overrides ──────────
        # Decompose parent OpEx/COGS into subcategory line items. When
        # subcategory driver overrides exist (e.g., "cut engineering by 20%"),
        # apply them to the individual subcategory and recalculate the parent.
        _proportions_cache: Dict[str, Dict[str, float]] = {}

        # Prefer pre-computed proportions from seed data
        _seed_props = company_data.get("_subcategory_proportions")
        if _seed_props:
            _proportions_cache = _seed_props

        # Fall back to live query
        _company_id = company_data.get("company_id")
        if not _proportions_cache and _company_id:
            try:
                from app.services.actuals_ingestion import get_subcategory_proportions
                for cat in ("opex_rd", "opex_sm", "opex_ga", "cogs"):
                    props = get_subcategory_proportions(_company_id, cat)
                    if props:
                        _proportions_cache[cat] = props
            except Exception as e:
                logger.debug("Subcategory proportions query failed: %s", e)

        if _proportions_cache:
            _opex_adj = company_data.get("opex_adjustments") or {}
            # Map driver keys → subcategory names
            _DRIVER_TO_SUBCAT = {
                "rd_engineering_salaries_delta": ("opex_rd", "engineering_salaries"),
                "rd_infra_cloud_delta": ("opex_rd", "infra_cloud"),
                "rd_tools_licenses_delta": ("opex_rd", "tools_licenses"),
                "rd_contractor_delta": ("opex_rd", "contractor"),
                "sm_paid_acquisition_delta": ("opex_sm", "paid_acquisition"),
                "sm_content_marketing_delta": ("opex_sm", "content_marketing"),
                "sm_sales_salaries_delta": ("opex_sm", "sales_salaries"),
                "sm_events_delta": ("opex_sm", "events"),
                "ga_finance_legal_delta": ("opex_ga", "finance_legal"),
                "ga_office_delta": ("opex_ga", "office"),
                "ga_admin_salaries_delta": ("opex_ga", "admin_salaries"),
                "cogs_hosting_delta": ("cogs", "hosting"),
                "cogs_support_salaries_delta": ("cogs", "support_salaries"),
                "cogs_payment_processing_delta": ("cogs", "payment_processing"),
                "cogs_third_party_apis_delta": ("cogs", "third_party_apis"),
            }

            cat_to_field = {
                "opex_rd": "rd_spend", "opex_sm": "sm_spend",
                "opex_ga": "ga_spend", "cogs": "cogs",
            }

            try:
                for row in results:
                    subcategories: Dict[str, Dict[str, float]] = {}
                    parent_adjustments: Dict[str, float] = {}

                    for cat, props in _proportions_cache.items():
                        field = cat_to_field.get(cat, cat)
                        cat_total = row.get(field, 0)
                        if not cat_total:
                            continue

                        sub_items: Dict[str, float] = {}
                        adjusted_total = 0.0
                        for sub, pct in props.items():
                            base_amount = cat_total * pct
                            # Apply subcategory driver override if present
                            for drv_key, (drv_cat, drv_sub) in _DRIVER_TO_SUBCAT.items():
                                if drv_cat == cat and drv_sub == sub and drv_key in _opex_adj:
                                    delta = float(_opex_adj[drv_key])
                                    base_amount *= (1 + delta)
                                    break
                            sub_items[sub] = round(base_amount, 2)
                            adjusted_total += base_amount

                        subcategories[cat] = sub_items
                        # If overrides changed the total, propagate back to parent
                        if abs(adjusted_total - cat_total) > 0.01:
                            parent_adjustments[field] = round(adjusted_total, 2)

                    if subcategories:
                        row["subcategories"] = subcategories
                    # Propagate subcategory adjustments to parent totals
                    for field, new_total in parent_adjustments.items():
                        row[field] = new_total
                    if parent_adjustments:
                        row["total_opex"] = round(
                            row.get("rd_spend", 0) + row.get("sm_spend", 0) + row.get("ga_spend", 0), 2
                        )
                        row["ebitda"] = round(row.get("gross_profit", 0) - row["total_opex"], 2)
            except Exception as e:
                logger.debug("Subcategory decomposition skipped: %s", e)

        # ── Seasonality overlay ──────────────────────────────────────
        # Apply detected seasonal patterns to adjust revenue forecasts.
        # Only applies when: (a) we have a company_id, (b) enough actuals
        # exist to detect a pattern, (c) seasonality_factors is not "none".
        seasonality_setting = company_data.get("seasonality_factors", "auto")
        if seasonality_setting != "none" and company_data.get("company_id"):
            try:
                from app.services.seasonality_engine import SeasonalityEngine
                se = SeasonalityEngine()
                pattern = se.detect_pattern(
                    company_data["company_id"], metric="revenue",
                )
                if pattern and pattern.confidence > 0.6:
                    results = se.apply_seasonal_factors(results, pattern)
                    logger.debug(
                        "Applied seasonal factors (strength=%.2f, confidence=%.2f)",
                        pattern.strength, pattern.confidence,
                    )
            except Exception as e:
                logger.debug("Seasonality overlay skipped: %s", e)

        return results

    # ------------------------------------------------------------------
    # Unified projection engine
    # ------------------------------------------------------------------

    def build_projection(
        self,
        company_data: Dict[str, Any],
        granularity: Granularity = "monthly",
        horizon: Optional[int] = None,
        growth_overrides: Optional[List[float]] = None,
        monthly_overrides: Optional[Dict[str, float]] = None,
        start_period: Optional[str] = None,
        revenue_trajectory: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Unified projection engine. Runs monthly internally, then aggregates
        to the requested granularity.

        Args:
            company_data: company dict with revenue, stage, growth_rate, etc.
            granularity: "monthly" | "quarterly" | "annual"
            horizon: number of periods at the target granularity.
                     Defaults: monthly=24, quarterly=8, annual=5
            growth_overrides: per-year growth rate list (annual model compat)
            monthly_overrides: {"YYYY-MM": rate} per-month overrides
            start_period: "YYYY-MM" start (defaults to next month)
            revenue_trajectory: optional regression-fitted revenue values to
                                cascade through the P&L instead of growth-rate model

        Returns:
            List of period dicts with full P&L breakdown at requested granularity.
        """
        # Default horizons
        if horizon is None:
            horizon = {"monthly": 24, "quarterly": 8, "annual": 5}[granularity]

        # Convert horizon to months
        months_needed = {
            "monthly": horizon,
            "quarterly": horizon * 3,
            "annual": horizon * 12,
        }[granularity]

        # If caller passed annual growth_overrides, convert to monthly_overrides
        if growth_overrides and not monthly_overrides:
            monthly_overrides = self._annual_overrides_to_monthly(
                growth_overrides, start_period, months_needed
            )

        # Build at monthly grain — this is always the source of truth
        monthly = self.build_monthly_cash_flow_model(
            company_data,
            months=months_needed,
            monthly_overrides=monthly_overrides,
            start_period=start_period,
            revenue_trajectory=revenue_trajectory,
        )

        if granularity == "monthly":
            return monthly
        elif granularity == "quarterly":
            return self._aggregate_to_quarterly(monthly)
        else:  # annual
            return self._aggregate_to_annual(monthly)

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_to_quarterly(monthly: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Roll up monthly P&L to quarterly. Flow items sum, stock items take end-of-quarter."""
        from itertools import groupby

        def quarter_key(m: Dict[str, Any]) -> str:
            period = m.get("period", "")
            if len(period) >= 7:
                y, mo = int(period[:4]), int(period[5:7])
                q = (mo - 1) // 3 + 1
                return f"{y}-Q{q}"
            return "unknown"

        _FLOW_KEYS = [
            "revenue", "cogs", "gross_profit",
            "rd_spend", "sm_spend", "ga_spend", "total_opex",
            "ebitda", "capex", "free_cash_flow",
        ]
        _STOCK_KEYS = ["cash_balance", "runway_months"]

        quarters: List[Dict[str, Any]] = []
        for qk, group in groupby(monthly, key=quarter_key):
            months_in_q = list(group)
            if not months_in_q:
                continue

            row: Dict[str, Any] = {"period": qk}

            # Sum flow items
            for k in _FLOW_KEYS:
                row[k] = round(sum(m.get(k, 0) for m in months_in_q), 2)

            # Stock items: take last month of quarter
            last = months_in_q[-1]
            for k in _STOCK_KEYS:
                row[k] = last.get(k, 0)

            # Derived ratios
            row["gross_margin"] = (
                round(row["gross_profit"] / row["revenue"], 4)
                if row["revenue"] > 0 else 0
            )
            row["ebitda_margin"] = (
                round(row["ebitda"] / row["revenue"], 4)
                if row["revenue"] > 0 else -1.0
            )
            # Carry the average annual growth rate for the quarter
            rates = [m.get("growth_rate_annual", 0) for m in months_in_q]
            row["growth_rate_annual"] = round(sum(rates) / len(rates), 4) if rates else 0

            quarters.append(row)

        return quarters

    @staticmethod
    def _aggregate_to_annual(monthly: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Roll up monthly P&L to annual. Flow items sum, stock items take year-end."""
        from itertools import groupby

        def year_key(m: Dict[str, Any]) -> str:
            period = m.get("period", "")
            return period[:4] if len(period) >= 4 else "unknown"

        _FLOW_KEYS = [
            "revenue", "cogs", "gross_profit",
            "rd_spend", "sm_spend", "ga_spend", "total_opex",
            "ebitda", "capex", "free_cash_flow",
        ]
        _STOCK_KEYS = ["cash_balance", "runway_months"]

        years: List[Dict[str, Any]] = []
        for yk, group in groupby(monthly, key=year_key):
            months_in_y = list(group)
            if not months_in_y:
                continue

            row: Dict[str, Any] = {"period": yk, "year": len(years) + 1}

            for k in _FLOW_KEYS:
                row[k] = round(sum(m.get(k, 0) for m in months_in_y), 2)

            last = months_in_y[-1]
            for k in _STOCK_KEYS:
                row[k] = last.get(k, 0)

            row["gross_margin"] = (
                round(row["gross_profit"] / row["revenue"], 4)
                if row["revenue"] > 0 else 0
            )
            row["ebitda_margin"] = (
                round(row["ebitda"] / row["revenue"], 4)
                if row["revenue"] > 0 else -1.0
            )
            rates = [m.get("growth_rate_annual", 0) for m in months_in_y]
            row["growth_rate"] = round(sum(rates) / len(rates), 4) if rates else 0

            years.append(row)

        return years

    @staticmethod
    def _annual_overrides_to_monthly(
        growth_overrides: List[float],
        start_period: Optional[str],
        months: int,
    ) -> Dict[str, float]:
        """Convert per-year growth rate list to monthly override dict."""
        if not start_period:
            today = date.today()
            start_period = f"{today.year}-{today.month:02d}"

        y, m = int(start_period[:4]), int(start_period[5:7])
        overrides: Dict[str, float] = {}
        for i in range(months):
            year_idx = i // 12
            rate = growth_overrides[min(year_idx, len(growth_overrides) - 1)]
            period = f"{y + (m + i - 1) // 12}-{(m + i - 1) % 12 + 1:02d}"
            overrides[period] = rate
        return overrides

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def build_three_scenario_model(
        self,
        company_data: Dict[str, Any],
        years: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Build bull/base/bear P&L models side by side."""
        return {
            "bull": self.build_cash_flow_model_with_scenario(company_data, years, scenario="bull"),
            "base": self.build_cash_flow_model_with_scenario(company_data, years, scenario="base"),
            "bear": self.build_cash_flow_model_with_scenario(company_data, years, scenario="bear"),
        }

    def build_cash_flow_model_with_scenario(
        self,
        company_data: Dict[str, Any],
        years: int = 5,
        growth_overrides: Optional[List[float]] = None,
        scenario: str = "base",
    ) -> List[Dict[str, Any]]:
        """Wrapper that applies bull/bear scenario adjustments to growth."""
        from app.services.revenue_projection_service import RevenueProjectionService

        base_revenue = (
            company_data.get("revenue") or company_data.get("arr")
            or company_data.get("inferred_revenue") or 0
        )
        stage = company_data.get("stage", "Series A")
        sector = company_data.get("sector", "saas")
        growth_rate = company_data.get("growth_rate") or company_data.get("inferred_growth_rate") or 0.30
        growth_rate = max(0.0, min(growth_rate, 3.0))

        # Scenario adjustment
        if scenario == "bull": growth_rate *= 1.5
        elif scenario == "bear": growth_rate *= 0.5

        if not growth_overrides:
            market = "bull" if scenario == "bull" else ("bear" if scenario == "bear" else "neutral")
            raw = RevenueProjectionService.project_revenue_with_decay(
                base_revenue=base_revenue, initial_growth=growth_rate, years=years,
                stage=stage, sector=sector, market_conditions=market,
                investor_quality=company_data.get("investor_quality"),
                geography=company_data.get("geography"),
                return_projections=True,
            )
            growth_overrides = [p.get("growth_rate", growth_rate) for p in raw] if isinstance(raw, list) else None

        return self.build_cash_flow_model(company_data, years, growth_overrides)

    def _build_projections_with_overrides(
        self,
        base_revenue: float,
        growth_overrides: List[float],
        stage: str,
        sector: str,
        company_data: Dict,
    ) -> List[Dict[str, Any]]:
        """Build projections using explicit growth rate overrides per year."""
        from app.services.revenue_projection_service import RevenueProjectionService

        projections = []
        current_revenue = base_revenue

        for i, rate in enumerate(growth_overrides):
            proj = RevenueProjectionService.project_revenue_with_decay(
                base_revenue=current_revenue,
                initial_growth=rate,
                years=1,
                stage=stage,
                sector=sector,
                investor_quality=company_data.get("investor_quality"),
                geography=company_data.get("geography"),
                return_projections=True,
            )
            if isinstance(proj, list) and proj:
                entry = proj[-1]
                entry["year"] = i + 1
                projections.append(entry)
                current_revenue = entry.get("revenue", current_revenue * (1 + rate))
            else:
                current_revenue = current_revenue * (1 + rate)
                projections.append({
                    "year": i + 1,
                    "revenue": current_revenue,
                    "growth_rate": rate,
                    "gross_margin": 0.65,
                    "gross_profit": current_revenue * 0.65,
                })

        return projections
