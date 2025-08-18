#!/usr/bin/env python3
"""Enhanced Public SaaS Acquirer Analysis for PWERM"""

import requests
import json
import re
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime

class EnhancedPublicSaaSAcquirers:
    def __init__(self, tavily_api_key: str = None):
        self.tavily_api_key = tavily_api_key
        self.base_url = "https://publicsaascompanies.com"
        
        # Strategic acquirer profiles with acquisition history
        self.strategic_acquirers = {
            "Salesforce": {
                "ticker": "CRM",
                "market_cap_b": 275.0,
                "acquisition_budget": "High",
                "recent_acquisitions": [
                    {"target": "Slack", "price": 27700, "year": 2021, "multiple": 26.2},
                    {"target": "Tableau", "price": 15700, "year": 2019, "multiple": 10.7},
                    {"target": "MuleSoft", "price": 6500, "year": 2018, "multiple": 15.9},
                    {"target": "Demandware", "price": 2800, "year": 2016, "multiple": 8.4}
                ],
                "acquisition_thesis": "Platform expansion, AI/automation, industry clouds",
                "sweet_spot_revenue": "50M-500M ARR",
                "preferred_sectors": ["CRM", "AI", "Analytics", "Integration", "Industry Vertical"]
            },
            "Microsoft": {
                "ticker": "MSFT",
                "market_cap_b": 2900.0,
                "acquisition_budget": "Very High",
                "recent_acquisitions": [
                    {"target": "Activision Blizzard", "price": 68700, "year": 2023, "multiple": 8.9},
                    {"target": "Nuance", "price": 19700, "year": 2021, "multiple": 12.9},
                    {"target": "LinkedIn", "price": 26200, "year": 2016, "multiple": 8.2},
                    {"target": "GitHub", "price": 7500, "year": 2018, "multiple": 25.0}
                ],
                "acquisition_thesis": "Cloud infrastructure, AI, security, developer tools",
                "sweet_spot_revenue": "100M-1B ARR",
                "preferred_sectors": ["AI", "Security", "DevTools", "Cloud", "Productivity"]
            },
            "Adobe": {
                "ticker": "ADBE",
                "market_cap_b": 220.0,
                "acquisition_budget": "High",
                "recent_acquisitions": [
                    {"target": "Figma", "price": 20000, "year": 2022, "multiple": 50.0},
                    {"target": "Workfront", "price": 1500, "year": 2020, "multiple": 10.0},
                    {"target": "Marketo", "price": 4750, "year": 2018, "multiple": 8.8},
                    {"target": "Magento", "price": 1680, "year": 2018, "multiple": 4.2}
                ],
                "acquisition_thesis": "Creative tools, marketing automation, e-commerce",
                "sweet_spot_revenue": "100M-500M ARR",
                "preferred_sectors": ["Design", "Marketing", "E-commerce", "Content", "Creative"]
            },
            "Oracle": {
                "ticker": "ORCL",
                "market_cap_b": 340.0,
                "acquisition_budget": "High",
                "recent_acquisitions": [
                    {"target": "Cerner", "price": 28300, "year": 2022, "multiple": 5.8},
                    {"target": "NetSuite", "price": 9300, "year": 2016, "multiple": 9.5},
                    {"target": "Responsys", "price": 1500, "year": 2013, "multiple": 6.4}
                ],
                "acquisition_thesis": "Industry clouds, healthcare, ERP expansion",
                "sweet_spot_revenue": "200M-1B ARR",
                "preferred_sectors": ["Healthcare", "ERP", "Industry Vertical", "Database"]
            },
            "Google": {
                "ticker": "GOOGL",
                "market_cap_b": 1700.0,
                "acquisition_budget": "Very High",
                "recent_acquisitions": [
                    {"target": "Mandiant", "price": 5400, "year": 2022, "multiple": 13.5},
                    {"target": "Fitbit", "price": 2100, "year": 2021, "multiple": 4.2},
                    {"target": "Looker", "price": 2600, "year": 2019, "multiple": 13.0}
                ],
                "acquisition_thesis": "Cloud, security, AI/ML, data analytics",
                "sweet_spot_revenue": "100M-500M ARR",
                "preferred_sectors": ["AI", "Security", "Cloud", "Analytics", "Developer Tools"]
            },
            "SAP": {
                "ticker": "SAP",
                "market_cap_b": 200.0,
                "acquisition_budget": "Medium",
                "recent_acquisitions": [
                    {"target": "Qualtrics", "price": 8000, "year": 2019, "multiple": 20.0},
                    {"target": "Callidus Cloud", "price": 2400, "year": 2018, "multiple": 6.0},
                    {"target": "Concur", "price": 8300, "year": 2014, "multiple": 12.4}
                ],
                "acquisition_thesis": "Experience management, spend management, vertical solutions",
                "sweet_spot_revenue": "100M-500M ARR",
                "preferred_sectors": ["ERP", "Experience", "Spend Management", "Analytics"]
            },
            "ServiceNow": {
                "ticker": "NOW",
                "market_cap_b": 188.0,
                "acquisition_budget": "Medium",
                "recent_acquisitions": [
                    {"target": "Element AI", "price": 500, "year": 2021, "multiple": None},
                    {"target": "Lightstep", "price": 300, "year": 2021, "multiple": None},
                    {"target": "Mapwize", "price": None, "year": 2022, "multiple": None}
                ],
                "acquisition_thesis": "AI/ML capabilities, observability, workflow automation",
                "sweet_spot_revenue": "20M-200M ARR",
                "preferred_sectors": ["AI", "Observability", "Automation", "ITSM"]
            },
            "Workday": {
                "ticker": "WDAY",
                "market_cap_b": 71.2,
                "acquisition_budget": "Medium",
                "recent_acquisitions": [
                    {"target": "Adaptive Insights", "price": 1550, "year": 2018, "multiple": 15.5},
                    {"target": "Scout RFP", "price": 540, "year": 2019, "multiple": None},
                    {"target": "VNDLY", "price": 510, "year": 2021, "multiple": None}
                ],
                "acquisition_thesis": "Planning, spend management, workforce management",
                "sweet_spot_revenue": "50M-300M ARR",
                "preferred_sectors": ["HR Tech", "Planning", "Spend Management", "Analytics"]
            },
            "Atlassian": {
                "ticker": "TEAM",
                "market_cap_b": 46.0,
                "acquisition_budget": "Medium",
                "recent_acquisitions": [
                    {"target": "Loom", "price": 975, "year": 2023, "multiple": 48.8},
                    {"target": "OpsGenie", "price": 295, "year": 2018, "multiple": None},
                    {"target": "Trello", "price": 425, "year": 2017, "multiple": 21.3}
                ],
                "acquisition_thesis": "Collaboration, DevOps, video communication",
                "sweet_spot_revenue": "20M-200M ARR",
                "preferred_sectors": ["Collaboration", "DevOps", "Project Management", "Communication"]
            },
            "Intuit": {
                "ticker": "INTU",
                "market_cap_b": 175.0,
                "acquisition_budget": "High",
                "recent_acquisitions": [
                    {"target": "Mailchimp", "price": 12000, "year": 2021, "multiple": 15.0},
                    {"target": "Credit Karma", "price": 7100, "year": 2020, "multiple": 11.8},
                    {"target": "Mint", "price": 170, "year": 2009, "multiple": None}
                ],
                "acquisition_thesis": "SMB tools, fintech, marketing automation",
                "sweet_spot_revenue": "100M-1B ARR",
                "preferred_sectors": ["SMB", "Fintech", "Marketing", "Accounting", "Tax"]
            }
        }
        
        # PE firms active in SaaS
        self.pe_acquirers = {
            "Thoma Bravo": {
                "type": "PE",
                "fund_size_b": 140.0,
                "recent_deals": ["Anaplan", "Ping Identity", "SailPoint", "Proofpoint"],
                "sweet_spot": "500M-10B valuation",
                "thesis": "Operational improvements, consolidation plays"
            },
            "Vista Equity": {
                "type": "PE",
                "fund_size_b": 100.0,
                "recent_deals": ["Citrix", "KnowBe4", "Pluralsight", "Marketo"],
                "sweet_spot": "500M-15B valuation",
                "thesis": "Best practices implementation, margin expansion"
            },
            "Francisco Partners": {
                "type": "PE",
                "fund_size_b": 30.0,
                "recent_deals": ["LogMeIn", "Zscaler", "ClickSoftware"],
                "sweet_spot": "200M-5B valuation",
                "thesis": "Tech-focused operational improvements"
            }
        }
    
    def analyze_acquirer_fit(self, company_data: Dict, market_landscape: Dict) -> Dict:
        """Analyze which acquirers would be the best fit for a company"""
        
        company_name = company_data.get('name', '')
        sector = company_data.get('sector', '')
        subsector = company_data.get('subsector', '')
        revenue = company_data.get('revenue', 0)
        growth_rate = company_data.get('growth_rate', 0)
        
        potential_acquirers = []
        
        # Analyze strategic acquirers
        for acquirer_name, acquirer_data in self.strategic_acquirers.items():
            fit_score = self._calculate_acquirer_fit_score(
                company_data, acquirer_data, sector, subsector, revenue
            )
            
            if fit_score > 0.5:  # Threshold for relevance
                recent_multiples = [
                    acq['multiple'] for acq in acquirer_data['recent_acquisitions'] 
                    if acq.get('multiple')
                ]
                avg_multiple = sum(recent_multiples) / len(recent_multiples) if recent_multiples else 0
                
                potential_acquirers.append({
                    'acquirer': acquirer_name,
                    'type': 'strategic',
                    'fit_score': fit_score,
                    'market_cap': acquirer_data['market_cap_b'],
                    'acquisition_budget': acquirer_data['acquisition_budget'],
                    'recent_acquisitions': acquirer_data['recent_acquisitions'][:3],
                    'average_acquisition_multiple': avg_multiple,
                    'acquisition_thesis': acquirer_data['acquisition_thesis'],
                    'sweet_spot_revenue': acquirer_data['sweet_spot_revenue'],
                    'strategic_rationale': self._generate_strategic_rationale(
                        company_name, acquirer_name, sector, subsector, acquirer_data
                    )
                })
        
        # Sort by fit score
        potential_acquirers.sort(key=lambda x: x['fit_score'], reverse=True)
        
        # Add PE firms if company size is appropriate
        if revenue > 50:  # $50M+ ARR makes sense for PE
            for pe_name, pe_data in self.pe_acquirers.items():
                potential_acquirers.append({
                    'acquirer': pe_name,
                    'type': 'financial',
                    'fit_score': 0.7 if revenue > 100 else 0.5,
                    'fund_size': pe_data['fund_size_b'],
                    'recent_deals': pe_data['recent_deals'],
                    'sweet_spot': pe_data['sweet_spot'],
                    'thesis': pe_data['thesis'],
                    'strategic_rationale': f"Financial buyer focused on {pe_data['thesis']}"
                })
        
        return {
            'potential_acquirers': potential_acquirers[:10],  # Top 10
            'most_likely_acquirers': potential_acquirers[:3],  # Top 3
            'acquisition_multiples_analysis': self._analyze_acquisition_multiples(sector, revenue, growth_rate),
            'market_dynamics': self._analyze_market_dynamics(sector, market_landscape)
        }
    
    def _calculate_acquirer_fit_score(self, company_data: Dict, acquirer_data: Dict, 
                                     sector: str, subsector: str, revenue: float) -> float:
        """Calculate how well a company fits an acquirer's profile"""
        
        score = 0.0
        
        # Sector alignment (40% weight)
        preferred_sectors = acquirer_data.get('preferred_sectors', [])
        if sector in preferred_sectors:
            score += 0.4
        elif any(s.lower() in sector.lower() for s in preferred_sectors):
            score += 0.2
        
        # Revenue range fit (30% weight)
        sweet_spot = acquirer_data.get('sweet_spot_revenue', '')
        if self._revenue_in_range(revenue, sweet_spot):
            score += 0.3
        
        # Recent acquisition pattern (20% weight)
        recent_acqs = acquirer_data.get('recent_acquisitions', [])
        if recent_acqs:
            # Check if similar companies acquired
            similar_sectors = sum(1 for acq in recent_acqs if 
                                sector.lower() in str(acq).lower() or 
                                subsector.lower() in str(acq).lower())
            if similar_sectors > 0:
                score += 0.2
        
        # Growth profile (10% weight)
        growth_rate = company_data.get('growth_rate', 0)
        if growth_rate > 0.5:  # 50%+ growth
            score += 0.1
        
        return score
    
    def _revenue_in_range(self, revenue: float, range_str: str) -> bool:
        """Check if revenue falls within the specified range"""
        
        import re
        # Extract numbers from range string like "50M-500M ARR"
        numbers = re.findall(r'(\d+)M', range_str)
        if len(numbers) >= 2:
            min_rev = float(numbers[0])
            max_rev = float(numbers[1])
            return min_rev <= revenue <= max_rev
        return False
    
    def _generate_strategic_rationale(self, company_name: str, acquirer_name: str, 
                                    sector: str, subsector: str, acquirer_data: Dict) -> str:
        """Generate strategic rationale for why an acquirer would buy this company"""
        
        thesis = acquirer_data.get('acquisition_thesis', '')
        
        rationales = {
            "Salesforce": f"Expand {subsector} capabilities within Salesforce ecosystem",
            "Microsoft": f"Strengthen Azure/{subsector} offering and integrate with Microsoft 365",
            "Adobe": f"Enhance Creative Cloud with {subsector} functionality",
            "Oracle": f"Deepen {sector} vertical solutions within Oracle Cloud",
            "Google": f"Accelerate Google Cloud's {subsector} capabilities",
            "SAP": f"Modernize SAP's {sector} offerings with cloud-native solution",
            "ServiceNow": f"Extend Now Platform into {subsector} workflows",
            "Workday": f"Complement Workday's suite with {subsector} capabilities",
            "Atlassian": f"Add {subsector} to Atlassian's collaboration toolkit",
            "Intuit": f"Expand QuickBooks ecosystem with {subsector} for SMBs"
        }
        
        base_rationale = rationales.get(acquirer_name, f"Strategic expansion into {subsector}")
        return f"{base_rationale}. {company_name} aligns with {acquirer_name}'s focus on {thesis}"
    
    def _analyze_acquisition_multiples(self, sector: str, revenue: float, growth_rate: float) -> Dict:
        """Analyze typical acquisition multiples for this profile"""
        
        # Base multiples by growth rate
        if growth_rate > 1.0:  # 100%+ growth
            base_multiple = 15.0
        elif growth_rate > 0.5:  # 50-100% growth
            base_multiple = 10.0
        elif growth_rate > 0.25:  # 25-50% growth
            base_multiple = 7.0
        else:
            base_multiple = 5.0
        
        # Sector adjustments
        sector_premiums = {
            "AI": 1.5,
            "Security": 1.3,
            "Data": 1.2,
            "HR Tech": 1.1,
            "Fintech": 1.2,
            "DevTools": 1.3
        }
        
        sector_multiplier = sector_premiums.get(sector, 1.0)
        
        # Size adjustments (larger = higher multiple typically)
        if revenue > 500:
            size_multiplier = 1.2
        elif revenue > 100:
            size_multiplier = 1.1
        else:
            size_multiplier = 1.0
        
        expected_multiple = base_multiple * sector_multiplier * size_multiplier
        
        return {
            'expected_multiple': expected_multiple,
            'multiple_range': {
                'low': expected_multiple * 0.7,
                'mid': expected_multiple,
                'high': expected_multiple * 1.3
            },
            'factors': {
                'base_multiple': base_multiple,
                'sector_premium': sector_multiplier,
                'size_premium': size_multiplier
            }
        }
    
    def _analyze_market_dynamics(self, sector: str, market_landscape: Dict) -> Dict:
        """Analyze market dynamics that affect acquisition likelihood"""
        
        fragmentation = market_landscape.get('fragmentation', {}).get('level', 'medium')
        
        consolidation_likelihood = {
            'high': 0.8,  # Highly fragmented = likely consolidation
            'medium': 0.5,
            'low': 0.3    # Already consolidated
        }
        
        return {
            'consolidation_likelihood': consolidation_likelihood.get(fragmentation, 0.5),
            'market_maturity': self._assess_market_maturity(sector),
            'competitive_dynamics': market_landscape.get('fragmentation', {}).get('explanation', ''),
            'acquisition_drivers': self._get_acquisition_drivers(sector)
        }
    
    def _assess_market_maturity(self, sector: str) -> str:
        """Assess market maturity level"""
        
        mature_sectors = ["CRM", "ERP", "HR Tech", "Marketing"]
        emerging_sectors = ["AI", "Climate Tech", "Web3", "Quantum"]
        
        if sector in mature_sectors:
            return "mature - consolidation phase"
        elif sector in emerging_sectors:
            return "emerging - land grab phase"
        else:
            return "growth - scaling phase"
    
    def _get_acquisition_drivers(self, sector: str) -> List[str]:
        """Get typical acquisition drivers for a sector"""
        
        drivers = {
            "AI": ["Talent acquisition", "Technology integration", "Competitive advantage"],
            "HR Tech": ["Customer base expansion", "Product suite completion", "Geographic expansion"],
            "Fintech": ["Regulatory compliance", "Technology platform", "Customer acquisition"],
            "Security": ["Threat intelligence", "Technology consolidation", "Enterprise customers"],
            "Data": ["Data assets", "Analytics capabilities", "Platform expansion"]
        }
        
        return drivers.get(sector, ["Market expansion", "Technology acquisition", "Customer base"])
    
    def format_acquirer_insights(self, analysis: Dict, company_name: str) -> str:
        """Format acquirer analysis for display"""
        
        output = f"\n🎯 POTENTIAL ACQUIRERS FOR {company_name}\n"
        output += "="*60 + "\n\n"
        
        # Most likely acquirers
        output += "TOP STRATEGIC ACQUIRERS:\n"
        for acq in analysis['most_likely_acquirers']:
            if acq['type'] == 'strategic':
                output += f"\n{acq['acquirer']} (Fit Score: {acq['fit_score']:.1%})\n"
                output += f"  • Market Cap: ${acq['market_cap']:.0f}B\n"
                output += f"  • Acquisition Budget: {acq['acquisition_budget']}\n"
                output += f"  • Strategic Rationale: {acq['strategic_rationale']}\n"
                if acq['average_acquisition_multiple'] > 0:
                    output += f"  • Avg Acquisition Multiple: {acq['average_acquisition_multiple']:.1f}x\n"
                
                # Recent relevant acquisitions
                if acq['recent_acquisitions']:
                    output += "  • Recent Acquisitions:\n"
                    for deal in acq['recent_acquisitions'][:2]:
                        output += f"    - {deal['target']} (${deal['price']}M"
                        if deal.get('multiple'):
                            output += f", {deal['multiple']:.1f}x revenue"
                        output += f")\n"
        
        # Expected multiples
        multiples = analysis['acquisition_multiples_analysis']
        output += f"\n\nEXPECTED ACQUISITION MULTIPLES:\n"
        output += f"  • Expected: {multiples['expected_multiple']:.1f}x revenue\n"
        output += f"  • Range: {multiples['multiple_range']['low']:.1f}x - {multiples['multiple_range']['high']:.1f}x\n"
        
        # Market dynamics
        dynamics = analysis['market_dynamics']
        output += f"\n\nMARKET DYNAMICS:\n"
        output += f"  • Consolidation Likelihood: {dynamics['consolidation_likelihood']:.0%}\n"
        output += f"  • Market Maturity: {dynamics['market_maturity']}\n"
        output += f"  • Key Drivers: {', '.join(dynamics['acquisition_drivers'])}\n"
        
        return output

