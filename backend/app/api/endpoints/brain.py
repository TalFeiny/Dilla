"""
API endpoints for Central Agent Brain with RL
Real-time monitoring and control of the learning system
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import json
import asyncio
import logging
from datetime import datetime

from app.services.central_agent_brain import (
    CentralAgentBrain, 
    get_brain, 
    TaskContext, 
    TaskOutcome,
    AgentType
)

logger = logging.getLogger(__name__)

router = APIRouter()


class TaskRequest(BaseModel):
    """Request model for task execution"""
    query: str
    task_type: str = "analysis"
    complexity: float = 0.5
    priority: int = 5
    metadata: Optional[Dict[str, Any]] = None


class BrainConfigRequest(BaseModel):
    """Request model for brain configuration"""
    learning_enabled: Optional[bool] = None
    exploration_rate: Optional[float] = None
    reward_weights: Optional[Dict[str, float]] = None


class DemoRequest(BaseModel):
    """Request model for demo execution"""
    num_tasks: int = 50
    task_types: Optional[List[str]] = None
    stream: bool = True


@router.get("/status")
async def get_brain_status():
    """Get current status of the central brain"""
    try:
        brain = get_brain()
        return brain.get_brain_state()
    except Exception as e:
        logger.error(f"Error getting brain status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/rankings")
async def get_agent_rankings():
    """Get performance rankings of all agents"""
    try:
        brain = get_brain()
        return {
            "rankings": brain.get_agent_rankings(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting agent rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_task(request: TaskRequest):
    """Execute a task using the central brain"""
    try:
        brain = get_brain()
        
        # Create task context
        task_context = TaskContext(
            task_id=f"task_{datetime.now().timestamp()}",
            query=request.query,
            task_type=request.task_type,
            complexity=request.complexity,
            priority=request.priority,
            metadata=request.metadata or {}
        )
        
        # Execute task
        result = await brain.execute_task(task_context)
        
        return {
            "task_id": result.task_id,
            "agent_id": result.agent_id,
            "outcome": result.outcome.value,
            "confidence": result.confidence,
            "execution_time": result.execution_time,
            "result_data": result.result_data,
            "brain_stats": {
                "total_tasks": brain.total_tasks,
                "success_rate": brain.successful_tasks / max(1, brain.total_tasks),
                "exploration_rate": brain.exploration_rate
            }
        }
    except Exception as e:
        logger.error(f"Error executing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configure")
async def configure_brain(request: BrainConfigRequest):
    """Configure brain parameters"""
    try:
        brain = get_brain()
        
        if request.learning_enabled is not None:
            brain.learning_enabled = request.learning_enabled
        
        if request.exploration_rate is not None:
            brain.exploration_rate = max(0.0, min(1.0, request.exploration_rate))
        
        if request.reward_weights:
            brain.reward_weights.update(request.reward_weights)
        
        return {
            "status": "configured",
            "learning_enabled": brain.learning_enabled,
            "exploration_rate": brain.exploration_rate,
            "reward_weights": brain.reward_weights
        }
    except Exception as e:
        logger.error(f"Error configuring brain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/demo")
async def run_demo(request: DemoRequest):
    """Run a learning demonstration"""
    try:
        brain = get_brain()
        
        if request.stream:
            # Stream results as they happen
            async def generate():
                async for update in _run_demo_stream(brain, request.num_tasks):
                    yield f"data: {json.dumps(update)}\n\n"
            
            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            # Run complete demo
            results = await brain.demonstrate_learning(request.num_tasks)
            return results
    
    except Exception as e:
        logger.error(f"Error running demo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_demo_stream(brain: CentralAgentBrain, num_tasks: int):
    """Stream demo updates"""
    for i in range(num_tasks):
        # Generate task
        import random
        task_types = ["calculation", "research", "analysis", "generation"]
        task_context = TaskContext(
            task_id=f"demo_{i}",
            query=f"Demo task {i}",
            task_type=random.choice(task_types),
            complexity=random.uniform(0.1, 1.0),
            priority=random.randint(1, 10)
        )
        
        # Execute
        result = await brain.execute_task(task_context)
        
        # Yield update
        yield {
            "task_number": i + 1,
            "total_tasks": num_tasks,
            "task_id": result.task_id,
            "agent_used": result.agent_id,
            "outcome": result.outcome.value,
            "confidence": result.confidence,
            "execution_time": result.execution_time,
            "current_stats": {
                "success_rate": brain.successful_tasks / (i + 1),
                "avg_reward": brain.total_reward / (i + 1),
                "exploration_rate": brain.exploration_rate
            }
        }
        
        # Small delay for visualization
        await asyncio.sleep(0.1)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time brain monitoring"""
    await websocket.accept()
    brain = get_brain()
    
    try:
        while True:
            # Send periodic updates
            state = brain.get_brain_state()
            await websocket.send_json({
                "type": "state_update",
                "data": state,
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for next update
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


@router.get("/metrics")
async def get_metrics():
    """Get detailed metrics for visualization"""
    try:
        brain = get_brain()
        
        # Collect metrics
        metrics = {
            "performance": {
                "total_tasks": brain.total_tasks,
                "successful_tasks": brain.successful_tasks,
                "success_rate": brain.successful_tasks / max(1, brain.total_tasks),
                "total_reward": brain.total_reward,
                "avg_reward": brain.total_reward / max(1, brain.total_tasks)
            },
            "learning": {
                "exploration_rate": brain.exploration_rate,
                "learning_enabled": brain.learning_enabled,
                "improvements": brain.learning_improvements[-20:] if brain.learning_improvements else []
            },
            "agents": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Add per-agent metrics
        for agent_id, agent in brain.agents.items():
            metrics["agents"][agent_id] = {
                "type": agent.agent_type.value,
                "success_rate": agent.success_rate,
                "avg_response_time": agent.avg_response_time,
                "total_tasks": agent.total_tasks,
                "is_busy": agent.is_busy,
                "current_load": agent.current_load,
                "recent_performance": list(brain.agent_performance[agent_id])[-10:]
            }
        
        return metrics
    
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def trigger_training():
    """Manually trigger a training cycle"""
    try:
        brain = get_brain()
        
        # Run training
        result = await brain.rl_system.train_agent(
            "central_brain",
            batch_size=32,
            num_steps=100
        )
        
        return {
            "status": "training_complete",
            "training_result": result,
            "current_performance": {
                "success_rate": brain.successful_tasks / max(1, brain.total_tasks),
                "avg_reward": brain.total_reward / max(1, brain.total_tasks),
                "exploration_rate": brain.exploration_rate
            }
        }
    
    except Exception as e:
        logger.error(f"Error triggering training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def brain_info():
    """Get information about the brain API"""
    return {
        "name": "Central Agent Brain API",
        "version": "1.0.0",
        "description": "Reinforcement Learning based agent coordination system",
        "endpoints": {
            "/status": "Get current brain state",
            "/agents/rankings": "Get agent performance rankings",
            "/execute": "Execute a task",
            "/configure": "Configure brain parameters",
            "/demo": "Run learning demonstration",
            "/metrics": "Get detailed metrics",
            "/train": "Trigger training cycle",
            "/ws": "WebSocket for real-time monitoring"
        },
        "features": [
            "Multi-agent coordination",
            "Real-time learning",
            "Performance optimization",
            "Dynamic agent selection",
            "Experience replay",
            "Exploration vs exploitation"
        ]
    }