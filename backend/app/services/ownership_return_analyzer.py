"""
Ownership & Return Analyzer with Bayesian Scenarios
Calculates ownership %, lead/follow dynamics, liquidation preferences, 
option dilution, ratchets, and fund-level impact
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InvestmentType(Enum):
    LEAD = "lead"
    CO_LEAD = "co_lead"  
    FOLLOW = "follow"
    PRO_RATA = "pro_rata"


@dataclass
class InvestmentTerms:
    """Terms for an investment"""
    investment_amount: float
    pre_money_valuation: float
    liquidation_preference: float = 1.0  # 1x, 1.5x, 2x
    participation: bool = False  # Participating preferred
    anti_dilution: Optional[str] = None  # "full_ratchet", "weighted_average", None
    board_seat: bool = False
    pro_rata_rights: bool = True
    option_pool_expansion: float = 0.0  # % of post-money for new option pool


@dataclass
class ExitScenario:
    """Exit scenario with probabilities"""
    name: str
    exit_value: float
    probability: float
    years_to_exit: float
    scenario_type: str  # "IPO", "M&A", "Secondary", "Liquidation", "Write-off"


class OwnershipReturnAnalyzer:
    """
    Analyzes ownership dynamics and return scenarios accounting for:
    - Lead vs follow positioning
    - Liquidation preferences and participation
    - Option pool dilution
    - Anti-dilution provisions (ratchets)
    - Fund portfolio construction
    """
    
    # SVB/Carta benchmarks for round dynamics
    ROUND_BENCHMARKS = {
        'seed': {
            'typical_round_size': 3_000_000,
            'typical_pre_money': 12_000_000,
            'lead_allocation': 0.40,  # Lead takes 40% of round
            'option_pool_expansion': 0.05,  # 5% expansion typical
            'liquidation_pref': 1.0,  # 1x non-participating standard
            'participating': False
        },
        'series_a': {
            'typical_round_size': 15_000_000,
            'typical_pre_money': 50_000_000,
            'lead_allocation': 0.35,  # Lead takes 35% of round
            'option_pool_expansion': 0.08,  # 8% expansion typical
            'liquidation_pref': 1.0,
            'participating': False
        },
        'series_b': {
            'typical_round_size': 40_000_000,
            'typical_pre_money': 160_000_000,
            'lead_allocation': 0.30,  # Lead takes 30% of round
            'option_pool_expansion': 0.05,  # 5% expansion
            'liquidation_pref': 1.0,
            'participating': False  # Sometimes true in down markets
        },
        'series_c': {
            'typical_round_size': 80_000_000,
            'typical_pre_money': 320_000_000,
            'lead_allocation': 0.25,
            'option_pool_expansion': 0.03,
            'liquidation_pref': 1.0,
            'participating': False
        },
        'late_stage': {
            'typical_round_size': 150_000_000,
            'typical_pre_money': 1_000_000_000,
            'lead_allocation': 0.20,
            'option_pool_expansion': 0.02,
            'liquidation_pref': 1.5,  # Often higher in late stage
            'participating': True  # More common in late stage
        }
    }
    
    def calculate_ownership_scenarios(
        self,
        company_data: Dict,
        investment_amount: float,
        investment_type: InvestmentType = InvestmentType.FOLLOW,
        fund_size: float = 100_000_000  # $100M fund default
    ) -> Dict:
        """
        Calculate ownership % and scenarios for lead vs follow
        """
        
        stage = company_data.get('stage', 'series_a').lower().replace(' ', '_')
        benchmarks = self.ROUND_BENCHMARKS.get(stage, self.ROUND_BENCHMARKS['series_a'])
        
        # Current valuation (or estimate from revenue)
        current_valuation = company_data.get('valuation', 0)
        if current_valuation == 0:
            revenue = company_data.get('revenue', company_data.get('arr', 2_000_000))
            multiple = company_data.get('valuation_multiple', 15)  # Default 15x for Series A
            current_valuation = revenue * multiple
        
        # Estimate round size
        round_size = benchmarks['typical_round_size']
        
        # Calculate ownership based on investment type
        if investment_type == InvestmentType.LEAD:
            # Lead investor dynamics
            our_allocation = round_size * benchmarks['lead_allocation']
            # Adjust if our investment amount differs
            if investment_amount < our_allocation:
                # We're a smaller lead
                our_allocation = investment_amount
                ownership_percent = investment_amount / (current_valuation + round_size)
            else:
                # We can take full lead allocation
                ownership_percent = our_allocation / (current_valuation + round_size)
            
            benefits = [
                "Board seat guaranteed",
                "Set terms for round",
                "Information rights",
                "Pro-rata rights in future rounds",
                "Reputation signal to market"
            ]
            
        elif investment_type == InvestmentType.CO_LEAD:
            # Co-lead: split lead allocation
            our_allocation = round_size * benchmarks['lead_allocation'] * 0.5
            ownership_percent = min(investment_amount, our_allocation) / (current_valuation + round_size)
            benefits = [
                "Potential board observer seat",
                "Major investor rights",
                "Strong pro-rata rights"
            ]
            
        elif investment_type == InvestmentType.FOLLOW:
            # Follow investor
            max_follow = round_size * (1.0 - benchmarks['lead_allocation']) * 0.3  # Max 30% of non-lead
            our_allocation = min(investment_amount, max_follow)
            ownership_percent = our_allocation / (current_valuation + round_size)
            benefits = [
                "Lower diligence burden",
                "Ride coattails of lead investor",
                "Potential pro-rata rights if >$1M"
            ]
            
        else:  # PRO_RATA
            # Maintaining pro-rata from previous round
            previous_ownership = company_data.get('our_previous_ownership', 0.05)  # 5% default
            our_allocation = round_size * previous_ownership
            ownership_percent = previous_ownership * (current_valuation / (current_valuation + round_size))
            benefits = [
                "Maintain ownership percentage",
                "Existing investor advantages"
            ]
        
        # Account for option pool dilution
        # Note: Option pool dilution is handled in PrePostCapTable.calculate_full_cap_table_history
        # We don't apply it here to avoid double dilution
        # The 70% unexercised assumption (30% exercised) is applied at exit in PrePostCapTable._apply_option_exercise
        diluted_ownership = ownership_percent
        
        # Future dilution scenarios
        future_rounds = self._estimate_future_rounds(stage, current_valuation)
        
        return {
            'initial_ownership': ownership_percent * 100,
            'post_option_pool_ownership': diluted_ownership * 100,
            'investment_amount': investment_amount,
            'round_size': round_size,
            'our_allocation': our_allocation,
            'investment_type': investment_type.value,
            'benefits': benefits,
            'future_dilution_scenarios': future_rounds,
            'ownership_vs_fund': (investment_amount / fund_size) * 100,
            'reserve_recommendation': our_allocation * 2  # 2x reserves for follow-on
        }
    
    def calculate_bayesian_returns(
        self,
        ownership_percent: float,
        investment_amount: float,
        company_data: Dict,
        terms: InvestmentTerms
    ) -> Dict:
        """
        Calculate Bayesian return scenarios with liquidation preferences
        """
        
        stage = company_data.get('stage', 'series_a').lower().replace(' ', '_')
        
        # Define exit scenarios with probabilities (from SVB data)
        scenarios = self._generate_exit_scenarios(stage, company_data)
        
        returns = []
        
        for scenario in scenarios:
            exit_value = scenario.exit_value
            
            # Calculate return with liquidation preferences
            if scenario.scenario_type == "Liquidation" or exit_value < investment_amount * 2:
                # Liquidation preference kicks in
                if terms.participation:
                    # Participating preferred: get preference + share of remainder
                    pref_amount = investment_amount * terms.liquidation_preference
                    remainder = max(0, exit_value - pref_amount)
                    our_return = pref_amount + (remainder * ownership_percent)
                else:
                    # Non-participating: max of preference or ownership
                    pref_amount = investment_amount * terms.liquidation_preference
                    ownership_value = exit_value * ownership_percent
                    our_return = max(pref_amount, ownership_value)
            else:
                # Normal exit - ownership percentage applies
                our_return = exit_value * ownership_percent
                
                # Check for anti-dilution (ratchets) in down scenarios
                if scenario.scenario_type == "Down Round M&A" and terms.anti_dilution:
                    if terms.anti_dilution == "full_ratchet":
                        # Full ratchet protection
                        protected_return = investment_amount * 2  # Minimum 2x
                        our_return = max(our_return, protected_return)
                    elif terms.anti_dilution == "weighted_average":
                        # Weighted average protection (less aggressive)
                        protected_return = investment_amount * 1.5  # Minimum 1.5x
                        our_return = max(our_return, protected_return)
            
            # Calculate multiple and IRR
            multiple = our_return / investment_amount if investment_amount > 0 else 0
            irr = ((multiple ** (1 / scenario.years_to_exit)) - 1) if scenario.years_to_exit > 0 else 0
            
            returns.append({
                'scenario': scenario.name,
                'exit_value': exit_value,
                'our_return': our_return,
                'multiple': multiple,
                'irr': irr * 100,  # As percentage
                'probability': scenario.probability,
                'expected_value': our_return * scenario.probability
            })
        
        # Calculate probability-weighted expected return
        expected_return = sum(r['expected_value'] for r in returns)
        expected_multiple = expected_return / investment_amount if investment_amount > 0 else 0
        
        # Calculate risk metrics
        returns_array = np.array([r['our_return'] for r in returns])
        probabilities = np.array([r['probability'] for r in returns])
        
        # Standard deviation of returns
        variance = np.sum(probabilities * (returns_array - expected_return) ** 2)
        std_dev = np.sqrt(variance)
        
        # Downside scenarios (return < 1x)
        downside_probability = sum(r['probability'] for r in returns if r['multiple'] < 1.0)
        
        # Upside scenarios (return > 5x)
        upside_probability = sum(r['probability'] for r in returns if r['multiple'] > 5.0)
        
        return {
            'scenarios': returns,
            'expected_return': expected_return,
            'expected_multiple': expected_multiple,
            'standard_deviation': std_dev,
            'downside_probability': downside_probability * 100,
            'upside_probability': upside_probability * 100,
            'liquidation_preference_value': investment_amount * terms.liquidation_preference,
            'participation_rights': terms.participation
        }
    
    def calculate_fund_impact(
        self,
        investment_amount: float,
        expected_return: float,
        fund_size: float = 100_000_000,
        fund_target_multiple: float = 3.0
    ) -> Dict:
        """
        Calculate impact on fund returns
        """
        
        # Position sizing
        position_size_percent = (investment_amount / fund_size) * 100
        
        # Contribution to fund return
        fund_return_contribution = (expected_return - investment_amount) / fund_size
        
        # How many X return needed to return the fund
        x_to_return_fund = fund_size / investment_amount
        
        # Impact on fund multiple
        # Assuming this is investment #N in a portfolio of 30
        portfolio_size = 30
        average_other_return = 2.0  # Assume others return 2x
        
        # Calculate blended fund multiple
        other_investments_value = (fund_size - investment_amount) * average_other_return
        total_fund_value = other_investments_value + expected_return
        fund_multiple = total_fund_value / fund_size
        
        # Fund target achievement
        contribution_to_target = ((expected_return / investment_amount) - 1) * (investment_amount / fund_size)
        target_achievement_percent = (contribution_to_target / (fund_target_multiple - 1)) * 100
        
        return {
            'position_size_percent': position_size_percent,
            'fund_return_contribution': fund_return_contribution,
            'x_to_return_fund': x_to_return_fund,
            'projected_fund_multiple': fund_multiple,
            'target_achievement_percent': target_achievement_percent,
            'portfolio_concentration_risk': 'High' if position_size_percent > 5 else 'Medium' if position_size_percent > 2 else 'Low',
            'reserve_allocation': investment_amount * 2,  # Typical 2x reserves
            'total_capital_allocated': investment_amount * 3  # Initial + reserves
        }
    
    def _estimate_future_rounds(self, current_stage: str, current_valuation: float) -> List[Dict]:
        """
        Estimate future funding rounds and dilution
        """
        
        stages = ['seed', 'series_a', 'series_b', 'series_c', 'late_stage']
        try:
            current_index = stages.index(current_stage)
        except ValueError:
            current_index = 1  # Default to Series A
        
        future_rounds = []
        cumulative_dilution = 1.0
        
        for i in range(current_index + 1, len(stages)):
            stage = stages[i]
            benchmark = self.ROUND_BENCHMARKS[stage]
            
            # Estimate this round's dilution
            round_dilution = benchmark['typical_round_size'] / (benchmark['typical_pre_money'] + benchmark['typical_round_size'])
            option_dilution = benchmark['option_pool_expansion']
            total_round_dilution = round_dilution + option_dilution
            
            # Apply to our ownership
            cumulative_dilution *= (1.0 - total_round_dilution)
            
            future_rounds.append({
                'stage': stage,
                'estimated_dilution': total_round_dilution * 100,
                'ownership_after': cumulative_dilution * 100,
                'option_pool_expansion': option_dilution * 100
            })
        
        return future_rounds
    
    def _generate_exit_scenarios(self, stage: str, company_data: Dict) -> List[ExitScenario]:
        """
        Generate exit scenarios with probabilities based on stage
        """
        
        revenue = company_data.get('revenue', 2_000_000)
        growth_rate = company_data.get('growth_rate', 1.5)
        
        # Base exit probabilities by stage (from SVB data)
        stage_probabilities = {
            'seed': {
                'IPO': 0.05, 'Strategic M&A': 0.20, 'PE Buyout': 0.05,
                'Acquihire': 0.15, 'Liquidation': 0.20, 'Write-off': 0.35
            },
            'series_a': {
                'IPO': 0.10, 'Strategic M&A': 0.35, 'PE Buyout': 0.10,
                'Acquihire': 0.05, 'Liquidation': 0.10, 'Write-off': 0.30
            },
            'series_b': {
                'IPO': 0.20, 'Strategic M&A': 0.40, 'PE Buyout': 0.15,
                'Down Round M&A': 0.05, 'Liquidation': 0.05, 'Write-off': 0.15
            },
            'series_c': {
                'IPO': 0.30, 'Strategic M&A': 0.35, 'PE Buyout': 0.20,
                'Secondary': 0.10, 'Liquidation': 0.02, 'Write-off': 0.03
            }
        }
        
        probs = stage_probabilities.get(stage, stage_probabilities['series_a'])
        
        scenarios = []
        
        for scenario_type, probability in probs.items():
            if probability == 0:
                continue
                
            # Calculate exit value based on scenario
            if scenario_type == 'IPO':
                # IPOs at 10x forward revenue
                years_to_exit = 5
                future_revenue = revenue * ((1 + growth_rate) ** years_to_exit)
                exit_value = future_revenue * 10
                
            elif scenario_type == 'Strategic M&A':
                # M&A at 5x forward revenue
                years_to_exit = 3
                future_revenue = revenue * ((1 + growth_rate) ** years_to_exit)
                exit_value = future_revenue * 5
                
            elif scenario_type == 'PE Buyout':
                # PE at 4x forward revenue
                years_to_exit = 3
                future_revenue = revenue * ((1 + growth_rate) ** years_to_exit)
                exit_value = future_revenue * 4
                
            elif scenario_type == 'Down Round M&A':
                # Distressed sale at 1.5x current revenue
                exit_value = revenue * 1.5
                years_to_exit = 2
                
            elif scenario_type == 'Acquihire':
                # Team value only
                team_size = company_data.get('team_size', 20)
                exit_value = team_size * 1_000_000  # $1M per engineer
                years_to_exit = 2
                
            elif scenario_type == 'Liquidation':
                # Return some capital
                exit_value = company_data.get('cash', 5_000_000) * 0.5
                years_to_exit = 2
                
            elif scenario_type == 'Secondary':
                # Secondary sale at current valuation
                exit_value = company_data.get('valuation', revenue * 3)
                years_to_exit = 2
                
            else:  # Write-off
                exit_value = 0
                years_to_exit = 3
            
            scenarios.append(ExitScenario(
                name=scenario_type,
                exit_value=exit_value,
                probability=probability,
                years_to_exit=years_to_exit,
                scenario_type=scenario_type
            ))
        
        return scenarios