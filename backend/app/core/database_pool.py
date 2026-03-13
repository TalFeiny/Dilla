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
        self._initialized = False

    async def initialize(self):
        """Initialize connection pool and Supabase client (independently)."""
        async with self._lock:
            if self._initialized:
                return
            self._initialized = True

            # --- Supabase REST client (independent of asyncpg) ---
            sb_key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
            supabase_url = settings.SUPABASE_URL or settings.NEXT_PUBLIC_SUPABASE_URL
            if not sb_key:
                sb_key = settings.NEXT_PUBLIC_SUPABASE_ANON_KEY
            if supabase_url and sb_key:
                try:
                    self.supabase_client = create_client(supabase_url, sb_key)
                    logger.info("Supabase client initialized (url=%s, key=%s…)", supabase_url[:40], sb_key[:8])
                except Exception as e:
                    logger.error(f"Failed to initialize Supabase client: {e}")
                    self.supabase_client = None
            else:
                logger.warning(
                    "Supabase client NOT initialized — missing env vars "
                    "(SUPABASE_URL=%s, key=%s)",
                    bool(supabase_url), bool(sb_key),
                )

            # --- asyncpg connection pool (optional, for raw SQL) ---
            db_dsn = getattr(settings, "DATABASE_URL", None)
            if db_dsn:
                try:
                    self.pool = await asyncpg.create_pool(
                        dsn=db_dsn,
                        min_size=2,
                        max_size=20,
                        max_inactive_connection_lifetime=300,
                        command_timeout=10,
                    )
                    logger.info("Database connection pool initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize database pool: {e}")
            else:
                logger.info("No DATABASE_URL set — asyncpg pool skipped (using Supabase REST only)")
    
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
        """Get the Supabase client instance, lazy-creating if needed."""
        if self.supabase_client is not None:
            return self.supabase_client

        supabase_url = settings.SUPABASE_URL or settings.NEXT_PUBLIC_SUPABASE_URL
        sb_key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
        if not sb_key:
            sb_key = settings.NEXT_PUBLIC_SUPABASE_ANON_KEY

        if not supabase_url or not sb_key:
            logger.error(
                "Cannot create Supabase client — SUPABASE_URL=%s, key=%s",
                bool(supabase_url), bool(sb_key),
            )
            return None

        try:
            self.supabase_client = create_client(supabase_url, sb_key)
            logger.info("Supabase client created (lazy, url=%s)", supabase_url[:40])
            return self.supabase_client
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {e}")
            return None
    
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