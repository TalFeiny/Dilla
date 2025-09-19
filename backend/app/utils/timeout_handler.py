"""
Timeout handler utilities for external API calls
"""

import asyncio
import aiohttp
from typing import Optional, Any, Dict, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class TimeoutConfig:
    """Configuration for different service timeouts"""
    DEFAULT_TIMEOUT = 30  # seconds
    
    TIMEOUTS = {
        "tavily": 15,  # Fast search API
        "firecrawl": 30,  # Web scraping can be slower
        "anthropic": 60,  # Claude API for complex tasks
        "openai": 45,  # GPT API
        "supabase": 10,  # Database should be fast
        "default": 30
    }
    
    @classmethod
    def get_timeout(cls, service: str) -> int:
        """Get timeout for a specific service"""
        return cls.TIMEOUTS.get(service.lower(), cls.DEFAULT_TIMEOUT)


def with_timeout(timeout: Optional[int] = None, service: Optional[str] = None):
    """
    Decorator to add timeout to async functions
    
    Args:
        timeout: Timeout in seconds (overrides service default)
        service: Service name to get default timeout
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Determine timeout value
            timeout_seconds = timeout
            if timeout_seconds is None and service:
                timeout_seconds = TimeoutConfig.get_timeout(service)
            elif timeout_seconds is None:
                timeout_seconds = TimeoutConfig.DEFAULT_TIMEOUT
            
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
                raise TimeoutError(f"{func.__name__} timed out after {timeout_seconds} seconds")
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator


class TimeoutHTTPClient:
    """HTTP client with built-in timeout handling"""
    
    def __init__(self, default_timeout: int = 30):
        self.default_timeout = default_timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        service: Optional[str] = None
    ) -> aiohttp.ClientResponse:
        """
        GET request with timeout
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        timeout_seconds = timeout or (
            TimeoutConfig.get_timeout(service) if service else self.default_timeout
        )
        
        try:
            async with self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds)
            ) as response:
                return response
        except asyncio.TimeoutError:
            logger.error(f"GET request to {url} timed out after {timeout_seconds} seconds")
            raise
        except Exception as e:
            logger.error(f"GET request to {url} failed: {e}")
            raise
    
    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        service: Optional[str] = None
    ) -> aiohttp.ClientResponse:
        """
        POST request with timeout
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        timeout_seconds = timeout or (
            TimeoutConfig.get_timeout(service) if service else self.default_timeout
        )
        
        try:
            async with self.session.post(
                url,
                json=json,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds)
            ) as response:
                return response
        except asyncio.TimeoutError:
            logger.error(f"POST request to {url} timed out after {timeout_seconds} seconds")
            raise
        except Exception as e:
            logger.error(f"POST request to {url} failed: {e}")
            raise


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0
) -> Any:
    """
    Retry an async function with exponential backoff
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed")
    
    raise last_exception