"""
Unified Data Models
Single source of truth for all data structures across the system
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

# Enums for standardized values
class CompanyStage(Enum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    SERIES_D = "series_d"
    GROWTH = "growth"
    IPO_READY = "ipo_ready"

class IndustryVertical(Enum):
    SAAS = "saas"
    FINTECH = "fintech"
    HEALTHTECH = "healthtech"
    EDTECH = "edtech"
    DEEPTECH = "deeptech"
    CONSUMER = "consumer"
    ENTERPRISE = "enterprise"
    CLIMATE = "climate"
    CRYPTO = "crypto"
    AI_ML = "ai_ml"
    BIOTECH = "biotech"
    HARDWARE = "hardware"

class InvestmentStatus(Enum):
    PIPELINE = "pipeline"
    DILIGENCE = "diligence"
    TERM_SHEET = "term_sheet"
    CLOSED = "closed"
    PASSED = "passed"
    MONITORING = "monitoring"
    EXITED = "exited"

class SecurityType(Enum):
    COMMON = "common"
    PREFERRED = "preferred"
    SAFE = "safe"
    CONVERTIBLE = "convertible"
    WARRANT = "warrant"
    PIK_LOAN = "pik_loan"

# Core data models
@dataclass
class Company:
    """Unified company data model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    domain: str = ""
    stage: Optional[CompanyStage] = None
    industry: Optional[IndustryVertical] = None
    
    # Basic info
    founded_year: Optional[int] = None
    location: str = ""
    employee_count: Optional[int] = None
    description: str = ""
    
    # Financial metrics
    revenue: Optional[float] = None
    arr: Optional[float] = None
    growth_rate: Optional[float] = None
    burn_rate: Optional[float] = None
    runway_months: Optional[int] = None
    gross_margin: Optional[float] = None
    
    # Market metrics
    tam: Optional[float] = None
    market_share: Optional[float] = None
    competitors: List[str] = field(default_factory=list)
    
    # Team metrics
    founder_names: List[str] = field(default_factory=list)
    cto_technical: bool = False
    repeat_founders: bool = False
    domain_expertise: Optional[int] = None
    
    # Product metrics
    nps: Optional[int] = None
    churn_rate: Optional[float] = None
    cac: Optional[float] = None
    ltv: Optional[float] = None
    payback_months: Optional[int] = None
    
    # Funding history
    total_raised: Optional[float] = None
    last_valuation: Optional[float] = None
    investors: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    data_sources: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "stage": self.stage.value if self.stage else None,
            "industry": self.industry.value if self.industry else None,
            "founded_year": self.founded_year,
            "location": self.location,
            "employee_count": self.employee_count,
            "description": self.description,
            "revenue": self.revenue,
            "arr": self.arr,
            "growth_rate": self.growth_rate,
            "burn_rate": self.burn_rate,
            "runway_months": self.runway_months,
            "gross_margin": self.gross_margin,
            "tam": self.tam,
            "market_share": self.market_share,
            "competitors": self.competitors,
            "founder_names": self.founder_names,
            "cto_technical": self.cto_technical,
            "repeat_founders": self.repeat_founders,
            "domain_expertise": self.domain_expertise,
            "nps": self.nps,
            "churn_rate": self.churn_rate,
            "cac": self.cac,
            "ltv": self.ltv,
            "payback_months": self.payback_months,
            "total_raised": self.total_raised,
            "last_valuation": self.last_valuation,
            "investors": self.investors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "data_sources": self.data_sources,
            "confidence_score": self.confidence_score
        }

