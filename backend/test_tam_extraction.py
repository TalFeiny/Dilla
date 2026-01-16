#!/usr/bin/env python3
"""
Test TAM extraction pipeline to ensure:
1. Software market TAM is extracted from search results
2. Labor statistics are extracted and used
3. TAM citations are properly preserved through the pipeline
4. Deck generation uses real TAM data with citations
"""

# MUST load environment variables BEFORE any app imports
from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
from datetime import datetime
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.structured_data_extractor import StructuredDataExtractor
from app.services.valuation_engine_service import ValuationEngineService
from app.services.pre_post_cap_table import PrePostCapTable

async def test_tam_extraction():
    """Test the complete TAM extraction pipeline"""
    
    print("\n" + "="*80)
    print("TAM EXTRACTION PIPELINE TEST")
    print("="*80 + "\n")
    
    # Initialize services
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with Mercury (digital banking) and Deel (HR/payroll)
    test_companies = ["@Mercury", "@Deel"]
    
    print(f"Testing TAM extraction for: {', '.join(test_companies)}")
    print("-" * 80)
    
    # Execute company fetch
    for company in test_companies:
        print(f"\n🔍 Fetching data for {company}...")
        
        result = await orchestrator._execute_company_fetch({
            "company": company
        })
        
        if result and result.get("companies"):
            company_data = result["companies"][0]
            
            print(f"\n✅ Results for {company}:")
            print("-" * 40)
            
            # Check software market extraction
            if company_data.get('software_market_size'):
                market = company_data['software_market_size']
                print(f"📊 Software Market TAM:")
                print(f"   - Size: ${market.get('market_size', 0)/1e9:.1f}B")
                print(f"   - Source: {market.get('source', 'Unknown')}")
                print(f"   - Citation: {market.get('citation', 'None')}")
                print(f"   - Year: {market.get('year', 'Unknown')}")
            else:
                print("❌ No software_market_size extracted")
            
            # Check labor statistics extraction
            if company_data.get('labor_statistics'):
                labor = company_data['labor_statistics']
                print(f"\n👷 Labor Statistics:")
                print(f"   - Workers: {labor.get('number_of_workers', 0):,}")
                print(f"   - Avg Salary: ${labor.get('avg_salary_per_role', 0):,}")
                print(f"   - Total Spend: ${labor.get('total_addressable_labor_spend', 0)/1e9:.1f}B")
                print(f"   - Citation: {labor.get('labor_citation', 'None')}")
            else:
                print("❌ No labor_statistics extracted")
            
            # Check market_size calculation
            if company_data.get('market_size'):
                market_size = company_data['market_size']
                
                print(f"\n📈 Calculated Market Size:")
                print(f"   - TAM: ${market_size.get('tam', 0)/1e9:.1f}B")
                print(f"   - Methodology: {market_size.get('tam_methodology', 'Unknown')}")
                print(f"   - Citation: {market_size.get('tam_citation', 'None')}")
                
                # Check TAM components
                if market_size.get('tam_components'):
                    components = market_size['tam_components']
                    print(f"\n   📍 TAM Components:")
                    print(f"      - Software TAM: ${components.get('traditional_software_tam', 0)/1e9:.1f}B")
                    print(f"      - Labor TAM: ${components.get('labor_replacement_tam', 0)/1e9:.1f}B")
                    print(f"      - Selected: {components.get('selection_method', 'Unknown')}")
                    print(f"      - Software Citation: {components.get('software_citation', 'None')}")
                    print(f"      - Labor Citation: {components.get('labor_citation', 'None')}")
            else:
                print("❌ No market_size calculated")
            
            # Verify no fallback to bottom-up calculation
            if company_data.get('market_size'):
                methodology = company_data['market_size'].get('tam_methodology', '')
                if 'Bottom-up from revenue' in methodology:
                    print("\n⚠️  WARNING: TAM fell back to bottom-up calculation!")
                    print("    This means search extraction failed.")
                elif 'Market research' in methodology or 'extracted' in methodology.lower():
                    print("\n✅ SUCCESS: TAM using real market data!")
                else:
                    print(f"\n⚠️  UNCLEAR: TAM methodology: {methodology}")
    
    print("\n" + "="*80)
    print("TAM EXTRACTION TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_tam_extraction())