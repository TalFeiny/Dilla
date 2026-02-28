from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class CompanyBase(BaseModel):
    """Base company fields matching the Supabase companies table."""
    model_config = ConfigDict(from_attributes=True, extra="allow")

    name: str
    sector: Optional[str] = None
    stage: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    headquarters: Optional[str] = None
    business_model: Optional[str] = None
    revenue_model: Optional[str] = None
    kpi_framework: Optional[str] = None
    funding_stage: Optional[str] = None
    founded_year: Optional[int] = None
    ai_first: Optional[bool] = None
    ai_category: Optional[str] = None
    category: Optional[str] = None


class CompanyMinimal(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str
    name: str
    current_arr_usd: Optional[float] = None
    sector: Optional[str] = None
    current_valuation_usd: Optional[float] = None
    founded_year: Optional[int] = None


class Company(CompanyBase):
    """Full company schema matching Supabase companies table columns."""
    id: str
    organization_id: Optional[str] = None
    fund_id: Optional[str] = None

    # Revenue metrics
    current_arr_usd: Optional[float] = None
    current_mrr_usd: Optional[float] = None
    revenue_growth_monthly_pct: Optional[float] = None
    revenue_growth_annual_pct: Optional[float] = None

    # Valuation
    current_valuation_usd: Optional[float] = None
    last_valuation_usd: Optional[float] = None

    # Burn & runway
    burn_rate_monthly_usd: Optional[float] = None
    runway_months: Optional[float] = None
    cash_in_bank_usd: Optional[float] = None

    # Funding
    total_raised: Optional[float] = None
    total_invested_usd: Optional[float] = None
    amount_raised: Optional[Any] = None  # JSONB in DB
    round_size: Optional[Any] = None  # JSONB in DB
    quarter_raised: Optional[str] = None
    last_funding_date: Optional[str] = None

    # Growth & efficiency
    growth_rate: Optional[float] = None
    gross_margin: Optional[float] = None
    employee_count: Optional[int] = None
    tam: Optional[float] = None
    current_option_pool_bps: Optional[float] = None

    # Funnel & sourcing
    funnel_status: Optional[str] = None
    thesis_match_score: Optional[float] = None
    recommendation_reason: Optional[Any] = None  # JSONB
    added_to_watchlist_at: Optional[str] = None
    watchlist_priority: Optional[str] = None

    # Term sheet
    term_sheet_sent_at: Optional[str] = None
    term_sheet_status: Optional[str] = None
    term_sheet_expiry_date: Optional[str] = None

    # Investment tracking
    first_investment_date: Optional[str] = None
    latest_investment_date: Optional[str] = None
    ownership_percentage: Optional[float] = None
    investment_lead: Optional[str] = None

    # Exit
    exit_date: Optional[str] = None
    exit_type: Optional[str] = None
    exit_value_usd: Optional[float] = None
    exit_multiple: Optional[float] = None

    # Customer segments
    customer_segment_enterprise_pct: Optional[float] = None
    customer_segment_midmarket_pct: Optional[float] = None
    customer_segment_sme_pct: Optional[float] = None

    # PWERM
    has_pwerm_model: Optional[bool] = None
    latest_pwerm_run_at: Optional[str] = None
    pwerm_scenarios_count: Optional[int] = None

    # Updates tracking
    latest_update: Optional[str] = None
    latest_update_date: Optional[str] = None
    update_frequency_days: Optional[int] = None
    last_contacted_date: Optional[str] = None

    # Field update timestamps
    cash_updated_at: Optional[str] = None
    burn_rate_updated_at: Optional[str] = None
    runway_updated_at: Optional[str] = None
    revenue_updated_at: Optional[str] = None
    gross_margin_updated_at: Optional[str] = None

    # Location & flexible data
    location: Optional[Any] = None  # JSONB
    extra_data: Optional[Dict[str, Any]] = None
    currency_mix: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    sector: Optional[str] = None
    stage: Optional[str] = None
    status: Optional[str] = None
    current_arr_usd: Optional[float] = None
    current_valuation_usd: Optional[float] = None
    burn_rate_monthly_usd: Optional[float] = None
    growth_rate: Optional[float] = None
    total_raised: Optional[float] = None
    extra_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
