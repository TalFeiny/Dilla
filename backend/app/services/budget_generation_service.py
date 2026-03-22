"""
Budget Generation Service
==========================
Full-depth auto-budgeting engine that generates budgets at subcategory
granularity from trailing actuals, seasonal patterns, headcount plans,
and growth assumptions per cost center.

Unlike the old service (which did `base × growth` for 5 parent categories),
this budgets every subcategory independently using the right growth model:
- Salaries: headcount × cost-per-head with annual raise assumptions
- Cloud/APIs: usage-driven scaling with revenue elasticity
- Licenses: stepped (annual renewal cycles)
- Paid acquisition: CAC × planned new customers
- Payment processing: % of budgeted revenue
- Revenue: seasonal-adjusted growth from trailing actuals

Supports three budget modes:
1. actuals_forward: Project trailing actuals forward with growth (default)
2. zero_based: Every line item starts at zero, must be justified
3. target_margin: Work backward from target EBITDA margin to budget OpEx

Flow:
  1. Pull trailing actuals at subcategory depth via fpa_actuals
  2. Detect per-category seasonality (not just revenue)
  3. Apply growth model per subcategory (headcount/usage/stepped/linear)
  4. Enforce constraints (headcount caps, spend caps, target margins)
  5. Generate m1..m12 budget lines at subcategory level
  6. Roll up to parent categories and compute derived lines
  7. Write to budgets + budget_lines tables
  8. Return full budget with analytics for user review
"""

import logging
import math
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.services.actuals_ingestion import SUBCOMPONENT_TAXONOMY

logger = logging.getLogger(__name__)

# Categories that map to budget_lines rows
BUDGET_CATEGORIES = [
    "revenue", "cogs", "gross_profit",
    "opex_rd", "opex_sm", "opex_ga", "opex_total",
    "ebitda", "net_income", "free_cash_flow", "cash_balance",
]

# Map from CompanyData keys → budget_lines category names
_ACTUALS_KEY_MAP = {
    "revenue": "revenue",
    "cogs": "cogs",
    "rd_spend": "opex_rd",
    "sm_spend": "opex_sm",
    "ga_spend": "opex_ga",
    "total_opex": "opex_total",
    "ebitda": "ebitda",
    "net_income": "net_income",
    "free_cash_flow": "free_cash_flow",
    "cash_balance": "cash_balance",
}

# Subcategory growth driver types — determines how each cost line
# is projected forward. Same definitions as liquidity_management_service
# but used for budgeting (annual planning vs operational forecasting).
_SUBCAT_BUDGET_DRIVERS = {
    "opex_rd": {
        "engineering_salaries": "headcount",
        "ml_engineering":       "headcount",
        "data_engineering":     "headcount",
        "infra_cloud":          "usage_revenue",
        "tools_licenses":       "stepped_annual",
        "contractor":           "linear",
        "research":             "linear",
        "prototyping":          "linear",
        "certifications":       "stepped_annual",
        "firmware":             "headcount",
        "hardware_engineering": "headcount",
        "industrial_design":    "headcount",
    },
    "opex_sm": {
        "paid_acquisition":     "cac_driven",
        "supply_acquisition":   "cac_driven",
        "demand_acquisition":   "cac_driven",
        "content_marketing":    "linear",
        "sales_salaries":       "headcount",
        "events":               "quarterly_stepped",
        "partnerships":         "linear",
        "business_development": "headcount",
        "channel_partners":     "revenue_pct",
        "email_marketing":      "linear",
        "affiliate":            "revenue_pct",
    },
    "opex_ga": {
        "finance_legal":        "stepped_annual",
        "office":               "stepped_annual",
        "admin_salaries":       "headcount",
        "insurance":            "stepped_annual",
        "other_ga":             "linear",
        "facility_lease":       "stepped_annual",
        "utilities":            "usage_headcount",
        "compliance":           "stepped_annual",
        "audit":                "stepped_annual",
    },
    "cogs": {
        "hosting":              "usage_revenue",
        "support_salaries":     "headcount",
        "payment_processing":   "revenue_pct",
        "third_party_apis":     "usage_revenue",
        "data_costs":           "usage_revenue",
        "api_inference_costs":  "usage_revenue",
        "inventory":            "usage_revenue",
        "fulfillment":          "usage_revenue",
        "shipping_costs":       "usage_revenue",
        "materials":            "usage_revenue",
        "manufacturing":        "usage_revenue",
        "direct_labor":         "headcount",
    },
}

# Default growth rates per driver type (annual)
_DRIVER_DEFAULTS = {
    "headcount":        0.05,   # 5% annual raise (excl. new hires)
    "usage_revenue":    0.15,   # scales with revenue at 60% elasticity
    "usage_headcount":  0.08,   # scales with headcount
    "stepped_annual":   0.05,   # annual step-up
    "quarterly_stepped": 0.0,   # flat between events
    "linear":           0.08,   # 8% annual
    "cac_driven":       0.12,   # 12% unless new customer plan given
    "revenue_pct":      0.0,    # tied to revenue, no independent growth
}

# Revenue growth defaults by stage
_REVENUE_GROWTH_DEFAULTS = {
    "Pre-seed": 1.50,
    "Seed": 1.00,
    "Series A": 0.60,
    "Series B": 0.40,
    "Series C": 0.30,
    "Series D": 0.20,
    "Growth": 0.15,
    "Late": 0.10,
}


