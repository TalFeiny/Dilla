"""
Agent Orchestrator API Endpoint
Main routing endpoint for all agent capabilities
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import json
import asyncio

# from app.services.orchestrator_service import orchestrator, AgentMode, AGENT_CAPABILITIES
from app.services.mcp_orchestrator import SingleAgentOrchestrator as MCPOrchestrator
orchestrator = MCPOrchestrator()
AgentMode = None
AGENT_CAPABILITIES = {}

router = APIRouter()
logger = logging.getLogger(__name__)


class OrchestratorRequest(BaseModel):
    message: str
    mode: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    auto_select: bool = True
    stream: bool = False


class StreamRequest(BaseModel):
    message: str
    parameters: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


@router.post("/route")
async def route_request(request: OrchestratorRequest):
    """
    Main orchestrator endpoint - routes requests to appropriate agents
    """
    try:
        result = await orchestrator.route_request(
            message=request.message,
            mode=request.mode,
            parameters=request.parameters,
            context=request.context,
            auto_select=request.auto_select
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_request(request: StreamRequest):
    """
    Streaming endpoint for real-time agent responses
    """
    async def generate():
        try:
            # Initial response
            yield json.dumps({
                "type": "start",
                "message": "Processing request...",
                "timestamp": datetime.now().isoformat()
            }) + "\n"
            
            # Route the request
            routing_result = await orchestrator.router.analyze_prompt(
                request.message,
                request.context
            )
            
            yield json.dumps({
                "type": "routing",
                "mode": routing_result['mode'].value,
                "confidence": routing_result['confidence'],
                "reasoning": routing_result['reasoning']
            }) + "\n"
            
            # Simulate streaming execution
            for i in range(5):
                await asyncio.sleep(1)
                yield json.dumps({
                    "type": "progress",
                    "progress": (i + 1) * 20,
                    "message": f"Processing step {i + 1}/5..."
                }) + "\n"
            
            # Final result
            result = await orchestrator.route_request(
                message=request.message,
                parameters=request.parameters,
                context=request.context
            )
            
            yield json.dumps({
                "type": "complete",
                "result": result
            }) + "\n"
            
        except Exception as e:
            yield json.dumps({
                "type": "error",
                "error": str(e)
            }) + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@router.get("/modes")
async def get_available_modes():
    """
    Get list of available agent modes and their capabilities
    """
    return {
        "available_modes": [
            {
                "mode": mode.value,
                **details
            }
            for mode, details in AGENT_CAPABILITIES.items()
        ],
        "default_mode": AgentMode.QUICK_CHAT.value,
        "auto_select_enabled": True
    }


@router.get("/status")
async def get_orchestrator_status():
    """
    Get orchestrator status and execution history
    """
    return await orchestrator.get_status()


@router.post("/execute/{mode}")
async def execute_specific_mode(
    mode: str,
    parameters: Dict[str, Any] = {},
    background_tasks: BackgroundTasks = None
):
    """
    Execute a specific agent mode directly
    """
    try:
        # Validate mode
        if mode not in [m.value for m in AgentMode]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {mode}"
            )
        
        # Execute
        result = await orchestrator.route_request(
            message=parameters.get('message', ''),
            mode=mode,
            parameters=parameters,
            auto_select=False
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Direct execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agent-specific endpoints

@router.post("/pwerm")
async def execute_pwerm(request: Dict[str, Any]):
    """Direct PWERM analysis endpoint"""
    return await orchestrator._execute_agent_mode(
        AgentMode.PWERM_ANALYSIS,
        request.get('message', ''),
        request,
        {}
    )


@router.post("/market-intelligence")
async def execute_market_intelligence(request: Dict[str, Any]):
    """Direct market intelligence endpoint"""
    return await orchestrator._execute_agent_mode(
        AgentMode.MARKET_RESEARCH,
        request.get('query', ''),
        request,
        {}
    )


@router.post("/company-cim")
async def generate_company_cim(request: Dict[str, Any]):
    """Generate company information memorandum"""
    return await orchestrator._execute_agent_mode(
        AgentMode.COMPANY_CIM,
        request.get('company_name', ''),
        request,
        {}
    )


@router.post("/compliance")
async def execute_compliance(request: Dict[str, Any]):
    """Execute compliance/KYC checks"""
    return await orchestrator._execute_agent_mode(
        AgentMode.COMPLIANCE_KYC,
        request.get('entity_name', ''),
        request,
        {}
    )


@router.post("/multi-agent")
async def execute_multi_agent(request: Dict[str, Any]):
    """Execute multi-agent analysis"""
    return await orchestrator._execute_agent_mode(
        AgentMode.MULTI_AGENT,
        request.get('message', ''),
        request,
        request.get('context', {})
    )


@router.post("/ipev-valuation")
async def execute_ipev_valuation(request: Dict[str, Any]):
    """Execute IPEV-compliant valuation"""
    return await orchestrator._execute_agent_mode(
        AgentMode.IPEV_VALUATION,
        '',
        request,
        {}
    )


@router.post("/world-model")
async def execute_world_model(request: Dict[str, Any]):
    """Execute world model scenario analysis"""
    return await orchestrator._execute_agent_mode(
        AgentMode.WORLD_MODEL,
        request.get('message', ''),
        request,
        {}
    )


@router.post("/reasoning")
async def execute_reasoning(request: Dict[str, Any]):
    """Execute reasoning agent"""
    return await orchestrator._execute_agent_mode(
        AgentMode.REASONING,
        request.get('message', ''),
        {},
        request.get('context', {})
    )


@router.post("/socratic")
async def execute_socratic(request: Dict[str, Any]):
    """Execute Socratic dialogue"""
    return await orchestrator._execute_agent_mode(
        AgentMode.SOCRATIC,
        request.get('message', ''),
        {},
        request.get('context', {})
    )


from datetime import datetime