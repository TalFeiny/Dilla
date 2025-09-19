"""
Position Sizing API Endpoints
Advanced position sizing, ownership tracking, scenario analysis, and FP&A
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.services.position_sizing_engine import (
    PositionSizingEngine,
    get_sizing_engine,
    SizingStrategy,
    PositionConstraints,
    InvestmentOpportunity,
    PortfolioState
)
from app.services.universal_investment_agent import get_universal_agent

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== REQUEST MODELS ====================

class OpportunityRequest(BaseModel):
    """Investment opportunity for sizing"""
    opportunity_id: str
    name: str
    valuation: float
    revenue: float = Field(0, description="Current annual revenue")
    growth_rate: float = Field(0.5, description="Expected annual growth rate")
    expected_return: float
    volatility: float = Field(0.3, description="Return volatility")
    probability_success: float = Field(0.3, description="Success probability")
    minimum_investment: float
    maximum_investment: Optional[float] = None
    sector: str
    stage: str
    target_ownership: Optional[float] = Field(None, description="Target ownership percentage")
    dilution_expected: Optional[float] = Field(0.3, description="Expected dilution over hold period")


class OwnershipScenario(BaseModel):
    """Ownership scenario parameters"""
    initial_investment: float
    valuation_at_entry: float
    future_rounds: List[Dict[str, Any]] = Field(default_factory=list)
    exit_scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    pro_rata_participation: bool = True


class FPARequest(BaseModel):
    """Financial Planning & Analysis request"""
    company_id: str
    historical_financials: Dict[str, Any]
    assumptions: Dict[str, Any]
    forecast_years: int = Field(5, description="Years to forecast")
    scenarios: List[str] = Field(default_factory=lambda: ["base", "upside", "downside"])


class ValuationRequest(BaseModel):
    """Enhanced valuation request"""
    company_data: Dict[str, Any]
    valuation_methods: List[str] = Field(
        default_factory=lambda: ["dcf", "multiples", "vc_method", "berkus"]
    )
    comparables: Optional[List[Dict[str, Any]]] = None
    market_data: Optional[Dict[str, Any]] = None


class PositionSizingRequest(BaseModel):
    """Position sizing request"""
    opportunities: List[OpportunityRequest]
    portfolio_state: Dict[str, Any]
    strategy: str = Field("kelly_criterion", description="Sizing strategy")
    constraints: Optional[Dict[str, Any]] = None
    include_ownership_analysis: bool = True


class ScenarioAnalysisRequest(BaseModel):
    """Scenario analysis request"""
    base_case: Dict[str, Any]
    scenarios: List[Dict[str, Any]]
    metrics_to_track: List[str] = Field(
        default_factory=lambda: ["irr", "moic", "ownership", "value"]
    )
    sensitivity_variables: Optional[List[str]] = None


# ==================== POSITION SIZING ENDPOINTS ====================

@router.post("/calculate-sizes")
async def calculate_position_sizes(request: PositionSizingRequest):
    """Calculate optimal position sizes with ownership analysis"""
    try:
        engine = get_sizing_engine()
        
        # Convert opportunities
        opportunities = []
        for opp_req in request.opportunities:
            opportunities.append(InvestmentOpportunity(
                opportunity_id=opp_req.opportunity_id,
                name=opp_req.name,
                expected_return=opp_req.expected_return,
                volatility=opp_req.volatility,
                probability_success=opp_req.probability_success,
                minimum_investment=opp_req.minimum_investment,
                maximum_investment=opp_req.maximum_investment,
                sector=opp_req.sector,
                stage=opp_req.stage
            ))
        
        # Create portfolio state
        portfolio_state = PortfolioState(
            total_capital=request.portfolio_state.get('total_capital', 100_000_000),
            deployed_capital=request.portfolio_state.get('deployed_capital', 0),
            reserve_capital=request.portfolio_state.get('reserve_capital', 100_000_000),
            current_positions=request.portfolio_state.get('current_positions', {}),
            sector_exposure=request.portfolio_state.get('sector_exposure', {}),
            stage_exposure=request.portfolio_state.get('stage_exposure', {}),
            portfolio_volatility=request.portfolio_state.get('portfolio_volatility', 0),
            portfolio_return=request.portfolio_state.get('portfolio_return', 0)
        )
        
        # Create constraints
        constraints = PositionConstraints(**(request.constraints or {}))
        
        # Calculate sizes
        result = engine.calculate_position_sizes(
            opportunities,
            portfolio_state,
            SizingStrategy(request.strategy),
            constraints
        )
        
        # Add ownership analysis if requested
        if request.include_ownership_analysis:
            ownership_analysis = {}
            for opp_req in request.opportunities:
                if opp_req.opportunity_id in result['positions']:
                    investment = result['positions'][opp_req.opportunity_id]
                    ownership = calculate_ownership(
                        investment,
                        opp_req.valuation,
                        opp_req.target_ownership,
                        opp_req.dilution_expected
                    )
                    ownership_analysis[opp_req.opportunity_id] = ownership
            
            result['ownership_analysis'] = ownership_analysis
        
        return {
            "status": "success",
            "sizing_results": result
        }
    
    except Exception as e:
        logger.error(f"Error calculating position sizes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vc-sizing")
async def calculate_vc_position_sizes(request: Dict[str, Any]):
    """VC-specific position sizing with reserve strategy"""
    try:
        engine = get_sizing_engine()
        
        # Convert opportunities
        opportunities = []
        for opp_data in request.get('opportunities', []):
            opportunities.append(InvestmentOpportunity(**opp_data))
        
        result = engine.calculate_vc_position_sizes(
            request['fund_size'],
            request['fund_stage'],
            opportunities,
            request.get('reserve_ratio', 1.0)
        )
        
        return {
            "status": "success",
            "vc_sizing": result
        }
    
    except Exception as e:
        logger.error(f"Error calculating VC position sizes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize-portfolio")
async def optimize_portfolio_allocation(request: Dict[str, Any]):
    """Optimize allocation across portfolio"""
    try:
        engine = get_sizing_engine()
        
        # Convert opportunities
        new_opportunities = []
        for opp_data in request.get('new_opportunities', []):
            new_opportunities.append(InvestmentOpportunity(**opp_data))
        
        result = engine.optimize_portfolio_allocation(
            request.get('current_portfolio', []),
            new_opportunities,
            request['total_fund_size'],
            request.get('optimization_target', 'max_sharpe')
        )
        
        return {
            "status": "success",
            "optimization_result": result
        }
    
    except Exception as e:
        logger.error(f"Error optimizing portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== OWNERSHIP ANALYSIS ====================

@router.post("/ownership-scenario")
async def analyze_ownership_scenario(request: OwnershipScenario):
    """Analyze ownership through multiple funding rounds"""
    try:
        # Calculate initial ownership
        initial_ownership = request.initial_investment / request.valuation_at_entry
        
        current_ownership = initial_ownership
        ownership_history = [{
            "round": "initial",
            "ownership": initial_ownership,
            "investment": request.initial_investment,
            "valuation": request.valuation_at_entry
        }]
        
        # Process future rounds
        for round_data in request.future_rounds:
            round_name = round_data.get('name', 'Series X')
            round_size = round_data.get('size', 0)
            pre_money = round_data.get('pre_money_valuation', request.valuation_at_entry * 2)
            post_money = pre_money + round_size
            
            if request.pro_rata_participation:
                # Maintain ownership by investing pro-rata
                pro_rata_investment = current_ownership * round_size
                new_ownership = (current_ownership * pre_money + pro_rata_investment) / post_money
                
                ownership_history.append({
                    "round": round_name,
                    "ownership": new_ownership,
                    "investment": pro_rata_investment,
                    "valuation": post_money,
                    "dilution": current_ownership - new_ownership
                })
            else:
                # Get diluted
                new_ownership = current_ownership * (pre_money / post_money)
                
                ownership_history.append({
                    "round": round_name,
                    "ownership": new_ownership,
                    "investment": 0,
                    "valuation": post_money,
                    "dilution": current_ownership - new_ownership
                })
            
            current_ownership = new_ownership
        
        # Calculate exit scenarios
        exit_analysis = []
        total_invested = sum(h['investment'] for h in ownership_history)
        
        for exit_scenario in request.exit_scenarios:
            exit_value = exit_scenario.get('exit_valuation', 1_000_000_000)
            exit_proceeds = current_ownership * exit_value
            
            exit_analysis.append({
                "scenario": exit_scenario.get('name', 'Exit'),
                "exit_valuation": exit_value,
                "ownership_at_exit": current_ownership,
                "proceeds": exit_proceeds,
                "total_invested": total_invested,
                "multiple": exit_proceeds / total_invested if total_invested > 0 else 0,
                "irr": calculate_irr_simple(total_invested, exit_proceeds, 5)  # Assume 5 year hold
            })
        
        return {
            "status": "success",
            "ownership_history": ownership_history,
            "final_ownership": current_ownership,
            "total_dilution": initial_ownership - current_ownership,
            "exit_analysis": exit_analysis
        }
    
    except Exception as e:
        logger.error(f"Error analyzing ownership scenario: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FP&A ENDPOINTS ====================

@router.post("/fpa/forecast")
async def create_financial_forecast(request: FPARequest):
    """Create comprehensive financial forecast with scenarios"""
    try:
        forecasts = {}
        
        for scenario in request.scenarios:
            # Adjust assumptions based on scenario
            scenario_assumptions = adjust_assumptions_for_scenario(
                request.assumptions,
                scenario
            )
            
            # Create forecast
            forecast = build_financial_forecast(
                request.historical_financials,
                scenario_assumptions,
                request.forecast_years
            )
            
            # Calculate key metrics
            metrics = calculate_fpa_metrics(forecast)
            
            forecasts[scenario] = {
                "forecast": forecast,
                "metrics": metrics,
                "assumptions": scenario_assumptions
            }
        
        # Compare scenarios
        comparison = compare_scenarios(forecasts)
        
        return {
            "status": "success",
            "forecasts": forecasts,
            "comparison": comparison,
            "key_insights": generate_fpa_insights(forecasts)
        }
    
    except Exception as e:
        logger.error(f"Error creating financial forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fpa/unit-economics")
async def analyze_unit_economics(request: Dict[str, Any]):
    """Analyze unit economics and scalability"""
    try:
        # Extract key metrics
        cac = request.get('customer_acquisition_cost', 0)
        ltv = request.get('lifetime_value', 0)
        gross_margin = request.get('gross_margin', 0)
        churn_rate = request.get('monthly_churn_rate', 0)
        
        # Calculate unit economics
        ltv_cac_ratio = ltv / cac if cac > 0 else 0
        payback_period = cac / (ltv / 36) if ltv > 0 else float('inf')  # Assume 36 month LTV
        
        # Calculate cohort economics
        cohort_analysis = {
            "month_1_retention": 1 - churn_rate,
            "month_6_retention": (1 - churn_rate) ** 6,
            "month_12_retention": (1 - churn_rate) ** 12,
            "break_even_month": int(payback_period),
            "contribution_margin": gross_margin * ltv
        }
        
        # Scalability analysis
        scalability = analyze_scalability(
            request.get('revenue_growth', 0),
            request.get('cost_growth', 0),
            gross_margin
        )
        
        return {
            "status": "success",
            "unit_economics": {
                "ltv": ltv,
                "cac": cac,
                "ltv_cac_ratio": ltv_cac_ratio,
                "payback_period_months": payback_period,
                "gross_margin": gross_margin,
                "monthly_churn": churn_rate
            },
            "cohort_analysis": cohort_analysis,
            "scalability": scalability,
            "health_score": calculate_saas_health_score(ltv_cac_ratio, gross_margin, churn_rate)
        }
    
    except Exception as e:
        logger.error(f"Error analyzing unit economics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== VALUATION ENDPOINTS ====================

@router.post("/valuation/comprehensive")
async def comprehensive_valuation(request: ValuationRequest):
    """Perform comprehensive valuation using multiple methods"""
    try:
        agent = get_universal_agent()
        valuations = {}
        
        # DCF Valuation
        if "dcf" in request.valuation_methods:
            dcf_result = perform_dcf_valuation(request.company_data)
            valuations["dcf"] = dcf_result
        
        # Multiples Valuation
        if "multiples" in request.valuation_methods and request.comparables:
            multiples_result = perform_multiples_valuation(
                request.company_data,
                request.comparables
            )
            valuations["multiples"] = multiples_result
        
        # VC Method
        if "vc_method" in request.valuation_methods:
            vc_result = perform_vc_method_valuation(request.company_data)
            valuations["vc_method"] = vc_result
        
        # Berkus Method (for early stage)
        if "berkus" in request.valuation_methods:
            berkus_result = perform_berkus_valuation(request.company_data)
            valuations["berkus"] = berkus_result
        
        # Calculate weighted average
        weighted_valuation = calculate_weighted_valuation(valuations)
        
        # Sensitivity analysis
        sensitivity = perform_valuation_sensitivity(
            request.company_data,
            valuations
        )
        
        return {
            "status": "success",
            "valuations": valuations,
            "weighted_valuation": weighted_valuation,
            "sensitivity_analysis": sensitivity,
            "valuation_range": {
                "low": min(v.get('valuation', 0) for v in valuations.values()),
                "high": max(v.get('valuation', 0) for v in valuations.values()),
                "median": calculate_median_valuation(valuations)
            }
        }
    
    except Exception as e:
        logger.error(f"Error performing valuation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SCENARIO ANALYSIS ====================

@router.post("/scenario-analysis")
async def perform_scenario_analysis(request: ScenarioAnalysisRequest):
    """Perform comprehensive scenario analysis"""
    try:
        results = {
            "base_case": evaluate_scenario(request.base_case, request.metrics_to_track)
        }
        
        # Evaluate each scenario
        for scenario in request.scenarios:
            scenario_name = scenario.get('name', 'Scenario')
            results[scenario_name] = evaluate_scenario(scenario, request.metrics_to_track)
        
        # Sensitivity analysis if requested
        if request.sensitivity_variables:
            sensitivity = {}
            for variable in request.sensitivity_variables:
                sensitivity[variable] = perform_sensitivity_on_variable(
                    request.base_case,
                    variable,
                    request.metrics_to_track
                )
            results['sensitivity'] = sensitivity
        
        # Calculate probability-weighted outcome
        if all('probability' in s for s in request.scenarios):
            weighted_outcome = calculate_probability_weighted_outcome(
                results,
                request.scenarios
            )
            results['probability_weighted'] = weighted_outcome
        
        return {
            "status": "success",
            "scenario_results": results,
            "summary": summarize_scenarios(results),
            "recommendations": generate_scenario_recommendations(results)
        }
    
    except Exception as e:
        logger.error(f"Error performing scenario analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HELPER FUNCTIONS ====================

def calculate_ownership(
    investment: float,
    valuation: float,
    target_ownership: Optional[float],
    expected_dilution: float
) -> Dict[str, Any]:
    """Calculate ownership metrics"""
    
    initial_ownership = investment / valuation
    
    # Adjust for target ownership if specified
    if target_ownership:
        required_investment = target_ownership * valuation
        ownership_gap = target_ownership - initial_ownership
    else:
        required_investment = investment
        ownership_gap = 0
    
    # Project diluted ownership
    diluted_ownership = initial_ownership * (1 - expected_dilution)
    
    return {
        "initial_ownership": initial_ownership,
        "diluted_ownership": diluted_ownership,
        "target_ownership": target_ownership,
        "ownership_gap": ownership_gap,
        "required_investment": required_investment,
        "dilution_buffer": initial_ownership - diluted_ownership
    }


def calculate_irr_simple(investment: float, exit_value: float, years: float) -> float:
    """Simple IRR calculation"""
    if investment <= 0 or years <= 0:
        return 0
    return (exit_value / investment) ** (1 / years) - 1


def adjust_assumptions_for_scenario(
    base_assumptions: Dict[str, Any],
    scenario: str
) -> Dict[str, Any]:
    """Adjust assumptions based on scenario"""
    
    adjusted = base_assumptions.copy()
    
    if scenario == "upside":
        adjusted['revenue_growth'] = base_assumptions.get('revenue_growth', 0.3) * 1.5
        adjusted['margin_improvement'] = base_assumptions.get('margin_improvement', 0) + 0.05
    elif scenario == "downside":
        adjusted['revenue_growth'] = base_assumptions.get('revenue_growth', 0.3) * 0.5
        adjusted['margin_improvement'] = base_assumptions.get('margin_improvement', 0) - 0.05
    
    return adjusted


def build_financial_forecast(
    historicals: Dict[str, Any],
    assumptions: Dict[str, Any],
    years: int
) -> Dict[str, Any]:
    """Build financial forecast"""
    
    forecast = {"years": []}
    
    # Starting values
    current_revenue = historicals.get('latest_revenue', 0)
    current_costs = historicals.get('latest_costs', 0)
    current_margin = (current_revenue - current_costs) / current_revenue if current_revenue > 0 else 0
    
    for year in range(1, years + 1):
        # Apply growth
        revenue = current_revenue * ((1 + assumptions.get('revenue_growth', 0.3)) ** year)
        
        # Apply margin improvement
        margin = current_margin + (assumptions.get('margin_improvement', 0.02) * year)
        costs = revenue * (1 - margin)
        
        # Calculate other metrics
        ebitda = revenue * margin
        fcf = ebitda * assumptions.get('fcf_conversion', 0.8)
        
        forecast["years"].append({
            "year": year,
            "revenue": revenue,
            "costs": costs,
            "ebitda": ebitda,
            "margin": margin,
            "fcf": fcf
        })
    
    return forecast


def calculate_fpa_metrics(forecast: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate key FP&A metrics"""
    
    years_data = forecast.get("years", [])
    
    if not years_data:
        return {}
    
    return {
        "cagr": ((years_data[-1]['revenue'] / years_data[0]['revenue']) ** (1/len(years_data))) - 1,
        "avg_margin": sum(y['margin'] for y in years_data) / len(years_data),
        "total_fcf": sum(y['fcf'] for y in years_data),
        "terminal_value": years_data[-1]['fcf'] * 10  # 10x terminal multiple
    }


