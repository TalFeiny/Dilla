"""
Unified Brain API Endpoints
Single endpoint that handles all agent requests using the unified orchestrator
Supports both streaming and non-streaming responses
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Optional
from pydantic import BaseModel, Field
import json
import asyncio
import logging

from app.services.unified_mcp_orchestrator import (
    get_unified_orchestrator,
    OutputFormat
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["unified-brain"])


class UnifiedRequest(BaseModel):
    """Request model for unified brain processing"""
    prompt: str = Field(..., description="User prompt to process")
    output_format: str = Field("analysis", description="Output format: spreadsheet, deck, docs, analysis, matrix")
    context: Optional[Dict] = Field(None, description="Additional context")
    stream: bool = Field(False, description="Enable streaming response")
    options: Optional[Dict] = Field(default_factory=dict, description="Additional options")


@router.post("/unified-brain")
async def process_unified_request(request: UnifiedRequest):
    """
    Main endpoint for all agent requests
    Handles data gathering, analysis, and formatting
    """
    try:
        # Validate output format
        try:
            output_format = OutputFormat(request.output_format)
        except ValueError:
            output_format = OutputFormat.ANALYSIS
        
        # Get orchestrator
        orchestrator = get_unified_orchestrator()
        # Clear cache for fresh results per request
        orchestrator.tavily_cache.clear()
        
        if request.stream:
            # Return streaming response
            async def generate():
                async with orchestrator:
                    async for result in orchestrator.process_request(
                        prompt=request.prompt,
                        output_format=output_format,
                        context=request.context,
                        stream=True
                    ):
                        # Format as Server-Sent Events
                        yield f"data: {json.dumps(result)}\n\n"
                    
                    # Send done signal
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                }
            )
        else:
            # Non-streaming response
            results = []
            async with orchestrator:
                async for result in orchestrator.process_request(
                    prompt=request.prompt,
                    output_format=output_format,
                    context=request.context,
                    stream=False
                ):
                    results.append(result)
            
            # Return the final result
            if results:
                final_result = results[-1]
                if final_result.get("type") == "complete":
                    return JSONResponse(content={
                        "success": True,
                        "result": final_result.get("result"),
                        "metadata": final_result.get("metadata")
                    })
                elif final_result.get("type") == "error":
                    raise HTTPException(status_code=500, detail=final_result.get("error"))
            
            return JSONResponse(content={
                "success": False,
                "error": "No results generated"
            })
    
    except Exception as e:
        logger.error(f"Unified brain error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unified-brain-stream")
async def process_unified_stream(request: UnifiedRequest):
    """
    Streaming-only endpoint for backwards compatibility
    Redirects to main endpoint with stream=True
    """
    request.stream = True
    return await process_unified_request(request)


@router.get("/unified-brain/health")
async def health_check():
    """Health check for unified brain"""
    return {
        "status": "healthy",
        "service": "unified-brain",
        "features": [
            "task-decomposition",
            "skill-orchestration",
            "parallel-execution",
            "streaming-support",
            "multi-format-output"
        ]
    }


@router.get("/unified-brain/skills")
async def get_available_skills():
    """Get list of available skills"""
    orchestrator = get_unified_orchestrator()
    return {
        "skills": list(orchestrator.skill_registry.keys()),
        "total": len(orchestrator.skill_registry)
    }


@router.post("/unified-brain/analyze-intent")
async def analyze_intent(request: UnifiedRequest):
    """
    Analyze prompt intent without executing
    Useful for debugging and understanding what will happen
    """
    try:
        orchestrator = get_unified_orchestrator()
        
        # Extract entities
        entities = orchestrator._extract_entities(request.prompt)
        
        # Analyze intent
        output_format = OutputFormat(request.output_format)
        async with orchestrator:
            intent = await orchestrator._analyze_intent(request.prompt, entities, output_format)
        
        # Build skill chain
        async with orchestrator:
            skill_chain = await orchestrator._build_skill_chain(
                request.prompt, output_format, intent
            )
        
        return {
            "entities": entities,
            "intent": intent,
            "skill_chain": [
                {
                    "skill": node.skill,
                    "purpose": node.purpose,
                    "parallel_group": node.parallel_group,
                    "confidence": node.confidence
                }
                for node in skill_chain
            ]
        }
    
    except Exception as e:
        logger.error(f"Intent analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))