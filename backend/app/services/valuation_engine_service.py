"""
Valuation Engine Service
Comprehensive valuation calculations for private companies
Migrated from frontend TypeScript implementation
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math

from app.core.database import supabase_service

logger = logging.getLogger(__name__)

class Stage(str, Enum):
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    GROWTH = "growth"
    LATE = "late"
    PUBLIC = "public"

class ValuationMethod(str, Enum):
    AUTO = "auto"
    PWERM = "pwerm"
    COMPARABLES = "comparables"
    DCF = "dcf"
    OPM = "opm"
    WATERFALL = "waterfall"

@dataclass
class ValuationRequest:
    """Valuation request parameters"""
    company_name: str
    stage: Stage
    revenue: Optional[float] = None
    growth_rate: Optional[float] = None
    last_round_valuation: Optional[float] = None
    last_round_date: Optional[str] = None
    total_raised: Optional[float] = None
    preferred_shares_outstanding: Optional[int] = None
    common_shares_outstanding: Optional[int] = None
    liquidation_preferences: List[Dict] = field(default_factory=list)
    method: ValuationMethod = ValuationMethod.AUTO

@dataclass
class PWERMScenario:
    """PWERM scenario parameters"""
    scenario: str
    probability: float
    exit_value: float
    time_to_exit: float
    present_value: float

@dataclass
class ComparableCompany:
    """Comparable company data"""
    name: str
    revenue_multiple: float
    growth_rate: float
    similarity_score: float

@dataclass
class WaterfallTier:
    """Waterfall analysis tier"""
    tier: int
    description: str
    amount: float
    participants: List[str]

@dataclass
class ValuationResult:
    """Comprehensive valuation result"""
    method_used: str
    fair_value: float
    common_stock_value: Optional[float] = None
    preferred_value: Optional[float] = None
    dlom_discount: Optional[float] = None
    assumptions: Dict[str, Any] = field(default_factory=dict)
    scenarios: List[PWERMScenario] = field(default_factory=list)
    comparables: List[ComparableCompany] = field(default_factory=list)
    waterfall: List[WaterfallTier] = field(default_factory=list)
    confidence: float = 0.8
    explanation: str = ""

class ValuationEngineService:
    """
    Advanced valuation engine for private company analysis
    """
    
    def __init__(self):
        # Industry multiples database
        self.industry_multiples = {
            'saas': {'revenue': 8.5, 'ebitda': 25.0, 'growth_premium': 1.3},
            'fintech': {'revenue': 6.2, 'ebitda': 18.0, 'growth_premium': 1.1}, 
            'healthtech': {'revenue': 4.8, 'ebitda': 15.0, 'growth_premium': 1.2},
            'edtech': {'revenue': 3.5, 'ebitda': 12.0, 'growth_premium': 0.9},
            'marketplace': {'revenue': 5.1, 'ebitda': 16.0, 'growth_premium': 1.15},
            'enterprise': {'revenue': 7.2, 'ebitda': 20.0, 'growth_premium': 1.25},
            'consumer': {'revenue': 2.8, 'ebitda': 10.0, 'growth_premium': 0.85},
            'e-commerce': {'revenue': 3.2, 'ebitda': 12.0, 'growth_premium': 0.95},
            'biotech': {'revenue': 6.5, 'ebitda': 30.0, 'growth_premium': 1.4},
            'cleantech': {'revenue': 4.0, 'ebitda': 14.0, 'growth_premium': 1.1}
        }
        
        # Stage-specific parameters
        self.stage_parameters = {
            Stage.SEED: {
                'discount_rate': 0.5,  # 50% for high risk
                'dlom': 0.4,  # 40% discount for lack of marketability
                'preferred_methods': ['pwerm']
            },
            Stage.SERIES_A: {
                'discount_rate': 0.4,
                'dlom': 0.35,
                'preferred_methods': ['pwerm', 'comparables']
            },
            Stage.SERIES_B: {
                'discount_rate': 0.3,
                'dlom': 0.3,
                'preferred_methods': ['comparables', 'pwerm']
            },
            Stage.SERIES_C: {
                'discount_rate': 0.25,
                'dlom': 0.25,
                'preferred_methods': ['comparables', 'dcf']
            },
            Stage.GROWTH: {
                'discount_rate': 0.2,
                'dlom': 0.2,
                'preferred_methods': ['dcf', 'comparables']
            },
            Stage.LATE: {
                'discount_rate': 0.15,
                'dlom': 0.15,
                'preferred_methods': ['dcf', 'opm']
            }
        }
    
    async def calculate_valuation(self, request: ValuationRequest) -> ValuationResult:
        """
        Main valuation method - automatically selects appropriate method based on stage
        """
        logger.info(f"Calculating valuation for {request.company_name} at {request.stage} stage")
        
        # Auto-select method based on stage if not specified
        method = self._select_method(request) if request.method == ValuationMethod.AUTO else request.method
        
        logger.info(f"Using valuation method: {method}")
        
        try:
            if method == ValuationMethod.PWERM:
                return await self._calculate_pwerm(request)
            elif method == ValuationMethod.COMPARABLES:
                return await self._calculate_comparables(request)
            elif method == ValuationMethod.DCF:
                return await self._calculate_dcf(request)
            elif method == ValuationMethod.OPM:
                return await self._calculate_opm(request)
            elif method == ValuationMethod.WATERFALL:
                return await self._calculate_waterfall(request)
            else:
                # Default to PWERM for startups
                return await self._calculate_pwerm(request)
                
        except Exception as e:
            logger.error(f"Valuation calculation failed: {e}")
            return ValuationResult(
                method_used="error",
                fair_value=0,
                explanation=f"Valuation failed: {str(e)}",
                confidence=0
            )
    
    def _select_method(self, request: ValuationRequest) -> ValuationMethod:
        """Select appropriate valuation method based on company stage"""
        stage = request.stage
        revenue = request.revenue or 0
        
        # Early stage (Seed, Series A) - use PWERM
        if stage in [Stage.SEED, Stage.SERIES_A]:
            return ValuationMethod.PWERM
        
        # Growth stage (Series B/C) - use Comparables with DLOM
        if stage in [Stage.SERIES_B, Stage.SERIES_C]:
            return ValuationMethod.COMPARABLES
        
        # Late stage with significant revenue - use DCF
        if stage in [Stage.GROWTH, Stage.LATE] and revenue > 50_000_000:
            return ValuationMethod.DCF
        
        # Public companies - use OPM
        if stage == Stage.PUBLIC:
            return ValuationMethod.OPM
        
        # Default to PWERM for uncertainty
        return ValuationMethod.PWERM
    
    async def _calculate_pwerm(self, request: ValuationRequest) -> ValuationResult:
        """
        Probability-Weighted Expected Return Method
        """
        logger.info("Calculating PWERM valuation")
        
        # Generate exit scenarios
        scenarios = self._generate_exit_scenarios(request)
        
        # Calculate present values
        discount_rate = self.stage_parameters[request.stage]['discount_rate']
        
        for scenario in scenarios:
            pv_factor = 1 / ((1 + discount_rate) ** scenario.time_to_exit)
            scenario.present_value = scenario.exit_value * pv_factor
        
        # Calculate probability-weighted value
        total_value = sum(s.probability * s.present_value for s in scenarios)
        
        # Apply DLOM discount
        dlom = self.stage_parameters[request.stage]['dlom']
        fair_value = total_value * (1 - dlom)
        
        # Calculate per-share values if shares outstanding provided
        common_value = None
        if request.common_shares_outstanding:
            common_value = fair_value / request.common_shares_outstanding
        
        return ValuationResult(
            method_used="PWERM",
            fair_value=fair_value,
            common_stock_value=common_value,
            dlom_discount=dlom,
            scenarios=scenarios,
            assumptions={
                'discount_rate': discount_rate,
                'dlom': dlom,
                'scenarios_count': len(scenarios)
            },
            confidence=0.75,
            explanation=f"PWERM analysis with {len(scenarios)} scenarios, {dlom*100:.0f}% DLOM discount applied"
        )
    
    async def _calculate_comparables(self, request: ValuationRequest) -> ValuationResult:
        """
        Market Comparables Method
        """
        logger.info("Calculating comparables valuation")
        
        # Get comparable companies (would query database in real implementation)
        comparables = await self._find_comparable_companies(request)
        
        if not comparables:
            # Fallback to industry averages
            return await self._calculate_industry_multiple_valuation(request)
        
        # Calculate weighted average multiple
        total_weight = sum(c.similarity_score for c in comparables)
        weighted_multiple = sum(c.revenue_multiple * c.similarity_score for c in comparables) / total_weight
        
        # Apply growth premium/discount
        avg_growth = sum(c.growth_rate for c in comparables) / len(comparables)
        company_growth = request.growth_rate or avg_growth
        
        growth_adjustment = 1 + (company_growth - avg_growth) * 0.5
        adjusted_multiple = weighted_multiple * growth_adjustment
        
        # Calculate value
        revenue = request.revenue or 0
        enterprise_value = revenue * adjusted_multiple
        
        # Apply DLOM
        dlom = self.stage_parameters[request.stage]['dlom']
        fair_value = enterprise_value * (1 - dlom)
        
        return ValuationResult(
            method_used="Market Comparables",
            fair_value=fair_value,
            dlom_discount=dlom,
            comparables=comparables,
            assumptions={
                'weighted_multiple': adjusted_multiple,
                'growth_adjustment': growth_adjustment,
                'dlom': dlom,
                'revenue_used': revenue
            },
            confidence=0.8,
            explanation=f"Market comparables analysis using {len(comparables)} companies, {adjusted_multiple:.1f}x revenue multiple"
        )
    
    async def _calculate_dcf(self, request: ValuationRequest) -> ValuationResult:
        """
        Discounted Cash Flow Method
        """
        logger.info("Calculating DCF valuation")
        
        # Build cash flow projections
        projections = self._build_cash_flow_projections(request)
        
        # Calculate terminal value
        terminal_growth = 0.03  # 3% perpetual growth
        discount_rate = self.stage_parameters[request.stage]['discount_rate']
        
        terminal_fcf = projections[-1]['free_cash_flow']
        terminal_value = terminal_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
        
        # Discount all cash flows to present value
        present_values = []
        for i, projection in enumerate(projections):
            year = i + 1
            pv = projection['free_cash_flow'] / ((1 + discount_rate) ** year)
            present_values.append(pv)
        
        # Discount terminal value
        terminal_pv = terminal_value / ((1 + discount_rate) ** len(projections))
        
        # Calculate enterprise value
        enterprise_value = sum(present_values) + terminal_pv
        
        # Convert to equity value (subtract net debt, add cash)
        # Assuming no net debt for simplicity
        equity_value = enterprise_value
        
        return ValuationResult(
            method_used="DCF",
            fair_value=equity_value,
            assumptions={
                'discount_rate': discount_rate,
                'terminal_growth': terminal_growth,
                'projection_years': len(projections),
                'terminal_value': terminal_value,
                'enterprise_value': enterprise_value
            },
            confidence=0.7,
            explanation=f"DCF analysis with {len(projections)}-year projections, {terminal_growth*100:.1f}% terminal growth"
        )
    
    async def _calculate_opm(self, request: ValuationRequest) -> ValuationResult:
        """
        Option Pricing Model (for complex capital structures)
        """
        logger.info("Calculating OPM valuation")
        
        # Simplified OPM implementation
        # In practice, would use Black-Scholes or binomial model
        
        enterprise_value = request.last_round_valuation or 100_000_000
        volatility = 0.6  # High volatility for private companies
        
        # Calculate common stock value as call option
        # This is a simplified version
        option_value = enterprise_value * 0.3  # Simplified calculation
        
        return ValuationResult(
            method_used="Option Pricing Model",
            fair_value=option_value,
            assumptions={
                'enterprise_value': enterprise_value,
                'volatility': volatility,
                'option_value_ratio': 0.3
            },
            confidence=0.6,
            explanation="Simplified OPM treating common stock as call option on enterprise value"
        )
    
    async def _calculate_waterfall(self, request: ValuationRequest) -> ValuationResult:
        """
        Liquidation Waterfall Analysis
        """
        logger.info("Calculating waterfall valuation")
        
        # Build waterfall from liquidation preferences
        waterfall_tiers = self._build_liquidation_waterfall(request)
        
        # Assume exit value for waterfall analysis
        exit_value = request.last_round_valuation or 100_000_000
        exit_value *= 2  # Assume 2x growth for exit
        
        # Distribute value through waterfall
        remaining_value = exit_value
        common_value = 0
        
        for tier in waterfall_tiers:
            if remaining_value <= 0:
                break
                
            if remaining_value >= tier.amount:
                remaining_value -= tier.amount
            else:
                tier.amount = remaining_value
                remaining_value = 0
        
        # Remaining value goes to common
        if remaining_value > 0:
            common_value = remaining_value
        
        return ValuationResult(
            method_used="Liquidation Waterfall",
            fair_value=common_value,
            waterfall=waterfall_tiers,
            assumptions={
                'exit_value': exit_value,
                'waterfall_tiers': len(waterfall_tiers)
            },
            confidence=0.65,
            explanation=f"Waterfall analysis with {len(waterfall_tiers)} liquidation tiers"
        )
    
    def _generate_exit_scenarios(self, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate realistic exit scenarios for PWERM"""
        base_value = request.last_round_valuation or 100_000_000
        
        scenarios = [
            PWERMScenario(
                scenario="IPO Success",
                probability=0.15,
                exit_value=base_value * 10,
                time_to_exit=5.0,
                present_value=0  # Will be calculated
            ),
            PWERMScenario(
                scenario="Strategic Acquisition",
                probability=0.35,
                exit_value=base_value * 4,
                time_to_exit=3.0,
                present_value=0
            ),
            PWERMScenario(
                scenario="PE Acquisition",
                probability=0.25,
                exit_value=base_value * 2.5,
                time_to_exit=4.0,
                present_value=0
            ),
            PWERMScenario(
                scenario="Management Buyout",
                probability=0.10,
                exit_value=base_value * 1.5,
                time_to_exit=2.0,
                present_value=0
            ),
            PWERMScenario(
                scenario="Down Round/Distress",
                probability=0.15,
                exit_value=base_value * 0.3,
                time_to_exit=1.0,
                present_value=0
            )
        ]
        
        return scenarios
    
    async def _find_comparable_companies(self, request: ValuationRequest) -> List[ComparableCompany]:
        """Find comparable companies from database"""
        # In real implementation, would query database
        # Returning mock data for now
        
        comparables = [
            ComparableCompany(
                name="Comp A",
                revenue_multiple=8.5,
                growth_rate=1.5,
                similarity_score=0.9
            ),
            ComparableCompany(
                name="Comp B", 
                revenue_multiple=6.2,
                growth_rate=1.2,
                similarity_score=0.8
            ),
            ComparableCompany(
                name="Comp C",
                revenue_multiple=7.8,
                growth_rate=1.8,
                similarity_score=0.85
            )
        ]
        
        return comparables
    
    async def _calculate_industry_multiple_valuation(self, request: ValuationRequest) -> ValuationResult:
        """Fallback to industry average multiples"""
        # Assume SaaS for default
        industry = 'saas'  # Would determine from company data
        multiples = self.industry_multiples[industry]
        
        revenue = request.revenue or 0
        growth_rate = request.growth_rate or 1.0
        
        # Apply growth premium
        growth_premium = multiples['growth_premium'] if growth_rate > 1.5 else 1.0
        adjusted_multiple = multiples['revenue'] * growth_premium
        
        enterprise_value = revenue * adjusted_multiple
        
        # Apply DLOM
        dlom = self.stage_parameters[request.stage]['dlom']
        fair_value = enterprise_value * (1 - dlom)
        
        return ValuationResult(
            method_used="Industry Multiples",
            fair_value=fair_value,
            dlom_discount=dlom,
            assumptions={
                'industry': industry,
                'revenue_multiple': adjusted_multiple,
                'growth_premium': growth_premium,
                'dlom': dlom
            },
            confidence=0.6,
            explanation=f"Industry average {industry} multiples: {adjusted_multiple:.1f}x revenue"
        )
    
    def _build_cash_flow_projections(self, request: ValuationRequest) -> List[Dict[str, float]]:
        """Build 5-year cash flow projections"""
        base_revenue = request.revenue or 10_000_000
        growth_rate = request.growth_rate or 1.3
        
        projections = []
        
        for year in range(1, 6):  # 5-year projection
            revenue = base_revenue * (growth_rate ** year)
            
            # Assume improving margins over time
            gross_margin = min(0.8, 0.6 + (year * 0.04))
            operating_margin = min(0.25, year * 0.05)
            
            gross_profit = revenue * gross_margin
            operating_income = revenue * operating_margin
            
            # Simplified tax and capex assumptions
            tax_rate = 0.25
            after_tax_income = operating_income * (1 - tax_rate)
            capex = revenue * 0.03  # 3% of revenue
            
            free_cash_flow = after_tax_income - capex
            
            projections.append({
                'year': year,
                'revenue': revenue,
                'gross_profit': gross_profit,
                'operating_income': operating_income,
                'free_cash_flow': free_cash_flow
            })
        
        return projections
    
    def _build_liquidation_waterfall(self, request: ValuationRequest) -> List[WaterfallTier]:
        """Build liquidation waterfall from preferences"""
        # Simplified waterfall - would parse actual liquidation preferences
        
        waterfall = []
        
        # Senior liquidation preferences first
        if request.total_raised:
            waterfall.append(WaterfallTier(
                tier=1,
                description="Liquidation Preferences",
                amount=request.total_raised,
                participants=["Preferred Shareholders"]
            ))
        
        # Then participation rights, etc.
        # This would be much more complex in practice
        
        return waterfall

# Global service instance
valuation_engine_service = ValuationEngineService()