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
    RECENT_TRANSACTION = "recent_transaction"
    COST_METHOD = "cost_method"
    MILESTONE = "milestone"

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
    business_model: Optional[str] = None  # CRITICAL: For correct multiples
    industry: Optional[str] = None  # Fallback if business_model not provided

@dataclass
class PWERMScenario:
    """PWERM scenario parameters"""
    scenario: str
    probability: float
    exit_value: float
    time_to_exit: float
    present_value: float
    moic: float

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
    
    def generate_simple_scenarios(self, request: ValuationRequest) -> Dict[str, Any]:
        """Generate simplified bear/base/bull scenarios for quick display"""
        base_value = request.last_round_valuation or 100_000_000
        
        # Get full PWERM scenarios first
        full_scenarios = self._generate_exit_scenarios(request)
        
        # Calculate weighted average exit value
        weighted_exit = sum(s.probability * s.exit_value for s in full_scenarios)
        
        # Generate bear/base/bull based on distribution
        bear_scenarios = [s for s in full_scenarios if s.exit_value < weighted_exit * 0.7]
        base_scenarios = [s for s in full_scenarios if weighted_exit * 0.7 <= s.exit_value <= weighted_exit * 1.3]
        bull_scenarios = [s for s in full_scenarios if s.exit_value > weighted_exit * 1.3]
        
        # If no scenarios in a category, create synthetic ones
        if not bear_scenarios:
            bear_value = weighted_exit * 0.5
            bear_prob = 0.25
        else:
            bear_value = sum(s.probability * s.exit_value for s in bear_scenarios) / sum(s.probability for s in bear_scenarios)
            bear_prob = sum(s.probability for s in bear_scenarios)
        
        if not base_scenarios:
            base_value = weighted_exit
            base_prob = 0.50
        else:
            base_value = sum(s.probability * s.exit_value for s in base_scenarios) / sum(s.probability for s in base_scenarios)
            base_prob = sum(s.probability for s in base_scenarios)
        
        if not bull_scenarios:
            bull_value = weighted_exit * 2.0
            bull_prob = 0.25
        else:
            bull_value = sum(s.probability * s.exit_value for s in bull_scenarios) / sum(s.probability for s in bull_scenarios)
            bull_prob = sum(s.probability for s in bull_scenarios)
        
        # Normalize probabilities
        total_prob = bear_prob + base_prob + bull_prob
        bear_prob /= total_prob
        base_prob /= total_prob
        bull_prob /= total_prob
        
        # Calculate IRR and MOIC for each scenario (assuming $10M investment)
        investment = 10_000_000
        time_to_exit = 5.0  # Default 5 years
        
        # Ownership percentage (simplified)
        ownership_pct = investment / base_value if base_value > 0 else 0.1
        
        # Calculate risk metrics
        risk_free_rate = 0.045  # Current T-bill rate
        fund_size = 250_000_000  # Typical Series A/B fund size
        
        # Calculate expected return and volatility for risk-adjusted metrics
        scenarios_for_risk = [
            {"return": ((bear_value * ownership_pct / investment) ** (1/time_to_exit)) - 1, "prob": bear_prob},
            {"return": ((base_value * ownership_pct / investment) ** (1/time_to_exit)) - 1, "prob": base_prob},
            {"return": ((bull_value * ownership_pct / investment) ** (1/time_to_exit)) - 1, "prob": bull_prob}
        ]
        
        expected_return = sum(s["return"] * s["prob"] for s in scenarios_for_risk)
        variance = sum(s["prob"] * (s["return"] - expected_return) ** 2 for s in scenarios_for_risk)
        volatility = variance ** 0.5
        
        # Sharpe ratio (risk-adjusted return)
        sharpe_ratio = (expected_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        # Calculate DPI contribution for each scenario
        bear_dpi_contribution = (bear_value * ownership_pct) / fund_size
        base_dpi_contribution = (base_value * ownership_pct) / fund_size
        bull_dpi_contribution = (bull_value * ownership_pct) / fund_size
        
        simplified = {
            "bear": {
                "exit_value": bear_value,
                "probability": bear_prob,
                "proceeds": bear_value * ownership_pct,
                "moic": (bear_value * ownership_pct) / investment,
                "irr": ((bear_value * ownership_pct / investment) ** (1/time_to_exit)) - 1,
                "risk_adjusted_irr": max(0, ((bear_value * ownership_pct / investment) ** (1/time_to_exit)) - 1 - risk_free_rate),
                "dpi_contribution": bear_dpi_contribution,
                "dpi_impact_pct": bear_dpi_contribution * 100,
                "waterfall_impact": "Common likely wiped out by preferences",
                "fund_impact": f"Reduces fund DPI by {bear_dpi_contribution:.2%}, may trigger LP concerns"
            },
            "base": {
                "exit_value": base_value,
                "probability": base_prob,
                "proceeds": base_value * ownership_pct,
                "moic": (base_value * ownership_pct) / investment,
                "irr": ((base_value * ownership_pct / investment) ** (1/time_to_exit)) - 1,
                "risk_adjusted_irr": ((base_value * ownership_pct / investment) ** (1/time_to_exit)) - 1 - risk_free_rate,
                "dpi_contribution": base_dpi_contribution,
                "dpi_impact_pct": base_dpi_contribution * 100,
                "waterfall_impact": "Preferences cleared, common participates",
                "fund_impact": f"Contributes {base_dpi_contribution:.2%} to fund DPI target of 2.5x"
            },
            "bull": {
                "exit_value": bull_value,
                "probability": bull_prob,
                "proceeds": bull_value * ownership_pct,
                "moic": (bull_value * ownership_pct) / investment,
                "irr": ((bull_value * ownership_pct / investment) ** (1/time_to_exit)) - 1,
                "risk_adjusted_irr": ((bull_value * ownership_pct / investment) ** (1/time_to_exit)) - 1 - risk_free_rate,
                "dpi_contribution": bull_dpi_contribution,
                "dpi_impact_pct": bull_dpi_contribution * 100,
                "waterfall_impact": "Full participation for all shareholders",
                "fund_impact": f"Fund returner ({bull_dpi_contribution:.1%} DPI), drives top quartile performance"
            },
            "risk_metrics": {
                "expected_irr": expected_return,
                "volatility": volatility,
                "sharpe_ratio": sharpe_ratio,
                "risk_adjusted_expected_return": expected_return - risk_free_rate,
                "probability_weighted_dpi": bear_dpi_contribution * bear_prob + base_dpi_contribution * base_prob + bull_dpi_contribution * bull_prob,
                "var_95": expected_return - 1.65 * volatility,  # Value at Risk (95% confidence)
                "risk_score": min(100, max(0, sharpe_ratio * 25 + 50))  # 0-100 score
            },
            "full_scenarios": full_scenarios,  # Include full PWERM for drill-down
            "weighted_value": weighted_exit,
            "ownership_percentage": ownership_pct,
            "fund_context": {
                "fund_size": fund_size,
                "investment_as_pct_of_fund": (investment / fund_size) * 100,
                "required_dpi_for_3x": 3.0,
                "current_scenario_weighted_dpi": bear_dpi_contribution * bear_prob + base_dpi_contribution * base_prob + bull_dpi_contribution * bull_prob
            },
            "citations": {
                "probabilities": "Carta State of Private Markets Q3 2024",
                "exit_multiples": "PitchBook VC Exit Report 2024",
                "waterfall": "SVB State of the Markets - 85% non-participating preferred",
                "fund_metrics": "Cambridge Associates US VC Benchmark Q2 2024"
            }
        }
        
        # Add funding path scenarios
        funding_paths = self._calculate_funding_path_scenarios(
            company_data, 
            investment, 
            ownership_pct,
            time_to_exit
        )
        
        simplified["funding_path_analysis"] = funding_paths
        
        return simplified
    
    def _calculate_funding_path_scenarios(
        self,
        company_data: Dict[str, Any],
        initial_investment: float,
        initial_ownership: float,
        time_to_exit: float
    ) -> Dict[str, Any]:
        """Calculate ownership evolution through different funding paths"""
        
        current_valuation = company_data.get("valuation", 100_000_000)
        current_stage = company_data.get("stage", "Series A")
        
        # Define typical funding paths
        paths = {
            "conservative": {
                "description": "Slow, steady growth with minimal dilution",
                "rounds": [
                    {"name": "Series B", "raise": 30_000_000, "valuation_step_up": 2.5, "year": 1.5},
                    {"name": "Series C", "raise": 50_000_000, "valuation_step_up": 2.0, "year": 3.0},
                    {"name": "Exit", "year": time_to_exit}
                ]
            },
            "aggressive": {
                "description": "Rapid scaling with heavy dilution",
                "rounds": [
                    {"name": "Series B", "raise": 50_000_000, "valuation_step_up": 2.0, "year": 1.0},
                    {"name": "Series C", "raise": 100_000_000, "valuation_step_up": 1.8, "year": 2.0},
                    {"name": "Series D", "raise": 150_000_000, "valuation_step_up": 1.5, "year": 3.5},
                    {"name": "Exit", "year": time_to_exit}
                ]
            },
            "bootstrapped": {
                "description": "Minimal external funding, founder-friendly",
                "rounds": [
                    {"name": "Series B", "raise": 20_000_000, "valuation_step_up": 3.0, "year": 2.0},
                    {"name": "Exit", "year": time_to_exit}
                ]
            }
        }
        
        results = {}
        
        for path_name, path_config in paths.items():
            current_ownership = initial_ownership
            total_invested = initial_investment
            current_val = current_valuation
            dilution_events = []
            
            for round_data in path_config["rounds"]:
                if round_data["name"] == "Exit":
                    continue
                    
                # Calculate new valuation
                pre_money = current_val * round_data["valuation_step_up"]
                post_money = pre_money + round_data["raise"]
                
                # Dilution calculation
                new_ownership = current_ownership * (pre_money / post_money)
                dilution = current_ownership - new_ownership
                
                # Pro-rata investment to maintain ownership (optional)
                pro_rata_investment = current_ownership * round_data["raise"]
                maintained_ownership = (current_ownership * pre_money + pro_rata_investment) / post_money
                
                dilution_events.append({
                    "round": round_data["name"],
                    "year": round_data["year"],
                    "pre_money": pre_money,
                    "post_money": post_money,
                    "ownership_before": current_ownership,
                    "ownership_after": new_ownership,
                    "dilution": dilution,
                    "pro_rata_needed": pro_rata_investment,
                    "ownership_if_pro_rata": maintained_ownership
                })
                
                current_ownership = new_ownership
                current_val = post_money
            
            # Calculate final returns based on exit scenarios
            exit_multiples = {
                "conservative": 3.0,  # 3x current valuation
                "base": 5.0,          # 5x current valuation
                "aggressive": 10.0    # 10x current valuation
            }
            
            path_returns = {}
            for exit_type, exit_multiple in exit_multiples.items():
                exit_valuation = current_val * exit_multiple
                proceeds = exit_valuation * current_ownership
                moic = proceeds / total_invested
                irr = (moic ** (1/time_to_exit)) - 1
                dpi_contribution = proceeds / 250_000_000  # Assume $250M fund
                
                path_returns[exit_type] = {
                    "exit_valuation": exit_valuation,
                    "proceeds": proceeds,
                    "moic": moic,
                    "irr": irr,
                    "dpi_contribution": dpi_contribution
                }
            
            results[path_name] = {
                "description": path_config["description"],
                "final_ownership": current_ownership,
                "total_dilution": initial_ownership - current_ownership,
                "dilution_events": dilution_events,
                "exit_scenarios": path_returns,
                "recommendation": self._get_path_recommendation(
                    current_ownership, initial_ownership, path_returns
                )
            }
        
        return results
    
    def _get_path_recommendation(
        self,
        final_ownership: float,
        initial_ownership: float,
        returns: Dict[str, Any]
    ) -> str:
        """Generate recommendation based on funding path analysis"""
        
        dilution_pct = (initial_ownership - final_ownership) / initial_ownership
        base_irr = returns["base"]["irr"]
        
        if dilution_pct > 0.7:
            return "Heavy dilution path - consider reserving capital for pro-rata"
        elif dilution_pct < 0.3 and base_irr > 0.35:
            return "Founder-friendly path with strong returns - optimal scenario"
        elif base_irr > 0.5:
            return "High return potential despite dilution - acceptable path"
        else:
            return "Moderate path - monitor execution closely"

    async def calculate_valuation(self, request: ValuationRequest) -> ValuationResult:
        """
        Main valuation method - automatically selects appropriate method based on stage
        """
        logger.info(f"Calculating valuation for {request.company_name} at {request.stage} stage")
        
        # Auto-select method based on stage if not specified
        method = self._select_method(request) if request.method == ValuationMethod.AUTO else request.method
        
        logger.info(f"Using valuation method: {method}")
        
        try:
            if method == ValuationMethod.RECENT_TRANSACTION:
                return await self._calculate_recent_transaction(request)
            elif method == ValuationMethod.COST_METHOD:
                return await self._calculate_cost_method(request)
            elif method == ValuationMethod.MILESTONE:
                return await self._calculate_milestone(request)
            elif method == ValuationMethod.PWERM:
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
                # Default to Recent Transaction if available, else PWERM
                if request.last_round_valuation and request.last_round_date:
                    return await self._calculate_recent_transaction(request)
                else:
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
        
        # Calculate ownership and investment for MOIC calculation
        investment = 10_000_000  # Standard $10M investment assumption
        ownership_pct = investment / (request.last_round_valuation or 100_000_000)
        
        for scenario in scenarios:
            pv_factor = 1 / ((1 + discount_rate) ** scenario.time_to_exit)
            scenario.present_value = scenario.exit_value * pv_factor
            # Calculate MOIC: (exit value * ownership) / investment
            scenario.moic = (scenario.exit_value * ownership_pct) / investment
        
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
        Enhanced Market Comparables Method
        Includes both public comparables AND recent M&A transactions
        """
        logger.info("Calculating comparables valuation with M&A transactions")
        
        # Get comparable companies AND recent M&A deals
        comparables = await self._find_comparable_companies(request)
        ma_transactions = await self._find_recent_ma_transactions(request)
        
        # Combine both data sources
        all_comparables = []
        
        # Add public comparables
        if comparables:
            all_comparables.extend(comparables)
        
        # Add M&A comparables with higher weight (more relevant)
        if ma_transactions:
            for transaction in ma_transactions:
                # M&A transactions get 1.5x weight as they're actual exit values
                transaction.similarity_score *= 1.5
                all_comparables.append(transaction)
        
        if not all_comparables:
            # Fallback to industry averages
            return await self._calculate_industry_multiple_valuation(request)
        
        # Calculate weighted average multiple
        total_weight = sum(c.similarity_score for c in all_comparables)
        weighted_multiple = sum(c.revenue_multiple * c.similarity_score for c in all_comparables) / total_weight
        
        # Apply growth premium/discount
        avg_growth = sum(c.growth_rate for c in all_comparables) / len(all_comparables)
        company_growth = request.growth_rate or avg_growth
        
        growth_adjustment = 1 + (company_growth - avg_growth) * 0.5
        adjusted_multiple = weighted_multiple * growth_adjustment
        
        # Calculate value
        revenue = request.revenue or 1_000_000  # Default $1M if no revenue
        enterprise_value = revenue * adjusted_multiple
        
        # Apply DLOM - reduced if recent M&A activity in sector
        base_dlom = self.stage_parameters[request.stage]['dlom']
        if ma_transactions and len(ma_transactions) >= 3:
            # Active M&A market reduces DLOM
            dlom = base_dlom * 0.7  # 30% reduction in DLOM
        else:
            dlom = base_dlom
        
        fair_value = enterprise_value * (1 - dlom)
        
        # Determine confidence based on data quality
        if len(all_comparables) >= 5 and ma_transactions:
            confidence = 0.90  # High confidence with both public and M&A data
        elif len(all_comparables) >= 3:
            confidence = 0.75  # Good confidence
        else:
            confidence = 0.60  # Limited data
        
        return ValuationResult(
            method_used="Market Comparables (Enhanced with M&A)",
            fair_value=fair_value,
            dlom_discount=dlom,
            comparables=all_comparables,
            assumptions={
                'public_comparables': len([c for c in all_comparables if not hasattr(c, 'is_ma_transaction')]),
                'ma_transactions': len(ma_transactions) if ma_transactions else 0,
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
        
        # Adjust discount rate based on growth rate and stage
        base_discount_rate = self.stage_parameters[request.stage]['discount_rate']
        
        # For established high-growth companies (Series C+), use lower discount rates
        if request.stage in [Stage.SERIES_C, Stage.GROWTH, Stage.LATE]:
            if request.growth_rate and request.growth_rate > 1.0:
                # Proven hyper-growth at scale deserves lower discount
                discount_rate = 0.25  # 25% for proven execution
            elif request.growth_rate and request.growth_rate > 0.5:
                discount_rate = 0.22  # 22% for strong growth
            else:
                discount_rate = base_discount_rate
        else:
            # Earlier stage companies have higher risk
            if request.growth_rate and request.growth_rate > 1.0:
                discount_rate = min(base_discount_rate * 1.3, 0.30)  # Up to 30%
            elif request.growth_rate and request.growth_rate > 0.5:
                discount_rate = min(base_discount_rate * 1.15, 0.25)
            else:
                discount_rate = base_discount_rate
        
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
        Liquidation Waterfall Analysis with Base/Bull/Bear scenarios
        """
        logger.info("Calculating waterfall valuation with scenarios")
        
        # Build waterfall from liquidation preferences
        waterfall_tiers = self._build_liquidation_waterfall(request)
        
        # Base case exit value
        base_exit_value = request.last_round_valuation or 100_000_000
        base_exit_value *= 2  # Assume 2x growth for base case
        
        # Calculate scenarios: Bear (0.5x), Base (1x), Bull (2x)
        scenarios = {
            'bear': base_exit_value * 0.5,
            'base': base_exit_value,
            'bull': base_exit_value * 2.0
        }
        
        scenario_results = {}
        
        for scenario_name, exit_value in scenarios.items():
            # Distribute value through waterfall for each scenario
            remaining_value = exit_value
            common_value = 0
            tier_distributions = []
            
            for tier in waterfall_tiers:
                if remaining_value <= 0:
                    tier_distributions.append({
                        'tier': tier.tier,
                        'description': tier.description,
                        'amount_distributed': 0
                    })
                    continue
                    
                if remaining_value >= tier.amount:
                    tier_distributions.append({
                        'tier': tier.tier,
                        'description': tier.description,
                        'amount_distributed': tier.amount
                    })
                    remaining_value -= tier.amount
                else:
                    tier_distributions.append({
                        'tier': tier.tier,
                        'description': tier.description,
                        'amount_distributed': remaining_value
                    })
                    remaining_value = 0
            
            # Remaining value goes to common
            if remaining_value > 0:
                common_value = remaining_value
            
            scenario_results[scenario_name] = {
                'exit_value': exit_value,
                'common_value': common_value,
                'tier_distributions': tier_distributions,
                'total_to_preferred': exit_value - common_value,
                'common_percentage': (common_value / exit_value * 100) if exit_value > 0 else 0
            }
        
        # Identify breakpoints
        breakpoints = []
        
        # Breakpoint 1: Liquidation preferences fully covered
        total_liquidation_prefs = sum(tier.amount for tier in waterfall_tiers)
        if total_liquidation_prefs > 0:
            breakpoints.append({
                'value': total_liquidation_prefs,
                'description': 'All liquidation preferences covered',
                'impact': 'Common shareholders start receiving proceeds'
            })
        
        # Breakpoint 2: Common gets meaningful return (>$1M)
        common_threshold = total_liquidation_prefs + 1_000_000
        breakpoints.append({
            'value': common_threshold,
            'description': 'Common shareholders receive >$1M',
            'impact': 'Meaningful returns for founders/employees'
        })
        
        # Breakpoint 3: 2x return for preferred
        preferred_2x = total_liquidation_prefs * 2
        breakpoints.append({
            'value': preferred_2x,
            'description': 'Preferred shareholders achieve 2x return',
            'impact': 'Attractive returns for investors'
        })
        
        return ValuationResult(
            method_used="Liquidation Waterfall with Scenarios",
            fair_value=scenario_results['base']['common_value'],
            waterfall=waterfall_tiers,
            assumptions={
                'scenarios': scenario_results,
                'breakpoints': breakpoints,
                'total_liquidation_preferences': total_liquidation_prefs
            },
            confidence=0.75,
            explanation=f"Waterfall analysis with bear/base/bull scenarios. Base case common value: ${scenario_results['base']['common_value']:,.0f}"
        )
    
    def _generate_exit_scenarios(self, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate dynamic exit scenarios based on company stage and metrics"""
        base_value = request.last_round_valuation or 100_000_000
        
        # Stage-specific scenario generation with industry benchmarks
        if request.stage in [Stage.SEED, Stage.SERIES_A]:
            # Early stage: Higher variance, more scenarios
            scenarios = self._generate_early_stage_scenarios(base_value, request)
        elif request.stage in [Stage.SERIES_B, Stage.SERIES_C]:
            # Growth stage: Balanced scenarios
            scenarios = self._generate_growth_stage_scenarios(base_value, request)
        else:
            # Late stage: Lower variance, clearer paths
            scenarios = self._generate_late_stage_scenarios(base_value, request)
        
        # Adjust probabilities based on company metrics
        scenarios = self._adjust_scenario_probabilities(scenarios, request)
        
        # Ensure probabilities sum to 1.0
        total_prob = sum(s.probability for s in scenarios)
        for s in scenarios:
            s.probability = s.probability / total_prob
        
        return scenarios
    
    def _generate_early_stage_scenarios(self, base_value: float, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate scenarios for early stage companies (Seed/Series A)"""
        # Based on Carta and Cambridge Associates data for early stage exits
        scenarios = [
            # IPO scenarios (rare but high value)
            PWERMScenario(
                scenario="Blockbuster IPO (Uber/Airbnb trajectory)",
                probability=0.02,  # 2% - Carta: <2% of seed stage reach IPO
                exit_value=base_value * 50,
                time_to_exit=8.0,  # PitchBook: 8-10 years median
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Strong IPO (>$1B valuation)",
                probability=0.03,  # 3% - Additional IPO candidates
                exit_value=base_value * 20,
                time_to_exit=7.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Strategic acquisition scenarios
            PWERMScenario(
                scenario="Strategic Premium Acquisition (competitive bidding)",
                probability=0.08,  # 8% - Best outcomes
                exit_value=base_value * 15,
                time_to_exit=5.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Strategic Acquisition (strong fit)",
                probability=0.12,  # 12% - Good strategic fit
                exit_value=base_value * 8,
                time_to_exit=4.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Quick Strategic Exit (talent/tech acquisition)",
                probability=0.15,  # 15% - Common for seed stage
                exit_value=base_value * 4,
                time_to_exit=2.5,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Growth/PE scenarios
            PWERMScenario(
                scenario="Growth Equity Recap",
                probability=0.10,  # 10% - Secondary opportunity
                exit_value=base_value * 3,
                time_to_exit=3.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Modest exits
            PWERMScenario(
                scenario="Modest M&A Exit",
                probability=0.20,  # 20% - Break-even to small return
                exit_value=base_value * 1.5,
                time_to_exit=3.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Acquihire/Small Exit",
                probability=0.15,  # 15% - Team acquisition
                exit_value=base_value * 0.8,
                time_to_exit=2.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Negative scenarios
            PWERMScenario(
                scenario="Distressed Sale/Wind Down",
                probability=0.10,  # 10% - Fire sale
                exit_value=base_value * 0.3,
                time_to_exit=1.5,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Complete Write-off",
                probability=0.05,  # 5% - Total loss (Carta: 20-30% fail rate but not all are zeros)
                exit_value=0,
                time_to_exit=2.0,
                present_value=0,
                moic=0.0  # Total loss
            )
        ]
        
        return scenarios
    
    def _generate_growth_stage_scenarios(self, base_value: float, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate scenarios for growth stage companies (Series B/C)"""
        # More concentrated outcomes, higher success rates
        scenarios = [
            # IPO scenarios (more likely at this stage)
            PWERMScenario(
                scenario="Strong IPO (Unicorn status)",
                probability=0.10,  # 10% - Carta: Series B+ have better IPO odds
                exit_value=base_value * 10,
                time_to_exit=5.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Standard IPO/SPAC",
                probability=0.05,  # 5% - Alternative public paths
                exit_value=base_value * 5,
                time_to_exit=4.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Strategic acquisitions (primary exit path)
            PWERMScenario(
                scenario="Premium Strategic Acquisition",
                probability=0.20,  # 20% - Strong strategic value
                exit_value=base_value * 6,
                time_to_exit=3.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Strategic Acquisition (market consolidation)",
                probability=0.25,  # 25% - Most common good outcome
                exit_value=base_value * 3.5,
                time_to_exit=2.5,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # PE acquisitions
            PWERMScenario(
                scenario="PE Buyout (platform play)",
                probability=0.15,  # 15% - PE interest in proven models
                exit_value=base_value * 2.5,
                time_to_exit=2.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Modest outcomes
            PWERMScenario(
                scenario="Modest Exit (1-2x return)",
                probability=0.15,  # 15% - Break-even to small gain
                exit_value=base_value * 1.3,
                time_to_exit=2.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Negative scenarios (lower probability at this stage)
            PWERMScenario(
                scenario="Down Round/Recap",
                probability=0.07,  # 7% - Restructuring
                exit_value=base_value * 0.5,
                time_to_exit=1.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Distressed Sale",
                probability=0.03,  # 3% - Lower failure rate
                exit_value=base_value * 0.2,
                time_to_exit=1.0,
                present_value=0,
                moic=0.0  # Will be calculated
            )
        ]
        
        return scenarios
    
    def _generate_late_stage_scenarios(self, base_value: float, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate scenarios for late stage companies (Growth/Late)"""
        # Clearer paths to exit, lower variance
        scenarios = [
            # IPO scenarios (highest probability at this stage)
            PWERMScenario(
                scenario="Successful IPO",
                probability=0.25,  # 25% - Much higher for late stage
                exit_value=base_value * 3,
                time_to_exit=2.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="Direct Listing/SPAC",
                probability=0.10,  # 10% - Alternative public paths
                exit_value=base_value * 2.2,
                time_to_exit=1.5,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # M&A scenarios
            PWERMScenario(
                scenario="Strategic Premium Acquisition",
                probability=0.30,  # 30% - Primary alternative to IPO
                exit_value=base_value * 2.5,
                time_to_exit=1.5,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            PWERMScenario(
                scenario="PE Buyout",
                probability=0.20,  # 20% - Common for mature companies
                exit_value=base_value * 1.8,
                time_to_exit=1.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Continuation scenarios
            PWERMScenario(
                scenario="Secondary Sale/Continuation",
                probability=0.10,  # 10% - Liquidity without full exit
                exit_value=base_value * 1.3,
                time_to_exit=1.0,
                present_value=0,
                moic=0.0  # Will be calculated in PWERM calculation
            ),
            
            # Downside (minimal at this stage)
            PWERMScenario(
                scenario="Flat/Down Exit",
                probability=0.05,  # 5% - Rare but possible
                exit_value=base_value * 0.8,
                time_to_exit=1.0,
                present_value=0
            )
        ]
        
        return scenarios
    
    def _adjust_scenario_probabilities(self, scenarios: List[PWERMScenario], request: ValuationRequest) -> List[PWERMScenario]:
        """Adjust scenario probabilities based on company-specific metrics"""
        
        # Factors that affect probability distribution
        growth_adjustment = 1.0
        if request.growth_rate:
            if request.growth_rate > 100:  # High growth
                growth_adjustment = 1.2  # Increase positive scenario probabilities
            elif request.growth_rate < 20:  # Low growth
                growth_adjustment = 0.8  # Decrease positive scenario probabilities
        
        # Adjust probabilities based on growth
        for scenario in scenarios:
            if "IPO" in scenario.scenario or "Premium" in scenario.scenario:
                scenario.probability *= growth_adjustment
            elif "Distressed" in scenario.scenario or "Write-off" in scenario.scenario:
                scenario.probability *= (2.0 - growth_adjustment)  # Inverse adjustment
        
        return scenarios
    
    async def _find_recent_ma_transactions(self, request: ValuationRequest) -> List[ComparableCompany]:
        """
        Find recent M&A transactions in the same sector
        This would connect to M&A databases or scrape recent deals
        """
        logger.info(f"Finding recent M&A transactions for {request.industry or 'SaaS'}")
        
        # Recent notable M&A transactions (would be dynamically fetched)
        recent_transactions = {
            "hr_tech": [
                {"company": "Sana", "acquirer": "Workday", "date": "2024-01", "revenue": 50_000_000, 
                 "price": 1_450_000_000, "multiple": 29.0, "growth": 1.0},  # Sana → Workday
                {"company": "HiBob", "acquirer": "Private", "date": "2023-10", "revenue": 100_000_000,
                 "price": 2_450_000_000, "multiple": 24.5, "growth": 0.8},
            ],
            "ai_search": [
                {"company": "Neeva", "acquirer": "Snowflake", "date": "2023-05", "revenue": 10_000_000,
                 "price": 185_000_000, "multiple": 18.5, "growth": 2.0},
                {"company": "AlphaSense", "acquirer": "Private", "date": "2023-06", "revenue": 100_000_000,
                 "price": 2_500_000_000, "multiple": 25.0, "growth": 0.7},
            ],
            "dev_tools": [
                {"company": "Fig", "acquirer": "AWS", "date": "2023-08", "revenue": 5_000_000,
                 "price": 100_000_000, "multiple": 20.0, "growth": 3.0},
                {"company": "Gitpod", "acquirer": "Private", "date": "2023-09", "revenue": 20_000_000,
                 "price": 300_000_000, "multiple": 15.0, "growth": 1.5},
            ],
            "data_infra": [
                {"company": "Cribl", "acquirer": "Private", "date": "2024-02", "revenue": 100_000_000,
                 "price": 2_750_000_000, "multiple": 27.5, "growth": 1.2},
                {"company": "Airbyte", "acquirer": "Private", "date": "2023-12", "revenue": 30_000_000,
                 "price": 500_000_000, "multiple": 16.7, "growth": 2.5},
            ],
            "security": [
                {"company": "Vanta", "acquirer": "Private", "date": "2024-01", "revenue": 80_000_000,
                 "price": 2_450_000_000, "multiple": 30.6, "growth": 1.5},
                {"company": "Wiz", "acquirer": "Google (attempted)", "date": "2024-07", "revenue": 500_000_000,
                 "price": 23_000_000_000, "multiple": 46.0, "growth": 2.0},  # Failed but shows valuation
            ],
            "fintech": [
                {"company": "Ramp", "acquirer": "Private", "date": "2024-01", "revenue": 300_000_000,
                 "price": 7_650_000_000, "multiple": 25.5, "growth": 1.0},
                {"company": "Mercury", "acquirer": "Private", "date": "2023-12", "revenue": 100_000_000,
                 "price": 1_620_000_000, "multiple": 16.2, "growth": 1.5},
            ]
        }
        
        # Determine sector
        sector = "general"
        if request.industry:
            industry_lower = request.industry.lower()
            if any(term in industry_lower for term in ["hr", "human", "talent", "recruiting"]):
                sector = "hr_tech"
            elif any(term in industry_lower for term in ["search", "discovery", "knowledge"]):
                sector = "ai_search"
            elif any(term in industry_lower for term in ["dev", "developer", "code", "git"]):
                sector = "dev_tools"
            elif any(term in industry_lower for term in ["data", "analytics", "pipeline", "etl"]):
                sector = "data_infra"
            elif any(term in industry_lower for term in ["security", "compliance", "cyber"]):
                sector = "security"
            elif any(term in industry_lower for term in ["fintech", "payments", "banking"]):
                sector = "fintech"
        
        # Get relevant transactions
        relevant_deals = recent_transactions.get(sector, [])
        
        # Also add cross-sector mega deals for context
        mega_deals = [
            {"company": "Figma", "acquirer": "Adobe (blocked)", "date": "2022-09", "revenue": 400_000_000,
             "price": 20_000_000_000, "multiple": 50.0, "growth": 1.0},
            {"company": "Slack", "acquirer": "Salesforce", "date": "2021-07", "revenue": 900_000_000,
             "price": 27_700_000_000, "multiple": 30.8, "growth": 0.5},
            {"company": "GitHub", "acquirer": "Microsoft", "date": "2018-06", "revenue": 300_000_000,
             "price": 7_500_000_000, "multiple": 25.0, "growth": 0.6},
        ]
        
        # Convert to ComparableCompany format
        comparables = []
        for deal in relevant_deals[:5]:  # Top 5 most relevant
            comparables.append(ComparableCompany(
                name=f"{deal['company']} → {deal['acquirer']}",
                revenue_multiple=deal['multiple'],
                growth_rate=deal['growth'],
                similarity_score=0.9  # High similarity for same-sector deals
            ))
        
        # Add mega deals with lower weight
        for deal in mega_deals[:2]:  # Add 2 mega deals for context
            comparables.append(ComparableCompany(
                name=f"{deal['company']} → {deal['acquirer']}",
                revenue_multiple=deal['multiple'],
                growth_rate=deal['growth'],
                similarity_score=0.5  # Lower weight for cross-sector
            ))
        
        return comparables
    
    async def _find_comparable_companies(self, request: ValuationRequest) -> List[ComparableCompany]:
        """Find comparable companies based on business model"""
        # Use business model to determine appropriate comparables
        business_model = request.business_model or request.industry or 'saas'
        
        # Business model specific comparables
        model_comparables = {
            'ai_first': [
                ComparableCompany(name="OpenAI", revenue_multiple=25.0, growth_rate=4.0, similarity_score=0.9),
                ComparableCompany(name="Anthropic", revenue_multiple=20.0, growth_rate=3.5, similarity_score=0.85),
                ComparableCompany(name="Cohere", revenue_multiple=18.0, growth_rate=3.0, similarity_score=0.8),
            ],
            'ai_saas': [
                ComparableCompany(name="Jasper", revenue_multiple=15.0, growth_rate=2.5, similarity_score=0.9),
                ComparableCompany(name="Copy.ai", revenue_multiple=12.0, growth_rate=2.0, similarity_score=0.85),
                ComparableCompany(name="Notion AI", revenue_multiple=14.0, growth_rate=2.3, similarity_score=0.8),
            ],
            'rollup': [
                ComparableCompany(name="Thrasio", revenue_multiple=4.0, growth_rate=1.2, similarity_score=0.9),
                ComparableCompany(name="Razor Group", revenue_multiple=3.5, growth_rate=1.1, similarity_score=0.85),
                ComparableCompany(name="Perch", revenue_multiple=4.5, growth_rate=1.3, similarity_score=0.8),
            ],
            'services': [
                ComparableCompany(name="Accenture", revenue_multiple=2.0, growth_rate=1.1, similarity_score=0.9),
                ComparableCompany(name="EPAM", revenue_multiple=2.5, growth_rate=1.2, similarity_score=0.85),
                ComparableCompany(name="Cognizant", revenue_multiple=1.8, growth_rate=1.0, similarity_score=0.8),
            ],
            'marketplace': [
                ComparableCompany(name="Airbnb", revenue_multiple=6.0, growth_rate=1.5, similarity_score=0.9),
                ComparableCompany(name="DoorDash", revenue_multiple=5.0, growth_rate=1.4, similarity_score=0.85),
                ComparableCompany(name="Uber", revenue_multiple=5.5, growth_rate=1.3, similarity_score=0.8),
            ],
            'saas': [
                ComparableCompany(name="Salesforce", revenue_multiple=8.5, growth_rate=1.5, similarity_score=0.9),
                ComparableCompany(name="ServiceNow", revenue_multiple=10.0, growth_rate=1.8, similarity_score=0.85),
                ComparableCompany(name="Workday", revenue_multiple=9.0, growth_rate=1.6, similarity_score=0.8),
            ],
        }
        
        # Default to SaaS comparables if model not found
        comparables = model_comparables.get(business_model, model_comparables['saas'])
        
        return comparables
    
    async def _calculate_industry_multiple_valuation(self, request: ValuationRequest) -> ValuationResult:
        """Fallback to industry average multiples"""
        # Use business_model or industry from request, default to saas
        industry = request.business_model or request.industry or 'saas'
        
        # Map business models to industry categories
        model_to_industry = {
            'ai_first': 'saas',  # Use SaaS with growth premium
            'ai_saas': 'saas',
            'rollup': 'marketplace',  # Lower multiples for roll-ups
            'services': 'consumer',  # People-heavy, lower multiples
            'ai_enhanced_rollup': 'fintech',  # Hybrid model
        }
        
        # Convert business model to industry if needed
        if industry not in self.industry_multiples:
            industry = model_to_industry.get(industry, 'saas')
        
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
        """Build 5-year cash flow projections with realistic growth decay"""
        base_revenue = request.revenue or 10_000_000
        initial_growth = request.growth_rate or 0.3  # Convert to percentage form
        
        projections = []
        current_revenue = base_revenue
        previous_growth = initial_growth  # Initialize for decay calculation
        
        for year in range(1, 6):  # 5-year projection
            # Apply growth decay curve - high growth companies see gradual deceleration
            # Growth decays each year but still compounds
            if initial_growth > 1.0:  # Hyper-growth (>100%)
                # For 300% growth: 300% → 210% → 147% → 103% → 72%
                decay_rate = 0.7  # 30% decay per year (less aggressive)
            elif initial_growth > 0.5:  # High growth (50-100%)
                # 70% → 56% → 45% → 36% → 29%
                decay_rate = 0.8  # 20% decay per year
            else:  # Normal growth (<50%)
                # 30% → 27% → 24% → 21% → 19%
                decay_rate = 0.9  # 10% decay per year
            
            # Calculate this year's growth rate (decaying from previous year)
            if year == 1:
                year_growth = initial_growth
            else:
                # Each year's growth is a decay from the previous year's growth
                year_growth = previous_growth * decay_rate
            
            year_growth = max(year_growth, 0.1)  # Floor at 10% growth
            previous_growth = year_growth  # Store for next iteration
            
            # Revenue compounds with the decaying growth rate
            current_revenue = current_revenue * (1 + year_growth)
            revenue = current_revenue
            
            # Log the growth rate being used
            logger.debug(f"DCF Year {year}: Growth {year_growth:.1%}, Revenue ${revenue:,.0f}")
            
            # Assume improving margins over time
            gross_margin = min(0.8, 0.6 + (year * 0.04))
            operating_margin = min(0.25, -0.1 + (year * 0.07))  # Start negative, improve over time
            
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
    
    async def _calculate_recent_transaction(self, request: ValuationRequest) -> ValuationResult:
        """
        IPEV Recent Transaction Method
        Uses the most recent funding round as the primary indicator of fair value
        Adjusts for time elapsed and market conditions
        """
        logger.info("Calculating valuation using Recent Transaction Method (IPEV)")
        
        if not request.last_round_valuation or not request.last_round_date:
            raise ValueError("Recent Transaction Method requires last round valuation and date")
        
        # Calculate months since last round
        try:
            last_round_date = datetime.strptime(request.last_round_date, "%Y-%m-%d")
            months_elapsed = (datetime.now() - last_round_date).days / 30.44
        except:
            months_elapsed = 6  # Default to 6 months if date parsing fails
        
        # Start with last round valuation
        base_value = request.last_round_valuation
        
        # Apply time-based adjustments per IPEV guidelines
        adjustment_factors = []
        
        # 1. Time adjustment (value typically increases over time)
        if months_elapsed < 3:
            time_adjustment = 1.0  # Very recent, no adjustment
            adjustment_factors.append(("Time: <3 months", 1.0))
        elif months_elapsed < 6:
            time_adjustment = 1.05  # Slight appreciation
            adjustment_factors.append(("Time: 3-6 months", 1.05))
        elif months_elapsed < 12:
            time_adjustment = 1.10  # Moderate appreciation
            adjustment_factors.append(("Time: 6-12 months", 1.10))
        elif months_elapsed < 18:
            time_adjustment = 1.15  # More appreciation
            adjustment_factors.append(("Time: 12-18 months", 1.15))
        else:
            # Over 18 months - less reliable, consider using other methods
            time_adjustment = 1.20
            adjustment_factors.append(("Time: >18 months (less reliable)", 1.20))
        
        # 2. Performance adjustment based on growth
        if request.revenue and request.growth_rate:
            if request.growth_rate > 2.0:  # >200% YoY
                performance_adjustment = 1.15
                adjustment_factors.append(("Performance: Exceptional growth", 1.15))
            elif request.growth_rate > 1.0:  # >100% YoY
                performance_adjustment = 1.10
                adjustment_factors.append(("Performance: Strong growth", 1.10))
            elif request.growth_rate > 0.5:  # >50% YoY
                performance_adjustment = 1.05
                adjustment_factors.append(("Performance: Good growth", 1.05))
            elif request.growth_rate > 0:
                performance_adjustment = 1.0
                adjustment_factors.append(("Performance: Moderate growth", 1.0))
            else:
                performance_adjustment = 0.90  # Declining/flat
                adjustment_factors.append(("Performance: Flat/declining", 0.90))
        else:
            performance_adjustment = 1.0
        
        # 3. Market conditions adjustment (simplified - in practice would use indices)
        # This would ideally reference market indices like PitchBook/Cambridge
        market_adjustment = 0.95  # Current market: slightly down from 2021-22 peaks
        adjustment_factors.append(("Market conditions: Current environment", 0.95))
        
        # 4. Stage progression adjustment
        stage_progression = 1.0
        if request.stage and request.last_round_date:
            # If company has likely progressed to next stage
            if months_elapsed > 12:
                stage_progression = 1.10
                adjustment_factors.append(("Stage progression: Likely advanced", 1.10))
        
        # Calculate adjusted fair value
        total_adjustment = time_adjustment * performance_adjustment * market_adjustment * stage_progression
        fair_value = base_value * total_adjustment
        
        # Apply DLOM (Discount for Lack of Marketability) for private companies
        dlom = 0.15  # Standard 15% DLOM for private companies
        fair_value_after_dlom = fair_value * (1 - dlom)
        
        # Determine confidence based on recency
        if months_elapsed < 6:
            confidence = 0.95  # Very high confidence
        elif months_elapsed < 12:
            confidence = 0.85  # High confidence
        elif months_elapsed < 18:
            confidence = 0.70  # Moderate confidence
        else:
            confidence = 0.50  # Low confidence - consider other methods
        
        return ValuationResult(
            method_used="Recent Transaction (IPEV)",
            fair_value=fair_value_after_dlom,
            common_stock_value=fair_value_after_dlom * 0.8,  # Common typically worth 80% of preferred
            preferred_value=fair_value_after_dlom,
            dlom_discount=dlom,
            assumptions={
                'last_round_valuation': base_value,
                'months_since_round': months_elapsed,
                'total_adjustment': total_adjustment,
                'adjustment_factors': adjustment_factors,
                'dlom_applied': dlom
            },
            confidence=confidence,
            explanation=f"Based on ${base_value/1e6:.1f}M round {months_elapsed:.1f} months ago, "
                       f"adjusted {(total_adjustment-1)*100:+.1f}% for time/performance/market, "
                       f"with {dlom*100:.0f}% DLOM applied"
        )
    
    async def _calculate_cost_method(self, request: ValuationRequest) -> ValuationResult:
        """
        IPEV Cost Method
        Used for very recent investments or when no better info available
        Adjusts cost for any impairments or enhancements
        """
        logger.info("Calculating valuation using Cost Method (IPEV)")
        
        # Use last round amount as the cost basis
        if request.last_round_valuation:
            cost_basis = request.last_round_valuation
        elif request.total_raised:
            # Estimate based on total raised
            cost_basis = request.total_raised * 1.5  # Rough estimate of post-money
        else:
            raise ValueError("Cost Method requires investment cost information")
        
        # Check if investment is recent (within 12 months)
        months_elapsed = 12  # Default
        if request.last_round_date:
            try:
                last_round_date = datetime.strptime(request.last_round_date, "%Y-%m-%d")
                months_elapsed = (datetime.now() - last_round_date).days / 30.44
            except:
                pass
        
        # Adjustments to cost
        adjustments = []
        total_adjustment = 1.0
        
        # 1. Impairment indicators
        if request.revenue and request.growth_rate:
            if request.growth_rate < 0:
                # Negative growth - potential impairment
                impairment = 0.80  # 20% impairment
                adjustments.append(("Impairment: Negative growth", 0.80))
                total_adjustment *= impairment
            elif request.growth_rate < 0.2:
                # Very slow growth
                impairment = 0.90
                adjustments.append(("Impairment: Slow growth", 0.90))
                total_adjustment *= impairment
        
        # 2. Enhancement indicators
        if months_elapsed < 12:
            # Recent investment, minimal adjustment
            if request.growth_rate and request.growth_rate > 1.0:
                enhancement = 1.10
                adjustments.append(("Enhancement: Strong performance", 1.10))
                total_adjustment *= enhancement
        
        # Apply adjustments
        fair_value = cost_basis * total_adjustment
        
        # Confidence depends on recency
        if months_elapsed < 3:
            confidence = 0.90
            explanation = "Very recent investment - cost is good approximation"
        elif months_elapsed < 6:
            confidence = 0.80
            explanation = "Recent investment - cost with minor adjustments"
        elif months_elapsed < 12:
            confidence = 0.65
            explanation = "Investment within past year - cost method acceptable"
        else:
            confidence = 0.40
            explanation = "Old investment - consider using other valuation methods"
        
        return ValuationResult(
            method_used="Cost Method (IPEV)",
            fair_value=fair_value,
            assumptions={
                'cost_basis': cost_basis,
                'months_since_investment': months_elapsed,
                'adjustments': adjustments,
                'total_adjustment': total_adjustment
            },
            confidence=confidence,
            explanation=explanation
        )
    
    async def _calculate_milestone(self, request: ValuationRequest) -> ValuationResult:
        """
        IPEV Milestone/Calibration Method
        Values company based on achievement of key milestones
        Particularly relevant for biotech, deep tech, hardware
        """
        logger.info("Calculating valuation using Milestone Method (IPEV)")
        
        # Start with last known valuation or cost basis
        if request.last_round_valuation:
            base_value = request.last_round_valuation
        elif request.total_raised:
            base_value = request.total_raised * 2  # Rough estimate
        else:
            base_value = 10_000_000  # Default $10M for early stage
        
        # Define milestone multipliers by industry
        milestone_adjustments = []
        total_multiplier = 1.0
        
        # Check for revenue milestones (applicable to all)
        if request.revenue:
            if request.revenue > 100_000_000:
                milestone_adjustments.append(("Revenue >$100M", 2.0))
                total_multiplier *= 2.0
            elif request.revenue > 50_000_000:
                milestone_adjustments.append(("Revenue >$50M", 1.75))
                total_multiplier *= 1.75
            elif request.revenue > 10_000_000:
                milestone_adjustments.append(("Revenue >$10M", 1.5))
                total_multiplier *= 1.5
            elif request.revenue > 1_000_000:
                milestone_adjustments.append(("Revenue >$1M", 1.25))
                total_multiplier *= 1.25
            elif request.revenue > 100_000:
                milestone_adjustments.append(("Initial revenue", 1.1))
                total_multiplier *= 1.1
        
        # Industry-specific milestones
        if request.industry:
            industry_lower = request.industry.lower()
            
            if 'biotech' in industry_lower or 'pharma' in industry_lower:
                # Biotech milestones
                if request.stage == Stage.GROWTH:
                    milestone_adjustments.append(("Phase III trials", 3.0))
                    total_multiplier *= 3.0
                elif request.stage == Stage.SERIES_C:
                    milestone_adjustments.append(("Phase II trials", 2.0))
                    total_multiplier *= 2.0
                elif request.stage == Stage.SERIES_B:
                    milestone_adjustments.append(("Phase I trials", 1.5))
                    total_multiplier *= 1.5
                elif request.stage == Stage.SERIES_A:
                    milestone_adjustments.append(("Pre-clinical complete", 1.25))
                    total_multiplier *= 1.25
                    
            elif 'hardware' in industry_lower or 'robotics' in industry_lower:
                # Hardware milestones
                if request.revenue and request.revenue > 0:
                    milestone_adjustments.append(("Production started", 1.5))
                    total_multiplier *= 1.5
                elif request.stage in [Stage.SERIES_B, Stage.SERIES_C]:
                    milestone_adjustments.append(("Prototype validated", 1.3))
                    total_multiplier *= 1.3
                    
            elif 'ai' in industry_lower or 'ml' in industry_lower:
                # AI/ML milestones
                if request.revenue and request.revenue > 10_000_000:
                    milestone_adjustments.append(("Product-market fit", 1.75))
                    total_multiplier *= 1.75
                elif request.revenue and request.revenue > 1_000_000:
                    milestone_adjustments.append(("Initial customers", 1.4))
                    total_multiplier *= 1.4
        
        # Stage progression milestone
        if request.stage:
            if request.stage == Stage.SERIES_C:
                milestone_adjustments.append(("Series C stage", 1.2))
                total_multiplier *= 1.2
            elif request.stage == Stage.GROWTH:
                milestone_adjustments.append(("Growth stage", 1.5))
                total_multiplier *= 1.5
        
        # Calculate fair value
        fair_value = base_value * total_multiplier
        
        # Apply risk adjustment based on milestone achievement certainty
        risk_adjustment = 0.85  # 15% discount for execution risk
        fair_value = fair_value * risk_adjustment
        
        # Confidence based on milestone clarity
        if len(milestone_adjustments) >= 3:
            confidence = 0.75
            explanation = f"Multiple milestones achieved: {len(milestone_adjustments)} key markers"
        elif len(milestone_adjustments) >= 1:
            confidence = 0.65
            explanation = f"Some milestones achieved: {len(milestone_adjustments)} markers"
        else:
            confidence = 0.50
            explanation = "Limited milestone data - consider other valuation methods"
        
        return ValuationResult(
            method_used="Milestone Method (IPEV)",
            fair_value=fair_value,
            assumptions={
                'base_value': base_value,
                'milestones_achieved': milestone_adjustments,
                'total_multiplier': total_multiplier,
                'risk_adjustment': risk_adjustment,
                'industry': request.industry or 'General'
            },
            confidence=confidence,
            explanation=explanation
        )

# Global service instance
valuation_engine_service = ValuationEngineService()