"""
Dynamic Scenario Generator
Creates real-time simulations based on today's market events
"""

import random
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass 
class MarketEvent:
    """Real-time market event"""
    date: datetime
    company: str
    event_type: str  # IPO, acquisition, funding, shutdown
    value: float
    details: Dict

class DynamicScenarioGenerator:
    """
    Generate scenarios based on what's happening TODAY in the market
    """
    
    def __init__(self):
        # This would connect to real news feeds
        # For now, we'll simulate with recent events
        self.recent_events = []
        self.market_momentum = {}
        
    def generate_figma_inspired_scenarios(self, company_data: Dict, 
                                        today_event: str = "Figma IPO'd at $15B") -> List[Dict]:
        """
        Generate scenarios inspired by today's Figma IPO
        Example: "If Figma IPO'd today at $15B, what does that mean for [your company]?"
        """
        
        scenarios = []
        
        # Parse today's event
        if "Figma" in today_event and "IPO" in today_event:
            # Extract valuation
            import re
            value_match = re.search(r'\$(\d+)B', today_event)
            figma_valuation = float(value_match.group(1)) * 1_000_000_000 if value_match else 15_000_000_000
            
            # Figma's metrics (approximate)
            figma_arr = 400_000_000  # ~$400M ARR
            figma_multiple = figma_valuation / figma_arr  # ~37.5x
            
            # How does this affect YOUR company?
            your_arr = company_data.get('arr', 50_000_000)
            your_sector = company_data.get('sector', 'SaaS')
            
            # Scenario 1: The Figma Comp
            if your_sector in ['Design', 'Collaboration', 'Creative Tools']:
                scenarios.append({
                    'id': 'figma_comp_boost',
                    'title': 'The Figma Comparable Boost',
                    'narrative': f"""
                    Figma's {figma_multiple:.1f}x ARR multiple at IPO today creates a new benchmark.
                    Your {your_sector} company with ${your_arr/1e6:.0f}M ARR could argue for similar multiples.
                    
                    Investment banker pitch: "Figma proves design tools command premium multiples. 
                    At even half their multiple ({figma_multiple/2:.1f}x), you're worth ${your_arr * figma_multiple/2 / 1e9:.1f}B"
                    """,
                    'probability': 0.15,
                    'exit_value': your_arr * (figma_multiple * 0.6),  # 60% of Figma multiple
                    'timeline': '12-18 months',
                    'trigger': "Figma IPO creates new comp set"
                })
            
            # Scenario 2: The Adobe Defensive Response
            scenarios.append({
                'id': 'adobe_defensive',
                'title': 'Adobe\'s Defensive Shopping Spree',
                'narrative': f"""
                Adobe lost Figma (antitrust killed the $20B deal). Now they're shopping again.
                With Figma public at ${figma_valuation/1e9:.0f}B, Adobe needs to respond.
                
                Your {your_sector} tools look attractive. Adobe offers {25 if your_arr < 100_000_000 else 15}x ARR.
                They learned their lesson: move fast, close quick, avoid antitrust.
                """,
                'probability': 0.08,
                'exit_value': your_arr * (25 if your_arr < 100_000_000 else 15),
                'timeline': '6-9 months',
                'trigger': "Adobe needs Figma alternative"
            })
            
            # Scenario 3: The IPO Window Opens
            scenarios.append({
                'id': 'ipo_window_opens',
                'title': 'Figma Opens the IPO Window',
                'narrative': f"""
                Figma's successful IPO (up 45% on day one!) signals the IPO window is OPEN.
                Every growth board meeting this week: "If Figma can IPO at {figma_multiple:.0f}x, why can't we?"
                
                Your metrics: ${your_arr/1e6:.0f}M ARR, {company_data.get('growth_rate', 0.5)*100:.0f}% growth
                Banker math: At {figma_multiple * 0.4:.0f}x (sector discount), you IPO at ${your_arr * figma_multiple * 0.4 / 1e9:.1f}B
                
                The catch: You need to move fast. IPO windows close quickly.
                """,
                'probability': 0.12,
                'exit_value': your_arr * (figma_multiple * 0.4),
                'timeline': '9-12 months',
                'trigger': "IPO window momentum"
            })
        
        # Add market-specific reactions
        scenarios.extend(self._generate_market_reactions(company_data, today_event))
        
        return scenarios
    
    def generate_today_inspired_scenarios(self, company_data: Dict) -> List[Dict]:
        """
        Generate scenarios based on TODAY's actual market events
        This would pull from real news APIs
        """
        
        # Simulate today's events (would be real API)
        todays_events = self._get_todays_market_events()
        
        scenarios = []
        
        for event in todays_events:
            if event.event_type == 'ipo':
                scenarios.extend(self._generate_ipo_inspired_scenarios(company_data, event))
            elif event.event_type == 'acquisition':
                scenarios.extend(self._generate_acquisition_inspired_scenarios(company_data, event))
            elif event.event_type == 'shutdown':
                scenarios.extend(self._generate_shutdown_inspired_scenarios(company_data, event))
        
        return scenarios
    
    def _get_todays_market_events(self) -> List[MarketEvent]:
        """
        In production, this would hit news APIs
        For now, simulate recent events
        """
        
        # Simulated events (would be real-time)
        events = [
            MarketEvent(
                date=datetime.now(),
                company='Figma',
                event_type='ipo',
                value=15_000_000_000,
                details={'multiple': 37.5, 'arr': 400_000_000, 'pop': 0.45}
            ),
            MarketEvent(
                date=datetime.now() - timedelta(days=1),
                company='Klaviyo',
                event_type='ipo',
                value=9_000_000_000,
                details={'multiple': 11, 'arr': 820_000_000, 'pop': -0.08}
            ),
            MarketEvent(
                date=datetime.now() - timedelta(days=3),
                company='Cisco',
                event_type='acquisition',
                value=28_000_000_000,
                details={'target': 'Splunk', 'multiple': 8, 'strategic': True}
            )
        ]
        
        return events
    
    def _generate_ipo_inspired_scenarios(self, company_data: Dict, 
                                        ipo_event: MarketEvent) -> List[Dict]:
        """
        Generate scenarios based on a recent IPO
        """
        
        scenarios = []
        
        # Calculate relevance to your company
        relevance = self._calculate_market_relevance(company_data, ipo_event)
        
        if relevance > 0.5:  # Relevant comp
            ipo_multiple = ipo_event.details['multiple']
            your_arr = company_data.get('arr', 50_000_000)
            
            # Your IPO scenario influenced by this event
            scenarios.append({
                'id': f'{ipo_event.company.lower()}_comp_ipo',
                'title': f'Following {ipo_event.company}\'s IPO Playbook',
                'narrative': f"""
                {ipo_event.company} just IPO'd at {ipo_multiple}x ARR (${ipo_event.value/1e9:.1f}B).
                {'They popped ' + str(int(ipo_event.details["pop"]*100)) + '% on day one!' if ipo_event.details["pop"] > 0 else 'They dropped ' + str(int(-ipo_event.details["pop"]*100)) + '% - rough start.'}
                
                Your similar profile suggests a {ipo_multiple * relevance:.1f}x multiple.
                IPO value: ${your_arr * ipo_multiple * relevance / 1e9:.2f}B
                
                Key lesson from {ipo_event.company}: {self._extract_ipo_lesson(ipo_event)}
                """,
                'probability': 0.10 * relevance,
                'exit_value': your_arr * ipo_multiple * relevance,
                'timeline': '12-18 months',
                'market_catalyst': f"{ipo_event.company} IPO success"
            })
        
        return scenarios
    
    def _generate_acquisition_inspired_scenarios(self, company_data: Dict,
                                               acq_event: MarketEvent) -> List[Dict]:
        """
        Generate scenarios based on recent acquisitions
        """
        
        scenarios = []
        acquirer = acq_event.company
        target = acq_event.details.get('target', 'Unknown')
        
        # Is the acquirer likely to buy more?
        if acq_event.details.get('strategic', False):
            scenarios.append({
                'id': f'{acquirer.lower()}_follow_on',
                'title': f'{acquirer} Continues Shopping After {target}',
                'narrative': f"""
                {acquirer} just bought {target} for ${acq_event.value/1e9:.1f}B.
                Industry sources say they're not done - building a suite.
                
                Your {company_data.get("sector", "SaaS")} product could complement {target}.
                Expected offer: {acq_event.details["multiple"] * 0.8:.1f}x ARR (slight discount to {target}).
                """,
                'probability': 0.06,
                'exit_value': company_data.get('arr', 50_000_000) * acq_event.details['multiple'] * 0.8,
                'timeline': '6-12 months',
                'market_catalyst': f"{acquirer}-{target} deal creates consolidation"
            })
        
        return scenarios
    
    def _generate_market_reactions(self, company_data: Dict, event: str) -> List[Dict]:
        """
        Generate second-order effects from market events
        """
        
        reactions = []
        
        # The Competitor Panic Buy
        reactions.append({
            'id': 'competitor_panic',
            'title': 'Competitors Panic After Market Move',
            'narrative': f"""
            Today's {event} triggers a chain reaction.
            Your biggest competitor's board emergency meeting: "We can't let them have the whole market!"
            
            Panic offer arrives: {random.randint(60, 80)}% premium to last round.
            Due diligence? Minimal. They need to move FAST.
            """,
            'probability': 0.04,
            'exit_value': company_data.get('last_valuation', 100_000_000) * random.uniform(1.6, 1.8),
            'timeline': '2-3 months',
            'chaos_factor': 'high'
        })
        
        return reactions
    
    def _calculate_market_relevance(self, company: Dict, event: MarketEvent) -> float:
        """
        How relevant is this market event to your company?
        """
        
        relevance = 0.5  # Base relevance
        
        # Sector match
        if company.get('sector') == event.details.get('sector'):
            relevance += 0.3
            
        # Size match (within same order of magnitude)
        if abs(company.get('arr', 0) - event.details.get('arr', 0)) < event.details.get('arr', 1) * 0.5:
            relevance += 0.2
            
        # Growth rate similarity
        if abs(company.get('growth_rate', 0.5) - event.details.get('growth_rate', 0.5)) < 0.2:
            relevance += 0.1
            
        return min(relevance, 1.0)
    
    def _extract_ipo_lesson(self, event: MarketEvent) -> str:
        """
        Extract key lesson from IPO event
        """
        
        if event.details.get('pop', 0) > 0.3:
            return "Price below market appetite - leave money on table for momentum"
        elif event.details.get('pop', 0) < -0.1:
            return "Don't be greedy - market punishes aggressive pricing"
        else:
            return "Fair pricing works - steady gains build confidence"