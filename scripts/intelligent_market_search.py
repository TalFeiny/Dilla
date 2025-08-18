#!/usr/bin/env python3
"""Intelligent market search that finds real strategic context, barriers, and opportunities"""

import os
import sys
import json
import requests
from typing import Dict, List, Tuple
from datetime import datetime

class IntelligentMarketSearch:
    def __init__(self, tavily_api_key: str, claude_api_key: str = None):
        self.tavily_api_key = tavily_api_key
        self.claude_api_key = claude_api_key
        self.tavily_base_url = "https://api.tavily.com/search"
    
    def search_strategic_intelligence(self, company_name: str, sector: str, current_arr: float = None) -> Dict:
        """Perform intelligent, context-aware market search"""
        
        print(f"\n🔍 Performing intelligent market analysis for {company_name} in {sector}...")
        
        results = {
            "company": company_name,
            "sector": sector,
            "current_arr": current_arr,
            "timestamp": datetime.now().isoformat(),
            "exit_scenarios": {
                "ipo": {"likelihood": None, "barriers": [], "catalysts": [], "timeline": None},
                "acquisition": {"likelihood": None, "acquirers": [], "barriers": [], "strategic_fit": []},
                "stay_private": {"likelihood": None, "reasons": []}
            },
            "strategic_context": {
                "legal_issues": [],
                "regulatory_barriers": [],
                "competitive_threats": [],
                "market_position": {},
                "growth_trajectory": {}
            },
            "comparable_exits": [],
            "market_intelligence": {},
            "key_insights": []
        }
        
        # Phase 1: Company-specific intelligence
        print("\n📋 Phase 1: Company Intelligence")
        self._search_company_intelligence(company_name, sector, results)
        
        # Phase 2: Exit scenario analysis
        print("\n🚪 Phase 2: Exit Scenarios")
        self._search_exit_scenarios(company_name, sector, results)
        
        # Phase 3: Market dynamics and comparables
        print("\n📊 Phase 3: Market Analysis")
        self._search_market_dynamics(company_name, sector, results)
        
        # Phase 4: Strategic barriers and catalysts
        print("\n⚠️  Phase 4: Barriers & Catalysts")
        self._search_barriers_catalysts(company_name, sector, results)
        
        # Phase 5: Synthesize insights
        print("\n💡 Phase 5: Synthesizing Insights")
        self._synthesize_insights(results)
        
        return results
    
    def _search_company_intelligence(self, company: str, sector: str, results: Dict):
        """Search for company-specific intelligence"""
        
        queries = [
            # Legal and regulatory issues
            f'"{company}" lawsuit legal dispute regulatory investigation SEC',
            f'"{company}" compliance issues regulatory barriers {sector}',
            
            # Financial metrics
            f'"{company}" revenue ARR growth rate valuation 2024',
            f'"{company}" funding history investors board members',
            
            # Strategic position
            f'"{company}" market share competitive position {sector}',
            f'"{company}" CEO founder leadership team strategy'
        ]
        
        for query in queries:
            print(f"  → {query[:60]}...")
            data = self._execute_search(query)
            
            if "lawsuit" in query or "legal" in query:
                self._extract_legal_issues(data, results)
            elif "revenue" in query or "ARR" in query:
                self._extract_financial_metrics(data, results)
            elif "market share" in query:
                self._extract_market_position(data, results)
    
    def _search_exit_scenarios(self, company: str, sector: str, results: Dict):
        """Search for exit scenario intelligence"""
        
        queries = [
            # IPO scenarios
            f'"{company}" IPO plans going public timeline barriers',
            f'{company} IPO readiness revenue scale profitability requirements',
            f'why {company} would IPO instead of acquisition strategic rationale',
            
            # Acquisition scenarios
            f'who would acquire {company} strategic buyers {sector}',
            f'Workday ADP Oracle Salesforce acquire {company} strategic fit',
            f'{company} acquisition barriers antitrust regulatory issues',
            
            # Comparable exits
            f'{sector} IPOs 2023 2024 revenue valuation at IPO',
            f'{sector} acquisitions M&A deals price revenue multiple 2024',
            f'companies similar to {company} exit valuation revenue'
        ]
        
        for query in queries:
            print(f"  → {query[:60]}...")
            data = self._execute_search(query)
            
            if "IPO" in query and company in query:
                self._extract_ipo_intelligence(data, company, results)
            elif "acquire" in query:
                self._extract_acquisition_intelligence(data, company, results)
            elif "IPOs" in query or "acquisitions" in query:
                self._extract_comparable_exits(data, sector, results)
    
    def _search_market_dynamics(self, company: str, sector: str, results: Dict):
        """Search for market dynamics and trends"""
        
        queries = [
            # Market structure
            f'{sector} market consolidation M&A activity trends 2024',
            f'{sector} market size growth rate competitive landscape',
            
            # Competitive dynamics
            f'{company} competitors market share battle competitive threats',
            f'disruption in {sector} new entrants threats to {company}',
            
            # Strategic trends
            f'{sector} strategic buyers acquisition thesis consolidation',
            f'private equity interest {sector} rollup platform deals'
        ]
        
        for query in queries:
            print(f"  → {query[:60]}...")
            data = self._execute_search(query)
            
            if "consolidation" in query:
                self._extract_consolidation_trends(data, results)
            elif "competitors" in query:
                self._extract_competitive_dynamics(data, results)
    
    def _search_barriers_catalysts(self, company: str, sector: str, results: Dict):
        """Search for specific barriers and catalysts"""
        
        queries = [
            # Barriers
            f'{company} barriers to acquisition IPO exit challenges',
            f'{company} antitrust concerns market dominance regulatory',
            f'{company} litigation risk legal exposure liabilities',
            
            # Catalysts
            f'{company} growth catalysts expansion opportunities',
            f'{sector} exit windows market timing IPO environment',
            f'{company} strategic value synergies acquisition rationale'
        ]
        
        for query in queries:
            print(f"  → {query[:60]}...")
            data = self._execute_search(query)
            
            if "barriers" in query or "antitrust" in query:
                self._extract_barriers(data, results)
            elif "catalysts" in query or "opportunities" in query:
                self._extract_catalysts(data, results)
    
    def _execute_search(self, query: str) -> Dict:
        """Execute a single search query"""
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
                print(f"    ❌ Error: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            return {}
    
    def _extract_legal_issues(self, data: Dict, results: Dict):
        """Extract legal issues and lawsuits"""
        import re
        
        for result in data.get("results", []):
            content = result.get("content", "")
            
            # Look for lawsuit mentions
            lawsuit_patterns = [
                r'lawsuit|legal action|litigation|sued',
                r'regulatory investigation|SEC investigation|compliance issues',
                r'legal dispute|legal challenge|legal risk'
            ]
            
            for pattern in lawsuit_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Extract context
                    sentences = content.split('.')
                    for sentence in sentences:
                        if re.search(pattern, sentence, re.IGNORECASE):
                            issue = {
                                "type": "legal",
                                "description": sentence.strip(),
                                "source": result.get("title", "")[:100]
                            }
                            results["strategic_context"]["legal_issues"].append(issue)
                            
                            # This could be a barrier to exit
                            if "lawsuit" in sentence.lower():
                                results["exit_scenarios"]["ipo"]["barriers"].append(
                                    f"Legal: {sentence.strip()[:100]}..."
                                )
                                results["exit_scenarios"]["acquisition"]["barriers"].append(
                                    f"Legal: {sentence.strip()[:100]}..."
                                )
                            break
    
    def _extract_financial_metrics(self, data: Dict, results: Dict):
        """Extract financial metrics"""
        import re
        
        for result in data.get("results", []):
            content = result.get("content", "")
            
            # Revenue patterns
            revenue_patterns = [
                r'\$?([\d,]+(?:\.\d+)?)\s*(billion|million|M|B)\s*(?:in\s+)?(?:ARR|annual recurring revenue|revenue)',
                r'(?:ARR|revenue)\s*of\s*\$?([\d,]+(?:\.\d+)?)\s*(billion|million|M|B)'
            ]
            
            for pattern in revenue_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    amount = float(match.group(1).replace(',', ''))
                    unit = match.group(2).lower()
                    if unit in ['billion', 'b']:
                        amount *= 1000
                    
                    results["strategic_context"]["growth_trajectory"]["revenue_millions"] = amount
                    break
            
            # Growth rate
            growth_pattern = r'(\d+)%\s*(?:growth|increase|YoY)'
            growth_match = re.search(growth_pattern, content, re.IGNORECASE)
            if growth_match:
                results["strategic_context"]["growth_trajectory"]["growth_rate"] = int(growth_match.group(1))
    
    def _extract_ipo_intelligence(self, data: Dict, company: str, results: Dict):
        """Extract IPO-specific intelligence"""
        
        if data.get("answer"):
            # Check if answer suggests IPO likelihood
            answer = data["answer"].lower()
            if "ipo" in answer and company.lower() in answer:
                if any(word in answer for word in ["likely", "planning", "preparing", "considering"]):
                    results["exit_scenarios"]["ipo"]["likelihood"] = "high"
                    results["key_insights"].append(f"IPO appears likely based on market intelligence")
                elif any(word in answer for word in ["unlikely", "not ready", "barriers"]):
                    results["exit_scenarios"]["ipo"]["likelihood"] = "low"
        
        for result in data.get("results", []):
            content = result.get("content", "")
            
            # Look for IPO barriers
            if "barrier" in content.lower() or "challenge" in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if "ipo" in sentence.lower() and any(word in sentence.lower() for word in ["barrier", "challenge", "prevent"]):
                        results["exit_scenarios"]["ipo"]["barriers"].append(sentence.strip())
            
            # Look for IPO catalysts
            if "catalyst" in content.lower() or "ready" in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if "ipo" in sentence.lower() and any(word in sentence.lower() for word in ["catalyst", "ready", "prepare"]):
                        results["exit_scenarios"]["ipo"]["catalysts"].append(sentence.strip())
    
    def _extract_acquisition_intelligence(self, data: Dict, company: str, results: Dict):
        """Extract acquisition intelligence"""
        import re
        
        for result in data.get("results", []):
            content = result.get("content", "")
            
            # Extract potential acquirers
            acquirer_patterns = [
                r'(Workday|ADP|Oracle|Salesforce|SAP|Microsoft|Google|Amazon)',
                r'([A-Z][\w\s&]+?)\s+(?:could|would|might)\s+acquire',
                r'strategic buyer[s]?\s+(?:include|such as|like)\s+([A-Z][\w\s&,]+)'
            ]
            
            for pattern in acquirer_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    acquirer = match.strip() if isinstance(match, str) else match[0].strip()
                    if acquirer and acquirer not in [a["name"] for a in results["exit_scenarios"]["acquisition"]["acquirers"]]:
                        results["exit_scenarios"]["acquisition"]["acquirers"].append({
                            "name": acquirer,
                            "rationale": self._extract_acquisition_rationale(content, acquirer)
                        })
            
            # Extract barriers
            if "antitrust" in content.lower() or "regulatory" in content.lower():
                sentences = content.split('.')
                for sentence in sentences:
                    if company.lower() in sentence.lower() and any(word in sentence.lower() for word in ["antitrust", "regulatory", "block"]):
                        results["exit_scenarios"]["acquisition"]["barriers"].append(sentence.strip())
    
    def _extract_acquisition_rationale(self, content: str, acquirer: str) -> str:
        """Extract why this acquirer would buy"""
        # Find sentence mentioning the acquirer
        sentences = content.split('.')
        for sentence in sentences:
            if acquirer in sentence:
                return sentence.strip()
        return "Strategic fit"
    
    def _extract_comparable_exits(self, data: Dict, sector: str, results: Dict):
        """Extract comparable exit transactions"""
        import re
        
        for result in data.get("results", []):
            content = result.get("content", "")
            title = result.get("title", "")
            
            # Look for exit transactions
            exit_patterns = [
                r'([A-Z][\w\s&]+?)\s+(?:IPO|went public|goes public)\s+(?:at|with)?\s*(?:a\s+)?(?:valuation\s+of\s+)?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)',
                r'([A-Z][\w\s&]+?)\s+(?:acquired|bought)\s+(?:for|at)\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)',
                r'([A-Z][\w\s&]+?)\s+valued\s+at\s+\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\s+(?:in\s+)?(?:IPO|acquisition)'
            ]
            
            for pattern in exit_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    company = match.group(1).strip()
                    value = float(match.group(2).replace(',', ''))
                    unit = match.group(3).lower()
                    
                    if unit in ['billion', 'b']:
                        value *= 1000
                    
                    exit_comp = {
                        "company": company,
                        "exit_value_millions": value,
                        "type": "IPO" if "ipo" in match.group(0).lower() else "Acquisition",
                        "source": title[:100]
                    }
                    
                    # Try to find revenue for multiple calculation
                    rev_pattern = rf'{re.escape(company)}.*?\$?([\d,]+(?:\.\d+)?)\s*(billion|million|B|M)\s*(?:revenue|ARR)'
                    rev_match = re.search(rev_pattern, content, re.IGNORECASE)
                    if rev_match:
                        rev_value = float(rev_match.group(1).replace(',', ''))
                        if rev_match.group(2).lower() in ['billion', 'b']:
                            rev_value *= 1000
                        exit_comp["revenue_millions"] = rev_value
                        exit_comp["implied_multiple"] = value / rev_value
                    
                    results["comparable_exits"].append(exit_comp)
    
    def _extract_consolidation_trends(self, data: Dict, results: Dict):
        """Extract market consolidation trends"""
        
        if data.get("answer"):
            results["market_intelligence"]["consolidation_summary"] = data["answer"]
        
        for result in data.get("results", []):
            content = result.get("content", "").lower()
            
            if "consolidation" in content:
                # Extract consolidation indicators
                if any(word in content for word in ["increasing", "accelerating", "active"]):
                    results["market_intelligence"]["consolidation_trend"] = "increasing"
                    results["exit_scenarios"]["acquisition"]["catalysts"].append("Market consolidation accelerating")
                elif any(word in content for word in ["slowing", "decreasing", "limited"]):
                    results["market_intelligence"]["consolidation_trend"] = "decreasing"
    
    def _extract_competitive_dynamics(self, data: Dict, results: Dict):
        """Extract competitive dynamics"""
        import re
        
        for result in data.get("results", []):
            content = result.get("content", "")
            
            # Look for competitor names and threats
            competitor_pattern = r'compet(?:e|ing|itor[s]?)\s+(?:include|are|such as)\s+([A-Z][\w\s,&]+)'
            match = re.search(competitor_pattern, content, re.IGNORECASE)
            if match:
                competitors = [c.strip() for c in match.group(1).split(',')]
                results["strategic_context"]["competitive_threats"].extend(competitors)
    
    def _extract_barriers(self, data: Dict, results: Dict):
        """Extract barriers to exit"""
        
        for result in data.get("results", []):
            content = result.get("content", "")
            
            barrier_keywords = ["barrier", "challenge", "prevent", "block", "difficulty", "issue"]
            
            sentences = content.split('.')
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in barrier_keywords):
                    # Categorize the barrier
                    if "regulatory" in sentence.lower() or "antitrust" in sentence.lower():
                        results["strategic_context"]["regulatory_barriers"].append(sentence.strip())
                    elif "legal" in sentence.lower() or "lawsuit" in sentence.lower():
                        results["strategic_context"]["legal_issues"].append({
                            "type": "barrier",
                            "description": sentence.strip()
                        })
    
    def _extract_catalysts(self, data: Dict, results: Dict):
        """Extract catalysts for exit"""
        
        for result in data.get("results", []):
            content = result.get("content", "")
            
            catalyst_keywords = ["catalyst", "opportunity", "driver", "accelerate", "enable"]
            
            sentences = content.split('.')
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in catalyst_keywords):
                    # Add to appropriate exit scenario
                    if "ipo" in sentence.lower():
                        results["exit_scenarios"]["ipo"]["catalysts"].append(sentence.strip())
                    elif "acquisition" in sentence.lower() or "m&a" in sentence.lower():
                        results["exit_scenarios"]["acquisition"]["catalysts"].append(sentence.strip())
    
    def _synthesize_insights(self, results: Dict):
        """Synthesize key insights from all data"""
        
        # Determine most likely exit path
        ipo_barriers = len(results["exit_scenarios"]["ipo"]["barriers"])
        ipo_catalysts = len(results["exit_scenarios"]["ipo"]["catalysts"])
        acq_barriers = len(results["exit_scenarios"]["acquisition"]["barriers"])
        acq_catalysts = len(results["exit_scenarios"]["acquisition"]["catalysts"])
        
        if ipo_catalysts > ipo_barriers and ipo_catalysts > acq_catalysts:
            results["key_insights"].append("IPO appears to be the most likely exit path")
            if not results["exit_scenarios"]["ipo"]["likelihood"]:
                results["exit_scenarios"]["ipo"]["likelihood"] = "high"
        elif acq_catalysts > acq_barriers and len(results["exit_scenarios"]["acquisition"]["acquirers"]) > 0:
            results["key_insights"].append(f"Acquisition likely with {len(results['exit_scenarios']['acquisition']['acquirers'])} potential acquirers identified")
            if not results["exit_scenarios"]["acquisition"]["likelihood"]:
                results["exit_scenarios"]["acquisition"]["likelihood"] = "high"
        
        # Highlight key barriers
        if results["strategic_context"]["legal_issues"]:
            results["key_insights"].append(f"Legal issues identified: {len(results['strategic_context']['legal_issues'])} potential concerns")
        
        if results["strategic_context"]["regulatory_barriers"]:
            results["key_insights"].append(f"Regulatory barriers may impact exit options")
        
        # Market dynamics
        if results["market_intelligence"].get("consolidation_trend") == "increasing":
            results["key_insights"].append("Market consolidation trend favors strategic acquisition")
        
        # Comparable multiples
        if results["comparable_exits"]:
            multiples = [c["implied_multiple"] for c in results["comparable_exits"] if "implied_multiple" in c]
            if multiples:
                avg_multiple = sum(multiples) / len(multiples)
                results["key_insights"].append(f"Average exit multiple for comparables: {avg_multiple:.1f}x")