# Integration function for PWERM
def enhance_pwerm_with_acquirers(company_data: Dict, market_landscape: Dict, 
                                tavily_api_key: str = None) -> Dict:
    """Enhance PWERM analysis with detailed acquirer insights"""
    
    analyzer = EnhancedPublicSaaSAcquirers(tavily_api_key)
    
    # Analyze potential acquirers
    acquirer_analysis = analyzer.analyze_acquirer_fit(company_data, market_landscape)
    
    # Calculate probability-weighted exit values based on acquirer analysis
    exit_scenarios = []
    
    for acquirer in acquirer_analysis['most_likely_acquirers'][:5]:
        if acquirer['type'] == 'strategic':
            # Use acquirer's typical multiples
            if acquirer.get('average_acquisition_multiple', 0) > 0:
                multiple = acquirer['average_acquisition_multiple']
            else:
                multiple = acquirer_analysis['acquisition_multiples_analysis']['expected_multiple']
            
            exit_value = company_data.get('revenue', 100) * multiple
            
            exit_scenarios.append({
                'acquirer': acquirer['acquirer'],
                'type': 'strategic acquisition',
                'exit_value': exit_value,
                'probability': acquirer['fit_score'] * 0.3,  # Adjust base probability by fit
                'multiple': multiple,
                'rationale': acquirer['strategic_rationale']
            })
    
    return {
        'acquirer_analysis': acquirer_analysis,
        'exit_scenarios': exit_scenarios,
        'formatted_insights': analyzer.format_acquirer_insights(acquirer_analysis, company_data['name'])
    }

# Test function
if __name__ == "__main__":
    # Test with Deel
    test_company = {
        'name': 'Deel',
        'sector': 'HR Tech',
        'subsector': 'Global Payroll',
        'revenue': 500,  # $500M ARR
        'growth_rate': 1.0  # 100% growth
    }
    
    test_landscape = {
        'fragmentation': {'level': 'high', 'explanation': 'Many regional players'},
        'incumbents': [{'name': 'ADP'}, {'name': 'Workday'}],
        'competitors': [{'name': 'Rippling'}, {'name': 'Remote'}]
    }
    
    result = enhance_pwerm_with_acquirers(test_company, test_landscape)
    print(result['formatted_insights'])
    
    print("\n📊 EXIT SCENARIOS:")
    for scenario in result['exit_scenarios']:
        print(f"\n{scenario['acquirer']}:")
        print(f"  Exit Value: ${scenario['exit_value']:,.0f}M ({scenario['multiple']:.1f}x)")
        print(f"  Probability: {scenario['probability']:.1%}")
        print(f"  Rationale: {scenario['rationale']}")