"""
Outlier Score Analyzer
Analyzes specific market segments to predict acquisition patterns and outlier potential
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass

@dataclass
class MarketSegmentAnalysis:
    """Analysis of a specific market segment"""
    segment: str
    key_players: List[Dict]
    recent_acquisitions: List[Dict]
    strategic_buyers: List[Dict]
    market_dynamics: Dict
    failure_indicators: List[str]
    success_patterns: List[str]

class OutlierScoreAnalyzer:
    """
    Analyze outlier potential based on specific market dynamics
    Example: Enterprise ERP with Rillet, Pigment, etc.
    """
    
    def __init__(self):
        # Market segment data - this would be dynamically updated
        self.market_segments = {
            'enterprise_erp': {
                'emerging_players': [
                    {'name': 'Rillet', 'focus': 'Real-time finance ops', 'arr': 15_000_000, 'growth': 2.5},
                    {'name': 'Pigment', 'focus': 'Business planning', 'arr': 30_000_000, 'growth': 2.2},
                    {'name': 'Mosaic', 'focus': 'Strategic finance', 'arr': 20_000_000, 'growth': 1.8},
                    {'name': 'Runway', 'focus': 'Financial modeling', 'arr': 10_000_000, 'growth': 3.0},
                    {'name': 'Digits', 'focus': 'AI-powered accounting', 'arr': 8_000_000, 'growth': 4.0}
                ],
                'incumbents': [
                    {'name': 'SAP', 'market_cap': 150_000_000_000, 'acquisition_budget': 10_000_000_000},
                    {'name': 'Oracle', 'market_cap': 280_000_000_000, 'acquisition_budget': 15_000_000_000},
                    {'name': 'Sage', 'market_cap': 8_000_000_000, 'acquisition_budget': 1_000_000_000},
                    {'name': 'Xero', 'market_cap': 12_000_000_000, 'acquisition_budget': 2_000_000_000},
                    {'name': 'Intuit', 'market_cap': 140_000_000_000, 'acquisition_budget': 8_000_000_000}
                ],
                'recent_deals': [
                    {'acquirer': 'Xero', 'target': 'Melio', 'price': 300_000_000, 'multiple': 15, 'rationale': 'B2B payments'},
                    {'acquirer': 'Sage', 'target': 'Brightpearl', 'price': 250_000_000, 'multiple': 8, 'rationale': 'Retail ops'},
                    {'acquirer': 'Intuit', 'target': 'Mailchimp', 'price': 12_000_000_000, 'multiple': 20, 'rationale': 'SMB expansion'}
                ]
            }
        }
        
    def analyze_outlier_potential(self, company_name: str, segment: str, 
                                 company_data: Dict) -> Dict:
        """
        Calculate outlier score for a company in a specific segment
        """
        
        segment_data = self.market_segments.get(segment, {})
        if not segment_data:
            return {'error': f'Unknown segment: {segment}'}
        
        # Find company in emerging players
        company_profile = None
        for player in segment_data['emerging_players']:
            if player['name'].lower() == company_name.lower():
                company_profile = player
                break
        
        if not company_profile:
            company_profile = {
                'name': company_name,
                'arr': company_data.get('arr', 10_000_000),
                'growth': company_data.get('growth_rate', 1.5)
            }
        
        # Calculate various outlier factors
        acquisition_likelihood = self._calculate_acquisition_likelihood(
            company_profile, segment_data
        )
        
        failure_risk = self._calculate_failure_risk(company_profile, segment)
        
        strategic_value = self._calculate_strategic_value(
            company_profile, segment_data
        )
        
        competitive_moat = self._assess_competitive_moat(
            company_profile, segment_data
        )
        
        # Generate specific acquisition scenarios
        acquisition_scenarios = self._generate_acquisition_scenarios(
            company_profile, segment_data
        )
        
        # Calculate overall outlier score
        outlier_score = self._calculate_overall_outlier_score(
            acquisition_likelihood,
            failure_risk,
            strategic_value,
            competitive_moat
        )
        
        return {
            'company': company_name,
            'segment': segment,
            'outlier_score': outlier_score,
            'acquisition_likelihood': acquisition_likelihood,
            'failure_risk': failure_risk,
            'strategic_value': strategic_value,
            'competitive_moat': competitive_moat,
            'acquisition_scenarios': acquisition_scenarios,
            'market_insights': self._generate_market_insights(segment, segment_data),
            'recommendation': self._generate_recommendation(outlier_score, acquisition_scenarios)
        }
    
    def _calculate_acquisition_likelihood(self, company: Dict, segment_data: Dict) -> Dict:
        """
        Calculate likelihood of acquisition by specific buyers
        """
        
        likelihood_by_buyer = {}
        
        for incumbent in segment_data['incumbents']:
            score = 0.5  # Base score
            
            # Check acquisition patterns
            recent_deals = [d for d in segment_data['recent_deals'] 
                          if d['acquirer'] == incumbent['name']]
            
            if recent_deals:
                # Active acquirer
                score += 0.2
                
                # Check if they need this capability
                if incumbent['name'] == 'Sage' and 'planning' in company.get('focus', '').lower():
                    score += 0.3  # Sage needs modern planning tools
                elif incumbent['name'] == 'Xero' and 'finance ops' in company.get('focus', '').lower():
                    score += 0.25  # Xero expanding beyond payments
                elif incumbent['name'] == 'SAP' and company.get('arr', 0) > 50_000_000:
                    score += 0.2  # SAP only buys at scale
            
            # Budget constraints
            likely_price = company.get('arr', 10_000_000) * 12  # 12x multiple
            if likely_price > incumbent['acquisition_budget'] * 0.3:
                score *= 0.5  # Too expensive
            
            likelihood_by_buyer[incumbent['name']] = {
                'score': min(score, 0.95),
                'likely_multiple': self._estimate_acquisition_multiple(company, incumbent),
                'strategic_fit': self._assess_strategic_fit(company, incumbent),
                'recent_activity': len(recent_deals) > 0
            }
        
        # Also consider PE buyers
        likelihood_by_buyer['PE Funds'] = {
            'score': 0.7 if company.get('arr', 0) > 20_000_000 else 0.3,
            'likely_multiple': 8 if company.get('growth', 1) < 1.5 else 12,
            'strategic_fit': 'Financial buyer - focus on profitability',
            'recent_activity': True
        }
        
        return likelihood_by_buyer
    
    def _calculate_failure_risk(self, company: Dict, segment: str) -> Dict:
        """
        Calculate risk of failure in this segment
        """
        
        risk_factors = []
        risk_score = 0.0
        
        # Market-specific risks
        if segment == 'enterprise_erp':
            # Long sales cycles
            if company.get('arr', 0) < 10_000_000:
                risk_factors.append('Sub-scale for enterprise sales')
                risk_score += 0.3
            
            # Incumbent competition
            if company.get('growth', 1) < 1.5:
                risk_factors.append('Growth slowing - incumbents catching up')
                risk_score += 0.25
            
            # Funding environment
            if company.get('runway_months', 18) < 12:
                risk_factors.append('Limited runway in capital-intensive market')
                risk_score += 0.35
            
            # Product-market fit
            if 'AI' in company.get('focus', '') and company.get('arr', 0) < 5_000_000:
                risk_factors.append('AI-first in traditional market - adoption risk')
                risk_score += 0.2
        
        return {
            'risk_score': min(risk_score, 0.9),
            'risk_factors': risk_factors,
            'survival_probability': 1 - min(risk_score, 0.9),
            'time_to_danger': self._estimate_time_to_danger(company, risk_score)
        }
    
    def _calculate_strategic_value(self, company: Dict, segment_data: Dict) -> Dict:
        """
        Calculate strategic value to potential acquirers
        """
        
        value_drivers = []
        strategic_score = 0.5  # Base
        
        # Unique technology
        if 'AI' in company.get('focus', '') or 'real-time' in company.get('focus', ''):
            value_drivers.append('Next-gen technology')
            strategic_score += 0.2
        
        # Customer base
        if company.get('enterprise_customers', 0) > 100:
            value_drivers.append('Strong enterprise traction')
            strategic_score += 0.25
        
        # Geographic expansion opportunity
        if company.get('primary_market') != 'US':
            value_drivers.append('International expansion play')
            strategic_score += 0.15
        
        # Talent acquisition
        if company.get('engineering_team_size', 0) > 50:
            value_drivers.append('Strong technical team')
            strategic_score += 0.1
        
        return {
            'score': min(strategic_score, 0.95),
            'value_drivers': value_drivers,
            'acquirer_rationale': self._generate_acquirer_rationale(value_drivers, segment_data)
        }
    
    def _generate_acquisition_scenarios(self, company: Dict, segment_data: Dict) -> List[Dict]:
        """
        Generate specific acquisition scenarios with narratives
        """
        
        scenarios = []
        
        # Scenario 1: Sage's European Consolidation Play
        if company.get('arr', 0) < 50_000_000:
            scenarios.append({
                'id': 'sage_consolidation',
                'acquirer': 'Sage',
                'narrative': """
                After Xero bought Melio, Sage needs to respond. They've been losing mid-market share.
                Your modern planning tools could revitalize their offering. European roots help with regulatory approval.
                
                Likely approach: Strategic partnership first, acquisition in 12-18 months at 10-12x ARR.
                """,
                'probability': 0.15,
                'value_range': (company.get('arr', 10_000_000) * 10, company.get('arr', 10_000_000) * 12),
                'timeline': '12-18 months',
                'key_catalyst': 'Sage Q4 earnings miss on cloud transition'
            })
        
        # Scenario 2: Oracle's AI ERP Vision
        if 'AI' in company.get('focus', ''):
            scenarios.append({
                'id': 'oracle_ai_play',
                'acquirer': 'Oracle',
                'narrative': """
                Larry Ellison's new obsession: "Autonomous ERP". Your AI-native approach fits perfectly.
                Oracle NetSuite division given mandate to acquire AI-first finance tools.
                
                Warning: Oracle integration is brutal. But the price (15-18x) makes founders forget.
                """,
                'probability': 0.08,
                'value_range': (company.get('arr', 10_000_000) * 15, company.get('arr', 10_000_000) * 18),
                'timeline': '6-9 months',
                'key_catalyst': 'Oracle CloudWorld announcement on Autonomous Finance'
            })
        
        # Scenario 3: PE Roll-up Play
        if segment_data.get('emerging_players', []):
            scenarios.append({
                'id': 'pe_rollup',
                'acquirer': 'Vista/Thoma Bravo',
                'narrative': f"""
                PE sees opportunity: combine {company['name']}, Mosaic, and Digits into "NextGen FinanceOS".
                Classic playbook: Buy 3-4 players, merge tech, cut costs, sell to SAP in 5 years.
                
                You're piece #1. Founders get 20% of NewCo to run the combined entity.
                """,
                'probability': 0.12,
                'value_range': (company.get('arr', 10_000_000) * 8, company.get('arr', 10_000_000) * 10),
                'timeline': '3-6 months',
                'key_catalyst': 'PE dry powder at record highs'
            })
        
        # Scenario 4: The Failure Path
        scenarios.append({
            'id': 'market_rejection',
            'acquirer': 'None',
            'narrative': """
            Enterprise ERP proves too hard. Sales cycles kill growth. Incumbents copy features.
            After 18 months of flat growth, board pushes for acquihire. Best offer: 2x ARR from Brex.
            
            Lesson: Building for enterprises requires massive capital. The middle dies.
            """,
            'probability': 0.25,
            'value_range': (company.get('arr', 10_000_000) * 1, company.get('arr', 10_000_000) * 2),
            'timeline': '18-24 months',
            'key_catalyst': 'Growth stalls below 50%'
        })
        
        return scenarios
    
    def _generate_market_insights(self, segment: str, segment_data: Dict) -> Dict:
        """
        Generate insights about the market segment
        """
        
        insights = {
            'market_stage': 'Early consolidation',
            'key_trends': [],
            'warning_signs': [],
            'opportunities': []
        }
        
        if segment == 'enterprise_erp':
            insights['key_trends'] = [
                'Incumbents struggling with cloud transition',
                'AI-first players gaining traction',
                'Real-time finance becoming table stakes',
                'Consolidation starting (Xero-Melio first of many)'
            ]
            
            insights['warning_signs'] = [
                'Several players targeting same ICP',
                'Enterprise sales cycles lengthening',
                'Incumbents launching competitive products',
                'Funding environment tightening'
            ]
            
            insights['opportunities'] = [
                'Vertical ERP (industry-specific) still open',
                'International markets underserved',
                'Mid-market sweet spot between SMB and enterprise',
                'Integration/workflow plays valuable'
            ]
        
        return insights
    
    def _calculate_overall_outlier_score(self, acquisition: Dict, failure: Dict,
                                       strategic: Dict, moat: Dict) -> float:
        """
        Calculate overall outlier score (0-100)
        """
        
        # Weight the factors
        acquisition_score = max([b['score'] for b in acquisition.values()]) * 30
        failure_penalty = failure['risk_score'] * 40
        strategic_bonus = strategic['score'] * 20
        moat_bonus = moat['score'] * 10
        
        # Calculate total
        outlier_score = acquisition_score + strategic_bonus + moat_bonus - failure_penalty
        
        # Normalize to 0-100
        return max(0, min(100, outlier_score * 2))
    
    def _generate_recommendation(self, outlier_score: float, scenarios: List[Dict]) -> str:
        """
        Generate strategic recommendation
        """
        
        if outlier_score > 70:
            return f"""
            HIGH OUTLIER POTENTIAL ({outlier_score:.0f}/100)
            
            Recommendation: Hold for strategic acquisition. Multiple buyers interested.
            Best scenario: {max(scenarios, key=lambda x: x['value_range'][1])['acquirer']} at {max(scenarios, key=lambda x: x['value_range'][1])['value_range'][1]/1e6:.0f}M
            
            Action items:
            1. Build relationships with strategic buyers
            2. Focus on enterprise logos over revenue
            3. Maintain 18+ months runway
            """
        elif outlier_score > 40:
            return f"""
            MODERATE OUTLIER POTENTIAL ({outlier_score:.0f}/100)
            
            Recommendation: Execution risk high. Focus on fundamentals.
            Likely outcome: {max(scenarios, key=lambda x: x['probability'])['narrative'][:100]}...
            
            Action items:
            1. Prove enterprise product-market fit
            2. Get to $50M ARR for better multiples
            3. Consider strategic partnerships
            """
        else:
            return f"""
            LOW OUTLIER POTENTIAL ({outlier_score:.0f}/100)
            
            Recommendation: Difficult market. Consider pivot or early exit.
            Risk: {max(scenarios, key=lambda x: x['probability'])['narrative'][:100]}...
            
            Action items:
            1. Explore acquihire opportunities
            2. Cut burn to extend runway
            3. Consider vertical/geographic focus
            """
    
    def _assess_competitive_moat(self, company: Dict, segment_data: Dict) -> Dict:
        """Assess competitive moat"""
        return {
            'score': 0.6,
            'factors': ['Technical complexity', 'Customer switching costs', 'Network effects']
        }
    
    def _estimate_acquisition_multiple(self, company: Dict, buyer: Dict) -> float:
        """Estimate acquisition multiple based on buyer patterns"""
        base_multiple = 10
        if company.get('growth', 1) > 2:
            base_multiple *= 1.5
        if buyer['name'] in ['Oracle', 'SAP']:
            base_multiple *= 1.2  # Premium buyers
        return base_multiple
    
    def _assess_strategic_fit(self, company: Dict, buyer: Dict) -> str:
        """Assess strategic fit with buyer"""
        if buyer['name'] == 'Sage':
            return 'Gap in modern planning tools'
        elif buyer['name'] == 'Xero':
            return 'Expansion beyond payments into operations'
        return 'General market expansion'
    
    def _estimate_time_to_danger(self, company: Dict, risk_score: float) -> str:
        """Estimate time until critical risk materializes"""
        if risk_score > 0.7:
            return '6-9 months'
        elif risk_score > 0.5:
            return '12-18 months'
        return '18+ months'
    
    def _generate_acquirer_rationale(self, value_drivers: List[str], segment_data: Dict) -> Dict:
        """Generate specific acquirer rationales"""
        rationales = {}
        
        for incumbent in segment_data.get('incumbents', []):
            if 'Next-gen technology' in value_drivers and incumbent['name'] == 'SAP':
                rationales[incumbent['name']] = 'Accelerate S/4HANA AI capabilities'
            elif 'International expansion play' in value_drivers and incumbent['name'] == 'Intuit':
                rationales[incumbent['name']] = 'QuickBooks global expansion'
        
        return rationales