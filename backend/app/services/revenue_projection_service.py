"""
Unified Revenue Projection Service

This service provides a single, consistent implementation for revenue projections
with growth decay, used across gap_filler and valuation_engine services.

The implementation uses a quality-adjusted decay model where:
- Higher quality companies (quality_score > 1.0) have slower growth decay
- Growth rates naturally decelerate over time following realistic patterns
- Supports both single-value returns and year-by-year projections
"""

from typing import List, Dict, Any, Union, Optional
import logging

logger = logging.getLogger(__name__)


class RevenueProjectionService:
    """
    Unified service for revenue projections with growth decay.
    
    This service standardizes revenue projection logic across the codebase,
    ensuring consistent calculations in gap_filler and valuation_engine.
    """
    
    @staticmethod
    def _get_investor_quality_tier(investors: List[str]) -> Optional[str]:
        """
        Determine investor quality tier from investor list.
        Returns "tier1", "tier2", or "tier3" based on presence of top-tier firms.
        Defaults to "tier2" when no investors found.
        """
        if not investors:
            return "tier2"  # Default to tier2 instead of None when no investors found
        
        investors_str = " ".join(str(inv).lower() for inv in investors)
        
        # Tier 1: Top-tier VCs (a16z, Sequoia, Benchmark, Accel, etc.)
        tier1_firms = [
            'andreessen horowitz', 'a16z', 'sequoia', 'benchmark', 'accel',
            'kleiner perkins', 'kp', 'greylock', 'lightspeed', 'insight partners',
            'battery ventures', 'general catalyst', 'index ventures', 'new enterprise',
            'first round', 'founders fund', 'y combinator', 'yc'
        ]
        
        # Check for tier 1
        for firm in tier1_firms:
            if firm in investors_str:
                return "tier1"
        
        # Tier 2: Well-known VCs but not top-tier
        tier2_firms = [
            'redpoint', 'menlo ventures', 'sierra ventures', 'mayfield',
            'crosslink', 'venrock', 'union square', 'spark capital'
        ]
        
        for firm in tier2_firms:
            if firm in investors_str:
                return "tier2"
        
        # Tier 3: Default for unknown/other investors
        return "tier3"
    
    @staticmethod
    def _get_geography_from_location(location: str) -> Optional[str]:
        """
        Extract geography from headquarters location.
        Returns "US", "Europe", or "Asia" based on location string.
        """
        if not location:
            return None
        
        location_lower = location.lower()
        
        # US cities/regions
        us_indicators = [
            'san francisco', 'sf', 'silicon valley', 'palo alto', 'menlo park',
            'new york', 'nyc', 'brooklyn', 'manhattan', 'boston', 'cambridge',
            'seattle', 'austin', 'los angeles', 'la', 'chicago', 'atlanta',
            'denver', 'miami', 'philadelphia', 'united states', 'usa', 'california'
        ]
        
        # European cities
        europe_indicators = [
            'london', 'berlin', 'paris', 'amsterdam', 'dublin', 'stockholm',
            'copenhagen', 'zurich', 'munich', 'frankfurt', 'barcelona', 'madrid',
            'lisbon', 'vienna', 'warsaw', 'europe', 'uk', 'united kingdom'
        ]
        
        # Asian cities
        asia_indicators = [
            'singapore', 'bangalore', 'mumbai', 'delhi', 'tokyo', 'seoul',
            'hong kong', 'beijing', 'shanghai', 'shenzhen', 'taipei', 'asia'
        ]
        
        for indicator in us_indicators:
            if indicator in location_lower:
                return "US"
        
        for indicator in europe_indicators:
            if indicator in location_lower:
                return "Europe"
        
        for indicator in asia_indicators:
            if indicator in location_lower:
                return "Asia"
        
        return None
    
    @staticmethod
    def _get_sector_from_industry(industry: Optional[str], description: Optional[str] = None) -> Optional[str]:
        """
        Classify sector from industry or description.
        Returns "SaaS", "Marketplace", "Hardware", etc.
        """
        text = ""
        if industry:
            text += " " + str(industry).lower()
        if description:
            text += " " + str(description).lower()
        
        if not text:
            return None
        
        # SaaS indicators
        if any(term in text for term in ['saas', 'software as a service', 'subscription', 'api', 'platform']):
            return "SaaS"
        
        # Marketplace indicators
        if any(term in text for term in ['marketplace', 'two-sided', 'marketplace', 'e-commerce', 'ecommerce']):
            return "Marketplace"
        
        # Hardware indicators
        if any(term in text for term in ['hardware', 'iot', 'device', 'physical product', 'manufacturing']):
            return "Hardware"
        
        return None
    
    @staticmethod
    def _calculate_company_age(founded_year: Optional[int]) -> Optional[int]:
        """
        Calculate company age in years from founded year.
        """
        if not founded_year:
            return None
        
        from datetime import datetime
        current_year = datetime.now().year
        age = current_year - founded_year
        return max(0, age)
    
    @staticmethod
    def project_revenue_with_decay(
        base_revenue: float,
        initial_growth: float,
        years: int,
        quality_score: float = 1.0,
        stage: Optional[str] = None,
        market_conditions: Optional[str] = None,  # "bull", "bear", "neutral"
        return_projections: bool = False,
        # Business model decay modifiers (all active)
        investor_quality: Optional[str] = None,    # "tier1", "tier2", "tier3" — affects decay rate
        geography: Optional[str] = None,            # "US", "Europe", "Asia" — US = slower decay
        sector: Optional[str] = None,               # "ai_first", "vertical_saas", "services", etc.
        company_age_years: Optional[int] = None,    # >5yr adds incremental decay penalty
        market_size_tam: Optional[float] = None,    # TAM ceiling — faster decay near saturation
        competitive_position: Optional[str] = None  # reserved for future use
    ) -> Union[float, List[Dict[str, Any]]]:
        """
        Project revenue forward with realistic growth decay, adjusted for company quality.
        
        This method uses the initial inferred growth rate and applies decay over time.
        It is separate from PWERM validation to avoid ridiculous revenue multiples.
        
        Decay model:
        - Hyper-growth companies (>100% YoY) decay at 30% per year (base_decay_rate = 0.7)
        - High-growth companies (50-100% YoY) decay at 20% per year (base_decay_rate = 0.8)
        - Normal growth companies (<50% YoY) decay at 10% per year (base_decay_rate = 0.9)
        
        Quality adjustment: Better companies (quality_score > 1.0) have slower decay.
        Formula: quality_adjusted_decay = 1.0 - (1.0 - base_decay_rate) / quality_score
        
        Args:
            base_revenue: Starting revenue
            initial_growth: Initial growth rate in decimal format (e.g., 0.3 for 30%, 1.0 for 100%, 2.0 for 200%)
            years: Number of years to project
            quality_score: Company quality multiplier (1.0 = baseline, >1.0 = better quality = slower decay)
            stage: Company stage (affects decay rate - early stage = slower decay)
            market_conditions: "bull", "bear", or "neutral" (affects decay rate)
            return_projections: If True, returns list of year-by-year projections instead of final value
            investor_quality: Investor quality tier — "tier1" (0.90x decay), "tier2" (1.0x), "tier3" (1.10x)
            geography: Geography — "US" (0.95x decay), "Europe" (1.0x), "Asia" (1.02x)
            sector: Business model — "ai_first" (1.15x), "vertical_saas" (0.85x), "services" (1.20x), etc.
            company_age_years: Company age — >5yr adds incremental decay penalty (capped at 20%)
            market_size_tam: TAM ceiling — faster decay as SOM approaches TAM
            competitive_position: Reserved for future use
        
        Returns:
            If return_projections=False: final revenue after years
            If return_projections=True: List[Dict] with [{year: 1, revenue: X, growth_rate: Y}, ...]
        
        Note: This method is separate from PWERM and should be validated independently
        to ensure revenue multiples remain reasonable.
        """
        if base_revenue <= 0:
            logger.warning(f"Invalid base_revenue: {base_revenue}, returning 0")
            if return_projections:
                return [{'year': y, 'revenue': 0.0, 'growth_rate': 0.0} for y in range(1, years + 1)]
            return 0.0
        
        if years <= 0:
            logger.warning(f"Invalid years: {years}, returning base_revenue")
            if return_projections:
                return [{'year': 1, 'revenue': base_revenue, 'growth_rate': initial_growth}]
            return base_revenue
        
        if quality_score <= 0:
            logger.warning(f"Invalid quality_score: {quality_score}, using 1.0")
            quality_score = 1.0
        
        current_revenue = base_revenue
        previous_growth = initial_growth
        projections = []
        
        for year in range(1, years + 1):
            # Determine base decay rate based on initial growth rate
            # Higher initial growth = more aggressive decay (lower decay_rate)
            # Note: initial_growth should be in decimal format (0.5 = 50% growth)
            # But we check for multiplier format for backwards compatibility
            # FIX: Check decay category BEFORE normalization to avoid misclassification
            # Determine growth category based on original format
            if initial_growth > 10:
                # Percentage format: 50 = 50%, 150 = 150%
                growth_decimal = initial_growth / 100.0
                if initial_growth > 100:  # Hyper-growth (>100% in percentage format)
                    base_decay_rate = 0.7  # 30% decay per year
                elif initial_growth > 50:  # High growth (50-100% in percentage format)
                    base_decay_rate = 0.8  # 20% decay per year
                else:  # Normal growth (<50% in percentage format)
                    base_decay_rate = 0.9  # 10% decay per year
                growth_for_decay = growth_decimal
            elif initial_growth > 1.0:
                # Multiplier format: 1.5 = 150% total = 50% YoY, 2.0 = 200% total = 100% YoY
                if initial_growth > 2.0:  # Hyper-growth (>200% total = >100% YoY in multiplier format)
                    base_decay_rate = 0.7  # 30% decay per year
                elif initial_growth >= 1.5:  # High growth (>=150% total = >=50% YoY in multiplier format)
                    base_decay_rate = 0.8  # 20% decay per year
                else:  # Normal growth (100-150% total = 0-50% YoY in multiplier format)
                    base_decay_rate = 0.9  # 10% decay per year
                growth_for_decay = initial_growth - 1.0  # Convert to decimal for calculation
            else:
                # Already in decimal format: 0.5 = 50%, 1.0 = 100%
                growth_for_decay = initial_growth
                if initial_growth > 1.0:  # Hyper-growth (>100% in decimal format)
                    base_decay_rate = 0.7  # 30% decay per year
                elif initial_growth > 0.5:  # High growth (50-100% in decimal format)
                    base_decay_rate = 0.8  # 20% decay per year
                else:  # Normal growth (<50% in decimal format)
                    base_decay_rate = 0.9  # 10% decay per year
            
            # Stage-based decay adjustments (early stage = slower decay, late stage = faster decay)
            stage_decay_multiplier = 1.0
            if stage:
                stage_lower = stage.lower().replace(' ', '_').replace('-', '_')
                if stage_lower in ['pre_seed', 'seed', 'series_a']:
                    stage_decay_multiplier = 0.95  # Slower decay (5% less) for early stage
                elif stage_lower in ['series_b']:
                    stage_decay_multiplier = 1.0  # Baseline
                elif stage_lower in ['series_c', 'series_d', 'series_e', 'growth', 'late_stage']:
                    stage_decay_multiplier = 1.1  # Faster decay (10% more) for late stage
            
            # Market Conditions: Bull = 0.95x, Neutral = 1.0x, Bear = 1.1x
            market_conditions_multiplier = 1.0
            if market_conditions:
                market_lower = market_conditions.lower()
                if 'bull' in market_lower:
                    market_conditions_multiplier = 0.95  # Slower decay in bull market
                elif 'bear' in market_lower:
                    market_conditions_multiplier = 1.1  # Faster decay in bear market
                else:
                    market_conditions_multiplier = 1.0  # Neutral baseline
            
            # Business model / sector decay modifier
            # ai_first decays 15% faster (competition), vertical_saas 15% slower (moat),
            # services 20% faster (linear scaling)
            sector_decay_multiplier = 1.0
            if sector:
                sector_lower = sector.lower().replace(' ', '_').replace('-', '_')
                _BM_DECAY = {
                    'ai_first': 1.15,       # 15% faster decay (intense competition)
                    'ai': 1.15,
                    'vertical_saas': 0.85,  # 15% slower decay (deep moat)
                    'vertical': 0.85,
                    'saas': 1.0,            # baseline
                    'horizontal_saas': 1.05, # 5% faster (more competition)
                    'horizontal': 1.05,
                    'services': 1.20,       # 20% faster (linear scaling)
                    'marketplace': 0.90,    # 10% slower (network effects)
                    'hardware': 1.10,       # 10% faster (capital intensive)
                    'fintech': 0.95,        # 5% slower (regulatory moat)
                    'rollup': 1.10,         # 10% faster (integration drag)
                }
                sector_decay_multiplier = _BM_DECAY.get(sector_lower, 1.0)

            # Investor quality: tier1 = 10% slower decay, tier3 = 10% faster
            investor_decay_multiplier = 1.0
            if investor_quality:
                iq_lower = investor_quality.lower()
                if iq_lower == 'tier1':
                    investor_decay_multiplier = 0.90
                elif iq_lower == 'tier3':
                    investor_decay_multiplier = 1.10

            # Geography: US = 5% slower decay (more runway access)
            geography_decay_multiplier = 1.0
            if geography:
                geo_lower = geography.lower()
                if geo_lower == 'us':
                    geography_decay_multiplier = 0.95
                elif geo_lower == 'asia':
                    geography_decay_multiplier = 1.02

            # Company age: >5yr = incremental decay penalty (2%/yr, capped 20%)
            age_decay_multiplier = 1.0
            if company_age_years and company_age_years > 5:
                age_decay_multiplier = 1.0 + min(0.20, (company_age_years - 5) * 0.02)

            # TAM ceiling: growth decays faster as revenue approaches TAM
            tam_decay_multiplier = 1.0
            if market_size_tam and market_size_tam > 0 and current_revenue > 0:
                penetration = current_revenue / market_size_tam
                if penetration > 0.10:
                    tam_decay_multiplier = 1.15
                elif penetration > 0.05:
                    tam_decay_multiplier = 1.08
                elif penetration > 0.01:
                    tam_decay_multiplier = 1.03

            # Calculate total decay multiplier from all factors
            total_decay_multiplier = (
                stage_decay_multiplier
                * market_conditions_multiplier
                * sector_decay_multiplier
                * investor_decay_multiplier
                * geography_decay_multiplier
                * age_decay_multiplier
                * tam_decay_multiplier
            )
            
            # FIX: Apply multipliers to base_decay_rate first, then apply quality adjustment
            # This ensures multipliers affect the base rate before quality score adjustment
            # Apply multipliers to base decay rate first
            adjusted_base_decay = base_decay_rate * total_decay_multiplier
            # Clamp to valid range before quality adjustment
            adjusted_base_decay = max(0.1, min(0.99, adjusted_base_decay))
            
            # Then apply quality score adjustment
            # Better companies (quality_score > 1.0) have slower decay
            # Formula: decay_rate = 1.0 - (1.0 - adjusted_base_decay) / quality_score
            # This means:
            # - quality_score = 1.0: decay_rate = adjusted_base_decay (baseline)
            # - quality_score = 2.0: decay_rate closer to 1.0 (slower decay)
            # - quality_score = 0.5: decay_rate further from 1.0 (faster decay)
            decay_rate = 1.0 - (1.0 - adjusted_base_decay) / quality_score
            decay_rate = max(0.5, min(0.95, decay_rate))  # Final clamp
            
            # Calculate this year's growth rate (decaying from previous year)
            if year == 1:
                year_growth = initial_growth
            else:
                # Each year's growth is a decay from the previous year's growth
                year_growth = previous_growth * decay_rate
            
            # Floor at 10% growth to prevent unrealistic scenarios
            year_growth = max(year_growth, 0.1)
            previous_growth = year_growth  # Store for next iteration
            
            # Revenue compounds with the decaying growth rate
            current_revenue = current_revenue * (1 + year_growth)
            
            if return_projections:
                # Margin expansion trajectory by business model
                # SaaS margins improve ~2pp/yr, AI companies ~3pp/yr (GPU efficiency),
                # services stay flat, marketplaces ~1.5pp/yr
                _MARGIN_EXPANSION_RATES = {
                    'ai_first': 0.03, 'ai': 0.03,
                    'vertical_saas': 0.025, 'vertical': 0.025,
                    'saas': 0.02, 'horizontal_saas': 0.02, 'horizontal': 0.02,
                    'services': 0.005,
                    'marketplace': 0.015,
                    'hardware': 0.01,
                    'fintech': 0.02,
                    'rollup': 0.01,
                }
                _BASE_MARGINS = {
                    'ai_first': 0.55, 'ai': 0.55,
                    'vertical_saas': 0.75, 'vertical': 0.75,
                    'saas': 0.70, 'horizontal_saas': 0.70, 'horizontal': 0.70,
                    'services': 0.40,
                    'marketplace': 0.65,
                    'hardware': 0.45,
                    'fintech': 0.60,
                    'rollup': 0.50,
                }
                sector_key = (sector or '').lower().replace(' ', '_').replace('-', '_')
                base_margin = _BASE_MARGINS.get(sector_key, 0.65)
                margin_rate = _MARGIN_EXPANSION_RATES.get(sector_key, 0.015)
                gross_margin = min(0.90, base_margin + margin_rate * year)

                projections.append({
                    'year': year,
                    'revenue': current_revenue,
                    'growth_rate': year_growth,
                    'gross_margin': round(gross_margin, 3),
                    'gross_profit': current_revenue * gross_margin,
                })

        # VALIDATION: Ensure revenue multiples remain reasonable (separate from PWERM validation)
        # This prevents ridiculous projections that would break PWERM assumptions
        if return_projections:
            final_revenue = projections[-1]['revenue'] if projections else base_revenue
        else:
            final_revenue = current_revenue
        
        # Validate final revenue multiple vs base (should be reasonable growth, not astronomical)
        # Typical 5-year projections: 3x-50x revenue growth is reasonable for high-growth companies
        # Beyond 100x is suspicious and likely indicates calculation error
        revenue_multiple = final_revenue / base_revenue if base_revenue > 0 else 1.0
        max_reasonable_multiple = 200.0  # 200x over 5 years is extreme but possible for hyper-growth
        min_reasonable_multiple = 0.1    # 10% of original is minimum (company shrinking)
        
        if revenue_multiple > max_reasonable_multiple:
            logger.warning(f"[REVENUE_DECAY_VALIDATION] Revenue multiple {revenue_multiple:.1f}x exceeds reasonable maximum {max_reasonable_multiple}x. "
                          f"Base: ${base_revenue/1e6:.1f}M, Final: ${final_revenue/1e6:.1f}M, Years: {years}, Initial Growth: {initial_growth:.1%}")
            # Cap at reasonable maximum to prevent ridiculous multiples
            capped_multiple = max_reasonable_multiple
            if return_projections:
                # Scale down all projections proportionally
                scale_factor = capped_multiple / revenue_multiple
                for proj in projections:
                    proj['revenue'] = proj['revenue'] * scale_factor
                final_revenue = projections[-1]['revenue'] if projections else base_revenue
            else:
                final_revenue = base_revenue * capped_multiple
        
        if revenue_multiple < min_reasonable_multiple:
            logger.warning(f"[REVENUE_DECAY_VALIDATION] Revenue multiple {revenue_multiple:.1f}x below reasonable minimum {min_reasonable_multiple}x. "
                          f"Base: ${base_revenue/1e6:.1f}M, Final: ${final_revenue/1e6:.1f}M, Years: {years}")
            # Floor at reasonable minimum
            if return_projections:
                scale_factor = min_reasonable_multiple / revenue_multiple
                for proj in projections:
                    proj['revenue'] = proj['revenue'] * scale_factor
                final_revenue = projections[-1]['revenue'] if projections else base_revenue
            else:
                final_revenue = base_revenue * min_reasonable_multiple
        
        if return_projections:
            return projections
        return final_revenue
