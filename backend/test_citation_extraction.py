#!/usr/bin/env python3
"""
Test the improved citation-based extraction for Lunio and Connexone
"""
import asyncio
import logging
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.structured_data_extractor import StructuredDataExtractor
from app.services.intelligent_gap_filler import IntelligentGapFiller

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_extraction():
    """Test extraction with citation requirements"""
    
    # Initialize services
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test companies
    companies = ["@Lunio", "@Connexone"]
    
    for company in companies:
        print(f"\n{'='*60}")
        print(f"Testing extraction for: {company}")
        print(f"{'='*60}")
        
        try:
            # Execute company fetch
            result = await orchestrator._execute_company_fetch({"company": company})
            
            if result and "companies" in result:
                company_data = result["companies"][0] if result["companies"] else {}
                
                # Check funding data
                print(f"\nExtracted data for {company}:")
                print(f"- Total funding: ${company_data.get('total_funding', 0):,.0f}")
                print(f"- Valuation: ${company_data.get('valuation', 0):,.0f}")
                print(f"- Revenue: ${company_data.get('revenue', 0):,.0f}")
                print(f"- Stage: {company_data.get('stage', 'Unknown')}")
                
                # Check funding rounds with citations
                funding_rounds = company_data.get('funding_rounds', [])
                if funding_rounds:
                    print(f"\nFunding rounds ({len(funding_rounds)} found):")
                    for round_data in funding_rounds[:3]:  # Show first 3
                        amount = round_data.get('amount', 0)
                        round_name = round_data.get('round', 'Unknown')
                        citation = round_data.get('citation', {})
                        
                        print(f"\n  {round_name}: ${amount:,.0f}")
                        if citation.get('exact_sentence'):
                            print(f"  Citation: \"{citation['exact_sentence'][:200]}...\"")
                            print(f"  Confidence: {citation.get('confidence', 'none')}")
                        else:
                            print(f"  ⚠️  NO CITATION PROVIDED")
                
                # Check if the numbers make sense
                print(f"\n📊 Validation:")
                
                # Lunio should have ~$15M Series A
                if "lunio" in company.lower():
                    total = company_data.get('total_funding', 0)
                    if 10_000_000 < total < 30_000_000:
                        print(f"  ✅ Lunio funding looks correct: ${total:,.0f}")
                    else:
                        print(f"  ❌ Lunio funding seems wrong: ${total:,.0f} (expected ~$15M)")
                
                # Connexone should have ~$115M Series C  
                if "connexone" in company.lower():
                    total = company_data.get('total_funding', 0)
                    if 90_000_000 < total < 150_000_000:
                        print(f"  ✅ Connexone funding looks correct: ${total:,.0f}")
                    else:
                        print(f"  ❌ Connexone funding seems wrong: ${total:,.0f} (expected ~$115M)")
                        
            else:
                print(f"❌ No data extracted for {company}")
                
        except Exception as e:
            print(f"❌ Error testing {company}: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_extraction())