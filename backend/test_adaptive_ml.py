#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append('.')
os.environ['PYTHONPATH'] = '.'

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    print("Testing AdaptiveML extraction after JSON fix...")
    orchestrator = UnifiedMCPOrchestrator()
    
    result = await orchestrator.process_request({
        'skill': 'company_analysis',
        'parameters': {
            'companies': ['@AdaptiveML'],
            'analysis_type': 'comprehensive'
        }
    })
    
    # Check if we got good data
    if 'companies' in result and result['companies']:
        company = result['companies'][0]
        print(f"\n✅ Company: {company.get('company', 'Unknown')}")
        print(f"✅ Business Model: {company.get('business_model', 'MISSING')}")
        print(f"✅ Sector: {company.get('sector', 'MISSING')}")
        print(f"✅ Website: {company.get('website_url', 'MISSING')}")
        print(f"✅ Total Raised: ${company.get('total_raised', 0):,}")
        print(f"✅ Funding Rounds: {len(company.get('funding_rounds', []))}")
        
        if company.get('funding_rounds'):
            for round_info in company.get('funding_rounds', []):
                print(f"  - {round_info.get('round', 'Unknown')}: ${round_info.get('amount', 0):,}")
    else:
        print('❌ No company data returned')

if __name__ == '__main__':
    asyncio.run(test())