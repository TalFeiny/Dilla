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
import yfinance as yf
import requests
import time

from app.core.database import supabase_service
from app.services.pwerm_comprehensive import ComprehensivePWERM, ComprehensivePWERMScenario
from app.utils.numpy_converter import convert_numpy_to_native

logger = logging.getLogger(__name__)

class Stage(str, Enum):
    PRE_SEED = "pre_seed"
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
    DCF = "dcf"
    OPM = "opm"
    WATERFALL = "waterfall"
    RECENT_TRANSACTION = "recent_transaction"
    COST_METHOD = "cost_method"
    MILESTONE = "milestone"

@dataclass(frozen=True, eq=True)
class ValuationRequest:
    """Valuation request parameters"""
    company_name: str
    stage: Stage
    revenue: Optional[float] = None
    growth_rate: Optional[float] = None
    last_round_valuation: Optional[float] = None
    inferred_valuation: Optional[float] = None  # Inferred valuation from IntelligentGapFiller
    last_round_date: Optional[str] = None
    total_raised: Optional[float] = None
    preferred_shares_outstanding: Optional[int] = None
    common_shares_outstanding: Optional[int] = None
    liquidation_preferences: Optional[tuple] = None  # Changed to tuple for hashability
    method: ValuationMethod = ValuationMethod.AUTO
    business_model: Optional[str] = None  # CRITICAL: For correct multiples
    industry: Optional[str] = None  # Fallback if business_model not provided
    category: Optional[str] = None  # For rollup, SaaS, AI detection
    ai_component_percentage: Optional[float] = None  # Percentage of AI in the business

