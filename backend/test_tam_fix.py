#!/usr/bin/env python3
"""Test TAM calculation fix"""

import asyncio
import traceback
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_tam_calculation():
    """Test TAM calculation with Mercury"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        # Just test the company fetch which triggers TAM calculation
        result = await orchestrator._execute_company_fetch({
            "company": "Mercury"
        })
        
        print(f"✅ TAM calculation succeeded for Mercury")
        if result and "companies" in result and result["companies"]:
            company = result["companies"][0]
            print(f"  TAM: ${company.get('tam', 0):,.0f}")
            print(f"  Revenue: ${company.get('revenue', 0):,.0f}")
        return True
        
    except Exception as e:
        print(f"❌ TAM calculation failed: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_tam_calculation())
    exit(0 if success else 1)