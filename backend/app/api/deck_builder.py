"""
Deck Builder API endpoints
Handles deck creation, editing, and export operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Response
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
import logging

from app.services.deck_builder_agent import (
    deck_builder_agent,
    DeckType,
    SlideTemplate,
    DeckTheme,
    Deck,
    SlideContent
)
from app.services.deck_content_agents import content_agent_orchestrator
from app.services.deck_export_service import deck_export_service
from app.services.slide_templates import slide_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deck-builder", tags=["deck-builder"])


# Request/Response Models
class CreateDeckRequest(BaseModel):
    """Request to create a new deck"""
    title: str = Field(..., description="Deck title")
    type: str = Field(..., description="Type of deck (pitch, cim, sales, board)")
    company_info: Dict[str, Any] = Field(..., description="Company information")
    requirements: Optional[str] = Field(None, description="Specific requirements")
    data_sources: Optional[Dict] = Field(None, description="External data sources")
    theme: Optional[Dict] = Field(None, description="Visual theme preferences")
    auto_generate: bool = Field(True, description="Auto-generate all content")


class UpdateSlideRequest(BaseModel):
    """Request to update a slide"""
    deck_id: str
    slide_id: str
    content: Optional[Dict] = None
    template: Optional[str] = None
    regenerate: bool = False
    instructions: Optional[str] = None


class ExportDeckRequest(BaseModel):
    """Request to export a deck"""
    deck_id: str
    format: str = Field("pptx", description="Export format (pptx, pdf, html)")


class SlideContentRequest(BaseModel):
    """Request to generate slide content"""
    slide_type: str
    context: Dict[str, Any]
    requirements: Optional[str] = None
    tone: str = "professional"
    length: str = "concise"


class DeckResponse(BaseModel):
    """Response with deck information"""
    id: str
    title: str
    type: str
    company_name: str
    author: str
    created_at: str
    slide_count: int
    status: str
    preview_url: Optional[str] = None


@router.post("/create", response_model=DeckResponse)
async def create_deck(
    request: CreateDeckRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new presentation deck
    
    This endpoint creates a new deck with AI-generated content.
    The deck is generated asynchronously if auto_generate is true.
    """
    try:
        # Convert string type to enum
        deck_type = DeckType(request.type.lower())
        
        # Parse theme if provided
        theme = None
        if request.theme:
            theme = DeckTheme(**request.theme)
        
        if request.auto_generate:
            # Generate deck asynchronously
            deck = await deck_builder_agent.create_deck(
                title=request.title,
                deck_type=deck_type,
                company_info=request.company_info,
                requirements=request.requirements,
                data_sources=request.data_sources,
                theme=theme
            )
            
            return DeckResponse(
                id=deck.id,
                title=deck.title,
                type=deck.type.value,
                company_name=deck.company_name,
                author=deck.author,
                created_at=deck.created_at.isoformat(),
                slide_count=len(deck.slides),
                status="completed",
                preview_url=f"/api/deck-builder/{deck.id}/preview"
            )
        else:
            # Create empty deck structure
            deck = Deck(
                id=str(uuid.uuid4()),
                title=request.title,
                type=deck_type,
                company_name=request.company_info.get("name", "Company"),
                author=request.company_info.get("author", "User"),
                created_at=datetime.now(),
                modified_at=datetime.now(),
                theme=theme or DeckTheme(),
                slides=[],
                metadata={"requirements": request.requirements},
                data_sources=request.data_sources
            )
            
            # Generate in background
            background_tasks.add_task(
                generate_deck_content,
                deck,
                request.company_info,
                request.requirements
            )
            
            return DeckResponse(
                id=deck.id,
                title=deck.title,
                type=deck.type.value,
                company_name=deck.company_name,
                author=deck.author,
                created_at=deck.created_at.isoformat(),
                slide_count=0,
                status="generating",
                preview_url=None
            )
            
    except Exception as e:
        logger.error(f"Error creating deck: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{deck_id}")
