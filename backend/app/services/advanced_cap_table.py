"""
Advanced Cap Table Mathematics with Benchmarks and Complex Scenarios
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

# HARDCODED ASSUMPTION: Industry benchmark shows 70% of options don't get exercised at exit
DEFAULT_OPTION_EXERCISE_RATE = 0.30  # 30% of options are typically exercised (70% unexercised)


class ShareClass(str, Enum):
    """Types of share classes"""
    COMMON = "common"
    PREFERRED_A = "preferred_a"
    PREFERRED_B = "preferred_b"
    PREFERRED_C = "preferred_c"
    PREFERRED_D = "preferred_d"
    PREFERRED_E = "preferred_e"
    PREFERRED_F = "preferred_f"
    OPTIONS = "options"
    WARRANTS = "warrants"
    SAFE = "safe"
    CONVERTIBLE_NOTE = "convertible_note"


@dataclass
class ShareholderRights:
    """Rights associated with shares"""
    voting_rights: bool = True
    liquidation_preference: float = 1.0
    participation_rights: bool = False
    pro_rata_rights: bool = False
    drag_along: bool = False
    tag_along: bool = False
    board_seats: int = 0
    information_rights: bool = False
    registration_rights: bool = False
    anti_dilution: Optional[str] = None  # "full_ratchet", "weighted_average", None


@dataclass
class ShareEntry:
    """Individual shareholding entry"""
    shareholder_id: str
    shareholder_name: str
    share_class: ShareClass
    num_shares: Decimal
    price_per_share: Decimal
    investment_date: datetime
    vesting_schedule: Optional['VestingSchedule'] = None
    rights: ShareholderRights = field(default_factory=ShareholderRights)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VestingSchedule:
    """Vesting schedule for shares/options"""
    total_shares: Decimal
    cliff_months: int
    vesting_months: int
    start_date: datetime
    acceleration_on_change_of_control: bool = False
    
    def calculate_vested(self, as_of_date: datetime) -> Decimal:
        """Calculate vested shares as of a given date"""
        months_elapsed = (as_of_date - self.start_date).days / 30.44
        
        if months_elapsed < self.cliff_months:
            return Decimal('0')
        
        if months_elapsed >= self.vesting_months:
            return self.total_shares
        
        # Linear vesting after cliff
        cliff_vested = self.total_shares * Decimal(self.cliff_months) / Decimal(self.vesting_months)
        monthly_vest = self.total_shares / Decimal(self.vesting_months)
        additional_months = Decimal(months_elapsed - self.cliff_months)
        
        return cliff_vested + (monthly_vest * additional_months)


class CapTableCalculator:
    """Advanced cap table calculations with complex scenarios"""
    
    # Industry benchmarks for different stages
    BENCHMARKS = {
        'seed': {
            'dilution_range': (0.15, 0.25),
            'option_pool': (0.10, 0.15),
            'valuation_multiple': (3, 10),
            'liquidation_preference': 1.0
        },
        'series_a': {
            'dilution_range': (0.20, 0.30),
            'option_pool': (0.12, 0.18),
            'valuation_multiple': (10, 30),
            'liquidation_preference': 1.0
        },
        'series_b': {
            'dilution_range': (0.15, 0.25),
            'option_pool': (0.10, 0.15),
            'valuation_multiple': (20, 50),
            'liquidation_preference': 1.0
        },
        'series_c': {
            'dilution_range': (0.10, 0.20),
            'option_pool': (0.08, 0.12),
            'valuation_multiple': (30, 100),
            'liquidation_preference': 1.0
        },
        'late_stage': {
            'dilution_range': (0.05, 0.15),
            'option_pool': (0.05, 0.10),
            'valuation_multiple': (50, 200),
            'liquidation_preference': 1.0
        }
    }
    
    def __init__(self):
        self.share_entries: List[ShareEntry] = []
        self.total_shares_authorized = Decimal('10000000')
        self.company_stage = 'seed'
        
    def add_shareholder(self, entry: ShareEntry):
        """Add a shareholder to the cap table"""
        self.share_entries.append(entry)
        
    def calculate_ownership(
        self,
        as_of_date: Optional[datetime] = None,
        fully_diluted: bool = True,
        option_exercise_rate: float = DEFAULT_OPTION_EXERCISE_RATE
    ) -> pd.DataFrame:
        """Calculate ownership percentages
        
        Note: For fully diluted calculations, assumes only 25% of options are exercised
        """
        
        if as_of_date is None:
            as_of_date = datetime.now()
            
        ownership_data = []
        
        # Calculate shares for each holder
        for entry in self.share_entries:
            if entry.vesting_schedule and not fully_diluted:
                shares = entry.vesting_schedule.calculate_vested(as_of_date)
            else:
                # Apply option exercise rate for options in fully diluted calculations
                if entry.share_class == ShareClass.OPTIONS and fully_diluted:
                    shares = entry.num_shares * Decimal(str(option_exercise_rate))
                else:
                    shares = entry.num_shares
                
            ownership_data.append({
                'shareholder': entry.shareholder_name,
                'share_class': entry.share_class.value,
                'shares': float(shares),
                'investment': float(entry.num_shares * entry.price_per_share),
                'price_per_share': float(entry.price_per_share)
            })
            
        df = pd.DataFrame(ownership_data)
        
        # Calculate total shares
        total_shares = df['shares'].sum()
        
        # Calculate ownership percentages
        df['ownership_pct'] = df['shares'] / total_shares * 100
        
        # Group by shareholder
        summary = df.groupby('shareholder').agg({
            'shares': 'sum',
            'investment': 'sum',
            'ownership_pct': 'sum'
        }).round(2)
        
        return summary
        
    def simulate_financing_round(
        self,
        investment_amount: Decimal,
        pre_money_valuation: Decimal,
        option_pool_increase: Decimal = Decimal('0'),
        participating_preferred: bool = False,
        liquidation_multiple: float = 1.0,
        option_exercise_rate: float = DEFAULT_OPTION_EXERCISE_RATE
    ) -> Dict[str, Any]:
        """Simulate a new financing round
        
        Note: Assumes only 25% of options are exercised for dilution calculations
        """
        
        # Calculate post-money valuation
        post_money = pre_money_valuation + investment_amount
        
        # Calculate new shares issued - apply option exercise rate
        current_shares = Decimal('0')
        for entry in self.share_entries:
            if entry.share_class == ShareClass.OPTIONS:
                current_shares += entry.num_shares * Decimal(str(option_exercise_rate))
            else:
                current_shares += entry.num_shares
        price_per_share = pre_money_valuation / current_shares
        new_shares = investment_amount / price_per_share
        
        # Calculate dilution
        dilution = new_shares / (current_shares + new_shares)
        
        # Option pool expansion (dilutes existing shareholders)
        if option_pool_increase > 0:
            option_pool_shares = (current_shares + new_shares) * option_pool_increase
            total_new_shares = new_shares + option_pool_shares
            actual_dilution = total_new_shares / (current_shares + total_new_shares)
        else:
            option_pool_shares = Decimal('0')
            actual_dilution = dilution
            
        # Calculate pro-forma ownership
        proforma_ownership = {}
        for entry in self.share_entries:
            old_ownership = entry.num_shares / current_shares
            new_ownership = entry.num_shares / (current_shares + new_shares + option_pool_shares)
            proforma_ownership[entry.shareholder_name] = {
                'old_ownership': float(old_ownership * 100),
                'new_ownership': float(new_ownership * 100),
                'dilution': float((old_ownership - new_ownership) * 100)
            }
            
        # Check against benchmarks
        benchmark = self.BENCHMARKS.get(self.company_stage, self.BENCHMARKS['seed'])
        dilution_in_range = benchmark['dilution_range'][0] <= float(actual_dilution) <= benchmark['dilution_range'][1]
        
        return {
            'pre_money_valuation': float(pre_money_valuation),
            'post_money_valuation': float(post_money),
            'investment_amount': float(investment_amount),
            'new_shares_issued': float(new_shares),
            'option_pool_shares': float(option_pool_shares),
            'price_per_share': float(price_per_share),
            'dilution_pct': float(actual_dilution * 100),
            'benchmark_dilution_range': benchmark['dilution_range'],
            'dilution_in_benchmark': dilution_in_range,
            'proforma_ownership': proforma_ownership,
            'liquidation_preference': {
                'multiple': liquidation_multiple,
                'participating': participating_preferred,
                'amount': float(investment_amount * Decimal(str(liquidation_multiple)))
            }
        }
        
    def calculate_liquidation_waterfall(
        self,
        exit_value: float,
        cap_table: Dict[str, float],
        liquidation_preferences: Optional[Dict[str, Dict]] = None,
        funding_rounds: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Calculate liquidation waterfall for exit scenarios
        
        This is the method called by the orchestrator for waterfall calculations.
        Now properly implements LIFO/stacked preferences (last money in, first money out).
        """
        # Convert exit value to Decimal for precision
        exit_value_decimal = Decimal(str(exit_value))
        
        # If we have existing share entries, use the detailed calculation
        if self.share_entries:
            df_result = self.calculate_exit_waterfall(exit_value_decimal)
            # Convert DataFrame to dict format
            return {
                'distributions': df_result.to_dict('records'),
                'total_distributed': float(df_result['total'].sum()),
                'escrow': float(exit_value_decimal * Decimal('0.1')),
                'summary': {
                    'founders': float(df_result[df_result['share_class'] == 'common']['total'].sum()),
                    'investors': float(df_result[df_result['share_class'] != 'common']['total'].sum()),
                    'employees': float(df_result[df_result['shareholder'].str.contains('Employee|Option', case=False, na=False)]['total'].sum())
                }
            }
        
        # LIFO/Stacked waterfall implementation
        distributions = []
        total_distributed = 0
        remaining = exit_value
        
        # Build liquidation stack from funding rounds (LIFO order)
        liquidation_stack = []
        
        if funding_rounds:
            # Process rounds in REVERSE order (last round first)
            for round_data in reversed(funding_rounds):
                round_name = round_data.get('round', 'Unknown')
                amount_raised = round_data.get('amount', 0)
                investors = round_data.get('investors', [])
                lead_investor = round_data.get('lead_investor', '')
                
                # Default to 1x non-participating liquidation preference
                liq_multiple = round_data.get('liquidation_multiple', 1.0)
                participating = round_data.get('participating', False)
                
                # Calculate preference amount (typically 1x the investment)
                preference_amount = amount_raised * liq_multiple
                
                liquidation_stack.append({
                    'round': round_name,
                    'investors': investors,
                    'lead_investor': lead_investor,
                    'preference_amount': preference_amount,
                    'participating': participating,
                    'amount_raised': amount_raised
                })
        
        # Step 1: Pay out liquidation preferences in LIFO order
        for round_info in liquidation_stack:
            if remaining <= 0:
                break
                
            pref_amount = round_info['preference_amount']
            round_name = round_info['round']
            
            # Determine how much this round gets
            if remaining >= pref_amount:
                # Full preference paid
                amount_to_distribute = pref_amount
                remaining -= pref_amount
            else:
                # Partial preference (not enough money left)
                amount_to_distribute = remaining
                remaining = 0
            
            # Distribute to this round's investors
            if round_info['lead_investor']:
                # Lead gets 60% of the round's distribution
                lead_amount = amount_to_distribute * 0.6
                distributions.append({
                    'shareholder': f"{round_info['lead_investor']} ({round_name} Lead)",
                    'amount': lead_amount,
                    'type': 'liquidation_preference',
                    'round': round_name
                })
                total_distributed += lead_amount
                
                # Other investors split remaining 40%
                other_investors = [inv for inv in round_info['investors'] if inv != round_info['lead_investor']]
                if other_investors:
                    per_investor = (amount_to_distribute * 0.4) / len(other_investors)
                    for investor in other_investors:
                        distributions.append({
                            'shareholder': f"{investor} ({round_name})",
                            'amount': per_investor,
                            'type': 'liquidation_preference',
                            'round': round_name
                        })
                        total_distributed += per_investor
            elif round_info['investors']:
                # Equal split among all investors
                per_investor = amount_to_distribute / len(round_info['investors'])
                for investor in round_info['investors']:
                    distributions.append({
                        'shareholder': f"{investor} ({round_name})",
                        'amount': per_investor,
                        'type': 'liquidation_preference',
                        'round': round_name
                    })
                    total_distributed += per_investor
            else:
                # Generic investor label
                distributions.append({
                    'shareholder': f"{round_name} Investors",
                    'amount': amount_to_distribute,
                    'type': 'liquidation_preference',
                    'round': round_name
                })
                total_distributed += amount_to_distribute
        
        # Step 2: Distribute remaining to common shareholders (founders, employees)
        if remaining > 0:
            # Common shareholders include founders and employees
            common_holders = {k: v for k, v in cap_table.items() 
                            if 'Founder' in k or 'Employee' in k or 'Option' in k or k == 'Founders'}
            
            if common_holders:
                total_common_ownership = sum(common_holders.values())
                if total_common_ownership > 0:
                    for shareholder, ownership_pct in common_holders.items():
                        # Pro-rata distribution of remaining value
                        amount = remaining * (ownership_pct / total_common_ownership)
                        distributions.append({
                            'shareholder': shareholder,
                            'amount': amount,
                            'type': 'common_distribution'
                        })
                        total_distributed += amount
        
        # Calculate escrow (typically 10% held back)
        escrow = exit_value * 0.1
        
        return {
            'distributions': distributions,
            'total_distributed': total_distributed,
            'escrow': escrow,
            'remaining_after_preferences': max(0, remaining),
            'summary': {
                'founders': sum(d['amount'] for d in distributions if 'Founder' in d['shareholder']),
                'investors': sum(d['amount'] for d in distributions if any(x in d['shareholder'] for x in ['Lead', 'Investor', 'VC', 'Series', 'Seed'])),
                'employees': sum(d['amount'] for d in distributions if 'Employee' in d['shareholder'] or 'Option' in d['shareholder']),
                'total_preferences_paid': sum(d['amount'] for d in distributions if d['type'] == 'liquidation_preference'),
                'common_distributions': sum(d['amount'] for d in distributions if d['type'] == 'common_distribution')
            },
            'preference_stack': liquidation_stack  # Include for transparency
        }
    
    def calculate_exit_waterfall(
        self,
        exit_value: Decimal,
        include_escrow: bool = True,
        escrow_pct: float = 0.10,
        option_exercise_rate: float = DEFAULT_OPTION_EXERCISE_RATE
    ) -> pd.DataFrame:
        """Calculate exit proceeds distribution
        
        Note: Assumes only 25% of options are exercised at exit (industry benchmark)
        """
        
        # Deduct escrow if applicable
        if include_escrow:
            distributable = exit_value * (Decimal('1') - Decimal(str(escrow_pct)))
            escrow_amount = exit_value * Decimal(str(escrow_pct))
        else:
            distributable = exit_value
            escrow_amount = Decimal('0')
            
        distributions = []
        remaining = distributable
        
        # Step 1: Pay liquidation preferences
        for entry in self.share_entries:
            if entry.share_class != ShareClass.COMMON:
                liq_pref = entry.num_shares * entry.price_per_share * Decimal(str(entry.rights.liquidation_preference))
                
                if remaining >= liq_pref:
                    distributions.append({
                        'shareholder': entry.shareholder_name,
                        'share_class': entry.share_class.value,
                        'liquidation_preference': float(liq_pref),
                        'participation': 0,
                        'common_distribution': 0,
                        'total': float(liq_pref)
                    })
                    remaining -= liq_pref
                else:
                    # Pro-rata if not enough to cover all preferences
                    distributions.append({
                        'shareholder': entry.shareholder_name,
                        'share_class': entry.share_class.value,
                        'liquidation_preference': float(remaining),
                        'participation': 0,
                        'common_distribution': 0,
                        'total': float(remaining)
                    })
                    remaining = Decimal('0')
                    break
                    
        # Step 2: Distribute remaining to common (and participating preferred)
        if remaining > 0:
            # Calculate participating shares
            total_participating = Decimal('0')
            for entry in self.share_entries:
                if entry.share_class == ShareClass.COMMON or entry.rights.participation_rights:
                    # Apply option exercise rate - only 25% of options are exercised
                    if entry.share_class == ShareClass.OPTIONS:
                        exercised_shares = entry.num_shares * Decimal(str(option_exercise_rate))
                        total_participating += exercised_shares
                    else:
                        total_participating += entry.num_shares
                    
            # Distribute pro-rata
            for i, entry in enumerate(self.share_entries):
                if entry.share_class == ShareClass.COMMON or entry.rights.participation_rights:
                    # Apply option exercise rate for options
                    if entry.share_class == ShareClass.OPTIONS:
                        effective_shares = entry.num_shares * Decimal(str(option_exercise_rate))
                    else:
                        effective_shares = entry.num_shares
                    share_of_remaining = (effective_shares / total_participating) * remaining
                    
                    if i < len(distributions):
                        distributions[i]['common_distribution'] = float(share_of_remaining)
                        distributions[i]['total'] += float(share_of_remaining)
                    else:
                        distributions.append({
                            'shareholder': entry.shareholder_name,
                            'share_class': entry.share_class.value,
                            'liquidation_preference': 0,
                            'participation': float(share_of_remaining) if entry.rights.participation_rights else 0,
                            'common_distribution': float(share_of_remaining) if entry.share_class == ShareClass.COMMON else 0,
                            'total': float(share_of_remaining)
                        })
                        
        df = pd.DataFrame(distributions)
        
        # Add summary row
        summary = pd.DataFrame([{
            'shareholder': 'TOTAL',
            'share_class': '',
            'liquidation_preference': df['liquidation_preference'].sum(),
            'participation': df['participation'].sum(),
            'common_distribution': df['common_distribution'].sum(),
            'total': df['total'].sum()
        }])
        
        df = pd.concat([df, summary], ignore_index=True)
        
        # Add metrics
        df['return_multiple'] = df.apply(
            lambda row: row['total'] / self._get_investment(row['shareholder']) 
            if row['shareholder'] != 'TOTAL' and self._get_investment(row['shareholder']) > 0 
            else 0,
            axis=1
        )
        
        return df
        
    def _get_investment(self, shareholder_name: str) -> float:
        """Get total investment for a shareholder"""
        total = Decimal('0')
        for entry in self.share_entries:
            if entry.shareholder_name == shareholder_name:
                total += entry.num_shares * entry.price_per_share
        return float(total)
        
    def calculate_dilution_scenarios(
        self,
        num_rounds: int = 3,
        avg_dilution_per_round: float = 0.20
    ) -> pd.DataFrame:
        """Calculate multi-round dilution scenarios"""
        
        scenarios = []
        
        # Base case
        base_ownership = self.calculate_ownership()
        
        for dilution_rate in [avg_dilution_per_round * 0.5, avg_dilution_per_round, avg_dilution_per_round * 1.5]:
            cumulative_ownership = base_ownership.copy()
            
            for round_num in range(1, num_rounds + 1):
                # Apply dilution
                cumulative_ownership['ownership_pct'] *= (Decimal('1') - Decimal(str(dilution_rate)))
                
                scenarios.append({
                    'scenario': f'{dilution_rate*100:.0f}% dilution',
                    'round': f'Round {round_num}',
                    'founder_ownership': cumulative_ownership.loc[
                        cumulative_ownership.index.str.contains('Founder', case=False), 
                        'ownership_pct'
                    ].sum() if any('founder' in idx.lower() for idx in cumulative_ownership.index) else 0,
                    'investor_ownership': cumulative_ownership.loc[
                        ~cumulative_ownership.index.str.contains('Founder', case=False), 
                        'ownership_pct'
                    ].sum() if any('founder' in idx.lower() for idx in cumulative_ownership.index) else 100,
                    'total_dilution': float((Decimal('1') - (Decimal('1') - Decimal(str(dilution_rate))) ** round_num) * 100)
                })
                
        return pd.DataFrame(scenarios)
    
    def calculate_waterfall_breakpoints(
        self,
        base_case_exit: Decimal,
        bull_multiplier: float = 2.0,
        bear_multiplier: float = 0.5
    ) -> Dict[str, Any]:
        """Calculate liquidation waterfall breakpoints for base, bull, and bear cases
        
        Args:
            base_case_exit: Base case exit value
            bull_multiplier: Multiplier for bull case (default 2x base)
            bear_multiplier: Multiplier for bear case (default 0.5x base)
            
        Returns:
            Dictionary with breakpoint analysis for each scenario
        """
        
        scenarios = {
            'bear': base_case_exit * Decimal(str(bear_multiplier)),
            'base': base_case_exit,
            'bull': base_case_exit * Decimal(str(bull_multiplier))
        }
        
        results = {}
        
        for scenario_name, exit_value in scenarios.items():
            # Calculate waterfall for this scenario
            waterfall_df = self.calculate_exit_waterfall(exit_value)
            
            # Calculate key breakpoints
            total_liquidation_prefs = Decimal('0')
            investor_breakeven_points = {}
            
            for entry in self.share_entries:
                if entry.share_class != ShareClass.COMMON:
                    liq_pref = entry.num_shares * entry.price_per_share * Decimal(str(entry.rights.liquidation_preference))
                    total_liquidation_prefs += liq_pref
                    
                    # Calculate breakeven point for this investor
                    investment = entry.num_shares * entry.price_per_share
                    investor_breakeven_points[entry.shareholder_name] = {
                        'investment': float(investment),
                        'liquidation_preference': float(liq_pref),
                        'breakeven_exit': float(investment),  # Minimum exit to return capital
                        '2x_exit': float(investment * 2),     # Exit needed for 2x return
                        '3x_exit': float(investment * 3),     # Exit needed for 3x return
                        '5x_exit': float(investment * 5),     # Exit needed for 5x return
                        '10x_exit': float(investment * 10)    # Exit needed for 10x return
                    }
            
            # Identify key transition points
            transition_points = []
            
            # Point 1: Liquidation preferences fully covered
            if total_liquidation_prefs > 0:
                transition_points.append({
                    'exit_value': float(total_liquidation_prefs),
                    'description': 'All liquidation preferences covered',
                    'impact': 'Preferred shareholders receive full preference, common starts participating'
                })
            
            # Point 2: Common shareholders start receiving meaningful proceeds (>$1M)
            common_threshold = total_liquidation_prefs + Decimal('1000000')
            transition_points.append({
                'exit_value': float(common_threshold),
                'description': 'Common shareholders receive >$1M',
                'impact': 'Founders/employees start seeing meaningful returns'
            })
            
            # Point 3: Conversion point (where preferred would convert to common)
            # This happens when common proceeds > liquidation preference
            conversion_point = self._calculate_conversion_point()
            if conversion_point > 0:
                transition_points.append({
                    'exit_value': float(conversion_point),
                    'description': 'Optimal conversion point for preferred',
                    'impact': 'Preferred shareholders would convert to common for better returns'
                })
            
            # Calculate actual distributions at this exit value
            distributions = waterfall_df[waterfall_df['shareholder'] != 'TOTAL']
            
            # Group by share class
            by_class = distributions.groupby('share_class').agg({
                'total': 'sum',
                'liquidation_preference': 'sum',
                'common_distribution': 'sum'
            }).to_dict('index')
            
            # Calculate return multiples for major investors
            investor_returns = {}
            for idx, row in distributions.iterrows():
                if row['shareholder'] != 'TOTAL':
                    investment = self._get_investment(row['shareholder'])
                    if investment > 0:
                        investor_returns[row['shareholder']] = {
                            'proceeds': row['total'],
                            'investment': investment,
                            'return_multiple': row['total'] / investment,
                            'irr_5_year': ((row['total'] / investment) ** (1/5) - 1) * 100  # Approximate 5-year IRR
                        }
            
            results[scenario_name] = {
                'exit_value': float(exit_value),
                'total_liquidation_preferences': float(total_liquidation_prefs),
                'transition_points': sorted(transition_points, key=lambda x: x['exit_value']),
                'distributions_by_class': by_class,
                'investor_returns': investor_returns,
                'investor_breakeven_points': investor_breakeven_points,
                'common_shareholders_total': float(distributions[distributions['share_class'] == 'common']['total'].sum()),
                'preferred_shareholders_total': float(distributions[distributions['share_class'] != 'common']['total'].sum())
            }
        
        # Add comparative analysis
        results['comparative_analysis'] = {
            'bear_to_base_ratio': float(scenarios['bear'] / scenarios['base']),
            'bull_to_base_ratio': float(scenarios['bull'] / scenarios['base']),
            'common_upside': {
                'bear': results['bear']['common_shareholders_total'],
                'base': results['base']['common_shareholders_total'],
                'bull': results['bull']['common_shareholders_total']
            },
            'preferred_protection': {
                'bear_coverage': results['bear']['preferred_shareholders_total'] / float(total_liquidation_prefs) if total_liquidation_prefs > 0 else 0,
                'base_coverage': results['base']['preferred_shareholders_total'] / float(total_liquidation_prefs) if total_liquidation_prefs > 0 else 0,
                'bull_coverage': results['bull']['preferred_shareholders_total'] / float(total_liquidation_prefs) if total_liquidation_prefs > 0 else 0
            }
        }
        
        return results
    
    def _calculate_conversion_point(self) -> Decimal:
        """Calculate the exit value where preferred would convert to common"""
        # Simplified calculation - actual would depend on specific terms
        total_shares = sum(entry.num_shares for entry in self.share_entries)
        total_liquidation_prefs = sum(
            entry.num_shares * entry.price_per_share * Decimal(str(entry.rights.liquidation_preference))
            for entry in self.share_entries
            if entry.share_class != ShareClass.COMMON
        )
        
        # Conversion happens when: exit_value / total_shares > liquidation_pref_per_share
        if total_shares > 0:
            return total_liquidation_prefs * Decimal('1.5')  # Rough approximation
        return Decimal('0')
        
    def anti_dilution_adjustment(
        self,
        original_price: Decimal,
        new_price: Decimal,
        shares_affected: Decimal,
        method: str = "weighted_average"
    ) -> Dict[str, Any]:
        """Calculate anti-dilution adjustments"""
        
        if new_price >= original_price:
            return {
                'adjustment_needed': False,
                'original_price': float(original_price),
                'new_price': float(new_price),
                'adjusted_price': float(original_price),
                'additional_shares': 0
            }
            
        if method == "full_ratchet":
            # Full ratchet: adjust to new lower price
            adjusted_price = new_price
            additional_shares = shares_affected * (original_price / new_price - 1)
            
        elif method == "weighted_average":
            # Broad-based weighted average
            total_shares = sum(entry.num_shares for entry in self.share_entries)
            money_raised = new_price * shares_affected
            
            adjusted_price = (
                (original_price * total_shares + money_raised) /
                (total_shares + shares_affected)
            )
            additional_shares = shares_affected * (original_price / adjusted_price - 1)
            
        else:
            raise ValueError(f"Unknown anti-dilution method: {method}")
            
        return {
            'adjustment_needed': True,
            'method': method,
            'original_price': float(original_price),
            'new_price': float(new_price),
            'adjusted_price': float(adjusted_price),
            'additional_shares': float(additional_shares),
            'dilution_protection': float((original_price - adjusted_price) / original_price * 100)
        }
        
    def generate_benchmark_report(self) -> Dict[str, Any]:
        """Generate comprehensive benchmark comparison"""
        
        ownership = self.calculate_ownership()
        benchmark = self.BENCHMARKS.get(self.company_stage, self.BENCHMARKS['seed'])
        
        # Calculate metrics
        founder_ownership = ownership.loc[
            ownership.index.str.contains('Founder', case=False), 
            'ownership_pct'
        ].sum() if any('founder' in idx.lower() for idx in ownership.index) else 0
        
        investor_ownership = ownership.loc[
            ~ownership.index.str.contains('Founder|Employee', case=False), 
            'ownership_pct'
        ].sum()
        
        employee_ownership = ownership.loc[
            ownership.index.str.contains('Employee|Option', case=False), 
            'ownership_pct'
        ].sum() if any('employee' in idx.lower() or 'option' in idx.lower() for idx in ownership.index) else 0
        
        # Industry comparisons
        industry_benchmarks = {
            'seed': {'founder': (60, 80), 'investor': (15, 30), 'employee': (10, 15)},
            'series_a': {'founder': (40, 60), 'investor': (25, 40), 'employee': (12, 18)},
            'series_b': {'founder': (25, 40), 'investor': (40, 60), 'employee': (10, 15)},
            'series_c': {'founder': (15, 30), 'investor': (55, 75), 'employee': (8, 12)},
            'late_stage': {'founder': (5, 20), 'investor': (70, 85), 'employee': (5, 10)}
        }
        
        stage_benchmark = industry_benchmarks.get(self.company_stage, industry_benchmarks['seed'])
        
        return {
            'current_ownership': {
                'founders': founder_ownership,
                'investors': investor_ownership,
                'employees': employee_ownership
            },
            'benchmark_ranges': stage_benchmark,
            'in_benchmark': {
                'founders': stage_benchmark['founder'][0] <= founder_ownership <= stage_benchmark['founder'][1],
                'investors': stage_benchmark['investor'][0] <= investor_ownership <= stage_benchmark['investor'][1],
                'employees': stage_benchmark['employee'][0] <= employee_ownership <= stage_benchmark['employee'][1]
            },
            'recommendations': self._generate_recommendations(
                founder_ownership, investor_ownership, employee_ownership, stage_benchmark
            )
        }
        
    def _generate_recommendations(
        self,
        founder_pct: float,
        investor_pct: float,
        employee_pct: float,
        benchmark: Dict
    ) -> List[str]:
        """Generate recommendations based on benchmarks"""
        
        recommendations = []
        
        if founder_pct < benchmark['founder'][0]:
            recommendations.append(
                f"Founder ownership ({founder_pct:.1f}%) is below typical range "
                f"({benchmark['founder'][0]}-{benchmark['founder'][1]}%). "
                "Consider negotiating for less dilution in next round."
            )
            
        if employee_pct < benchmark['employee'][0]:
            recommendations.append(
                f"Employee option pool ({employee_pct:.1f}%) is below typical range "
                f"({benchmark['employee'][0]}-{benchmark['employee'][1]}%). "
                "Consider expanding to attract talent."
            )
            
        if investor_pct > benchmark['investor'][1]:
            recommendations.append(
                f"Investor ownership ({investor_pct:.1f}%) exceeds typical range "
                f"({benchmark['investor'][0]}-{benchmark['investor'][1]}%). "
                "Future fundraising may be challenging without significant growth."
            )
            
        return recommendations


# Singleton instance
cap_table_calculator = CapTableCalculator()