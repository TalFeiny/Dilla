"""
GRPO API Endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from app.services.grpo_training_system import get_grpo_system
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/grpo", tags=["grpo"])


class TrainRequest(BaseModel):
    num_epochs: int = 10
    batch_size: int = 32


class RankRequest(BaseModel):
    prompt: str
    responses: List[str]


class ImproveRequest(BaseModel):
    prompt: str
    response: str
    alternatives: int = 3


@router.post("/train")
async def train_grpo(request: TrainRequest):
    """
    Train GRPO on collected feedback
    """
    try:
        grpo = get_grpo_system()
        result = await grpo.train_grpo(
            num_epochs=request.num_epochs,
            batch_size=request.batch_size
        )
        return result
    except Exception as e:
        logger.error(f"GRPO training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rank")
async def rank_responses(request: RankRequest):
    """
    Rank responses using trained GRPO model
    """
    try:
        grpo = get_grpo_system()
        ranked = grpo.rank_responses(request.prompt, request.responses)
        
        return {
            "success": True,
            "rankings": [
                {"response": resp, "score": score}
                for resp, score in ranked
            ]
        }
    except Exception as e:
        logger.error(f"GRPO ranking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/improve")
async def improve_response(request: ImproveRequest):
    """
    Improve a response using GRPO
    """
    try:
        grpo = get_grpo_system()
        improved = await grpo.improve_response(
            request.prompt,
            request.response,
            request.alternatives
        )
        
        return {
            "success": True,
            "original": request.response,
            "improved": improved
        }
    except Exception as e:
        logger.error(f"GRPO improvement error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_training_stats():
    """
    Get GRPO training statistics
    """
    try:
        grpo = get_grpo_system()
        
        return {
            "success": True,
            "buffer_size": len(grpo.preference_buffer),
            "training_stats": grpo.training_stats[-10:] if grpo.training_stats else [],
            "cache_size": len(grpo.embedding_cache)
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_grpo():
    """
    Test GRPO with sample data
    """
    try:
        grpo = get_grpo_system()
        
        # Test ranking
        test_prompt = "Create a DCF model for @Ramp"
        test_responses = [
            "Simple DCF with 10% discount rate",
            "Comprehensive DCF with scenario analysis, 15% WACC, and sensitivity tables",
            "Basic revenue multiple valuation"
        ]
        
        ranked = grpo.rank_responses(test_prompt, test_responses)
        
        return {
            "success": True,
            "test_prompt": test_prompt,
            "rankings": [
                {"response": resp[:50] + "...", "score": score}
                for resp, score in ranked
            ]
        }
    except Exception as e:
        logger.error(f"GRPO test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train-tool-calling")
async def train_tool_calling():
    """
    Train Qwen2.5-Coder on tool calling examples
    """
    try:
        grpo = get_grpo_system()
        
        # Generate synthetic examples
        examples = grpo.generate_tool_calling_examples()
        
        # Train on examples
        results = await grpo.train_on_examples(examples)
        
        return {
            "success": True,
            "model": results["model"],
            "examples_processed": results["examples_processed"],
            "new_success_rate": results["new_success_rate"],
            "improvements": len(results["improvements"])
        }
    except Exception as e:
        logger.error(f"Tool calling training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tool-calling-stats")
async def get_tool_calling_stats():
    """
    Get tool calling training statistics
    """
    try:
        grpo = get_grpo_system()
        stats = grpo.get_training_stats()
        
        return {
            "success": True,
            **stats
        }
    except Exception as e:
        logger.error(f"Error getting tool calling stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))