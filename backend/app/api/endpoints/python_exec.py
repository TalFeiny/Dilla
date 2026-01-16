"""
Python Script Execution API Endpoints
Provides controlled execution of analysis scripts
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import uuid

from app.services.python_executor import python_executor

router = APIRouter()
logger = logging.getLogger(__name__)


class ScriptExecutionRequest(BaseModel):
    script_name: str
    arguments: Dict[str, Any]
    timeout: Optional[int] = None
    async_execution: bool = False


class PWERMExecutionRequest(BaseModel):
    company_name: str
    arr: Optional[float] = None
    growth_rate: Optional[float] = None
    scenarios: int = 499
    sector: Optional[str] = None


class CrewAIExecutionRequest(BaseModel):
    query: str
    company_name: Optional[str] = None
    analysis_type: str = "comprehensive"


class MarketSearchRequest(BaseModel):
    query: str
    deep_search: bool = True


class KYCExecutionRequest(BaseModel):
    entity_name: str
    check_type: str = "full"


class ScenarioAnalysisRequest(BaseModel):
    company_data: Dict[str, Any]
    num_scenarios: int = 100


@router.post("/execute")
async def execute_script(
    request: ScriptExecutionRequest,
    background_tasks: BackgroundTasks
):
    """Execute a Python analysis script"""
    try:
        if request.async_execution:
            task_id = str(uuid.uuid4())

            async def run_script() -> None:
                result = await python_executor.execute_script(
                    script_name=request.script_name,
                    arguments=request.arguments,
                    timeout=request.timeout
                )
                logger.info("Async script execution %s finished: %s", task_id, result.get("success"))

            background_tasks.add_task(run_script)

            return {
                "success": True,
                "message": "Script execution started",
                "task_id": task_id,
                "async": True
            }

        result = await python_executor.execute_script(
            script_name=request.script_name,
            arguments=request.arguments,
            timeout=request.timeout
        )
        return result

    except Exception as e:
        logger.error("Error executing script %s: %s", request.script_name, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pwerm")
async def execute_pwerm_analysis(request: PWERMExecutionRequest):
    """Execute PWERM analysis script"""
    try:
        result = await python_executor.execute_pwerm_analysis(
            company_name=request.company_name,
            arr=request.arr,
            growth_rate=request.growth_rate,
            scenarios=request.scenarios,
            sector=request.sector,
        )
        return result

    except Exception as e:
        logger.error("Error executing PWERM analysis: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crewai")
async def execute_crew_agents(request: CrewAIExecutionRequest):
    """Execute CrewAI multi-agent analysis"""
    try:
        result = await python_executor.execute_crew_agents(
            query=request.query,
            company_name=request.company_name,
            analysis_type=request.analysis_type
        )
        return result

    except Exception as e:
        logger.error("Error executing CrewAI agents: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market-search")
async def execute_market_search(request: MarketSearchRequest):
    """Execute intelligent market search"""
    try:
        result = await python_executor.execute_market_search(
            query=request.query,
            deep_search=request.deep_search
        )
        return result

    except Exception as e:
        logger.error("Error executing market search: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kyc")
async def execute_kyc_check(request: KYCExecutionRequest):
    """Execute KYC/compliance check"""
    try:
        result = await python_executor.execute_kyc_check(
            entity_name=request.entity_name,
            check_type=request.check_type
        )
        return result

    except Exception as e:
        logger.error("Error executing KYC check: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario-analysis")
async def execute_scenario_analysis(request: ScenarioAnalysisRequest):
    """Execute dynamic scenario generation"""
    try:
        result = await python_executor.execute_scenario_analysis(
            company_data=request.company_data,
            num_scenarios=request.num_scenarios,
        )
        return result

    except Exception as e:
        logger.error("Error executing scenario analysis: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scripts")
async def get_available_scripts():
    """Get list of available Python scripts"""
    try:
        scripts = python_executor.get_available_scripts()
        return {
            "available_scripts": scripts,
            "total": len(scripts)
        }

    except Exception as e:
        logger.error("Error getting available scripts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scripts/{script_name}")
async def get_script_info(script_name: str):
    """Get information about a specific script"""
    try:
        scripts = python_executor.get_available_scripts()
        script_info = next((s for s in scripts if s["name"] == script_name), None)

        if not script_info:
            raise HTTPException(status_code=404, detail="Script not found")

        param_info = {
            "pwerm_analysis": {
                "required": ["company_name"],
                "optional": ["arr", "growth_rate", "sector", "scenarios"],
                "description": "PWERM valuation analysis"
            },
            "crewai_agents": {
                "required": ["query"],
                "optional": ["company_name", "analysis_type"],
                "description": "Multi-agent analysis"
            },
            "market_search": {
                "required": ["query"],
                "optional": ["deep_search"],
                "description": "Market research and intelligence"
            },
            "kyc_processor": {
                "required": ["entity_name"],
                "optional": ["check_type"],
                "description": "KYC and compliance checking"
            },
            "scenario_analysis": {
                "required": ["company_data"],
                "optional": ["num_scenarios"],
                "description": "Scenario generation using valuation engine"
            },
        }

        script_info["parameters"] = param_info.get(script_name, {})
        return script_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting script info: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
