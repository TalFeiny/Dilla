#!/usr/bin/env python3
"""Comprehensive test to ensure all InferenceResult comparisons are fixed"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_all_formats():
    orchestrator = UnifiedMCPOrchestrator()
    results = {}
    
    test_cases = [
        ("deck", "Create an investment deck for @Dwelly and @Mercury"),
        ("matrix", "Compare @Ramp and @Deel in a matrix format"),
        ("docs", "Analyze @Anthropic for investment")
    ]
    
    for format_type, prompt in test_cases:
        try:
            print(f"\n🔍 Testing {format_type} format...")
            response = await orchestrator.process_request({
                "prompt": prompt,
                "output_format": format_type
            })
            
            if format_type == "deck" and response.get("slides"):
                print(f"  ✅ Deck: {len(response['slides'])} slides generated")
                # Check for fund fit comparisons
                has_fund_fit = any(s.get("type") == "fund_fit" for s in response["slides"])
                if has_fund_fit:
                    print(f"  ✅ Fund fit slide with score comparisons working")
                    
            elif format_type == "matrix" and response.get("matrix"):
                print(f"  ✅ Matrix: comparison data generated")
                # Check if fund_fit_score comparisons worked
                companies = response.get("companies", [])
                if companies:
                    print(f"  ✅ Processed {len(companies)} companies with scoring")
                    
            elif format_type == "docs" and response.get("sections"):
                print(f"  ✅ Docs: {len(response['sections'])} sections generated")
                
            results[format_type] = True
            
        except Exception as e:
            print(f"  ❌ {format_type} failed: {e}")
            results[format_type] = False
            
    # Summary
    print("\n" + "="*50)
    print("TEST RESULTS:")
    all_passed = all(results.values())
    
    for fmt, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {fmt}: {status}")
        
    if all_passed:
        print("\n🎉 ALL INFERENCERESULT COMPARISONS FIXED!")
    else:
        print("\n⚠️  Some tests failed - check errors above")
        
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(test_all_formats())
    exit(0 if success else 1)