def compare_scenarios(forecasts: Dict[str, Any]) -> Dict[str, Any]:
    """Compare different scenario forecasts"""
    
    comparison = {}
    
    for metric in ['revenue', 'ebitda', 'fcf']:
        comparison[metric] = {
            scenario: sum(y[metric] for y in data['forecast']['years'])
            for scenario, data in forecasts.items()
        }
    
    return comparison


def generate_fpa_insights(forecasts: Dict[str, Any]) -> List[str]:
    """Generate insights from FP&A analysis"""
    
    insights = []
    
    # Compare scenarios
    base_revenue = sum(y['revenue'] for y in forecasts.get('base', {}).get('forecast', {}).get('years', []))
    upside_revenue = sum(y['revenue'] for y in forecasts.get('upside', {}).get('forecast', {}).get('years', []))
    
    if upside_revenue > base_revenue * 1.5:
        insights.append("Significant upside potential if growth assumptions are met")
    
    # Check margins
    base_margins = [y['margin'] for y in forecasts.get('base', {}).get('forecast', {}).get('years', [])]
    if base_margins and base_margins[-1] > base_margins[0] * 1.2:
        insights.append("Strong margin expansion expected over forecast period")
    
    return insights


def analyze_scalability(revenue_growth: float, cost_growth: float, gross_margin: float) -> Dict[str, Any]:
    """Analyze business scalability"""
    
    operating_leverage = revenue_growth / cost_growth if cost_growth > 0 else float('inf')
    
    return {
        "operating_leverage": operating_leverage,
        "scalable": operating_leverage > 1.2,
        "margin_expansion_potential": (1 - cost_growth/revenue_growth) * gross_margin if revenue_growth > 0 else 0
    }


