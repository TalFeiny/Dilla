#!/usr/bin/env python3
"""Enhanced Tavily search module for PWERM - finds real deals and calculates multiples"""

import re
import sys
import json
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class EnhancedTavilySearch:
    def __init__(self, tavily_api_key: str):
        self.tavily_api_key = tavily_api_key
        self.tavily_base_url = "https://api.tavily.com/search"
    
    def search_comprehensive_market_data(self, company_name: str, sector: str) -> Dict:
        """Perform comprehensive market search focusing on real data"""
        
        research = {
            "company": company_name,
            "sector": sector,
            "timestamp": datetime.now().isoformat(),
            "transactions": [],  # Real M&A and IPO transactions with values
            "competitors": [],   # Direct competitors with metrics
            "market_dynamics": {
                "headwinds": [],
                "tailwinds": [],
                "market_size": None,
                "growth_rate": None
            },
            "strategic_intelligence": {
                "potential_acquirers": [],
                "ipo_readiness": {},
                "market_position": {}
            },
            "funding_data": {},
            "raw_results": []  # Keep raw results for debugging
        }
        
        # Execute targeted searches
        self._search_transactions(company_name, sector, research)
        self._search_company_specifics(company_name, sector, research)
        self._search_market_dynamics(company_name, sector, research)
        self._search_strategic_context(company_name, sector, research)
        
        return research
    
    def _search_transactions(self, company: str, sector: str, research: Dict):
        """Search for real M&A and IPO transactions"""
        
        queries = [
            # Recent M&A deals with values
            f'{sector} acquisitions 2023 2024 deal value price billion million',
            f'{sector} M&A transactions exits "acquired for" "sold for" valuation',
            f'companies like {company} acquired acquisition price revenue "billion" "million"',
            
            # IPO transactions
            f'{sector} IPO 2023 2024 valuation revenue "went public" "public offering"',
            f'tech IPOs recent valuation revenue market cap ARR',
            
            # Specific high-value deals
            f'Figma Adobe acquisition 20 billion revenue',
            f'Klaviyo IPO valuation revenue multiple 2023',
            f'recent unicorn exits {sector} valuation revenue'
        ]
        
        for query in queries:
            sys.stderr.write(f"Transaction search: {query}\n")
            results = self._execute_search(query)
            
            # Extract transactions from results
            for result in results.get('results', []):
                transactions = self._extract_transactions(
                    result.get('content', ''),
                    result.get('title', ''),
                    result.get('url', '')
                )
                research['transactions'].extend(transactions)
            
            # Store raw results
            research['raw_results'].append({
                'query': query,
                'answer': results.get('answer', ''),
                'results_count': len(results.get('results', []))
            })
    
    def _search_company_specifics(self, company: str, sector: str, research: Dict):
        """Search for company-specific data"""
        
        queries = [
            f'"{company}" revenue ARR "annual recurring revenue" growth rate 2024',
            f'"{company}" valuation funding rounds investors "Series" "raised"',
            f'"{company}" competitors alternatives market share {sector}',
            f'"{company}" employees headcount growth scaling'
        ]
        
        for query in queries:
            sys.stderr.write(f"Company search: {query}\n")
            results = self._execute_search(query)
            
            # Extract company metrics
            if 'revenue' in query:
                self._extract_company_metrics(results, company, research)
            elif 'funding' in query:
                self._extract_funding_data(results, company, research)
            elif 'competitors' in query:
                self._extract_competitors(results, company, research)
    
    def _search_market_dynamics(self, company: str, sector: str, research: Dict):
        """Search for market headwinds and tailwinds"""
        
        queries = [
            f'{sector} market challenges headwinds risks 2024 2025',
            f'{sector} market opportunities tailwinds growth drivers trends',
            f'{sector} market size TAM growth rate CAGR forecast',
            f'{company} challenges risks threats competitive pressure',
            f'{company} opportunities growth catalysts expansion potential'
        ]
        
        for query in queries:
            sys.stderr.write(f"Market dynamics search: {query}\n")
            results = self._execute_search(query)
            
            # Extract headwinds and tailwinds
            self._extract_market_forces(results, query, research)
    
    def _search_strategic_context(self, company: str, sector: str, research: Dict):
        """Search for strategic acquisition and IPO context"""
        
        queries = [
            f'who would acquire {company} strategic buyers {sector} consolidation',
            f'why {company} IPO instead of acquisition strategic rationale',
            f'{sector} consolidation M&A activity strategic buyers private equity',
            f'{company} acquisition barriers antitrust regulatory concerns',
            f'{company} IPO readiness profitability scale requirements'
        ]
        
        for query in queries:
            sys.stderr.write(f"Strategic search: {query}\n")
            results = self._execute_search(query)
            
            # Extract strategic intelligence
            if 'acquire' in query:
                self._extract_acquirer_intelligence(results, company, research)
            elif 'IPO' in query:
                self._extract_ipo_intelligence(results, company, research)
    
    def _execute_search(self, query: str) -> Dict:
        """Execute a Tavily search"""
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
                return response.json()
            else:
                sys.stderr.write(f"Search error: {response.status_code}\n")
                return {}
                
        except Exception as e:
            sys.stderr.write(f"Search exception: {e}\n")
            return {}
    
    def _extract_transactions(self, content: str, title: str, url: str) -> List[Dict]:
        """Extract M&A/IPO transactions with values"""
        transactions = []
        
        # Combined text for better context
        full_text = f"{title} {content}"
        
        # M&A patterns
        ma_patterns = [
            # Company A acquired Company B for $X
            r'([A-Z][\w\s&\.]+?)\s+(?:acquired|acquires?|bought|buys?)\s+([A-Z][\w\s&\.]+?)(?:\s+for\s+(?:up\s+to\s+)?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M))?',
            # Company B sold to Company A for $X
            r'([A-Z][\w\s&\.]+?)\s+(?:sold\s+to|acquired\s+by)\s+([A-Z][\w\s&\.]+?)(?:\s+for\s+(?:up\s+to\s+)?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M))?',
            # $X acquisition of Company
            r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\s+acquisition\s+of\s+([A-Z][\w\s&\.]+)',
        ]
        
        for pattern in ma_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                transaction = {
                    'type': 'M&A',
                    'source': title[:100],
                    'url': url
                }
                
                # Parse based on pattern structure
                if pattern.startswith(r'([A-Z]'):
                    if len(match.groups()) >= 2:
                        transaction['acquirer'] = match.group(1).strip()
                        transaction['target'] = match.group(2).strip()
                    if len(match.groups()) >= 4 and match.group(3):
                        value = float(match.group(3).replace(',', ''))
                        unit = match.group(4).lower()
                        if unit in ['billion', 'b']:
                            value *= 1000
                        transaction['deal_value_millions'] = value
                elif pattern.startswith(r'\$'):
                    if len(match.groups()) >= 3:
                        value = float(match.group(1).replace(',', ''))
                        unit = match.group(2).lower()
                        if unit in ['billion', 'b']:
                            value *= 1000
                        transaction['deal_value_millions'] = value
                        transaction['target'] = match.group(3).strip()
                        transaction['acquirer'] = 'Strategic Buyer'
                
                # Look for revenue in the surrounding context
                if 'target' in transaction:
                    transaction = self._find_transaction_revenue(full_text, transaction)
                
                # Calculate multiple if we have both values
                if 'deal_value_millions' in transaction and 'revenue_millions' in transaction:
                    if transaction['revenue_millions'] > 0:
                        transaction['calculated_multiple'] = transaction['deal_value_millions'] / transaction['revenue_millions']
                
                transactions.append(transaction)
        
        # IPO patterns
        ipo_patterns = [
            r'([A-Z][\w\s&\.]+?)\s+(?:IPO|went\s+public|goes\s+public)(?:\s+at\s+(?:a\s+)?valuation\s+of\s+)?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)',
            r'([A-Z][\w\s&\.]+?)\s+valued\s+at\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\s+(?:in\s+)?(?:its\s+)?IPO',
        ]
        
        for pattern in ipo_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for match in matches:
                company = match.group(1).strip()
                value = float(match.group(2).replace(',', ''))
                unit = match.group(3).lower()
                
                if unit in ['billion', 'b']:
                    value *= 1000
                
                transaction = {
                    'type': 'IPO',
                    'company': company,
                    'valuation_millions': value,
                    'source': title[:100],
                    'url': url
                }
                
                # Look for revenue
                transaction = self._find_transaction_revenue(full_text, transaction)
                
                # Calculate multiple
                if 'revenue_millions' in transaction and transaction['revenue_millions'] > 0:
                    transaction['calculated_multiple'] = value / transaction['revenue_millions']
                
                transactions.append(transaction)
        
        return transactions
    
    def _find_transaction_revenue(self, text: str, transaction: Dict) -> Dict:
        """Find revenue data for a transaction"""
        
        # Get company name to search for
        company = transaction.get('target') or transaction.get('company', '')
        if not company:
            return transaction
        
        # Revenue patterns specific to the company
        patterns = [
            rf'{re.escape(company)}[^.]*?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\s*(?:in\s+)?(?:revenue|ARR|annual\s+recurring\s+revenue)',
            rf'(?:revenue|ARR)\s+of\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)[^.]*?{re.escape(company)}',
            rf'{re.escape(company)}[^.]*?(?:revenue|ARR)\s+(?:of\s+)?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                revenue = float(match.group(1).replace(',', ''))
                unit = match.group(2).lower()
                if unit in ['billion', 'b']:
                    revenue *= 1000
                transaction['revenue_millions'] = revenue
                break
        
        return transaction
    
    def _extract_company_metrics(self, results: Dict, company: str, research: Dict):
        """Extract company revenue and growth metrics"""
        
        for result in results.get('results', []):
            content = result.get('content', '')
            
            # Revenue patterns
            revenue_patterns = [
                r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\s*(?:in\s+)?(?:revenue|ARR)',
                r'(?:revenue|ARR)\s+of\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)',
            ]
            
            for pattern in revenue_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    revenue = float(match.group(1).replace(',', ''))
                    unit = match.group(2).lower()
                    if unit in ['billion', 'b']:
                        revenue *= 1000
                    
                    if 'revenue_millions' not in research['strategic_intelligence']['market_position']:
                        research['strategic_intelligence']['market_position']['revenue_millions'] = revenue
                    break
            
            # Growth rate
            growth_pattern = r'(\d+)%\s*(?:growth|increase|YoY|year-over-year)'
            growth_match = re.search(growth_pattern, content, re.IGNORECASE)
            if growth_match:
                research['strategic_intelligence']['market_position']['growth_rate'] = int(growth_match.group(1))
    
    def _extract_funding_data(self, results: Dict, company: str, research: Dict):
        """Extract funding information"""
        
        for result in results.get('results', []):
            content = result.get('content', '')
            
            # Funding patterns
            funding_patterns = [
                r'raised\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)',
                r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\s+(?:funding|round)',
                r'valued\s+at\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)',
            ]
            
            funding_rounds = []
            for pattern in funding_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    amount = float(match.group(1).replace(',', ''))
                    unit = match.group(2).lower()
                    if unit in ['billion', 'b']:
                        amount *= 1000
                    
                    round_info = {
                        'amount_millions': amount,
                        'type': 'valuation' if 'valued' in match.group(0) else 'funding'
                    }
                    
                    # Try to extract round name
                    round_match = re.search(r'(Series\s+[A-Z]|seed|growth)', content[max(0, match.start()-50):match.end()+50], re.IGNORECASE)
                    if round_match:
                        round_info['round'] = round_match.group(1)
                    
                    funding_rounds.append(round_info)
            
            if funding_rounds:
                research['funding_data']['rounds'] = funding_rounds
                research['funding_data']['total_raised'] = sum(r['amount_millions'] for r in funding_rounds if r['type'] == 'funding')
    
    def _extract_competitors(self, results: Dict, company: str, research: Dict):
        """Extract competitor information"""
        
        for result in results.get('results', []):
            content = result.get('content', '')
            
            # Competitor patterns
            patterns = [
                r'competitors?\s+(?:include|are|such\s+as)\s+([A-Z][\w\s,&]+)',
                r'([A-Z][\w\s&]+)\s+(?:competes?|competing)\s+with',
                r'alternatives?\s+(?:to\s+)?(?:include|are)\s+([A-Z][\w\s,&]+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Split by commas and clean
                    companies = [c.strip() for c in match.split(',')]
                    for comp in companies:
                        if comp and len(comp) > 2 and comp != company:
                            if comp not in [c['name'] for c in research['competitors']]:
                                research['competitors'].append({
                                    'name': comp,
                                    'source': result.get('title', '')[:100]
                                })
    
    def _extract_market_forces(self, results: Dict, query: str, research: Dict):
        """Extract headwinds and tailwinds"""
        
        # Determine if this is headwind or tailwind search
        is_headwind = any(word in query.lower() for word in ['challenge', 'headwind', 'risk', 'threat'])
        is_tailwind = any(word in query.lower() for word in ['opportunity', 'tailwind', 'growth', 'driver', 'catalyst'])
        
        for result in results.get('results', []):
            content = result.get('content', '')
            
            # Extract relevant sentences
            sentences = content.split('.')
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20 or len(sentence) > 300:
                    continue
                
                # Headwind indicators
                if is_headwind or any(word in sentence.lower() for word in ['challenge', 'risk', 'threat', 'pressure', 'decline', 'concern']):
                    if sentence not in research['market_dynamics']['headwinds']:
                        research['market_dynamics']['headwinds'].append(sentence)
                
                # Tailwind indicators
                elif is_tailwind or any(word in sentence.lower() for word in ['opportunity', 'growth', 'demand', 'adoption', 'expansion', 'potential']):
                    if sentence not in research['market_dynamics']['tailwinds']:
                        research['market_dynamics']['tailwinds'].append(sentence)
            
            # Extract market size and growth
            size_pattern = r'market\s+(?:size|worth)\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|trillion)'
            size_match = re.search(size_pattern, content, re.IGNORECASE)
            if size_match:
                size = float(size_match.group(1).replace(',', ''))
                unit = size_match.group(2).lower()
                if unit == 'trillion':
                    size *= 1000000
                elif unit == 'billion':
                    size *= 1000
                research['market_dynamics']['market_size'] = size
            
            growth_pattern = r'(?:CAGR|growth\s+rate)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%'
            growth_match = re.search(growth_pattern, content, re.IGNORECASE)
            if growth_match:
                research['market_dynamics']['growth_rate'] = float(growth_match.group(1))
    
    def _extract_acquirer_intelligence(self, results: Dict, company: str, research: Dict):
        """Extract potential acquirer information"""
        
        # Major tech companies and PE firms
        major_acquirers = [
            'Microsoft', 'Google', 'Amazon', 'Apple', 'Meta', 'Oracle', 'Salesforce', 
            'Adobe', 'IBM', 'SAP', 'Workday', 'ServiceNow', 'Intuit', 'Shopify',
            'Vista Equity', 'Thoma Bravo', 'KKR', 'Blackstone', 'Silver Lake'
        ]
        
        for result in results.get('results', []):
            content = result.get('content', '')
            
            # Look for acquirer mentions
            for acquirer in major_acquirers:
                if acquirer.lower() in content.lower():
                    # Extract context
                    sentences = content.split('.')
                    for sentence in sentences:
                        if acquirer.lower() in sentence.lower() and company.lower() in sentence.lower():
                            if acquirer not in [a['name'] for a in research['strategic_intelligence']['potential_acquirers']]:
                                research['strategic_intelligence']['potential_acquirers'].append({
                                    'name': acquirer,
                                    'rationale': sentence.strip()[:200]
                                })
                            break
    
    def _extract_ipo_intelligence(self, results: Dict, company: str, research: Dict):
        """Extract IPO readiness indicators"""
        
        ipo_readiness = research['strategic_intelligence']['ipo_readiness']
        
        for result in results.get('results', []):
            content = result.get('content', '')
            
            # Look for IPO readiness indicators
            if company.lower() in content.lower() and 'ipo' in content.lower():
                # Positive indicators
                if any(word in content.lower() for word in ['ready', 'preparing', 'planning', 'considering']):
                    ipo_readiness['likelihood'] = 'high'
                    ipo_readiness['indicators'] = ipo_readiness.get('indicators', [])
                    ipo_readiness['indicators'].append('Company appears to be preparing for IPO')
                
                # Negative indicators
                elif any(word in content.lower() for word in ['not ready', 'unlikely', 'barriers']):
                    ipo_readiness['likelihood'] = 'low'
                    ipo_readiness['barriers'] = ipo_readiness.get('barriers', [])
                    
                    # Extract specific barriers
                    sentences = content.split('.')
                    for sentence in sentences:
                        if 'barrier' in sentence.lower() or 'challenge' in sentence.lower():
                            ipo_readiness['barriers'].append(sentence.strip())

def test_enhanced_search():
    """Test the enhanced search functionality"""
    import os
    
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        print("Error: No TAVILY_API_KEY found")
        return
    
    # Test with Deel
    searcher = EnhancedTavilySearch(tavily_key)
    results = searcher.search_comprehensive_market_data("Deel", "HR Tech")
    
    print("\n" + "="*60)
    print("ENHANCED SEARCH RESULTS: Deel (HR Tech)")
    print("="*60)
    
    print(f"\n📊 TRANSACTIONS FOUND: {len(results['transactions'])}")
    for tx in results['transactions'][:5]:
        if tx['type'] == 'M&A':
            print(f"  • {tx.get('acquirer', 'Unknown')} → {tx.get('target', 'Unknown')}", end="")
        else:
            print(f"  • {tx.get('company', 'Unknown')} (IPO)", end="")
        
        if 'deal_value_millions' in tx or 'valuation_millions' in tx:
            value = tx.get('deal_value_millions') or tx.get('valuation_millions')
            print(f" - ${value:,.0f}M", end="")
        
        if 'calculated_multiple' in tx:
            print(f" ({tx['calculated_multiple']:.1f}x)", end="")
        
        print()
    
    print(f"\n🤝 COMPETITORS: {len(results['competitors'])}")
    for comp in results['competitors'][:5]:
        print(f"  • {comp['name']}")
    
    print(f"\n📈 MARKET DYNAMICS")
    print(f"  Headwinds: {len(results['market_dynamics']['headwinds'])}")
    for hw in results['market_dynamics']['headwinds'][:2]:
        print(f"    - {hw[:100]}...")
    
    print(f"  Tailwinds: {len(results['market_dynamics']['tailwinds'])}")
    for tw in results['market_dynamics']['tailwinds'][:2]:
        print(f"    + {tw[:100]}...")
    
    if results['market_dynamics']['market_size']:
        print(f"  Market Size: ${results['market_dynamics']['market_size']:,.0f}M")
    
    print(f"\n🎯 STRATEGIC INTELLIGENCE")
    print(f"  Potential Acquirers: {len(results['strategic_intelligence']['potential_acquirers'])}")
    for acq in results['strategic_intelligence']['potential_acquirers']:
        print(f"    • {acq['name']}: {acq.get('rationale', '')[:80]}...")
    
    # Save results
    with open('enhanced_search_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\n💾 Full results saved to enhanced_search_results.json")

if __name__ == "__main__":
    test_enhanced_search()