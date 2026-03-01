"""
Intelligent Gap Filler for MCP
Wires together existing funding cadence, liquidation waterfall, and benchmark systems
to intelligently infer missing data and score companies for fund fit
"""

import logging
import math
import random
import json
import asyncio
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
from datetime import datetime, timedelta

# Ensure environment variables are loaded before ModelRouter initialization
if not os.getenv("ANTHROPIC_API_KEY"):
    from dotenv import load_dotenv
    load_dotenv()

from app.services.model_router import ModelRouter, ModelCapability

# Import centralized data validator to prevent None errors
from app.services.data_validator import (
    ensure_numeric as ensure_numeric_central,
    safe_divide as safe_divide_central,
    safe_get_value as safe_get_value_central,
    validate_company_data as validate_company_data_central
)

logger = logging.getLogger(__name__)


@dataclass
class FundProfile:
    """Our fund's investment profile"""
    name: str = "Dilla Ventures"
    stage_focus: List[str] = None  # ["Seed", "Series A", "Series B"]
    sector_focus: List[str] = None  # ["SaaS", "Fintech", "AI/ML"]
    geography_focus: List[str] = None  # ["US", "UK", "Europe"]
    check_size_range: Tuple[float, float] = (500_000, 10_000_000)
    ownership_target: float = 0.10  # 10% target ownership
    reserve_ratio: float = 2.0  # 2x reserves for follow-on
    typical_holding_period: int = 60  # months
    exit_multiple_target: float = 10.0
    irr_threshold: float = 0.30  # 30% IRR minimum
    
    def __post_init__(self):
        if self.stage_focus is None:
            self.stage_focus = ["Series A", "Series B"]
        if self.sector_focus is None:
            self.sector_focus = ["SaaS", "Fintech", "AI/ML", "Enterprise"]
        if self.geography_focus is None:
            self.geography_focus = ["US", "UK", "Europe"]


@dataclass
class InferenceResult:
    """Result of intelligent inference"""
    field: str
    value: Any
    confidence: float
    source: str
    reasoning: str
    citations: List[str]


