"""
Hybrid PWERM: Simple Bear/Base/Bull with Deep Analysis Capability
Combines quick 3-scenario display with full matrix for detailed analysis
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Single scenario result"""
    name: str
    exit_value: float
    probability: float
    irr: float
    multiple: float
    waterfall_impact: str  # How waterfall affects this scenario
    key_driver: str  # What drives this outcome


class HybridPWERM:
    """
    Smart PWERM that adapts based on context:
    - Quick 3 scenarios for grid display
    - Full analysis when drilling down
    - Funding path-aware probability adjustments
    """
    
    def calculate_quick_scenarios(
        self,
        company_data: Dict,
        investment_amount: float = None
    ) -> Dict[str, ScenarioResult]:
        """
        Quick Bear/Base/Bull for grid display
        Uses funding path to intelligently set ranges
        """
        
        # Extract key data
        last_valuation = company_data.get('last_round_valuation', 100_000_000)
        funding_rounds = company_data.get('funding_rounds', [])
        growth_rate = company_data.get('growth_rate', 1.5)
        burn_rate = company_data.get('burn_rate', 0)
        runway = company_data.get('runway_months', 18)
        
        # Determine stage from funding path
        stage = self._determine_stage(funding_rounds)
        
        # INTELLIGENT SCENARIO GENERATION based on stage and metrics
        scenarios = {}
        
        # BEAR CASE - Tailored by stage
        if stage == 'early':  # Pre-seed/Seed
            # High liquidation risk
            bear_multiple = 0.3 if runway < 12 else 0.5
            bear_outcome = 'Liquidation' if runway < 6 else 'Acquihire'
            bear_waterfall = 'Common likely wiped out'
        elif stage == 'growth':  # Series A/B
            # Modest exit or down round
            bear_multiple = 0.7
            bear_outcome = 'Down round acquisition'
            bear_waterfall = 'Liquidation prefs matter significantly'
        else:  # Late stage C+
            # Below expectations but still substantial
            bear_multiple = 0.8
            bear_outcome = 'Disappointing exit'
            bear_waterfall = 'IPO ratchets may trigger'
        
        scenarios['bear'] = ScenarioResult(
            name=f"Bear: {bear_outcome}",
            exit_value=last_valuation * bear_multiple,
            probability=0.25,
            irr=self._calculate_irr(investment_amount or last_valuation * 0.1, 
                                   last_valuation * bear_multiple, 3),
            multiple=bear_multiple,
            waterfall_impact=bear_waterfall,
            key_driver=f"Runway: {runway} months"
        )
        
        # BASE CASE - Most likely outcome by stage
        if stage == 'early':
            base_multiple = 2.0 if growth_rate > 2 else 1.5
            base_outcome = 'Strategic acquisition'
            base_waterfall = 'Preferences covered, common gets some'
            base_time = 3
        elif stage == 'growth':
            base_multiple = 3.0
            base_outcome = 'Growth PE exit'
            base_waterfall = 'Good returns for all'
            base_time = 4
        else:
            base_multiple = 2.5
            base_outcome = 'Midcap IPO'
            base_waterfall = 'Preferences convert to common'
            base_time = 2
        
        scenarios['base'] = ScenarioResult(
            name=f"Base: {base_outcome}",
            exit_value=last_valuation * base_multiple,
            probability=0.50,
            irr=self._calculate_irr(investment_amount or last_valuation * 0.1,
                                   last_valuation * base_multiple, base_time),
            multiple=base_multiple,
            waterfall_impact=base_waterfall,
            key_driver=f"Growth: {growth_rate*100:.0f}%"
        )
        
        # BULL CASE - Best realistic outcome
        if stage == 'early':
            # Breakout success possible
            bull_multiple = 10.0 if growth_rate > 3 else 5.0
            bull_outcome = 'Hot acquisition'
            bull_waterfall = 'Everyone wins'
            bull_time = 4
        elif stage == 'growth':
            bull_multiple = 8.0
            bull_outcome = 'Competitive bidding war'
            bull_waterfall = 'Waterfall less relevant'
            bull_time = 3
        else:
            bull_multiple = 5.0
            bull_outcome = 'Successful IPO'
            bull_waterfall = 'All convert to common'
            bull_time = 2
        
        scenarios['bull'] = ScenarioResult(
            name=f"Bull: {bull_outcome}",
            exit_value=last_valuation * bull_multiple,
            probability=0.25,
            irr=self._calculate_irr(investment_amount or last_valuation * 0.1,
                                   last_valuation * bull_multiple, bull_time),
            multiple=bull_multiple,
            waterfall_impact=bull_waterfall,
            key_driver='Market timing + execution'
        )
        
        return scenarios
    
    def calculate_deep_analysis(
        self,
        company_data: Dict,
        num_scenarios: int = 20
    ) -> Dict[str, Any]:
        """
        Deep analysis with intelligent scenario selection
        Picks most relevant scenarios from full matrix based on company profile
        """
        
        funding_rounds = company_data.get('funding_rounds', [])
        stage = self._determine_stage(funding_rounds)
        growth_rate = company_data.get('growth_rate', 1.5)
        revenue = company_data.get('revenue', 0)
        burn_rate = company_data.get('burn_rate', 0)
        
        # SELECT RELEVANT SCENARIOS from the full matrix
        selected_scenarios = []
        
        # Based on stage, select appropriate outcome types
        if stage == 'early':
            # Focus on liquidation, acquihire, small acquisitions
            outcome_weights = {
                'Liquidation': 0.30,
                'Acquihire': 0.25,
                'Strategic Acquisition <$100M': 0.25,
                'Strategic Acquisition $100-300M': 0.15,
                'IPO': 0.05
            }
        elif stage == 'growth':
            outcome_weights = {
                'Liquidation': 0.10,
                'Strategic Acquisition $100-300M': 0.30,
                'Strategic Acquisition $300-500M': 0.25,
                'PE Buyout': 0.20,
                'IPO <$1B': 0.15
            }
        else:  # Late stage
            outcome_weights = {
                'Strategic Acquisition $500M+': 0.20,
                'PE Buyout': 0.25,
                'IPO $1-2B': 0.30,
                'IPO $2B+': 0.20,
                'Liquidation': 0.05
            }
        
        # Generate scenarios based on weights
        for outcome_type, weight in outcome_weights.items():
            num_for_type = max(1, int(num_scenarios * weight))
            
            for i in range(num_for_type):
                selected_scenarios.append(self._generate_scenario(
                    outcome_type,
                    company_data,
                    stage
                ))
        
        # Calculate probability-weighted value
        total_value = sum(s['probability'] * s['present_value'] for s in selected_scenarios)
        
        # Group by outcome type for visualization
        outcome_groups = {}
        for scenario in selected_scenarios:
            outcome = scenario['outcome_type']
            if outcome not in outcome_groups:
                outcome_groups[outcome] = {
                    'scenarios': [],
                    'total_probability': 0,
                    'expected_value': 0
                }
            outcome_groups[outcome]['scenarios'].append(scenario)
            outcome_groups[outcome]['total_probability'] += scenario['probability']
            outcome_groups[outcome]['expected_value'] += scenario['probability'] * scenario['exit_value']
        
        return {
            'total_scenarios': len(selected_scenarios),
            'expected_value': total_value,
            'outcome_groups': outcome_groups,
            'top_scenarios': sorted(selected_scenarios, 
                                   key=lambda x: x['probability'], 
                                   reverse=True)[:5],
            'methodology': 'Intelligent scenario selection based on stage and metrics'
        }
    
    def _determine_stage(self, funding_rounds: List[Dict]) -> str:
        """Determine company stage from funding history"""
        if not funding_rounds:
            return 'early'
        
        round_types = [r.get('round', '').lower() for r in funding_rounds]
        
        if any('d' in r or 'e' in r or 'f' in r for r in round_types):
            return 'late'
        elif any('b' in r or 'c' in r for r in round_types):
            return 'growth'
        else:
            return 'early'
    
    def _calculate_irr(self, investment: float, exit_value: float, years: float) -> float:
        """Calculate IRR for a scenario"""
        if investment <= 0 or exit_value <= 0 or years <= 0:
            return 0
        return (pow(exit_value / investment, 1/years) - 1) * 100
    
    def _generate_scenario(
        self,
        outcome_type: str,
        company_data: Dict,
        stage: str
    ) -> Dict[str, Any]:
        """Generate a specific scenario based on outcome type"""
        
        last_valuation = company_data.get('last_round_valuation', 100_000_000)
        
        # Define exit value ranges by outcome type
        if 'Liquidation' in outcome_type:
            exit_value = last_valuation * np.random.uniform(0.1, 0.3)
            time_to_exit = 1.0
            probability = 0.15
        elif 'Acquihire' in outcome_type:
            exit_value = np.random.uniform(5_000_000, 25_000_000)
            time_to_exit = 1.5
            probability = 0.10
        elif '<$100M' in outcome_type:
            exit_value = np.random.uniform(50_000_000, 100_000_000)
            time_to_exit = 2.5
            probability = 0.15
        elif '$100-300M' in outcome_type:
            exit_value = np.random.uniform(100_000_000, 300_000_000)
            time_to_exit = 3.0
            probability = 0.20
        elif '$300-500M' in outcome_type:
            exit_value = np.random.uniform(300_000_000, 500_000_000)
            time_to_exit = 3.5
            probability = 0.15
        elif '$500M+' in outcome_type:
            exit_value = np.random.uniform(500_000_000, 1_000_000_000)
            time_to_exit = 4.0
            probability = 0.10
        elif 'PE Buyout' in outcome_type:
            exit_value = last_valuation * np.random.uniform(2.5, 4.0)
            time_to_exit = 4.0
            probability = 0.15
        elif 'IPO <$1B' in outcome_type:
            exit_value = np.random.uniform(500_000_000, 1_000_000_000)
            time_to_exit = 5.0
            probability = 0.08
        elif 'IPO $1-2B' in outcome_type:
            exit_value = np.random.uniform(1_000_000_000, 2_000_000_000)
            time_to_exit = 6.0
            probability = 0.05
        elif 'IPO $2B+' in outcome_type:
            exit_value = np.random.uniform(2_000_000_000, 5_000_000_000)
            time_to_exit = 7.0
            probability = 0.02
        else:
            exit_value = last_valuation * 2
            time_to_exit = 3.0
            probability = 0.10
        
        # Adjust probability based on company metrics
        growth_rate = company_data.get('growth_rate', 1.5)
        if growth_rate > 2.0 and 'IPO' in outcome_type:
            probability *= 1.5
        elif growth_rate < 1.2 and 'Liquidation' in outcome_type:
            probability *= 1.5
        
        # Calculate present value (simple discount)
        discount_rate = 0.25  # 25% discount rate
        present_value = exit_value / ((1 + discount_rate) ** time_to_exit)
        
        return {
            'outcome_type': outcome_type,
            'exit_value': exit_value,
            'time_to_exit': time_to_exit,
            'probability': probability,
            'present_value': present_value,
            'description': f"{outcome_type} in {time_to_exit:.1f} years at ${exit_value/1_000_000:.0f}M"
        }


def get_smart_scenarios(company_data: Dict, quick: bool = True) -> Any:
    """
    Main entry point - returns either quick 3 scenarios or deep analysis
    
    Args:
        company_data: Company information including funding history
        quick: If True, returns bear/base/bull. If False, returns deep analysis
    """
    pwerm = HybridPWERM()
    
    if quick:
        return pwerm.calculate_quick_scenarios(company_data)
    else:
        return pwerm.calculate_deep_analysis(company_data)