"""
Financial Tools API - Production Ready Endpoints
FastAPI endpoints for financial calculations and spreadsheet operations
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import logging
from app.tools.financial_tools import financial_tools, spreadsheet_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/financial", tags=["Financial Tools"])


# Request/Response Models
class NPVRequest(BaseModel):
    discount_rate: float = Field(..., description="Discount rate (e.g., 0.10 for 10%)", ge=0, le=1)
    cash_flows: List[float] = Field(..., description="Cash flows [initial_investment, year1, year2, ...]", min_items=2)


class LoanRequest(BaseModel):
    principal: float = Field(..., description="Loan amount", gt=0)
    annual_rate: float = Field(..., description="Annual interest rate (e.g., 0.05 for 5%)", ge=0, le=1)
    years: int = Field(..., description="Loan term in years", gt=0, le=50)
    payment_frequency: int = Field(12, description="Payments per year (12 for monthly)", gt=0, le=365)


class InvestmentRequest(BaseModel):
    initial_amount: float = Field(..., description="Initial investment", ge=0)
    annual_return: float = Field(..., description="Expected annual return", ge=0, le=1)
    years: int = Field(..., description="Investment period", gt=0, le=50)
    additional_monthly: float = Field(0, description="Monthly additional contributions", ge=0)


class FinancialModelRequest(BaseModel):
    revenue: float = Field(..., description="Base year revenue", gt=0)
    growth_rate: float = Field(..., description="Annual growth rate", ge=0, le=5)
    margins: Dict[str, float] = Field(..., description="Margin assumptions (gross, operating, net)")
    years: int = Field(5, description="Number of years to project", gt=0, le=20)


class FormulaRequest(BaseModel):
    formula: str = Field(..., description="Excel-style formula")
    cell_values: Optional[Dict[str, Any]] = Field(None, description="Cell reference values")
    named_ranges: Optional[Dict[str, List[Any]]] = Field(None, description="Named range values")


class StatisticsRequest(BaseModel):
    values: List[Union[int, float]] = Field(..., description="Numeric values for analysis", min_items=1)


class PivotRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(..., description="Data records", min_items=1)
    group_by: str = Field(..., description="Field to group by")
    aggregate_field: str = Field(..., description="Field to aggregate")
    operation: str = Field("sum", description="Aggregation operation", regex="^(sum|average|count|min|max)$")


# API Endpoints
@router.post("/npv", summary="Calculate Net Present Value")
async def calculate_npv(request: NPVRequest):
    """
    Calculate Net Present Value (NPV) for a series of cash flows.
    
    NPV helps determine the profitability of an investment by calculating
    the present value of future cash flows minus the initial investment.
    """
    try:
        result = financial_tools.calculate_npv(request.discount_rate, request.cash_flows)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "data": result,
            "interpretation": {
                "decision": "Accept" if result["npv"] > 0 else "Reject",
                "reasoning": f"NPV of ${result['npv']:,.2f} indicates the project will " +
                           ("add value" if result["npv"] > 0 else "destroy value"),
                "profitability_index": result["profitability_index"],
                "break_even_rate": "Higher than provided discount rate" if result["npv"] > 0 else "Lower than provided discount rate"
            }
        }
        
    except Exception as e:
        logger.error(f"NPV calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/irr", summary="Calculate Internal Rate of Return")
async def calculate_irr(cash_flows: List[float] = Field(..., description="Cash flows", min_items=2)):
    """
    Calculate Internal Rate of Return (IRR) for a series of cash flows.
    
    IRR is the discount rate that makes the NPV of cash flows equal to zero.
    """
    try:
        result = financial_tools.calculate_irr(cash_flows)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "data": result,
            "interpretation": {
                "annualized_return": f"{result['irr']:.1%}",
                "comparison_benchmark": "Compare with cost of capital or alternative investments",
                "risk_assessment": "Higher IRR generally indicates better investment, but consider risk factors"
            }
        }
        
    except Exception as e:
        logger.error(f"IRR calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/loan", summary="Calculate Loan Payment Details")
async def calculate_loan(request: LoanRequest):
    """
    Calculate comprehensive loan payment analysis including monthly payments,
    total interest, and amortization schedule.
    """
    try:
        result = financial_tools.calculate_loan_payment(
            request.principal, 
            request.annual_rate, 
            request.years, 
            request.payment_frequency
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "data": result,
            "summary": {
                "monthly_payment": f"${result['monthly_payment']:,.2f}",
                "total_cost": f"${result['total_cost']:,.2f}",
                "interest_percentage": f"{result['interest_to_principal_ratio']:.1%}",
                "affordability_check": "Payment should be <28% of monthly income for conventional loans"
            }
        }
        
    except Exception as e:
        logger.error(f"Loan calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/investment", summary="Calculate Investment Growth Projection")
async def calculate_investment(request: InvestmentRequest):
    """
    Project investment growth with compound interest and regular contributions.
    """
    try:
        result = financial_tools.calculate_investment_growth(
            request.initial_amount,
            request.annual_return,
            request.years,
            request.additional_monthly
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "data": result,
            "milestones": {
                "doubling_time": f"~{70 / (request.annual_return * 100):.1f} years (Rule of 72)",
                "monthly_growth": f"${(result['final_value'] - result['total_contributions']) / (request.years * 12):,.2f}",
                "compound_effect": f"${result['final_value'] - result['total_contributions']:,.2f}"
            }
        }
        
    except Exception as e:
        logger.error(f"Investment calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model", summary="Create Financial Model")
async def create_financial_model(request: FinancialModelRequest):
    """
    Generate a comprehensive financial model with multi-year projections,
    including revenue, costs, and profitability metrics.
    """
    try:
        result = financial_tools.create_financial_model(
            request.revenue,
            request.growth_rate,
            request.margins,
            request.years
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Add valuation metrics
        final_revenue = result["projections"][-1]["revenue"]
        final_net_income = result["projections"][-1]["net_income"]
        
        # Simple P/E and revenue multiple estimates
        pe_ratio = 25  # Assume 25x P/E for growth company
        revenue_multiple = 5  # Assume 5x revenue multiple
        
        estimated_valuation = {
            "earnings_based": final_net_income * pe_ratio,
            "revenue_based": final_revenue * revenue_multiple,
            "dcf_inputs": {
                "terminal_growth": 0.03,  # 3% terminal growth
                "discount_rate": 0.12     # 12% discount rate
            }
        }
        
        return {
            "success": True,
            "data": result,
            "valuation_estimates": estimated_valuation,
            "key_metrics": {
                "revenue_cagr": f"{result['summary']['revenue_cagr']:.1f}%",
                "average_net_margin": f"{sum(p['net_margin_percentage'] for p in result['projections']) / len(result['projections']):.1f}%",
                "total_net_income": f"${result['summary']['total_projected_net_income']:,.0f}"
            }
        }
        
    except Exception as e:
        logger.error(f"Financial model error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/formula", summary="Evaluate Excel Formula")
async def evaluate_formula(request: FormulaRequest):
    """
    Evaluate Excel-compatible formulas with support for 50+ functions
    including financial, statistical, mathematical, and logical operations.
    """
    try:
        result = spreadsheet_tools.evaluate_formula(
            request.formula,
            request.cell_values,
            request.named_ranges
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "data": result,
            "formula_info": {
                "input": request.formula,
                "result": result["result"],
                "result_type": result["result_type"],
                "complexity": "High" if len(request.formula) > 50 else "Medium" if len(request.formula) > 20 else "Low"
            }
        }
        
    except Exception as e:
        logger.error(f"Formula evaluation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/statistics", summary="Calculate Statistical Analysis")
async def calculate_statistics(request: StatisticsRequest):
    """
    Perform comprehensive statistical analysis including descriptive statistics,
    distribution measures, and quartile analysis.
    """
    try:
        result = spreadsheet_tools.calculate_statistics(request.values)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Add interpretation
        cv = result["coefficient_of_variation"]
        variability = "Low" if cv < 15 else "Moderate" if cv < 30 else "High"
        
        return {
            "success": True,
            "data": result,
            "interpretation": {
                "sample_size": result["count"],
                "central_tendency": f"Mean: {result['average']}, Median: {result['median']}",
                "variability": f"{variability} (CV: {cv:.1f}%)",
                "distribution": f"Range: {result['range']}, IQR: {result['iqr']}",
                "outlier_threshold": {
                    "lower": result["q1"] - 1.5 * result["iqr"],
                    "upper": result["q3"] + 1.5 * result["iqr"]
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Statistics calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pivot", summary="Create Pivot Table Summary")
async def create_pivot(request: PivotRequest):
    """
    Generate pivot table summaries with grouping and aggregation operations.
    """
    try:
        result = spreadsheet_tools.create_pivot_summary(
            request.data,
            request.group_by,
            request.aggregate_field,
            request.operation
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Add insights
        pivot_data = result["pivot_data"]
        max_group = max(pivot_data.keys(), key=lambda k: pivot_data[k])
        min_group = min(pivot_data.keys(), key=lambda k: pivot_data[k])
        
        return {
            "success": True,
            "data": result,
            "insights": {
                "top_performer": f"{max_group}: {pivot_data[max_group]}",
                "lowest_performer": f"{min_group}: {pivot_data[min_group]}",
                "average_value": result["total"] / result["group_count"] if result["group_count"] > 0 else 0,
                "data_distribution": "Analyze the spread across groups for patterns"
            }
        }
        
    except Exception as e:
        logger.error(f"Pivot table error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Utility Endpoints
@router.get("/functions", summary="List Available Functions")
async def get_available_functions():
    """Get list of all available spreadsheet functions"""
    try:
        from app.services.formula_evaluator import formula_evaluator
        
        functions = list(formula_evaluator.functions.keys())
        
        categories = {
            "Financial": ["NPV", "IRR", "PV", "FV", "PMT", "RATE", "NPER", "SLN", "DB", "DDB", "EFFECT", "NOMINAL"],
            "Mathematical": ["SUM", "AVERAGE", "MIN", "MAX", "COUNT", "ROUND", "SQRT", "POWER", "ABS", "LOG", "LN", "EXP"],
            "Statistical": ["MEDIAN", "MODE", "STDEV", "STDEVP", "VAR", "VARP"],
            "Trigonometric": ["SIN", "COS", "TAN", "ASIN", "ACOS", "ATAN", "ATAN2", "RADIANS", "DEGREES"],
            "Logical": ["IF", "AND", "OR", "NOT", "TRUE", "FALSE", "IFERROR", "ISNA", "ISERROR"],
            "Text": ["CONCATENATE", "LEN", "LEFT", "RIGHT", "MID", "UPPER", "LOWER", "TRIM", "FIND", "SEARCH"],
            "Date": ["TODAY", "NOW", "DATE", "TIME", "YEAR", "MONTH", "DAY", "WEEKDAY", "DAYS"],
            "Lookup": ["VLOOKUP", "HLOOKUP", "INDEX", "MATCH", "CHOOSE", "LOOKUP"],
            "Other": ["PI", "E", "RAND", "RANDBETWEEN", "SIGN", "MOD", "FACT", "GCD", "LCM"]
        }
        
        return {
            "success": True,
            "total_functions": len(functions),
            "categories": categories,
            "all_functions": sorted(functions)
        }
        
    except Exception as e:
        logger.error(f"Function listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="Health Check")
async def health_check():
    """Check if financial tools are working correctly"""
    try:
        # Quick calculation test
        test_result = financial_tools.calculate_npv(0.1, [-1000, 300, 400, 500])
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "features": [
                "Financial calculations (NPV, IRR, loans)",
                "Investment projections",
                "Excel formula evaluation",
                "Statistical analysis",
                "Financial modeling",
                "50+ spreadsheet functions"
            ],
            "test_calculation": f"NPV test: ${test_result.get('npv', 0):,.2f}"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Export router
__all__ = ["router"]