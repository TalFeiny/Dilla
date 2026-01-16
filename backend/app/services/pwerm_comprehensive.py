"""
Comprehensive PWERM Implementation with Full Exit Scenario Matrix
Combines funding path history with exit probabilities
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Base valuation for template scenarios (will be scaled to company's actual valuation)
BASE_VALUATION = 100_000_000  # $100M base for Series A company

@dataclass
class ComprehensivePWERMScenario:
    """Full PWERM scenario with funding path"""
    scenario_type: str  # Liquidation, IPO, Acquisition, etc.
    funding_path: str  # Pre-seed, Seed, A, B, C, D, E, F with extensions/debt
    exit_value_range: Tuple[float, float]  # Min and max exit value
    exit_description: str  # Detailed description
    probability: float
    time_to_exit: float  # Years
    present_value: float = 0  # Calculated
    
    @property
    def exit_value(self) -> float:
        """Get midpoint of exit range"""
        return (self.exit_value_range[0] + self.exit_value_range[1]) / 2


class ComprehensivePWERM:
    """
    Full PWERM implementation with 300+ scenarios based on funding path
    """
    
    # Base probabilities by exit type and funding stage
    EXIT_PROBABILITIES = {
        'Liquidation': {
            'Pre-seed only': 0.40,
            'Pre-seed and seed': 0.35,
            'Pre-seed,seed and seed extension': 0.30,
            'Pre-seed,seed and A': 0.25,
            'Pre-seed,seed,A,B': 0.20,
            'Pre-seed,seed,A,B,C': 0.15,
            'Pre-seed,seed,A,B,C,D': 0.10,
            'Pre-seed,seed,A,B,C,D,E': 0.08,
            'Pre-seed,seed,A,B,C,D,E,F': 0.05
        },
        'Acquihire': {
            'Pre-seed only': 0.15,
            'Pre-seed and seed': 0.20,
            'Pre-seed,seed and seed extension': 0.18,
            'Pre-seed,seed and A': 0.15,
            'Pre-seed,seed,A,B': 0.10,
            'Pre-seed,seed,A,B,C': 0.05,
        },
        'Strategic Acquisition': {
            'Pre-seed and seed': 0.10,
            'Pre-seed,seed and A': 0.15,
            'Pre-seed,seed,A,B': 0.20,
            'Pre-seed,seed,A,B,C': 0.25,
            'Pre-seed,seed,A,B,C,D': 0.20,
            'Pre-seed,seed,A,B,C,D,E': 0.15,
            'Pre-seed,seed,A,B,C,D,E,F': 0.10
        },
        'PE Buyout': {
            'Pre-seed,seed,A,B': 0.05,
            'Pre-seed,seed,A,B,C': 0.10,
            'Pre-seed,seed,A,B,C,D': 0.15,
            'Pre-seed,seed,A,B,C,D,E': 0.12,
            'Pre-seed,seed,A,B,C,D,E,F': 0.08
        },
        'IPO': {
            'Pre-seed,seed,A,B': 0.02,
            'Pre-seed,seed,A,B,C': 0.05,
            'Pre-seed,seed,A,B,C,D': 0.10,
            'Pre-seed,seed,A,B,C,D,E': 0.15,
            'Pre-seed,seed,A,B,C,D,E,F': 0.20
        },
        'Roll-up': {
            'Pre-seed,seed,A,B': 0.03,
            'Pre-seed,seed,A,B,C': 0.04,
            'Pre-seed,seed,A,B,C,D': 0.03,
            'Pre-seed,seed,A,B,C,D,E': 0.02
        }
    }
    
    def __init__(self):
        """Initialize with full scenario matrix"""
        self.scenarios = self._build_full_scenario_matrix()
    
    def _parse_funding_path(self, company_data: Dict) -> str:
        """
        Parse actual funding history from company data
        Returns funding path string like "Pre-seed,seed,A,B"
        """
        funding_rounds = company_data.get('funding_rounds', [])
        
        if not funding_rounds:
            return "Pre-seed only"
        
        # Sort rounds by date
        rounds = sorted(funding_rounds, key=lambda x: x.get('date', ''))
        
        # Build path string
        path_components = []
        has_debt = False
        has_extension = False
        
        for round_data in rounds:
            round_type = round_data.get('round_type', '').lower()
            
            if 'pre' in round_type or 'preseed' in round_type:
                path_components.append('Pre-seed')
            elif 'seed' in round_type and 'pre' not in round_type:
                if 'extension' in round_type:
                    has_extension = True
                else:
                    path_components.append('seed')
            elif 'series a' in round_type or 'series_a' in round_type or 'a round' in round_type:
                path_components.append('A')
            elif 'series b' in round_type or 'series_b' in round_type or 'b round' in round_type:
                path_components.append('B')
            elif 'series c' in round_type or 'series_c' in round_type or 'c round' in round_type:
                path_components.append('C')
            elif 'series d' in round_type or 'series_d' in round_type or 'd round' in round_type:
                path_components.append('D')
            elif 'series e' in round_type or 'series_e' in round_type or 'e round' in round_type:
                path_components.append('E')
            elif 'series f' in round_type or 'series_f' in round_type or 'f round' in round_type:
                path_components.append('F')
            elif 'debt' in round_type or 'venture debt' in round_type:
                has_debt = True
        
        # Build final path string
        if not path_components:
            return "Pre-seed only"
        
        path = ','.join(path_components)
        
        # Add modifiers
        if has_extension:
            path = path.replace('seed', 'seed,seed extension')
        if has_debt:
            # Insert debt after B round typically
            if 'B' in path and 'Debt' not in path:
                path = path.replace('B,C', 'B,Debt,C') if 'C' in path else path + ',Debt'
        
        return path
    
    def _build_full_scenario_matrix(self) -> List[ComprehensivePWERMScenario]:
        """
        Build complete scenario matrix with base dollar amounts.
        These are for a typical $100M Series A company and will be scaled.
        """
        scenarios = []
        
        # LIQUIDATION SCENARIOS ($1M - $45M base)
        liquidation_ranges = [
            (1, 5), (5, 10), (10, 15), (15, 20), (20, 25),
            (25, 30), (30, 35), (35, 40), (40, 45)
        ]
        
        liquidation_paths = [
            "Pre-seed only",
            "Pre-seed and seed", 
            "Pre-seed,seed and seed extension",
            "Pre-seed,seed and A",
            "Pre-seed,seed,seed extension,A",
            "Pre-seed,seed,A,B",
            "Pre-seed,seed,extension,A,B",
            "Pre-seed,seed,A,B,C"
        ]
        
        for value_range in liquidation_ranges:
            for path in liquidation_paths:
                # Get probability from benchmark data
                base_prob = self.EXIT_PROBABILITIES.get('Liquidation', {}).get(path, 0.20)
                # Adjust slightly based on exit value (lower values more likely)
                value_adjustment = 1.0 + (45 - value_range[1]) / 100  # Higher prob for lower values
                adjusted_prob = base_prob * value_adjustment / len(liquidation_ranges)
                
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="Liquidation",
                    funding_path=path,
                    exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                    exit_description=f"Liquidation at ${value_range[0]}-{value_range[1]}M",
                    probability=adjusted_prob,
                    time_to_exit=2.0
                ))
        
        # ACQUIHIRE SCENARIOS ($5M - $30M base)
        acquihire_ranges = [
            (5, 10), (10, 15), (15, 20), (20, 25), (25, 30)
        ]
        
        acquihire_paths = [
            "Pre-seed only",
            "Pre-seed and seed",
            "Pre-seed,seed and A"
        ]
        
        for value_range in acquihire_ranges:
            for path in acquihire_paths:
                # Get base probability from benchmark data
                base_prob = self.EXIT_PROBABILITIES.get('Acquihire', {}).get(path, 0.10)
                # Distribute across value ranges, slightly favoring lower values  
                value_adjustment = 1.0 + (30 - value_range[1]) / 50
                adjusted_prob = base_prob * value_adjustment / len(acquihire_ranges)
                
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="Acquihire",
                    funding_path=path,
                    exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                    exit_description=f"Acquihire at ${value_range[0]}-{value_range[1]}M",
                    probability=adjusted_prob,
                    time_to_exit=2.5
                ))
        
        # STRATEGIC ACQUISITION SCENARIOS ($50M - $500M base)
        acquisition_ranges = [
            (50, 100), (100, 150), (150, 200), (200, 250),
            (250, 300), (300, 350), (350, 400), (400, 450), (450, 500)
        ]
        
        for value_range in acquisition_ranges:
            for path in ["Pre-seed,seed and A", "Pre-seed,seed,A,B", "Pre-seed,seed,A,B,C"]:
                # Get base probability from benchmark data
                base_prob = self.EXIT_PROBABILITIES.get('Strategic Acquisition', {}).get(path, 0.15)
                # Distribute across value ranges, peak around mid-range
                value_adjustment = 1.0 - abs(value_range[0] - 250) / 500
                value_adjustment = max(0.5, value_adjustment)  # Ensure minimum adjustment
                adjusted_prob = base_prob * value_adjustment / len(acquisition_ranges)
                
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="Strategic Acquisition",
                    funding_path=path,
                    exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                    exit_description=f"Strategic acquisition at ${value_range[0]}-{value_range[1]}M",
                    probability=adjusted_prob,
                    time_to_exit=3.5
                ))
        
        # IPO SCENARIOS (5x - 100x of valuation)
        # For a $100M company, this is $500M - $10B+
        ipo_scenarios = [
            # Microcap IPO (5x - 10x)
            {
                'type': 'Microcap Regional IPO',
                'ranges': [(5, 6), (6, 7), (7, 8), (8, 9), (9, 10)],
                'paths': ["Pre-seed,seed,A,B,C", "Pre-seed,seed,A,B,C,D"]
            },
            # Midcap IPO (10x - 20x)
            {
                'type': 'Midcap IPO',
                'ranges': [(10, 12), (12, 14), (14, 16), (16, 18), (18, 20)],
                'paths': ["Pre-seed,seed,A,B,C,D", "Pre-seed,seed,A,B,C,D,E"]
            },
            # Largecap IPO (20x - 50x)
            {
                'type': 'Largecap IPO',
                'ranges': [(20, 25), (25, 30), (30, 35), (35, 40), (40, 50)],
                'paths': ["Pre-seed,seed,A,B,C,D,E", "Pre-seed,seed,A,B,C,D,E,F"]
            },
            # Mega IPO (50x+)
            {
                'type': 'Mega IPO',
                'ranges': [(50, 60), (60, 70), (70, 80), (80, 90), (90, 100)],
                'paths': ["Pre-seed,seed,A,B,C,D,E,F"]
            }
        ]
        
        for ipo_config in ipo_scenarios:
            for value_range in ipo_config['ranges']:
                for path in ipo_config['paths']:
                    # Get base probability from benchmark data
                    base_prob = self.EXIT_PROBABILITIES.get('IPO', {}).get(path, 0.05)
                    # Distribute across IPO tiers and value ranges
                    # Higher tier IPOs (larger multiples) are less likely
                    tier_index = ipo_scenarios.index(ipo_config)
                    tier_adjustment = 1.0 / (1 + tier_index * 0.3)  # Decrease probability for higher tiers
                    range_count = len(ipo_config['ranges']) * len(ipo_config['paths'])
                    adjusted_prob = base_prob * tier_adjustment / range_count
                    
                    scenarios.append(ComprehensivePWERMScenario(
                        scenario_type=ipo_config['type'],
                        funding_path=path,
                        exit_value_range=(value_range[0] * BASE_VALUATION, value_range[1] * BASE_VALUATION),
                        exit_description=f"{ipo_config['type']} at {value_range[0]:.0f}x-{value_range[1]:.0f}x",
                        probability=adjusted_prob,
                        time_to_exit=7.0  # Median time to IPO
                    ))
        
        # ROLL-UP SCENARIOS (4x - 20x of valuation)
        # For a $100M company, this is $400M - $2B
        rollup_ranges = [(4, 6), (6, 8), (8, 10), (10, 15), (15, 20)]
        
        for value_range in rollup_ranges:
            for path in ["Pre-seed,seed,A,B", "Pre-seed,seed,A,B,C"]:
                # Get base probability from benchmark data
                base_prob = self.EXIT_PROBABILITIES.get('Roll-up', {}).get(path, 0.03)
                # Distribute across value ranges
                adjusted_prob = base_prob / len(rollup_ranges)
                
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="Roll-up",
                    funding_path=path,
                    exit_value_range=(value_range[0] * BASE_VALUATION, value_range[1] * BASE_VALUATION),
                    exit_description=f"Industry roll-up at {value_range[0]:.0f}x-{value_range[1]:.0f}x",
                    probability=adjusted_prob,
                    time_to_exit=4.0
                ))
        
        # PE BUYOUT SCENARIOS (5x - 30x of valuation)
        # For a $100M company, this is $500M - $3B
        pe_ranges = [(5, 7.5), (7.5, 10), (10, 15), (15, 20), (20, 30)]
        
        for value_range in pe_ranges:
            for path in ["Pre-seed,seed,A,B,C", "Pre-seed,seed,A,B,C,D"]:
                # Get base probability from benchmark data
                base_prob = self.EXIT_PROBABILITIES.get('PE Buyout', {}).get(path, 0.08)
                # Distribute across value ranges
                adjusted_prob = base_prob / len(pe_ranges)
                
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="PE Buyout",
                    funding_path=path,
                    exit_value_range=(value_range[0] * BASE_VALUATION, value_range[1] * BASE_VALUATION),
                    exit_description=f"PE buyout at {value_range[0]:.0f}x-{value_range[1]:.0f}x",
                    probability=adjusted_prob,
                    time_to_exit=5.0
                ))
        
        # Normalize probabilities to sum to 1
        total_prob = sum(s.probability for s in scenarios)
        for scenario in scenarios:
            scenario.probability = scenario.probability / total_prob
        
        return scenarios
    
    def calculate_valuation(
        self,
        company_data: Dict,
        discount_rate: float = 0.25,
        dlom: float = 0.30
    ) -> Dict[str, Any]:
        """
        Calculate PWERM valuation based on company's actual funding path
        
        Args:
            company_data: Company data including funding history
            discount_rate: Discount rate for present value calculation
            dlom: Discount for lack of marketability
            
        Returns:
            Valuation results with scenario breakdown
        """
        
        # Parse company's funding path
        funding_path = self._parse_funding_path(company_data)
        logger.info(f"Company funding path: {funding_path}")
        
        # Filter scenarios based on funding path
        relevant_scenarios = self._filter_scenarios_by_path(funding_path)
        
        # Scale scenarios based on company's actual valuation
        scaled_scenarios = self._scale_scenarios_to_company(relevant_scenarios, company_data)
        
        # Adjust probabilities based on company-specific factors
        adjusted_scenarios = self._adjust_probabilities(scaled_scenarios, company_data)
        
        # Calculate present values
        for scenario in adjusted_scenarios:
            pv_factor = 1 / ((1 + discount_rate) ** scenario.time_to_exit)
            scenario.present_value = scenario.exit_value * pv_factor
        
        # Calculate probability-weighted value
        total_value = sum(s.probability * s.present_value for s in adjusted_scenarios)
        
        # Apply DLOM
        fair_value = total_value * (1 - dlom)
        
        # Group scenarios by type for analysis
        scenario_groups = {}
        for scenario in adjusted_scenarios:
            if scenario.scenario_type not in scenario_groups:
                scenario_groups[scenario.scenario_type] = {
                    'scenarios': [],
                    'total_probability': 0,
                    'weighted_value': 0
                }
            scenario_groups[scenario.scenario_type]['scenarios'].append(scenario)
            scenario_groups[scenario.scenario_type]['total_probability'] += scenario.probability
            scenario_groups[scenario.scenario_type]['weighted_value'] += scenario.probability * scenario.present_value
        
        return {
            'valuation': fair_value,  # Primary valuation output
            'fair_value': fair_value,
            'pre_dlom_value': total_value,
            'expected_return': total_value,  # Expected return before DLOM
            'dlom_applied': dlom,
            'discount_rate': discount_rate,
            'funding_path': funding_path,
            'scenario_count': len(adjusted_scenarios),
            'scenario_groups': scenario_groups,
            'scenarios': [{
                'type': s.scenario_type,
                'exit_value': s.exit_value,
                'probability': s.probability,
                'present_value': s.present_value
            } for s in sorted(adjusted_scenarios, key=lambda x: x.probability, reverse=True)[:10]],
            'top_scenarios': sorted(adjusted_scenarios, key=lambda x: x.probability, reverse=True)[:10],
            'methodology': 'Comprehensive PWERM with funding path analysis'
        }
    
    def _filter_scenarios_by_path(self, funding_path: str) -> List[ComprehensivePWERMScenario]:
        """
        Filter scenarios to those relevant for the company's funding path
        """
        relevant_scenarios = []
        
        # Count funding rounds
        rounds_count = funding_path.count(',') + 1 if funding_path != "Pre-seed only" else 1
        
        for scenario in self.scenarios:
            scenario_rounds = scenario.funding_path.count(',') + 1
            
            # Include scenarios with similar or next stage funding paths
            if abs(scenario_rounds - rounds_count) <= 2:
                # Check if the path is a logical progression
                if self._is_logical_progression(funding_path, scenario.funding_path):
                    relevant_scenarios.append(scenario)
        
        return relevant_scenarios
    
    def _is_logical_progression(self, current_path: str, scenario_path: str) -> bool:
        """
        Check if scenario path is a logical progression from current path
        """
        # Simple check - scenario should include current rounds or be achievable
        current_rounds = set(current_path.split(','))
        scenario_rounds = set(scenario_path.split(','))
        
        # If current is subset of scenario, it's a progression
        # Or if they're very similar (within 1-2 rounds)
        return len(current_rounds) <= len(scenario_rounds) + 2
    
    def _adjust_probabilities(
        self,
        scenarios: List[ComprehensivePWERMScenario],
        company_data: Dict
    ) -> List[ComprehensivePWERMScenario]:
        """
        Adjust scenario probabilities based on company-specific factors
        """
        adjusted = scenarios.copy()
        
        # Factors that affect probabilities
        growth_rate = company_data.get('growth_rate', 1.0)
        burn_rate = company_data.get('burn_rate', 0)
        runway = company_data.get('runway_months', 12)
        revenue = company_data.get('revenue', 0)
        
        for scenario in adjusted:
            # High growth increases IPO probability
            if 'IPO' in scenario.scenario_type and growth_rate > 2.0:
                scenario.probability *= 1.5
            
            # Low runway increases liquidation probability
            if scenario.scenario_type == 'Liquidation' and runway < 6:
                scenario.probability *= 2.0
            
            # Strong revenue increases acquisition probability
            if 'Acquisition' in scenario.scenario_type and revenue > 10_000_000:
                scenario.probability *= 1.3
            
            # Adjust for market conditions (could be dynamic)
            if scenario.scenario_type == 'PE Buyout':
                scenario.probability *= 1.2  # PE is active in current market
        
        # Renormalize probabilities
        total_prob = sum(s.probability for s in adjusted)
        for scenario in adjusted:
            scenario.probability = scenario.probability / total_prob
        
        return adjusted
    
    def _scale_scenarios_to_company(
        self,
        scenarios: List[ComprehensivePWERMScenario],
        company_data: Dict
    ) -> List[ComprehensivePWERMScenario]:
        """
        Scale scenario exit values based on company's actual valuation.
        This transforms the hardcoded template values into company-specific ranges.
        """
        # Extract company's current valuation
        current_val = (
            company_data.get('valuation') or 
            company_data.get('last_round_valuation') or 
            company_data.get('post_money_valuation') or
            100_000_000  # Default $100M if no valuation found
        )
        
        # Handle case where valuation might be a dict with 'value' field
        if isinstance(current_val, dict) and 'value' in current_val:
            current_val = current_val['value']
        
        # Determine the company's stage
        stage = company_data.get('stage', 'series_a')
        if isinstance(stage, str):
            stage = stage.lower().replace(' ', '_')
        
        # Define base valuations that the hardcoded scenarios assume
        # These are the median valuations for each stage
        stage_bases = {
            'pre_seed': 5_000_000,       # $5M pre-seed
            'pre-seed': 5_000_000,       # $5M pre-seed (alternate spelling)
            'seed': 20_000_000,          # $20M seed
            'series_a': 50_000_000,      # $50M Series A
            'series_b': 150_000_000,     # $150M Series B
            'series_c': 400_000_000,     # $400M Series C
            'series_d': 800_000_000,     # $800M Series D
            'series_e': 1_500_000_000,   # $1.5B Series E
            'series_f': 3_000_000_000,   # $3B Series F
            'growth': 250_000_000,       # $250M growth stage
            'late': 1_000_000_000,       # $1B late stage
            'unknown': 100_000_000,      # $100M default
        }
        
        # Get the base valuation for this stage
        stage_base = stage_bases.get(stage, 100_000_000)
        
        # Calculate the scaling factor
        scale_factor = current_val / stage_base
        
        logger.info(f"Scaling PWERM scenarios: current_val=${current_val:,.0f}, stage={stage}, base=${stage_base:,.0f}, scale={scale_factor:.2f}x")
        
        # Create scaled scenarios
        scaled_scenarios = []
        for scenario in scenarios:
            # Create a copy to avoid modifying the original
            scaled_scenario = ComprehensivePWERMScenario(
                scenario_type=scenario.scenario_type,
                funding_path=scenario.funding_path,
                exit_value_range=(
                    scenario.exit_value_range[0] * scale_factor,
                    scenario.exit_value_range[1] * scale_factor
                ),
                exit_description=self._format_scaled_description(
                    scenario.scenario_type,
                    scenario.exit_value_range[0] * scale_factor,
                    scenario.exit_value_range[1] * scale_factor
                ),
                probability=scenario.probability,
                time_to_exit=scenario.time_to_exit,
                present_value=scenario.present_value
            )
            scaled_scenarios.append(scaled_scenario)
        
        return scaled_scenarios
    
    def _format_scaled_description(self, scenario_type: str, min_val: float, max_val: float) -> str:
        """
        Format the exit description with properly scaled values.
        """
        # Format values based on magnitude
        if min_val >= 1_000_000_000:  # Billions
            return f"{scenario_type} at ${min_val/1_000_000_000:.1f}-{max_val/1_000_000_000:.1f}B"
        elif min_val >= 1_000_000:  # Millions
            return f"{scenario_type} at ${min_val/1_000_000:.0f}-{max_val/1_000_000:.0f}M"
        else:  # Thousands or less
            return f"{scenario_type} at ${min_val/1_000:.0f}-{max_val/1_000:.0f}K"
    
    def _ensure_numeric(self, value: Any, default: float = 0) -> float:
        """
        Ensure a value is numeric, extracting from dict if needed.
        """
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict) and 'value' in value:
            return float(value['value'])
        if isinstance(value, str):
            try:
                return float(value.replace(',', '').replace('$', ''))
            except:
                return default
        return default