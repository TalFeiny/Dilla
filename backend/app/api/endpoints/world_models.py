"""
World Models API Endpoints
API for building and managing world models
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from app.services.world_model_builder import WorldModelBuilder, FactorType, FactorCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/world-models", tags=["world-models"])

# Initialize service
model_builder = WorldModelBuilder()


class CreateModelRequest(BaseModel):
    name: str
    model_type: str
    fund_id: Optional[str] = None
    company_id: Optional[str] = None


class AddEntityRequest(BaseModel):
    model_id: str
    entity_type: str
    entity_name: str
    entity_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class AddFactorRequest(BaseModel):
    model_id: str
    entity_id: str
    factor_name: str
    factor_type: str
    factor_category: str
    value_type: str
    current_value: Optional[Any] = None
    source: str = "manual"
    confidence_score: float = 0.5
    dependencies: Optional[List[str]] = None
    formula: Optional[str] = None
    assumptions: Optional[Dict[str, Any]] = None


class BuildCompanyModelRequest(BaseModel):
    company_data: Dict[str, Any]
    model_name: Optional[str] = None
    fund_id: Optional[str] = None


@router.post("/create")
async def create_model(request: CreateModelRequest):
    """Create a new world model"""
    try:
        model = await model_builder.create_model(
            name=request.name,
            model_type=request.model_type,
            fund_id=request.fund_id,
            company_id=request.company_id,
            created_by=None  # TODO: Get from auth
        )
        return model
    except Exception as e:
        logger.error(f"Error creating world model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entities")
async def add_entity(request: AddEntityRequest):
    """Add an entity to a world model"""
    try:
        entity = await model_builder.add_entity(
            model_id=request.model_id,
            entity_type=request.entity_type,
            entity_name=request.entity_name,
            entity_id=request.entity_id,
            properties=request.properties
        )
        return entity
    except Exception as e:
        logger.error(f"Error adding entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/factors")
async def add_factor(request: AddFactorRequest):
    """Add a factor to a world model"""
    try:
        factor_type = FactorType(request.factor_type)
        factor_category = FactorCategory(request.factor_category)
        
        factor = await model_builder.add_factor(
            model_id=request.model_id,
            entity_id=request.entity_id,
            factor_name=request.factor_name,
            factor_type=factor_type,
            factor_category=factor_category,
            value_type=request.value_type,
            current_value=request.current_value,
            source=request.source,
            confidence_score=request.confidence_score,
            dependencies=request.dependencies,
            formula=request.formula,
            assumptions=request.assumptions
        )
        return factor
    except Exception as e:
        logger.error(f"Error adding factor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build-company-model")
async def build_company_model(request: BuildCompanyModelRequest):
    """Build a comprehensive world model for a company"""
    try:
        result = await model_builder.build_company_world_model(
            company_data=request.company_data,
            model_name=request.model_name,
            fund_id=request.fund_id,
            created_by=None  # TODO: Get from auth
        )
        return result
    except Exception as e:
        logger.error(f"Error building company world model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{model_id}")
async def get_model(model_id: str):
    """Get a world model with all entities, factors, and relationships"""
    try:
        model = await model_builder.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return model
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting world model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{model_id}/execute")
async def execute_model(model_id: str):
    """Execute a world model - calculate all factors"""
    try:
        results = await model_builder.execute_model(model_id)
        return results
    except Exception as e:
        logger.error(f"Error executing world model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
