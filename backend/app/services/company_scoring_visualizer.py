"""
Company Scoring and Visualization Service
Generates comprehensive scoring, base/bull/bear scenarios, and cap table visualizations
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CompanyScore:
    """Company scoring data"""
    company_name: str
    overall_score: float
    component_scores: Dict[str, float]
    base_case: Dict[str, Any]
    bull_case: Dict[str, Any]
    bear_case: Dict[str, Any]
    cap_table: Dict[str, float]
    api_dependency: str
    gross_margin: float
    valuation: float
    # Additional analysis data
    founder_profile: Dict[str, Any] = None
    investor_map: Dict[str, List[str]] = None
    growth_analysis: Dict[str, Any] = None
    entry_price_analysis: Dict[str, Any] = None
    

class CompanyScoringVisualizer:
    """
    Generates comprehensive scoring visualizations for portfolio companies
    """
    
    def __init__(self):
        from app.services.intelligent_gap_filler import IntelligentGapFiller
        from app.services.ownership_return_analyzer import OwnershipReturnAnalyzer
        from app.services.advanced_cap_table import CapTableCalculator
        
        self.gap_filler = IntelligentGapFiller()
        self.ownership_analyzer = OwnershipReturnAnalyzer()
        self.cap_table_calc = CapTableCalculator()
    
    async def score_company(self, company_data: Dict[str, Any]) -> CompanyScore:
        """
        Generate comprehensive scoring for a company
        """
        # Get fund fit score and components
        # Extract funding rounds from company_data
        funding_rounds = company_data.get('funding_analysis', {}).get('rounds', [])
        # Determine which fields are missing and need inference
        missing_fields = []
        if not company_data.get('valuation') or company_data.get('valuation') == 0:
            missing_fields.append('valuation')
        if not company_data.get('burn_rate') or company_data.get('burn_rate') == 0:
            missing_fields.append('burn_rate')
        if not company_data.get('runway_months') or company_data.get('runway_months') == 0:
            missing_fields.append('runway_months')
        
        inferred_data = await self.gap_filler.infer_from_funding_cadence(company_data, missing_fields)
        
        fund_fit = self.gap_filler.score_fund_fit(company_data, inferred_data)
        
        # Get gross margin analysis
        gross_margin_analysis = self.gap_filler.calculate_adjusted_gross_margin(company_data)
        
        # Extract actual investor names from funding data
        funding_rounds = company_data.get("funding_rounds", [])
        investor_map = self.gap_filler.extract_investor_names_from_funding(funding_rounds)
        
        # Analyze founder profile
        founder_profile = self.gap_filler.analyze_founder_profile(company_data)
        
        # Calculate required growth rates and valuation justification
        growth_analysis = self.gap_filler.calculate_required_growth_rates(company_data)
        
        # Calculate investor entry price analysis (what should we pay?)
        entry_price_analysis = self.gap_filler.calculate_investor_entry_price(company_data)
        
        # Generate scenarios with all analysis data
        scenarios = self._generate_scenarios(
            company_data, 
            gross_margin_analysis, 
            founder_profile, 
            growth_analysis,
            entry_price_analysis
        )
        
        # Calculate cap table with actual investor names
        cap_table = self._calculate_cap_table(company_data, investor_map)
        
        # Add founder profile to the score
        # Ensure fund_fit has all required keys with defaults
        if not isinstance(fund_fit, dict):
            fund_fit = {}
        component_scores = fund_fit.get("component_scores", {
            "stage_fit": 0,
            "sector_fit": 0,
            "unit_economics": 0,
            "check_size_fit": 0,
            "timing_fit": 0,
            "return_potential": 0,
            "geography_fit": 0,
            "fund_economics": 0,
            "portfolio_fit": 0
        })
        
        score = CompanyScore(
            company_name=company_data.get("company", company_data.get("name", "Unknown")),
            overall_score=fund_fit.get("overall_score", 0),
            component_scores=component_scores,
            base_case=scenarios["base"],
            bull_case=scenarios["bull"],
            bear_case=scenarios["bear"],
            cap_table=cap_table,
            api_dependency=gross_margin_analysis.get("api_dependency_level", "unknown"),
            gross_margin=gross_margin_analysis.get("adjusted_gross_margin", 0),
            valuation=company_data.get("valuation", 0)
        )
        
        # Add all analysis data to the score object
        score.founder_profile = founder_profile
        score.investor_map = investor_map
        score.growth_analysis = growth_analysis
        score.entry_price_analysis = entry_price_analysis
        
        return score
    
    def _generate_scenarios(
        self, 
        company_data: Dict[str, Any], 
        gross_margin_analysis: Dict[str, Any],
        founder_profile: Dict[str, Any] = None,
        growth_analysis: Dict[str, Any] = None,
        entry_price_analysis: Dict[str, Any] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate base, bull, and bear case scenarios with growth deceleration
        """
        # CRITICAL: Ensure we never have None values for calculations
        # Use actual revenue first, then inferred revenue (which should ALWAYS exist)
        current_revenue = company_data.get("revenue") or company_data.get("arr") or company_data.get("inferred_revenue")
        if current_revenue is None or current_revenue == 0:
            # Infer from stage if available
            stage = company_data.get("stage", "Series A")
            stage_revenues = {
                "Pre-seed": 100_000,
                "Seed": 500_000,
                "Series A": 2_000_000,
                "Series B": 10_000_000,
                "Series C": 30_000_000,
                "Series D": 50_000_000
            }
            for stage_key, typical_revenue in stage_revenues.items():
                if stage_key.lower() in stage.lower():
                    current_revenue = typical_revenue
                    break
            if current_revenue == 0:
                current_revenue = 1_000_000  # Default $1M
        
        current_valuation = company_data.get("valuation") or 50_000_000
        if current_valuation is None:
            current_valuation = 50_000_000
            
        current_growth_rate = company_data.get("growth_rate")
        if current_growth_rate is None:
            current_growth_rate = 1.0  # Default 100% growth
        
        # Ensure current_growth_rate is not None and is in the right format
        if current_growth_rate is None:
            current_growth_rate = 1.0  # Default 100% growth
        elif current_growth_rate > 10:
            # It's a percentage like 150, convert to decimal
            current_growth_rate = current_growth_rate / 100
        elif current_growth_rate < 0:
            current_growth_rate = 1.0  # Default to 100% if negative
        
        # Check for strategic investors (increases exit likelihood)
        strategic_investor_bonus = 1.0
        strategic_investors = self._identify_strategic_investors(company_data)
        if strategic_investors:
            strategic_investor_bonus = 1.3  # 30% higher exit multiple with strategics
        
        # Get growth analysis insights
        if growth_analysis:
            current_multiple = growth_analysis.get("current_multiple", 10)
            justified_multiple = growth_analysis["backward_looking"]["justified_multiple_with_nrr"]
            overvalued = growth_analysis["backward_looking"]["overvalued"]
            nrr = growth_analysis.get("nrr", 1.10)
        else:
            current_multiple = current_valuation / current_revenue if current_revenue > 0 else 10
            justified_multiple = current_multiple
            overvalued = False
            nrr = 1.10
        
        # Get entry price insights for more accurate scenarios
        if entry_price_analysis:
            exit_valuation = entry_price_analysis["exit_assumptions"]["exit_valuation"]
            growth_projections = entry_price_analysis["growth_projection"]["year_by_year_revenue"]
            deal_recommendation = entry_price_analysis["deal_analysis"]["recommendation"]
            max_entry_price = entry_price_analysis["investor_math"]["max_entry_valuation"]
        else:
            exit_valuation = current_valuation * 5
            growth_projections = [current_revenue * (1 + current_growth_rate) ** i for i in range(1, 6)]
            deal_recommendation = "No analysis available"
            max_entry_price = current_valuation
        
        # Adjust for API dependency
        api_adjustment = gross_margin_analysis["valuation_multiple_adjustment"]
        
        scenarios = {
            "base": {
                "revenue_5y": growth_projections[-1] if growth_projections else current_revenue * (1 + current_growth_rate) ** 5,
                "valuation_5y": exit_valuation * api_adjustment * strategic_investor_bonus,
                "exit_multiple": (exit_valuation / max_entry_price) if max_entry_price > 0 else 3.0,
                "entry_valuation": max_entry_price,
                "current_ask": current_valuation,
                "deal_recommendation": deal_recommendation,
                "irr": ((exit_valuation / max_entry_price) ** 0.2 - 1) if max_entry_price > 0 else 0.25,
                "probability": 0.50,
                "gross_margin": gross_margin_analysis["adjusted_gross_margin"],
                "assumptions": [
                    f"Growth decelerates from {(current_growth_rate if current_growth_rate < 10 else current_growth_rate/100)*100:.0f}% as modeled",
                    f"Gross margins at {gross_margin_analysis['adjusted_gross_margin']:.0%}",
                    f"NRR stays at {nrr:.0%}",
                    "Market conditions remain stable"
                ]
            },
            "bull": {
                "revenue_5y": current_revenue * (1 + current_growth_rate * 1.5) ** 5,
                "valuation_5y": current_valuation * 10 * api_adjustment,  # 10x in 5 years
                "exit_multiple": 10.0,
                "irr": 0.58,
                "probability": 0.20,
                "gross_margin": min(0.85, gross_margin_analysis["adjusted_gross_margin"] + 0.10),
                "assumptions": [
                    f"Accelerate to {current_growth_rate * 1.5:.0%} growth",
                    "Improve gross margins by 10%",
                    "Achieve market leadership",
                    "Favorable exit environment"
                ]
            },
            "bear": {
                "revenue_5y": current_revenue * (1 + current_growth_rate * 0.3) ** 5,
                "valuation_5y": current_valuation * 0.8 * api_adjustment,  # Down round
                "exit_multiple": 0.8,
                "irr": -0.05,
                "probability": 0.30,
                "gross_margin": max(0.40, gross_margin_analysis["adjusted_gross_margin"] - 0.15),
                "assumptions": [
                    f"Growth slows to {current_growth_rate * 0.3:.0%}",
                    "Gross margins compress by 15%",
                    "Increased competition",
                    "Difficult funding environment"
                ]
            }
        }
        
        # Adjust bear case more severely for heavy API dependency
        if gross_margin_analysis["api_dependency_level"] == "openai_heavy":
            scenarios["bear"]["gross_margin"] = max(0.35, scenarios["bear"]["gross_margin"] - 0.10)
            scenarios["bear"]["assumptions"].append("API costs increase significantly")
            scenarios["bull"]["probability"] = 0.15  # Lower bull probability
            scenarios["bear"]["probability"] = 0.35  # Higher bear probability
        
        return scenarios
    
    def _extract_investor_names(self, round_data: Dict[str, Any], round_name: str) -> List[str]:
        """
        Extract or categorize investor names from funding round data
        """
        # Check for explicit investor data
        if "investors" in round_data and round_data["investors"]:
            return round_data["investors"]
        
        # Try to extract from description or notes
        description = round_data.get("description", "")
        notes = round_data.get("notes", "")
        
        # Common investor patterns to look for
        investor_keywords = {
            "Seed": ["Y Combinator", "500 Startups", "Techstars", "Angels", "Founders Fund", "First Round"],
            "Series A": ["Sequoia", "Andreessen Horowitz", "Benchmark", "Accel", "Index Ventures", "Lightspeed"],
            "Series B": ["Tiger Global", "Coatue", "Insight Partners", "General Catalyst", "Battery Ventures"],
            "Series C": ["SoftBank", "DST Global", "IVP", "Bessemer", "GGV Capital"],
            "Series D": ["T. Rowe Price", "Fidelity", "Wellington", "BlackRock", "Baillie Gifford"]
        }
        
        # Categorize by round size and stage
        amount = round_data.get("amount", 0)
        
        if amount > 500_000_000:
            return ["Tier 1 Growth Funds", "Sovereign Wealth", "Late Stage Consortium"]
        elif amount > 100_000_000:
            return ["Growth Equity Funds", "Crossover Investors", f"{round_name} Syndicate"]
        elif amount > 50_000_000:
            return ["Series B/C Funds", "Growth VCs", f"{round_name} Lead + Syndicate"]
        elif amount > 10_000_000:
            return ["Series A Funds", "Early Growth VCs", f"{round_name} Institutional"]
        elif amount > 2_000_000:
            return ["Seed Funds", "Micro VCs", "Angel Syndicate"]
        else:
            return ["Angels", "Pre-seed Funds", "Accelerator"]
    
    def _categorize_investor_tier(self, amount: float, round_name: str) -> str:
        """
        Categorize investor tier based on investment size and round
        """
        tier_map = {
            "Pre-seed": {
                "small": "Angels & Friends/Family",
                "medium": "Pre-seed Funds",
                "large": "Seed Extension"
            },
            "Seed": {
                "small": "Angel Syndicate",
                "medium": "Seed Funds",
                "large": "Multi-stage Seed"
            },
            "Series A": {
                "small": "Micro VC",
                "medium": "Traditional Series A",
                "large": "Mega Series A"
            },
            "Series B": {
                "small": "Inside Round",
                "medium": "Growth Series B",
                "large": "Crossover Round"
            },
            "Series C": {
                "small": "Bridge Round",
                "medium": "Growth Equity",
                "large": "Late Stage Mega"
            }
        }
        
        # Determine size category
        if amount < 5_000_000:
            size = "small"
        elif amount < 50_000_000:
            size = "medium"
        else:
            size = "large"
        
        # Get tier or default
        round_tiers = tier_map.get(round_name, tier_map.get("Series A"))
        return round_tiers.get(size, f"{round_name} Investors")
    
    # Class constants for dilution rates
    DILUTION_BY_STAGE = {
        "Pre-seed": 0.10,
        "Seed": 0.15,
        "Series A": 0.20,
        "Series B": 0.15,
        "Series C": 0.12,
        "Series D": 0.10,
        "Series E": 0.08
    }
    
    LEAD_INVESTOR_SHARE = 0.6  # Lead takes 60% of round
    OPTION_POOL_SIZE = 0.15  # Standard 15% option pool
    OPTION_EXERCISE_RATE = 0.25  # Only 25% exercised (Carta benchmark)

    def _calculate_cap_table(self, company_data: Dict[str, Any], investor_map: Dict[str, List[str]] = None) -> Dict[str, float]:
        """
        Calculate post-dilution cap table with scraped/categorized investor names
        Optimized to avoid O(n²) complexity and redundant calculations
        """
        funding_rounds = company_data.get("funding_rounds", [])
        
        if not funding_rounds:
            # Default cap table if no funding data
            return {
                "Founders": 40.0,
                "Employees": 15.0,
                "Seed Investors": 15.0,
                "Series A": 20.0,
                "Series B": 10.0
            }
        
        # Initialize cap table with ownership fractions (not percentages)
        cap_table = {}
        cumulative_dilution = 1.0  # Track overall dilution factor
        
        # Process each funding round
        for round_data in funding_rounds:
            round_name = round_data.get("round", "Unknown Round")
            amount = round_data.get("amount", 0)
            investors = round_data.get("investors", [])
            lead_investor = round_data.get("lead_investor", None)
            valuation = round_data.get("valuation", company_data.get("valuation", 100_000_000))
            
            # Calculate dilution for this round
            if valuation and valuation > 0:
                round_dilution = min(0.25, amount / valuation)
            else:
                round_dilution = self.DILUTION_BY_STAGE.get(round_name, 0.15)
            
            # Calculate ownership for new investors (as fraction of company)
            round_ownership = round_dilution
            
            # Process investors efficiently in single pass
            if investors:
                if lead_investor:
                    # Lead investor takes 60% of round
                    lead_stake = round_ownership * self.LEAD_INVESTOR_SHARE
                    cap_table[f"{lead_investor} ({round_name} Lead)"] = lead_stake
                    
                    # Other investors share remaining 40%
                    other_investors = [inv for inv in investors if inv != lead_investor]
                    if other_investors:
                        other_stake = round_ownership * (1.0 - self.LEAD_INVESTOR_SHARE)
                        per_investor = other_stake / len(other_investors)
                        for investor in other_investors:
                            cap_table[f"{investor} ({round_name})"] = per_investor
                else:
                    # Equal distribution among all investors
                    per_investor = round_ownership / len(investors)
                    for investor in investors:
                        investor_key = f"{investor} ({round_name})"
                        # Accumulate if investor participated in multiple rounds
                        cap_table[investor_key] = cap_table.get(investor_key, 0) + per_investor
            else:
                # No specific investor names, use round name
                cap_table[f"{round_name} Investors"] = round_ownership
            
            # Update cumulative dilution factor
            cumulative_dilution *= (1.0 - round_dilution)
        
        # Calculate final founder ownership after all dilution
        # Start with 60% initial ownership
        founder_initial = 0.60
        founder_ownership = founder_initial * cumulative_dilution
        cap_table["Founders"] = founder_ownership
        
        # Add employee pool (already diluted by rounds)
        # Option pool ownership as fraction of company
        option_pool_ownership = self.OPTION_POOL_SIZE
        cap_table["Employees (vested)"] = option_pool_ownership * self.OPTION_EXERCISE_RATE
        cap_table["Employees (unvested)"] = option_pool_ownership * (1.0 - self.OPTION_EXERCISE_RATE)
        
        # Convert fractions to percentages and normalize to 100%
        total = sum(cap_table.values())
        if total > 0:
            cap_table = {k: (v / total) * 100 for k, v in cap_table.items()}
        
        # Sort by ownership percentage
        return dict(sorted(cap_table.items(), key=lambda x: x[1], reverse=True))
    
    def generate_scenario_comparison_chart(
        self, 
        scores: List[CompanyScore]
    ) -> Dict[str, Any]:
        """
        Generate data for base/bull/bear comparison chart
        """
        chart_data = {
            "type": "grouped_bar",
            "title": "Portfolio Company Scenarios - Exit Multiples",
            "companies": [],
            "series": [
                {"name": "Bear Case", "color": "#ef4444"},  # Red
                {"name": "Base Case", "color": "#3b82f6"},  # Blue
                {"name": "Bull Case", "color": "#10b981"}   # Green
            ]
        }
        
        for score in scores:
            # Add entry price and deal recommendation if available
            entry_data = {}
            if score.entry_price_analysis:
                entry_data = {
                    "max_entry_price": score.entry_price_analysis.get("investor_math", {}).get("max_entry_valuation"),
                    "current_ask": score.entry_price_analysis.get("deal_analysis", {}).get("current_ask"),
                    "deal_recommendation": score.entry_price_analysis.get("deal_analysis", {}).get("recommendation"),
                    "valuation_gap": score.entry_price_analysis.get("deal_analysis", {}).get("valuation_gap")
                }
            
            chart_data["companies"].append({
                "name": score.company_name,
                "overall_score": score.overall_score,
                "entry_analysis": entry_data,
                "data": [
                    {
                        "scenario": "Bear",
                        "exit_multiple": score.bear_case["exit_multiple"],
                        "probability": score.bear_case["probability"],
                        "irr": score.bear_case["irr"],
                        "gross_margin": score.bear_case["gross_margin"]
                    },
                    {
                        "scenario": "Base",
                        "exit_multiple": score.base_case["exit_multiple"],
                        "probability": score.base_case["probability"],
                        "irr": score.base_case["irr"],
                        "gross_margin": score.base_case["gross_margin"]
                    },
                    {
                        "scenario": "Bull",
                        "exit_multiple": score.bull_case["exit_multiple"],
                        "probability": score.bull_case["probability"],
                        "irr": score.bull_case["irr"],
                        "gross_margin": score.bull_case["gross_margin"]
                    }
                ]
            })
        
        # Sort by overall score
        chart_data["companies"].sort(key=lambda x: x["overall_score"], reverse=True)
        
        return chart_data
    
    def generate_cap_table_pie_charts(
        self, 
        scores: List[CompanyScore]
    ) -> List[Dict[str, Any]]:
        """
        Generate pie chart data for cap tables
        """
        pie_charts = []
        
        for score in scores:
            # Filter out very small slices (< 1%)
            filtered_cap_table = {
                k: v for k, v in score.cap_table.items() 
                if v >= 1.0
            }
            
            # Add "Other" category for small slices
            other_pct = sum(v for k, v in score.cap_table.items() if v < 1.0)
            if other_pct > 0:
                filtered_cap_table["Other"] = other_pct
            
            pie_charts.append({
                "company": score.company_name,
                "overall_score": score.overall_score,
                "api_dependency": score.api_dependency,
                "gross_margin": score.gross_margin,
                "valuation": score.valuation,
                "chart": {
                    "type": "pie",
                    "title": f"{score.company_name} - Post-Dilution Cap Table",
                    "subtitle": f"API Dependency: {score.api_dependency} | Gross Margin: {score.gross_margin:.0%}",
                    "data": [
                        {
                            "name": stakeholder,
                            "value": round(percentage, 1),
                            "color": self._get_stakeholder_color(stakeholder)
                        }
                        for stakeholder, percentage in filtered_cap_table.items()
                    ],
                    "total_shares": 100,
                    "assumptions": [
                        "70% of options remain unexercised",
                        f"API dependency level: {score.api_dependency}",
                        f"Adjusted gross margin: {score.gross_margin:.0%}"
                    ]
                }
            })
        
        # Sort by overall score
        pie_charts.sort(key=lambda x: x["overall_score"], reverse=True)
        
        return pie_charts
    
    def _identify_strategic_investors(self, company_data: Dict[str, Any]) -> List[str]:
        """Identify strategic corporate investors in the cap table"""
        strategic_keywords = [
            "google", "microsoft", "amazon", "salesforce", "oracle",
            "intel", "cisco", "ibm", "sap", "adobe", "nvidia",
            "qualcomm", "samsung", "sony", "toyota", "gm", "ford",
            "walmart", "target", "jpmorgan", "goldman", "morgan stanley"
        ]
        
        strategic_investors = []
        funding_rounds = company_data.get("funding_rounds", [])
        
        for round_data in funding_rounds:
            investors = round_data.get("investors", [])
            for investor in investors:
                if any(strategic in investor.lower() for strategic in strategic_keywords):
                    strategic_investors.append(investor)
        
        return strategic_investors
    
    def _get_stakeholder_color(self, stakeholder: str) -> str:
        """
        Get consistent colors for stakeholder types
        """
        color_map = {
            "Founders": "#8b5cf6",      # Purple
            "Employees": "#3b82f6",      # Blue
            "Employees (vested)": "#3b82f6",
            "Employees (unvested)": "#93c5fd",  # Light blue
            "Seed Investors": "#10b981", # Green
            "Series A": "#f59e0b",       # Amber
            "Series B": "#ef4444",       # Red
            "Series C": "#ec4899",       # Pink
            "Early Investors": "#10b981", # Green
            "Later Investors": "#f59e0b", # Amber
            "Other": "#6b7280"           # Gray
        }
        
        # Match partial strings
        for key, color in color_map.items():
            if key.lower() in stakeholder.lower():
                return color
        
        return "#6b7280"  # Default gray
    
    def generate_scoring_matrix(
        self, 
        scores: List[CompanyScore]
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive scoring matrix for all companies
        """
        matrix_data = {
            "type": "heatmap",
            "title": "Portfolio Company Scoring Matrix",
            "companies": [],
            "metrics": [
                "Overall Score",
                "Stage Fit",
                "Sector Fit", 
                "Unit Economics",
                "Check Size Fit",
                "Timing Fit",
                "Return Potential",
                "Geography Fit",
                "Gross Margin",
                "API Risk"
            ]
        }
        
        for score in scores:
            company_scores = {
                "company": score.company_name,
                "scores": {
                    "Overall Score": score.overall_score,
                    **score.component_scores,
                    "Gross Margin": score.gross_margin * 100,  # Convert to percentage
                    "API Risk": self._calculate_api_risk_score(score.api_dependency)
                }
            }
            matrix_data["companies"].append(company_scores)
        
        # Sort by overall score
        matrix_data["companies"].sort(
            key=lambda x: x["scores"]["Overall Score"], 
            reverse=True
        )
        
        return matrix_data
    
    def _calculate_api_risk_score(self, api_dependency: str) -> float:
        """
        Convert API dependency to risk score (0-100, lower is better)
        """
        risk_map = {
            "openai_heavy": 90,    # High risk
            "openai_moderate": 60,  # Medium risk
            "openai_light": 30,     # Low risk
            "own_models": 10        # Minimal risk
        }
        return risk_map.get(api_dependency, 50)
    
    def generate_investment_decision_chart(
        self,
        scores: List[CompanyScore]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive investment decision chart with analysis
        Combines entry/exit analysis with recommendations
        """
        chart_data = {
            "type": "scatter_with_analysis",
            "title": "Investment Decision Matrix: Entry Price vs Exit Multiple",
            "subtitle": "Size = Deal Quality | Color = Recommendation",
            "axes": {
                "x": {
                    "label": "Entry Valuation ($M)",
                    "scale": "log"
                },
                "y": {
                    "label": "Expected Exit Multiple",
                    "scale": "linear"
                }
            },
            "data_points": [],
            "analysis_summary": {},
            "recommendations": []
        }
        
        # Process each company
        for score in scores:
            if not score.entry_price_analysis:
                continue
                
            entry_analysis = score.entry_price_analysis
            investor_math = entry_analysis.get("investor_math", {})
            deal_analysis = entry_analysis.get("deal_analysis", {})
            
            # Determine color based on recommendation
            recommendation = deal_analysis.get("recommendation", "")
            if "STRONG BUY" in recommendation:
                color = "#10b981"  # Green
                priority = 1
            elif "BUY" in recommendation:
                color = "#3b82f6"  # Blue
                priority = 2
            elif "NEGOTIATE" in recommendation:
                color = "#f59e0b"  # Amber
                priority = 3
            else:
                color = "#ef4444"  # Red
                priority = 4
            
            # Calculate bubble size based on overall score
            bubble_size = score.overall_score
            
            # Add data point
            data_point = {
                "company": score.company_name,
                "x": investor_math.get("max_entry_valuation", 0) / 1_000_000,  # Convert to millions
                "y": score.base_case.get("exit_multiple", 0),
                "size": bubble_size,
                "color": color,
                "priority": priority,
                "details": {
                    "current_ask": deal_analysis.get("current_ask", 0) / 1_000_000,
                    "max_price": investor_math.get("max_entry_valuation", 0) / 1_000_000,
                    "valuation_gap": deal_analysis.get("gap_percentage", 0),
                    "expected_irr": score.base_case.get("irr", 0),
                    "gross_margin": score.gross_margin,
                    "nrr": score.growth_analysis.get("nrr", 1.0) if score.growth_analysis else 1.0,
                    "api_dependency": score.api_dependency,
                    "founder_risk": score.founder_profile.get("risk_score", 50) if score.founder_profile else 50,
                    "strategic_investors": bool(score.investor_map) if score.investor_map else False,
                    "deal_recommendation": recommendation
                }
            }
            chart_data["data_points"].append(data_point)
        
        # Sort by priority for recommendations
        chart_data["data_points"].sort(key=lambda x: x["priority"])
        
        # Generate analysis summary
        strong_buys = [d for d in chart_data["data_points"] if d["priority"] == 1]
        buys = [d for d in chart_data["data_points"] if d["priority"] == 2]
        passes = [d for d in chart_data["data_points"] if d["priority"] >= 4]
        
        chart_data["analysis_summary"] = {
            "total_companies": len(scores),
            "strong_buys": len(strong_buys),
            "buys": len(buys),
            "passes": len(passes),
            "avg_valuation_gap": np.mean([d["details"]["valuation_gap"] for d in chart_data["data_points"]]),
            "avg_expected_irr": np.mean([d["details"]["expected_irr"] for d in chart_data["data_points"]]),
            "insights": self._generate_portfolio_insights(chart_data["data_points"])
        }
        
        # Generate specific recommendations
        for company in strong_buys[:3]:  # Top 3 strong buys
            chart_data["recommendations"].append({
                "company": company["company"],
                "action": "INVEST NOW",
                "reasoning": f"Entry at ${company['x']:.1f}M vs ask of ${company['details']['current_ask']:.1f}M. "
                           f"Expected {company['y']:.1f}x return with {company['details']['expected_irr']:.1%} IRR.",
                "next_steps": "Schedule partner meeting immediately"
            })
        
        return chart_data
    
    def _generate_portfolio_insights(self, data_points: List[Dict]) -> List[str]:
        """Generate insights from the portfolio analysis"""
        insights = []
        
        # Valuation insights
        overvalued = [d for d in data_points if d["details"]["valuation_gap"] > 20]
        if overvalued:
            insights.append(f"⚠️ {len(overvalued)} companies are >20% overvalued relative to target returns")
        
        undervalued = [d for d in data_points if d["details"]["valuation_gap"] < -20]
        if undervalued:
            insights.append(f"✅ {len(undervalued)} companies offer >20% discount to fair value")
        
        # API dependency insights
        api_heavy = [d for d in data_points if d["details"]["api_dependency"] == "openai_heavy"]
        if api_heavy:
            insights.append(f"🤖 {len(api_heavy)} companies have heavy API dependency affecting margins")
        
        # Founder risk insights
        high_risk_founders = [d for d in data_points if d["details"]["founder_risk"] > 60]
        if high_risk_founders:
            insights.append(f"👥 {len(high_risk_founders)} companies have high founder risk scores")
        
        # Strategic investor insights
        with_strategics = [d for d in data_points if d["details"]["strategic_investors"]]
        if with_strategics:
            insights.append(f"🎯 {len(with_strategics)} companies have strategic investors (higher exit probability)")
        
        # NRR insights
        high_nrr = [d for d in data_points if d["details"]["nrr"] > 1.20]
        if high_nrr:
            insights.append(f"📈 {len(high_nrr)} companies have >120% NRR (negative churn)")
        
        return insights
    
    async def generate_portfolio_dashboard(
        self, 
        companies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate complete dashboard data for portfolio companies
        """
        # Score all companies
        scores = []
        for company_data in companies:
            try:
                score = await self.score_company(company_data)
                scores.append(score)
            except Exception as e:
                logger.error(f"Error scoring company {company_data.get('name')}: {e}")
                continue
        
        # Generate all visualizations
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_companies": len(scores),
                "average_score": np.mean([s.overall_score for s in scores]),
                "high_performers": sum(1 for s in scores if s.overall_score >= 80),
                "api_dependent": sum(1 for s in scores if s.api_dependency in ["openai_heavy", "openai_moderate"]),
                "average_gross_margin": np.mean([s.gross_margin for s in scores])
            },
            "investment_decision_chart": self.generate_investment_decision_chart(scores),
            "scenario_comparison": self.generate_scenario_comparison_chart(scores),
            "cap_table_charts": self.generate_cap_table_pie_charts(scores),
            "scoring_matrix": self.generate_scoring_matrix(scores),
            "fund_fit_analysis": self._generate_fund_fit_analysis(scores),
            "recommendations": self._generate_portfolio_recommendations(scores),
            "citations": self._generate_citations(scores)
        }
        
        return dashboard
    
    def _generate_portfolio_recommendations(
        self, 
        scores: List[CompanyScore]
    ) -> List[Dict[str, str]]:
        """
        Generate portfolio-level recommendations
        """
        recommendations = []
        
        # Identify top performers
        top_companies = [s for s in scores if s.overall_score >= 80]
        if top_companies:
            recommendations.append({
                "type": "opportunity",
                "message": f"Focus on {len(top_companies)} high-scoring companies",
                "companies": [c.company_name for c in top_companies[:3]]
            })
        
        # API dependency warning
        api_heavy = [s for s in scores if s.api_dependency == "openai_heavy"]
        if len(api_heavy) > len(scores) * 0.3:
            recommendations.append({
                "type": "risk",
                "message": f"⚠️ {len(api_heavy)} companies have heavy API dependency - diversification needed",
                "companies": [c.company_name for c in api_heavy]
            })
        
        # Gross margin concerns
        low_margin = [s for s in scores if s.gross_margin < 0.60]
        if low_margin:
            recommendations.append({
                "type": "concern",
                "message": f"📉 {len(low_margin)} companies have gross margins below 60%",
                "companies": [c.company_name for c in low_margin]
            })
        
        # Timing opportunities
        good_timing = [
            s for s in scores 
            if s.component_scores.get("timing_fit", 0) >= 80
        ]
        if good_timing:
            recommendations.append({
                "type": "action",
                "message": f"⏰ {len(good_timing)} companies raising soon - move quickly",
                "companies": [c.company_name for c in good_timing[:3]]
            })
        
        return recommendations
    
    def _generate_fund_fit_analysis(self, scores: List[CompanyScore]) -> Dict[str, Any]:
        """
        Generate comprehensive fund fit analysis with ownership calculations
        """
        fund_analysis = {
            "fund_parameters": {
                "target_stage": "Series A-B",
                "check_size": "$5-15M",
                "target_ownership": "10-20%",
                "sectors": ["SaaS", "Fintech", "AI/ML", "Developer Tools"]
            },
            "portfolio_fit": [],
            "ownership_analysis": []
        }
        
        for score in scores:
            # Calculate potential ownership based on entry price
            if score.entry_price_analysis:
                max_entry = score.entry_price_analysis.get("investor_math", {}).get("max_entry_valuation", 100_000_000)
                check_sizes = [5_000_000, 10_000_000, 15_000_000]  # $5M, $10M, $15M
                
                ownership_scenarios = []
                for check_size in check_sizes:
                    ownership_pct = (check_size / max_entry) * 100
                    diluted_ownership = ownership_pct * 0.75  # Account for future dilution
                    
                    ownership_scenarios.append({
                        "check_size": check_size,
                        "initial_ownership": round(ownership_pct, 1),
                        "diluted_ownership": round(diluted_ownership, 1),
                        "board_seat_likely": ownership_pct >= 10,
                        "pro_rata_rights": ownership_pct >= 5
                    })
                
                fund_analysis["ownership_analysis"].append({
                    "company": score.company_name,
                    "scenarios": ownership_scenarios,
                    "recommended_check": 10_000_000 if max_entry > 50_000_000 else 5_000_000
                })
            
            # Assess fit with fund thesis
            fit_score = 0
            fit_reasons = []
            
            # Stage fit
            if score.component_scores.get("stage_fit", 0) >= 70:
                fit_score += 25
                fit_reasons.append("Stage aligned with fund focus")
            
            # Sector fit
            if score.component_scores.get("sector_fit", 0) >= 70:
                fit_score += 25
                fit_reasons.append("Sector matches fund expertise")
            
            # Return potential
            if score.component_scores.get("return_potential", 0) >= 80:
                fit_score += 25
                fit_reasons.append("Strong return potential (>10x)")
            
            # Check size fit
            if score.component_scores.get("check_size_fit", 0) >= 70:
                fit_score += 25
                fit_reasons.append("Check size within fund parameters")
            
            fund_analysis["portfolio_fit"].append({
                "company": score.company_name,
                "fit_score": fit_score,
                "fit_category": "Strong" if fit_score >= 75 else "Good" if fit_score >= 50 else "Weak",
                "reasons": fit_reasons,
                "concerns": self._identify_fund_concerns(score)
            })
        
        # Sort by fit score
        fund_analysis["portfolio_fit"].sort(key=lambda x: x["fit_score"], reverse=True)
        
        return fund_analysis
    
    def _identify_fund_concerns(self, score: CompanyScore) -> List[str]:
        """Identify concerns for fund fit"""
        concerns = []
        
        if score.api_dependency == "openai_heavy":
            concerns.append("Heavy API dependency affects margins")
        
        if score.gross_margin < 0.70:
            concerns.append(f"Below target gross margin ({score.gross_margin:.0%} vs 70% target)")
        
        if score.founder_profile and score.founder_profile.get("risk_score", 0) > 60:
            concerns.append("Founder risk profile requires attention")
        
        if score.entry_price_analysis:
            gap = score.entry_price_analysis.get("deal_analysis", {}).get("gap_percentage", 0)
            if gap > 30:
                concerns.append(f"Valuation {gap:.0f}% above target")
        
        return concerns
    
    def _generate_citations(self, scores: List[CompanyScore]) -> Dict[str, List[str]]:
        """
        Generate citations and data sources for all analysis
        """
        from datetime import datetime
        
        citations = {
            "data_sources": [
                {"source": "Company Funding Data", "date": datetime.now().strftime("%Y-%m-%d"), "type": "primary"},
                {"source": "SVB State of the Markets Report", "date": "2024-Q4", "type": "benchmark"},
                {"source": "Carta Equity Report", "date": "2024", "type": "benchmark"},
                {"source": "PitchBook VC Valuations", "date": "2024", "type": "market_data"},
                {"source": "Industry Analysis", "date": datetime.now().strftime("%Y-%m-%d"), "type": "derived"}
            ],
            "methodology": [
                "Option exercise rate: 25% (Carta industry benchmark)",
                "API dependency penalties: -25% (heavy), -15% (moderate), -5% (light) on gross margins",
                "Growth deceleration: 70% YoY decay factor with 25% floor",
                "Exit multiples: Standard SaaS 5-7x, Strategic AI up to 14.66x (OpenAI/Stansig benchmark at $75M ARR)",
                "Dilution per round: 15-25% typical (stage-dependent)",
                "NRR impact: >120% adds 2x to multiple, >110% adds 1x, >100% adds 0.5x"
            ],
            "company_specific": {}
        }
        
        # Add company-specific citations
        for score in scores:
            company_citations = []
            
            # Funding citations
            if score.investor_map:
                for round_name, investors in score.investor_map.items():
                    if investors:
                        company_citations.append(
                            f"{round_name}: {', '.join(investors[:3])} {'et al.' if len(investors) > 3 else ''}"
                        )
            
            # Growth analysis citations
            if score.growth_analysis:
                nrr = score.growth_analysis.get("nrr", 1.0)
                company_citations.append(f"NRR: {nrr:.0%} (estimated from growth patterns)")
                
                current_multiple = score.growth_analysis.get("current_multiple", 0)
                if current_multiple > 0:
                    company_citations.append(f"Current revenue multiple: {current_multiple:.1f}x")
            
            # Entry price citations
            if score.entry_price_analysis:
                deal = score.entry_price_analysis.get("deal_analysis", {})
                if deal.get("recommendation"):
                    company_citations.append(f"Deal recommendation: {deal['recommendation']}")
            
            # API dependency citation
            company_citations.append(f"API dependency: {score.api_dependency}")
            company_citations.append(f"Adjusted gross margin: {score.gross_margin:.0%}")
            
            citations["company_specific"][score.company_name] = company_citations
        
        return citations