#!/usr/bin/env python3
"""Quick test for InferenceResult fixes"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def quick_test():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test just the deck generation path where errors occurred
    try:
        response = await orchestrator.process_request({
            "prompt": "Create deck for @Dwelly",
            "output_format": "deck",
            "context": {"skip_tavily": True}  # Skip external calls for speed
        })
        
        # Check both possible locations for slides
        if response.get("slides"):
            print("✅ Deck generated successfully")
            return True
        elif response.get("results", {}).get("slides"):
            print("✅ Deck generated successfully (in results)")
            return True
        else:
            print("❌ No slides generated")
            print("Response structure:", list(response.keys()))
            if "results" in response:
                print("Results keys:", list(response["results"].keys()))
            return False
            
    except TypeError as e:
        if "InferenceResult" in str(e) or "NoneType" in str(e):
            print(f"❌ Type error still present: {e}")
            return False
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_test())
    print("\n✅ ALL INFERENCERESULT FIXES CONFIRMED!" if success else "\n❌ Issues remain")