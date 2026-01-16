"""
Deck Export API Endpoints
Export decks to PowerPoint and PDF formats
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from typing import Dict, Any
from pydantic import BaseModel
import logging

from app.services.deck_export_service import DeckExportService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])


class DeckExportRequest(BaseModel):
    """Request model for deck export"""
    deck_data: Dict[str, Any]
    format: str = "pptx"  # pptx or pdf


@router.post("/export/deck")
async def export_deck(request: DeckExportRequest):
    """Export deck to PowerPoint or PDF"""
    try:
        # Create fresh instance to avoid cached data
        deck_export_service = DeckExportService()
        
        # Log deck structure for debugging
        slides = request.deck_data.get("slides", [])
        chart_slides = [s for s in slides if s.get("content", {}).get("chart_data") or s.get("type") == "chart"]
        logger.info(f"Export request - total slides: {len(slides)}, chart slides: {len(chart_slides)}")
        if chart_slides:
            logger.info(f"First chart slide structure: {chart_slides[0]}")
        
        if request.format.lower() == "pptx":
            # Export to PowerPoint
            file_bytes = deck_export_service.export_to_pptx(request.deck_data)
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            filename = "deck.pptx"
        elif request.format.lower() == "pdf":
            # Export to PDF
            file_bytes = deck_export_service.export_to_pdf(request.deck_data)
            media_type = "application/pdf"
            filename = "deck.pdf"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")
        
        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting deck: {e}")
        raise HTTPException(status_code=500, detail=str(e))