"""
MAWorkflowService - Complete M&A workflow orchestration  
Handles sophisticated M&A modeling from deal origination to valuation
Supports queries like: "model an M&A of Stripe and Dansig"
"""

import asyncio
import aiohttp
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import math

from app.core.config import settings
from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.valuation_engine_service import ValuationEngineService

logger = logging.getLogger(__name__)


class DealType(str, Enum):
    """Types of M&A deals"""
    STRATEGIC_ACQUISITION = "strategic"
    FINANCIAL_ACQUISITION = "financial"
    MERGER_OF_EQUALS = "merger"
    ACQUIHIRE = "acquihire"
    ASSET_PURCHASE = "asset_purchase"
    ROLLUP = "rollup"


class SynergyType(str, Enum):
    """Types of synergies in M&A"""
    REVENUE_SYNERGIES = "revenue"
    COST_SYNERGIES = "cost"
    TAX_SYNERGIES = "tax"
    FINANCIAL_SYNERGIES = "financial"
    OPERATIONAL_SYNERGIES = "operational"


class IntegrationRisk(str, Enum):
    """Integration risk levels"""
    LOW = "low"
    MODERATE = "moderate" 
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class CompanyFinancials:
    """Comprehensive financial data for M&A analysis"""
    company_name: str
    
    # Income Statement (in millions)
    revenue: float = 0.0
    revenue_growth: float = 0.0  # % growth rate
    gross_profit: float = 0.0
    gross_margin: float = 0.0
    ebitda: float = 0.0
    ebitda_margin: float = 0.0
    ebit: float = 0.0
    net_income: float = 0.0
    
    # Balance Sheet (in millions)
    total_assets: float = 0.0
    cash: float = 0.0
    total_debt: float = 0.0
    shareholders_equity: float = 0.0
    
    # Cash Flow (in millions)
    operating_cash_flow: float = 0.0
    capex: float = 0.0
    free_cash_flow: float = 0.0
    
    # Valuation Metrics
    market_cap: float = 0.0
    enterprise_value: float = 0.0
    
    # Operating Metrics
    employees: int = 0
    customers: int = 0
    arr: float = 0.0  # Annual Recurring Revenue
    nrr: float = 0.0  # Net Revenue Retention
    cac: float = 0.0  # Customer Acquisition Cost
    ltv: float = 0.0  # Lifetime Value
    
    # Market Data
    industry: str = ""
    geography: str = ""
    business_model: str = ""
    
    # Quality scores (0-100)
    financial_quality: float = 0.0
    growth_quality: float = 0.0
    profitability_score: float = 0.0


@dataclass  
class SynergyAnalysis:
    """Detailed synergy analysis for M&A"""
    synergy_type: SynergyType
    description: str
    annual_value: float  # Annual synergy value in millions
    realization_timeline: int  # Months to full realization
    probability: float  # 0-1 probability of achieving
    one_time_cost: float = 0.0  # Implementation cost
    risk_factors: List[str] = field(default_factory=list)
    
    @property
    def npv_10_year(self) -> float:
        """10-year NPV of synergy at 10% discount rate"""
        if self.realization_timeline <= 12:
            # Full value from year 1
            return self.annual_value * self.probability * 6.144  # 10-year annuity factor
        else:
            # Ramp up over realization timeline
            years_to_full = self.realization_timeline / 12
            ramp_value = self.annual_value * self.probability * (10 - years_to_full) / 10
            return ramp_value * 6.144
    

@dataclass
class DealStructure:
    """M&A deal structure and terms"""
    deal_type: DealType
    consideration_mix: Dict[str, float]  # {"cash": 0.6, "stock": 0.4}
    total_consideration: float  # Total deal value in millions
    
    # Pricing metrics
    revenue_multiple: float = 0.0
    ebitda_multiple: float = 0.0
    premium_to_market: float = 0.0  # % premium to current market cap
    
    # Deal terms
    closing_conditions: List[str] = field(default_factory=list)
    regulatory_approval_required: bool = False
    break_fee: float = 0.0
    estimated_closing_timeline: int = 6  # Months
    
    # Financing structure
    debt_financing: float = 0.0
    equity_financing: float = 0.0
    cash_on_hand: float = 0.0


@dataclass
class MAValuation:
    """Complete M&A valuation analysis"""
    target_company: str
    acquirer_company: str
    
    # Standalone valuations
    target_standalone_value: float
    acquirer_standalone_value: float
    
    # Synergy analysis  
    total_synergies_npv: float
    synergy_breakdown: List[SynergyAnalysis] = field(default_factory=list)
    
    # Combined entity valuation
    combined_entity_value: float
    value_creation: float  # Total value created
    value_to_acquirer: float  # Net value to acquirer shareholders
    
    # Deal metrics
    deal_structure: Optional[DealStructure] = None
    irr_to_acquirer: float = 0.0
    payback_period: float = 0.0  # Years
    
    # Risk assessment
    integration_risk: IntegrationRisk = IntegrationRisk.MODERATE
    execution_probability: float = 0.85
    regulatory_risk: float = 0.1
    
    # Financial projections (10-year)
    projected_financials: Dict[str, List[float]] = field(default_factory=dict)
    

