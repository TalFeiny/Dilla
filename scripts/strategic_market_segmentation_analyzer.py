"""
Strategic Market Segmentation Analyzer
High-level analysis of SME/Mid-Market/Enterprise dynamics like a top-tier analyst
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

@dataclass
class MarketSegment:
    """Define a market segment with its characteristics"""
    name: str
    arr_range: Tuple[float, float]
    typical_acv: Tuple[float, float]  # Annual Contract Value
    sales_cycle_days: Tuple[int, int]
    gross_margin_range: Tuple[float, float]
    growth_rate_range: Tuple[float, float]
    churn_range: Tuple[float, float]
    market_size: float
    competitive_dynamics: Dict
    key_success_factors: List[str]
    typical_buyers: List[str]
    death_traps: List[str]

class StrategicMarketAnalyzer:
    """
    Think like a McKinsey partner analyzing B2B SaaS markets
    """
    
    def __init__(self):
        self.segments = self._define_market_segments()
        self.transition_patterns = self._define_transition_patterns()
        
    def _define_market_segments(self) -> Dict[str, MarketSegment]:
        """Define the three core market segments with brutal honesty"""
        
        return {
            'SME': MarketSegment(
                name='SME (Small-Medium Enterprise)',
                arr_range=(0, 10_000_000),
                typical_acv=(500, 10_000),
                sales_cycle_days=(1, 30),
                gross_margin_range=(0.60, 0.75),
                growth_rate_range=(1.0, 4.0),  # 100-400% possible
                churn_range=(0.15, 0.30),  # 15-30% annual churn
                market_size=500_000_000_000,  # $500B TAM
                competitive_dynamics={
                    'barriers_to_entry': 'Low',
                    'competitive_intensity': 'Extreme',
                    'winner_take_all': False,
                    'platform_effects': 'Weak'
                },
                key_success_factors=[
                    'Product-led growth',
                    'Viral loops',
                    'Self-serve onboarding',
                    'Price point under $500/mo',
                    'Credit card payments'
                ],
                typical_buyers=['Shopify', 'Square', 'Intuit', 'GoDaddy', 'Wix'],
                death_traps=[
                    'High CAC relative to LTV',
                    'Feature creep from customer requests',
                    'Platform dependency (Shopify app store risk)',
                    'Race to the bottom pricing',
                    'Churn makes growth unsustainable'
                ]
            ),
            
            'Mid-Market': MarketSegment(
                name='Mid-Market',
                arr_range=(10_000_000, 100_000_000),
                typical_acv=(10_000, 100_000),
                sales_cycle_days=(30, 120),
                gross_margin_range=(0.70, 0.85),
                growth_rate_range=(0.5, 1.5),  # 50-150% 
                churn_range=(0.08, 0.15),  # 8-15% churn
                market_size=300_000_000_000,  # $300B TAM
                competitive_dynamics={
                    'barriers_to_entry': 'Medium',
                    'competitive_intensity': 'High',
                    'winner_take_all': 'Category-dependent',
                    'platform_effects': 'Moderate'
                },
                key_success_factors=[
                    'Land and expand motion',
                    'Strong customer success',
                    'Integrations ecosystem',
                    'Vertical specialization',
                    'Inside sales efficiency'
                ],
                typical_buyers=['Salesforce', 'HubSpot', 'ServiceNow', 'PE funds'],
                death_traps=[
                    'Stuck in the middle - too complex for SME, too simple for Enterprise',
                    'Sales efficiency never improves',
                    'Cant afford enterprise features but customers demand them',
                    'Acquisition offers at bad multiples',
                    'PE rollup target - lose soul'
                ]
            ),
            
            'Enterprise': MarketSegment(
                name='Enterprise',
                arr_range=(100_000_000, 10_000_000_000),
                typical_acv=(100_000, 10_000_000),
                sales_cycle_days=(120, 365),
                gross_margin_range=(0.80, 0.90),
                growth_rate_range=(0.2, 0.8),  # 20-80%
                churn_range=(0.02, 0.08),  # 2-8% churn
                market_size=800_000_000_000,  # $800B TAM
                competitive_dynamics={
                    'barriers_to_entry': 'Extreme',
                    'competitive_intensity': 'Oligopoly',
                    'winner_take_all': True,
                    'platform_effects': 'Strong'
                },
                key_success_factors=[
                    'Enterprise-grade security/compliance',
                    'Services ecosystem',
                    'Global support',
                    'Platform extensibility',
                    'C-suite relationships',
                    'Multi-year contracts'
                ],
                typical_buyers=['Microsoft', 'Oracle', 'SAP', 'Adobe', 'Cisco'],
                death_traps=[
                    'Cant close first 10 Fortune 500 logos',
                    'Services revenue > Software revenue',
                    'Customization requests kill product roadmap',
                    'Incumbent copies features and bundles',
                    'Sales cycles kill cash flow'
                ]
            )
        }
    
    def _define_transition_patterns(self) -> Dict[str, Dict]:
        """Define how companies transition between segments"""
        
        return {
            'SME_to_MidMarket': {
                'success_rate': 0.15,  # Only 15% make it
                'typical_time_years': 3,
                'key_challenges': [
                    'Building inside sales team',
                    'Moving from PLG to sales-led',
                    'Increasing ACV without losing velocity',
                    'Adding enterprise features'
                ],
                'success_examples': ['Calendly', 'Canva', 'Notion'],
                'failure_examples': ['Most Y Combinator companies']
            },
            
            'MidMarket_to_Enterprise': {
                'success_rate': 0.25,  # 25% make it
                'typical_time_years': 5,
                'key_challenges': [
                    'Enterprise sales talent acquisition',
                    'SOC2, ISO, compliance burden',
                    'Global infrastructure',
                    'Services and support scale',
                    'Competing with incumbents'
                ],
                'success_examples': ['Datadog', 'Snowflake', 'ServiceNow'],
                'failure_examples': ['Many Series C companies']
            },
            
            'Direct_to_Enterprise': {
                'success_rate': 0.10,  # Very rare
                'typical_time_years': 7,
                'key_challenges': [
                    'Massive capital requirements',
                    'Long path to product-market fit',
                    'Founder needs enterprise DNA',
                    'Early customers shape product too much'
                ],
                'success_examples': ['Palantir', 'Databricks', 'Rubrik'],
                'failure_examples': ['Most enterprise AI startups']
            }
        }
    
    def analyze_company_positioning(self, company_data: Dict) -> Dict:
        """
        Analyze where a company sits and where it should go
        Like a strategy consultant would
        """
        
        arr = company_data.get('arr', 5_000_000)
        acv = company_data.get('acv', 5_000)
        growth_rate = company_data.get('growth_rate', 0.5)
        sales_cycle = company_data.get('sales_cycle_days', 30)
        
        # Determine current segment
        current_segment = self._identify_segment(arr)
        segment_fit = self._assess_segment_fit(company_data, current_segment)
        
        # Strategic analysis
        analysis = {
            'current_segment': current_segment.name,
            'segment_fit_score': segment_fit['score'],
            'segment_misalignments': segment_fit['misalignments'],
            
            'strategic_options': self._generate_strategic_options(
                company_data, current_segment
            ),
            
            'transition_readiness': self._assess_transition_readiness(
                company_data, current_segment
            ),
            
            'competitive_position': self._analyze_competitive_position(
                company_data, current_segment
            ),
            
            'valuation_implications': self._calculate_valuation_implications(
                company_data, current_segment
            ),
            
            'strategic_recommendation': self._generate_strategic_recommendation(
                company_data, current_segment, segment_fit
            )
        }
        
        return analysis
    
    def _identify_segment(self, arr: float) -> MarketSegment:
        """Identify which segment a company is in based on ARR"""
        
        if arr < 10_000_000:
            return self.segments['SME']
        elif arr < 100_000_000:
            return self.segments['Mid-Market']
        else:
            return self.segments['Enterprise']
    
    def _assess_segment_fit(self, company_data: Dict, segment: MarketSegment) -> Dict:
        """Assess how well company fits its current segment"""
        
        fit_score = 1.0
        misalignments = []
        
        # Check ACV alignment
        acv = company_data.get('acv', 5_000)
        if not (segment.typical_acv[0] <= acv <= segment.typical_acv[1]):
            fit_score *= 0.7
            misalignments.append({
                'factor': 'ACV',
                'issue': f'ACV ${acv:,.0f} outside typical range ${segment.typical_acv[0]:,.0f}-${segment.typical_acv[1]:,.0f}',
                'impact': 'Sales efficiency and unit economics misaligned'
            })
        
        # Check sales cycle alignment
        sales_cycle = company_data.get('sales_cycle_days', 30)
        if not (segment.sales_cycle_days[0] <= sales_cycle <= segment.sales_cycle_days[1]):
            fit_score *= 0.8
            misalignments.append({
                'factor': 'Sales Cycle',
                'issue': f'{sales_cycle} days vs typical {segment.sales_cycle_days[0]}-{segment.sales_cycle_days[1]}',
                'impact': 'Go-to-market motion inefficient for segment'
            })
        
        # Check growth rate alignment
        growth = company_data.get('growth_rate', 0.5)
        if not (segment.growth_rate_range[0] <= growth <= segment.growth_rate_range[1]):
            fit_score *= 0.85
            misalignments.append({
                'factor': 'Growth Rate',
                'issue': f'{growth*100:.0f}% growth vs typical {segment.growth_rate_range[0]*100:.0f}%-{segment.growth_rate_range[1]*100:.0f}%',
                'impact': 'May indicate product-market fit issues'
            })
        
        return {
            'score': fit_score,
            'misalignments': misalignments,
            'recommendation': self._recommend_segment_adjustments(misalignments)
        }
    
    def _generate_strategic_options(self, company_data: Dict, 
                                  current_segment: MarketSegment) -> List[Dict]:
        """Generate strategic options like a McKinsey partner would"""
        
        options = []
        
        # Option 1: Double down on current segment
        options.append({
            'name': f'Dominate {current_segment.name}',
            'description': f'Focus on becoming category leader in {current_segment.name}',
            'pros': [
                'Shortest path to profitability',
                'Clear customer profile',
                'Existing product-market fit'
            ],
            'cons': [
                f'Limited TAM within {current_segment.name}',
                'Valuation ceiling',
                'Acquisition multiples lower'
            ],
            'success_probability': 0.6,
            'time_to_outcome': '2-3 years',
            'likely_exit': f'{current_segment.typical_buyers[0]} at 6-10x ARR'
        })
        
        # Option 2: Move upmarket
        if current_segment.name != 'Enterprise':
            next_segment = 'Mid-Market' if current_segment.name == 'SME' else 'Enterprise'
            transition_key = f'{current_segment.name}_to_{next_segment}'.replace(' ', '').replace('(Small-MediumEnterprise)', 'SME')
            
            options.append({
                'name': f'Graduate to {next_segment}',
                'description': f'Build capabilities to serve {next_segment} customers',
                'pros': [
                    'Higher ACVs and better unit economics',
                    'Lower churn rates',
                    'Premium valuation multiples'
                ],
                'cons': [
                    'Expensive transition (sales, product, support)',
                    f"Only {self.transition_patterns.get(transition_key, {}).get('success_rate', 0.2)*100:.0f}% succeed",
                    'Risk of losing core business'
                ],
                'success_probability': self.transition_patterns.get(transition_key, {}).get('success_rate', 0.2),
                'time_to_outcome': f"{self.transition_patterns.get(transition_key, {}).get('typical_time_years', 5)} years",
                'likely_exit': 'IPO or strategic at 15-25x ARR'
            })
        
        # Option 3: Vertical focus
        options.append({
            'name': 'Vertical Specialization',
            'description': 'Become the dominant solution for a specific industry',
            'pros': [
                'Defensible moat',
                'Premium pricing',
                'Clear acquisition path'
            ],
            'cons': [
                'Limited TAM',
                'Harder to pivot',
                'Industry risk concentration'
            ],
            'success_probability': 0.45,
            'time_to_outcome': '3-4 years',
            'likely_exit': 'Vertical strategic or PE at 8-12x'
        })
        
        # Option 4: Platform play
        if company_data.get('arr', 0) > 20_000_000:
            options.append({
                'name': 'Platform Transformation',
                'description': 'Build ecosystem of apps/integrations around core product',
                'pros': [
                    'Network effects',
                    'Multiple expansion paths',
                    'Stickier customers'
                ],
                'cons': [
                    'Massive investment required',
                    'Long time to value',
                    'Execution complexity'
                ],
                'success_probability': 0.25,
                'time_to_outcome': '5-7 years',
                'likely_exit': 'IPO at 20-40x ARR or $10B+ acquisition'
            })
        
        return options
    
    def _assess_transition_readiness(self, company_data: Dict, 
                                   current_segment: MarketSegment) -> Dict:
        """Assess readiness to move to next segment"""
        
        readiness_score = 0
        requirements = []
        gaps = []
        
        if current_segment.name == 'SME':
            # SME → Mid-Market requirements
            requirements = [
                {'factor': 'ARR', 'required': 8_000_000, 'weight': 0.2},
                {'factor': 'ACV', 'required': 10_000, 'weight': 0.25},
                {'factor': 'Sales team size', 'required': 10, 'weight': 0.2},
                {'factor': 'Gross margin', 'required': 0.75, 'weight': 0.15},
                {'factor': 'Enterprise features', 'required': True, 'weight': 0.2}
            ]
            
        elif current_segment.name == 'Mid-Market':
            # Mid-Market → Enterprise requirements
            requirements = [
                {'factor': 'ARR', 'required': 80_000_000, 'weight': 0.15},
                {'factor': 'ACV', 'required': 100_000, 'weight': 0.2},
                {'factor': 'Fortune 500 logos', 'required': 5, 'weight': 0.25},
                {'factor': 'Global presence', 'required': True, 'weight': 0.2},
                {'factor': 'Compliance certs', 'required': ['SOC2', 'ISO27001'], 'weight': 0.2}
            ]
        
        # Calculate readiness
        for req in requirements:
            factor_value = company_data.get(req['factor'].lower().replace(' ', '_'), 0)
            if isinstance(req['required'], bool):
                met = factor_value == req['required']
            elif isinstance(req['required'], list):
                met = all(cert in company_data.get('certifications', []) for cert in req['required'])
            else:
                met = factor_value >= req['required']
            
            if met:
                readiness_score += req['weight']
            else:
                gaps.append({
                    'factor': req['factor'],
                    'current': factor_value,
                    'required': req['required'],
                    'impact': f"Critical for {current_segment.name} → next segment"
                })
        
        return {
            'readiness_score': readiness_score,
            'ready': readiness_score > 0.7,
            'gaps': gaps,
            'time_to_ready': f"{len(gaps) * 6}-{len(gaps) * 12} months" if gaps else "Ready now"
        }
    
    def _analyze_competitive_position(self, company_data: Dict,
                                    segment: MarketSegment) -> Dict:
        """Analyze competitive position within segment"""
        
        # Simple competitive scoring
        position_score = 0.5  # Base
        
        # Market share impact
        market_share = company_data.get('market_share', 0.01)
        if market_share > 0.15:
            position_score += 0.3
            position = 'Leader'
        elif market_share > 0.05:
            position_score += 0.15
            position = 'Challenger'
        else:
            position = 'Niche Player'
        
        # Growth vs market
        if company_data.get('growth_rate', 0.5) > segment.growth_rate_range[1]:
            position_score += 0.2
            momentum = 'Taking share'
        else:
            momentum = 'Losing share'
        
        return {
            'position': position,
            'momentum': momentum,
            'competitive_score': position_score,
            'key_competitors': self._identify_key_competitors(company_data, segment),
            'competitive_advantages': company_data.get('competitive_advantages', []),
            'strategic_threats': self._identify_strategic_threats(company_data, segment)
        }
    
    def _calculate_valuation_implications(self, company_data: Dict,
                                        segment: MarketSegment) -> Dict:
        """Calculate how segment affects valuation"""
        
        arr = company_data.get('arr', 10_000_000)
        growth = company_data.get('growth_rate', 0.5)
        
        # Base multiples by segment
        segment_multiples = {
            'SME': (3, 8),  # 3-8x ARR
            'Mid-Market': (5, 15),  # 5-15x  
            'Enterprise': (8, 25)  # 8-25x
        }
        
        base_range = segment_multiples.get(segment.name.replace(' (Small-Medium Enterprise)', ''), (5, 12))
        
        # Adjust for growth
        if growth > segment.growth_rate_range[1]:
            multiple_range = (base_range[0] * 1.5, base_range[1] * 1.5)
        elif growth < segment.growth_rate_range[0]:
            multiple_range = (base_range[0] * 0.7, base_range[1] * 0.7)
        else:
            multiple_range = base_range
        
        return {
            'current_segment_multiple': multiple_range,
            'current_valuation_range': (arr * multiple_range[0], arr * multiple_range[1]),
            'if_moved_upmarket': {
                'new_multiple': (multiple_range[0] * 1.5, multiple_range[1] * 1.5),
                'value_creation': arr * multiple_range[1] * 0.5  # 50% uplift
            },
            'acquisition_likelihood': self._calculate_acquisition_likelihood(company_data, segment),
            'ipo_viability': arr > 100_000_000 and growth > 0.3
        }
    
    def _generate_strategic_recommendation(self, company_data: Dict,
                                         segment: MarketSegment,
                                         fit_analysis: Dict) -> str:
        """Generate McKinsey-style strategic recommendation"""
        
        arr = company_data.get('arr', 10_000_000)
        growth = company_data.get('growth_rate', 0.5)
        fit_score = fit_analysis['score']
        
        if fit_score > 0.8 and growth > segment.growth_rate_range[0]:
            return f"""
            RECOMMENDATION: OPTIMIZE WITHIN {segment.name.upper()}
            
            Your strong segment fit ({fit_score:.0%}) and solid growth ({growth*100:.0f}%) suggest 
            focusing on segment leadership rather than premature expansion.
            
            Key Actions:
            1. Double down on {segment.key_success_factors[0]}
            2. Expand within segment through {segment.key_success_factors[1]}
            3. Prepare for exit to {segment.typical_buyers[0]} in 18-24 months
            
            Expected Outcome: {segment.typical_buyers[0]} acquisition at {arr * 8 / 1e6:.0f}M 
            ({8}x ARR) within 2 years.
            """
            
        elif arr > segment.arr_range[1] * 0.8:  # Near top of segment
            return f"""
            RECOMMENDATION: GRADUATE TO NEXT SEGMENT
            
            You're outgrowing {segment.name} (ARR: ${arr/1e6:.1f}M vs segment cap: ${segment.arr_range[1]/1e6:.0f}M).
            Time to move upmarket or face growth ceiling.
            
            Transition Requirements:
            1. Hire enterprise sales leadership (budget $2-3M/year)
            2. Achieve compliance certifications (SOC2, ISO)
            3. Build customer success infrastructure
            
            Risk: Only {self.transition_patterns.get(f'{segment.name}_to_MidMarket', {}).get('success_rate', 0.2)*100:.0f}% successfully transition.
            Reward: Valuation multiple expansion from {8}x to {15}x ARR.
            """
            
        else:  # Struggling in segment
            return f"""
            RECOMMENDATION: FOCUS OR FOLD
            
            Weak segment fit ({fit_score:.0%}) and below-average growth ({growth*100:.0f}%) 
            indicate fundamental challenges.
            
            Option A: Radical Focus
            - Pick one vertical/use case
            - Cut burn by 40%
            - Extend runway to 24+ months
            - Prove unit economics in niche
            
            Option B: Strategic Exit
            - Current value: ${arr * 4 / 1e6:.0f}M (distressed multiple)
            - Likely acquirers: {segment.typical_buyers[-1]} or PE rollup
            - Timeline: 3-6 months
            
            Hard Truth: Without dramatic change, you're on path to zombie status or shutdown.
            """
    
    def _identify_key_competitors(self, company_data: Dict, segment: MarketSegment) -> List[str]:
        """Identify key competitors in segment"""
        # This would pull from a competitive intelligence database
        return ['Competitor A', 'Competitor B', 'Competitor C']
    
    def _identify_strategic_threats(self, company_data: Dict, segment: MarketSegment) -> List[str]:
        """Identify strategic threats"""
        threats = []
        
        if segment.name == 'SME':
            threats.extend([
                'Platform players adding competing features',
                'Free alternatives from big tech',
                'New VC-backed entrants'
            ])
        elif segment.name == 'Mid-Market':
            threats.extend([
                'Enterprise vendors moving downmarket',
                'PE consolidation plays',
                'Vertical-specific solutions'
            ])
        else:  # Enterprise
            threats.extend([
                'Incumbent feature copying',
                'Platform bundling',
                'Open source alternatives'
            ])
            
        return threats
    
    def _calculate_acquisition_likelihood(self, company_data: Dict, segment: MarketSegment) -> Dict:
        """Calculate likelihood of acquisition by segment buyers"""
        
        likelihood = {}
        for buyer in segment.typical_buyers[:3]:  # Top 3 buyers
            score = 0.3  # Base
            
            # Adjust for strategic fit
            if company_data.get('strategic_value', {}).get(buyer, 0) > 0.5:
                score += 0.3
                
            # Adjust for size
            if segment.arr_range[0] < company_data.get('arr', 0) < segment.arr_range[1]:
                score += 0.2
                
            likelihood[buyer] = {
                'probability': score,
                'likely_multiple': 8 if score > 0.5 else 6,
                'timeline': '12-18 months' if score > 0.5 else '18-24 months'
            }
            
        return likelihood
    
    def _recommend_segment_adjustments(self, misalignments: List[Dict]) -> str:
        """Recommend how to better fit segment"""
        
        if not misalignments:
            return "Strong segment fit - maintain course"
            
        adjustments = []
        for misalignment in misalignments:
            if misalignment['factor'] == 'ACV':
                adjustments.append("Restructure pricing to align with segment norms")
            elif misalignment['factor'] == 'Sales Cycle':
                adjustments.append("Optimize sales process for segment velocity")
            elif misalignment['factor'] == 'Growth Rate':
                adjustments.append("Address product-market fit gaps")
                
        return " | ".join(adjustments)