@dataclass
class PWERMScenario:
    """PWERM scenario parameters with qualitative descriptors"""
    scenario: str
    probability: float
    exit_value: float
    time_to_exit: float
    funding_path: str = ""  # e.g., "Pre-seed→seed→A→B→C"
    exit_type: str = ""  # e.g., "Megacap Buyout", "NYSE IPO", "Strategic Acquisition"
    # New fields for cap table evolution tracking
    cap_table_evolution: List[Dict] = field(default_factory=list)
    final_ownership: float = 0.0  # Our final ownership after all dilution
    final_liq_pref: float = 0.0  # Total liquidation preference at exit
    breakpoints: Dict[str, float] = field(default_factory=dict)  # Key breakpoint values
    return_curve: Dict[str, Any] = field(default_factory=dict)  # Return at different exit values
    present_value: float = field(init=False, default=0.0)
    moic: float = 0.0  # Calculated later by valuation engine logic

    def __post_init__(self):
        # Normalize legacy kwargs that may provide moic; engine always recalculates it.
        self.moic = 0.0

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
            Stage.PRE_SEED: {
                'discount_rate': 0.6,  # 60% for very high risk
                'dlom': 0.5,  # 50% discount for lack of marketability
                'preferred_methods': ['pwerm']
            },
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
        
        # Initialize comprehensive PWERM system
        self.comprehensive_pwerm = ComprehensivePWERM()
    
    def _sanitize_valuation_result(self, result: ValuationResult) -> ValuationResult:
        """
        Sanitize ValuationResult by converting all numpy types to native Python types.
        This prevents JSON serialization errors.
        """
        # Convert scenarios (the main source of numpy types)
        sanitized_scenarios = []
        for scenario in result.scenarios:
            # Create new PWERMScenario with converted values
            from copy import copy
            sanitized_scenario = copy(scenario)
            sanitized_scenario.probability = convert_numpy_to_native(scenario.probability)
            sanitized_scenario.exit_value = convert_numpy_to_native(scenario.exit_value)
            sanitized_scenario.time_to_exit = convert_numpy_to_native(scenario.time_to_exit)
            sanitized_scenario.present_value = convert_numpy_to_native(getattr(scenario, 'present_value', 0))
            sanitized_scenario.moic = convert_numpy_to_native(getattr(scenario, 'moic', 0))
            
            # Convert cap_table_evolution if it exists
            if hasattr(scenario, 'cap_table_evolution'):
                sanitized_scenario.cap_table_evolution = convert_numpy_to_native(scenario.cap_table_evolution)
            
            # Convert breakpoints if they exist
            if hasattr(scenario, 'breakpoints'):
                sanitized_scenario.breakpoints = convert_numpy_to_native(scenario.breakpoints)
            
            # Convert return_curve if it exists
            if hasattr(scenario, 'return_curve'):
                sanitized_scenario.return_curve = convert_numpy_to_native(scenario.return_curve)
            
            sanitized_scenarios.append(sanitized_scenario)
        
        # Convert assumptions dict
        sanitized_assumptions = convert_numpy_to_native(result.assumptions) if result.assumptions else {}
        
        # Create sanitized result
        return ValuationResult(
            method_used=result.method_used,
            fair_value=convert_numpy_to_native(result.fair_value),
            common_stock_value=convert_numpy_to_native(result.common_stock_value),
            preferred_value=convert_numpy_to_native(result.preferred_value),
            dlom_discount=convert_numpy_to_native(result.dlom_discount),
            assumptions=sanitized_assumptions,
            scenarios=sanitized_scenarios,
            comparables=convert_numpy_to_native(result.comparables) if result.comparables else [],
            waterfall=convert_numpy_to_native(result.waterfall) if result.waterfall else [],
            confidence=convert_numpy_to_native(result.confidence),
            explanation=result.explanation
        )
    
    def _convert_request_to_company_data(self, request: ValuationRequest) -> Dict[str, Any]:
        """
        Convert ValuationRequest to company_data format expected by ComprehensivePWERM
        """
        # Map stage to string format expected by ComprehensivePWERM
        stage_mapping = {
            Stage.PRE_SEED: "pre_seed",
            Stage.SEED: "seed", 
            Stage.SERIES_A: "series_a",
            Stage.SERIES_B: "series_b",
            Stage.SERIES_C: "series_c",
            Stage.GROWTH: "growth",
            Stage.LATE: "late"
        }
        
        # Create funding history from total_raised
        funding_rounds = []
        if request.total_raised and request.total_raised > 0:
            # Estimate funding rounds based on stage and total raised
            if request.stage == Stage.PRE_SEED:
                funding_rounds = [{"round": "pre_seed", "amount": request.total_raised}]
            elif request.stage == Stage.SEED:
                funding_rounds = [
                    {"round": "pre_seed", "amount": request.total_raised * 0.3},
                    {"round": "seed", "amount": request.total_raised * 0.7}
                ]
            elif request.stage == Stage.SERIES_A:
                funding_rounds = [
                    {"round": "pre_seed", "amount": request.total_raised * 0.1},
                    {"round": "seed", "amount": request.total_raised * 0.2},
                    {"round": "series_a", "amount": request.total_raised * 0.7}
                ]
            # Add more stages as needed
        
        return {
            "company": request.company_name,
            "stage": stage_mapping.get(request.stage, "seed"),
            "revenue": request.revenue or 0,
            "growth_rate": request.growth_rate or 0,
            "burn_rate": 0,  # Not available in ValuationRequest
            "runway_months": 0,  # Not available in ValuationRequest
            "funding_rounds": funding_rounds,
            "total_raised": request.total_raised or 0,
            "last_round_valuation": request.last_round_valuation or 0,
            "valuation": request.last_round_valuation or 0,
            "inferred_valuation": getattr(request, 'inferred_valuation', request.last_round_valuation or 0)
        }
    
    def _convert_comprehensive_to_pwerm_scenarios(
        self, 
        comprehensive_scenarios: List[ComprehensivePWERMScenario]
    ) -> List[PWERMScenario]:
        """
        Convert ComprehensivePWERMScenario objects to PWERMScenario objects
        """
        pwerm_scenarios = []
        
        for comp_scenario in comprehensive_scenarios:
            pwerm_scenario = PWERMScenario(
                scenario=comp_scenario.scenario_type,
                probability=comp_scenario.probability,
                exit_value=comp_scenario.exit_value,
                time_to_exit=comp_scenario.time_to_exit,
                funding_path=comp_scenario.funding_path,
                exit_type=comp_scenario.scenario_type
            )
            # Set present_value after initialization since it's a calculated field
            pwerm_scenario.present_value = comp_scenario.present_value
            pwerm_scenarios.append(pwerm_scenario)
        
        return pwerm_scenarios
    
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
        # Convert request to dict for funding path calculation
        company_data = {
            'name': request.company_name,
            'stage': request.stage.value if request.stage else 'SERIES_A',
            'revenue': request.revenue,
            'growth_rate': request.growth_rate,
            'last_round_valuation': request.last_round_valuation,
            'total_raised': request.total_raised
        }
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
        """Calculate ownership evolution through different funding paths with actual dates"""
        
        from datetime import datetime, timedelta
        
        current_valuation = company_data.get("valuation", 100_000_000)
        current_stage = company_data.get("stage", "Series A")
        
        # Get company's last funding date from actual data
        last_funding_date = company_data.get("last_funding_date")
        if last_funding_date:
            if isinstance(last_funding_date, str):
                try:
                    # Try to parse various date formats
                    from dateutil import parser
                    last_funding_date = parser.parse(last_funding_date)
                except:
                    last_funding_date = datetime.now() - timedelta(days=180)  # Assume 6 months ago if can't parse
        else:
            # Estimate based on stage if no date available
            stage_to_months_ago = {
                "Seed": 6,
                "Series A": 9,
                "Series B": 12,
                "Series C": 15,
                "Series D": 18
            }
            months_ago = stage_to_months_ago.get(current_stage, 6)
            last_funding_date = datetime.now() - timedelta(days=months_ago * 30)
        
        # Define typical funding paths with actual dates
        paths = {
            "conservative": {
                "description": "Slow, steady growth with minimal dilution",
                "rounds": [
                    {"name": "Series B", "raise": 30_000_000, "valuation_step_up": 2.5, 
                     "date": last_funding_date + timedelta(days=548), "year": 1.5},  # ~18 months
                    {"name": "Series C", "raise": 50_000_000, "valuation_step_up": 2.0, 
                     "date": last_funding_date + timedelta(days=1095), "year": 3.0},  # ~3 years
                    {"name": "Exit", "date": last_funding_date + timedelta(days=int(time_to_exit*365)), 
                     "year": time_to_exit}
                ]
            },
            "aggressive": {
                "description": "Rapid scaling with heavy dilution",
                "rounds": [
                    {"name": "Series B", "raise": 50_000_000, "valuation_step_up": 2.0, 
                     "date": last_funding_date + timedelta(days=365), "year": 1.0},  # 12 months
                    {"name": "Series C", "raise": 100_000_000, "valuation_step_up": 1.8, 
                     "date": last_funding_date + timedelta(days=730), "year": 2.0},  # 24 months
                    {"name": "Series D", "raise": 150_000_000, "valuation_step_up": 1.5, 
                     "date": last_funding_date + timedelta(days=1278), "year": 3.5},  # 42 months
                    {"name": "Exit", "date": last_funding_date + timedelta(days=int(time_to_exit*365)), 
                     "year": time_to_exit}
                ]
            },
            "bootstrapped": {
                "description": "Minimal external funding, founder-friendly",
                "rounds": [
                    {"name": "Series B", "raise": 20_000_000, "valuation_step_up": 3.0, 
                     "date": last_funding_date + timedelta(days=730), "year": 2.0},  # 24 months
                    {"name": "Exit", "date": last_funding_date + timedelta(days=int(time_to_exit*365)), 
                     "year": time_to_exit}
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
                    "date": round_data.get("date", last_funding_date + timedelta(days=int(round_data["year"]*365))),
                    "date_str": round_data.get("date", last_funding_date + timedelta(days=int(round_data["year"]*365))).strftime("%b %Y"),
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

    def _company_data_to_request(
        self,
        company_data: Dict[str, Any],
        method: str = "auto",
        comparables: Optional[List[Dict[str, Any]]] = None,
        assumptions: Optional[Dict[str, Any]] = None,
    ) -> ValuationRequest:
        """Build ValuationRequest from company_data dict (thin API / value_company adapter)."""
        stage_str = (company_data.get("stage") or company_data.get("investment_stage") or "seed")
        if isinstance(stage_str, Stage):
            stage = stage_str
        else:
            stage_map = {
                "pre_seed": Stage.PRE_SEED,
                "seed": Stage.SEED,
                "series_a": Stage.SERIES_A,
                "series_b": Stage.SERIES_B,
                "series_c": Stage.SERIES_C,
                "growth": Stage.GROWTH,
                "late": Stage.LATE,
                "public": Stage.PUBLIC,
            }
            stage = stage_map.get(str(stage_str).lower().replace("-", "_"), Stage.SEED)

        method_str = (method or "auto").lower()
        method_map = {
            "auto": ValuationMethod.AUTO,
            "pwerm": ValuationMethod.PWERM,
            "dcf": ValuationMethod.DCF,
            "opm": ValuationMethod.OPM,
            "waterfall": ValuationMethod.WATERFALL,
            "recent_transaction": ValuationMethod.RECENT_TRANSACTION,
            "cost_method": ValuationMethod.COST_METHOD,
            "milestone": ValuationMethod.MILESTONE,
            "multiples": ValuationMethod.AUTO,
        }
        method_enum = method_map.get(method_str, ValuationMethod.AUTO)

        def _num(v: Any) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        name = company_data.get("name") or company_data.get("company") or "Unknown"
        return ValuationRequest(
            company_name=name,
            stage=stage,
            revenue=_num(company_data.get("revenue") or company_data.get("arr") or company_data.get("current_arr_usd")),
            growth_rate=_num(company_data.get("growth_rate") or company_data.get("revenue_growth_pct")),
            last_round_valuation=_num(company_data.get("last_round_valuation") or company_data.get("current_valuation_usd") or company_data.get("valuation")),
            inferred_valuation=_num(company_data.get("inferred_valuation")),
            last_round_date=company_data.get("last_round_date") or company_data.get("last_valuation_date"),
            total_raised=_num(company_data.get("total_raised") or company_data.get("total_invested_usd")),
            preferred_shares_outstanding=company_data.get("preferred_shares_outstanding"),
            common_shares_outstanding=company_data.get("common_shares_outstanding"),
            liquidation_preferences=tuple(company_data["liquidation_preferences"]) if isinstance(company_data.get("liquidation_preferences"), (list, tuple)) else None,
            method=method_enum,
            business_model=company_data.get("business_model"),
            industry=company_data.get("industry") or company_data.get("sector"),
            category=company_data.get("category"),
            ai_component_percentage=_num(company_data.get("ai_component_percentage")),
        )

    async def value_company(
        self,
        company_data: Dict[str, Any],
        method: str = "auto",
        comparables: Optional[List[Dict[str, Any]]] = None,
        assumptions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Adapter for thin API: build ValuationRequest from company_data dict, call
        calculate_valuation, return a serializable dict (fair_value, method_used, etc.).
        """
        request = self._company_data_to_request(company_data, method, comparables or [], assumptions or {})
        result = await self.calculate_valuation(request)
        # Serialize ValuationResult to dict for JSON response
        return {
            "fair_value": getattr(result, "fair_value", 0),
            "value": getattr(result, "fair_value", 0),
            "method_used": getattr(result, "method_used", method),
            "explanation": getattr(result, "explanation", ""),
            "confidence": getattr(result, "confidence", 0.5),
            "common_stock_value": getattr(result, "common_stock_value", None),
            "preferred_value": getattr(result, "preferred_value", None),
            "assumptions": getattr(result, "assumptions", {}),
            "scenarios": [
                {
                    "scenario": getattr(s, "scenario", ""),
                    "probability": getattr(s, "probability", 0),
                    "exit_value": getattr(s, "exit_value", 0),
                    "present_value": getattr(s, "present_value", 0),
                    "moic": getattr(s, "moic", 0),
                }
                for s in (getattr(result, "scenarios", None) or [])
            ],
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
            if method == ValuationMethod.RECENT_TRANSACTION:
                return await self._calculate_recent_transaction(request)
            elif method == ValuationMethod.COST_METHOD:
                return await self._calculate_cost_method(request)
            elif method == ValuationMethod.MILESTONE:
                return await self._calculate_milestone(request)
            elif method == ValuationMethod.PWERM:
                return await self._calculate_pwerm(request)
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
            result = ValuationResult(
                method_used="error",
                fair_value=0,
                explanation=f"Valuation failed: {str(e)}",
                confidence=0
            )
            return self._sanitize_valuation_result(result)
    
    def _select_method(self, request: ValuationRequest) -> ValuationMethod:
        """Select appropriate valuation method based on company stage"""
        stage = request.stage
        revenue = request.revenue or 0
        
        # Early stage (Pre-Seed, Seed, Series A) - use PWERM
        if stage in [Stage.PRE_SEED, Stage.SEED, Stage.SERIES_A]:
            return ValuationMethod.PWERM
        
        # Growth stage (Series B/C) - use PWERM
        if stage in [Stage.SERIES_B, Stage.SERIES_C]:
            return ValuationMethod.PWERM
        
        # Late stage with significant revenue - use DCF
        if stage in [Stage.GROWTH, Stage.LATE] and revenue > 50_000_000:
            return ValuationMethod.DCF
        
        # Public companies - use OPM
        if stage == Stage.PUBLIC:
            return ValuationMethod.OPM
        
        # Default to PWERM for uncertainty
        return ValuationMethod.PWERM
    
    def annotate_scenarios_with_returns(
        self,
        scenarios: List[PWERMScenario],
        request: ValuationRequest,
        *,
        discount_rate: Optional[float] = None,
    ) -> List[PWERMScenario]:
        """Populate present value and MOIC for generated scenarios."""
        if discount_rate is None:
            discount_rate = self.stage_parameters[request.stage]['discount_rate']

        investment = 10_000_000  # Standard check size assumption
        # Check explicitly for None (not just falsy) since 0 might be a valid value
        base_valuation = None
        if request.last_round_valuation is not None and request.last_round_valuation > 0:
            base_valuation = request.last_round_valuation
        elif request.inferred_valuation is not None and request.inferred_valuation > 0:
            base_valuation = request.inferred_valuation
        elif request.total_raised and request.total_raised > 0:
            base_valuation = request.total_raised * 3
        else:
            base_valuation = 100_000_000  # Default $100M if all else fails
        
        if base_valuation <= 0 or base_valuation is None:
            base_valuation = 100_000_000
        ownership_pct = investment / base_valuation

        for scenario in scenarios:
            pv_factor = 1 / ((1 + discount_rate) ** scenario.time_to_exit)
            scenario.present_value = scenario.exit_value * pv_factor
            scenario.moic = (scenario.exit_value * ownership_pct) / investment
        return scenarios

    async def _calculate_pwerm(self, request: ValuationRequest) -> ValuationResult:
        """
        Probability-Weighted Expected Return Method
        """
        logger.info(f"Calculating PWERM valuation for {request.company_name}")
        
        # Ensure we have a valid valuation
        # CRITICAL FIX: Cannot modify frozen dataclass - create new instance instead
        # Use inferred_valuation as fallback before defaulting to $100M
        # Check explicitly for None (not just falsy) since 0 might be a valid value
        base_valuation = None
        if request.last_round_valuation is not None and request.last_round_valuation > 0:
            base_valuation = request.last_round_valuation
        elif request.inferred_valuation is not None and request.inferred_valuation > 0:
            base_valuation = request.inferred_valuation
        elif request.total_raised and request.total_raised > 0:
            base_valuation = request.total_raised * 3
        else:
            base_valuation = 100_000_000  # Only default if all are missing
        
        if base_valuation == 0 or base_valuation is None:
            base_valuation = 100_000_000  # Final fallback
        
        if not request.last_round_valuation or request.last_round_valuation == 0:
            logger.warning(f"PWERM: No valuation provided for {request.company_name}, using ${base_valuation:,.0f}")
            from dataclasses import replace
            request = replace(request, last_round_valuation=base_valuation)
        
        # Generate exit scenarios and annotate returns
        scenarios = self._generate_exit_scenarios(request)
        discount_rate = self.stage_parameters[request.stage]['discount_rate']
        
        # Calculate probability-weighted value
        total_value = sum(s.probability * s.present_value for s in scenarios)
        
        # Apply DLOM discount
        dlom = self.stage_parameters[request.stage]['dlom']
        fair_value = total_value * (1 - dlom)
        
        # Calculate per-share values if shares outstanding provided
        common_value = None
        if request.common_shares_outstanding:
            common_value = fair_value / request.common_shares_outstanding
        
        result = ValuationResult(
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
        
        # Convert any numpy types to native Python types
        return self._sanitize_valuation_result(result)
    
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
        
        result = ValuationResult(
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
        
        return self._sanitize_valuation_result(result)
    
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
        
        result = ValuationResult(
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
        
        return self._sanitize_valuation_result(result)
    
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
        
        result = ValuationResult(
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
        
        return self._sanitize_valuation_result(result)
    
    def _generate_exit_scenarios(self, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate dynamic exit scenarios using comprehensive PWERM system"""
        # Convert ValuationRequest to company_data format
        company_data = self._convert_request_to_company_data(request)
        
        # Calculate valuation using comprehensive PWERM
        pwerm_result = self.comprehensive_pwerm.calculate_valuation(
            company_data=company_data,
            discount_rate=0.25,  # Standard VC discount rate
            dlom=0.30  # Standard DLOM for private companies
        )
        
        # Convert comprehensive scenarios to PWERM scenarios
        # Get all scenarios from the comprehensive PWERM - we need to call the internal method
        # to get the full distribution, not just the grouped/top scenarios
        
        # Parse funding path and get all relevant scenarios
        funding_path = pwerm_result.get('funding_path', 'Pre-seed only')
        all_relevant_scenarios = self.comprehensive_pwerm._filter_scenarios_by_path(funding_path)
        
        # Adjust probabilities based on company data
        company_data = self._convert_request_to_company_data(request)
        adjusted_scenarios = self.comprehensive_pwerm._adjust_probabilities(all_relevant_scenarios, company_data)
        
        # Calculate present values for all scenarios
        discount_rate = 0.25
        for scenario in adjusted_scenarios:
            pv_factor = 1 / ((1 + discount_rate) ** scenario.time_to_exit)
            scenario.present_value = scenario.exit_value * pv_factor
        
        # Convert all scenarios to PWERM format
        pwerm_scenarios = self._convert_comprehensive_to_pwerm_scenarios(adjusted_scenarios)
        
        # Annotate with returns and finalize
        return self.annotate_scenarios_with_returns(pwerm_scenarios, request)
    
    def _generate_early_stage_scenarios(self, base_value: float, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate scenarios for early stage companies (Seed/Series A)"""
        # Based on Carta and Cambridge Associates data for early stage exits
        scenarios = [
            # IPO scenarios (rare but high value)
            PWERMScenario(
                scenario="NYSE Blockbuster IPO",
                funding_path="Pre-seed→seed→A→B→C→D→E→F",
                exit_type="IPO (Uber/Airbnb trajectory)",
                probability=0.02,  # 2% - Carta: <2% of seed stage reach IPO
                exit_value=base_value * 50,
                time_to_exit=8.0  # PitchBook: 8-10 years median
            ),
            PWERMScenario(
                scenario="Upper Midcap IPO",
                funding_path="Pre-seed→seed→A→B→C→D",
                exit_type="Small Cap Buyout/Crown Jewel Asset",
                probability=0.03,  # 3% - Additional IPO candidates
                exit_value=base_value * 20,
                time_to_exit=7.0
            ),
            
            # Strategic acquisition scenarios
            PWERMScenario(
                scenario="Strategic Premium Acquisition (competitive bidding)",
                funding_path="seed→A→B→C→D",
                exit_type="M&A - Strategic (Premium)",
                probability=0.08,  # 8% - Best outcomes
                exit_value=base_value * 15,
                time_to_exit=5.0
            ),
            PWERMScenario(
                scenario="Strategic Acquisition (strong fit)",
                funding_path="seed→A→B→C",
                exit_type="M&A - Strategic",
                probability=0.12,  # 12% - Good strategic fit
                exit_value=base_value * 8,
                time_to_exit=4.0
            ),
            PWERMScenario(
                scenario="Quick Strategic Exit (talent/tech acquisition)",
                funding_path="seed→A",
                exit_type="M&A - Acquihire",
                probability=0.15,  # 15% - Common for seed stage
                exit_value=base_value * 4,
                time_to_exit=2.5
            ),
            
            # Growth/PE scenarios
            PWERMScenario(
                scenario="Growth Equity Recap",
                funding_path="seed→A→B→Growth",
                exit_type="PE - Growth Equity",
                probability=0.10,  # 10% - Secondary opportunity
                exit_value=base_value * 3,
                time_to_exit=3.0
            ),
            
            # Modest exits
            PWERMScenario(
                scenario="Modest M&A Exit",
                funding_path="seed→A→B",
                exit_type="M&A - Modest",
                probability=0.20,  # 20% - Break-even to small return
                exit_value=base_value * 1.5,
                time_to_exit=3.0
            ),
            PWERMScenario(
                scenario="Acquihire/Small Exit",
                funding_path="seed",
                exit_type="M&A - Acquihire",
                probability=0.15,  # 15% - Team acquisition
                exit_value=base_value * 0.8,
                time_to_exit=2.0
            ),
            
            # Negative scenarios
            PWERMScenario(
                scenario="Distressed Sale/Wind Down",
                funding_path="seed",
                exit_type="Distressed Sale",
                probability=0.10,  # 10% - Fire sale
                exit_value=base_value * 0.3,
                time_to_exit=1.5
            ),
            PWERMScenario(
                scenario="Complete Write-off",
                funding_path="",
                exit_type="Write-off",
                probability=0.05,  # 5% - Total loss (Carta: 20-30% fail rate but not all are zeros)
                exit_value=0,
                time_to_exit=2.0
            )
        ]
        
        return self.annotate_scenarios_with_returns(scenarios, request)
    
    def _generate_growth_stage_scenarios(self, base_value: float, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate scenarios for growth stage companies (Series B/C)"""
        # More concentrated outcomes, higher success rates
        scenarios = [
            # IPO scenarios (more likely at this stage)
            PWERMScenario(
                scenario="Strong IPO (Unicorn status)",
                funding_path="B→C→D→E",
                exit_type="IPO - NYSE/NASDAQ",
                probability=0.10,  # 10% - Carta: Series B+ have better IPO odds
                exit_value=base_value * 10,
                time_to_exit=5.0,
            ),
            PWERMScenario(
                scenario="Standard IPO/SPAC",
                funding_path="B→C→D",
                exit_type="IPO - SPAC",
                probability=0.05,  # 5% - Alternative public paths
                exit_value=base_value * 5,
                time_to_exit=4.0,
            ),
            
            # Strategic acquisitions (primary exit path)
            PWERMScenario(
                scenario="Premium Strategic Acquisition",
                funding_path="B→C→D",
                exit_type="M&A - Strategic (Premium)",
                probability=0.20,  # 20% - Strong strategic value
                exit_value=base_value * 6,
                time_to_exit=3.0,
            ),
            PWERMScenario(
                scenario="Strategic Acquisition (market consolidation)",
                funding_path="B→C",
                exit_type="M&A - Strategic",
                probability=0.25,  # 25% - Most common good outcome
                exit_value=base_value * 3.5,
                time_to_exit=2.5,
            ),
            
            # PE acquisitions
            PWERMScenario(
                scenario="PE Buyout (platform play)",
                funding_path="B→C",
                exit_type="PE - Buyout",
                probability=0.15,  # 15% - PE interest in proven models
                exit_value=base_value * 2.5,
                time_to_exit=2.0,
            ),
            
            # Modest outcomes
            PWERMScenario(
                scenario="Modest Exit (1-2x return)",
                funding_path="B",
                exit_type="M&A - Modest",
                probability=0.15,  # 15% - Break-even to small gain
                exit_value=base_value * 1.3,
                time_to_exit=2.0,
            ),
            
            # Negative scenarios (lower probability at this stage)
            PWERMScenario(
                scenario="Down Round/Distressed M&A",
                funding_path="B",
                exit_type="M&A - Distressed",
                probability=0.07,  # 7% - Restructuring
                exit_value=base_value * 0.5,
                time_to_exit=1.0,
            ),
            PWERMScenario(
                scenario="Distressed Sale",
                funding_path="",
                exit_type="Distressed Sale",
                probability=0.03,  # 3% - Lower failure rate
                exit_value=base_value * 0.2,
                time_to_exit=1.0,
            )
        ]
        
        return self.annotate_scenarios_with_returns(scenarios, request)
    
    def _generate_late_stage_scenarios(self, base_value: float, request: ValuationRequest) -> List[PWERMScenario]:
        """Generate scenarios for late stage companies (Growth/Late)"""
        # Clearer paths to exit, lower variance
        scenarios = [
            # IPO scenarios (highest probability at this stage)
            PWERMScenario(
                scenario="Successful IPO",
                funding_path="Late→IPO",
                exit_type="IPO - NYSE/NASDAQ",
                probability=0.25,  # 25% - Much higher for late stage
                exit_value=base_value * 3,
                time_to_exit=2.0,
            ),
            PWERMScenario(
                scenario="Direct Listing/SPAC",
                funding_path="Late",
                exit_type="IPO - Direct Listing",
                probability=0.10,  # 10% - Alternative public paths
                exit_value=base_value * 2.2,
                time_to_exit=1.5,
            ),
            
            # M&A scenarios
            PWERMScenario(
                scenario="Strategic Premium Acquisition",
                funding_path="Late",
                exit_type="M&A - Strategic (Premium)",
                probability=0.30,  # 30% - Primary alternative to IPO
                exit_value=base_value * 2.5,
                time_to_exit=1.5,
            ),
            PWERMScenario(
                scenario="PE Buyout",
                funding_path="Late",
                exit_type="PE - Buyout",
                probability=0.20,  # 20% - Common for mature companies
                exit_value=base_value * 1.8,
                time_to_exit=1.0,
            ),
            
            # Continuation scenarios
            PWERMScenario(
                scenario="Secondary Sale",
                funding_path="Late",
                exit_type="Secondary Sale",
                probability=0.10,  # 10% - Liquidity without full exit
                exit_value=base_value * 1.3,
                time_to_exit=1.0,
            ),
            
            # Downside (minimal at this stage)
            PWERMScenario(
                scenario="Flat/Down Exit",
                funding_path="Late",
                exit_type="M&A - Flat",
                probability=0.05,  # 5% - Rare but possible
                exit_value=base_value * 0.8,
                time_to_exit=1.0,
            )
        ]
        
        return self.annotate_scenarios_with_returns(scenarios, request)
    
    def _get_funding_path_for_stage(self, stage: Stage, rounds_to_exit: int = 3) -> str:
        """Generate funding path from current stage to exit"""
        progressions = {
            Stage.PRE_SEED: ["pre-seed", "seed", "A", "B", "C", "D"],
            Stage.SEED: ["seed", "A", "B", "C", "D", "E"],
            Stage.SERIES_A: ["A", "B", "C", "D", "E"],
            Stage.SERIES_B: ["B", "C", "D", "E"],
            Stage.SERIES_C: ["C", "D", "E"],
            Stage.GROWTH: ["Growth", "Late"],
            Stage.LATE: ["Late"]
        }
        
        path = progressions.get(stage, ["A", "B", "C"])
        # Take minimum of requested rounds and available path length
        actual_rounds = min(rounds_to_exit, len(path))
        return "→".join(path[:actual_rounds]) if actual_rounds > 0 else ""
    
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
        
        return self.annotate_scenarios_with_returns(scenarios, request)
    
    def model_cap_table_evolution(self, scenario: PWERMScenario, company_data: Dict[str, Any], 
                                  our_investment: Dict[str, float]) -> None:
        """
        Model cap table evolution for a specific PWERM scenario.
        NOW WITH TAM/SAM/SOM VALIDATION
        Updates the scenario object with cap table evolution, final ownership, and breakpoints.
        """
        # Parse funding path
        rounds = [r.strip() for r in scenario.funding_path.split('→') if r.strip()]
        
        # Start with current state
        current_liq_pref = company_data.get('total_funding', 0)
        our_ownership = our_investment.get('ownership', 0.10)
        
        # NEW: Get market size analysis (from intelligent_gap_filler)
        market_analysis = company_data.get('market_size', {})
        tam = market_analysis.get('tam', 0)
        sam = market_analysis.get('sam', 0)
        som = market_analysis.get('som', 0)
        
        # Track cap table evolution
        cap_table_evolution = []
        
        # Dilution benchmarks (from intelligent_gap_filler)
        ROUND_DILUTION = {
            "seed": 0.15, "Seed": 0.15,
            "A": 0.20, "Series A": 0.20,
            "B": 0.15, "Series B": 0.15, 
            "C": 0.12, "Series C": 0.12,
            "D": 0.10, "Series D": 0.10,
            "E": 0.08, "Series E": 0.08,
            "F": 0.08, "Series F": 0.08
        }
        
        # ESOP expansion per round
        ESOP_EXPANSION = {
            "seed": 0.05, "Seed": 0.05,
            "A": 0.05, "Series A": 0.05,
            "B": 0.03, "Series B": 0.03,
            "C": 0.02, "Series C": 0.02,
            "D": 0.02, "Series D": 0.02,
            "E": 0.01, "Series E": 0.01,
            "F": 0.01, "Series F": 0.01
        }
        
        # Round sizes (approximate)
        ROUND_SIZES = {
            "seed": 3_000_000, "Seed": 3_000_000,
            "A": 15_000_000, "Series A": 15_000_000,
            "B": 50_000_000, "Series B": 50_000_000,
            "C": 100_000_000, "Series C": 100_000_000,
            "D": 200_000_000, "Series D": 200_000_000,
            "E": 300_000_000, "Series E": 300_000_000,
            "F": 500_000_000, "Series F": 500_000_000
        }
        
        for round_name in rounds:
            # Get base dilution
            base_dilution = ROUND_DILUTION.get(round_name, 0.15)
            esop_expansion = ESOP_EXPANSION.get(round_name, 0.03)
            round_size = ROUND_SIZES.get(round_name, 50_000_000)
            
            # Adjust dilution based on scenario quality
            if "NYSE Blockbuster" in scenario.scenario or "Strong IPO" in scenario.scenario:
                # Premium path - Tier 1 investors, less dilution
                quality_mult = 0.85
                liq_pref_multiple = 1.0
            elif "Strategic Premium" in scenario.scenario:
                # Good path - Tier 2 investors
                quality_mult = 1.0
                liq_pref_multiple = 1.0
            elif "Distressed" in scenario.scenario or "Acquihire" in scenario.scenario:
                # Difficult path - worse terms
                quality_mult = 1.25
                liq_pref_multiple = 1.5 if "C" in round_name or "D" in round_name else 1.0
            else:
                # Standard terms
                quality_mult = 1.0
                liq_pref_multiple = 1.0
            
            # Apply geography adjustment (if SF/NYC, less dilution)
            geo_mult = 0.95 if company_data.get('geography', '') in ['SF', 'San Francisco', 'NYC', 'New York'] else 1.0
            
            # Calculate actual dilution
            actual_dilution = base_dilution * quality_mult * geo_mult
            total_dilution = actual_dilution + esop_expansion
            
            # Update ownership
            our_ownership *= (1 - total_dilution)
            
            # Update liquidation preference
            current_liq_pref += round_size * liq_pref_multiple
            
            # NEW: Calculate implied revenue needed to justify valuation
            post_money = current_liq_pref / actual_dilution  # Rough valuation
            
            # NEW: TAM/SAM/SOM sanity check
            market_capture_needed = 0
            tam_feasibility = "unknown"
            if tam > 0:
                # At exit, assume company captures 1-5% of TAM
                market_capture_needed = (scenario.exit_value / tam) * 100
                if market_capture_needed < 1:
                    tam_feasibility = "highly achievable"
                elif market_capture_needed < 5:
                    tam_feasibility = "achievable"
                elif market_capture_needed < 15:
                    tam_feasibility = "aggressive"
                else:
                    tam_feasibility = "unrealistic"
            
            # Calculate breakpoints at this stage
            breakpoints = {
                'liquidation_satisfied': current_liq_pref,
                'conversion_point': current_liq_pref * 1.5,  # Typical conversion threshold
                'our_breakeven': our_investment['amount'] / our_ownership if our_ownership > 0 else float('inf'),
                'our_3x': (our_investment['amount'] * 3) / our_ownership if our_ownership > 0 else float('inf'),
                'common_meaningful': current_liq_pref + 10_000_000  # Common gets >$10M
            }
            
            cap_table_evolution.append({
                'round': round_name,
                'dilution': actual_dilution,
                'esop_expansion': esop_expansion,
                'our_ownership': our_ownership,
                'total_liq_pref': current_liq_pref,
                'breakpoints': breakpoints.copy(),
                # NEW MARKET SIZE FIELDS
                'market_capture_pct': market_capture_needed,
                'tam_feasibility': tam_feasibility,
            })
        
        # Update scenario with evolution
        scenario.cap_table_evolution = cap_table_evolution
        scenario.final_ownership = our_ownership
        scenario.final_liq_pref = current_liq_pref
        
        # NEW: Add market sizing to scenario
        scenario.market_analysis = {
            'tam': tam,
            'sam': sam,
            'som': som,
            'exit_market_capture': (scenario.exit_value / tam * 100) if tam > 0 else 0,
            'citations': market_analysis.get('citations', [])
        }
        
        # Set final breakpoints
        if cap_table_evolution:
            scenario.breakpoints = cap_table_evolution[-1]['breakpoints']
        else:
            # No future rounds - use current state
            scenario.breakpoints = {
                'liquidation_satisfied': current_liq_pref,
                'conversion_point': current_liq_pref * 1.5,
                'our_breakeven': our_investment['amount'] / our_ownership if our_ownership > 0 else float('inf'),
                'our_3x': (our_investment['amount'] * 3) / our_ownership if our_ownership > 0 else float('inf'),
                'common_meaningful': current_liq_pref + 10_000_000
            }
        
        # Calculate MOIC based on exit value and final ownership
        if scenario.exit_value and our_investment['amount'] > 0:
            # Simple calculation: our proceeds / our investment
            our_proceeds = scenario.exit_value * scenario.final_ownership
            scenario.moic = our_proceeds / our_investment['amount']
        else:
            scenario.moic = 0.0
    
    def calculate_breakpoint_distributions(self, scenarios: List[PWERMScenario]) -> Dict[str, Dict[str, float]]:
        """
        Calculate probability distributions for breakpoints across all scenarios.
        Returns percentiles and expected values for each breakpoint type.
        Handles both PWERMScenario objects and dictionaries.
        """
        import numpy as np
        
        # Collect breakpoints by type with their probabilities
        breakpoint_collections = {
            'liquidation_satisfied': [],
            'conversion_point': [],
            'our_breakeven': [],
            'our_3x': [],
            'common_meaningful': []
        }
        
        for scenario in scenarios:
            # Handle both PWERMScenario objects and dictionaries
            # Use defensive checks: try dict-like access first, then attribute access
            try:
                # Try dict-like access first (handles dict, OrderedDict, custom mappings)
                if hasattr(scenario, 'get') and callable(scenario.get):
                    weight = scenario.get('probability', 0)
                    exit_type = scenario.get('exit_type', '')
                    breakpoints = scenario.get('breakpoints', {})
                else:
                    # Try attribute access (PWERMScenario object)
                    weight = getattr(scenario, 'probability', 0)
                    exit_type = getattr(scenario, 'exit_type', '')
                    breakpoints = getattr(scenario, 'breakpoints', {})
            except (AttributeError, TypeError) as e:
                logger.warning(f"Skipping malformed scenario: {e}")
                continue
            
            # Skip scenarios with zero probability
            if weight == 0:
                continue
                
            # For IPO scenarios, some breakpoints don't apply
            if "IPO" in exit_type:
                # In IPO, all convert to common - no liquidation preference
                # But we still track ownership-based breakpoints
                if breakpoints:
                    if isinstance(breakpoints, dict):
                        breakpoint_collections['our_breakeven'].append({
                            'value': breakpoints.get('our_breakeven', 0),
                            'weight': weight
                        })
                        breakpoint_collections['our_3x'].append({
                            'value': breakpoints.get('our_3x', 0),
                            'weight': weight
                        })
            else:
                # M&A scenarios - all breakpoints matter
                if breakpoints:
                    for bp_type in breakpoint_collections.keys():
                        value = breakpoints.get(bp_type, 0) if isinstance(breakpoints, dict) else 0
                        if value > 0 and value != float('inf'):
                            breakpoint_collections[bp_type].append({
                                'value': value,
                                'weight': weight
                            })
        
        # Calculate distributions
        distributions = {}
        for bp_type, points in breakpoint_collections.items():
            if not points:
                continue
                
            # Extract values and weights
            values = np.array([p['value'] for p in points])
            weights = np.array([p['weight'] for p in points])
            
            # Normalize weights
            total_weight = weights.sum()
            if total_weight == 0:
                continue
            weights = weights / total_weight
            
            # Sort by value for percentile calculation
            sorted_indices = np.argsort(values)
            sorted_values = values[sorted_indices]
            sorted_weights = weights[sorted_indices]
            
            # Calculate cumulative probability
            cumulative = np.cumsum(sorted_weights)
            
            # Calculate percentiles
            def weighted_percentile(perc):
                target = perc / 100.0
                idx = np.searchsorted(cumulative, target)
                if idx >= len(sorted_values):
                    return sorted_values[-1]
                return sorted_values[idx]
            
            # Calculate expected value
            expected = np.sum(values * weights)
            
            distributions[bp_type] = {
                'p10': weighted_percentile(10),
                'p25': weighted_percentile(25),
                'median': weighted_percentile(50),
                'p75': weighted_percentile(75),
                'p90': weighted_percentile(90),
                'expected': expected,
                'min': values.min(),
                'max': values.max()
            }
        
        return distributions
    
    def generate_return_curves(self, scenarios: List[PWERMScenario], our_investment: Dict[str, float]) -> None:
        """
        Generate return curves for each scenario across a range of exit values.
        Updates each scenario with its return curve data.
        """
        import numpy as np
        
        # Exit value range from $10M to $10B (log scale)
        exit_values = np.logspace(7, 10, 100)  # 100 points from 10M to 10B
        
        for scenario in scenarios:
            returns = []
            
            for exit_value in exit_values:
                if scenario.exit_type and "IPO" in scenario.exit_type:
                    # IPO: Simple ownership-based return (all convert to common)
                    our_proceeds = exit_value * scenario.final_ownership
                else:
                    # M&A: Need to calculate waterfall
                    # Simplified waterfall calculation
                    if exit_value <= scenario.final_liq_pref:
                        # Below liquidation preference - we might get nothing
                        our_proceeds = 0  # Simplified - would need full waterfall
                    elif exit_value <= scenario.breakpoints.get('conversion_point', scenario.final_liq_pref * 1.5):
                        # Between liq pref and conversion - liquidation preference applies
                        remaining = exit_value - scenario.final_liq_pref
                        our_proceeds = remaining * scenario.final_ownership
                    else:
                        # Above conversion - everyone converts to common
                        our_proceeds = exit_value * scenario.final_ownership
                
                # Calculate return multiple
                return_multiple = our_proceeds / our_investment['amount'] if our_investment['amount'] > 0 else 0
                returns.append(return_multiple)
            
            # Store return curve
            scenario.return_curve = {
                'exit_values': exit_values.tolist(),
                'return_multiples': returns,
                'color': self._get_scenario_color(scenario),
                'opacity': min(scenario.probability * 3, 0.9)  # Higher probability = more opaque
            }
    
    def _get_scenario_color(self, scenario: PWERMScenario) -> str:
        """Get color based on scenario quality."""
        if "NYSE Blockbuster" in scenario.scenario or "Strong IPO" in scenario.scenario:
            return "#22c55e"  # Green - best outcomes
        elif "Strategic Premium" in scenario.scenario:
            return "#3b82f6"  # Blue - good outcomes
        elif "Modest" in scenario.scenario or "Growth Equity" in scenario.scenario:
            return "#f59e0b"  # Orange - moderate outcomes
        elif "Distressed" in scenario.scenario or "Write-off" in scenario.scenario:
            return "#ef4444"  # Red - poor outcomes
        else:
            return "#9ca3af"  # Gray - neutral
    
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
    
    def calculate_fund_dpi_impact(
        self,
        investment_amount: float,
        entry_stage: str,
        exit_value: float,
        total_preferences_ahead: float,
        our_ownership_pct: float = None,  # CALCULATE THIS, DON'T HARDCODE
        fund_size: float = 260_000_000,
        fund_dpi: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculate how a $150M exit impacts a 0 DPI fund
        Most fund managers are average - they need these exits
        
        Args:
            our_ownership_pct: Our actual ownership % (e.g., 0.12 for 12%). 
                              If not provided, estimates from investment amount and stage.
        """
        # Simple waterfall - preferences get paid first
        remaining_after_prefs = max(0, exit_value - total_preferences_ahead)
        
        # CALCULATE ownership from investment, don't hardcode!
        if our_ownership_pct is None:
            # Estimate from stage benchmarks and investment size
            # Typical valuations by stage
            typical_valuations = {
                'Seed': 10_000_000,
                'Series A': 40_000_000,
                'Series B': 120_000_000,
                'Series C': 400_000_000,
            }
            typical_valuation = typical_valuations.get(entry_stage, 100_000_000)
            # Calculate ownership as: investment / (pre-money + investment)
            our_ownership_pct = investment_amount / (typical_valuation + investment_amount)
            
        our_return = remaining_after_prefs * our_ownership_pct
        
        # The brutal math
        dpi_contribution = our_return / fund_size
        moic = our_return / investment_amount if investment_amount > 0 else 0
        
        # For a 0 DPI fund, every dollar matters
        result = {
            'exit_value': exit_value,
            'preferences_ahead': total_preferences_ahead,
            'remaining_for_common': remaining_after_prefs,
            'our_return': our_return,
            'our_investment': investment_amount,
            'moic': moic,
            'dpi_contribution': dpi_contribution * 100,  # As percentage
            'new_fund_dpi': (fund_dpi + dpi_contribution) * 100
        }
        
        # The harsh reality check
        if exit_value == 150_000_000:
            if our_return == 0:
                result['reality_check'] = "THE $150M PROBLEM: Decent exit, we get ZERO"
            elif moic < 1:
                result['reality_check'] = f"Lost ${(investment_amount - our_return)/1e6:.1f}M on a $150M exit"
            elif dpi_contribution < 0.01:
                result['reality_check'] = "Moved DPI by <1% - need 100 of these to return fund"
            else:
                result['reality_check'] = f"Rare win - actually got {moic:.1f}x on $150M exit"
        
        # What we actually need
        if fund_dpi == 0:
            # For 0 DPI fund, calculate exits needed to get to 1x
            exits_needed_for_1x = fund_size / our_return if our_return > 0 else float('inf')
            result['exits_needed_for_1x_dpi'] = exits_needed_for_1x
            result['years_to_1x_at_this_rate'] = exits_needed_for_1x / 2  # Assume 2 exits per year
        
        return result
    
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

    # ------------------------------------------------------------------
    # Phase 2: Scenario-Branching Cap Tables with Full Waterfall
    # ------------------------------------------------------------------
    def generate_scenario_cap_tables(
        self,
        company_data: Dict[str, Any],
        analytics: Optional[Dict[str, Any]] = None,
        our_investment: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate scenario-branching cap tables with full waterfall integration.

        For each company, models 4 future scenarios for the next round,
        then runs AdvancedCapTable.calculate_liquidation_waterfall() at
        various exit values to show exactly what we get paid — including
        liquidation preferences, participation rights, and seniority.

        Args:
            company_data: Company dict with funding_rounds, stage, valuation, etc.
            analytics: CompanyAnalytics dict (from Phase 1). Optional — will infer if missing.
            our_investment: {amount, ownership_pct, round_name}. If missing, uses company data.

        Returns:
            Dict with scenario branches, each containing waterfall at key exit values,
            return curves, breakpoints, and Sankey data.
        """
        from app.services.advanced_cap_table import CapTableCalculator
        from app.services.pre_post_cap_table import PrePostCapTable
        from app.services.data_validator import ensure_numeric

        cap_table_service = PrePostCapTable()
        waterfall_calc = CapTableCalculator()

        # --- Extract company info ---
        stage = str(company_data.get("stage", "Series A"))
        funding_rounds = company_data.get("funding_rounds", []) or []
        current_valuation = ensure_numeric(
            company_data.get("valuation") or company_data.get("current_valuation_usd"), 0
        )
        total_funding = ensure_numeric(company_data.get("total_funding"), 0)
        if total_funding == 0:
            total_funding = sum(
                ensure_numeric(r.get("amount") or r.get("round_size"), 0)
                for r in funding_rounds if isinstance(r, dict)
            )

        # Our investment
        our_amount = ensure_numeric((our_investment or {}).get("amount"), 0)
        our_ownership = ensure_numeric((our_investment or {}).get("ownership_pct"), 0) / 100
        our_round = (our_investment or {}).get("round_name", stage)

        # Use analytics if available, else use company_data directly
        growth_rate = 1.0
        runway_months = 18.0
        valuation_direction = "flat"
        if analytics:
            growth_rate = analytics.get("growth_rate", 1.0)
            runway_months = analytics.get("estimated_runway_months", 18.0)
            valuation_direction = analytics.get("valuation_direction", "flat")

        # Get current cap table
        try:
            cap_history = cap_table_service.calculate_full_cap_table_history(company_data)
            current_cap = cap_history.get("current_cap_table", {})
        except Exception as e:
            logger.warning(f"Cap table calculation failed: {e}")
            current_cap = {"Founders": 50.0, f"{stage} Investors": 30.0, "Option Pool": 20.0}

        # Determine next stage
        stage_sequence = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Series E"]
        next_stage = "Series B"
        for i, s in enumerate(stage_sequence):
            if s.lower() in stage.lower() and i + 1 < len(stage_sequence):
                next_stage = stage_sequence[i + 1]
                break

        # Stage-typical round data
        typical_rounds = {
            "Seed": {"amount": 3_000_000, "dilution": 0.15},
            "Series A": {"amount": 15_000_000, "dilution": 0.20},
            "Series B": {"amount": 50_000_000, "dilution": 0.15},
            "Series C": {"amount": 100_000_000, "dilution": 0.12},
            "Series D": {"amount": 200_000_000, "dilution": 0.10},
            "Series E": {"amount": 350_000_000, "dilution": 0.08},
        }
        typical = typical_rounds.get(next_stage, {"amount": 50_000_000, "dilution": 0.15})

        # --- Build 4 scenarios ---
        scenarios = []

        # 1. Base Case — Hits Current Trajectory
        base_round_size = typical["amount"]
        base_dilution = typical["dilution"]
        base_pre_money = base_round_size / base_dilution - base_round_size if base_dilution > 0 else current_valuation * 1.5
        scenarios.append({
            "name": "base",
            "label": "Base Case — Hits Targets",
            "round_stage": next_stage,
            "round_size": base_round_size,
            "pre_money": base_pre_money,
            "dilution": base_dilution,
            "new_investor_preference": 1.0,
            "new_investor_participating": False,
            "esop_expansion": 0.02,
        })

        # 2. Growth Decay — Misses by 30%
        decay_dilution = min(base_dilution * 1.4, 0.30)
        decay_round_size = base_round_size * 0.75
        decay_pre_money = decay_round_size / decay_dilution - decay_round_size if decay_dilution > 0 else current_valuation * 0.9
        scenarios.append({
            "name": "growth_decay",
            "label": "Growth Decay — Misses by 30%",
            "round_stage": next_stage,
            "round_size": decay_round_size,
            "pre_money": decay_pre_money,
            "dilution": decay_dilution,
            "new_investor_preference": 1.0,
            "new_investor_participating": True,
            "esop_expansion": 0.02,
        })

        # 3. Bridge / Extension
        bridge_round_size = base_round_size * 0.3
        bridge_pre_money = current_valuation * 0.75 if current_valuation > 0 else base_pre_money * 0.5
        bridge_dilution = bridge_round_size / (bridge_pre_money + bridge_round_size) if (bridge_pre_money + bridge_round_size) > 0 else 0.25
        scenarios.append({
            "name": "bridge",
            "label": "Bridge / Extension",
            "round_stage": f"{stage} Extension",
            "round_size": bridge_round_size,
            "pre_money": bridge_pre_money,
            "dilution": bridge_dilution,
            "new_investor_preference": 1.5,
            "new_investor_participating": True,
            "esop_expansion": 0.0,
        })

        # 4. Outperformance
        outperform_dilution = max(base_dilution * 0.65, 0.08)
        outperform_round_size = base_round_size * 1.3
        outperform_pre_money = outperform_round_size / outperform_dilution - outperform_round_size if outperform_dilution > 0 else base_pre_money * 2.5
        scenarios.append({
            "name": "outperform",
            "label": "Outperformance — 2x+ Step-Up",
            "round_stage": next_stage,
            "round_size": outperform_round_size,
            "pre_money": outperform_pre_money,
            "dilution": outperform_dilution,
            "new_investor_preference": 1.0,
            "new_investor_participating": False,
            "esop_expansion": 0.01,
        })

        # --- For each scenario, compute cap table + waterfall ---
        exit_values = [
            10_000_000, 25_000_000, 50_000_000, 100_000_000,
            250_000_000, 500_000_000, 750_000_000, 1_000_000_000,
            2_000_000_000, 5_000_000_000,
        ]

        scenario_results = []

        for sc in scenarios:
            # Apply dilution to compute post-scenario ownership
            dilution = sc["dilution"]
            esop = sc["esop_expansion"]
            total_dilution = dilution + esop

            our_ownership_post = our_ownership * (1 - total_dilution)
            founder_ownership_post = 0.0
            for k, v in current_cap.items():
                if "founder" in k.lower() or k == "Founders":
                    founder_ownership_post += (v / 100) * (1 - total_dilution)

            # Build total preference stack
            existing_prefs = total_funding  # simplified: all prior funding = 1x pref
            new_pref = sc["round_size"] * sc["new_investor_preference"]
            total_pref_stack = existing_prefs + new_pref

            # Build funding rounds for waterfall calculation (include the new round)
            waterfall_rounds = []
            for i, r in enumerate(funding_rounds):
                if not isinstance(r, dict):
                    continue
                waterfall_rounds.append({
                    "round": r.get("round", f"Round {i+1}"),
                    "amount": ensure_numeric(r.get("amount") or r.get("round_size"), 0),
                    "investors": r.get("investors", []) or [],
                    "lead_investor": r.get("lead_investor", ""),
                    "liquidation_multiple": 1.0,
                    "participating": False,
                    "seniority": i + 1,
                })
            # Add the scenario's new round
            waterfall_rounds.append({
                "round": sc["round_stage"],
                "amount": sc["round_size"],
                "investors": [f"{sc['round_stage']} New Investor"],
                "lead_investor": f"{sc['round_stage']} New Investor",
                "liquidation_multiple": sc["new_investor_preference"],
                "participating": sc["new_investor_participating"],
                "seniority": len(waterfall_rounds) + 1,
            })

            # --- Compute our position in the preference stack ---
            # Which seniority tranche are we in? What's above/below us?
            our_seniority = 0
            prefs_senior_to_us = 0.0
            prefs_junior_to_us = 0.0
            our_preference_amount = our_amount * 1.0  # 1x pref on our invested amount

            for wr in waterfall_rounds:
                wr_seniority = wr.get("seniority", 0)
                wr_pref_amount = ensure_numeric(wr.get("amount"), 0) * wr.get("liquidation_multiple", 1.0)
                # Identify our round by matching on our_round name
                if our_round and our_round.lower() in str(wr.get("round", "")).lower():
                    our_seniority = wr_seniority
                    continue
                if our_seniority > 0 and wr_seniority > our_seniority:
                    prefs_senior_to_us += wr_pref_amount
                elif our_seniority > 0 and wr_seniority < our_seniority:
                    prefs_junior_to_us += wr_pref_amount
                elif our_seniority == 0:
                    # Haven't found our round yet — these are all potentially senior
                    pass

            # If we couldn't match our round, estimate based on total stack
            if our_seniority == 0:
                # New round in this scenario is always most senior
                new_round_pref = sc["round_size"] * sc["new_investor_preference"]
                prefs_senior_to_us = new_round_pref
                prefs_junior_to_us = total_pref_stack - new_round_pref - our_preference_amount

            # Run waterfall at each exit value
            waterfall_at_exits = []
            return_curve_exits = []
            return_curve_moics = []
            return_curve_proceeds = []

            for ev in exit_values:
                try:
                    wf = waterfall_calc.calculate_liquidation_waterfall(
                        exit_value=ev,
                        cap_table=current_cap,
                        funding_rounds=waterfall_rounds,
                    )
                except Exception as e:
                    logger.warning(f"Waterfall calc failed for exit={ev}: {e}")
                    wf = {"distributions": [], "summary": {}}

                pref_paid = sum(
                    d.get("amount", 0) for d in wf.get("distributions", [])
                    if d.get("type") == "liquidation_preference"
                )
                common_dist = sum(
                    d.get("amount", 0) for d in wf.get("distributions", [])
                    if d.get("type") == "common_distribution"
                )

                # Calculate our proceeds with full waterfall logic
                our_proceeds = 0.0
                our_proceeds_source = "none"  # Track where our money comes from
                if our_ownership_post > 0:
                    if ev > total_pref_stack:
                        # Preferences fully satisfied — we participate in common
                        our_proceeds = (ev - total_pref_stack) * our_ownership_post
                        our_proceeds_source = "common_participation"
                    elif our_amount > 0 and ev <= total_pref_stack:
                        # Preference waterfall — we get our pro-rata of preferences
                        our_pref_share = our_amount / total_pref_stack if total_pref_stack > 0 else 0
                        our_proceeds = ev * our_pref_share
                        our_proceeds_source = "preference_pro_rata"

                our_moic = our_proceeds / our_amount if our_amount > 0 else 0
                our_profit = our_proceeds - our_amount

                # How much of exit goes to preferences vs common
                pref_pct_of_exit = (total_pref_stack / ev * 100) if ev > 0 else 100

                waterfall_at_exits.append({
                    "exit_value": ev,
                    # --- Full context for our position ---
                    "our_invested": our_amount,
                    "our_entry_round": our_round,
                    "our_ownership_at_entry_pct": round(our_ownership * 100, 2),
                    "our_ownership_post_scenario_pct": round(our_ownership_post * 100, 2),
                    "our_preference_amount": round(our_preference_amount, 0),
                    "prefs_senior_to_us": round(prefs_senior_to_us, 0),
                    "prefs_junior_to_us": round(prefs_junior_to_us, 0),
                    # --- Proceeds breakdown ---
                    "our_proceeds": round(our_proceeds, 0),
                    "our_proceeds_source": our_proceeds_source,
                    "our_profit": round(our_profit, 0),
                    "our_moic": round(our_moic, 2),
                    # --- Waterfall context ---
                    "total_pref_stack": round(total_pref_stack, 0),
                    "pref_consumed": round(pref_paid, 0),
                    "pref_pct_of_exit": round(pref_pct_of_exit, 1),
                    "common_gets": round(common_dist, 0),
                    "total_distributed": round(wf.get("total_distributed", 0), 0),
                })

                return_curve_exits.append(ev)
                return_curve_moics.append(round(our_moic, 3))
                return_curve_proceeds.append(round(our_proceeds, 0))

            # Calculate breakpoints
            breakeven_exit = 0
            three_x_exit = 0
            for w in waterfall_at_exits:
                if w["our_moic"] >= 1.0 and breakeven_exit == 0:
                    breakeven_exit = w["exit_value"]
                if w["our_moic"] >= 3.0 and three_x_exit == 0:
                    three_x_exit = w["exit_value"]

            scenario_results.append({
                "name": sc["name"],
                "label": sc["label"],
                "round_stage": sc["round_stage"],
                "round_valuation_pre": round(sc["pre_money"], 0),
                "round_size": round(sc["round_size"], 0),
                "dilution_pct": round(sc["dilution"] * 100, 1),
                "new_investor_preference": sc["new_investor_preference"],
                "new_investor_participating": sc["new_investor_participating"],
                # --- Our position context (carried at scenario level too) ---
                "our_entry": {
                    "invested": our_amount,
                    "entry_round": our_round,
                    "entry_ownership_pct": round(our_ownership * 100, 2),
                    "entry_valuation": current_valuation,
                    "cost_basis_per_pct": round(our_amount / (our_ownership * 100), 0) if our_ownership > 0 else 0,
                },
                "our_ownership_post": round(our_ownership_post * 100, 2),
                "our_dilution_this_scenario_pct": round((our_ownership - our_ownership_post) / our_ownership * 100, 1) if our_ownership > 0 else 0,
                "founder_ownership_post": round(founder_ownership_post * 100, 2),
                # --- Preference stack context ---
                "preference_stack": {
                    "total": round(total_pref_stack, 0),
                    "senior_to_us": round(prefs_senior_to_us, 0),
                    "our_preference": round(our_preference_amount, 0),
                    "junior_to_us": round(prefs_junior_to_us, 0),
                    "our_seniority_rank": our_seniority,
                    "total_rounds_in_stack": len(waterfall_rounds),
                },
                "waterfall_at_exits": waterfall_at_exits,
                "return_curve": {
                    "exit_values": return_curve_exits,
                    "our_moic": return_curve_moics,
                    "our_proceeds": return_curve_proceeds,
                },
                "breakeven_exit_value": breakeven_exit,
                "three_x_exit_value": three_x_exit,
                "preference_satisfaction_value": round(total_pref_stack, 0),
            })

        return {
            "company_name": company_data.get("name", "Unknown"),
            "current_stage": stage,
            "current_valuation": current_valuation,
            "total_funding_to_date": total_funding,
            "our_investment": {
                "amount": our_amount,
                "ownership_pct": round(our_ownership * 100, 2),
                "round": our_round,
                "cost_basis_per_pct": round(our_amount / (our_ownership * 100), 0) if our_ownership > 0 else 0,
            },
            "scenarios": scenario_results,
        }

    # ------------------------------------------------------------------
    # Phase 4: Multi-Round Ownership Trees with Preference Deep Dive
    # ------------------------------------------------------------------
    def generate_ownership_tree(
        self,
        company_data: Dict[str, Any],
        our_investment: Optional[Dict[str, Any]] = None,
        rounds_forward: int = 3,
    ) -> Dict[str, Any]:
        """Model ownership evolution through multiple future rounds.

        For a company at stage X, model paths through X+1, X+2, ... to exit.
        Each future round branches into base/decay scenarios. At each terminal
        node, run the full waterfall to show what we get paid including all
        accumulated preference stacking.

        Args:
            company_data: Company dict
            our_investment: {amount, ownership_pct, round_name}
            rounds_forward: How many future rounds to model (default 3)

        Returns:
            Ownership tree with nested branches, preference stacks, and
            waterfall outcomes at terminal exits.
        """
        from app.services.advanced_cap_table import CapTableCalculator
        from app.services.data_validator import ensure_numeric

        waterfall_calc = CapTableCalculator()

        stage = str(company_data.get("stage", "Series A"))
        funding_rounds = company_data.get("funding_rounds", []) or []
        total_funding = ensure_numeric(company_data.get("total_funding"), 0)
        if total_funding == 0:
            total_funding = sum(
                ensure_numeric(r.get("amount") or r.get("round_size"), 0)
                for r in funding_rounds if isinstance(r, dict)
            )

        our_amount = ensure_numeric((our_investment or {}).get("amount"), 0)
        our_ownership = ensure_numeric((our_investment or {}).get("ownership_pct"), 0) / 100

        stage_sequence = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Series E"]
        typical_rounds = {
            "Series A": {"amount": 15_000_000, "dilution": 0.20, "pref": 1.0, "participating": False},
            "Series B": {"amount": 50_000_000, "dilution": 0.15, "pref": 1.0, "participating": False},
            "Series C": {"amount": 100_000_000, "dilution": 0.12, "pref": 1.0, "participating": False},
            "Series D": {"amount": 200_000_000, "dilution": 0.10, "pref": 1.0, "participating": True},
            "Series E": {"amount": 350_000_000, "dilution": 0.08, "pref": 1.0, "participating": True},
        }

        def _get_next_stages(current: str, count: int) -> List[str]:
            stages = []
            try:
                idx = next(i for i, s in enumerate(stage_sequence) if s.lower() in current.lower())
            except StopIteration:
                idx = 2  # default to Series A
            for i in range(1, count + 1):
                if idx + i < len(stage_sequence):
                    stages.append(stage_sequence[idx + i])
            return stages

        future_stages = _get_next_stages(stage, rounds_forward)

        # Determine our seniority in the existing stack
        our_round_name = (our_investment or {}).get("round_name", stage)
        our_seniority_in_tree = 0
        for i, r in enumerate(funding_rounds):
            if isinstance(r, dict) and our_round_name.lower() in str(r.get("round", "")).lower():
                our_seniority_in_tree = i + 1
                break

        # Build branches recursively
        def _build_branch(
            ownership: float,
            pref_stack: float,
            invested: float,
            stage_idx: int,
            path_label: str,
            accumulated_rounds: List[Dict],
        ) -> Dict[str, Any]:
            if stage_idx >= len(future_stages):
                # Terminal node — compute exit outcomes
                exit_outcomes = []
                exit_multiples = [1, 3, 5, 8, 10]
                current_valuation = ensure_numeric(company_data.get("valuation"), 100_000_000)

                # Count rounds by seniority to figure out our position
                rounds_senior = sum(1 for r in accumulated_rounds if r.get("seniority", 0) > our_seniority_in_tree)
                rounds_junior = len(accumulated_rounds) - rounds_senior - 1  # minus our round

                for em in exit_multiples:
                    exit_value = current_valuation * em
                    # Run waterfall
                    try:
                        wf = waterfall_calc.calculate_liquidation_waterfall(
                            exit_value=exit_value,
                            cap_table={},
                            funding_rounds=accumulated_rounds,
                        )
                    except Exception:
                        wf = {"distributions": [], "summary": {}}

                    # Our proceeds
                    our_proceeds_source = "none"
                    if exit_value > pref_stack:
                        our_proceeds = (exit_value - pref_stack) * ownership
                        our_proceeds_source = "common_participation"
                    else:
                        our_pref_share = invested / pref_stack if pref_stack > 0 else 0
                        our_proceeds = exit_value * our_pref_share
                        our_proceeds_source = "preference_pro_rata"

                    moic = our_proceeds / invested if invested > 0 else 0
                    our_profit = our_proceeds - invested
                    pref_pct = (pref_stack / exit_value * 100) if exit_value > 0 else 100

                    exit_outcomes.append({
                        "exit_multiple_label": f"{em}x",
                        "exit_value": round(exit_value, 0),
                        # Full context
                        "our_invested": round(invested, 0),
                        "our_entry_round": (our_investment or {}).get("round_name", stage),
                        "our_ownership_at_entry_pct": round(our_ownership * 100, 2),
                        "our_ownership_at_exit_pct": round(ownership * 100, 2),
                        "dilution_from_entry_pct": round((1 - ownership / our_ownership) * 100, 1) if our_ownership > 0 else 0,
                        "rounds_since_entry": len(accumulated_rounds) - len(initial_rounds),
                        # Proceeds breakdown
                        "our_proceeds": round(our_proceeds, 0),
                        "our_proceeds_source": our_proceeds_source,
                        "our_profit": round(our_profit, 0),
                        "our_moic": round(moic, 2),
                        # Preference context
                        "pref_stack_total": round(pref_stack, 0),
                        "pref_as_pct_of_exit": round(pref_pct, 1),
                        "rounds_senior_to_us": rounds_senior,
                        "rounds_junior_to_us": rounds_junior,
                    })

                return {
                    "path": path_label,
                    "our_ownership_pct": round(ownership * 100, 2),
                    "total_preference_stack": round(pref_stack, 0),
                    "total_invested_by_us": round(invested, 0),
                    "dilution_from_entry_pct": round((1 - ownership / our_ownership) * 100, 1) if our_ownership > 0 else 0,
                    "exit_outcomes": exit_outcomes,
                    "branches": [],
                }

            next_stage = future_stages[stage_idx]
            typical = typical_rounds.get(next_stage, {"amount": 50_000_000, "dilution": 0.15, "pref": 1.0, "participating": False})

            branches = []

            # Branch 1: Base case
            base_dilution = typical["dilution"]
            base_round_size = typical["amount"]
            base_pref = typical["pref"]
            new_ownership = ownership * (1 - base_dilution - 0.02)  # 2% ESOP
            new_pref = pref_stack + base_round_size * base_pref
            new_rounds = accumulated_rounds + [{
                "round": next_stage,
                "amount": base_round_size,
                "investors": [f"{next_stage} Investor"],
                "lead_investor": f"{next_stage} Investor",
                "liquidation_multiple": base_pref,
                "participating": typical["participating"],
                "seniority": len(accumulated_rounds) + 1,
            }]
            base_branch = _build_branch(
                new_ownership, new_pref, invested,
                stage_idx + 1, f"{path_label} → {next_stage} (base)", new_rounds,
            )
            base_branch["round_label"] = f"{next_stage} — Base"
            base_branch["round_dilution"] = round(base_dilution * 100, 1)
            base_branch["round_size"] = base_round_size
            base_branch["new_pref_added"] = round(base_round_size * base_pref, 0)
            branches.append(base_branch)

            # Branch 2: Decay/tough terms
            decay_dilution = min(base_dilution * 1.5, 0.30)
            decay_round_size = base_round_size * 0.6
            decay_pref_mult = 1.5
            decay_ownership = ownership * (1 - decay_dilution - 0.02)
            decay_pref = pref_stack + decay_round_size * decay_pref_mult
            decay_rounds = accumulated_rounds + [{
                "round": f"{next_stage} (tough)",
                "amount": decay_round_size,
                "investors": [f"{next_stage} Investor"],
                "lead_investor": f"{next_stage} Investor",
                "liquidation_multiple": decay_pref_mult,
                "participating": True,
                "seniority": len(accumulated_rounds) + 1,
            }]
            decay_branch = _build_branch(
                decay_ownership, decay_pref, invested,
                stage_idx + 1, f"{path_label} → {next_stage} (decay)", decay_rounds,
            )
            decay_branch["round_label"] = f"{next_stage} — Growth Decay"
            decay_branch["round_dilution"] = round(decay_dilution * 100, 1)
            decay_branch["round_size"] = decay_round_size
            decay_branch["new_pref_added"] = round(decay_round_size * decay_pref_mult, 0)
            branches.append(decay_branch)

            return {
                "path": path_label,
                "our_ownership_pct": round(ownership * 100, 2),
                "total_preference_stack": round(pref_stack, 0),
                "total_invested_by_us": round(invested, 0),
                "branches": branches,
            }

        # Build the initial waterfall rounds from existing funding
        initial_rounds = []
        for i, r in enumerate(funding_rounds):
            if not isinstance(r, dict):
                continue
            initial_rounds.append({
                "round": r.get("round", f"Round {i+1}"),
                "amount": ensure_numeric(r.get("amount") or r.get("round_size"), 0),
                "investors": r.get("investors", []) or [],
                "lead_investor": r.get("lead_investor", ""),
                "liquidation_multiple": 1.0,
                "participating": False,
                "seniority": i + 1,
            })

        tree = _build_branch(
            our_ownership, total_funding, our_amount,
            0, f"Current ({stage})", initial_rounds,
        )

        # Add preference stack summary
        # Count total terminal scenarios
        def _count_terminals(node: Dict) -> int:
            if not node.get("branches"):
                return 1
            return sum(_count_terminals(b) for b in node["branches"])

        return {
            "company_name": company_data.get("name", "Unknown"),
            "current_stage": stage,
            "our_investment": {
                "amount": our_amount,
                "ownership_pct": round(our_ownership * 100, 2),
            },
            "rounds_modeled": len(future_stages),
            "total_terminal_scenarios": _count_terminals(tree),
            "ownership_tree": tree,
        }


# Global service instance
valuation_engine_service = ValuationEngineService()
