from supabase import create_client, Client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self):
        self.client: Client = None
        self._initialized = False
        self._last_attempt: float = 0
        self._retry_interval: float = 30.0  # seconds between retries
        # Don't initialize during import - do it lazily

    def initialize(self):
        """Lazy initialization of Supabase client with retry on failure."""
        import time
        now = time.time()

        # If already successfully initialized, skip
        if self._initialized and self.client is not None:
            return

        # If previously failed, only retry after the retry interval
        if self._initialized and self.client is None:
            if now - self._last_attempt < self._retry_interval:
                return
            logger.info("Retrying Supabase client initialization...")

        self._last_attempt = now

        try:
            # Use NEXT_PUBLIC_SUPABASE_URL if SUPABASE_URL is not set
            supabase_url = settings.SUPABASE_URL or settings.NEXT_PUBLIC_SUPABASE_URL
            supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_SERVICE_KEY

            # Check if we have valid Supabase URL
            if not supabase_url or supabase_url.startswith("https://xxxxx"):
                logger.warning("Supabase URL not configured - database features will be limited")
                self.client = None
                self._initialized = True
                return

            if not supabase_key:
                logger.warning("Supabase key not configured - database features will be limited")
                self.client = None
                self._initialized = True
                return

            logger.info("Initializing Supabase client...")
            self.client = create_client(
                supabase_url,
                supabase_key
            )
            logger.info("Supabase client initialized successfully")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.client = None
            self._initialized = True  # Mark attempted, but will retry after interval

    def get_client(self) -> Client:
        if not self._initialized or (self.client is None):
            self.initialize()
        return self.client
    
    def search_companies(self, query: str, limit: int = 10):
        """Search for companies in the database"""
        try:
            if not self.client:
                logger.warning("Supabase client not initialized - returning empty results")
                return []
            
            # Try to search in companies table if it exists
            # For now, return empty array as fallback
            try:
                result = self.client.table('companies').select('*').ilike('name', f'%{query}%').limit(limit).execute()
                return result.data if result else []
            except:
                # Table might not exist, return empty
                return []
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            return []


# Lazy initialization - don't initialize during module import
def get_supabase_service():
    """Get the singleton Supabase service instance"""
    global _supabase_service_instance
    if '_supabase_service_instance' not in globals():
        _supabase_service_instance = SupabaseService()
    return _supabase_service_instance

# For backwards compatibility, create instance but don't initialize
supabase_service = SupabaseService()