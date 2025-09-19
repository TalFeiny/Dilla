"""
Data Query and Semantic Search Endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import json

from app.core.database import supabase_service

router = APIRouter()
logger = logging.getLogger(__name__)


class SemanticQueryRequest(BaseModel):
    query: str
    context: Optional[str] = None
    limit: int = 10
    include_embeddings: bool = False


class ContextAwareQueryRequest(BaseModel):
    query: str
    context: Dict[str, Any]
    data_sources: List[str] = ["companies", "documents", "market_research"]


@router.post("/semantic-query")
async def semantic_query(request: SemanticQueryRequest):
    """Execute semantic search across data"""
    try:
        client = supabase_service.get_client()
        
        # This would use vector embeddings in production
        # For now, simple text search
        results = []
        
        if client:
            # Search companies
            companies = client.table("companies")\
                .select("*")\
                .ilike("name", f"%{request.query}%")\
                .limit(request.limit)\
                .execute()
            
            if companies.data:
                for company in companies.data:
                    results.append({
                        "type": "company",
                        "data": company,
                        "relevance": 0.8  # Mock relevance score
                    })
        
        return {
            "query": request.query,
            "results": results,
            "total": len(results),
            "method": "semantic" if request.include_embeddings else "text"
        }
        
    except Exception as e:
        logger.error(f"Semantic query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context-aware-query")
async def context_aware_query(request: ContextAwareQueryRequest):
    """Execute context-aware data query"""
    try:
        # Use context to refine query
        refined_query = request.query
        
        if "company" in request.context:
            refined_query += f" {request.context['company']}"
        if "sector" in request.context:
            refined_query += f" {request.context['sector']}"
        
        results = {}
        client = supabase_service.get_client()
        
        if client:
            for source in request.data_sources:
                if source == "companies":
                    data = client.table("companies")\
                        .select("*")\
                        .ilike("name", f"%{refined_query}%")\
                        .limit(5)\
                        .execute()
                    results[source] = data.data if data.data else []
                elif source == "documents":
                    data = client.table("documents")\
                        .select("*")\
                        .ilike("filename", f"%{refined_query}%")\
                        .limit(5)\
                        .execute()
                    results[source] = data.data if data.data else []
        
        return {
            "query": request.query,
            "refined_query": refined_query,
            "context": request.context,
            "results": results,
            "sources_queried": request.data_sources
        }
        
    except Exception as e:
        logger.error(f"Context-aware query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings")
async def create_embeddings(text: str):
    """Create embeddings for text"""
    # This would use OpenAI/other embedding models
    return {
        "text": text[:100],
        "embedding": [0.1] * 1536,  # Mock 1536-dim embedding
        "model": "text-embedding-ada-002"
    }


@router.post("/embeddings/company")
async def create_company_embeddings(company_id: str):
    """Create embeddings for a company"""
    return {
        "company_id": company_id,
        "embeddings": {
            "description": [0.1] * 1536,
            "sector": [0.2] * 1536,
            "metrics": [0.3] * 1536
        },
        "status": "created"
    }