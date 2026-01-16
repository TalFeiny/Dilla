"""
Scenario Analysis and Modeling Endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from app.services.valuation_engine_service import (
    ValuationEngineService,
    ValuationRequest,
    Stage,
)

router = APIRouter()
logger = logging.getLogger(__name__)

valuation_engine = ValuationEngineService()


def _map_stage(stage_str: Optional[str]) -> Stage:
    if not stage_str:
        return Stage.SERIES_A
    normalized = stage_str.strip().lower()
    if "pre" in normalized and "seed" in normalized:
        return Stage.SEED
    if "seed" in normalized:
        return Stage.SEED
    if "series a" in normalized or normalized in {"a", "series_a"}:
        return Stage.SERIES_A
    if "series b" in normalized or normalized in {"b", "series_b"}:
        return Stage.SERIES_B
    if "series c" in normalized or normalized in {"c", "series_c"}:
        return Stage.SERIES_C
    if "series d" in normalized or normalized in {"d", "series_d"} or "growth" in normalized:
        return Stage.GROWTH
    if "late" in normalized:
        return Stage.LATE
    if "public" in normalized:
        return Stage.PUBLIC
    return Stage.SERIES_A


def _fallback_total_raised(stage: Stage) -> float:
    return {
        Stage.SEED: 5_000_000,
        Stage.SERIES_A: 15_000_000,
        Stage.SERIES_B: 40_000_000,
        Stage.SERIES_C: 75_000_000,
        Stage.GROWTH: 120_000_000,
        Stage.LATE: 200_000_000,
        Stage.PUBLIC: 250_000_000,
    }.get(stage, 20_000_000)


class ScenarioRequest(BaseModel):
    company_id: str
    company_data: Dict[str, Any]
    num_scenarios: int = 100
    include_downside: bool = True
    include_upside: bool = True
    time_horizon: int = 5  # years


class LiquidationAnalysisRequest(BaseModel):
    company_id: str
    current_valuation: float
    liquidation_preferences: List[Dict[str, Any]]
    exit_value: Optional[float] = None


@router.post("/run")
async def run_scenarios(request: ScenarioRequest):
    """Run scenario analysis"""
    try:
        company = request.company_data or {}

        stage = _map_stage(
            company.get("stage")
            or company.get("funding_stage")
            or company.get("stage_name")
        )

        revenue = company.get("revenue") or company.get("inferred_revenue")
        try:
            revenue = float(revenue) if revenue is not None else 10_000_000
        except (TypeError, ValueError):
            revenue = 10_000_000

        growth_rate = (
            company.get("growth_rate")
            or company.get("revenue_growth")
            or company.get("inferred_growth_rate")
            or 0.5
        )
        try:
            growth_rate = float(growth_rate)
        except (TypeError, ValueError):
            growth_rate = 0.5

        valuation = (
            company.get("valuation")
            or company.get("current_valuation")
            or company.get("inferred_valuation")
            or 100_000_000
        )
        try:
            valuation = float(valuation)
        except (TypeError, ValueError):
            valuation = 100_000_000

        total_raised = (
            company.get("total_funding")
            or company.get("total_raised")
            or company.get("inferred_total_funding")
            or _fallback_total_raised(stage)
        )
        try:
            total_raised = float(total_raised)
        except (TypeError, ValueError):
            total_raised = _fallback_total_raised(stage)

        request_payload = ValuationRequest(
            company_name=company.get("company") or request.company_id,
            stage=stage,
            revenue=revenue,
            growth_rate=growth_rate,
            last_round_valuation=valuation,
            total_raised=total_raised,
            business_model=company.get("business_model"),
            industry=company.get("sector") or company.get("industry"),
            category=company.get("category"),
            ai_component_percentage=company.get("ai_component_percentage")
            or company.get("ai_percentage"),
        )

        valuation_result = await valuation_engine.calculate_valuation(request_payload)
        scenarios = valuation_result.scenarios or []
        if not scenarios:
            raise HTTPException(status_code=502, detail="No scenarios produced by valuation service")

        scenarios_sorted = sorted(scenarios, key=lambda s: s.exit_value)
        cumulative = 0.0
        p10 = p50 = p90 = scenarios_sorted[-1].exit_value
        for scenario in scenarios_sorted:
            cumulative += scenario.probability
            if cumulative >= 0.1 and p10 == scenarios_sorted[-1].exit_value:
                p10 = scenario.exit_value
            if cumulative >= 0.5 and p50 == scenarios_sorted[-1].exit_value:
                p50 = scenario.exit_value
            if cumulative >= 0.9:
                p90 = scenario.exit_value
                break

        expected_exit = sum(s.exit_value * s.probability for s in scenarios)
        expected_present_value = sum(s.present_value * s.probability for s in scenarios)

        payload = [
            {
                "scenario": s.scenario,
                "probability": s.probability,
                "exit_value": s.exit_value,
                "present_value": getattr(s, "present_value", None),
                "moic": getattr(s, "moic", None),
                "time_to_exit": s.time_to_exit,
                "funding_path": s.funding_path,
                "exit_type": s.exit_type,
                "return_curve": getattr(s, "return_curve", {}),
            }
            for s in scenarios
        ]

        return {
            "company_id": request.company_id,
            "total_scenarios": len(payload),
            "expected_exit": expected_exit,
            "expected_present_value": expected_present_value,
            "median_exit": p50,
            "p10_exit": p10,
            "p90_exit": p90,
            "scenarios": payload[: request.num_scenarios],
            "fair_value": valuation_result.fair_value,
            "method": valuation_result.method_used,
            "assumptions": valuation_result.assumptions,
            "execution_result": {
                "engine": "valuation-service",
                "notes": "Scenarios generated via PWERM valuation engine",
            },
        }

    except Exception as e:
        logger.error(f"Scenario analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/liquidation-analysis")
async def liquidation_analysis(request: LiquidationAnalysisRequest):
    """Analyze liquidation preferences and waterfall"""
    try:
        # Calculate liquidation waterfall
        exit_value = request.exit_value or request.current_valuation * 1.5
        
        distributions = []
        remaining = exit_value
        
        for pref in request.liquidation_preferences:
            if remaining <= 0:
                break
            
            amount = min(remaining, pref.get("amount", 0))
            distributions.append({
                "investor": pref.get("investor", "Unknown"),
                "class": pref.get("class", "Common"),
                "preference": pref.get("amount", 0),
                "distribution": amount
            })
            remaining -= amount
        
        return {
            "company_id": request.company_id,
            "exit_value": exit_value,
            "total_preferences": sum(p.get("amount", 0) for p in request.liquidation_preferences),
            "distributions": distributions,
            "common_pool": max(0, remaining),
            "waterfall_complete": True
        }
        
    except Exception as e:
        logger.error(f"Liquidation analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def get_scenario_templates():
    """Get pre-defined scenario templates"""
    return {
        "templates": [
            {
                "name": "Conservative Growth",
                "description": "Modest growth with limited downside",
                "parameters": {
                    "growth_range": [0.1, 0.3],
                    "exit_multiple_range": [2, 4],
                    "probability_of_success": 0.7
                }
            },
            {
                "name": "Aggressive Growth",
                "description": "High growth with higher risk",
                "parameters": {
                    "growth_range": [0.5, 1.5],
                    "exit_multiple_range": [5, 20],
                    "probability_of_success": 0.4
                }
            },
            {
                "name": "Recession Case",
                "description": "Downside scenario with market contraction",
                "parameters": {
                    "growth_range": [-0.2, 0.1],
                    "exit_multiple_range": [0.5, 2],
                    "probability_of_success": 0.3
                }
            }
        ]
    }
