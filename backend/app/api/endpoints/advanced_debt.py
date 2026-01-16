"""
Advanced Debt Structures Endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

try:
    from app.services.advanced_debt_structures_service import AdvancedDebtStructures
except ImportError as exc:
    AdvancedDebtStructures = None  # Degraded mode
    logger = logging.getLogger(__name__)
    logger.warning(
        "AdvancedDebtStructures service unavailable: %s", exc
    )

router = APIRouter()
logger = logging.getLogger(__name__)


class DebtAnalysisRequest(BaseModel):
    debt_type: str  # venture_debt, convertible_debt, pik_loan, etc.
    principal: float
    terms: Dict[str, Any]
    company_metrics: Dict[str, Any] = {}


class VentureDebtRequest(BaseModel):
    principal: float
    interest_rate: float
    term_months: int
    warrant_coverage: float = 0.05  # 5% warrant coverage typical
    company_valuation: float
    monthly_burn: float
    cash_runway_months: int


class ConvertibleDebtRequest(BaseModel):
    principal: float
    interest_rate: float
    maturity_months: int
    conversion_discount: float = 0.2  # 20% discount typical
    valuation_cap: Optional[float] = None
    company_metrics: Dict[str, Any] = {}


@router.post("/analyze-structure")
async def analyze_debt_structure(request: DebtAnalysisRequest):
    """Analyze any debt structure type"""
    if not AdvancedDebtStructures:
        raise HTTPException(status_code=503, detail="Advanced debt module unavailable")

    try:
        debt_engine = AdvancedDebtStructures()
        
        result = await debt_engine.analyze_structure(
            debt_type=request.debt_type,
            principal=request.principal,
            terms=request.terms,
            company_metrics=request.company_metrics
        )
        
        return {
            "success": True,
            "debt_type": request.debt_type,
            "principal": request.principal,
            "analysis": result,
            "recommendations": result.get("recommendations", [])
        }
        
    except Exception as e:
        logger.error(f"Debt structure analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/venture-debt")
async def venture_debt_analysis(request: VentureDebtRequest):
    """Analyze venture debt terms and impact"""
    if not AdvancedDebtStructures:
        raise HTTPException(status_code=503, detail="Advanced debt module unavailable")

    try:
        debt_engine = AdvancedDebtStructures()
        
        terms = {
            "interest_rate": request.interest_rate,
            "term_months": request.term_months,
            "warrant_coverage": request.warrant_coverage,
            "company_valuation": request.company_valuation
        }
        
        company_metrics = {
            "monthly_burn": request.monthly_burn,
            "cash_runway_months": request.cash_runway_months,
            "valuation": request.company_valuation
        }
        
        result = await debt_engine.analyze_structure(
            debt_type="venture_debt",
            principal=request.principal,
            terms=terms,
            company_metrics=company_metrics
        )
        
        return {
            "success": True,
            "debt_type": "venture_debt",
            "principal": request.principal,
            "monthly_payment": result.get("monthly_payment", 0),
            "total_cost": result.get("total_cost", 0),
            "warrant_value": result.get("warrant_value", 0),
            "runway_extension": result.get("runway_extension_months", 0),
            "dilution_impact": result.get("dilution_impact", 0),
            "risk_assessment": result.get("risk_assessment", {})
        }
        
    except Exception as e:
        logger.error(f"Venture debt analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/convertible-debt")
async def convertible_debt_analysis(request: ConvertibleDebtRequest):
    """Analyze convertible debt terms and conversion scenarios"""
    if not AdvancedDebtStructures:
        raise HTTPException(status_code=503, detail="Advanced debt module unavailable")

    try:
        debt_engine = AdvancedDebtStructures()
        
        terms = {
            "interest_rate": request.interest_rate,
            "maturity_months": request.maturity_months,
            "conversion_discount": request.conversion_discount,
            "valuation_cap": request.valuation_cap
        }
        
        result = await debt_engine.analyze_structure(
            debt_type="convertible_debt",
            principal=request.principal,
            terms=terms,
            company_metrics=request.company_metrics
        )
        
        return {
            "success": True,
            "debt_type": "convertible_debt",
            "principal": request.principal,
            "conversion_scenarios": result.get("conversion_scenarios", []),
            "interest_accrual": result.get("interest_accrual", 0),
            "dilution_analysis": result.get("dilution_analysis", {}),
            "optimal_conversion": result.get("optimal_conversion", {}),
            "investor_returns": result.get("investor_returns", {})
        }
        
    except Exception as e:
        logger.error(f"Convertible debt analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debt-types")
async def get_debt_types():
    """Get available debt structure types and their characteristics"""
    return {
        "debt_types": {
            "venture_debt": {
                "name": "Venture Debt",
                "description": "Non-dilutive debt financing with warrants",
                "typical_terms": {
                    "interest_rate": "8-15%",
                    "term": "24-36 months",
                    "warrant_coverage": "3-10%",
                    "covenants": "Financial and operational"
                },
                "best_for": "Companies with 12+ months runway, recurring revenue"
            },
            "convertible_debt": {
                "name": "Convertible Note",
                "description": "Debt that converts to equity in future round",
                "typical_terms": {
                    "interest_rate": "2-8%",
                    "maturity": "18-24 months",
                    "discount": "10-25%",
                    "cap": "Optional valuation ceiling"
                },
                "best_for": "Bridge financing, pre-Series A companies"
            },
            "pik_loan": {
                "name": "Payment-in-Kind Loan",
                "description": "Interest paid in additional debt rather than cash",
                "typical_terms": {
                    "interest_rate": "12-20%",
                    "term": "3-7 years",
                    "compounding": "Quarterly or annual",
                    "security": "Often secured by assets"
                },
                "best_for": "Cash-strapped companies, distressed situations"
            },
            "revenue_based": {
                "name": "Revenue-Based Financing",
                "description": "Repayment tied to percentage of monthly revenue",
                "typical_terms": {
                    "fee": "2-10% of revenue",
                    "multiple": "1.3-2.5x principal",
                    "term": "Until multiple paid",
                    "revenue_floor": "Minimum monthly payment"
                },
                "best_for": "SaaS companies with predictable revenue"
            }
        },
        "key_metrics": [
            "effective_interest_rate",
            "total_cost_of_capital",
            "dilution_impact",
            "cash_runway_extension",
            "covenant_compliance_risk"
        ]
    }


@router.post("/compare-structures")
async def compare_debt_structures(structures: List[DebtAnalysisRequest]):
    """Compare multiple debt structure options"""
    try:
        debt_engine = AdvancedDebtStructures()
        comparisons = []
        
        for structure in structures:
            result = await debt_engine.analyze_structure(
                debt_type=structure.debt_type,
                principal=structure.principal,
                terms=structure.terms,
                company_metrics=structure.company_metrics
            )
            
            comparisons.append({
                "debt_type": structure.debt_type,
                "principal": structure.principal,
                "total_cost": result.get("total_cost", 0),
                "effective_rate": result.get("effective_interest_rate", 0),
                "runway_impact": result.get("runway_extension_months", 0),
                "risk_score": result.get("risk_score", 0),
                "recommendation": result.get("recommendation", "")
            })
        
        # Rank by total cost and risk
        ranked = sorted(comparisons, key=lambda x: x["total_cost"] + x["risk_score"] * 1000)
        
        return {
            "success": True,
            "comparison": comparisons,
            "recommended": ranked[0] if ranked else None,
            "key_differences": [
                "Total cost of capital varies by structure type",
                "Dilution impact depends on warrant/conversion terms",
                "Risk profiles differ based on covenants and terms"
            ]
        }
        
    except Exception as e:
        logger.error(f"Debt structure comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
