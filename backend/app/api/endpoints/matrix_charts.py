"""
Matrix Charts API - Generate charts from matrix data for ChartViewport.
Supports: sankey, waterfall, heatmap, path_to_100m, probability_cloud, cashflow,
revenue_treemap, product_velocity, dpi_sankey, auto.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.skills.chart_generation_skill import ChartGenerationSkill
from app.services.chart_data_service import ChartDataService

logger = logging.getLogger(__name__)


def _build_dpi_sankey(fund_id: str) -> Optional[Dict[str, Any]]:
    """Build DPI Sankey from portfolio. Live with portfolio data."""
    try:
        from app.core.database import supabase_service
        client = supabase_service.get_client()
        if not client:
            return None
        portfolio_response = client.from_("portfolio_companies").select(
            "*, companies(*)"
        ).eq("fund_id", fund_id).execute()
        companies = portfolio_response.data if portfolio_response.data else []
        nodes = [{"id": 0, "name": f"Fund {fund_id[:8]}...", "level": 0}]
        links = []
        total_invested = 0
        total_distributed = 0
        node_id = 1
        for pc in companies:
            company = pc.get("companies", {})
            company_name = company.get("name", f"Company {node_id}")
            investment = pc.get("investment_amount", 0) or pc.get("total_invested_usd", 0) or 0
            ownership_pct = pc.get("ownership_pct", 0) or pc.get("ownership_percentage", 0) or 0
            status = pc.get("status") or company.get("status", "active")
            total_invested += investment
            nodes.append({"id": node_id, "name": company_name, "level": 1})
            links.append({"source": 0, "target": node_id, "value": investment})
            if status == "exited":
                exit_value = pc.get("exit_value_usd") or company.get("exit_value_usd", 0) or 0
                distributed = (ownership_pct / 100) * exit_value
                total_distributed += distributed
                exit_node_id = node_id + 1000
                nodes.append({"id": exit_node_id, "name": f"{company_name} Exit", "level": 2})
                dist_node_id = node_id + 2000
                if not any(n["id"] == dist_node_id for n in nodes):
                    nodes.append({"id": dist_node_id, "name": "LP Distributions", "level": 3})
                links.append({"source": node_id, "target": exit_node_id, "value": exit_value})
                links.append({"source": exit_node_id, "target": dist_node_id, "value": distributed})
            node_id += 1
        dpi = total_distributed / total_invested if total_invested > 0 else 0
        return {
            "type": "sankey",
            "title": f"DPI Flow: {dpi:.2f}x (Follow-on Strategy)",
            "data": {"nodes": nodes, "links": links},
            "renderType": "tableau",
        }
    except Exception as e:
        logger.warning(f"DPI Sankey build failed: {e}")
        return None

router = APIRouter(prefix="/matrix/charts", tags=["matrix-charts"])


class ChartGenerateRequest(BaseModel):
    fund_id: Optional[str] = None
    matrix_data: Dict[str, Any]
    chart_type: str = "auto"


class ChartGenerateResponse(BaseModel):
    charts: List[Dict[str, Any]]
    chart_count: int


def _matrix_to_companies(matrix_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transform matrix rows into company dicts for chart services."""
    rows = matrix_data.get("rows") or matrix_data.get("companies") or []
    companies = []
    for row in rows:
        if isinstance(row, dict):
            # Already company-like
            cells = row.get("cells") or {}
            company = {
                "company": row.get("companyName") or row.get("company") or row.get("id"),
                "id": row.get("id"),
            }
            field_map = {
                "arr": "revenue",
                "currentArr": "revenue",
                "valuation": "valuation",
                "currentValuation": "valuation",
                "burnRate": "burn_rate",
                "runway": "runway_months",
                "runwayMonths": "runway_months",
                "cashInBank": "cash_balance",
                "grossMargin": "gross_margin",
                "totalInvested": "total_funding",
                "sector": "sector",
                "stage": "stage",
                "revenueGrowthMonthly": "revenue_growth_monthly_pct",
                "revenueGrowthAnnual": "revenue_growth_annual_pct",
                "growth_rate": "growth_rate",
            }
            for col_id, cell in cells.items():
                val = cell.get("value") if isinstance(cell, dict) else cell
                if val is None or val == "":
                    continue
                field = field_map.get(col_id, col_id)
                if field in ("company", "sector", "stage"):
                    company[field] = str(val)
                else:
                    try:
                        if isinstance(val, (int, float)):
                            company[field] = val
                        else:
                            company[field] = float(str(val).replace("$", "").replace(",", "").replace("%", ""))
                    except (ValueError, TypeError):
                        company[field] = val
            companies.append(company)
    return companies


