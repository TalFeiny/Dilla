#!/usr/bin/env python3
"""Test the enhanced valuation system with risk-adjusted returns and growth decay"""

import asyncio
import json
from app.services.valuation_engine_service import ValuationEngineService, ValuationRequest
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_enhanced_valuation():
    """Test the new risk-adjusted return and growth decay features"""
    
    # Initialize services
    valuation_engine = ValuationEngineService()
    gap_filler = IntelligentGapFiller()
    
    # Test company data
    company_data = {
        "company": "@Deel",
        "revenue": 25_000_000,  # $25M ARR
        "growth_rate": 1.5,      # 150% YoY growth
        "stage": "Series B",
        "valuation": 500_000_000, # $500M valuation
        "burn_rate": 2_000_000,   # $2M/month burn
        "gross_margin": 0.75,
        "nrr": 1.25,              # 125% NRR
        "just_raised": True       # Just closed funding
    }
    
    print("="*60)
    print("ENHANCED VALUATION ANALYSIS")
    print("="*60)
    print(f"Company: {company_data['company']}")
    print(f"Revenue: ${company_data['revenue']:,.0f}")
    print(f"Growth Rate: {company_data['growth_rate']*100:.0f}%")
    print(f"Current Valuation: ${company_data['valuation']:,.0f}")
    print(f"Revenue Multiple: {company_data['valuation']/company_data['revenue']:.1f}x")
    
    # 1. Test growth decay modeling with investor math
    print("\n" + "="*60)
    print("1. GROWTH DECAY & REVENUE MULTIPLE ANALYSIS")
    print("="*60)
    
    investor_math = gap_filler.calculate_investor_math(company_data)
    if investor_math:
        print(f"Stage: {investor_math['investor_math'].get('stage', 'unknown')}")
        print(f"Decay Factor: {investor_math['investor_math'].get('decay_factor', 0):.2f}")
        print(f"Growth-Adjusted Multiple: {investor_math['investor_math'].get('growth_adjusted_multiple', 0):.1f}x")
        print(f"Max Entry Multiple: {investor_math['investor_math'].get('max_entry_multiple', 0):.1f}x")
        
        print("\nGrowth Projection (with decay):")
        for i, growth in enumerate(investor_math['growth_projection']['year_by_year_growth'], 1):
            print(f"  Year {i}: {growth*100:.0f}% growth")
        
        print(f"\nExit Assumptions:")
        print(f"  Exit Multiple: {investor_math['exit_assumptions']['exit_multiple']:.1f}x")
        print(f"  Exit Valuation: ${investor_math['exit_assumptions']['exit_valuation']:,.0f}")
        
        print(f"\nDeal Analysis:")
        print(f"  Current Ask: ${investor_math['deal_analysis']['current_ask']:,.0f}")
        print(f"  Max We Should Pay: ${investor_math['deal_analysis']['max_we_should_pay']:,.0f}")
        print(f"  Assessment: {investor_math['deal_analysis']['deal_assessment']}")
    
    # 2. Test PWERM scenarios with risk-adjusted returns
    print("\n" + "="*60)
    print("2. RISK-ADJUSTED RETURNS & DPI IMPACT")
    print("="*60)
    
    valuation_request = ValuationRequest(
        revenue=company_data['revenue'],
        growth_rate=company_data['growth_rate'],
        burn_rate=company_data['burn_rate'],
        stage=company_data['stage'],
        last_valuation=company_data['valuation'],
        arr=company_data['revenue'],
        gross_margin=company_data['gross_margin']
    )
    
    # Calculate PWERM scenarios
    scenarios = valuation_engine.generate_simple_scenarios(company_data)
    
    print("\nScenario Analysis:")
    for scenario_name in ['bear', 'base', 'bull']:
        if scenario_name in scenarios:
            s = scenarios[scenario_name]
            print(f"\n{scenario_name.upper()} CASE:")
            print(f"  Exit Value: ${s.get('exit_value', 0):,.0f}")
            print(f"  Probability: {s.get('probability', 0)*100:.0f}%")
            print(f"  IRR: {s.get('irr', 0)*100:.1f}%")
            print(f"  Risk-Adjusted IRR: {s.get('risk_adjusted_irr', 0)*100:.1f}%")
            print(f"  DPI Contribution: {s.get('dpi_contribution', 0)*100:.2f}%")
            print(f"  Fund Impact: {s.get('fund_impact', 'N/A')}")
    
    # Risk metrics
    if 'risk_metrics' in scenarios:
        risk = scenarios['risk_metrics']
        print(f"\nRisk Metrics:")
        print(f"  Expected IRR: {risk.get('expected_irr', 0)*100:.1f}%")
        print(f"  Volatility: {risk.get('volatility', 0)*100:.1f}%")
        print(f"  Sharpe Ratio: {risk.get('sharpe_ratio', 0):.2f}")
        print(f"  Probability-Weighted DPI: {risk.get('probability_weighted_dpi', 0)*100:.2f}%")
        print(f"  Risk Score: {risk.get('risk_score', 0):.0f}/100")
    
    # 3. Test funding path scenarios
    print("\n" + "="*60)
    print("3. FUNDING PATH SCENARIO ANALYSIS")
    print("="*60)
    
    if 'funding_path_analysis' in scenarios:
        for path_name, path_data in scenarios['funding_path_analysis'].items():
            print(f"\n{path_name.upper()} PATH: {path_data['description']}")
            print(f"  Final Ownership: {path_data['final_ownership']*100:.1f}%")
            print(f"  Total Dilution: {path_data['total_dilution']*100:.1f}%")
            
            # Show exit scenarios for this path
            if 'exit_scenarios' in path_data and 'base' in path_data['exit_scenarios']:
                base = path_data['exit_scenarios']['base']
                print(f"  Base Case IRR: {base['irr']*100:.1f}%")
                print(f"  Base Case DPI: {base['dpi_contribution']*100:.2f}%")
            
            print(f"  Recommendation: {path_data.get('recommendation', 'N/A')}")
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_enhanced_valuation())