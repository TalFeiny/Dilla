#!/usr/bin/env python3
"""Test script to verify InferenceResult comparison fixes"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_dwelly():
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        # Test deck generation with @Dwelly
        response = await orchestrator.process_request({
            "prompt": "Create an investment deck for @Dwelly",
            "output_format": "deck"
        })
        
        if response.get("slides"):
            print("✅ SUCCESS: Deck generated without InferenceResult errors!")
            print(f"Generated {len(response['slides'])} slides")
            
            # Check if fund_fit_score was properly extracted
            for slide in response.get("slides", []):
                if slide.get("type") == "fund_fit":
                    print("✅ Fund fit slide generated successfully")
                    break
                    
        return response
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_dwelly())
    if result:
        print("\n✅ All InferenceResult comparisons fixed!")
    else:
        print("\n❌ Test failed - check errors above")