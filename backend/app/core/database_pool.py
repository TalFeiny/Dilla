"""
Database connection pooling to prevent exhaustion
Replaces creating new connections on every request
"""

import asyncio
import logging
from typing import Optional, Any
from contextlib import asynccontextmanager
import asyncpg
from supabase import create_client, Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabasePool:
    """Manages database connection pooling"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.supabase_client: Optional[Client] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize connection pool"""
        async with self._lock:
            if self.pool is not None:
                return  # Already initialized
            
            try:
                # Parse Supabase URL to get PostgreSQL connection string
                supabase_url = settings.SUPABASE_URL
                if supabase_url:
                    # Convert Supabase URL to PostgreSQL DSN
                    # Format: postgresql://user:password@host:port/database
                    db_url = supabase_url.replace('https://', 'postgresql://')
                    db_url = db_url.replace('.supabase.co', '.supabase.co:5432')
                    
                    # Create connection pool
                    self.pool = await asyncpg.create_pool(
                        dsn=db_url,
                        min_size=2,  # Minimum connections
                        max_size=20,  # Maximum connections
                        max_inactive_connection_lifetime=300,  # 5 minutes
                        command_timeout=10,
                        pool_recycle=3600  # Recycle connections after 1 hour
                    )
                    logger.info("Database connection pool initialized")
                
                # Initialize Supabase client (this is stateless, so one instance is fine)
                if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
                    self.supabase_client = create_client(
                        settings.SUPABASE_URL,
                        settings.SUPABASE_SERVICE_KEY
                    )
                    logger.info("Supabase client initialized")
                    
            except Exception as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise
    
    async def close(self):
        """Close connection pool"""
        async with self._lock:
            if self.pool:
                await self.pool.close()
                self.pool = None
                logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args, timeout: float = 10.0) -> str:
        """Execute a query using a pooled connection"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)
    
    async def fetch(self, query: str, *args, timeout: float = 10.0) -> list:
        """Fetch results using a pooled connection"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)
    
    async def fetchrow(self, query: str, *args, timeout: float = 10.0) -> Optional[asyncpg.Record]:
        """Fetch a single row using a pooled connection"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)
    
    async def fetchval(self, query: str, *args, timeout: float = 10.0) -> Any:
        """Fetch a single value using a pooled connection"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, timeout=timeout)
    
    def get_supabase_client(self) -> Optional[Client]:
        """Get the Supabase client instance"""
        if self.supabase_client is None and settings.SUPABASE_URL:
            self.supabase_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY
            )
        return self.supabase_client
    
    async def health_check(self) -> bool:
        """Check if database is accessible"""
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global instance (but connections are pooled, not singleton data)
db_pool = DatabasePool()


# Circuit breaker for database failures
class CircuitBreaker:
    """Circuit breaker pattern for database failures"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        async with self._lock:
            # Check if circuit is open
            if self.is_open:
                if self.last_failure_time:
                    time_since_failure = asyncio.get_event_loop().time() - self.last_failure_time
                    if time_since_failure > self.recovery_timeout:
                        # Try to close circuit
                        self.is_open = False
                        self.failure_count = 0
                        logger.info("Circuit breaker closed, retrying...")
                    else:
                        raise Exception(f"Circuit breaker is open, retry in {self.recovery_timeout - time_since_failure:.0f}s")
                else:
                    raise Exception("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            # Reset on success
            async with self._lock:
                self.failure_count = 0
            return result
        except Exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = asyncio.get_event_loop().time()
                
                if self.failure_count >= self.failure_threshold:
                    self.is_open = True
                    logger.error(f"Circuit breaker opened after {self.failure_count} failures")
                
            raise


# Global circuit breaker for database
db_circuit_breaker = CircuitBreaker()