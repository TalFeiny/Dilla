#!/usr/bin/env python3
"""
Run liquidation preference analysis on PWERM scenarios
"""

import sys
import json
from datetime import datetime
from liquidation_preference_calculator import (
    CapTable, LiquidationWaterfall, LiquidationScenarioAnalyzer,
    LiquidationType, FundingRound
)

def main(input_path: str, output_path: str):
    """Run liquidation analysis on provided cap table and scenarios"""
    
    # Load input data
    with open(input_path, 'r') as f:
        data = json.load(f)
    
    # Build cap table
    cap_table = CapTable()
    
    # Add common shares
    if 'common_shares' in data['company']:
        cap_table.common_shares = data['company']['common_shares']
        cap_table.option_pool = data['company'].get('option_pool', 0)
        cap_table.total_shares = sum(cap_table.common_shares.values()) + cap_table.option_pool
    
    # Add funding rounds
    for round_data in data['funding_rounds']:
        cap_table.add_funding_round(round_data)
    
    # Create analyzers
    waterfall = LiquidationWaterfall(cap_table)
    analyzer = LiquidationScenarioAnalyzer(cap_table)
    
    # Calculate preference stack
    preference_stack = sum(r.liquidation_preference for r in cap_table.funding_rounds)
    
    # Find conversion thresholds
    conversion_thresholds = waterfall.find_conversion_threshold()
    
    # Analyze each scenario
    enhanced_scenarios = analyzer.analyze_scenario_returns(data['scenarios'])
    
    # Generate waterfall chart data for visualization
    # Create exit values from 0 to 2x the highest scenario value
    max_value = max(s['value'] for s in data['scenarios'])
    exit_values = [i * max_value * 0.02 for i in range(101)]  # 0 to 2x in 100 steps
    waterfall_chart_data = waterfall.generate_waterfall_chart_data(exit_values)
    
    # Calculate key metrics
    ownership_table = cap_table.calculate_ownership()
    
    # Identify key insights
    insights = generate_insights(cap_table, enhanced_scenarios, conversion_thresholds)
    
    # Prepare output
    output = {
        'preference_stack': preference_stack,
        'conversion_thresholds': conversion_thresholds,
        'ownership_table': ownership_table,
        'enhanced_scenarios': enhanced_scenarios,
        'waterfall_chart_data': waterfall_chart_data,
        'insights': insights,
        'cap_table_summary': {
            'total_raised': sum(r.amount_raised for r in cap_table.funding_rounds),
            'rounds': len(cap_table.funding_rounds),
            'total_shares': cap_table.total_shares,
            'participating_rounds': sum(1 for r in cap_table.funding_rounds 
                                      if r.liquidation_type != LiquidationType.NON_PARTICIPATING)
        }
    }
    
    # Write output
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)

def generate_insights(cap_table: CapTable, scenarios: list, thresholds: list) -> dict:
    """Generate key insights from the liquidation analysis"""
    
    insights = {
        'preference_overhang': False,
        'common_squeeze': False,
        'misaligned_incentives': False,
        'key_observations': []
    }
    
    # Check preference overhang
    preference_stack = sum(r.liquidation_preference for r in cap_table.funding_rounds)
    median_scenario_value = sorted([s['value'] for s in scenarios])[len(scenarios)//2]
    
    if preference_stack > median_scenario_value * 0.5:
        insights['preference_overhang'] = True
        insights['key_observations'].append(
            f"Liquidation preferences of ${preference_stack/1e6:.1f}M represent "
            f"{preference_stack/median_scenario_value*100:.0f}% of median exit value. "
            "This could misalign incentives."
        )
    
    # Check common squeeze
    for scenario in scenarios:
        if scenario['value'] < preference_stack * 1.5:
            common_dilution = scenario['liquidation_analysis']['common_dilution']
            if common_dilution > 0.5:  # Common getting less than 50% of their ownership
                insights['common_squeeze'] = True
                break
    
    if insights['common_squeeze']:
        insights['key_observations'].append(
            "Common shareholders face significant dilution in lower exit scenarios. "
            "Consider employee retention risks."
        )
    
    # Check for participating preferred
    participating_rounds = [r for r in cap_table.funding_rounds 
                          if r.liquidation_type != LiquidationType.NON_PARTICIPATING]
    if participating_rounds:
        insights['misaligned_incentives'] = True
        total_participating = sum(r.amount_raised for r in participating_rounds)
        insights['key_observations'].append(
            f"${total_participating/1e6:.1f}M in participating preferred. "
            "This creates different incentives between investor classes."
        )
    
    # Add conversion threshold insights
    if thresholds:
        first_threshold = thresholds[0]['threshold']
        insights['key_observations'].append(
            f"First conversion threshold at ${first_threshold/1e6:.1f}M exit value. "
            f"Below this, {thresholds[0]['round']} investors take liquidation preference."
        )
    
    return insights

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python run_liquidation_analysis.py <input.json> <output.json>")
        sys.exit(1)
    
    main(sys.argv[1], sys.argv[2])