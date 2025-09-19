"""
Investment API Endpoints
Comprehensive API for VC, PE, Credit, and M&A calculations
"""

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import json
import asyncio
import logging

from app.services.universal_investment_agent import (
    UniversalInvestmentAgent,
    get_universal_agent,
    PortfolioCompany,
    LBODeal,
    CreditInvestment,
    InvestmentType
)
from app.services.fund_learning_system import (
    FundLearningSystem,
    get_learning_system,
    FundTrainingData,
    DealTrainingData
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== REQUEST MODELS ====================

class VCFundRequest(BaseModel):
    """Request model for VC fund calculations"""
    fund_size: float = Field(..., description="Total fund size")
    portfolio_companies: List[Dict[str, Any]] = Field(..., description="Portfolio company data")
    management_fee: float = Field(0.02, description="Annual management fee")
    carry: float = Field(0.20, description="Carried interest percentage")
    hurdle_rate: float = Field(0.08, description="Hurdle rate for carry")


class PortfolioConstructionRequest(BaseModel):
    """Request for portfolio construction modeling"""
    fund_size: float
    stage_focus: str = Field(..., description="seed, series_a, or growth")
    target_returns: float = Field(3.0, description="Target fund multiple")
    constraints: Optional[Dict[str, Any]] = None


class WaterfallRequest(BaseModel):
    """Request for waterfall calculation"""
    exit_value: float
    cap_table: Dict[str, float] = Field(..., description="Shareholder ownership percentages")
    liquidation_preferences: Dict[str, Dict[str, Any]]
    participating_preferred: Optional[Dict[str, bool]] = None


class LBORequest(BaseModel):
    """Request for LBO modeling"""
    company_name: str
    enterprise_value: float
    ebitda: float
    debt_amount: float
    equity_amount: float
    exit_multiple: float
    exit_year: int = Field(5, description="Years to exit")
    ebitda_growth_rate: float = Field(0.10, description="Annual EBITDA growth")
    include_sensitivity: bool = True


class CreditRequest(BaseModel):
    """Request for credit investment analysis"""
    borrower: str
    principal: float
    interest_rate: float = Field(..., description="Annual interest rate")
    maturity_years: int
    seniority: str = Field(..., description="first_lien, second_lien, mezz")
    ltv: float = Field(..., description="Loan to value ratio")
    dscr: float = Field(..., description="Debt service coverage ratio")
    include_stress_test: bool = True


class MARequest(BaseModel):
    """Request for M&A analysis"""
    acquirer: Dict[str, Any]
    target: Dict[str, Any]
    deal_terms: Dict[str, Any]
    include_synergies: bool = True


class ComparisonRequest(BaseModel):
    """Request to compare investment strategies"""
    company_data: Dict[str, Any]
    strategies_to_compare: Optional[List[str]] = None


class LearningDataRequest(BaseModel):
    """Request to train models with historical data"""
    fund_data: Optional[List[Dict[str, Any]]] = None
    deal_data: Optional[List[Dict[str, Any]]] = None
    model_type: str = Field("all", description="Which models to train")


class PredictionRequest(BaseModel):
    """Request for performance prediction"""
    entity_type: str = Field(..., description="fund or deal")
    characteristics: Dict[str, Any]
    include_comparables: bool = True


# ==================== VC ENDPOINTS ====================

@router.post("/vc/fund-metrics")
async def calculate_vc_fund_metrics(request: VCFundRequest):
    """Calculate comprehensive VC fund metrics including DPI, TVPI, IRR"""
    try:
        agent = get_universal_agent()
        
        # Convert dict to PortfolioCompany objects
        portfolio = []
        for pc_data in request.portfolio_companies:
            portfolio.append(PortfolioCompany(
                company_id=pc_data.get('company_id', 'unknown'),
                name=pc_data.get('name', 'Company'),
                initial_investment=pc_data.get('initial_investment', 0),
                total_invested=pc_data.get('total_invested', 0),
                current_valuation=pc_data.get('current_valuation', 0),
                ownership_percentage=pc_data.get('ownership_percentage', 0),
                entry_date=datetime.fromisoformat(pc_data.get('entry_date', datetime.now().isoformat())),
                stage=pc_data.get('stage', 'unknown'),
                sector=pc_data.get('sector', 'unknown'),
                exit_data=pc_data.get('exit_data')
            ))
        
        metrics = await agent.calculate_vc_fund_metrics(
            request.fund_size,
            portfolio,
            request.management_fee,
            request.carry,
            request.hurdle_rate
        )
        
        return {
            "status": "success",
            "metrics": metrics,
            "portfolio_count": len(portfolio)
        }
    
    except Exception as e:
        logger.error(f"Error calculating VC fund metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vc/portfolio-construction")
async def model_portfolio_construction(request: PortfolioConstructionRequest):
    """Model optimal portfolio construction for VC fund"""
    try:
        agent = get_universal_agent()
        
        result = await agent.model_vc_portfolio_construction(
            request.fund_size,
            request.stage_focus,
            request.target_returns
        )
        
        return {
            "status": "success",
            "portfolio_model": result
        }
    
    except Exception as e:
        logger.error(f"Error modeling portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vc/waterfall")
async def calculate_waterfall(request: WaterfallRequest):
    """Calculate exit distribution waterfall"""
    try:
        agent = get_universal_agent()
        
        distributions = await agent.calculate_waterfall(
            request.exit_value,
            request.cap_table,
            request.liquidation_preferences
        )
        
        # Calculate summary statistics
        total_distributed = sum(distributions.values())
        
        return {
            "status": "success",
            "exit_value": request.exit_value,
            "distributions": distributions,
            "total_distributed": total_distributed,
            "verification": abs(total_distributed - request.exit_value) < 0.01
        }
    
    except Exception as e:
        logger.error(f"Error calculating waterfall: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PE ENDPOINTS ====================

@router.post("/pe/lbo-model")
async def model_lbo(request: LBORequest):
    """Model leveraged buyout returns"""
    try:
        agent = get_universal_agent()
        
        deal = LBODeal(
            company_name=request.company_name,
            enterprise_value=request.enterprise_value,
            ebitda=request.ebitda,
            entry_multiple=request.enterprise_value / request.ebitda,
            debt_amount=request.debt_amount,
            equity_amount=request.equity_amount,
            senior_debt=request.debt_amount * 0.7,  # Assume 70% senior
            subordinated_debt=request.debt_amount * 0.3,  # 30% sub debt
            exit_multiple=request.exit_multiple,
            exit_year=request.exit_year,
            ebitda_growth_rate=request.ebitda_growth_rate
        )
        
        result = await agent.model_lbo(deal, request.include_sensitivity)
        
        return {
            "status": "success",
            "lbo_analysis": result
        }
    
    except Exception as e:
        logger.error(f"Error modeling LBO: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pe/fund-metrics")
async def calculate_pe_fund_metrics(request: Dict[str, Any]):
    """Calculate PE fund performance metrics"""
    try:
        agent = get_universal_agent()
        
        # Convert to LBODeal objects
        portfolio_deals = []
        for deal_data in request.get('portfolio_deals', []):
            portfolio_deals.append(LBODeal(**deal_data))
        
        metrics = await agent.calculate_pe_fund_metrics(
            request['fund_size'],
            portfolio_deals,
            request.get('management_fee', 0.02),
            request.get('carry', 0.20)
        )
        
        return {
            "status": "success",
            "metrics": metrics
        }
    
    except Exception as e:
        logger.error(f"Error calculating PE fund metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CREDIT ENDPOINTS ====================

@router.post("/credit/analyze")
async def analyze_credit_investment(request: CreditRequest):
    """Analyze credit investment returns and risks"""
    try:
        agent = get_universal_agent()
        
        investment = CreditInvestment(
            borrower=request.borrower,
            principal=request.principal,
            interest_rate=request.interest_rate,
            maturity_years=request.maturity_years,
            seniority=request.seniority,
            covenants={},  # Simplified for now
            ltv=request.ltv,
            dscr=request.dscr,
            payment_structure="cash"  # Default to cash
        )
        
        analysis = await agent.analyze_credit_investment(
            investment,
            request.include_stress_test
        )
        
        return {
            "status": "success",
            "credit_analysis": analysis
        }
    
    except Exception as e:
        logger.error(f"Error analyzing credit investment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/credit/portfolio")
async def analyze_credit_portfolio(request: Dict[str, Any]):
    """Analyze credit portfolio metrics"""
    try:
        agent = get_universal_agent()
        
        # Convert to CreditInvestment objects
        investments = []
        for inv_data in request.get('investments', []):
            investments.append(CreditInvestment(**inv_data))
        
        metrics = await agent.calculate_credit_portfolio_metrics(
            investments,
            request.get('default_assumptions')
        )
        
        return {
            "status": "success",
            "portfolio_metrics": metrics
        }
    
    except Exception as e:
        logger.error(f"Error analyzing credit portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== M&A ENDPOINTS ====================

@router.post("/ma/analyze")
async def analyze_ma_transaction(request: MARequest):
    """Analyze M&A transaction including accretion/dilution"""
    try:
        agent = get_universal_agent()
        
        analysis = await agent.analyze_ma_transaction(
            request.acquirer,
            request.target,
            request.deal_terms,
            request.include_synergies
        )
        
        return {
            "status": "success",
            "ma_analysis": analysis
        }
    
    except Exception as e:
        logger.error(f"Error analyzing M&A transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CROSS-STRATEGY ENDPOINTS ====================

@router.post("/compare-strategies")
async def compare_investment_strategies(request: ComparisonRequest):
    """Compare same opportunity across different investment strategies"""
    try:
        agent = get_universal_agent()
        
        comparison = await agent.compare_investment_strategies(
            request.company_data
        )
        
        return {
            "status": "success",
            "comparison": comparison,
            "recommendation": comparison.get('recommendation')
        }
    
    except Exception as e:
        logger.error(f"Error comparing strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LEARNING ENDPOINTS ====================

@router.post("/train")
async def train_models(request: LearningDataRequest):
    """Train models with historical data"""
    try:
        learning = get_learning_system()
        
        results = {}
        
        # Train fund models
        if request.fund_data:
            fund_training_data = []
            for fund in request.fund_data:
                fund_training_data.append(FundTrainingData(**fund))
            
            learning.train_fund_performance_model(
                fund_training_data,
                request.model_type
            )
            results['fund_models'] = f"Trained with {len(fund_training_data)} funds"
        
        # Train deal models
        if request.deal_data:
            deal_training_data = []
            for deal in request.deal_data:
                deal_training_data.append(DealTrainingData(**deal))
            
            learning.train_deal_model(deal_training_data)
            results['deal_models'] = f"Trained with {len(deal_training_data)} deals"
        
        return {
            "status": "success",
            "training_results": results,
            "model_performance": learning.model_performance
        }
    
    except Exception as e:
        logger.error(f"Error training models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict_performance(request: PredictionRequest):
    """Predict fund or deal performance"""
    try:
        learning = get_learning_system()
        
        if request.entity_type == "fund":
            prediction = learning.predict_fund_performance(
                request.characteristics
            )
        elif request.entity_type == "deal":
            prediction = learning.predict_deal_outcome(
                request.characteristics
            )
        else:
            raise ValueError(f"Unknown entity type: {request.entity_type}")
        
        return {
            "status": "success",
            "prediction": prediction
        }
    
    except Exception as e:
        logger.error(f"Error making prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learn-from-outcome")
async def learn_from_outcome(request: Dict[str, Any]):
    """Learn from actual vs predicted outcomes"""
    try:
        agent = get_universal_agent()
        learning = get_learning_system()
        
        # Agent learns patterns
        agent.learn_from_outcome(
            request['prediction'],
            request['actual'],
            InvestmentType(request.get('deal_type', 'vc'))
        )
        
        # Learning system updates models
        learning.learn_from_outcome(
            request['prediction'],
            request['actual'],
            request.get('context', {})
        )
        
        return {
            "status": "success",
            "agent_accuracy": agent.predictions_accurate / max(agent.predictions_made, 1),
            "patterns_stored": len(agent.pattern_library)
        }
    
    except Exception as e:
        logger.error(f"Error learning from outcome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PATTERN ANALYSIS ====================

@router.post("/analyze-patterns")
async def analyze_patterns(request: Dict[str, Any]):
    """Analyze patterns in portfolio or historical data"""
    try:
        agent = get_universal_agent()
        learning = get_learning_system()
        
        # Agent identifies patterns
        agent_patterns = agent.identify_patterns(
            request.get('portfolio', []),
            request.get('pattern_type', 'all')
        )
        
        # Learning system patterns
        learning_patterns = learning.identify_patterns(
            request.get('portfolio', []),
            request.get('pattern_type', 'all')
        )
        
        return {
            "status": "success",
            "agent_patterns": agent_patterns,
            "learning_patterns": learning_patterns
        }
    
    except Exception as e:
        logger.error(f"Error analyzing patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DEMO & TEST ENDPOINTS ====================

@router.get("/demo/vc-fund")
async def demo_vc_fund():
    """Demo endpoint showing VC fund analysis"""
    try:
        agent = get_universal_agent()
        
        # Create sample portfolio
        sample_portfolio = [
            PortfolioCompany(
                company_id="1",
                name="Unicorn Inc",
                initial_investment=2_000_000,
                total_invested=5_000_000,
                current_valuation=100_000_000,
                ownership_percentage=0.05,
                entry_date=datetime(2019, 1, 1),
                stage="series_a",
                sector="fintech"
            ),
            PortfolioCompany(
                company_id="2",
                name="FailCo",
                initial_investment=1_000_000,
                total_invested=1_000_000,
                current_valuation=0,
                ownership_percentage=0.10,
                entry_date=datetime(2020, 1, 1),
                stage="seed",
                sector="consumer"
            ),
            PortfolioCompany(
                company_id="3",
                name="SteadyCo",
                initial_investment=3_000_000,
                total_invested=4_000_000,
                current_valuation=12_000_000,
                ownership_percentage=0.15,
                entry_date=datetime(2019, 6, 1),
                stage="series_a",
                sector="enterprise"
            )
        ]
        
        metrics = await agent.calculate_vc_fund_metrics(
            fund_size=100_000_000,
            portfolio_companies=sample_portfolio
        )
        
        return {
            "demo": "VC Fund Analysis",
            "fund_size": 100_000_000,
            "portfolio_companies": 3,
            "metrics": metrics
        }
    
    except Exception as e:
        logger.error(f"Error in demo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/demo/lbo")
async def demo_lbo():
    """Demo endpoint showing LBO analysis"""
    try:
        agent = get_universal_agent()
        
        sample_deal = LBODeal(
            company_name="TargetCo",
            enterprise_value=500_000_000,
            ebitda=50_000_000,
            entry_multiple=10,
            debt_amount=300_000_000,
            equity_amount=200_000_000,
            senior_debt=200_000_000,
            subordinated_debt=100_000_000,
            exit_multiple=12,
            exit_year=5,
            ebitda_growth_rate=0.10
        )
        
        result = await agent.model_lbo(sample_deal, include_sensitivity=True)
        
        return {
            "demo": "LBO Analysis",
            "deal": "TargetCo Acquisition",
            "analysis": result
        }
    
    except Exception as e:
        logger.error(f"Error in LBO demo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for investment API"""
    return {
        "status": "healthy",
        "service": "Universal Investment API",
        "capabilities": [
            "VC Fund Analysis",
            "PE/LBO Modeling",
            "Credit Analysis",
            "M&A Evaluation",
            "Machine Learning Predictions",
            "Pattern Recognition"
        ],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/")
async def investment_api_info():
    """Get information about the investment API"""
    return {
        "name": "Universal Investment Analysis API",
        "version": "1.0.0",
        "description": "Comprehensive investment analysis across VC, PE, Credit, and M&A",
        "endpoints": {
            "vc": [
                "/vc/fund-metrics",
                "/vc/portfolio-construction",
                "/vc/waterfall"
            ],
            "pe": [
                "/pe/lbo-model",
                "/pe/fund-metrics"
            ],
            "credit": [
                "/credit/analyze",
                "/credit/portfolio"
            ],
            "ma": [
                "/ma/analyze"
            ],
            "analysis": [
                "/compare-strategies",
                "/analyze-patterns"
            ],
            "learning": [
                "/train",
                "/predict",
                "/learn-from-outcome"
            ],
            "demo": [
                "/demo/vc-fund",
                "/demo/lbo"
            ]
        },
        "features": [
            "DPI/TVPI/IRR calculations",
            "Waterfall distributions",
            "LBO modeling with sensitivity",
            "Credit risk analysis",
            "M&A accretion/dilution",
            "Machine learning predictions",
            "Pattern recognition",
            "Cross-strategy comparison"
        ]
    }