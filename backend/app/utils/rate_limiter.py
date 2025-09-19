"""
Rate Limiter with Exponential Backoff for Claude API
Prevents hitting rate limits and handles retries gracefully
"""

import asyncio
import time
import logging
from typing import Any, Callable, Optional, TypeVar, Union
from functools import wraps
import random

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RateLimiter:
    """
    Rate limiter with exponential backoff for API calls
    """
    
    def __init__(
        self, 
        max_requests_per_minute: int = 50,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        
        # Track request timestamps
        self.request_times = []
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        """Wait if we're approaching rate limit"""
        async with self.lock:
            now = time.time()
            
            # Clean up old timestamps (older than 1 minute)
            self.request_times = [t for t in self.request_times if now - t < 60]
            
            # Check if we need to wait
            if len(self.request_times) >= self.max_requests_per_minute:
                # Calculate wait time
                oldest_request = self.request_times[0]
                wait_time = 60 - (now - oldest_request) + 0.1  # Add small buffer
                
                if wait_time > 0:
                    logger.info(f"Rate limit approaching, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = time.time()
                    self.request_times = [t for t in self.request_times if now - t < 60]
            
            # Record this request
            self.request_times.append(now)
    
    async def execute_with_backoff(
        self, 
        func: Callable[..., T], 
        *args, 
        **kwargs
    ) -> T:
        """
        Execute function with exponential backoff retry logic
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                # Wait if needed for rate limiting
                await self.wait_if_needed()
                
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                return result
                
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                # Check if it's a rate limit error
                if any(err in error_str for err in ['rate_limit', 'rate limit', '429', 'too many requests']):
                    # Calculate backoff delay with jitter
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    # Add jitter to prevent thundering herd
                    delay += random.uniform(0, delay * 0.1)
                    
                    logger.warning(
                        f"Rate limit hit on attempt {attempt + 1}/{self.max_retries}. "
                        f"Waiting {delay:.2f} seconds before retry..."
                    )
                    
                    await asyncio.sleep(delay)
                    continue
                    
                # Check if it's a temporary error worth retrying
                elif any(err in error_str for err in ['timeout', 'connection', 'temporary']):
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (attempt + 1)
                        logger.warning(
                            f"Temporary error on attempt {attempt + 1}/{self.max_retries}: {e}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                        await asyncio.sleep(delay)
                        continue
                
                # Non-retryable error, raise immediately
                raise e
        
        # All retries exhausted
        logger.error(f"All {self.max_retries} retries exhausted. Last error: {last_exception}")
        raise last_exception


# Global rate limiter instance for Claude API
claude_rate_limiter = RateLimiter(
    max_requests_per_minute=50,  # Claude's default tier limit
    max_retries=3,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0
)


def with_rate_limit(func: Callable) -> Callable:
    """
    Decorator to add rate limiting to any async function
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await claude_rate_limiter.execute_with_backoff(func, *args, **kwargs)
    return wrapper


class ClaudeAPIWrapper:
    """
    Wrapper for Claude API client with built-in rate limiting
    """
    
    def __init__(self, client):
        self.client = client
        self.rate_limiter = claude_rate_limiter
    
    async def create_message(self, **kwargs) -> Any:
        """
        Create a message with rate limiting and retry logic
        """
        async def _create():
            # Check if it's an async client (has __aenter__ method)
            if hasattr(self.client, '__aenter__'):
                # For async client
                return await self.client.messages.create(**kwargs)
            else:
                # For sync client (run in executor to not block)
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, 
                    lambda: self.client.messages.create(**kwargs)
                )
        
        return await self.rate_limiter.execute_with_backoff(_create)
    
    # Add messages property for compatibility
    @property
    def messages(self):
        """Provide messages property for compatibility"""
        return self
    
    async def create(self, **kwargs) -> Any:
        """Alias for create_message to support messages.create syntax"""
        return await self.create_message(**kwargs)
    
    async def create_completion(self, **kwargs) -> Any:
        """
        Create a completion with rate limiting and retry logic
        """
        async def _create():
            if hasattr(self.client.completions, 'create'):
                return await self.client.completions.create(**kwargs)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: self.client.completions.create(**kwargs)
                )
        
        return await self.rate_limiter.execute_with_backoff(_create)


def create_rate_limited_claude_client(api_key: str):
    """
    Create a Claude client with rate limiting wrapper
    """
    import anthropic
    
    # Create the base client
    base_client = anthropic.Anthropic(api_key=api_key)
    
    # Wrap it with rate limiting
    return ClaudeAPIWrapper(base_client)


# Utility functions for common patterns
async def batch_claude_requests(
    requests: list,
    client: ClaudeAPIWrapper,
    max_concurrent: int = 5
) -> list:
    """
    Execute multiple Claude requests with controlled concurrency
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_request(request):
        async with semaphore:
            return await client.create_message(**request)
    
    tasks = [process_request(req) for req in requests]
    return await asyncio.gather(*tasks, return_exceptions=True)


# Usage tracking for monitoring
class UsageTracker:
    """Track API usage for cost monitoring"""
    
    def __init__(self):
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.start_time = time.time()
    
    def track_request(self, response):
        """Track a single request"""
        self.total_requests += 1
        
        if hasattr(response, 'usage'):
            tokens = response.usage.total_tokens
            self.total_tokens += tokens
            
            # Estimate cost (adjust based on your tier)
            # Opus: $15/1M input, $75/1M output
            # Rough estimate: $45/1M average
            self.total_cost += (tokens / 1_000_000) * 45
    
    def get_stats(self) -> dict:
        """Get usage statistics"""
        elapsed = time.time() - self.start_time
        
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "estimated_cost": f"${self.total_cost:.2f}",
            "requests_per_minute": self.total_requests / (elapsed / 60) if elapsed > 0 else 0,
            "runtime_seconds": elapsed
        }


# Global usage tracker
usage_tracker = UsageTracker()