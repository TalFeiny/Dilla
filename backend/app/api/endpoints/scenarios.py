"""
Scenario Analysis and Modeling Endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import random

from app.services.python_executor import python_executor

router = APIRouter()
logger = logging.getLogger(__name__)


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
        result = await python_executor.execute_scenario_analysis(
            company_data=request.company_data,
            num_scenarios=request.num_scenarios
        )
        
        # Add scenario categorization
        scenarios = []
        for i in range(request.num_scenarios):
            scenario_type = random.choice(["base", "upside", "downside"])
            value = request.company_data.get("current_valuation", 10000000)
            
            if scenario_type == "upside" and request.include_upside:
                value *= random.uniform(2, 10)
            elif scenario_type == "downside" and request.include_downside:
                value *= random.uniform(0.1, 0.8)
            else:
                value *= random.uniform(0.8, 2)
            
            scenarios.append({
                "id": i,
                "type": scenario_type,
                "exit_value": value,
                "probability": random.uniform(0, 1),
                "time_to_exit": random.randint(1, request.time_horizon)
            })
        
        return {
            "company_id": request.company_id,
            "scenarios": scenarios[:10],  # Return sample
            "total_scenarios": request.num_scenarios,
            "expected_value": sum(s["exit_value"] * s["probability"] for s in scenarios) / len(scenarios),
            "execution_result": result
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