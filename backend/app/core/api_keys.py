"""
Centralized API key management with validation and fallbacks
"""
import os
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages API keys with validation and fallback logic"""
    
    def __init__(self):
        self._keys = {}
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from multiple sources with fallbacks"""
        # Priority order: Environment vars > .env file > Secrets manager
        
        # 1. Try environment variables first (highest priority)
        tavily_key = os.environ.get('TAVILY_API_KEY')
        
        # 2. If not in env, try from .env file
        if not tavily_key:
            from dotenv import load_dotenv
            load_dotenv(override=True)
            tavily_key = os.environ.get('TAVILY_API_KEY')
        
        # 3. Strip whitespace and validate format
        if tavily_key:
            tavily_key = tavily_key.strip()
            if not self._validate_tavily_key(tavily_key):
                logger.error(f"Invalid Tavily API key format: {tavily_key[:10]}...")
                tavily_key = None
        
        # Store validated keys
        self._keys['tavily'] = tavily_key
        
        # Log status
        if tavily_key:
            logger.info(f"Tavily API key loaded: {tavily_key[:10]}...{tavily_key[-4:]}")
        else:
            logger.warning("No valid Tavily API key found")
    
    def _validate_tavily_key(self, key: str) -> bool:
        """Validate Tavily API key format"""
        if not key:
            return False
        
        # Tavily keys should start with 'tvly-' and be ~41 chars
        if not key.startswith('tvly-'):
            return False
        
        if len(key) < 35 or len(key) > 50:
            return False
        
        # Check for common issues
        if ' ' in key or '\n' in key or '\t' in key:
            return False
        
        return True
    
    def get_tavily_key(self) -> Optional[str]:
        """Get validated Tavily API key"""
        return self._keys.get('tavily')
    
    def get_key(self, service: str) -> Optional[str]:
        """Get API key for a service"""
        return self._keys.get(service.lower())
    
    async def test_tavily_key(self) -> bool:
        """Test if Tavily API key works"""
        import aiohttp
        
        key = self.get_tavily_key()
        if not key:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.tavily.com/search',
                    json={'query': 'test', 'max_results': 1},
                    headers={'X-API-Key': key, 'Content-Type': 'application/json'}
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Tavily API test failed: {e}")
            return False


# Singleton instance
@lru_cache(maxsize=1)
def get_api_key_manager() -> APIKeyManager:
    """Get singleton API key manager"""
    return APIKeyManager()