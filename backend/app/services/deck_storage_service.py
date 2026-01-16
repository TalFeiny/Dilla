import json
import uuid
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DeckStorageService:
    """Temporary storage service for deck data during PDF export"""
    
    def __init__(self):
        # Use in-memory storage for simplicity (can be replaced with Redis)
        self._storage: Dict[str, Dict[str, Any]] = {}
    
    def store_deck(self, deck_data: Dict[str, Any], ttl_seconds: int = 300) -> str:
        """Store deck data and return a unique ID"""
        deck_id = f"deck_{uuid.uuid4().hex[:8]}"
        
        self._storage[deck_id] = {
            'data': deck_data,
            'created_at': json.dumps({'timestamp': uuid.uuid1().time_low}),  # Simple timestamp
            'ttl': ttl_seconds
        }
        
        logger.info(f"[DECK_STORAGE] Stored deck {deck_id} with {len(deck_data.get('slides', []))} slides")
        return deck_id
    
    def get_deck(self, deck_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve deck data by ID"""
        if deck_id not in self._storage:
            logger.warning(f"[DECK_STORAGE] Deck {deck_id} not found")
            return None
        
        deck_info = self._storage[deck_id]
        logger.info(f"[DECK_STORAGE] Retrieved deck {deck_id}")
        return deck_info['data']
    
    def delete_deck(self, deck_id: str) -> bool:
        """Delete deck data by ID"""
        if deck_id in self._storage:
            del self._storage[deck_id]
            logger.info(f"[DECK_STORAGE] Deleted deck {deck_id}")
            return True
        return False
    
    def cleanup_expired(self):
        """Clean up expired deck data (simple implementation)"""
        # In a production environment, you'd implement proper TTL checking
        # For now, we'll just log the current storage size
        logger.info(f"[DECK_STORAGE] Current storage size: {len(self._storage)} decks")

# Global instance
deck_storage = DeckStorageService()