@router.post("/generate", response_model=ChartGenerateResponse)
async def generate_charts(request: ChartGenerateRequest) -> ChartGenerateResponse:
    """
    Generate charts from matrix data.
    chart_type: auto | sankey | waterfall | heatmap | path_to_100m | probability_cloud |
    cashflow | revenue_treemap | revenue_growth_treemap | product_velocity | dpi_sankey
    """
    matrix_data = request.matrix_data
    chart_type = (request.chart_type or "auto").lower().strip()
    fund_id = request.fund_id
    companies = _matrix_to_companies(matrix_data)

    charts: List[Dict[str, Any]] = []

    try:
        if chart_type in ("dpi_sankey", "auto") and fund_id:
            dpi = _build_dpi_sankey(fund_id)
            if dpi:
                charts.append(dpi)

        if chart_type in ("path_to_100m", "path_to_100m_arr", "auto"):
            if companies:
                chart_svc = ChartDataService()
                path_chart = chart_svc.generate_path_to_100m(companies)
                if path_chart:
                    charts.append(path_chart)

        if chart_type in ("probability_cloud", "auto"):
            if companies:
                chart_svc = ChartDataService()
                # Use first company, check_size from valuation or default
                first = companies[0]
                check_size = float(
                    first.get("total_funding") or first.get("valuation") or 5_000_000
                ) * 0.08
                if check_size <= 0:
                    check_size = 5_000_000 * 0.08
                prob_chart = chart_svc.generate_probability_cloud(first, check_size)
                if prob_chart:
                    charts.append(prob_chart)

        if chart_type in ("cashflow", "cashflow_projection", "auto"):
            if companies:
                chart_svc = ChartDataService()
                cf_chart = chart_svc.generate_cashflow_projection(companies)
                if cf_chart:
                    charts.append(cf_chart)

        if chart_type in ("revenue_treemap", "treemap", "auto"):
            if companies:
                chart_svc = ChartDataService()
                tm_chart = chart_svc.generate_revenue_treemap(companies)
                if tm_chart:
                    charts.append(tm_chart)

        if chart_type in ("next_round_treemap", "treemap", "auto"):
            if companies:
                chart_svc = ChartDataService()
                next_round = chart_svc.generate_next_round_treemap(companies)
                if next_round:
                    charts.append(next_round)

        if chart_type in ("revenue_growth_treemap", "auto"):
            if companies:
                chart_svc = ChartDataService()
                for period in ("monthly", "quarter", "annual"):
                    growth_tm = chart_svc.generate_revenue_growth_treemap(companies, period=period)
                    if growth_tm:
                        charts.append(growth_tm)

        if chart_type in ("product_velocity", "velocity_ranking", "auto"):
            if companies:
                chart_svc = ChartDataService()
                vel_chart = chart_svc.generate_product_velocity_ranking(companies)
                if vel_chart:
                    charts.append(vel_chart)

        if chart_type in ("scatter", "revenue_multiple_scatter", "auto"):
            if companies:
                chart_svc = ChartDataService()
                scatter_chart = chart_svc.generate_revenue_multiple_scatter(companies)
                if scatter_chart:
                    charts.append(scatter_chart)

        if chart_type in ("sankey", "waterfall", "heatmap", "auto"):
            chart_skill = ChartGenerationSkill()
            inp = {
                "data": {"companies": companies},
                "chart_type": chart_type if chart_type not in ("path_to_100m", "probability_cloud") else "auto",
            }
            result = await chart_skill.execute(inp)
            if result.get("success") and result.get("charts"):
                for c in result["charts"]:
                    config = {
                        "type": c.get("type", "bar"),
                        "title": c.get("title", "Generated Chart"),
                        "data": c.get("data", {}),
                        "renderType": c.get("renderType", "tableau"),
                    }
                    charts.append(config)

        # Deduplicate by (type, title) so multiple treemaps (e.g. growth by period) are kept
        seen: set = set()
        unique_charts = []
        for c in charts:
            key = (c.get("type", "unknown"), c.get("title") or "")
            if key not in seen:
                seen.add(key)
                unique_charts.append(c)

        return ChartGenerateResponse(charts=unique_charts, chart_count=len(unique_charts))

    except Exception as e:
        logger.exception("Chart generation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
