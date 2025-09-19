"""
Advanced Agent System API Routes
Exposes the enhanced multi-agent coordination system
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import asyncio

from app.services.enhanced_prompt_router import EnhancedPromptRouter
from app.services.sub_agent_coordinator import AgentCoordinator as SubAgentCoordinator
from app.services.advanced_rl_system import AdvancedRLSystem
from app.services.advanced_cap_table import CapTableCalculator as AdvancedCapTable
from app.services.dcf_model_citations import DCFModel as DCFModelWithCitations
from app.services.enhanced_cim_scraper import EnhancedCIMScraper

router = APIRouter(prefix="/api/advanced", tags=["Advanced Agents"])
logger = logging.getLogger(__name__)

# Initialize systems
prompt_router = EnhancedPromptRouter()
coordinator = SubAgentCoordinator()
rl_system = AdvancedRLSystem()
cap_table = AdvancedCapTable()
dcf_model = None  # Initialize on demand with company name
cim_scraper = EnhancedCIMScraper()


class PromptRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class CapTableRequest(BaseModel):
    company_id: str
    scenario: str  # 'waterfall', 'dilution', 'exit', 'vesting'
    parameters: Dict[str, Any]


class DCFRequest(BaseModel):
    company_name: str
    include_citations: bool = True
    sensitivity_analysis: bool = True
    export_format: Optional[str] = "json"  # json, excel, markdown


class CIMRequest(BaseModel):
    company_name: str
    sources: Optional[List[str]] = None
    depth: str = "comprehensive"  # basic, standard, comprehensive


@router.post("/route")
async def route_prompt(request: PromptRequest):
    """Route a prompt to the appropriate agent(s) using advanced linguistic analysis"""
    try:
        # Analyze prompt
        analysis = await prompt_router.analyze_prompt(
            request.prompt,
            context=request.context
        )
        
        # Get routing decision
        routing = await prompt_router.route(analysis)
        
        # If multiple agents needed, use coordinator
        if len(routing['agents']) > 1:
            result = await coordinator.coordinate_task(
                task=request.prompt,
                agents=routing['agents'],
                strategy=routing.get('strategy', 'parallel')
            )
        else:
            # Single agent execution
            agent = routing['agents'][0]
            result = await coordinator.execute_single_agent(
                agent=agent,
                task=request.prompt,
                context=request.context
            )
        
        return {
            "analysis": analysis,
            "routing": routing,
            "result": result
        }
    except Exception as e:
        logger.error(f"Routing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/coordinate")
async def coordinate_agents(request: PromptRequest):
    """Coordinate multiple agents for complex tasks"""
    try:
        # Start coordination
        result = await coordinator.coordinate_complex_task(
            prompt=request.prompt,
            context=request.context,
            session_id=request.session_id
        )
        
        return result
    except Exception as e:
        logger.error(f"Coordination error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cap-table")
async def analyze_cap_table(request: CapTableRequest):
    """Perform advanced cap table analysis"""
    try:
        if request.scenario == "waterfall":
            result = await cap_table.calculate_exit_waterfall(
                company_id=request.company_id,
                exit_value=request.parameters.get('exit_value'),
                preferences=request.parameters.get('preferences', {})
            )
        elif request.scenario == "dilution":
            result = await cap_table.calculate_dilution(
                company_id=request.company_id,
                new_investment=request.parameters.get('new_investment'),
                valuation=request.parameters.get('valuation'),
                anti_dilution=request.parameters.get('anti_dilution')
            )
        elif request.scenario == "vesting":
            result = await cap_table.calculate_vesting_schedule(
                company_id=request.company_id,
                schedule_type=request.parameters.get('schedule_type', 'standard')
            )
        else:
            result = await cap_table.comprehensive_analysis(
                company_id=request.company_id
            )
        
        return result
    except Exception as e:
        logger.error(f"Cap table analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dcf-model")
async def create_dcf_model(request: DCFRequest):
    """Create DCF model with citations"""
    try:
        # Generate DCF model
        model = await dcf_model.create_model(
            company_name=request.company_name,
            include_citations=request.include_citations
        )
        
        # Add sensitivity analysis if requested
        if request.sensitivity_analysis:
            sensitivity = await dcf_model.sensitivity_analysis(
                model=model,
                variables=['discount_rate', 'growth_rate', 'terminal_multiple']
            )
            model['sensitivity'] = sensitivity
        
        # Export in requested format
        if request.export_format == "excel":
            file_path = await dcf_model.export_to_excel(model)
            model['excel_file'] = file_path
        elif request.export_format == "markdown":
            markdown = await dcf_model.export_to_markdown(model)
            model['markdown'] = markdown
        
        return model
    except Exception as e:
        logger.error(f"DCF model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cim-scrape")
async def scrape_for_cim(request: CIMRequest):
    """Scrape and generate comprehensive CIM"""
    try:
        # Scrape company data
        cim_data = await cim_scraper.scrape_comprehensive(
            company_name=request.company_name,
            sources=request.sources,
            depth=request.depth
        )
        
        # Generate structured CIM
        cim = await cim_scraper.generate_cim(cim_data)
        
        return cim
    except Exception as e:
        logger.error(f"CIM scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def trigger_training(background_tasks: BackgroundTasks):
    """Trigger overnight training pipeline"""
    try:
        # Add training to background tasks
        background_tasks.add_task(run_training_pipeline)
        
        return {
            "message": "Training pipeline started",
            "status": "running",
            "monitor_endpoint": "/api/advanced/training-status"
        }
    except Exception as e:
        logger.error(f"Training trigger error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-status")
async def get_training_status():
    """Get current training status"""
    try:
        status = await rl_system.get_training_status()
        return status
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-metrics")
async def get_agent_metrics():
    """Get performance metrics for all agents"""
    try:
        metrics = {
            "prompt_router": await prompt_router.get_metrics(),
            "coordinator": await coordinator.get_metrics(),
            "rl_system": await rl_system.get_metrics(),
            "agents": await coordinator.get_all_agent_metrics()
        }
        return metrics
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_training_pipeline():
    """Run the overnight training pipeline"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    from overnight_training import OvernightTrainingPipeline
    
    pipeline = OvernightTrainingPipeline()
    await pipeline.run()
    
    logger.info("Training pipeline completed")