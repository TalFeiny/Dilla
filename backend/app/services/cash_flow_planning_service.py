"""
Cash Flow Planning Service
Composes existing services into a full P&L per year for a company,
including runway calculation and funding gap analysis.

Data sources:
- RevenueProjectionService: forward revenue with decay + gross margins
- IntelligentGapFiller: burn rate decomposition, stage benchmarks
- CATEGORY_MARGINS from revenue_projection_service
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
        growth_rate = company_data.get("growth_rate") or company_data.get("inferred_growth_rate") or 1.0

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

        # Resolve starting cash and burn
        total_raised = company_data.get("total_raised") or 0
        burn_monthly = company_data.get("burn_rate") or STAGE_BURN_MONTHLY.get(stage, 400_000)
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

            # OpEx with efficiency improvement over time
            eff = 1 - (OPEX_EFFICIENCY_RATE * i)
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

            results.append({
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
            })

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
        growth_rate = company_data.get("growth_rate") or company_data.get("inferred_growth_rate") or 1.0

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
