#!/usr/bin/env python3
"""Script to update PWERM analysis with better search functionality"""

import os
import shutil
from datetime import datetime

def create_improved_pwerm():
    """Create an improved version of pwerm_analysis.py with better search"""
    
    print("Creating improved PWERM analysis script...")
    
    # Read the original file
    original_path = "/Users/admin/Documents/Document Processor/vc-platform-new/scripts/pwerm_analysis.py"
    backup_path = f"{original_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create backup
    shutil.copy2(original_path, backup_path)
    print(f"Backup created: {backup_path}")
    
    # Read the content
    with open(original_path, 'r') as f:
        content = f.read()
    
    # Key improvements to make:
    improvements = """
# IMPROVEMENTS TO MAKE:

1. Replace generic queries with specific M&A searches:
   - Search for actual deals: "Workday acquired Peakon $700 million"
   - Find comparable exits: "HR tech acquisitions 2024 price revenue"
   - Get real multiples by finding deals with both price AND revenue

2. Remove dummy data fallbacks:
   - No more sector_defaults = {'SaaS': [6, 10, 15, 25]}
   - If no data found, that's valuable information
   - Better to have fewer real comparables than many fake ones

3. Enhance extraction patterns:
   - Look for "$X billion acquisition" patterns
   - Find revenue separately, then calculate multiples
   - Extract headwinds/tailwinds from actual search results

4. Improve Claude analysis prompt:
   - Focus on analyst-grade insights
   - Identify specific barriers (lawsuits, regulatory)
   - Calculate multiples from found data
   - Provide actionable PWERM inputs

5. Better sector-specific searches:
   - HR Tech: Workday, ADP, Ceridian deals
   - Fintech: Stripe, Square, PayPal comparables
   - AI: Recent AI platform acquisitions
   - Customize per sector for relevance
"""
    
    print(improvements)
    
    # Create the enhanced search function
    enhanced_search_code = '''
    def _enhanced_tavily_search(self, company_name: str, sector: str) -> Dict:
        """Enhanced Tavily search with smart queries that find real data"""
        
        research = {
            "exit_comparables": [],
            "strategic_acquirers": [],
            "market_dynamics": {
                "headwinds": [],
                "tailwinds": [],
                "competitive_threats": [],
                "market_position": {}
            },
            "company_intelligence": {},
            "competitors": [],
            "found_real_data": False
        }
        
        # Smart sector-specific M&A queries
        ma_queries = self._get_smart_ma_queries(company_name, sector)
        
        sys.stderr.write(f"\\n🔍 Executing {len(ma_queries)} smart searches...\\n")
        
        # Execute searches
        for i, query in enumerate(ma_queries[:15]):
            sys.stderr.write(f"[{i+1}/15] {query[:60]}...\\n")
            
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
                    
                    # Extract based on query type
                    if any(term in query for term in ['acquisition', 'acquired', 'M&A', 'IPO']):
                        comparables = self._extract_smart_comparables(data, sector)
                        research["exit_comparables"].extend(comparables)
                        if comparables:
                            research["found_real_data"] = True
                    
                    elif any(term in query for term in ['headwind', 'challenge', 'risk', 'lawsuit']):
                        self._extract_headwinds(data, research)
                    
                    elif any(term in query for term in ['competitor', 'alternative']):
                        self._extract_competitors(data, company_name, research)
                    
                    # Store AI summaries
                    if data.get('answer'):
                        research["company_intelligence"][f"q{i}"] = data['answer']
                        
            except Exception as e:
                sys.stderr.write(f"  ❌ Error: {str(e)}\\n")
        
        return research
    
    def _get_smart_ma_queries(self, company: str, sector: str) -> List[str]:
        """Generate smart queries based on sector"""
        
        queries = []
        
        if sector == "HR Tech":
            queries = [
                'Workday acquired Peakon $700 million employee engagement revenue',
                'Ultimate Kronos merger $22 billion combined revenue HR',
                'Cornerstone OnDemand Vista Equity $5.2 billion revenue',
                'Ceridian Dayforce market cap revenue public company',
                'ADP acquisitions WorkMarket Global Cash Card price',
                f'{company} valuation revenue ARR growth rate 2024',
                'Gusto Rippling BambooHR valuation revenue comparison',
                'HR tech M&A deals 2024 price revenue multiple'
            ]
        elif sector == "Fintech":
            queries = [
                'Square Afterpay $29 billion acquisition revenue',
                'Stripe valuation $95 billion revenue payments',
                'PayPal acquisitions Honey Paidy price revenue',
                f'{company} fintech valuation revenue growth 2024',
                'fintech M&A transactions 2024 price multiples'
            ]
        else:
            # Generic but targeted
            queries = [
                f'{sector} acquisitions 2024 "acquired for $" revenue',
                f'{sector} M&A deals valuation revenue multiple',
                f'{company} valuation revenue ARR funding 2024',
                f'{company} competitors market share {sector}'
            ]
        
        # Add strategic searches
        queries.extend([
            f'who would acquire {company} strategic buyers {sector}',
            f'{company} IPO likelihood barriers readiness',
            f'{company} lawsuit regulatory issues challenges'
        ])
        
        return queries
    
    def _extract_smart_comparables(self, data: Dict, sector: str) -> List[Dict]:
        """Extract comparables with smart pattern matching"""
        comparables = []
        
        for result in data.get('results', []):
            content = result.get('content', '')
            title = result.get('title', '')
            
            # Look for deals with values
            import re
            
            # Pattern: Company A acquired Company B for $X
            pattern = r'([A-Z][\\w\\s&]+?)\\s+(?:acquired|bought)\\s+([A-Z][\\w\\s&]+?)\\s+for\\s+\\$?([\\d,]+(?:\\.\\d+)?)\\s*(billion|million|B|M)'
            matches = re.finditer(pattern, content, re.IGNORECASE)
            
            for match in matches:
                deal = {
                    "acquirer": match.group(1).strip(),
                    "target": match.group(2).strip(),
                    "deal_value": float(match.group(3).replace(',', '')),
                    "unit": match.group(4).lower(),
                    "source": title[:100],
                    "sector": sector
                }
                
                # Convert to millions
                if deal["unit"] in ['billion', 'b']:
                    deal["deal_value"] *= 1000
                
                # Look for revenue to calculate multiple
                revenue = self._find_revenue_near_company(content, deal["target"])
                if revenue:
                    deal["target_revenue"] = revenue
                    deal["ev_revenue_multiple"] = deal["deal_value"] / revenue
                    deal["revenue_multiple"] = deal["ev_revenue_multiple"]
                
                comparables.append(deal)
        
        return comparables
    
    def _extract_headwinds(self, data: Dict, research: Dict):
        """Extract specific headwinds from search results"""
        
        for result in data.get('results', []):
            content = result.get('content', '')
            
            # Look for headwind indicators
            headwind_patterns = [
                r'(lawsuit|litigation|legal dispute)[^.]*\\.',
                r'(regulatory|compliance|antitrust)[^.]*\\.',
                r'(challenge|risk|threat|barrier)[^.]*\\.',
                r'(competition|competitive pressure)[^.]*\\.'
            ]
            
            for pattern in headwind_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Extract the full sentence
                    start = content.rfind('.', 0, match.start()) + 1
                    end = content.find('.', match.end())
                    if end == -1:
                        end = len(content)
                    
                    headwind = content[start:end].strip()
                    if 20 < len(headwind) < 300:
                        research["market_dynamics"]["headwinds"].append(headwind)
    
    def _find_revenue_near_company(self, text: str, company: str) -> Optional[float]:
        """Find revenue mentioned near company name"""
        import re
        
        # Look for revenue within 100 chars of company name
        company_pos = text.lower().find(company.lower())
        if company_pos == -1:
            return None
        
        # Extract surrounding context
        start = max(0, company_pos - 100)
        end = min(len(text), company_pos + len(company) + 100)
        context = text[start:end]
        
        # Revenue patterns
        patterns = [
            r'\\$?([\\d,]+(?:\\.\\d+)?)\\s*(billion|million|B|M)\\s*(?:in\\s+)?(?:revenue|ARR)',
            r'(?:revenue|ARR)\\s+(?:of\\s+)?\\$?([\\d,]+(?:\\.\\d+)?)\\s*(billion|million|B|M)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                amount = float(match.group(1).replace(',', ''))
                unit = match.group(2).lower()
                if unit in ['billion', 'b']:
                    amount *= 1000
                return amount
        
        return None
'''
    
    print("\n✅ Key improvements prepared")
    print("\n📝 Next steps:")
    print("1. Replace _tavily_market_search with _enhanced_tavily_search")
    print("2. Remove all dummy data fallbacks")
    print("3. Update _extract_exit_comparables to use smart patterns")
    print("4. Enhance Claude prompt for analyst-grade insights")
    print("5. Test with real companies to validate")
    
    return backup_path

if __name__ == "__main__":
    backup = create_improved_pwerm()
    print(f"\n💾 Original backed up to: {backup}")
    print("\n🚀 Ready to implement improvements!")