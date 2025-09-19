"""
Portfolio Visualization API Endpoints
Provides comprehensive scoring and visualization for portfolio companies
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel

from app.services.company_scoring_visualizer import CompanyScoringVisualizer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio-visualization", tags=["portfolio-visualization"])


class CompanyInput(BaseModel):
    """Input model for company data"""
    name: str
    revenue: Optional[float] = None
    arr: Optional[float] = None
    valuation: Optional[float] = None
    growth_rate: Optional[float] = None
    stage: Optional[str] = None
    sector: Optional[str] = None
    geography: Optional[str] = "US"
    funding_rounds: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None
    product: Optional[str] = None
    tech_stack: Optional[str] = None
    category: Optional[str] = None
    team_size: Optional[int] = None
    customers: Optional[int] = None
    burn_rate: Optional[float] = None
    runway: Optional[float] = None
    

class PortfolioRequest(BaseModel):
    """Request model for portfolio visualization"""
    companies: List[CompanyInput]
    include_scenarios: bool = True
    include_cap_tables: bool = True
    include_matrix: bool = True


@router.post("/dashboard")
async def generate_portfolio_dashboard(request: PortfolioRequest):
    """
    Generate complete portfolio dashboard with scoring and visualizations
    
    Returns:
    - Scenario comparison chart (base/bull/bear for all companies)
    - Cap table pie charts for each company
    - Scoring matrix heatmap
    - Portfolio recommendations
    """
    try:
        visualizer = CompanyScoringVisualizer()
        
        # Convert Pydantic models to dicts
        companies_data = [company.dict() for company in request.companies]
        
        # Generate full dashboard
        dashboard = await visualizer.generate_portfolio_dashboard(companies_data)
        
        # Filter based on request flags
        if not request.include_scenarios:
            dashboard.pop("scenario_comparison", None)
        if not request.include_cap_tables:
            dashboard.pop("cap_table_charts", None)
        if not request.include_matrix:
            dashboard.pop("scoring_matrix", None)
        
        return {
            "success": True,
            "data": dashboard
        }
        
    except Exception as e:
        logger.error(f"Error generating portfolio dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/score-company")
async def score_single_company(company: CompanyInput):
    """
    Score a single company and return detailed analysis
    
    Returns:
    - Overall score and component scores
    - Base/bull/bear scenarios
    - Cap table breakdown
    - API dependency analysis
    - Gross margin analysis
    """
    try:
        visualizer = CompanyScoringVisualizer()
        
        # Score the company
        score = await visualizer.score_company(company.dict())
        
        return {
            "success": True,
            "data": {
                "company_name": score.company_name,
                "overall_score": score.overall_score,
                "component_scores": score.component_scores,
                "scenarios": {
                    "base": score.base_case,
                    "bull": score.bull_case,
                    "bear": score.bear_case
                },
                "cap_table": score.cap_table,
                "api_dependency": score.api_dependency,
                "gross_margin": score.gross_margin,
                "valuation": score.valuation,
                "entry_analysis": {
                    "max_entry_price": score.entry_price_analysis.get("investor_math", {}).get("max_entry_valuation"),
                    "current_ask": score.entry_price_analysis.get("deal_analysis", {}).get("current_ask"),
                    "deal_recommendation": score.entry_price_analysis.get("deal_analysis", {}).get("recommendation"),
                    "growth_projections": score.entry_price_analysis.get("growth_projection", {}),
                    "exit_assumptions": score.entry_price_analysis.get("exit_assumptions", {})
                } if hasattr(score, 'entry_price_analysis') else None,
                "growth_analysis": {
                    "required_growth_rates": score.growth_analysis.get("required_growth_rates", {}),
                    "backward_looking": score.growth_analysis.get("backward_looking", {}),
                    "nrr": score.growth_analysis.get("nrr", 1.10),
                    "churn_impact": score.growth_analysis.get("churn_impact", {})
                } if hasattr(score, 'growth_analysis') else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error scoring company: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenario-comparison")
async def generate_scenario_comparison(request: PortfolioRequest):
    """
    Generate scenario comparison chart data for portfolio companies
    
    Returns grouped bar chart data showing base/bull/bear cases
    """
    try:
        visualizer = CompanyScoringVisualizer()
        
        # Score all companies
        scores = []
        for company in request.companies:
            score = await visualizer.score_company(company.dict())
            scores.append(score)
        
        # Generate comparison chart
        chart_data = visualizer.generate_scenario_comparison_chart(scores)
        
        return {
            "success": True,
            "data": chart_data
        }
        
    except Exception as e:
        logger.error(f"Error generating scenario comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cap-tables")
async def generate_cap_table_charts(request: PortfolioRequest):
    """
    Generate cap table pie charts for portfolio companies
    
    Returns pie chart data for each company's post-dilution cap table
    """
    try:
        visualizer = CompanyScoringVisualizer()
        
        # Score all companies
        scores = []
        for company in request.companies:
            score = await visualizer.score_company(company.dict())
            scores.append(score)
        
        # Generate pie charts
        pie_charts = visualizer.generate_cap_table_pie_charts(scores)
        
        return {
            "success": True,
            "data": pie_charts
        }
        
    except Exception as e:
        logger.error(f"Error generating cap table charts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scoring-matrix")
async def generate_scoring_matrix(request: PortfolioRequest):
    """
    Generate scoring matrix heatmap for portfolio companies
    
    Returns heatmap data showing all scoring components for each company
    """
    try:
        visualizer = CompanyScoringVisualizer()
        
        # Score all companies
        scores = []
        for company in request.companies:
            score = await visualizer.score_company(company.dict())
            scores.append(score)
        
        # Generate matrix
        matrix_data = visualizer.generate_scoring_matrix(scores)
        
        return {
            "success": True,
            "data": matrix_data
        }
        
    except Exception as e:
        logger.error(f"Error generating scoring matrix: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sample-data")
async def get_sample_portfolio_data():
    """
    Get sample portfolio data for testing visualizations
    """
    sample_companies = [
        {
            "name": "@Ramp",
            "revenue": 100_000_000,
            "valuation": 8_100_000_000,
            "growth_rate": 2.0,
            "stage": "Series C",
            "sector": "Fintech",
            "description": "AI-powered expense management platform",
            "product": "Corporate card and expense management with AI insights",
            "funding_rounds": [
                {"round": "Seed", "amount": 7_000_000, "date": "2019-06"},
                {"round": "Series A", "amount": 25_000_000, "date": "2020-04"},
                {"round": "Series B", "amount": 115_000_000, "date": "2021-03"},
                {"round": "Series C", "amount": 300_000_000, "date": "2021-08"}
            ]
        },
        {
            "name": "@Cursor",
            "revenue": 5_000_000,
            "valuation": 400_000_000,
            "growth_rate": 4.0,
            "stage": "Series A",
            "sector": "Developer Tools",
            "description": "AI-first code editor powered by GPT models",
            "product": "AI assistant integrated IDE",
            "tech_stack": "OpenAI GPT-4, Anthropic Claude",
            "category": "AI-first developer tools"
        },
        {
            "name": "@Deel",
            "revenue": 295_000_000,
            "valuation": 12_000_000_000,
            "growth_rate": 1.8,
            "stage": "Series D",
            "sector": "HR Tech",
            "description": "Global payroll and compliance platform",
            "product": "International contractor management",
            "funding_rounds": [
                {"round": "Seed", "amount": 14_000_000, "date": "2019-09"},
                {"round": "Series A", "amount": 30_000_000, "date": "2020-07"},
                {"round": "Series B", "amount": 156_000_000, "date": "2021-04"},
                {"round": "Series C", "amount": 425_000_000, "date": "2021-10"},
                {"round": "Series D", "amount": 50_000_000, "date": "2022-05"}
            ]
        },
        {
            "name": "@Perplexity",
            "revenue": 20_000_000,
            "valuation": 3_000_000_000,
            "growth_rate": 5.0,
            "stage": "Series B",
            "sector": "AI/Search",
            "description": "AI-powered search engine using LLMs",
            "product": "Conversational search with citations",
            "tech_stack": "Heavy OpenAI API usage, custom models",
            "category": "AI chatbot"
        },
        {
            "name": "@Anthropic",
            "revenue": 200_000_000,
            "valuation": 18_000_000_000,
            "growth_rate": 3.0,
            "stage": "Series C",
            "sector": "AI/ML",
            "description": "AI safety company with proprietary LLMs",
            "product": "Claude AI models",
            "tech_stack": "Proprietary models, own infrastructure",
            "category": "AI platform"
        }
    ]
    
    return {
        "success": True,
        "data": sample_companies
    }