@dataclass
class FundingRound:
    """Unified funding round data model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str = ""
    round_type: str = ""
    amount: float = 0
    pre_money_valuation: Optional[float] = None
    post_money_valuation: Optional[float] = None
    date: Optional[datetime] = None
    lead_investor: str = ""
    investors: List[str] = field(default_factory=list)
    security_type: Optional[SecurityType] = None
    
    # Terms
    liquidation_preference: float = 1.0
    participating: bool = False
    anti_dilution: str = "weighted_average"
    dividend_rate: Optional[float] = None
    
    # SAFE/Convertible specific
    cap: Optional[float] = None
    discount: Optional[float] = None
    interest_rate: Optional[float] = None
    maturity_date: Optional[datetime] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    data_sources: List[str] = field(default_factory=list)

@dataclass
class PortfolioCompany:
    """Portfolio company tracking model"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str = ""
    fund_id: str = ""
    investment_status: InvestmentStatus = InvestmentStatus.PIPELINE
    
    # Investment details
    initial_investment: Optional[float] = None
    ownership_percentage: Optional[float] = None
    board_seat: bool = False
    pro_rata_rights: bool = False
    follow_on_rights: Optional[float] = None
    
    # Performance tracking
    current_valuation: Optional[float] = None
    last_mark_date: Optional[datetime] = None
    unrealized_gain: Optional[float] = None
    realized_gain: Optional[float] = None
    
    # Monitoring
    last_board_meeting: Optional[datetime] = None
    next_milestone: str = ""
    risk_level: str = "medium"  # low, medium, high
    notes: str = ""
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class AgentInteraction:
    """Track all agent interactions for learning"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    user_id: str = ""
    agent_type: str = ""
    
    # Request details
    prompt: str = ""
    input_parameters: Dict[str, Any] = field(default_factory=dict)
    output_format: str = ""
    
    # Response details
    response: str = ""
    execution_time: float = 0
    tokens_used: int = 0
    success: bool = True
    error_message: str = ""
    
    # Context
    skills_used: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    companies_analyzed: List[str] = field(default_factory=list)
    
    # Feedback
    user_rating: Optional[int] = None  # 1-5
    user_feedback: str = ""
    
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class MarketData:
    """Market research and intelligence data"""
    industry: IndustryVertical
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Market sizing
    tam: Optional[float] = None
    sam: Optional[float] = None
    som: Optional[float] = None
    growth_rate: Optional[float] = None
    
    # Competitive landscape
    top_players: List[str] = field(default_factory=list)
    market_leaders: List[str] = field(default_factory=list)
    emerging_players: List[str] = field(default_factory=list)
    
    # Trends and insights
    trends: List[str] = field(default_factory=list)
    threats: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    
    # Investment activity
    total_investment: Optional[float] = None
    deal_count: Optional[int] = None
    avg_deal_size: Optional[float] = None
    top_investors: List[str] = field(default_factory=list)
    
    data_date: datetime = field(default_factory=datetime.utcnow)
    sources: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None

@dataclass
class InvestmentThesis:
    """Investment thesis and decision framework"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str = ""
    analyst_id: str = ""
    
    # Investment case
    thesis_summary: str = ""
    bull_case: List[str] = field(default_factory=list)
    bear_case: List[str] = field(default_factory=list)
    key_risks: List[str] = field(default_factory=list)
    
    # Scoring (1-10 scale)
    team_score: Optional[int] = None
    market_score: Optional[int] = None
    product_score: Optional[int] = None
    traction_score: Optional[int] = None
    financials_score: Optional[int] = None
    overall_score: Optional[int] = None
    
    # Recommendation
    recommendation: str = ""  # PASS, TRACK, DILIGENCE, INVEST
    target_ownership: Optional[float] = None
    max_valuation: Optional[float] = None
    follow_on_reserve: Optional[float] = None
    
    # Exit scenarios
    exit_scenarios: List[Dict[str, Any]] = field(default_factory=list)
    expected_return: Optional[float] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

# Helper functions for data validation and conversion
def validate_company_data(data: Dict[str, Any]) -> Company:
    """Validate and convert dictionary to Company object"""
    company = Company()
    
    # Safe conversions with validation
    if "name" in data and data["name"]:
        company.name = str(data["name"])
    
    if "stage" in data and data["stage"]:
        try:
            company.stage = CompanyStage(data["stage"])
        except ValueError:
            pass
    
    if "industry" in data and data["industry"]:
        try:
            company.industry = IndustryVertical(data["industry"])
        except ValueError:
            pass
    
    # Numeric fields with validation
    numeric_fields = [
        "founded_year", "employee_count", "revenue", "arr", 
        "growth_rate", "burn_rate", "runway_months", "gross_margin",
        "tam", "market_share", "nps", "churn_rate", "cac", "ltv",
        "payback_months", "total_raised", "last_valuation"
    ]
    
    for field in numeric_fields:
        if field in data and data[field] is not None:
            try:
                value = float(data[field])
                setattr(company, field, value)
            except (ValueError, TypeError):
                pass
    
    # List fields
    list_fields = ["competitors", "founder_names", "investors", "data_sources"]
    for field in list_fields:
        if field in data and isinstance(data[field], list):
            setattr(company, field, data[field])
    
    # Boolean fields
    bool_fields = ["cto_technical", "repeat_founders"]
    for field in bool_fields:
        if field in data:
            setattr(company, field, bool(data[field]))
    
    # String fields
    string_fields = ["domain", "location", "description"]
    for field in string_fields:
        if field in data and data[field]:
            setattr(company, field, str(data[field]))
    
    return company

def merge_company_data(existing: Company, new_data: Dict[str, Any]) -> Company:
    """Merge new data into existing company, preferring non-null values"""
    new_company = validate_company_data(new_data)
    
    # Create merged company
    merged = Company(**existing.__dict__)
    
    # Update non-null fields from new data
    for field_name, field_obj in new_company.__dataclass_fields__.items():
        new_value = getattr(new_company, field_name)
        
        # Skip default values
        if isinstance(new_value, list) and len(new_value) == 0:
            continue
        if new_value is None or new_value == "":
            continue
            
        # Update the field
        setattr(merged, field_name, new_value)
    
    # Update timestamp
    merged.updated_at = datetime.utcnow()
    
    return merged

# Export all models
__all__ = [
    'Company', 'FundingRound', 'PortfolioCompany', 'AgentInteraction',
    'MarketData', 'InvestmentThesis', 'CompanyStage', 'IndustryVertical',
    'InvestmentStatus', 'SecurityType', 'validate_company_data', 
    'merge_company_data'
]