"""
API endpoint for intelligent skill orchestration
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from app.services.intelligent_skill_orchestrator import intelligent_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestrate", tags=["orchestration"])


class OrchestrationRequest(BaseModel):
    """Request model for orchestration"""
    prompt: str
    context: Optional[Dict[str, Any]] = None
    stream: bool = False
    output_format: Optional[str] = "analysis"


class OrchestrationResponse(BaseModel):
    """Response model for orchestration"""
    success: bool
    prompt: str
    decomposition: Dict[str, Any]
    results: list
    analysis: str
    citations: list
    execution_time: float
    shared_data: Optional[Dict[str, Any]] = None


@router.post("/intelligent", response_model=OrchestrationResponse)
async def orchestrate_intelligent(request: OrchestrationRequest):
    """
    Intelligently orchestrate task execution using Claude
    
    This endpoint:
    1. Uses Claude to decompose the request (no patterns)
    2. Executes tasks with specific, contextual queries
    3. Analyzes results with Claude
    4. Returns comprehensive insights
    """
    try:
        logger.info(f"Orchestrating request: {request.prompt[:100]}...")
        
        # Execute orchestration
        result = await intelligent_orchestrator.orchestrate(
            prompt=request.prompt,
            context=request.context
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail="Orchestration failed")
        
        return OrchestrationResponse(**result)
        
    except Exception as e:
        logger.error(f"Orchestration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decompose")
async def decompose_only(request: OrchestrationRequest):
    """
    Only decompose the task without execution
    Useful for understanding what the system will do
    """
    try:
        decomposed = await intelligent_orchestrator.decompose_with_claude(
            prompt=request.prompt,
            context=request.context
        )
        
        return {
            "success": True,
            "task_id": decomposed.task_id,
            "prompt": decomposed.prompt,
            "tasks": [
                {
                    "id": t.id,
                    "skill": t.skill,
                    "description": t.description,
                    "inputs": t.inputs,
                    "dependencies": t.dependencies,
                    "category": t.category.value
                }
                for t in decomposed.tasks
            ],
            "execution_graph": decomposed.execution_graph,
            "confidence": decomposed.confidence,
            "meta_reasoning": decomposed.meta_reasoning
        }
        
    except Exception as e:
        logger.error(f"Decomposition error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Get status of an orchestration task"""
    # This would check execution history
    # For now, return a placeholder
    return {
        "task_id": task_id,
        "status": "completed",
        "message": "Task status tracking not yet implemented"
    }