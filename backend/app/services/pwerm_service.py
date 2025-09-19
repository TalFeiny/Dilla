"""
PWERM Service - Unified interface for PWERM calculations
Wraps the hybrid and comprehensive PWERM implementations
"""

from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from app.services.pwerm_hybrid import HybridPWERM
from app.services.pwerm_comprehensive import ComprehensivePWERM

logger = logging.getLogger(__name__)


class PWERMService:
    """
    Unified PWERM service that provides:
    - Simple 3-scenario analysis (bear/base/bull)
    - Comprehensive multi-scenario analysis
    - Hybrid approach for different contexts
    """
    
    def __init__(self):
        self.hybrid_pwerm = HybridPWERM()
        self.comprehensive_pwerm = ComprehensivePWERM()
        logger.info("PWERM Service initialized")
    
    async def analyze(
        self,
        company_data: Dict[str, Any],
        analysis_type: str = "hybrid",
        scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Main PWERM analysis entry point
        
        Args:
            company_data: Company financial data
            analysis_type: "simple", "comprehensive", or "hybrid"
            scenarios: Optional custom scenarios
        
        Returns:
            PWERM analysis results
        """
        try:
            if analysis_type == "simple":
                return await self._simple_analysis(company_data, scenarios)
            elif analysis_type == "comprehensive":
                return await self._comprehensive_analysis(company_data, scenarios)
            else:  # hybrid
                return await self._hybrid_analysis(company_data, scenarios)
        except Exception as e:
            logger.error(f"PWERM analysis failed: {str(e)}")
            return {
                "error": str(e),
                "status": "failed",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _simple_analysis(
        self,
        company_data: Dict[str, Any],
        scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Simple 3-scenario PWERM (bear/base/bull)
        """
        if not scenarios:
            # Default scenarios
            scenarios = [
                {
                    "name": "Bear",
                    "exit_value": company_data.get("valuation", 10000000) * 0.5,
                    "probability": 0.25,
                    "time_to_exit": 5
                },
                {
                    "name": "Base",
                    "exit_value": company_data.get("valuation", 10000000) * 1.0,
                    "probability": 0.50,
                    "time_to_exit": 4
                },
                {
                    "name": "Bull",
                    "exit_value": company_data.get("valuation", 10000000) * 2.0,
                    "probability": 0.25,
                    "time_to_exit": 3
                }
            ]
        
        # Calculate probability-weighted value
        weighted_value = sum(
            s["exit_value"] * s["probability"] 
            for s in scenarios
        )
        
        return {
            "method": "PWERM_simple",
            "scenarios": scenarios,
            "weighted_value": weighted_value,
            "company": company_data.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _comprehensive_analysis(
        self,
        company_data: Dict[str, Any],
        scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive multi-scenario PWERM with detailed outcomes
        """
        result = self.comprehensive_pwerm.calculate_pwerm(
            company_data=company_data,
            custom_scenarios=scenarios
        )
        
        return {
            "method": "PWERM_comprehensive",
            "results": result,
            "company": company_data.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _hybrid_analysis(
        self,
        company_data: Dict[str, Any],
        scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Hybrid approach - simple display with comprehensive backup
        """
        result = self.hybrid_pwerm.calculate_hybrid_pwerm(
            company_data=company_data,
            display_mode="grid"  # Can be "grid" or "detailed"
        )
        
        return {
            "method": "PWERM_hybrid",
            "results": result,
            "company": company_data.get("name", "Unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_scenario_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get pre-defined scenario templates
        """
        return {
            "conservative": [
                {"name": "Failure", "probability": 0.4, "multiple": 0},
                {"name": "Acquihire", "probability": 0.3, "multiple": 0.5},
                {"name": "Modest Exit", "probability": 0.2, "multiple": 2},
                {"name": "Good Exit", "probability": 0.1, "multiple": 5}
            ],
            "balanced": [
                {"name": "Failure", "probability": 0.25, "multiple": 0},
                {"name": "Acquihire", "probability": 0.25, "multiple": 1},
                {"name": "Strategic Sale", "probability": 0.35, "multiple": 3},
                {"name": "IPO", "probability": 0.15, "multiple": 10}
            ],
            "aggressive": [
                {"name": "Acquihire", "probability": 0.2, "multiple": 1},
                {"name": "Strategic Sale", "probability": 0.4, "multiple": 5},
                {"name": "IPO", "probability": 0.3, "multiple": 15},
                {"name": "Unicorn", "probability": 0.1, "multiple": 50}
            ]
        }


# Singleton instance
pwerm_service = PWERMService()