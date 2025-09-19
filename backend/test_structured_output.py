#!/usr/bin/env python3
import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

async def test_structured_output():
    """Test that structured output format returns citations and charts"""
    orchestrator = get_unified_orchestrator()
    
    # Test with analysis format (should map to structured)
    prompt = "Compare @Deel and @Ramp for investment"
    
    print("Testing with output_format='structured'...")
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format="structured",
        context={}
    )
    
    print("\nResult keys:", result.keys())
    print("Success:", result.get('success'))
    
    # Check the 'results' key
    results = result.get('results')
    print("\nType of results:", type(results))
    
    if isinstance(results, dict):
        print("Results is a dict with keys:", results.keys())
        print("Has citations:", 'citations' in results)
        print("Has charts:", 'charts' in results)
        print("Has companies:", 'companies' in results)
        print("Has data:", 'data' in results)
        
        if 'citations' in results:
            print(f"Number of citations: {len(results['citations'])}")
        if 'charts' in results:
            print(f"Number of charts: {len(results['charts'])}")
    else:
        print("Results is NOT a dict, it's:", type(results))
        print("First 500 chars:", str(results)[:500])

if __name__ == "__main__":
    asyncio.run(test_structured_output())