class MAWorkflowService:
    """
    Complete M&A workflow service for institutional-grade deal analysis
    """
    
    def __init__(self):
        self.tavily_api_key = settings.TAVILY_API_KEY
        self.session = None
        self.gap_filler = IntelligentGapFiller()
        self.valuation_engine = ValuationEngineService()
        
        # Industry-specific synergy benchmarks
        self.synergy_benchmarks = {
            "fintech": {
                "revenue_synergies": 0.15,  # 15% revenue uplift potential
                "cost_synergies": 0.25,     # 25% cost reduction potential
                "integration_complexity": 0.7  # 0-1 scale
            },
            "saas": {
                "revenue_synergies": 0.20,
                "cost_synergies": 0.30,
                "integration_complexity": 0.5
            },
            "healthcare": {
                "revenue_synergies": 0.10,
                "cost_synergies": 0.20,
                "integration_complexity": 0.9
            },
            "default": {
                "revenue_synergies": 0.12,
                "cost_synergies": 0.22,
                "integration_complexity": 0.6
            }
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def model_acquisition(
        self,
        acquirer: str,
        target: str,
        deal_rationale: Optional[str] = None
    ) -> MAValuation:
        """
        Model a complete M&A transaction with DCF, synergies, and deal structure
        
        Args:
            acquirer: Acquiring company name
            target: Target company name  
            deal_rationale: Optional strategic rationale for deal
            
        Returns:
            Complete MAValuation with financial models and deal analysis
        """
        logger.info(f"Modeling M&A: {acquirer} acquiring {target}")
        
        try:
            # Step 1: Gather comprehensive financial data for both companies
            acquirer_data, target_data = await asyncio.gather(
                self._get_company_financials(acquirer),
                self._get_company_financials(target)
            )
            
            # Step 2: Calculate standalone valuations using multiple methods
            acquirer_valuation, target_valuation = await asyncio.gather(
                self._calculate_standalone_valuation(acquirer_data),
                self._calculate_standalone_valuation(target_data)
            )
            
            # Step 3: Identify and quantify synergies
            synergies = await self._identify_synergies(
                acquirer_data, target_data, deal_rationale
            )
            
            # Step 4: Model combined entity and integration
            combined_model = await self._model_combined_entity(
                acquirer_data, target_data, synergies
            )
            
            # Step 5: Optimize deal structure and pricing
            deal_structure = await self._optimize_deal_structure(
                acquirer_data, target_data, target_valuation, synergies
            )
            
            # Step 6: Calculate returns and risks
            returns_analysis = await self._calculate_deal_returns(
                acquirer_valuation, target_valuation, synergies, deal_structure
            )
            
            # Step 7: Assess integration risks
            risk_assessment = await self._assess_integration_risks(
                acquirer_data, target_data, deal_structure
            )
            
            # Build comprehensive valuation result
            ma_valuation = MAValuation(
                target_company=target,
                acquirer_company=acquirer,
                target_standalone_value=target_valuation,
                acquirer_standalone_value=acquirer_valuation,
                total_synergies_npv=sum(s.npv_10_year for s in synergies),
                synergy_breakdown=synergies,
                combined_entity_value=combined_model["enterprise_value"],
                value_creation=returns_analysis["value_creation"],
                value_to_acquirer=returns_analysis["acquirer_value"],
                deal_structure=deal_structure,
                irr_to_acquirer=returns_analysis["irr"],
                payback_period=returns_analysis["payback_years"],
                integration_risk=risk_assessment["integration_risk"],
                execution_probability=risk_assessment["execution_probability"],
                regulatory_risk=risk_assessment["regulatory_risk"],
                projected_financials=combined_model["projections"]
            )
            
            return ma_valuation
            
        except Exception as e:
            logger.error(f"Error in model_acquisition: {str(e)}")
            # Return minimal valuation with error info
            return MAValuation(
                target_company=target,
                acquirer_company=acquirer,
                target_standalone_value=0.0,
                acquirer_standalone_value=0.0,
                total_synergies_npv=0.0
            )

    async def identify_strategic_acquirers(
        self,
        target_company: str,
        criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify potential strategic acquirers for a target company
        
        Args:
            target_company: Target company to find acquirers for
            criteria: Optional filtering criteria
            
        Returns:
            List of potential acquirers with strategic fit scores
        """
        try:
            # Get target company data
            target_data = await self._get_company_financials(target_company)
            
            # Search for strategic acquirers
            acquirer_queries = [
                f"{target_data.industry} companies acquisitions strategic buyers",
                f"{target_data.business_model} consolidation market leaders",
                f"companies competing with {target_company}",
                f"larger players {target_data.industry} M&A activity"
            ]
            
            # Execute parallel searches
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            search_tasks = [self._execute_tavily_search(query) for query in acquirer_queries]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Extract and score potential acquirers
            potential_acquirers = self._extract_potential_acquirers(
                search_results, target_data
            )
            
            # Calculate strategic fit scores
            scored_acquirers = []
            for acquirer in potential_acquirers:
                try:
                    acquirer_data = await self._get_company_financials(acquirer["name"])
                    fit_score = self._calculate_strategic_fit(target_data, acquirer_data)
                    
                    scored_acquirers.append({
                        "name": acquirer["name"],
                        "strategic_fit_score": fit_score,
                        "financial_capacity": acquirer_data.market_cap > target_data.market_cap * 3,
                        "industry_overlap": acquirer_data.industry == target_data.industry,
                        "revenue_multiple": acquirer_data.revenue / max(target_data.revenue, 1),
                        "synergy_potential": self._estimate_synergy_potential(target_data, acquirer_data),
                        "deal_precedents": acquirer.get("recent_deals", [])
                    })
                    
                except Exception as e:
                    logger.warning(f"Error analyzing acquirer {acquirer['name']}: {str(e)}")
                    continue
            
            # Sort by strategic fit score
            return sorted(scored_acquirers, key=lambda x: x["strategic_fit_score"], reverse=True)[:10]
            
        except Exception as e:
            logger.error(f"Error in identify_strategic_acquirers: {str(e)}")
            return []

    async def calculate_synergy_value(
        self,
        acquirer: str,
        target: str,
        synergy_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Calculate detailed synergy analysis for M&A transaction
        
        Args:
            acquirer: Acquiring company
            target: Target company
            synergy_types: Optional list of synergy types to focus on
            
        Returns:
            Comprehensive synergy analysis with NPV calculations
        """
        try:
            # Get financial data
            acquirer_data, target_data = await asyncio.gather(
                self._get_company_financials(acquirer),
                self._get_company_financials(target)
            )
            
            # Identify synergies
            synergies = await self._identify_synergies(
                acquirer_data, target_data, synergy_types
            )
            
            # Calculate total synergy value
            total_synergy_npv = sum(s.npv_10_year for s in synergies)
            total_implementation_cost = sum(s.one_time_cost for s in synergies)
            
            return {
                "total_synergy_npv": total_synergy_npv,
                "net_synergy_value": total_synergy_npv - total_implementation_cost,
                "implementation_cost": total_implementation_cost,
                "synergy_breakdown": [
                    {
                        "type": s.synergy_type.value,
                        "description": s.description,
                        "annual_value": s.annual_value,
                        "npv_10_year": s.npv_10_year,
                        "probability": s.probability,
                        "implementation_cost": s.one_time_cost,
                        "timeline_months": s.realization_timeline
                    }
                    for s in synergies
                ],
                "synergy_as_percent_of_deal": (total_synergy_npv / max(target_data.market_cap, 1)) * 100
            }
            
        except Exception as e:
            logger.error(f"Error in calculate_synergy_value: {str(e)}")
            return {"total_synergy_npv": 0.0, "synergy_breakdown": []}

    async def optimize_deal_structure(
        self,
        acquirer: str,
        target: str,
        max_price: Optional[float] = None,
        financing_constraints: Optional[Dict[str, Any]] = None
    ) -> DealStructure:
        """
        Optimize M&A deal structure considering tax, financing, and strategic factors
        
        Args:
            acquirer: Acquiring company
            target: Target company  
            max_price: Optional maximum price constraint
            financing_constraints: Optional financing limitations
            
        Returns:
            Optimized DealStructure with consideration mix and terms
        """
        try:
            # Get company data and valuations
            acquirer_data, target_data = await asyncio.gather(
                self._get_company_financials(acquirer),
                self._get_company_financials(target)
            )
            
            target_valuation = await self._calculate_standalone_valuation(target_data)
            
            # Calculate optimal consideration mix
            optimal_mix = self._calculate_optimal_consideration_mix(
                acquirer_data, target_data, financing_constraints
            )
            
            # Determine appropriate premium
            market_premium = self._calculate_market_premium(target_data, acquirer_data)
            
            # Calculate total consideration
            total_consideration = target_valuation * (1 + market_premium)
            
            if max_price and total_consideration > max_price:
                total_consideration = max_price
                market_premium = (max_price / target_valuation) - 1
            
            # Structure the deal
            deal_structure = DealStructure(
                deal_type=self._determine_deal_type(acquirer_data, target_data),
                consideration_mix=optimal_mix,
                total_consideration=total_consideration,
                revenue_multiple=total_consideration / max(target_data.revenue, 1),
                ebitda_multiple=total_consideration / max(target_data.ebitda, 1) if target_data.ebitda > 0 else 0,
                premium_to_market=market_premium * 100,
                closing_conditions=self._determine_closing_conditions(acquirer_data, target_data),
                regulatory_approval_required=self._requires_regulatory_approval(acquirer_data, target_data),
                break_fee=total_consideration * 0.03,  # 3% break fee standard
                estimated_closing_timeline=self._estimate_closing_timeline(acquirer_data, target_data),
                debt_financing=total_consideration * optimal_mix.get("debt", 0.0),
                equity_financing=total_consideration * optimal_mix.get("equity", 0.0),
                cash_on_hand=total_consideration * optimal_mix.get("cash", 0.0)
            )
            
            return deal_structure
            
        except Exception as e:
            logger.error(f"Error in optimize_deal_structure: {str(e)}")
            return DealStructure(
                deal_type=DealType.STRATEGIC_ACQUISITION,
                consideration_mix={"cash": 0.6, "stock": 0.4},
                total_consideration=0.0
            )

    # Private helper methods

    async def _get_company_financials(self, company_name: str) -> CompanyFinancials:
        """Gather comprehensive financial data for a company"""
        try:
            # Build financial data search queries
            financial_queries = [
                f"{company_name} revenue financials annual report",
                f"{company_name} valuation market cap enterprise value",
                f"{company_name} employees customers business model",
                f"{company_name} growth metrics ARR NRR LTV CAC"
            ]
            
            # Execute parallel searches
            if not self.session:
                self.session = aiohttp.ClientSession()
                
            search_tasks = [self._execute_tavily_search(query) for query in financial_queries]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Extract financial metrics
            financials = CompanyFinancials(company_name=company_name)
            
            for result_set in search_results:
                if isinstance(result_set, Exception):
                    continue
                    
                results = result_set.get("results", [])
                for result in results:
                    self._extract_financial_metrics(result, financials)
            
            # Use IntelligentGapFiller for missing metrics
            financials = await self._fill_missing_financials(financials)
            
            # Calculate derived metrics
            self._calculate_derived_metrics(financials)
            
            return financials
            
        except Exception as e:
            logger.error(f"Error getting financials for {company_name}: {str(e)}")
            return CompanyFinancials(company_name=company_name)

    async def _calculate_standalone_valuation(self, company_data: CompanyFinancials) -> float:
        """Calculate standalone company valuation using multiple methods"""
        try:
            # Use ValuationEngineService for comprehensive valuation
            valuation_data = {
                "company_name": company_data.company_name,
                "revenue": company_data.revenue,
                "growth_rate": company_data.revenue_growth,
                "ebitda": company_data.ebitda,
                "ebitda_margin": company_data.ebitda_margin,
                "free_cash_flow": company_data.free_cash_flow,
                "industry": company_data.industry,
                "stage": "growth" if company_data.revenue_growth > 0.3 else "mature"
            }
            
            valuation_result = await self.valuation_engine.calculate_valuation(valuation_data)
            
            # Return primary valuation or market cap if available
            if hasattr(valuation_result, 'fair_value') and valuation_result.fair_value:
                return valuation_result.fair_value
            elif company_data.market_cap > 0:
                return company_data.market_cap
            else:
                # Fallback to revenue multiple
                industry_multiple = self._get_industry_revenue_multiple(company_data.industry)
                return company_data.revenue * industry_multiple
                
        except Exception as e:
            logger.error(f"Error calculating valuation: {str(e)}")
            return company_data.market_cap if company_data.market_cap > 0 else 0.0

    async def _identify_synergies(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials,
        deal_rationale: Optional[str] = None
    ) -> List[SynergyAnalysis]:
        """Identify and quantify synergies between acquirer and target"""
        synergies = []
        
        # Get industry benchmarks
        industry = target_data.industry.lower() or "default"
        benchmarks = self.synergy_benchmarks.get(industry, self.synergy_benchmarks["default"])
        
        # Revenue Synergies
        revenue_synergy = SynergyAnalysis(
            synergy_type=SynergyType.REVENUE_SYNERGIES,
            description=f"Cross-selling, market expansion, and pricing power improvements",
            annual_value=target_data.revenue * benchmarks["revenue_synergies"],
            realization_timeline=18,  # 18 months to realize
            probability=0.7,
            one_time_cost=target_data.revenue * 0.05,  # 5% of revenue implementation cost
            risk_factors=["Customer overlap", "Sales force integration", "Brand conflicts"]
        )
        synergies.append(revenue_synergy)
        
        # Cost Synergies
        combined_costs = (acquirer_data.revenue - acquirer_data.ebitda) + (target_data.revenue - target_data.ebitda)
        cost_synergy = SynergyAnalysis(
            synergy_type=SynergyType.COST_SYNERGIES,
            description="Elimination of duplicate functions, economies of scale, vendor consolidation",
            annual_value=combined_costs * benchmarks["cost_synergies"],
            realization_timeline=12,  # 12 months to realize
            probability=0.85,
            one_time_cost=target_data.employees * 0.1,  # Severance and integration costs
            risk_factors=["Regulatory restrictions", "Key talent retention", "System integration"]
        )
        synergies.append(cost_synergy)
        
        # Financial Synergies
        if target_data.total_debt > acquirer_data.total_debt:
            # Target can benefit from acquirer's lower cost of capital
            debt_savings = target_data.total_debt * 0.02  # 200 bps savings
            financial_synergy = SynergyAnalysis(
                synergy_type=SynergyType.FINANCIAL_SYNERGIES,
                description="Lower cost of capital and improved access to capital markets",
                annual_value=debt_savings,
                realization_timeline=6,
                probability=0.95,
                one_time_cost=0.0,
                risk_factors=["Credit rating changes"]
            )
            synergies.append(financial_synergy)
        
        # Tax Synergies (if different geographies)
        if acquirer_data.geography != target_data.geography:
            tax_benefit = target_data.ebit * 0.03  # 3% tax efficiency gain
            tax_synergy = SynergyAnalysis(
                synergy_type=SynergyType.TAX_SYNERGIES,
                description="Tax optimization through geographic arbitrage and structure optimization",
                annual_value=tax_benefit,
                realization_timeline=24,
                probability=0.6,
                one_time_cost=5.0,  # Legal and advisory costs
                risk_factors=["Tax law changes", "Regulatory scrutiny"]
            )
            synergies.append(tax_synergy)
        
        return synergies

    async def _model_combined_entity(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials,
        synergies: List[SynergyAnalysis]
    ) -> Dict[str, Any]:
        """Model the combined entity with synergies over 10-year period"""
        
        # Start with combined baseline
        combined_revenue = acquirer_data.revenue + target_data.revenue
        combined_ebitda = acquirer_data.ebitda + target_data.ebitda
        
        # Calculate synergy realization schedule
        revenue_synergy_annual = sum(s.annual_value for s in synergies if s.synergy_type == SynergyType.REVENUE_SYNERGIES)
        cost_synergy_annual = sum(s.annual_value for s in synergies if s.synergy_type == SynergyType.COST_SYNERGIES)
        
        # 10-year projections
        years = 10
        projections = {
            "revenue": [],
            "ebitda": [],
            "free_cash_flow": [],
            "enterprise_value": []
        }
        
        # Blended growth rate
        acquirer_weight = acquirer_data.revenue / combined_revenue
        target_weight = target_data.revenue / combined_revenue
        blended_growth = (acquirer_data.revenue_growth * acquirer_weight) + (target_data.revenue_growth * target_weight)
        
        for year in range(1, years + 1):
            # Base revenue growth
            year_revenue = combined_revenue * ((1 + blended_growth) ** year)
            
            # Add revenue synergies (ramp over 2 years)
            synergy_realization = min(1.0, year / 2.0)
            year_revenue += revenue_synergy_annual * synergy_realization
            
            # EBITDA with cost synergies  
            base_ebitda = year_revenue * (combined_ebitda / combined_revenue)  # Maintain margin
            year_ebitda = base_ebitda + (cost_synergy_annual * synergy_realization)
            
            # Free cash flow (assume 80% conversion)
            year_fcf = year_ebitda * 0.8
            
            projections["revenue"].append(year_revenue)
            projections["ebitda"].append(year_ebitda)
            projections["free_cash_flow"].append(year_fcf)
        
        # Calculate terminal enterprise value (exit multiple)
        terminal_ebitda = projections["ebitda"][-1]
        industry_multiple = self._get_industry_ebitda_multiple(target_data.industry)
        terminal_value = terminal_ebitda * industry_multiple
        
        # DCF valuation
        discount_rate = self._calculate_wacc(acquirer_data, target_data)
        
        pv_cash_flows = sum(
            fcf / ((1 + discount_rate) ** year) 
            for year, fcf in enumerate(projections["free_cash_flow"], 1)
        )
        
        pv_terminal_value = terminal_value / ((1 + discount_rate) ** years)
        enterprise_value = pv_cash_flows + pv_terminal_value
        
        return {
            "enterprise_value": enterprise_value,
            "projections": projections,
            "terminal_value": terminal_value,
            "discount_rate": discount_rate,
            "pv_cash_flows": pv_cash_flows,
            "pv_terminal_value": pv_terminal_value
        }

    async def _optimize_deal_structure(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials,
        target_valuation: float,
        synergies: List[SynergyAnalysis]
    ) -> DealStructure:
        """Optimize deal structure considering all factors"""
        
        # Calculate total synergy value
        total_synergy_npv = sum(s.npv_10_year for s in synergies)
        
        # Determine maximum price (standalone value + share of synergies)
        max_reasonable_price = target_valuation + (total_synergy_npv * 0.3)  # Target gets 30% of synergies
        
        # Calculate market premium based on industry and deal characteristics
        base_premium = 0.25  # 25% base premium
        
        # Adjust premium based on strategic importance
        if target_data.revenue_growth > 0.5:  # High growth target
            base_premium += 0.10
        if total_synergy_npv > target_valuation:  # High synergy potential
            base_premium += 0.15
        
        total_consideration = target_valuation * (1 + base_premium)
        total_consideration = min(total_consideration, max_reasonable_price)
        
        # Optimize consideration mix
        consideration_mix = self._calculate_optimal_consideration_mix(
            acquirer_data, target_data, {}
        )
        
        return DealStructure(
            deal_type=DealType.STRATEGIC_ACQUISITION,
            consideration_mix=consideration_mix,
            total_consideration=total_consideration,
            revenue_multiple=total_consideration / max(target_data.revenue, 1),
            ebitda_multiple=total_consideration / max(target_data.ebitda, 1) if target_data.ebitda > 0 else 0,
            premium_to_market=base_premium * 100,
            closing_conditions=["Regulatory approval", "Shareholder approval", "Material adverse change clause"],
            regulatory_approval_required=total_consideration > 1000,  # >$1B requires approval
            break_fee=total_consideration * 0.03,
            estimated_closing_timeline=6 if total_consideration < 1000 else 12
        )

    async def _calculate_deal_returns(
        self,
        acquirer_valuation: float,
        target_valuation: float,
        synergies: List[SynergyAnalysis],
        deal_structure: DealStructure
    ) -> Dict[str, Any]:
        """Calculate returns and value creation for the deal"""
        
        total_synergy_npv = sum(s.npv_10_year for s in synergies)
        total_consideration = deal_structure.total_consideration
        
        # Value creation calculation
        combined_standalone = acquirer_valuation + target_valuation
        combined_with_synergies = combined_standalone + total_synergy_npv
        value_creation = combined_with_synergies - (acquirer_valuation + total_consideration)
        
        # IRR calculation (simplified)
        annual_synergy_value = sum(s.annual_value for s in synergies)
        if total_consideration > 0:
            irr = (annual_synergy_value / total_consideration) - 0.1  # Rough IRR estimate
        else:
            irr = 0.0
        
        # Payback period
        payback_years = total_consideration / max(annual_synergy_value, 1) if annual_synergy_value > 0 else float('inf')
        
        return {
            "value_creation": value_creation,
            "acquirer_value": value_creation,  # Simplified - acquirer gets all value creation
            "irr": max(0, irr),
            "payback_years": min(payback_years, 20)  # Cap at 20 years
        }

    async def _assess_integration_risks(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials,
        deal_structure: DealStructure
    ) -> Dict[str, Any]:
        """Assess integration risks and execution probability"""
        
        risk_factors = []
        risk_score = 0.0  # 0 = low risk, 1 = high risk
        
        # Size mismatch risk
        size_ratio = target_data.revenue / max(acquirer_data.revenue, 1)
        if size_ratio > 0.5:  # Large acquisition relative to acquirer
            risk_score += 0.2
            risk_factors.append("Large acquisition relative to acquirer size")
        
        # Cultural/geographic integration risk
        if acquirer_data.geography != target_data.geography:
            risk_score += 0.15
            risk_factors.append("Cross-border integration complexity")
        
        # Technology integration risk
        if acquirer_data.business_model != target_data.business_model:
            risk_score += 0.1
            risk_factors.append("Different business model integration")
        
        # Financial risk
        if target_data.ebitda < 0:  # Unprofitable target
            risk_score += 0.25
            risk_factors.append("Target company unprofitability")
        
        # Determine integration risk level
        if risk_score < 0.3:
            integration_risk = IntegrationRisk.LOW
        elif risk_score < 0.6:
            integration_risk = IntegrationRisk.MODERATE
        elif risk_score < 0.8:
            integration_risk = IntegrationRisk.HIGH
        else:
            integration_risk = IntegrationRisk.EXTREME
        
        # Execution probability
        execution_probability = max(0.3, 1.0 - risk_score)
        
        # Regulatory risk
        regulatory_risk = 0.1  # Base 10%
        if deal_structure.total_consideration > 5000:  # >$5B deals
            regulatory_risk += 0.2
        if acquirer_data.industry == target_data.industry:  # Horizontal integration
            regulatory_risk += 0.15
        
        return {
            "integration_risk": integration_risk,
            "execution_probability": execution_probability,
            "regulatory_risk": min(0.8, regulatory_risk),
            "risk_factors": risk_factors,
            "overall_risk_score": risk_score
        }

    # Additional helper methods for financial extraction and calculations
    
    async def _execute_tavily_search(self, query: str) -> Dict[str, Any]:
        """Execute Tavily search for financial data"""
        try:
            tavily_url = "https://api.tavily.com/search"
            
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 8,
                "include_domains": [
                    "sec.gov",
                    "finance.yahoo.com",
                    "bloomberg.com",
                    "marketwatch.com",
                    "crunchbase.com",
                    "pitchbook.com"
                ]
            }
            
            async with self.session.post(tavily_url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"results": []}
                    
        except Exception as e:
            logger.error(f"Tavily search error: {str(e)}")
            return {"results": []}

    def _extract_financial_metrics(self, result: Dict[str, Any], financials: CompanyFinancials):
        """Extract financial metrics from search results"""
        content = (result.get("title", "") + " " + result.get("content", "")).lower()
        
        import re
        
        # Revenue extraction
        revenue_patterns = [
            r'revenue of \$?([\d.,]+)\s?([mb]illion)?',
            r'sales of \$?([\d.,]+)\s?([mb]illion)?',
            r'\$?([\d.,]+)\s?([mb]illion) in revenue'
        ]
        
        for pattern in revenue_patterns:
            match = re.search(pattern, content)
            if match and financials.revenue == 0:
                try:
                    amount = float(match.group(1).replace(",", ""))
                    multiplier = match.group(2) if len(match.groups()) > 1 else None
                    
                    if multiplier == "billion":
                        amount *= 1000
                    elif not multiplier and amount < 100:  # Assume millions if no unit and reasonable size
                        pass  # Already in millions
                    elif not multiplier and amount > 1000:
                        amount = amount / 1000  # Convert to millions
                    
                    financials.revenue = amount
                    break
                except:
                    continue
        
        # Market cap extraction
        market_cap_patterns = [
            r'market cap of \$?([\d.,]+)\s?([mb]illion)?',
            r'valued at \$?([\d.,]+)\s?([mb]illion)?'
        ]
        
        for pattern in market_cap_patterns:
            match = re.search(pattern, content)
            if match and financials.market_cap == 0:
                try:
                    amount = float(match.group(1).replace(",", ""))
                    multiplier = match.group(2) if len(match.groups()) > 1 else None
                    
                    if multiplier == "billion":
                        amount *= 1000
                    
                    financials.market_cap = amount
                    break
                except:
                    continue

    async def _fill_missing_financials(self, financials: CompanyFinancials) -> CompanyFinancials:
        """Use IntelligentGapFiller to estimate missing financial metrics"""
        try:
            # Create data dict for gap filler
            company_data = {
                "revenue": financials.revenue,
                "market_cap": financials.market_cap,
                "industry": financials.industry,
                "stage": "growth" if financials.revenue_growth > 0.3 else "mature"
            }
            
            # Use gap filler to estimate missing metrics
            if financials.ebitda == 0 and financials.revenue > 0:
                ebitda_result = await self.gap_filler.infer_from_stage_benchmarks(company_data, "ebitda_margin")
                if hasattr(ebitda_result, 'value'):
                    financials.ebitda_margin = ebitda_result.value
                    financials.ebitda = financials.revenue * financials.ebitda_margin
            
            if financials.employees == 0 and financials.revenue > 0:
                # Simple heuristic: $200K revenue per employee for tech companies
                financials.employees = max(10, int(financials.revenue * 1000 / 200))
            
            return financials
            
        except Exception as e:
            logger.error(f"Error filling missing financials: {str(e)}")
            return financials

    def _calculate_derived_metrics(self, financials: CompanyFinancials):
        """Calculate derived financial metrics"""
        try:
            # Calculate margins
            if financials.revenue > 0:
                if financials.gross_profit > 0:
                    financials.gross_margin = financials.gross_profit / financials.revenue
                if financials.ebitda > 0:
                    financials.ebitda_margin = financials.ebitda / financials.revenue
            
            # Estimate enterprise value
            if financials.market_cap > 0 and financials.enterprise_value == 0:
                net_debt = max(0, financials.total_debt - financials.cash)
                financials.enterprise_value = financials.market_cap + net_debt
            
            # Calculate free cash flow if missing
            if financials.free_cash_flow == 0 and financials.operating_cash_flow > 0:
                financials.free_cash_flow = financials.operating_cash_flow - financials.capex
            
        except Exception as e:
            logger.error(f"Error calculating derived metrics: {str(e)}")

    def _get_industry_revenue_multiple(self, industry: str) -> float:
        """Get industry-appropriate revenue multiple"""
        multiples = {
            "saas": 8.0,
            "fintech": 6.0,
            "healthcare": 4.0,
            "consumer": 3.0,
            "enterprise": 5.0,
            "default": 4.0
        }
        return multiples.get(industry.lower(), 4.0)

    def _get_industry_ebitda_multiple(self, industry: str) -> float:
        """Get industry-appropriate EBITDA multiple"""
        multiples = {
            "saas": 25.0,
            "fintech": 20.0,
            "healthcare": 15.0,
            "consumer": 12.0,
            "enterprise": 18.0,
            "default": 15.0
        }
        return multiples.get(industry.lower(), 15.0)

    def _calculate_wacc(self, acquirer_data: CompanyFinancials, target_data: CompanyFinancials) -> float:
        """Calculate Weighted Average Cost of Capital for DCF"""
        # Simplified WACC calculation
        risk_free_rate = 0.04  # 4% risk-free rate
        market_premium = 0.06  # 6% market risk premium
        
        # Industry risk adjustments
        industry_beta = {
            "saas": 1.3,
            "fintech": 1.4,
            "healthcare": 1.0,
            "consumer": 1.2,
            "default": 1.1
        }
        
        beta = industry_beta.get(target_data.industry.lower(), 1.1)
        cost_of_equity = risk_free_rate + (beta * market_premium)
        
        # Assume 30% debt financing at 6% cost
        debt_weight = 0.3
        equity_weight = 0.7
        cost_of_debt = 0.06
        tax_rate = 0.25
        
        wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
        
        return wacc

    def _calculate_optimal_consideration_mix(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials,
        financing_constraints: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate optimal mix of cash, stock, and debt"""
        
        # Default to 60% cash, 40% stock for strategic acquisitions
        base_mix = {"cash": 0.6, "stock": 0.4}
        
        # Adjust based on acquirer's cash position
        if acquirer_data.cash < target_data.market_cap * 0.3:
            # Cash constrained - use more stock
            base_mix = {"cash": 0.3, "stock": 0.7}
        
        # Adjust based on acquirer's stock performance (simplified)
        # In practice, would look at recent stock performance
        if acquirer_data.market_cap > target_data.market_cap * 10:
            # Large acquirer - can use stock effectively
            base_mix = {"cash": 0.4, "stock": 0.6}
        
        return base_mix

    def _calculate_market_premium(
        self,
        target_data: CompanyFinancials,
        acquirer_data: CompanyFinancials
    ) -> float:
        """Calculate appropriate acquisition premium"""
        base_premium = 0.25  # 25% base
        
        # Adjust for growth
        if target_data.revenue_growth > 0.5:
            base_premium += 0.10
        
        # Adjust for profitability
        if target_data.ebitda_margin > 0.3:
            base_premium += 0.05
        elif target_data.ebitda < 0:
            base_premium -= 0.10
        
        # Adjust for strategic value
        if acquirer_data.industry == target_data.industry:
            base_premium += 0.15  # Strategic fit
        
        return max(0.1, min(0.6, base_premium))  # Cap between 10% and 60%

    def _determine_deal_type(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials
    ) -> DealType:
        """Determine most appropriate deal type"""
        
        revenue_ratio = target_data.revenue / max(acquirer_data.revenue, 1)
        
        if revenue_ratio > 0.8:
            return DealType.MERGER_OF_EQUALS
        elif target_data.employees < 50 and target_data.ebitda < 0:
            return DealType.ACQUIHIRE
        elif acquirer_data.industry == target_data.industry:
            return DealType.STRATEGIC_ACQUISITION
        else:
            return DealType.FINANCIAL_ACQUISITION

    def _determine_closing_conditions(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials
    ) -> List[str]:
        """Determine standard closing conditions"""
        conditions = [
            "Shareholder approval",
            "No material adverse change",
            "Regulatory approvals"
        ]
        
        # Add industry-specific conditions
        if target_data.industry in ["healthcare", "financial"]:
            conditions.append("Industry-specific regulatory approvals")
        
        if target_data.total_debt > target_data.revenue:
            conditions.append("Debt refinancing approval")
        
        return conditions

    def _requires_regulatory_approval(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials
    ) -> bool:
        """Determine if deal requires regulatory approval"""
        
        # Hart-Scott-Rodino threshold (~$100M in 2024)
        combined_revenue = acquirer_data.revenue + target_data.revenue
        
        if combined_revenue > 100:  # $100M threshold
            return True
        
        # Industry-specific thresholds
        regulated_industries = ["healthcare", "financial", "telecom", "defense"]
        if target_data.industry.lower() in regulated_industries:
            return True
        
        return False

    def _estimate_closing_timeline(
        self,
        acquirer_data: CompanyFinancials,
        target_data: CompanyFinancials
    ) -> int:
        """Estimate closing timeline in months"""
        
        base_timeline = 4  # 4 months base
        
        # Add complexity factors
        if self._requires_regulatory_approval(acquirer_data, target_data):
            base_timeline += 6
        
        if acquirer_data.geography != target_data.geography:
            base_timeline += 2
        
        if target_data.industry in ["healthcare", "financial"]:
            base_timeline += 3
        
        return min(18, base_timeline)  # Cap at 18 months

    def _extract_potential_acquirers(
        self,
        search_results: List[Dict[str, Any]],
        target_data: CompanyFinancials
    ) -> List[Dict[str, Any]]:
        """Extract potential acquirers from search results"""
        acquirers = []
        
        # This is a simplified implementation
        # In practice, would have more sophisticated company name extraction
        
        for result_set in search_results:
            if isinstance(result_set, Exception):
                continue
                
            results = result_set.get("results", [])
            for result in results:
                content = result.get("content", "")
                title = result.get("title", "")
                
                # Simple extraction - look for company names in acquisition contexts
                import re
                patterns = [
                    r'([A-Z][a-zA-Z\s]+) acquired',
                    r'([A-Z][a-zA-Z\s]+) purchased',
                    r'([A-Z][a-zA-Z\s]+) bought'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, title + " " + content)
                    for match in matches:
                        if len(match.strip()) > 2 and len(match.strip()) < 30:
                            acquirers.append({
                                "name": match.strip(),
                                "source": result.get("url", ""),
                                "recent_deals": []
                            })
        
        # Deduplicate
        seen = set()
        unique_acquirers = []
        for acq in acquirers:
            if acq["name"] not in seen:
                seen.add(acq["name"])
                unique_acquirers.append(acq)
        
        return unique_acquirers[:20]  # Limit results

    def _calculate_strategic_fit(
        self,
        target_data: CompanyFinancials,
        acquirer_data: CompanyFinancials
    ) -> float:
        """Calculate strategic fit score (0-100)"""
        
        fit_score = 0.0
        
        # Industry alignment (30 points)
        if acquirer_data.industry == target_data.industry:
            fit_score += 30
        elif self._are_adjacent_industries(acquirer_data.industry, target_data.industry):
            fit_score += 20
        
        # Size compatibility (20 points)
        size_ratio = target_data.revenue / max(acquirer_data.revenue, 1)
        if 0.05 <= size_ratio <= 0.5:  # Good size fit
            fit_score += 20
        elif 0.01 <= size_ratio <= 1.0:  # Acceptable fit
            fit_score += 10
        
        # Financial health (25 points)
        if acquirer_data.ebitda_margin > 0.2:  # Strong acquirer
            fit_score += 15
        if target_data.revenue_growth > 0.3:  # Fast-growing target
            fit_score += 10
        
        # Geographic synergy (15 points)
        if acquirer_data.geography == target_data.geography:
            fit_score += 15
        elif self._are_adjacent_geographies(acquirer_data.geography, target_data.geography):
            fit_score += 8
        
        # Financial capacity (10 points)
        if acquirer_data.market_cap > target_data.market_cap * 3:
            fit_score += 10
        elif acquirer_data.market_cap > target_data.market_cap:
            fit_score += 5
        
        return min(100.0, fit_score)

    def _are_adjacent_industries(self, industry1: str, industry2: str) -> bool:
        """Check if industries are adjacent/complementary"""
        adjacent_pairs = [
            ("fintech", "financial"),
            ("saas", "enterprise"),
            ("healthcare", "biotech"),
            ("ai", "saas"),
            ("consumer", "marketplace")
        ]
        
        pair = (industry1.lower(), industry2.lower())
        return pair in adjacent_pairs or (pair[1], pair[0]) in adjacent_pairs

    def _are_adjacent_geographies(self, geo1: str, geo2: str) -> bool:
        """Check if geographies are adjacent/complementary"""
        adjacent_pairs = [
            ("us", "canada"),
            ("uk", "europe"),
            ("germany", "europe"),
            ("nordics", "europe")
        ]
        
        pair = (geo1.lower(), geo2.lower())
        return pair in adjacent_pairs or (pair[1], pair[0]) in adjacent_pairs

    def _estimate_synergy_potential(
        self,
        target_data: CompanyFinancials,
        acquirer_data: CompanyFinancials
    ) -> float:
        """Estimate synergy potential (0-100 score)"""
        
        synergy_score = 0.0
        
        # Revenue synergy potential (50 points max)
        if acquirer_data.customers > target_data.customers * 2:
            synergy_score += 25  # Large customer base to cross-sell to
        
        if target_data.business_model == "saas" and acquirer_data.business_model == "saas":
            synergy_score += 15  # Easy integration
        
        # Cost synergy potential (50 points max)
        combined_revenue = acquirer_data.revenue + target_data.revenue
        if combined_revenue > 1000:  # Large combined entity
            synergy_score += 20  # Economies of scale
        
        if acquirer_data.geography == target_data.geography:
            synergy_score += 15  # Overlapping operations to consolidate
        
        if acquirer_data.industry == target_data.industry:
            synergy_score += 15  # Similar functions to combine
        
        return min(100.0, synergy_score)