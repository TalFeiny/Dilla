#!/usr/bin/env python3
"""Strategic acquirer analysis using public SaaS data for PWERM scenarios"""

import json
from typing import Dict, List, Tuple
from public_saas_scraper import PublicSaaSScraper

class StrategicAcquirerAnalyzer:
    def __init__(self):
        self.scraper = PublicSaaSScraper()
        
    def analyze_strategic_acquirers(self, target_company: str, sector: str, 
                                  target_revenue: float, target_growth: float) -> Dict:
        """Analyze potential strategic acquirers using public company data"""
        
        # Get public company data
        public_data = self.scraper.fetch_public_saas_data()
        companies = public_data['companies']
        
        # Identify potential acquirers
        potential_acquirers = []
        
        for company in companies:
            acquirer_score = self._calculate_acquirer_score(
                company, target_company, sector, target_revenue, target_growth
            )
            
            if acquirer_score['total_score'] > 0:
                potential_acquirers.append({
                    'acquirer': company,
                    'scores': acquirer_score,
                    'acquisition_capacity': self._calculate_acquisition_capacity(company, target_revenue),
                    'strategic_rationale': self._generate_strategic_rationale(
                        company, target_company, sector, acquirer_score
                    )
                })
        
        # Sort by total score
        potential_acquirers.sort(key=lambda x: x['scores']['total_score'], reverse=True)
        
        # Generate acquisition scenarios
        scenarios = self._generate_acquisition_scenarios(
            potential_acquirers[:5], target_revenue, target_growth
        )
        
        return {
            'potential_acquirers': potential_acquirers[:10],
            'acquisition_scenarios': scenarios,
            'market_insights': self._generate_market_insights(potential_acquirers, sector)
        }
    
    def _calculate_acquirer_score(self, acquirer: Dict, target: str, 
                                sector: str, target_revenue: float, target_growth: float) -> Dict:
        """Score potential acquirer based on multiple factors"""
        
        scores = {
            'sector_fit': 0,
            'size_fit': 0,
            'growth_synergy': 0,
            'financial_capacity': 0,
            'strategic_need': 0
        }
        
        # 1. Sector Fit Score (0-25)
        if sector == "HR Tech" and acquirer['category'] in ['HR Tech', 'Enterprise']:
            scores['sector_fit'] = 25
        elif sector == "Fintech" and acquirer['category'] in ['FinTech', 'Payments']:
            scores['sector_fit'] = 25
        elif acquirer['category'] in ['Enterprise', 'CRM']:  # General enterprise buyers
            scores['sector_fit'] = 15
        else:
            scores['sector_fit'] = 5
        
        # 2. Size Fit Score (0-25) - Can they digest this acquisition?
        acquirer_revenue = acquirer['revenue_b'] * 1000  # Convert to millions
        size_ratio = target_revenue / acquirer_revenue
        
        if 0.05 <= size_ratio <= 0.3:  # Sweet spot: 5-30% of acquirer revenue
            scores['size_fit'] = 25
        elif 0.01 <= size_ratio <= 0.5:
            scores['size_fit'] = 15
        elif size_ratio < 0.01:  # Too small to matter
            scores['size_fit'] = 5
        else:  # Too big to swallow
            scores['size_fit'] = 0
        
        # 3. Growth Synergy Score (0-25)
        growth_diff = abs(acquirer['revenue_growth'] - target_growth)
        if target_growth > acquirer['revenue_growth'] + 10:  # Target much faster growing
            scores['growth_synergy'] = 25  # Acquirer needs growth
        elif growth_diff <= 20:
            scores['growth_synergy'] = 15
        else:
            scores['growth_synergy'] = 5
        
        # 4. Financial Capacity Score (0-25)
        if acquirer['market_cap_b'] > 50:  # Large cap with capacity
            scores['financial_capacity'] = 25
        elif acquirer['market_cap_b'] > 20:
            scores['financial_capacity'] = 20
        elif acquirer['market_cap_b'] > 10:
            scores['financial_capacity'] = 15
        else:
            scores['financial_capacity'] = 10
        
        # 5. Strategic Need Score - Specific patterns
        scores['strategic_need'] = self._assess_strategic_need(acquirer, target, sector)
        
        scores['total_score'] = sum(scores.values())
        return scores
    
    def _assess_strategic_need(self, acquirer: Dict, target: str, sector: str) -> int:
        """Assess specific strategic needs"""
        
        # Known strategic gaps and initiatives
        strategic_patterns = {
            'Workday': {
                'HR Tech': 25,  # Core business expansion
                'Fintech': 15,  # Payroll adjacency
            },
            'Salesforce': {
                'CRM': 20,
                'AI': 25,  # AI everywhere strategy
                'HR Tech': 15,  # HCM expansion
            },
            'Microsoft': {
                'AI': 25,
                'Security': 20,
                'HR Tech': 15,  # LinkedIn synergy
            },
            'ServiceNow': {
                'Enterprise': 20,
                'HR Tech': 20,  # HR Service Delivery
            },
            'Bill.com': {
                'Fintech': 25,  # Core expansion
                'Payments': 20,
            }
        }
        
        company_name = acquirer['company']
        if company_name in strategic_patterns:
            return strategic_patterns[company_name].get(sector, 10)
        
        return 10  # Default strategic interest
    
    def _calculate_acquisition_capacity(self, acquirer: Dict, target_revenue: float) -> Dict:
        """Calculate acquisition capacity and likely deal structure"""
        
        market_cap = acquirer['market_cap_b'] * 1000  # Convert to millions
        acquirer_revenue = acquirer['revenue_b'] * 1000
        
        # Typical acquisition capacity is 10-30% of market cap
        max_deal_size = market_cap * 0.3
        comfortable_deal_size = market_cap * 0.15
        
        # Calculate likely valuation multiple for target
        # Acquirers typically pay 1.5-2x their own multiple for growth
        acquirer_multiple = acquirer['ev_revenue']
        
        # Premium calculation based on growth differential
        growth_premium = max(1.0, 1 + (100 - acquirer['revenue_growth']) / 100)
        likely_multiple = acquirer_multiple * growth_premium
        
        # Deal feasibility
        likely_deal_value = target_revenue * likely_multiple
        
        return {
            'max_capacity': max_deal_size,
            'comfortable_capacity': comfortable_deal_size,
            'likely_multiple_paid': likely_multiple,
            'likely_deal_value': likely_deal_value,
            'feasibility': 'High' if likely_deal_value < comfortable_deal_size else 
                          'Medium' if likely_deal_value < max_deal_size else 'Low',
            'deal_structure': self._suggest_deal_structure(likely_deal_value, max_deal_size)
        }
    
    def _suggest_deal_structure(self, deal_value: float, max_capacity: float) -> str:
        """Suggest likely deal structure"""
        
        if deal_value < max_capacity * 0.5:
            return "All cash"
        elif deal_value < max_capacity:
            return "70% cash, 30% stock"
        else:
            return "50% cash, 50% stock with earnout"
    
    def _generate_strategic_rationale(self, acquirer: Dict, target: str, 
                                    sector: str, scores: Dict) -> List[str]:
        """Generate strategic rationale for acquisition"""
        
        rationales = []
        
        # Growth rationale
        if scores['growth_synergy'] >= 20:
            rationales.append(f"Accelerate growth (target growing faster than acquirer's {acquirer['revenue_growth']}%)")
        
        # Sector expansion
        if scores['sector_fit'] >= 20:
            rationales.append(f"Strengthen position in {sector}")
        elif scores['sector_fit'] >= 10:
            rationales.append(f"Expand into adjacent {sector} market")
        
        # Size and scale
        if scores['size_fit'] >= 20:
            rationales.append("Ideal size for integration without disruption")
        
        # Specific strategic initiatives
        company = acquirer['company']
        if company == "Workday" and sector == "HR Tech":
            rationales.append("Expand global payroll and compliance capabilities")
        elif company == "Microsoft" and "AI" in sector:
            rationales.append("Enhance AI capabilities across product suite")
        elif company == "Salesforce":
            rationales.append("Add to Customer 360 platform")
        
        # Financial rationale
        if acquirer['rule_of_40'] < 80:
            rationales.append("Improve Rule of 40 metrics")
        
        return rationales
    
    def _generate_acquisition_scenarios(self, top_acquirers: List[Dict], 
                                      target_revenue: float, target_growth: float) -> List[Dict]:
        """Generate specific acquisition scenarios"""
        
        scenarios = []
        
        for i, acquirer_data in enumerate(top_acquirers):
            acquirer = acquirer_data['acquirer']
            capacity = acquirer_data['acquisition_capacity']
            
            # Base scenario
            base_scenario = {
                'scenario_id': f'acq_{i+1}_base',
                'type': 'acquisition',
                'acquirer': acquirer['company'],
                'probability': self._calculate_probability(acquirer_data),
                'valuation_multiple': capacity['likely_multiple_paid'],
                'deal_value': capacity['likely_deal_value'],
                'structure': capacity['deal_structure'],
                'timing': '18-24 months',
                'rationale': acquirer_data['strategic_rationale'][:2]
            }
            scenarios.append(base_scenario)
            
            # Premium scenario (bidding war or strategic imperative)
            if capacity['feasibility'] in ['High', 'Medium']:
                premium_scenario = {
                    'scenario_id': f'acq_{i+1}_premium',
                    'type': 'acquisition_premium',
                    'acquirer': acquirer['company'],
                    'probability': base_scenario['probability'] * 0.3,
                    'valuation_multiple': capacity['likely_multiple_paid'] * 1.3,
                    'deal_value': capacity['likely_deal_value'] * 1.3,
                    'structure': '60% cash, 40% stock',
                    'timing': '12-18 months',
                    'rationale': ['Competitive bidding situation', 'Strategic imperative']
                }
                scenarios.append(premium_scenario)
        
        return scenarios
    
    def _calculate_probability(self, acquirer_data: Dict) -> float:
        """Calculate acquisition probability based on scores"""
        
        total_score = acquirer_data['scores']['total_score']
        feasibility = acquirer_data['acquisition_capacity']['feasibility']
        
        # Base probability from score (max 125 points)
        base_prob = min(total_score / 125 * 0.4, 0.4)  # Max 40% from scores
        
        # Adjust for feasibility
        feasibility_multiplier = {
            'High': 1.2,
            'Medium': 1.0,
            'Low': 0.5
        }
        
        return min(base_prob * feasibility_multiplier.get(feasibility, 1.0), 0.45)
    
    def _generate_market_insights(self, acquirers: List[Dict], sector: str) -> Dict:
        """Generate market insights from acquirer analysis"""
        
        insights = {
            'most_likely_acquirers': [],
            'market_dynamics': [],
            'valuation_guidance': {}
        }
        
        # Top acquirers
        for acq in acquirers[:3]:
            insights['most_likely_acquirers'].append({
                'company': acq['acquirer']['company'],
                'score': acq['scores']['total_score'],
                'capacity': acq['acquisition_capacity']['feasibility']
            })
        
        # Market dynamics
        high_capacity_count = sum(1 for a in acquirers if a['acquisition_capacity']['feasibility'] == 'High')
        if high_capacity_count >= 3:
            insights['market_dynamics'].append("Multiple strategic acquirers with capacity - competitive dynamics likely")
        
        # Valuation guidance
        likely_multiples = [a['acquisition_capacity']['likely_multiple_paid'] for a in acquirers[:5]]
        insights['valuation_guidance'] = {
            'min_multiple': min(likely_multiples),
            'avg_multiple': sum(likely_multiples) / len(likely_multiples),
            'max_multiple': max(likely_multiples)
        }
        
        return insights

