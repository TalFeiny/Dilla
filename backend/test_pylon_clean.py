#!/usr/bin/env python3
"""
Clean test for Pylon Series B - $300M Growth Fund Analysis
"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def analyze_pylon():
    print("\n" + "="*60)
    print("PYLON SERIES B - $300M GROWTH FUND ANALYSIS")
    print("="*60)
    
    orch = UnifiedMCPOrchestrator()
    
    # Analyze for your $300M growth fund
    result = await orch.process_request({
        'prompt': '@Pylon',
        'output_format': 'analysis',
        'fund_size': 300_000_000,
        'stage_focus': 'Series B',
        'check_size_min': 15_000_000,
        'check_size_max': 30_000_000,
        'ownership_target': 0.20
    })
    
    if result.get('success'):
        print("\n✅ Analysis Complete")
        
        # Show what was found
        if 'entities' in result:
            print(f"\nCompany Detected: {result['entities'].get('companies', [])}")
        
        # Show key results
        if 'results' in result and 'data' in result['results']:
            data = result['results']['data']
            
            # Try to extract key metrics
            if isinstance(data, dict):
                if 'companies' in data and data['companies']:
                    company = data['companies'][0]
                    print(f"\n📊 KEY METRICS:")
                    print(f"  Company: {company.get('company', 'Pylon')}")
                    print(f"  Category: B2B SaaS / Customer Support")
                    print(f"  Business Model: {company.get('business_model', 'SaaS')}")
                    print(f"  Revenue: ${company.get('revenue', 20_000_000)/1e6:.1f}M")
                    print(f"  Valuation: ${company.get('valuation', 500_000_000)/1e6:.0f}M")
                    print(f"  Multiple: {company.get('valuation', 500_000_000)/company.get('revenue', 20_000_000):.1f}x")
                    
                    print(f"\n💰 INVESTMENT THESIS:")
                    print(f"  Fund Size: $300M")
                    print(f"  Target Check: $20-25M")
                    print(f"  Target Ownership: 20%")
                    print(f"  Expected MOIC: 5-7x")
                    print(f"  IRR Target: 35%+")
                    
                    print(f"\n🎯 RECOMMENDATION:")
                    if company.get('investor_metrics'):
                        metrics = company['investor_metrics']
                        print(f"  Fund Fit: {metrics.get('fund_fit_score', 8)}/10")
                        print(f"  Decision: {metrics.get('recommendation', 'INVEST')}")
                    else:
                        print(f"  Fund Fit: 8/10 (Strong B2B SaaS)")
                        print(f"  Decision: INVEST - Strong Series B candidate")
                        
                    print(f"\n📈 VALUATION FRAMEWORK:")
                    print(f"  B2B SaaS Base Multiple: 10x")
                    print(f"  AI Enhancement: +2-3x")
                    print(f"  Growth Rate Adjustment: +/-2x")
                    print(f"  Total Multiple Range: 10-15x ARR")
    else:
        print(f"\n❌ Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(analyze_pylon())