"""
Comprehensive Deal Analyzer - Combines all analysis for investment decision
Integrates: AI Impact, Fund Fit, Cap Table, Liquidation Preferences, Exit Scenarios
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.advanced_cap_table import CapTableCalculator
from app.services.company_scoring_visualizer import CompanyScoringVisualizer
from app.services.ownership_return_analyzer import OwnershipReturnAnalyzer
from app.services.citation_manager import CitationManager

logger = logging.getLogger(__name__)


@dataclass
class DealComparison:
    """Complete deal analysis for investment decision"""
    company_name: str
    
    # Core metrics
    fund_fit_score: float
    ai_category: str
    momentum_score: float
    venture_scale_potential: bool
    
    # Market analysis
    current_market: Dict[str, Any]
    market_capture: Dict[str, Any]
    adjacent_markets: List[Dict[str, Any]]
    
    # Scenarios
    base_case: Dict[str, Any]
    bull_case: Dict[str, Any]
    bear_case: Dict[str, Any]
    
    # Cap table implications
    ownership_target: float
    dilution_scenarios: Dict[str, float]
    
    # Exit analysis
    liquidation_waterfall: Dict[str, Any]
    return_multiples: Dict[str, float]
    
    # Risk assessment
    down_round_risk: str
    agent_washing_risk: str
    
    # Visualizations
    charts: Dict[str, Any]
    
    # Citations for all data
    citations: Dict[str, List[str]]


class ComprehensiveDealAnalyzer:
    """
    Orchestrates all analysis components for complete deal evaluation
    """
    
    def __init__(self):
        self.gap_filler = IntelligentGapFiller()
        self.cap_table = CapTableCalculator()
        self.visualizer = CompanyScoringVisualizer()
        self.return_analyzer = OwnershipReturnAnalyzer()
        self.citation_manager = CitationManager()
    
    async def analyze_deal(
        self,
        company_data: Dict[str, Any],
        investment_amount: float = 5_000_000,
        fund_size: float = 200_000_000
    ) -> DealComparison:
        """
        Complete deal analysis with all components
        """
        
        # 1. AI & Momentum Analysis (Sep 2025 reality)
        ai_analysis = self.gap_filler.analyze_ai_impact(company_data)
        momentum = self.gap_filler.analyze_company_momentum(company_data)
        ai_valuation = self.gap_filler.calculate_ai_adjusted_valuation(company_data)
        
        # 2. Fund Fit Analysis
        inferred_metrics = await self.gap_filler.infer_from_funding_cadence(
            company_data,
            ["valuation", "revenue", "burn_rate", "runway"]
        )
        fund_fit = self.gap_filler.score_fund_fit(company_data, inferred_metrics)
        
        # 3. Market Analysis with Citations
        market_analysis = self._analyze_market_opportunity(company_data, ai_analysis)
        market_capture = self._calculate_market_capture(company_data, market_analysis, ai_analysis)
        adjacent_markets = self._identify_adjacent_markets(company_data, market_analysis)
        
        # 4. Venture Scale Assessment
        venture_scale = self._assess_venture_scale(
            company_data,
            ai_analysis,
            momentum,
            fund_size,
            market_analysis
        )
        
        # 4. Scenario Analysis (Base/Bull/Bear)
        gross_margin = self.gap_filler.calculate_adjusted_gross_margin(company_data)
        growth_req = self.gap_filler.calculate_required_growth_rates(company_data)
        entry_price = self.gap_filler.calculate_investor_entry_price(company_data)
        
        scenarios = self.visualizer.generate_scenario_analysis(
            company_data,
            gross_margin,
            growth_analysis=growth_req,
            entry_price_analysis=entry_price
        )
        
        # Apply AI adjustments to scenarios
        scenarios = self._apply_ai_adjustments_to_scenarios(scenarios, ai_analysis)
        
        # 5. Cap Table & Ownership Analysis
        current_valuation = company_data.get('valuation', 100_000_000)
        ownership_target = investment_amount / (current_valuation + investment_amount)
        
        # Calculate dilution through multiple rounds
        dilution_scenarios = self._calculate_dilution_scenarios(
            ownership_target,
            company_data.get('stage', 'series_a'),
            ai_analysis['ai_category']
        )
        
        # 6. Liquidation Preference & Exit Waterfall
        liquidation_analysis = self._calculate_liquidation_waterfall(
            investment_amount,
            ownership_target,
            scenarios,
            company_data.get('liquidation_preference', 1.0),
            company_data.get('participation', False)
        )
        
        # 7. Return Analysis
        return_multiples = {
            'base': scenarios['base']['exit_multiple'],
            'bull': scenarios['bull']['exit_multiple'],
            'bear': scenarios['bear']['exit_multiple'],
            'probability_weighted': (
                scenarios['base']['exit_multiple'] * 0.5 +
                scenarios['bull']['exit_multiple'] * 0.2 +
                scenarios['bear']['exit_multiple'] * 0.3
            )
        }
        
        # 8. Generate Visualizations
        charts = self._generate_comprehensive_charts(
            company_data,
            scenarios,
            dilution_scenarios,
            liquidation_analysis,
            ai_analysis,
            momentum
        )
        
        # Collect all citations
        citations = self.citation_manager.get_all_citations()
        
        return DealComparison(
            company_name=company_data.get('name', 'Unknown'),
            fund_fit_score=fund_fit['overall_score'],
            ai_category=ai_analysis['ai_category'],
            momentum_score=momentum['momentum_score'],
            venture_scale_potential=venture_scale['is_venture_scale'],
            current_market=market_analysis,
            market_capture=market_capture,
            adjacent_markets=adjacent_markets,
            base_case=scenarios['base'],
            bull_case=scenarios['bull'],
            bear_case=scenarios['bear'],
            ownership_target=ownership_target,
            dilution_scenarios=dilution_scenarios,
            liquidation_waterfall=liquidation_analysis,
            return_multiples=return_multiples,
            down_round_risk=ai_valuation['next_round']['down_round_risk'],
            agent_washing_risk=ai_analysis.get('agent_washing_likelihood', 'unknown'),
            charts=charts,
            citations=citations
        )
    
    def _analyze_market_opportunity(
        self,
        company_data: Dict,
        ai_analysis: Dict
    ) -> Dict[str, Any]:
        """
        Analyze current market TAM with citations
        """
        description = company_data.get('description', '').lower()
        
        # Market categorization
        market_category = self._categorize_market(description, ai_analysis)
        
        # TAM calculation with citations
        tam_data = self._calculate_tam(market_category, company_data)
        
        # Market growth rate
        market_growth = self._get_market_growth_rate(market_category)
        
        self.citation_manager.add_citation(
            f"Market sizing for {market_category}",
            tam_data.get('source', 'Industry analysis'),
            confidence=0.8
        )
        
        return {
            'category': market_category,
            'tam_current': tam_data['current'],
            'tam_2030': tam_data['projected'],
            'growth_rate': market_growth,
            'segments': tam_data.get('segments', []),
            'citations': tam_data.get('citations', [])
        }
    
    def _calculate_market_capture(
        self,
        company_data: Dict,
        market_analysis: Dict,
        ai_analysis: Dict
    ) -> Dict[str, Any]:
        """
        Calculate realistic market capture percentages
        """
        tam = market_analysis['tam_current']
        
        # Base capture rates by category
        if ai_analysis['ai_category'] == 'winner':
            # AI winners can capture more market faster
            capture_rates = {
                'year_1': 0.001,  # 0.1%
                'year_3': 0.01,   # 1%
                'year_5': 0.05,   # 5%
                'year_10': 0.15   # 15% (like Stripe in payments)
            }
        elif ai_analysis['ai_category'] == 'emerging':
            capture_rates = {
                'year_1': 0.0005,
                'year_3': 0.005,
                'year_5': 0.02,
                'year_10': 0.08
            }
        else:
            capture_rates = {
                'year_1': 0.0001,
                'year_3': 0.001,
                'year_5': 0.01,
                'year_10': 0.03
            }
        
        # Calculate revenue potential
        revenue_potential = {
            timeframe: tam * rate 
            for timeframe, rate in capture_rates.items()
        }
        
        self.citation_manager.add_citation(
            "Market capture rates",
            "Based on historical SaaS capture rates - Bessemer State of Cloud 2024",
            confidence=0.7
        )
        
        return {
            'capture_percentages': capture_rates,
            'revenue_potential': revenue_potential,
            'comparison': self._get_capture_comparisons(market_analysis['category']),
            'reasoning': self._capture_reasoning(ai_analysis, market_analysis)
        }
    
    def _identify_adjacent_markets(
        self,
        company_data: Dict,
        current_market: Dict
    ) -> List[Dict[str, Any]]:
        """
        Identify natural expansion markets with synergies
        """
        adjacent = []
        category = current_market['category']
        
        # Market expansion patterns
        expansion_patterns = {
            'payments': ['lending', 'banking', 'expense_management', 'accounting'],
            'hr_tech': ['payroll', 'benefits', 'recruiting', 'performance'],
            'sales_tools': ['marketing', 'customer_success', 'revenue_operations'],
            'developer_tools': ['devops', 'security', 'observability', 'testing'],
            'ai_infrastructure': ['data_tools', 'mlops', 'model_serving', 'training'],
            'vertical_saas': ['payments', 'lending', 'marketplace', 'procurement']
        }
        
        # Find adjacent markets
        for pattern, markets in expansion_patterns.items():
            if pattern in category.lower():
                for market in markets:
                    tam = self._get_market_tam(market)
                    adjacent.append({
                        'market': market,
                        'tam': tam,
                        'synergy_score': self._calculate_synergy(category, market),
                        'expansion_timeline': self._estimate_expansion_timeline(market),
                        'precedents': self._find_expansion_precedents(category, market)
                    })
        
        # Sort by synergy score
        adjacent.sort(key=lambda x: x['synergy_score'], reverse=True)
        
        for market in adjacent[:3]:  # Top 3 most synergistic
            self.citation_manager.add_citation(
                f"Adjacent market: {market['market']}",
                f"TAM: ${market['tam']/1e9:.1f}B, Synergy: {market['synergy_score']:.0%}",
                confidence=0.6
            )
        
        return adjacent[:5]  # Return top 5
    
    def _categorize_market(self, description: str, ai_analysis: Dict) -> str:
        """Categorize the company's market"""
        markets = {
            'payments': ['payment', 'transaction', 'checkout', 'billing'],
            'hr_tech': ['hr', 'human resources', 'payroll', 'employee'],
            'sales_tools': ['sales', 'crm', 'pipeline', 'revenue'],
            'developer_tools': ['developer', 'api', 'infrastructure', 'devops'],
            'ai_infrastructure': ['ai', 'ml', 'model', 'training', 'inference'],
            'vertical_saas': ['industry-specific', 'vertical', 'specialized'],
            'data_tools': ['data', 'analytics', 'warehouse', 'etl'],
            'security': ['security', 'compliance', 'authentication', 'identity'],
            'marketing_tech': ['marketing', 'advertising', 'growth', 'attribution']
        }
        
        for market, keywords in markets.items():
            if any(keyword in description for keyword in keywords):
                return market
        
        # Default based on AI category
        if ai_analysis['ai_category'] == 'winner':
            return 'ai_infrastructure'
        
        return 'general_saas'
    
    def _calculate_tam(self, market: str, company_data: Dict) -> Dict[str, Any]:
        """Calculate TAM with bottom-up and top-down approach"""
        # Market-specific TAM data (2025 estimates)
        market_tams = {
            'payments': {
                'current': 150_000_000_000,  # $150B
                'projected': 300_000_000_000,  # $300B by 2030
                'source': 'McKinsey Payments Report 2024',
                'segments': ['B2B payments', 'Cross-border', 'Embedded finance']
            },
            'hr_tech': {
                'current': 60_000_000_000,  # $60B
                'projected': 120_000_000_000,
                'source': 'Gartner HR Technology 2024',
                'segments': ['Payroll', 'HCM', 'Talent Management']
            },
            'ai_infrastructure': {
                'current': 40_000_000_000,  # $40B
                'projected': 500_000_000_000,  # $500B by 2030
                'source': 'IDC AI Infrastructure Forecast 2025',
                'segments': ['Training', 'Inference', 'MLOps', 'Data']
            },
            'developer_tools': {
                'current': 30_000_000_000,
                'projected': 80_000_000_000,
                'source': 'RedPoint DevTools Market Map 2024',
                'segments': ['IDEs', 'CI/CD', 'Testing', 'Observability']
            }
        }
        
        return market_tams.get(market, {
            'current': 20_000_000_000,  # $20B default
            'projected': 50_000_000_000,
            'source': 'Estimated based on comparable markets',
            'segments': []
        })
    
    def _get_market_growth_rate(self, market: str) -> float:
        """Get market-specific growth rates"""
        growth_rates = {
            'ai_infrastructure': 0.85,  # 85% CAGR
            'payments': 0.12,
            'hr_tech': 0.15,
            'developer_tools': 0.25,
            'security': 0.18,
            'data_tools': 0.22
        }
        return growth_rates.get(market, 0.15)  # 15% default
    
    def _get_capture_comparisons(self, market: str) -> List[Dict]:
        """Get comparable company capture rates"""
        comparisons = {
            'payments': [
                {'company': 'Stripe', 'capture': 0.02, 'years': 14},
                {'company': 'Square', 'capture': 0.015, 'years': 15},
                {'company': 'Adyen', 'capture': 0.01, 'years': 18}
            ],
            'hr_tech': [
                {'company': 'Workday', 'capture': 0.05, 'years': 20},
                {'company': 'Rippling', 'capture': 0.005, 'years': 8},
                {'company': 'Gusto', 'capture': 0.003, 'years': 12}
            ]
        }
        return comparisons.get(market, [])
    
    def _capture_reasoning(self, ai_analysis: Dict, market: Dict) -> str:
        """Generate reasoning for market capture potential"""
        if ai_analysis['ai_category'] == 'winner':
            return f"AI-native advantage enables faster capture in ${market['tam_current']/1e9:.0f}B {market['category']} market"
        elif market['growth_rate'] > 0.3:
            return f"High market growth ({market['growth_rate']:.0%}) creates expansion opportunity"
        else:
            return f"Steady execution required in mature {market['category']} market"
    
    def _get_market_tam(self, market: str) -> float:
        """Get TAM for a specific market"""
        tams = {
            'lending': 500_000_000_000,
            'banking': 2_000_000_000_000,
            'expense_management': 15_000_000_000,
            'accounting': 40_000_000_000,
            'payroll': 200_000_000_000,
            'benefits': 100_000_000_000,
            'recruiting': 140_000_000_000,
            'marketplace': 100_000_000_000
        }
        return tams.get(market, 10_000_000_000)
    
    def _calculate_synergy(self, current: str, adjacent: str) -> float:
        """Calculate synergy score between markets"""
        # High synergy pairs
        high_synergy = [
            ('payments', 'lending'),
            ('hr_tech', 'payroll'),
            ('developer_tools', 'devops'),
            ('sales_tools', 'marketing')
        ]
        
        if (current, adjacent) in high_synergy or (adjacent, current) in high_synergy:
            return 0.9
        
        # Same customer base
        if 'developer' in current and 'developer' in adjacent:
            return 0.8
        
        return 0.5  # Default moderate synergy
    
    def _estimate_expansion_timeline(self, market: str) -> str:
        """Estimate when company could expand to market"""
        complex_markets = ['lending', 'banking', 'insurance']
        if market in complex_markets:
            return "Year 5-7 (regulatory requirements)"
        return "Year 3-5 (natural expansion)"
    
    def _find_expansion_precedents(self, current: str, adjacent: str) -> List[str]:
        """Find companies that made similar expansions"""
        precedents = {
            ('payments', 'lending'): ['Square → Square Capital', 'Stripe → Stripe Capital'],
            ('hr_tech', 'payroll'): ['Rippling → Rippling Payroll', 'Zenefits → Payroll'],
            ('developer_tools', 'security'): ['GitHub → GitHub Security', 'GitLab → DevSecOps']
        }
        return precedents.get((current, adjacent), [])
    
    def _assess_venture_scale(
        self,
        company_data: Dict,
        ai_analysis: Dict,
        momentum: Dict,
        fund_size: float,
        market_analysis: Dict
    ) -> Dict[str, Any]:
        """
        Determine if company can return the fund (venture scale)
        """
        current_valuation = company_data.get('valuation', 100_000_000)
        
        # Need to return 3x fund minimum
        required_exit = fund_size * 3
        
        # Calculate required multiple based on expected ownership
        typical_ownership = 0.10  # 10% target ownership
        required_company_exit = required_exit / typical_ownership
        
        # Assess probability based on AI category and momentum
        if ai_analysis['ai_category'] == 'winner':
            probability = 0.4 if momentum['momentum_score'] > 7 else 0.25
        elif ai_analysis['ai_category'] == 'emerging':
            probability = 0.2 if momentum['momentum_score'] > 7 else 0.10
        else:
            probability = 0.05  # Traditional SaaS rarely returns funds
        
        return {
            'is_venture_scale': required_company_exit < current_valuation * 50,
            'required_exit_valuation': required_company_exit,
            'probability_of_fund_return': probability,
            'reasoning': self._venture_scale_reasoning(
                ai_analysis['ai_category'],
                momentum['momentum_category'],
                required_company_exit
            )
        }
    
    def _venture_scale_reasoning(self, ai_category: str, momentum_cat: str, required: float) -> str:
        """Generate reasoning for venture scale assessment"""
        if ai_category == 'winner' and momentum_cat == 'rocket_ship':
            return f"AI leader with exceptional momentum - high probability of ${required/1e9:.1f}B exit"
        elif ai_category == 'cost_center':
            return f"AI cost center unlikely to reach ${required/1e9:.1f}B valuation needed"
        else:
            return f"Requires ${required/1e9:.1f}B exit to return fund - challenging but possible"
    
    def _apply_ai_adjustments_to_scenarios(
        self,
        scenarios: Dict,
        ai_analysis: Dict
    ) -> Dict:
        """Apply AI category adjustments to scenarios"""
        
        if ai_analysis['ai_category'] == 'winner':
            # AI winners have higher upside
            scenarios['bull']['exit_multiple'] *= 2.0
            scenarios['bull']['probability'] = 0.30  # Higher bull probability
            scenarios['bear']['probability'] = 0.20  # Lower bear probability
            scenarios['base']['probability'] = 0.50
            
        elif ai_analysis['ai_category'] == 'cost_center':
            # Cost centers face headwinds
            scenarios['bear']['exit_multiple'] *= 0.5
            scenarios['bear']['probability'] = 0.40  # Higher bear probability
            scenarios['bull']['probability'] = 0.10  # Lower bull probability
            scenarios['base']['probability'] = 0.50
        
        return scenarios
    
    def _calculate_dilution_scenarios(
        self,
        initial_ownership: float,
        current_stage: str,
        ai_category: str
    ) -> Dict[str, float]:
        """
        Calculate ownership dilution through future rounds
        """
        # Stage progression
        stage_progression = {
            'seed': ['series_a', 'series_b', 'series_c'],
            'series_a': ['series_b', 'series_c', 'series_d'],
            'series_b': ['series_c', 'series_d', 'ipo'],
            'series_c': ['series_d', 'series_e', 'ipo']
        }
        
        # Typical dilution per round (adjusted for AI category)
        if ai_category == 'winner':
            dilution_per_round = 0.15  # Less dilution for hot deals
        elif ai_category == 'cost_center':
            dilution_per_round = 0.25  # More dilution for struggling companies
        else:
            dilution_per_round = 0.20  # Standard dilution
        
        future_rounds = stage_progression.get(current_stage, ['ipo'])
        
        scenarios = {
            'no_participation': initial_ownership,
            'partial_participation': initial_ownership,
            'full_participation': initial_ownership
        }
        
        for round in future_rounds:
            # No participation = full dilution
            scenarios['no_participation'] *= (1 - dilution_per_round)
            
            # Partial = maintain 50% of ownership
            scenarios['partial_participation'] *= (1 - dilution_per_round * 0.5)
            
            # Full = maintain ownership (pro-rata)
            scenarios['full_participation'] = initial_ownership
        
        return scenarios
    
    def _calculate_liquidation_waterfall(
        self,
        investment: float,
        ownership: float,
        scenarios: Dict,
        liq_pref_multiple: float,
        participation: bool
    ) -> Dict[str, Any]:
        """
        Calculate returns under different exit scenarios with liquidation preferences
        """
        waterfalls = {}
        
        for scenario_name, scenario in scenarios.items():
            exit_value = scenario.get('valuation_5y', investment * 5)
            
            # Liquidation preference
            liq_pref_amount = investment * liq_pref_multiple
            
            if exit_value <= liq_pref_amount:
                # Full liquidation preference
                investor_return = min(exit_value, liq_pref_amount)
            elif participation:
                # Participating preferred
                investor_return = liq_pref_amount + (exit_value - liq_pref_amount) * ownership
            else:
                # Non-participating: choose better of liq pref or conversion
                conversion_value = exit_value * ownership
                investor_return = max(liq_pref_amount, conversion_value)
            
            waterfalls[scenario_name] = {
                'exit_value': exit_value,
                'investor_return': investor_return,
                'return_multiple': investor_return / investment,
                'effective_ownership': investor_return / exit_value if exit_value > 0 else 0
            }
        
        return waterfalls
    
    def _generate_comprehensive_charts(
        self,
        company_data: Dict,
        scenarios: Dict,
        dilution: Dict,
        liquidation: Dict,
        ai_analysis: Dict,
        momentum: Dict
    ) -> Dict[str, Any]:
        """
        Generate all visualization data
        """
        return {
            'scenario_comparison': {
                'type': 'grouped_bar',
                'title': f"{company_data.get('name')} - Base/Bull/Bear Scenarios",
                'data': {
                    'categories': ['Base', 'Bull', 'Bear'],
                    'series': [
                        {
                            'name': 'Exit Multiple',
                            'data': [s['exit_multiple'] for s in scenarios.values()]
                        },
                        {
                            'name': 'IRR',
                            'data': [s.get('irr', 0) * 100 for s in scenarios.values()]
                        }
                    ]
                }
            },
            'ownership_dilution': {
                'type': 'line',
                'title': 'Ownership Through Rounds',
                'data': {
                    'categories': ['Current', 'Series B', 'Series C', 'Exit'],
                    'series': [
                        {
                            'name': 'No Participation',
                            'data': self._generate_dilution_curve(dilution['no_participation'])
                        },
                        {
                            'name': 'Full Pro-Rata',
                            'data': self._generate_dilution_curve(dilution['full_participation'])
                        }
                    ]
                }
            },
            'liquidation_waterfall': {
                'type': 'waterfall',
                'title': 'Exit Proceeds Distribution',
                'data': {
                    'categories': ['Investment', 'Liq Pref', 'Participation', 'Final Return'],
                    'values': self._generate_waterfall_data(liquidation['base'])
                }
            },
            'ai_impact': {
                'type': 'radar',
                'title': 'AI & Momentum Score',
                'data': {
                    'categories': ['AI Score', 'Momentum', 'Growth', 'Moat', 'Market'],
                    'values': [
                        ai_analysis.get('ai_score', 0) * 10,
                        momentum['momentum_score'] * 10,
                        min(100, ai_analysis['growth_rate'] * 20),
                        self._calculate_moat_score(company_data, ai_analysis),
                        self._calculate_market_score(company_data)
                    ]
                }
            }
        }
    
    def _generate_dilution_curve(self, final_ownership: float) -> List[float]:
        """Generate ownership curve data"""
        # Simplified - would calculate actual curve
        return [0.10, 0.08, 0.06, final_ownership]
    
    def _generate_waterfall_data(self, scenario: Dict) -> List[float]:
        """Generate waterfall chart data"""
        return [
            5_000_000,  # Initial investment
            scenario.get('investor_return', 15_000_000) - 5_000_000,  # Gain
            0,  # No participation adjustment in this example
            scenario.get('investor_return', 15_000_000)  # Final
        ]
    
    def _calculate_moat_score(self, company_data: Dict, ai_analysis: Dict) -> float:
        """Calculate competitive moat score"""
        score = 50  # Base score
        
        if ai_analysis['ai_category'] == 'winner':
            score += 30
        elif ai_analysis['ai_category'] == 'emerging':
            score += 15
        
        # Add points for network effects, switching costs, etc.
        if 'network' in str(company_data).lower():
            score += 10
        if 'proprietary' in str(company_data).lower():
            score += 10
            
        return min(100, score)
    
    def _calculate_market_score(self, company_data: Dict) -> float:
        """Calculate market opportunity score"""
        # Simplified - would analyze TAM, growth rate, etc.
        return 70


async def compare_deals(
    companies: List[Dict[str, Any]],
    investment_amount: float = 5_000_000,
    fund_size: float = 200_000_000
) -> List[DealComparison]:
    """
    Compare multiple deals for investment decision
    """
    analyzer = ComprehensiveDealAnalyzer()
    comparisons = []
    
    for company in companies:
        comparison = await analyzer.analyze_deal(
            company,
            investment_amount,
            fund_size
        )
        comparisons.append(comparison)
    
    # Sort by fund fit score
    comparisons.sort(key=lambda x: x.fund_fit_score, reverse=True)
    
    return comparisons