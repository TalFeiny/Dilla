#!/usr/bin/env python3
"""Enhanced PWERM search that focuses on finding deals and strategic fits"""

import os
import sys
import json
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class EnhancedPWERMSearch:
    def __init__(self, tavily_api_key: str, claude_api_key: str):
        self.tavily_api_key = tavily_api_key
        self.claude_api_key = claude_api_key
        self.tavily_base_url = "https://api.tavily.com/search"
        self.claude_base_url = "https://api.anthropic.com/v1/messages"
    
    def search_strategic_intelligence(self, company_name: str, sector: str) -> Dict:
        """Search for comprehensive market intelligence without focusing on multiples"""
        
        results = {
            "recent_transactions": [],
            "strategic_acquirers": [],
            "comparable_companies": [],
            "market_dynamics": {},
            "potential_scenarios": []
        }
        
        # 1. Search for recent M&A transactions in the sector
        transaction_queries = [
            f"{sector} acquisitions 2024 2025 deal price valuation",
            f"{sector} M&A transactions recent exits startup acquired",
            f"{company_name} competitors acquired acquisition price",
            f"recent {sector} IPOs public offerings valuation revenue"
        ]
        
        sys.stderr.write(f"\nSearching for recent transactions in {sector}...\n")
        for query in transaction_queries:
            sys.stderr.write(f"Query: {query}\n")
            transactions = self._search_transactions(query)
            results["recent_transactions"].extend(transactions)
        
        # 2. Search for strategic acquirers and their acquisition history
        acquirer_queries = [
            f"who would acquire {company_name} strategic buyers {sector}",
            f"{sector} consolidation M&A activity strategic acquirers",
            f"Apple Google Microsoft Amazon acquisitions {sector}",
            f"private equity {sector} rollup strategy consolidation"
        ]
        
        sys.stderr.write(f"\nSearching for strategic acquirers...\n")
        for query in acquirer_queries:
            sys.stderr.write(f"Query: {query}\n")
            acquirers = self._search_acquirers(query, company_name, sector)
            results["strategic_acquirers"].extend(acquirers)
        
        # 3. Search for comparable companies and their metrics
        comparable_queries = [
            f"{company_name} competitors revenue funding valuation",
            f"companies similar to {company_name} {sector} market share",
            f"{sector} unicorns revenue growth funding rounds",
            f"fast growing {sector} companies ARR revenue metrics"
        ]
        
        sys.stderr.write(f"\nSearching for comparable companies...\n")
        for query in comparable_queries:
            sys.stderr.write(f"Query: {query}\n")
            comparables = self._search_comparables(query)
            results["comparable_companies"].extend(comparables)
        
        # 4. Search for market dynamics and strategic rationale
        market_queries = [
            f"{sector} market consolidation trends 2024 2025",
            f"why would someone acquire {company_name} strategic rationale",
            f"{sector} market size growth rate competitive landscape",
            f"disruption in {sector} market leaders challengers"
        ]
        
        sys.stderr.write(f"\nSearching for market dynamics...\n")
        for query in market_queries:
            sys.stderr.write(f"Query: {query}\n")
            dynamics = self._search_market_dynamics(query)
            results["market_dynamics"].update(dynamics)
        
        # 5. Use Claude to synthesize insights
        sys.stderr.write(f"\nSynthesizing insights with Claude...\n")
        insights = self._synthesize_with_claude(company_name, sector, results)
        results["ai_insights"] = insights
        
        return results
    
    def _search_transactions(self, query: str) -> List[Dict]:
        """Search for M&A transactions and extract deal information"""
        transactions = []
        
        try:
            response = requests.post(
                self.tavily_base_url,
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 10,
                    "include_answer": True
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Process each result
                for result in data.get('results', []):
                    transaction = self._extract_transaction_data(
                        result.get('content', ''),
                        result.get('title', ''),
                        result.get('url', '')
                    )
                    if transaction:
                        transactions.append(transaction)
        
        except Exception as e:
            sys.stderr.write(f"Search error: {e}\n")
        
        return transactions
    
    def _search_acquirers(self, query: str, target_company: str, sector: str) -> List[Dict]:
        """Search for potential acquirers and their strategic fit"""
        acquirers = []
        
        try:
            response = requests.post(
                self.tavily_base_url,
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 10
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for result in data.get('results', []):
                    acquirer = self._extract_acquirer_data(
                        result.get('content', ''),
                        result.get('title', ''),
                        target_company,
                        sector
                    )
                    if acquirer:
                        acquirers.append(acquirer)
        
        except Exception as e:
            sys.stderr.write(f"Search error: {e}\n")
        
        return acquirers
    
    def _search_comparables(self, query: str) -> List[Dict]:
        """Search for comparable companies and their metrics"""
        comparables = []
        
        try:
            response = requests.post(
                self.tavily_base_url,
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 10
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for result in data.get('results', []):
                    comparable = self._extract_comparable_data(
                        result.get('content', ''),
                        result.get('title', '')
                    )
                    if comparable:
                        comparables.append(comparable)
        
        except Exception as e:
            sys.stderr.write(f"Search error: {e}\n")
        
        return comparables
    
    def _search_market_dynamics(self, query: str) -> Dict:
        """Search for market dynamics and trends"""
        dynamics = {}
        
        try:
            response = requests.post(
                self.tavily_base_url,
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract key themes
                if data.get('answer'):
                    dynamics['market_summary'] = data['answer']
                
                # Extract trends from results
                trends = []
                for result in data.get('results', []):
                    trend = self._extract_market_trend(result.get('content', ''))
                    if trend:
                        trends.append(trend)
                
                if trends:
                    dynamics['key_trends'] = trends
        
        except Exception as e:
            sys.stderr.write(f"Search error: {e}\n")
        
        return dynamics
    
    def _extract_transaction_data(self, content: str, title: str, url: str) -> Optional[Dict]:
        """Extract transaction data from search result"""
        import re
        
        # Look for company names and deal values
        transaction = {
            "source": title[:100],
            "url": url,
            "type": "acquisition"
        }
        
        # Extract acquirer and target
        patterns = [
            r'([A-Z][\w\s&]+?)\s+(?:acquires?|acquired|buys?|bought)\s+([A-Z][\w\s&]+)',
            r'([A-Z][\w\s&]+?)\s+to\s+acquire\s+([A-Z][\w\s&]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                transaction["acquirer"] = match.group(1).strip()
                transaction["target"] = match.group(2).strip()
                break
        
        # Extract deal value
        value_pattern = r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)'
        value_matches = re.findall(value_pattern, content.lower())
        
        for amount_str, unit in value_matches:
            amount = float(amount_str.replace(',', ''))
            if unit in ['billion', 'bn', 'b']:
                amount *= 1000  # Convert to millions
            
            # Check context to determine if this is deal value
            context_start = max(0, content.lower().find(amount_str) - 50)
            context = content[context_start:context_start + 150].lower()
            
            if any(word in context for word in ['deal', 'acquisition', 'acquired', 'valued', 'price', 'bought']):
                transaction["deal_value_millions"] = amount
                break
        
        # Extract revenue if mentioned
        revenue_patterns = [
            r'([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)\s+(?:in\s+)?(?:revenue|arr)',
            r'revenue\s+of\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)',
        ]
        
        for pattern in revenue_patterns:
            match = re.search(pattern, content.lower())
            if match:
                rev_amount = float(match.group(1).replace(',', ''))
                if match.group(2) in ['billion', 'bn', 'b']:
                    rev_amount *= 1000
                transaction["target_revenue_millions"] = rev_amount
                break
        
        # Extract date
        date_pattern = r'(20\d{2})'
        date_match = re.search(date_pattern, content)
        if date_match:
            transaction["year"] = date_match.group(1)
        
        # Only return if we found meaningful data
        if "acquirer" in transaction or "deal_value_millions" in transaction:
            return transaction
        
        return None
    
    def _extract_acquirer_data(self, content: str, title: str, target: str, sector: str) -> Optional[Dict]:
        """Extract potential acquirer information"""
        import re
        
        acquirer = {
            "target_company": target,
            "sector": sector,
            "source": title[:100]
        }
        
        # Look for company names that could be acquirers
        major_tech = ['Apple', 'Google', 'Microsoft', 'Amazon', 'Meta', 'Oracle', 'Salesforce', 'Adobe', 'IBM']
        pe_firms = ['KKR', 'Blackstone', 'Carlyle', 'Apollo', 'TPG', 'Vista Equity', 'Thoma Bravo']
        
        mentioned_companies = []
        for company in major_tech + pe_firms:
            if company.lower() in content.lower():
                mentioned_companies.append(company)
        
        if mentioned_companies:
            acquirer["potential_acquirers"] = mentioned_companies
        
        # Extract strategic rationale
        if 'consolidation' in content.lower():
            acquirer["rationale"] = "Market consolidation"
        elif 'strategic' in content.lower():
            acquirer["rationale"] = "Strategic fit"
        elif 'synerg' in content.lower():
            acquirer["rationale"] = "Synergies"
        
        # Look for acquisition history
        acq_pattern = r'acquired\s+(\d+)\s+compan'
        acq_match = re.search(acq_pattern, content.lower())
        if acq_match:
            acquirer["acquisition_count"] = int(acq_match.group(1))
        
        if "potential_acquirers" in acquirer or "rationale" in acquirer:
            return acquirer
        
        return None
    
    def _extract_comparable_data(self, content: str, title: str) -> Optional[Dict]:
        """Extract comparable company data"""
        import re
        
        comparable = {
            "source": title[:100]
        }
        
        # Extract company name (usually in title or early in content)
        company_pattern = r'^([A-Z][\w\s&]+?)(?:\s+raises|\s+valued|\s+reports|\s+announces)'
        match = re.search(company_pattern, title + ' ' + content)
        if match:
            comparable["company"] = match.group(1).strip()
        
        # Extract valuation
        val_pattern = r'valued\s+at\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)'
        val_match = re.search(val_pattern, content.lower())
        if val_match:
            amount = float(val_match.group(1).replace(',', ''))
            if val_match.group(2) in ['billion', 'bn', 'b']:
                amount *= 1000
            comparable["valuation_millions"] = amount
        
        # Extract revenue
        rev_patterns = [
            r'([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)\s+(?:in\s+)?(?:revenue|arr)',
            r'revenue\s+of\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mn|b|m)',
        ]
        
        for pattern in rev_patterns:
            rev_match = re.search(pattern, content.lower())
            if rev_match:
                rev_amount = float(rev_match.group(1).replace(',', ''))
                if rev_match.group(2) in ['billion', 'bn', 'b']:
                    rev_amount *= 1000
                comparable["revenue_millions"] = rev_amount
                break
        
        # Extract growth rate
        growth_pattern = r'(\d+)%\s+(?:growth|increase|yoy)'
        growth_match = re.search(growth_pattern, content.lower())
        if growth_match:
            comparable["growth_rate"] = int(growth_match.group(1))
        
        if "company" in comparable and ("valuation_millions" in comparable or "revenue_millions" in comparable):
            return comparable
        
        return None
    
    def _extract_market_trend(self, content: str) -> Optional[str]:
        """Extract key market trends from content"""
        # Look for key trend indicators
        trend_keywords = ['consolidation', 'disruption', 'growth', 'decline', 'emerging', 'mature']
        
        for keyword in trend_keywords:
            if keyword in content.lower():
                # Extract sentence containing the keyword
                sentences = content.split('.')
                for sentence in sentences:
                    if keyword in sentence.lower():
                        return sentence.strip()
        
        return None
    
    def _synthesize_with_claude(self, company: str, sector: str, data: Dict) -> Dict:
        """Use Claude to synthesize insights from the data"""
        try:
            prompt = f"""
            Analyze this market intelligence for {company} in the {sector} sector:
            
            Recent Transactions: {json.dumps(data['recent_transactions'][:10], indent=2)}
            Strategic Acquirers: {json.dumps(data['strategic_acquirers'][:10], indent=2)}
            Comparable Companies: {json.dumps(data['comparable_companies'][:10], indent=2)}
            Market Dynamics: {json.dumps(data['market_dynamics'], indent=2)}
            
            Based on this data, provide:
            1. Most likely acquirers for {company} and why
            2. Expected valuation range based on comparables
            3. Strategic rationale for acquisition
            4. Market timing considerations
            5. Key risks and opportunities
            
            If you see deal values and revenues, calculate the implied multiples.
            Focus on real data, not speculation.
            
            Respond in JSON format.
            """
            
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 2000,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return json.loads(result['content'][0]['text'])
            
        except Exception as e:
            sys.stderr.write(f"Claude error: {e}\n")
        
        return {}

def main():
    """Test the enhanced search"""
    
    # Get API keys
    tavily_key = os.getenv('TAVILY_API_KEY')
    claude_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
    
    if not tavily_key or not claude_key:
        print("Error: Missing API keys")
        return
    
    # Test with a company
    searcher = EnhancedPWERMSearch(tavily_key, claude_key)
    
    # Get input
    company = input("Company name (e.g., Deel): ").strip() or "Deel"
    sector = input("Sector (e.g., HR Tech): ").strip() or "HR Tech"
    
    print(f"\nSearching strategic intelligence for {company} in {sector}...\n")
    
    results = searcher.search_strategic_intelligence(company, sector)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    print(f"\nFound {len(results['recent_transactions'])} transactions")
    print(f"Found {len(results['strategic_acquirers'])} potential acquirer insights")
    print(f"Found {len(results['comparable_companies'])} comparable companies")
    
    print("\nSample Transactions:")
    for tx in results['recent_transactions'][:3]:
        print(f"- {tx.get('acquirer', 'Unknown')} acquired {tx.get('target', 'Unknown')}")
        if 'deal_value_millions' in tx:
            print(f"  Deal value: ${tx['deal_value_millions']}M")
        if 'target_revenue_millions' in tx:
            print(f"  Target revenue: ${tx['target_revenue_millions']}M")
            if 'deal_value_millions' in tx:
                multiple = tx['deal_value_millions'] / tx['target_revenue_millions']
                print(f"  Implied multiple: {multiple:.1f}x")
    
    print("\nAI Insights:")
    print(json.dumps(results.get('ai_insights', {}), indent=2))

if __name__ == "__main__":
    main()