"""
Custom exception classes for better error handling
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException


class DillaBaseException(Exception):
    """Base exception for all Dilla AI exceptions"""
    def __init__(self, message: str, code: str = "DILLA_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(DillaBaseException):
    """Raised when input validation fails"""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


class ExternalAPIError(DillaBaseException):
    """Raised when external API calls fail"""
    def __init__(self, service: str, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, f"{service.upper()}_API_ERROR", details)
        self.service = service
        self.status_code = status_code


class DatabaseError(DillaBaseException):
    """Raised when database operations fail"""
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_ERROR", details)
        self.operation = operation


class AuthenticationError(DillaBaseException):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTH_ERROR", details)


class AuthorizationError(DillaBaseException):
    """Raised when authorization fails"""
    def __init__(self, message: str = "Insufficient permissions", resource: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTHZ_ERROR", details)
        self.resource = resource


class RateLimitError(DillaBaseException):
    """Raised when rate limits are exceeded"""
    def __init__(self, service: str, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        message = f"Rate limit exceeded for {service}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, "RATE_LIMIT_ERROR", details)
        self.service = service
        self.retry_after = retry_after


class TimeoutError(DillaBaseException):
    """Raised when operations timeout"""
    def __init__(self, operation: str, timeout_seconds: int, details: Optional[Dict[str, Any]] = None):
        message = f"Operation '{operation}' timed out after {timeout_seconds} seconds"
        super().__init__(message, "TIMEOUT_ERROR", details)
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class ResourceNotFoundError(DillaBaseException):
    """Raised when a resource is not found"""
    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(message, "NOT_FOUND", details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class CalculationError(DillaBaseException):
    """Raised when financial calculations fail"""
    def __init__(self, calculation_type: str, message: str, inputs: Optional[Dict[str, Any]] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CALCULATION_ERROR", details)
        self.calculation_type = calculation_type
        self.inputs = inputs


def create_http_exception(error: DillaBaseException) -> HTTPException:
    """Convert a DillaBaseException to an HTTPException"""
    status_code = 500  # Default to internal server error
    
    # Map error types to HTTP status codes
    if isinstance(error, ValidationError):
        status_code = 400
    elif isinstance(error, AuthenticationError):
        status_code = 401
    elif isinstance(error, AuthorizationError):
        status_code = 403
    elif isinstance(error, ResourceNotFoundError):
        status_code = 404
    elif isinstance(error, RateLimitError):
        status_code = 429
    elif isinstance(error, TimeoutError):
        status_code = 408
    elif isinstance(error, ExternalAPIError) and error.status_code:
        status_code = error.status_code
    
    return HTTPException(
        status_code=status_code,
        detail={
            "code": error.code,
            "message": error.message,
            "details": error.details
        }
    )