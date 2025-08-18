#!/usr/bin/env python3
"""
IPEV-Compliant PWERM (Probability-Weighted Expected Return Method) Analysis
Implements IPEV Valuation Guidelines (December 2022) for Private Equity/VC investments
"""

import json
import sys
import os
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class ExitScenario(Enum):
    """Exit scenarios per IPEV guidelines"""
    IPO = "ipo"
    STRATEGIC_SALE = "strategic_sale"
    FINANCIAL_SALE = "financial_sale"
    LIQUIDATION = "liquidation"
    CONTINUATION = "continuation"
    REDEMPTION = "redemption"

@dataclass
class CapitalStructure:
    """Company capital structure for waterfall analysis"""
    common_shares: float
    preferred_shares: float
    liquidation_preference: float
    participation_cap: float
    conversion_price: float
    employee_options: float
    debt: float

@dataclass
class ScenarioOutput:
    """Output for a single PWERM scenario"""
    scenario_type: ExitScenario
    exit_value: float
    probability: float
    time_to_exit: float
    investor_proceeds: float
    gross_moic: float
    irr: float

class IPEVPWERMAnalyzer:
    """IPEV-compliant PWERM analyzer"""
    
    def __init__(self, tavily_api_key: str = None, claude_api_key: str = None):
        """Initialize with API keys for market data"""
        self.tavily_api_key = tavily_api_key or os.environ.get('TAVILY_API_KEY')
        self.claude_api_key = claude_api_key or os.environ.get('CLAUDE_API_KEY')
        
        # IPEV parameters
        self.market_participant_perspective = True
        self.fair_value_measurement = True
        self.calibration_required = True
        
    def determine_enterprise_value(self, 
                                  company_data: Dict,
                                  market_data: Dict,
                                  method: str = "multiple") -> Dict:
        """
        Step 1: Determine Enterprise Value using IPEV-approved methods
        
        Methods:
        - 'multiple': Market multiples approach
        - 'dcf': Discounted cash flow
        - 'recent_investment': Price of recent investment
        """
        
        if method == "multiple":
            return self._ev_from_multiples(company_data, market_data)
        elif method == "dcf":
            return self._ev_from_dcf(company_data, market_data)
        elif method == "recent_investment":
            return self._ev_from_recent_transaction(company_data)
        else:
            raise ValueError(f"Invalid EV method: {method}")
    
    def _ev_from_multiples(self, company_data: Dict, market_data: Dict) -> Dict:
        """Calculate EV using market multiples (IPEV preferred for growth companies)"""
        
        # Extract company metrics
        revenue = company_data.get('current_arr_usd', 0)
        growth_rate = company_data.get('revenue_growth_annual_pct', 30) / 100
        ebitda = company_data.get('ebitda', revenue * 0.2)  # Assume 20% margin if not provided
        
        # Get comparable company multiples
        comparables = market_data.get('comparables', [])
        
        if not comparables:
            # Use sector defaults
            sector = company_data.get('sector', 'SaaS')
            if sector == 'SaaS':
                ev_revenue_multiple = 6.0  # Current SaaS median
            else:
                ev_revenue_multiple = 4.0  # General tech median
        else:
            # Calculate median multiple from comparables
            multiples = []
            for comp in comparables:
                if comp.get('ev') and comp.get('revenue'):
                    multiples.append(comp['ev'] / comp['revenue'])
            
            if multiples:
                ev_revenue_multiple = np.median(multiples)
            else:
                ev_revenue_multiple = 5.0
        
        # Adjust for company-specific factors (size, growth, margins)
        size_discount = 0.8 if revenue < 10_000_000 else 1.0  # Small company discount
        growth_premium = 1.0 + (growth_rate - 0.3) * 0.5 if growth_rate > 0.3 else 1.0
        
        adjusted_multiple = ev_revenue_multiple * size_discount * growth_premium
        
        # Apply DLOM (Discount for Lack of Marketability) - IPEV requirement
        dlom = 0.3  # 30% standard DLOM for private companies
        final_multiple = adjusted_multiple * (1 - dlom)
        
        enterprise_value = revenue * final_multiple
        
        return {
            'enterprise_value': enterprise_value,
            'method': 'Market Multiples',
            'base_multiple': ev_revenue_multiple,
            'adjusted_multiple': final_multiple,
            'dlom_applied': dlom,
            'comparables_used': len(comparables)
        }
    
    def _ev_from_dcf(self, company_data: Dict, market_data: Dict) -> Dict:
        """Calculate EV using DCF (IPEV preferred for stable cash flow companies)"""
        
        # Initial parameters
        revenue = company_data.get('current_arr_usd', 0)
        growth_rate = company_data.get('revenue_growth_annual_pct', 30) / 100
        margin = company_data.get('ebitda_margin', 0.2)
        
        # Build 5-year projection
        projection_years = 5
        cash_flows = []
        
        for year in range(1, projection_years + 1):
            # Decay growth rate over time
            year_growth = growth_rate * (0.8 ** (year - 1))
            year_revenue = revenue * ((1 + year_growth) ** year)
            year_fcf = year_revenue * margin * 0.7  # Convert EBITDA to FCF
            cash_flows.append(year_fcf)
        
        # Terminal value (Gordon Growth Model)
        terminal_growth = 0.03  # 3% perpetual growth
        terminal_fcf = cash_flows[-1] * (1 + terminal_growth)
        
        # Determine appropriate discount rate (WACC)
        # Per IPEV: should reflect systematic risk only
        risk_free_rate = 0.04  # Current 10-year treasury
        market_premium = 0.08  # Equity risk premium
        beta = 1.5  # Higher for growth companies
        size_premium = 0.03  # Small company premium
        
        cost_of_equity = risk_free_rate + beta * market_premium + size_premium
        wacc = cost_of_equity  # Assume no debt
        
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        
        # Discount cash flows to present value
        pv_cash_flows = sum([cf / ((1 + wacc) ** (i + 1)) 
                            for i, cf in enumerate(cash_flows)])
        pv_terminal = terminal_value / ((1 + wacc) ** projection_years)
        
        enterprise_value = pv_cash_flows + pv_terminal
        
        return {
            'enterprise_value': enterprise_value,
            'method': 'Discounted Cash Flow',
            'wacc': wacc,
            'terminal_growth': terminal_growth,
            'projection_years': projection_years
        }
    
    def _ev_from_recent_transaction(self, company_data: Dict) -> Dict:
        """Calculate EV from recent investment round (IPEV preferred for recent investments)"""
        
        last_valuation = company_data.get('last_round_valuation', 0)
        months_since = company_data.get('months_since_last_round', 6)
        
        if last_valuation == 0:
            raise ValueError("No recent transaction data available")
        
        # Calibration adjustments per IPEV
        if months_since <= 3:
            adjustment = 1.0  # Recent enough, no adjustment
        elif months_since <= 12:
            adjustment = 0.95  # Minor adjustment for time
        else:
            adjustment = 0.85  # Significant time passed, larger adjustment
        
        # Consider market conditions change
        market_adjustment = company_data.get('market_adjustment', 1.0)
        
        enterprise_value = last_valuation * adjustment * market_adjustment
        
        return {
            'enterprise_value': enterprise_value,
            'method': 'Price of Recent Investment',
            'last_valuation': last_valuation,
            'months_since': months_since,
            'adjustment_factor': adjustment * market_adjustment
        }
    
    def generate_scenarios(self,
                          enterprise_value: float,
                          market_data: Dict,
                          company_stage: str = "growth") -> List[ScenarioOutput]:
        """
        Step 2: Generate probability-weighted scenarios per IPEV guidelines
        
        Considers:
        - Company stage (seed, early, growth, late)
        - Market conditions
        - Sector-specific exit patterns
        """
        
        scenarios = []
        
        # Define scenario probabilities based on stage
        if company_stage == "seed":
            probs = {
                ExitScenario.LIQUIDATION: 0.65,
                ExitScenario.STRATEGIC_SALE: 0.20,
                ExitScenario.CONTINUATION: 0.10,
                ExitScenario.FINANCIAL_SALE: 0.04,
                ExitScenario.IPO: 0.01
            }
            time_horizons = {
                ExitScenario.LIQUIDATION: 2.0,
                ExitScenario.STRATEGIC_SALE: 4.0,
                ExitScenario.CONTINUATION: 5.0,
                ExitScenario.FINANCIAL_SALE: 5.0,
                ExitScenario.IPO: 7.0
            }
        elif company_stage == "early":
            probs = {
                ExitScenario.LIQUIDATION: 0.50,
                ExitScenario.STRATEGIC_SALE: 0.30,
                ExitScenario.CONTINUATION: 0.10,
                ExitScenario.FINANCIAL_SALE: 0.08,
                ExitScenario.IPO: 0.02
            }
            time_horizons = {
                ExitScenario.LIQUIDATION: 2.0,
                ExitScenario.STRATEGIC_SALE: 3.5,
                ExitScenario.CONTINUATION: 4.0,
                ExitScenario.FINANCIAL_SALE: 4.5,
                ExitScenario.IPO: 6.0
            }
        elif company_stage == "growth":
            probs = {
                ExitScenario.LIQUIDATION: 0.30,
                ExitScenario.STRATEGIC_SALE: 0.35,
                ExitScenario.FINANCIAL_SALE: 0.20,
                ExitScenario.CONTINUATION: 0.10,
                ExitScenario.IPO: 0.05
            }
            time_horizons = {
                ExitScenario.LIQUIDATION: 1.5,
                ExitScenario.STRATEGIC_SALE: 3.0,
                ExitScenario.FINANCIAL_SALE: 3.5,
                ExitScenario.CONTINUATION: 4.0,
                ExitScenario.IPO: 5.0
            }
        else:  # late stage
            probs = {
                ExitScenario.LIQUIDATION: 0.15,
                ExitScenario.STRATEGIC_SALE: 0.30,
                ExitScenario.FINANCIAL_SALE: 0.25,
                ExitScenario.IPO: 0.20,
                ExitScenario.CONTINUATION: 0.10
            }
            time_horizons = {
                ExitScenario.LIQUIDATION: 1.0,
                ExitScenario.STRATEGIC_SALE: 2.0,
                ExitScenario.FINANCIAL_SALE: 2.5,
                ExitScenario.IPO: 3.0,
                ExitScenario.CONTINUATION: 4.0
            }
        
        # Generate scenarios with exit value distributions
        for scenario_type, probability in probs.items():
            # Number of sub-scenarios for this type
            num_subscenarios = max(1, int(499 * probability))
            
            for i in range(num_subscenarios):
                # Generate exit value based on scenario type
                if scenario_type == ExitScenario.LIQUIDATION:
                    # Liquidation: 0-50% recovery
                    exit_multiple = np.random.uniform(0, 0.5)
                elif scenario_type == ExitScenario.CONTINUATION:
                    # Continuation: 80-120% of current value
                    exit_multiple = np.random.uniform(0.8, 1.2)
                elif scenario_type == ExitScenario.STRATEGIC_SALE:
                    # Strategic: 1.5-5x with some mega exits
                    if np.random.random() < 0.1:  # 10% chance of mega exit
                        exit_multiple = np.random.uniform(5, 10)
                    else:
                        exit_multiple = np.random.uniform(1.5, 5)
                elif scenario_type == ExitScenario.FINANCIAL_SALE:
                    # Financial buyer: 1.2-3x
                    exit_multiple = np.random.uniform(1.2, 3)
                elif scenario_type == ExitScenario.IPO:
                    # IPO: 2-8x with upside
                    exit_multiple = np.random.uniform(2, 8)
                else:
                    exit_multiple = 1.0
                
                exit_value = enterprise_value * exit_multiple
                time_to_exit = time_horizons[scenario_type] + np.random.normal(0, 0.5)
                time_to_exit = max(0.5, time_to_exit)  # Minimum 6 months
                
                scenarios.append(ScenarioOutput(
                    scenario_type=scenario_type,
                    exit_value=exit_value,
                    probability=probability / num_subscenarios,
                    time_to_exit=time_to_exit,
                    investor_proceeds=0,  # Will be calculated in waterfall
                    gross_moic=0,  # Will be calculated
                    irr=0  # Will be calculated
                ))
        
        return scenarios
    
    def apply_waterfall(self,
                       scenarios: List[ScenarioOutput],
                       capital_structure: CapitalStructure,
                       investment_amount: float,
                       ownership_percent: float) -> List[ScenarioOutput]:
        """
        Step 3: Apply liquidation waterfall to determine investor proceeds
        Per IPEV guidelines for complex capital structures
        """
        
        for scenario in scenarios:
            exit_value = scenario.exit_value
            
            # 1. Pay off debt
            remaining = max(0, exit_value - capital_structure.debt)
            
            # 2. Pay liquidation preferences
            liq_pref_payment = min(remaining, capital_structure.liquidation_preference)
            remaining -= liq_pref_payment
            
            # 3. Common distribution (if participating preferred)
            if remaining > 0:
                # Calculate fully diluted shares
                total_shares = (capital_structure.common_shares + 
                               capital_structure.preferred_shares + 
                               capital_structure.employee_options)
                
                # Investor's share of common distribution
                investor_common = remaining * ownership_percent
                
                # Check participation cap
                if capital_structure.participation_cap > 0:
                    max_proceeds = investment_amount * capital_structure.participation_cap
                    investor_proceeds = min(liq_pref_payment + investor_common, max_proceeds)
                else:
                    investor_proceeds = liq_pref_payment + investor_common
            else:
                investor_proceeds = liq_pref_payment * (ownership_percent / 
                                                       (capital_structure.preferred_shares / 
                                                        capital_structure.liquidation_preference))
            
            # Calculate returns
            scenario.investor_proceeds = investor_proceeds
            scenario.gross_moic = investor_proceeds / investment_amount if investment_amount > 0 else 0
            
            # Calculate IRR
            if scenario.time_to_exit > 0:
                scenario.irr = (scenario.gross_moic ** (1 / scenario.time_to_exit) - 1) * 100
            else:
                scenario.irr = 0
        
        return scenarios
    
    def calculate_fair_value(self, scenarios: List[ScenarioOutput]) -> Dict:
        """
        Step 4: Calculate probability-weighted fair value
        Per IPEV guidelines
        """
        
        # Calculate expected value
        expected_value = sum(s.investor_proceeds * s.probability for s in scenarios)
        
        # Calculate other statistics
        expected_moic = sum(s.gross_moic * s.probability for s in scenarios)
        expected_irr = sum(s.irr * s.probability for s in scenarios)
        
        # Calculate percentiles
        sorted_proceeds = sorted([s.investor_proceeds for s in scenarios])
        p10 = np.percentile(sorted_proceeds, 10)
        p25 = np.percentile(sorted_proceeds, 25)
        median = np.percentile(sorted_proceeds, 50)
        p75 = np.percentile(sorted_proceeds, 75)
        p90 = np.percentile(sorted_proceeds, 90)
        
        # Success metrics
        success_scenarios = [s for s in scenarios if s.gross_moic >= 3.0]
        success_probability = sum(s.probability for s in success_scenarios)
        
        mega_scenarios = [s for s in scenarios if s.gross_moic >= 10.0]
        mega_probability = sum(s.probability for s in mega_scenarios)
        
        loss_scenarios = [s for s in scenarios if s.gross_moic < 1.0]
        loss_probability = sum(s.probability for s in loss_scenarios)
        
        return {
            'fair_value': expected_value,
            'expected_moic': expected_moic,
            'expected_irr': expected_irr,
            'value_distribution': {
                'p10': p10,
                'p25': p25,
                'median': median,
                'p75': p75,
                'p90': p90
            },
            'probabilities': {
                'success_probability': success_probability,
                'mega_exit_probability': mega_probability,
                'loss_probability': loss_probability
            },
            'scenario_count': len(scenarios),
            'methodology': 'IPEV PWERM'
        }
    
    def perform_sensitivity_analysis(self,
                                    base_scenarios: List[ScenarioOutput],
                                    enterprise_value: float,
                                    capital_structure: CapitalStructure,
                                    investment_amount: float,
                                    ownership_percent: float) -> Dict:
        """
        Step 5: Perform sensitivity analysis as required by IPEV
        """
        
        sensitivities = {}
        
        # EV sensitivity (+/- 20%)
        ev_changes = [-0.2, -0.1, 0, 0.1, 0.2]
        ev_results = []
        
        for change in ev_changes:
            adjusted_ev = enterprise_value * (1 + change)
            # Regenerate scenarios with new EV
            adjusted_scenarios = []
            for s in base_scenarios:
                new_scenario = ScenarioOutput(
                    scenario_type=s.scenario_type,
                    exit_value=s.exit_value * (1 + change),
                    probability=s.probability,
                    time_to_exit=s.time_to_exit,
                    investor_proceeds=0,
                    gross_moic=0,
                    irr=0
                )
                adjusted_scenarios.append(new_scenario)
            
            # Reapply waterfall
            adjusted_scenarios = self.apply_waterfall(
                adjusted_scenarios, capital_structure, 
                investment_amount, ownership_percent
            )
            
            # Calculate new fair value
            fv = self.calculate_fair_value(adjusted_scenarios)
            ev_results.append({
                'change': change,
                'enterprise_value': adjusted_ev,
                'fair_value': fv['fair_value'],
                'expected_moic': fv['expected_moic']
            })
        
        sensitivities['enterprise_value'] = ev_results
        
        # Time to exit sensitivity
        time_changes = [-1, -0.5, 0, 0.5, 1]  # Years
        time_results = []
        
        for change in time_changes:
            adjusted_scenarios = []
            for s in base_scenarios:
                new_scenario = ScenarioOutput(
                    scenario_type=s.scenario_type,
                    exit_value=s.exit_value,
                    probability=s.probability,
                    time_to_exit=max(0.5, s.time_to_exit + change),
                    investor_proceeds=s.investor_proceeds,
                    gross_moic=s.gross_moic,
                    irr=(s.gross_moic ** (1 / max(0.5, s.time_to_exit + change)) - 1) * 100
                )
                adjusted_scenarios.append(new_scenario)
            
            fv = self.calculate_fair_value(adjusted_scenarios)
            time_results.append({
                'change': change,
                'expected_irr': fv['expected_irr']
            })
        
        sensitivities['time_to_exit'] = time_results
        
        return sensitivities
    
    def generate_ipev_report(self, analysis_results: Dict) -> Dict:
        """Generate IPEV-compliant valuation report"""
        
        report = {
            'valuation_date': datetime.now().isoformat(),
            'methodology': 'IPEV PWERM (Probability-Weighted Expected Return Method)',
            'compliance': 'IPEV Valuation Guidelines December 2022',
            
            'enterprise_value': analysis_results['enterprise_value'],
            'fair_value': analysis_results['fair_value'],
            
            'key_assumptions': analysis_results['assumptions'],
            'scenario_analysis': analysis_results['scenarios_summary'],
            'sensitivity_analysis': analysis_results['sensitivity'],
            
            'governance': {
                'preparer': 'IPEV PWERM Analyzer',
                'reviewer': 'Pending',
                'approval': 'Pending',
                'documentation': 'Complete'
            },
            
            'disclosures': {
                'valuation_approach': analysis_results['ev_method'],
                'key_inputs': analysis_results['key_inputs'],
                'material_changes': analysis_results.get('material_changes', []),
                'calibration': analysis_results.get('calibration', {})
            }
        }
        
        return report

