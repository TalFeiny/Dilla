#!/usr/bin/env python3
"""
Complete system test for @Howieai - monitoring all stages
"""
import asyncio
import json
import sys
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, '/Users/admin/code/dilla-ai/backend')

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_complete_system():
    """Test the entire pipeline with @Howieai"""
    print("\n" + "="*80)
    print("COMPLETE SYSTEM TEST: @Howieai")
    print("="*80 + "\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test request
    request = {
        'prompt': 'Analyze @Howieai - show market sizing, valuation, and investment case',
        'output_format': 'analysis',
        'context': {}
    }
    
    print("📋 Request:", json.dumps(request, indent=2))
    print("\n" + "-"*40 + "\n")
    
    try:
        # Process request
        print("🔄 Processing request through UnifiedMCPOrchestrator...")
        result = await orchestrator.process_request(request)
        
        # Check what we got back
        print(f"\n✅ Response received!")
        print(f"   Keys: {list(result.keys())}")
        
        # Check for errors
        if 'error' in result:
            print(f"\n❌ ERROR: {result['error']}")
            return
        
        # Check companies
        if 'companies' not in result or len(result.get('companies', [])) == 0:
            print("\n⚠️ No companies returned!")
            print(f"Full result: {json.dumps(result, indent=2)[:500]}")
            return
            
        company = result['companies'][0]
        print(f"\n🏢 Company Found: {company.get('name', 'Unknown')}")
        print(f"   Stage: {company.get('stage', 'Unknown')}")
        print(f"   Business Model: {company.get('business_model', 'Unknown')}")
        
        # 1. CHECK DATA EXTRACTION
        print("\n" + "="*40)
        print("1️⃣ DATA EXTRACTION CHECK")
        print("="*40)
        
        print(f"Revenue: ${company.get('revenue', 0):,.0f}")
        print(f"Valuation: ${company.get('valuation', 0):,.0f}")
        print(f"Total Raised: ${company.get('total_raised', 0):,.0f}")
        print(f"Employees: {company.get('employee_count', 'Unknown')}")
        print(f"Founded: {company.get('founded_year', 'Unknown')}")
        
        # Check if data was fetched
        if company.get('revenue', 0) == 0:
            print("⚠️ No revenue data found - checking inference...")
        
        # 2. CHECK INTELLIGENT GAP FILLER
        print("\n" + "="*40)
        print("2️⃣ INTELLIGENT GAP FILLER CHECK")
        print("="*40)
        
        if 'inferences' in company:
            print(f"Inferences made: {len(company['inferences'])} fields")
            for field, inference in list(company.get('inferences', {}).items())[:5]:
                if isinstance(inference, dict):
                    print(f"  • {field}: {inference.get('value')} (confidence: {inference.get('confidence', 0):.1%})")
        else:
            print("⚠️ No inferences field found")
            
        # 3. CHECK MARKET SIZING
        print("\n" + "="*40)
        print("3️⃣ MARKET SIZING CHECK")
        print("="*40)
        
        if 'investment_case' in company:
            inv_case = company['investment_case']
            market = inv_case.get('market_position', {})
            
            tam = market.get('tam', 0)
            print(f"TAM: ${tam:,.0f}")
            
            # Check if TAM is realistic
            if tam > 1_000_000_000_000:  # Over 1 trillion
                print(f"❌ TAM is UNREALISTIC: ${tam/1e12:.1f} TRILLION")
                print("   This is the labor pool, not the software TAM!")
            elif tam > 100_000_000_000:  # Over 100 billion
                print(f"⚠️ TAM seems high: ${tam/1e9:.1f} billion")
            else:
                print(f"✅ TAM is realistic: ${tam/1e9:.2f} billion")
                
            print(f"Current Penetration: {market.get('current_penetration', 'N/A')}")
            print(f"Target Penetration: {market.get('target_penetration', 'N/A')}")
            print(f"Required CAGR: {market.get('required_cagr', 'N/A')}")
            
            # Check TAM calculation details
            if 'tam_calculation' in market:
                tam_calc = market['tam_calculation']
                print("\nTAM Calculation Methods:")
                print(f"  • Primary TAM: ${tam_calc.get('primary_tam', 0):,.0f}")
                print(f"  • Bottom-up TAM: ${tam_calc.get('bottom_up_tam', 0):,.0f}")
                print(f"  • Segment TAM: ${tam_calc.get('segment_tam', 0):,.0f}")
                print(f"  • Labor Pool Ceiling: ${tam_calc.get('labor_pool_ceiling', 0):,.0f}")
        else:
            print("❌ No investment_case found!")
            
        # 4. CHECK VALUATION CALCULATIONS
        print("\n" + "="*40)
        print("4️⃣ VALUATION ENGINE CHECK")
        print("="*40)
        
        if 'valuation_analysis' in company:
            val = company['valuation_analysis']
            print(f"Entry Valuation: ${val.get('entry_valuation', 0):,.0f}")
            print(f"Target Exit: ${val.get('target_exit', 0):,.0f}")
            print(f"Multiple: {val.get('multiple', 0):.1f}x")
        else:
            print("⚠️ No valuation_analysis found")
            
        # 5. CHECK OWNERSHIP & CAP TABLE
        print("\n" + "="*40)
        print("5️⃣ OWNERSHIP & CAP TABLE CHECK")
        print("="*40)
        
        if 'investment_case' in company:
            ownership = inv_case.get('ownership_recommendation', {})
            print(f"Current Valuation: ${ownership.get('current_valuation', 0):,.0f}")
            print(f"Recommendation: {ownership.get('recommendation', 'N/A')}")
            
            check_sizes = ownership.get('check_sizes', {})
            if check_sizes:
                print("\nCheck Sizes:")
                for level, data in check_sizes.items():
                    if isinstance(data, dict):
                        print(f"  • {level}: ${data.get('check_size', 0)/1e6:.1f}M for {data.get('ownership', 0):.1%}")
        
        # 6. CHECK CITATIONS
        print("\n" + "="*40)
        print("6️⃣ CITATIONS CHECK")
        print("="*40)
        
        citations = result.get('citations', [])
        print(f"Total Citations: {len(citations)}")
        if citations:
            print("\nFirst 3 citations:")
            for i, cite in enumerate(citations[:3]):
                print(f"  [{i+1}] {cite.get('source', 'Unknown')}")
                if 'url' in cite:
                    print(f"      URL: {cite['url'][:80]}...")
        else:
            print("⚠️ No citations found - data may not be properly sourced")
            
        # 7. CHECK FOR ERRORS/WARNINGS
        print("\n" + "="*40)
        print("7️⃣ ERROR/WARNING CHECK")
        print("="*40)
        
        # Check for None values in critical fields
        critical_fields = ['revenue', 'valuation', 'total_raised', 'employee_count']
        none_fields = []
        for field in critical_fields:
            if company.get(field) is None:
                none_fields.append(field)
                
        if none_fields:
            print(f"❌ None values found in: {', '.join(none_fields)}")
            print("   This will cause calculation errors!")
        else:
            print("✅ No None values in critical fields")
            
        # Final Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        issues = []
        if tam > 1_000_000_000_000:
            issues.append("TAM is using labor pool instead of software market")
        if not citations:
            issues.append("No citations found")
        if none_fields:
            issues.append(f"None values in: {', '.join(none_fields)}")
        if company.get('revenue', 0) == 0:
            issues.append("No revenue data (inference may have failed)")
            
        if issues:
            print("\n🔴 Issues Found:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("\n🟢 All systems working correctly!")
            
        # Save full result for inspection
        output_file = f"howieai_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Full result saved to: {output_file}")
        
    except Exception as e:
        print(f"\n💥 EXCEPTION OCCURRED: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        
        # Try to identify where it broke
        print("\n🔍 Likely failure point:")
        tb = traceback.extract_tb(e.__traceback__)
        for frame in tb[-3:]:  # Last 3 frames
            print(f"  File: {frame.filename}:{frame.lineno}")
            print(f"  Function: {frame.name}")
            print(f"  Line: {frame.line}")

if __name__ == "__main__":
    print("Starting complete system test...")
    asyncio.run(test_complete_system())
    print("\nTest complete!")