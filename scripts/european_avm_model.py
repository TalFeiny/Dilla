"""
European AVM (Automated Valuation Model)
Adjusts for European market dynamics: higher cost of capital, lower graduation rates
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class EuropeanMarketParameters:
    """European market-specific parameters"""
    
    # Cost of capital adjustments
    risk_free_rate: float = 0.04  # ECB rates typically higher
    equity_risk_premium: float = 0.09  # Higher than US (7%)
    size_premium: float = 0.03  # Liquidity discount
    
    # Graduation rates - European reality
    graduation_rates = {
        'Seed_to_A': 0.25,      # vs 0.35 in US
        'A_to_B': 0.35,         # vs 0.45 in US  
        'B_to_C': 0.40,         # vs 0.50 in US
        'C_to_Exit': 0.30,      # vs 0.40 in US
        'IPO_probability': 0.05  # vs 0.15 in US - limited IPO markets
    }
    
    # Exit multiple discounts
    exit_multiple_discount: float = 0.75  # European exits typically 25% lower
    
    # Time adjustments
    time_between_rounds: float = 2.0  # vs 1.5 years in US
    time_to_exit: float = 8.0  # vs 6.0 years in US

class EuropeanAVM:
    """
    Automated Valuation Model adjusted for European markets
    """
    
    def __init__(self):
        self.params = EuropeanMarketParameters()
        
    def calculate_company_value(self, company_data: Dict) -> Dict:
        """
        Calculate expected value using European graduation rates
        """
        
        # Extract company data
        current_arr = company_data.get('arr', 5_000_000)
        growth_rate = company_data.get('growth_rate', 0.40)
        stage = company_data.get('stage', 'Series A')
        sector = company_data.get('sector', 'SaaS')
        country = company_data.get('country', 'UK')
        
        # Calculate cost of capital
        wacc = self._calculate_european_wacc(stage, sector, country)
        
        # Generate graduation path scenarios
        scenarios = self._generate_graduation_scenarios(
            current_arr, growth_rate, stage, sector
        )
        
        # Calculate probability-weighted value
        expected_value = 0
        scenario_details = []
        
        for scenario in scenarios:
            # Discount future value to present
            pv = scenario['exit_value'] / ((1 + wacc) ** scenario['years_to_exit'])
            weighted_value = pv * scenario['probability']
            expected_value += weighted_value
            
            scenario['present_value'] = pv
            scenario['weighted_contribution'] = weighted_value
            scenario['wacc_used'] = wacc
            scenario_details.append(scenario)
        
        return {
            'expected_value': expected_value,
            'wacc': wacc,
            'scenarios': scenario_details,
            'european_adjustments': {
                'graduation_discount': self._calculate_graduation_discount(stage),
                'exit_multiple_discount': self.params.exit_multiple_discount,
                'time_premium': self.params.time_between_rounds / 1.5  # vs US
            }
        }
    
    def _calculate_european_wacc(self, stage: str, sector: str, country: str) -> float:
        """
        Calculate Weighted Average Cost of Capital for European startups
        """
        
        # Base cost of equity
        cost_of_equity = (self.params.risk_free_rate + 
                         self.params.equity_risk_premium + 
                         self.params.size_premium)
        
        # Stage risk adjustment
        stage_premiums = {
            'Seed': 0.15,      # +15% for seed
            'Series A': 0.10,   # +10% for A
            'Series B': 0.06,   # +6% for B
            'Series C+': 0.03   # +3% for late stage
        }
        cost_of_equity += stage_premiums.get(stage, 0.08)
        
        # Country risk adjustment
        country_premiums = {
            'UK': 0.00,         # Baseline
            'Germany': -0.01,   # Slightly lower risk
            'France': 0.01,     # Slightly higher
            'Spain': 0.03,      # Higher risk
            'Italy': 0.03,      # Higher risk
            'Netherlands': -0.01,
            'Sweden': -0.01,
            'Eastern EU': 0.05  # Significantly higher
        }
        cost_of_equity += country_premiums.get(country, 0.02)
        
        # Sector adjustment
        if sector in ['DeepTech', 'Biotech', 'Hardware']:
            cost_of_equity += 0.03  # Higher risk sectors
        elif sector in ['SaaS', 'Marketplace']:
            cost_of_equity -= 0.01  # Lower risk, proven models
        
        return cost_of_equity
    
    def _generate_graduation_scenarios(self, current_arr: float, growth_rate: float, 
                                     stage: str, sector: str) -> List[Dict]:
        """
        Generate scenarios based on European graduation rates
        """
        scenarios = []
        
        # Map current stage to graduation path
        stage_map = {
            'Seed': ['Seed_to_A', 'A_to_B', 'B_to_C', 'C_to_Exit'],
            'Series A': ['A_to_B', 'B_to_C', 'C_to_Exit'],
            'Series B': ['B_to_C', 'C_to_Exit'],
            'Series C+': ['C_to_Exit']
        }
        
        remaining_stages = stage_map.get(stage, ['A_to_B', 'B_to_C', 'C_to_Exit'])
        
        # Calculate cumulative graduation probability
        cumulative_prob = 1.0
        years_elapsed = 0
        
        # Scenario 1: Full graduation path
        for i, stage_transition in enumerate(remaining_stages):
            grad_rate = self.params.graduation_rates[stage_transition]
            cumulative_prob *= grad_rate
            years_elapsed += self.params.time_between_rounds
        
        # Project ARR with European growth decay
        projected_arr = self._project_arr_with_decay(
            current_arr, growth_rate, years_elapsed, 'european'
        )
        
        # Calculate exit value with European multiples
        exit_multiple = self._get_european_exit_multiple(projected_arr, sector)
        
        scenarios.append({
            'name': 'Full Graduation to Exit',
            'probability': cumulative_prob,
            'exit_value': projected_arr * exit_multiple,
            'years_to_exit': years_elapsed,
            'projected_arr': projected_arr,
            'exit_multiple': exit_multiple,
            'path': ' → '.join(remaining_stages)
        })
        
        # Scenario 2: Early M&A exit (more common in Europe)
        if len(remaining_stages) > 1:
            early_exit_prob = 0.30  # 30% chance of early exit
            early_years = self.params.time_between_rounds * 1.5
            early_arr = self._project_arr_with_decay(
                current_arr, growth_rate, early_years, 'european'
            )
            early_multiple = exit_multiple * 0.7  # Discount for early exit
            
            scenarios.append({
                'name': 'Early Strategic Acquisition',
                'probability': early_exit_prob,
                'exit_value': early_arr * early_multiple,
                'years_to_exit': early_years,
                'projected_arr': early_arr,
                'exit_multiple': early_multiple,
                'path': 'Early M&A Exit'
            })
        
        # Scenario 3: Stagnation/Zombie (common in Europe)
        zombie_prob = 0.25  # 25% become zombies
        zombie_years = 6.0
        zombie_arr = self._project_arr_with_decay(
            current_arr, growth_rate * 0.3, zombie_years, 'zombie'
        )
        zombie_multiple = 2.5  # Low multiple for struggling companies
        
        scenarios.append({
            'name': 'Stagnation/Zombie',
            'probability': zombie_prob,
            'exit_value': zombie_arr * zombie_multiple,
            'years_to_exit': zombie_years,
            'projected_arr': zombie_arr,
            'exit_multiple': zombie_multiple,
            'path': 'Flatline → Acquihire'
        })
        
        # Scenario 4: Failure
        failure_prob = 1.0 - sum(s['probability'] for s in scenarios)
        scenarios.append({
            'name': 'Failure/Liquidation',
            'probability': max(0.15, failure_prob),  # At least 15% failure rate
            'exit_value': 0,
            'years_to_exit': 3.0,
            'projected_arr': 0,
            'exit_multiple': 0,
            'path': 'Shutdown'
        })
        
        # Normalize probabilities
        total_prob = sum(s['probability'] for s in scenarios)
        for s in scenarios:
            s['probability'] /= total_prob
        
        return scenarios
    
    def _project_arr_with_decay(self, current_arr: float, initial_growth: float, 
                               years: float, growth_type: str) -> float:
        """
        Project ARR with European growth decay patterns
        """
        
        if growth_type == 'zombie':
            # Flat or declining growth
            return current_arr * (1 + 0.1) ** years  # 10% total growth
        
        # European companies typically see faster growth decay
        decay_rates = {
            'european': 0.80,  # 20% annual decay in growth rate
            'us': 0.85  # 15% annual decay (for comparison)
        }
        
        decay_rate = decay_rates.get(growth_type, 0.80)
        
        projected_arr = current_arr
        current_growth = initial_growth
        
        for year in range(int(years)):
            projected_arr *= (1 + current_growth)
            current_growth *= decay_rate  # Apply decay
            
        # Handle fractional year
        if years % 1 > 0:
            projected_arr *= (1 + current_growth * (years % 1))
        
        return projected_arr
    
    def _get_european_exit_multiple(self, arr: float, sector: str) -> float:
        """
        Get exit multiples adjusted for European markets
        """
        
        # Base multiples by ARR size (European reality)
        if arr < 10_000_000:  # <€10M
            base_multiple = 3.5
        elif arr < 50_000_000:  # €10-50M
            base_multiple = 5.0
        elif arr < 100_000_000:  # €50-100M
            base_multiple = 6.5
        else:  # >€100M
            base_multiple = 8.0
        
        # Sector adjustments
        sector_multipliers = {
            'SaaS': 1.0,
            'Marketplace': 0.9,
            'Fintech': 1.1,
            'DeepTech': 0.8,  # Lower multiples despite potential
            'AdTech': 0.7,
            'E-commerce': 0.6
        }
        
        sector_mult = sector_multipliers.get(sector, 0.85)
        
        return base_multiple * sector_mult * self.params.exit_multiple_discount
    
    def _calculate_graduation_discount(self, stage: str) -> float:
        """
        Calculate how much European graduation rates discount value vs US
        """
        
        us_rates = {
            'Seed_to_A': 0.35,
            'A_to_B': 0.45,
            'B_to_C': 0.50,
            'C_to_Exit': 0.40
        }
        
        eu_rates = self.params.graduation_rates
        
        # Calculate cumulative probability difference
        stages = ['Seed_to_A', 'A_to_B', 'B_to_C', 'C_to_Exit']
        
        if stage == 'Seed':
            relevant_stages = stages
        elif stage == 'Series A':
            relevant_stages = stages[1:]
        elif stage == 'Series B':
            relevant_stages = stages[2:]
        else:
            relevant_stages = stages[3:]
        
        us_cumulative = 1.0
        eu_cumulative = 1.0
        
        for s in relevant_stages:
            us_cumulative *= us_rates.get(s, 0.4)
            eu_cumulative *= eu_rates.get(s, 0.3)
        
        return eu_cumulative / us_cumulative if us_cumulative > 0 else 0.7