"""
Unified Brain API Endpoints - Single entry point for all agent operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime

from ..services.unified_orchestrator import UnifiedOrchestratorService

# Initialize the orchestrator service
orchestrator_service = UnifiedOrchestratorService()

router = APIRouter(prefix="/agent", tags=["agent"])

class UnifiedRequest(BaseModel):
    prompt: str
    companies: Optional[List[str]] = []
    format: Optional[str] = "analysis"  # analysis, deck, spreadsheet, cim, matrix
    context: Optional[Dict] = {}
    stream: Optional[bool] = False
    timeout: Optional[int] = 60000

class UnifiedResponse(BaseModel):
    success: bool
    task_id: str
    data: Optional[Dict] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    skills_used: Optional[List[str]] = None

@router.post("/unified-brain", response_model=UnifiedResponse)
async def unified_brain(request: UnifiedRequest, background_tasks: BackgroundTasks):
    """
    Main endpoint for all agent operations
    Replaces all individual agent endpoints
    """
    task_id = str(uuid.uuid4())
    
    try:
        # Convert request to dict
        request_dict = request.dict()
        
        # Execute task
        result = await orchestrator_service.execute_task(task_id, request_dict)
        
        return UnifiedResponse(**result)
        
    except Exception as e:
        return UnifiedResponse(
            success=False,
            task_id=task_id,
            error=str(e)
        )

@router.get("/task/{task_id}/status")
async def get_task_status(task_id: str):
    """Get status of a running task"""
    if task_id in orchestrator_service.active_tasks:
        task = orchestrator_service.active_tasks[task_id]
        return {
            "status": task["status"],
            "started_at": task["started_at"],
            "progress": task.get("progress", 0)
        }
    else:
        return {"status": "not_found"}

@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    if task_id in orchestrator_service.active_tasks:
        orchestrator_service.active_tasks[task_id]["status"] = "cancelled"
        return {"success": True, "message": "Task cancelled"}
    else:
        raise HTTPException(status_code=404, detail="Task not found")

@router.get("/skills")
async def list_skills():
    """List all available skills"""
    skills = []
    for name, skill in orchestrator_service.skill_registry.items():
        skills.append({
            "name": name,
            "category": skill["category"].value,
            "description": skill["description"],
            "timeout": skill["timeout"],
            "requires_computer_use": skill.get("requires_computer_use", False)
        })
    return {"skills": skills}

@router.post("/skills/{skill_name}/execute")
async def execute_skill(skill_name: str, inputs: Dict):
    """Execute a specific skill directly"""
    if skill_name not in orchestrator_service.skill_registry:
        raise HTTPException(status_code=404, detail=f"Skill {skill_name} not found")
    
    skill = orchestrator_service.skill_registry[skill_name]
    try:
        result = await skill["handler"](inputs)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}