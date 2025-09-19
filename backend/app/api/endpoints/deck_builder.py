"""
Deck Builder Endpoint
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class DeckGenerateRequest(BaseModel):
    companies: List[str]
    template: Optional[str] = "investment_memo"
    sections: Optional[List[str]] = None
    
class DeckGenerateResponse(BaseModel):
    slides: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    format: str = "pptx"

@router.post("/generate", response_model=DeckGenerateResponse)
async def generate_deck(request: DeckGenerateRequest):
    """Generate investment deck"""
    try:
        # Mock response with basic slide structure
        slides = []
        
        # Title slide
        slides.append({
            "type": "title",
            "title": f"Investment Analysis: {', '.join(request.companies)}",
            "subtitle": "Comprehensive Market & Financial Review"
        })
        
        # Executive summary
        slides.append({
            "type": "text",
            "title": "Executive Summary",
            "content": [
                "Market opportunity analysis",
                "Financial metrics comparison",
                "Investment thesis",
                "Risk assessment"
            ]
        })
        
        # Company comparison
        for company in request.companies:
            slides.append({
                "type": "company",
                "title": f"{company} Overview",
                "content": {
                    "description": f"{company} is a leading company in its sector",
                    "metrics": {
                        "revenue": "Growing",
                        "funding": "Series B",
                        "employees": "100-500"
                    }
                }
            })
        
        return DeckGenerateResponse(
            slides=slides,
            metadata={
                "total_slides": len(slides),
                "companies": request.companies,
                "template": request.template
            }
        )
    except Exception as e:
        logger.error(f"Deck generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))