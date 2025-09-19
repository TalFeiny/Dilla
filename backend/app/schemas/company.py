from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class CompanyBase(BaseModel):
    name: str
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    year_founded: Optional[int] = None
    headquarters: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    business_model: Optional[str] = None
    target_customer: Optional[str] = None
    
    class Config:
        from_attributes = True


class CompanyMinimal(BaseModel):
    id: str
    name: str
    current_arr_usd: Optional[float] = None
    sector: Optional[str] = None
    current_valuation_usd: Optional[float] = None
    year_founded: Optional[int] = None
    
    class Config:
        from_attributes = True


class Company(CompanyBase):
    id: str
    current_arr_usd: Optional[float] = None
    current_valuation_usd: Optional[float] = None
    growth_rate: Optional[float] = None
    burn_rate: Optional[float] = None
    runway_months: Optional[int] = None
    last_funding_date: Optional[datetime] = None
    last_funding_amount_usd: Optional[float] = None
    total_funding_usd: Optional[float] = None
    employee_count: Optional[int] = None
    churn_rate: Optional[float] = None
    gross_margin: Optional[float] = None
    ltv_cac_ratio: Optional[float] = None
    nps_score: Optional[int] = None
    competitive_position: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    current_arr_usd: Optional[float] = None
    current_valuation_usd: Optional[float] = None
    growth_rate: Optional[float] = None
    burn_rate: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None