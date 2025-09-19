#!/usr/bin/env python3
"""Test script to verify revenue inference fixes"""

import asyncio
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'test_revenue_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

import sys
sys.path.append('/Users/admin/code/dilla-ai/backend')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.core.unified_data_models import ExecutionContext, SkillChain

async def test_deel_valuation():
    """Test Deel valuation to ensure revenue inference works"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Create context
    context = ExecutionContext(
        prompt="Value @Deel using PWERM and comparables methods",
        entities={'companies': ['@Deel']},
        skill_chain=SkillChain(
            skills=['company-data-fetcher', 'valuation-engine'],
            context={}
        ),
        results={}
    )
    
    print("\n" + "="*80)
    print("TESTING DEEL VALUATION - REVENUE INFERENCE FIX")
    print("="*80)
    
    # Step 1: Fetch company data
    print("\n1. FETCHING COMPANY DATA...")
    print("-" * 40)
    
    fetch_result = await orchestrator._execute_company_fetch(
        {'companies': ['@Deel']},
        context
    )
    
    if fetch_result.get('companies'):
        company_data = fetch_result['companies'][0]
        
        print(f"✓ Company: {company_data.get('company', 'Unknown')}")
        print(f"✓ Revenue: ${company_data.get('revenue', 0):,.0f}")
        print(f"✓ ARR: ${company_data.get('arr', 0):,.0f}")
        print(f"✓ Stage: {company_data.get('funding_analysis', {}).get('current_stage', 'Unknown')}")
        print(f"✓ Total Raised: ${company_data.get('funding_analysis', {}).get('total_raised', 0):,.0f}")
        
        # Step 2: Run valuation
        print("\n2. RUNNING VALUATION...")
        print("-" * 40)
        
        valuation_result = await orchestrator._execute_valuation(
            {'company': '@Deel'},
            context
        )
        
        if 'error' not in valuation_result:
            print(f"✓ PWERM Fair Value: ${valuation_result.get('pwerm', {}).get('fair_value', 0):,.0f}")
            print(f"✓ DCF Fair Value: ${valuation_result.get('valuation_methods', {}).get('dcf', {}).get('fair_value', 0):,.0f}")
            print(f"✓ Comparables Fair Value: ${valuation_result.get('valuation_methods', {}).get('comparables', {}).get('fair_value', 0):,.0f}")
            
            # Check if revenue was properly inferred
            final_revenue = valuation_result.get('revenue', 0)
            if final_revenue > 0:
                print(f"\n✅ SUCCESS: Revenue properly inferred: ${final_revenue:,.0f}")
            else:
                print(f"\n❌ ISSUE: Revenue not inferred, still 0")
            
            # Save results
            with open('test_revenue_fix_result.json', 'w') as f:
                json.dump({
                    'company_data': {
                        'company': company_data.get('company'),
                        'revenue': company_data.get('revenue'),
                        'arr': company_data.get('arr'),
                        'stage': company_data.get('funding_analysis', {}).get('current_stage')
                    },
                    'valuation_result': {
                        'pwerm': valuation_result.get('pwerm'),
                        'valuation_methods': valuation_result.get('valuation_methods')
                    }
                }, f, indent=2, default=str)
            
            print("\n✓ Results saved to test_revenue_fix_result.json")
        else:
            print(f"❌ Valuation error: {valuation_result.get('error')}")
    else:
        print(f"❌ Fetch error: {fetch_result.get('error', 'Unknown error')}")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_deel_valuation())