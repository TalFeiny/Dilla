#!/usr/bin/env python3
"""Smart M&A search queries that actually find deal values"""

import os
import requests
import json
from datetime import datetime

def demonstrate_smart_searches():
    """Show how to construct searches that find real M&A data"""
    
    # SMART M&A SEARCH PATTERNS
    smart_search_patterns = {
        
        "Recent Major Deals with Prices": [
            # These searches find actual announced prices
            'Microsoft Activision $69 billion acquisition completed 2023',
            'Adobe Figma $20 billion acquisition terminated September 2023',
            'Broadcom VMware $69 billion acquisition May 2023',
            'Cisco Splunk $28 billion acquisition March 2024',
            'IBM HashiCorp $6.4 billion acquisition April 2024',
            'Databricks MosaicML $1.3 billion acquisition June 2023',
            'Salesforce Slack $27.7 billion acquisition details revenue',
            'Vista Equity Cvent $8.5 billion take private 2023'
        ],
        
        "HR Tech Specific M&A": [
            # Find HR tech deals where price was disclosed
            'Ultimate Software Kronos merger $22 billion valuation 2020',
            'Hellman Friedman Ultimate Software $11 billion acquisition',
            'Workday acquired Peakon $700 million employee engagement',
            'Workday acquired Adaptive Insights $1.55 billion planning',
            'ADP acquired WorkMarket $200 million freelance management',
            'Ceridian Dayforce public company $5 billion market cap revenue',
            'Cornerstone OnDemand acquired $5.2 billion Vista Equity 2021',
            'SAP SuccessFactors acquisition $3.4 billion HR cloud'
        ],
        
        "Competitor Deals (Deel/Rippling Space)": [
            # Contractor/payroll/global employment platforms
            'Remote.com valuation $3 billion Series C 2022 revenue',
            'Oyster HR $150 million funding $1.2 billion valuation',
            'Papaya Global $250 million funding $3.7 billion valuation',
            'Velocity Global acquisition PEO employer of record',
            'TriNet Zenefits acquisition discussions price',
            'Gusto valuation $10 billion revenue run rate 2022',
            'Justworks IPO valuation $2 billion revenue public'
        ],
        
        "Private Equity HR Rollups": [
            # PE firms actively consolidating HR tech
            'Vista Equity Partners HR tech acquisitions portfolio',
            'Thoma Bravo Paycor $2.3 billion acquisition 2018',
            'H&F Partners Ultimate Kronos combination valuation',
            'Leonard Green Ceridian investment return multiple',
            'Warburg Pincus Modernizing Medicine $1.1 billion',
            'Stone Point Capital Kestra Financial acquisition'
        ],
        
        "Finding Revenue for Multiple Calculation": [
            # Searches that reveal both price AND revenue
            '"acquired for $X billion" "annual revenue $Y million"',
            '"valuation of $X billion" "ARR of $Y million" SaaS',
            '"sold for $X million" "revenue run rate" enterprise value',
            'acquisition price revenue multiple disclosed M&A 2024',
            'private equity acquisition EBITDA multiple purchase price'
        ],
        
        "Market Intelligence Queries": [
            # Understanding consolidation and strategic rationale
            'HR tech market consolidation 2024 strategic buyers',
            'global payroll compliance acquisition targets 2024',
            'contractor management platforms M&A activity trends',
            'why Workday would acquire Deel strategic rationale',
            'antitrust concerns HR tech market concentration'
        ]
    }
    
    # Test with real Tavily API
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        print("Set TAVILY_API_KEY to test real searches")
        return
    
    print("🔍 TESTING SMART M&A SEARCHES\n")
    
    # Test a few key searches
    test_searches = [
        'Workday acquired Peakon $700 million employee engagement revenue',
        'Vista Equity Cornerstone OnDemand $5.2 billion revenue EBITDA',
        'Ultimate Kronos merger $22 billion combined revenue $5 billion'
    ]
    
    for query in test_searches:
        print(f"\n📍 Search: {query}")
        print("-" * 60)
        
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 3,
                    "include_answer": True
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Show the AI answer
                if data.get('answer'):
                    print(f"AI Summary: {data['answer'][:200]}...")
                
                # Show what we found
                for i, result in enumerate(data.get('results', [])[:2]):
                    print(f"\nResult {i+1}: {result.get('title', '')[:80]}")
                    content = result.get('content', '')
                    
                    # Look for key data points
                    import re
                    
                    # Find dollar amounts
                    amounts = re.findall(r'\$[\d,]+(?:\.\d+)?\s*(?:billion|million|B|M)', content)
                    if amounts:
                        print(f"💰 Found amounts: {', '.join(amounts[:3])}")
                    
                    # Find revenue mentions
                    if 'revenue' in content.lower():
                        # Extract sentence with revenue
                        sentences = content.split('.')
                        for sent in sentences:
                            if 'revenue' in sent.lower() and '$' in sent:
                                print(f"📊 Revenue context: {sent.strip()[:150]}...")
                                break
                    
                    # Find multiple mentions
                    multiple_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|times)\s*(?:revenue|EBITDA|sales)', content, re.I)
                    if multiple_match:
                        print(f"📈 Multiple found: {multiple_match.group(0)}")
            
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n\n💡 KEY INSIGHTS:")
    print("1. Search for SPECIFIC deals with company names")
    print("2. Include deal value terms: 'acquired for $X billion'")
    print("3. Add revenue/EBITDA terms to calculate multiples")
    print("4. Focus on disclosed transactions (public companies, PE deals)")
    print("5. Use date ranges to get recent comparables")
    
    print("\n📊 For Deel PWERM Analysis:")
    print("- Workday is the most likely acquirer (global payroll strategy)")
    print("- Recent HR tech multiples: 5-15x revenue (mature) vs 20-30x (high growth)")
    print("- Deel at $12B / $500M ARR = 24x (high but justified by growth)")
    print("- Key barriers: Rippling lawsuit, regulatory complexity")
    print("- IPO more likely than acquisition due to size/complexity")

if __name__ == "__main__":
    demonstrate_smart_searches()