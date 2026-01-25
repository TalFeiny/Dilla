"""
Scenarios API Endpoints
API for scenario analysis
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from app.services.scenario_analyzer import ScenarioAnalyzer, ScenarioType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

# Initialize service
scenario_analyzer = ScenarioAnalyzer()


class CreateScenarioRequest(BaseModel):
    model_id: str
    scenario_name: str
    scenario_type: str
    probability: float = 0.33
    factor_overrides: Optional[Dict[str, Any]] = None
    relationship_changes: Optional[Dict[str, Any]] = None
    temporal_changes: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


@router.post("/create")
async def create_scenario(request: CreateScenarioRequest):
    """Create a scenario for a world model"""
    try:
        scenario_type = ScenarioType(request.scenario_type)
        
        scenario = await scenario_analyzer.create_scenario(
            model_id=request.model_id,
            scenario_name=request.scenario_name,
            scenario_type=scenario_type,
            probability=request.probability,
            factor_overrides=request.factor_overrides,
            relationship_changes=request.relationship_changes,
            temporal_changes=request.temporal_changes,
            description=request.description
        )
        return scenario
    except Exception as e:
        logger.error(f"Error creating scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{scenario_id}/execute")
async def execute_scenario(scenario_id: str):
    """Execute a scenario and calculate results"""
    try:
        results = await scenario_analyzer.execute_scenario(scenario_id)
        return results
    except Exception as e:
        logger.error(f"Error executing scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/{model_id}/compare")
async def compare_scenarios(model_id: str):
    """Compare all scenarios for a model"""
    try:
        comparison = await scenario_analyzer.compare_scenarios(model_id)
        return comparison
    except Exception as e:
        logger.error(f"Error comparing scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model/{model_id}/create-standard")
async def create_standard_scenarios(model_id: str):
    """Create standard base case, upside, and downside scenarios"""
    try:
        scenarios = await scenario_analyzer.create_standard_scenarios(model_id)
        return scenarios
    except Exception as e:
        logger.error(f"Error creating standard scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))
