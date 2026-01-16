"""
Simple test of fund context with partial data
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

async def test_simple():
    """Test with minimal fund context"""
    
    orchestrator = get_unified_orchestrator()
    
    # Test with minimal context - just fund size
    minimal_context = {
        "fund_size": 300_000_000  # Just provide fund size
    }
    
    print("Testing with minimal context (only fund_size)...")
    
    result = await orchestrator.process_request(
        prompt="analyze @Mercury for investment",
        output_format="analysis",
        context=minimal_context
    )
    
    if result.get('success'):
        print("✅ Success with minimal context")
        data = result.get('data', {})
        
        # Check if fund context was properly inferred
        if 'companies' in data:
            company = data['companies'][0] if data['companies'] else {}
            print(f"  Company: {company.get('company', 'Unknown')}")
            print(f"  Optimal check: ${company.get('optimal_check_size', 0)/1e6:.1f}M")
            print(f"  Fund fit score: {company.get('fund_fit_score', 0):.0f}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    # Test with partial context
    partial_context = {
        "fund_size": 150_000_000,
        "portfolio_size": 8,
        "current_dpi": 0.6
    }
    
    print("\nTesting with partial context...")
    
    result2 = await orchestrator.process_request(
        prompt="evaluate @Brex",
        output_format="analysis", 
        context=partial_context
    )
    
    if result2.get('success'):
        print("✅ Success with partial context")
    else:
        print(f"❌ Error: {result2.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_simple())