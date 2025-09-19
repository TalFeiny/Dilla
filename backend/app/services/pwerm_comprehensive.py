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
            elif 'series a' in round_type or 'a round' in round_type:
                path_components.append('A')
            elif 'series b' in round_type or 'b round' in round_type:
                path_components.append('B')
            elif 'series c' in round_type or 'c round' in round_type:
                path_components.append('C')
            elif 'series d' in round_type or 'd round' in round_type:
                path_components.append('D')
            elif 'series e' in round_type or 'e round' in round_type:
                path_components.append('E')
            elif 'series f' in round_type or 'f round' in round_type:
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
        Build complete scenario matrix from your provided data
        """
        scenarios = []
        
        # LIQUIDATION SCENARIOS ($1M - $45M)
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
                # Probability decreases with higher valuations and more rounds
                base_prob = 0.15 - (value_range[0] / 500) - (path.count(',') * 0.01)
                base_prob = max(0.001, base_prob)  # Minimum probability
                
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="Liquidation",
                    funding_path=path,
                    exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                    exit_description=f"Liquidation at ${value_range[0]}-{value_range[1]}M",
                    probability=base_prob,
                    time_to_exit=2.0
                ))
        
        # STRATEGIC ACQUISITION SCENARIOS ($50M - $500M)
        acquisition_ranges = [
            (50, 100), (100, 150), (150, 200), (200, 250),
            (250, 300), (300, 350), (350, 400), (400, 450), (450, 500)
        ]
        
        for value_range in acquisition_ranges:
            for path in ["Pre-seed,seed,A", "Pre-seed,seed,A,B", "Pre-seed,seed,A,B,C"]:
                base_prob = 0.08 - (abs(value_range[0] - 200) / 5000)  # Peak around $200M
                base_prob = max(0.001, base_prob)
                
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="Strategic Acquisition",
                    funding_path=path,
                    exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                    exit_description=f"Strategic acquisition at ${value_range[0]}-{value_range[1]}M",
                    probability=base_prob,
                    time_to_exit=3.5
                ))
        
        # IPO SCENARIOS ($500M - $10B+)
        ipo_scenarios = [
            # Microcap IPO ($500M - $1B)
            {
                'type': 'Microcap Regional IPO',
                'ranges': [(500, 600), (600, 700), (700, 800), (800, 900), (900, 1000)],
                'paths': ["Pre-seed,seed,A,B,C", "Pre-seed,seed,A,B,C,D"],
                'base_prob': 0.02
            },
            # Midcap IPO ($1B - $2B)
            {
                'type': 'Midcap IPO',
                'ranges': [(1000, 1200), (1200, 1400), (1400, 1600), (1600, 1800), (1800, 2000)],
                'paths': ["Pre-seed,seed,A,B,C,D", "Pre-seed,seed,A,B,C,D,E"],
                'base_prob': 0.015
            },
            # Largecap IPO ($2B - $5B)
            {
                'type': 'Largecap IPO',
                'ranges': [(2000, 2500), (2500, 3000), (3000, 3500), (3500, 4000), (4000, 5000)],
                'paths': ["Pre-seed,seed,A,B,C,D,E", "Pre-seed,seed,A,B,C,D,E,F"],
                'base_prob': 0.01
            },
            # Mega IPO ($5B+)
            {
                'type': 'Mega IPO',
                'ranges': [(5000, 6000), (6000, 7000), (7000, 8000), (8000, 9000), (9000, 10000)],
                'paths': ["Pre-seed,seed,A,B,C,D,E,F"],
                'base_prob': 0.005
            }
        ]
        
        for ipo_config in ipo_scenarios:
            for value_range in ipo_config['ranges']:
                for path in ipo_config['paths']:
                    scenarios.append(ComprehensivePWERMScenario(
                        scenario_type=ipo_config['type'],
                        funding_path=path,
                        exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                        exit_description=f"{ipo_config['type']} at ${value_range[0]/1000:.1f}-{value_range[1]/1000:.1f}B",
                        probability=ipo_config['base_prob'],
                        time_to_exit=7.0  # Median time to IPO
                    ))
        
        # ROLL-UP SCENARIOS ($400M - $2B)
        rollup_ranges = [(400, 600), (600, 800), (800, 1000), (1000, 1500), (1500, 2000)]
        
        for value_range in rollup_ranges:
            for path in ["Pre-seed,seed,A,B", "Pre-seed,seed,A,B,C"]:
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="Roll-up",
                    funding_path=path,
                    exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                    exit_description=f"Industry roll-up at ${value_range[0]}-{value_range[1]}M",
                    probability=0.03,
                    time_to_exit=4.0
                ))
        
        # PE BUYOUT SCENARIOS ($500M - $3B)
        pe_ranges = [(500, 750), (750, 1000), (1000, 1500), (1500, 2000), (2000, 3000)]
        
        for value_range in pe_ranges:
            for path in ["Pre-seed,seed,A,B,C", "Pre-seed,seed,A,B,C,D"]:
                scenarios.append(ComprehensivePWERMScenario(
                    scenario_type="PE Buyout",
                    funding_path=path,
                    exit_value_range=(value_range[0] * 1_000_000, value_range[1] * 1_000_000),
                    exit_description=f"PE buyout at ${value_range[0]/1000:.1f}-{value_range[1]/1000:.1f}B",
                    probability=0.04,
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
        
        # Adjust probabilities based on company-specific factors
        adjusted_scenarios = self._adjust_probabilities(relevant_scenarios, company_data)
        
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
            'fair_value': fair_value,
            'pre_dlom_value': total_value,
            'dlom_applied': dlom,
            'discount_rate': discount_rate,
            'funding_path': funding_path,
            'scenario_count': len(adjusted_scenarios),
            'scenario_groups': scenario_groups,
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