"""
Chart Data Service - Shared chart generation for matrix and deck-agent flows.
Extracts path_to_100m and probability_cloud logic for reuse by matrix chart API.
"""

import logging
import math
from typing import Dict, List, Any, Optional

from app.services.valuation_engine_service import (
    ValuationEngineService,
    ValuationRequest,
    Stage,
)
from app.services.data_validator import ensure_numeric

logger = logging.getLogger(__name__)


def _get_field_safe(data: Dict, key: str, default: Any = None) -> Any:
    """Safely get field from dict, handling nested keys."""
    if not data:
        return default
    v = data.get(key)
    if v is not None and v != "":
        return v
    return default


def _generate_date_labels(projection_years: int = 6) -> List[str]:
    """Generate year labels for projection charts."""
    from datetime import datetime
    year = datetime.now().year
    return [str(year + i) for i in range(projection_years)]


class ChartDataService:
    """
    Generates chart data for matrix viewport: path_to_100m, probability_cloud,
    sankey, waterfall, heatmap. Uses ValuationEngineService and ChartGenerationSkill.
    """

    def __init__(self):
        self.valuation_engine = ValuationEngineService()

    def generate_probability_cloud(
        self,
        company_data: Dict[str, Any],
        check_size: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate probability cloud chart data for a single company.
        Returns chart config compatible with TableauLevelCharts.
        """
        try:
            scenarios = company_data.get("pwerm_scenarios", [])
            if not scenarios:
                stage_map = {
                    "Pre-Seed": Stage.PRE_SEED,
                    "Pre Seed": Stage.PRE_SEED,
                    "Seed": Stage.SEED,
                    "Series A": Stage.SERIES_A,
                    "Series B": Stage.SERIES_B,
                    "Series C": Stage.SERIES_C,
                    "Growth": Stage.GROWTH,
                    "Late": Stage.LATE,
                }
                company_stage = stage_map.get(
                    company_data.get("stage", "Series A"), Stage.SERIES_A
                )
                revenue = ensure_numeric(company_data.get("revenue"), 0)
                if revenue == 0:
                    revenue = ensure_numeric(company_data.get("inferred_revenue"), 0)
                    if revenue == 0:
                        revenue = ensure_numeric(company_data.get("arr"), 0)
                        if revenue == 0:
                            revenue = ensure_numeric(
                                company_data.get("inferred_arr"), 1_000_000
                            )
                growth_rate = ensure_numeric(company_data.get("growth_rate"), 0)
                if growth_rate == 0:
                    growth_rate = ensure_numeric(
                        company_data.get("inferred_growth_rate"), 1.5
                    )
                valuation = ensure_numeric(company_data.get("valuation"), 0)
                if valuation == 0:
                    valuation = ensure_numeric(
                        company_data.get("inferred_valuation"), 0
                    )
                    if valuation == 0:
                        valuation = ensure_numeric(
                            company_data.get("total_funding"), 0
                        ) * 3

                inferred_val = (
                    ensure_numeric(company_data.get("inferred_valuation"), None)
                    if company_data.get("inferred_valuation") is not None
                    else None
                )
                val_request = ValuationRequest(
                    company_name=company_data.get("company", "Unknown"),
                    stage=company_stage,
                    revenue=revenue,
                    growth_rate=growth_rate,
                    last_round_valuation=valuation if valuation and valuation > 0 else None,
                    inferred_valuation=inferred_val,
                    total_raised=_get_field_safe(company_data, "total_funding"),
                )
                scenarios = self.valuation_engine._generate_exit_scenarios(
                    val_request
                )
                self.valuation_engine.annotate_scenarios_with_returns(
                    scenarios, val_request
                )

            valuation = company_data.get("valuation", 100_000_000)
            our_entry_ownership = check_size / valuation if valuation > 0 else 0.08
            our_investment = {"amount": check_size, "ownership": our_entry_ownership}

            for scenario in scenarios:
                self.valuation_engine.model_cap_table_evolution(
                    scenario, company_data, our_investment
                )
            breakpoint_distributions = (
                self.valuation_engine.calculate_breakpoint_distributions(scenarios)
            )
            self.valuation_engine.generate_return_curves(scenarios, our_investment)

            breakpoint_clouds = []
            if "our_breakeven" in breakpoint_distributions:
                dist = breakpoint_distributions["our_breakeven"]
                breakpoint_clouds.append({
                    "type": "return_of_capital",
                    "label": "Return of Capital",
                    "median": dist["median"],
                    "p10_p90": [dist["p10"], dist["p90"]],
                    "p25_p75": [dist["p25"], dist["p75"]],
                    "color": "#ef4444",
                })
            if "our_3x" in breakpoint_distributions:
                dist = breakpoint_distributions["our_3x"]
                breakpoint_clouds.append({
                    "type": "3x_return",
                    "label": "3x Return",
                    "median": dist["median"],
                    "p10_p90": [dist["p10"], dist["p90"]],
                    "p25_p75": [dist["p25"], dist["p75"]],
                    "color": "#22c55e",
                })
            if "liquidation_satisfied" in breakpoint_distributions:
                dist = breakpoint_distributions["liquidation_satisfied"]
                breakpoint_clouds.append({
                    "type": "liquidation_cleared",
                    "label": "Liquidation Cleared",
                    "median": dist["median"],
                    "p10_p90": [dist["p10"], dist["p90"]],
                    "p25_p75": [dist["p25"], dist["p75"]],
                    "color": "#3b82f6",
                })

            sorted_scenarios = sorted(
                scenarios, key=lambda s: s.probability, reverse=True
            )[:10]
            scenario_curves = []
            for scenario in sorted_scenarios:
                if hasattr(scenario, "return_curve") and scenario.return_curve:
                    if scenario.exit_type and "IPO" in scenario.exit_type:
                        color = "#10b981"
                    elif scenario.exit_type and "Downside" in scenario.exit_type:
                        color = "#ef4444"
                    else:
                        color = "#f59e0b"
                    rc = scenario.return_curve
                    if isinstance(rc, dict) and "exit_values" in rc and "return_multiples" in rc:
                        ev = rc["exit_values"]
                        rm = rc["return_multiples"]
                        if isinstance(ev, list) and isinstance(rm, list) and len(ev) == len(rm):
                            scenario_curves.append({
                                "name": scenario.scenario,
                                "scenario": scenario.scenario,
                                "probability": scenario.probability,
                                "exit_type": scenario.exit_type or "M&A",
                                "return_curve": {"exit_values": ev, "return_multiples": rm},
                                "color": color,
                            })

            decision_zones = []
            loss_threshold = breakpoint_distributions.get("our_breakeven", {}).get(
                "p25", check_size * 2
            )
            decision_zones.append({
                "range": [0, loss_threshold],
                "label": "Loss Zone",
                "color": "#fee2e2",
                "opacity": 0.1,
            })
            defensive_end = breakpoint_distributions.get("our_3x", {}).get(
                "median", check_size * 10
            )
            decision_zones.append({
                "range": [loss_threshold, defensive_end],
                "label": "Defensive Returns",
                "color": "#fef3c7",
                "opacity": 0.1,
            })

            config = {
                "x_axis": {"label": "Exit Value ($M)", "type": "log"},
                "y_axis": {"label": "Return Multiple", "type": "linear"},
            }

            return {
                "type": "probability_cloud",
                "title": f"Probability Cloud: {company_data.get('company', 'Company')}",
                "data": {
                    "scenario_curves": scenario_curves,
                    "breakpoint_clouds": breakpoint_clouds,
                    "decision_zones": decision_zones,
                    "config": config,
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Probability cloud generation failed: {e}")
            return None

    def generate_path_to_100m(
        self,
        companies: List[Dict[str, Any]],
        projection_years: int = 6,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate Path to $100M ARR comparison chart for multiple companies.
        Returns line chart config compatible with TableauLevelCharts.
        """
        if not companies:
            return None
        try:
            projection_data_by_company: Dict[str, Dict] = {}
            for company in companies[:3]:  # Max 3 companies for clarity
                name = company.get("company") or company.get("companyName") or "Unknown"
                current_arr = ensure_numeric(
                    company.get("revenue")
                    or company.get("arr")
                    or company.get("inferred_revenue")
                    or company.get("inferred_arr"),
                    1_000_000,
                )
                growth = ensure_numeric(
                    company.get("growth_rate")
                    or company.get("inferred_growth_rate"),
                    1.5,
                )
                if growth < 10:
                    yoy_growth = growth
                else:
                    yoy_growth = 1 + (growth / 100)
                if yoy_growth < 1.0:
                    yoy_growth = 1.2

                target_arr = 100_000_000
                target_name = "$100M"
                if current_arr >= 100_000_000:
                    target_arr = 1_000_000_000
                    target_name = "$1B"
                elif current_arr >= 1_000_000_000:
                    target_arr = 10_000_000_000
                    target_name = "$10B"

                if current_arr > 0 and current_arr < target_arr and yoy_growth > 1.0:
                    try:
                        years_to_target = math.log(
                            target_arr / current_arr
                        ) / math.log(yoy_growth)
                        years_to_target = max(0, min(years_to_target, 10))
                    except (ValueError, ZeroDivisionError):
                        years_to_target = 5
                else:
                    years_to_target = 0 if current_arr >= target_arr else 5

                starting_revenue_m = current_arr / 1_000_000
                cagr = (yoy_growth - 1) * 100 / 100.0 if years_to_target > 0 else 0.2
                projection = []
                for i in range(projection_years):
                    if i == 0:
                        projection.append(round(starting_revenue_m, 2))
                    else:
                        val = starting_revenue_m * ((1 + cagr) ** i)
                        projection.append(round(val, 2))

                projection_data_by_company[name] = {
                    "current_arr": current_arr,
                    "years_to_target": round(years_to_target, 1),
                    "target": target_name,
                    "growth_rate_pct": int((yoy_growth - 1) * 100),
                    "projection": projection,
                }

            labels = _generate_date_labels(projection_years)
            colors = [
                "rgba(0, 255, 159, 1)",
                "rgba(255, 71, 87, 1)",
                "rgba(99, 102, 241, 1)",
            ]
            datasets = []
            for idx, (company_name, data) in enumerate(
                projection_data_by_company.items()
            ):
                color = colors[idx % len(colors)]
                datasets.append({
                    "label": f"{company_name} ({data['growth_rate_pct']}% YoY)",
                    "data": data["projection"],
                    "borderColor": color,
                    "backgroundColor": "transparent",
                    "fill": False,
                    "tension": 0.5,
                    "pointRadius": 4,
                    "borderWidth": 2,
                })

            return {
                "type": "line",
                "title": "Path to $100M ARR",
                "data": {
                    "labels": labels,
                    "datasets": datasets,
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Path to 100M generation failed: {e}")
            return None

    def generate_cashflow_projection(
        self,
        companies: List[Dict[str, Any]],
        projection_years: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Generate cashflow projection chart from matrix companies (revenue → FCF)."""
        if not companies:
            return None
        try:
            labels = _generate_date_labels(projection_years)
            datasets = []
            for idx, company in enumerate(companies[:5]):
                name = company.get("company") or company.get("companyName") or "Unknown"
                arr = ensure_numeric(
                    company.get("revenue") or company.get("arr") or company.get("inferred_revenue"),
                    1_000_000,
                )
                growth = ensure_numeric(
                    company.get("growth_rate") or company.get("inferred_growth_rate"),
                    0.3,
                )
                if growth > 1 and growth < 10:
                    growth = growth / 100
                elif growth >= 10:
                    growth = growth / 100
                margin = ensure_numeric(company.get("gross_margin"), 0.65)
                if margin > 1:
                    margin = margin / 100
                fcf_conv = 0.8
                fcf_series = []
                rev = arr / 1_000_000
                for i in range(projection_years):
                    rev = rev * (1 + growth) * (0.95 ** i)  # Decay
                    fcf = rev * margin * fcf_conv
                    fcf_series.append(round(fcf, 2))
                colors = ["#065f46", "#047857", "#059669", "#10b981", "#34d399"]
                datasets.append({
                    "label": name,
                    "data": fcf_series,
                    "borderColor": colors[idx % len(colors)],
                    "backgroundColor": "transparent",
                    "fill": False,
                })
            return {
                "type": "line",
                "title": "Cashflow Projection (FCF $M)",
                "data": {"labels": labels, "datasets": datasets},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Cashflow projection failed: {e}")
            return None

    def generate_revenue_treemap(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Generate revenue treemap: company → ARR by company."""
        if not companies:
            return None
        try:
            children = []
            for c in companies:
                name = c.get("company") or c.get("companyName") or c.get("id") or "Unknown"
                arr = ensure_numeric(
                    c.get("revenue") or c.get("arr") or c.get("inferred_revenue"),
                    0,
                )
                if arr > 0:
                    children.append({"name": name, "value": arr})
            if not children:
                return None
            return {
                "type": "treemap",
                "title": "Revenue by Company",
                "data": {"children": children},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Revenue treemap failed: {e}")
            return None

    def generate_next_round_treemap(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Treemap segmented by funding round/stage.
        Uses valuation/funding data to enrich: pre/post, dilution, round.
        Output: nested by stage, then companies within each stage.
        """
        if not companies:
            return None
        try:
            stage_map = {
                "pre-seed": "Pre-Seed",
                "preseed": "Pre-Seed",
                "seed": "Seed",
                "series a": "Series A",
                "seriesa": "Series A",
                "series b": "Series B",
                "seriesb": "Series B",
                "series c": "Series C",
                "seriesc": "Series C",
                "growth": "Growth",
                "late": "Late",
            }
            by_stage: Dict[str, List[Dict[str, Any]]] = {}
            for c in companies:
                name = c.get("company") or c.get("companyName") or c.get("id") or "Unknown"
                stage_raw = str(c.get("stage") or c.get("funding_stage") or "").lower().strip()
                stage = stage_map.get(stage_raw.replace(" ", "").replace("-", "")) or stage_map.get(
                    stage_raw
                ) or "Unknown"
                # Value: valuation or total_funding for treemap size
                val = ensure_numeric(
                    c.get("valuation")
                    or c.get("current_valuation_usd")
                    or c.get("total_funding")
                    or c.get("total_raised"),
                    0,
                )
                if val <= 0:
                    val = ensure_numeric(
                        c.get("revenue") or c.get("arr") or c.get("inferred_revenue"),
                        1_000_000,
                    )
                if val > 0:
                    by_stage.setdefault(stage, []).append({"name": name, "value": val})
            if not by_stage:
                return None
            # Flat children with stage in label for current treemap renderer compatibility
            children = []
            for stage_name in sorted(by_stage.keys()):
                for item in by_stage[stage_name]:
                    children.append({
                        "name": f"{item['name']} ({stage_name})",
                        "value": item["value"],
                    })
            return {
                "type": "treemap",
                "title": "Portfolio by Funding Round",
                "data": {"children": children},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Next round treemap failed: {e}")
            return None

    def generate_revenue_growth_treemap(
        self,
        companies: List[Dict[str, Any]],
        period: str = "annual",
    ) -> Optional[Dict[str, Any]]:
        """
        Treemap of revenue growth by company for a given period.
        period: "monthly" | "quarter" | "annual". Same output shape as revenue treemap
        for existing TableauLevelCharts treemap (children with name, value).
        """
        if not companies:
            return None
        try:
            children = []
            for c in companies:
                name = c.get("company") or c.get("companyName") or c.get("id") or "Unknown"
                if period == "monthly":
                    growth = ensure_numeric(
                        c.get("revenue_growth_monthly_pct")
                        or c.get("revenueGrowthMonthly")
                        or c.get("growth_rate"),
                        0,
                    )
                    if growth is not None and growth != 0:
                        # Store as positive for treemap size (use abs for display)
                        children.append({"name": name, "value": round(abs(growth), 1)})
                elif period == "quarter":
                    monthly = ensure_numeric(
                        c.get("revenue_growth_monthly_pct") or c.get("revenueGrowthMonthly"),
                        0,
                    )
                    annual = ensure_numeric(
                        c.get("revenue_growth_annual_pct")
                        or c.get("revenueGrowthAnnual")
                        or c.get("growth_rate"),
                        0,
                    )
                    if monthly is not None and monthly != 0:
                        growth_q = monthly * 3
                    elif annual is not None and annual != 0:
                        growth_q = (annual * 100 if 0 < annual <= 2 else annual) / 4
                    else:
                        growth_q = None
                    if growth_q is not None and growth_q != 0:
                        children.append({"name": name, "value": round(abs(growth_q), 1)})
                else:
                    # annual
                    growth = ensure_numeric(
                        c.get("revenue_growth_annual_pct")
                        or c.get("revenueGrowthAnnual")
                        or c.get("growth_rate"),
                        0,
                    )
                    if growth is not None and growth != 0:
                        # Normalize to percentage: if decimal (e.g. 0.5 = 50%), scale up
                        if -1 <= growth <= 1 and growth != 0:
                            growth = growth * 100
                        children.append({"name": name, "value": round(abs(growth), 1)})
            if not children:
                return None
            titles = {
                "monthly": "Revenue growth (last month %)",
                "quarter": "Revenue growth (quarter %)",
                "annual": "Revenue growth (annual %)",
            }
            return {
                "type": "treemap",
                "title": titles.get(period, "Revenue growth"),
                "data": {"children": children},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Revenue growth treemap failed: {e}")
            return None

    def generate_revenue_multiple_scatter(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Scatter chart: growth rate (x) vs valuation multiple (y).
        Each point = company. Useful for portfolio positioning.
        """
        if not companies:
            return None
        try:
            points = []
            for c in companies:
                name = c.get("company") or c.get("companyName") or c.get("id") or "Unknown"
                rev = ensure_numeric(
                    c.get("revenue")
                    or c.get("arr")
                    or c.get("inferred_revenue")
                    or c.get("inferred_arr"),
                    0,
                )
                val = ensure_numeric(
                    c.get("valuation")
                    or c.get("current_valuation_usd")
                    or c.get("inferred_valuation"),
                    0,
                )
                growth = ensure_numeric(
                    c.get("growth_rate")
                    or c.get("inferred_growth_rate")
                    or c.get("revenue_growth_annual_pct"),
                    0,
                )
                if growth > 1 and growth < 10:
                    growth = growth * 100
                elif growth > 0 and growth < 1:
                    growth = growth * 100
                multiple = val / rev if rev and rev > 0 else 0
                if multiple > 0 and (growth != 0 or multiple > 0):
                    points.append({
                        "name": name,
                        "x": round(growth, 1),
                        "y": round(multiple, 1),
                        "z": min(rev / 1_000_000, 100) if rev else 10,
                    })
            if not points:
                return None
            return {
                "type": "scatter",
                "title": "Growth vs Valuation Multiple",
                "data": points,
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Revenue multiple scatter failed: {e}")
            return None

    def generate_revenue_multiples_scatter(
        self,
        grid_snapshot: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Scatter: X = ARR ($M), Y = Valuation/ARR multiple. Dot size = total funding.
        Works from grid snapshot (matrix rows), not company data array."""
        rows = grid_snapshot.get("rows", [])
        if not rows:
            return None
        try:
            stage_colors = {
                "seed": "#94a3b8",
                "series_a": "#3b82f6",
                "series_b": "#8b5cf6",
                "series_c": "#f59e0b",
                "growth": "#10b981",
            }
            datasets_by_stage: Dict[str, list] = {}

            for row in rows:
                cells = row.get("cells", {})
                # Helper to pull numeric from cell (may be dict with .value or raw)
                def _num(key: str, *alt_keys: str) -> float:
                    for k in (key, *alt_keys):
                        raw = cells.get(k)
                        if isinstance(raw, dict):
                            raw = raw.get("value")
                        val = ensure_numeric(raw, 0)
                        if val:
                            return val
                    return 0.0

                arr = _num("arr", "revenue", "annualRecurringRevenue")
                valuation = _num("valuation", "currentValuation", "current_valuation_usd")
                funding = _num("totalFunding", "totalRaised", "total_funding")

                if arr <= 0 or valuation <= 0:
                    continue

                multiple = valuation / arr
                name = row.get("companyName", row.get("rowId", ""))
                stage_raw = cells.get("fundingStage", "")
                if isinstance(stage_raw, dict):
                    stage_raw = stage_raw.get("value", "")
                stage = str(stage_raw).lower().replace(" ", "_")
                key = stage if stage in stage_colors else "other"

                point = {
                    "x": round(arr / 1e6, 2),
                    "y": round(multiple, 1),
                    "r": max(4, min(20, (funding or 1e6) / 1e7)),
                    "label": name,
                    "funding_stage": stage,
                }
                datasets_by_stage.setdefault(key, []).append(point)

            if not datasets_by_stage:
                return None

            datasets = []
            for stage, pts in datasets_by_stage.items():
                color = stage_colors.get(stage, "#6b7280")
                datasets.append({
                    "label": stage.replace("_", " ").title(),
                    "data": pts,
                    "backgroundColor": color + "80",
                    "borderColor": color,
                })

            return {
                "type": "scatter",
                "title": "Revenue Multiples (Valuation / ARR)",
                "data": {"datasets": datasets},
                "options": {
                    "scales": {
                        "x": {"title": {"display": True, "text": "ARR ($M)"}},
                        "y": {"title": {"display": True, "text": "Valuation / ARR Multiple"}},
                    },
                },
                "renderType": "tableau",
                "responsive": True,
            }
        except Exception as e:
            logger.warning(f"Revenue multiples scatter (grid) failed: {e}")
            return None

    def generate_product_velocity_ranking(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Generate product velocity ranking: growth + product signals → bar chart."""
        if not companies:
            return None
        try:
            scores = []
            for c in companies:
                name = c.get("company") or c.get("companyName") or c.get("id") or "Unknown"
                growth = ensure_numeric(
                    c.get("growth_rate") or c.get("inferred_growth_rate"),
                    0,
                )
                if growth > 1 and growth < 10:
                    growth = growth * 10
                elif growth >= 10:
                    pass
                else:
                    growth = growth * 100
                product_updates = 1 if c.get("product_updates") or c.get("productUpdates") else 0
                velocity = growth * 0.7 + (product_updates * 20) + 10
                scores.append({"name": name, "value": round(velocity, 1), "growth": growth})
            scores.sort(key=lambda x: x["value"], reverse=True)
            return {
                "type": "bar",
                "title": "Product Velocity Ranking",
                "data": {
                    "labels": [s["name"] for s in scores[:15]],
                    "datasets": [{"label": "Velocity", "data": [s["value"] for s in scores[:15]]}],
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Product velocity ranking failed: {e}")
            return None

    # ── New generators: wire every prompt chart type end-to-end ──────────

    def generate_waterfall(
        self,
        companies: List[Dict[str, Any]],
        metric: str = "nav_contribution",
    ) -> Optional[Dict[str, Any]]:
        """Waterfall chart: NAV contribution or exit proceeds by company.
        metric: 'nav_contribution' | 'exit_proceeds'
        """
        if not companies:
            return None
        try:
            items: List[Dict[str, Any]] = []
            running = 0.0
            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                if metric == "exit_proceeds":
                    val = ensure_numeric(
                        c.get("exit_proceeds")
                        or c.get("exit_value")
                        or c.get("expected_proceeds"),
                        0,
                    )
                else:
                    # NAV contribution: current value minus cost basis
                    current = ensure_numeric(
                        c.get("nav_contribution")
                        or c.get("current_nav")
                        or c.get("fair_value")
                        or c.get("valuation")
                        or c.get("inferred_valuation"),
                        0,
                    )
                    cost = ensure_numeric(
                        c.get("cost_basis")
                        or c.get("investment_amount")
                        or c.get("total_funding"),
                        0,
                    )
                    val = current - cost if current > 0 and cost > 0 else current
                if val == 0:
                    continue
                items.append({"name": name, "value": round(val / 1_000_000, 2)})
                running += val
            if not items:
                return None
            items.append({"name": "Total", "value": round(running / 1_000_000, 2)})
            title_map = {
                "nav_contribution": "NAV Contribution by Company ($M)",
                "exit_proceeds": "Exit Proceeds by Company ($M)",
            }
            return {
                "type": "waterfall",
                "title": title_map.get(metric, "Waterfall ($M)"),
                "data": {"items": items},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Waterfall generation failed: {e}")
            return None

    def generate_bar_comparison(
        self,
        companies: List[Dict[str, Any]],
        metric: str = "moic",
    ) -> Optional[Dict[str, Any]]:
        """Bar comparison chart: MOIC, ARR, or any metric across companies."""
        if not companies:
            return None
        try:
            metric_extractors = {
                "moic": lambda c: ensure_numeric(c.get("moic") or c.get("expected_moic"), 0),
                "arr": lambda c: ensure_numeric(
                    c.get("revenue") or c.get("arr") or c.get("inferred_revenue"), 0
                ) / 1_000_000,
                "valuation": lambda c: ensure_numeric(
                    c.get("valuation") or c.get("inferred_valuation"), 0
                ) / 1_000_000,
                "growth_rate": lambda c: ensure_numeric(
                    c.get("growth_rate") or c.get("inferred_growth_rate"), 0
                ) * (100 if ensure_numeric(c.get("growth_rate") or c.get("inferred_growth_rate"), 0) < 10 else 1),
            }
            extractor = metric_extractors.get(metric, metric_extractors["moic"])
            labels = []
            values = []
            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                val = extractor(c)
                if val != 0:
                    labels.append(name)
                    values.append(round(val, 2))
            if not labels:
                return None
            metric_labels = {
                "moic": "MOIC",
                "arr": "ARR ($M)",
                "valuation": "Valuation ($M)",
                "growth_rate": "Growth Rate (%)",
            }
            return {
                "type": "bar",
                "title": f"{metric_labels.get(metric, metric)} Comparison",
                "data": {
                    "labels": labels,
                    "datasets": [{"label": metric_labels.get(metric, metric), "data": values}],
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Bar comparison generation failed: {e}")
            return None

    def generate_cap_table_sankey(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Cap table Sankey: ownership flow through funding rounds.
        Uses stage and funding data to build round-by-round ownership flow.
        """
        if not companies:
            return None
        try:
            from app.services.pre_post_cap_table import PrePostCapTable
            cap_table = PrePostCapTable()
            # Use first company with enough data
            company = companies[0]
            name = company.get("company") or company.get("companyName") or "Unknown"
            stage = company.get("stage") or company.get("funding_stage") or "Series A"
            total_funding = ensure_numeric(
                company.get("total_funding") or company.get("total_raised"), 0
            )
            valuation = ensure_numeric(
                company.get("valuation") or company.get("inferred_valuation"), 0
            )
            if valuation <= 0:
                valuation = total_funding * 3 if total_funding > 0 else 100_000_000

            # Build synthetic round history for sankey
            stage_rounds = {
                "Seed": [("Seed", 0.15)],
                "Series A": [("Seed", 0.15), ("Series A", 0.20)],
                "Series B": [("Seed", 0.15), ("Series A", 0.20), ("Series B", 0.18)],
                "Series C": [("Seed", 0.15), ("Series A", 0.20), ("Series B", 0.18), ("Series C", 0.15)],
                "Growth": [("Seed", 0.15), ("Series A", 0.20), ("Series B", 0.18), ("Series C", 0.15), ("Growth", 0.12)],
            }
            rounds = stage_rounds.get(stage, stage_rounds["Series A"])

            nodes: List[Dict[str, Any]] = []
            links: List[Dict[str, Any]] = []
            node_id = 0
            # Track stakeholder ownership
            founders_pct = 1.0
            esop_pct = 0.0
            investor_pcts: Dict[str, float] = {}

            for round_name, dilution in rounds:
                # Pre-round snapshot
                pre_founders_id = node_id
                nodes.append({"id": node_id, "name": f"Founders", "round": round_name, "stage": "pre"})
                node_id += 1

                # New investor takes dilution from everyone
                new_inv_pct = dilution
                # Everyone gets diluted
                prev_founders = founders_pct
                founders_pct *= (1 - dilution)
                esop_pct *= (1 - dilution)
                for inv in investor_pcts:
                    investor_pcts[inv] *= (1 - dilution)

                # Add ESOP expansion at certain rounds
                if round_name in ("Series A", "Series B"):
                    esop_expansion = 0.05
                    founders_pct -= esop_expansion
                    esop_pct += esop_expansion

                investor_pcts[f"{round_name} Investors"] = new_inv_pct

                # Post-round nodes and links
                post_founders_id = node_id
                nodes.append({"id": node_id, "name": f"Founders", "round": round_name, "stage": "post"})
                node_id += 1
                links.append({"source": pre_founders_id, "target": post_founders_id, "value": max(0.001, founders_pct)})

                inv_node_id = node_id
                nodes.append({"id": node_id, "name": f"{round_name} Investors", "round": round_name, "stage": "post"})
                node_id += 1
                links.append({"source": pre_founders_id, "target": inv_node_id, "value": max(0.001, new_inv_pct)})

            return {
                "type": "sankey",
                "title": f"Cap Table: {name}",
                "data": {"nodes": nodes, "links": links},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Cap table sankey generation failed: {e}")
            return None

    def generate_dpi_sankey(
        self,
        companies: List[Dict[str, Any]],
        fund_size: float = 260_000_000,
    ) -> Optional[Dict[str, Any]]:
        """DPI Sankey: Fund → Investments → Exits/Unrealized NAV → LP Distributions.
        Infers NAV from stage + time since last funding when actual NAV is unavailable.
        """
        if not companies:
            return None
        try:
            nodes: List[Dict[str, Any]] = [{"id": "fund", "label": "Fund"}]
            links: List[Dict[str, Any]] = []
            total_invested = 0.0
            total_realized = 0.0
            total_unrealized = 0.0

            for c in companies:
                name = c.get("company") or c.get("companyName") or c.get("name") or "Unknown"
                node_id = f"co_{name.lower().replace(' ', '_')[:20]}"

                # Investment amount: actual or estimated
                invested = ensure_numeric(
                    c.get("investment_amount")
                    or c.get("cost_basis")
                    or c.get("invested"),
                    0,
                )
                if invested <= 0:
                    # Estimate: ~5-10% of total funding or proportional to fund
                    total_funding = ensure_numeric(c.get("total_funding") or c.get("total_raised"), 0)
                    invested = total_funding * 0.08 if total_funding > 0 else fund_size * 0.04
                if invested <= 0:
                    continue

                nodes.append({"id": node_id, "label": name})
                links.append({"source": "fund", "target": node_id, "value": invested})
                total_invested += invested

                # Realized exits
                realized = ensure_numeric(
                    c.get("realized") or c.get("distributions") or c.get("exit_proceeds"), 0
                )
                status = str(c.get("status") or "active").lower()

                if realized > 0 or status == "exited":
                    if realized <= 0:
                        realized = invested * 2  # conservative exit estimate
                    links.append({"source": node_id, "target": "realized", "value": realized, "type": "realized"})
                    total_realized += realized
                else:
                    # Unrealized NAV — infer from stage + time since funding
                    nav = self._infer_nav(c, invested)
                    links.append({"source": node_id, "target": "unrealized", "value": nav, "type": "unrealized"})
                    total_unrealized += nav

            if not links:
                return None

            # Terminal nodes
            if total_realized > 0:
                nodes.append({"id": "realized", "label": "Realized Exits"})
                nodes.append({"id": "lp_dist", "label": "LP Distributions"})
                # After carry/fees, ~80% goes to LPs
                lp_share = total_realized * 0.80
                links.append({"source": "realized", "target": "lp_dist", "value": lp_share, "type": "realized"})
            if total_unrealized > 0:
                nodes.append({"id": "unrealized", "label": "Unrealized NAV"})

            dpi = total_realized / total_invested if total_invested > 0 else 0.0
            tvpi = (total_realized + total_unrealized) / total_invested if total_invested > 0 else 0.0

            return {
                "type": "dpi_sankey",
                "title": f"Fund DPI Flow — DPI: {dpi:.2f}x | TVPI: {tvpi:.2f}x",
                "data": {"nodes": nodes, "links": links},
                "metrics": {
                    "total_invested": total_invested,
                    "total_realized": total_realized,
                    "total_unrealized": total_unrealized,
                    "dpi": round(dpi, 3),
                    "tvpi": round(tvpi, 3),
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"DPI sankey generation failed: {e}")
            return None

    def _infer_nav(self, company: Dict[str, Any], cost_basis: float) -> float:
        """Infer current NAV for a portfolio company from stage + time since funding.

        Priority:
        1. Explicit NAV / fair_value / current_nav
        2. Current valuation × ownership estimate
        3. Stage-based markup from cost basis, adjusted for time since last round
        """
        # 1. Explicit NAV
        explicit = ensure_numeric(
            company.get("nav_contribution")
            or company.get("current_nav")
            or company.get("fair_value"),
            0,
        )
        if explicit > 0:
            return explicit

        # 2. Valuation × estimated ownership
        valuation = ensure_numeric(
            company.get("valuation")
            or company.get("current_valuation_usd")
            or company.get("inferred_valuation"),
            0,
        )
        ownership = ensure_numeric(company.get("ownership_pct"), 0)
        if valuation > 0 and ownership > 0:
            own_frac = ownership / 100.0 if ownership > 1 else ownership
            return valuation * own_frac

        # 3. Stage-based markup × time adjustment
        stage = str(company.get("stage") or company.get("funding_stage") or "Series A").lower()
        # Typical step-up multiples from entry to "current fair value"
        stage_markup = {
            "pre-seed": 1.0, "pre seed": 1.0, "preseed": 1.0,
            "seed": 1.3,
            "series a": 1.8,
            "series b": 2.2,
            "series c": 2.0,
            "growth": 1.5,
            "late": 1.3,
        }
        base_markup = stage_markup.get(stage, 1.5)

        # Time adjustment: months since last funding → compound monthly appreciation
        months_since = ensure_numeric(company.get("months_since_funding"), 0)
        if months_since <= 0:
            # Try to compute from last round date
            from datetime import datetime
            last_round_date = company.get("last_round_date") or company.get("last_funding_date")
            if last_round_date:
                try:
                    if isinstance(last_round_date, str):
                        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
                            try:
                                dt = datetime.strptime(last_round_date[:10], fmt)
                                months_since = max(0, (datetime.now() - dt).days / 30.0)
                                break
                            except ValueError:
                                continue
                except Exception:
                    months_since = 12  # 1 year default

        if months_since <= 0:
            months_since = 12  # default 1 year

        # ~1.5% monthly appreciation for healthy startups, capped at 3x over time
        monthly_rate = 0.015
        time_multiplier = min(3.0, (1 + monthly_rate) ** months_since)

        # If valuation exists but no ownership, use valuation relative to funding
        if valuation > 0 and cost_basis > 0:
            return cost_basis * (valuation / (cost_basis * 3)) * time_multiplier

        return cost_basis * base_markup * time_multiplier

    def generate_bull_bear_base(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Bull/Bear/Base exit scenario comparison across companies.
        Returns grouped bar chart with three scenarios per company.
        """
        if not companies:
            return None
        try:
            labels = []
            bear_data = []
            base_data = []
            bull_data = []

            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                labels.append(name)

                # Use PWERM scenarios if available
                scenarios = c.get("pwerm_scenarios", [])
                if scenarios:
                    bear_val = 0
                    base_val = 0
                    bull_val = 0
                    for s in scenarios:
                        exit_val = ensure_numeric(
                            s.get("exit_value") if isinstance(s, dict) else getattr(s, "exit_value", 0), 0
                        )
                        scenario_name = (
                            s.get("scenario", "") if isinstance(s, dict) else getattr(s, "scenario", "")
                        ).lower()
                        if "bear" in scenario_name or "down" in scenario_name:
                            bear_val = max(bear_val, exit_val)
                        elif "bull" in scenario_name or "ipo" in scenario_name or "upside" in scenario_name:
                            bull_val = max(bull_val, exit_val)
                        else:
                            base_val = max(base_val, exit_val)
                    bear_data.append(round(bear_val / 1_000_000, 1))
                    base_data.append(round(base_val / 1_000_000, 1))
                    bull_data.append(round(bull_val / 1_000_000, 1))
                else:
                    # Infer from valuation
                    val = ensure_numeric(
                        c.get("valuation") or c.get("inferred_valuation"), 0
                    )
                    if val <= 0:
                        val = ensure_numeric(
                            c.get("revenue") or c.get("inferred_revenue"), 1_000_000
                        ) * 10
                    bear_data.append(round(val * 0.3 / 1_000_000, 1))
                    base_data.append(round(val * 1.0 / 1_000_000, 1))
                    bull_data.append(round(val * 3.0 / 1_000_000, 1))

            if not labels:
                return None

            return {
                "type": "bar",
                "title": "Bull / Bear / Base Exit Scenarios ($M)",
                "data": {
                    "labels": labels,
                    "datasets": [
                        {"label": "Bear", "data": bear_data, "backgroundColor": "#ef4444"},
                        {"label": "Base", "data": base_data, "backgroundColor": "#f59e0b"},
                        {"label": "Bull", "data": bull_data, "backgroundColor": "#22c55e"},
                    ],
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Bull/bear/base generation failed: {e}")
            return None

    def generate_radar_comparison(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Radar comparison chart: multi-dimensional scoring for team/moat/company comparison.
        Dimensions: Technical, Domain, Execution, Sales, Market Fit, Defensibility.
        """
        if not companies:
            return None
        try:
            dimensions = ["Technical", "Domain Expertise", "Execution", "Sales", "Market Fit", "Defensibility"]
            subjects = []

            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                # Use explicit scores if provided
                explicit_scores = c.get("radar_scores") or c.get("team_scores") or c.get("moat_scores")
                if explicit_scores and isinstance(explicit_scores, dict):
                    scores = [ensure_numeric(explicit_scores.get(d.lower().replace(" ", "_"), 5), 5) for d in dimensions]
                else:
                    # Infer scores from available data
                    scores = self._infer_radar_scores(c)
                subjects.append({"name": name, "scores": scores})

            if not subjects:
                return None

            return {
                "type": "radar_comparison",
                "title": "Company Comparison",
                "data": {
                    "dimensions": dimensions,
                    "subjects": subjects,
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Radar comparison generation failed: {e}")
            return None

    def _infer_radar_scores(self, company: Dict[str, Any]) -> List[float]:
        """Infer radar scores [Technical, Domain, Execution, Sales, Market Fit, Defensibility] from company data."""
        scores = [5.0] * 6  # default mid-range

        # Technical: higher if AI company or technical product
        desc = str(company.get("product_description") or company.get("description") or "").lower()
        if any(kw in desc for kw in ["ai", "ml", "machine learning", "deep learning", "algorithm"]):
            scores[0] = 7.5
        if company.get("technical_founder"):
            scores[0] = min(10, scores[0] + 1.5)

        # Domain Expertise: higher for vertical companies
        biz_model = str(company.get("business_model") or "").lower()
        if "vertical" in biz_model or any(kw in desc for kw in ["healthcare", "legal", "fintech", "construction"]):
            scores[1] = 7.5

        # Execution: infer from growth rate
        growth = ensure_numeric(company.get("growth_rate") or company.get("inferred_growth_rate"), 0)
        if growth > 2 or (growth > 0 and growth < 1 and growth * 100 > 100):
            scores[2] = 8.0
        elif growth > 1 or (growth > 0 and growth < 1 and growth * 100 > 50):
            scores[2] = 6.5

        # Sales: infer from revenue and customer data
        rev = ensure_numeric(company.get("revenue") or company.get("inferred_revenue"), 0)
        if rev > 50_000_000:
            scores[3] = 8.5
        elif rev > 10_000_000:
            scores[3] = 7.0
        elif rev > 1_000_000:
            scores[3] = 5.5

        # Market Fit: infer from stage progression + revenue
        stage = str(company.get("stage") or "").lower()
        if "series c" in stage or "growth" in stage:
            scores[4] = 8.0
        elif "series b" in stage:
            scores[4] = 7.0
        elif "series a" in stage:
            scores[4] = 5.5

        # Defensibility: infer from moat data if available
        moat = company.get("moat_score") or company.get("defensibility_score")
        if moat:
            scores[5] = min(10, ensure_numeric(moat, 5))
        elif "network" in desc or "data" in desc:
            scores[5] = 7.0

        return [round(s, 1) for s in scores]

    def generate_heatmap(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Heatmap: multi-dimensional scoring matrix (companies × dimensions)."""
        if not companies:
            return None
        try:
            dimensions = ["Growth", "Market Size", "Defensibility", "Capital Efficiency", "Team", "Product"]
            company_names = []
            all_scores: List[List[float]] = []

            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                company_names.append(name)

                explicit = c.get("heatmap_scores") or c.get("dimension_scores")
                if explicit and isinstance(explicit, dict):
                    row = [ensure_numeric(explicit.get(d.lower().replace(" ", "_"), 5), 5) for d in dimensions]
                else:
                    # Infer scores
                    growth = ensure_numeric(c.get("growth_rate") or c.get("inferred_growth_rate"), 0)
                    growth_score = min(10, max(1, growth * 3 if growth < 3 else 8))
                    tam = ensure_numeric(c.get("market_size") or c.get("tam"), 0)
                    market_score = min(10, max(1, 3 + (math.log10(max(tam, 1)) - 6) * 2)) if tam > 0 else 5
                    moat = ensure_numeric(c.get("moat_score") or c.get("defensibility_score"), 5)
                    rev = ensure_numeric(c.get("revenue") or c.get("inferred_revenue"), 0)
                    funding = ensure_numeric(c.get("total_funding"), 1)
                    cap_eff = min(10, max(1, (rev / funding) * 5)) if funding > 0 and rev > 0 else 4
                    team_score = 7 if c.get("technical_founder") else 5
                    product_score = 6
                    row = [round(growth_score, 1), round(market_score, 1), round(moat, 1),
                           round(cap_eff, 1), round(team_score, 1), round(product_score, 1)]
                all_scores.append(row)

            if not company_names:
                return None

            return {
                "type": "heatmap",
                "title": "Company Scoring Heatmap",
                "data": {
                    "dimensions": dimensions,
                    "companies": company_names,
                    "scores": all_scores,
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Heatmap generation failed: {e}")
            return None

    def generate_cap_table_evolution(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Cap table evolution: stacked area of ownership % across funding rounds."""
        if not companies:
            return None
        try:
            company = companies[0]
            stage = str(company.get("stage") or company.get("funding_stage") or "Series A")

            stage_rounds_map = {
                "Seed": ["Founding", "Seed"],
                "Series A": ["Founding", "Seed", "Series A"],
                "Series B": ["Founding", "Seed", "Series A", "Series B"],
                "Series C": ["Founding", "Seed", "Series A", "Series B", "Series C"],
                "Growth": ["Founding", "Seed", "Series A", "Series B", "Series C", "Growth"],
            }
            rounds = stage_rounds_map.get(stage, stage_rounds_map["Series A"])

            # Typical dilution schedule
            dilution_by_round = {
                "Founding": 0.0,
                "Seed": 0.15,
                "Series A": 0.20,
                "Series B": 0.18,
                "Series C": 0.15,
                "Growth": 0.12,
            }
            esop_expansion = {"Series A": 0.05, "Series B": 0.03}

            evolution = []
            founders = 1.0
            esop = 0.0
            investors: Dict[str, float] = {}

            for round_name in rounds:
                dilution = dilution_by_round.get(round_name, 0.15)
                if round_name == "Founding":
                    esop = 0.10
                    founders = 0.90
                    evolution.append({"round": round_name, "founders": founders, "esop": esop})
                    continue

                # Everyone diluted
                founders *= (1 - dilution)
                esop *= (1 - dilution)
                for inv in investors:
                    investors[inv] *= (1 - dilution)

                # ESOP expansion
                if round_name in esop_expansion:
                    exp = esop_expansion[round_name]
                    founders -= exp
                    esop += exp

                investors[f"{round_name} Investors"] = dilution

                entry = {"round": round_name, "founders": round(founders, 4), "esop": round(esop, 4)}
                for inv_name, inv_pct in investors.items():
                    entry[inv_name.lower().replace(" ", "_")] = round(inv_pct, 4)
                evolution.append(entry)

            return {
                "type": "cap_table_evolution",
                "title": f"Cap Table Evolution: {company.get('company', 'Company')}",
                "data": {"evolution": evolution},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Cap table evolution generation failed: {e}")
            return None

    def generate_stacked_bar(
        self,
        companies: List[Dict[str, Any]],
        metric: str = "funding_by_round",
    ) -> Optional[Dict[str, Any]]:
        """Stacked bar chart for funding by round or revenue breakdown."""
        if not companies:
            return None
        try:
            labels = []
            seed_data = []
            a_data = []
            b_data = []
            c_data = []

            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                labels.append(name)
                total = ensure_numeric(c.get("total_funding") or c.get("total_raised"), 0)
                stage = str(c.get("stage") or "Series A").lower()

                # Estimate round split from stage
                if "seed" in stage:
                    seed_data.append(round(total / 1e6, 1))
                    a_data.append(0)
                    b_data.append(0)
                    c_data.append(0)
                elif "series a" in stage:
                    seed_data.append(round(total * 0.2 / 1e6, 1))
                    a_data.append(round(total * 0.8 / 1e6, 1))
                    b_data.append(0)
                    c_data.append(0)
                elif "series b" in stage:
                    seed_data.append(round(total * 0.1 / 1e6, 1))
                    a_data.append(round(total * 0.3 / 1e6, 1))
                    b_data.append(round(total * 0.6 / 1e6, 1))
                    c_data.append(0)
                else:
                    seed_data.append(round(total * 0.05 / 1e6, 1))
                    a_data.append(round(total * 0.15 / 1e6, 1))
                    b_data.append(round(total * 0.30 / 1e6, 1))
                    c_data.append(round(total * 0.50 / 1e6, 1))

            if not labels:
                return None

            return {
                "type": "bar",
                "title": "Funding by Round ($M)",
                "data": {
                    "labels": labels,
                    "datasets": [
                        {"label": "Seed", "data": seed_data, "backgroundColor": "#94a3b8"},
                        {"label": "Series A", "data": a_data, "backgroundColor": "#3b82f6"},
                        {"label": "Series B", "data": b_data, "backgroundColor": "#8b5cf6"},
                        {"label": "Series C+", "data": c_data, "backgroundColor": "#f59e0b"},
                    ],
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Stacked bar generation failed: {e}")
            return None

    def generate_market_map(
        self,
        companies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Market map: bubble chart with market positioning.
        X = market maturity (stage), Y = growth rate, size = revenue.
        """
        if not companies:
            return None
        try:
            stage_x = {
                "pre-seed": 1, "seed": 2, "series a": 3, "series b": 4,
                "series c": 5, "growth": 6, "late": 7,
            }
            points = []
            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                stage = str(c.get("stage") or "Series A").lower()
                x = stage_x.get(stage, 3)
                growth = ensure_numeric(c.get("growth_rate") or c.get("inferred_growth_rate"), 0)
                if 0 < growth < 1:
                    growth *= 100
                elif growth > 10:
                    pass  # already %
                else:
                    growth *= 100
                rev = ensure_numeric(
                    c.get("revenue") or c.get("arr") or c.get("inferred_revenue"), 1_000_000
                )
                sector = c.get("sector") or c.get("industry") or "Other"
                points.append({
                    "name": name,
                    "x": x,
                    "y": round(growth, 1),
                    "z": max(5, min(30, rev / 2_000_000)),
                    "sector": sector,
                    "stage": stage.title(),
                })

            if not points:
                return None

            return {
                "type": "bubble",
                "title": "Market Map: Stage × Growth × Revenue",
                "data": points,
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Market map generation failed: {e}")
            return None

    def generate_nav_live(
        self,
        companies: List[Dict[str, Any]],
        fund_size: float = 260_000_000,
    ) -> Optional[Dict[str, Any]]:
        """Live NAV dashboard: bar chart with each company's inferred NAV.
        Uses _infer_nav for companies without explicit NAV.
        """
        if not companies:
            return None
        try:
            labels = []
            nav_values = []
            cost_values = []

            for c in companies:
                name = c.get("company") or c.get("companyName") or "Unknown"
                invested = ensure_numeric(
                    c.get("investment_amount") or c.get("cost_basis") or c.get("invested"), 0
                )
                if invested <= 0:
                    total_funding = ensure_numeric(c.get("total_funding"), 0)
                    invested = total_funding * 0.08 if total_funding > 0 else fund_size * 0.04
                if invested <= 0:
                    continue

                nav = self._infer_nav(c, invested)
                labels.append(name)
                nav_values.append(round(nav / 1_000_000, 2))
                cost_values.append(round(invested / 1_000_000, 2))

            if not labels:
                return None

            total_nav = sum(nav_values)
            total_cost = sum(cost_values)

            return {
                "type": "bar",
                "title": f"Live NAV by Company ($M) — Total: ${total_nav:.1f}M | MOIC: {total_nav/total_cost:.2f}x" if total_cost > 0 else "Live NAV by Company ($M)",
                "data": {
                    "labels": labels,
                    "datasets": [
                        {"label": "NAV ($M)", "data": nav_values, "backgroundColor": "#22c55e"},
                        {"label": "Cost Basis ($M)", "data": cost_values, "backgroundColor": "#94a3b8"},
                    ],
                },
                "metrics": {
                    "total_nav": round(total_nav, 2),
                    "total_cost": round(total_cost, 2),
                    "moic": round(total_nav / total_cost, 3) if total_cost > 0 else 0,
                },
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"NAV live generation failed: {e}")
            return None

    def generate_fpa_stress_test(
        self,
        companies: List[Dict[str, Any]],
        scenarios: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """FP&A stress test forecasting: project revenue under base/stress/severe scenarios.
        Shows impact of growth deceleration, churn increase, or market downturn.
        """
        if not companies:
            return None
        if scenarios is None:
            scenarios = ["base", "stress", "severe"]
        try:
            labels = _generate_date_labels(5)
            datasets = []
            colors_map = {
                "base": "#22c55e",
                "stress": "#f59e0b",
                "severe": "#ef4444",
            }
            # Scenario growth multipliers (applied to base growth)
            scenario_multipliers = {
                "base": 1.0,
                "stress": 0.5,   # 50% of base growth
                "severe": 0.0,   # zero growth (flat)
            }

            for scenario in scenarios:
                multiplier = scenario_multipliers.get(scenario, 1.0)
                total_revenue = []
                for year_idx in range(5):
                    year_total = 0.0
                    for c in companies:
                        rev = ensure_numeric(
                            c.get("revenue") or c.get("arr") or c.get("inferred_revenue"), 1_000_000
                        ) / 1_000_000
                        growth = ensure_numeric(c.get("growth_rate") or c.get("inferred_growth_rate"), 0.3)
                        if growth > 10:
                            growth = growth / 100
                        elif growth > 1:
                            growth = growth - 1
                        adj_growth = growth * multiplier
                        # Additional stress: churn increase in severe
                        if scenario == "severe" and year_idx > 1:
                            adj_growth -= 0.05 * (year_idx - 1)
                        projected = rev * ((1 + adj_growth) ** year_idx)
                        year_total += max(0, projected)
                    total_revenue.append(round(year_total, 2))

                datasets.append({
                    "label": f"{scenario.title()} Case",
                    "data": total_revenue,
                    "borderColor": colors_map.get(scenario, "#6b7280"),
                    "backgroundColor": "transparent",
                    "fill": False,
                    "borderDash": [5, 5] if scenario != "base" else [],
                    "tension": 0.3,
                })

            return {
                "type": "line",
                "title": "FP&A Stress Test — Portfolio Revenue Forecast ($M)",
                "data": {"labels": labels, "datasets": datasets},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"FP&A stress test generation failed: {e}")
            return None

    # ── Analytics-bridge generators ─────────────────────────────────────
    # These take raw output from FPARegressionService, ScenarioTreeService,
    # RevenueProjectionService etc. and transform into render-ready chart
    # configs using the shared format helpers below.

    def generate_sensitivity_tornado(
        self,
        sensitivity_result: Dict[str, Any],
        title: str = "Sensitivity Analysis",
    ) -> Optional[Dict[str, Any]]:
        """Transform FPA sensitivity_analysis output → tornado chart config.

        Expects ``sensitivity_result`` to have ``tornado_chart_data`` (list of
        ``{variable, min_impact, max_impact, ...}``).  Falls back to
        ``tornado_chart`` or ``results.tornado_chart`` for AnalyticsBridge
        format.
        """
        if not sensitivity_result:
            return None
        try:
            # Handle FPARegressionService format
            items = sensitivity_result.get("tornado_chart_data")
            # Handle AnalyticsBridge format
            if not items:
                items = sensitivity_result.get("tornado_chart")
            if not items and isinstance(sensitivity_result.get("results"), dict):
                items = sensitivity_result["results"].get("tornado_chart")
            if not items:
                return None
            tornado_items = []
            base_output = ensure_numeric(sensitivity_result.get("base_output") or
                                          (sensitivity_result.get("results") or {}).get("base_case_valuation"), 0)
            for item in items:
                tornado_items.append({
                    "name": item.get("variable") or item.get("factor", ""),
                    "low": ensure_numeric(item.get("min_impact") or item.get("low_impact"), 0),
                    "high": ensure_numeric(item.get("max_impact") or item.get("high_impact"), 0),
                    "base": base_output,
                })
            return format_tornado_chart(tornado_items, title=title)
        except Exception as e:
            logger.warning(f"Sensitivity tornado generation failed: {e}")
            return None

    def generate_regression_line(
        self,
        regression_result: Dict[str, Any],
        x_data: List[float] = None,
        y_data: List[float] = None,
        title: str = "Regression Analysis",
    ) -> Optional[Dict[str, Any]]:
        """Transform FPA linear_regression output → scatter + trendline chart.

        ``regression_result`` should have ``{slope, intercept, r_squared}``.
        If x_data/y_data are provided, plots actual points plus the fitted line.
        """
        if not regression_result:
            return None
        try:
            slope = ensure_numeric(regression_result.get("slope"), 0)
            intercept = ensure_numeric(regression_result.get("intercept"), 0)
            r_squared = ensure_numeric(regression_result.get("r_squared"), 0)

            datasets = []
            x_vals = x_data or []
            y_vals = y_data or []

            if x_vals and y_vals:
                # Scatter points of actual data
                datasets.append({
                    "label": "Observed",
                    "data": [{"x": x, "y": y} for x, y in zip(x_vals, y_vals)],
                    "type": "scatter",
                    "backgroundColor": "#6366f1",
                    "pointRadius": 4,
                })
                # Trend line
                x_min, x_max = min(x_vals), max(x_vals)
                datasets.append({
                    "label": f"Fit (R²={r_squared:.2f})",
                    "data": [
                        {"x": x_min, "y": slope * x_min + intercept},
                        {"x": x_max, "y": slope * x_max + intercept},
                    ],
                    "type": "line",
                    "borderColor": "#ef4444",
                    "borderWidth": 2,
                    "pointRadius": 0,
                    "fill": False,
                })

            return format_scatter_chart(
                datasets=datasets,
                title=f"{title} (R²={r_squared:.2f})",
                x_label="X",
                y_label="Y",
            )
        except Exception as e:
            logger.warning(f"Regression line generation failed: {e}")
            return None

    def generate_ltm_ntm_regression(
        self,
        companies: List[Dict[str, Any]],
        title: str = "LTM vs NTM Revenue — Portfolio Regression",
    ) -> Optional[Dict[str, Any]]:
        """Plot LTM and NTM revenue per company with regression trend lines.

        For each company, LTM = current ARR / trailing revenue,
        NTM = LTM × (1 + growth_rate).  X-axis = company index (ordered by LTM).
        Two scatter series (LTM, NTM) plus fitted regression lines for each.
        """
        if not companies:
            return None
        try:
            points = []
            for c in companies:
                name = c.get("company") or c.get("companyName") or c.get("name") or "?"
                ltm = ensure_numeric(
                    c.get("arr") or c.get("revenue") or c.get("inferred_revenue"), 0
                )
                if ltm <= 0:
                    continue
                growth = ensure_numeric(c.get("growth_rate") or c.get("yoy_growth"), 0)
                if growth > 10:
                    growth = growth / 100.0  # normalise 250 → 2.5
                ntm = ltm * (1 + growth) if growth else ltm * 1.20  # default 20% growth
                points.append({"name": name, "ltm": ltm, "ntm": ntm})

            if not points:
                return None

            points.sort(key=lambda p: p["ltm"])
            labels = [p["name"] for p in points]
            ltm_vals = [round(p["ltm"] / 1e6, 2) for p in points]
            ntm_vals = [round(p["ntm"] / 1e6, 2) for p in points]

            # Simple OLS regression y = mx + b
            def _ols(ys):
                n = len(ys)
                if n < 2:
                    return ys[:]
                xs = list(range(n))
                x_mean = sum(xs) / n
                y_mean = sum(ys) / n
                num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
                den = sum((x - x_mean) ** 2 for x in xs)
                slope = num / den if den else 0
                intercept = y_mean - slope * x_mean
                return [round(slope * x + intercept, 2) for x in xs]

            ltm_trend = _ols(ltm_vals)
            ntm_trend = _ols(ntm_vals)

            datasets = [
                {
                    "label": "LTM Revenue ($M)",
                    "data": ltm_vals,
                    "borderColor": "#3b82f6",
                    "backgroundColor": "#3b82f6",
                },
                {
                    "label": "NTM Revenue ($M)",
                    "data": ntm_vals,
                    "borderColor": "#22c55e",
                    "backgroundColor": "#22c55e",
                },
                {
                    "label": "LTM Trend",
                    "data": ltm_trend,
                    "borderColor": "#93bbfc",
                    "backgroundColor": "transparent",
                    "strokeDasharray": "6 3",
                },
                {
                    "label": "NTM Trend",
                    "data": ntm_trend,
                    "borderColor": "#86efac",
                    "backgroundColor": "transparent",
                    "strokeDasharray": "6 3",
                },
            ]

            return {
                "type": "ltm_ntm_regression",
                "title": title,
                "data": {"labels": labels, "datasets": datasets},
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"LTM/NTM regression generation failed: {e}")
            return None

    def generate_monte_carlo_histogram(
        self,
        mc_result: Dict[str, Any],
        variable: str = "revenue",
        title: str = None,
        bins: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """Transform Monte Carlo simulation output → histogram with percentile markers.

        Handles both FPARegressionService format (``{results, statistics}``)
        and AnalyticsBridge format (``{results.sample_simulations, results.confidence_intervals}``).
        """
        if not mc_result:
            return None
        try:
            # FPARegressionService format: list of scenario dicts
            raw_results = mc_result.get("results", [])
            stats = mc_result.get("statistics", {})

            values = []
            if isinstance(raw_results, list) and raw_results:
                if isinstance(raw_results[0], dict):
                    # Each result is a scenario dict — extract the variable
                    values = [ensure_numeric(r.get(variable), 0) for r in raw_results
                              if variable in r]
                elif isinstance(raw_results[0], (int, float)):
                    values = [float(v) for v in raw_results]

            # AnalyticsBridge format: sample_simulations under results
            if not values and isinstance(mc_result.get("results"), dict):
                samples = mc_result["results"].get("sample_simulations", [])
                values = [float(v) for v in samples if isinstance(v, (int, float))]

            if not values:
                return None

            # Build histogram bins
            v_min, v_max = min(values), max(values)
            if v_max <= v_min:
                return None
            bin_width = (v_max - v_min) / bins
            bin_labels = []
            bin_counts = []
            for i in range(bins):
                lo = v_min + i * bin_width
                hi = lo + bin_width
                count = sum(1 for v in values if lo <= v < hi)
                bin_labels.append(f"{lo / 1e6:.1f}M" if abs(lo) > 1e4 else f"{lo:.1f}")
                bin_counts.append(count)

            # Percentile markers from stats
            percentile_annotations = {}
            var_stats = stats.get(variable, {})
            if not var_stats and isinstance(mc_result.get("results"), dict):
                ci = mc_result["results"].get("confidence_intervals", {})
                var_stats = {
                    "p5": ci.get("10%"),
                    "median": mc_result["results"].get("median_valuation"),
                    "p95": ci.get("90%"),
                }
            for pct_key in ("p5", "median", "p95"):
                val = ensure_numeric(var_stats.get(pct_key))
                if val:
                    percentile_annotations[pct_key] = val

            chart_title = title or f"Monte Carlo — {variable.replace('_', ' ').title()} Distribution"
            return {
                "type": "bar",
                "title": chart_title,
                "data": {
                    "labels": bin_labels,
                    "datasets": [{
                        "label": "Frequency",
                        "data": bin_counts,
                        "backgroundColor": "#6366f1",
                    }],
                },
                "renderType": "tableau",
                "annotations": percentile_annotations,
            }
        except Exception as e:
            logger.warning(f"Monte Carlo histogram generation failed: {e}")
            return None

    def generate_revenue_forecast(
        self,
        projections: List[Dict[str, Any]],
        company_name: str = "",
        title: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Transform RevenueProjectionService output → dual-axis line chart.

        ``projections`` is ``[{year, revenue, growth_rate}, ...]`` from
        ``project_revenue_with_decay(return_projections=True)``.
        """
        if not projections:
            return None
        try:
            labels = [str(p.get("year", i + 1)) for i, p in enumerate(projections)]
            revenues = [ensure_numeric(p.get("revenue"), 0) / 1e6 for p in projections]
            growth_rates = [ensure_numeric(p.get("growth_rate"), 0) * 100 for p in projections]

            datasets = [
                {
                    "label": f"Revenue ($M){' — ' + company_name if company_name else ''}",
                    "data": [round(r, 2) for r in revenues],
                    "borderColor": "#22c55e",
                    "backgroundColor": "rgba(34,197,94,0.1)",
                    "fill": True,
                    "yAxisID": "y",
                    "tension": 0.3,
                },
                {
                    "label": "Growth Rate (%)",
                    "data": [round(g, 1) for g in growth_rates],
                    "borderColor": "#f59e0b",
                    "backgroundColor": "transparent",
                    "fill": False,
                    "yAxisID": "y1",
                    "borderDash": [5, 5],
                    "tension": 0.3,
                },
            ]
            chart_title = title or f"Revenue Forecast{' — ' + company_name if company_name else ''}"
            return format_line_chart(labels=labels, datasets=datasets, title=chart_title)
        except Exception as e:
            logger.warning(f"Revenue forecast generation failed: {e}")
            return None

    def generate_fund_scenario_comparison(
        self,
        scenario_bundle: Dict[str, Any],
        title: str = "Scenario Analysis Overview",
    ) -> Optional[Dict[str, Any]]:
        """Transform ScenarioTreeService.to_all_charts() bundle → enriched chart set.

        Returns the bundle as-is (it's already chart-ready) but ensures every
        sub-chart has ``renderType: "tableau"`` and fills missing fields.
        """
        if not scenario_bundle or not isinstance(scenario_bundle, dict):
            return None
        try:
            # Ensure all sub-charts have renderType
            for key, chart in scenario_bundle.items():
                if isinstance(chart, dict) and chart.get("type"):
                    chart.setdefault("renderType", "tableau")

            # Return as a multi-chart bundle
            return {
                "type": "multi_chart",
                "title": title,
                "charts": scenario_bundle,
                "renderType": "tableau",
            }
        except Exception as e:
            logger.warning(f"Fund scenario comparison generation failed: {e}")
            return None


# ── Shared chart format helpers ─────────────────────────────────────────
# Stateless functions that produce consistently-structured chart dicts.
# Used by the orchestrator, memo service, and deck export service so every
# chart goes through the same shape — no ad-hoc dict construction.


def format_sankey_chart(
    nodes: List[Dict], links: List[Dict], title: str = None, **kwargs
) -> Dict[str, Any]:
    """Format Sankey chart data consistently."""
    chart_data: Dict[str, Any] = {
        "type": "sankey",
        "data": {"nodes": nodes, "links": links},
        "renderType": "tableau",
    }
    if title:
        chart_data["title"] = title
    chart_data.update(kwargs)
    return chart_data


def format_side_by_side_sankey_chart(
    company1_data: Dict[str, Any],
    company2_data: Dict[str, Any],
    company1_name: str,
    company2_name: str,
    title: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """Format side-by-side Sankey chart data consistently."""
    chart_data: Dict[str, Any] = {
        "type": "side_by_side_sankey",
        "data": {
            "company1_data": company1_data,
            "company2_data": company2_data,
            "company1_name": company1_name,
            "company2_name": company2_name,
        },
        "renderType": "tableau",
    }
    if title:
        chart_data["title"] = title
    if kwargs:
        chart_data["data"].update(kwargs)
    return chart_data


def format_probability_cloud_chart(
    scenario_curves: List[Dict],
    breakpoint_clouds: List[Dict],
    decision_zones: List[Dict],
    config: Dict[str, Any],
    insights: Dict[str, Any] = None,
    title: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """Format probability cloud chart data consistently."""
    chart_data: Dict[str, Any] = {
        "type": "probability_cloud",
        "data": {
            "scenario_curves": scenario_curves,
            "breakpoint_clouds": breakpoint_clouds,
            "decision_zones": decision_zones,
            "config": config,
        },
        "renderType": "tableau",
    }
    if title:
        chart_data["title"] = title
    if insights:
        chart_data["data"]["insights"] = insights
    chart_data.update(kwargs)
    return chart_data


def format_heatmap_chart(
    dimensions: List[str],
    companies: List[str],
    scores: List[List[float]],
    weights: Dict[str, int] = None,
    title: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """Format heatmap chart data consistently."""
    chart_data: Dict[str, Any] = {
        "type": "heatmap",
        "data": {
            "dimensions": dimensions,
            "companies": companies,
            "scores": scores,
        },
        "renderType": "tableau",
    }
    if title:
        chart_data["title"] = title
    if weights:
        chart_data["data"]["weights"] = weights
    if kwargs:
        for key, value in kwargs.items():
            if key.startswith("data_"):
                chart_data["data"][key[5:]] = value
            else:
                chart_data[key] = value
    return chart_data


def format_waterfall_chart(
    items: List[Dict[str, Any]], title: str = None
) -> Dict[str, Any]:
    """Format waterfall chart data consistently."""
    return {"type": "waterfall", "data": {"items": items}, "title": title, "renderType": "tableau"}


def format_bar_chart(
    labels: List[str],
    datasets: List[Dict[str, Any]],
    title: str = None,
) -> Dict[str, Any]:
    """Format bar chart data consistently."""
    return {
        "type": "bar",
        "data": {"labels": labels, "datasets": datasets},
        "title": title,
        "renderType": "tableau",
    }


def format_line_chart(
    labels: List[str],
    datasets: List[Dict[str, Any]],
    title: str = None,
) -> Dict[str, Any]:
    """Format line chart data consistently."""
    return {
        "type": "line",
        "data": {"labels": labels, "datasets": datasets},
        "title": title,
        "renderType": "tableau",
    }


def format_pie_chart(
    labels: List[str], data: List[float], title: str = None
) -> Dict[str, Any]:
    """Format pie chart data consistently."""
    return {
        "type": "pie",
        "data": {"labels": labels, "datasets": [{"label": "Distribution", "data": data}]},
        "title": title,
        "renderType": "tableau",
    }


def format_treemap_chart(
    children: List[Dict[str, Any]], title: str = None
) -> Dict[str, Any]:
    """Format treemap chart data consistently.

    ``children`` should be ``[{name, value, ...}, ...]``.
    """
    return {
        "type": "treemap",
        "data": {"children": children},
        "title": title,
        "renderType": "tableau",
    }


def format_scatter_chart(
    datasets: List[Dict[str, Any]],
    title: str = None,
    x_label: str = "X",
    y_label: str = "Y",
) -> Dict[str, Any]:
    """Format scatter chart data consistently.

    Each dataset should have ``{label, data: [{x, y}, ...], ...}``.
    """
    return {
        "type": "scatter",
        "data": {"datasets": datasets},
        "title": title,
        "renderType": "tableau",
        "options": {"x_label": x_label, "y_label": y_label},
    }


def format_radar_chart(
    labels: List[str],
    datasets: List[Dict[str, Any]],
    title: str = None,
) -> Dict[str, Any]:
    """Format radar chart data consistently.

    ``labels`` are the spoke labels; each dataset has ``{label, data: [...]}``.
    """
    return {
        "type": "radar_comparison",
        "data": {"labels": labels, "datasets": datasets},
        "title": title,
        "renderType": "tableau",
    }


def format_tornado_chart(
    items: List[Dict[str, Any]], title: str = None
) -> Dict[str, Any]:
    """Format tornado chart data consistently.

    ``items`` should be ``[{name, low, high, base}, ...]``.
    """
    return {
        "type": "tornado",
        "data": {"items": items},
        "title": title,
        "renderType": "tableau",
    }
