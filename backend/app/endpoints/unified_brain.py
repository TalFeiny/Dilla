"""
Unified Brain API Endpoints - Single entry point for all agent operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime

from ..services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from ..services.model_router import set_provider_affinity

# Initialize the orchestrator service
orchestrator_service = UnifiedMCPOrchestrator()

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
async def unified_brain(request: UnifiedRequest, background_tasks: BackgroundTasks, raw_request: Request):
    """
    Main endpoint for all agent operations
    Replaces all individual agent endpoints
    """
    task_id = str(uuid.uuid4())

    # Set provider affinity for load distribution.
    # Use auth user_id if available, fall back to task_id so even
    # unauthenticated requests get distributed across providers.
    user_id = None
    if request.context and request.context.get("user_id"):
        user_id = request.context["user_id"]
    if not user_id:
        # Check Authorization header for JWT sub claim (best-effort)
        auth_header = raw_request.headers.get("authorization", "")
        if auth_header.startswith("Bearer ") and len(auth_header) > 40:
            # Use the token itself as a stable user identifier
            user_id = auth_header[7:39]  # first 32 chars of token = stable per-user
    set_provider_affinity(user_id or task_id)

    try:
        # Execute task using the UnifiedMCPOrchestrator
        result = await orchestrator_service.process_request(
            prompt=request.prompt,
            output_format=request.format or "analysis",
            context=request.context
        )
        
        # Handle case where result is None or doesn't have expected structure
        if result is None:
            return UnifiedResponse(
                success=False,
                task_id=task_id,
                error="No result returned from orchestrator"
            )
        
        return UnifiedResponse(
            success=result.get("success", False),
            task_id=task_id,
            data=result.get("result"),
            error=result.get("error")
        )
        
    except Exception as e:
        return UnifiedResponse(
            success=False,
            task_id=task_id,
            error=str(e)
        )

@router.get("/task/{task_id}/status")
async def get_task_status(task_id: str):
    """Get status of a running task"""
    # UnifiedMCPOrchestrator doesn't track active tasks, return not found
    return {"status": "not_found"}

@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    # UnifiedMCPOrchestrator doesn't track active tasks
    raise HTTPException(status_code=404, detail="Task not found")

@router.get("/skills")
async def list_skills():
    """List all available skills"""
    skills = []
    for name, skill in orchestrator_service.skills.items():
        skills.append({
            "name": name,
            "category": skill["category"].value,
            "description": skill["description"],
            "timeout": skill.get("timeout", 30000),
            "requires_computer_use": skill.get("requires_computer_use", False)
        })
    return {"skills": skills}

@router.post("/skills/{skill_name}/execute")
async def execute_skill(skill_name: str, inputs: Dict):
    """Execute a specific skill directly"""
    if skill_name not in orchestrator_service.skills:
        raise HTTPException(status_code=404, detail=f"Skill {skill_name} not found")
    
    skill = orchestrator_service.skills[skill_name]
    try:
        result = await skill["handler"](inputs)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}