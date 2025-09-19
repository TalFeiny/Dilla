"""
RL Training API Routes
Endpoints for training and managing the reinforcement learning agent
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

# from app.services.agent_service import self_learning_agent  # Temporarily disabled

router = APIRouter(prefix="/api/rl", tags=["RL Training"])
logger = logging.getLogger(__name__)


class FeedbackRequest(BaseModel):
    task_id: str
    score: float  # -1 to 1
    comments: Optional[str] = None


class TrainingRequest(BaseModel):
    min_reward: float = 0.0
    iterations: int = 10


class TaskRequest(BaseModel):
    task_type: str
    task_data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


@router.post("/train")
async def train_agent(request: TrainingRequest):
    """Train the agent on historical data"""
    try:
        result = await self_learning_agent.train_on_historical_data(
            min_reward=request.min_reward
        )
        return result
    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def provide_feedback(request: FeedbackRequest):
    """Provide feedback on agent performance"""
    try:
        result = await self_learning_agent.provide_feedback(
            task_id=request.task_id,
            score=request.score,
            comments=request.comments
        )
        return result
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/task")
async def process_task(request: TaskRequest):
    """Process a task with the RL agent"""
    try:
        result = await self_learning_agent.process_task(
            task_type=request.task_type,
            task_data=request.task_data,
            context=request.context
        )
        return result
    except Exception as e:
        logger.error(f"Task processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_agent_status():
    """Get current agent status and statistics"""
    try:
        status = await self_learning_agent.get_agent_status()
        return status
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_agent_state():
    """Save current agent state to database"""
    try:
        state = await self_learning_agent.save_state()
        return {"message": "Agent state saved", "timestamp": state["timestamp"]}
    except Exception as e:
        logger.error(f"Save error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load")
async def load_agent_state(state_id: Optional[str] = None):
    """Load agent state from database"""
    try:
        success = await self_learning_agent.load_state(state_id)
        if success:
            return {"message": "Agent state loaded successfully"}
        else:
            raise HTTPException(status_code=404, detail="State not found")
    except Exception as e:
        logger.error(f"Load error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiences")
async def get_experience_statistics():
    """Get statistics about stored experiences"""
    try:
        stats = self_learning_agent.experience_buffer.get_statistics()
        return {
            "statistics": stats,
            "buffer_size": len(self_learning_agent.experience_buffer.buffer),
            "max_size": self_learning_agent.experience_buffer.max_size
        }
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))