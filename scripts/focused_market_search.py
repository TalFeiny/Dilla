#!/usr/bin/env python3
"""Focused market search for PWERM analysis - get real data, calculate multiples ourselves"""

import os
import sys
import json
import requests
from typing import Dict, List
from datetime import datetime

def search_market_intelligence(company_name: str, sector: str) -> Dict:
    """Search for comprehensive market intelligence"""
    
    tavily_api_key = os.getenv('TAVILY_API_KEY')
    if not tavily_api_key:
        print("ERROR: No TAVILY_API_KEY found")
        return {}
    
    results = {
        "company": company_name,
        "sector": sector,
        "search_timestamp": datetime.now().isoformat(),
        "incumbents": [],
        "competitors": [],
        "recent_transactions": [],
        "funding_rounds": [],
        "market_analysis": {},
        "headwinds": [],
        "tailwinds": [],
        "raw_search_results": []
    }
    
    # Define search queries
    queries = [
        # Incumbent players
        f"{sector} market leaders largest companies revenue 2024",
        
        # Direct competitors
        f"{company_name} competitors alternatives market share",
        
        # Recent transactions
        f"{sector} acquisitions 2024 2025 deal value price",
        f"{sector} M&A exits IPO transactions recent",
        
        # Funding landscape
        f"{company_name} funding rounds valuation investors",
        f"{sector} venture capital funding 2024 unicorns",
        
        # Market dynamics
        f"{sector} market size growth rate trends 2024 2025",
        f"{sector} disruption challenges opportunities",
        
        # Market sizing and analyst reports (NEW)
        f"{sector} market size TAM SAM SOM Gartner Forrester IDC report 2024",
        f"{sector} TAM market sizing analyst report McKinsey BCG Bain",
        f"{company_name} Gartner Magic Quadrant position analyst coverage",
        f"{sector} industry analysis market forecast CAGR growth projection 2025-2030",
        f"{sector} market research report industry trends analyst firm",
        
        # Specific company intel
        f"{company_name} revenue ARR growth rate employees",
        f"{company_name} valuation latest round funding"
    ]
    
    print(f"\nExecuting {len(queries)} market intelligence searches...\n")
    
    for i, query in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] Searching: {query}")
        
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 10,
                    "include_answer": True
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Store raw results
                results["raw_search_results"].append({
                    "query": query,
                    "answer": data.get("answer", ""),
                    "results_count": len(data.get("results", []))
                })
                
                # Process based on query type
                if "market leaders" in query:
                    process_incumbents(data, results)
                elif "competitors" in query:
                    process_competitors(data, results)
                elif "acquisitions" in query or "M&A" in query:
                    process_transactions(data, results)
                elif "funding" in query:
                    process_funding(data, results)
                elif "market size" in query:
                    process_market_analysis(data, results)
                elif "disruption" in query:
                    process_market_dynamics(data, results)
                
                # Print summary answer if available
                if data.get("answer"):
                    print(f"   → {data['answer'][:150]}...")
            else:
                print(f"   → Error: {response.status_code}")
                
        except Exception as e:
            print(f"   → Error: {str(e)}")
    
    # Analyze results to extract headwinds and tailwinds
    analyze_market_forces(results)
    
    return results

def process_incumbents(data: Dict, results: Dict):
    """Extract incumbent market leaders"""
    import re
    
    for result in data.get("results", [])[:5]:
        content = result.get("content", "")
        title = result.get("title", "")
        
        # Look for company names with revenue/valuation
        companies = re.findall(r'([A-Z][\w\s&]+?)(?:\s+(?:revenue|valued|worth)\s+\$?[\d,]+\s*(?:billion|million))', content)
        
        for company in companies:
            if company.strip() and len(company.strip()) > 2:
                incumbent = {
                    "name": company.strip(),
                    "source": title[:100]
                }
                
                # Try to extract revenue
                rev_pattern = rf'{re.escape(company)}.*?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)\s*(?:revenue|sales)'
                rev_match = re.search(rev_pattern, content, re.IGNORECASE)
                if rev_match:
                    amount = float(rev_match.group(1).replace(',', ''))
                    if rev_match.group(2).lower() in ['billion', 'bn', 'b']:
                        amount *= 1000
                    incumbent["revenue_millions"] = amount
                
                results["incumbents"].append(incumbent)