class BudgetGenerationService:
    """Full-depth auto-budgeting engine with subcategory granularity."""

    def generate_from_actuals(
        self,
        company_id: str,
        fiscal_year: int,
        growth_assumptions: Optional[Dict[str, float]] = None,
        name: Optional[str] = None,
        persist: bool = True,
        mode: str = "actuals_forward",
        headcount_plan: Optional[Dict[str, int]] = None,
        new_customer_plan: Optional[Dict[str, int]] = None,
        target_ebitda_margin: Optional[float] = None,
        spend_caps: Optional[Dict[str, float]] = None,
        subcategory_overrides: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a full-year budget at subcategory depth.

        Args:
            company_id: Company to budget for
            fiscal_year: Target year (e.g., 2026)
            growth_assumptions: Per-category or per-subcategory annual growth.
                {"revenue": 0.25, "opex_rd": 0.10}
                {"opex_rd.engineering_salaries": 0.15}  # subcategory-level
            name: Budget name
            persist: Whether to write to DB
            mode: "actuals_forward" | "zero_based" | "target_margin"
            headcount_plan: Monthly new hires by department
                {"engineering": 2, "sales": 1, "ga": 0}
            new_customer_plan: Monthly new customer targets
                {"m1": 10, "m6": 15, "m12": 20}
            target_ebitda_margin: For target_margin mode — target EBITDA margin
            spend_caps: Max monthly spend per category
                {"opex_rd": 500000, "opex_sm": 200000}
            subcategory_overrides: Exact monthly amounts for specific subcategories
                {"opex_rd.engineering_salaries": {"m1": 100000, "m2": 105000, ...}}

        Returns:
            Full budget with parent + subcategory lines, analytics, warnings.
        """
        from app.services.company_data_pull import pull_company_data

        cd = pull_company_data(company_id)
        if not cd.periods:
            return {
                "budget_id": None,
                "error": "No actuals available — cannot generate budget",
                "lines": [],
            }

        actuals_months = len(cd.periods)
        seed = cd.to_forecast_seed()
        stage = seed.get("stage", "Series A")

        # Pull subcategory-level actuals
        subcat_actuals = self._pull_subcategory_actuals(company_id)
        subcat_proportions = seed.get("_subcategory_proportions", {})

        # Detect seasonality per category
        seasonal_patterns = self._detect_multi_category_seasonality(company_id, cd)

        # Compute trailing stats at both parent and subcategory level
        parent_trailing = self._compute_parent_trailing(cd)
        subcat_trailing = self._compute_subcategory_trailing(subcat_actuals)

        # Resolve growth rates for every subcategory
        growth_map = self._resolve_all_growth_rates(
            parent_trailing, subcat_trailing, subcat_proportions,
            growth_assumptions, stage, seed,
        )

        # Resolve base amounts for subcategories
        subcat_bases = self._resolve_subcategory_bases(
            subcat_trailing, subcat_proportions, parent_trailing, seed,
        )

        # Generate budget lines
        if mode == "target_margin" and target_ebitda_margin is not None:
            lines, analytics = self._generate_target_margin_budget(
                parent_trailing, subcat_bases, growth_map,
                seasonal_patterns, fiscal_year,
                target_ebitda_margin, seed,
            )
        elif mode == "zero_based":
            lines, analytics = self._generate_zero_based_budget(
                subcat_bases, growth_map, seasonal_patterns,
                fiscal_year, headcount_plan, new_customer_plan, seed,
            )
        else:
            lines, analytics = self._generate_actuals_forward_budget(
                parent_trailing, subcat_bases, growth_map,
                seasonal_patterns, fiscal_year,
                headcount_plan, new_customer_plan, seed,
            )

        # Apply subcategory overrides (exact values)
        if subcategory_overrides:
            lines = self._apply_subcategory_overrides(lines, subcategory_overrides)

        # Enforce spend caps
        if spend_caps:
            lines, cap_warnings = self._enforce_spend_caps(lines, spend_caps)
            analytics["cap_warnings"] = cap_warnings

        # Recompute derived lines after all adjustments
        lines = self._recompute_derived_lines(lines)

        # Budget health analytics
        health = self._compute_budget_health(lines, parent_trailing, seed)

        result: Dict[str, Any] = {
            "budget_id": None,
            "name": name or f"Auto-Generated FY{fiscal_year}",
            "fiscal_year": fiscal_year,
            "status": "draft",
            "mode": mode,
            "lines": lines,
            "line_count": len(lines),
            "parent_lines": len([l for l in lines if not l.get("subcategory")]),
            "subcategory_lines": len([l for l in lines if l.get("subcategory")]),
            "seasonality_applied": bool(seasonal_patterns),
            "growth_rates_used": growth_map,
            "actuals_months_used": actuals_months,
            "analytics": analytics,
            "health": health,
        }

        if persist:
            budget_id = self._persist_budget(
                company_id, result["name"], fiscal_year, lines,
            )
            result["budget_id"] = budget_id

        return result

    # ------------------------------------------------------------------
    # Trailing stats computation
    # ------------------------------------------------------------------

    def _compute_parent_trailing(
        self,
        cd: Any,
    ) -> Dict[str, Dict[str, float]]:
        """Compute trailing averages and growth per parent category."""
        stats: Dict[str, Dict[str, float]] = {}

        for cat in ["revenue", "cogs", "opex_rd", "opex_sm", "opex_ga"]:
            values = cd.sorted_amounts(cat)
            if not values:
                continue

            recent = values[-12:] if len(values) >= 12 else values
            older = values[-24:-12] if len(values) > 12 else []

            avg = sum(recent) / len(recent)
            last = recent[-1]

            # YoY growth
            yoy = 0.0
            if older:
                older_avg = sum(older) / len(older)
                if older_avg > 0:
                    yoy = (avg - older_avg) / abs(older_avg)

            # MoM growth (last 3 months)
            mom = 0.0
            if len(recent) >= 3:
                r3 = recent[-3:]
                if r3[0] > 0:
                    mom = (r3[-1] / r3[0]) ** (1 / 2) - 1  # 2-period CAGR

            # Coefficient of variation (seasonality indicator)
            mean = sum(recent) / len(recent) if recent else 1
            variance = sum((v - mean) ** 2 for v in recent) / len(recent) if recent else 0
            cv = (variance ** 0.5) / abs(mean) if mean else 0

            stats[cat] = {
                "avg_monthly": round(avg, 2),
                "last_value": round(last, 2),
                "yoy_growth": round(yoy, 4),
                "mom_growth": round(mom, 4),
                "cv": round(cv, 4),
                "data_months": len(values),
                "monthly_values": recent,  # for seasonality
            }

        return stats

    def _compute_subcategory_trailing(
        self,
        subcat_actuals: Dict[str, Dict[str, List[float]]],
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Compute trailing stats per subcategory.

        Returns: {parent: {subcategory: {avg, last, growth, months}}}.
        """
        result: Dict[str, Dict[str, Dict[str, float]]] = {}

        for parent, subcats in subcat_actuals.items():
            parent_stats: Dict[str, Dict[str, float]] = {}
            for subcat, values in subcats.items():
                if not values:
                    continue

                recent = values[-12:] if len(values) >= 12 else values
                older = values[-24:-12] if len(values) > 12 else []

                avg = sum(recent) / len(recent)
                last = recent[-1]

                yoy = 0.0
                if older:
                    older_avg = sum(older) / len(older)
                    if older_avg > 0:
                        yoy = (avg - older_avg) / abs(older_avg)

                # MoM trend
                mom = 0.0
                if len(recent) >= 3:
                    r3 = recent[-3:]
                    if r3[0] > 0:
                        mom = (r3[-1] / r3[0]) ** (1 / 2) - 1

                parent_stats[subcat] = {
                    "avg_monthly": round(avg, 2),
                    "last_value": round(last, 2),
                    "yoy_growth": round(yoy, 4),
                    "mom_growth": round(mom, 4),
                    "data_months": len(values),
                    "monthly_values": recent,
                }

            if parent_stats:
                result[parent] = parent_stats

        return result

    # ------------------------------------------------------------------
    # Seasonality detection (multi-category)
    # ------------------------------------------------------------------

    def _detect_multi_category_seasonality(
        self,
        company_id: str,
        cd: Any,
    ) -> Dict[str, Any]:
        """Detect seasonal patterns for revenue and each OpEx category."""
        patterns = {}
        try:
            from app.services.seasonality_engine import SeasonalityEngine
            se = SeasonalityEngine()

            for metric in ["revenue", "cogs", "opex_rd", "opex_sm", "opex_ga"]:
                pattern = se.detect_pattern(
                    company_id, metric=metric, company_data=cd,
                )
                if pattern and pattern.confidence >= 0.4:
                    patterns[metric] = pattern
        except Exception as e:
            logger.debug("Multi-category seasonality detection skipped: %s", e)

        return patterns

    # ------------------------------------------------------------------
    # Growth rate resolution
    # ------------------------------------------------------------------

    def _resolve_all_growth_rates(
        self,
        parent_trailing: Dict[str, Dict[str, float]],
        subcat_trailing: Dict[str, Dict[str, Dict[str, float]]],
        subcat_proportions: Dict[str, Dict[str, float]],
        user_overrides: Optional[Dict[str, float]],
        stage: str,
        seed: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve annual growth rates for every category and subcategory.

        Priority per subcategory:
        1. User override at subcategory level ("opex_rd.engineering_salaries": 0.15)
        2. User override at parent level ("opex_rd": 0.10)
        3. Trailing YoY growth for that subcategory
        4. Driver-type default from _DRIVER_DEFAULTS
        5. Trailing parent growth
        6. Hardcoded defaults

        Returns nested dict: {parent: {subcategory: rate}}.
        """
        overrides = user_overrides or {}
        result: Dict[str, Any] = {}

        # Revenue is special — it's a single line
        rev_trailing = parent_trailing.get("revenue", {})
        if "revenue" in overrides:
            result["revenue"] = overrides["revenue"]
        elif rev_trailing.get("yoy_growth") and abs(rev_trailing["yoy_growth"]) > 0.01:
            result["revenue"] = max(-0.30, min(rev_trailing["yoy_growth"], 2.0))
        else:
            result["revenue"] = _REVENUE_GROWTH_DEFAULTS.get(stage, 0.25)

        # Per-parent and per-subcategory
        for parent in ("opex_rd", "opex_sm", "opex_ga", "cogs"):
            parent_growth: Dict[str, float] = {}
            parent_trail = parent_trailing.get(parent, {})
            parent_yoy = parent_trail.get("yoy_growth", 0)
            driver_map = _SUBCAT_BUDGET_DRIVERS.get(parent, {})

            # All subcategories for this parent
            subcats = set()
            if parent in subcat_trailing:
                subcats.update(subcat_trailing[parent].keys())
            if parent in subcat_proportions:
                subcats.update(subcat_proportions[parent].keys())

            for subcat in subcats:
                subcat_key = f"{parent}.{subcat}"
                driver = driver_map.get(subcat, "linear")
                subcat_trail = (subcat_trailing.get(parent, {}).get(subcat, {})
                                .get("yoy_growth", 0))

                # Priority resolution
                if subcat_key in overrides:
                    rate = overrides[subcat_key]
                elif parent in overrides:
                    rate = overrides[parent]
                elif "opex" in overrides and parent.startswith("opex_"):
                    rate = overrides["opex"]
                elif abs(subcat_trail) > 0.01:
                    rate = max(-0.30, min(subcat_trail, 1.5))
                elif driver in _DRIVER_DEFAULTS:
                    rate = _DRIVER_DEFAULTS[driver]
                elif abs(parent_yoy) > 0.01:
                    rate = max(-0.30, min(parent_yoy, 1.0))
                else:
                    rate = 0.10  # fallback

                parent_growth[subcat] = round(rate, 4)

            # Also store the parent-level aggregate rate
            if parent in overrides:
                parent_growth["_parent"] = overrides[parent]
            elif abs(parent_yoy) > 0.01:
                parent_growth["_parent"] = max(-0.30, min(parent_yoy, 1.0))
            else:
                parent_growth["_parent"] = 0.10

            result[parent] = parent_growth

        return result

    # ------------------------------------------------------------------
    # Base amount resolution
    # ------------------------------------------------------------------

    def _resolve_subcategory_bases(
        self,
        subcat_trailing: Dict[str, Dict[str, Dict[str, float]]],
        subcat_proportions: Dict[str, Dict[str, float]],
        parent_trailing: Dict[str, Dict[str, float]],
        seed: Dict[str, Any],
    ) -> Dict[str, Dict[str, float]]:
        """
        Resolve base monthly amount for each subcategory.

        Priority:
        1. Trailing 3-month average of actual subcategory values
        2. Parent total × proportion
        3. Skip
        """
        bases: Dict[str, Dict[str, float]] = {}

        parent_totals = {
            "opex_rd": parent_trailing.get("opex_rd", {}).get("last_value", 0),
            "opex_sm": parent_trailing.get("opex_sm", {}).get("last_value", 0),
            "opex_ga": parent_trailing.get("opex_ga", {}).get("last_value", 0),
            "cogs": parent_trailing.get("cogs", {}).get("last_value", 0),
        }

        for parent in ("opex_rd", "opex_sm", "opex_ga", "cogs"):
            parent_base: Dict[str, float] = {}

            if parent in subcat_trailing:
                for subcat, stats in subcat_trailing[parent].items():
                    if stats.get("avg_monthly", 0) > 0:
                        # Use trailing 3-month average
                        vals = stats.get("monthly_values", [])
                        recent = vals[-3:] if len(vals) >= 3 else vals
                        parent_base[subcat] = sum(recent) / len(recent)

            if not parent_base and parent in subcat_proportions:
                total = parent_totals.get(parent, 0)
                if total > 0:
                    for subcat, pct in subcat_proportions[parent].items():
                        parent_base[subcat] = total * pct

            if parent_base:
                bases[parent] = parent_base

        return bases

    # ------------------------------------------------------------------
    # Budget generation: actuals_forward mode
    # ------------------------------------------------------------------

    def _generate_actuals_forward_budget(
        self,
        parent_trailing: Dict[str, Dict[str, float]],
        subcat_bases: Dict[str, Dict[str, float]],
        growth_map: Dict[str, Any],
        seasonal_patterns: Dict[str, Any],
        fiscal_year: int,
        headcount_plan: Optional[Dict[str, int]],
        new_customer_plan: Optional[Dict[str, int]],
        seed: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generate budget by projecting trailing actuals forward
        with per-subcategory growth drivers.

        Returns (lines, analytics).
        """
        lines: List[Dict[str, Any]] = []
        analytics: Dict[str, Any] = {"mode": "actuals_forward", "subcategories_budgeted": 0}

        # ── Revenue ───────────────────────────────────────────────────
        rev_stats = parent_trailing.get("revenue", {})
        rev_base = rev_stats.get("last_value") or rev_stats.get("avg_monthly", 0)
        rev_growth_annual = growth_map.get("revenue", 0.20)
        rev_growth_monthly = (1 + rev_growth_annual) ** (1 / 12) - 1
        rev_pattern = seasonal_patterns.get("revenue")

        rev_line = {
            "category": "revenue", "subcategory": None,
            "notes": f"Trailing actuals → {rev_growth_annual:.1%} annual growth",
        }
        for m in range(1, 13):
            value = rev_base * (1 + rev_growth_monthly) ** m
            if rev_pattern:
                factor = rev_pattern.monthly_factors.get(m, 1.0)
                value *= factor
            rev_line[f"m{m}"] = round(value, 2)
        lines.append(rev_line)

        # Monthly revenue values for revenue_pct driver
        monthly_revenues = [rev_line[f"m{m}"] for m in range(1, 13)]

        # ── COGS + OpEx at subcategory depth ──────────────────────────
        for parent in ("cogs", "opex_rd", "opex_sm", "opex_ga"):
            parent_total_line = {
                "category": parent, "subcategory": None,
                "notes": "Sum of subcategory budget lines",
            }
            for m in range(1, 13):
                parent_total_line[f"m{m}"] = 0.0

            parent_bases = subcat_bases.get(parent, {})
            parent_growth = growth_map.get(parent, {})
            driver_map = _SUBCAT_BUDGET_DRIVERS.get(parent, {})
            cat_pattern = seasonal_patterns.get(parent)

            if parent_bases:
                # Budget each subcategory individually
                for subcat, base_amount in parent_bases.items():
                    if base_amount <= 0:
                        continue

                    driver = driver_map.get(subcat, "linear")
                    annual_growth = parent_growth.get(subcat, 0.10)
                    monthly_growth = (1 + annual_growth) ** (1 / 12) - 1

                    subcat_line = {
                        "category": parent,
                        "subcategory": subcat,
                        "notes": f"Driver: {driver}, growth: {annual_growth:.1%}",
                    }

                    for m in range(1, 13):
                        value = self._project_subcategory_month(
                            driver=driver,
                            base_amount=base_amount,
                            month=m,
                            monthly_growth=monthly_growth,
                            annual_growth=annual_growth,
                            monthly_revenue=monthly_revenues[m - 1],
                            headcount_plan=headcount_plan,
                            new_customer_plan=new_customer_plan,
                            seed=seed,
                            parent=parent,
                            subcat=subcat,
                        )

                        # Apply category-level seasonality
                        if cat_pattern:
                            factor = cat_pattern.monthly_factors.get(m, 1.0)
                            value *= factor

                        subcat_line[f"m{m}"] = round(value, 2)
                        parent_total_line[f"m{m}"] += value

                    lines.append(subcat_line)
                    analytics["subcategories_budgeted"] += 1

                    # Subcomponent breakdown — if this subcategory has known
                    # subcomponents (e.g., base_pay, bonus, benefits beneath
                    # engineering_salaries), emit budget lines at that depth too.
                    subcomponents = SUBCOMPONENT_TAXONOMY.get(subcat)
                    if subcomponents and driver == "headcount":
                        # For salary subcategories, decompose by comp component
                        _COMP_DEFAULTS = {
                            "base_pay": 0.62, "bonus": 0.10, "benefits": 0.15,
                            "equity_comp": 0.08, "payroll_tax": 0.05,
                            "commissions": 0.12, "overtime": 0.05,
                            "allowances": 0.02,
                        }
                        for comp_name in subcomponents:
                            pct = _COMP_DEFAULTS.get(comp_name, 1.0 / len(subcomponents))
                            comp_line = {
                                "category": parent,
                                "subcategory": f"{subcat}/{comp_name}",
                                "notes": f"Subcomponent: {pct:.0%} of {subcat}",
                            }
                            for m in range(1, 13):
                                comp_line[f"m{m}"] = round(subcat_line[f"m{m}"] * pct, 2)
                            lines.append(comp_line)

            else:
                # No subcategory data — budget at parent level
                p_stats = parent_trailing.get(parent, {})
                p_base = p_stats.get("last_value") or p_stats.get("avg_monthly", 0)
                p_growth = parent_growth.get("_parent", 0.10)
                p_monthly_growth = (1 + p_growth) ** (1 / 12) - 1

                parent_total_line["notes"] = f"No subcategory data — parent-level budget (growth: {p_growth:.1%})"
                for m in range(1, 13):
                    value = p_base * (1 + p_monthly_growth) ** m
                    if cat_pattern:
                        factor = cat_pattern.monthly_factors.get(m, 1.0)
                        value *= factor
                    parent_total_line[f"m{m}"] = round(value, 2)

            # Round parent totals
            for m in range(1, 13):
                parent_total_line[f"m{m}"] = round(parent_total_line[f"m{m}"], 2)
            lines.append(parent_total_line)

        return lines, analytics

    def _project_subcategory_month(
        self,
        driver: str,
        base_amount: float,
        month: int,
        monthly_growth: float,
        annual_growth: float,
        monthly_revenue: float,
        headcount_plan: Optional[Dict[str, int]],
        new_customer_plan: Optional[Dict[str, int]],
        seed: Dict[str, Any],
        parent: str,
        subcat: str,
    ) -> float:
        """
        Project a single subcategory for a single budget month
        using its growth driver.
        """
        if driver == "headcount":
            # Base salary/comp grows with annual raise + new hires
            raise_factor = (1 + 0.04) ** (month / 12)  # 4% annual raise
            value = base_amount * raise_factor

            # Add new hire cost if headcount plan provided
            if headcount_plan:
                dept_map = {
                    "opex_rd": "engineering",
                    "opex_sm": "sales",
                    "opex_ga": "ga",
                    "cogs": "support",
                }
                dept = dept_map.get(parent, "other")
                new_hires_monthly = headcount_plan.get(dept, 0)
                if new_hires_monthly > 0:
                    cost_per_head = seed.get("cost_per_head", 15_000)
                    # Cumulative new hires through this month
                    cum_hires = new_hires_monthly * month
                    # Share of this subcategory in the department
                    value += cum_hires * cost_per_head * 0.6  # 60% is comp

            return value

        elif driver == "usage_revenue":
            # Scales sub-linearly with revenue
            base_rev = seed.get("revenue", 0) or 1
            # monthly base_rev estimate
            base_rev_monthly = base_rev / 12 if base_rev > 12000 else base_rev
            if base_rev_monthly > 0:
                ratio = monthly_revenue / base_rev_monthly
                # Elasticity: 0.5-0.7 (cloud costs grow slower than revenue)
                elasticity = 0.6
                return base_amount * (ratio ** elasticity)
            return base_amount * (1 + monthly_growth) ** month

        elif driver == "usage_headcount":
            # Scales with headcount (utilities, per-seat licenses)
            hc = seed.get("headcount", 1) or 1
            hiring = (headcount_plan or {}).get("engineering", 0) + \
                     (headcount_plan or {}).get("sales", 0) + \
                     (headcount_plan or {}).get("ga", 0)
            new_hc = hc + hiring * month
            return base_amount * (new_hc / hc) ** 0.5

        elif driver == "stepped_annual":
            # Flat for 12 months then steps up
            step_pct = annual_growth
            # Within a budget year, this is flat (step happens at year boundary)
            return base_amount * (1 + step_pct)

        elif driver == "quarterly_stepped":
            # Events happen quarterly (trade shows, conferences)
            # Spending is lumpy: higher in event months
            quarter = (month - 1) // 3
            # Events typically in months 3, 6, 9, 12 of fiscal year
            is_event_month = month in (3, 6, 9, 12)
            if is_event_month:
                return base_amount * 2.5  # spike in event months
            return base_amount * 0.5  # quiet months

        elif driver == "cac_driven":
            # New customers × CAC
            cac = seed.get("cac_override")
            if cac and new_customer_plan:
                new_custs = new_customer_plan.get(f"m{month}", 0)
                if new_custs > 0:
                    return new_custs * cac
            # Fallback: grow linearly
            return base_amount * (1 + monthly_growth) ** month

        elif driver == "revenue_pct":
            # Percentage of revenue (payment processing, commissions)
            # Infer percentage from base
            base_rev = seed.get("revenue", 0) or 1
            base_rev_monthly = base_rev / 12 if base_rev > 12000 else base_rev
            if base_rev_monthly > 0:
                implied_pct = base_amount / base_rev_monthly
                return monthly_revenue * implied_pct
            return base_amount * (1 + monthly_growth) ** month

        else:  # linear
            return base_amount * (1 + monthly_growth) ** month

    # ------------------------------------------------------------------
    # Budget generation: zero-based mode
    # ------------------------------------------------------------------

    def _generate_zero_based_budget(
        self,
        subcat_bases: Dict[str, Dict[str, float]],
        growth_map: Dict[str, Any],
        seasonal_patterns: Dict[str, Any],
        fiscal_year: int,
        headcount_plan: Optional[Dict[str, int]],
        new_customer_plan: Optional[Dict[str, int]],
        seed: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Zero-based budget: every line starts at zero and is built
        from first principles using headcount × cost-per-head,
        customer plan × CAC, revenue × commission rate, etc.

        If no plan data is available, falls back to actuals_forward
        but flags those lines as "unvalidated".
        """
        lines: List[Dict[str, Any]] = []
        analytics: Dict[str, Any] = {
            "mode": "zero_based",
            "justified_lines": 0,
            "unjustified_lines": 0,
        }

        # Revenue from growth target
        rev_growth = growth_map.get("revenue", 0.20)
        rev_base = seed.get("revenue", 0) or 0
        rev_monthly = rev_base / 12 if rev_base > 12000 else rev_base
        rev_monthly_growth = (1 + rev_growth) ** (1 / 12) - 1
        rev_pattern = seasonal_patterns.get("revenue")

        rev_line = {"category": "revenue", "subcategory": None,
                    "notes": f"Zero-based: {rev_growth:.1%} growth target"}
        for m in range(1, 13):
            v = rev_monthly * (1 + rev_monthly_growth) ** m
            if rev_pattern:
                v *= rev_pattern.monthly_factors.get(m, 1.0)
            rev_line[f"m{m}"] = round(v, 2)
        lines.append(rev_line)

        monthly_revenues = [rev_line[f"m{m}"] for m in range(1, 13)]

        # Build cost lines from first principles
        headcount = seed.get("headcount", 0) or 10
        cost_per_head = seed.get("cost_per_head", 15_000)
        cac = seed.get("cac_override")
        hp = headcount_plan or {}
        ncp = new_customer_plan or {}

        for parent in ("cogs", "opex_rd", "opex_sm", "opex_ga"):
            parent_total = {"category": parent, "subcategory": None,
                            "notes": "Sum of zero-based subcategory lines"}
            for m in range(1, 13):
                parent_total[f"m{m}"] = 0.0

            driver_map = _SUBCAT_BUDGET_DRIVERS.get(parent, {})
            parent_bases = subcat_bases.get(parent, {})

            for subcat, base_amount in parent_bases.items():
                driver = driver_map.get(subcat, "linear")
                justified = False

                sub_line = {"category": parent, "subcategory": subcat}

                for m_idx in range(1, 13):
                    if driver == "headcount":
                        # Cost = people × cost per head
                        dept_key = {"opex_rd": "engineering", "opex_sm": "sales",
                                    "opex_ga": "ga", "cogs": "support"}.get(parent, "other")
                        hires_per_month = hp.get(dept_key, 0)
                        current_hc = headcount + hires_per_month * m_idx
                        # This subcategory's share of department cost
                        total_parent = sum(parent_bases.values())
                        share = base_amount / total_parent if total_parent > 0 else 0.2
                        v = current_hc * cost_per_head * share
                        justified = bool(hp)

                    elif driver == "cac_driven":
                        new_custs = ncp.get(f"m{m_idx}", 0)
                        if cac and new_custs > 0:
                            v = new_custs * cac
                            justified = True
                        else:
                            v = base_amount  # unjustified fallback
                            justified = False

                    elif driver == "revenue_pct":
                        base_rev_m = (seed.get("revenue", 1) or 1) / 12
                        pct = base_amount / base_rev_m if base_rev_m > 0 else 0.03
                        v = monthly_revenues[m_idx - 1] * pct
                        justified = True

                    elif driver in ("usage_revenue", "usage_headcount"):
                        base_rev_m = (seed.get("revenue", 1) or 1) / 12
                        ratio = monthly_revenues[m_idx - 1] / base_rev_m if base_rev_m > 0 else 1
                        v = base_amount * (ratio ** 0.6)
                        justified = True

                    else:
                        # Can't justify from first principles → use actuals
                        monthly_g = (1 + 0.05) ** (1 / 12) - 1  # minimal growth
                        v = base_amount * (1 + monthly_g) ** m_idx
                        justified = False

                    sub_line[f"m{m_idx}"] = round(v, 2)
                    parent_total[f"m{m_idx}"] += v

                status = "justified" if justified else "needs_review"
                sub_line["notes"] = f"Zero-based ({driver}) — {status}"
                if justified:
                    analytics["justified_lines"] += 1
                else:
                    analytics["unjustified_lines"] += 1

                lines.append(sub_line)

            for m in range(1, 13):
                parent_total[f"m{m}"] = round(parent_total[f"m{m}"], 2)
            lines.append(parent_total)

        return lines, analytics

    # ------------------------------------------------------------------
    # Budget generation: target margin mode
    # ------------------------------------------------------------------

    def _generate_target_margin_budget(
        self,
        parent_trailing: Dict[str, Dict[str, float]],
        subcat_bases: Dict[str, Dict[str, float]],
        growth_map: Dict[str, Any],
        seasonal_patterns: Dict[str, Any],
        fiscal_year: int,
        target_margin: float,
        seed: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Work backward from target EBITDA margin to allocate OpEx.

        1. Budget revenue with growth
        2. Budget COGS from gross margin
        3. Compute gross profit
        4. Target OpEx = gross_profit × (1 - target_margin_ratio)
        5. Distribute OpEx budget across R&D/S&M/G&A using current proportions
        6. Distribute each parent across subcategories proportionally
        """
        lines: List[Dict[str, Any]] = []
        analytics: Dict[str, Any] = {"mode": "target_margin", "target_ebitda_margin": target_margin}

        # Revenue
        rev_stats = parent_trailing.get("revenue", {})
        rev_base = rev_stats.get("last_value") or rev_stats.get("avg_monthly", 0)
        rev_growth = growth_map.get("revenue", 0.20)
        rev_mg = (1 + rev_growth) ** (1 / 12) - 1
        rev_pattern = seasonal_patterns.get("revenue")

        rev_line = {"category": "revenue", "subcategory": None,
                    "notes": f"Target margin mode: {target_margin:.0%} EBITDA"}
        for m in range(1, 13):
            v = rev_base * (1 + rev_mg) ** m
            if rev_pattern:
                v *= rev_pattern.monthly_factors.get(m, 1.0)
            rev_line[f"m{m}"] = round(v, 2)
        lines.append(rev_line)

        monthly_revenues = [rev_line[f"m{m}"] for m in range(1, 13)]

        # COGS from gross margin
        gm = seed.get("gross_margin", 0.65)
        cogs_line = {"category": "cogs", "subcategory": None,
                     "notes": f"Gross margin: {gm:.0%}"}
        for m in range(1, 13):
            cogs_line[f"m{m}"] = round(monthly_revenues[m - 1] * (1 - gm), 2)
        lines.append(cogs_line)

        # Target OpEx = gross_profit - target_ebitda
        # EBITDA = GP - OpEx → OpEx = GP - EBITDA = GP - (revenue × target_margin)
        # Distribute across R&D/S&M/G&A using trailing proportions
        rd_trail = parent_trailing.get("opex_rd", {}).get("last_value", 0)
        sm_trail = parent_trailing.get("opex_sm", {}).get("last_value", 0)
        ga_trail = parent_trailing.get("opex_ga", {}).get("last_value", 0)
        total_opex_trail = rd_trail + sm_trail + ga_trail

        # Default proportions if no trailing data
        if total_opex_trail > 0:
            rd_share = rd_trail / total_opex_trail
            sm_share = sm_trail / total_opex_trail
            ga_share = ga_trail / total_opex_trail
        else:
            rd_share, sm_share, ga_share = 0.40, 0.35, 0.25

        for parent, share in [("opex_rd", rd_share), ("opex_sm", sm_share), ("opex_ga", ga_share)]:
            parent_total = {"category": parent, "subcategory": None,
                            "notes": f"Target margin allocation: {share:.0%} of OpEx budget"}
            for m in range(1, 13):
                rev = monthly_revenues[m - 1]
                gp = rev * gm
                target_ebitda = rev * target_margin
                total_opex_budget = gp - target_ebitda
                parent_budget = total_opex_budget * share
                parent_total[f"m{m}"] = round(max(0, parent_budget), 2)

            lines.append(parent_total)

            # Subcategory allocation within parent
            parent_bases = subcat_bases.get(parent, {})
            if parent_bases:
                subcat_total = sum(parent_bases.values())
                for subcat, base in parent_bases.items():
                    sub_share = base / subcat_total if subcat_total > 0 else 0
                    sub_line = {"category": parent, "subcategory": subcat,
                                "notes": f"Target margin: {sub_share:.0%} of {parent}"}
                    for m in range(1, 13):
                        sub_line[f"m{m}"] = round(parent_total[f"m{m}"] * sub_share, 2)
                    lines.append(sub_line)

        analytics["opex_allocation"] = {
            "rd_share": round(rd_share, 4),
            "sm_share": round(sm_share, 4),
            "ga_share": round(ga_share, 4),
        }

        return lines, analytics

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _apply_subcategory_overrides(
        self,
        lines: List[Dict[str, Any]],
        overrides: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """Apply exact override values to specific subcategory lines."""
        for line in lines:
            cat = line["category"]
            sub = line.get("subcategory")
            if not sub:
                continue
            key = f"{cat}.{sub}"
            if key in overrides:
                for m_key, value in overrides[key].items():
                    if m_key in line:
                        line[m_key] = round(value, 2)
                line["notes"] = f"Override applied: {key}"
        return lines

    def _enforce_spend_caps(
        self,
        lines: List[Dict[str, Any]],
        caps: Dict[str, float],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Enforce maximum monthly spend per parent category."""
        warnings = []

        for line in lines:
            cat = line["category"]
            sub = line.get("subcategory")
            if sub:
                continue  # only cap at parent level

            cap = caps.get(cat)
            if not cap:
                continue

            for m in range(1, 13):
                if line[f"m{m}"] > cap:
                    original = line[f"m{m}"]
                    line[f"m{m}"] = round(cap, 2)
                    warnings.append(
                        f"{cat} m{m}: capped from ${original:,.0f} to ${cap:,.0f}"
                    )

                    # Scale subcategories proportionally
                    scale = cap / original if original > 0 else 1
                    for sub_line in lines:
                        if sub_line["category"] == cat and sub_line.get("subcategory"):
                            sub_line[f"m{m}"] = round(sub_line[f"m{m}"] * scale, 2)

        return lines, warnings

    def _recompute_derived_lines(
        self,
        lines: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Recompute derived lines (gross profit, total opex, ebitda)."""

        def _get_line(cat: str) -> Optional[Dict[str, Any]]:
            for l in lines:
                if l["category"] == cat and not l.get("subcategory"):
                    return l
            return None

        rev = _get_line("revenue")
        cogs = _get_line("cogs")
        rd = _get_line("opex_rd")
        sm = _get_line("opex_sm")
        ga = _get_line("opex_ga")

        # Recalculate parent totals from subcategories
        for parent in ("cogs", "opex_rd", "opex_sm", "opex_ga"):
            parent_line = _get_line(parent)
            sub_lines = [l for l in lines if l["category"] == parent and l.get("subcategory")]
            if parent_line and sub_lines:
                for m in range(1, 13):
                    parent_line[f"m{m}"] = round(
                        sum(sl.get(f"m{m}", 0) for sl in sub_lines), 2
                    )

        # Gross profit
        if rev and cogs:
            gp = _get_line("gross_profit")
            if not gp:
                gp = {"category": "gross_profit", "subcategory": None, "notes": "Derived: revenue - cogs"}
                lines.append(gp)
            for m in range(1, 13):
                gp[f"m{m}"] = round(rev[f"m{m}"] - cogs[f"m{m}"], 2)

        # Total OpEx
        if rd and sm and ga:
            opex = _get_line("opex_total")
            if not opex:
                opex = {"category": "opex_total", "subcategory": None, "notes": "Derived: R&D + S&M + G&A"}
                lines.append(opex)
            for m in range(1, 13):
                opex[f"m{m}"] = round(rd[f"m{m}"] + sm[f"m{m}"] + ga[f"m{m}"], 2)

        # EBITDA
        gp_line = _get_line("gross_profit")
        opex_line = _get_line("opex_total")
        if gp_line and opex_line:
            ebitda = _get_line("ebitda")
            if not ebitda:
                ebitda = {"category": "ebitda", "subcategory": None, "notes": "Derived: GP - OpEx"}
                lines.append(ebitda)
            for m in range(1, 13):
                ebitda[f"m{m}"] = round(gp_line[f"m{m}"] - opex_line[f"m{m}"], 2)

        return lines

    # ------------------------------------------------------------------
    # Budget health analytics
    # ------------------------------------------------------------------

    def _compute_budget_health(
        self,
        lines: List[Dict[str, Any]],
        parent_trailing: Dict[str, Dict[str, float]],
        seed: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze budget health: realism, efficiency, risk flags."""

        def _get_line(cat: str) -> Optional[Dict[str, Any]]:
            for l in lines:
                if l["category"] == cat and not l.get("subcategory"):
                    return l
            return None

        health: Dict[str, Any] = {"flags": []}

        rev = _get_line("revenue")
        ebitda = _get_line("ebitda")
        opex = _get_line("opex_total")
        cogs = _get_line("cogs")

        if not rev:
            return health

        # Annual totals
        annual_rev = sum(rev[f"m{m}"] for m in range(1, 13))
        annual_ebitda = sum(ebitda[f"m{m}"] for m in range(1, 13)) if ebitda else 0
        annual_opex = sum(opex[f"m{m}"] for m in range(1, 13)) if opex else 0
        annual_cogs = sum(cogs[f"m{m}"] for m in range(1, 13)) if cogs else 0

        health["annual_revenue"] = round(annual_rev, 2)
        health["annual_ebitda"] = round(annual_ebitda, 2)
        health["annual_opex"] = round(annual_opex, 2)
        health["annual_cogs"] = round(annual_cogs, 2)

        if annual_rev > 0:
            health["budgeted_ebitda_margin"] = round(annual_ebitda / annual_rev, 4)
            health["budgeted_gross_margin"] = round(
                (annual_rev - annual_cogs) / annual_rev, 4
            )
            health["opex_to_revenue"] = round(annual_opex / annual_rev, 4)

        # Compare to trailing
        trail_rev = parent_trailing.get("revenue", {}).get("avg_monthly", 0) * 12
        if trail_rev > 0:
            rev_growth_budgeted = (annual_rev - trail_rev) / trail_rev
            health["implied_revenue_growth"] = round(rev_growth_budgeted, 4)

            if rev_growth_budgeted > 1.0:
                health["flags"].append({
                    "type": "aggressive_revenue",
                    "message": f"Revenue budget implies {rev_growth_budgeted:.0%} growth — verify assumptions",
                })

        # OpEx efficiency
        if annual_rev > 0 and annual_opex / annual_rev > 0.8:
            health["flags"].append({
                "type": "high_opex",
                "message": f"OpEx is {annual_opex / annual_rev:.0%} of revenue — burns fast",
            })

        # Month-over-month volatility check
        if ebitda:
            ebitda_values = [ebitda[f"m{m}"] for m in range(1, 13)]
            sign_changes = sum(
                1 for i in range(1, 12) if (ebitda_values[i] > 0) != (ebitda_values[i-1] > 0)
            )
            if sign_changes > 2:
                health["flags"].append({
                    "type": "volatile_ebitda",
                    "message": f"EBITDA crosses zero {sign_changes} times — unstable budget",
                })

        # Top cost lines
        subcat_totals: List[Tuple[str, float]] = []
        for l in lines:
            if l.get("subcategory"):
                total = sum(l.get(f"m{m}", 0) for m in range(1, 13))
                subcat_totals.append((f"{l['category']}/{l['subcategory']}", total))
        subcat_totals.sort(key=lambda x: -x[1])
        health["top_cost_lines"] = [
            {"line": name, "annual_total": round(total, 2)}
            for name, total in subcat_totals[:10]
        ]

        return health

    # ------------------------------------------------------------------
    # Data pulling
    # ------------------------------------------------------------------

    def _pull_subcategory_actuals(
        self,
        company_id: str,
    ) -> Dict[str, Dict[str, List[float]]]:
        """Pull actual subcategory amounts from fpa_actuals."""
        try:
            from app.core.supabase_client import get_supabase_client
            sb = get_supabase_client()
            if not sb:
                return {}

            rows = (
                sb.table("fpa_actuals")
                .select("category, subcategory, amount, period")
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
                amount = row.get("amount")
                if not cat or not sub or amount is None:
                    continue
                result.setdefault(cat, {}).setdefault(sub, []).append(float(amount))

            return result
        except Exception as e:
            logger.warning("Failed to pull subcategory actuals: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_budget(
        self,
        company_id: str,
        name: str,
        fiscal_year: int,
        lines: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Write budget + budget_lines to Supabase."""
        try:
            from app.core.supabase_client import get_supabase_client
            sb = get_supabase_client()

            budget_data = {
                "company_id": company_id,
                "name": name,
                "fiscal_year": fiscal_year,
                "status": "draft",
            }
            result = sb.table("budgets").insert(budget_data).execute()
            if not result.data:
                logger.error("Failed to create budget record")
                return None

            budget_id = result.data[0]["id"]

            line_rows = []
            for line in lines:
                row = {
                    "budget_id": budget_id,
                    "category": line["category"],
                    "subcategory": line.get("subcategory"),
                    "notes": line.get("notes"),
                }
                for m in range(1, 13):
                    row[f"m{m}"] = line.get(f"m{m}", 0)
                line_rows.append(row)

            # Batch insert in chunks of 500
            for i in range(0, len(line_rows), 500):
                chunk = line_rows[i:i + 500]
                sb.table("budget_lines").insert(chunk).execute()

            logger.info(
                "Persisted budget %s (%d lines, %d subcategory) for company %s",
                budget_id, len(line_rows),
                len([l for l in line_rows if l.get("subcategory")]),
                company_id,
            )
            return budget_id

        except Exception as e:
            logger.error("Failed to persist budget: %s", e)
            return None