def main():
    """Run intelligent market search"""
    
    # Get API keys
    tavily_key = os.getenv('TAVILY_API_KEY')
    claude_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
    
    if not tavily_key:
        print("ERROR: Missing TAVILY_API_KEY")
        return
    
    # Get inputs
    if len(sys.argv) > 2:
        company = sys.argv[1]
        sector = sys.argv[2]
        arr = float(sys.argv[3]) if len(sys.argv) > 3 else None
    else:
        company = input("Company name: ").strip() or "Deel"
        sector = input("Sector: ").strip() or "HR Tech"
        arr_input = input("Current ARR ($M, optional): ").strip()
        arr = float(arr_input) if arr_input else None
    
    # Run search
    searcher = IntelligentMarketSearch(tavily_key, claude_key)
    results = searcher.search_strategic_intelligence(company, sector, arr)
    
    # Display results
    print("\n" + "="*70)
    print(f"STRATEGIC INTELLIGENCE REPORT: {company}")
    print("="*70)
    
    print("\n🎯 KEY INSIGHTS")
    for insight in results["key_insights"]:
        print(f"  • {insight}")
    
    print("\n📊 EXIT SCENARIOS")
    
    print("\n  IPO Path:")
    print(f"    Likelihood: {results['exit_scenarios']['ipo']['likelihood'] or 'Unknown'}")
    if results["exit_scenarios"]["ipo"]["barriers"]:
        print(f"    Barriers ({len(results['exit_scenarios']['ipo']['barriers'])}):")
        for barrier in results["exit_scenarios"]["ipo"]["barriers"][:3]:
            print(f"      - {barrier[:100]}...")
    if results["exit_scenarios"]["ipo"]["catalysts"]:
        print(f"    Catalysts ({len(results['exit_scenarios']['ipo']['catalysts'])}):")
        for catalyst in results["exit_scenarios"]["ipo"]["catalysts"][:3]:
            print(f"      + {catalyst[:100]}...")
    
    print("\n  Acquisition Path:")
    print(f"    Likelihood: {results['exit_scenarios']['acquisition']['likelihood'] or 'Unknown'}")
    if results["exit_scenarios"]["acquisition"]["acquirers"]:
        print(f"    Potential Acquirers ({len(results['exit_scenarios']['acquisition']['acquirers'])}):")
        for acquirer in results["exit_scenarios"]["acquisition"]["acquirers"][:5]:
            print(f"      • {acquirer['name']}: {acquirer.get('rationale', '')[:80]}...")
    if results["exit_scenarios"]["acquisition"]["barriers"]:
        print(f"    Barriers ({len(results['exit_scenarios']['acquisition']['barriers'])}):")
        for barrier in results["exit_scenarios"]["acquisition"]["barriers"][:3]:
            print(f"      - {barrier[:100]}...")
    
    print("\n⚠️  STRATEGIC CONTEXT")
    if results["strategic_context"]["legal_issues"]:
        print(f"  Legal Issues ({len(results['strategic_context']['legal_issues'])}):")
        for issue in results["strategic_context"]["legal_issues"][:2]:
            print(f"    - {issue['description'][:120]}...")
    
    if results["strategic_context"]["regulatory_barriers"]:
        print(f"  Regulatory Barriers ({len(results['strategic_context']['regulatory_barriers'])}):")
        for barrier in results["strategic_context"]["regulatory_barriers"][:2]:
            print(f"    - {barrier[:120]}...")
    
    print("\n💰 COMPARABLE EXITS")
    for comp in results["comparable_exits"][:5]:
        print(f"  • {comp['company']}: ${comp['exit_value_millions']:,.0f}M ({comp['type']})", end="")
        if "implied_multiple" in comp:
            print(f" - {comp['implied_multiple']:.1f}x revenue")
        else:
            print()
    
    # Save results
    filename = f"strategic_intel_{company.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Full report saved to: {filename}")

if __name__ == "__main__":
    main()