async def get_deck(deck_id: str):
    """
    Get deck details and content
    
    Returns the complete deck structure including all slides.
    """
    try:
        # In production, retrieve from database
        # For now, return mock data
        return {
            "id": deck_id,
            "title": "Sample Deck",
            "slides": [],
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Error retrieving deck: {e}")
        raise HTTPException(status_code=404, detail="Deck not found")


@router.get("/{deck_id}/slides")
async def get_slides(deck_id: str):
    """
    Get all slides for a deck
    
    Returns list of slides with content and metadata.
    """
    try:
        # In production, retrieve from database
        return {
            "deck_id": deck_id,
            "slides": [],
            "count": 0
        }
        
    except Exception as e:
        logger.error(f"Error retrieving slides: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_deck(request: CreateDeckRequest):
    """Generate a complete deck with AI"""
    try:
        # Create deck using the deck builder agent
        deck = await deck_builder_agent.create_deck(
            title=request.title,
            deck_type=DeckType(request.type),
            company_info=request.company_info,
            requirements=request.requirements,
            data_sources=request.data_sources
        )
        
        if request.auto_generate:
            # Generate all content
            deck = await content_agent_orchestrator.generate_all_content(deck)
        
        return {
            "success": True,
            "deck_id": deck.id,
            "title": deck.title,
            "slides": len(deck.slides),
            "message": "Deck generated successfully"
        }
    except Exception as e:
        logger.error(f"Deck generation error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/slides/generate")
async def generate_slide_content(request: SlideContentRequest):
    """
    Generate content for a specific slide type
    
    Uses AI agents to generate appropriate content based on slide type and context.
    """
    try:
        response = await content_agent_orchestrator.generate_content(
            slide_type=request.slide_type,
            context=request.context,
            requirements=request.requirements
        )
        
        return {
            "title": response.title,
            "content": response.content,
            "bullets": response.bullets,
            "metrics": response.metrics,
            "data": response.data,
            "notes": response.notes,
            "sources": response.sources
        }
        
    except Exception as e:
        logger.error(f"Error generating slide content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/slides/update")
async def update_slide(request: UpdateSlideRequest):
    """
    Update or regenerate a slide
    
    Allows updating slide content or regenerating with new instructions.
    """
    try:
        if request.regenerate and request.instructions:
            # Regenerate slide with new instructions
            slide = await deck_builder_agent.regenerate_slide(
                deck_id=request.deck_id,
                slide_id=request.slide_id,
                instructions=request.instructions
            )
        else:
            # Update slide content
            slide = await deck_builder_agent.update_slide(
                deck_id=request.deck_id,
                slide_id=request.slide_id,
                content=SlideContent(**request.content) if request.content else None,
                template=SlideTemplate[request.template.upper()] if request.template else None
            )
        
        return {
            "success": True,
            "slide": slide.to_dict() if slide else None
        }
        
    except Exception as e:
        logger.error(f"Error updating slide: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_deck(request: ExportDeckRequest):
    """
    Export deck to various formats
    
    Supports PowerPoint (.pptx), PDF, and HTML formats.
    """
    try:
        # Get deck (in production, from database)
        # For now, create a sample deck
        from app.services.deck_builder_agent import Deck, Slide, SlideContent
        import uuid
        
        sample_deck = Deck(
            id=request.deck_id,
            title="Sample Presentation",
            type=DeckType.PITCH,
            company_name="Sample Company",
            author="AI Agent",
            created_at=datetime.now(),
            modified_at=datetime.now(),
            theme=DeckTheme(),
            slides=[
                Slide(
                    id=str(uuid.uuid4()),
                    order=1,
                    template=SlideTemplate.TITLE,
                    content=SlideContent(
                        title="Welcome to Your Presentation",
                        content="AI-Generated Deck",
                        notes="Start with energy and confidence"
                    ),
                    layout=slide_templates.get_template("title")
                )
            ],
            metadata={}
        )
        
        # Export deck
        export_data = await deck_export_service.export_deck(
            sample_deck,
            format=request.format
        )
        
        # Set appropriate content type
        content_types = {
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "pdf": "application/pdf",
            "html": "text/html"
        }
        
        return Response(
            content=export_data,
            media_type=content_types.get(request.format, "application/octet-stream"),
            headers={
                "Content-Disposition": f"attachment; filename={request.deck_id}.{request.format}"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting deck: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/list")
async def list_templates():
    """
    Get list of available slide templates
    
    Returns all available slide templates with their configurations.
    """
    try:
        templates = [
            {
                "id": template.value,
                "name": template.value.replace("_", " ").title(),
                "description": f"Template for {template.value} slides",
                "preview": slide_templates.get_template(template.value)
            }
            for template in SlideTemplate
        ]
        
        return {
            "templates": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/themes/list")
async def list_themes():
    """
    Get list of available themes
    
    Returns predefined themes for deck styling.
    """
    themes = [
        {
            "id": "professional",
            "name": "Professional",
            "colors": {
                "primary": "#1E40AF",
                "secondary": "#3B82F6",
                "accent": "#10B981",
                "background": "#FFFFFF",
                "text": "#1F2937"
            },
            "font": "Inter"
        },
        {
            "id": "modern",
            "name": "Modern",
            "colors": {
                "primary": "#7C3AED",
                "secondary": "#A78BFA",
                "accent": "#F59E0B",
                "background": "#FAFAFA",
                "text": "#111827"
            },
            "font": "Montserrat"
        },
        {
            "id": "minimal",
            "name": "Minimal",
            "colors": {
                "primary": "#000000",
                "secondary": "#6B7280",
                "accent": "#EF4444",
                "background": "#FFFFFF",
                "text": "#000000"
            },
            "font": "Helvetica"
        },
        {
            "id": "vibrant",
            "name": "Vibrant",
            "colors": {
                "primary": "#DC2626",
                "secondary": "#F97316",
                "accent": "#14B8A6",
                "background": "#FEF3C7",
                "text": "#7C2D12"
            },
            "font": "Poppins"
        }
    ]
    
    return {
        "themes": themes,
        "count": len(themes)
    }


@router.get("/export/formats")
async def get_export_formats():
    """
    Get available export formats
    
    Returns list of formats that can be exported to.
    """
    formats = deck_export_service.get_available_formats()
    
    format_info = {
        "pptx": {
            "name": "PowerPoint",
            "extension": ".pptx",
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "editable": True
        },
        "pdf": {
            "name": "PDF",
            "extension": ".pdf",
            "mime_type": "application/pdf",
            "editable": False
        },
        "html": {
            "name": "HTML",
            "extension": ".html",
            "mime_type": "text/html",
            "editable": True
        }
    }
    
    return {
        "formats": [format_info.get(fmt, {"name": fmt}) for fmt in formats],
        "available": formats
    }


@router.post("/analyze")
async def analyze_content_for_deck(
    content: str = Query(..., description="Content to analyze"),
    deck_type: str = Query("pitch", description="Type of deck to create")
):
    """
    Analyze content and suggest deck structure
    
    Takes raw content and suggests an optimal deck structure.
    """
    try:
        analysis_prompt = f"""
        Analyze this content for creating a {deck_type} deck:
        {content}
        
        Suggest:
        1. Optimal slide structure
        2. Key points to highlight
        3. Data to visualize
        4. Missing information needed
        
        Return as structured JSON.
        """
        
        from app.services.mcp_orchestrator import SingleAgentOrchestrator as MCPOrchestrator
        mcp = MCPOrchestrator()
        
        analysis = await mcp.process_request(analysis_prompt)
        
        return {
            "deck_type": deck_type,
            "suggested_structure": analysis.get("structure", []),
            "key_points": analysis.get("key_points", []),
            "visualizations": analysis.get("visualizations", []),
            "missing_info": analysis.get("missing_info", [])
        }
        
    except Exception as e:
        logger.error(f"Error analyzing content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task functions
async def generate_deck_content(deck: Deck, company_info: Dict, requirements: Optional[str]):
    """Background task to generate deck content"""
    try:
        # Generate content for each slide based on deck structure
        slide_structure = deck_builder_agent._get_slide_structure(deck.type)
        
        for slide_config in slide_structure:
            content = await content_agent_orchestrator.generate_content(
                slide_type=slide_config["type"],
                context={"company_info": company_info},
                requirements=requirements
            )
            
            # Create slide with generated content
            # This would be saved to database in production
            
        logger.info(f"Successfully generated content for deck {deck.id}")
        
    except Exception as e:
        logger.error(f"Error generating deck content: {e}")


# Import uuid for ID generation
import uuid