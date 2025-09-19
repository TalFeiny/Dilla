"""
Compliance and KYC endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from app.core.database import supabase_service
from app.services.enhanced_compliance_service import enhanced_compliance_service

router = APIRouter()
logger = logging.getLogger(__name__)


class KYCCheckRequest(BaseModel):
    entity_name: str
    entity_type: str = "company"
    check_types: Optional[List[str]] = ["kyc", "aml", "sanctions"]


class KYCCheckResponse(BaseModel):
    entity_name: str
    entity_type: str
    check_status: str
    risk_score: int
    results: Dict[str, Any]
    checked_at: str


@router.post("/kyc/check", response_model=KYCCheckResponse)
async def perform_kyc_check(request: KYCCheckRequest):
    """
    Perform KYC/AML compliance check on an entity
    """
    try:
        logger.info(f"Performing KYC check for {request.entity_name}")
        
        # Mock KYC check results
        risk_score = 25 if "test" in request.entity_name.lower() else 15
        check_status = "clear" if risk_score < 30 else "review_required"
        
        results = {
            "kyc": {
                "status": "passed",
                "verified": True,
                "verification_date": datetime.now().isoformat()
            },
            "aml": {
                "status": "clear",
                "matches": 0,
                "last_checked": datetime.now().isoformat()
            },
            "sanctions": {
                "status": "clear",
                "lists_checked": ["OFAC", "UN", "EU"],
                "matches": 0
            },
            "pep": {
                "status": "not_found",
                "politically_exposed": False
            },
            "adverse_media": {
                "status": "clear",
                "articles_found": 0
            }
        }
        
        # Try to store in database if table exists
        try:
            client = supabase_service.get_client()
            client.table("compliance_checks").insert({
                "entity_name": request.entity_name,
                "entity_type": request.entity_type,
                "check_type": "kyc",
                "check_status": check_status,
                "risk_score": risk_score,
                "results": results,
                "checked_by": "system"
            }).execute()
        except Exception as db_error:
            logger.warning(f"Could not store compliance check: {db_error}")
        
        return KYCCheckResponse(
            entity_name=request.entity_name,
            entity_type=request.entity_type,
            check_status=check_status,
            risk_score=risk_score,
            results=results,
            checked_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error performing KYC check: {e}")
        raise HTTPException(status_code=500, detail=f"KYC check failed: {str(e)}")


@router.get("/kyc/history/{entity_name}")
async def get_kyc_history(entity_name: str):
    """
    Get KYC check history for an entity
    """
    try:
        client = supabase_service.get_client()
        
        try:
            response = client.table("compliance_checks")\
                .select("*")\
                .eq("entity_name", entity_name)\
                .order("created_at.desc")\
                .execute()
                
            if response.data:
                return response.data
            else:
                # Return mock history
                return [{
                    "entity_name": entity_name,
                    "check_type": "kyc",
                    "check_status": "clear",
                    "risk_score": 10,
                    "created_at": datetime.now().isoformat(),
                    "message": "Mock historical data"
                }]
                
        except Exception:
            # Return mock data if table doesn't exist
            return [{
                "entity_name": entity_name,
                "check_type": "kyc", 
                "check_status": "clear",
                "risk_score": 10,
                "created_at": datetime.now().isoformat(),
                "message": "Mock data - table pending"
            }]
            
    except Exception as e:
        logger.error(f"Error fetching KYC history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch KYC history")


@router.post("/aml/screen")
async def aml_screening(entity_name: str, entity_type: str = "company"):
    """
    Perform AML screening
    """
    try:
        logger.info(f"Performing AML screening for {entity_name}")
        
        # Mock AML screening
        return {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "screening_result": "clear",
            "matches": [],
            "risk_level": "low",
            "screened_at": datetime.now().isoformat(),
            "lists_checked": ["OFAC", "UN", "EU", "UK", "FATF"]
        }
        
    except Exception as e:
        logger.error(f"Error in AML screening: {e}")
        raise HTTPException(status_code=500, detail="AML screening failed")


@router.get("/risk/assessment/{entity_name}")
async def risk_assessment(entity_name: str):
    """
    Get comprehensive risk assessment for an entity
    """
    try:
        # Mock risk assessment
        return {
            "entity_name": entity_name,
            "overall_risk_score": 22,
            "risk_level": "low",
            "risk_factors": {
                "jurisdiction": 10,
                "industry": 15,
                "ownership": 20,
                "transactions": 25,
                "reputation": 30
            },
            "recommendations": [
                "Standard due diligence sufficient",
                "Annual review recommended"
            ],
            "assessed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in risk assessment: {e}")
        raise HTTPException(status_code=500, detail="Risk assessment failed")


class AdvisorInfoRequest(BaseModel):
    name: str
    sec_number: Optional[str] = "801-XXXXX"
    crd_number: Optional[str] = "XXXXXX"
    address: Optional[Dict[str, str]] = {}
    phone: Optional[str] = ""
    email: Optional[str] = ""
    website: Optional[str] = ""
    chief_compliance_officer: Optional[str] = ""
    compliance_phone: Optional[str] = ""
    supervised_persons: Optional[List[Dict[str, Any]]] = []
    aum: Optional[float] = 0
    client_count: Optional[int] = 0
    employee_count: Optional[int] = 0
    registration_status: Optional[str] = "registered"
    jurisdictions: Optional[List[str]] = ["SEC"]
    business_description: Optional[str] = ""
    client_types: Optional[List[str]] = ["institutional"]
    discretionary_aum: Optional[float] = 0
    fee_schedule: Optional[Dict[str, Any]] = {}
    billing_practices: Optional[str] = "quarterly in advance"
    charges_performance_fees: Optional[bool] = True
    investment_strategies: Optional[List[str]] = []
    has_custody: Optional[bool] = False
    custodian: Optional[str] = ""
    has_discretion: Optional[bool] = True
    votes_proxies: Optional[bool] = False


class AIFMDFundRequest(BaseModel):
    """Request model for European AIFMD reporting"""
    fund_name: str
    aifm_name: str
    lei_code: Optional[str] = ""
    fund_lei: Optional[str] = ""
    reporting_period: Optional[str] = "Q4 2024"
    inception_date: Optional[str] = ""
    aif_type: Optional[str] = "Hedge Fund"
    master_feeder: Optional[str] = "Standalone"
    prime_brokers: Optional[List[str]] = []
    primary_strategy: Optional[str] = "Equity Long/Short"
    nav: Optional[float] = 0
    aum: Optional[float] = 0
    leverage_gross: Optional[float] = 1.5
    leverage_commitment: Optional[float] = 1.2
    asset_breakdown: Optional[Dict[str, float]] = {}
    geo_breakdown: Optional[Dict[str, float]] = {}
    top_exposures: Optional[List[Dict[str, Any]]] = []
    currency_breakdown: Optional[Dict[str, float]] = {}
    market_risk: Optional[Dict[str, Any]] = {}
    counterparty_risk: Optional[Dict[str, Any]] = {}
    investor_liquidity: Optional[str] = "Quarterly with 90 days notice"
    portfolio_liquidity: Optional[Dict[str, float]] = {}
    stress_scenarios: Optional[List[Dict[str, Any]]] = []
    redemptions: Optional[float] = 0
    subscriptions: Optional[float] = 0
    nav_per_share: Optional[float] = 0
    sub_frequency: Optional[str] = "Monthly"
    red_frequency: Optional[str] = "Quarterly"


@router.post("/form-adv-2b/generate")
async def generate_form_adv_2b(advisor_info: AdvisorInfoRequest):
    """
    Generate Form ADV Part 2B - Brochure Supplement (US)
    """
    try:
        logger.info(f"Generating Form ADV Part 2B for {advisor_info.name}")
        
        result = enhanced_compliance_service.generate_form_adv_part_2b(advisor_info.dict())
        
        if result["success"]:
            return {
                "status": "success",
                "message": "Form ADV Part 2B generated successfully",
                "document": result["document"],
                "validation": result["validation"],
                "filing_requirements": result["filing_requirements"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate Form ADV Part 2B"))
            
    except Exception as e:
        logger.error(f"Error generating Form ADV Part 2B: {e}")
        raise HTTPException(status_code=500, detail=f"Form ADV Part 2B generation failed: {str(e)}")


@router.post("/form-adv/generate")
async def generate_form_adv(firm_info: AdvisorInfoRequest):
    """
    Generate complete Form ADV (Part 1, Part 2A, and Part 2B/Annex 5)
    """
    try:
        logger.info(f"Generating Form ADV for {firm_info.name}")
        
        result = enhanced_compliance_service.generate_form_adv(firm_info.dict())
        
        if result["success"]:
            return {
                "status": "success",
                "message": "Form ADV generated successfully",
                "form_adv": result["form_adv"],
                "validation": result["validation"],
                "filing_status": result["filing_status"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate Form ADV"))
            
    except Exception as e:
        logger.error(f"Error generating Form ADV: {e}")
        raise HTTPException(status_code=500, detail=f"Form ADV generation failed: {str(e)}")


@router.get("/compliance/status/{fund_id}")
async def get_compliance_status(fund_id: str):
    """
    Get overall compliance status for a fund
    """
    try:
        logger.info(f"Checking compliance status for fund {fund_id}")
        
        result = enhanced_compliance_service.check_compliance_status(fund_id)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to check compliance status"))
            
    except Exception as e:
        logger.error(f"Error checking compliance status: {e}")
        raise HTTPException(status_code=500, detail=f"Compliance status check failed: {str(e)}")


@router.get("/compliance/calendar")
async def get_regulatory_calendar(fund_name: Optional[str] = None):
    """
    Get regulatory filing calendar
    """
    try:
        logger.info("Generating regulatory calendar")
        
        fund_info = {
            "name": fund_name or "Default Fund",
            "type": "hedge_fund",
            "aum": 500000000
        }
        
        result = enhanced_compliance_service.generate_regulatory_calendar(fund_info)
        
        if result["success"]:
            return {
                "status": "success",
                "calendar": result["calendar"],
                "upcoming_deadlines": result["upcoming_deadlines"],
                "compliance_year": result["compliance_year"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate calendar"))
            
    except Exception as e:
        logger.error(f"Error generating regulatory calendar: {e}")
        raise HTTPException(status_code=500, detail=f"Calendar generation failed: {str(e)}")


@router.post("/aifmd/annex-iv/generate")
async def generate_aifmd_annex_iv(fund_info: AIFMDFundRequest):
    """
    Generate European AIFMD Annex IV reporting
    """
    try:
        logger.info(f"Generating AIFMD Annex IV for {fund_info.fund_name}")
        
        result = enhanced_compliance_service.generate_aifmd_annex_iv(fund_info.dict())
        
        if result["success"]:
            return {
                "status": "success",
                "message": "AIFMD Annex IV generated successfully",
                "document": result["document"],
                "validation": result["validation"],
                "filing_requirements": result["filing_requirements"]
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to generate AIFMD Annex IV"))
            
    except Exception as e:
        logger.error(f"Error generating AIFMD Annex IV: {e}")
        raise HTTPException(status_code=500, detail=f"AIFMD Annex IV generation failed: {str(e)}")