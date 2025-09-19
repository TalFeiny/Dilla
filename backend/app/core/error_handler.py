"""
Unified Error Handling and Retry Logic
Centralized error management for all components
"""

import asyncio
import logging
import traceback
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random
import time

# Configure logging
logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    NETWORK = "network"
    API_LIMIT = "api_limit" 
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    LOGIC = "logic"
    EXTERNAL = "external"

@dataclass
class ErrorInfo:
    """Standardized error information"""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)

# Pre-defined error configurations
ERROR_CONFIGS = {
    # Network errors - high retry with backoff
    "ConnectionError": ErrorInfo(
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.MEDIUM,
        message="Network connection failed",
        max_retries=5,
        retry_after=1
    ),
    "TimeoutError": ErrorInfo(
        category=ErrorCategory.TIMEOUT,
        severity=ErrorSeverity.MEDIUM,
        message="Request timeout",
        max_retries=3,
        retry_after=2
    ),
    "HTTPError": ErrorInfo(
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.MEDIUM,
        message="HTTP request failed",
        max_retries=3,
        retry_after=1
    ),
    
    # API rate limiting - longer backoff
    "RateLimitError": ErrorInfo(
        category=ErrorCategory.API_LIMIT,
        severity=ErrorSeverity.HIGH,
        message="API rate limit exceeded",
        max_retries=5,
        retry_after=60  # Wait 1 minute
    ),
    "QuotaExceededError": ErrorInfo(
        category=ErrorCategory.API_LIMIT,
        severity=ErrorSeverity.HIGH,
        message="API quota exceeded",
        max_retries=2,
        retry_after=300  # Wait 5 minutes
    ),
    
    # Authentication errors - no retry
    "AuthenticationError": ErrorInfo(
        category=ErrorCategory.AUTHENTICATION,
        severity=ErrorSeverity.CRITICAL,
        message="Authentication failed",
        max_retries=0
    ),
    "PermissionError": ErrorInfo(
        category=ErrorCategory.AUTHENTICATION,
        severity=ErrorSeverity.HIGH,
        message="Insufficient permissions",
        max_retries=1
    ),
    
    # Validation errors - no retry
    "ValidationError": ErrorInfo(
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.LOW,
        message="Input validation failed",
        max_retries=0
    ),
    "ValueError": ErrorInfo(
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.LOW,
        message="Invalid value provided",
        max_retries=0
    ),
    
    # Resource errors - retry with backoff
    "MemoryError": ErrorInfo(
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.HIGH,
        message="Insufficient memory",
        max_retries=2,
        retry_after=5
    ),
    "FileNotFoundError": ErrorInfo(
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.MEDIUM,
        message="Required file not found",
        max_retries=1
    ),
    
    # External service errors
    "ExternalServiceError": ErrorInfo(
        category=ErrorCategory.EXTERNAL,
        severity=ErrorSeverity.MEDIUM,
        message="External service unavailable",
        max_retries=3,
        retry_after=5
    )
}

class RetryStrategy(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    CONSTANT = "constant"
    JITTER = "jitter"

@dataclass
class RetryConfig:
    """Configuration for retry logic"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    backoff_multiplier: float = 2.0

class DillaErrorHandler:
    """
    Unified error handler for all Dilla AI components
    """
    
    def __init__(self):
        self.error_history: List[Dict[str, Any]] = []
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
    def classify_error(self, error: Exception) -> ErrorInfo:
        """Classify error and return appropriate ErrorInfo"""
        error_type = type(error).__name__
        
        if error_type in ERROR_CONFIGS:
            error_info = ERROR_CONFIGS[error_type]
        else:
            # Default error configuration
            error_info = ErrorInfo(
                category=ErrorCategory.LOGIC,
                severity=ErrorSeverity.MEDIUM,
                message=str(error),
                max_retries=1
            )
        
        # Add specific error details
        error_info.details = {
            "error_type": error_type,
            "traceback": traceback.format_exc(),
            "args": getattr(error, 'args', [])
        }
        
        return error_info
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if an operation should be retried"""
        error_info = self.classify_error(error)
        
        # Check max retries
        if attempt >= error_info.max_retries:
            return False
        
        # Check circuit breaker
        service_key = self._get_service_key(error)
        if self._is_circuit_open(service_key):
            return False
        
        # Don't retry authentication or validation errors
        if error_info.category in [ErrorCategory.AUTHENTICATION, ErrorCategory.VALIDATION]:
            return False
        
        return True
    
    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay before retry based on strategy"""
        if config.strategy == RetryStrategy.CONSTANT:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * attempt
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))
        elif config.strategy == RetryStrategy.JITTER:
            base_delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))
            delay = base_delay + random.uniform(0, base_delay * 0.1)
        else:
            delay = config.base_delay
        
        # Apply jitter if enabled
        if config.jitter and config.strategy != RetryStrategy.JITTER:
            jitter = random.uniform(-delay * 0.1, delay * 0.1)
            delay += jitter
        
        # Ensure within bounds
        return min(max(delay, 0.1), config.max_delay)
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Log error with context"""
        error_info = self.classify_error(error)
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": error_info.category.value,
            "severity": error_info.severity.value,
            "message": error_info.message,
            "details": error_info.details,
            "context": context or {}
        }
        
        self.error_history.append(log_entry)
        
        # Log based on severity
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"CRITICAL ERROR: {error_info.message}", extra=log_entry)
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(f"ERROR: {error_info.message}", extra=log_entry)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"WARNING: {error_info.message}", extra=log_entry)
        else:
            logger.info(f"INFO: {error_info.message}", extra=log_entry)
    
    def _get_service_key(self, error: Exception) -> str:
        """Extract service key from error for circuit breaker"""
        # Try to extract from error details
        if hasattr(error, 'url'):
            return getattr(error, 'url')
        if hasattr(error, 'service'):
            return getattr(error, 'service')
        
        # Default to error type
        return type(error).__name__
    
    def _is_circuit_open(self, service_key: str) -> bool:
        """Check if circuit breaker is open for service"""
        if service_key not in self.circuit_breakers:
            self.circuit_breakers[service_key] = {
                "failures": 0,
                "last_failure": None,
                "state": "closed"  # closed, open, half-open
            }
            return False
        
        breaker = self.circuit_breakers[service_key]
        
        # If circuit is open, check if enough time has passed
        if breaker["state"] == "open":
            if breaker["last_failure"]:
                time_since_failure = datetime.utcnow() - breaker["last_failure"]
                if time_since_failure > timedelta(minutes=5):  # 5 minute timeout
                    breaker["state"] = "half-open"
                    return False
            return True
        
        return False
    
    def record_failure(self, service_key: str):
        """Record failure for circuit breaker"""
        if service_key not in self.circuit_breakers:
            self.circuit_breakers[service_key] = {
                "failures": 0,
                "last_failure": None,
                "state": "closed"
            }
        
        breaker = self.circuit_breakers[service_key]
        breaker["failures"] += 1
        breaker["last_failure"] = datetime.utcnow()
        
        # Open circuit if too many failures
        if breaker["failures"] >= 5:  # 5 failures threshold
            breaker["state"] = "open"
    
    def record_success(self, service_key: str):
        """Record success for circuit breaker"""
        if service_key in self.circuit_breakers:
            breaker = self.circuit_breakers[service_key]
            breaker["failures"] = 0
            breaker["state"] = "closed"

