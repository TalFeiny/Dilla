#!/usr/bin/env python3
"""
Test the improved market sizing with bottom-up TAM calculation
"""

import asyncio
import logging
from app.services.intelligent_gap_filler import IntelligentGapFiller

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_market_sizing():
    """Test market sizing for different company types"""
    gap_filler = IntelligentGapFiller()
    
    test_companies = [
        {
            'company': 'TestPaymentCo',
            'vertical': 'payments',
            'sector': 'fintech',
            'stage': 'Series A',
            'business_model': 'saas',
            'revenue': 5_000_000,  # $5M ARR
            'description': 'Payment processing platform for SMBs'
        },
        {
            'company': 'TestAICo',
            'vertical': 'ai infrastructure',
            'sector': 'technology', 
            'stage': 'Series B',
            'business_model': 'ai_first',
            'revenue': 10_000_000,  # $10M ARR
            'description': 'AI model training platform',
            'compute_intensity': 'high'
        },
        {
            'company': 'TestHealthCo',
            'vertical': 'healthcare',
            'sector': 'healthtech',
            'stage': 'Seed',
            'business_model': 'saas',
            'revenue': 1_000_000,  # $1M ARR
            'description': 'Clinical AI for radiology'
        }
    ]
    
    for company_data in test_companies:
        print(f"\n{'='*60}")
        print(f"Testing: {company_data['company']}")
        print(f"{'='*60}")
        
        # Calculate market opportunity
        market_opp = gap_filler.calculate_market_opportunity(company_data)
        tam_calc = market_opp['tam_calculation']
        
        print(f"\n📊 Market Analysis for {company_data['company']}:")
        print(f"  Vertical: {company_data['vertical']}")
        print(f"  Stage: {company_data['stage']}")
        print(f"  Current Revenue: ${company_data['revenue']:,.0f}")
        
        print(f"\n🎯 TAM Calculation (Method: {tam_calc['method']}):")
        
        # Show primary TAM (the one we actually use)
        primary_tam = tam_calc.get('primary_tam', 0)
        if primary_tam > 1e9:
            print(f"  Primary TAM: ${primary_tam/1e9:.1f}B")
        else:
            print(f"  Primary TAM: ${primary_tam/1e6:.0f}M")
        
        # Show bottom-up calculation
        print(f"\n📈 Bottom-Up Analysis:")
        print(f"  Estimated ACV: ${tam_calc.get('estimated_acv', 0):,.0f}")
        print(f"  Current Customers: {tam_calc.get('current_customers', 0)}")
        print(f"  Addressable Customers: {tam_calc.get('addressable_customers', 0):,}")
        print(f"  Bottom-up TAM: ${tam_calc.get('bottom_up_tam', 0)/1e6:.0f}M")
        
        # Show growth requirements
        print(f"\n🚀 Growth Requirements to 1% Market Share:")
        print(f"  Current Penetration: {tam_calc.get('current_penetration', 0):.3%}")
        print(f"  Target Penetration: {tam_calc.get('target_penetration', 0.01):.1%}")
        print(f"  Required CAGR: {tam_calc.get('required_cagr', 0):.0%}")
        print(f"  Years to Target: {tam_calc.get('years_to_1_percent', 0)}")
        print(f"  Growth Multiple Needed: {tam_calc.get('required_growth_multiple', 'N/A')}")
        
        # Show margin profile
        margins = tam_calc.get('margin_profile', {})
        print(f"\n💰 Margin Profile ({company_data['business_model']}):")
        print(f"  Gross Margin: {margins.get('gross_margin', 0)*100:.0f}%")
        print(f"  Operating Margin: {margins.get('operating_margin', 0)*100:.0f}%")
        print(f"  {tam_calc.get('path_to_profitability', 'N/A')}")
        
        # Show labor pool ceiling for context
        print(f"\n🏛️ Labor Pool Context (Theoretical Ceiling):")
        labor_ceiling = tam_calc.get('labor_pool_ceiling', 0)
        if labor_ceiling > 1e12:
            print(f"  Sector Labor Pool: ${labor_ceiling/1e12:.1f}T")
        else:
            print(f"  Sector Labor Pool: ${labor_ceiling/1e9:.0f}B")
        print(f"  Current Software Penetration: {tam_calc.get('software_penetration_today', 'N/A')}")
        print(f"  AI Potential: {tam_calc.get('ai_potential_penetration', 'N/A')}")
        
        # Test investment case synthesis
        if company_data['revenue'] > 0:
            print(f"\n📋 Investment Case Synthesis:")
            try:
                investment_case = gap_filler.synthesize_investment_case(company_data)
                
                # Show market position
                market_pos = investment_case.get('market_position', {})
                print(f"  TAM Used: ${market_pos.get('tam', 0)/1e6:.0f}M")
                print(f"  Current Penetration: {market_pos.get('current_penetration', 'N/A')}")
                print(f"  Growth Headroom: {market_pos.get('growth_headroom', 'N/A')}")
                
                # Show decision
                decision = investment_case.get('decision', {})
                print(f"  Investment Decision: {decision.get('decision', 'N/A')}")
                print(f"  Reasoning: {decision.get('primary_reason', 'N/A')}")
            except Exception as e:
                print(f"  Error generating investment case: {e}")

if __name__ == "__main__":
    asyncio.run(test_market_sizing())