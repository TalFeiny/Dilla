import asyncio
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

# Check if API key is loaded
if not os.getenv('ANTHROPIC_API_KEY') and not os.getenv('CLAUDE_API_KEY'):
    print("WARNING: No ANTHROPIC_API_KEY or CLAUDE_API_KEY found in environment")

async def test_comprehensive_extraction():
    print("\n=== Testing Comprehensive Extraction ===\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Check if Claude is available
    if hasattr(orchestrator, 'claude') and orchestrator.claude:
        print("✅ Claude client initialized successfully")
    else:
        print("❌ Claude client NOT available - will use fallback extraction")
    
    # Test with @Dwelly
    prompt = "Analyze @Dwelly"
    
    print(f"Testing: {prompt}")
    print("-" * 50)
    
    try:
        # Extract entities
        entities = await orchestrator._extract_entities(prompt)
        print(f"Entities extracted: {entities}")
        
        # Build skill chain (this would normally be done)
        context = {"output_format": "structured"}
        
        # Execute company fetch which includes comprehensive extraction
        result = await orchestrator._execute_company_fetch(
            {"companies": entities["companies"]},
            type('ExecutionContext', (), {
                'entities': entities,
                'results': {},
                'fund_params': {
                    'fund_size': 100_000_000,
                    'deployed': 0,
                    'year': 3
                }
            })()
        )
        
        print("\n=== RESULTS ===")
        if result.get("companies"):
            for company_data in result["companies"]:
                print(f"\nCompany: {company_data.get('company')}")
                print(f"Website: {company_data.get('website_url', 'Not found')}")
                print(f"Business Model: {company_data.get('business_model', 'Not extracted')}")
                print(f"Strategy: {company_data.get('strategy', 'Not extracted')}")
                print(f"Sector/Vertical: {company_data.get('sector', 'Not extracted')}")
                print(f"Total Raised: ${company_data.get('total_raised', 0):,}")
                print(f"Acquisitions: {len(company_data.get('acquisitions', []))} found")
                
                if company_data.get('acquisitions'):
                    print("  Acquisitions:")
                    for acq in company_data['acquisitions'][:3]:
                        print(f"    - {acq.get('company', 'Unknown')}")
                
                if company_data.get('founders'):
                    print(f"Founders: {len(company_data['founders'])} found")
                    for founder in company_data['founders'][:2]:
                        print(f"  - {founder.get('name', 'Unknown')} ({founder.get('background', 'No background')})")
        else:
            print("No companies in result")
            print(f"Full result: {json.dumps(result, indent=2)[:1000]}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_comprehensive_extraction())