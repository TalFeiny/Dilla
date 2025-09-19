"""
Intelligent Gap Filler for MCP
Wires together existing funding cadence, liquidation waterfall, and benchmark systems
to intelligently infer missing data and score companies for fund fit
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
from datetime import datetime, timedelta

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
    
    # Stage-based benchmarks from Carta/SVB Benchmark (1).pdf data
    # These are ACTUAL median values from Carta State of Private Markets Q3 2024 + SVB reports
    STAGE_BENCHMARKS = {
        "Pre-seed": {
            "revenue_range": (0, 150_000),
            "arr_median": 50_000,  # $50K median ARR
            "growth_rate": 0.0,  # Pre-revenue/early
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
        
        # Sort rounds by date
        sorted_rounds = sorted(funding_rounds, key=lambda x: x.get("date", ""))
        
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
                months_of_burn = self._months_between_rounds(
                    prev_round.get("date"),
                    last_round.get("date")
                ) - 6
                
                if months_of_burn > 0:
                    estimated_burn = prev_round.get("amount", 0) / months_of_burn
                    
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
                        reasoning=f"{months_since} months since {last_round['round']} of ${last_round.get('amount', 0)/1e6:.1f}M",
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
        if "valuation" in missing_fields and sorted_rounds:
            last_round = sorted_rounds[-1]
            
            # Standard dilution assumptions by round
            dilution_map = {
                "Seed": 0.15,
                "Series A": 0.20,
                "Series B": 0.15,
                "Series C": 0.12,
                "Series D": 0.10
            }
            
            dilution = dilution_map.get(last_round.get("round", ""), 0.15)
            implied_post = last_round.get("amount", 0) / dilution
            
            # Apply geography adjustment only (keep this as it's based on real market data)
            geography = company_data.get("geography", "US")
            geo_mult = self.GEOGRAPHY_ADJUSTMENTS.get(geography, {}).get("valuation", 1.0)
            
            # NEW: Apply gross margin adjustment for API-dependent companies
            gross_margin_analysis = self.calculate_adjusted_gross_margin(company_data)
            api_valuation_adjustment = gross_margin_analysis["valuation_multiple_adjustment"]
            
            adjusted_valuation = implied_post * geo_mult * api_valuation_adjustment
            
            inferences["valuation"] = InferenceResult(
                field="valuation",
                value=adjusted_valuation,
                confidence=0.5,
                source="funding_cadence",
                reasoning=f"{last_round['round']} of ${last_round.get('amount', 0)/1e6:.1f}M implies {dilution:.0%} dilution, adjusted for API dependency",
                citations=[
                    f"Standard {last_round['round']} dilution: {dilution:.0%}",
                    f"Geography: {geography} (adjustment: {geo_mult:.1f}x)",
                    f"API dependency: {gross_margin_analysis['api_dependency_level']} (adjustment: {api_valuation_adjustment:.1f}x)",
                    f"Adjusted gross margin: {gross_margin_analysis['adjusted_gross_margin']:.0%}"
                ]
            )
        
        return inferences
    
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
            return inferences
        
        benchmarks = self.STAGE_BENCHMARKS.get(stage, {})
        
        # Infer revenue if missing
        if "revenue" in missing_fields:
            rev_range = benchmarks.get("revenue_range", (0, 0))
            
            # Start with benchmark midpoint
            benchmark_revenue = (rev_range[0] + rev_range[1]) / 2
            
            # Layer 1: Team size adjustment
            team_adjusted_revenue = benchmark_revenue
            team_ratio = 1.0
            if "team_size" in company_data:
                team = company_data["team_size"]
                expected_team = benchmarks.get("team_size", (10, 50))
                team_midpoint = (expected_team[0] + expected_team[1]) / 2
                team_ratio = team / team_midpoint if team_midpoint > 0 else 1
                team_adjusted_revenue *= team_ratio
            
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
                                      if any(signal in str(customer).lower() for signal in enterprise_signals))
                
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
            if team_ratio != 1:
                reasoning_parts.append(f"Team size adjustment: {team_ratio:.1f}x")
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
                citations=[f"Industry benchmark for {stage} stage", "Pricing page analysis", "Customer logo analysis"]
            )
        
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
            
        scores = {}
        reasons = []
        recommendations = []
        
        # CRITICAL: Extract fund parameters for calculations
        fund_size = context.get('fund_size', 200_000_000)  # Default $200M
        fund_year = context.get('fund_year', 2)
        portfolio_count = context.get('portfolio_count', 5)
        is_lead = context.get('lead_investor', False) or context.get('is_lead', False)
        
        # Log fund parameters for debugging
        import logging
        logger = logging.getLogger(__name__)
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
        target_deployed = fund_size * target_deployment_pct
        
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
            
            actual_deployed = fund_size * typical_deployment_rate
            avg_check_size = actual_deployed / portfolio_count if portfolio_count > 0 else fund_size * 0.03
        
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
            
            # Model fund-level impact
            # Power law: Need 1-2 deals to return fund
            fund_return_needed = fund_size * 3  # 3x target return
            can_return_fund = (selected_ownership * valuation * 25) >= fund_return_needed
            
            # Portfolio construction impact
            if portfolio_count < 10:
                # Early in fund, need potential fund-returners
                if can_return_fund:
                    scores["portfolio_fit"] = 100
                    reasons.append(f"🎯 FUND-RETURNER: Could return {(selected_ownership * valuation * 25)/fund_size:.1f}x the fund")
                else:
                    scores["portfolio_fit"] = 60
                    reasons.append(f"📊 Solid addition but not a fund-returner")
            else:
                # Later in fund, can take more measured bets
                scores["portfolio_fit"] = 80
            
            recommendations.append(f"📊 Expected return: {expected_return:.1f}x across scenarios")
            recommendations.append(f"💰 Check: ${selected_check/1e6:.1f}M | Ownership: {selected_ownership:.1%} | E[Return]: {expected_return:.1f}x")
            
            # Deployment pacing check
            if fund_year >= 3 and portfolio_count < 10:
                scores["deployment_urgency"] = 90
                reasons.append(f"⚡ DEPLOYMENT PRESSURE: Year {fund_year} with only {portfolio_count} deals")
        else:
            scores["fund_economics"] = 0
            reasons.append("⚠️ Cannot evaluate - no valuation data")
        
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
        
        # 6. Return Potential (0-100)
        valuation = all_data.get("valuation", 100_000_000)
        growth_rate = all_data.get("growth_rate", 0.5)
        
        # Simple exit multiple calculation
        years_to_exit = self.fund.typical_holding_period / 12
        projected_revenue = all_data.get("revenue", 1_000_000) * ((1 + growth_rate) ** years_to_exit)
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
        
        # 6. Geography Fit (0-100)
        geography = all_data.get("geography", "Unknown")
        if geography in self.fund.geography_focus:
            scores["geography_fit"] = 100
            reasons.append(f"✅ Geography match: {geography}")
        else:
            scores["geography_fit"] = 50
            reasons.append(f"🔶 Geography outside focus: {geography}")
        
        # Calculate overall score (weighted average) - UPDATED with unit economics
        # Fund economics is THE MOST IMPORTANT - if deal doesn't work, nothing else matters
        weights = {
            "fund_economics": 0.40,  # PRIMARY: Can we get ownership? Does math work?
            "stage_fit": 0.10,
            "sector_fit": 0.10,
            "unit_economics": 0.15,
            "check_size_fit": 0.05,  # Already covered in fund_economics
            "timing_fit": 0.10,
            "return_potential": 0.05,  # Already covered in fund_economics
            "geography_fit": 0.05
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
        
        return {
            "overall_score": overall_score,
            "component_scores": scores,
            "recommendation": recommendation,
            "action": action,
            "reasons": reasons,
            "specific_recommendations": recommendations,
            "confidence": self._calculate_confidence(inferred_data)
        }
    
    def _determine_stage(self, company_data: Dict[str, Any]) -> Optional[str]:
        """Determine company stage from available data"""
        
        # Check explicit stage
        if "stage" in company_data:
            return company_data["stage"]
        
        # Infer from last round
        if "funding_rounds" in company_data and company_data["funding_rounds"]:
            last_round = sorted(company_data["funding_rounds"], key=lambda x: x.get("date", ""))[-1]
            return last_round.get("round", "Unknown")
        
        # Infer from revenue
        revenue = company_data.get("revenue", 0)
        for stage, benchmarks in self.STAGE_BENCHMARKS.items():
            rev_range = benchmarks.get("revenue_range", (0, 0))
            if rev_range[0] <= revenue <= rev_range[1]:
                return stage
        
        return None
    
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
                if 'T' in date_str:
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
                return None
            
            # Parse date using same logic
            def parse_date(date_str):
                if 'T' in date_str:
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
    
    def _calculate_confidence(self, inferred_data: Dict[str, InferenceResult]) -> float:
        """Calculate overall confidence in the analysis"""
        if not inferred_data:
            return 1.0  # All data was available
        
        confidences = [inf.confidence for inf in inferred_data.values()]
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
    
    def calculate_adjusted_gross_margin(
        self,
        company_data: Dict[str, Any],
        base_gross_margin: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate gross margin adjusted for API dependency
        This affects valuation multiples significantly
        """
        # Detect API dependency level
        dependency_level = self.detect_api_dependency(company_data)
        dependency_impact = self.API_DEPENDENCY_IMPACT[dependency_level]
        
        # Get base gross margin from benchmarks or data
        if base_gross_margin is None:
            stage = self._determine_stage(company_data)
            if stage and stage in self.STAGE_BENCHMARKS:
                base_gross_margin = self.STAGE_BENCHMARKS[stage].get("gross_margin", 0.75)
            else:
                base_gross_margin = 0.75  # Default SaaS gross margin
        
        # Calculate adjusted gross margin
        adjusted_gross_margin = base_gross_margin - dependency_impact["gross_margin_penalty"]
        
        # Calculate API costs impact on unit economics
        revenue_raw = company_data.get("revenue", company_data.get("arr", 1_000_000))
        # Handle case where revenue might be a dict or InferenceResult
        if isinstance(revenue_raw, dict):
            revenue = revenue_raw.get('value', 1_000_000) if 'value' in revenue_raw else 1_000_000
        elif hasattr(revenue_raw, 'value'):
            revenue = revenue_raw.value
        else:
            revenue = revenue_raw or 1_000_000
            
        # Smart customer contract estimation based on tiers
        customers_raw = company_data.get("customers", {})
        
        # Calculate weighted average contract value and effective customer count
        if isinstance(customers_raw, dict):
            # Extract customer tiers
            enterprise_customers = customers_raw.get('enterprise_customers', [])
            customer_names = customers_raw.get('customer_names', [])
            total_customers = self._ensure_numeric(customers_raw.get('customer_count', len(customer_names)))
            
            # Determine company stage for ACV estimation
            stage = company_data.get('stage', 'seed').lower()
            
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
                if revenue > 10_000_000:
                    num_enterprise = 20
                    num_mid = 50
                    num_smb = 100
                elif revenue > 1_000_000:
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
            if revenue > estimated_revenue * 0.5 and revenue < estimated_revenue * 2:
                # Actual revenue seems reasonable
                final_revenue = revenue
            else:
                # Our estimate might be better
                final_revenue = max(revenue, estimated_revenue)
                logger.info(f"Using estimated revenue ${final_revenue:,.0f} based on customer tiers")
            
            customers = api_adjusted_customers if api_adjusted_customers > 0 else total_customers
            
        elif hasattr(customers_raw, 'value'):
            customers = self._ensure_numeric(customers_raw.value)
        else:
            # Fallback to simple customer count
            customers = self._ensure_numeric(customers_raw) if customers_raw else revenue / 12_000
        
        # Ensure customers is a valid number
        if not isinstance(customers, (int, float)) or customers <= 0:
            customers = max(10, revenue / 12_000)
        
        api_cost_per_user = dependency_impact["typical_api_cost_per_user"]
        monthly_api_costs = api_cost_per_user * customers
        annual_api_costs = monthly_api_costs * 12
        
        # Calculate valuation impact
        # Companies with heavy API dependencies get lower multiples
        valuation_multiple_adjustment = 1.0
        if dependency_level == "openai_heavy":
            valuation_multiple_adjustment = 0.6  # 40% discount on valuation multiple
        elif dependency_level == "openai_moderate":
            valuation_multiple_adjustment = 0.8  # 20% discount
        elif dependency_level == "openai_light":
            valuation_multiple_adjustment = 0.95  # 5% discount
        else:  # own_models
            valuation_multiple_adjustment = 1.1  # 10% premium for own IP
        
        return {
            "base_gross_margin": base_gross_margin,
            "adjusted_gross_margin": adjusted_gross_margin,
            "api_dependency_level": dependency_level,
            "gross_margin_penalty": dependency_impact["gross_margin_penalty"],
            "estimated_annual_api_costs": annual_api_costs,
            "api_cost_per_user": api_cost_per_user,
            "valuation_multiple_adjustment": valuation_multiple_adjustment,
            "scalability_discount": dependency_impact["scalability_discount"],
            "investment_recommendation": self._get_api_dependency_recommendation(dependency_level),
            "risk_factors": self._get_api_dependency_risks(dependency_level)
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
                description = round_data.get("description", "")
                announcement = round_data.get("announcement", "")
                
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
        current_revenue = company_data.get("revenue", company_data.get("arr", 1_000_000))
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
        is_ai_company = any(keyword in company_data.get("description", "").lower() 
                           for keyword in ["ai", "ml", "gpt", "llm", "model"])
        has_strategic_value = exit_revenue > 50_000_000 and final_growth > 0.30
        
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
                "recommendation": self._get_investment_recommendation(valuation_gap, current_ask_valuation)
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
            investors = round_data.get("investors", [])
            for investor in investors:
                if any(strategic in investor.lower() for strategic in strategic_keywords):
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
    
    def _get_investment_recommendation(self, gap, ask):
        """Get investment recommendation based on valuation gap"""
        if gap < -ask * 0.20:  # 20%+ discount
            return "🟢 STRONG BUY - Significantly undervalued"
        elif gap < 0:
            return "🟢 BUY - Fairly priced for target returns"
        elif gap < ask * 0.20:  # Up to 20% premium
            return "🟡 NEGOTIATE - Close to fair value, push for lower"
        elif gap < ask * 0.50:
            return "🟡 PASS - Overvalued, wait for reality check"
        else:
            return "🔴 HARD PASS - Severely overvalued"
    
    def calculate_required_growth_rates(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate required growth rates to justify valuation multiples
        Both forward (next 12 months) and backward (last 12 months) looking
        """
        current_revenue = company_data.get("revenue", company_data.get("arr", 1_000_000))
        valuation = company_data.get("valuation", 100_000_000)
        nrr = company_data.get("nrr", company_data.get("net_retention", 1.10))  # Default 110%
        
        # Current revenue multiple
        current_multiple = valuation / current_revenue if current_revenue > 0 else 0
        
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
        industry = company_data.get("industry", "").lower()
        description = company_data.get("description", "").lower()
        
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
            
            # Query companies with revenue and valuation data
            result = await supabase_service.client.table('companies').select(
                'name', 'revenue', 'valuation', 'growth_rate', 'stage', 
                'last_round_date', 'funding_rounds', 'sector'
            ).not_('revenue', 'is', None).not_('valuation', 'is', None).execute()
            
            if not result.data:
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
                    revenue = company.get('revenue', 0)
                    valuation = company.get('valuation', 0)
                    growth = company.get('growth_rate')
                    
                    if revenue <= 0:
                        continue
                    
                    # Trailing revenue multiple (valuation / current revenue)
                    trailing_multiple = valuation / revenue
                    
                    # Forward revenue multiple (valuation / next year revenue)
                    if growth is not None:
                        forward_revenue = revenue * (1 + growth)
                        forward_multiple = valuation / forward_revenue if forward_revenue > 0 else trailing_multiple
                    else:
                        # Infer growth from investor quality if not available
                        inferred_growth = self._infer_growth_from_investors(company.get('funding_rounds', []))
                        forward_revenue = revenue * (1 + inferred_growth)
                        forward_multiple = valuation / forward_revenue if forward_revenue > 0 else trailing_multiple
                        growth = inferred_growth
                    
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
                        'avg_rule_of_40': sum(m['rule_of_40'] for m in stage_multiples) / len(stage_multiples)
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
    
    def _infer_growth_from_investors(self, funding_rounds: List[Dict]) -> float:
        """
        Infer growth rate from investor prestige
        Top tier VCs only invest in high growth companies
        """
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
        
        # Return implied growth rate based on investor quality
        if has_tier1:
            return 1.5  # 150% YoY - Only hypergrowth gets Tier 1
        elif has_tier2:
            return 1.0  # 100% YoY - Strong growth for Tier 2
        elif has_tier3:
            return 0.7  # 70% YoY - Good growth for Tier 3
        else:
            return 0.4  # 40% YoY - Below tier funds = slower growth
    
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
    
    def calculate_ai_adjusted_valuation(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate valuation with AI impact adjustments
        """
        # Get base market multiples
        market_multiples = self.get_market_multiples_from_database()
        
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
        name = company_data.get('name', '').lower()
        description = company_data.get('description', '').lower()
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
        has_red_flags = sum(1 for flag in agent_washing_red_flags if flag in description.lower())
        has_green_flags = sum(1 for flag in agent_washing_green_flags if flag in description.lower())
        
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
        if any(term in description.lower() for term in ['llm', 'large language model', 'foundation model']):
            ai_score += 2
        
        # 2. Technical depth (0-3 points)
        tech_matches = sum(1 for term in ai_tech_depth if term in description.lower())
        ai_score += min(3, tech_matches)
        
        # 3. AI-native business model (0-2 points)
        if any(signal in description.lower() for signal in ai_revenue_signals):
            ai_score += 1
        if any(signal in description.lower() for signal in ai_customer_signals):
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
        
        is_cost_center = any(industry in description.lower() for industry in cost_center_industries)
        
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
                all_text += result.get('content', '') + " "
        
        if website_data:
            if 'raw_content' in website_data:
                all_text += str(website_data.get('raw_content', ''))
        
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
        
        salaries = base_salaries.get(region.lower(), base_salaries['us'])
        
        # Calculate salary burn
        annual_salaries = (
            team_structure.get('founders', 0) * salaries['founder'] +
            team_structure.get('senior', 0) * salaries['senior'] +
            team_structure.get('mid', 0) * salaries['mid'] +
            team_structure.get('junior', 0) * salaries['junior']
        )
        
        # Add employer burden (taxes, benefits, equity)
        burden_rate = {'us': 1.35, 'uk': 1.14, 'europe': 1.45, 'asia': 1.2}.get(region.lower(), 1.3)
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
        }.get(stage.lower().replace(' ', '_'), 0.25)
        
        # OTHER COSTS
        # Legal & Accounting
        legal_monthly = 5000 if stage.lower() in ['seed', 'pre_seed', 'pre-seed'] else 15000
        
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
        sm_as_percent_revenue = (total_sm_spend / revenue * 100) if revenue > 0 else 0
        
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