# Global error handler instance
error_handler = DillaErrorHandler()

def with_retry(
    func: Callable = None,
    *,
    config: Optional[RetryConfig] = None,
    context: Optional[Dict[str, Any]] = None
):
    """
    Decorator for automatic retry with error handling
    
    Usage:
    @with_retry(config=RetryConfig(max_attempts=5))
    async def risky_function():
        # Code that might fail
        pass
    """
    if func is None:
        # Called with arguments
        return lambda f: with_retry(f, config=config, context=context)
    
    retry_config = config or RetryConfig()
    
    if asyncio.iscoroutinefunction(func):
        async def async_wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(1, retry_config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_error = e
                    error_handler.log_error(e, context)
                    
                    # Record failure for circuit breaker
                    service_key = error_handler._get_service_key(e)
                    error_handler.record_failure(service_key)
                    
                    if not error_handler.should_retry(e, attempt):
                        break
                    
                    if attempt < retry_config.max_attempts:
                        delay = error_handler.calculate_delay(attempt, retry_config)
                        logger.info(f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{retry_config.max_attempts})")
                        await asyncio.sleep(delay)
            
            # All retries exhausted
            if last_error:
                raise last_error
            
        return async_wrapper
    else:
        def sync_wrapper(*args, **kwargs):
            last_error = None
            
            for attempt in range(1, retry_config.max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Record success for circuit breaker
                    if last_error:
                        service_key = error_handler._get_service_key(last_error)
                        error_handler.record_success(service_key)
                    
                    return result
                    
                except Exception as e:
                    last_error = e
                    error_handler.log_error(e, context)
                    
                    # Record failure for circuit breaker
                    service_key = error_handler._get_service_key(e)
                    error_handler.record_failure(service_key)
                    
                    if not error_handler.should_retry(e, attempt):
                        break
                    
                    if attempt < retry_config.max_attempts:
                        delay = error_handler.calculate_delay(attempt, retry_config)
                        logger.info(f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{retry_config.max_attempts})")
                        time.sleep(delay)
            
            # All retries exhausted
            if last_error:
                raise last_error
            
        return sync_wrapper

# Convenience functions
def handle_api_error(error: Exception, service_name: str = "unknown") -> bool:
    """Handle API errors and return whether to retry"""
    context = {"service": service_name}
    error_handler.log_error(error, context)
    return error_handler.should_retry(error, 1)

def get_error_stats() -> Dict[str, Any]:
    """Get error statistics for monitoring"""
    if not error_handler.error_history:
        return {"total_errors": 0}
    
    recent_errors = [
        e for e in error_handler.error_history
        if datetime.fromisoformat(e["timestamp"]) > datetime.utcnow() - timedelta(hours=24)
    ]
    
    categories = {}
    severities = {}
    
    for error in recent_errors:
        categories[error["category"]] = categories.get(error["category"], 0) + 1
        severities[error["severity"]] = severities.get(error["severity"], 0) + 1
    
    return {
        "total_errors": len(error_handler.error_history),
        "recent_errors": len(recent_errors),
        "categories": categories,
        "severities": severities,
        "circuit_breakers": {
            k: v for k, v in error_handler.circuit_breakers.items()
            if v["state"] != "closed"
        }
    }

# Export main components
__all__ = [
    'DillaErrorHandler', 'ErrorInfo', 'ErrorCategory', 'ErrorSeverity',
    'RetryConfig', 'RetryStrategy', 'with_retry', 'handle_api_error',
    'get_error_stats', 'error_handler'
]