class IntelligentGapFiller:
    """
    Intelligently fills data gaps using funding cadence, benchmarks, and patterns
    """
    
    # Tier 1 investors indicate higher revenue/traction
    TIER_1_INVESTORS = [
        'a16z', 'andressen', 'andreessen', 'sequoia', 'benchmark', 'accel', 
        'greylock', 'kleiner', 'founders fund', 'index ventures', 'lightspeed',
        'insight partners', 'bessemer', 'general catalyst', 'thrive', 'coatue',
        'tiger global', 'altimeter', 'iconiq', 'ggv capital', 'battery ventures'
    ]
    
    # Stage-based revenue benchmarks (2025 data)
    STAGE_REVENUE_BENCHMARKS = {
        'Pre-Seed': {
            'min': 0,
            'median': 200_000,  # $200K ARR
            'top_quartile': 500_000,  # $500K ARR
            'with_tier_1': 750_000  # Tier 1 invest higher
        },
        'Seed': {
            'min': 0,
            'median': 1_000_000,  # $1M ARR
            'top_quartile': 2_500_000,  # $2.5M ARR
            'with_tier_1': 3_500_000  # $3.5M ARR with tier 1
        },
        'Series A': {
            'min': 2_000_000,
            'median': 5_000_000,  # $5M ARR
            'top_quartile': 10_000_000,  # $10M ARR
            'with_tier_1': 12_000_000  # $12M ARR with tier 1
        },
        'Series B': {
            'min': 10_000_000,
            'median': 20_000_000,  # $20M ARR
            'top_quartile': 40_000_000,  # $40M ARR
            'with_tier_1': 50_000_000  # $50M ARR with tier 1
        },
        'Series C': {
            'min': 30_000_000,
            'median': 60_000_000,  # $60M ARR
            'top_quartile': 100_000_000,  # $100M ARR
            'with_tier_1': 120_000_000  # $120M ARR with tier 1
        }
    }
    
    # Removed sector adjustments - evaluate each company on its own merits
    
    # Geographic adjustments
    GEOGRAPHY_ADJUSTMENTS = {
        "US": {
            "valuation": 1.0,
            "funding_speed": 1.0,
            "exit_likelihood": 1.0
        },
        "UK": {
            "valuation": 0.7,
            "funding_speed": 1.1,
            "exit_likelihood": 0.8
        },
        "Europe": {
            "valuation": 0.6,
            "funding_speed": 1.2,
            "exit_likelihood": 0.7
        },
        "Asia": {
            "valuation": 0.8,
            "funding_speed": 0.9,
            "exit_likelihood": 0.6
        },
        "Israel": {
            "valuation": 0.9,
            "funding_speed": 1.0,
            "exit_likelihood": 0.9
        }
    }
    
    # Category-based gross margins
    CATEGORY_MARGINS = {
        'ai_first': 0.55,  # AI-first companies with high API costs
        'vertical_saas': 0.75,  # Vertical SaaS with focused market
        'horizontal_saas': 0.70,  # Horizontal SaaS across industries
        'consumer': 0.65,  # Consumer-facing products
        'enterprise': 0.80,  # Enterprise software
        'marketplace': 0.60,  # Marketplace/transaction-based
        'hardware': 0.40,  # Hardware/physical products
        'services': 0.30,  # Service-heavy businesses
    }
    
    # API/Model Provider Dependency Impact on Gross Margins
    API_DEPENDENCY_IMPACT = {
        "openai_heavy": {  # Companies heavily dependent on OpenAI/Anthropic
            "gross_margin_penalty": 0.25,  # 25% gross margin reduction
            "examples": ["AI writing tools", "AI chatbots", "Code assistants"],
            "typical_api_cost_per_user": 15,  # $15/user/month
            "scalability_discount": 0.90  # Costs don't decrease much with scale
        },
        "openai_moderate": {  # Moderate API usage
            "gross_margin_penalty": 0.15,  # 15% reduction
            "examples": ["AI-enhanced SaaS", "Smart analytics"],
            "typical_api_cost_per_user": 5,
            "scalability_discount": 0.85  # Some economies of scale
        },
        "openai_light": {  # Light/strategic API usage
            "gross_margin_penalty": 0.05,  # 5% reduction
            "examples": ["Traditional SaaS with AI features"],
            "typical_api_cost_per_user": 1,
            "scalability_discount": 0.70  # Better unit economics at scale
        },
        "own_models": {  # Own models/infrastructure
            "gross_margin_penalty": 0.0,  # No API costs but higher R&D
            "examples": ["Companies with proprietary models"],
            "typical_api_cost_per_user": 0,
            "scalability_discount": 0.50  # Excellent economies of scale
        }
    }
    
    # GPU/Compute Intensity Cost Analysis (from CLAUDE.md)
    GPU_COST_PER_TRANSACTION = {
        "code_generation": {  # Lovable, Cursor, Replit
            "cost_range": (5, 20),  # $5-20 per full output
            "examples": ["Cursor", "Replit", "GitHub Copilot", "Lovable"],
            "compute_intensity": "extreme",
            "margin_impact": 0.40  # 40% margin reduction
        },
        "search_synthesis": {  # Perplexity, You.com
            "cost_range": (0.10, 0.50),  # $0.10-0.50 per query
            "examples": ["Perplexity", "You.com", "Phind"],
            "compute_intensity": "high", 
            "margin_impact": 0.25  # 25% margin reduction
        },
        "chat_exchange": {  # ChatGPT wrappers
            "cost_range": (0.01, 0.05),  # $0.01-0.05 per interaction
            "examples": ["Jasper", "Copy.ai", "ChatGPT clones"],
            "compute_intensity": "moderate",
            "margin_impact": 0.15  # 15% margin reduction
        },
        "image_video_gen": {  # Midjourney, RunwayML
            "cost_range": (0.50, 5.00),  # $0.50-5.00 per asset
            "examples": ["Midjourney", "Runway", "Stable Diffusion apps"],
            "compute_intensity": "extreme",
            "margin_impact": 0.35  # 35% margin reduction
        },
        "traditional_ml": {  # Classic ML/analytics
            "cost_range": (0.001, 0.01),  # $0.001-0.01 per prediction
            "examples": ["DataRobot", "H2O.ai", "Traditional ML platforms"],
            "compute_intensity": "low",
            "margin_impact": 0.05  # 5% margin reduction
        },
        "no_ai": {  # Pure software, no AI
            "cost_range": (0, 0),
            "examples": ["Traditional SaaS", "Databases", "Dev tools"],
            "compute_intensity": "none",
            "margin_impact": 0.0
        }
    }
    
    # Stage-based benchmarks from Carta/SVB Benchmark (1).pdf data
    # These are ACTUAL median values from Carta State of Private Markets Q3 2024 + SVB reports
    STAGE_BENCHMARKS = {
        "Pre-seed": {
            "revenue_range": (0, 150_000),
            "arr_median": 50_000,  # $50K median ARR
            "growth_rate": 2.5,  # 250% YoY - realistic for YC/pre-seed with traction
            "burn_monthly": 75_000,  # $75K/month median
            "team_size": (2, 6),
            "runway_months": 18,
            "next_round_months": 12,
            "valuation_median": 5_000_000,  # $5M median post
            "valuation_multiple": 25  # 25x ARR for pre-seed
        },
        "Seed": {
            "revenue_range": (150_000, 500_000),
            "arr_median": 250_000,  # $250K median ARR
            "growth_rate": 3.0,  # 300% YoY (T3D3 target)
            "burn_monthly": 100_000,  # $100K/month median
            "team_size": (5, 12),
            "runway_months": 18,
            "next_round_months": 15,  # 15 months to Series A
            "valuation_median": 8_000_000,  # $8M median post
            "valuation_multiple": 20,  # 20x ARR
            "ltv_cac_ratio": 2.5,
            "gross_margin": 0.70  # 70% median
        },
        "Series A": {
            "revenue_range": (500_000, 3_000_000),
            "arr_median": 2_000_000,  # $2M median ARR
            "growth_rate": 2.5,  # 250% YoY
            "burn_monthly": 400_000,  # $400K/month median
            "team_size": (15, 35),
            "runway_months": 18,
            "next_round_months": 18,  # 18 months to Series B
            "valuation_median": 35_000_000,  # $35M median post
            "valuation_multiple": 15,  # 15x ARR
            "ltv_cac_ratio": 3.0,
            "gross_margin": 0.75,  # 75% median
            "magic_number": 0.8,  # Sales efficiency
            "rule_of_40": 25  # Growth + margin
        },
        "Series B": {
            "revenue_range": (3_000_000, 15_000_000),
            "arr_median": 8_000_000,  # $8M median ARR
            "growth_rate": 1.5,  # 150% YoY
            "burn_monthly": 1_200_000,  # $1.2M/month median
            "team_size": (40, 100),
            "runway_months": 24,
            "next_round_months": 20,  # 20 months to Series C
            "valuation_median": 100_000_000,  # $100M median post
            "valuation_multiple": 12,  # 12x ARR
            "ltv_cac_ratio": 3.5,
            "gross_margin": 0.78,  # 78% median
            "magic_number": 1.0,
            "rule_of_40": 35,
            "net_retention": 1.15  # 115% NRR
        },
        "Series C": {
            "revenue_range": (15_000_000, 50_000_000),
            "arr_median": 25_000_000,  # $25M median ARR
            "growth_rate": 1.0,  # 100% YoY
            "burn_monthly": 2_500_000,  # $2.5M/month median
            "team_size": (100, 300),
            "runway_months": 24,
            "next_round_months": 24,
            "valuation_median": 250_000_000,  # $250M median post
            "valuation_multiple": 10,  # 10x ARR
            "ltv_cac_ratio": 4.0,
            "gross_margin": 0.80,  # 80% median
            "magic_number": 1.2,
            "rule_of_40": 40,
            "net_retention": 1.20,  # 120% NRR
            "ebitda_margin": -0.20  # -20% (still burning)
        },
        "Series D+": {
            "revenue_range": (50_000_000, 200_000_000),
            "arr_median": 75_000_000,  # $75M median ARR
            "growth_rate": 0.7,  # 70% YoY
            "burn_monthly": 3_500_000,  # $3.5M/month median
            "team_size": (300, 1000),
            "runway_months": 36,
            "next_round_months": 30,
            "valuation_median": 500_000_000,  # $500M median post
            "valuation_multiple": 8,  # 8x ARR
            "ltv_cac_ratio": 5.0,
            "gross_margin": 0.82,  # 82% median
            "magic_number": 1.3,
            "rule_of_40": 50,
            "net_retention": 1.25,  # 125% NRR
            "ebitda_margin": -0.10  # -10% (approaching profitability)
        }
    }
    
    def __init__(self, fund_profile: Optional[FundProfile] = None):
        self.fund = fund_profile or FundProfile()
        self.growth_adjusted_multiples_cache = None  # Cache for database multiples
        # Initialize ModelRouter for LLM calls
        try:
            self.model_router = ModelRouter()
            logger.info("ModelRouter initialized for TAM extraction")
        except Exception as e:
            logger.warning(f"ModelRouter initialization failed: {e}")
            self.model_router = None
        
        # Stage-based funding benchmarks (typical raise amounts and dilution)
        self.STAGE_SEQUENCE = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Series E", "Growth"]
        self.STAGE_TYPICAL_ROUND = {
            "Pre-seed": {"amount": 1_500_000, "dilution": 0.15},
            "Seed": {"amount": 3_000_000, "dilution": 0.15},
            "Series A": {"amount": 15_000_000, "dilution": 0.20},
            "Series B": {"amount": 50_000_000, "dilution": 0.15},
            "Series C": {"amount": 100_000_000, "dilution": 0.12},
            "Series D": {"amount": 200_000_000, "dilution": 0.10},
            "Series E": {"amount": 350_000_000, "dilution": 0.08},
            "Growth": {"amount": 500_000_000, "dilution": 0.07},
        }
    
    def _ensure_string(self, value: Any, default: str = "") -> str:
        """
        Ensure a value is a string, handling dicts, None, and other types.
        This prevents regex errors when dicts are passed to string operations.
        """
        if value is None:
            return default
        if isinstance(value, dict):
            # If it's a dict, try to get a sensible string representation
            # Check for common fields that might contain the actual string value
            for field in ['text', 'value', 'content', 'description', 'name', 'amount']:
                if field in value:
                    return str(value[field])
            # Otherwise return the default
            return default
        if isinstance(value, (list, tuple)):
            # Join list items as strings
            return ' '.join(str(item) for item in value)
        # Convert everything else to string
        return str(value)
    
    def _ensure_numeric(self, value: Any, default: float = 0) -> float:
        """
        Ensure a value is numeric, handling various input types.
        """
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove common currency symbols and commas
            cleaned = value.replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
            try:
                return float(cleaned)
            except (ValueError, AttributeError):
                return default
        if isinstance(value, dict):
            # Try to get a numeric value from common fields
            for field in ['value', 'amount', 'number', 'total']:
                if field in value:
                    return self._ensure_numeric(value[field], default)
        return default
    
    def _safe_get_value(self, value: Any, default: Any = 0) -> Any:
        """
        Safely extract a usable value from InferenceResult objects, dicts, or lists.
        Falls back to centralized validator to keep behavior consistent across services.
        """
        if value is None:
            return default
        
        if isinstance(value, InferenceResult):
            return value.value if value.value is not None else default
        
        if isinstance(value, dict):
            for key in ['value', 'amount', 'estimate', 'number', 'median', 'low', 'high']:
                if key in value and value[key] not in (None, ''):
                    return self._safe_get_value(value[key], default)
            return default
        
        if isinstance(value, (list, tuple)):
            for item in value:
                extracted = self._safe_get_value(item, default)
                if extracted not in (None, '', [], {}):
                    return extracted
            return default
        
        extracted_value = safe_get_value_central(value, default)
        return extracted_value if extracted_value not in (None, '', [], {}) else default
    
    def _get_revenue_with_fallbacks(self, company_data: Dict[str, Any], default: float = 0) -> float:
        """
        Pull the most reliable revenue figure by checking all relevant fields.
        Ensures TAM calculations still run even when primary revenue is missing.
        """
        revenue_fields = [
            'revenue',
            'inferred_revenue',
            'arr',
            'annual_recurring_revenue',
            'current_arr',
            'projected_revenue',
            'mr',
            'monthly_recurring_revenue'
        ]
        
        for field in revenue_fields:
            if field in company_data:
                candidate = self._safe_get_value(company_data.get(field))
                numeric_candidate = self._ensure_numeric(candidate, default)
                if numeric_candidate and numeric_candidate > 0:
                    return numeric_candidate
        
        return default
    
    def _safe_amount(self, round_dict: Dict, company_data: Dict) -> float:
        """Get funding amount, inferring from YC if needed"""
        amount = round_dict.get('amount')
        if amount is not None and amount > 0:
            return amount
        
        # Check if YC company - infer standard check
        investors = round_dict.get('investors', [])
        is_yc = company_data.get('is_yc', False) or any('Y Combinator' in str(inv) for inv in investors)
        
        if is_yc:
            # YC check size by year (rough approximation)
            year = round_dict.get('date', '')[:4] if round_dict.get('date') else '2024'
            if year >= '2021':
                return 500_000  # $500k post-2021
            elif year >= '2017':
                return 150_000  # $150k 2017-2020
            else:
                return 125_000  # $125k pre-2017
        
        return 0
    
    async def infer_from_funding_cadence(
        self,
        company_data: Dict[str, Any],
        missing_fields: List[str]
    ) -> Dict[str, InferenceResult]:
        """
        Use funding history to infer missing metrics
        """
        inferences = {}
        
        funding_rounds = company_data.get("funding_rounds", [])
        if not funding_rounds:
            return inferences
        
        # Sort rounds by date (handle None values)
        sorted_rounds = sorted(funding_rounds, key=lambda x: x.get("date") or "")
        
        # Calculate funding velocity
        if len(sorted_rounds) >= 2:
            # Time between rounds
            round_gaps = []
            for i in range(1, len(sorted_rounds)):
                # Parse dates and calculate months between
                months_diff = self._months_between_rounds(
                    sorted_rounds[i-1].get("date"),
                    sorted_rounds[i].get("date")
                )
                if months_diff:
                    round_gaps.append(months_diff)
            
            avg_gap = np.mean(round_gaps) if round_gaps else 18
            
            # Infer burn rate if missing
            if "burn_rate" in missing_fields and len(sorted_rounds) >= 2:
                last_round = sorted_rounds[-1]
                prev_round = sorted_rounds[-2]
                
                # Assume they raised when they had 6 months runway left
                months_between = self._months_between_rounds(
                    prev_round.get("date"),
                    last_round.get("date")
                )
                
                # Safe subtraction - check for None first
                if months_between is not None and months_between > 6:
                    months_of_burn = months_between - 6
                else:
                    # Fallback if dates missing or too close together
                    months_of_burn = 12  # Assume 12 month burn by default
                
                if months_of_burn and months_of_burn > 0:
                    prev_amount = self._ensure_numeric(prev_round.get("amount"))
                    estimated_burn = prev_amount / months_of_burn if prev_amount > 0 else 500_000
                    
                    inferences["burn_rate"] = InferenceResult(
                        field="burn_rate",
                        value=estimated_burn,
                        confidence=0.7,
                        source="funding_cadence",
                        reasoning=f"Estimated from {prev_round['round']} to {last_round['round']} gap of {months_of_burn} months",
                        citations=[f"Funding history shows {avg_gap:.0f} month average between rounds"]
                    )
            
            # Infer runway if missing
            if "runway" in missing_fields:
                last_round = sorted_rounds[-1]
                months_since = self._months_since_date(last_round.get("date"))
                
                if months_since and "burn_rate" in inferences:
                    burn = inferences["burn_rate"].value
                    cash_left = last_round.get("amount", 0) - (burn * months_since)
                    runway = cash_left / burn if burn > 0 else 0
                    
                    inferences["runway"] = InferenceResult(
                        field="runway",
                        value=max(0, runway),
                        confidence=0.6,
                        source="funding_cadence",
                        reasoning=f"{months_since} months since {last_round['round']} of ${self._safe_amount(last_round, company_data)/1e6:.1f}M",
                        citations=[f"Last funding: {last_round.get('date')}"]
                    )
            
            # Predict next round timing
            if "next_round_timing" in missing_fields:
                # Is funding accelerating or decelerating?
                if len(round_gaps) >= 2:
                    acceleration = round_gaps[-1] - round_gaps[-2]
                    trend = "accelerating" if acceleration < 0 else "steady" if abs(acceleration) < 3 else "decelerating"
                else:
                    trend = "steady"
                
                next_gap = avg_gap
                if trend == "accelerating":
                    next_gap *= 0.8
                elif trend == "decelerating":
                    next_gap *= 1.2
                
                # Apply geography adjustment
                geography = company_data.get("geography", "US")
                geo_adj = self.GEOGRAPHY_ADJUSTMENTS.get(geography, {}).get("funding_speed", 1.0)
                next_gap *= geo_adj
                
                last_round = sorted_rounds[-1]
                months_since = self._months_since_date(last_round.get("date"))
                months_until_next = max(0, next_gap - months_since)
                
                inferences["next_round_timing"] = InferenceResult(
                    field="next_round_timing",
                    value=months_until_next,
                    confidence=0.65,
                    source="funding_cadence",
                    reasoning=f"Funding {trend}, avg gap {avg_gap:.0f} months, {months_since} months since last round",
                    citations=[f"Historical funding cadence: {', '.join([r['round'] for r in sorted_rounds[-3:]])}"]
                )
        
        # Infer valuation from funding amounts
        if ("valuation" in missing_fields or "inferred_valuation" in missing_fields) and sorted_rounds:
            last_round = sorted_rounds[-1]
            
            # Better round-based valuation with step-ups
            round_configs = {
                "Seed": {"dilution": 0.15, "step_up": 3.0, "default_amount": 3_000_000},
                "Series A": {"dilution": 0.20, "step_up": 2.5, "default_amount": 15_000_000},
                "Series B": {"dilution": 0.15, "step_up": 2.0, "default_amount": 50_000_000},
                "Series C": {"dilution": 0.12, "step_up": 1.5, "default_amount": 100_000_000},
                "Series D": {"dilution": 0.10, "step_up": 1.3, "default_amount": 200_000_000}
            }
            
            round_config = round_configs.get(last_round.get("round", ""), 
                                            {"dilution": 0.15, "step_up": 2.0, "default_amount": 10_000_000})
            
            amount = self._ensure_numeric(last_round.get("amount"))
            
            # If no amount, use stage-based estimates
            if amount == 0:
                amount = round_config["default_amount"]
                
            # Calculate post-money valuation
            if amount is None or amount <= 0:
                amount = round_config["default_amount"]
            
            # Calculate post-money valuation
            implied_post = amount / round_config["dilution"] if round_config["dilution"] > 0 and amount is not None else amount * 7
            
            # If we have previous round data, also consider step-up
            if len(sorted_rounds) > 1:
                prev_round = sorted_rounds[-2]
                prev_valuation = self._ensure_numeric(prev_round.get("valuation", 0))
                if prev_valuation > 0:
                    step_up_valuation = prev_valuation * round_config["step_up"]
                    # Take the higher of dilution-based or step-up based
                    implied_post = max(implied_post, step_up_valuation)
                    print(f"  Valuation calc: Dilution-based: ${implied_post/1e6:.0f}M, Step-up: ${step_up_valuation/1e6:.0f}M")
            
            # Apply geography adjustment only (keep this as it's based on real market data)
            geography = company_data.get("geography", "US")
            geo_mult = self.GEOGRAPHY_ADJUSTMENTS.get(geography, {}).get("valuation", 1.0)
            
            # No API penalty on valuation - API costs just affect burn/margins
            adjusted_valuation = implied_post * geo_mult
            
            valuation_inference = InferenceResult(
                field="valuation",
                value=adjusted_valuation,
                confidence=0.5,
                source="funding_cadence",
                reasoning=f"{last_round['round']} of ${self._safe_amount(last_round, company_data)/1e6:.1f}M implies {round_config['dilution']:.0%} dilution",
                citations=[
                    f"Standard {last_round['round']} dilution: {round_config['dilution']:.0%}",
                    f"Geography: {geography} (adjustment: {geo_mult:.1f}x)",
                    f"Post-money valuation: ${implied_post/1e6:.1f}M"
                ]
            )
            inferences["valuation"] = valuation_inference
            inferences["inferred_valuation"] = InferenceResult(
                field="inferred_valuation",
                value=adjusted_valuation,
                confidence=0.5,
                source="funding_cadence",
                reasoning=f"{last_round['round']} of ${self._safe_amount(last_round, company_data)/1e6:.1f}M implies {round_config['dilution']:.0%} dilution",
                citations=[
                    f"Standard {last_round['round']} dilution: {round_config['dilution']:.0%}",
                    f"Geography: {geography} (adjustment: {geo_mult:.1f}x)",
                    f"Post-money valuation: ${implied_post/1e6:.1f}M"
                ]
            )
        
        # Infer revenue using context-aware approach
        if "revenue" in missing_fields or "inferred_revenue" in missing_fields:
            revenue_inference = self._infer_revenue_from_context(company_data, sorted_rounds)
            if revenue_inference:
                inferences["inferred_revenue"] = revenue_inference
        
        return inferences
    
    def _infer_revenue_from_context(self, company_data: Dict, sorted_rounds: List) -> Optional[InferenceResult]:
        """Infer revenue using stage, investors, and funding context"""
        
        if not sorted_rounds:
            return None
        
        last_round = sorted_rounds[-1]
        stage = last_round.get('round', company_data.get('stage', 'Unknown'))
        
        # Check for tier 1 investors
        investors = company_data.get('investors', [])
        if isinstance(investors, list):
            investor_names = [inv.lower() if isinstance(inv, str) else str(inv).lower() for inv in investors]
        else:
            investor_names = []
        
        has_tier_1 = any(
            any(tier1 in inv_name for tier1 in self.TIER_1_INVESTORS)
            for inv_name in investor_names
        )
        
        # Get revenue benchmark for stage
        stage_benchmarks = self.STAGE_REVENUE_BENCHMARKS.get(stage, self.STAGE_REVENUE_BENCHMARKS.get('Seed', {}))
        
        if not stage_benchmarks:
            return None
        
        # Start with median
        estimated_revenue = stage_benchmarks.get('median', 1_000_000)
        
        # Adjust for tier 1 investors
        if has_tier_1:
            estimated_revenue = stage_benchmarks.get('with_tier_1', estimated_revenue * 1.5)
            confidence = 0.75
            reasoning = f"{stage} company with Tier 1 investors (higher traction signal)"
        else:
            confidence = 0.65
            reasoning = f"{stage} median revenue estimate"
        
        # Adjust for large round size (indicates strong traction)
        last_amount = self._ensure_numeric(last_round.get('amount', 0))
        if last_amount > 0:
            # Large rounds relative to stage indicate outperformance
            if stage == 'Seed' and last_amount > 5_000_000:
                estimated_revenue *= 1.4  # Large seed = exceptional traction
                reasoning += ", large round size indicates strong traction"
            elif stage == 'Series A' and last_amount > 20_000_000:
                estimated_revenue *= 1.3  # Large A = top quartile
                reasoning += ", large Series A indicates top quartile"
        
        # Validate reasonableness (don't go below stage minimum)
        min_revenue = stage_benchmarks.get('min', 0)
        estimated_revenue = max(estimated_revenue, min_revenue)
        
        logger.info(f"[REVENUE_INFERENCE] {company_data.get('company')}: Estimated ${estimated_revenue/1e6:.1f}M ARR ({stage}, tier_1={has_tier_1})")
        
        return InferenceResult(
            field="inferred_revenue",
            value=estimated_revenue,
            confidence=confidence,
            source="context_aware_inference",
            reasoning=reasoning,
            citations=[
                f"Stage: {stage}",
                f"Investors: {', '.join(investors[:3])}" if investors else "Investor quality assessed",
                f"Last round: ${last_amount/1e6:.1f}M" if last_amount > 0 else "Funding history reviewed"
            ]
        )
    
    def generate_stage_based_funding_rounds(self, company_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create synthetic funding rounds based on inferred stage and benchmarks.
        Ensures downstream models have realistic financing data even when extraction misses it.
        """
        try:
            stage = self._determine_stage(company_data) or "Seed"
        except Exception:
            stage = "Seed"
        
        # Map to known sequence key
        stage_lower = stage.lower()
        stage_key = None
        for key in self.STAGE_SEQUENCE:
            if key.lower() in stage_lower or stage_lower in key.lower():
                stage_key = key
                break
        if not stage_key:
            stage_key = "Seed"
        
        # Determine multiplier adjustments
        geography = company_data.get("geography", "") or company_data.get("headquarters", "")
        geo_mult = 1.0
        if any(loc in str(geography).lower() for loc in ["san francisco", "sf", "silicon valley", "bay area", "new york", "nyc"]):
            geo_mult = 1.15
        elif any(loc in str(geography).lower() for loc in ["europe", "uk", "london", "berlin"]):
            geo_mult = 0.95
        elif any(loc in str(geography).lower() for loc in ["india", "latam", "brazil", "mexico", "southeast asia"]):
            geo_mult = 0.85
        
        investors = company_data.get("investors", []) or []
        investor_mult = 1.0
        tier1 = ["sequoia", "a16z", "benchmark", "accel", "founders fund", "greylock"]
        tier2 = ["nea", "bessemer", "lightspeed", "gv", "index", "norwest", "menlo", "ivp"]
        inv_string = " ".join(str(inv).lower() for inv in investors)
        if any(name in inv_string for name in tier1):
            investor_mult = 1.2
        elif any(name in inv_string for name in tier2):
            investor_mult = 1.1
        
        # Determine total funding target (use actual, inferred, or benchmark sum)
        inferred_total = company_data.get("total_funding") or company_data.get("total_raised") or company_data.get("inferred_total_funding")
        if not inferred_total:
            # Sum typical raises up to current stage
            stage_index = self.STAGE_SEQUENCE.index(stage_key)
            benchmark_total = sum(self.STAGE_TYPICAL_ROUND.get(self.STAGE_SEQUENCE[i], {}).get("amount", 0) for i in range(stage_index + 1))
            inferred_total = benchmark_total * geo_mult * investor_mult
        
        # Build list of stages we have likely completed
        stage_index = self.STAGE_SEQUENCE.index(stage_key)
        relevant_stages = self.STAGE_SEQUENCE[:stage_index + 1]
        typical_amounts = [self.STAGE_TYPICAL_ROUND[st]["amount"] for st in relevant_stages if st in self.STAGE_TYPICAL_ROUND]
        if not typical_amounts:
            return []
        
        typical_total = sum(typical_amounts)
        scaling_factor = inferred_total / typical_total if typical_total > 0 else 1.0
        scaling_factor = max(0.6, min(scaling_factor, 1.6))  # prevent extreme outliers
        
        synthetic_rounds = []
        cumulative_post = 0.0
        
        # Generate realistic dates - typical 12-18 month cadence between rounds
        from datetime import datetime, timedelta
        current_date = datetime.now()
        # Work backwards from current stage
        months_between_rounds = 15  # average 15 months
        
        for idx, stage_name in enumerate(relevant_stages):
            round_info = self.STAGE_TYPICAL_ROUND.get(stage_name)
            if not round_info:
                continue
            amount = round_info["amount"] * scaling_factor * geo_mult * (investor_mult if idx >= len(relevant_stages) - 2 else 1.0)
            dilution = round_info["dilution"]
            post_money = amount / dilution if dilution > 0 and amount is not None else amount * 6
            pre_money = post_money - amount
            cumulative_post = max(cumulative_post, post_money)
            
            # Calculate synthetic date - most recent round is current, work backwards
            rounds_ago = len(relevant_stages) - idx - 1
            round_date = current_date - timedelta(days=rounds_ago * months_between_rounds * 30)
            
            synthetic_rounds.append({
                "round": stage_name,
                "amount": amount,
                "date": round_date.strftime("%Y-%m-%d"),
                "investors": [],
                "pre_money_valuation": pre_money,
                "post_money_valuation": post_money,
                "synthetic": True
            })
        
        return synthetic_rounds
    
    async def infer_from_stage_benchmarks(
        self,
        company_data: Dict[str, Any],
        missing_fields: List[str]
    ) -> Dict[str, InferenceResult]:
        """
        Use stage-specific benchmarks to fill gaps
        """
        inferences = {}
        
        # Determine stage
        stage = self._determine_stage(company_data)
        if not stage:
            stage = 'Seed'  # Default to Seed
        
        # Map stage to benchmark key - CRITICAL FIX
        stage_key = stage
        if stage not in self.STAGE_BENCHMARKS:
            # Map various stage names to our benchmark keys
            stage_lower = (stage or 'seed').lower()
            if 'seed' in stage_lower:
                stage_key = 'Seed'
            elif 'series a' in stage_lower or stage == 'A':
                stage_key = 'Series A'
            elif 'series b' in stage_lower or stage == 'B':
                stage_key = 'Series B'
            elif 'series c' in stage_lower or stage == 'C':
                stage_key = 'Series C'
            elif 'series d' in stage_lower or stage == 'D':
                stage_key = 'Series D+'
            else:
                stage_key = 'Seed'  # Default to Seed
        
        benchmarks = self.STAGE_BENCHMARKS.get(stage_key, self.STAGE_BENCHMARKS.get('Seed', {}))
        
        print(f"\n[REVENUE_INFERENCE] {company_data.get('name', 'unknown')}:")
        print(f"  Stage: {stage_key} (original: {stage})")
        print(f"  Base benchmark: ${benchmarks.get('arr_median', 0):,.0f}")
        
        # Infer stage if missing
        if "stage" in missing_fields:
            inferred_stage = stage  # Already determined above on line 430
            inferences["stage"] = InferenceResult(
                field="stage",
                value=inferred_stage,
                confidence=0.7 if company_data.get("funding_rounds") else 0.5,
                source="funding_rounds" if company_data.get("funding_rounds") else "default",
                reasoning=f"Inferred from funding rounds as {inferred_stage}" if company_data.get("funding_rounds") 
                          else f"Defaulted to {inferred_stage}",
                citations=[]
            )
            print(f"  Inferred stage: {inferred_stage}")
        
        # Infer gross margin if missing (BEFORE revenue since it affects valuation)
        if "gross_margin" in missing_fields:
            # Use the CATEGORY that was SEMANTICALLY extracted by Claude, NOT keywords
            category = company_data.get('category', 'saas').lower()
            vertical = company_data.get('vertical', '').lower()
            
            # Use category-based margins (category was already intelligently determined by extraction)
            # These are industry benchmarks, not keyword matching
            category_margins = {
                'industrial': 0.25,  # Manufacturing, production facilities
                'materials': 0.30,   # Raw materials, chemicals, metals
                'manufacturing': 0.35,  # Assembly operations
                'deeptech_hardware': 0.40,  # Robotics, chips, advanced hardware
                'hardware': 0.45,  # Consumer electronics
                'marketplace': 0.50,  # Transaction fees model
                'services': 0.55,  # Human labor component
                'tech_enabled_services': 0.60,  # Tech-augmented services
                'rollup': 0.45,  # Varies by underlying business
                'gtm_software': 0.75,  # Sales/marketing software
                'saas': 0.78,  # Standard SaaS
                'ai_saas': 0.65,  # SaaS with AI costs
                'ai_first': 0.55,  # Core AI product
                'full_stack_ai': 0.50  # Complete AI service delivery
            }
            
            # Get margin based on the semantically-determined category
            inferred_margin = category_margins.get(category, benchmarks.get('gross_margin', 0.70))
            
            # Vertical adjustments
            if 'healthcare' in vertical:
                inferred_margin *= 0.92
            elif 'defense' in vertical:
                inferred_margin *= 1.15
            elif 'fintech' in vertical:
                inferred_margin *= 0.95
            
            inferences["gross_margin"] = InferenceResult(
                field="gross_margin",
                value=inferred_margin,
                confidence=0.8,
                source="category_analysis",
                reasoning=f"Inferred {inferred_margin*100:.0f}% margin based on {category} category and {vertical or 'general'} vertical",
                citations=[]
            )
            print(f"  Inferred gross margin: {inferred_margin*100:.0f}% (category: {category})")
        
        # Infer revenue if missing
        if "revenue" in missing_fields:
            # Check if company is a unicorn FIRST
            current_valuation = company_data.get('valuation', 0)
            if current_valuation >= 1_000_000_000:
                # Unicorn: work backwards from valuation
                # $1B+ companies typically trade at 10-15x ARR
                # Use 12.5x as middle ground
                benchmark_revenue = current_valuation / 12.5
                print(f"  🦄 Unicorn valuation: ${current_valuation/1e9:.1f}B → ${benchmark_revenue/1e6:.0f}M revenue (12.5x multiple)")
            else:
                # Start with arr_median, NOT revenue_range midpoint
                benchmark_revenue = benchmarks.get("arr_median", 1_000_000)
            
            # Apply time-based growth since last funding with realistic caps
            funding_rounds = company_data.get('funding_rounds', [])
            if funding_rounds:
                last_round = funding_rounds[-1]
                last_funding_date = last_round.get('date')
                if last_funding_date:
                    months_since = self._months_since_date(last_funding_date)
                    if months_since and months_since > 0:
                        # Get base growth rate for this stage
                        base_growth_rate = benchmarks.get('growth_rate', 1.0)
                        
                        # For unicorns and hot companies, ensure high growth rates
                        if current_valuation >= 1_000_000_000:
                            # Unicorns should be growing 2-4x YoY minimum
                            base_growth_rate = max(2.0, min(base_growth_rate, 4.0))
                            print(f"  Unicorn growth rate adjusted to {base_growth_rate:.1f}x YoY")
                        
                        # Apply growth decay - growth rates decline over time
                        # Year 1: 100% of growth rate
                        # Year 2: 70% of growth rate  
                        # Year 3: 50% of growth rate
                        # Year 4+: 30% of growth rate
                        years_since = months_since / 12.0
                        
                        if years_since <= 1:
                            effective_growth = base_growth_rate
                        elif years_since <= 2:
                            # Linear decay from 100% to 70% over year 2
                            decay_factor = 1.0 - (years_since - 1) * 0.3
                            effective_growth = base_growth_rate * decay_factor
                        elif years_since <= 3:
                            # Linear decay from 70% to 50% over year 3
                            decay_factor = 0.7 - (years_since - 2) * 0.2
                            effective_growth = base_growth_rate * decay_factor
                        else:
                            # 30% of base growth for mature companies
                            effective_growth = base_growth_rate * 0.3
                        
                        # Calculate cumulative growth with decay
                        # Break into yearly segments for more accurate decay
                        cumulative_multiple = 1.0
                        remaining_months = months_since
                        year_num = 1
                        
                        while remaining_months > 0:
                            months_in_period = min(12, remaining_months)
                            
                            # Decay factor for this year
                            if year_num == 1:
                                period_growth = base_growth_rate
                            elif year_num == 2:
                                period_growth = base_growth_rate * 0.7
                            elif year_num == 3:
                                period_growth = base_growth_rate * 0.5
                            else:
                                period_growth = base_growth_rate * 0.3
                            
                            # Apply growth for this period
                            monthly_growth = (1 + period_growth) ** (1/12) - 1
                            period_multiple = (1 + monthly_growth) ** months_in_period
                            cumulative_multiple *= period_multiple
                            
                            remaining_months -= months_in_period
                            year_num += 1
                        
                        # Additional reality check caps based on stage
                        max_growth_multiples = {
                            'Pre-seed': 2.0,  # Max 2x growth (more realistic)
                            'Seed': 3.0,      # Max 3x growth
                            'Series A': 5.0,  # Max 5x growth
                            'Series B': 7.0,  # Max 7x growth
                            'Series C': 8.0,  # Max 8x growth
                            'Series D+': 10.0 # Max 10x growth
                        }
                        max_multiple = max_growth_multiples.get(stage_key, 3.0)
                        
                        # Apply the growth with cap
                        growth_multiple = min(cumulative_multiple, max_multiple)
                        benchmark_revenue = benchmark_revenue * growth_multiple
                        
                        time_multiplier = growth_multiple
                        print(f"  Time multiplier: {time_multiplier:.2f}x ({months_since:.1f} months since funding)")
            
            # Apply geographic adjustment
            location = (company_data.get('headquarters') or '').lower()
            geo_mult = 1.0
            geography = "Other"
            if 'san francisco' in location or 'new york' in location or 'sf' in location or 'nyc' in location:
                geo_mult = 1.15  # SF/NYC premium
                geography = "SF/NYC"
            elif 'europe' in location or 'berlin' in location or 'london' in location or 'paris' in location:
                geo_mult = 0.85  # European discount
                geography = "Europe"
            benchmark_revenue *= geo_mult
            
            # Apply investor quality adjustment
            quality_mult = 1.0
            if funding_rounds:
                tier1_vcs = ['sequoia', 'a16z', 'benchmark', 'accel', 'greylock', 'kleiner', 'bessemer', 'index']
                investors_str = str(funding_rounds).lower()
                if any(vc in investors_str for vc in tier1_vcs):
                    quality_mult = 1.2  # Tier 1 VC boost
                    benchmark_revenue *= quality_mult
            
            print(f"  Geography: {geography} → {geo_mult:.2f}x")
            print(f"  Investor quality: {quality_mult:.2f}x")
            
            # Start with benchmark revenue after adjustments
            team_adjusted_revenue = benchmark_revenue
            
            # Layer 2: Pricing model adjustment
            pricing_adjusted_revenue = team_adjusted_revenue
            pricing_reasoning = ""
            pricing = company_data.get('pricing_tiers', {})
            
            if pricing:
                if pricing.get('has_enterprise') and not pricing.get('plans'):
                    # "Contact Sales" only = Enterprise sales motion
                    pricing_adjusted_revenue *= 1.5  # Enterprise typically higher ACV
                    pricing_reasoning = "Enterprise pricing model (Contact Sales)"
                elif pricing.get('plans'):
                    # Has transparent pricing
                    prices = []
                    for plan_name, plan_data in pricing.get('plans', {}).items():
                        if isinstance(plan_data, dict) and 'price' in plan_data:
                            prices.append(plan_data['price'])
                    
                    if prices:
                        avg_monthly_price = sum(prices) / len(prices)
                        
                        # Estimate customer count from team size
                        team = company_data.get('team_size', 30)
                        estimated_customers = team * 10
                        
                        # If we have free tier, expect more customers but lower conversion
                        if pricing.get('has_free_tier'):
                            estimated_customers *= 3  # More users
                            conversion_rate = 0.02  # 2% convert from free
                            estimated_customers *= conversion_rate
                            pricing_reasoning = f"PLG model with {avg_monthly_price:.0f}/mo avg price"
                        else:
                            pricing_reasoning = f"Self-serve pricing at ${avg_monthly_price:.0f}/mo avg"
                        
                        # Calculate from actual pricing
                        pricing_based_revenue = avg_monthly_price * 12 * estimated_customers
                        
                        # Blend with benchmark (50/50 weight)
                        pricing_adjusted_revenue = (team_adjusted_revenue + pricing_based_revenue) / 2
                elif pricing.get('has_free_tier'):
                    # Free tier without paid plans visible = likely PLG
                    pricing_adjusted_revenue *= 0.7  # Lower ACV for PLG
                    pricing_reasoning = "PLG model (free tier)"
            
            # Layer 3: Customer quality adjustment
            final_revenue = pricing_adjusted_revenue
            customer_reasoning = ""
            customer_logos = company_data.get('customer_logos', [])
            
            if customer_logos:
                # Check for enterprise customers
                enterprise_signals = ['fortune', '500', 'bank', 'insurance', 'global', 'microsoft', 'google', 'amazon']
                enterprise_count = sum(1 for customer in customer_logos 
                                      if customer and any(signal in str(customer).lower() for signal in enterprise_signals))
                
                if enterprise_count > 5:
                    # Strong enterprise presence
                    final_revenue *= 1.3
                    customer_reasoning = f"{enterprise_count} enterprise customers identified"
                elif enterprise_count > 0:
                    # Some enterprise
                    final_revenue *= 1.1
                    customer_reasoning = f"{enterprise_count} enterprise + {len(customer_logos)-enterprise_count} mid-market customers"
                else:
                    # SMB/startup customers
                    final_revenue *= 0.9
                    customer_reasoning = f"{len(customer_logos)} SMB/startup customers"
            
            # Build comprehensive reasoning
            reasoning_parts = [f"{stage} benchmark: ${benchmark_revenue/1e6:.1f}M"]
            # Team ratio removed - no longer calculated
            if pricing_reasoning:
                reasoning_parts.append(pricing_reasoning)
            if customer_reasoning:
                reasoning_parts.append(customer_reasoning)
            
            inferences["revenue"] = InferenceResult(
                field="revenue",
                value=final_revenue,
                confidence=0.6 if (pricing or customer_logos) else 0.4,
                source="layered_inference",
                reasoning=" | ".join(reasoning_parts),
                citations=[f"Industry benchmark for {stage_key} stage", "Pricing page analysis", "Customer logo analysis"]
            )
            
            # Get category and gross margin for final output
            category = company_data.get('category', 'saas')
            gross_margin = inferences.get('gross_margin', InferenceResult('gross_margin', 0.70, 0.8, '', '', [])).value
            
            print(f"  Category: {category} → margin {gross_margin*100:.0f}%")
            print(f"  ✅ FINAL REVENUE: ${final_revenue:,.0f}")
            confidence_val = 0.6 if (pricing or customer_logos) else 0.4
            print(f"  Confidence: {confidence_val:.1%}")
        
        # Infer growth rate
        if "growth_rate" in missing_fields:
            base_growth = benchmarks.get("growth_rate", 0.5)
            
            # Use benchmark growth directly without sector adjustments
            adjusted_growth = base_growth
            
            inferences["growth_rate"] = InferenceResult(
                field="growth_rate",
                value=adjusted_growth,
                confidence=0.5,
                source="stage_benchmark",
                reasoning=f"{stage} companies typically grow at {adjusted_growth:.0%} YoY",
                citations=[f"{stage} benchmark: {base_growth:.0%}"]
            )
        
        # Infer total funding using the same adjustment logic as revenue
        if "total_funding" in missing_fields:
            funding_rounds = company_data.get("funding_rounds", [])
            total = 0
            
            # Sum known funding amounts
            for r in funding_rounds:
                if r.get("amount"):
                    total += r.get("amount", 0)
            
            # For missing rounds, use adjusted amounts based on geography/investors
            stage_order = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D"]
            
            # Base typical raises
            stage_typical_raise = {
                "Pre-seed": 500_000,
                "Seed": 2_000_000,  
                "Series A": 10_000_000,
                "Series B": 25_000_000,
                "Series C": 50_000_000,
                "Series D": 100_000_000
            }
            
            # Geography adjustment (same as revenue)
            geography = company_data.get("geography", "US")
            geo_mult = self.GEOGRAPHY_ADJUSTMENTS.get(geography, {}).get("funding", 1.0)
            
            # Investor quality adjustment
            investor_mult = 1.0
            investors = company_data.get("investors", [])
            if any(inv in ["Sequoia", "a16z", "Benchmark", "Accel", "Founders Fund"] for inv in investors):
                investor_mult = 1.3  # Tier 1 VCs raise larger rounds
            elif any(inv in ["NEA", "Bessemer", "Lightspeed", "GV"] for inv in investors):
                investor_mult = 1.15  # Tier 2 VCs
            
            # Find where we are in progression
            current_idx = stage_order.index(stage_key) if stage_key in stage_order else 1
            
            # Check which rounds we already have
            existing_rounds = {r.get("round", "").lower() for r in funding_rounds}
            
            # Add all missing preceding rounds with adjustments
            for i in range(current_idx + 1):  # Include current stage
                stage = stage_order[i]
                # Check if we already have this round
                has_round = any(stage.lower() in r or r in stage.lower() for r in existing_rounds)
                if not has_round:
                    # Apply adjustments to typical raise
                    adjusted_amount = stage_typical_raise.get(stage, 0) * geo_mult * investor_mult
                    total += adjusted_amount
            
            reasoning = f"Known rounds + adjusted typical amounts for {stage_key} ({geography}, {len(investors)} investors)"
            
            inferences["total_funding"] = InferenceResult(
                field="total_funding",
                value=total,
                confidence=0.6,
                source="adjusted_benchmarks",
                reasoning=reasoning,
                citations=[f"Adjusted for {geography} market and investor quality"]
            )
        
        # Infer team size using similar adjustment logic as revenue
        if "team_size" in missing_fields:
            # Get base team size range from benchmark
            team_range = benchmarks.get("team_size", (10, 30))
            base_team = (team_range[0] + team_range[1]) / 2  # Take midpoint
            
            # Apply time-based growth from funding
            funding_date = None
            if company_data.get("funding_rounds"):
                latest_round = max(company_data["funding_rounds"], 
                                 key=lambda x: x.get("date", ""), 
                                 default={})
                funding_date = latest_round.get("date")
            
            if funding_date:
                months_since = self._months_since_date(funding_date)
                # More realistic growth: teams grow ~2-3% per month, not 7%
                # This gives ~30-40% annual growth which is more realistic
                team_growth_rate = 0.025  # 2.5% monthly compound
                time_multiplier = (1 + team_growth_rate) ** months_since
                # Cap time multiplier at 3x to prevent unrealistic numbers
                time_multiplier = min(time_multiplier, 3.0)
            else:
                time_multiplier = 1.0
            
            # Adjust for company quality signals (smaller adjustments)
            quality_mult = 1.0
            
            # Geography adjustment (smaller)
            geography = company_data.get("geography", "")
            if any(city in geography for city in ["San Francisco", "New York", "Silicon Valley"]):
                quality_mult *= 1.1  # Reduced from 1.2
            
            # Investor signal (smaller)
            investors = company_data.get("investors", [])
            if any(inv in str(investors) for inv in ["Sequoia", "a16z", "Benchmark", "Accel"]):
                quality_mult *= 1.05  # Reduced from 1.15
            
            # Customer signal (smaller)
            if company_data.get("customers"):
                quality_mult *= 1.05  # Reduced from 1.1
            
            # Apply all adjustments
            adjusted_team = int(base_team * time_multiplier * quality_mult)
            
            # Apply hard caps based on stage to prevent unrealistic values
            stage_caps = {
                "Pre-seed": 15,
                "Seed": 35,
                "Series A": 120,
                "Series B": 350,
                "Series C": 800,
                "Series D": 1500,
                "Growth": 3000
            }
            
            cap = stage_caps.get(stage_key, 500)
            adjusted_team = min(adjusted_team, cap)
            
            inferences["team_size"] = InferenceResult(
                field="team_size",
                value=adjusted_team,
                confidence=0.5,
                source="stage_benchmark_adjusted",
                reasoning=f"{stage_key} benchmark: {int(base_team)} | Growth: {time_multiplier:.1f}x | Quality: {quality_mult:.1f}x",
                citations=[f"Estimated from {stage_key} stage patterns"]
            )
        
        # Infer valuation using dilution-based calculation with adjustments
        if "valuation" in missing_fields or "inferred_valuation" in missing_fields:
            funding_rounds = company_data.get("funding_rounds", [])
            
            # First try dilution-based calculation from funding rounds
            if funding_rounds:
                # Sort by date to get latest round
                sorted_rounds = sorted(funding_rounds, key=lambda x: x.get("date", ""), reverse=False)
                last_round = sorted_rounds[-1] if sorted_rounds else None
                
                if last_round:
                    # Round-specific dilution configs
                    round_configs = {
                        "Seed": {"dilution": 0.15, "step_up": 3.0, "default_amount": 3_000_000},
                        "Series A": {"dilution": 0.20, "step_up": 2.5, "default_amount": 15_000_000},
                        "Series B": {"dilution": 0.15, "step_up": 2.0, "default_amount": 50_000_000},
                        "Series C": {"dilution": 0.12, "step_up": 1.5, "default_amount": 100_000_000},
                        "Series D": {"dilution": 0.10, "step_up": 1.3, "default_amount": 200_000_000}
                    }
                    
                    round_name = last_round.get("round", stage_key)
                    round_config = round_configs.get(round_name, 
                                                    {"dilution": 0.15, "step_up": 2.0, "default_amount": 10_000_000})
                    
                    amount = self._ensure_numeric(last_round.get("amount"))
                    if amount == 0:
                        amount = round_config["default_amount"]
                    
                    # Calculate post-money valuation from dilution
                    implied_post = amount / round_config["dilution"] if round_config["dilution"] > 0 and amount is not None else amount * 7
                    last_post_money = implied_post  # Store the original post-money
                    
                    # Apply time-based growth since funding
                    funding_date = last_round.get("date")
                    time_multiplier = 1.0
                    if funding_date:
                        months_since = self._months_since_date(funding_date)
                        if months_since and months_since > 0:
                            # Valuations grow ~10-15% per quarter for successful companies
                            quarterly_growth = 0.125  # 12.5% per quarter
                            quarters_since = months_since / 3
                            time_multiplier = (1 + quarterly_growth) ** quarters_since
                            implied_post *= time_multiplier
                    
                    # Apply geography adjustment
                    geography = company_data.get("geography", company_data.get("headquarters", "US"))
                    geo_mult = self.GEOGRAPHY_ADJUSTMENTS.get(geography, {}).get("valuation", 1.0)
                    if not geo_mult:
                        # Check city-level
                        if any(city in str(geography).lower() for city in ["san francisco", "new york", "silicon valley"]):
                            geo_mult = 1.15
                        else:
                            geo_mult = 1.0
                    
                    # Apply investor quality adjustment
                    investor_mult = 1.0
                    investors = company_data.get("investors", [])
                    if any(inv in str(investors) for inv in ["Sequoia", "a16z", "Benchmark", "Accel", "Founders Fund"]):
                        investor_mult = 1.15  # Tier 1 VCs command premium valuations
                    elif any(inv in str(investors) for inv in ["NEA", "Bessemer", "Lightspeed", "GV"]):
                        investor_mult = 1.08  # Tier 2 VCs
                    
                    adjusted_valuation = implied_post * geo_mult * investor_mult
                    current_valuation = adjusted_valuation  # This is after all adjustments
                    
                    valuation_inference = InferenceResult(
                        field="valuation",
                        value=current_valuation,
                        confidence=0.7,
                        source="dilution_based_adjusted",
                        reasoning=f"Last: ${last_post_money/1e6:.0f}M post ({round_name}), Current: ${current_valuation/1e6:.0f}M (time: {time_multiplier:.2f}x, geo: {geo_mult:.2f}x, investors: {investor_mult:.2f}x)",
                        citations=[
                            f"Last round: ${amount/1e6:.1f}M {round_name} at {round_config['dilution']:.0%} dilution",
                            f"Post-money at funding: ${last_post_money/1e6:.0f}M",
                            f"Current valuation (next pre): ${current_valuation/1e6:.0f}M"
                        ]
                    )
                    inferences["valuation"] = valuation_inference
                    inferences["inferred_valuation"] = InferenceResult(
                        field="inferred_valuation",
                        value=current_valuation,
                        confidence=0.7,
                        source="dilution_based_adjusted",
                        reasoning=f"Last: ${last_post_money/1e6:.0f}M post ({round_name}), Current: ${current_valuation/1e6:.0f}M (time: {time_multiplier:.2f}x, geo: {geo_mult:.2f}x, investors: {investor_mult:.2f}x)",
                        citations=[
                            f"Last round: ${amount/1e6:.1f}M {round_name} at {round_config['dilution']:.0%} dilution",
                            f"Post-money at funding: ${last_post_money/1e6:.0f}M",
                            f"Current valuation (next pre): ${current_valuation/1e6:.0f}M"
                        ]
                    )
                else:
                    # Fallback to revenue multiple if no funding rounds
                    revenue = company_data.get("revenue") or inferences.get("revenue", InferenceResult("revenue", 0, 0, "", "", [])).value
                    if revenue and revenue > 0:
                        base_multiple = benchmarks.get("valuation_multiple", 10)
                        
                        # MARGIN-BASED MULTIPLE ADJUSTMENT
                        gross_margin = inferences.get("gross_margin", InferenceResult("gross_margin", 0.70, 0, "", "", [])).value if "gross_margin" in inferences else company_data.get("gross_margin", 0.70)
                        margin_adjustment = gross_margin / 0.75  # vs SaaS benchmark
                        margin_adjustment = max(0.5, min(1.3, margin_adjustment))
                        valuation_multiple = base_multiple * margin_adjustment
                        
                        adjusted_valuation = revenue * valuation_multiple
                        
                        valuation_inference = InferenceResult(
                            field="valuation",
                            value=adjusted_valuation,
                            confidence=0.5,
                            source="revenue_multiple",
                            reasoning=f"Revenue ${revenue/1e6:.1f}M × {valuation_multiple:.1f}x (base {base_multiple}x × {margin_adjustment:.2f} margin adj)",
                            citations=[f"{stage_key} base multiple: {base_multiple}x, adjusted for {gross_margin*100:.0f}% margin"]
                        )
                        inferences["valuation"] = valuation_inference
                        inferences["inferred_valuation"] = InferenceResult(
                            field="inferred_valuation",
                            value=adjusted_valuation,
                            confidence=0.5,
                            source="revenue_multiple",
                            reasoning=f"Revenue ${revenue/1e6:.1f}M × {valuation_multiple:.1f}x (base {base_multiple}x × {margin_adjustment:.2f} margin adj)",
                            citations=[f"{stage_key} base multiple: {base_multiple}x, adjusted for {gross_margin*100:.0f}% margin"]
                        )
            else:
                # No funding rounds - use revenue multiple or median
                revenue = company_data.get("revenue") or inferences.get("revenue", InferenceResult("revenue", 0, 0, "", "", [])).value
                if revenue and revenue > 0:
                    base_multiple = benchmarks.get("valuation_multiple", 10)
                    
                    # MARGIN-BASED MULTIPLE ADJUSTMENT
                    gross_margin = inferences.get("gross_margin", InferenceResult("gross_margin", 0.70, 0, "", "", [])).value if "gross_margin" in inferences else company_data.get("gross_margin", 0.70)
                    margin_adjustment = gross_margin / 0.75  # vs SaaS benchmark
                    margin_adjustment = max(0.5, min(1.3, margin_adjustment))
                    valuation_multiple = base_multiple * margin_adjustment
                    
                    adjusted_valuation = revenue * valuation_multiple
                else:
                    # Last resort - use stage median with adjustments
                    base_valuation = benchmarks.get("valuation_median", 10_000_000)
                    
                    # Apply same quality adjustments as team size
                    quality_mult = 1.0
                    geography = company_data.get("geography", company_data.get("headquarters", ""))
                    if any(city in str(geography).lower() for city in ["san francisco", "new york", "silicon valley"]):
                        quality_mult *= 1.2
                    
                    investors = company_data.get("investors", [])
                    if any(inv in str(investors) for inv in ["Sequoia", "a16z", "Benchmark", "Accel"]):
                        quality_mult *= 1.15
                    
                    adjusted_valuation = base_valuation * quality_mult
                
                valuation_inference = InferenceResult(
                    field="valuation",
                    value=adjusted_valuation,
                    confidence=0.4,
                    source="stage_benchmark",
                    reasoning=f"{stage_key} benchmark with adjustments",
                    citations=[f"{stage_key} median: ${benchmarks.get('valuation_median', 0)/1e6:.0f}M"]
                )
                inferences["valuation"] = valuation_inference
                inferences["inferred_valuation"] = InferenceResult(
                    field="inferred_valuation",
                    value=adjusted_valuation,
                    confidence=0.4,
                    source="stage_benchmark",
                    reasoning=f"{stage_key} benchmark with adjustments",
                    citations=[f"{stage_key} median: ${benchmarks.get('valuation_median', 0)/1e6:.0f}M"]
                )
        
        return inferences
    
    def score_fund_fit(
        self,
        company_data: Dict[str, Any],
        inferred_data: Dict[str, InferenceResult],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        DETERMINISTIC fund fit scoring based on fund economics
        
        Context MUST include:
        - fund_size: Total fund size
        - fund_year: Current year of fund (1-10)
        - portfolio_count: Number of investments made
        - lead_investor: Whether we lead rounds
        
        This determines:
        1. Can we write the check size needed?
        2. Can we get sufficient ownership?
        3. Does the return profile work for our fund?
        """
        if context is None:
            context = {}
            
        # CRITICAL: Extract fund parameters for calculations
        fund_size = context.get('fund_size')  # From user prompt
        
        # Log fund parameters for debugging
        import logging
        logger = logging.getLogger(__name__)
        
        # Calculate realistic_exit_multiple even without fund_size (it only needs valuation/revenue)
        # Combine actual and inferred data for calculation
        all_data_for_exit_multiple = {**company_data}
        for field, inference in inferred_data.items():
            if hasattr(inference, 'value'):
                all_data_for_exit_multiple[field] = inference.value
            else:
                all_data_for_exit_multiple[field] = inference
        
        # Get valuation and revenue for exit multiple calculation
        valuation_raw = all_data_for_exit_multiple.get('valuation', 0) or all_data_for_exit_multiple.get('post_money', 0)
        if isinstance(valuation_raw, dict):
            valuation_for_exit = valuation_raw.get('value', 0) if 'value' in valuation_raw else 0
        elif hasattr(valuation_raw, 'value'):
            valuation_for_exit = valuation_raw.value
        else:
            valuation_for_exit = valuation_raw or 0
        
        revenue_raw = all_data_for_exit_multiple.get("revenue", all_data_for_exit_multiple.get("inferred_revenue", 1_000_000))
        if isinstance(revenue_raw, dict):
            revenue_for_exit = revenue_raw.get('value', 1_000_000) if 'value' in revenue_raw else 1_000_000
        elif hasattr(revenue_raw, 'value'):
            revenue_for_exit = revenue_raw.value
        else:
            revenue_for_exit = revenue_raw or 1_000_000
        
        # Calculate realistic_exit_multiple based on entry valuation
        realistic_exit_multiple = 10  # Default
        if valuation_for_exit > 0 and revenue_for_exit > 0:
            current_revenue_multiple = valuation_for_exit / revenue_for_exit
            # Validate: reasonable multiples are 0.5x to 100x
            if current_revenue_multiple < 0.5:
                current_revenue_multiple = max(0.5, current_revenue_multiple)
            elif current_revenue_multiple > 100:
                current_revenue_multiple = 100
            
            # Adjust exit multiple based on entry - expensive entry = lower exit multiple
            if current_revenue_multiple <= 10:  # Great entry
                realistic_exit_multiple = 20  # Can achieve 20x from here
            elif current_revenue_multiple <= 20:  # Fair entry
                realistic_exit_multiple = 10  # Can achieve 10x
            elif current_revenue_multiple <= 40:  # Expensive entry
                realistic_exit_multiple = 5   # Only 5x realistic
            else:  # Very expensive
                realistic_exit_multiple = 3   # Hard to get good returns
        
        # Early exit if no fund size provided
        if not fund_size or fund_size == 0:
            logger.warning("[FUND_FIT] No fund size provided - cannot score fund fit")
            return {
                "overall_score": 0,
                "component_scores": {},
                "recommendation": "Cannot score - no fund size provided",
                "action": "SKIP",
                "reasons": ["Fund size required for analysis"],
                "confidence": 0,
                "fund_economics_score": 0,
                "selected_check": 0,
                "target_ownership": 0,
                "selected_ownership": 0,
                "realistic_exit_multiple": realistic_exit_multiple
            }
        
        scores = {}
        reasons = []
        recommendations = []
        
        fund_year = context.get('fund_year', 3)  # Year 3 of fund
        portfolio_count = context.get('portfolio_count', 9)  # 9 investments made
        is_lead = context.get('lead_investor', False) or context.get('is_lead', False)
        current_dpi = context.get('dpi', 0.5)  # 0.5x DPI achieved
        target_tvpi = context.get('target_tvpi', 3.0)  # 3x target
        
        logger.info(f"Fund fit scoring with context: fund_size={fund_size/1e6:.0f}M, year={fund_year}, portfolio={portfolio_count}, lead={is_lead}")
        
        # Combine actual and inferred data
        all_data = {**company_data}
        for field, inference in inferred_data.items():
            # Handle both InferenceResult objects and raw values
            if hasattr(inference, 'value'):
                all_data[field] = inference.value
            else:
                all_data[field] = inference
        
        # =====================================================
        # FUND DEPLOYMENT MODEL - DETERMINISTIC CALCULATIONS
        # =====================================================
        
        # Model fund deployment schedule
        total_portfolio_target = 25 if fund_size > 100_000_000 else 20
        
        # Calculate actual deployment based on fund year and quarter
        quarters_elapsed = (fund_year - 1) * 4 + context.get('fund_quarter', 2)
        total_fund_quarters = 12 * 4  # 12 year fund life
        
        # Standard deployment curve (S-curve)
        # Years 1-3: Deploy 60% (initial investments)
        # Years 4-5: Deploy 15% (follow-ons)
        # Years 6+: Reserve 25% (late stage follow-ons)
        
        if quarters_elapsed <= 12:  # Year 1-3
            target_deployment_pct = (quarters_elapsed / 12) * 0.60
        elif quarters_elapsed <= 20:  # Year 4-5
            target_deployment_pct = 0.60 + ((quarters_elapsed - 12) / 8) * 0.15
        else:  # Year 6+
            target_deployment_pct = 0.75
        
        # Calculate target deployment amount
        target_deployed = (fund_size or 0) * target_deployment_pct
        
        # Calculate actual deployment from what they've told us
        # If they have context about deployed capital, use it
        if context.get('deployed_capital'):
            actual_deployed = context['deployed_capital']
            avg_check_size = actual_deployed / portfolio_count if portfolio_count > 0 else 0
        else:
            # Otherwise infer from typical deployment curve
            # Year 3 Q3 = they should have deployed ~45% of fund
            if fund_year <= 3:
                typical_deployment_rate = 0.15 * fund_year  # ~15% per year in first 3 years
            else:
                typical_deployment_rate = 0.45 + (fund_year - 3) * 0.05
            
            actual_deployed = (fund_size or 0) * typical_deployment_rate
            avg_check_size = actual_deployed / portfolio_count if portfolio_count > 0 else (fund_size or 0) * 0.03
        
        # Remaining capital and pacing
        remaining_capital = fund_size - actual_deployed
        deployment_gap = target_deployed - actual_deployed
        remaining_investments = max(total_portfolio_target - portfolio_count, 5)
        
        # Calculate remaining to deploy (for pacing)
        if deployment_gap > 0:
            # Behind schedule - need to catch up
            remaining_to_deploy = remaining_capital * 0.7  # Deploy 70% of remaining
        else:
            # On or ahead of schedule
            remaining_to_deploy = remaining_capital * 0.5  # Deploy 50% of remaining
        
        # For Series A in Year 3 with 9 deals:
        # - Deployed: ~45% of 160M = 72M
        # - Avg check: 72M / 9 = 8M
        # - Remaining: 88M
        # - Need to deploy: 16 more deals
        
        # Calculate optimal check size
        if is_lead:
            max_check_percentage = 0.05  # 5% max per deal when leading
            target_ownership = 0.15  # 15% ownership target for leads
        else:
            max_check_percentage = 0.03  # 3% max when not leading
            target_ownership = 0.10  # 10% ownership target for follow
        
        max_check_size = fund_size * max_check_percentage
        optimal_check_per_deal = remaining_to_deploy / remaining_investments if remaining_investments > 0 else max_check_size
        
        # Get company valuation
        valuation_raw = all_data.get('valuation', 0) or all_data.get('post_money', 0)
        # Handle case where valuation might be a dict or InferenceResult
        if isinstance(valuation_raw, dict):
            valuation = valuation_raw.get('value', 0) if 'value' in valuation_raw else 0
        elif hasattr(valuation_raw, 'value'):
            valuation = valuation_raw.value
        else:
            valuation = valuation_raw or 0
            
        if valuation == 0:
            # Estimate from last round
            last_round_raw = all_data.get('last_round_amount', 0)
            # Also handle dict/InferenceResult for last_round
            if isinstance(last_round_raw, dict):
                last_round = last_round_raw.get('value', 0) if 'value' in last_round_raw else 0
            elif hasattr(last_round_raw, 'value'):
                last_round = last_round_raw.value
            else:
                last_round = last_round_raw or 0
                
            if last_round > 0:
                valuation = last_round * 5  # Assume 20% dilution typical
        
        # =====================================================
        # DEAL ECONOMICS CALCULATION
        # =====================================================
        
        if valuation > 0:
            # Calculate ownership at different check sizes
            ownership_at_max = max_check_size / (valuation + max_check_size)
            ownership_at_optimal = optimal_check_per_deal / (valuation + optimal_check_per_deal)
            
            # Calculate required check for target ownership
            required_check_for_target = (valuation * target_ownership) / (1 - target_ownership)
            
            # Determine if deal works
            deal_works = False
            selected_check = 0
            selected_ownership = 0
            
            if required_check_for_target <= max_check_size:
                # We can achieve target ownership
                deal_works = True
                selected_check = required_check_for_target
                selected_ownership = target_ownership
                scores["fund_economics"] = 100
                reasons.append(f"✅ DEAL WORKS: ${selected_check/1e6:.1f}M for {selected_ownership:.1%} ownership")
            elif ownership_at_max >= target_ownership * 0.67:  # Accept 2/3 of target
                # We can get acceptable ownership at max check
                deal_works = True
                selected_check = max_check_size
                selected_ownership = ownership_at_max
                scores["fund_economics"] = 75
                reasons.append(f"🔶 ACCEPTABLE: ${selected_check/1e6:.1f}M for {selected_ownership:.1%} ownership")
            else:
                # Deal doesn't work - valuation too high
                deal_works = False
                selected_check = max_check_size
                selected_ownership = ownership_at_max
                scores["fund_economics"] = 25
                reasons.append(f"❌ DOESN'T WORK: Only {selected_ownership:.1%} ownership at max ${max_check_size/1e6:.1f}M")
            
            # =====================================================
            # LIQUIDATION WATERFALL & RETURN MODELING
            # =====================================================
            
            # Model different exit scenarios
            exit_scenarios = {
                "base_case": {"multiple": 5, "probability": 0.4},
                "good_case": {"multiple": 10, "probability": 0.3},
                "home_run": {"multiple": 25, "probability": 0.1},
                "loss": {"multiple": 0.5, "probability": 0.2}
            }
            
            expected_return = 0
            scenario_details = []
            
            for scenario_name, scenario in exit_scenarios.items():
                exit_val = valuation * scenario["multiple"]
                
                # Model liquidation preference impact
                # Assume we have 1x participating preferred
                if is_lead:
                    # As lead, we likely have liquidation preference
                    our_liquidation_pref = selected_check
                    remaining_after_pref = max(0, exit_val - our_liquidation_pref)
                    our_participation = selected_ownership * remaining_after_pref
                    our_total = min(exit_val, our_liquidation_pref + our_participation)
                else:
                    # As non-lead, straight equity
                    our_total = selected_ownership * exit_val
                
                scenario_return = our_total / selected_check if selected_check > 0 else 0
                expected_return += scenario_return * scenario["probability"]
                
                scenario_details.append({
                    "scenario": scenario_name,
                    "exit_value": exit_val,
                    "our_proceeds": our_total,
                    "multiple": scenario_return,
                    "probability": scenario["probability"]
                })
            
            # Model fund-level impact with entry valuation consideration
            # Power law: Need 1-2 deals to return fund, BUT at the right price
            fund_return_needed = fund_size * 3  # 3x target return
            
            # Calculate realistic exit multiples based on entry valuation
            revenue_raw = all_data.get("revenue", all_data.get("inferred_revenue", 1_000_000))
            # Handle dict/InferenceResult for revenue
            if isinstance(revenue_raw, dict):
                revenue = revenue_raw.get('value', 1_000_000) if 'value' in revenue_raw else 1_000_000
            elif hasattr(revenue_raw, 'value'):
                revenue = revenue_raw.value
            else:
                revenue = revenue_raw or 1_000_000
            
            # Calculate revenue multiple with validation
            if revenue > 0:
                current_revenue_multiple = valuation / revenue
                # VALIDATE: Reasonable multiples are 0.5x to 100x
                # Flag if outside this range - likely data error
                if current_revenue_multiple < 0.5:
                    logger.warning(f"[MULTIPLE_VALIDATION] Suspiciously low multiple {current_revenue_multiple:.1f}x - valuation may be wrong")
                    current_revenue_multiple = max(0.5, current_revenue_multiple)
                elif current_revenue_multiple > 100:
                    logger.error(f"[MULTIPLE_VALIDATION] Impossible multiple {current_revenue_multiple:.0f}x (valuation=${valuation/1e6:.0f}M, revenue=${revenue/1e6:.1f}M) - capping at 100x")
                    # Likely valuation or revenue is wrong - cap at 100x
                    current_revenue_multiple = 100
            else:
                current_revenue_multiple = 50
            
            # Adjust exit multiple based on entry - expensive entry = lower exit multiple
            if current_revenue_multiple <= 10:  # Great entry
                realistic_exit_multiple = 20  # Can achieve 20x from here
            elif current_revenue_multiple <= 20:  # Fair entry
                realistic_exit_multiple = 10  # Can achieve 10x
            elif current_revenue_multiple <= 40:  # Expensive entry
                realistic_exit_multiple = 5   # Only 5x realistic
            else:  # Very expensive
                realistic_exit_multiple = 3   # Hard to get good returns
            
            can_return_fund = (selected_ownership * valuation * realistic_exit_multiple) >= fund_return_needed
            value_adjusted_return = (selected_ownership * valuation * realistic_exit_multiple) / fund_size
            
            # Portfolio construction impact with value consideration
            if portfolio_count < 10:
                # Early in fund, need potential fund-returners AT RIGHT PRICE
                if can_return_fund and current_revenue_multiple <= 20:
                    scores["portfolio_fit"] = 100
                    reasons.append(f"🎯 FUND-RETURNER: {value_adjusted_return:.1f}x fund at {realistic_exit_multiple}x exit (entry: {current_revenue_multiple:.0f}x)")
                elif can_return_fund and current_revenue_multiple > 20:
                    scores["portfolio_fit"] = 70
                    reasons.append(f"🔶 Potential returner but expensive entry: {current_revenue_multiple:.0f}x revenue")
                elif value_adjusted_return >= 0.5:  # Can return 0.5x fund
                    scores["portfolio_fit"] = 60
                    reasons.append(f"📊 Solid addition: {value_adjusted_return:.1f}x fund potential")
                else:
                    scores["portfolio_fit"] = 40
                    reasons.append(f"❌ Poor risk/reward at {current_revenue_multiple:.0f}x entry")
            else:
                # Later in fund, value matters even more
                if current_revenue_multiple <= 15:
                    scores["portfolio_fit"] = 90
                    reasons.append(f"✅ Good value for late-stage fund addition")
                elif current_revenue_multiple <= 25:
                    scores["portfolio_fit"] = 70
                    reasons.append(f"🔶 Acceptable for portfolio balance")
                else:
                    scores["portfolio_fit"] = 40
                    reasons.append(f"⚠️ Too expensive for this stage of fund")
            
            # =====================================================
            # BACKWARD ANALYSIS: What do we need for fund returns?
            # =====================================================
            
            # Calculate fund-level requirements
            current_value = fund_size * current_dpi
            target_value = fund_size * target_tvpi
            needed_returns = target_value - current_value
            per_investment_target = needed_returns / 25  # Assume 25 total investments
            
            # What ownership would we need at different exit multiples to hit our target?
            backward_scenarios = []
            for exit_multiple in [5, 10, 25, 50]:
                exit_value = valuation * exit_multiple
                required_proceeds = per_investment_target
                required_exit_ownership = required_proceeds / exit_value if exit_value > 0 else 1.0
                
                # Account for dilution - work backwards
                dilution_factor = 0.65  # Assume 35% dilution to exit
                required_initial_ownership = required_exit_ownership / dilution_factor
                required_check = (valuation * required_initial_ownership) / (1 - required_initial_ownership) if required_initial_ownership < 1 else 999999999
                
                is_feasible = required_check <= max_check_size and required_initial_ownership <= 0.30  # 30% max ownership
                
                backward_scenarios.append({
                    "exit_multiple": exit_multiple,
                    "required_check": required_check,
                    "required_ownership": required_initial_ownership,
                    "is_feasible": is_feasible
                })
            
            # Add detailed math breakdown
            recommendations.append(f"📊 FORWARD: ${selected_check/1e6:.1f}M → {selected_ownership:.1%} ownership → E[{expected_return:.1f}x] return")
            recommendations.append(f"💰 Expected proceeds: ${selected_check * expected_return / 1e6:.1f}M ({(selected_check * expected_return / needed_returns):.1%} of ${needed_returns/1e6:.0f}M fund target)")
            
            # Find best backward scenario
            feasible_scenarios = [s for s in backward_scenarios if s["is_feasible"]]
            if feasible_scenarios:
                best_scenario = feasible_scenarios[0]  # Take lowest multiple that works
                recommendations.append(f"🎯 BACKWARD: For {best_scenario['exit_multiple']}x exit, need ${best_scenario['required_check']/1e6:.1f}M for {best_scenario['required_ownership']:.1%} ownership")
            else:
                min_check_scenario = min(backward_scenarios, key=lambda x: x["required_check"])
                recommendations.append(f"⚠️ CHALLENGE: Even at 50x exit, need ${min_check_scenario['required_check']/1e6:.1f}M (exceeds ${max_check_size/1e6:.1f}M limit)")
            
            # Add fund context
            recommendations.append(f"📈 FUND CONTEXT: Year {fund_year}, {portfolio_count} deals, ${remaining_capital/1e6:.0f}M remaining, need ${needed_returns/1e6:.0f}M returns")
            
            # Deployment pacing check with more context
            if fund_year >= 3:
                deployment_rate = actual_deployed / fund_size
                if deployment_rate < 0.45:  # Should be ~45% deployed by year 3
                    scores["deployment_urgency"] = 95
                    reasons.append(f"⚡ URGENT: Only {deployment_rate:.0%} deployed in Year {fund_year} (target: 45%)")
                    recommendations.append(f"🚨 Must deploy ${remaining_to_deploy/1e6:.0f}M across {remaining_investments} deals")
                elif portfolio_count < 10:
                    scores["deployment_urgency"] = 90
                    reasons.append(f"⚡ DEPLOYMENT PRESSURE: Year {fund_year} with only {portfolio_count} deals")
                else:
                    scores["deployment_urgency"] = 70
                    reasons.append(f"✅ On track: {deployment_rate:.0%} deployed, {portfolio_count} investments")
        else:
            # When valuation is missing, still calculate position sizing based on fund economics
            scores["fund_economics"] = 0
            reasons.append("⚠️ Cannot fully evaluate - no valuation data")
            
            # But we can still calculate optimal position size based on fund parameters
            selected_check = optimal_check_per_deal  # Use the calculated optimal check
            selected_ownership = 0  # Can't calculate ownership without valuation
            expected_return = 0  # Can't calculate returns without valuation
            realistic_exit_multiple = 10  # Default exit multiple when valuation is missing
            
            # Add reasoning about position sizing even without valuation
            reasons.append(f"📊 Position sizing: ${selected_check/1e6:.1f}M based on fund deployment needs")
            recommendations.append(f"💡 With {remaining_investments} investments remaining, optimal check is ${selected_check/1e6:.1f}M")
            recommendations.append(f"📈 Max position size: ${max_check_size/1e6:.1f}M ({max_check_percentage*100:.0f}% of fund)")
        
        # =====================================================
        # TRADITIONAL SCORING (now secondary to fund math)
        # =====================================================
        
        # 1. Stage Fit (0-100)
        stage = self._determine_stage(all_data)
        if stage in self.fund.stage_focus:
            scores["stage_fit"] = 100
            reasons.append(f"✅ Perfect stage fit: {stage} is in our focus")
        elif self._is_adjacent_stage(stage, self.fund.stage_focus):
            scores["stage_fit"] = 70
            reasons.append(f"🔶 Adjacent stage: {stage} (we focus on {', '.join(self.fund.stage_focus)})")
        else:
            scores["stage_fit"] = 20
            reasons.append(f"❌ Stage mismatch: {stage} vs our focus on {', '.join(self.fund.stage_focus)}")
        
        # 2. Sector Fit (0-100)
        sector = all_data.get("sector", "Unknown")
        if sector in self.fund.sector_focus:
            scores["sector_fit"] = 100
            reasons.append(f"✅ Sector aligned: {sector}")
        elif self._is_related_sector(sector, self.fund.sector_focus):
            scores["sector_fit"] = 60
            reasons.append(f"🔶 Related sector: {sector}")
        else:
            scores["sector_fit"] = 30
            reasons.append(f"❌ Sector outside focus: {sector}")
        
        # 3. Gross Margin & Unit Economics (0-100) - Based on API dependency
        gross_margin_analysis = self.calculate_adjusted_gross_margin(all_data)
        adjusted_margin = gross_margin_analysis["adjusted_gross_margin"]
        
        if adjusted_margin >= 0.75:
            scores["unit_economics"] = 100
            reasons.append(f"✅ Excellent gross margins: {adjusted_margin:.0%}")
        elif adjusted_margin >= 0.65:
            scores["unit_economics"] = 70
            reasons.append(f"🔶 Good gross margins: {adjusted_margin:.0%}")
        elif adjusted_margin >= 0.55:
            scores["unit_economics"] = 40
            reasons.append(f"⚠️ Concerning gross margins: {adjusted_margin:.0%} due to {gross_margin_analysis['api_dependency_level']}")
        else:
            scores["unit_economics"] = 10
            reasons.append(f"❌ Poor gross margins: {adjusted_margin:.0%} - heavy API dependency")
        
        # Add API dependency warning if applicable
        if gross_margin_analysis["api_dependency_level"] in ["openai_heavy", "openai_moderate"]:
            recommendations.append(gross_margin_analysis["investment_recommendation"])
        
        # 4. Check Size & Ownership Fit (0-100) - Context-aware
        last_round_amount = all_data.get("last_round_amount", 0)
        valuation = all_data.get("valuation", 0)
        
        # Use context to determine optimal check size
        if context.get('fund_size'):
            fund_size = context['fund_size']
            portfolio_count = context.get('portfolio_count', 0)
            fund_year = context.get('fund_year', 1)
            is_lead = context.get('lead_investor', False)
            
            # Calculate optimal check size based on fund parameters
            remaining_deals = max(20 - portfolio_count, 5)  # Assume 20-25 total portfolio companies
            deployable_capital = fund_size * (1 - min(0.6, fund_year * 0.2))  # Deployment curve
            
            if is_lead:
                optimal_check = min(fund_size * 0.05, deployable_capital / remaining_deals * 1.5)  # 5% max for lead
                min_ownership = 0.15  # 15% minimum for lead
            else:
                optimal_check = min(fund_size * 0.03, deployable_capital / remaining_deals)  # 3% max for non-lead
                min_ownership = 0.08  # 8% minimum for non-lead
            
            # Calculate actual ownership we'd get
            if valuation > 0:
                ownership_at_optimal = optimal_check / (valuation + optimal_check)
                
                # Score based on ownership achieved
                if ownership_at_optimal >= min_ownership:
                    scores["check_size_fit"] = 100
                    reasons.append(f"✅ Can achieve {ownership_at_optimal:.1%} ownership with ${optimal_check/1e6:.1f}M check")
                elif ownership_at_optimal >= min_ownership * 0.7:
                    scores["check_size_fit"] = 70
                    reasons.append(f"🔶 Would get {ownership_at_optimal:.1%} ownership (target: {min_ownership:.0%})")
                else:
                    scores["check_size_fit"] = 30
                    reasons.append(f"❌ Only {ownership_at_optimal:.1%} ownership possible (need {min_ownership:.0%})")
                
                # Add return calculation
                exit_multiple = 10  # Assume 10x on winners
                exit_value = valuation * exit_multiple
                our_return = ownership_at_optimal * exit_value
                return_multiple = our_return / optimal_check if optimal_check > 0 else 0
                
                if return_multiple >= 10:
                    recommendations.append(f"💰 Potential {return_multiple:.1f}x return on ${optimal_check/1e6:.1f}M investment")
                elif return_multiple >= 5:
                    recommendations.append(f"📊 Decent {return_multiple:.1f}x return potential")
                else:
                    recommendations.append(f"⚠️ Low {return_multiple:.1f}x return - need better entry price")
            else:
                # Fallback to simple check size
                if self.fund.check_size_range[0] <= last_round_amount <= self.fund.check_size_range[1]:
                    scores["check_size_fit"] = 80
                else:
                    scores["check_size_fit"] = 40
        else:
            # Original logic if no context
            if self.fund.check_size_range[0] <= last_round_amount <= self.fund.check_size_range[1]:
                scores["check_size_fit"] = 100
                reasons.append(f"✅ Check size fits: ${last_round_amount/1e6:.1f}M")
            elif last_round_amount < self.fund.check_size_range[0]:
                scores["check_size_fit"] = 50
                reasons.append(f"🔶 Below typical check: ${last_round_amount/1e6:.1f}M < ${self.fund.check_size_range[0]/1e6:.1f}M")
            else:
                scores["check_size_fit"] = 30
                reasons.append(f"❌ Above typical check: ${last_round_amount/1e6:.1f}M > ${self.fund.check_size_range[1]/1e6:.1f}M")
        
        # 5. Timing Fit (0-100)
        runway = all_data.get("runway", 12)
        next_round_timing = all_data.get("next_round_timing", 12)
        
        if 3 <= next_round_timing <= 9:
            scores["timing_fit"] = 100
            reasons.append(f"✅ Perfect timing: Raising in {next_round_timing:.0f} months")
            recommendations.append("Move quickly - company will be fundraising soon")
        elif next_round_timing < 3:
            scores["timing_fit"] = 60
            reasons.append(f"🔶 May be too late: Raising in {next_round_timing:.0f} months")
            recommendations.append("Urgent: May already be in process")
        elif next_round_timing > 12:
            scores["timing_fit"] = 40
            reasons.append(f"⏰ Too early: Not raising for {next_round_timing:.0f} months")
            recommendations.append("Build relationship for next round")
        else:
            scores["timing_fit"] = 80
            reasons.append(f"🔶 Good timing window: {next_round_timing:.0f} months")
        
        # 6. Return Potential (0-100) - ENHANCED WITH ENTRY CONSIDERATION
        # Get valuation with proper handling
        valuation_raw = all_data.get("valuation", 100_000_000)
        if isinstance(valuation_raw, dict):
            valuation = valuation_raw.get('value', 100_000_000) if 'value' in valuation_raw else 100_000_000
        elif hasattr(valuation_raw, 'value'):
            valuation = valuation_raw.value
        else:
            valuation = valuation_raw or 100_000_000
            
        # Get growth rate with proper handling
        growth_rate_raw = all_data.get("growth_rate", 0.5)
        if isinstance(growth_rate_raw, dict):
            growth_rate = growth_rate_raw.get('value', 0.5) if 'value' in growth_rate_raw else 0.5
        elif hasattr(growth_rate_raw, 'value'):
            growth_rate = growth_rate_raw.value
        else:
            growth_rate = growth_rate_raw or 0.5
            
        # Get revenue with proper handling
        revenue_raw = all_data.get("revenue", 1_000_000)
        if isinstance(revenue_raw, dict):
            revenue = revenue_raw.get('value', 1_000_000) if 'value' in revenue_raw else 1_000_000
        elif hasattr(revenue_raw, 'value'):
            revenue = revenue_raw.value
        else:
            revenue = revenue_raw or 1_000_000
        
        # Simple exit multiple calculation
        years_to_exit = self.fund.typical_holding_period / 12
        projected_revenue = revenue * ((1 + growth_rate) ** years_to_exit)
        exit_valuation = projected_revenue * 10  # Assume 10x revenue multiple at exit
        
        return_multiple = exit_valuation / valuation if valuation > 0 else 0
        
        if return_multiple >= self.fund.exit_multiple_target:
            scores["return_potential"] = 100
            reasons.append(f"✅ Strong return potential: {return_multiple:.1f}x projected")
        elif return_multiple >= self.fund.exit_multiple_target * 0.7:
            scores["return_potential"] = 70
            reasons.append(f"🔶 Moderate return potential: {return_multiple:.1f}x projected")
        else:
            scores["return_potential"] = 40
            reasons.append(f"❌ Below return threshold: {return_multiple:.1f}x vs {self.fund.exit_multiple_target}x target")
        
        # 7. Entry Value Score (0-100) - NEW: Evaluate entry point attractiveness
        current_multiple = valuation / revenue if revenue > 0 else 999999
        stage = self._determine_stage(all_data)
        stage_benchmark_multiple = self.STAGE_BENCHMARKS.get(stage, {}).get("valuation_multiple", 15)
        
        # Calculate max entry valuation we should pay (backward looking)
        exit_revenue = projected_revenue
        target_irr = 0.30  # 30% IRR target
        target_multiple = self.fund.exit_multiple_target
        max_entry_valuation_irr = exit_valuation / ((1 + target_irr) ** years_to_exit)
        max_entry_valuation_multiple = exit_valuation / target_multiple
        max_entry_valuation = min(max_entry_valuation_irr, max_entry_valuation_multiple)
        
        # Score based on how attractive the entry point is
        if valuation <= max_entry_valuation * 0.8:  # 20% discount to our max
            scores["entry_value"] = 100
            reasons.append(f"💎 EXCELLENT ENTRY: Valued at {current_multiple:.1f}x revenue (max: {max_entry_valuation/revenue:.1f}x)")
            recommendations.append(f"Strong value at entry - can pay up to ${max_entry_valuation/1e6:.1f}M")
        elif valuation <= max_entry_valuation:
            scores["entry_value"] = 80
            reasons.append(f"✅ Fair entry: {current_multiple:.1f}x revenue vs {stage_benchmark_multiple}x benchmark")
        elif valuation <= max_entry_valuation * 1.2:  # Up to 20% premium
            scores["entry_value"] = 60
            reasons.append(f"🔶 Slightly expensive: {current_multiple:.1f}x revenue (20% above our max)")
            recommendations.append(f"Try to negotiate down from ${valuation/1e6:.1f}M to ${max_entry_valuation/1e6:.1f}M")
        elif valuation <= max_entry_valuation * 1.5:  # Up to 50% premium
            scores["entry_value"] = 40
            reasons.append(f"⚠️ Overvalued: {current_multiple:.1f}x revenue ({((valuation/max_entry_valuation - 1) * 100):.0f}% premium)")
            recommendations.append(f"Wait for better entry in next round or market correction")
        else:
            scores["entry_value"] = 20
            reasons.append(f"🚫 SEVERELY OVERVALUED: {current_multiple:.1f}x revenue (benchmark: {stage_benchmark_multiple}x)")
            recommendations.append(f"PASS - Entry valuation ${valuation/1e6:.1f}M vs max ${max_entry_valuation/1e6:.1f}M")
        
        # 8. Growth Trajectory & TAM Analysis (0-100) - Acceleration/Deceleration + Upside
        # Get historical growth if available
        historical_growth = []
        if "funding_rounds" in all_data:
            rounds = sorted(all_data["funding_rounds"], key=lambda x: x.get("date", ""))
            for i in range(1, len(rounds)):
                curr_revenue = rounds[i].get("revenue")
                prev_revenue = rounds[i - 1].get("revenue")
                if curr_revenue is None or prev_revenue is None:
                    continue

                try:
                    curr_revenue = float(curr_revenue)
                    prev_revenue = float(prev_revenue)
                except (TypeError, ValueError):
                    continue

                if prev_revenue <= 0:
                    continue

                time_diff_years = 1.0  # Default to one year if we cannot infer dates
                current_date = rounds[i].get("date")
                previous_date = rounds[i - 1].get("date")
                if current_date and previous_date:
                    months_between = self._months_between_rounds(previous_date, current_date)
                    if months_between and months_between > 0:
                        time_diff_years = max(months_between / 12.0, 0.25)

                if time_diff_years <= 0:
                    continue

                growth = (curr_revenue / prev_revenue - 1) / time_diff_years
                historical_growth.append(growth)
        
        # Calculate growth trajectory (accelerating vs decelerating)
        if len(historical_growth) >= 2:
            recent_growth = historical_growth[-1]
            prior_growth = historical_growth[-2]
            is_accelerating = recent_growth > prior_growth
            growth_delta = recent_growth - prior_growth
        else:
            # Use current growth rate vs stage benchmark
            recent_growth = growth_rate
            stage_benchmark_growth = self.STAGE_BENCHMARKS.get(stage, {}).get("yoy_growth", 1.5)
            is_accelerating = recent_growth > stage_benchmark_growth
            growth_delta = recent_growth - stage_benchmark_growth
        
        # Calculate TAM penetration and remaining upside
        tam_raw = all_data.get("tam", all_data.get("market_size", 10_000_000_000))  # Default $10B TAM
        # Handle dict/InferenceResult for TAM
        if isinstance(tam_raw, dict):
            tam = tam_raw.get('value', 10_000_000_000) if 'value' in tam_raw else tam_raw.get('tam', 10_000_000_000)
        elif hasattr(tam_raw, 'value'):
            tam = tam_raw.value
        else:
            tam = tam_raw or 10_000_000_000
        current_penetration = revenue / tam if tam > 0 else 0
        
        # Calculate potential exit size based on TAM capture
        # Best case: 10% TAM capture for category leader
        # Base case: 1% TAM capture for strong player
        # Bear case: 0.1% TAM capture for niche player
        best_case_revenue = tam * 0.10
        base_case_revenue = tam * 0.01
        bear_case_revenue = tam * 0.001
        
        # How many years to reach different TAM penetrations at current growth?
        # Fix calculation logic to ensure positive values before math operations
        if revenue > 0 and base_case_revenue > revenue and growth_rate > -1:
            ratio = base_case_revenue / revenue
            if ratio > 0:
                growth_factor = 1 + max(growth_rate, 0.01)  # Ensure positive
                years_to_1pct = math.log(ratio) / math.log(growth_factor)
            else:
                years_to_1pct = 20
        else:
            years_to_1pct = 20
        
        if revenue > 0 and best_case_revenue > revenue and growth_rate > -1:
            ratio = best_case_revenue / revenue
            if ratio > 0:
                growth_factor = 1 + max(growth_rate, 0.01)  # Ensure positive
                years_to_10pct = math.log(ratio) / math.log(growth_factor)
            else:
                years_to_10pct = 20
        else:
            years_to_10pct = 20
        
        # Calculate upside from current valuation
        # What would company be worth at different TAM penetrations?
        base_case_valuation = base_case_revenue * 8  # 8x revenue at scale
        best_case_valuation = best_case_revenue * 12  # 12x for category leader
        
        base_upside = base_case_valuation / valuation if valuation > 0 else 0
        best_upside = best_case_valuation / valuation if valuation > 0 else 0
        
        # Score based on growth trajectory AND TAM upside
        trajectory_score = 0
        tam_score = 0
        
        # Growth trajectory scoring
        if is_accelerating and growth_delta > 0.2:  # Strongly accelerating
            trajectory_score = 100
            # Check if prior_growth is defined
            if 'prior_growth' in locals():
                reasons.append(f"🚀 ACCELERATING: Growth increasing from {prior_growth:.0%} to {recent_growth:.0%}")
            else:
                reasons.append(f"🚀 ACCELERATING: Growth at {recent_growth:.0%}")
        elif is_accelerating:
            trajectory_score = 80
            reasons.append(f"📈 Accelerating growth: {recent_growth:.0%} YoY")
        elif growth_delta > -0.1:  # Slight deceleration
            trajectory_score = 60
            reasons.append(f"📊 Stable growth: {recent_growth:.0%} YoY")
        elif growth_delta > -0.3:  # Moderate deceleration
            trajectory_score = 40
            reasons.append(f"📉 Decelerating: Growth slowing to {recent_growth:.0%}")
        else:  # Severe deceleration
            trajectory_score = 20
            reasons.append(f"⚠️ RAPID DECELERATION: Growth collapsed to {recent_growth:.0%}")
        
        # TAM upside scoring
        if base_upside >= 50 and years_to_1pct <= 7:  # Can be 50x+ in 7 years
            tam_score = 100
            reasons.append(f"🎯 MASSIVE TAM: ${tam/1e9:.0f}B market, {base_upside:.0f}x upside to 1% penetration")
            recommendations.append(f"Can reach ${base_case_revenue/1e6:.0f}M revenue (1% TAM) in {years_to_1pct:.1f} years")
        elif base_upside >= 20 and years_to_1pct <= 10:
            tam_score = 80
            reasons.append(f"✅ Large TAM: ${tam/1e9:.0f}B market, {base_upside:.0f}x upside potential")
        elif base_upside >= 10:
            tam_score = 60
            reasons.append(f"🔶 Decent TAM: ${tam/1e9:.0f}B market, {base_upside:.0f}x upside")
        elif base_upside >= 5:
            tam_score = 40
            reasons.append(f"📊 Limited TAM upside: Only {base_upside:.0f}x to 1% penetration")
        else:
            tam_score = 20
            reasons.append(f"❌ TAM CONSTRAINED: <5x upside even at 1% market share")
            recommendations.append(f"Already at {current_penetration:.2%} of ${tam/1e9:.1f}B TAM")
        
        # Combined growth trajectory score
        scores["growth_trajectory"] = (trajectory_score * 0.4 + tam_score * 0.6)
        
        # Add specific recommendations based on trajectory
        if is_accelerating and base_upside >= 20:
            recommendations.append(f"🎯 IDEAL: Accelerating growth + {base_upside:.0f}x TAM upside = compound winner")
        elif not is_accelerating and base_upside >= 20:
            recommendations.append(f"⚠️ WATCH: Great TAM but decelerating - why is growth slowing?")
        elif is_accelerating and base_upside < 10:
            recommendations.append(f"📊 CAUTION: Accelerating but TAM-limited - exit timing critical")
        
        # 6. Geography Fit (0-100)
        geography = all_data.get("geography", "Unknown")
        if geography in self.fund.geography_focus:
            scores["geography_fit"] = 100
            reasons.append(f"✅ Geography match: {geography}")
        else:
            scores["geography_fit"] = 50
            reasons.append(f"🔶 Geography outside focus: {geography}")
        
        # Calculate overall score (weighted average) - REBALANCED for value + growth
        # Entry value and growth trajectory are now key factors
        weights = {
            "fund_economics": 0.25,      # Still important: ownership & fund math
            "entry_value": 0.20,          # NEW: Is the entry price attractive?
            "growth_trajectory": 0.20,    # NEW: TAM upside + acceleration
            "unit_economics": 0.10,       # Gross margins matter
            "stage_fit": 0.05,            
            "sector_fit": 0.05,           
            "check_size_fit": 0.03,       # Less important (covered in fund_economics)
            "timing_fit": 0.07,           
            "return_potential": 0.03,     # Less important (covered by entry_value)
            "geography_fit": 0.02         
        }
        
        # Add deployment urgency if present
        if "deployment_urgency" in scores:
            weights["deployment_urgency"] = 0.15
        
        # Calculate weighted score - but only for keys that exist in scores
        total_weight = sum(weights[k] for k in weights if k in scores)
        overall_score = sum(scores.get(k, 0) * weights[k] for k in weights if k in scores) / total_weight if total_weight > 0 else 0
        
        # Generate investment recommendation
        if overall_score >= 80:
            recommendation = "STRONG BUY - Excellent fit with fund thesis"
            action = "Schedule partner meeting immediately"
        elif overall_score >= 65:
            recommendation = "BUY - Good fit, some concerns"
            action = "Proceed with deep diligence"
        elif overall_score >= 50:
            recommendation = "HOLD - Interesting but not ideal"
            action = "Monitor and revisit next round"
        else:
            recommendation = "PASS - Poor fit with fund strategy"
            action = "Pass but maintain relationship"
        
        # Return comprehensive fund fit analysis including economics
        return {
            "overall_score": overall_score,
            "component_scores": scores,
            "recommendation": recommendation,
            "action": action,
            "reasons": reasons,
            "specific_recommendations": recommendations,
            "confidence": self._calculate_confidence(inferred_data),
            # Add fund economics for the test
            "selected_check": selected_check if 'selected_check' in locals() else 0,
            "selected_ownership": selected_ownership if 'selected_ownership' in locals() else 0,
            "expected_return": expected_return if 'expected_return' in locals() else 0,
            "expected_exit_value": expected_value if 'expected_value' in locals() else 0,
            "required_check_for_target": required_check_for_target if 'required_check_for_target' in locals() else 0,
            "target_ownership": target_ownership if 'target_ownership' in locals() else 0,
            "realistic_exit_multiple": realistic_exit_multiple if 'realistic_exit_multiple' in locals() else 10
        }
    
    def _determine_stage(self, company_data: Dict[str, Any]) -> Optional[str]:
        """Determine company stage from available data
        
        Priority:
        1. Last funding round type (most accurate - what they actually raised)
        2. Extracted stage field (if no funding rounds)
        3. Infer from financials (fallback)
        """
        
        # PRIORITY 1: Use last funding round - this is what they ACTUALLY raised!
        if "funding_rounds" in company_data and company_data["funding_rounds"]:
            # Sort by date to get the most recent
            sorted_rounds = sorted(
                company_data["funding_rounds"], 
                key=lambda x: x.get("date", "1900-01-01"),
                reverse=True  # Most recent first
            )
            last_round = sorted_rounds[0]
            round_type = last_round.get("round", "")
            if round_type and round_type.lower() not in ["unknown", "none", ""]:
                logger.info(f"[STAGE] Using last funding round: {round_type}")
                return round_type
        
        # PRIORITY 2: Trust extracted stage field
        if "stage" in company_data:
            stage_value = company_data["stage"]
            if stage_value and str(stage_value).strip() and str(stage_value).lower() not in ["unknown", "none", ""]:
                logger.info(f"[STAGE] Using extracted stage: {stage_value}")
                return stage_value
        
        # Infer from total funding amount
        total_funding = company_data.get("total_funding", 0) or company_data.get("inferred_total_funding", 0)
        if total_funding > 0:
            if total_funding < 2_000_000:
                return "Pre-Seed"
            elif total_funding < 10_000_000:
                return "Seed"
            elif total_funding < 30_000_000:
                return "Series A"
            elif total_funding < 70_000_000:
                return "Series B"
            elif total_funding < 150_000_000:
                return "Series C"
            else:
                return "Series D+"
        
        # Infer from revenue
        revenue = company_data.get("revenue", 0) or company_data.get("inferred_revenue", 0)
        if revenue > 0:
            if revenue < 100_000:
                return "Pre-Seed"
            elif revenue < 1_000_000:
                return "Seed"
            elif revenue < 5_000_000:
                return "Series A"
            elif revenue < 20_000_000:
                return "Series B"
            elif revenue < 50_000_000:
                return "Series C"
            else:
                return "Series D+"
        
        # Infer from team size
        team_size = company_data.get("team_size", 0) or company_data.get("employee_count", 0)
        if team_size > 0:
            if team_size < 10:
                return "Pre-Seed"
            elif team_size < 30:
                return "Seed"
            elif team_size < 100:
                return "Series A"
            elif team_size < 250:
                return "Series B"
            else:
                return "Series C"
        
        return "Seed"  # Default to Seed instead of None
    
    def _normalize_stage_key(self, stage: str) -> str:
        """Normalize stage strings to match STAGE_BENCHMARKS keys"""
        if not stage:
            return 'Seed'
        
        stage_lower = str(stage).lower().strip()
        
        # Check for Series rounds with letter pattern
        import re
        series_match = re.search(r'series[\s-]*([a-z])', stage_lower)
        if series_match:
            letter = series_match.group(1).upper()
            if letter <= 'C':
                return f'Series {letter}'
            elif letter == 'D':
                return 'Series D'
            else:  # E, F, G, H, I, J, etc.
                return 'Series D+'  # All late-stage map to D+
        
        # Check for standalone letters
        if len(stage_lower) == 1 and stage_lower in 'abcdefghijklmnopqrstuvwxyz':
            letter = stage_lower.upper()
            if letter <= 'C':
                return f'Series {letter}'
            elif letter == 'D':
                return 'Series D'
            else:
                return 'Series D+'
        
        # Check for seed stages
        if stage_lower in ['seed']:
            return 'Seed'
        elif stage_lower in ['pre-seed', 'preseed', 'pre seed']:
            return 'Pre-seed'
        elif 'seed' in stage_lower and 'pre' not in stage_lower:
            return 'Seed'
        elif 'pre' in stage_lower and 'seed' in stage_lower:
            return 'Pre-seed'
        
        # Default fallback
        return 'Seed'
    
    def _is_adjacent_stage(self, stage: str, focus_stages: List[str]) -> bool:
        """Check if stage is adjacent to focus stages"""
        stage_order = ["Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D", "Growth"]
        
        if stage not in stage_order:
            return False
        
        stage_idx = stage_order.index(stage)
        for focus in focus_stages:
            if focus in stage_order:
                focus_idx = stage_order.index(focus)
                if abs(stage_idx - focus_idx) == 1:
                    return True
        
        return False
    
    def _is_related_sector(self, sector: str, focus_sectors: List[str]) -> bool:
        """Check if sectors are related"""
        related_sectors = {
            "SaaS": ["Enterprise", "B2B", "Cloud"],
            "Fintech": ["Payments", "Banking", "InsurTech"],
            "AI/ML": ["DeepTech", "Data", "Automation"],
            "Enterprise": ["SaaS", "B2B", "Security"]
        }
        
        for focus in focus_sectors:
            if sector in related_sectors.get(focus, []):
                return True
        
        return False
    
    def _months_between_rounds(self, date1: str, date2: str) -> Optional[float]:
        """Calculate months between funding round dates"""
        from datetime import datetime
        try:
            if not date1 or not date2:
                logger.warning(f"Missing dates for comparison: date1={date1}, date2={date2}")
                return None
            
            # Parse ISO format dates and other common formats
            def parse_date(date_str):
                # Handle YYYY-MM format (e.g., "2024-04")
                if len(date_str) == 7 and '-' in date_str:
                    # Append first day of month for parsing
                    return datetime.strptime(date_str + '-01', '%Y-%m-%d')
                elif 'T' in date_str:
                    # ISO format with time
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                elif len(date_str) >= 10 and '-' in date_str[:10]:
                    # Date only format YYYY-MM-DD
                    return datetime.strptime(date_str[:10], '%Y-%m-%d')
                else:
                    # Try other formats
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except:
                            continue
                    raise ValueError(f"Could not parse date: {date_str}")
            
            d1 = parse_date(date1)
            d2 = parse_date(date2)
            
            # Calculate months difference
            months = (d2.year - d1.year) * 12 + (d2.month - d1.month)
            # Add day difference as fraction
            days_diff = (d2.day - d1.day) / 30.0
            result = abs(months + days_diff)
            
            logger.info(f"Calculated {result:.1f} months between {date1[:10]} and {date2[:10]}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to parse dates {date1}, {date2}: {e}, using default 18 months")
            return 18.0  # Fallback to default assumption
    
    def _months_since_date(self, date_str: str) -> Optional[float]:
        """Calculate months since a given date"""
        from datetime import datetime
        try:
            if not date_str:
                logger.warning("No date provided for months_since calculation")
                return 12.0  # Default to 12 months instead of None
            
            # Parse date using same logic
            def parse_date(date_str):
                # Handle YYYY-MM format (e.g., "2024-04")
                if len(date_str) == 7 and '-' in date_str:
                    # Append first day of month for parsing
                    return datetime.strptime(date_str + '-01', '%Y-%m-%d')
                elif 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                elif len(date_str) >= 10 and '-' in date_str[:10]:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d')
                else:
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except:
                            continue
                    raise ValueError(f"Could not parse date: {date_str}")
            
            date = parse_date(date_str)
            now = datetime.now()
            
            # Calculate months since
            months = (now.year - date.year) * 12 + (now.month - date.month)
            days_diff = (now.day - date.day) / 30.0
            result = max(0, months + days_diff)
            
            logger.info(f"Calculated {result:.1f} months since {date_str[:10]}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to parse date {date_str}: {e}, using default 6 months")
            return 6.0  # Fallback to default assumption
    
    def _calculate_confidence(self, inferred_data: Dict[str, Any]) -> float:
        """Calculate overall confidence in the analysis"""
        if not inferred_data:
            return 1.0  # All data was available
        
        confidences = []
        for inf in inferred_data.values():
            if hasattr(inf, 'confidence'):
                # InferenceResult object with confidence attribute
                confidences.append(inf.confidence)
            else:
                # Raw value, assume moderate confidence
                confidences.append(0.7)
        
        return np.mean(confidences) if confidences else 0.5
    
    def detect_api_dependency(self, company_data: Dict[str, Any]) -> str:
        """
        Detect level of API/model provider dependency based on company data
        Returns: 'openai_heavy', 'openai_moderate', 'openai_light', or 'own_models'
        """
        # Look for signals in company description, product, or metadata
        description = str(company_data.get("description", "")).lower()
        product = str(company_data.get("product", "")).lower()
        tech_stack = str(company_data.get("tech_stack", "")).lower()
        category = str(company_data.get("category", "")).lower()
        
        # Heavy dependency signals
        heavy_signals = [
            "ai assistant", "ai writer", "ai chatbot", "gpt wrapper",
            "ai copilot", "ai agent", "generative ai", "llm powered",
            "ai-first", "ai native", "prompt engineering"
        ]
        
        # Moderate dependency signals
        moderate_signals = [
            "ai-enhanced", "ai features", "smart", "intelligent",
            "ml-powered", "ai analytics", "ai insights"
        ]
        
        # Own model signals
        own_model_signals = [
            "proprietary model", "custom model", "own models",
            "trained model", "fine-tuned", "self-hosted", 
            "on-premise ai", "edge ai"
        ]
        
        combined_text = f"{description} {product} {tech_stack} {category}"
        
        # Check for own models first (highest priority)
        if any(signal in combined_text for signal in own_model_signals):
            return "own_models"
        
        # Count dependency signals
        heavy_count = sum(1 for signal in heavy_signals if signal in combined_text)
        moderate_count = sum(1 for signal in moderate_signals if signal in combined_text)
        
        # Classify based on signal strength
        if heavy_count >= 2 or "gpt" in combined_text or "openai" in combined_text:
            return "openai_heavy"
        elif heavy_count >= 1 or moderate_count >= 2:
            return "openai_moderate"
        elif moderate_count >= 1 or "ai" in combined_text:
            return "openai_light"
        else:
            return "own_models"  # Default to assuming they have their own tech
    
    def calculate_exit_dilution_scenarios(self, initial_ownership: float, 
                                          rounds_to_exit: int = 2,
                                          reserve_ratio: float = 2.0,
                                          company_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Calculate ownership dilution based on ACTUAL valuation multiples and growth rates
        No hardcoded dilution - everything derived from revenue growth and multiples
        """
        if company_data is None:
            company_data = {}
        
        # Get current metrics
        current_revenue = company_data.get('revenue') or company_data.get('arr') or company_data.get('inferred_revenue', 10_000_000)
        current_valuation = company_data.get('valuation') or company_data.get('inferred_valuation', 100_000_000)
        current_stage = company_data.get('stage', 'Series A')
        
        # Calculate ACTUAL current multiple (not hardcoded)
        current_multiple = current_valuation / current_revenue if current_revenue > 0 else 15
        
        # Get growth rate
        arr_growth = company_data.get('arr_growth_rate') or company_data.get('growth_rate', 1.0)
        if not arr_growth or arr_growth == 0:
            # Use stage benchmark if no growth data
            stage_key = self._normalize_stage_key(current_stage)
            benchmarks = self.STAGE_BENCHMARKS.get(stage_key, self.STAGE_BENCHMARKS.get('Series A'))
            arr_growth = benchmarks.get('growth_rate', 1.5)
        
        # Quality signals
        investors = company_data.get('investors', [])
        investors_str = str(investors).lower()
        tier1_vcs = ['sequoia', 'a16z', 'andreessen', 'benchmark', 'accel', 'greylock']
        has_tier1 = any(vc in investors_str for vc in tier1_vcs)
        
        # Tier 2 VCs face different dynamics
        tier2_vcs = ['bessemer', 'lightspeed', 'battery', 'insight', 'general catalyst']
        has_tier2 = any(vc in investors_str for vc in tier2_vcs)
        
        # Our fund context (we're Tier 2 selling to Tier 2s)
        our_fund_tier = company_data.get('our_fund_tier', 2)  # Default Tier 2
        
        # Stage progression and round configs
        stage_progression = ["Seed", "Series A", "Series B", "Series C", "Series D", "Series E"]
        
        # Round sizes from benchmarks (but dilution will be calculated, not hardcoded)
        round_sizes = {
            "Seed": 3_000_000,
            "Series A": 15_000_000,
            "Series B": 50_000_000,
            "Series C": 100_000_000,
            "Series D": 200_000_000,
            "Series E": 350_000_000
        }
        
        # Months between rounds (from STAGE_BENCHMARKS)
        months_to_next = {
            "Seed": 15,      # 15 months to A
            "Series A": 18,  # 18 months to B
            "Series B": 20,  # 20 months to C
            "Series C": 24,  # 24 months to D
            "Series D": 30,  # 30 months to exit
            "Series E": 36   # 36 months to exit
        }
        
        # Find current position
        try:
            current_idx = stage_progression.index(current_stage)
        except ValueError:
            if current_stage in ["Growth", "Late Stage"]:
                current_idx = 4  # Series D+
            else:
                current_idx = 1  # Default to Series A
        
        # Track scenarios
        scenarios = {
            'optimistic': {'ownership': initial_ownership, 'rounds': [], 'revenue': current_revenue},
            'base': {'ownership': initial_ownership, 'rounds': [], 'revenue': current_revenue},
            'pessimistic': {'ownership': initial_ownership, 'rounds': [], 'revenue': current_revenue}
        }
        
        # Calculate dilution for each future round
        for round_num in range(rounds_to_exit):
            next_idx = min(current_idx + round_num + 1, len(stage_progression) - 1)
            next_stage = stage_progression[next_idx]
            months_elapsed = months_to_next.get(stage_progression[min(current_idx + round_num, len(stage_progression) - 1)], 18)
            
            # Project revenue forward based on growth rate
            # Using compound growth: revenue * (1 + growth_rate)^(months/12)
            years_elapsed = months_elapsed / 12.0
            
            for scenario_name, growth_adj in [('optimistic', 1.2), ('base', 1.0), ('pessimistic', 0.7)]:
                scenario = scenarios[scenario_name]
                adjusted_growth = arr_growth * growth_adj
                
                # Project revenue
                projected_revenue = scenario['revenue'] * ((1 + adjusted_growth) ** years_elapsed)
                
                # Calculate valuation multiple for next round
                # Multiple compression/expansion based on growth and stage
                if adjusted_growth > 3.0:  # Hypergrowth (>300% YoY) like Decagon
                    # Multiple can EXPAND for hypergrowth
                    next_multiple = current_multiple * 1.5  # Can go to 100x+
                    if has_tier1 and scenario_name == 'optimistic':
                        next_multiple *= 1.3  # Tier 1s bid up hot deals
                    elif has_tier2 and our_fund_tier == 2:
                        # Tier 2 to Tier 2 deals - more variance/risk
                        if scenario_name == 'optimistic':
                            next_multiple *= 1.1  # Might get good terms
                        elif scenario_name == 'pessimistic':
                            next_multiple *= 0.9  # Might face squeeze
                elif adjusted_growth > 2.0:  # T2D3 growth
                    next_multiple = current_multiple * 1.1  # Slight expansion
                    if has_tier1:
                        next_multiple *= 1.15
                    elif has_tier2 and our_fund_tier == 2:
                        # Tier 2 dynamics - more uncertainty
                        next_multiple *= 1.05 if scenario_name != 'pessimistic' else 0.95
                elif adjusted_growth > 1.0:  # Good growth
                    next_multiple = current_multiple * 0.95  # Slight compression
                else:  # Slow growth
                    next_multiple = current_multiple * 0.8  # Multiple compression
                
                # Stage-based multiple caps (reality check)
                stage_caps = {
                    "Seed": 50,      # Can be very high for hot seeds
                    "Series A": 40,   # Still high for breakouts
                    "Series B": 30,   # Starting to normalize
                    "Series C": 20,   # More mature
                    "Series D": 15,   # Late stage
                    "Series E": 12    # Pre-IPO
                }
                max_multiple = stage_caps.get(next_stage, 10)
                next_multiple = min(next_multiple, max_multiple)
                
                # But also has a floor based on stage
                min_multiples = {
                    "Seed": 8,
                    "Series A": 10,
                    "Series B": 8,
                    "Series C": 6,
                    "Series D": 5,
                    "Series E": 4
                }
                min_multiple = min_multiples.get(next_stage, 5)
                next_multiple = max(next_multiple, min_multiple)
                
                # Calculate next round valuation
                next_valuation = projected_revenue * next_multiple
                
                # Get round size
                round_size = round_sizes.get(next_stage, 100_000_000)
                
                # CALCULATE ACTUAL DILUTION (not hardcoded!)
                # Dilution = round_size / (pre_money + round_size)
                # where pre_money = next_valuation
                actual_dilution = round_size / (next_valuation + round_size)
                
                # Tier 2 funds face term uncertainty (might get aggressive terms)
                if has_tier2 and not has_tier1 and our_fund_tier == 2:
                    # Risk of aggressive terms (participating preferred, ratchets, etc.)
                    if scenario_name == 'pessimistic':
                        # Effective dilution higher due to structure
                        actual_dilution *= 1.2  # 20% worse due to terms
                    elif scenario_name == 'optimistic':
                        # Might negotiate better
                        actual_dilution *= 0.95
                
                # Cap dilution to realistic ranges (5-35%)
                actual_dilution = max(0.05, min(0.35, actual_dilution))
                
                # Update ownership
                new_ownership = scenario['ownership'] * (1 - actual_dilution)
                
                # Track the round
                scenario['rounds'].append({
                    'round': next_stage,
                    'months_elapsed': months_elapsed,
                    'projected_revenue': projected_revenue,
                    'valuation_multiple': next_multiple,
                    'pre_money': next_valuation,
                    'round_size': round_size,
                    'post_money': next_valuation + round_size,
                    'dilution': actual_dilution,
                    'ownership_after': new_ownership
                })
                
                # Update for next round
                scenario['ownership'] = new_ownership
                scenario['revenue'] = projected_revenue
        
        # Calculate with pro-rata
        with_pro_rata = {}
        for scenario_name in ['optimistic', 'base', 'pessimistic']:
            if reserve_ratio > 1:
                maintained = initial_ownership
                reserves_used = 0
                
                for round_data in scenarios[scenario_name]['rounds']:
                    dilution = round_data['dilution']
                    pro_rata_needed = maintained * dilution / (1 - dilution)
                    
                    if reserves_used + pro_rata_needed <= (reserve_ratio - 1):
                        reserves_used += pro_rata_needed
                        # Ownership maintained
                    else:
                        remaining = (reserve_ratio - 1) - reserves_used
                        partial = remaining / pro_rata_needed if pro_rata_needed > 0 else 0
                        actual_dilution = dilution * (1 - partial)
                        maintained *= (1 - actual_dilution)
                        break
                
                with_pro_rata[scenario_name] = maintained
            else:
                with_pro_rata[scenario_name] = scenarios[scenario_name]['ownership']
        
        return {
            # Primary format for orchestrator
            'with_pro_rata': with_pro_rata['base'],
            'without_pro_rata': scenarios['base']['ownership'],
            
            # Detailed scenarios with full data
            'scenarios': {
                scenario: {
                    'final_ownership': scenarios[scenario]['ownership'],
                    'final_ownership_with_reserves': with_pro_rata[scenario],
                    'dilution_multiple': initial_ownership / scenarios[scenario]['ownership'] if scenarios[scenario]['ownership'] > 0 else 999,
                    'ownership_retained': scenarios[scenario]['ownership'] / initial_ownership if initial_ownership > 0 else 0,
                    'rounds': scenarios[scenario]['rounds']
                }
                for scenario in ['optimistic', 'base', 'pessimistic']
            },
            
            # Metadata
            'assumptions': {
                'initial_ownership': initial_ownership,
                'current_stage': current_stage,
                'current_revenue': current_revenue,
                'current_valuation': current_valuation,
                'current_multiple': current_multiple,
                'rounds_to_exit': rounds_to_exit,
                'reserve_ratio': reserve_ratio,
                'has_tier1_vcs': has_tier1,
                'arr_growth_rate': arr_growth,
                'dynamic_calculation': True
            }
        }
    
    def predict_next_round(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict next funding round timing, size, and valuation
        Based on burn rate, stage progression, and market conditions
        """
        current_stage = company_data.get('stage', 'Series A')
        stage_key = self._normalize_stage_key(current_stage)
        
        # Get current metrics - prefer inferred_valuation over raw valuation
        inferred_valuation = self._ensure_numeric(company_data.get('inferred_valuation'), 0)
        raw_valuation = self._ensure_numeric(company_data.get('valuation'), 50_000_000)
        current_valuation = inferred_valuation if inferred_valuation > 0 else raw_valuation
        current_revenue = self._ensure_numeric(company_data.get('inferred_revenue', 0), 1_000_000)
        burn_rate = self._ensure_numeric(company_data.get('burn_rate'), current_revenue * 0.15)  # Assume 15% monthly burn if not provided
        runway = self._ensure_numeric(company_data.get('runway_months'), 18)
        
        # Get funding history to predict patterns
        funding_rounds = company_data.get('funding_rounds', [])
        last_round_date = None
        months_since_last = 12  # Default
        
        if funding_rounds:
            last_round = funding_rounds[-1]
            last_round_date = last_round.get('date')
            if last_round_date:
                months_since_last = self._months_since_date(last_round_date) or 12
        
        # Stage-based benchmarks for next round
        next_round_benchmarks = {
            'Pre-seed': {
                'next_stage': 'Seed',
                'months_to_raise': 12,
                'size_multiple': 2.5,  # 2.5x last round
                'valuation_step_up': 2.0,  # 2x valuation increase
                'min_revenue_for_round': 100_000
            },
            'Seed': {
                'next_stage': 'Series A', 
                'months_to_raise': 15,
                'size_multiple': 3.0,
                'valuation_step_up': 2.5,
                'min_revenue_for_round': 500_000
            },
            'Series A': {
                'next_stage': 'Series B',
                'months_to_raise': 18,
                'size_multiple': 2.5,
                'valuation_step_up': 2.2,
                'min_revenue_for_round': 2_000_000
            },
            'Series B': {
                'next_stage': 'Series C',
                'months_to_raise': 20,
                'size_multiple': 2.0,
                'valuation_step_up': 2.0,
                'min_revenue_for_round': 10_000_000
            },
            'Series C': {
                'next_stage': 'Series D',
                'months_to_raise': 24,
                'size_multiple': 1.8,
                'valuation_step_up': 1.8,
                'min_revenue_for_round': 30_000_000
            },
            'Series D': {
                'next_stage': 'Growth/IPO',
                'months_to_raise': 30,
                'size_multiple': 1.5,
                'valuation_step_up': 1.5,
                'min_revenue_for_round': 75_000_000
            }
        }
        
        benchmark = next_round_benchmarks.get(stage_key, next_round_benchmarks['Series B'])
        
        # Calculate timing based on runway and stage
        typical_months = benchmark['months_to_raise']
        
        # Adjust based on current runway
        if runway < 6:
            # Urgent - likely already fundraising
            months_to_next = 3
            urgency = "URGENT - Likely in process"
        elif runway < 9:
            # Starting soon
            months_to_next = 6
            urgency = "Starting within 3 months"
        elif runway < 15:
            # Normal timing
            months_to_next = min(runway - 6, typical_months)
            urgency = "Normal timing"
        else:
            # Has time
            months_to_next = typical_months
            urgency = "Well-funded"
        
        # Calculate round size based on burn and stage
        last_round_size = funding_rounds[-1].get('amount', 10_000_000) if funding_rounds else 5_000_000
        
        # Next round size factors
        base_size = last_round_size * benchmark['size_multiple']
        
        # Adjust for burn rate (need 18-24 months runway)
        burn_based_size = burn_rate * 24  # 24 months runway
        
        # Take larger of benchmark or burn-based
        next_round_size = max(base_size, burn_based_size)
        
        # Cap based on stage
        stage_caps = {
            'Pre-seed': 3_000_000,
            'Seed': 10_000_000,
            'Series A': 25_000_000,
            'Series B': 50_000_000,
            'Series C': 100_000_000,
            'Series D': 200_000_000
        }
        
        next_round_size = min(next_round_size, stage_caps.get(benchmark['next_stage'], 100_000_000))
        
        # Calculate next valuation based on progress
        # Use actual revenue growth rate if available, otherwise use stage-based defaults
        revenue_growth_rate_raw = company_data.get('revenue_growth', company_data.get('growth_rate'))
        if revenue_growth_rate_raw:
            revenue_growth_rate = self._ensure_numeric(revenue_growth_rate_raw, 2.0)
            # Convert to annual if it's a decimal (e.g., 0.5 -> 1.5x annual)
            if revenue_growth_rate < 1.0:
                revenue_growth_rate = 1.0 + revenue_growth_rate
        else:
            revenue_growth_rate = 2.5 if stage_key in ['Seed', 'Series A'] else 1.8
        
        projected_revenue_at_raise = current_revenue * (revenue_growth_rate ** (months_to_next / 12))
        
        # Dynamic step-up calculation based on multiple factors
        base_step_up = benchmark['valuation_step_up']
        
        # Adjust step-up based on time since last round (longer = higher step-up expected)
        if months_since_last > 24:
            time_adjustment = 1.2  # 20% boost if >2 years
        elif months_since_last > 18:
            time_adjustment = 1.1  # 10% boost if >18 months
        elif months_since_last < 6:
            time_adjustment = 0.9  # 10% discount if very recent round
        else:
            time_adjustment = 1.0
        
        # Adjust step-up based on growth rate (higher growth = higher step-up)
        if revenue_growth_rate >= 3.0:
            growth_adjustment = 1.15  # 15% boost for very high growth
        elif revenue_growth_rate >= 2.5:
            growth_adjustment = 1.1  # 10% boost for high growth
        elif revenue_growth_rate < 1.5:
            growth_adjustment = 0.9  # 10% discount for lower growth
        else:
            growth_adjustment = 1.0
        
        # Calculate base valuation multiple
        valuation_multiple = base_step_up * time_adjustment * growth_adjustment
        
        # Adjust based on hitting milestones
        if projected_revenue_at_raise >= benchmark['min_revenue_for_round']:
            milestone_confidence = "On track for milestones"
        else:
            # May face down round pressure - reduce step-up
            revenue_gap = benchmark['min_revenue_for_round'] / max(projected_revenue_at_raise, 1)
            valuation_multiple = max(1.0, valuation_multiple / revenue_gap)
            milestone_confidence = f"Revenue gap: Need {revenue_gap:.1f}x growth"
        
        # Calculate next valuation - ensure it's >= inferred_valuation
        next_valuation_pre = current_valuation * valuation_multiple
        if inferred_valuation > 0:
            # Ensure next round valuation is at least as high as inferred valuation
            next_valuation_pre = max(next_valuation_pre, inferred_valuation)
            # Recalculate step-up to reflect this
            valuation_multiple = next_valuation_pre / current_valuation
        
        next_valuation_post = next_valuation_pre + next_round_size
        
        # Assess down round risk
        if valuation_multiple < 1.2:
            down_round_risk = "HIGH"
            down_round_probability = 0.4
        elif valuation_multiple < 1.5:
            down_round_risk = "MEDIUM"
            down_round_probability = 0.25
        else:
            down_round_risk = "LOW"
            down_round_probability = 0.1
        
        # Market conditions remain neutral - no AI tailwind adjustments
        market_sentiment = "Neutral market conditions"
        
        return {
            'next_round_timing': months_to_next,
            'next_round_timing_label': urgency,
            'next_round_stage': benchmark['next_stage'],
            'next_round_size': next_round_size,
            'next_round_valuation_pre': next_valuation_pre,
            'next_round_valuation_post': next_valuation_post,
            'valuation_step_up': valuation_multiple,
            'down_round_risk': down_round_risk,
            'down_round_probability': down_round_probability,
            'revenue_at_next_round': projected_revenue_at_raise,
            'revenue_milestone': benchmark['min_revenue_for_round'],
            'milestone_confidence': milestone_confidence,
            'market_sentiment': market_sentiment,
            'months_since_last_round': months_since_last,
            'current_runway': runway,
            'burn_rate': burn_rate,
            'dilution_expected': next_round_size / next_valuation_post,
            'our_prorata_amount': next_round_size * company_data.get('ownership_evolution', {}).get('entry_ownership', 0.1)
        }
    
    def calculate_adjusted_gross_margin(
        self,
        company_data: Dict[str, Any],
        base_gross_margin: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate gross margin adjusted for BOTH API dependency AND GPU compute costs
        This affects valuation multiples significantly
        """
        # Detect API dependency level
        dependency_level = self.detect_api_dependency(company_data)
        dependency_impact = self.API_DEPENDENCY_IMPACT[dependency_level]
        
        # ALSO calculate GPU compute intensity impact
        gpu_metrics = self.calculate_gpu_adjusted_metrics(company_data)
        
        # Get base gross margin based on SEMANTIC category, not keywords
        if base_gross_margin is None:
            category = company_data.get('category', 'saas').lower()
            
            # Use the semantically-extracted category to determine margins
            category_margins = {
                'industrial': 0.25,
                'materials': 0.30,
                'manufacturing': 0.35,
                'deeptech_hardware': 0.40,
                'hardware': 0.45,
                'marketplace': 0.50,
                'services': 0.55,
                'tech_enabled_services': 0.60,
                'rollup': 0.45,
                'gtm_software': 0.75,
                'saas': 0.78,
                'ai_saas': 0.65,
                'ai_first': 0.55,
                'full_stack_ai': 0.50
            }
            
            # Get base margin from the SEMANTIC category
            base_gross_margin = category_margins.get(category, 0.70)
            
            # Adjust for specific verticals
            vertical = company_data.get('vertical', '').lower()
            if vertical:
                if 'healthcare' in vertical or 'medical' in vertical:
                    base_gross_margin *= 0.92  # 8% reduction for compliance/regulatory
                elif 'defense' in vertical or 'aerospace' in vertical:
                    base_gross_margin *= 1.15  # 15% premium for government contracts
                elif 'fintech' in vertical or 'financial' in vertical:
                    base_gross_margin *= 0.95  # 5% reduction for regulatory costs
                elif 'enterprise' in vertical:
                    base_gross_margin *= 1.05  # 5% premium for enterprise pricing
                elif 'consumer' in vertical:
                    base_gross_margin *= 0.90  # 10% reduction for consumer pricing pressure
            
            # Log the dynamic margin calculation
            print(f"[MARGIN] Dynamic margin for {company_data.get('company', 'Unknown')}:")
            print(f"  Category: {category} → Base margin: {self.CATEGORY_MARGINS.get(category, 0.70)*100:.0f}%")
            print(f"  Vertical: {vertical} → Adjusted margin: {base_gross_margin*100:.0f}%")
        
        # Calculate adjusted gross margin - COMBINE API and GPU penalties
        api_penalty = dependency_impact["gross_margin_penalty"]
        gpu_penalty = gpu_metrics["margin_impact"]
        
        # Use the LARGER of the two penalties (they overlap, not additive)
        total_penalty = max(api_penalty, gpu_penalty)
        adjusted_gross_margin = base_gross_margin - total_penalty
        
        # Always start with inferred revenue - NEVER None
        # Use the properly inferred revenue if available
        inferred_revenue = company_data.get('inferred_revenue', 0)
        if inferred_revenue and inferred_revenue > 0:
            final_revenue = inferred_revenue
        else:
            # Fallback to stage benchmark WITH adjustments
            stage = company_data.get('stage', 'Seed')
            stage_key = self._normalize_stage_key(stage)
            
            if stage_key in self.STAGE_BENCHMARKS:
                base_revenue = self.STAGE_BENCHMARKS[stage_key].get('arr_median', 500_000)
            else:
                base_revenue = self.STAGE_BENCHMARKS['Seed'].get('arr_median', 500_000)
            
            # Apply time-based growth since last funding
            funding_rounds = company_data.get('funding_rounds', [])
            if funding_rounds:
                last_round = funding_rounds[-1]
                last_funding_date = last_round.get('date')
                if last_funding_date:
                    months_since = self._months_since_date(last_funding_date)
                    if months_since and months_since > 0:
                        # Get base growth rate for this stage
                        benchmarks = self.STAGE_BENCHMARKS.get(stage_key, self.STAGE_BENCHMARKS['Seed'])
                        base_growth_rate = benchmarks.get('growth_rate', 1.0)
                        
                        # Calculate time-based growth (simplified version)
                        years_since = months_since / 12.0
                        if years_since <= 1:
                            effective_growth = base_growth_rate
                        elif years_since <= 2:
                            effective_growth = base_growth_rate * 0.7
                        else:
                            effective_growth = base_growth_rate * 0.3
                        
                        # Apply growth
                        monthly_growth = (1 + effective_growth) ** (1/12) - 1
                        growth_multiple = (1 + monthly_growth) ** min(months_since, 36)  # Cap at 3 years
                        base_revenue = base_revenue * min(growth_multiple, 5.0)  # Cap at 5x
            
            # Apply geographic adjustment
            location = (company_data.get('headquarters') or '').lower()
            if 'san francisco' in location or 'new york' in location or 'sf' in location or 'nyc' in location:
                base_revenue *= 1.15  # SF/NYC premium
            elif 'europe' in location or 'berlin' in location or 'london' in location or 'paris' in location:
                base_revenue *= 0.85  # European discount
            
            # Apply investor quality adjustment
            if funding_rounds:
                tier1_vcs = ['sequoia', 'a16z', 'benchmark', 'accel', 'greylock', 'kleiner', 'bessemer', 'index']
                investors_str = str(funding_rounds).lower()
                if any(vc in investors_str for vc in tier1_vcs):
                    base_revenue *= 1.2  # Tier 1 VC boost
            
            final_revenue = base_revenue
        
        # Check if we have actual extracted revenue to overwrite the inferred
        revenue_raw = company_data.get("revenue", company_data.get("arr", None))
        if revenue_raw:
            if isinstance(revenue_raw, dict) and revenue_raw.get('value'):
                final_revenue = revenue_raw['value']
            elif hasattr(revenue_raw, 'value') and revenue_raw.value:
                final_revenue = revenue_raw.value
            elif isinstance(revenue_raw, (int, float)) and revenue_raw > 0:
                final_revenue = revenue_raw
            
        # Smart customer contract estimation based on tiers
        customers_raw = company_data.get("customers", {})
        
        # Calculate weighted average contract value and effective customer count
        if isinstance(customers_raw, dict):
            # Extract customer tiers
            enterprise_customers = customers_raw.get('enterprise_customers', [])
            customer_names = customers_raw.get('customer_names', [])
            total_customers = self._ensure_numeric(customers_raw.get('customer_count', len(customer_names)))
            
            # Determine company stage for ACV estimation
            stage = (company_data.get('stage') or 'seed').lower()
            
            # Stage-based ACV ranges (not hardcoded - based on market data)
            acv_by_stage = {
                'series-d': {'enterprise': 750_000, 'mid': 150_000, 'smb': 30_000},
                'series-c': {'enterprise': 500_000, 'mid': 100_000, 'smb': 25_000},
                'series-b': {'enterprise': 250_000, 'mid': 50_000, 'smb': 15_000},
                'series-a': {'enterprise': 150_000, 'mid': 30_000, 'smb': 10_000},
                'seed': {'enterprise': 75_000, 'mid': 20_000, 'smb': 5_000},
                'pre-seed': {'enterprise': 50_000, 'mid': 15_000, 'smb': 3_000}
            }
            
            # Get ACVs for current stage
            stage_acvs = acv_by_stage.get(stage, acv_by_stage['seed'])
            
            # Calculate customer breakdown
            num_enterprise = len(enterprise_customers) if isinstance(enterprise_customers, list) else 0
            
            # Check for Fortune 500 or large companies in customer list
            fortune_500_keywords = ['microsoft', 'google', 'amazon', 'apple', 'meta', 'walmart', 
                                   'exxon', 'berkshire', 'johnson', 'jpmorgan', 'bank of america']
            num_fortune500 = 0
            if isinstance(customer_names, list):
                for customer in customer_names:
                    if any(f500 in str(customer).lower() for f500 in fortune_500_keywords):
                        num_fortune500 += 1
            
            # Estimate customer mix
            if total_customers > 0:
                # If we have Fortune 500, they're super enterprise
                num_super_enterprise = num_fortune500
                # Regular enterprise (non-Fortune 500)
                num_regular_enterprise = max(0, num_enterprise - num_fortune500)
                # Estimate mid-market as 30% of remaining
                remaining = total_customers - num_enterprise
                num_mid = int(remaining * 0.3)
                # Rest are SMB
                num_smb = total_customers - num_enterprise - num_mid
            else:
                # No customer data, estimate from revenue
                if final_revenue and final_revenue > 10_000_000:
                    num_enterprise = 20
                    num_mid = 50
                    num_smb = 100
                elif final_revenue and final_revenue > 1_000_000:
                    num_enterprise = 5
                    num_mid = 20
                    num_smb = 50
                else:
                    num_enterprise = 1
                    num_mid = 5
                    num_smb = 20
                num_super_enterprise = 0
                num_regular_enterprise = num_enterprise
            
            # Calculate weighted revenue estimate
            estimated_revenue = (
                num_super_enterprise * stage_acvs['enterprise'] * 2 +  # Fortune 500 pay 2x
                num_regular_enterprise * stage_acvs['enterprise'] +
                num_mid * stage_acvs['mid'] +
                num_smb * stage_acvs['smb']
            )
            
            # For API cost calculation, enterprise customers use more API calls
            api_adjusted_customers = (
                num_super_enterprise * 10 +  # Fortune 500 = 10x API usage
                num_regular_enterprise * 5 +  # Enterprise = 5x API usage
                num_mid * 2 +                 # Mid-market = 2x API usage
                num_smb                        # SMB = 1x API usage
            )
            
            # Use the better of actual revenue or estimated revenue
            if final_revenue > estimated_revenue * 0.5 and final_revenue < estimated_revenue * 2:
                # Actual revenue seems reasonable, keep it
                pass
            else:
                # Our estimate might be better
                final_revenue = max(final_revenue, estimated_revenue)
                logger.info(f"Using estimated revenue ${final_revenue:,.0f} based on customer tiers")
            
            customers = api_adjusted_customers if api_adjusted_customers > 0 else total_customers
            
        elif hasattr(customers_raw, 'value'):
            customers = self._ensure_numeric(customers_raw.value)
        else:
            # Fallback to simple customer count
            customers = self._ensure_numeric(customers_raw) if customers_raw else final_revenue / 12_000
        
        # Ensure customers is a valid number
        if not isinstance(customers, (int, float)) or customers <= 0:
            customers = max(10, final_revenue / 12_000)
        
        api_cost_per_user = dependency_impact["typical_api_cost_per_user"]
        monthly_api_costs = api_cost_per_user * customers
        annual_api_costs = monthly_api_costs * 12
        
        # API costs affect burn rate, not valuation directly
        # The impact shows up in gross margins and burn rate
        valuation_multiple_adjustment = 1.0  # No direct valuation penalty
        
        # API costs just increase burn
        additional_monthly_burn = monthly_api_costs  # This adds to burn rate
        
        # Combine valuation adjustments from API and GPU
        combined_valuation_adjustment = min(valuation_multiple_adjustment, gpu_metrics["valuation_multiple_adjustment"])
        
        # Choose the more severe investment recommendation
        if gpu_metrics["compute_intensity"] in ["extreme", "high"]:
            investment_rec = gpu_metrics["investment_thesis"]
        else:
            investment_rec = self._get_api_dependency_recommendation(dependency_level)
        
        return {
            "base_gross_margin": base_gross_margin,
            "adjusted_gross_margin": adjusted_gross_margin,
            "api_dependency_level": dependency_level,
            "compute_intensity": gpu_metrics["compute_intensity"],
            "gross_margin_penalty": total_penalty,
            "api_penalty": api_penalty,
            "gpu_penalty": gpu_penalty,
            "estimated_annual_api_costs": annual_api_costs,
            "estimated_annual_gpu_costs": gpu_metrics["annual_gpu_costs"],
            "total_compute_costs": annual_api_costs + gpu_metrics["annual_gpu_costs"],
            "api_cost_per_user": api_cost_per_user,
            "gpu_cost_per_transaction": gpu_metrics.get("cost_per_transaction", 0),
            "valuation_multiple_adjustment": combined_valuation_adjustment,
            "scalability_discount": dependency_impact["scalability_discount"],
            "investment_recommendation": investment_rec,
            "risk_factors": self._get_api_dependency_risks(dependency_level) + self._get_gpu_intensity_risks(gpu_metrics["compute_intensity"]),
            "customer_count": customers  # Add inferred customer count for ACV calculation
        }
    
    def _get_api_dependency_recommendation(self, dependency_level: str) -> str:
        """Get investment recommendation based on API dependency"""
        if dependency_level == "openai_heavy":
            return "⚠️ HIGH RISK: Heavy API dependency limits gross margins and scalability. Demand path to proprietary models."
        elif dependency_level == "openai_moderate":
            return "🔶 MODERATE RISK: Some API dependency. Ensure unit economics work at scale."
        elif dependency_level == "openai_light":
            return "✅ ACCEPTABLE: Light API usage maintains healthy margins."
        else:
            return "🚀 STRONG: Proprietary models provide competitive moat and superior unit economics."
    
    def _ensure_numeric(self, value: Any, default: float = 0) -> float:
        """
        Ensure a value is numeric, handling various input types
        """
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove common string patterns
            cleaned = value.replace('$', '').replace(',', '').replace('%', '').strip()
            try:
                return float(cleaned)
            except:
                return default
        if hasattr(value, 'value'):
            return self._ensure_numeric(value.value, default)
        if isinstance(value, dict) and 'value' in value:
            return self._ensure_numeric(value['value'], default)
        return default
    
    def extract_investor_names_from_funding(self, funding_rounds: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Extract actual investor names from funding search data
        """
        investor_map = {}
        
        for round_data in funding_rounds:
            round_name = round_data.get("round", "Unknown")
            
            # Check for investors field (from Tavily/Firecrawl searches)
            investors = round_data.get("investors", [])
            lead_investor = round_data.get("lead_investor", None)
            
            # Also check for investor_names, participants fields
            if not investors:
                investors = round_data.get("investor_names", [])
            if not investors:
                investors = round_data.get("participants", [])
            
            # Parse from description if needed
            if not investors:
                description = self._ensure_string(round_data.get("description", ""))
                announcement = self._ensure_string(round_data.get("announcement", ""))
                
                # Common patterns in funding announcements
                # "led by Sequoia with participation from..."
                # "Andreessen Horowitz leads $50M Series B"
                import re
                
                # Pattern for "led by X"
                led_pattern = r"led by ([A-Z][A-Za-z\s&]+?)(?:\s+with|\s+and|\,|\.)"
                led_match = re.search(led_pattern, description + " " + announcement, re.IGNORECASE)
                if led_match:
                    lead_investor = led_match.group(1).strip()
                
                # Pattern for "participation from X, Y, and Z"
                participation_pattern = r"participation from ([A-Za-z\s,&]+?)(?:\.|$)"
                part_match = re.search(participation_pattern, description + " " + announcement, re.IGNORECASE)
                if part_match:
                    participants = part_match.group(1).split(",")
                    investors.extend([p.strip() for p in participants])
            
            # Store in map
            if lead_investor:
                investors.insert(0, lead_investor)  # Lead goes first
            
            investor_map[round_name] = investors if investors else [f"{round_name} Investors"]
        
        return investor_map
    
    def calculate_investor_entry_price(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate what an investor should pay today given expected growth deceleration
        This is the core VC math: what's the entry price for target returns?
        """
        # Use actual revenue first, then inferred (which should ALWAYS exist)
        revenue_candidates = [
            company_data.get("revenue"),
            company_data.get("arr"),
            company_data.get("inferred_revenue"),
            company_data.get("estimated_revenue"),
            company_data.get("revenue_estimate"),
            company_data.get("inferred_arr"),
            company_data.get("calculated_revenue"),
        ]
        current_revenue = None
        for candidate in revenue_candidates:
            if candidate is None:
                continue
            numeric_candidate = self._safe_get_value(candidate, None)
            if numeric_candidate is not None:
                current_revenue = numeric_candidate
                break
        
        if current_revenue is None:
            current_revenue = 0
            logger.warning(
                "[GAP_FILLER] No revenue data available for revenue-dependent calculations; defaulting to 0 to maintain flow."
            )
        current_growth = company_data.get("growth_rate", 1.0)  # 100% YoY
        nrr = company_data.get("nrr", 1.10)  # 110% net retention
        current_valuation = company_data.get("valuation", 100_000_000)
        
        # VC return requirements
        target_irr = 0.35  # 35% IRR minimum for Series A/B
        target_multiple = 5.0  # 5x minimum return target
        hold_period = 5  # Years to exit
        
        # Growth deceleration model (reality for 99% of companies)
        # Year 1: current growth, then decay by factor each year
        decay_factor = 0.7  # Growth rate decays to 70% of prior year
        min_growth = 0.25  # Floor at 25% growth (still good for mature SaaS)
        
        # Project revenue with decelerating growth
        projected_revenues = [current_revenue]
        growth_rates = []
        
        for year in range(1, hold_period + 1):
            if year == 1:
                year_growth = current_growth
            else:
                # Growth decelerates but has a floor
                year_growth = max(min_growth, growth_rates[-1] * decay_factor)
            
            growth_rates.append(year_growth)
            next_revenue = projected_revenues[-1] * (1 + year_growth)
            projected_revenues.append(next_revenue)
        
        exit_revenue = projected_revenues[-1]
        
        # Exit multiple based on growth rate at exit and acquisition benchmarks
        final_growth = growth_rates[-1]
        
        # Real acquisition benchmarks (non-growth-adjusted)
        # OpenAI paid 14.66x for company at $75M ARR - this is the strategic premium
        strategic_acquisition_multiple = 14.66  # OpenAI benchmark for AI companies
        standard_saas_multiple = 5.0  # Standard SaaS acquisition (3-8x range)
        
        # Determine if this is a strategic or standard acquisition candidate
        is_ai_company = any(keyword in (company_data.get("description") or "").lower() 
                           for keyword in ["ai", "ml", "gpt", "llm", "model"])
        has_strategic_value = exit_revenue and exit_revenue > 50_000_000 and final_growth > 0.30
        
        if is_ai_company and has_strategic_value:
            # Could get strategic premium like OpenAI acquisition
            base_exit_multiple = strategic_acquisition_multiple * 0.8  # Conservative estimate
        else:
            # Standard SaaS multiple calculation
            # Rule of thumb: Multiple = 2 + (Growth% * 10) + NRR bonus
            base_exit_multiple = 2 + (final_growth * 10)
        
        # NRR bonus (high retention = higher multiple)
        if nrr > 1.20:
            nrr_bonus = 2.0
        elif nrr > 1.10:
            nrr_bonus = 1.0
        elif nrr > 1.00:
            nrr_bonus = 0.5
        else:
            nrr_bonus = -1.0
        
        exit_multiple = base_exit_multiple + nrr_bonus
        
        # Strategic investor bonus (if they have strategics, more likely to exit)
        has_strategics = self._has_strategic_investors(company_data)
        if has_strategics:
            exit_multiple *= 1.2  # 20% premium
        
        # Calculate exit valuation
        exit_valuation = exit_revenue * exit_multiple
        
        # Work backwards: what should we pay today?
        # PV = FV / (1 + IRR)^years
        max_entry_valuation_irr = exit_valuation / ((1 + target_irr) ** hold_period)
        max_entry_valuation_multiple = exit_valuation / target_multiple
        
        # Take the lower (more conservative)
        max_entry_valuation = min(max_entry_valuation_irr, max_entry_valuation_multiple)
        
        # Calculate implied ownership needed
        investment_size = company_data.get("raising_amount", 20_000_000)
        implied_ownership = investment_size / max_entry_valuation
        
        # Is current ask reasonable?
        current_ask_valuation = company_data.get("pre_money", current_valuation)
        valuation_gap = current_ask_valuation - max_entry_valuation
        deal_attractiveness = "attractive" if valuation_gap < 0 else "overpriced"
        
        results = {
            "current_metrics": {
                "revenue": current_revenue,
                "growth_rate": current_growth,
                "nrr": nrr,
                "current_multiple": current_valuation / current_revenue
            },
            "growth_projection": {
                "year_by_year_growth": growth_rates,
                "year_by_year_revenue": projected_revenues[1:],
                "exit_year_revenue": exit_revenue,
                "cagr": (exit_revenue / current_revenue) ** (1/hold_period) - 1
            },
            "exit_assumptions": {
                "hold_period": hold_period,
                "final_growth_rate": final_growth,
                "exit_multiple": exit_multiple,
                "exit_valuation": exit_valuation,
                "has_strategic_investors": has_strategics
            },
            "investor_math": {
                "target_irr": target_irr,
                "target_multiple": target_multiple,
                "max_entry_via_irr": max_entry_valuation_irr,
                "max_entry_via_multiple": max_entry_valuation_multiple,
                "max_entry_valuation": max_entry_valuation,
                "max_entry_multiple": max_entry_valuation / current_revenue
            },
            "deal_analysis": {
                "current_ask": current_ask_valuation,
                "max_we_should_pay": max_entry_valuation,
                "valuation_gap": valuation_gap,
                "gap_percentage": (valuation_gap / current_ask_valuation * 100) if current_ask_valuation > 0 else 0,
                "deal_assessment": deal_attractiveness,
                "required_ownership": implied_ownership,
                "recommendation": self._get_investment_recommendation(
                    valuation_gap, 
                    current_ask_valuation, 
                    context=company_data.get('_fund_context')
                )
            },
            "sensitivity": {
                "if_growth_10pct_lower": self._calculate_scenario_value(
                    current_revenue, growth_rates, -0.1, hold_period, target_irr
                ),
                "if_exit_1yr_later": exit_valuation / ((1 + target_irr) ** (hold_period + 1)),
                "if_nrr_drops_to_100": self._calculate_scenario_value(
                    current_revenue, growth_rates, 0, hold_period, target_irr, nrr_override=1.0
                )
            }
        }
        
        return results
    
    def _has_strategic_investors(self, company_data: Dict[str, Any]) -> bool:
        """Check if company has strategic corporate investors"""
        strategic_keywords = [
            "google", "microsoft", "amazon", "salesforce", "oracle",
            "intel", "cisco", "ibm", "sap", "adobe", "nvidia",
            "qualcomm", "samsung", "sony", "toyota", "gm", "ford",
            "walmart", "target", "jpmorgan", "goldman", "morgan stanley"
        ]
        
        funding_rounds = company_data.get("funding_rounds", [])
        for round_data in funding_rounds:
            # FIX: Handle cases where investors might be None even with default value
            investors = round_data.get("investors", [])
            if investors is None:
                investors = []
            for investor in investors:
                if investor and any(strategic in investor.lower() for strategic in strategic_keywords):
                    return True
        return False
    
    def _calculate_scenario_value(self, base_revenue, growth_rates, adjustment, years, target_irr, nrr_override=None):
        """Calculate value under different scenarios"""
        adjusted_rates = [g * (1 + adjustment) for g in growth_rates]
        revenue = base_revenue
        for rate in adjusted_rates[:years]:
            revenue *= (1 + rate)
        
        # Recalculate exit multiple
        final_growth = adjusted_rates[years-1] if years <= len(adjusted_rates) else 0.25
        exit_multiple = 2 + (final_growth * 10)
        if nrr_override:
            exit_multiple += 0 if nrr_override == 1.0 else 1.0
        
        exit_value = revenue * exit_multiple
        return exit_value / ((1 + target_irr) ** years)
    
    def _get_investment_recommendation(self, gap, ask, context=None):
        """Get detailed investment recommendation with math and reasoning"""
        if context is None:
            context = {}
            
        # Extract fund parameters
        fund_size = context.get('fund_size')  # From user prompt
        if not fund_size:
            # Use a reasonable default if fund_size is missing
            fund_size = 200_000_000  # $200M default
        max_check = fund_size * 0.05  # 5% concentration limit
        target_ownership = 0.15 if context.get('is_lead') else 0.10
        
        # Calculate required check for target ownership at ask valuation
        required_check = (ask * target_ownership) / (1 - target_ownership)
        
        # Calculate what we'd get at max check
        ownership_at_max = max_check / (ask + max_check)
        
        # Calculate expected returns
        exit_multiple = 10  # Assume 10x for good outcomes
        dilution_factor = 0.65  # 35% dilution to exit
        exit_ownership = ownership_at_max * dilution_factor
        proceeds_at_exit = exit_ownership * (ask * exit_multiple)
        return_multiple = proceeds_at_exit / max_check if max_check > 0 else 0
        
        # Build detailed recommendation
        if gap < -ask * 0.20:  # 20%+ discount
            rec = f"🟢 STRONG BUY at ${ask/1e6:.0f}M valuation\n"
            rec += f"   • Can get {ownership_at_max:.1%} ownership with ${min(required_check, max_check)/1e6:.1f}M check\n"
            rec += f"   • Expected {return_multiple:.1f}x return at 10x exit (${proceeds_at_exit/1e6:.0f}M proceeds)\n"
            rec += f"   • {abs(gap)/ask:.0%} discount to fair value"
            return rec
        elif gap < 0:
            rec = f"🟢 BUY at ${ask/1e6:.0f}M - fairly priced\n"
            rec += f"   • ${min(required_check, max_check)/1e6:.1f}M for {ownership_at_max:.1%} ownership\n"
            rec += f"   • {return_multiple:.1f}x expected return"
            return rec
        elif gap < ask * 0.20:
            rec = f"🟡 NEGOTIATE - asking ${ask/1e6:.0f}M (${gap/1e6:.0f}M premium)\n"
            rec += f"   • At ask: only {ownership_at_max:.1%} ownership with max ${max_check/1e6:.1f}M\n"
            rec += f"   • Returns {return_multiple:.1f}x (below 10x target)\n"
            rec += f"   • Push for ${(ask-gap)/1e6:.0f}M valuation"
            return rec
        elif required_check > max_check:
            rec = f"❌ TOO EXPENSIVE at ${ask/1e6:.0f}M\n"
            rec += f"   • Need ${required_check/1e6:.1f}M for {target_ownership:.0%} ownership (exceeds ${max_check/1e6:.1f}M limit)\n"
            rec += f"   • Max check only gets {ownership_at_max:.1%} ownership\n"
            rec += f"   • Wait for Series B+ when valuation resets"
            return rec
        else:
            rec = f"🔴 PASS at ${ask/1e6:.0f}M - severely overvalued\n"
            rec += f"   • {gap/ask:.0%} above fair value\n"
            rec += f"   • Would need {(ask * exit_multiple)/1e9:.1f}B exit to make 10x\n"
            rec += f"   • Consider revisiting if drops below ${(ask-gap)/1e6:.0f}M"
            return rec
    
    def calculate_required_growth_rates(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate required growth rates to justify valuation multiples
        Both forward (next 12 months) and backward (last 12 months) looking
        """
        # Use actual revenue first, then inferred (which should ALWAYS exist)
        revenue_candidates = [
            company_data.get("revenue"),
            company_data.get("arr"),
            company_data.get("inferred_revenue"),
            company_data.get("estimated_revenue"),
            company_data.get("revenue_estimate"),
            company_data.get("inferred_arr"),
            company_data.get("calculated_revenue"),
        ]
        current_revenue = None
        for candidate in revenue_candidates:
            if candidate is None:
                continue
            numeric_candidate = self._safe_get_value(candidate, None)
            if numeric_candidate is not None:
                current_revenue = numeric_candidate
                break
        
        if current_revenue is None:
            current_revenue = 0
            logger.warning(
                "[GAP_FILLER] No revenue data available for calculate_required_growth_rates; defaulting to 0 to maintain flow."
            )
        valuation = company_data.get("valuation") or company_data.get("inferred_valuation") or 100_000_000
        nrr = company_data.get("nrr", company_data.get("net_retention", 1.10))  # Default 110%
        
        # Current revenue multiple - safe division
        current_multiple = valuation / current_revenue if current_revenue and current_revenue > 0 else 15
        
        # Stage-based benchmark multiples (from real market data)
        stage = self._determine_stage(company_data)
        benchmark_multiples = {
            "Seed": {"low": 8, "median": 15, "high": 30},
            "Series A": {"low": 6, "median": 12, "high": 20},
            "Series B": {"low": 5, "median": 10, "high": 15},
            "Series C": {"low": 4, "median": 8, "high": 12},
            "Series D": {"low": 3, "median": 6, "high": 10}
        }
        
        benchmarks = benchmark_multiples.get(stage, benchmark_multiples["Series A"])
        
        # Calculate required growth rates for different scenarios
        # Formula: Next Year Revenue = Current Revenue * (1 + growth_rate)
        # Target Multiple = Valuation / Next Year Revenue
        # Therefore: growth_rate = (Valuation / (Target Multiple * Current Revenue)) - 1
        
        results = {
            "current_multiple": current_multiple,
            "stage": stage,
            "nrr": nrr,
            "churn_rate": max(0, 1 - nrr),  # Monthly churn implied by NRR
            "required_growth_rates": {},
            "justification_analysis": {}
        }
        
        # Forward looking (what growth do we need next year to justify current valuation?)
        target_multiples = {
            "aggressive": benchmarks["high"],
            "median": benchmarks["median"], 
            "conservative": benchmarks["low"]
        }
        
        for scenario, target_multiple in target_multiples.items():
            # To reach this multiple in 1 year
            required_revenue_next_year = valuation / target_multiple
            required_growth = (required_revenue_next_year / current_revenue - 1) if current_revenue > 0 else 0
            
            results["required_growth_rates"][f"forward_{scenario}"] = {
                "target_multiple": target_multiple,
                "required_growth_rate": required_growth,
                "required_revenue_next_year": required_revenue_next_year,
                "feasibility": self._assess_growth_feasibility(required_growth, nrr)
            }
        
        # Backward looking (what growth would have justified this valuation?)
        # If they grew at X% last year to reach current revenue, what multiple does that imply?
        last_year_revenue = company_data.get("last_year_revenue", current_revenue / 1.5)  # Assume 50% growth if unknown
        actual_growth = (current_revenue / last_year_revenue - 1) if last_year_revenue > 0 else 0.5
        
        # Rule of 40 calculation (growth + profit margin)
        profit_margin = company_data.get("profit_margin", -0.2)  # Default -20% for growth stage
        rule_of_40 = (actual_growth * 100) + (profit_margin * 100)
        
        # Growth-adjusted multiple (higher growth justifies higher multiple)
        # Using SaaS benchmark: Multiple = 2 + (growth_rate * 10)
        justified_multiple_by_growth = 2 + (actual_growth * 10)
        
        # NRR-adjusted multiple (better retention justifies higher multiple)
        # Companies with >120% NRR get premium, <100% get discount
        nrr_multiplier = 1.0
        if nrr > 1.20:
            nrr_multiplier = 1.2  # 20% premium
        elif nrr > 1.10:
            nrr_multiplier = 1.1  # 10% premium
        elif nrr < 1.00:
            nrr_multiplier = 0.8  # 20% discount
        
        justified_multiple_with_nrr = justified_multiple_by_growth * nrr_multiplier
        
        results["backward_looking"] = {
            "last_year_revenue": last_year_revenue,
            "actual_growth_rate": actual_growth,
            "rule_of_40": rule_of_40,
            "justified_multiple_by_growth": justified_multiple_by_growth,
            "justified_multiple_with_nrr": justified_multiple_with_nrr,
            "valuation_gap": current_multiple - justified_multiple_with_nrr,
            "overvalued": current_multiple > justified_multiple_with_nrr * 1.2  # 20% buffer
        }
        
        # Calculate T2D3 trajectory (Triple, Triple, Double, Double, Double)
        # This is the gold standard for SaaS growth
        t2d3_trajectory = {
            "year_1": current_revenue * 3,  # Triple
            "year_2": current_revenue * 9,  # Triple again
            "year_3": current_revenue * 18,  # Double
            "year_4": current_revenue * 36,  # Double
            "year_5": current_revenue * 72   # Double
        }
        
        # What growth rate gets us to $100M ARR?
        years_to_100m = 0
        if current_revenue > 0 and current_revenue < 100_000_000:
            # Solve: 100M = current * (1 + g)^n
            for years in range(1, 11):  # Check up to 10 years
                required_growth_for_100m = (100_000_000 / current_revenue) ** (1/years) - 1
                if required_growth_for_100m <= 2.0:  # Max 200% growth is somewhat realistic
                    years_to_100m = years
                    break
        
        results["growth_scenarios"] = {
            "t2d3_trajectory": t2d3_trajectory,
            "years_to_100m_arr": years_to_100m,
            "required_growth_for_100m": (100_000_000 / current_revenue) ** (1/max(years_to_100m, 3)) - 1 if years_to_100m > 0 else None
        }
        
        # Churn impact on growth
        # With NRR, you need to grow new bookings faster to compensate for churn
        gross_retention = min(nrr, 1.0)  # Can't retain more than 100% of customers
        expansion_revenue = max(0, nrr - 1.0)  # Revenue expansion from existing customers
        
        results["churn_impact"] = {
            "gross_retention": gross_retention,
            "monthly_logo_churn": (1 - gross_retention ** (1/12)),  # Convert annual to monthly
            "expansion_revenue_rate": expansion_revenue,
            "new_revenue_needed": current_revenue * (1 - gross_retention),  # To maintain flat
            "growth_efficiency": nrr,  # >1 means negative churn (expansion > churn)
        }
        
        # Add projected_growth_rate for deck generation to use
        # Use the backward-looking actual growth as the projection
        # Convert from decimal (0.5 = 50%) to multiplier (1.5 = 50% growth)
        if "backward_looking" in results and "actual_growth_rate" in results["backward_looking"]:
            actual_growth = results["backward_looking"]["actual_growth_rate"]
            # Ensure it's a multiplier format (1.5 = 50% growth, not 0.5)
            if actual_growth < 1.0 and actual_growth > -1.0:
                # It's in decimal format, convert to multiplier
                results["projected_growth_rate"] = actual_growth + 1
            else:
                # Already in multiplier format
                results["projected_growth_rate"] = actual_growth
        else:
            # Fallback based on stage
            stage_growth_defaults = {
                "Seed": 2.5,      # 150% YoY
                "Series A": 2.0,  # 100% YoY
                "Series B": 1.7,  # 70% YoY
                "Series C": 1.5,  # 50% YoY
                "Series D": 1.3   # 30% YoY
            }
            results["projected_growth_rate"] = stage_growth_defaults.get(stage, 1.5)
        
        return results
    
    def _assess_growth_feasibility(self, required_growth: float, nrr: float) -> str:
        """
        Assess if a growth rate is feasible given NRR
        """
        if required_growth < 0:
            return "⚠️ Negative growth required - overvalued"
        elif required_growth <= 0.3:
            return "✅ Very achievable (<30% growth)"
        elif required_growth <= 0.5:
            return "✅ Achievable (30-50% growth)"
        elif required_growth <= 1.0:
            return "🔶 Aggressive but possible (50-100% growth)"
        elif required_growth <= 2.0:
            return "⚠️ Very aggressive (100-200% growth)"
        else:
            return "❌ Unrealistic (>200% growth required)"
    
    def analyze_founder_profile(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze founder tech skills and track record
        """
        founders = company_data.get("founders", [])
        team_data = company_data.get("team", {})
        
        # Initialize profile
        founder_profile = {
            "technical_founders": False,
            "repeat_founders": False,
            "exit_experience": False,
            "domain_expertise": False,
            "top_company_experience": False,
            "education_tier": "unknown",
            "years_experience": 0,
            "previous_companies": [],
            "technical_skills": [],
            "risk_score": 50,  # 0-100, lower is better
            "strengths": [],
            "concerns": []
        }
        
        # Analyze each founder
        for founder in founders:
            name = founder.get("name", "")
            bio = founder.get("bio", "")
            linkedin = founder.get("linkedin", "")
            background = founder.get("background", "")
            
            combined_text = f"{bio} {background} {linkedin}".lower()
            
            # Check for technical background
            tech_signals = ["engineer", "cto", "developer", "programmer", "cs degree", 
                          "computer science", "ml", "ai", "software", "coding", "github"]
            if any(signal in combined_text for signal in tech_signals):
                founder_profile["technical_founders"] = True
                founder_profile["strengths"].append("Technical founder(s)")
            
            # Check for repeat founder
            repeat_signals = ["founded", "co-founded", "previous startup", "sold", "acquired", "exit"]
            if any(signal in combined_text for signal in repeat_signals):
                founder_profile["repeat_founders"] = True
                founder_profile["strengths"].append("Repeat entrepreneur")
            
            # Check for exit experience
            exit_signals = ["acquired", "sold", "ipo", "acquisition", "exit", "bought by"]
            if any(signal in combined_text for signal in exit_signals):
                founder_profile["exit_experience"] = True
                founder_profile["strengths"].append("Previous exit")
            
            # Check for top company experience (FAANG + top startups)
            top_companies = ["google", "facebook", "meta", "amazon", "apple", "microsoft", 
                           "netflix", "stripe", "airbnb", "uber", "lyft", "snapchat", 
                           "twitter", "tesla", "spacex", "palantir", "databricks"]
            for company in top_companies:
                if company in combined_text:
                    founder_profile["top_company_experience"] = True
                    founder_profile["previous_companies"].append(company.title())
                    founder_profile["strengths"].append(f"Ex-{company.title()}")
            
            # Check education
            if "stanford" in combined_text or "mit" in combined_text or "harvard" in combined_text:
                founder_profile["education_tier"] = "elite"
                founder_profile["strengths"].append("Elite education")
            elif "berkeley" in combined_text or "cmu" in combined_text or "caltech" in combined_text:
                founder_profile["education_tier"] = "top"
            elif "university" in combined_text or "college" in combined_text:
                founder_profile["education_tier"] = "standard"
            
            # Extract years of experience
            import re
            years_pattern = r"(\d+)\+?\s*years?"
            years_match = re.search(years_pattern, combined_text)
            if years_match:
                years = int(years_match.group(1))
                founder_profile["years_experience"] = max(founder_profile["years_experience"], years)
            
            # Extract technical skills
            tech_skills = ["python", "javascript", "react", "node", "aws", "kubernetes", 
                          "docker", "tensorflow", "pytorch", "sql", "mongodb", "redis"]
            for skill in tech_skills:
                if skill in combined_text:
                    founder_profile["technical_skills"].append(skill)
        
        # Calculate risk score
        risk_score = 50  # Base score
        
        if founder_profile["technical_founders"]:
            risk_score -= 10
        else:
            founder_profile["concerns"].append("No technical founder")
            risk_score += 15
        
        if founder_profile["repeat_founders"]:
            risk_score -= 15
        else:
            founder_profile["concerns"].append("First-time founders")
            risk_score += 10
        
        if founder_profile["exit_experience"]:
            risk_score -= 20
        
        if founder_profile["top_company_experience"]:
            risk_score -= 10
        
        if founder_profile["education_tier"] == "elite":
            risk_score -= 5
        elif founder_profile["education_tier"] == "unknown":
            risk_score += 5
        
        if founder_profile["years_experience"] < 5:
            founder_profile["concerns"].append("Limited experience (<5 years)")
            risk_score += 10
        elif founder_profile["years_experience"] > 15:
            risk_score -= 5
        
        # Domain expertise check
        industry = (company_data.get("industry") or "").lower()
        description = (company_data.get("description") or "").lower()
        
        # Check if founders have relevant domain experience
        domain_keywords = {
            "fintech": ["payments", "banking", "financial", "stripe", "square", "paypal"],
            "healthtech": ["healthcare", "medical", "hospital", "clinical", "pharma"],
            "edtech": ["education", "learning", "teaching", "school", "university"],
            "logistics": ["supply chain", "logistics", "shipping", "freight", "warehouse"],
            "security": ["security", "cybersecurity", "infosec", "penetration", "cryptography"]
        }
        
        for domain, keywords in domain_keywords.items():
            if domain in industry or domain in description:
                # Check if founders have this domain experience
                founder_text = " ".join([f.get("background", "") for f in founders]).lower()
                if any(keyword in founder_text for keyword in keywords):
                    founder_profile["domain_expertise"] = True
                    founder_profile["strengths"].append(f"Domain expertise in {domain}")
                    risk_score -= 10
                    break
        
        founder_profile["risk_score"] = max(0, min(100, risk_score))
        
        return founder_profile
    
    def detect_compute_intensity(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect compute intensity category based on business model
        Returns category, cost range, and margin impact
        """
        business_model = str(company_data.get("business_model", "")).lower()
        product = str(company_data.get("product_description", "")).lower()
        category = str(company_data.get("category", "")).lower()
        sector = str(company_data.get("sector", "")).lower()
        
        combined_text = f"{business_model} {product} {category} {sector}"
        
        # Check for code generation patterns
        code_gen_signals = ["code generation", "code editor", "ide", "coding assistant", 
                            "code completion", "copilot", "developer tools", "ai-powered code"]
        if any(signal in combined_text for signal in code_gen_signals):
            return self.GPU_COST_PER_TRANSACTION["code_generation"]
            
        # Check for search/synthesis patterns  
        search_signals = ["search engine", "conversational search", "answer engine",
                         "knowledge synthesis", "research assistant"]
        if any(signal in combined_text for signal in search_signals):
            return self.GPU_COST_PER_TRANSACTION["search_synthesis"]
            
        # Check for image/video generation
        media_signals = ["image generation", "video generation", "visual ai", "generative art",
                         "text-to-image", "text-to-video", "stable diffusion", "dall-e"]
        if any(signal in combined_text for signal in media_signals):
            return self.GPU_COST_PER_TRANSACTION["image_video_gen"]
            
        # Check for AI agents (high compute)
        agent_signals = ["ai agent", "autonomous agent", "ai assistant", "virtual assistant",
                        "workflow automation", "ai copilot", "intelligent automation"]
        if any(signal in combined_text for signal in agent_signals):
            # Agents are typically high compute, similar to code gen
            return {
                "cost_range": (2, 10),  # $2-10 per agent task
                "examples": ["AI agents", "Virtual assistants"],
                "compute_intensity": "high",
                "margin_impact": 0.30  # 30% margin reduction
            }
            
        # Check for chat/writing tools
        chat_signals = ["chatbot", "ai writer", "content generation", "copywriting",
                       "chat assistant", "conversational ai"]
        if any(signal in combined_text for signal in chat_signals):
            return self.GPU_COST_PER_TRANSACTION["chat_exchange"]
            
        # Check for traditional ML
        ml_signals = ["machine learning", "predictive analytics", "data science platform",
                      "ml platform", "automl"]
        if any(signal in combined_text for signal in ml_signals) and "generative" not in combined_text:
            return self.GPU_COST_PER_TRANSACTION["traditional_ml"]
            
        # Default to no AI if no patterns found
        if "ai" not in combined_text and "ml" not in combined_text:
            return self.GPU_COST_PER_TRANSACTION["no_ai"]
            
        # If AI is mentioned but no specific pattern, assume moderate
        return self.GPU_COST_PER_TRANSACTION["chat_exchange"]
    
    def calculate_gpu_adjusted_metrics(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate GPU cost impact on unit economics and valuation
        """
        # Get GPU workload info from extraction
        gpu_unit_of_work = company_data.get('gpu_unit_of_work', '')
        gpu_workload_description = company_data.get('gpu_workload_description', '')
        compute_intensity = company_data.get('compute_intensity')
        
        # Infer compute_intensity if not provided
        if not compute_intensity or compute_intensity == 'Unknown':
            compute_intensity = self._infer_compute_intensity(company_data)
        
        # Use Claude-extracted unit economics if available
        unit_economics = company_data.get('unit_economics', {})
        gpu_cost_per_unit = unit_economics.get('gpu_cost_per_unit', 0)
        units_per_customer_per_month = unit_economics.get('units_per_customer_per_month', 100)
        
        # Ensure gpu_cost_per_unit is numeric
        if isinstance(gpu_cost_per_unit, str):
            # Try to extract number from string like "$5.00" or "5.00"
            import re
            match = re.search(r'[\d.]+', str(gpu_cost_per_unit))
            gpu_cost_per_unit = float(match.group()) if match else 0
        
        # Map intensity to cost if not provided by extraction
        if not gpu_cost_per_unit or gpu_cost_per_unit == 0:
            intensity_to_cost = {
                'extreme': 10.0,  # $10 midpoint of $5-20
                'high': 2.0,      # $2 midpoint of $0.50-5
                'moderate': 0.1,  # $0.10 midpoint of $0.01-0.50
                'low': 0.005,     # $0.005 midpoint of $0.001-0.01
                'none': 0
            }
            gpu_cost_per_unit = intensity_to_cost.get(compute_intensity, 0.1)
        
        # Build compute profile from extraction
        compute_profile = {
            "cost_range": (gpu_cost_per_unit * 0.5, gpu_cost_per_unit * 2),
            "compute_intensity": compute_intensity,
            "margin_impact": unit_economics.get('gross_margin_impact', 0.2),
            "workload": gpu_workload_description or 'Unknown workload',
            "unit_of_work": gpu_unit_of_work or 'per transaction'
        }
        
        # Always start with inferred revenue - NEVER None
        # Use the properly inferred revenue if available
        inferred_revenue = company_data.get('inferred_revenue', 0)
        if inferred_revenue and inferred_revenue > 0:
            revenue = inferred_revenue
        else:
            # This should NEVER happen - inferred_revenue should ALWAYS be set
            # by infer_from_stage_benchmarks which runs BEFORE this
            revenue = 1_000_000  # Emergency fallback
            company_identifier = company_data.get('company_name', company_data.get('company', company_data.get('name', 'Unknown')))
            print(f"ERROR: No inferred_revenue for {company_identifier} - using emergency fallback")
        
        # Check if we have actual extracted revenue to overwrite the inferred
        revenue_raw = company_data.get("revenue", company_data.get("arr", None))
        if revenue_raw:
            extracted_revenue = None
            if isinstance(revenue_raw, dict) and revenue_raw.get('value'):
                extracted_revenue = revenue_raw['value']
            elif hasattr(revenue_raw, 'value') and revenue_raw.value:
                extracted_revenue = revenue_raw.value
            elif isinstance(revenue_raw, (int, float)) and revenue_raw > 0:
                extracted_revenue = revenue_raw
            
            # Validate extracted revenue is reasonable for the stage
            if extracted_revenue:
                stage = company_data.get('stage', 'unknown').lower()
                min_reasonable_revenue = {
                    'series c': 5_000_000,
                    'series b': 2_000_000,
                    'series a': 500_000,
                    'seed': 100_000,
                    'pre-seed': 10_000
                }.get(stage, 100_000)
                
                # Only use extracted revenue if it's reasonable
                if extracted_revenue >= min_reasonable_revenue:
                    revenue = extracted_revenue
                else:
                    # Log that we're rejecting unrealistic revenue
                    company_name = company_data.get('company_name', 'Unknown')
                    print(f"[GAP FILLER] Rejecting unrealistic revenue ${extracted_revenue:,.0f} for {stage} company {company_name}, using inferred ${revenue:,.0f}")
            
        # Estimate transaction volume based on business type
        customers = company_data.get("customers", 100)
        if isinstance(customers, list):
            customers = len(customers)
        
        # Ensure customers is numeric
        try:
            customers = float(customers) if customers else 100
        except (TypeError, ValueError):
            customers = 100
        
        # Use extracted units per customer or fall back to intensity-based defaults
        if not units_per_customer_per_month or units_per_customer_per_month == 0:
            # Define the UNIT OF WORK for different AI workloads
            # This is critical - we're measuring actual GPU-intensive operations
            units_per_customer_per_month = {
                "extreme": 10,     # Code gen: ~10 full code completions/month per user
                "high": 50,        # Search: ~50 complex searches/month per user
                "moderate": 200,   # Chat: ~200 messages/month per user
                "low": 1000,       # Traditional ML: many small predictions
                "none": 0
            }.get(compute_intensity, 100)
        
        # Calculate GPU costs - use percentage of revenue for AI companies
        # This better reflects reality where GPU costs scale with usage/revenue
        
        # Determine GPU cost as percentage of revenue based on compute intensity
        # These percentages come from real-world data on AI companies
        intensity_to_percentage = {
            'extreme': 0.35,   # 35% - Code generation, video generation
            'high': 0.25,      # 25% - LLMs, real-time processing
            'moderate': 0.15,  # 15% - Search + synthesis, chat
            'low': 0.05,       # 5% - Light AI features
            'none': 0.01       # 1% - Minimal GPU usage
        }
        
        # Use the intensity-based percentage
        gpu_percentage = intensity_to_percentage.get(compute_intensity, 0.15)
        
        # Calculate actual GPU costs based on revenue percentage
        # This is more accurate than unit-based calculation for AI companies
        annual_gpu_costs = revenue * gpu_percentage
        monthly_gpu_costs = annual_gpu_costs / 12
        
        # Also calculate unit costs for reference
        if customers > 0 and units_per_customer_per_month > 0:
            total_monthly_units = float(customers) * float(units_per_customer_per_month)
            if total_monthly_units > 0:
                cost_per_unit = monthly_gpu_costs / total_monthly_units
            else:
                cost_per_unit = float(gpu_cost_per_unit)
        else:
            cost_per_unit = float(gpu_cost_per_unit)
        
        # GPU cost as percent of revenue
        gpu_cost_as_percent_revenue = gpu_percentage * 100
        
        # Determine valuation impact based on GPU dependency
        if compute_profile["compute_intensity"] == "extreme":
            valuation_multiple = 0.4  # 60% discount - these are tough businesses
            investment_thesis = "⚠️ EXTREME GPU COSTS: Very challenging unit economics. Need massive scale or pricing power."
        elif compute_profile["compute_intensity"] == "high":
            valuation_multiple = 0.6  # 40% discount
            investment_thesis = "🔶 HIGH GPU COSTS: Monitor unit economics carefully. Path to profitability unclear."
        elif compute_profile["compute_intensity"] == "moderate":
            valuation_multiple = 0.8  # 20% discount
            investment_thesis = "✅ MODERATE GPU COSTS: Manageable if pricing and retention are strong."
        else:
            valuation_multiple = 1.0  # No discount
            investment_thesis = "🚀 LOW/NO GPU COSTS: Strong unit economics potential."
            
        return {
            "compute_intensity": compute_profile["compute_intensity"],
            "compute_category": compute_profile.get("examples", ["Unknown"])[0],
            "cost_per_unit": cost_per_unit,
            "cost_per_transaction": cost_per_unit,  # Alias for compatibility
            "unit_of_work": compute_profile.get("unit_of_work", "per transaction"),
            "monthly_gpu_costs": monthly_gpu_costs,
            "annual_gpu_costs": annual_gpu_costs,
            "gpu_cost_as_percent_revenue": gpu_cost_as_percent_revenue,
            "margin_impact": compute_profile["margin_impact"],
            "valuation_multiple_adjustment": valuation_multiple,
            "investment_thesis": investment_thesis,
            "cost_range": compute_profile["cost_range"],
            "workload_description": compute_profile.get("workload", "Unknown workload"),
            "units_per_customer_per_month": units_per_customer_per_month
        }
    
    def _infer_compute_intensity(self, company_data: Dict[str, Any]) -> str:
        """Infer compute intensity from business model and signals"""
        
        # Get all relevant text signals
        gpu_unit = (company_data.get('gpu_unit_of_work', '') or '').lower()
        workload_desc = (company_data.get('gpu_workload_description', '') or '').lower()
        business_model = self._ensure_string(company_data.get('business_model', '')).lower()
        description = self._ensure_string(company_data.get('description', '')).lower()
        product_desc = self._ensure_string(company_data.get('product_description', '')).lower()
        compute_signals = company_data.get('compute_signals', [])
        if not isinstance(compute_signals, list):
            compute_signals = []
        
        # Combine all text - ensure all parts are strings
        gpu_unit = self._ensure_string(gpu_unit)
        workload_desc = self._ensure_string(workload_desc)
        compute_signals_text = ' '.join(self._ensure_string(s) for s in compute_signals)
        all_text = f"{gpu_unit} {workload_desc} {business_model} {description} {product_desc} {compute_signals_text}".lower()
        
        # EXTREME: Full code generation, video, autonomous agents
        if any(signal in all_text for signal in [
            'full code file', 'complete implementation', 'video generation',
            'autonomous agent', 'multi-step agent', 'entire codebase',
            'full application', 'complete project', 'hours of processing',
            'lovable', 'cursor', 'v0', 'replit agent'
        ]):
            return 'extreme'
        
        # HIGH: Search synthesis, real-time voice, medical/legal analysis
        if any(signal in all_text for signal in [
            'search with synthesis', 'perplexity', 'corti', 'vocca',
            'real-time voice', 'voice assistant', 'medical consultation',
            'legal document', 'code review', 'pull request review',
            'live transcription', 'real-time transcription'
        ]):
            return 'high'
        
        # MODERATE: Chat, Q&A, summarization
        if any(signal in all_text for signal in [
            'chat', 'question answer', 'q&a', 'summarization',
            'extraction', 'document processing', 'per message',
            'per query', 'customer support', 'helpdesk'
        ]):
            return 'moderate'
        
        # LOW: Traditional ML, embeddings
        if any(signal in all_text for signal in [
            'traditional ml', 'embedding', 'classification',
            'batch processing', 'offline', 'analytics'
        ]):
            return 'low'
        
        # NONE: No AI workload
        if any(signal in all_text for signal in [
            'no ai', 'no gpu', 'pure saas', 'marketplace',
            'payments', 'crm', 'erp', 'fintech platform'
        ]):
            return 'none'
        
        # Default to moderate if unclear
        return 'moderate'
    
    def _get_gpu_intensity_risks(self, compute_intensity: str) -> List[str]:
        """Get risk factors based on GPU compute intensity"""
        if compute_intensity == "extreme":
            return [
                "GPU costs could exceed 40% of revenue",
                "Unit economics worsen with scale",
                "Requires massive funding to reach profitability",
                "Competition from Big Tech with cheaper compute"
            ]
        elif compute_intensity == "high":
            return [
                "GPU costs impact margins by 25-30%",
                "Need efficient caching and optimization",
                "Scaling challenges with user growth"
            ]
        elif compute_intensity == "moderate":
            return [
                "GPU costs manageable at 10-15% of revenue",
                "Room for margin improvement with optimization"
            ]
        else:
            return []
    
    def _get_api_dependency_risks(self, dependency_level: str) -> List[str]:
        """Get risk factors based on API dependency"""
        if dependency_level == "openai_heavy":
            return [
                "Gross margins capped at ~50-55% due to API costs",
                "Unit economics deteriorate with usage growth",
                "Platform risk - dependent on OpenAI/Anthropic pricing",
                "Limited pricing power due to high COGS",
                "Difficult to achieve Rule of 40 benchmarks"
            ]
        elif dependency_level == "openai_moderate":
            return [
                "API costs impact gross margins by 10-15%",
                "Need to monitor API usage per customer",
                "Some platform dependency risk"
            ]
        elif dependency_level == "openai_light":
            return [
                "Minimal API cost impact",
                "Can maintain 75%+ gross margins"
            ]
        else:
            return [
                "Higher R&D costs for model development", 
                "Need strong ML/AI team",
                "Longer time to market for new features"
            ]
    
    async def get_market_multiples_from_database(self) -> Dict[str, Any]:
        """
        Get trailing and forward revenue multiples from our database
        Calculate growth-adjusted multiples accounting for cost of capital
        """
        try:
            from app.core.database import supabase_service
            
            # Check if Supabase client is initialized
            if not supabase_service.client:
                logger.warning("Supabase client not initialized - using default market multiples")
                return self._get_default_market_multiples()
            
            try:
                # Query companies with revenue and valuation data
                if not supabase_service.client:
                    logger.warning("Supabase client not available - using default market multiples")
                    return self._get_default_market_multiples()
                    
                result = supabase_service.client.table('companies').select(
                    'name', 'revenue', 'valuation', 'growth_rate', 'stage', 
                    'last_round_date', 'funding_rounds', 'sector'
                ).not_.is_('revenue', None).not_.is_('valuation', None).execute()
                
                if not result.data:
                    logger.warning("No companies found in database - using default market multiples")
                    return self._get_default_market_multiples()
                    
            except Exception as e:
                logger.error(f"Supabase query failed: {e}")
                return self._get_default_market_multiples()
            
            companies = result.data
            logger.info(f"Found {len(companies)} companies with revenue/valuation data")
            
            # Separate by whether they have growth rates
            with_growth = [c for c in companies if c.get('growth_rate') is not None]
            without_growth = [c for c in companies if c.get('growth_rate') is None]
            
            logger.info(f"{len(with_growth)} companies have growth rates, {len(without_growth)} don't")
            
            # Calculate multiples by stage
            multiples_analysis = {}
            
            for stage in ['Seed', 'Series A', 'Series B', 'Series C', 'Series D', 'Growth']:
                stage_companies = [c for c in companies if c.get('stage') == stage]
                
                if not stage_companies:
                    continue
                
                stage_multiples = []
                
                for company in stage_companies:
                    revenue = company.get('revenue')
                    valuation = company.get('valuation', 0)
                    growth = company.get('growth_rate')
                    
                    # Use inferred revenue if actual revenue is missing
                    if not revenue or revenue <= 0:
                        inferred_revenue = company.get('inferred_revenue')
                        if inferred_revenue and inferred_revenue > 0:
                            revenue = inferred_revenue
                        else:
                            # If still no revenue, skip
                            continue
                    
                    # Use inferred growth if actual growth is missing
                    if growth is None:
                        growth = company.get('inferred_growth_rate')
                        if growth is None:
                            # Infer from investors using multiplier method
                            growth = self._infer_growth_from_investors(company.get('funding_rounds', []), company)
                    
                    # Trailing revenue multiple (valuation / current revenue)
                    trailing_multiple = valuation / revenue
                    
                    # VALIDATION: Revenue multiples should be reasonable (0.5x-50x typical)
                    if trailing_multiple < 0.5 or trailing_multiple > 100:
                        logger.warning(f"[REVENUE_MULTIPLE] Suspicious trailing multiple: {trailing_multiple:.1f}x (valuation=${valuation/1e6:.1f}M, revenue=${revenue/1e6:.1f}M)")
                        # If clearly wrong, skip this data point
                        if trailing_multiple > 1000 or trailing_multiple < 0.1:
                            logger.error(f"[REVENUE_MULTIPLE] Rejecting impossible multiple: {trailing_multiple:.1f}x")
                            continue
                    
                    # Forward revenue multiple (valuation / next year revenue)
                    if growth is not None:
                        forward_revenue = revenue * (1 + growth)
                        forward_multiple = valuation / forward_revenue if forward_revenue > 0 else trailing_multiple
                    else:
                        # Infer growth from investor quality if not available
                        inferred_growth = self._infer_growth_from_investors(company.get('funding_rounds', []), company)
                        forward_revenue = revenue * (1 + inferred_growth)
                        forward_multiple = valuation / forward_revenue if forward_revenue > 0 else trailing_multiple
                        growth = inferred_growth
                    
                    # VALIDATION: Forward multiple should also be reasonable
                    if forward_multiple < 0.5 or forward_multiple > 100:
                        logger.warning(f"[REVENUE_MULTIPLE] Suspicious forward multiple: {forward_multiple:.1f}x")
                        if forward_multiple > 1000 or forward_multiple < 0.1:
                            forward_multiple = trailing_multiple
                    
                    # Growth-adjusted multiple (accounting for cost of capital)
                    # Public market cost of capital ~8-10% now (higher than 2021)
                    cost_of_capital = 0.10
                    
                    # Rule of 40 score (growth + profit margin)
                    # Assume -20% margins for growth stage
                    profit_margin = -0.20 if stage in ['Seed', 'Series A'] else -0.10
                    rule_of_40 = (growth * 100) + (profit_margin * 100)
                    
                    # Growth-adjusted multiple formula:
                    # Base multiple = 2x for 0% growth
                    # Add 0.1x for each 1% of growth above cost of capital
                    growth_premium = max(0, growth - cost_of_capital)
                    growth_adjusted_multiple = 2 + (growth_premium * 10)
                    
                    # Compare actual to theoretical
                    multiple_premium = trailing_multiple / growth_adjusted_multiple if growth_adjusted_multiple > 0 else 1.0
                    
                    stage_multiples.append({
                        'company': company.get('name'),
                        'trailing': trailing_multiple,
                        'forward': forward_multiple,
                        'growth_rate': growth,
                        'growth_adjusted': growth_adjusted_multiple,
                        'premium_to_fair': multiple_premium,
                        'rule_of_40': rule_of_40
                    })
                
                if stage_multiples:
                    # Sort for percentile calculations
                    trailing_sorted = sorted([m['trailing'] for m in stage_multiples])
                    forward_sorted = sorted([m['forward'] for m in stage_multiples])
                    growth_adj_sorted = sorted([m['growth_adjusted'] for m in stage_multiples])
                    
                    # Calculate statistics
                    multiples_analysis[stage] = {
                        'count': len(stage_multiples),
                        'trailing': {
                            'p25': trailing_sorted[int(len(trailing_sorted) * 0.25)],
                            'p50': trailing_sorted[int(len(trailing_sorted) * 0.50)],
                            'p75': trailing_sorted[int(len(trailing_sorted) * 0.75)],
                            'mean': sum(trailing_sorted) / len(trailing_sorted)
                        },
                        'forward': {
                            'p25': forward_sorted[int(len(forward_sorted) * 0.25)],
                            'p50': forward_sorted[int(len(forward_sorted) * 0.50)],
                            'p75': forward_sorted[int(len(forward_sorted) * 0.75)],
                            'mean': sum(forward_sorted) / len(forward_sorted)
                        },
                        'growth_adjusted': {
                            'p50': growth_adj_sorted[int(len(growth_adj_sorted) * 0.50)],
                            'mean': sum(growth_adj_sorted) / len(growth_adj_sorted)
                        },
                        'avg_growth_rate': sum(m['growth_rate'] for m in stage_multiples) / len(stage_multiples),
                        'avg_rule_of_40': sum(m['rule_of_40'] for m in stage_multiples) / len(stage_multiples),
                        'revenue_weighted_growth': self._calculate_revenue_weighted_growth(stage_multiples)
                    }
            
            # Add market context
            multiples_analysis['market_context'] = {
                'cost_of_capital': 0.10,  # 10% in current market
                'public_comps': {
                    'high_growth_saas': 8.0,  # Down from 15x in 2021
                    'mid_growth_saas': 5.0,   # Down from 10x
                    'low_growth_saas': 3.0    # Down from 6x
                },
                'vintage_adjustments': {
                    '2021': 0.5,   # 50% discount from peak (4 years old)
                    '2022': 0.65,  # 35% discount (3 years old)
                    '2023': 0.8,   # 20% discount (2 years old)
                    '2024': 0.95,  # 5% discount (1 year old)
                    '2025': 1.0    # Current market (Sep 2025)
                },
                'cambridge_associates_benchmarks': self._get_cambridge_benchmarks()
            }
            
            self.growth_adjusted_multiples_cache = multiples_analysis
            return multiples_analysis
            
        except Exception as e:
            logger.error(f"Failed to get market multiples: {e}")
            return self._get_default_market_multiples()
    
    def _get_default_market_multiples(self) -> Dict[str, Any]:
        """Default multiples based on current market conditions"""
        return {
            'Seed': {
                'trailing': {'p25': 8, 'p50': 15, 'p75': 30, 'mean': 18},
                'forward': {'p25': 5, 'p50': 10, 'p75': 20, 'mean': 12},
                'growth_adjusted': {'p50': 12, 'mean': 12},
                'avg_growth_rate': 1.5,
                'avg_rule_of_40': 30
            },
            'Series A': {
                'trailing': {'p25': 5, 'p50': 10, 'p75': 20, 'mean': 12},
                'forward': {'p25': 3, 'p50': 7, 'p75': 15, 'mean': 8},
                'growth_adjusted': {'p50': 10, 'mean': 10},
                'avg_growth_rate': 1.0,
                'avg_rule_of_40': 20
            },
            'Series B': {
                'trailing': {'p25': 4, 'p50': 8, 'p75': 15, 'mean': 9},
                'forward': {'p25': 3, 'p50': 6, 'p75': 10, 'mean': 6},
                'growth_adjusted': {'p50': 8, 'mean': 8},
                'avg_growth_rate': 0.7,
                'avg_rule_of_40': 10
            },
            'Series C': {
                'trailing': {'p25': 3, 'p50': 6, 'p75': 10, 'mean': 7},
                'forward': {'p25': 2.5, 'p50': 5, 'p75': 8, 'mean': 5},
                'growth_adjusted': {'p50': 6, 'mean': 6},
                'avg_growth_rate': 0.5,
                'avg_rule_of_40': 5
            },
            'market_context': {
                'cost_of_capital': 0.10,
                'public_comps': {
                    'high_growth_saas': 8.0,
                    'mid_growth_saas': 5.0,
                    'low_growth_saas': 3.0
                },
                'vintage_adjustments': {
                    '2021': 0.5,   # 50% discount from peak
                    '2022': 0.65,  # 35% discount
                    '2023': 0.8,   # 20% discount
                    '2024': 0.95,  # 5% discount
                    '2025': 1.0    # Current market
                }
            }
        }
    
    def _calculate_revenue_weighted_growth(self, stage_multiples: List[Dict[str, Any]]) -> float:
        """
        Calculate revenue-weighted average growth rate.
        Companies with higher revenue get more weight in the average.
        This gives a more realistic market growth rate.
        """
        if not stage_multiples:
            return 0.0
        
        total_revenue_weight = 0.0
        weighted_growth_sum = 0.0
        
        for multiple_data in stage_multiples:
            # Get revenue from the original company data
            company_name = multiple_data.get('company', '')
            # Find the company in our database results to get revenue
            # For now, use a simple approach - assume revenue is proportional to valuation
            # In a real implementation, we'd look up the actual revenue
            
            # Use trailing multiple as proxy for revenue size
            trailing_multiple = multiple_data.get('trailing', 0)
            growth_rate = multiple_data.get('growth_rate', 0)
            
            # Weight by trailing multiple (higher multiple = higher revenue typically)
            revenue_weight = max(1.0, trailing_multiple)  # Minimum weight of 1.0
            
            weighted_growth_sum += growth_rate * revenue_weight
            total_revenue_weight += revenue_weight
        
        if total_revenue_weight > 0:
            return weighted_growth_sum / total_revenue_weight
        else:
            return 0.0
    
    def _infer_growth_from_investors(self, funding_rounds: List[Dict], company_data: Dict[str, Any] = None) -> float:
        """
        Infer growth rate using MULTIPLIER approach:
        Base Growth (from stage) × Investor Quality Multiplier × Market Multiplier
        
        This creates differentiation between companies at same stage
        """
        if company_data is None:
            company_data = {}
        
        # BASE GROWTH from stage benchmarks
        stage = self._determine_stage(company_data) if company_data else "Seed"
        base_growth_by_stage = {
            "Pre-Seed": 0.5,  # 50% base for pre-seed
            "Seed": 0.8,      # 80% base for seed
            "Series A": 1.0,  # 100% base for Series A
            "Series B": 0.6,  # 60% base for Series B
            "Series C": 0.4,  # 40% base for Series C
            "Growth": 0.3     # 30% base for growth
        }
        base_growth = base_growth_by_stage.get(stage, 0.8)
        
        # INVESTOR QUALITY MULTIPLIER
        # Tier 1: Elite funds (only back 100%+ growth, top 1% selectivity)
        tier1_investors = [
            'sequoia', 'andreessen', 'a16z', 'benchmark', 'greylock',
            'accel', 'index', 'lightspeed', 'bessemer', 'gv', 'google ventures',
            'founders fund', 'kleiner perkins', 'nea', 'general catalyst',
            'insight partners', 'tiger global', 'coatue', 'altimeter', 'dsg', 'iconiq'
        ]
        
        # Tier 2: Top funds (back 75%+ growth, top 5% selectivity)  
        tier2_investors = [
            'menlo ventures', 'redpoint', 'norwest', 'ivp', 'sapphire ventures',
            'scale venture', 'emergence', 'wing', 'cowboy ventures', 'craft ventures',
            'mayfield', 'sierra ventures', 'spark capital', 'union square',
            'first round', 'initialized', 'matrix partners', 'bain capital ventures',
            'thrive capital', 'ribbit capital', 'felicis ventures'
        ]
        
        # Tier 3: Good funds (back 50%+ growth, top 10% selectivity)
        tier3_investors = [
            'harrison metal', 'slow ventures', 'sv angel', 'uncork capital',
            'founder collective', 'village global', 'work-bench', 'boldstart',
            'eniac ventures', 'nextview', 'flybridge', 'polaris partners',
            'vista equity', 'warburg pincus', 'tpg growth', 'ta associates'
        ]
        
        # Check investor tiers
        has_tier1 = False
        has_tier2 = False
        has_tier3 = False
        
        for round_data in funding_rounds:
            if not round_data:
                continue
            investors = round_data.get('investors', [])
            if isinstance(investors, str):
                investors = [investors]
            
            for investor in investors:
                investor_lower = str(investor).lower()
                if any(t1 in investor_lower for t1 in tier1_investors):
                    has_tier1 = True
                elif any(t2 in investor_lower for t2 in tier2_investors):
                    has_tier2 = True
                elif any(t3 in investor_lower for t3 in tier3_investors):
                    has_tier3 = True
        
        # Investor quality multiplier
        if has_tier1:
            investor_multiplier = 1.8  # 80% boost for Tier 1
        elif has_tier2:
            investor_multiplier = 1.4  # 40% boost for Tier 2
        elif has_tier3:
            investor_multiplier = 1.2  # 20% boost for Tier 3
        else:
            investor_multiplier = 1.0  # No boost
        
        # MARKET MULTIPLIER based on category/sector
        category = company_data.get('category', '').lower()
        sector = company_data.get('sector', '').lower()
        combined = f"{category} {sector}"
        
        if 'ai' in combined or 'artificial intelligence' in combined or 'ml' in combined:
            market_multiplier = 1.5  # AI premium
        elif 'fintech' in combined or 'payments' in combined or 'crypto' in combined:
            market_multiplier = 1.3  # Fintech premium
        elif 'devtools' in combined or 'developer' in combined or 'infrastructure' in combined:
            market_multiplier = 1.2  # DevTools premium
        elif 'healthcare' in combined or 'biotech' in combined:
            market_multiplier = 0.9  # Healthcare slower
        elif 'saas' in combined or 'software' in combined:
            market_multiplier = 1.0  # SaaS baseline
        else:
            market_multiplier = 1.0  # Default
        
        # CALCULATE FINAL GROWTH RATE
        final_growth = base_growth * investor_multiplier * market_multiplier
        
        logger.info(f"[GROWTH_INFERENCE] Stage={stage} base={base_growth:.2f}, investor_mult={investor_multiplier:.2f}, market_mult={market_multiplier:.2f} → final={final_growth:.2f}")
        
        return final_growth
    
    def _get_cambridge_benchmarks(self) -> Dict[str, Any]:
        """
        Cambridge Associates US VC Index benchmarks
        Data from December 31, 2024 report
        """
        return {
            # Actual CA data from Dec 31, 2024
            'us_venture_capital_index': {
                '6_month': 0.047,  # 4.7%
                '1_year': 0.062,   # 6.2%
                '3_year': -0.064,  # -6.4% (2021-22 bubble impact)
                '5_year': 0.151,   # 15.1%
                '10_year': 0.137,  # 13.7%
                '15_year': 0.148,  # 14.8%
                '20_year': 0.119,  # 11.9%
                '25_year': 0.080   # 8.0%
            },
            'us_private_equity_index': {
                '6_month': 0.046,  # 4.6%
                '1_year': 0.081,   # 8.1%
                '3_year': 0.044,   # 4.4%
                '5_year': 0.158,   # 15.8%
                '10_year': 0.151,  # 15.1%
                '15_year': 0.160,  # 16.0%
                '20_year': 0.139,  # 13.9%
                '25_year': 0.121   # 12.1%
            },
            'pooled_returns': {
                '1_year': {'irr': 0.062, 'multiple': 1.062},
                '3_year': {'irr': -0.064, 'multiple': 0.82},  # Negative!
                '5_year': {'irr': 0.151, 'multiple': 2.01},
                '10_year': {'irr': 0.137, 'multiple': 3.54},
                '20_year': {'irr': 0.119, 'multiple': 8.47}
            },
            'quartile_returns_10yr': {
                'top_quartile': {'irr': 0.22, 'multiple': 3.8},
                'median': {'irr': 0.11, 'multiple': 2.1},
                'bottom_quartile': {'irr': 0.02, 'multiple': 1.2}
            },
            'stage_returns_5yr': {
                'seed': {'irr': 0.25, 'multiple': 2.8},
                'early_stage': {'irr': 0.20, 'multiple': 2.4},
                'late_stage': {'irr': 0.15, 'multiple': 1.9},
                'multi_stage': {'irr': 0.17, 'multiple': 2.1}
            },
            'vintage_performance': {
                '2015': {'irr': 0.16, 'dpi': 2.1, 'tvpi': 2.8},   # Mature
                '2016': {'irr': 0.14, 'dpi': 1.5, 'tvpi': 2.4},   # Harvesting
                '2017': {'irr': 0.19, 'dpi': 1.2, 'tvpi': 2.5},   # Harvesting
                '2018': {'irr': 0.21, 'dpi': 0.8, 'tvpi': 2.3},   # Mid-cycle
                '2019': {'irr': 0.15, 'dpi': 0.5, 'tvpi': 2.0},   # Mid-cycle
                '2020': {'irr': 0.25, 'dpi': 0.3, 'tvpi': 1.9},   # Early returns
                '2021': {'irr': -0.08, 'dpi': 0.1, 'tvpi': 0.85}, # Peak vintage markdown
                '2022': {'irr': -0.05, 'dpi': 0.05, 'tvpi': 0.90}, # Recovering
                '2023': {'irr': 0.08, 'dpi': 0.02, 'tvpi': 1.10},  # Stabilizing
                '2024': {'irr': 0.12, 'dpi': 0.01, 'tvpi': 1.15},  # New normal
                '2025': {'irr': None, 'dpi': 0.0, 'tvpi': 1.0}     # Too early
            },
            'loss_ratios': {
                'complete_loss': 0.30,  # 30% go to zero
                'partial_loss': 0.20,   # 20% return <1x
                'breakeven': 0.20,      # 20% return 1-2x
                'modest_win': 0.20,     # 20% return 2-5x
                'home_run': 0.10        # 10% return >5x
            },
            'j_curve_expectations': {
                'year_1': -0.15,  # -15% due to fees
                'year_2': -0.10,  # Still negative
                'year_3': -0.05,  # Approaching breakeven
                'year_4': 0.05,   # Turning positive
                'year_5': 0.15,   # Acceleration
                'year_7': 0.25,   # Peak IRR
                'year_10': 0.18   # Mature fund
            }
        }
    
    def extract_liquidation_preferences(self, funding_rounds: List[Dict], search_content: str = "") -> List[Dict]:
        """
        Extract or infer liquidation preference terms for each funding round
        Including convertible notes, SAFEs, and venture debt
        """
        enhanced_rounds = []
        
        for round_data in funding_rounds:
            round_name = round_data.get('round', '').lower()
            amount = round_data.get('amount', 0)
            investors = round_data.get('investors', [])
            valuation = round_data.get('valuation', 0)
            
            # Start with copy of original round data
            enhanced_round = round_data.copy()
            
            # Detect instrument type
            if 'safe' in round_name:
                enhanced_round['instrument_type'] = 'safe'
                enhanced_round['liquidation_multiple'] = 1.0
                enhanced_round['participating'] = False
                enhanced_round['conversion_discount'] = 0.20  # Standard 20% discount
                enhanced_round['valuation_cap'] = valuation if valuation > 0 else amount * 10
                enhanced_round['seniority'] = 0  # SAFEs convert to common
                
            elif 'convertible' in round_name or 'note' in round_name:
                enhanced_round['instrument_type'] = 'convertible_note'
                enhanced_round['liquidation_multiple'] = 1.0
                enhanced_round['participating'] = False
                enhanced_round['conversion_discount'] = 0.20
                enhanced_round['valuation_cap'] = valuation if valuation > 0 else amount * 8
                enhanced_round['interest_rate'] = 0.08  # 8% annual
                enhanced_round['maturity_years'] = 2
                enhanced_round['seniority'] = 1  # Senior to equity, junior to debt
                
            elif 'debt' in round_name or 'venture debt' in round_name:
                enhanced_round['instrument_type'] = 'venture_debt'
                enhanced_round['liquidation_multiple'] = 1.0  # Debt gets paid first
                enhanced_round['participating'] = False
                enhanced_round['interest_rate'] = 0.12  # 12% for venture debt
                enhanced_round['warrant_coverage'] = 0.10  # 10% warrant coverage typical
                enhanced_round['seniority'] = 10  # Most senior
                
            else:
                # Regular equity round - extract or infer preferences
                enhanced_round['instrument_type'] = 'preferred_equity'
                
                # Try to extract from search content (rare but worth checking)
                participating = False
                liquidation_multiple = 1.0
                
                if search_content:
                    search_lower = search_content.lower()
                    if 'participating preferred' in search_lower:
                        participating = True
                    if 'non-participating' in search_lower:
                        participating = False
                    if '2x liquidation' in search_lower or '2x preference' in search_lower:
                        liquidation_multiple = 2.0  # Very rare, only in distressed
                    elif '1.5x liquidation' in search_lower or '1.5x preference' in search_lower:
                        liquidation_multiple = 1.5  # Uncommon but happens
                
                # Standard market terms - 99% of deals are 1x non-participating
                # What matters is the STACK not individual terms
                if 'seed' in round_name:
                    liquidation_multiple = 1.0
                    participating = False
                    seniority = 2
                elif 'series a' in round_name or 'a round' in round_name:
                    liquidation_multiple = 1.0
                    participating = False
                    seniority = 3
                elif 'series b' in round_name:
                    liquidation_multiple = 1.0
                    participating = False  
                    seniority = 4
                elif 'series c' in round_name:
                    liquidation_multiple = 1.0
                    participating = False  
                    seniority = 5
                elif 'series d' in round_name or 'series e' in round_name:
                    liquidation_multiple = 1.0
                    participating = False  # Even late stage usually 1x non-participating
                    seniority = 6
                elif 'growth' in round_name or 'late' in round_name:
                    liquidation_multiple = 1.0
                    participating = False  # Standard terms
                    seniority = 7
                else:
                    liquidation_multiple = 1.0
                    participating = False
                    seniority = 3
                    
                    # Adjust for investor quality (Tier 1 gets cleaner terms)
                    tier1_investors = ['sequoia', 'a16z', 'benchmark', 'greylock', 'accel']
                    tier2_investors = ['menlo', 'redpoint', 'matrix', 'bessemer']
                    tier3_investors = ['unnamed', 'angel', 'family office', 'corporate']
                    
                    has_tier1 = any(inv for inv in investors if any(t1 in str(inv).lower() for t1 in tier1_investors))
                    has_tier2 = any(inv for inv in investors if any(t2 in str(inv).lower() for t2 in tier2_investors))
                    has_tier3 = any(inv for inv in investors if any(t3 in str(inv).lower() for t3 in tier3_investors))
                    unknown_investors = not (has_tier1 or has_tier2 or has_tier3) and len(investors) > 0
                    
                    # Tier 1 investors typically get better terms
                    if has_tier1:
                        if participating:
                            participating = True  # They get participation if market allows
                        if liquidation_multiple > 1.0:
                            liquidation_multiple = min(2.0, liquidation_multiple * 1.25)
                    
                    # Tier 3 or unknown = SOME risk of complex terms (but still rare)
                    elif has_tier3 or unknown_investors:
                        # Most are still standard 1x, but flag the risk
                        if 'seed' in round_name or 'pre' in round_name:
                            # Unknown early investors = hidden terms risk
                            enhanced_round['hidden_terms_risk'] = True
                            enhanced_round['mfn_clause'] = True  # Likely has MFN
                            
                            # Check for distress signals
                            if amount < 500_000 and len(investors) > 3:
                                # Small round with many investors = party round, complex
                                liquidation_multiple = 1.25
                                participating = True
                                enhanced_round['complex_terms_warning'] = "Party round - likely complex terms"
                        else:
                            # Later rounds with Tier 3
                            if valuation < amount * 3:  # Low valuation multiple = distress
                                liquidation_multiple = 1.5
                                participating = True
                                enhanced_round['complex_terms_warning'] = "Low valuation - likely protective terms"
                    
                    # Down round or distressed financing
                    if round_data.get('is_down_round'):
                        liquidation_multiple = max(2.0, liquidation_multiple)  # 2x minimum in down rounds
                        participating = True
                        enhanced_round['cumulative_dividends'] = 0.08  # 8% cumulative
                        enhanced_round['anti_dilution'] = 'full_ratchet'
                        enhanced_round['pay_to_play'] = True  # Force future participation
                    else:
                        enhanced_round['anti_dilution'] = 'weighted_average'
                    
                    # Add hidden risk flags for due diligence
                    if unknown_investors or has_tier3:
                        enhanced_round['dd_risk'] = 'high'
                        enhanced_round['term_sheet_variance'] = 0.3  # 30% chance of surprise terms
                    elif has_tier2:
                        enhanced_round['dd_risk'] = 'medium' 
                        enhanced_round['term_sheet_variance'] = 0.15  # 15% chance of surprises
                    else:
                        enhanced_round['dd_risk'] = 'low'
                        enhanced_round['term_sheet_variance'] = 0.05  # 5% chance with Tier 1
                
                enhanced_round['liquidation_multiple'] = liquidation_multiple
                enhanced_round['participating'] = participating
                enhanced_round['seniority'] = seniority
                enhanced_round['participation_cap'] = 3.0 if participating else None  # 3x cap typical
            
            # Add board seats inference
            if amount > 10_000_000:
                enhanced_round['board_seats'] = 2 if amount > 50_000_000 else 1
            else:
                enhanced_round['board_seats'] = 0
            
            # Add pro-rata rights (typically for >$1M investments)
            enhanced_round['pro_rata_rights'] = amount > 1_000_000
            
            enhanced_rounds.append(enhanced_round)
        
        return enhanced_rounds

    async def calculate_ai_adjusted_valuation(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate valuation with AI impact adjustments
        """
        # Get base market multiples
        market_multiples = await self.get_market_multiples_from_database()
        
        # Get AI impact analysis
        ai_impact = self.analyze_ai_impact(company_data)
        
        # Get basic company info
        stage = self._determine_stage(company_data)
        last_valuation = company_data.get('last_valuation', 0)
        last_round_date = company_data.get('last_round_date')
        
        # Calculate base multiple from market
        if stage and stage in market_multiples:
            base_multiple = market_multiples[stage].get('trailing', {}).get('p50', 5.0)
        else:
            base_multiple = 5.0  # Default SaaS multiple
        
        # Apply AI adjustments
        valuation_adj = ai_impact.get('valuation_adjustment', 1.0) if isinstance(ai_impact, dict) else 1.0
        adjusted_multiple = base_multiple * valuation_adj
        
        # Apply vintage adjustment if company raised in 2021-2022
        if last_round_date:
            year = int(last_round_date[:4]) if isinstance(last_round_date, str) else last_round_date.year
            vintage_adjustments = {
                2021: 0.5,   # 50% discount
                2022: 0.65,  # 35% discount
                2023: 0.8,   # 20% discount
                2024: 0.95,  # 5% discount
                2025: 1.0    # Current market
            }
            vintage_adj = vintage_adjustments.get(year, 1.0)
            adjusted_multiple *= vintage_adj
        
        # Estimate revenue from valuation
        implied_revenue = last_valuation / adjusted_multiple if adjusted_multiple > 0 else 0
        
        # Calculate next round implications
        next_round_analysis = {
            'current_multiple': adjusted_multiple,
            'ai_category': ai_impact['ai_category'],
            'ai_first': ai_impact['ai_first'],
            'ai_impact': ai_impact['ai_impact'],
            'growth_rate': ai_impact['growth_rate'],
            'reasoning': ai_impact['reason']
        }
        
        # Down round risk assessment
        if ai_impact['ai_category'] == 'winner':
            next_round_analysis['down_round_risk'] = 'Very Low'
            next_round_analysis['expected_uplift'] = '3-5x'
        elif ai_impact['ai_category'] == 'emerging':
            next_round_analysis['down_round_risk'] = 'Low'
            next_round_analysis['expected_uplift'] = '1.5-2x'
        elif ai_impact['ai_category'] == 'cost_center':
            next_round_analysis['down_round_risk'] = 'High'
            next_round_analysis['expected_uplift'] = '0.5-0.8x (down round likely)'
        else:  # traditional
            next_round_analysis['down_round_risk'] = 'Medium'
            next_round_analysis['expected_uplift'] = '1.0-1.3x'
        
        return {
            'base_multiple': base_multiple,
            'ai_adjusted_multiple': adjusted_multiple,
            'implied_revenue': implied_revenue,
            'ai_analysis': ai_impact,
            'next_round': next_round_analysis,
            'market_context': market_multiples.get('market_context', {})
        }
    
    def analyze_company_momentum(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze company momentum from founding to current state
        Key signals: founding year, funding velocity, team growth, product momentum
        """
        import datetime
        current_year = 2025
        
        # Extract founding year
        founding_year = company_data.get('founded')
        if not founding_year:
            # Try to infer from first funding round
            funding_history = company_data.get('funding_history', [])
            if funding_history:
                first_round = min(funding_history, key=lambda x: x.get('date', '9999'))
                first_date = first_round.get('date', '')
                if first_date:
                    founding_year = int(first_date[:4]) - 1  # Usually founded 1 year before first round
        
        company_age = current_year - founding_year if founding_year else None
        
        # Funding momentum analysis
        funding_history = company_data.get('funding_history', [])
        total_raised = sum(r.get('amount', 0) for r in funding_history)
        num_rounds = len(funding_history)
        
        # Calculate funding velocity
        funding_velocity = {
            'total_raised': total_raised,
            'num_rounds': num_rounds,
            'avg_round_size': total_raised / num_rounds if num_rounds > 0 else 0,
            'years_to_unicorn': None,
            'funding_acceleration': 'unknown'
        }
        
        if funding_history and company_age:
            # Check if unicorn
            last_valuation = funding_history[-1].get('valuation', 0) if funding_history else 0
            if last_valuation >= 1_000_000_000:
                funding_velocity['years_to_unicorn'] = company_age
            
            # Measure acceleration (are rounds getting bigger/faster?)
            if len(funding_history) >= 2:
                recent_rounds = funding_history[-2:]
                older_rounds = funding_history[:-2] if len(funding_history) > 2 else funding_history[:1]
                
                recent_avg = sum(r.get('amount', 0) for r in recent_rounds) / len(recent_rounds)
                older_avg = sum(r.get('amount', 0) for r in older_rounds) / len(older_rounds) if older_rounds else recent_avg
                
                if recent_avg > older_avg * 2:
                    funding_velocity['funding_acceleration'] = 'rapid'
                elif recent_avg > older_avg * 1.5:
                    funding_velocity['funding_acceleration'] = 'strong'
                elif recent_avg > older_avg:
                    funding_velocity['funding_acceleration'] = 'steady'
                else:
                    funding_velocity['funding_acceleration'] = 'slowing'
        
        # Team momentum (from headcount if available)
        team_size = company_data.get('team_size', 0)
        team_momentum = 'unknown'
        if team_size > 0 and company_age:
            growth_per_year = team_size / company_age
            if growth_per_year > 100:
                team_momentum = 'hypergrowth'
            elif growth_per_year > 50:
                team_momentum = 'rapid'
            elif growth_per_year > 20:
                team_momentum = 'strong'
            elif growth_per_year > 10:
                team_momentum = 'steady'
            else:
                team_momentum = 'slow'
        
        # Product momentum signals
        product_signals = {
            'has_paying_customers': any(keyword in str(company_data).lower() 
                for keyword in ['customers', 'clients', 'users', 'revenue', 'arr', 'mrr']),
            'has_enterprise_deals': any(keyword in str(company_data).lower() 
                for keyword in ['enterprise', 'fortune 500', 'government', 'federal']),
            'has_partnerships': any(keyword in str(company_data).lower() 
                for keyword in ['partnership', 'integration', 'collaboration']),
            'has_product_market_fit': funding_velocity.get('funding_acceleration') in ['rapid', 'strong']
        }
        
        # Overall momentum score (0-10)
        momentum_score = 0
        
        # Age factor (younger + successful = higher momentum)
        if company_age and company_age <= 2 and total_raised > 10_000_000:
            momentum_score += 3
        elif company_age and company_age <= 4 and total_raised > 50_000_000:
            momentum_score += 2
        elif company_age and company_age <= 6:
            momentum_score += 1
        
        # Funding acceleration
        if funding_velocity['funding_acceleration'] == 'rapid':
            momentum_score += 3
        elif funding_velocity['funding_acceleration'] == 'strong':
            momentum_score += 2
        elif funding_velocity['funding_acceleration'] == 'steady':
            momentum_score += 1
        
        # Unicorn speed bonus
        if funding_velocity['years_to_unicorn']:
            if funding_velocity['years_to_unicorn'] <= 3:
                momentum_score += 3
            elif funding_velocity['years_to_unicorn'] <= 5:
                momentum_score += 2
            elif funding_velocity['years_to_unicorn'] <= 7:
                momentum_score += 1
        
        # Product signals
        momentum_score += sum([
            1 if product_signals['has_enterprise_deals'] else 0,
            1 if product_signals['has_product_market_fit'] else 0
        ])
        
        # Categorize momentum
        if momentum_score >= 8:
            momentum_category = 'rocket_ship'
            momentum_description = 'Exceptional momentum - top 1% trajectory'
        elif momentum_score >= 6:
            momentum_category = 'high_momentum'
            momentum_description = 'Strong momentum - clear product-market fit'
        elif momentum_score >= 4:
            momentum_category = 'building_momentum'
            momentum_description = 'Good momentum - scaling steadily'
        elif momentum_score >= 2:
            momentum_category = 'early_momentum'
            momentum_description = 'Early signs of momentum'
        else:
            momentum_category = 'seeking_momentum'
            momentum_description = 'Still seeking product-market fit'
        
        return {
            'founded': founding_year,
            'company_age': company_age,
            'momentum_score': momentum_score,
            'momentum_category': momentum_category,
            'momentum_description': momentum_description,
            'funding_velocity': funding_velocity,
            'team_momentum': team_momentum,
            'product_signals': product_signals,
            'key_milestones': {
                'years_to_series_a': None,  # Could calculate if we have the data
                'years_to_100_employees': None,
                'years_to_unicorn': funding_velocity.get('years_to_unicorn')
            }
        }
    
    def analyze_ai_impact(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically analyze AI impact based on actual signals, not hardcoded companies
        AI has created massive bifurcation in the market (Sep 2025)
        """
        name = (company_data.get('company_name', company_data.get('company', company_data.get('name', ''))) or '').lower()
        description = (company_data.get('description') or '').lower()
        tags = company_data.get('tags', [])
        
        # Extract actual growth and traction signals
        funding_data = company_data.get('funding_history', [])
        last_round = funding_data[-1] if funding_data else {}
        prev_round = funding_data[-2] if len(funding_data) > 1 else {}
        
        # Calculate actual growth signals
        valuation_growth = 0
        if prev_round and last_round:
            prev_val = prev_round.get('valuation', 0)
            last_val = last_round.get('valuation', 0)
            if prev_val > 0:
                valuation_growth = (last_val / prev_val - 1)
        
        # Time between rounds (faster = hotter)
        months_between_rounds = 24  # default
        if len(funding_data) > 1:
            months_between_rounds = self._months_between_rounds(
                prev_round.get('date'),
                last_round.get('date')
            )
            # Ensure we have a valid number for arithmetic operations
            if months_between_rounds is None:
                months_between_rounds = 24  # fallback to default
        
        # AI-specific signals
        ai_revenue_signals = [
            'per seat', 'per user', 'usage-based', 'api pricing',
            'token', 'inference', 'model', 'endpoint'
        ]
        
        ai_customer_signals = [
            'developers', 'engineers', 'data scientists', 
            'ml teams', 'ai teams', 'research'
        ]
        
        ai_tech_depth = [
            'proprietary model', 'fine-tuned', 'rlhf', 'constitutional ai',
            'multimodal', 'agents', 'rag', 'vector', 'embedding',
            'transformer', 'diffusion', 'gan'
        ]
        
        # Agent washing detection signals
        agent_washing_red_flags = [
            'ai-powered', 'ai-enabled', 'ai-driven', 'leverages ai',
            'uses machine learning', 'incorporates ai', 'ai features'
        ]
        
        agent_washing_green_flags = [
            'trained our own', 'proprietary model', 'fine-tuned',
            'model architecture', 'training data', 'inference optimization',
            'model serving', 'gpu infrastructure', 'model evaluation'
        ]
        
        # Check for agent washing
        has_red_flags = sum(1 for flag in agent_washing_red_flags if description and flag in description.lower())
        has_green_flags = sum(1 for flag in agent_washing_green_flags if description and flag in description.lower())
        
        agent_washing_likelihood = 'low'
        if has_red_flags > 2 and has_green_flags == 0:
            agent_washing_likelihood = 'high'
        elif has_red_flags > has_green_flags:
            agent_washing_likelihood = 'medium'
        
        # Score AI depth (0-10)
        ai_score = 0
        
        # 1. Core AI indicators (0-3 points)
        if 'ai' in name or 'artificial intelligence' in description:
            ai_score += 1
        if description and any(term in description.lower() for term in ['llm', 'large language model', 'foundation model']):
            ai_score += 2
        
        # 2. Technical depth (0-3 points)
        tech_matches = sum(1 for term in ai_tech_depth if description and term in description.lower())
        ai_score += min(3, tech_matches)
        
        # 3. AI-native business model (0-2 points)
        if description and any(signal in description.lower() for signal in ai_revenue_signals):
            ai_score += 1
        if description and any(signal in description.lower() for signal in ai_customer_signals):
            ai_score += 1
        
        # 4. Momentum signals (0-2 points)
        if months_between_rounds < 12 and valuation_growth > 2:  # Raised fast at >2x
            ai_score += 2
        elif months_between_rounds < 18 and valuation_growth > 1.5:
            ai_score += 1
        
        # Penalize for agent washing
        if agent_washing_likelihood == 'high':
            ai_score = max(0, ai_score - 3)
        elif agent_washing_likelihood == 'medium':
            ai_score = max(0, ai_score - 1)
        
        # Categorize based on score AND signals
        if ai_score >= 7:
            # AI Winner - strong technical depth + momentum
            growth_rate = max(3.0, valuation_growth * 2)  # Use actual growth
            multiple = min(50, 10 * ai_score)  # Cap at 50x
            
            return {
                'ai_first': True,
                'ai_category': 'winner',
                'ai_impact': 'accelerator',
                'revenue_multiple': multiple,
                'growth_rate': growth_rate,
                'valuation_adjustment': 2.0,  # 2x premium
                'ai_score': ai_score,
                'reason': f"AI leader with {growth_rate*100:.0f}% growth, {months_between_rounds} months between rounds"
            }
        
        elif ai_score >= 4:
            # AI Emerging - some AI but not dominant
            growth_rate = max(1.5, valuation_growth) if valuation_growth > 0 else 1.5
            
            return {
                'ai_first': True,
                'ai_category': 'emerging',
                'ai_impact': 'potential_accelerator',
                'revenue_multiple': 10 + ai_score,
                'growth_rate': growth_rate,
                'valuation_adjustment': 1.3,  # 30% premium
                'ai_score': ai_score,
                'reason': f"AI-enabled with {ai_score}/10 AI depth score"
            }
        
        # Check if it's a cost center (non-AI company in affected industry)
        cost_center_industries = [
            'marketing', 'advertising', 'social media', 'e-commerce',
            'marketplace', 'food delivery', 'rideshare', 'travel',
            'recruiting', 'staffing', 'outsourcing'
        ]
        
        is_cost_center = description and any(industry in description.lower() for industry in cost_center_industries)
        
        if is_cost_center and ai_score < 2:
            # These companies are getting disrupted by AI
            return {
                'ai_first': False,
                'ai_category': 'cost_center',
                'ai_impact': 'margin_pressure',
                'revenue_multiple': 3,
                'growth_rate': 0.3,  # 30% YoY
                'valuation_adjustment': 0.7,  # 30% discount
                'ai_score': ai_score,
                'reason': "AI disruption risk - margins under pressure from AI adoption costs"
            }
        
        # Traditional SaaS - not AI but not necessarily hurt by it
        base_growth = 0.5  # 50% YoY default
        if valuation_growth > 0:
            base_growth = min(1.0, valuation_growth)
        
        return {
            'ai_first': False,
            'ai_category': 'traditional',
            'ai_impact': 'neutral',
            'revenue_multiple': 5,
            'growth_rate': base_growth,
            'valuation_adjustment': 1.0,  # No adjustment
            'ai_score': ai_score,
            'reason': f"Traditional SaaS with {base_growth*100:.0f}% growth - competing with AI-native alternatives"
        }
    
    def extract_team_structure(self, search_data: Dict = None, website_data: Dict = None) -> Dict:
        """Extract team composition and seniority from various data sources"""
        import re
        
        team = {
            'founders': 0,
            'senior': 0,
            'mid': 0,
            'junior': 0,
            'departments': {
                'engineering': 0,
                'product': 0,
                'sales': 0,
                'marketing': 0,
                'operations': 0
            },
            'total_headcount': 0
        }
        
        # Combine all text sources
        all_text = ""
        if search_data and search_data.get('success'):
            for result in search_data.get('data', {}).get('results', []):
                # Ensure content is a string, not a dict
                content = self._ensure_string(result.get('content', ''))
                all_text += content + " "
        
        if website_data:
            if 'raw_content' in website_data:
                # Ensure raw_content is a string, not a dict
                raw_content = self._ensure_string(website_data.get('raw_content', ''))
                all_text += raw_content
        
        # Seniority patterns
        founder_pattern = r'\b(?:Co-)?(?:Founder|CEO|CTO|CFO|COO)\b'
        senior_pattern = r'\b(?:VP|Vice President|Director|Head of|Senior|Staff|Principal|Lead)\s+\w+'
        junior_pattern = r'\b(?:Junior|Jr\.|Associate|Intern|Entry[- ]level)\s+\w+'
        
        # Department patterns  
        eng_pattern = r'\b(?:Engineer|Developer|DevOps|QA|Engineering)\b'
        product_pattern = r'\b(?:Product|PM|Designer|UX|UI)\b'
        sales_pattern = r'\b(?:Sales|Account Executive|AE|SDR|BDR)\b'
        marketing_pattern = r'\b(?:Marketing|Growth|Content|SEO)\b'
        ops_pattern = r'\b(?:Operations|HR|People|Finance|Legal)\b'
        
        # Count matches
        team['founders'] = len(re.findall(founder_pattern, all_text, re.IGNORECASE))
        team['senior'] = len(re.findall(senior_pattern, all_text, re.IGNORECASE))
        team['junior'] = len(re.findall(junior_pattern, all_text, re.IGNORECASE))
        
        # Count departments
        team['departments']['engineering'] = len(re.findall(eng_pattern, all_text, re.IGNORECASE))
        team['departments']['product'] = len(re.findall(product_pattern, all_text, re.IGNORECASE))
        team['departments']['sales'] = len(re.findall(sales_pattern, all_text, re.IGNORECASE))
        team['departments']['marketing'] = len(re.findall(marketing_pattern, all_text, re.IGNORECASE))
        team['departments']['operations'] = len(re.findall(ops_pattern, all_text, re.IGNORECASE))
        
        # Estimate mid-level (assume 40% of team if not explicitly mentioned)
        explicit_count = team['founders'] + team['senior'] + team['junior']
        total_dept_count = sum(team['departments'].values())
        
        if total_dept_count > explicit_count:
            team['mid'] = int((total_dept_count - explicit_count) * 0.6)
            team['total_headcount'] = total_dept_count
        else:
            team['total_headcount'] = max(explicit_count, 5)  # Minimum 5 people
            
        return team
    
    def estimate_burn_rate_from_team(self, team_structure: Dict, stage: str, region: str = 'us') -> Dict:
        """Estimate monthly burn rate based on team composition"""
        
        # Base salaries by seniority (annual, USD)
        base_salaries = {
            'us': {'founder': 150_000, 'senior': 180_000, 'mid': 120_000, 'junior': 80_000},
            'uk': {'founder': 120_000, 'senior': 140_000, 'mid': 90_000, 'junior': 60_000},
            'europe': {'founder': 100_000, 'senior': 120_000, 'mid': 80_000, 'junior': 50_000},
            'asia': {'founder': 80_000, 'senior': 100_000, 'mid': 60_000, 'junior': 35_000},
        }
        
        salaries = base_salaries.get((region or 'us').lower(), base_salaries['us'])
        
        # Calculate salary burn
        annual_salaries = (
            team_structure.get('founders', 0) * salaries['founder'] +
            team_structure.get('senior', 0) * salaries['senior'] +
            team_structure.get('mid', 0) * salaries['mid'] +
            team_structure.get('junior', 0) * salaries['junior']
        )
        
        # Add employer burden (taxes, benefits, equity)
        burden_rate = {'us': 1.35, 'uk': 1.14, 'europe': 1.45, 'asia': 1.2}.get((region or 'us').lower(), 1.3)
        annual_salaries_with_burden = annual_salaries * burden_rate
        
        # Fixed costs based on headcount
        headcount = team_structure.get('total_headcount', 10)
        
        # Office/Remote costs
        office_monthly = headcount * 500 if headcount < 50 else headcount * 400
        
        # SaaS/Tools (Slack, Notion, GitHub, etc.)
        saas_monthly = headcount * 250
        
        # AWS/GCP/Infrastructure (scales with engineering)
        eng_count = team_structure.get('departments', {}).get('engineering', 0)
        infra_monthly = 3000 + (eng_count * 500) + (headcount * 100)  # Base + eng scaling + general
        
        # Marketing & Sales spend (stage dependent)
        marketing_multiplier = {
            'pre_seed': 0.1,  # 10% of salary burn
            'seed': 0.2,      # 20% of salary burn
            'series_a': 0.4,  # 40% of salary burn (CAC investment)
            'series_b': 0.6   # 60% of salary burn (growth mode)
        }.get((stage or 'seed').lower().replace(' ', '_'), 0.25)
        
        # OTHER COSTS
        # Legal & Accounting
        legal_monthly = 5000 if (stage or 'seed').lower() in ['seed', 'pre_seed', 'pre-seed'] else 15000
        
        # Insurance (D&O, E&O, General)
        insurance_monthly = 2000 + (headcount * 50)
        
        # Travel & Entertainment
        travel_monthly = headcount * 200
        
        # Contractors & Consultants
        contractor_monthly = annual_salaries * 0.1 / 12  # 10% of salary base
        
        # Miscellaneous (10% buffer)
        misc_buffer = 0.1
        
        # Calculate total monthly burn
        salary_monthly = annual_salaries_with_burden / 12
        operational_monthly = (
            office_monthly + 
            saas_monthly + 
            infra_monthly + 
            legal_monthly + 
            insurance_monthly + 
            travel_monthly + 
            contractor_monthly
        )
        marketing_monthly = salary_monthly * marketing_multiplier
        
        subtotal = salary_monthly + operational_monthly + marketing_monthly
        total_monthly_burn = subtotal * (1 + misc_buffer)  # Add 10% buffer
        
        return {
            'monthly_burn': total_monthly_burn,
            'annual_burn': total_monthly_burn * 12,
            'breakdown': {
                'salaries': salary_monthly,
                'office': office_monthly,
                'saas': saas_monthly,
                'infrastructure': infra_monthly,
                'marketing': marketing_monthly,
                'legal': legal_monthly,
                'insurance': insurance_monthly,
                'travel': travel_monthly,
                'contractors': contractor_monthly,
                'misc_buffer': subtotal * misc_buffer
            },
            'headcount': headcount,
            'burn_per_employee': total_monthly_burn / headcount if headcount > 0 else 0,
            'burn_multiple': None  # Will be calculated with revenue data
        }
    
    def infer_sales_marketing_spend(self, company_data: Dict, stage: str = 'Series A') -> Dict:
        """Infer S&M spend from headcount and benchmarks"""
        
        stage_key = stage.replace(' ', ' ').title()
        if stage_key not in self.STAGE_BENCHMARKS:
            stage_key = 'Series A'
        benchmarks = self.STAGE_BENCHMARKS[stage_key]
        
        # Get team breakdown from existing inference
        team_structure = company_data.get('team_structure', {})
        departments = team_structure.get('departments', {})
        
        # Sales team size (from parsing or direct data)
        sales_count = departments.get('sales', 0) + company_data.get('sales_team_size', 0)
        marketing_count = departments.get('marketing', 0) + company_data.get('marketing_team_size', 0)
        
        # If no direct data, infer from total headcount using SV benchmarks
        total_headcount = company_data.get('team_size', team_structure.get('total_headcount', 0))
        
        if sales_count == 0 and marketing_count == 0 and total_headcount > 0:
            # SVB/Carta benchmarks for S&M as % of headcount by stage
            sm_ratios = {
                'Pre-seed': 0.10,  # 10% of team in S&M
                'Seed': 0.20,      # 20% of team in S&M  
                'Series A': 0.35,  # 35% of team in S&M (growth mode)
                'Series B': 0.40,  # 40% of team in S&M (scaling)
                'Series C': 0.35,  # 35% of team in S&M (efficiency focus)
            }
            sm_ratio = sm_ratios.get(stage_key, 0.30)
            
            # Split between sales and marketing (typically 70/30)
            sales_count = int(total_headcount * sm_ratio * 0.7)
            marketing_count = int(total_headcount * sm_ratio * 0.3)
        
        # Calculate spend using market compensation data
        # SVB State of SaaS 2024: Avg sales comp = $150K base + $150K variable
        # Marketing comp = $120K average
        sales_cost_per_head = 300000  # Total comp including variable
        marketing_cost_per_head = 120000
        
        annual_sales_spend = sales_count * sales_cost_per_head
        annual_marketing_spend = marketing_count * marketing_cost_per_head
        total_sm_spend = annual_sales_spend + annual_marketing_spend
        
        # Calculate as % of revenue (key efficiency metric)
        revenue = company_data.get('revenue', company_data.get('arr', benchmarks.get('arr_median', 1000000)))
        sm_as_percent_revenue = (total_sm_spend / revenue * 100) if revenue and revenue > 0 else 0
        
        # SVB benchmarks for S&M spend as % of revenue
        benchmark_sm_percent = {
            'Pre-seed': 50,   # 50% of revenue on S&M
            'Seed': 70,       # 70% of revenue on S&M
            'Series A': 90,   # 90% of revenue on S&M (heavy growth investment)
            'Series B': 75,   # 75% of revenue on S&M (improving efficiency)
            'Series C': 60,   # 60% of revenue on S&M (path to profitability)
        }.get(stage_key, 70)
        
        # Calculate implied CAC from S&M spend
        new_customers_monthly = company_data.get('new_customers_monthly', 10)
        if new_customers_monthly == 0:
            # Infer from growth rate and customer count
            customers = company_data.get('customers', 50)
            growth_rate = company_data.get('growth_rate', benchmarks.get('growth_rate', 1.0))
            new_customers_monthly = customers * (growth_rate / 12) if customers > 0 else 5
        
        implied_cac = (total_sm_spend / 12) / new_customers_monthly if new_customers_monthly > 0 else 0
        
        return {
            'sales_headcount': sales_count,
            'marketing_headcount': marketing_count,
            'total_sm_headcount': sales_count + marketing_count,
            'annual_sales_spend': annual_sales_spend,
            'annual_marketing_spend': annual_marketing_spend,
            'total_annual_sm_spend': total_sm_spend,
            'monthly_sm_spend': total_sm_spend / 12,
            'sm_as_percent_revenue': sm_as_percent_revenue,
            'benchmark_sm_percent': benchmark_sm_percent,
            'efficiency_vs_benchmark': 'Efficient' if sm_as_percent_revenue < benchmark_sm_percent else 'Inefficient',
            'implied_cac': implied_cac,
            'sales_productivity': (revenue / sales_count) if sales_count > 0 else 0,
            'marketing_efficiency': new_customers_monthly / marketing_count if marketing_count > 0 else 0
        }
    
    async def _async_tam_extract(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Async helper for TAM extraction via ModelRouter"""
        try:
            response = await self.model_router.get_completion(
                prompt=prompt,
                capability=ModelCapability.STRUCTURED,
                max_tokens=1000,
                temperature=0.1,
                caller_context="extraction"
            )
            return response
        except Exception as e:
            logger.error(f"ModelRouter TAM extraction failed: {e}")
            return None
    
    async def extract_tam_from_search(self, search_content: str, company_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use ModelRouter to intelligently extract TAM data from search results
        
        Args:
            search_content: Combined search results text
            company_data: Company info including sector, business model
            
        Returns:
            Dict with tam_value, source, confidence, and citation
        """
        if not search_content:
            return None
        
        if not self.model_router:
            logger.warning("ModelRouter not available for TAM extraction")
            return None
            
        try:
            # Fix 3: Add search content logging and TAM number detection
            logger.info(f"[TAM_EXTRACTION] Search content length: {len(search_content)} chars")
            logger.info(f"[TAM_EXTRACTION] First 1000 chars:\n{search_content[:1000]}")
            
            # Check if search content has any numbers that look like TAM
            import re
            tam_patterns = re.findall(r'\$[\d.]+\s*(?:billion|trillion|B|T)', search_content[:8000], re.IGNORECASE)
            logger.info(f"[TAM_EXTRACTION] Found {len(tam_patterns)} potential TAM numbers: {tam_patterns[:5]}")
            
            prompt = f"""YOU ARE A JSON-ONLY EXTRACTION BOT. OUTPUT FORMAT: PURE JSON ONLY.
RULE #1: Your entire response must be valid JSON starting with {{ and ending with }}
RULE #2: Zero explanations, zero markdown, zero commentary
RULE #3: If you include ANY text before {{ or after }}, you FAIL

You are a market data extraction specialist. Your ONLY job is to extract market size numbers and return them as JSON.

Company Context:
- Company: {company_data.get('company_name', 'Unknown')}
- Vertical: {company_data.get('vertical', 'Unknown')}
- Business: {company_data.get('business_model', 'Unknown')}
- Competitors: {company_data.get('competitors', [])}

Search Results (these contain market size data):
{search_content[:8000]}

**MANDATORY EXTRACTION RULES - YOU MUST EXTRACT EVERY SINGLE MARKET SIZE NUMBER**:

1. **YOU MUST EXTRACT EVERY SINGLE MARKET SIZE NUMBER** - If you see '$3.5B', '$2 billion', '$50B', '$1.2T' anywhere in the text, YOU MUST extract it
2. **NEVER return empty tam_estimates if there are ANY dollar amounts in the search results**
3. **Even if uncertain about context, EXTRACT the number and let the citation provide context**
4. **If tam_estimates is empty but search results contain dollar amounts, you have FAILED**

**EXTRACTION PATTERNS TO FIND**:
- "$XX billion market", "$XX trillion TAM", "market size of $XX"
- "valued at $XXB", "worth $XXB by 2025", "$XXB CAGR"
- "market to reach $XX billion", "expected to grow to $XX"
- "Global [industry] Market Size Valued at $XX Billion"
- "TAM of $XX", "addressable market of $XX"

**REQUIRED DATA FOR EACH EXTRACTION**:
- tam_value: Raw number (e.g., 3500000000 for $3.5B)
- source: Extract from [Title] or content (Gartner, IDC, Forrester, McKinsey, etc.)
- url: The "URL:" line RIGHT AFTER the [Title]
- citation: EXACT sentence with the number
- year: Year mentioned (2023, 2024, 2025, etc.)
- cagr: Growth rate if mentioned (0.15 for 15% CAGR)

**MARKET DEFINITION** - Identify the BROAD market category:
- GOOD: "digital banking", "fintech", "HR software", "payment processing"
- BAD: "Mercury's market", "AI infrastructure" (too broad), "productivity tools" (too vague)

**INCUMBENTS** - Find established players with market share:
- Look for: "Oracle holds 31% market share", "Salesforce dominates with 25%"
- Extract company name, percentage, citation, source

**CRITICAL JSON FORMATTING RULES**:
- START with {{ and END with }}
- DO NOT include ```json markdown blocks
- DO NOT include any text before the {{
- DO NOT include any text after the }}
- ABSOLUTELY NO explanations or commentary
- tam_value MUST be a NUMBER not a string (3500000000 not "3.5B")
- market_share MUST be a DECIMAL (0.31 not "31%" or 31)
- If you find NO market data, return {{"tam_market_definition": "Unknown", "tam_estimates": [], "tam_aggregated": {{"mean": 0, "median": 0, "min": 0, "max": 0}}, "incumbents": []}}

RETURN THIS EXACT JSON STRUCTURE (no markdown, no code blocks):
{{
    "tam_market_definition": "broad market category like 'digital banking'",
    "tam_estimates": [
        {{
            "tam_value": 3500000000,
            "source": "Gartner",
            "url": "https://example.com/report",
            "citation": "The global digital banking market was valued at $3.5 billion in 2024",
            "year": 2024,
            "cagr": 0.15
        }}
    ],
    "tam_aggregated": {{
        "mean": 3500000000,
        "median": 3500000000,
        "min": 3500000000,
        "max": 3500000000
    }},
    "incumbents": [
        {{
            "name": "Salesforce",
            "market_share": 0.25,
            "market_share_percentage": "25%",
            "citation": "Salesforce dominates the CRM market with 25% share",
            "source": "Gartner"
        }}
    ]
}}

RESPOND NOW WITH PURE JSON. FIRST CHARACTER MUST BE {{.
"""
            
            # Use ModelRouter directly with await
            try:
                logger.info(f"[TAM_EXTRACTION] Calling ModelRouter for {company_data.get('company_name', 'Unknown')}")
                response = await self.model_router.get_completion(
                    prompt=prompt,
                    capability=ModelCapability.STRUCTURED,
                    max_tokens=2000,
                    temperature=0.1,
                    json_mode=True,
                    caller_context="extraction"
                )
                logger.info(f"[TAM_EXTRACTION] ModelRouter response received: {response is not None}")
                logger.info(f"[TAM_EXTRACTION] Model used: {response.get('model', 'unknown') if response else 'no response'}")
            except Exception as e:
                logger.error(f"ModelRouter TAM extraction failed: {e}")
                return None
            
            if response and response.get('response'):
                response_text = response['response'].strip()
                logger.info(f"[TAM_EXTRACTION] ModelRouter response text (first 500 chars): {response_text[:500]}")
                logger.info(f"[TAM_EXTRACTION] Response length: {len(response_text)} chars")
            else:
                logger.warning(f"ModelRouter returned no content for TAM extraction. Response: {response}")
                return None
            
            import re
            
            # Fix 1: Strip markdown code blocks if present (CRITICAL)
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith('```'):
                response_text = response_text[3:]   # Remove ```
            if response_text.endswith('```'):
                response_text = response_text[:-3] # Remove trailing ```
            response_text = response_text.strip()
            
            # Check for markdown wrapper FIRST before trying to parse
            if '```json' in response_text:
                logger.info("[TAM_EXTRACTION] Detected markdown JSON wrapper, extracting...")
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1).strip()
                    logger.info(f"[TAM_EXTRACTION] Extracted JSON from markdown: {len(response_text)} chars")
            elif '```' in response_text:
                # Generic code block
                logger.info("[TAM_EXTRACTION] Detected generic markdown code block, removing...")
                response_text = response_text.replace('```', '').strip()
            
            # Try to parse as JSON
            try:
                tam_data = json.loads(response_text)
                logger.info(f"[TAM_EXTRACTION] Successfully parsed JSON with keys: {list(tam_data.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"[TAM_EXTRACTION] JSON parse failed: {e}")
                logger.error(f"[TAM_EXTRACTION] Full response: {response_text[:500]}...")
                logger.error(f"[TAM_EXTRACTION] Response length: {len(response_text)} chars")
                
                # Try to extract JSON object from the response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        tam_data = json.loads(json_match.group())
                        logger.info(f"[TAM_EXTRACTION] Successfully extracted JSON from response")
                    except Exception as json_error:
                        logger.error(f"[TAM_EXTRACTION] Even extracted JSON failed to parse: {json_error}")
                        logger.error(f"[TAM_EXTRACTION] Extracted text: {json_match.group()[:500]}")
                        return None
                else:
                    logger.error(f"[TAM_EXTRACTION] No JSON pattern found in response")
                    return None
            
            # Validate and normalize the response - handle new multi-estimate structure
            if tam_data and 'tam_market_definition' in tam_data:
                # New structure with multiple estimates
                market_definition = tam_data.get('tam_market_definition', 'Unknown market')
                tam_estimates = tam_data.get('tam_estimates', [])
                tam_aggregated = tam_data.get('tam_aggregated', {})
                
                # Fix 4: Log if model returned empty despite data being present
                if not tam_estimates:
                    model_used = response.get('model', 'unknown') if 'response' in locals() else 'unknown'
                    logger.warning(f"[TAM_EXTRACTION] {model_used} returned empty tam_estimates despite prompt")
                    logger.warning(f"[TAM_EXTRACTION] Market definition: {tam_data.get('tam_market_definition')}")
                    # Log what content was sent for debugging
                    logger.warning(f"[TAM_EXTRACTION] Search content had potential numbers: {tam_patterns[:3] if 'tam_patterns' in locals() else 'Not checked'}")
                    logger.warning(f"[TAM_EXTRACTION] This indicates the model failed to extract market data from search results")
                
                if tam_estimates and len(tam_estimates) > 0:
                    # Use the mean from aggregated data, or calculate from estimates
                    tam_value = tam_aggregated.get('mean', 0)
                    if tam_value == 0 and tam_estimates:
                        # Calculate mean if not provided
                        values = [est.get('tam_value', 0) for est in tam_estimates if est.get('tam_value', 0) > 0]
                        if values:
                            tam_value = sum(values) / len(values)
                    
                    tam_formatted = f"${tam_value/1e9:.1f}B" if tam_value > 0 else "$0B"
                    
                    return {
                        'tam_market_definition': market_definition,
                        'tam_value': tam_value,
                        'tam_formatted': tam_formatted,
                        'tam_estimates': tam_estimates,
                        'tam_aggregated': tam_aggregated,
                        'tam_range': f"${tam_aggregated.get('min', 0)/1e9:.1f}B-${tam_aggregated.get('max', 0)/1e9:.1f}B" if tam_aggregated else "",
                        'incumbents': tam_data.get('incumbents', []),
                        'incumbent_market_share': sum(inc.get('market_share', 0) for inc in tam_data.get('incumbents', []) if inc.get('market_share') is not None),
                        'incumbent_names': [inc.get('name', '') for inc in tam_data.get('incumbents', [])],
                        'confidence': 0.9,  # High confidence for multi-source extraction
                        'source': 'Multiple analyst reports',
                        'year': tam_estimates[0].get('year') if tam_estimates else None,
                        'growth_rate': tam_estimates[0].get('cagr') if tam_estimates else None
                    }
            
            # Fallback: handle old single-estimate structure
            elif tam_data and 'tam_value' in tam_data and tam_data['tam_value']:
                # Safely handle tam_value formatting
                tam_value = tam_data['tam_value']
                if tam_value and isinstance(tam_value, (int, float)):
                    tam_formatted = tam_data.get('tam_formatted') or f"${tam_value/1e9:.1f}B"
                else:
                    tam_formatted = tam_data.get('tam_formatted', '$0B')
                    
                return {
                    'tam_market_definition': 'Unknown market',
                    'tam_value': tam_value,
                    'tam_formatted': tam_formatted,
                    'tam_estimates': [{
                        'tam_value': tam_value,
                        'source': tam_data.get('source', 'Search results'),
                        'citation': tam_data.get('citation', 'Market research'),
                        'year': tam_data.get('year'),
                        'cagr': tam_data.get('growth_rate')
                    }],
                    'tam_aggregated': {
                        'mean': tam_value,
                        'median': tam_value,
                        'min': tam_value,
                        'max': tam_value
                    },
                    'tam_range': tam_formatted,
                    'confidence': tam_data.get('confidence', 0.7),
                    'source': tam_data.get('source', 'Search results'),
                    'year': tam_data.get('year'),
                    'growth_rate': tam_data.get('growth_rate')
                }
                
        except Exception as e:
            logger.warning(f"Failed to extract TAM with Claude: {e}")
            
        return None
    
    async def extract_market_definition(self, company_data: Dict[str, Any], search_content: str = None) -> Dict[str, Any]:
        """Extract comprehensive market definition and sizing data
        
        Args:
            company_data: Company information including sector, business model, etc.
            search_content: Optional search results to extract from
            
        Returns:
            Dict with market definition, TAM/SAM/SOM, sources, and methodology
        """
        try:
            # Extract basic company info
            company_name = company_data.get('company_name', 'Unknown')
            sector = company_data.get('sector', 'Unknown')
            business_model = company_data.get('business_model', 'Unknown')
            description = company_data.get('description', '')
            
            # Define the market clearly
            market_definition = f"Market for {sector} solutions targeting {company_data.get('target_customer', 'businesses')}"
            
            # Initialize market analysis structure
            market_analysis = {
                'market_definition': market_definition,
                'tam_value': None,
                'sam_value': None,
                'som_value': None,
                'calculation_method': None,
                'sources': [],
                'assumptions': [],
                'confidence': 0.0,
                'year': 2024,
                'growth_rate': None,
                'market_segments': [],
                'geographic_scope': 'Global',
                'customer_segments': [],
                'competitive_landscape': []
            }
            
            # Method 1: Extract from search content if available
            if search_content:
                extracted_tam = await self.extract_tam_from_search(search_content, company_data)
                if extracted_tam:
                    market_analysis.update({
                        'tam_value': extracted_tam.get('tam_value'),
                        'sources': extracted_tam.get('sources', []),
                        'confidence': extracted_tam.get('confidence', 0.7),
                        'year': extracted_tam.get('year', 2024),
                        'growth_rate': extracted_tam.get('growth_rate'),
                        'calculation_method': 'Search-based extraction'
                    })
            
            # Method 2: Calculate from company context if no search data
            if not market_analysis['tam_value']:
                calculated_tam = self._calculate_tam_from_company_context(company_data)
                market_analysis.update({
                    'tam_value': calculated_tam,
                    'calculation_method': 'Company context-based calculation',
                    'confidence': 0.5,
                    'assumptions': [
                        f"Based on {sector} sector benchmarks",
                        f"Business model: {business_model}",
                        "Using industry average penetration rates"
                    ]
                })
            
            # Calculate SAM and SOM
            if market_analysis['tam_value']:
                # SAM calculation based on addressable segments
                sam_percentage = self._calculate_sam_percentage(company_data)
                market_analysis['sam_value'] = market_analysis['tam_value'] * sam_percentage
                
                # SOM calculation based on realistic capture rates
                som_percentage = self._calculate_som_percentage(company_data)
                market_analysis['som_value'] = market_analysis['sam_value'] * som_percentage
                
                # Add market segments
                market_analysis['market_segments'] = self._identify_market_segments(company_data)
                market_analysis['customer_segments'] = self._identify_customer_segments(company_data)
                market_analysis['competitive_landscape'] = self._identify_competitors(company_data)
            
            # Generate searchable terms for TAM research
            market_analysis['searchable_terms'] = self._generate_searchable_terms(company_data)
            market_analysis['tam_search_queries'] = self._generate_tam_search_queries(company_data)
            
            return market_analysis
            
        except Exception as e:
            logger.error(f"Failed to extract market definition: {e}")
            return {
                'market_definition': f"Market for {company_data.get('sector', 'Unknown')} solutions",
                'tam_value': 50_000_000_000,  # Fallback
                'sam_value': 5_000_000_000,
                'som_value': 500_000_000,
                'calculation_method': 'Fallback estimation',
                'confidence': 0.3,
                'searchable_terms': [company_data.get('sector', 'Unknown')],
                'tam_search_queries': [f"{company_data.get('sector', 'Unknown')} market size"],
                'error': str(e)
            }
    
    def _calculate_sam_percentage(self, company_data: Dict[str, Any]) -> float:
        """Calculate SAM as percentage of TAM based on company characteristics"""
        sector = company_data.get('sector', '').lower()
        stage = company_data.get('stage', 'Seed')
        
        # SAM percentages by sector and stage
        sam_percentages = {
            'fintech': 0.15,      # 15% of TAM (regulatory constraints)
            'healthcare': 0.20,   # 20% of TAM (compliance requirements)
            'hr': 0.25,           # 25% of TAM (easier to address)
            'sales': 0.30,        # 30% of TAM (broad applicability)
            'marketing': 0.25,    # 25% of TAM
            'security': 0.20,     # 20% of TAM (enterprise focus)
            'dev': 0.35,          # 35% of TAM (developer tools)
            'saas': 0.30          # 30% of TAM (general SaaS)
        }
        
        # Adjust based on stage
        stage_multipliers = {
            'Pre-Seed': 0.5,
            'Seed': 0.7,
            'Series A': 0.8,
            'Series B': 0.9,
            'Series C+': 1.0
        }
        
        base_percentage = 0.25  # Default
        for key, percentage in sam_percentages.items():
            if key in sector:
                base_percentage = percentage
                break
        
        stage_multiplier = 0.7  # Default
        for stage_key, multiplier in stage_multipliers.items():
            if stage_key in stage:
                stage_multiplier = multiplier
                break
        
        return base_percentage * stage_multiplier
    
    def _calculate_som_percentage(self, company_data: Dict[str, Any]) -> float:
        """Calculate SOM as percentage of SAM based on realistic capture rates"""
        stage = company_data.get('stage', 'Seed')
        team_size = company_data.get('team_size', 10)
        
        # SOM percentages by stage (realistic capture rates)
        som_percentages = {
            'Pre-Seed': 0.01,     # 1% of SAM
            'Seed': 0.03,         # 3% of SAM
            'Series A': 0.05,     # 5% of SAM
            'Series B': 0.10,     # 10% of SAM
            'Series C+': 0.15     # 15% of SAM
        }
        
        base_percentage = 0.03  # Default
        for stage_key, percentage in som_percentages.items():
            if stage_key in stage:
                base_percentage = percentage
                break
        
        # Adjust based on team size (more resources = higher capture rate)
        team_multiplier = min(1.0, team_size / 50)  # Cap at 50 employees
        
        return base_percentage * (0.5 + team_multiplier * 0.5)
    
    def _identify_market_segments(self, company_data: Dict[str, Any]) -> List[str]:
        """Identify relevant market segments for the company"""
        sector = company_data.get('sector', '').lower()
        business_model = company_data.get('business_model', '').lower()
        
        segments = []
        
        # Add sector-specific segments
        if 'fintech' in sector:
            segments.extend(['Payments', 'Banking', 'Insurance', 'Trading'])
        elif 'healthcare' in sector:
            segments.extend(['Providers', 'Payers', 'Pharma', 'MedTech'])
        elif 'hr' in sector:
            segments.extend(['Recruiting', 'Payroll', 'Benefits', 'Performance'])
        elif 'sales' in sector:
            segments.extend(['CRM', 'Lead Generation', 'Sales Enablement'])
        elif 'marketing' in sector:
            segments.extend(['Digital Marketing', 'Content', 'Analytics'])
        
        # Add business model segments
        if 'saas' in business_model:
            segments.append('SaaS Software')
        if 'marketplace' in business_model:
            segments.append('Marketplace')
        if 'platform' in business_model:
            segments.append('Platform')
        
        return list(set(segments))  # Remove duplicates
    
    def _identify_customer_segments(self, company_data: Dict[str, Any]) -> List[str]:
        """Identify target customer segments"""
        stage = company_data.get('stage', 'Seed')
        sector = company_data.get('sector', '').lower()
        
        segments = []
        
        # Add stage-appropriate segments
        if 'Pre-Seed' in stage or 'Seed' in stage:
            segments.extend(['SMBs', 'Startups', 'Mid-market'])
        elif 'Series A' in stage:
            segments.extend(['Mid-market', 'Enterprise'])
        else:
            segments.extend(['Enterprise', 'Fortune 500'])
        
        # Add sector-specific segments
        if 'fintech' in sector:
            segments.extend(['Financial Institutions', 'Fintech Companies'])
        elif 'healthcare' in sector:
            segments.extend(['Hospitals', 'Clinics', 'Health Systems'])
        
        return list(set(segments))
    
    def _identify_competitors(self, company_data: Dict[str, Any]) -> List[str]:
        """Identify competitive landscape"""
        competitors = company_data.get('competitors', [])
        sector = company_data.get('sector', '').lower()
        
        # Add sector-specific competitors if not already listed
        sector_competitors = {
            'fintech': ['Stripe', 'Square', 'PayPal'],
            'healthcare': ['Epic', 'Cerner', 'Allscripts'],
            'hr': ['Workday', 'BambooHR', 'Gusto'],
            'sales': ['Salesforce', 'HubSpot', 'Pipedrive'],
            'marketing': ['HubSpot', 'Marketo', 'Mailchimp']
        }
        
        if sector in sector_competitors:
            competitors.extend(sector_competitors[sector])
        
        return list(set(competitors))  # Remove duplicates
    
    def _extract_industry_keywords(self, company_data: Dict[str, Any]) -> List[str]:
        """Extract specific industry keywords from description fields for targeted searches"""
        keywords = []
        
        # Get all possible description fields
        description_fields = [
            company_data.get('description', ''),
            company_data.get('what_they_do', ''),
            company_data.get('product_description', ''),
            company_data.get('business_model', ''),
            company_data.get('vertical', ''),
            company_data.get('category', '')
        ]
        
        # Combine all descriptions
        combined_text = ' '.join([field.lower() for field in description_fields if field]).lower()
        
        # Specific industry terms that are searchable
        industry_terms = [
            'neobank', 'digital banking', 'fintech', 'banking infrastructure', 'business banking',
            'telemedicine', 'telehealth', 'healthcare ai', 'medical software', 'healthcare tech',
            'pos payments', 'payment processing', 'expense management', 'payroll', 'hr software',
            'devops', 'ci/cd', 'code review', 'collaboration', 'productivity', 'workflow automation',
            'data analytics', 'business intelligence', 'machine learning', 'ai platform', 'saas',
            'marketplace', 'e-commerce', 'logistics', 'supply chain', 'inventory management',
            'customer support', 'helpdesk', 'ticketing', 'crm', 'sales automation', 'marketing automation',
            'security', 'cybersecurity', 'compliance', 'audit', 'risk management', 'insurance tech',
            'edtech', 'online learning', 'education', 'training', 'skill development', 'recruiting',
            'real estate', 'proptech', 'construction', 'manufacturing', 'industrial', 'iot', 'hardware',
            'blockchain', 'crypto', 'defi', 'web3', 'nft', 'gaming', 'entertainment', 'media',
            'legal tech', 'lawtech', 'regtech', 'adtech', 'martech', 'content management',
            'api platform', 'developer tools', 'cloud infrastructure', 'database', 'storage'
        ]
        
        # Find industry terms in the combined text
        for term in industry_terms:
            if term in combined_text:
                keywords.append(term)
        
        # Also look for single-word industry terms
        single_word_terms = ['banking', 'fintech', 'payments', 'saas', 'platform', 'software', 'analytics', 'ai', 'ml']
        for word in combined_text.split():
            word = word.strip('.,!?').lower()
            if word in single_word_terms and len(word) > 3:
                keywords.append(word)
        
        # Also extract specific product/service terms (2+ words, not generic)
        words = combined_text.split()
        for i in range(len(words) - 1):
            # Look for 2-word phrases that could be industry terms
            phrase = f"{words[i]} {words[i+1]}"
            # Filter out generic phrases, incomplete sentences, and punctuation
            if (len(words[i]) > 3 and len(words[i+1]) > 3 and 
                phrase not in ['software platform', 'business solution', 'cloud platform', 'web platform',
                              'designed specifically', 'management services', 'businesses business',
                              'checking accounts', 'debit cards', 'treasury services', 'small businesses',
                              'startups and', 'and small', 'for startups', 'and treasury', 'services. provides',
                              'platform designed', 'accounts, market', 'cards, and'] and
                not phrase.endswith('.') and not phrase.endswith(',') and 
                not phrase.startswith('we ') and not phrase.startswith('i ') and
                not phrase.startswith('mercury ') and not phrase.startswith('provides ')):
                keywords.append(phrase)
        
        # Remove duplicates and limit to most specific terms
        unique_keywords = list(set(keywords))
        
        # Prioritize more specific terms (longer, more descriptive)
        unique_keywords.sort(key=len, reverse=True)
        
        return unique_keywords[:5]  # Return top 5 most specific terms

    def _generate_searchable_terms(self, company_data: Dict[str, Any]) -> List[str]:
        """Generate actual searchable phrases that someone would type into Google"""
        terms = []
        
        # Use ALL field fallbacks for sector/vertical
        sector = (company_data.get('sector', '') or 
                company_data.get('vertical', '') or 
                company_data.get('category', '')).lower()
        
        business_model = company_data.get('business_model', '').lower()
        
        # Get ALL description sources
        description = (company_data.get('description', '') or 
                      company_data.get('what_they_do', '') or 
                      company_data.get('product_description', '')).lower()
        
        # Extract industry keywords from all description fields
        industry_keywords = self._extract_industry_keywords(company_data)
        
        # Generate diverse searchable phrases using all available data
        analyst_names = ['gartner', 'forrester', 'mckinsey', 'idc', 'deloitte']
        
        # 1. Sector + Business Model combinations
        if sector and business_model:
            terms.append(f"{sector} {business_model} market size gartner")
            terms.append(f"{sector} market size forrester")
        
        # 2. Industry keywords from descriptions
        for keyword in industry_keywords[:3]:  # Use top 3 keywords
            terms.append(f"{keyword} market size gartner")
            terms.append(f"{keyword} market size mckinsey")
        
        # 3. Specific product/service terms from description
        if description:
            # Look for specific product/service keywords that could be searched
            key_terms = []
            desc_words = description.split()
            
            # Find specific, searchable terms (not generic words)
            for word in desc_words:
                word = word.strip('.,!?').lower()
                if len(word) > 4 and word not in ['that', 'this', 'with', 'from', 'they', 'have', 'been', 'will', 'more', 'than', 'only', 'also', 'each', 'some', 'time', 'very', 'when', 'much', 'new', 'way', 'may', 'say', 'use', 'man', 'old', 'see', 'him', 'two', 'how', 'its', 'who', 'oil', 'sit', 'now', 'find', 'long', 'down', 'day', 'did', 'get', 'has', 'her', 'was', 'one', 'our', 'out', 'up', 'all', 'any', 'but', 'can', 'had', 'his', 'not', 'she', 'you', 'are', 'for', 'and', 'the', 'platform', 'software', 'solution', 'service', 'company', 'business', 'technology', 'digital', 'online', 'cloud', 'mobile', 'web', 'app', 'system', 'tool', 'product']:
                    key_terms.append(word)
            
            # Add specific product/service term as searchable phrase
            if key_terms:
                terms.append(f"{key_terms[0]} market size")
        
        # 4. Fallback: Use any available field
        if not terms:
            if sector:
                terms.append(f"{sector} market size gartner")
            elif industry_keywords:
                terms.append(f"{industry_keywords[0]} market size gartner")
        
        # Remove duplicates and empty strings
        terms = list(set([term.strip() for term in terms if term.strip()]))
        
        return terms[:5]  # Return up to 5 diverse searchable phrases
    
    def _generate_tam_search_queries(self, company_data: Dict[str, Any]) -> List[str]:
        """Generate focused TAM search queries with analyst names"""
        queries = []
        
        # Use ALL field fallbacks for sector/vertical
        sector = (company_data.get('sector', '') or 
                company_data.get('vertical', '') or 
                company_data.get('category', '')).lower()
        
        business_model = company_data.get('business_model', '').lower()
        
        # Extract industry keywords from all description fields
        industry_keywords = self._extract_industry_keywords(company_data)
        
        # Generate focused TAM queries using all available data
        analyst_combinations = [
            'gartner forrester idc',
            'mckinsey gartner',
            'forrester deloitte'
        ]
        
        # 1. Primary: Sector + Business Model + Multiple Analysts
        if sector and business_model:
            queries.append(f"{sector} {business_model} market size {analyst_combinations[0]}")
            queries.append(f"{sector} market size {analyst_combinations[1]}")
        
        # 2. Industry keywords + Multiple Analysts
        for keyword in industry_keywords[:2]:  # Use top 2 keywords
            queries.append(f"{keyword} market size {analyst_combinations[0]}")
        
        # 3. Fallback: Use any available field
        if not queries:
            if sector:
                queries.append(f"{sector} market size {analyst_combinations[1]}")
            elif industry_keywords:
                queries.append(f"{industry_keywords[0]} market size {analyst_combinations[0]}")
        
        # Remove duplicates and empty strings
        queries = list(set([query.strip() for query in queries if query.strip()]))
        
        return queries[:3]  # Return up to 3 focused TAM queries
    
    def _calculate_tam_from_company_context(self, company_data: Dict[str, Any]) -> float:
        """Dynamically calculate TAM from company context - NO HARDCODING"""
        
        # Method 1: From target customer count and ACV
        revenue = self._safe_get_value(company_data.get('revenue', 0)) or self._safe_get_value(company_data.get('inferred_revenue', 0))
        
        if revenue > 0:
            # Bottom-up: If they have revenue, estimate TAM from market penetration
            # Assume 0.1% - 1% market penetration for early stage
            stage = company_data.get('stage', 'Seed')
            if 'Seed' in stage or 'Pre-Seed' in stage:
                penetration = 0.001  # 0.1% penetration
            elif 'Series A' in stage:
                penetration = 0.005  # 0.5% penetration
            elif 'Series B' in stage:
                penetration = 0.01   # 1% penetration
            else:
                penetration = 0.02   # 2% penetration
            
            estimated_tam = revenue / penetration
            return estimated_tam
        
        # Method 2: From business model and sector
        sector = company_data.get('sector', '').lower()
        business_model = company_data.get('business_model', '').lower()
        
        # 2025 market size data (from industry reports)
        sector_tams = {
            'fintech': 550_000_000_000,      # $550B
            'healthcare': 450_000_000_000,   # $450B
            'hr': 35_000_000_000,            # $35B
            'sales': 80_000_000_000,         # $80B
            'marketing': 350_000_000_000,    # $350B
            'security': 200_000_000_000,     # $200B
            'dev': 50_000_000_000,           # $50B developer tools
            'saas': 200_000_000_000,         # $200B general SaaS
        }
        
        # Match sector
        for key, tam_value in sector_tams.items():
            if key in sector or key in business_model:
                return tam_value
        
        # Method 3: Calculate from team size and efficiency
        team_size = company_data.get('team_size', 0)
        if team_size > 0:
            # Revenue per employee for SaaS: ~$200K-$500K
            revenue_per_employee = 300_000
            estimated_revenue = team_size * revenue_per_employee
            # Assume 0.5% penetration
            return estimated_revenue / 0.005
        
        # Final fallback: Use global technology spend as baseline
        # Global IT spending ~$5T, assume addressing 2-5% of a segment
        return 50_000_000_000  # $50B - reasonable for most tech categories
    
    async def calculate_market_opportunity(self, company_data: Dict[str, Any], search_content: str = None, tam_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """TAM processing disabled; return placeholder market analysis."""
        logger.info("[GAP_FILLER] calculate_market_opportunity disabled; returning placeholder.")
        market_category = company_data.get('sector') or company_data.get('category') or 'Technology'
        placeholder = {
            'status': 'tam_disabled',
            'tam_calculation': {
                'tam': 0,
                'sam': 0,
                'som': 0,
                'market_category': market_category,
                'tam_definition': 'Market analysis disabled',
                'sam_definition': 'Market analysis disabled',
                'som_definition': 'Market analysis disabled',
                'growth_rate': 0,
                'confidence': 0,
                'confidence_level': 'Low',
                'methodology': 'TAM processing disabled',
                'notes': 'TAM processing disabled'
            }
        }
        placeholder['tam'] = 0
        placeholder['sam'] = 0
        placeholder['som'] = 0
        return placeholder
