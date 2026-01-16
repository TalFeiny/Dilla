"""
Dependency injection for request-scoped services
Replaces singleton pattern to prevent race conditions
"""

from typing import Optional
from fastapi import Request, Depends
import logging
import uuid
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.pre_post_cap_table import PrePostCapTable
from app.services.advanced_cap_table import CapTableCalculator
from app.services.comprehensive_deal_analyzer import ComprehensiveDealAnalyzer
# ModelRouter is the single source of truth - no direct client creation
logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating request-scoped service instances"""
    
    @staticmethod
    def create_orchestrator(request_id: Optional[str] = None) -> UnifiedMCPOrchestrator:
        """Create a new orchestrator instance with isolated state"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        logger.info(f"Creating new orchestrator for request {request_id}")
        
        # Create orchestrator - it uses ModelRouter internally (single source of truth)
        orchestrator = UnifiedMCPOrchestrator()
        orchestrator.request_id = request_id
        orchestrator.shared_data = {}  # Isolated data per request
        
        return orchestrator
    
    @staticmethod
    def create_gap_filler() -> IntelligentGapFiller:
        """Create a new gap filler instance"""
        return IntelligentGapFiller()
    
    @staticmethod
    def create_cap_table() -> PrePostCapTable:
        """Create a new simple cap table instance"""
        return PrePostCapTable()
    
    @staticmethod
    def create_advanced_cap_table() -> CapTableCalculator:
        """Create a new advanced cap table instance"""
        return CapTableCalculator()
    
    @staticmethod
    def create_deal_analyzer() -> ComprehensiveDealAnalyzer:
        """Create a new deal analyzer instance"""
        return ComprehensiveDealAnalyzer()


# Dependency injection functions for FastAPI
def get_request_id(request: Request) -> str:
    """Extract or generate request ID"""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
        logger.debug(f"Generated request ID: {request_id}")
    return request_id


def get_orchestrator(request_id: str = Depends(get_request_id)) -> UnifiedMCPOrchestrator:
    """Get request-scoped orchestrator instance"""
    return ServiceFactory.create_orchestrator(request_id)


def get_gap_filler() -> IntelligentGapFiller:
    """Get request-scoped gap filler instance"""
    return ServiceFactory.create_gap_filler()


def get_cap_table() -> PrePostCapTable:
    """Get request-scoped cap table instance"""
    return ServiceFactory.create_cap_table()


def get_advanced_cap_table() -> CapTableCalculator:
    """Get request-scoped advanced cap table instance"""
    return ServiceFactory.create_advanced_cap_table()


def get_deal_analyzer() -> ComprehensiveDealAnalyzer:
    """Get request-scoped deal analyzer instance"""
    return ServiceFactory.create_deal_analyzer()


# Import settings after defining everything else to avoid circular imports
from app.core.config import settings