#!/usr/bin/env python3
"""
Test TAM functionality specifically for automotive software market
This test verifies that our TAM system can:
1. Take a company profile with "automotive software" market
2. Pull in Gartner, IDC, Forrester, McKinsey citations with numbers
3. Define the RIGHT market (automotive software vs generic automotive)
4. Extract CAGR, dates, and proper market sizing
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the backend directory to the Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.intelligent_gap_filler import IntelligentGapFiller

class AutomotiveTAMTester:
    """Test TAM functionality for automotive software market"""
    
    def __init__(self):
        self.orchestrator = UnifiedMCPOrchestrator()
        self.gap_filler = IntelligentGapFiller()
        
    async def test_automotive_software_tam(self):
        """Test TAM extraction for automotive software market"""
        
        print("🚗 Testing Automotive Software TAM Functionality")
        print("=" * 60)
        
        # Test company profile with automotive software market
        automotive_company = {
            "name": "AutoTech Solutions",
            "sector": "Automotive",
            "vertical": "Automotive",
            "business_model": "Automotive Software",
            "category": "Automotive Software",
            "description": "AI-powered automotive software platform for autonomous vehicles and connected car systems",
            "what_they_do": "develops software solutions for automotive manufacturers including ADAS, infotainment systems, and vehicle connectivity",
            "product_description": "comprehensive automotive software suite including autonomous driving algorithms, vehicle-to-everything (V2X) communication, and predictive maintenance systems",
            "stage": "Series A"
        }
        
        print(f"📋 Testing company: {automotive_company['name']}")
        print(f"   Sector: {automotive_company['sector']}")
        print(f"   Business Model: {automotive_company['business_model']}")
        print(f"   Description: {automotive_company['description']}")
        print()
        
        # Test 1: Company fetch with TAM extraction
        print("🔍 Test 1: Company Fetch with TAM Extraction")
        print("-" * 40)
        
        try:
            result = await self.orchestrator.execute_company_fetch({
                "company": automotive_company["name"],
                "include_tam": True,
                "company_data": automotive_company
            })
            
            print(f"✅ Company fetch completed")
            print(f"   Result keys: {list(result.keys())}")
            
            # Check TAM data
            if 'tam_data' in result and result['tam_data']:
                tam_data = result['tam_data']
                print(f"\n📊 TAM Data Found:")
                print(f"   Market Definition: {tam_data.get('tam_market_definition', 'Not defined')}")
                print(f"   TAM Value: ${tam_data.get('tam_value', 0)/1e9:.1f}B")
                print(f"   TAM Formatted: {tam_data.get('tam_formatted', 'Not formatted')}")
                
                # Check for analyst citations
                estimates = tam_data.get('tam_estimates', [])
                if estimates:
                    print(f"\n📈 Found {len(estimates)} TAM estimates:")
                    analyst_sources = []
                    for i, est in enumerate(estimates, 1):
                        source = est.get('source', 'Unknown')
                        value = est.get('tam_value', 0)
                        url = est.get('url', 'No URL')
                        citation = est.get('citation', 'No citation')
                        
                        print(f"   {i}. ${value/1e9:.1f}B")
                        print(f"      Source: {source}")
                        print(f"      URL: {url}")
                        print(f"      Citation: {citation[:100]}...")
                        
                        # Check for analyst firms
                        if any(analyst in source.lower() for analyst in ['gartner', 'idc', 'forrester', 'mckinsey']):
                            analyst_sources.append(source)
                    
                    print(f"\n🎯 Analyst Sources Found: {analyst_sources}")
                else:
                    print("❌ No TAM estimates found")
            else:
                print("❌ No TAM data extracted")
                
        except Exception as e:
            print(f"❌ Company fetch failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Direct market opportunity calculation
        print(f"\n🔍 Test 2: Direct Market Opportunity Calculation")
        print("-" * 40)
        
        try:
            market_analysis = await self.gap_filler.calculate_market_opportunity(
                company_data=automotive_company,
                search_content=""
            )
            
            print(f"✅ Market analysis completed")
            print(f"   Analysis keys: {list(market_analysis.keys())}")
            
            # Check market analysis results
            if market_analysis:
                print(f"\n📊 Market Analysis Results:")
                print(f"   Market Category: {market_analysis.get('category', 'Not defined')}")
                print(f"   TAM Current: ${market_analysis.get('tam_current', 0)/1e9:.1f}B")
                print(f"   TAM 2030: ${market_analysis.get('tam_2030', 0)/1e9:.1f}B")
                print(f"   Growth Rate: {market_analysis.get('growth_rate', 0):.1f}%")
                print(f"   Methodology: {market_analysis.get('tam_methodology', 'Not specified')}")
                print(f"   Citation: {market_analysis.get('tam_citation', 'No citation')}")
                
                # Check if it's defining the RIGHT market
                category = market_analysis.get('category', '').lower()
                if 'automotive' in category and 'software' in category:
                    print(f"✅ Correctly defined market: Automotive Software")
                elif 'automotive' in category:
                    print(f"⚠️  Partially correct: {category} (should be more specific)")
                else:
                    print(f"❌ Wrong market definition: {category}")
                    
        except Exception as e:
            print(f"❌ Market analysis failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Search query generation
        print(f"\n🔍 Test 3: TAM Search Query Generation")
        print("-" * 40)
        
        try:
            # Test the search query building logic
            from test_tam_search_queries import TAMSearchTester
            tester = TAMSearchTester()
            
            queries = await tester.build_tam_queries(automotive_company)
            
            print(f"✅ Generated {len(queries)} TAM search queries:")
            for i, query in enumerate(queries, 1):
                print(f"   {i}. {query}")
                
            # Check if queries target the right market
            automotive_queries = [q for q in queries if 'automotive' in q.lower()]
            analyst_queries = [q for q in queries if any(analyst in q.lower() for analyst in ['gartner', 'idc', 'forrester', 'mckinsey'])]
            
            print(f"\n🎯 Query Analysis:")
            print(f"   Automotive-specific queries: {len(automotive_queries)}")
            print(f"   Analyst-focused queries: {len(analyst_queries)}")
            
            if automotive_queries:
                print(f"✅ Queries target automotive market")
            else:
                print(f"❌ Queries don't target automotive market")
                
            if analyst_queries:
                print(f"✅ Queries include analyst firms")
            else:
                print(f"❌ Queries don't include analyst firms")
                
        except Exception as e:
            print(f"❌ Query generation failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 4: Real search execution (if API key available)
        print(f"\n🔍 Test 4: Real Search Execution")
        print("-" * 40)
        
        try:
            # Check if we have Tavily API key
            from app.core.config import settings
            if hasattr(settings, 'TAVILY_API_KEY') and settings.TAVILY_API_KEY:
                print("✅ Tavily API key found, executing real searches...")
                
                from test_tam_search_queries import TAMSearchTester
                async with TAMSearchTester() as tester:
                    search_result = await tester.test_company_queries(automotive_company)
                    
                    print(f"✅ Real search completed")
                    print(f"   Successful searches: {search_result['summary']['successful_searches']}")
                    print(f"   Sources with market data: {search_result['summary']['sources_with_market_data']}")
                    print(f"   Sources with CAGR: {search_result['summary']['sources_with_cagr']}")
                    
                    # Show market data found
                    if search_result['tam_sources']:
                        print(f"\n📊 Market Data Found:")
                        for i, source in enumerate(search_result['tam_sources'], 1):
                            market_size = source['market_size']
                            cagr_info = f" (CAGR: {source['cagr']['value']}%)" if source['cagr'] else ""
                            print(f"   {i}. ${market_size['value_billions']:.1f}B {market_size['unit']}{cagr_info}")
                            print(f"      Source: {source['source_domain']} ({source['source_type']})")
                            print(f"      Market: {source['market_definition']}")
                            print(f"      URL: {source['url']}")
                    else:
                        print("❌ No market data found in real searches")
            else:
                print("⚠️  No Tavily API key found, skipping real search test")
                
        except Exception as e:
            print(f"❌ Real search test failed: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'='*60}")
        print("AUTOMOTIVE SOFTWARE TAM TEST COMPLETE")
        print("=" * 60)

async def main():
    """Main test function"""
    tester = AutomotiveTAMTester()
    await tester.test_automotive_software_tam()

if __name__ == "__main__":
    asyncio.run(main())
