"""
Narrative-Driven Simulation Engine
Create specific, fun scenarios with real company stories and outcomes
"""

import random
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class SimulationStory:
    """A specific narrative scenario"""
    id: str
    title: str
    protagonist: str  # The acquirer/outcome driver
    narrative: str
    probability: float
    value_drivers: Dict[str, float]
    timeline: str
    key_events: List[str]
    liquidation_impact: str

class NarrativeSimulationEngine:
    """
    Generate specific, story-driven scenarios that make PWERM fun
    """
    
    def __init__(self):
        # Real companies and their acquisition patterns
        self.acquirer_profiles = {
            'Revolut': {
                'sweet_spot': 'Fintech with Gen Z appeal',
                'typical_multiple': '8-12x ARR',
                'recent_moves': ['Acquired crypto exchange', 'Launched Revolut Business'],
                'strategic_needs': ['US market entry', 'Credit products', 'Gen Z engagement'],
                'war_chest': 5_000_000_000
            },
            'Stripe': {
                'sweet_spot': 'Developer-first payment infrastructure',
                'typical_multiple': '15-25x ARR',
                'recent_moves': ['Acquired TaxJar', 'Launched Stripe Capital'],
                'strategic_needs': ['International expansion', 'B2B payments', 'Crypto rails'],
                'war_chest': 10_000_000_000
            },
            'Microsoft': {
                'sweet_spot': 'B2B SaaS with enterprise distribution',
                'typical_multiple': '10-20x ARR',
                'recent_moves': ['GitHub $7.5B', 'Activision $69B', 'Nuance $19.7B'],
                'strategic_needs': ['AI capabilities', 'Developer tools', 'Vertical SaaS'],
                'war_chest': 100_000_000_000
            },
            'Salesforce': {
                'sweet_spot': 'CRM-adjacent with data moat',
                'typical_multiple': '12-18x ARR',
                'recent_moves': ['Slack $27.7B', 'Tableau $15.7B', 'MuleSoft $6.5B'],
                'strategic_needs': ['AI/automation', 'Industry clouds', 'Developer platform'],
                'war_chest': 30_000_000_000
            }
        }
        
    def generate_cleo_simulations(self, cleo_data: Dict, cap_table: Dict) -> List[SimulationStory]:
        """
        Generate specific narrative simulations for Cleo AI
        Using real ARR: $134M official, $284M per founder
        """
        simulations = []
        
        # Simulation 1: Revolut Breaking Their Rules
        revolut_scenario = SimulationStory(
            id='revolut_breaks_rules',
            title='Revolut Breaks "All In-House" Rule for Cleo',
            protagonist='Revolut',
            narrative="""
            After years of building everything in-house, Revolut's board finally convinces 
            Nik Storonsky that acquiring Cleo is cheaper than building competing Gen Z features.
            
            The trigger? Cleo's viral "Roast Mode" drives 2M new users in Q1 2024, with 65% 
            under 25 - exactly Revolut's target demo. Barney pitches directly to Nik: "You're 
            spending $200M/year on Gen Z acquisition. We convert at 3x your rate."
            
            Revolut offers $1.2B (4.2x official ARR, but really 2x actual ARR). The kicker? 
            They want Cleo's team to run ALL of Revolut's consumer AI.
            """,
            probability=0.15,  # 15% - Revolut rarely acquires
            value_drivers={
                'strategic_fit': 0.9,
                'culture_clash': 0.3,  # Big risk
                'revenue_multiple': 4.2,
                'actual_multiple': 2.0  # Based on real $284M ARR
            },
            timeline='9-12 months',
            key_events=[
                'Q1 2024: Cleo hits 10M users, "Roast Mode" goes viral on TikTok',
                'Q2 2024: Revolut loses 500k Gen Z users to Cleo',
                'Q3 2024: Secret meetings in London, Nik flies to SF',
                'Q4 2024: Deal announced at $1.2B, Barney joins as Chief AI Officer'
            ],
            liquidation_impact=self._calculate_revolut_liquidation(1_200_000_000, cap_table)
        )
        simulations.append(revolut_scenario)
        
        # Simulation 2: The Stripe Developer Play
        stripe_scenario = SimulationStory(
            id='stripe_api_vision',
            title='Stripe\'s "Emotional Banking API" Vision',
            protagonist='Stripe',
            narrative="""
            Patrick Collison has a vision: What if every app could have Cleo-like financial 
            coaching? Stripe acquires Cleo for $3.5B to launch "Stripe Advisor" - emotional 
            AI for any fintech.
            
            The narrative: "We made payments invisible. Now we'll make financial advice invisible 
            too." Cleo's personality engine becomes an API. Imagine Robinhood with Cleo sass, 
            or Coinbase with Cleo's budgeting.
            
            Plot twist: Cleo's consumer app stays independent, now powered by Stripe's 50M 
            merchant network for cashback and rewards.
            """,
            probability=0.08,  # 8% - Stripe is selective
            value_drivers={
                'strategic_fit': 0.95,
                'platform_potential': 1.0,
                'revenue_multiple': 12.3,
                'developer_adoption': 0.8
            },
            timeline='6-8 months',
            key_events=[
                'Month 1: Patrick tweets "What if your app could roast users\' spending?"',
                'Month 3: Stripe launches "Project Personality" internally',
                'Month 5: Cleo demos API version to Stripe leadership',
                'Month 7: $3.5B deal, largest fintech API acquisition ever'
            ],
            liquidation_impact=self._calculate_stripe_liquidation(3_500_000_000, cap_table)
        )
        simulations.append(stripe_scenario)
        
        # Simulation 3: The TikTok Financial Super App
        tiktok_scenario = SimulationStory(
            id='tiktok_fintech_move',
            title='TikTok Launches Finance with $2.8B Cleo Acquisition',
            protagonist='TikTok/ByteDance',
            narrative="""
            ByteDance shocks everyone by acquiring Cleo to launch TikTok Finance. The logic? 
            They have 150M Gen Z users in the US alone - why let banks monetize them?
            
            Cleo's "Roast Mode" already has 50M views on TikTok. ByteDance realizes Cleo 
            has cracked the code: making finance entertaining. Integration is seamless - 
            swipe up on any TikTok to see what Cleo thinks of that purchase.
            
            US regulators go crazy, but ByteDance structures it through a Singapore entity. 
            Cleo becomes the first fintech unicorn to exit to social media.
            """,
            probability=0.05,  # 5% - Regulatory nightmare but massive strategic fit
            value_drivers={
                'user_overlap': 0.95,  # Huge Gen Z overlap
                'regulatory_risk': 0.8,  # High risk
                'revenue_multiple': 9.9,
                'viral_potential': 1.0
            },
            timeline='12-18 months',
            key_events=[
                'Month 2: ByteDance hires Goldman Sachs for fintech strategy',
                'Month 6: Cleo TikTok integration test in UK goes viral',
                'Month 10: CFIUS review begins, intense lobbying',
                'Month 14: Deal clears with conditions, $2.8B price tag'
            ],
            liquidation_impact=self._calculate_tiktok_liquidation(2_800_000_000, cap_table)
        )
        simulations.append(tiktok_scenario)
        
        # Simulation 4: The Klarna Survival Acquisition
        klarna_scenario = SimulationStory(
            id='klarna_defensive_move',
            title='Klarna\'s Defensive Play: $800M for Cleo',
            protagonist='Klarna',
            narrative="""
            Klarna's valuation crashed from $46B to $6.7B. They need a Gen Z win desperately. 
            Sebastian Siemiatkowski makes a bold move: acquire Cleo for $800M (mostly stock).
            
            The synergy is obvious: Klarna helps you buy, Cleo helps you budget. But the real 
            reason? Cleo's 85% US user base. Klarna trades at 2x ARR, so paying 3x for Cleo's 
            US growth actually makes sense.
            
            Plot twist: Cleo's founders negotiate for 15% of combined company, betting Klarna 
            recovers to $20B+. If they're right, it's a $3B outcome.
            """,
            probability=0.12,  # 12% - Klarna needs this
            value_drivers={
                'desperation_factor': 0.8,
                'stock_upside': 3.0,  # If Klarna recovers
                'revenue_multiple': 2.8,
                'synergy_score': 0.9
            },
            timeline='4-6 months',
            key_events=[
                'Month 1: Klarna Q4 results disappoint, stock craters',
                'Month 2: Emergency board meeting, "Buy growth" strategy',
                'Month 3: Cleo-Klarna pilot in UK shows 40% cross-sell',
                'Month 5: All-stock deal at $800M current value'
            ],
            liquidation_impact=self._calculate_klarna_liquidation(800_000_000, cap_table)
        )
        simulations.append(klarna_scenario)
        
        # Simulation 5: The IPO Attempt That Becomes PE
        pe_scenario = SimulationStory(
            id='failed_ipo_to_pe',
            title='From IPO Dreams to Vista Equity Reality',
            protagonist='Vista Equity Partners',
            narrative="""
            Cleo files S-1 at $300M ARR, targeting $5B IPO. But the market tanks - fintech 
            multiples collapse to 3-4x. The roadshow flops. Banks suggest $2B valuation.
            
            Enter Vista Equity. They see Cleo's 70% gross margins and Rule of 40 score of 65. 
            Their offer: $2.2B take-private. "We'll optimize for 3 years, then sell to Microsoft 
            for $8B." Robert Smith personally calls Barney.
            
            The liquidation stack makes this painful - Series C investors barely break even. 
            But it's better than a broken IPO at $1.5B.
            """,
            probability=0.18,  # 18% - PE loves profitable SaaS
            value_drivers={
                'market_timing': 0.3,  # Bad IPO window
                'operational_improvement': 0.9,
                'revenue_multiple': 7.3,
                'exit_multiple_target': 20.0  # In 3 years
            },
            timeline='3-4 months post S-1',
            key_events=[
                'Month 1: S-1 filed, targeting $5B at 17x ARR',
                'Month 2: Fed raises rates, SaaS multiples crash 40%',
                'Month 3: Roadshow feedback devastating, considering pulling IPO',
                'Month 4: Vista swoops with $2.2B binding offer'
            ],
            liquidation_impact=self._calculate_pe_liquidation(2_200_000_000, cap_table)
        )
        simulations.append(pe_scenario)
        
        # Simulation 6: The LSE IPO - Breaking the Duck but Diving
        lse_ipo_scenario = SimulationStory(
            id='lse_ipo_dive',
            title='LSE IPO: Breaking the Duck, Then the Hearts',
            protagonist='Public Markets',
            narrative="""
            Cleo becomes the first major fintech IPO on the LSE in 3 years, "breaking the duck."
            UK government celebrates - finally, a British tech champion staying home!
            
            IPO prices at £16/share, £2.8B valuation (9.9x ARR). Opening bell: shoots to £19!
            Then reality hits. US investors can't buy (liquidity concerns). UK pension funds 
            think fintech = crypto = bad. By close, it's £12. Market cap: £2.1B.
            
            The real pain? 180-day lockup. Founders watch their paper wealth drop 25% daily.
            Employee morale crashes harder than the stock. The Slack channel goes silent.
            
            Silver lining: At £2.1B, early investors still make money. But Series C? 
            They're underwater, plotting secondary sales the minute lockup expires.
            """,
            probability=0.22,  # 22% - LSE desperate for tech IPOs
            value_drivers={
                'ipo_discount': 0.25,  # 25% day-one drop
                'liquidity_penalty': 0.15,  # LSE vs NASDAQ
                'revenue_multiple': 7.4,  # Down from 9.9 at pricing
                'uk_market_sentiment': 0.6
            },
            timeline='6-8 months',
            key_events=[
                'Month 1: UK Treasury personally calls Barney about "British champion"',
                'Month 3: Roadshow - London loves it, NYC skeptical',
                'Month 5: Prices at top of range due to UK institutional demand',
                'IPO Day: Opens +18%, closes -25%, Reddit goes wild',
                'Month 8: Lockup expires, Series C dumps 40% of holdings'
            ],
            liquidation_impact=self._calculate_ipo_liquidation(2_100_000_000, cap_table, 'LSE')
        )
        simulations.append(lse_ipo_scenario)
        
        # Add more creative scenarios...
        return simulations
    
    def _calculate_revolut_liquidation(self, exit_value: float, cap_table: Dict) -> str:
        """Calculate specific liquidation story for Revolut scenario"""
        
        # Get actual cap table data
        total_raised = cap_table.get('total_raised', 133_000_000)
        series_c_price = cap_table.get('series_c_price', 500_000_000)
        
        return f"""
        At $1.2B exit, here's how the cookie crumbles:
        
        • Series C ($70M at $500M) → 2.4x return, $168M back
        • Series B ($28M at $180M) → 6.7x return, $187M back  
        • Series A ($20M at $60M) → 20x return, $400M back
        • Seed ($5M at $15M) → 80x return, $400M back
        
        But wait! Series C has 1.5x liquidation preference. They take $105M first.
        
        Founders (25% diluted ownership) get $185M. Not bad, but they left $2B+ on 
        the table by selling early. Classic fintech infrastructure vs consumer app valuation gap.
        """
    
    def _calculate_stripe_liquidation(self, exit_value: float, cap_table: Dict) -> str:
        return f"""
        The $3.5B Stripe outcome - here's where it gets spicy:
        
        • Liquidation preferences: $133M total (all 1x non-participating)
        • After preferences, $3.367B to distribute pro-rata
        
        Series C investors celebrate - 7x in 2 years. But the real winners? 
        Seed investors with 233x returns. The €4.5M they put in returns €1.05B.
        
        Twist: Employees with early options make $400M combined. Three engineers 
        who joined in 2019 each clear $15M. Cleo's Slack channel crashes from 
        champagne emojis.
        
        Barney's take: 18% final ownership = $630M. He buys the London pub where 
        he wrote Cleo's first line of code.
        """
    
    def _calculate_tiktok_liquidation(self, exit_value: float, cap_table: Dict) -> str:
        return f"""
        TikTok's $2.8B deal - complicated by ByteDance stock component:
        
        • 60% cash ($1.68B) distributed immediately
        • 40% ByteDance RSUs ($1.12B) with 4-year vest
        
        Liquidation waterfall on cash portion:
        - Preferences paid: $133M ✓
        - Remaining $1.547B distributed pro-rata
        
        Plot twist: ByteDance goes public in 2026 at $500B valuation. 
        Those RSUs double. Series A's $20M investment returns $580M total.
        
        One early employee tweets: "Joined for the roast mode jokes, 
        stayed for the ByteDance equity 📈"
        """
    
    def _calculate_klarna_liquidation(self, exit_value: float, cap_table: Dict) -> str:
        return f"""
        Klarna's $800M mostly-stock deal - the hedge fund's nightmare:
        
        • $200M cash (pays preferences with $67M left over)
        • $600M in Klarna stock at $6.7B valuation
        
        Series C barely breaks even at 1.14x. They're furious until...
        
        Plot twist 2026: Klarna IPOs at $25B. That $600M in stock? 
        Now worth $2.2B. Total outcome: $2.4B vs initial $800M = 3x.
        
        Lesson: Sometimes the worst deal becomes the best deal. 
        Series C partner goes from zero to hero at Monday partners meeting.
        
        Barney's quote to TechCrunch: "We bet on Sebastian. Turns out 
        Swedish persistence > British sass 🇸🇪"
        """
    
    def _calculate_pe_liquidation(self, exit_value: float, cap_table: Dict) -> str:
        return f"""
        Vista's $2.2B take-private - the "optimize and flip" special:
        
        Immediate liquidation:
        • Series C ($70M pref) → 3.14x, just okay
        • Series B ($28M pref) → 7.9x, decent
        • Common/founders → diluted but liquid
        
        The Vista playbook:
        Year 1: Cut burn by 40%, improve margins to 82%
        Year 2: Acquire 3 small competitors, add enterprise tier  
        Year 3: ARR hits $580M, Rule of 40 score: 95
        
        2027 exit to Microsoft at $8B:
        • Management keeps 15% for hitting targets = $1.2B
        • Original Series A's $20M is now worth $295M (14.75x)
        
        Cleo engineers watching from their new startups: "Should've 
        held through the PE years 😭"
        """
    
    def _calculate_ipo_liquidation(self, exit_value: float, cap_table: Dict, exchange: str = 'NASDAQ') -> str:
        """Calculate returns for IPO scenarios - no liquidation preferences"""
        
        # Extract funding rounds from cap table
        rounds = cap_table.get('funding_rounds', [])
        total_shares = cap_table.get('total_shares', 100_000_000)
        
        # Calculate price per share at exit
        share_price = exit_value / total_shares
        
        # Build return story
        story_lines = [f"{exchange} IPO at ${exit_value/1e9:.1f}B - conversion to common:\n"]
        
        # Calculate returns for each round
        for round_data in rounds:
            round_name = round_data.get('round_name', 'Unknown')
            investment = round_data.get('amount_raised', 0)
            shares = round_data.get('shares_issued', 0)
            
            if shares > 0 and investment > 0:
                proceeds = shares * share_price
                multiple = proceeds / investment
                
                emoji = "🚀" if multiple > 50 else "💰" if multiple > 20 else "📈" if multiple > 10 else "😐"
                story_lines.append(f"• {round_name} (${investment/1e6:.0f}M → ${proceeds/1e6:.0f}M): {multiple:.1f}x return {emoji}")
        
        # Add founder/employee portions
        founder_pct = cap_table.get('founder_ownership', 0.20)
        employee_pct = cap_table.get('employee_pool', 0.10)
        
        story_lines.append(f"\n• Founders ({founder_pct*100:.0f}%): ${exit_value * founder_pct / 1e6:.0f}M")
        story_lines.append(f"• Employees ({employee_pct*100:.0f}% pool): ${exit_value * employee_pct / 1e6:.0f}M")
        
        # Add exchange-specific color
        if exchange == 'LSE':
            story_lines.append("\nLSE Reality: Lower liquidity, UK pension funds skeptical of tech")
        elif exchange == 'NASDAQ':
            story_lines.append("\nNASDAQ Premium: Deep liquidity, tech-savvy investors")
        
        return '\n'.join(story_lines)
    
    def generate_simulation_variations(self, base_story: SimulationStory, 
                                     market_conditions: Dict) -> List[SimulationStory]:
        """
        Generate variations of each story based on market conditions
        """
        variations = []
        
        if market_conditions['sentiment'] == 'hot':
            # Hot market - higher multiples, competitive dynamics
            hot_variation = self._create_hot_market_variation(base_story)
            variations.append(hot_variation)
            
        elif market_conditions['sentiment'] == 'cold':
            # Cold market - lower multiples, distressed dynamics
            cold_variation = self._create_cold_market_variation(base_story)
            variations.append(cold_variation)
            
        # Add black swan variations
        if random.random() < 0.05:  # 5% chance
            black_swan = self._create_black_swan_variation(base_story)
            variations.append(black_swan)
            
        return variations
    
    def _create_hot_market_variation(self, story: SimulationStory) -> SimulationStory:
        """In hot markets, everything is a bidding war"""
        
        hot_story = SimulationStory(
            id=f"{story.id}_hot_market",
            title=f"{story.title} (Bidding War Edition)",
            protagonist=story.protagonist,
            narrative=story.narrative + "\n\nBUT THEN: Competing bids emerge! " +
                     "The price jumps 40% in final negotiations.",
            probability=story.probability * 0.7,  # Less likely but possible
            value_drivers={**story.value_drivers, 'competition_multiplier': 1.4},
            timeline="3-4 months (accelerated)",
            key_events=story.key_events + ["Final week: 3 competing bids, board drama"],
            liquidation_impact=self._recalculate_hot_market_impact(story)
        )
        
        return hot_story
    
    def _create_cold_market_variation(self, story: SimulationStory) -> SimulationStory:
        """In cold markets, buyers have leverage"""
        
        cold_story = SimulationStory(
            id=f"{story.id}_cold_market",
            title=f"{story.title} (Winter is Here)",
            protagonist=story.protagonist,
            narrative=story.narrative + "\n\nREALITY CHECK: Market conditions force " +
                     "a 30% haircut. Take it or face down round.",
            probability=story.probability * 1.5,  # More likely in bad markets
            value_drivers={**story.value_drivers, 'market_discount': 0.7},
            timeline="8-12 months (drawn out)",
            key_events=story.key_events + ["Month 6: Deal almost dies twice"],
            liquidation_impact=self._recalculate_cold_market_impact(story)
        )
        
        return cold_story
    
    def _create_black_swan_variation(self, story: SimulationStory) -> SimulationStory:
        """The crazy 1% scenarios that actually happen"""
        
        black_swans = [
            "Apple acquires just for the Roast Mode IP",
            "Cleo AI becomes sentient, negotiates its own sale",
            "Elon tweets about Cleo, valuation 10x overnight",
            "EU bans financial AI, emergency US-only sale"
        ]
        
        return SimulationStory(
            id=f"{story.id}_black_swan",
            title=f"Black Swan: {random.choice(black_swans)}",
            protagonist="Chaos",
            narrative="Nobody saw this coming...",
            probability=0.01,
            value_drivers={'chaos_factor': random.uniform(0.1, 10.0)},
            timeline="48 hours",
            key_events=["Hour 1: Tweet", "Hour 24: Chaos", "Hour 48: Deal"],
            liquidation_impact="All models break. Lawyers cry. Founders buy islands."
        )