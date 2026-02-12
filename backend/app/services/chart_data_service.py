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
