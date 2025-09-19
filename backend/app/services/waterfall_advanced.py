"""
Advanced Waterfall Analysis with Real-World Assumptions
Implements institutional-grade liquidation waterfall calculations
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)


class ExitType(str, Enum):
    """Types of exit scenarios"""
    IPO = "ipo"
    STRATEGIC_MA = "strategic_ma"
    PE_BUYOUT = "pe_buyout"
    ROLL_UP = "roll_up"
    MANAGEMENT_BUYOUT = "management_buyout"
    ACQUIHIRE = "acquihire"
    LIQUIDATION = "liquidation"
    DOWNROUND = "downround"
    EXTENSION = "extension"


class InvestorStage(str, Enum):
    """Investment stages"""
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"  # Growth stage - may have non-vanilla terms
    SERIES_C = "series_c"  # Growth stage - may have non-vanilla terms
    SERIES_D = "series_d"  # Late stage - may have IPO ratchet
    SERIES_E_PLUS = "series_e_plus"  # Late stage - likely IPO ratchet


class InvestorQuality(str, Enum):
    """Investor quality tiers affecting negotiation power"""
    MEGA_FUND = "mega_fund"  # Tiger, Coatue, DST - price insensitive, accept bad terms
    TIER_1 = "tier_1"  # Top funds (Sequoia, a16z, Benchmark) - strong negotiation  
    TIER_2 = "tier_2"  # Strong funds - moderate negotiation
    TIER_3 = "tier_3"  # Mid-tier funds - standard terms
    STRATEGIC = "strategic"  # Corporate investors - may accept worse terms for strategic value
    ANGEL = "angel"  # Individual investors - weak negotiation


class DealStructure(str, Enum):
    """Different deal structures that affect waterfall"""
    STANDARD_PREFERRED = "standard_preferred"
    SAFE = "safe"  # Converts at next qualified financing
    CONVERTIBLE_NOTE = "convertible_note"  # Debt that converts
    REVENUE_BASED = "revenue_based"  # Revenue-based financing
    STRUCTURED_EQUITY = "structured_equity"  # Complex structures with ratchets
    VENTURE_DEBT = "venture_debt"  # Debt with warrants


@dataclass
class LiquidationTerms:
    """Liquidation preference terms for an investor"""
    investor_name: str
    stage: InvestorStage
    investment_amount: Decimal
    shares_owned: Decimal
    investor_quality: InvestorQuality = InvestorQuality.TIER_3
    deal_structure: DealStructure = DealStructure.STANDARD_PREFERRED
    
    # Standard terms
    liquidation_multiple: Decimal = Decimal('1.0')  # Default 1X non-participating
    participating: bool = False  # Default non-participating
    
    # Growth stage terms (Series B/C)
    participation_cap: Optional[Decimal] = None  # Cap on participation (e.g., 3X)
    cumulative_dividend_rate: Optional[Decimal] = None  # Annual cumulative dividend
    
    # Late stage terms (Series D+)
    has_ipo_ratchet: bool = False
    ipo_ratchet_return: Decimal = Decimal('0.20')  # 20% guaranteed return
    
    # Downround/extension terms
    is_downround_investor: bool = False
    
    # M&A blocking rights
    has_blocking_rights: bool = True  # All preferred can block M&A
    
    # Negotiation power (affected by investor quality and ownership)
    negotiation_multiplier: Decimal = Decimal('1.0')
    
    @property
    def diluted_ownership(self) -> Decimal:
        """Calculate diluted ownership percentage"""
        # This would be calculated based on full cap table
        return self.shares_owned / Decimal('100000000')  # Placeholder
    
    @property
    def negotiation_power(self) -> Decimal:
        """
        Calculate negotiation power based on:
        - Investor quality/reputation
        - Ownership percentage
        - Deal structure
        """
        # Base power from investor quality
        quality_power = {
            InvestorQuality.MEGA_FUND: Decimal('0.5'),  # Weak - price insensitive
            InvestorQuality.TIER_1: Decimal('1.5'),     # Strong - brand matters
            InvestorQuality.TIER_2: Decimal('1.2'),
            InvestorQuality.TIER_3: Decimal('1.0'),
            InvestorQuality.STRATEGIC: Decimal('0.8'),  # Accept worse for strategic value
            InvestorQuality.ANGEL: Decimal('0.6')
        }.get(self.investor_quality, Decimal('1.0'))
        
        # Ownership impact (more ownership = more power)
        ownership_power = min(self.diluted_ownership * Decimal('10'), Decimal('2.0'))
        
        # Deal structure impact
        structure_power = {
            DealStructure.STANDARD_PREFERRED: Decimal('1.0'),
            DealStructure.STRUCTURED_EQUITY: Decimal('1.3'),  # Complex = more power
            DealStructure.SAFE: Decimal('0.7'),  # Less power until conversion
            DealStructure.CONVERTIBLE_NOTE: Decimal('0.8'),
            DealStructure.REVENUE_BASED: Decimal('0.6'),
            DealStructure.VENTURE_DEBT: Decimal('0.5')
        }.get(self.deal_structure, Decimal('1.0'))
        
        return quality_power * ownership_power * structure_power * self.negotiation_multiplier
    
    def __post_init__(self):
        """Apply stage-specific and investor quality defaults"""
        
        # MEGA FUNDS (60% of capital) - Accept worse terms for best founders
        if self.investor_quality == InvestorQuality.MEGA_FUND:
            # Mega funds lower cost of capital by accepting founder-friendly terms
            if self.stage in [InvestorStage.SERIES_B, InvestorStage.SERIES_C, InvestorStage.SERIES_D]:
                # 70% chance they accept standard 1X non-participating (founder friendly)
                if np.random.random() < 0.70:
                    self.liquidation_multiple = Decimal('1.0')
                    self.participating = False
                    self.has_ipo_ratchet = False  # Often waive ratchets
                # Only 30% get any enhanced terms, and even then modest
                else:
                    self.liquidation_multiple = Decimal('1.25')  # Lower than typical
            
            # Mega funds rarely negotiate hard in downside scenarios
            self.negotiation_multiplier = Decimal('0.7')
        
        # TIER 1 FUNDS - Balance of terms and reputation
        elif self.investor_quality == InvestorQuality.TIER_1:
            # Late stage deals (Series D+) 
            if self.stage in [InvestorStage.SERIES_D, InvestorStage.SERIES_E_PLUS]:
                # Only 10% probability of 1.5X for Tier 1 (vs 14% market)
                if np.random.random() < 0.10:
                    self.liquidation_multiple = Decimal('1.5')
                # IPO ratchet more common for Tier 1
                self.has_ipo_ratchet = True
        
        # STANDARD MARKET TERMS (Tier 2/3)
        else:
            # Late stage deals (Series D+) 
            if self.stage in [InvestorStage.SERIES_D, InvestorStage.SERIES_E_PLUS]:
                # 14% probability of 1.5X liquidation preference
                if np.random.random() < 0.14:
                    self.liquidation_multiple = Decimal('1.5')
                # IPO ratchet for late stage
                self.has_ipo_ratchet = True
                
            # Growth stage deals (Series B/C) - non-vanilla structures
            elif self.stage in [InvestorStage.SERIES_B, InvestorStage.SERIES_C]:
                # 30% chance of capped participating
                if np.random.random() < 0.30:
                    self.participating = True
                    self.participation_cap = Decimal('3.0')  # 3X cap typical
                # 20% chance of cumulative dividends
                elif np.random.random() < 0.20:
                    self.cumulative_dividend_rate = Decimal('0.08')  # 8% annual
        
        # STRATEGIC INVESTORS - Often accept worse terms for strategic access
        if self.investor_quality == InvestorQuality.STRATEGIC:
            self.liquidation_multiple = min(self.liquidation_multiple, Decimal('1.0'))
            self.participating = False  # Rarely get participation
            self.has_blocking_rights = False  # May waive blocking rights
                    
        # Downround/extension - enhanced terms (but varies by investor quality)
        if self.is_downround_investor:
            if self.investor_quality == InvestorQuality.MEGA_FUND:
                # Mega funds less aggressive in downrounds
                self.liquidation_multiple = Decimal('1.25')
            elif self.investor_quality == InvestorQuality.TIER_1:
                # Tier 1 moderate enhancement
                self.liquidation_multiple = Decimal('1.5')
            else:
                # Others push harder
                if np.random.random() < 0.60:
                    self.liquidation_multiple = Decimal('2.0')
                else:
                    self.participating = True


class AdvancedWaterfallCalculator:
    """
    Advanced waterfall calculator with real-world assumptions
    
    Key Assumptions:
    - 1X non-participating liquidation preference as default
    - No pari passu (seniority by round)
    - IPO scenario: liquidation preferences don't matter
    - Late stage (D+): IPO ratchet guaranteeing 20% return
    - 14% of late stage have 1.5X liquidation preference
    - M&A: any preferred can block and negotiate
    - M&A: 50:50 cash/stock mix (except buyout/roll-up)
    - Growth stage (B/C): may have capped participating or cumulative dividends
    - Downrounds: investors push for >1X or participating
    - No pay-to-play provisions
    """
    
    def __init__(self, investors: List[LiquidationTerms]):
        """
        Initialize with investor terms
        
        Args:
            investors: List of investor liquidation terms (ordered by seniority)
        """
        self.investors = sorted(investors, 
                               key=lambda x: self._stage_seniority(x.stage), 
                               reverse=True)  # Most senior first
        
    def _stage_seniority(self, stage: InvestorStage) -> int:
        """Return seniority level (higher = more senior)"""
        seniority_map = {
            InvestorStage.PRE_SEED: 1,
            InvestorStage.SEED: 2,
            InvestorStage.SERIES_A: 3,
            InvestorStage.SERIES_B: 4,
            InvestorStage.SERIES_C: 5,
            InvestorStage.SERIES_D: 6,
            InvestorStage.SERIES_E_PLUS: 7
        }
        return seniority_map.get(stage, 0)
    
    def calculate_waterfall(
        self,
        exit_value: Decimal,
        exit_type: ExitType,
        years_to_exit: float = 3.0,
        common_shares_outstanding: Decimal = Decimal('10000000')
    ) -> Dict[str, Any]:
        """
        Calculate waterfall distribution for given exit scenario
        
        Args:
            exit_value: Total exit proceeds
            exit_type: Type of exit (IPO, M&A, etc.)
            years_to_exit: Years from now to exit
            common_shares_outstanding: Total common shares
            
        Returns:
            Distribution analysis with breakpoints
        """
        
        if exit_type == ExitType.IPO:
            return self._calculate_ipo_distribution(exit_value, common_shares_outstanding)
        elif exit_type in [ExitType.STRATEGIC_MA, ExitType.PE_BUYOUT, ExitType.ROLL_UP]:
            return self._calculate_ma_distribution(exit_value, exit_type, years_to_exit)
        elif exit_type in [ExitType.DOWNROUND, ExitType.EXTENSION]:
            return self._calculate_downround_distribution(exit_value)
        else:
            return self._calculate_standard_waterfall(exit_value)
    
    def _calculate_ipo_distribution(
        self, 
        exit_value: Decimal,
        common_shares_outstanding: Decimal
    ) -> Dict[str, Any]:
        """
        IPO scenario: liquidation preferences don't matter, but IPO ratchet does
        """
        total_shares = common_shares_outstanding + sum(inv.shares_owned for inv in self.investors)
        price_per_share = exit_value / total_shares
        
        distributions = {}
        adjustments = {}
        
        for investor in self.investors:
            base_proceeds = investor.shares_owned * price_per_share
            
            # Apply IPO ratchet for late stage investors
            if investor.has_ipo_ratchet:
                min_return = investor.investment_amount * (Decimal('1') + investor.ipo_ratchet_return)
                if base_proceeds < min_return:
                    # Ratchet kicks in - investor gets more shares
                    additional_value = min_return - base_proceeds
                    adjustments[investor.investor_name] = {
                        'ratchet_triggered': True,
                        'additional_value': float(additional_value),
                        'explanation': f"IPO ratchet guarantees {float(investor.ipo_ratchet_return)*100:.0f}% return"
                    }
                    distributions[investor.investor_name] = float(min_return)
                else:
                    distributions[investor.investor_name] = float(base_proceeds)
            else:
                distributions[investor.investor_name] = float(base_proceeds)
        
        # Common shareholders get remaining
        total_to_investors = sum(distributions.values())
        distributions['Common Shareholders'] = float(exit_value - Decimal(str(total_to_investors)))
        
        return {
            'exit_type': 'IPO',
            'exit_value': float(exit_value),
            'distributions': distributions,
            'adjustments': adjustments,
            'price_per_share': float(price_per_share),
            'note': 'Liquidation preferences convert to common in IPO'
        }
    
    def _calculate_ma_distribution(
        self,
        exit_value: Decimal,
        exit_type: ExitType,
        years_to_exit: float
    ) -> Dict[str, Any]:
        """
        M&A scenario: blocking rights allow negotiation
        50:50 cash/stock mix (except buyout/roll-up which are all cash)
        Game theory: In downside scenarios, negotiation based on diluted ownership
        """
        
        # Determine if this is a downside scenario
        total_invested = sum(inv.investment_amount for inv in self.investors)
        is_downside = exit_value < total_invested * Decimal('1.5')
        
        # Determine cash/stock mix
        if exit_type in [ExitType.PE_BUYOUT, ExitType.ROLL_UP]:
            cash_portion = Decimal('1.0')
            stock_portion = Decimal('0.0')
            mix_note = "All cash transaction (buyout/roll-up)"
        else:
            cash_portion = Decimal('0.5')
            stock_portion = Decimal('0.5')
            mix_note = "50:50 cash/stock mix"
        
        cash_proceeds = exit_value * cash_portion
        stock_proceeds = exit_value * stock_portion
        
        # GAME THEORY NEGOTIATION in downside scenarios
        negotiation_adjustments = {}
        if is_downside:
            # Calculate each investor's negotiation power
            total_shares = sum(inv.shares_owned for inv in self.investors)
            
            for investor in self.investors:
                # Diluted ownership drives negotiation
                diluted_ownership = investor.shares_owned / total_shares if total_shares > 0 else Decimal('0')
                
                # Negotiation factors:
                # 1. Large ownership (>20%) can demand better terms
                # 2. Mega funds with large ownership paradoxically accept worse terms
                # 3. Tier 1 funds use reputation to get better terms
                
                if diluted_ownership > Decimal('0.20'):  # Large owner
                    if investor.investor_quality == InvestorQuality.MEGA_FUND:
                        # Mega funds don't push hard despite large ownership
                        adjustment = Decimal('0.95')  # Accept 5% haircut
                        negotiation_adjustments[investor.investor_name] = {
                            'factor': float(adjustment),
                            'reason': f"Mega fund with {float(diluted_ownership)*100:.1f}% ownership - accepts haircut"
                        }
                    elif investor.investor_quality == InvestorQuality.TIER_1:
                        # Tier 1 uses leverage
                        adjustment = Decimal('1.15')  # Get 15% premium
                        negotiation_adjustments[investor.investor_name] = {
                            'factor': float(adjustment),
                            'reason': f"Tier 1 fund with {float(diluted_ownership)*100:.1f}% ownership - negotiates premium"
                        }
                    else:
                        # Standard negotiation based on ownership
                        adjustment = Decimal('1') + (diluted_ownership * Decimal('0.5'))
                        negotiation_adjustments[investor.investor_name] = {
                            'factor': float(adjustment),
                            'reason': f"{float(diluted_ownership)*100:.1f}% ownership provides leverage"
                        }
                
                elif diluted_ownership > Decimal('0.10'):  # Medium owner
                    if investor.investor_quality in [InvestorQuality.TIER_1, InvestorQuality.TIER_2]:
                        adjustment = Decimal('1.05')  # Small premium
                        negotiation_adjustments[investor.investor_name] = {
                            'factor': float(adjustment),
                            'reason': "Quality fund with meaningful ownership"
                        }
            
            # Apply negotiation adjustments to liquidation preferences
            for investor in self.investors:
                if investor.investor_name in negotiation_adjustments:
                    adj_factor = Decimal(str(negotiation_adjustments[investor.investor_name]['factor']))
                    investor.liquidation_multiple *= adj_factor
        
        # Calculate standard waterfall for cash portion (now with adjusted terms)
        cash_distributions = self._distribute_proceeds(cash_proceeds)
        
        # Stock portion distributed pro-rata (simplified)
        total_ownership = sum(inv.shares_owned for inv in self.investors)
        stock_distributions = {}
        
        for investor in self.investors:
            ownership_pct = investor.shares_owned / total_ownership if total_ownership > 0 else Decimal('0')
            stock_distributions[investor.investor_name] = float(stock_proceeds * ownership_pct)
        
        # Combine distributions
        final_distributions = {}
        for investor in self.investors:
            name = investor.investor_name
            cash = cash_distributions.get(name, 0)
            stock = stock_distributions.get(name, 0)
            final_distributions[name] = {
                'cash': cash,
                'stock': stock,
                'total': cash + stock,
                'can_block': investor.has_blocking_rights
            }
        
        # Add common shareholders
        common_cash = cash_distributions.get('Common Shareholders', 0)
        common_stock = float(stock_proceeds) - sum(stock_distributions.values())
        final_distributions['Common Shareholders'] = {
            'cash': common_cash,
            'stock': common_stock,
            'total': common_cash + common_stock,
            'can_block': False
        }
        
        return {
            'exit_type': exit_type.value,
            'exit_value': float(exit_value),
            'is_downside_scenario': is_downside,
            'cash_portion': float(cash_portion),
            'stock_portion': float(stock_portion),
            'distributions': final_distributions,
            'negotiation_adjustments': negotiation_adjustments if is_downside else {},
            'mix_note': mix_note,
            'blocking_note': 'All preferred investors can block M&A and negotiate terms',
            'game_theory_note': 'In downside M&A, large owners negotiate based on diluted ownership and investor quality'
        }
    
    def _calculate_downround_distribution(self, exit_value: Decimal) -> Dict[str, Any]:
        """
        Downround/extension scenario with enhanced terms
        """
        # Mark downround investors
        for investor in self.investors:
            if investor.is_downround_investor:
                # These investors have enhanced terms already set in __post_init__
                pass
        
        # Calculate with enhanced terms
        distributions = self._distribute_proceeds(exit_value)
        
        # Highlight enhanced terms
        enhanced_terms = []
        for investor in self.investors:
            if investor.is_downround_investor:
                enhanced_terms.append({
                    'investor': investor.investor_name,
                    'liquidation_multiple': float(investor.liquidation_multiple),
                    'participating': investor.participating,
                    'note': 'Enhanced terms due to downround/extension'
                })
        
        return {
            'exit_type': 'Downround/Extension',
            'exit_value': float(exit_value),
            'distributions': distributions,
            'enhanced_terms': enhanced_terms,
            'note': 'Investors pushed for >1X or participating terms'
        }
    
    def _distribute_proceeds(self, proceeds: Decimal) -> Dict[str, float]:
        """
        Distribute proceeds through standard waterfall
        No pari passu - strict seniority by round
        """
        remaining = proceeds
        distributions = {}
        
        # Step 1: Pay liquidation preferences (no pari passu - by seniority)
        for investor in self.investors:
            liq_pref = investor.investment_amount * investor.liquidation_multiple
            
            # Apply cumulative dividends if any
            if investor.cumulative_dividend_rate:
                # Assume 3 years for simplicity
                dividend = investor.investment_amount * investor.cumulative_dividend_rate * Decimal('3')
                liq_pref += dividend
            
            if remaining >= liq_pref:
                distributions[investor.investor_name] = float(liq_pref)
                remaining -= liq_pref
            else:
                distributions[investor.investor_name] = float(remaining)
                remaining = Decimal('0')
                break
        
        # Step 2: Participation (if any) and common distribution
        if remaining > Decimal('0'):
            # Calculate participating shares
            participating_investors = [inv for inv in self.investors if inv.participating]
            
            # Total shares for distribution
            total_shares = sum(inv.shares_owned for inv in self.investors)
            
            for investor in self.investors:
                if investor.participating:
                    # Participating preferred gets pro-rata share
                    share_pct = investor.shares_owned / total_shares if total_shares > 0 else Decimal('0')
                    participation = remaining * share_pct
                    
                    # Apply participation cap if exists
                    if investor.participation_cap:
                        max_total = investor.investment_amount * investor.participation_cap
                        current_total = Decimal(str(distributions.get(investor.investor_name, 0)))
                        participation = min(participation, max_total - current_total)
                    
                    distributions[investor.investor_name] = distributions.get(investor.investor_name, 0) + float(participation)
            
            # Remaining to common
            total_distributed = sum(distributions.values())
            common_proceeds = float(proceeds) - total_distributed
            if common_proceeds > 0:
                distributions['Common Shareholders'] = common_proceeds
        
        return distributions
    
    def _calculate_standard_waterfall(self, exit_value: Decimal) -> Dict[str, Any]:
        """Standard waterfall calculation"""
        distributions = self._distribute_proceeds(exit_value)
        
        return {
            'exit_type': 'Standard',
            'exit_value': float(exit_value),
            'distributions': distributions,
            'note': '1X non-participating as default, no pari passu'
        }
    
    def calculate_scenarios(
        self,
        base_exit_value: Decimal,
        exit_type: ExitType = ExitType.STRATEGIC_MA
    ) -> Dict[str, Any]:
        """
        Calculate bear/base/bull scenarios with breakpoints
        
        Args:
            base_exit_value: Base case exit value
            exit_type: Type of exit scenario
            
        Returns:
            Scenario analysis with breakpoints
        """
        
        scenarios = {
            'bear': base_exit_value * Decimal('0.5'),
            'base': base_exit_value,
            'bull': base_exit_value * Decimal('2.0')
        }
        
        results = {}
        
        for scenario_name, exit_value in scenarios.items():
            results[scenario_name] = self.calculate_waterfall(
                exit_value=exit_value,
                exit_type=exit_type
            )
        
        # Calculate breakpoints
        breakpoints = self._identify_breakpoints()
        
        return {
            'scenarios': results,
            'breakpoints': breakpoints,
            'assumptions': {
                '1x_non_participating': 'Default for all rounds',
                'no_pari_passu': 'Strict seniority by round',
                'ipo_preferences': 'Convert to common, but ratchets apply',
                'late_stage_ipo_ratchet': '20% guaranteed return for Series D+',
                'late_stage_1_5x': '14% probability of 1.5X preference',
                'ma_blocking': 'All preferred can block and negotiate',
                'ma_consideration': '50:50 cash/stock (except buyouts)',
                'growth_stage_terms': 'May have capped participating or cumulative dividends',
                'downround_terms': 'Push for >1X or participating',
                'pay_to_play': 'None assumed'
            }
        }
    
    def _identify_breakpoints(self) -> List[Dict[str, Any]]:
        """Identify key value breakpoints in waterfall"""
        breakpoints = []
        
        # Calculate total liquidation preferences
        total_liq_prefs = sum(
            inv.investment_amount * inv.liquidation_multiple 
            for inv in self.investors
        )
        
        # Breakpoint 1: All liquidation preferences covered
        breakpoints.append({
            'value': float(total_liq_prefs),
            'description': 'All liquidation preferences satisfied',
            'impact': 'Common shareholders begin receiving proceeds'
        })
        
        # Breakpoint 2: Participation caps reached (if any)
        for investor in self.investors:
            if investor.participating and investor.participation_cap:
                cap_value = investor.investment_amount * investor.participation_cap
                breakpoints.append({
                    'value': float(total_liq_prefs + cap_value),
                    'description': f'{investor.investor_name} participation cap reached',
                    'impact': f'No further participation for {investor.investor_name}'
                })
        
        # Breakpoint 3: IPO ratchet trigger points
        for investor in self.investors:
            if investor.has_ipo_ratchet:
                min_return = investor.investment_amount * (Decimal('1') + investor.ipo_ratchet_return)
                breakpoints.append({
                    'value': float(min_return * Decimal('10')),  # Approximate company value
                    'description': f'{investor.investor_name} IPO ratchet threshold',
                    'impact': f'Below this, {investor.investor_name} gets {float(investor.ipo_ratchet_return)*100:.0f}% guaranteed'
                })
        
        # Breakpoint 4: Common gets meaningful value (>$10M)
        common_threshold = total_liq_prefs + Decimal('10000000')
        breakpoints.append({
            'value': float(common_threshold),
            'description': 'Common shareholders receive >$10M',
            'impact': 'Meaningful returns for founders and employees'
        })
        
        # Sort by value
        breakpoints.sort(key=lambda x: x['value'])
        
        return breakpoints


# Example usage function
def create_example_cap_table() -> AdvancedWaterfallCalculator:
    """Create example cap table with typical startup structure"""
    
    investors = [
        LiquidationTerms(
            investor_name="Seed Investors",
            stage=InvestorStage.SEED,
            investment_amount=Decimal('2000000'),
            shares_owned=Decimal('2000000')
        ),
        LiquidationTerms(
            investor_name="Series A Lead",
            stage=InvestorStage.SERIES_A,
            investment_amount=Decimal('10000000'),
            shares_owned=Decimal('3000000')
        ),
        LiquidationTerms(
            investor_name="Series B Lead",
            stage=InvestorStage.SERIES_B,
            investment_amount=Decimal('25000000'),
            shares_owned=Decimal('4000000')
        ),
        LiquidationTerms(
            investor_name="Series C Lead",
            stage=InvestorStage.SERIES_C,
            investment_amount=Decimal('50000000'),
            shares_owned=Decimal('5000000')
        ),
        LiquidationTerms(
            investor_name="Series D Lead",
            stage=InvestorStage.SERIES_D,
            investment_amount=Decimal('100000000'),
            shares_owned=Decimal('6000000')
        )
    ]
    
    return AdvancedWaterfallCalculator(investors)