def integrate_with_pwerm(company_name: str, sector: str, revenue: float, growth: float) -> Dict:
    """Integration function for PWERM analysis"""
    
    analyzer = StrategicAcquirerAnalyzer()
    
    # Get strategic acquirer analysis
    analysis = analyzer.analyze_strategic_acquirers(company_name, sector, revenue, growth)
    
    # Format for PWERM
    return {
        'strategic_acquirers': analysis['potential_acquirers'],
        'acquisition_scenarios': analysis['acquisition_scenarios'],
        'market_insights': analysis['market_insights'],
        'summary': f"Identified {len(analysis['potential_acquirers'])} potential acquirers, " +
                   f"with {analysis['market_insights']['most_likely_acquirers'][0]['company']} as top candidate"
    }

# Test the analyzer
if __name__ == "__main__":
    # Test with Deel
    print("STRATEGIC ACQUIRER ANALYSIS: Deel")
    print("="*60)
    
    results = integrate_with_pwerm("Deel", "HR Tech", 500, 100)
    
    print(f"\n🎯 TOP STRATEGIC ACQUIRERS:")
    for i, acq in enumerate(results['strategic_acquirers'][:5]):
        print(f"\n{i+1}. {acq['acquirer']['company']} (Score: {acq['scores']['total_score']}/125)")
        print(f"   Market Cap: ${acq['acquirer']['market_cap_b']:.1f}B")
        print(f"   Capacity: {acq['acquisition_capacity']['feasibility']}")
        print(f"   Likely Multiple: {acq['acquisition_capacity']['likely_multiple_paid']:.1f}x")
        print(f"   Deal Value: ${acq['acquisition_capacity']['likely_deal_value']:,.0f}M")
        print(f"   Rationale: {', '.join(acq['strategic_rationale'][:2])}")
    
    print(f"\n📊 ACQUISITION SCENARIOS:")
    for scenario in results['acquisition_scenarios'][:5]:
        print(f"\n{scenario['scenario_id']}:")
        print(f"  Acquirer: {scenario['acquirer']}")
        print(f"  Probability: {scenario['probability']:.1%}")
        print(f"  Valuation: ${scenario['deal_value']:,.0f}M ({scenario['valuation_multiple']:.1f}x)")
        print(f"  Structure: {scenario['structure']}")
    
    print(f"\n💡 MARKET INSIGHTS:")
    insights = results['market_insights']
    print(f"  Most Likely: {insights['most_likely_acquirers'][0]['company']}")
    print(f"  Valuation Range: {insights['valuation_guidance']['min_multiple']:.1f}x - {insights['valuation_guidance']['max_multiple']:.1f}x")
    print(f"  Average Multiple: {insights['valuation_guidance']['avg_multiple']:.1f}x")