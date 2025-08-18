"""
Liquidation Preference Calculator for PWERM
Handles complex cap table structures and waterfall calculations
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class LiquidationType(Enum):
    NON_PARTICIPATING = "non_participating"  # 1x, done
    PARTICIPATING = "participating"          # 1x + pro rata
    CAPPED_PARTICIPATING = "capped_participating"  # 1x + pro rata up to cap

@dataclass
class FundingRound:
    """Represents a single funding round"""
    round_name: str  # Seed, Series A, B, C, etc.
    date: datetime
    amount_raised: float
    pre_money_valuation: float
    post_money_valuation: float
    liquidation_multiple: float  # Usually 1x, sometimes 2x or more
    liquidation_type: LiquidationType
    participation_cap: Optional[float]  # For capped participating (e.g., 3x)
    shares_issued: int
    share_price: float
    investors: List[Dict[str, float]]  # {investor_name: amount}
    
    @property
    def liquidation_preference(self) -> float:
        """Total liquidation preference for this round"""
        return self.amount_raised * self.liquidation_multiple

class CapTable:
    """Complete cap table with all funding rounds and ownership"""
    
    def __init__(self):
        self.funding_rounds: List[FundingRound] = []
        self.common_shares: Dict[str, int] = {}  # Founders, employees
        self.option_pool: int = 0
        self.total_shares: int = 0
        
    def add_funding_round(self, round_data: Dict) -> FundingRound:
        """Add a new funding round to the cap table"""
        
        # Calculate share price and shares issued
        pre_money = round_data['pre_money_valuation']
        amount = round_data['amount_raised']
        post_money = pre_money + amount
        
        # Get existing shares before this round
        existing_shares = self.total_shares
        
        # Calculate ownership percentage and new shares
        ownership_pct = amount / post_money
        new_shares = int(existing_shares * ownership_pct / (1 - ownership_pct))
        share_price = amount / new_shares
        
        # Create funding round
        funding_round = FundingRound(
            round_name=round_data['round_name'],
            date=round_data.get('date', datetime.now()),
            amount_raised=amount,
            pre_money_valuation=pre_money,
            post_money_valuation=post_money,
            liquidation_multiple=round_data.get('liquidation_multiple', 1.0),
            liquidation_type=LiquidationType(round_data.get('liquidation_type', 'non_participating')),
            participation_cap=round_data.get('participation_cap'),
            shares_issued=new_shares,
            share_price=share_price,
            investors=round_data.get('investors', {})
        )
        
        self.funding_rounds.append(funding_round)
        self.total_shares += new_shares
        
        return funding_round
    
    def calculate_ownership(self) -> Dict[str, float]:
        """Calculate current ownership percentages"""
        ownership = {}
        
        # Common shareholders
        for holder, shares in self.common_shares.items():
            ownership[holder] = shares / self.total_shares
            
        # Preferred shareholders by round
        for round in self.funding_rounds:
            round_ownership = round.shares_issued / self.total_shares
            for investor, amount in round.investors.items():
                investor_pct = amount / round.amount_raised
                ownership[f"{investor} ({round.round_name})"] = round_ownership * investor_pct
                
        return ownership

class LiquidationWaterfall:
    """Calculate how proceeds are distributed in exit scenarios"""
    
    def __init__(self, cap_table: CapTable):
        self.cap_table = cap_table
        
    def calculate_returns(self, exit_value: float) -> Dict[str, Dict[str, float]]:
        """
        Calculate returns for all shareholders at given exit value
        Returns detailed breakdown by investor and round
        """
        
        remaining_proceeds = exit_value
        distributions = {}
        
        # Step 1: Pay liquidation preferences in reverse chronological order (last money in, first money out)
        for round in reversed(self.cap_table.funding_rounds):
            if remaining_proceeds <= 0:
                break
                
            # Pay the liquidation preference
            pref_amount = min(round.liquidation_preference, remaining_proceeds)
            
            # Distribute to investors in this round
            for investor, investment in round.investors.items():
                investor_share = investment / round.amount_raised
                investor_pref = pref_amount * investor_share
                
                key = f"{investor} ({round.round_name})"
                distributions[key] = distributions.get(key, {})
                distributions[key]['preference'] = investor_pref
                distributions[key]['investment'] = investment
                
            remaining_proceeds -= pref_amount
        
        # Step 2: If there's money left, distribute based on participation rights
        if remaining_proceeds > 0:
            participating_shares = 0
            non_participating_shares = 0
            
            # Calculate participating vs non-participating shares
            for round in self.cap_table.funding_rounds:
                if round.liquidation_type == LiquidationType.NON_PARTICIPATING:
                    # These investors must choose: preference OR participation
                    # We need to check if participation would be better
                    participation_value = (round.shares_issued / self.cap_table.total_shares) * exit_value
                    if participation_value > round.liquidation_preference:
                        # They convert to common
                        participating_shares += round.shares_issued
                    else:
                        # They keep preference (already paid)
                        non_participating_shares += round.shares_issued
                else:
                    # Participating preferred get both
                    participating_shares += round.shares_issued
            
            # Add common shares
            common_shares = sum(self.cap_table.common_shares.values()) + self.cap_table.option_pool
            participating_shares += common_shares
            
            # Distribute remaining proceeds pro-rata
            if participating_shares > 0:
                per_share_value = remaining_proceeds / participating_shares
                
                # Distribute to preferred shareholders who are participating
                for round in self.cap_table.funding_rounds:
                    if round.liquidation_type != LiquidationType.NON_PARTICIPATING:
                        round_proceeds = round.shares_issued * per_share_value
                        
                        # Check participation cap
                        if round.liquidation_type == LiquidationType.CAPPED_PARTICIPATING:
                            max_return = round.amount_raised * round.participation_cap
                            already_received = round.liquidation_preference
                            round_proceeds = min(round_proceeds, max_return - already_received)
                        
                        # Distribute to investors
                        for investor, investment in round.investors.items():
                            investor_share = investment / round.amount_raised
                            investor_proceeds = round_proceeds * investor_share
                            
                            key = f"{investor} ({round.round_name})"
                            distributions[key] = distributions.get(key, {})
                            distributions[key]['participation'] = distributions[key].get('participation', 0) + investor_proceeds
                
                # Distribute to common shareholders
                for holder, shares in self.cap_table.common_shares.items():
                    distributions[holder] = {
                        'common': shares * per_share_value,
                        'investment': 0  # Common usually doesn't have cash investment
                    }
        
        # Step 3: Calculate returns and multiples
        results = {}
        for investor, amounts in distributions.items():
            total_return = sum(amounts.get(k, 0) for k in ['preference', 'participation', 'common'])
            investment = amounts.get('investment', 0)
            
            results[investor] = {
                'proceeds': total_return,
                'investment': investment,
                'multiple': total_return / investment if investment > 0 else 0,
                'irr': self._calculate_irr(investment, total_return, 5),  # Assume 5 year hold
                'breakdown': amounts
            }
            
        return results
    
    def find_conversion_threshold(self) -> float:
        """
        Find the exit value where preferred shareholders start converting to common
        This is a key insight for understanding incentive alignment
        """
        thresholds = []
        
        for round in self.cap_table.funding_rounds:
            if round.liquidation_type == LiquidationType.NON_PARTICIPATING:
                # They convert when: (shares/total_shares) * exit_value > liquidation_preference
                ownership_pct = round.shares_issued / self.cap_table.total_shares
                threshold = round.liquidation_preference / ownership_pct
                thresholds.append({
                    'round': round.round_name,
                    'threshold': threshold,
                    'ownership': ownership_pct,
                    'preference': round.liquidation_preference
                })
        
        return sorted(thresholds, key=lambda x: x['threshold'])
    
    def generate_waterfall_chart_data(self, exit_values: List[float]) -> Dict:
        """
        Generate data for visualizing the waterfall at different exit values
        """
        chart_data = {
            'exit_values': exit_values,
            'investor_returns': {},
            'common_returns': {}
        }
        
        for exit_value in exit_values:
            returns = self.calculate_returns(exit_value)
            
            for investor, data in returns.items():
                if investor not in chart_data['investor_returns']:
                    chart_data['investor_returns'][investor] = []
                chart_data['investor_returns'][investor].append(data['proceeds'])
        
        return chart_data
    
    def _calculate_irr(self, investment: float, return_value: float, years: float) -> float:
        """Simple IRR calculation"""
        if investment <= 0 or return_value <= 0:
            return 0
        return (return_value / investment) ** (1 / years) - 1

class LiquidationScenarioAnalyzer:
    """
    Analyze how liquidation preferences affect returns across PWERM scenarios
    """
    
    def __init__(self, cap_table: CapTable):
        self.cap_table = cap_table
        self.waterfall = LiquidationWaterfall(cap_table)
        
    def analyze_scenario_returns(self, scenarios: List[Dict]) -> List[Dict]:
        """
        For each PWERM scenario, calculate actual investor returns after liquidation preferences
        """
        enhanced_scenarios = []
        
        for scenario in scenarios:
            exit_value = scenario['value']
            
            # Calculate returns for all investors
            returns = self.waterfall.calculate_returns(exit_value)
            
            # Add liquidation preference analysis to scenario
            scenario['liquidation_analysis'] = {
                'investor_returns': returns,
                'common_dilution': self._calculate_common_dilution(exit_value),
                'preference_stack': sum(r.liquidation_preference for r in self.cap_table.funding_rounds),
                'participation_threshold': self._find_participation_threshold(exit_value),
                'effective_ownership': self._calculate_effective_ownership(exit_value)
            }
            
            enhanced_scenarios.append(scenario)
            
        return enhanced_scenarios
    
    def _calculate_common_dilution(self, exit_value: float) -> float:
        """
        Calculate how much common shareholders are diluted by preferences
        """
        # What would common get with no preferences (pure pro-rata)?
        common_shares = sum(self.cap_table.common_shares.values())
        common_ownership = common_shares / self.cap_table.total_shares
        theoretical_common = exit_value * common_ownership
        
        # What do they actually get?
        returns = self.waterfall.calculate_returns(exit_value)
        actual_common = sum(
            data['proceeds'] 
            for investor, data in returns.items() 
            if investor in self.cap_table.common_shares
        )
        
        # Dilution percentage
        if theoretical_common > 0:
            dilution = 1 - (actual_common / theoretical_common)
            return max(0, dilution)
        return 0
    
    def _find_participation_threshold(self, exit_value: float) -> Dict:
        """
        Find key thresholds where investor behavior changes
        """
        preference_stack = sum(r.liquidation_preference for r in self.cap_table.funding_rounds)
        
        return {
            'preference_covered': exit_value > preference_stack,
            'common_participation_starts': exit_value - preference_stack if exit_value > preference_stack else 0,
            'conversion_points': self.waterfall.find_conversion_threshold()
        }
    
    def _calculate_effective_ownership(self, exit_value: float) -> Dict[str, float]:
        """
        Calculate effective ownership (proceeds / exit_value) vs paper ownership
        """
        returns = self.waterfall.calculate_returns(exit_value)
        
        effective = {}
        for investor, data in returns.items():
            effective[investor] = data['proceeds'] / exit_value if exit_value > 0 else 0
            
        return effective

# Example usage
def create_example_cap_table() -> CapTable:
    """Create a realistic cap table example"""
    
    cap_table = CapTable()
    
    # Founders
    cap_table.common_shares = {
        'Founder A': 3_000_000,
        'Founder B': 2_000_000,
        'Employees': 1_000_000
    }
    cap_table.option_pool = 1_000_000
    cap_table.total_shares = 7_000_000  # Starting shares
    
    # Seed Round
    cap_table.add_funding_round({
        'round_name': 'Seed',
        'amount_raised': 2_000_000,
        'pre_money_valuation': 8_000_000,
        'liquidation_multiple': 1.0,
        'liquidation_type': 'non_participating',
        'investors': {
            'Angel Fund': 1_000_000,
            'Seed VC': 1_000_000
        }
    })
    
    # Series A
    cap_table.add_funding_round({
        'round_name': 'Series A',
        'amount_raised': 10_000_000,
        'pre_money_valuation': 30_000_000,
        'liquidation_multiple': 1.0,
        'liquidation_type': 'non_participating',
        'investors': {
            'Tier 1 VC': 7_000_000,
            'Seed VC': 3_000_000  # Pro-rata
        }
    })
    
    # Series B
    cap_table.add_funding_round({
        'round_name': 'Series B',
        'amount_raised': 25_000_000,
        'pre_money_valuation': 75_000_000,
        'liquidation_multiple': 1.0,
        'liquidation_type': 'participating',  # Participating preferred!
        'participation_cap': 3.0,  # 3x cap
        'investors': {
            'Growth Fund': 20_000_000,
            'Tier 1 VC': 5_000_000  # Pro-rata
        }
    })
    
    return cap_table