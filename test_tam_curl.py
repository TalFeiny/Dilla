#!/usr/bin/env python3
"""
Simple TAM Search Test Script
Tests the TAM search functionality without requiring the full server setup
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def test_tam_search():
    """Test TAM search functionality directly"""
    
    # Test company data
    company_data = {
        'name': 'Gradient Labs',
        'vertical': 'Healthcare',
        'business_model': 'Healthcare AI',
        'description': 'AI-powered healthcare analytics platform',
        'what_they_do': 'provides machine learning tools for medical diagnosis and treatment optimization'
    }
    
    print("="*60)
    print("TAM SEARCH TEST")
    print("="*60)
    print(f"Testing company: {company_data['name']}")
    print(f"Vertical: {company_data['vertical']}")
    print(f"Business Model: {company_data['business_model']}")
    print()
    
    try:
        # Import the TAM search tester
        from test_tam_search_queries import TAMSearchTester
        
        async with TAMSearchTester() as tester:
            print("Building TAM search queries...")
            queries = await tester.build_tam_queries(company_data)
            
            print(f"Generated {len(queries)} TAM search queries:")
            for i, query in enumerate(queries, 1):
                print(f"  {i}. {query}")
            
            print("\nExecuting first query as test...")
            if queries:
                result = await tester.search_tavily(queries[0])
                print(f"Search result keys: {list(result.keys()) if result else 'None'}")
                print(f"Number of results: {len(result.get('results', [])) if result else 0}")
                
                if result and result.get('results'):
                    print("\nFirst result:")
                    first_result = result['results'][0]
                    print(f"  Title: {first_result.get('title', 'N/A')}")
                    print(f"  URL: {first_result.get('url', 'N/A')}")
                    print(f"  Snippet: {first_result.get('snippet', 'N/A')[:200]}...")
                    
                    # Test TAM data extraction
                    tam_data = tester.extract_tam_data(first_result, queries[0], company_data['name'])
                    if tam_data:
                        print(f"\nExtracted TAM data:")
                        print(f"  Market Size: ${tam_data['market_size']['value_billions']:.1f}B")
                        print(f"  Source: {tam_data['source_domain']}")
                        print(f"  Source Type: {tam_data['source_type']}")
                    else:
                        print("\nNo TAM data extracted from first result")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tam_search())
