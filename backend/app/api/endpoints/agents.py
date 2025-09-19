from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import logging
# from app.services.agent_service import self_learning_agent  # Temporarily disabled

router = APIRouter()
logger = logging.getLogger(__name__)


class AgentTaskRequest(BaseModel):
    task_type: str
    task_data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


class AgentFeedbackRequest(BaseModel):
    task_id: str
    feedback: float  # -1 to 1 rating
    comments: Optional[str] = None


@router.post("/run")
async def run_agent(request: AgentTaskRequest):
    """
    Run the self-learning AI agent with a specific task.
    """
    try:
        result = await self_learning_agent.process_task(
            task_type=request.task_type,
            task_data=request.task_data,
            context=request.context
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs")
async def get_agent_runs():
    """
    Get agent run history.
    """
    try:
        # Return recent task history
        history = self_learning_agent.task_history[-50:]  # Last 50 tasks
        
        return {
            "total_runs": len(self_learning_agent.task_history),
            "recent_runs": history,
            "statistics": self_learning_agent.experience_buffer.get_statistics()
        }
        
    except Exception as e:
        logger.error(f"Error getting agent runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}/status")
async def get_run_status(run_id: str):
    """
    Get status of an agent run.
    """
    # This would need to track individual runs by ID
    # For now, return general status
    return {
        "run_id": run_id,
        "status": "completed",
        "message": "Individual run tracking to be implemented"
    }


@router.post("/process", response_model=Dict[str, Any])
async def process_agent_task(request: AgentTaskRequest):
    """
    Process a task using the self-learning agent.
    """
    try:
        result = await self_learning_agent.process_task(
            task_type=request.task_type,
            task_data=request.task_data,
            context=request.context
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing agent task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=Dict[str, Any])
async def get_agent_status():
    """
    Get current status and statistics of the self-learning agent.
    """
    try:
        status = await self_learning_agent.get_agent_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learn")
async def trigger_learning(background_tasks: BackgroundTasks):
    """
    Trigger a learning cycle for the agent.
    """
    try:
        # Run learning in background
        background_tasks.add_task(self_learning_agent._learn_from_experience)
        
        return {
            "message": "Learning cycle initiated",
            "current_experiences": len(self_learning_agent.experience_buffer.buffer)
        }
        
    except Exception as e:
        logger.error(f"Error triggering learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def provide_feedback(request: AgentFeedbackRequest):
    """
    Provide feedback to the agent about a completed task.
    """
    try:
        # Add feedback as a new experience with adjusted reward
        self_learning_agent.experience_buffer.add(
            state={"task_id": request.task_id, "type": "feedback"},
            action={"type": "previous_action"},
            reward=request.feedback,
            next_state={"task_id": request.task_id, "type": "feedback_processed"}
        )
        
        return {
            "message": "Feedback recorded",
            "feedback_value": request.feedback,
            "total_experiences": len(self_learning_agent.experience_buffer.buffer)
        }
        
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_agent_state():
    """
    Save the current agent state to database.
    """
    try:
        state = await self_learning_agent.save_state()
        
        return {
            "message": "Agent state saved",
            "timestamp": state["timestamp"],
            "task_history_size": len(state["task_history"])
        }
        
    except Exception as e:
        logger.error(f"Error saving agent state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load")
async def load_agent_state(state_id: Optional[str] = None):
    """
    Load agent state from database.
    """
    try:
        success = await self_learning_agent.load_state(state_id)
        
        if success:
            return {
                "message": "Agent state loaded successfully",
                "status": await self_learning_agent.get_agent_status()
            }
        else:
            return {
                "message": "No saved state found or loading failed",
                "status": "using default initialization"
            }
        
    except Exception as e:
        logger.error(f"Error loading agent state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_agent():
    """
    Test the self-learning agent with a sample task.
    """
    try:
        # Test with a sample valuation task
        result = await self_learning_agent.process_task(
            task_type="valuation",
            task_data={
                "company": "Test Company",
                "revenue": 10000000,
                "growth_rate": 0.25
            },
            context={"test": True}
        )
        
        return {
            "message": "Agent test successful",
            "result": result,
            "agent_status": await self_learning_agent.get_agent_status()
        }
        
    except Exception as e:
        logger.error(f"Error testing agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))