#!/usr/bin/env python3
import asyncio
import json
from datetime import datetime
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_full_extraction():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test request
    request = {
        "prompt": "Compare @Tracelight with @OriginRobotics for Series A from my 305m fund with 0.4 dpi not recycled in year 3 q3, with 104m to deploy",
        "output_format": "analysis",
        "context": {}
    }
    
    print(f"\n{'='*80}")
    print(f"Running test at {datetime.now()}")
    print(f"Request: {json.dumps(request, indent=2)}")
    print(f"{'='*80}\n")
    
    try:
        result = await orchestrator.process_request(
            prompt=request['prompt'],
            output_format=request['output_format'],
            context=request['context']
        )
        
        # Save full output
        output_file = f"test_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"✅ Test completed successfully")
        print(f"📄 Full output saved to: {output_file}")
        
        # Print key fields we're looking for
        if 'companies' in result:
            for company in result.get('companies', []):
                print(f"\n{'='*40}")
                print(f"Company: {company.get('name', 'Unknown')}")
                print(f"  business_model: {company.get('business_model', 'NOT FOUND')}")
                print(f"  category: {company.get('category', 'NOT FOUND')}")
                print(f"  vertical: {company.get('vertical', 'NOT FOUND')}")
                print(f"  compute_intensity: {company.get('compute_intensity', 'NOT FOUND')}")
                print(f"  compute_signals: {company.get('compute_signals', 'NOT FOUND')}")
                print(f"  revenue: {company.get('revenue', 'NOT FOUND')}")
                print(f"  valuation: {company.get('valuation', 'NOT FOUND')}")
                print(f"  TAM: {company.get('market_position', {}).get('TAM', 'NOT FOUND')}")
                print(f"  investors: {company.get('investors', 'NOT FOUND')}")
                
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Still save error output
        error_file = f"test_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(error_file, 'w') as f:
            f.write(f"Error: {e}\n\n")
            f.write(traceback.format_exc())
        print(f"📄 Error details saved to: {error_file}")
        return None

if __name__ == "__main__":
    asyncio.run(test_full_extraction())