def calculate_saas_health_score(ltv_cac: float, gross_margin: float, churn: float) -> float:
    """Calculate SaaS business health score (0-100)"""
    
    score = 0
    
    # LTV/CAC contribution (40 points)
    if ltv_cac > 3:
        score += 40
    elif ltv_cac > 2:
        score += 30
    elif ltv_cac > 1:
        score += 20
    
    # Gross margin contribution (30 points)
    score += min(30, gross_margin * 100 * 0.4)
    
    # Churn contribution (30 points)
    if churn < 0.02:  # Less than 2% monthly
        score += 30
    elif churn < 0.05:
        score += 20
    elif churn < 0.10:
        score += 10
    
    return min(100, score)


def perform_dcf_valuation(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Perform DCF valuation"""
    
    # Simplified DCF
    fcf_projections = company_data.get('fcf_projections', [])
    discount_rate = company_data.get('wacc', 0.12)
    terminal_growth = company_data.get('terminal_growth', 0.03)
    
    if not fcf_projections:
        return {"error": "No FCF projections provided"}
    
    # Calculate PV of cash flows
    pv_fcf = sum(
        fcf / ((1 + discount_rate) ** (i + 1))
        for i, fcf in enumerate(fcf_projections)
    )
    
    # Terminal value
    terminal_fcf = fcf_projections[-1] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1 + discount_rate) ** len(fcf_projections))
    
    enterprise_value = pv_fcf + pv_terminal
    
    return {
        "method": "DCF",
        "valuation": enterprise_value,
        "pv_cash_flows": pv_fcf,
        "pv_terminal_value": pv_terminal,
        "assumptions": {
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth
        }
    }


def perform_multiples_valuation(
    company_data: Dict[str, Any],
    comparables: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Perform comparables-based valuation"""
    
    # Calculate median multiples from comparables
    ev_revenue_multiples = [c.get('ev_revenue', 0) for c in comparables if c.get('ev_revenue')]
    ev_ebitda_multiples = [c.get('ev_ebitda', 0) for c in comparables if c.get('ev_ebitda')]
    
    median_ev_revenue = sorted(ev_revenue_multiples)[len(ev_revenue_multiples)//2] if ev_revenue_multiples else 5
    median_ev_ebitda = sorted(ev_ebitda_multiples)[len(ev_ebitda_multiples)//2] if ev_ebitda_multiples else 15
    
    # Apply to company
    company_revenue = company_data.get('revenue', 0)
    company_ebitda = company_data.get('ebitda', company_revenue * 0.2)
    
    valuation_by_revenue = company_revenue * median_ev_revenue
    valuation_by_ebitda = company_ebitda * median_ev_ebitda
    
    return {
        "method": "Multiples",
        "valuation": (valuation_by_revenue + valuation_by_ebitda) / 2,
        "by_revenue": valuation_by_revenue,
        "by_ebitda": valuation_by_ebitda,
        "multiples_used": {
            "ev_revenue": median_ev_revenue,
            "ev_ebitda": median_ev_ebitda
        }
    }


def perform_vc_method_valuation(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Perform VC method valuation"""
    
    exit_year = company_data.get('exit_year', 5)
    exit_revenue = company_data.get('current_revenue', 0) * ((1 + company_data.get('growth_rate', 0.5)) ** exit_year)
    exit_multiple = company_data.get('exit_multiple', 5)
    exit_value = exit_revenue * exit_multiple
    
    required_return = company_data.get('required_return', 0.30)
    
    # Present value
    post_money = exit_value / ((1 + required_return) ** exit_year)
    
    return {
        "method": "VC Method",
        "valuation": post_money,
        "exit_value": exit_value,
        "required_return": required_return,
        "exit_year": exit_year
    }


def perform_berkus_valuation(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Perform Berkus method valuation for early stage"""
    
    value = 0
    components = {}
    
    # Sound idea (up to $500k)
    if company_data.get('has_sound_idea'):
        components['sound_idea'] = 500_000
        value += 500_000
    
    # Prototype (up to $500k)
    if company_data.get('has_prototype'):
        components['prototype'] = 500_000
        value += 500_000
    
    # Quality management team (up to $500k)
    if company_data.get('team_score', 0) > 7:
        components['quality_team'] = 500_000
        value += 500_000
    
    # Strategic relationships (up to $500k)
    if company_data.get('has_strategic_relationships'):
        components['relationships'] = 500_000
        value += 500_000
    
    # Product rollout or sales (up to $500k)
    if company_data.get('has_sales'):
        components['sales'] = 500_000
        value += 500_000
    
    return {
        "method": "Berkus",
        "valuation": value,
        "components": components
    }


def calculate_weighted_valuation(valuations: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate weighted average valuation"""
    
    # Default weights
    weights = {
        "dcf": 0.40,
        "multiples": 0.30,
        "vc_method": 0.20,
        "berkus": 0.10
    }
    
    weighted_sum = 0
    total_weight = 0
    
    for method, data in valuations.items():
        if 'valuation' in data and method in weights:
            weighted_sum += data['valuation'] * weights[method]
            total_weight += weights[method]
    
    return {
        "weighted_valuation": weighted_sum / total_weight if total_weight > 0 else 0,
        "weights_used": weights
    }


def calculate_median_valuation(valuations: Dict[str, Any]) -> float:
    """Calculate median valuation"""
    
    values = [v.get('valuation', 0) for v in valuations.values() if 'valuation' in v]
    
    if not values:
        return 0
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    if n % 2 == 0:
        return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
    else:
        return sorted_values[n//2]


def perform_valuation_sensitivity(
    company_data: Dict[str, Any],
    valuations: Dict[str, Any]
) -> Dict[str, Any]:
    """Perform sensitivity analysis on valuation"""
    
    # Key variables to test
    variables = ['revenue_growth', 'discount_rate', 'exit_multiple']
    
    sensitivity = {}
    
    for variable in variables:
        base_value = company_data.get(variable, 0)
        
        # Test +/- 20%
        scenarios = {
            'down_20': base_value * 0.8,
            'base': base_value,
            'up_20': base_value * 1.2
        }
        
        sensitivity[variable] = scenarios
    
    return sensitivity


def evaluate_scenario(scenario: Dict[str, Any], metrics: List[str]) -> Dict[str, Any]:
    """Evaluate a specific scenario"""
    
    results = {}
    
    for metric in metrics:
        if metric == "irr":
            results['irr'] = calculate_irr_simple(
                scenario.get('investment', 0),
                scenario.get('exit_value', 0),
                scenario.get('hold_period', 5)
            )
        elif metric == "moic":
            investment = scenario.get('investment', 1)
            results['moic'] = scenario.get('exit_value', 0) / investment if investment > 0 else 0
        elif metric == "ownership":
            results['ownership'] = scenario.get('final_ownership', 0)
        elif metric == "value":
            results['value'] = scenario.get('exit_value', 0) * scenario.get('ownership', 0)
    
    return results


def perform_sensitivity_on_variable(
    base_case: Dict[str, Any],
    variable: str,
    metrics: List[str]
) -> Dict[str, Any]:
    """Perform sensitivity analysis on a single variable"""
    
    base_value = base_case.get(variable, 0)
    
    results = {}
    
    for change in [-0.5, -0.25, 0, 0.25, 0.5]:
        scenario = base_case.copy()
        scenario[variable] = base_value * (1 + change)
        
        results[f"{int(change*100):+d}%"] = evaluate_scenario(scenario, metrics)
    
    return results


def calculate_probability_weighted_outcome(
    results: Dict[str, Any],
    scenarios: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Calculate probability-weighted expected outcome"""
    
    weighted = {}
    
    for scenario in scenarios:
        scenario_name = scenario.get('name', 'Scenario')
        probability = scenario.get('probability', 0)
        
        if scenario_name in results:
            for metric, value in results[scenario_name].items():
                if isinstance(value, (int, float)):
                    weighted[metric] = weighted.get(metric, 0) + (value * probability)
    
    return weighted


def summarize_scenarios(results: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize scenario analysis results"""
    
    # Extract key metrics across scenarios
    irrs = []
    moics = []
    
    for scenario_name, scenario_results in results.items():
        if isinstance(scenario_results, dict):
            if 'irr' in scenario_results:
                irrs.append(scenario_results['irr'])
            if 'moic' in scenario_results:
                moics.append(scenario_results['moic'])
    
    return {
        "irr_range": [min(irrs), max(irrs)] if irrs else [0, 0],
        "moic_range": [min(moics), max(moics)] if moics else [0, 0],
        "scenario_count": len(results)
    }


def generate_scenario_recommendations(results: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on scenario analysis"""
    
    recommendations = []
    
    # Check IRR spread
    summary = summarize_scenarios(results)
    irr_spread = summary['irr_range'][1] - summary['irr_range'][0]
    
    if irr_spread > 0.20:
        recommendations.append("High variability in returns - consider risk mitigation strategies")
    
    # Check base case
    if 'base_case' in results:
        base_irr = results['base_case'].get('irr', 0)
        if base_irr < 0.20:
            recommendations.append("Base case IRR below 20% - evaluate investment thesis")
    
    # Check probability-weighted outcome
    if 'probability_weighted' in results:
        weighted_irr = results['probability_weighted'].get('irr', 0)
        if weighted_irr > 0.25:
            recommendations.append("Strong probability-weighted returns support investment")
    
    return recommendations


# ==================== INFO ENDPOINTS ====================

@router.get("/strategies")
async def get_sizing_strategies():
    """Get available position sizing strategies"""
    return {
        "strategies": [
            {
                "id": "equal_weight",
                "name": "Equal Weight",
                "description": "Allocate equal amounts to each position"
            },
            {
                "id": "kelly_criterion",
                "name": "Kelly Criterion",
                "description": "Optimal bet sizing based on edge and odds"
            },
            {
                "id": "risk_parity",
                "name": "Risk Parity",
                "description": "Equal risk contribution from each position"
            },
            {
                "id": "volatility_scaled",
                "name": "Volatility Scaled",
                "description": "Size inversely proportional to volatility"
            },
            {
                "id": "max_sharpe",
                "name": "Maximum Sharpe",
                "description": "Optimize for highest risk-adjusted returns"
            }
        ]
    }


@router.get("/")
async def position_sizing_info():
    """Get information about position sizing API"""
    return {
        "name": "Position Sizing & FP&A API",
        "version": "1.0.0",
        "description": "Advanced position sizing, ownership analysis, and financial planning",
        "capabilities": [
            "Optimal position sizing with multiple strategies",
            "Ownership tracking through funding rounds",
            "Scenario analysis and sensitivity testing",
            "FP&A forecasting with multiple scenarios",
            "Unit economics analysis",
            "Comprehensive valuation methods",
            "Portfolio optimization"
        ],
        "endpoints": {
            "sizing": [
                "/calculate-sizes",
                "/vc-sizing",
                "/optimize-portfolio"
            ],
            "ownership": [
                "/ownership-scenario"
            ],
            "fpa": [
                "/fpa/forecast",
                "/fpa/unit-economics"
            ],
            "valuation": [
                "/valuation/comprehensive"
            ],
            "analysis": [
                "/scenario-analysis"
            ]
        }
    }