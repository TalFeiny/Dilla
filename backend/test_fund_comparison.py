#!/usr/bin/env python3
"""
Test the enhanced fund intelligence system with Goodcall and Telli comparison
"""

import asyncio
import json
from datetime import datetime
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_fund_comparison():
    """Test comparing two companies for a specific fund context"""
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Fund context from natural language
    prompt = "compare @Goodcall and @Telli for my 198m fund, with 78m to deploy in year 3 q1, with 0.3 dpi recycled, 14 portfolio companies 2 exits, 2.34 tvpi"
    
    # Process the request
    request = {
        "prompt": prompt,
        "output_format": "analysis",
        "context": {}
    }
    
    print(f"Testing fund comparison at {datetime.now()}")
    print(f"Prompt: {prompt}")
    print("-" * 80)
    
    try:
        # Process through orchestrator
        result = await orchestrator.process_request(
            prompt=request["prompt"],
            output_format=request["output_format"],
            context=request["context"]
        )
        
        # Save the full response
        with open('test_fund_comparison_result.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print("\n✅ Test completed successfully!")
        print(f"Full results saved to: test_fund_comparison_result.json")
        
        # Print summary
        if 'companies' in result:
            print("\n📊 COMPANIES ANALYZED:")
            for company in result['companies']:
                print(f"\n🏢 {company.get('company', 'Unknown')}")
                print(f"   Stage: {company.get('stage', 'N/A')}")
                print(f"   Valuation: ${company.get('valuation', 0)/1e6:.1f}M")
                print(f"   Business Model: {company.get('business_model', 'N/A')}")
                
                # Print fund fit score if available
                if 'fund_fit_score' in company:
                    score_data = company['fund_fit_score']
                    print(f"\n   📈 Fund Fit Analysis:")
                    if 'scores' in score_data:
                        for key, value in score_data['scores'].items():
                            print(f"      {key}: {value}/100")
                    
                    if 'recommendations' in score_data:
                        print(f"\n   💡 Recommendations:")
                        for rec in score_data['recommendations'][:3]:
                            print(f"      {rec}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_fund_comparison())
