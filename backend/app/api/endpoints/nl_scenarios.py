"""
Natural Language Scenario API
"What happens if..." query endpoint
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from app.services.nl_scenario_composer import NLScenarioComposer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nl-scenarios", tags=["nl-scenarios"])

# Initialize service
composer = NLScenarioComposer()


class WhatIfQueryRequest(BaseModel):
    query: str
    model_id: Optional[str] = None
    fund_id: Optional[str] = None


class ComposeScenarioRequest(BaseModel):
    query: str
    model_id: str
    fund_id: Optional[str] = None


class EvaluateScenarioRequest(BaseModel):
    query: str
    fund_id: Optional[str] = None
    company_id: Optional[str] = None
    row_id: Optional[str] = None
    column_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.post("/evaluate")
async def evaluate_scenario(request: EvaluateScenarioRequest):
    """
    Evaluate a "what if" query and return the impact value for cell-based formulas.
    Used by =WHATIF("query", params) formulas in cells.
    
    Examples:
    - =WHATIF("growth 30%", {growth: 0.30})
    - =WHATIF("revenue increases by 50%")
    - =WHATIF("burn rate decreases to 1M/month")
    
    Returns:
    {
        "value": <calculated_impact_value>,
        "displayValue": "<formatted_value>",
        "metadata": {
            "scenario": {...},
            "impact_factors": [...],
            "confidence": 0.85
        }
    }
    """
    try:
        # Parse the query
        composed = await composer.parse_what_if_query(
            query=request.query,
            fund_id=request.fund_id
        )
        
        # If context provided, use it to calculate impact
        impact_value = None
        if request.context:
            # Extract relevant values from context
            # For now, return a simple numeric impact based on scenario type
            if composed.events:
                # Calculate impact based on first event
                event = composed.events[0]
                if event.event_type == "growth_change":
                    # Extract growth change from parameters
                    growth_change = event.parameters.get("growth_rate", 0)
                    # Simple impact calculation (would be more sophisticated in production)
                    impact_value = growth_change * 100  # Convert to percentage
                elif event.event_type == "funding":
                    impact_value = event.parameters.get("amount", 0)
                else:
                    # Default impact
                    impact_value = 0.0
        else:
            # No context - return scenario probability as impact
            impact_value = composed.probability * 100
        
        # Format display value
        display_value = f"{impact_value:,.2f}" if isinstance(impact_value, (int, float)) else str(impact_value)
        
        return {
            "success": True,
            "value": impact_value,
            "displayValue": display_value,
            "metadata": {
                "scenario": {
                    "name": composed.scenario_name,
                    "description": composed.description,
                    "events": [
                        {
                            "entity_name": e.entity_name,
                            "event_type": e.event_type,
                            "event_description": e.event_description,
                            "parameters": e.parameters
                        }
                        for e in composed.events
                    ],
                    "probability": composed.probability
                },
                "impact_factors": [f for e in composed.events for f in e.impact_factors],
                "confidence": 0.85  # Default confidence
            }
        }
    except Exception as e:
        logger.error(f"Error evaluating scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/what-if")
async def parse_what_if_query(request: WhatIfQueryRequest):
    """
    Parse a "what if" query into a composed scenario
    
    Examples:
    - "What happens if growth decelerates in YX in year 2"
    - "What happens if Tundex starts a commercial pilot with a tier 1 aerospace company"
    - "What if YX growth slows in Q2 but Tundex gets a major partnership"
    """
    try:
        composed = await composer.parse_what_if_query(
            query=request.query,
            fund_id=request.fund_id
        )
        
        return {
            "query": request.query,
            "composed_scenario": {
                "scenario_name": composed.scenario_name,
                "description": composed.description,
                "events": [
                    {
                        "entity_name": e.entity_name,
                        "event_type": e.event_type,
                        "event_description": e.event_description,
                        "timing": e.timing,
                        "parameters": e.parameters,
                        "impact_factors": e.impact_factors
                    }
                    for e in composed.events
                ],
                "probability": composed.probability
            }
        }
    except Exception as e:
        logger.error(f"Error parsing what-if query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compose")
async def compose_scenario(request: ComposeScenarioRequest):
    """
    Compose a scenario from natural language and add it to a world model
    """
    try:
        # Parse query
        composed = await composer.parse_what_if_query(
            query=request.query,
            fund_id=request.fund_id
        )
        
        # Convert to world model scenario
        result = await composer.compose_scenario_to_world_model(
            composed_scenario=composed,
            model_id=request.model_id,
            fund_id=request.fund_id
        )
        
        # Execute scenario to get results
        from app.services.scenario_analyzer import ScenarioAnalyzer
        scenario_analyzer = ScenarioAnalyzer()
        execution_result = await scenario_analyzer.execute_scenario(result["scenario"]["id"])
        
        return {
            "query": request.query,
            "scenario": result["scenario"],
            "execution": execution_result,
            "impact_summary": {
                "factors_changed": len(result["factor_overrides"]),
                "key_changes": [
                    {
                        "factor_id": fid,
                        "new_value": val
                    }
                    for fid, val in list(result["factor_overrides"].items())[:5]
                ]
            }
        }
    except Exception as e:
        logger.error(f"Error composing scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))
