"""
Streaming API Endpoints
Provides Server-Sent Events (SSE) and streaming responses
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, AsyncGenerator
from pydantic import BaseModel
import json
import asyncio
import logging
from datetime import datetime
import uuid

from app.services.pwerm_service import pwerm_service
# from app.services.orchestrator_service import orchestrator
from app.services.mcp_orchestrator import SingleAgentOrchestrator as MCPOrchestrator
orchestrator = MCPOrchestrator()

router = APIRouter()
logger = logging.getLogger(__name__)


class StreamingAnalysisRequest(BaseModel):
    analysis_type: str  # pwerm, market, portfolio, etc.
    parameters: Dict[str, Any]
    stream_updates: bool = True


async def generate_sse_event(event_type: str, data: Any) -> str:
    """Format data as Server-Sent Event"""
    event = f"event: {event_type}\n"
    event += f"data: {json.dumps(data)}\n\n"
    return event


@router.post("/analysis")
async def stream_analysis(request: StreamingAnalysisRequest):
    """
    Stream analysis updates in real-time using Server-Sent Events
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        task_id = str(uuid.uuid4())
        
        try:
            # Send initial event
            yield await generate_sse_event("start", {
                "task_id": task_id,
                "analysis_type": request.analysis_type,
                "timestamp": datetime.now().isoformat(),
                "message": "Analysis started"
            })
            
            # Simulate progressive analysis steps
            if request.analysis_type == "pwerm":
                # PWERM Analysis streaming
                steps = [
                    ("gathering_data", "Gathering company data...", 10),
                    ("market_research", "Conducting market research...", 25),
                    ("scenario_generation", "Generating scenarios...", 50),
                    ("valuation_calc", "Calculating valuations...", 75),
                    ("final_analysis", "Finalizing analysis...", 90),
                    ("complete", "Analysis complete", 100)
                ]
                
                for step, message, progress in steps:
                    await asyncio.sleep(1)  # Simulate processing time
                    
                    yield await generate_sse_event("progress", {
                        "task_id": task_id,
                        "step": step,
                        "message": message,
                        "progress": progress,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Send intermediate results for some steps
                    if step == "market_research":
                        yield await generate_sse_event("data", {
                            "task_id": task_id,
                            "type": "market_data",
                            "data": {
                                "market_size": 50000000000,
                                "growth_rate": 0.25,
                                "key_players": ["Company A", "Company B", "Company C"]
                            }
                        })
                    elif step == "scenario_generation":
                        yield await generate_sse_event("data", {
                            "task_id": task_id,
                            "type": "scenarios",
                            "data": {
                                "scenarios_count": 499,
                                "categories": ["IPO", "Acquisition", "Growth", "Downside"]
                            }
                        })
                
                # Final result
                final_result = {
                    "task_id": task_id,
                    "analysis_type": request.analysis_type,
                    "status": "complete",
                    "result": {
                        "expected_value": 125000000,
                        "probability_of_success": 0.65,
                        "scenarios": 499
                    }
                }
                
                yield await generate_sse_event("result", final_result)
                
            elif request.analysis_type == "market":
                # Market analysis streaming
                steps = [
                    ("search", "Searching market data...", 20),
                    ("analysis", "Analyzing trends...", 50),
                    ("synthesis", "Synthesizing insights...", 80),
                    ("complete", "Analysis complete", 100)
                ]
                
                for step, message, progress in steps:
                    await asyncio.sleep(0.8)
                    
                    yield await generate_sse_event("progress", {
                        "task_id": task_id,
                        "step": step,
                        "message": message,
                        "progress": progress
                    })
                
                yield await generate_sse_event("result", {
                    "task_id": task_id,
                    "market_size": 25000000000,
                    "growth_rate": 0.18
                })
                
            else:
                # Generic streaming for other analysis types
                for i in range(5):
                    await asyncio.sleep(0.5)
                    yield await generate_sse_event("progress", {
                        "task_id": task_id,
                        "progress": (i + 1) * 20,
                        "message": f"Processing step {i + 1}/5..."
                    })
                
                yield await generate_sse_event("result", {
                    "task_id": task_id,
                    "status": "complete"
                })
            
            # Send completion event
            yield await generate_sse_event("complete", {
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "message": "Stream ended successfully"
            })
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield await generate_sse_event("error", {
                "task_id": task_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/pwerm/{company_name}")
async def stream_pwerm_analysis(
    company_name: str,
    arr: Optional[float] = None,
    growth_rate: Optional[float] = None
):
    """
    Stream PWERM analysis for a specific company
    """
    async def stream_pwerm():
        try:
            # Initial event
            yield await generate_sse_event("start", {
                "company": company_name,
                "timestamp": datetime.now().isoformat()
            })
            
            # Market research phase
            yield await generate_sse_event("phase", {
                "phase": "market_research",
                "message": f"Researching {company_name} market data..."
            })
            await asyncio.sleep(2)
            
            # Scenario generation phase
            yield await generate_sse_event("phase", {
                "phase": "scenario_generation",
                "message": "Generating probability-weighted scenarios..."
            })
            await asyncio.sleep(2)
            
            # Valuation phase
            yield await generate_sse_event("phase", {
                "phase": "valuation",
                "message": "Calculating exit valuations..."
            })
            await asyncio.sleep(2)
            
            # Run actual PWERM analysis
            result = await pwerm_service.analyze_company(
                company_name=company_name,
                arr=arr,
                growth_rate=growth_rate
            )
            
            # Send result
            yield await generate_sse_event("result", result)
            
            # Complete
            yield await generate_sse_event("complete", {
                "message": "PWERM analysis complete",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            yield await generate_sse_event("error", {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    return StreamingResponse(
        stream_pwerm(),
        media_type="text/event-stream"
    )


@router.post("/agent")
async def stream_agent_response(request: Dict[str, Any]):
    """
    Stream agent responses with progressive updates
    """
    async def stream_agent():
        try:
            message = request.get("message", "")
            mode = request.get("mode")
            
            # Start event
            yield await generate_sse_event("start", {
                "message": message[:100],
                "mode": mode,
                "timestamp": datetime.now().isoformat()
            })
            
            # Route analysis
            yield await generate_sse_event("routing", {
                "status": "Determining best agent for your request..."
            })
            await asyncio.sleep(1)
            
            # Execute with orchestrator
            result = await orchestrator.route_request(
                message=message,
                mode=mode,
                parameters=request.get("parameters", {}),
                context=request.get("context", {})
            )
            
            # Send routing decision
            yield await generate_sse_event("routed", {
                "mode": result["mode"],
                "confidence": result["routing"]["confidence"]
            })
            
            # Stream result
            yield await generate_sse_event("result", result)
            
            # Complete
            yield await generate_sse_event("complete", {
                "execution_time": result["execution_time"],
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            yield await generate_sse_event("error", {
                "error": str(e)
            })
    
    return StreamingResponse(
        stream_agent(),
        media_type="text/event-stream"
    )


@router.get("/health")
async def streaming_health_check():
    """
    Test streaming endpoint health
    """
    async def health_stream():
        for i in range(3):
            yield await generate_sse_event("ping", {
                "count": i + 1,
                "timestamp": datetime.now().isoformat()
            })
            await asyncio.sleep(1)
        
        yield await generate_sse_event("complete", {
            "status": "healthy",
            "message": "Streaming service operational"
        })
    
    return StreamingResponse(
        health_stream(),
        media_type="text/event-stream"
    )