"""
Advanced Debt Structures Service
Handles complex debt instruments and structures for portfolio companies
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class DebtInstrument:
    """Represents a debt instrument"""
    instrument_type: str  # convertible_note, venture_debt, revenue_based_financing
    principal: float
    interest_rate: float
    maturity_date: Optional[str]
    conversion_discount: Optional[float] = None
    valuation_cap: Optional[float] = None
    
@dataclass
class DebtStructure:
    """Complete debt structure for a company"""
    company_name: str
    total_debt: float
    instruments: List[DebtInstrument]
    debt_to_equity_ratio: float
    interest_coverage_ratio: Optional[float]

class AdvancedDebtStructures:
    """Service for managing advanced debt structures"""
    
    def __init__(self):
        self.debt_cache = {}
        logger.info("AdvancedDebtStructures service initialized")
    
    def analyze_debt_structure(self, company_data: Dict[str, Any]) -> DebtStructure:
        """
        Analyze a company's debt structure
        
        Args:
            company_data: Company information including financials
            
        Returns:
            DebtStructure with analysis results
        """
        company_name = company_data.get("company", "Unknown")
        
        # Extract debt information from funding rounds
        instruments = []
        total_debt = 0
        
        funding_rounds = company_data.get("funding_rounds", [])
        for round_data in funding_rounds:
            if "debt" in round_data.get("round", "").lower() or "note" in round_data.get("round", "").lower():
                amount = round_data.get("amount", 0)
                total_debt += amount
                
                # Create debt instrument
                instrument = DebtInstrument(
                    instrument_type="convertible_note" if "convertible" in round_data.get("round", "").lower() else "venture_debt",
                    principal=amount,
                    interest_rate=0.08,  # Default 8% interest
                    maturity_date=None,
                    conversion_discount=0.20 if "convertible" in round_data.get("round", "").lower() else None,
                    valuation_cap=round_data.get("valuation", None)
                )
                instruments.append(instrument)
        
        # Calculate ratios
        equity = company_data.get("valuation", 100_000_000) - total_debt
        debt_to_equity = total_debt / equity if equity > 0 else 0
        
        # Create debt structure
        structure = DebtStructure(
            company_name=company_name,
            total_debt=total_debt,
            instruments=instruments,
            debt_to_equity_ratio=debt_to_equity,
            interest_coverage_ratio=None  # Would need EBITDA to calculate
        )
        
        # Cache result
        self.debt_cache[company_name] = structure
        
        return structure
    
    def calculate_conversion_scenarios(
        self, 
        debt_structure: DebtStructure,
        exit_valuation: float
    ) -> Dict[str, Any]:
        """
        Calculate conversion scenarios for convertible debt
        
        Args:
            debt_structure: Company's debt structure
            exit_valuation: Assumed exit valuation
            
        Returns:
            Conversion analysis including dilution impact
        """
        conversion_analysis = {
            "exit_valuation": exit_valuation,
            "convertible_instruments": [],
            "total_dilution": 0,
            "debt_remaining": 0
        }
        
        for instrument in debt_structure.instruments:
            if instrument.conversion_discount is not None or instrument.valuation_cap is not None:
                # This is convertible debt
                conversion_price = exit_valuation
                
                # Apply valuation cap if present
                if instrument.valuation_cap:
                    conversion_price = min(conversion_price, instrument.valuation_cap)
                
                # Apply discount if present
                if instrument.conversion_discount:
                    conversion_price *= (1 - instrument.conversion_discount)
                
                # Calculate shares from conversion
                shares_issued = instrument.principal / conversion_price
                dilution = shares_issued / (1 + shares_issued)  # Simplified dilution calc
                
                conversion_analysis["convertible_instruments"].append({
                    "principal": instrument.principal,
                    "conversion_price": conversion_price,
                    "shares_issued": shares_issued,
                    "dilution": dilution
                })
                conversion_analysis["total_dilution"] += dilution
            else:
                # Regular debt, doesn't convert
                conversion_analysis["debt_remaining"] += instrument.principal
        
        return conversion_analysis
    
    def evaluate_debt_capacity(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a company's capacity for additional debt
        
        Args:
            company_data: Company financial information
            
        Returns:
            Debt capacity analysis
        """
        revenue = company_data.get("revenue", 0) or company_data.get("inferred_revenue", 0)
        burn_rate = company_data.get("burn_rate", 0) or 500_000
        
        # Simple debt capacity model based on revenue
        # Companies can typically support debt of 3-4x ARR for venture debt
        max_debt = revenue * 3
        
        # Get current debt
        current_structure = self.analyze_debt_structure(company_data)
        current_debt = current_structure.total_debt
        
        # Available capacity
        available_capacity = max(0, max_debt - current_debt)
        
        return {
            "current_debt": current_debt,
            "max_debt_capacity": max_debt,
            "available_capacity": available_capacity,
            "debt_service_coverage": revenue / (current_debt * 0.15) if current_debt > 0 else float('inf'),
            "recommendation": "Can support additional debt" if available_capacity > 0 else "At debt capacity limit"
        }