"""
Intelligent Scenario Generator for PWERM
Move beyond simplistic base/home-run models to nuanced, data-driven simulations
"""

import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
import json

class IntelligentScenarioEngine:
    """
    Replace traditional base/home-run with intelligent graduation-based outcomes
    """
    
    def __init__(self):
        # Instead of base/home-run, we have nuanced outcome paths
        self.outcome_archetypes = {
            'fast_grower': {
                'name': 'Zoom/Datadog Path',
                'description': 'Rapid graduation through stages, premium multiples',
                'probability_factors': ['nrr > 130%', 'growth > 100%', 'gross_margin > 75%'],
                'examples': ['Zoom', 'Datadog', 'Snowflake', 'CrowdStrike']
            },
            'steady_builder': {
                'name': 'Atlassian/HubSpot Path', 
                'description': 'Consistent growth, methodical stage progression',
                'probability_factors': ['rule_of_40 > 50', 'cac_payback < 12mo', 'nrr > 110%'],
                'examples': ['Atlassian', 'HubSpot', 'Veeva', 'ServiceNow']
            },
            'pivot_winner': {
                'name': 'Slack/Pinterest Path',
                'description': 'Struggled early, found PMF, accelerated',
                'probability_factors': ['pivot_success', 'viral_growth', 'category_creator'],
                'examples': ['Slack', 'Pinterest', 'Twitter', 'Roblox']
            },
            'acquisition_target': {
                'name': 'WhatsApp/GitHub Path',
                'description': 'Strategic value exceeds financial metrics',
                'probability_factors': ['strategic_buyers > 3', 'unique_tech', 'market_leader'],
                'examples': ['WhatsApp', 'GitHub', 'LinkedIn', 'Figma']
            },
            'platform_play': {
                'name': 'Shopify/Square Path',
                'description': 'Ecosystem expansion drives exponential value',
                'probability_factors': ['platform_revenue > 30%', 'developer_ecosystem', 'network_effects'],
                'examples': ['Shopify', 'Square', 'Twilio', 'Stripe']
            },
            'distressed_turnaround': {
                'name': 'Uber/WeWork Path',
                'description': 'High burn, needs restructuring, may recover',
                'probability_factors': ['burn_rate_high', 'market_leader', 'recap_likely'],
                'examples': ['Uber (2016)', 'WeWork', 'Blue Apron', 'Casper']
            },
            'zombie_walker': {
                'name': 'Living Dead Path',
                'description': 'Flat growth, can\'t raise, can\'t sell, won\'t die',
                'probability_factors': ['growth < 20%', 'burn_controlled', 'niche_market'],
                'examples': ['Many Series B/C companies you\'ve never heard of']
            },
            'acquihire': {
                'name': 'Talent Acquisition',
                'description': 'Tech/team value only, business model failed',
                'probability_factors': ['elite_team', 'failed_pmf', 'strategic_tech'],
                'examples': ['Lala → Apple', 'Parakey → Facebook', 'FriendFeed → Facebook']
            }
        }
        
    def generate_intelligent_scenarios(self, company_profile: Dict) -> List[Dict]:
        """
        Generate scenarios based on which archetype paths are most likely
        """
        scenarios = []
        
        # Assess fit for each archetype
        archetype_fits = self._assess_archetype_fit(company_profile)
        
        # Generate probability distribution (NOT Gaussian!)
        probabilities = self._calculate_path_probabilities(archetype_fits, company_profile)
        
        # Create detailed scenarios for each viable path
        scenario_id = 1
        for archetype, data in self.outcome_archetypes.items():
            if probabilities[archetype] > 0.01:  # >1% chance
                
                # Generate multiple sub-scenarios within each archetype
                sub_scenarios = self._generate_archetype_scenarios(
                    archetype, 
                    data,
                    probabilities[archetype],
                    company_profile
                )
                
                for sub in sub_scenarios:
                    scenarios.append({
                        'id': scenario_id,
                        'archetype': archetype,
                        'name': sub['name'],
                        'probability': sub['probability'],
                        'value': sub['value'],
                        'time_to_exit': sub['time'],
                        'key_assumptions': sub['assumptions'],
                        'comparable_exits': sub['comparables'],
                        'confidence': sub['confidence']
                    })
                    scenario_id += 1
        
        return scenarios
    
    def _assess_archetype_fit(self, company: Dict) -> Dict[str, float]:
        """
        Score how well company fits each archetype (0-100)
        """
        fits = {}
        
        # Fast Grower fit
        fast_grower_score = 0
        if company.get('growth_rate', 0) > 1.0:  # >100%
            fast_grower_score += 40
        if company.get('net_revenue_retention', 1.0) > 1.3:  # >130%
            fast_grower_score += 30
        if company.get('gross_margin', 0.7) > 0.75:  # >75%
            fast_grower_score += 20
        if company.get('market_position') == 'leader':
            fast_grower_score += 10
        fits['fast_grower'] = fast_grower_score
        
        # Steady Builder fit
        steady_builder_score = 0
        rule_of_40 = (company.get('growth_rate', 0.3) * 100) + (company.get('ebitda_margin', -0.2) * 100)
        if rule_of_40 > 50:
            steady_builder_score += 40
        if company.get('cac_payback_months', 12) < 12:
            steady_builder_score += 30
        if company.get('customer_count', 0) > 1000:
            steady_builder_score += 20
        if company.get('churn_rate', 0.1) < 0.05:
            steady_builder_score += 10
        fits['steady_builder'] = steady_builder_score
        
        # Pivot Winner fit (harder to detect)
        pivot_winner_score = 0
        if company.get('pivot_history', False):
            pivot_winner_score += 50
        if company.get('viral_coefficient', 1.0) > 1.5:
            pivot_winner_score += 30
        if company.get('category_creator', False):
            pivot_winner_score += 20
        fits['pivot_winner'] = pivot_winner_score
        
        # Acquisition Target fit
        acquisition_score = 0
        if len(company.get('potential_acquirers', [])) > 3:
            acquisition_score += 40
        if company.get('strategic_value_score', 0) > 80:
            acquisition_score += 30
        if company.get('unique_tech_patents', 0) > 5:
            acquisition_score += 20
        if company.get('market_share', 0) > 0.3:  # >30% share
            acquisition_score += 10
        fits['acquisition_target'] = acquisition_score
        
        # Platform Play fit
        platform_score = 0
        if company.get('platform_revenue_pct', 0) > 0.3:
            platform_score += 40
        if company.get('developer_count', 0) > 1000:
            platform_score += 30
        if company.get('api_calls_billions', 0) > 1:
            platform_score += 20
        if company.get('ecosystem_gmv_multiple', 1) > 10:
            platform_score += 10
        fits['platform_play'] = platform_score
        
        # Distressed fit (negative signals)
        distressed_score = 0
        if company.get('runway_months', 12) < 6:
            distressed_score += 40
        if company.get('burn_multiple', 1) > 3:  # Burning $3 for every $1 of ARR
            distressed_score += 30
        if company.get('failed_fundraise', False):
            distressed_score += 20
        if company.get('founder_departed', False):
            distressed_score += 10
        fits['distressed_turnaround'] = distressed_score
        
        # Zombie fit
        zombie_score = 0
        if 0.1 < company.get('growth_rate', 0.3) < 0.2:  # 10-20% growth
            zombie_score += 40
        if company.get('years_since_funding', 0) > 3:
            zombie_score += 30
        if company.get('acquisition_attempts_failed', 0) > 2:
            zombie_score += 20
        if company.get('market_position') == 'also-ran':
            zombie_score += 10
        fits['zombie_walker'] = zombie_score
        
        # Acquihire fit
        acquihire_score = 0
        if company.get('team_pedigree_score', 50) > 80:
            acquihire_score += 40
        if company.get('revenue', 10) < 2:  # <$2M revenue
            acquihire_score += 30
        if company.get('patents_filed', 0) > 3:
            acquihire_score += 20
        if company.get('pmf_achieved', True) == False:
            acquihire_score += 10
        fits['acquihire'] = acquihire_score
        
        return fits
    
    def _calculate_path_probabilities(self, fits: Dict[str, float], company: Dict) -> Dict[str, float]:
        """
        Convert fit scores to probabilities using market data
        NOT Gaussian - based on actual historical outcomes
        """
        
        # Base rates from historical data (these would come from your database)
        historical_rates = {
            'fast_grower': 0.02,      # 2% become rockets
            'steady_builder': 0.15,    # 15% build steadily  
            'pivot_winner': 0.03,      # 3% pivot successfully
            'acquisition_target': 0.20, # 20% get acquired well
            'platform_play': 0.05,     # 5% become platforms
            'distressed_turnaround': 0.15, # 15% struggle but may recover
            'zombie_walker': 0.25,     # 25% become zombies
            'acquihire': 0.15          # 15% acquihired
        }
        
        # Adjust base rates by fit scores
        probabilities = {}
        for archetype, base_rate in historical_rates.items():
            fit_score = fits[archetype] / 100  # 0-1 scale
            
            # Use logistic function to map fit to probability adjustment
            # High fit can increase probability up to 3x
            # Low fit can decrease down to 0.3x
            adjustment = 0.3 + (2.7 / (1 + np.exp(-5 * (fit_score - 0.5))))
            
            probabilities[archetype] = base_rate * adjustment
        
        # Normalize to sum to 1.0
        total = sum(probabilities.values())
        return {k: v/total for k, v in probabilities.items()}
    
    def _generate_archetype_scenarios(self, archetype: str, data: Dict, 
                                    base_probability: float, company: Dict) -> List[Dict]:
        """
        Generate 5-10 scenarios within each archetype
        These represent the distribution WITHIN the path
        """
        scenarios = []
        
        if archetype == 'fast_grower':
            # Fast growers have wide outcome distribution
            variants = [
                ('Conservative', 0.4, 0.7),   # 40% chance, 70% of best case
                ('Expected', 0.3, 1.0),        # 30% chance, base case
                ('Optimistic', 0.2, 1.5),      # 20% chance, 150% of base
                ('Moonshot', 0.1, 3.0),        # 10% chance, 3x base
            ]
            
            base_multiple = 50 * (1 + company.get('growth_rate', 0.5))
            
        elif archetype == 'acquisition_target':
            # Acquisitions cluster around strategic value
            variants = [
                ('Quick Exit', 0.3, 0.6),      # Fast but lower price
                ('Competitive Bid', 0.4, 1.0),  # Normal process
                ('Bidding War', 0.2, 1.5),      # Multiple bidders
                ('Strategic Premium', 0.1, 2.5), # Must-have asset
            ]
            
            base_multiple = 20 * (1 + len(company.get('potential_acquirers', [])) * 0.1)
            
        # ... similar for other archetypes
        
        revenue = company.get('revenue', 10)
        
        for variant_name, variant_prob, variant_mult in variants:
            exit_value = revenue * base_multiple * variant_mult
            
            scenarios.append({
                'name': f"{data['name']} - {variant_name}",
                'probability': base_probability * variant_prob,
                'value': exit_value,
                'time': self._estimate_time_to_exit(archetype, company),
                'assumptions': self._generate_assumptions(archetype, variant_name, company),
                'comparables': self._find_comparables(archetype, exit_value, company),
                'confidence': self._calculate_confidence(company, archetype)
            })
        
        return scenarios
    
    def _estimate_time_to_exit(self, archetype: str, company: Dict) -> float:
        """
        Time to exit varies by archetype and company stage
        """
        base_times = {
            'fast_grower': 3.0,
            'steady_builder': 5.0,
            'pivot_winner': 4.0,
            'acquisition_target': 2.5,
            'platform_play': 6.0,
            'distressed_turnaround': 1.5,
            'zombie_walker': 7.0,
            'acquihire': 1.0
        }
        
        base = base_times.get(archetype, 4.0)
        
        # Adjust for stage
        stage = company.get('stage', 'Series A')
        stage_multipliers = {
            'Seed': 1.5,
            'Series A': 1.2,
            'Series B': 1.0,
            'Series C+': 0.8
        }
        
        return base * stage_multipliers.get(stage, 1.0)
    
    def _generate_assumptions(self, archetype: str, variant: str, company: Dict) -> List[str]:
        """
        Generate specific assumptions for each scenario
        """
        assumptions = []
        
        if archetype == 'fast_grower':
            assumptions.extend([
                f"Maintains {int(company.get('growth_rate', 0.5) * 100)}%+ growth rate",
                f"NRR stays above {int(company.get('net_revenue_retention', 1.2) * 100)}%",
                "Successfully scales GTM internationally",
                "No major competitive threats emerge"
            ])
            
        elif archetype == 'acquisition_target':
            acquirers = company.get('potential_acquirers', [])
            if acquirers:
                assumptions.append(f"{acquirers[0]} or similar makes strategic move")
            assumptions.extend([
                "Strategic value recognized by buyers",
                "Clean due diligence process",
                "Favorable M&A environment"
            ])
            
        # Add variant-specific assumptions
        if variant == 'Moonshot':
            assumptions.append("Achieves category-defining breakthrough")
        elif variant == 'Bidding War':
            assumptions.append("Multiple strategic buyers compete")
            
        return assumptions
    
    def _find_comparables(self, archetype: str, exit_value: float, company: Dict) -> List[str]:
        """
        Find real comparable exits
        This would query your database of actual exits
        """
        # Placeholder - would query real data
        if archetype == 'fast_grower' and exit_value > 5000:
            return ['Snowflake ($12.4B IPO)', 'Datadog ($10.9B IPO)', 'Zoom ($9.2B IPO)']
        elif archetype == 'acquisition_target' and exit_value > 1000:
            return ['Slack ($27.7B to Salesforce)', 'GitHub ($7.5B to Microsoft)']
        else:
            return ['Multiple precedent transactions in range']
    
    def _calculate_confidence(self, company: Dict, archetype: str) -> float:
        """
        How confident are we in this scenario?
        Based on data quality and precedents
        """
        confidence = 0.5  # Base confidence
        
        # More data = more confidence
        if company.get('years_of_data', 1) > 3:
            confidence += 0.2
            
        # Clear comparables = more confidence  
        if company.get('clear_comps_count', 0) > 5:
            confidence += 0.15
            
        # Market leader = more confidence
        if company.get('market_position') == 'leader':
            confidence += 0.15
            
        return min(0.95, confidence)  # Cap at 95%