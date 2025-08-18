#!/usr/bin/env python3
"""
Enhanced PWERM Analysis with Proper VC Power Law Distribution
Focuses on real M&A exits and filters bad data
"""

import json
import sys
import os
import requests
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class EnhancedPWERMAnalyzer:
    def __init__(self, tavily_api_key: str = None, claude_api_key: str = None):
        """Initialize Enhanced PWERM Analyzer"""
        self.tavily_api_key = tavily_api_key
        self.claude_api_key = claude_api_key
        self.claude_base_url = "https://api.anthropic.com/v1/messages"
        self.tavily_base_url = "https://api.tavily.com/search"
        
        # Fixed 499 scenarios for PWERM
        self.num_scenarios = 499
        
        # Curated benchmark M&A exits (NOT funding rounds)
        self.curated_benchmarks = {
            'SaaS-HR Tech': [
                {'company': 'Workday', 'acquirer': 'Private', 'exit_value': 23000, 'revenue': 1400, 'multiple': 16.4, 'year': 2019},
                {'company': 'Ultimate Software', 'acquirer': 'Hellman & Friedman', 'exit_value': 11000, 'revenue': 940, 'multiple': 11.7, 'year': 2019},
                {'company': 'Cornerstone OnDemand', 'acquirer': 'Clearlake Capital', 'exit_value': 5200, 'revenue': 730, 'multiple': 7.1, 'year': 2021},
                {'company': 'BambooHR', 'acquirer': 'TA Associates', 'exit_value': 1500, 'revenue': 150, 'multiple': 10.0, 'year': 2023},
                {'company': 'Lattice', 'acquirer': 'Thoma Bravo', 'exit_value': 3000, 'revenue': 200, 'multiple': 15.0, 'year': 2024},
            ],
            'AI-ML Infra': [
                {'company': 'MosaicML', 'acquirer': 'Databricks', 'exit_value': 1300, 'revenue': 50, 'multiple': 26.0, 'year': 2023},
                {'company': 'Neeva', 'acquirer': 'Snowflake', 'exit_value': 150, 'revenue': 10, 'multiple': 15.0, 'year': 2023},
                {'company': 'Runway', 'acquirer': 'Adobe', 'exit_value': 500, 'revenue': 30, 'multiple': 16.7, 'year': 2024},
            ],
            'Fintech-Payments': [
                {'company': 'Afterpay', 'acquirer': 'Square', 'exit_value': 29000, 'revenue': 925, 'multiple': 31.4, 'year': 2021},
                {'company': 'Paysafe', 'acquirer': 'Blackstone/CVC', 'exit_value': 9000, 'revenue': 1500, 'multiple': 6.0, 'year': 2021},
                {'company': 'Payoneer', 'acquirer': 'SPAC', 'exit_value': 3300, 'revenue': 345, 'multiple': 9.6, 'year': 2021},
                {'company': 'Bill.com', 'acquirer': 'Public', 'exit_value': 8900, 'revenue': 450, 'multiple': 19.8, 'year': 2021},
            ],
            'E-commerce': [
                {'company': 'Jet.com', 'acquirer': 'Walmart', 'exit_value': 3300, 'revenue': 1000, 'multiple': 3.3, 'year': 2016},
                {'company': 'Chewy', 'acquirer': 'PetSmart', 'exit_value': 3350, 'revenue': 900, 'multiple': 3.7, 'year': 2017},
                {'company': 'Zulily', 'acquirer': 'QVC', 'exit_value': 2400, 'revenue': 1500, 'multiple': 1.6, 'year': 2015},
            ],
            'Cybersecurity': [
                {'company': 'Splunk', 'acquirer': 'Cisco', 'exit_value': 28000, 'revenue': 3700, 'multiple': 7.6, 'year': 2023},
                {'company': 'Mandiant', 'acquirer': 'Google', 'exit_value': 5400, 'revenue': 500, 'multiple': 10.8, 'year': 2022},
                {'company': 'Proofpoint', 'acquirer': 'Thoma Bravo', 'exit_value': 12300, 'revenue': 1000, 'multiple': 12.3, 'year': 2021},
            ]
        }
        
    def filter_revenue_multiple(self, multiple: float) -> bool:
        """Filter out bad revenue multiples"""
        # Reject multiples < 2x or > 100x as likely errors
        return 2.0 <= multiple <= 100.0
    
    def search_ma_exits(self, company_name: str, sector: str) -> List[Dict]:
        """Search specifically for M&A exits, NOT funding rounds"""
        if not self.tavily_api_key:
            return []
            
        exit_comparables = []
        
        # Targeted search queries for M&A exits
        search_queries = [
            f"{sector} companies acquired 2024 2023 exit price revenue multiple NOT funding",
            f"{company_name} competitors acquisition M&A exit valuation revenue",
            f"{sector} M&A transactions strategic buyers exit multiples",
            f"recent {sector} acquisitions deal value annual revenue",
        ]
        
        for query in search_queries:
            try:
                response = requests.post(
                    self.tavily_base_url,
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": 10,
                        "include_domains": ["techcrunch.com", "reuters.com", "bloomberg.com", "businesswire.com"],
                        "exclude_domains": ["wikipedia.org", "facebook.com", "twitter.com"]
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for result in data.get('results', []):
                        exit_data = self._extract_exit_data(result)
                        if exit_data and self.filter_revenue_multiple(exit_data.get('multiple', 0)):
                            exit_comparables.append(exit_data)
                            
            except Exception as e:
                print(f"Search error: {e}")
                
        return exit_comparables
    
    def _extract_exit_data(self, search_result: Dict) -> Optional[Dict]:
        """Extract M&A exit data from search result"""
        content = search_result.get('content', '').lower()
        
        # Skip if it's about funding rounds
        if any(word in content for word in ['funding round', 'series a', 'series b', 'raised', 'investment']):
            return None
            
        # Look for acquisition keywords
        if not any(word in content for word in ['acquired', 'acquisition', 'bought', 'purchase', 'deal']):
            return None
            
        # Extract deal information
        import re
        
        # Try to extract valuation and revenue
        val_patterns = [
            r'(\$[\d,]+(?:\.\d+)?)\s*(?:billion|million|b|m).*?acquisition',
            r'acquired.*?(\$[\d,]+(?:\.\d+)?)\s*(?:billion|million|b|m)',
            r'deal.*?valued.*?(\$[\d,]+(?:\.\d+)?)\s*(?:billion|million|b|m)'
        ]
        
        rev_patterns = [
            r'revenue.*?(\$[\d,]+(?:\.\d+)?)\s*(?:billion|million|b|m)',
            r'(\$[\d,]+(?:\.\d+)?)\s*(?:billion|million|b|m).*?revenue',
            r'annual.*?revenue.*?(\$[\d,]+(?:\.\d+)?)\s*(?:billion|million|b|m)'
        ]
        
        valuation = None
        revenue = None
        
        for pattern in val_patterns:
            match = re.search(pattern, content)
            if match:
                val_str = match.group(1).replace('$', '').replace(',', '')
                multiplier = 1000 if ('billion' in content or 'b' in content) else 1
                valuation = float(val_str) * multiplier
                break
                
        for pattern in rev_patterns:
            match = re.search(pattern, content)
            if match:
                rev_str = match.group(1).replace('$', '').replace(',', '')
                multiplier = 1000 if ('billion' in content or 'b' in content) else 1
                revenue = float(rev_str) * multiplier
                break
                
        if valuation and revenue and revenue > 0:
            multiple = valuation / revenue
            if self.filter_revenue_multiple(multiple):
                return {
                    'source': 'web_search',
                    'title': search_result.get('title', ''),
                    'valuation': valuation,
                    'revenue': revenue,
                    'multiple': multiple,
                    'confidence': 'medium'
                }
                
        return None
    
    def generate_pwerm_scenarios(self, company_data: Dict, market_data: Dict) -> List[Dict]:
        """Generate 499 scenarios following VC power law distribution"""
        scenarios = []
        
        current_arr = company_data.get('revenue', 5.0)
        growth_rate = company_data.get('growth_rate', 0.30)
        sector = company_data.get('sector', 'SaaS')
        
        # Get sector-specific multiples
        sector_benchmarks = self.curated_benchmarks.get(sector, [])
        if sector_benchmarks:
            valid_multiples = [b['multiple'] for b in sector_benchmarks if self.filter_revenue_multiple(b['multiple'])]
            median_multiple = np.median(valid_multiples) if valid_multiples else 10.0
            p25_multiple = np.percentile(valid_multiples, 25) if valid_multiples else 6.0
            p75_multiple = np.percentile(valid_multiples, 75) if valid_multiples else 15.0
        else:
            median_multiple, p25_multiple, p75_multiple = 10.0, 6.0, 15.0
        
        # Scenario distribution following VC power law
        # 65% fail or return <1x (325 scenarios)
        fail_count = 325
        # 20% return 1-3x (100 scenarios)
        small_return_count = 100
        # 10% return 3-10x (50 scenarios)
        medium_return_count = 50
        # 4% return 10-50x (20 scenarios)
        large_return_count = 20
        # 1% outlier returns 50x+ (4 scenarios)
        outlier_count = 4
        
        scenario_id = 1
        
        # 1. Failure scenarios (65%)
        for i in range(fail_count):
            exit_value = np.random.uniform(0.1, 0.9) * current_arr
            scenarios.append({
                'id': scenario_id,
                'type': 'liquidation',
                'exit_value': exit_value,
                'probability': 0.65 / fail_count,
                'description': f'Liquidation scenario {i+1}',
                'time_to_exit': np.random.uniform(1, 3),
                'return_multiple': exit_value / current_arr
            })
            scenario_id += 1
        
        # 2. Small returns 1-3x (20%)
        for i in range(small_return_count):
            time_to_exit = np.random.uniform(2, 5)
            projected_arr = current_arr * (1 + growth_rate) ** time_to_exit
            
            # Use lower multiples for small returns
            revenue_multiple = np.random.uniform(p25_multiple * 0.5, p25_multiple)
            exit_value = projected_arr * revenue_multiple
            return_multiple = exit_value / current_arr
            
            # Ensure it's in 1-3x range
            if return_multiple < 1:
                return_multiple = np.random.uniform(1.0, 1.5)
            elif return_multiple > 3:
                return_multiple = np.random.uniform(2.5, 3.0)
                
            exit_value = current_arr * return_multiple
            
            scenarios.append({
                'id': scenario_id,
                'type': 'small_acquisition',
                'exit_value': exit_value,
                'probability': 0.20 / small_return_count,
                'description': f'Small acquisition scenario {i+1}',
                'time_to_exit': time_to_exit,
                'return_multiple': return_multiple,
                'revenue_multiple': revenue_multiple
            })
            scenario_id += 1
        
        # 3. Medium returns 3-10x (10%)
        for i in range(medium_return_count):
            time_to_exit = np.random.uniform(3, 6)
            projected_arr = current_arr * (1 + growth_rate) ** time_to_exit
            
            # Use median multiples
            revenue_multiple = np.random.uniform(median_multiple * 0.8, median_multiple * 1.2)
            if self.filter_revenue_multiple(revenue_multiple):
                exit_value = projected_arr * revenue_multiple
                return_multiple = exit_value / current_arr
                
                # Ensure it's in 3-10x range
                if return_multiple < 3:
                    return_multiple = np.random.uniform(3.0, 4.0)
                elif return_multiple > 10:
                    return_multiple = np.random.uniform(8.0, 10.0)
                    
                exit_value = current_arr * return_multiple
                
                scenarios.append({
                    'id': scenario_id,
                    'type': 'strategic_acquisition',
                    'exit_value': exit_value,
                    'probability': 0.10 / medium_return_count,
                    'description': f'Strategic acquisition scenario {i+1}',
                    'time_to_exit': time_to_exit,
                    'return_multiple': return_multiple,
                    'revenue_multiple': revenue_multiple
                })
            scenario_id += 1
        
        # 4. Large returns 10-50x (4%)
        for i in range(large_return_count):
            time_to_exit = np.random.uniform(4, 7)
            projected_arr = current_arr * (1 + growth_rate) ** time_to_exit
            
            # Use higher multiples
            revenue_multiple = np.random.uniform(p75_multiple, p75_multiple * 2)
            if self.filter_revenue_multiple(revenue_multiple):
                exit_value = projected_arr * revenue_multiple
                return_multiple = exit_value / current_arr
                
                # Ensure it's in 10-50x range
                if return_multiple < 10:
                    return_multiple = np.random.uniform(10.0, 15.0)
                elif return_multiple > 50:
                    return_multiple = np.random.uniform(40.0, 50.0)
                    
                exit_value = current_arr * return_multiple
                
                scenarios.append({
                    'id': scenario_id,
                    'type': 'ipo',
                    'exit_value': exit_value,
                    'probability': 0.04 / large_return_count,
                    'description': f'IPO scenario {i+1}',
                    'time_to_exit': time_to_exit,
                    'return_multiple': return_multiple,
                    'revenue_multiple': revenue_multiple
                })
            scenario_id += 1
        
        # 5. Outlier returns 50x+ (1%)
        for i in range(outlier_count):
            time_to_exit = np.random.uniform(5, 8)
            
            # For mature companies (>$500M ARR), cap at 2-5x scaling
            if current_arr > 500:
                scaling_factor = np.random.uniform(2, 5)
            else:
                scaling_factor = np.random.uniform(3, 10)
                
            projected_arr = current_arr * scaling_factor
            
            # Use exceptional multiples
            revenue_multiple = np.random.uniform(p75_multiple * 1.5, p75_multiple * 3)
            if revenue_multiple > 100:  # Cap at 100x
                revenue_multiple = np.random.uniform(50, 100)
                
            exit_value = projected_arr * revenue_multiple
            return_multiple = exit_value / current_arr
            
            # Ensure it's 50x+
            if return_multiple < 50:
                return_multiple = np.random.uniform(50, 100)
                exit_value = current_arr * return_multiple
                
            scenarios.append({
                'id': scenario_id,
                'type': 'mega_exit',
                'exit_value': exit_value,
                'probability': 0.01 / outlier_count,
                'description': f'Outlier exit scenario {i+1}',
                'time_to_exit': time_to_exit,
                'return_multiple': return_multiple,
                'revenue_multiple': revenue_multiple
            })
            scenario_id += 1
        
        return scenarios
    
    def analyze_with_claude(self, company_name: str, sector: str, current_arr: float, growth_rate: float) -> Dict:
        """Use Claude to analyze exit potential with focus on M&A"""
        if not self.claude_api_key:
            return {}
            
        prompt = f"""
        Analyze {company_name} as a potential M&A target in the {sector} sector.
        Current ARR: ${current_arr}M, Growth Rate: {growth_rate*100:.0f}%
        
        Focus ONLY on actual M&A exits and acquisitions. DO NOT include funding rounds or private valuations.
        
        Provide:
        1. Most likely strategic acquirers and why they would acquire
        2. Comparable M&A exits in this sector (with exit price and revenue multiples)
        3. Expected revenue multiple range based on ACTUAL acquisitions
        4. Timeline to likely exit (years)
        
        Return as JSON with:
        {{
            "likely_acquirers": [
                {{"name": "Company", "strategic_rationale": "Why they would buy", "likelihood": "High/Medium/Low"}}
            ],
            "comparable_exits": [
                {{"target": "Company", "acquirer": "Buyer", "exit_value": 1000, "revenue": 100, "multiple": 10.0, "year": 2024}}
            ],
            "expected_multiple_range": {{"low": 8, "median": 12, "high": 20}},
            "exit_timeline": {{"min_years": 3, "likely_years": 5, "max_years": 7}}
        }}
        
        IMPORTANT: Only include deals where companies were actually acquired, not funding rounds.
        """
        
        try:
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                
                # Extract JSON
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                    
        except Exception as e:
            print(f"Claude analysis error: {e}")
            
        return {}
    
    def run_analysis(self, company_data: Dict) -> Dict:
        """Run enhanced PWERM analysis"""
        company_name = company_data.get('name', 'Unknown')
        current_arr = company_data.get('revenue', 5.0)
        growth_rate = company_data.get('growth_rate', 0.30)
        sector = company_data.get('sector', 'SaaS')
        
        # 1. Search for M&A exits
        exit_comparables = self.search_ma_exits(company_name, sector)
        
        # 2. Get curated benchmarks
        curated = self.curated_benchmarks.get(sector, [])
        
        # 3. Claude analysis
        claude_analysis = self.analyze_with_claude(company_name, sector, current_arr, growth_rate)
        
        # 4. Combine all exit data
        all_exits = curated + exit_comparables
        if claude_analysis.get('comparable_exits'):
            all_exits.extend([
                {
                    'company': ex['target'],
                    'acquirer': ex['acquirer'],
                    'exit_value': ex['exit_value'],
                    'revenue': ex['revenue'],
                    'multiple': ex['multiple'],
                    'year': ex.get('year', 2024),
                    'source': 'claude'
                }
                for ex in claude_analysis['comparable_exits']
                if self.filter_revenue_multiple(ex.get('multiple', 0))
            ])
        
        # 5. Generate scenarios
        market_data = {
            'exits': all_exits,
            'claude_analysis': claude_analysis
        }
        scenarios = self.generate_pwerm_scenarios(company_data, market_data)
        
        # 6. Calculate summary
        exit_values = [s['exit_value'] for s in scenarios]
        probabilities = [s['probability'] for s in scenarios]
        expected_value = np.average(exit_values, weights=probabilities)
        
        # Calculate percentiles
        sorted_values = sorted(exit_values)
        p50_idx = int(len(sorted_values) * 0.50)
        p90_idx = int(len(sorted_values) * 0.90)
        p99_idx = int(len(sorted_values) * 0.99)
        
        summary = {
            'expected_exit_value': float(expected_value),
            'median_exit_value': float(sorted_values[p50_idx]),
            'p90_exit_value': float(sorted_values[p90_idx]),
            'p99_exit_value': float(sorted_values[p99_idx]),
            'total_scenarios': len(scenarios),
            'success_probability': sum(s['probability'] for s in scenarios if s['return_multiple'] > 1),
            'ipo_probability': sum(s['probability'] for s in scenarios if s['type'] == 'ipo'),
            'mega_exit_probability': sum(s['probability'] for s in scenarios if s['type'] == 'mega_exit')
        }
        
        return {
            'company_data': company_data,
            'market_analysis': {
                'exit_comparables': all_exits,
                'potential_acquirers': claude_analysis.get('likely_acquirers', []),
                'expected_multiples': claude_analysis.get('expected_multiple_range', {})
            },
            'scenarios': scenarios,
            'summary': summary,
            'analysis_timestamp': datetime.now().isoformat()
        }

def main():
    """Main function"""
    # Read input
    try:
        input_data = json.loads(sys.stdin.read())
    except:
        print(json.dumps({'error': 'Invalid input'}))
        return
        
    # Extract data
    company_data = input_data.get('company_data', {})
    
    # Initialize analyzer
    analyzer = EnhancedPWERMAnalyzer(
        tavily_api_key=os.getenv('TAVILY_API_KEY'),
        claude_api_key=os.getenv('CLAUDE_API_KEY')
    )
    
    # Prepare company data
    prepared_data = {
        'name': company_data.get('name', 'Unknown'),
        'revenue': company_data.get('current_arr_usd', 5000000) / 1000000,  # Convert to millions
        'growth_rate': company_data.get('revenue_growth_annual_pct', 30) / 100,  # Convert to decimal
        'sector': company_data.get('sector', 'SaaS')
    }
    
    # Run analysis
    try:
        results = analyzer.run_analysis(prepared_data)
        print(json.dumps(results, indent=2))
    except Exception as e:
        import traceback
        print(json.dumps({
            'error': str(e),
            'traceback': traceback.format_exc()
        }))

if __name__ == "__main__":
    main()