def main():
    """Main execution function for API integration"""
    
    try:
        # Read input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract parameters
        company_data = input_data.get('company_data', {})
        assumptions = input_data.get('assumptions', {})
        fund_config = input_data.get('fund_config', {})
        existing_comparables = input_data.get('existing_comparables', [])
        
        # Initialize analyzer
        analyzer = IPEVPWERMAnalyzer()
        
        # Prepare market data from existing comparables
        market_data = {
            'comparables': existing_comparables,
            'sector': company_data.get('sector', 'SaaS')
        }
        
        # Step 1: Determine Enterprise Value
        ev_result = analyzer.determine_enterprise_value(
            company_data, 
            market_data,
            method='multiple'  # Use market multiples as primary method
        )
        
        enterprise_value = ev_result['enterprise_value']
        
        # Step 2: Generate scenarios
        company_stage = assumptions.get('stage', 'growth')
        scenarios = analyzer.generate_scenarios(
            enterprise_value,
            market_data,
            company_stage
        )
        
        # Step 3: Define capital structure (simplified for now)
        capital_structure = CapitalStructure(
            common_shares=10_000_000,
            preferred_shares=3_000_000,
            liquidation_preference=assumptions.get('liquidation_preference', 50_000_000),
            participation_cap=assumptions.get('participation_cap', 2.0),
            conversion_price=assumptions.get('conversion_price', 10.0),
            employee_options=1_500_000,
            debt=assumptions.get('debt', 0)
        )
        
        # Step 4: Apply waterfall
        investment_amount = assumptions.get('investment_amount', 10_000_000)
        ownership_percent = assumptions.get('ownership_percent', 0.15)
        
        scenarios = analyzer.apply_waterfall(
            scenarios,
            capital_structure,
            investment_amount,
            ownership_percent
        )
        
        # Step 5: Calculate fair value
        fair_value_result = analyzer.calculate_fair_value(scenarios)
        
        # Step 6: Sensitivity analysis
        sensitivity = analyzer.perform_sensitivity_analysis(
            scenarios,
            enterprise_value,
            capital_structure,
            investment_amount,
            ownership_percent
        )
        
        # Prepare output
        output = {
            'methodology': 'IPEV PWERM',
            'compliance': 'IPEV Guidelines December 2022',
            
            'enterprise_value_analysis': ev_result,
            'fair_value_analysis': fair_value_result,
            
            'summary': {
                'company_name': company_data.get('name'),
                'enterprise_value': enterprise_value,
                'fair_value': fair_value_result['fair_value'],
                'expected_moic': fair_value_result['expected_moic'],
                'expected_irr': fair_value_result['expected_irr'],
                'success_probability': fair_value_result['probabilities']['success_probability'],
                'loss_probability': fair_value_result['probabilities']['loss_probability']
            },
            
            'scenarios': [
                {
                    'type': s.scenario_type.value,
                    'exit_value': s.exit_value,
                    'probability': s.probability,
                    'time_to_exit': s.time_to_exit,
                    'investor_proceeds': s.investor_proceeds,
                    'gross_moic': s.gross_moic,
                    'irr': s.irr
                }
                for s in scenarios[:20]  # Return top 20 scenarios
            ],
            
            'sensitivity_analysis': sensitivity,
            
            'key_assumptions': {
                'investment_amount': investment_amount,
                'ownership_percent': ownership_percent * 100,
                'liquidation_preference': capital_structure.liquidation_preference,
                'company_stage': company_stage
            }
        }
        
        # Output as JSON
        print(json.dumps(output, indent=2))
        
    except Exception as e:
        error_output = {
            'error': str(e),
            'type': 'IPEV PWERM Analysis Error',
            'details': 'Failed to complete IPEV-compliant PWERM analysis'
        }
        print(json.dumps(error_output))
        sys.exit(1)

if __name__ == '__main__':
    main()