def process_competitors(data: Dict, results: Dict):
    """Extract competitor information"""
    import re
    
    for result in data.get("results", [])[:5]:
        content = result.get("content", "")
        
        # Common patterns for competitor mentions
        patterns = [
            r'competitors?\s+(?:include|are|such as)\s+([A-Z][\w\s,&]+)',
            r'([A-Z][\w\s&]+)\s+(?:competes?|competing)\s+with',
            r'alternatives?\s+(?:include|are|such as)\s+([A-Z][\w\s,&]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Split by commas and clean up
                companies = [c.strip() for c in match.split(',')]
                for company in companies:
                    if company and len(company) > 2 and company not in [c["name"] for c in results["competitors"]]:
                        results["competitors"].append({
                            "name": company,
                            "mentioned_context": content[max(0, content.find(company)-50):content.find(company)+50]
                        })

def process_transactions(data: Dict, results: Dict):
    """Extract M&A transactions"""
    import re
    
    for result in data.get("results", []):
        content = result.get("content", "")
        title = result.get("title", "")
        
        # Transaction patterns
        patterns = [
            r'([A-Z][\w\s&]+?)\s+(?:acquired|acquires?|bought|buys?)\s+([A-Z][\w\s&]+?)(?:\s+for\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m))?',
            r'([A-Z][\w\s&]+?)\s+(?:acquisition|purchase)\s+of\s+([A-Z][\w\s&]+?)(?:\s+for\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m))?'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                transaction = {
                    "acquirer": match.group(1).strip(),
                    "target": match.group(2).strip(),
                    "source": title[:100]
                }
                
                # Extract deal value if present
                if match.group(3):
                    amount = float(match.group(3).replace(',', ''))
                    unit = match.group(4).lower()
                    if unit in ['billion', 'bn', 'b']:
                        amount *= 1000
                    transaction["deal_value_millions"] = amount
                
                # Extract date
                date_pattern = r'(20\d{2})'
                date_match = re.search(date_pattern, content[max(0, match.start()-50):match.end()+50])
                if date_match:
                    transaction["year"] = date_match.group(1)
                
                results["recent_transactions"].append(transaction)

def process_funding(data: Dict, results: Dict):
    """Extract funding information"""
    import re
    
    for result in data.get("results", []):
        content = result.get("content", "")
        
        # Funding patterns
        patterns = [
            r'([A-Z][\w\s&]+?)\s+raises?\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)',
            r'([A-Z][\w\s&]+?)\s+(?:secured?|closed?)\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)\s+(?:funding|round)',
            r'([A-Z][\w\s&]+?)\s+valued\s+at\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                company = match.group(1).strip()
                amount = float(match.group(2).replace(',', ''))
                unit = match.group(3).lower()
                
                if unit in ['billion', 'bn', 'b']:
                    amount *= 1000
                
                funding = {
                    "company": company,
                    "amount_millions": amount,
                    "type": "valuation" if "valued" in match.group(0) else "funding"
                }
                
                # Extract round type
                round_match = re.search(r'(seed|series [a-z]|growth|late stage)', content[max(0, match.start()-50):match.end()+50], re.IGNORECASE)
                if round_match:
                    funding["round"] = round_match.group(1)
                
                results["funding_rounds"].append(funding)

def process_market_analysis(data: Dict, results: Dict):
    """Extract market size and growth data"""
    import re
    
    if data.get("answer"):
        results["market_analysis"]["summary"] = data["answer"]
    
    for result in data.get("results", [])[:3]:
        content = result.get("content", "")
        
        # Market size patterns
        size_patterns = [
            r'market\s+(?:size|worth|valued)\s+(?:at\s+)?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|trillion)',
            r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million|trillion)\s+market'
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                amount = float(match.group(1).replace(',', ''))
                unit = match.group(2).lower()
                if unit == 'trillion':
                    amount *= 1000000
                elif unit == 'billion':
                    amount *= 1000
                results["market_analysis"]["market_size_millions"] = amount
                break
        
        # Growth rate patterns
        growth_pattern = r'(?:grow|growth|CAGR|increase).*?(\d+(?:\.\d+)?)\s*%'
        growth_match = re.search(growth_pattern, content, re.IGNORECASE)
        if growth_match:
            results["market_analysis"]["growth_rate_percent"] = float(growth_match.group(1))

def process_market_dynamics(data: Dict, results: Dict):
    """Extract market challenges and opportunities"""
    
    for result in data.get("results", [])[:5]:
        content = result.get("content", "").lower()
        
        # Headwind indicators
        headwind_keywords = ['challenge', 'risk', 'threat', 'decline', 'pressure', 'regulation', 'competition']
        for keyword in headwind_keywords:
            if keyword in content:
                # Extract sentence containing keyword
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword in sentence and len(sentence) > 20:
                        results["headwinds"].append(sentence.strip())
                        break
        
        # Tailwind indicators
        tailwind_keywords = ['opportunity', 'growth', 'demand', 'adoption', 'innovation', 'disruption']
        for keyword in tailwind_keywords:
            if keyword in content:
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword in sentence and len(sentence) > 20:
                        results["tailwinds"].append(sentence.strip())
                        break

def analyze_market_forces(results: Dict):
    """Analyze all results to identify key market forces"""
    # Deduplicate and clean up headwinds/tailwinds
    results["headwinds"] = list(set(results["headwinds"]))[:5]
    results["tailwinds"] = list(set(results["tailwinds"]))[:5]
    
    # Calculate some basic metrics
    if results["recent_transactions"]:
        deals_with_value = [t for t in results["recent_transactions"] if "deal_value_millions" in t]
        if deals_with_value:
            avg_deal_size = sum(t["deal_value_millions"] for t in deals_with_value) / len(deals_with_value)
            results["market_analysis"]["avg_deal_size_millions"] = avg_deal_size

def main():
    """Run focused market search"""
    
    # Get company and sector
    if len(sys.argv) > 2:
        company = sys.argv[1]
        sector = sys.argv[2]
    else:
        company = input("Company name: ").strip() or "Deel"
        sector = input("Sector: ").strip() or "HR Tech"
    
    results = search_market_intelligence(company, sector)
    
    # Display results
    print("\n" + "="*60)
    print(f"MARKET INTELLIGENCE: {company} ({sector})")
    print("="*60)
    
    print(f"\n📊 MARKET OVERVIEW")
    if results["market_analysis"]:
        if "market_size_millions" in results["market_analysis"]:
            print(f"Market Size: ${results['market_analysis']['market_size_millions']:,.0f}M")
        if "growth_rate_percent" in results["market_analysis"]:
            print(f"Growth Rate: {results['market_analysis']['growth_rate_percent']:.1f}%")
        if "summary" in results["market_analysis"]:
            print(f"Summary: {results['market_analysis']['summary'][:200]}...")
    
    print(f"\n🏢 INCUMBENTS ({len(results['incumbents'])})")
    for inc in results["incumbents"][:5]:
        print(f"- {inc['name']}", end="")
        if "revenue_millions" in inc:
            print(f" (Revenue: ${inc['revenue_millions']:,.0f}M)")
        else:
            print()
    
    print(f"\n🤝 COMPETITORS ({len(results['competitors'])})")
    for comp in results["competitors"][:5]:
        print(f"- {comp['name']}")
    
    print(f"\n💰 RECENT TRANSACTIONS ({len(results['recent_transactions'])})")
    for tx in results["recent_transactions"][:5]:
        print(f"- {tx['acquirer']} → {tx['target']}", end="")
        if "deal_value_millions" in tx:
            print(f" (${tx['deal_value_millions']:,.0f}M)", end="")
        if "year" in tx:
            print(f" [{tx['year']}]", end="")
        print()
    
    print(f"\n💸 FUNDING ACTIVITY ({len(results['funding_rounds'])})")
    for fund in results["funding_rounds"][:5]:
        print(f"- {fund['company']}: ${fund['amount_millions']:,.0f}M", end="")
        if "round" in fund:
            print(f" ({fund['round']})", end="")
        print(f" [{fund['type']}]")
    
    print(f"\n⚠️  HEADWINDS")
    for hw in results["headwinds"]:
        print(f"- {hw[:100]}...")
    
    print(f"\n✅ TAILWINDS")
    for tw in results["tailwinds"]:
        print(f"- {tw[:100]}...")
    
    # Save full results
    output_file = f"market_intel_{company.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Full results saved to: {output_file}")

if __name__ == "__main__":
    main()