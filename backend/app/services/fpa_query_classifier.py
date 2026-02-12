"""
FPA Query Classifier
Routes parsed queries to appropriate handlers
"""

import logging
from typing import Dict, Any
from enum import Enum

from app.services.nl_fpa_parser import ParsedQuery

logger = logging.getLogger(__name__)


class QueryHandlerType(str, Enum):
    """Types of query handlers"""
    SCENARIO = "scenario"
    FORECAST = "forecast"
    VALUATION = "valuation"
    IMPACT = "impact"
    SENSITIVITY = "sensitivity"
    COMPARISON = "comparison"
    REGRESSION = "regression"
    GROWTH_DECAY = "growth_decay"


class FPAQueryClassifier:
    """Classifies parsed queries and routes them to appropriate handlers"""
    
    def __init__(self):
        pass
    
    def route(self, parsed: ParsedQuery) -> str:
        """
        Route a parsed query to the appropriate handler
        
        Args:
            parsed: ParsedQuery object
            
        Returns:
            Handler key (e.g., "scenario", "forecast", etc.)
        """
        # TODO: Implement classification logic using LLM or rule-based system
        logger.info(f"Classifying query type: {parsed.query_type}")
        
        # Placeholder: return based on query_type
        query_type_lower = parsed.query_type.lower()
        
        if "scenario" in query_type_lower or "multi_step" in query_type_lower:
            return QueryHandlerType.SCENARIO
        elif "forecast" in query_type_lower:
            return QueryHandlerType.FORECAST
        elif "valuation" in query_type_lower:
            return QueryHandlerType.VALUATION
        elif "regression" in query_type_lower:
            return QueryHandlerType.REGRESSION
        elif "sensitivity" in query_type_lower:
            return QueryHandlerType.SENSITIVITY
        else:
            return QueryHandlerType.SCENARIO  # Default
