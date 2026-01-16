from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from ..services.deck_storage_service import deck_storage

router = APIRouter(prefix="/api/deck-storage", tags=["deck-storage"])
logger = logging.getLogger(__name__)

@router.post("/store")
async def store_deck(deck_data: Dict[str, Any]):
    """Store deck data temporarily for PDF export"""
    try:
        deck_id = deck_storage.store_deck(deck_data)
        logger.info(f"[DECK_STORAGE_API] Stored deck with ID: {deck_id}")
        return {"deck_id": deck_id}
    except Exception as e:
        logger.error(f"[DECK_STORAGE_API] Error storing deck: {e}")
        raise HTTPException(status_code=500, detail="Failed to store deck data")

@router.get("/{deck_id}")
async def get_deck(deck_id: str):
    """Retrieve deck data by ID"""
    try:
        deck_data = deck_storage.get_deck(deck_id)
        if deck_data is None:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        logger.info(f"[DECK_STORAGE_API] Retrieved deck: {deck_id}")
        return deck_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DECK_STORAGE_API] Error retrieving deck {deck_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deck data")

@router.delete("/{deck_id}")
async def delete_deck(deck_id: str):
    """Delete deck data by ID"""
    try:
        success = deck_storage.delete_deck(deck_id)
        if not success:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        logger.info(f"[DECK_STORAGE_API] Deleted deck: {deck_id}")
        return {"message": "Deck deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DECK_STORAGE_API] Error deleting deck {deck_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete deck data")
