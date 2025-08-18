"""
Full Flow No Comp - Document Processing Pipeline (Thread-Safe Version)
Text-based pipeline: PDF → OCR → Classification → Structured JSON
"""

import os
import sys
import time
import json
import base64
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
from dotenv import load_dotenv
import fitz  # PyMuPDF
import re
from dataclasses import dataclass
import threading
import shutil
import concurrent.futures
import uuid

# Optional imports with fallbacks
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    sys.stderr.write("Warning: yfinance not available. Financial data enhancement will be disabled.\n")
    YFINANCE_AVAILABLE = False
    yf = None

# Create a simple document classifier
class SizeBasedClassifier:
    """Simple document classifier based on file size and content"""
    
    def __init__(self):
        self.thresholds = {
            'monthly_update': (1, 15),      # 1-15 pages
            'board_deck': (10, 60),         # 10-60 pages  
            'transcript': (20, 300)         # 20-300 pages
        }
    
    def classify_document(self, pdf_content, filename="", extracted_text=""):
        """Classify document based on content length and filename"""
        try:
            # Simple classification based on text length
            text_length = len(extracted_text) if extracted_text else 0
            
            if text_length < 5000:
                return "monthly_update", {"confidence": "medium", "method": "text_length"}
            elif text_length < 50000:
                return "board_deck", {"confidence": "medium", "method": "text_length"}
            else:
                return "transcript", {"confidence": "medium", "method": "text_length"}
                
        except Exception as e:
            return "unknown", {"confidence": "low", "method": "fallback", "error": str(e)}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

@dataclass
class CompanyComparable:
    """Structure for comparable company data with financials"""
    name: str
    ticker: Optional[str]
    description: str
    industry: str
    market_cap: Optional[float]
    enterprise_value: Optional[float]
    revenue_ttm: Optional[float]
    ev_revenue_multiple: Optional[float]
    source: str
    relevance_score: float
    key_metrics: Dict[str, Any]
    financial_data_quality: str  # 'complete', 'partial', 'missing'

@dataclass
class MATransaction:
    """Structure for M&A transaction data"""
    target_company: str
    acquirer: str
    deal_value: Optional[float]
    deal_date: str
    industry: str
    description: str
    revenue_multiple: Optional[float]
    source: str
    relevance_score: float

class FullFlowNoCompPipeline:
    def __init__(self, temp_dir=None):
        """Initialize the full flow pipeline with thread safety"""
        # Load environment variables from the correct path
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
            logger.info(f"Loaded .env.local from {env_path}")
        else:
            # Try current directory
            if os.path.exists('.env.local'):
                load_dotenv('.env.local', override=True)
                logger.info("Loaded .env.local from current directory")
            else:
                logger.warning("No .env.local file found")
        
        # Initialize components
        self.classifier = SizeBasedClassifier()
        
        # Configuration
        self.supabase_project_ref = 'ijkatixkebddtkdvgkog'
        self.supabase_url = f'https://{self.supabase_project_ref}.supabase.co'
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        self.bucket_name = 'documents'
        # Claude configuration (primary)
        self.claude_api_key = os.getenv('CLAUDE_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        if not self.claude_api_key:
            logger.warning("CLAUDE_API_KEY not found in environment")
        self.claude_base_url = 'https://api.anthropic.com/v1'
        
        # OpenAI configuration (fallback)
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_base_url = 'https://api.openai.com/v1'
        
        self.tavily_api_key = os.getenv('TAVILY_API_KEY')
        
        # NEW: Thread-safe temp directory management
        if temp_dir:
            self.temp_dir = temp_dir
        else:
            thread_id = threading.current_thread().ident
            timestamp = int(time.time() * 1000)
            self.temp_dir = f"temp_thread_{thread_id}_{timestamp}"
        
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # NEW: Rate limiting for API calls
        self._last_claude_call = 0
        self._last_openai_call = 0
        self._last_tavily_call = 0
        self._api_lock = threading.Lock()
        
        # Validation
        self._validate_config()
        
        # Log to stderr to avoid interfering with JSON output
        sys.stderr.write(f"Initialized pipeline for thread {thread_id} with temp dir: {self.temp_dir}\n")
        
        # Extraction prompts for each document type
        self.extraction_prompts = {
            'monthly_update': """
Analyze this monthly update text and extract structured data. Focus on:

FINANCIAL METRICS:
- Monthly/quarterly revenue
- Burn rate (monthly cash burn)
- Runway (months of cash remaining)
- Cash balance
- ARR/MRR (Annual/Monthly Recurring Revenue)

OPERATIONAL METRICS:
- Headcount (total employees)
- New hires this month
- Customer count
- Churn rate
- CAC (Customer Acquisition Cost)
- LTV (Lifetime Value)

BUSINESS UPDATES:
- Key achievements this month
- Major challenges or setbacks
- Product launches or updates
- Partnership announcements

ENTITIES:
- Competitors mentioned
- Partners mentioned
- Industry terms and keywords

SECTOR CLASSIFICATION:
Classify the company into one of these specific sectors:
- AI (Artificial Intelligence, Machine Learning, Deep Learning)
- Adtech (Advertising Technology, Digital Advertising)
- Agtech (Agricultural Technology, Farming Tech)
- B2B Fintech (Business-to-Business Financial Technology)
- B2C (Business-to-Consumer)
- B2C Fintech (Consumer Financial Technology)
- Capital Markets (Trading, Investment, Securities)
- Climate Deep (Climate Technology, Carbon, Sustainability)
- Climate Software (Climate Software Solutions)
- Crypto (Cryptocurrency, Blockchain, DeFi, Web3)
- Cyber (Cybersecurity, Security Technology)
- Data Infrastructure (Data Platforms, Analytics, Warehousing)
- Deep (Deep Technology, Research, Scientific)
- Defense (Defense Technology, Military, Aerospace Defense)
- Dev Tool (Developer Tools, Software Development)
- E-com (E-commerce, Online Retail)
- Edtech (Education Technology, Learning Tech)
- Fintech B2B (Business Financial Technology)
- Fintech B2C (Consumer Financial Technology)
- GTM (Go-to-Market, Sales, Marketing)
- Gaming (Video Games, Gaming Platforms)
- Grocery Delivery (Food Delivery, Meal Delivery)
- HR (Human Resources, Recruitment, Talent)
- Health (Healthcare, Medical Technology)
- Insurtech (Insurance Technology)
- Legal (Legal Technology, Law Tech)
- Marketplace (Two-sided Platforms, Peer-to-Peer)
- Renewables (Renewable Energy, Clean Energy)
- SaaS (Software as a Service, Cloud Software)
- Space (Aerospace, Satellite Technology)
- Supply-Chain (Logistics, Warehouse, Distribution)
- Travel (Travel Technology, Tourism, Booking)

IMPORTANT: 
- All financial and operational metrics must be NUMERIC VALUES (numbers, not strings). Use null for missing values.
- CONVERT ALL CURRENCIES TO USD using current exchange rates (EUR to USD ≈ 1.08, GBP to USD ≈ 1.27)
- For burn_rate: Extract as a negative monthly cash flow amount. If presented as percentage of revenue, calculate the actual monthly burn amount by applying the percentage to the stated revenue figure.
- For percentages: Convert to decimal (e.g., 14% = 0.14)
- REASONING: When financial metrics are presented in non-standard formats, reason through what they mean in standard terms. For example, if burn rate is given as "X% of revenue", calculate the actual monthly cash outflow by applying that percentage to the stated revenue figure.

Respond ONLY with valid JSON. DO NOT include any comments (// or /* */) in the JSON. All explanatory text should go in separate fields, not as comments. Return ONLY pure JSON that can be parsed directly:
{
  "financial_metrics": {
    "revenue": 1000000,
    "burn_rate": -50000,
    "runway_months": 18,
    "cash_balance": 900000,
    "arr": 1200000,
    "mrr": 100000
  },
  "operational_metrics": {
    "headcount": 25,
    "new_hires": 3,
    "customer_count": 150,
    "churn_rate": 0.05,
    "cac": 5000,
    "ltv": 25000
  },
  "business_updates": {
    "achievements": [],
    "challenges": [],
    "product_updates": [],
    "partnerships": []
  },
  "extracted_entities": {
    "competitors_mentioned": [],
    "partners_mentioned": [],
    "industry_terms": []
  },
  "sector_classification": {
    "primary_sector": "SaaS",
    "confidence": "high/medium/low",
    "reasoning": "Brief explanation of sector classification"
  }
}
""",
            
            'board_deck': """
Extract the exact financial and operational data from this board meeting deck. Also classify the company sector.

SECTOR CLASSIFICATION:
Classify the company into one of these specific sectors:
- AI (Artificial Intelligence, Machine Learning, Deep Learning)
- Adtech (Advertising Technology, Digital Advertising)
- Agtech (Agricultural Technology, Farming Tech)
- B2B Fintech (Business-to-Business Financial Technology)
- B2C (Business-to-Consumer)
- B2C Fintech (Consumer Financial Technology)
- Capital Markets (Trading, Investment, Securities)
- Climate Deep (Climate Technology, Carbon, Sustainability)
- Climate Software (Climate Software Solutions)
- Crypto (Cryptocurrency, Blockchain, DeFi, Web3)
- Cyber (Cybersecurity, Security Technology)
- Data Infrastructure (Data Platforms, Analytics, Warehousing)
- Deep (Deep Technology, Research, Scientific)
- Defense (Defense Technology, Military, Aerospace Defense)
- Dev Tool (Developer Tools, Software Development)
- E-com (E-commerce, Online Retail)
- Edtech (Education Technology, Learning Tech)
- Fintech B2B (Business Financial Technology)
- Fintech B2C (Consumer Financial Technology)
- GTM (Go-to-Market, Sales, Marketing)
- Gaming (Video Games, Gaming Platforms)
- Grocery Delivery (Food Delivery, Meal Delivery)
- HR (Human Resources, Recruitment, Talent)
- Health (Healthcare, Medical Technology)
- Insurtech (Insurance Technology)
- Legal (Legal Technology, Law Tech)
- Marketplace (Two-sided Platforms, Peer-to-Peer)
- Renewables (Renewable Energy, Clean Energy)
- SaaS (Software as a Service, Cloud Software)
- Space (Aerospace, Satellite Technology)
- Supply-Chain (Logistics, Warehouse, Distribution)
- Travel (Travel Technology, Tourism, Booking)

IMPORTANT: 
- All financial metrics must be NUMERIC VALUES (numbers, not strings). Use null for missing values.
- CONVERT ALL CURRENCIES TO USD using current exchange rates (EUR to USD ≈ 1.08, GBP to USD ≈ 1.27)
- For burn_rate: Extract as a negative monthly cash flow amount (e.g., -50000 for monthly expenses of 50,000)
- For percentages: Convert to decimal (e.g., 14% = 0.14)
- DO NOT USE ANY COMMENTS IN JSON (no //, no /* */)
- Put any explanatory notes in a separate "notes" field if needed
- JSON must be directly parseable by JSON.parse() without any preprocessing

Output ONLY pure, valid JSON with the following structure:

{
  "company_info": {
    "company_name": "string",
    "meeting_date": "YYYY-MM-DD",
    "quarter": "string",
    "presentation_title": "string"
  },
  
  "runway_and_cash": {
    "cash_in_bank": 5000000,
    "as_of_date": "YYYY-MM-DD",
    "monthly_burn": {
      "current_month": -300000,
      "previous_month_1": -280000,
      "previous_month_2": -250000
    },
    "runway_months": 16,
    "runway_as_of": "string",
    "monthly_balance_history": [
      {
        "month": "string",
        "balance": 5000000
      }
    ]
  },
  
  "growth_metrics": {
    "current_arr": 2000000,
    "arr_growth_chart_data": [
      {
        "month": "string",
        "arr": 2000000
      }
    ],
    "customer_count": 100,
    "customer_growth_rate": 0.25
  },
  
  "sector_classification": {
    "primary_sector": "SaaS",
    "confidence": "high/medium/low",
    "reasoning": "Brief explanation of sector classification"
  }
}
""",
            
            'pitch_deck': """
Extract comprehensive data from this pitch deck including sector classification.

SECTOR CLASSIFICATION:
Classify the company into one of these specific sectors:
- AI (Artificial Intelligence, Machine Learning, Deep Learning)
- Adtech (Advertising Technology, Digital Advertising)
- Agtech (Agricultural Technology, Farming Tech)
- B2B Fintech (Business-to-Business Financial Technology)
- B2C (Business-to-Consumer)
- B2C Fintech (Consumer Financial Technology)
- Capital Markets (Trading, Investment, Securities)
- Climate Deep (Climate Technology, Carbon, Sustainability)
- Climate Software (Climate Software Solutions)
- Crypto (Cryptocurrency, Blockchain, DeFi, Web3)
- Cyber (Cybersecurity, Security Technology)
- Data Infrastructure (Data Platforms, Analytics, Warehousing)
- Deep (Deep Technology, Research, Scientific)
- Defense (Defense Technology, Military, Aerospace Defense)
- Dev Tool (Developer Tools, Software Development)
- E-com (E-commerce, Online Retail)
- Edtech (Education Technology, Learning Tech)
- Fintech B2B (Business Financial Technology)
- Fintech B2C (Consumer Financial Technology)
- GTM (Go-to-Market, Sales, Marketing)
- Gaming (Video Games, Gaming Platforms)
- Grocery Delivery (Food Delivery, Meal Delivery)
- HR (Human Resources, Recruitment, Talent)
- Health (Healthcare, Medical Technology)
- Insurtech (Insurance Technology)
- Legal (Legal Technology, Law Tech)
- Marketplace (Two-sided Platforms, Peer-to-Peer)
- Renewables (Renewable Energy, Clean Energy)
- SaaS (Software as a Service, Cloud Software)
- Space (Aerospace, Satellite Technology)
- Supply-Chain (Logistics, Warehouse, Distribution)
- Travel (Travel Technology, Tourism, Booking)

IMPORTANT: All financial metrics must be NUMERIC VALUES (numbers, not strings). Use null for missing values.

Return JSON with this structure:

{
  "company_overview": {
    "company_name": "string",
    "description": "string",
    "industry": "string",
    "business_model": "string",
    "target_market": "string"
  },
  
  "financial_projections": {
    "current_revenue": 500000,
    "projected_revenue_12m": 2000000,
    "projected_revenue_24m": 5000000,
    "burn_rate": -100000,
    "runway_months": 18
  },
  
  "market_analysis": {
    "total_addressable_market": 10000000000,
    "serviceable_market": 1000000000,
    "market_growth_rate": 0.15
  },
  
  "competitive_landscape": {
    "competitors": ["array of competitor names"],
    "competitive_advantages": ["array of advantages"]
  },
  
  "sector_classification": {
    "primary_sector": "SaaS",
    "confidence": "high/medium/low",
    "reasoning": "Brief explanation of sector classification"
  }
}
""",
            
            'financial_model': """
Extract financial model data and sector classification.

SECTOR CLASSIFICATION:
Classify the company into one of these specific sectors:
- AI (Artificial Intelligence, Machine Learning, Deep Learning)
- Adtech (Advertising Technology, Digital Advertising)
- Agtech (Agricultural Technology, Farming Tech)
- B2B Fintech (Business-to-Business Financial Technology)
- B2C (Business-to-Consumer)
- B2C Fintech (Consumer Financial Technology)
- Capital Markets (Trading, Investment, Securities)
- Climate Deep (Climate Technology, Carbon, Sustainability)
- Climate Software (Climate Software Solutions)
- Crypto (Cryptocurrency, Blockchain, DeFi, Web3)
- Cyber (Cybersecurity, Security Technology)
- Data Infrastructure (Data Platforms, Analytics, Warehousing)
- Deep (Deep Technology, Research, Scientific)
- Defense (Defense Technology, Military, Aerospace Defense)
- Dev Tool (Developer Tools, Software Development)
- E-com (E-commerce, Online Retail)
- Edtech (Education Technology, Learning Tech)
- Fintech B2B (Business Financial Technology)
- Fintech B2C (Consumer Financial Technology)
- GTM (Go-to-Market, Sales, Marketing)
- Gaming (Video Games, Gaming Platforms)
- Grocery Delivery (Food Delivery, Meal Delivery)
- HR (Human Resources, Recruitment, Talent)
- Health (Healthcare, Medical Technology)
- Insurtech (Insurance Technology)
- Legal (Legal Technology, Law Tech)
- Marketplace (Two-sided Platforms, Peer-to-Peer)
- Renewables (Renewable Energy, Clean Energy)
- SaaS (Software as a Service, Cloud Software)
- Space (Aerospace, Satellite Technology)
- Supply-Chain (Logistics, Warehouse, Distribution)
- Travel (Travel Technology, Tourism, Booking)

IMPORTANT: All financial metrics must be NUMERIC VALUES (numbers, not strings). Use null for missing values.

Return JSON with this structure:

{
  "financial_projections": {
    "revenue_forecast": [
      {
        "period": "string",
        "revenue": 1000000
      }
    ],
    "expense_breakdown": {
      "personnel": 300000,
      "marketing": 100000,
      "operations": 50000,
      "other": 25000
    },
    "key_metrics": {
      "gross_margin": 0.75,
      "net_margin": 0.25,
      "customer_acquisition_cost": 5000,
      "lifetime_value": 25000
    }
  },
  
  "sector_classification": {
    "primary_sector": "SaaS",
    "confidence": "high/medium/low",
    "reasoning": "Brief explanation of sector classification"
  }
}
""",
            
            'other': """
Extract any relevant business information and classify the sector.

SECTOR CLASSIFICATION:
Classify the company into one of these specific sectors:
- AI (Artificial Intelligence, Machine Learning, Deep Learning)
- Adtech (Advertising Technology, Digital Advertising)
- Agtech (Agricultural Technology, Farming Tech)
- B2B Fintech (Business-to-Business Financial Technology)
- B2C (Business-to-Consumer)
- B2C Fintech (Consumer Financial Technology)
- Capital Markets (Trading, Investment, Securities)
- Climate Deep (Climate Technology, Carbon, Sustainability)
- Climate Software (Climate Software Solutions)
- Crypto (Cryptocurrency, Blockchain, DeFi, Web3)
- Cyber (Cybersecurity, Security Technology)
- Data Infrastructure (Data Platforms, Analytics, Warehousing)
- Deep (Deep Technology, Research, Scientific)
- Defense (Defense Technology, Military, Aerospace Defense)
- Dev Tool (Developer Tools, Software Development)
- E-com (E-commerce, Online Retail)
- Edtech (Education Technology, Learning Tech)
- Fintech B2B (Business Financial Technology)
- Fintech B2C (Consumer Financial Technology)
- GTM (Go-to-Market, Sales, Marketing)
- Gaming (Video Games, Gaming Platforms)
- Grocery Delivery (Food Delivery, Meal Delivery)
- HR (Human Resources, Recruitment, Talent)
- Health (Healthcare, Medical Technology)
- Insurtech (Insurance Technology)
- Legal (Legal Technology, Law Tech)
- Marketplace (Two-sided Platforms, Peer-to-Peer)
- Renewables (Renewable Energy, Clean Energy)
- SaaS (Software as a Service, Cloud Software)
- Space (Aerospace, Satellite Technology)
- Supply-Chain (Logistics, Warehouse, Distribution)
- Travel (Travel Technology, Tourism, Booking)

Return JSON with this structure:

{
  "extracted_entities": {
    "competitors_mentioned": [],
    "partners_mentioned": [],
    "industry_terms": []
  },
  
  "business_updates": {
    "achievements": [],
    "challenges": [],
    "product_updates": [],
    "partnerships": []
  },
  
  "sector_classification": {
    "primary_sector": "SaaS",
    "confidence": "high/medium/low",
    "reasoning": "Brief explanation of sector classification"
  }
}
"""
        }
        
        # Issue analysis prompts
        self.issue_analysis_prompts = {
            'monthly_update': """
Analyze this monthly update for potential red flags and concerning patterns.

ANALYZE FOR:
- Missing key metrics that should be reported
- Euphemistic language hiding bad news
- Concerning trends in growth/burn/runway
- Signs of operational challenges
- Overly positive language masking problems
- Defensive or evasive language

RED FLAGS TO IDENTIFY:
- Cash flow concerns
- Growth slowdown indicators
- Team/hiring issues
- Customer satisfaction problems

Respond ONLY with valid JSON:
{
  "red_flags": [],
  "missing_metrics": [],
  "language_concerns": [],
  "business_concerns": [],
  "overall_sentiment": "positive/neutral/negative",
  "confidence_level": "high/medium/low",
  "key_concerns": []
}
""",
            
            'board_deck': """
Analyze this board presentation for strategic concerns and unrealistic assumptions.

ANALYZE FOR:
- Unrealistic market size claims
- Weak competitive analysis
- Missing risk assessment
- Overly optimistic projections
- Unsupported revenue projections
- Unclear unit economics

STRATEGIC CONCERNS:
- Narrow competitive view
- Outdated market data
- Wishful thinking about market timing
- Underestimated competition

Respond ONLY with valid JSON:
{
  "strategic_concerns": [],
  "financial_red_flags": [],
  "market_analysis_issues": [],
  "projection_realism": "realistic/optimistic/unrealistic",
  "overall_assessment": "strong/moderate/weak",
  "key_risks_missing": [],
  "competitive_analysis_quality": "strong/moderate/weak"
}
""",
            
            'transcript': """
Analyze this earnings call transcript for management sentiment and concerning signals.

ANALYZE FOR:
- Management confidence level in guidance
- Defensive language patterns
- Avoided or deflected questions
- Lowered expectations
- Mentioned challenges or headwinds
- Competitive pressure indicators

SENTIMENT ANALYSIS:
- Management tone and confidence
- Forward-looking optimism/pessimism
- Response patterns to difficult questions

Respond ONLY with valid JSON:
{
  "management_sentiment": "confident/cautious/defensive",
  "avoided_topics": [],
  "concerning_signals": [],
  "guidance_tone": "optimistic/realistic/conservative",
  "competitive_pressures": [],
  "overall_business_health": "strong/stable/concerning",
  "confidence_indicators": [],
  "defensive_language_examples": []
}
"""
        }

    def _rate_limited_claude_call(self, api_func, *args, min_delay=2, **kwargs):
        """Rate-limited Claude API calls - OPTIMIZED for speed"""
        with self._api_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_claude_call
            
            if time_since_last < min_delay:
                sleep_time = min_delay - time_since_last
                sys.stderr.write(f"Rate limiting Claude: waiting {sleep_time:.1f} seconds...\n")
                time.sleep(sleep_time)
            
            try:
                result = api_func(*args, **kwargs)
                self._last_claude_call = time.time()
                return result
            except Exception as e:
                sys.stderr.write(f"Claude API error: {e}\n")
                # Faster retry
                time.sleep(3)
                result = api_func(*args, **kwargs)
                self._last_claude_call = time.time()
                return result

    def _rate_limited_openai_call(self, api_func, *args, min_delay=3, **kwargs):
        """Rate-limited OpenAI API calls - OPTIMIZED for speed"""
        with self._api_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_openai_call
            
            if time_since_last < min_delay:
                sleep_time = min_delay - time_since_last
                sys.stderr.write(f"Rate limiting OpenAI: waiting {sleep_time:.1f} seconds...\n")
                time.sleep(sleep_time)
            
            try:
                result = api_func(*args, **kwargs)
                self._last_openai_call = time.time()
                return result
            except Exception as e:
                sys.stderr.write(f"OpenAI API error: {e}\n")
                # Faster retry
                time.sleep(5)
                result = api_func(*args, **kwargs)
                self._last_openai_call = time.time()
                return result

    def _rate_limited_tavily_call(self, query, min_delay=2):
        """Rate-limited Tavily API calls - OPTIMIZED for speed"""
        with self._api_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_tavily_call
            
            if time_since_last < min_delay:
                sleep_time = min_delay - time_since_last
                sys.stderr.write(f"Rate limiting Tavily: waiting {sleep_time:.1f} seconds...\n")
                time.sleep(sleep_time)
            
            try:
                result = self.tavily_search(query)
                self._last_tavily_call = time.time()
                return result
            except Exception as e:
                sys.stderr.write(f"Tavily API error: {e}\n")
                # Faster retry
                time.sleep(3)
                result = self.tavily_search(query)
                self._last_tavily_call = time.time()
                return result

    def _get_thread_safe_temp_file(self, prefix="temp", suffix=".txt"):
        """Generate unique temp file path for this thread"""
        thread_id = threading.current_thread().ident
        timestamp = int(time.time() * 1000)
        filename = f"{prefix}_{thread_id}_{timestamp}{suffix}"
        return os.path.join(self.temp_dir, filename)

    def cleanup(self):
        """Clean up thread-specific temporary files"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                sys.stderr.write(f"Cleaned up temp directory: {self.temp_dir}\n")
        except Exception as e:
            sys.stderr.write(f"Error cleaning up temp directory: {e}\n")
    
    def _validate_config(self):
        """Validate configuration"""
        if not self.supabase_service_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is required")
        if not self.claude_api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is required")
        if not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY environment variable is required")
        logger.info("Configuration validated successfully")
    
    def get_supabase_headers(self) -> Dict[str, str]:
        """Get headers for Supabase API requests"""
        return {
            'apikey': self.supabase_service_key,
            'Authorization': f'Bearer {self.supabase_service_key}',
            'Content-Type': 'application/json'
        }
    
    def list_storage_files(self) -> List[Dict[str, Any]]:
        """List all files in Supabase storage"""
        try:
            url = f'{self.supabase_url}/storage/v1/object/list/{self.bucket_name}'
            payload = {'limit': 1000, 'prefix': '', 'search': ''}
            
            response = requests.post(url, json=payload, headers=self.get_supabase_headers())
            response.raise_for_status()
            
            files = response.json()
            logger.info(f"Found {len(files)} total files in storage")
            return files
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list storage files: {e}")
            raise
    
    def get_processed_files(self) -> set:
        """Get list of already processed files"""
        try:
            # Try Supabase first
            url = f'{self.supabase_url}/rest/v1/processed_documents?select=storage_path'
            response = requests.get(url, headers=self.get_supabase_headers())
            
            if response.status_code == 200:
                processed_paths = {item['storage_path'] for item in response.json()}
                logger.info(f"Found {len(processed_paths)} processed files in Supabase")
                return processed_paths
            else:
                logger.warning(f"Supabase processed_documents table not found (status: {response.status_code}). Using local tracking.")
                return self.get_local_processed_files()
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not fetch processed files from Supabase: {e}. Using local tracking.")
            return self.get_local_processed_files()
    
    def get_local_processed_files(self) -> set:
        """Get processed files from local file"""
        try:
            processed_file = 'processed_files.txt'
            if os.path.exists(processed_file):
                with open(processed_file, 'r') as f:
                    processed_files = {line.strip() for line in f if line.strip()}
                logger.info(f"Found {len(processed_files)} processed files locally: {processed_files}")
                return processed_files
            else:
                logger.info("No local processed files found")
                return set()
        except Exception as e:
            logger.error(f"Error reading local processed files: {e}")
            return set()
    
    def mark_as_processed_local(self, storage_path: str):
        """Mark file as processed locally"""
        try:
            processed_file = 'processed_files.txt'
            with open(processed_file, 'a') as f:
                f.write(f"{storage_path}\n")
            logger.info(f"Marked {storage_path} as processed locally")
        except Exception as e:
            logger.error(f"Failed to mark as processed locally: {e}")
    
    def get_next_unprocessed_pdf(self) -> Optional[Dict[str, Any]]:
        """Get next unprocessed PDF file"""
        try:
            processed_paths = self.get_processed_files()
            all_files = self.list_storage_files()
            
            unprocessed_pdfs = []
            for file in all_files:
                storage_path = f"{self.bucket_name}/{file['name']}"
                
                if (file['name'].lower().endswith('.pdf') and 
                    storage_path not in processed_paths and
                    not file['name'].startswith('.')):
                    unprocessed_pdfs.append(file)
            
            if not unprocessed_pdfs:
                return None
            
            unprocessed_pdfs.sort(key=lambda x: x.get('created_at', ''))
            selected_file = unprocessed_pdfs[0]
            logger.info(f"Selected file for processing: {selected_file['name']}")
            
            return selected_file
            
        except Exception as e:
            logger.error(f"Error getting next unprocessed PDF: {e}")
            raise
    
    def download_file(self, file_name: str) -> bytes:
        """Download file from Supabase storage"""
        try:
            # Handle file names with spaces - use the file_name directly without URL encoding
            url = f'{self.supabase_url}/storage/v1/object/{self.bucket_name}/{file_name}'
            headers = {
                'apikey': self.supabase_service_key,
                'Authorization': f'Bearer {self.supabase_service_key}'
            }
            
            logger.info(f"Downloading from URL: {url}")
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            
            logger.info(f"Downloaded file: {file_name} ({len(response.content)} bytes)")
            return response.content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download file: {e}")
            # Try alternative approach - list files and find the exact match
            try:
                logger.info("Trying alternative download approach...")
                files = self.list_storage_files()
                for file_info in files:
                    if file_info['name'] == file_name:
                        # Use the exact path from the file listing
                        exact_path = file_info['id']  # This should be the correct path
                        url = f'{self.supabase_url}/storage/v1/object/{self.bucket_name}/{exact_path}'
                        logger.info(f"Trying exact path: {url}")
                        response = requests.get(url, headers=headers, timeout=60)
                        response.raise_for_status()
                        logger.info(f"Downloaded file using exact path: {file_name} ({len(response.content)} bytes)")
                        return response.content
            except Exception as alt_e:
                logger.error(f"Alternative download also failed: {alt_e}")
            
            raise
    
    def download_file_from_storage_path(self, storage_path: str) -> bytes:
        """Download file from Supabase storage using full storage path"""
        try:
            # Try direct download first
            url = f'{self.supabase_url}/storage/v1/object/{self.bucket_name}/{storage_path}'
            headers = {
                'apikey': self.supabase_service_key,
                'Authorization': f'Bearer {self.supabase_service_key}'
            }
            
            logger.info(f"Downloading from storage path URL: {url}")
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            
            logger.info(f"Downloaded file from storage path: {storage_path} ({len(response.content)} bytes)")
            return response.content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download file from storage path: {e}")
            # Try alternative approach - list files and find the exact match
            try:
                logger.info("Trying alternative download approach - listing files...")
                files = self.list_storage_files()
                target_filename = os.path.basename(storage_path)
                
                for file_info in files:
                    if file_info['name'] == target_filename:
                        # Use the exact path from the file listing
                        exact_path = file_info['id']  # This should be the correct path
                        url = f'{self.supabase_url}/storage/v1/object/{self.bucket_name}/{exact_path}'
                        logger.info(f"Trying exact path from file listing: {url}")
                        response = requests.get(url, headers=headers, timeout=60)
                        response.raise_for_status()
                        logger.info(f"Downloaded file using exact path: {storage_path} ({len(response.content)} bytes)")
                        return response.content
                        
                logger.error(f"File not found in storage listing: {target_filename}")
                raise Exception(f"File not found in storage: {storage_path}")
                
            except Exception as alt_e:
                logger.error(f"Alternative download also failed: {alt_e}")
                raise
    
    def extract_text_from_pdf(self, pdf_bytes: bytes, doc_type: str, filename: str) -> str:
        """Extract text from PDF - use local extraction for text docs, vision for board decks"""
        try:
            if doc_type in ['monthly_update', 'transcript']:
                # Text-based documents - use fast local extraction
                logger.info(f"Using local text extraction for {doc_type}")
                return self.extract_text_locally(pdf_bytes, filename)
            else:
                # Board decks - use OpenAI vision for slides/charts/images
                logger.info(f"Using OpenAI vision for {doc_type}")
                return self.extract_text_with_vision(pdf_bytes, filename)
                
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise
    
    def extract_text_locally(self, pdf_bytes: bytes, filename: str) -> str:
        """Extract text locally from text-based PDFs (fast, no API calls)"""
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            all_content = []
            all_content.append(f"# Document: {filename}\n")
            all_content.append(f"Processed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Extract text directly from PDF
                page_text = page.get_text()
                
                if page_text.strip():  # Only add non-empty pages
                    all_content.append(f"## Page {page_num + 1}\n\n")
                    all_content.append(page_text)
                    all_content.append("\n\n---\n\n")
                else:
                    logger.warning(f"Page {page_num + 1} has no extractable text")
            
            pdf_document.close()
            
            final_content = "".join(all_content)
            logger.info(f"Local text extraction completed. Total content: {len(final_content)} characters")
            
            # If very little text was extracted, it might be a scanned document
            if len(final_content) < 500:
                logger.warning("Very little text extracted - document might be scanned. Consider using vision extraction.")
            
            return final_content
            
        except Exception as e:
            logger.error(f"Local text extraction failed: {e}")
            raise
    
    def extract_text_with_vision(self, pdf_bytes: bytes, filename: str) -> str:
        """Extract text from visual PDFs using OpenAI vision (for board decks)"""
        try:
            # Convert PDF to images
            images = self.pdf_to_images(pdf_bytes)
            
            # Process each page individually (your working approach)
            all_content = []
            all_content.append(f"# Document: {filename}\n")
            all_content.append(f"Processed on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for i, image_bytes in enumerate(images):
                logger.info(f"Processing page {i + 1}/{len(images)} with Claude vision...")
                
                page_content = self.process_image_with_openai(image_bytes, i + 1)  # Now uses Claude internally
                
                all_content.append(f"## Page {i + 1}\n\n")
                all_content.append(page_content)
                all_content.append("\n\n---\n\n")
                
                # Add delay to respect API rate limits
                time.sleep(1)
            
            final_content = "".join(all_content)
            logger.info(f"Vision extraction completed. Total content: {len(final_content)} characters")
            return final_content
            
        except Exception as e:
            logger.error(f"Vision extraction failed: {e}")
            raise
    
    def pdf_to_images(self, pdf_bytes: bytes) -> List[bytes]:
        """Convert PDF pages to images using PyMuPDF"""
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            images = []
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Convert page to image (PNG)
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                images.append(img_data)
                
                logger.info(f"Converted page {page_num + 1} to image ({len(img_data)} bytes)")
            
            pdf_document.close()
            logger.info(f"Converted PDF to {len(images)} images")
            return images
            
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise
    
    def process_image_with_openai(self, image_bytes: bytes, page_number: int) -> str:
        """Process a single image with Claude Vision API (renamed but using Claude)"""
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            def _make_vision_call():
                # Use Claude instead of OpenAI
                url = f'{self.claude_base_url}/messages'
                headers = {
                    'x-api-key': self.claude_api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                }
                
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 4000,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": """Extract all text from this document page. Preserve the formatting, structure, and layout as much as possible. 
                                    
Include:
- All text content
- Table structures (use markdown table format)
- Headers and subheaders
- Lists and bullet points
- Any important visual elements or charts (describe them)

Format the output as clean markdown."""
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": base64_image
                                    }
                                }
                            ]
                        }
                    ]
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                return result['content'][0]['text']
            
            # Use rate-limited call for Claude
            content = self._rate_limited_claude_call(_make_vision_call)
            
            logger.info(f"Processed page {page_number} with Claude Vision ({len(content)} characters)")
            return content
            
        except Exception as e:
            logger.error(f"Failed to process image with Claude: {e}")
            raise
    
    def classify_document(self, pdf_content: bytes, extracted_text: str, filename: str) -> Tuple[str, Dict]:
        """Classify document using size + content"""
        try:
            doc_type, details = self.classifier.classify_document(
                pdf_content, 
                filename=filename, 
                extracted_text=extracted_text
            )
            logger.info(f"Document classified as: {doc_type} (confidence: {details.get('confidence', 'unknown')})")
            return doc_type, details
            
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return 'unknown', {'error': str(e)}
    
    def call_claude_text_only(self, prompt: str, max_tokens: int = 4000) -> str:
        """Call Claude with text-only prompt (rate-limited)"""
        try:
            def _make_claude_call():
                url = f'{self.claude_base_url}/messages'
                headers = {
                    'x-api-key': self.claude_api_key,
                    'Content-Type': 'application/json',
                    'anthropic-version': '2023-06-01'
                }
                
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=120)
                
                if response.status_code == 401:
                    raise Exception("Invalid Claude API key. Please check CLAUDE_API_KEY in .env.local")
                elif response.status_code == 429:
                    raise Exception("Claude API rate limit exceeded. Please wait and try again.")
                elif response.status_code != 200:
                    raise Exception(f"Claude API error: {response.status_code} - {response.text[:200]}")
                
                result = response.json()
                if 'content' not in result or not result['content']:
                    raise Exception("Invalid response from Claude API")
                    
                return result['content'][0]['text']
            
            # Use rate-limited call
            content_result = self._rate_limited_claude_call(_make_claude_call)
            return content_result
            
        except Exception as e:
            logger.error(f"Claude text processing failed: {e}")
            raise

    def call_openai_text_only(self, prompt: str, max_tokens: int = 4000) -> str:
        """Call OpenAI with text-only prompt (rate-limited)"""
        try:
            def _make_text_call():
                url = f'{self.openai_base_url}/chat/completions'
                headers = {
                    'Authorization': f'Bearer {self.openai_api_key}',
                    'Content-Type': 'application/json'
                }
                
                payload = {
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.1
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=120)
                response.raise_for_status()
                
                result = response.json()
                return result['choices'][0]['message']['content']
            
            # Use rate-limited call
            content_result = self._rate_limited_openai_call(_make_text_call)
            return content_result
            
        except Exception as e:
            logger.error(f"Claude text processing failed: {e}")
            raise
    
    def extract_structured_data(self, extracted_text: str, doc_type: str) -> Dict:
        """Extract structured data based on document type"""
        try:
            prompt = self.extraction_prompts.get(doc_type, self.extraction_prompts['monthly_update'])
            full_prompt = f"{prompt}\n\nDocument text to analyze:\n{extracted_text}"
            
            logger.info(f"Extracting structured data for {doc_type}")
            raw_response = self.call_claude_text_only(full_prompt)
            
            # Try to parse JSON from response
            try:
                # Clean the response and extract JSON
                cleaned_response = raw_response.strip()
                
                # Look for JSON block
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    extracted_data = json.loads(json_str)
                else:
                    # Try parsing the whole response
                    extracted_data = json.loads(cleaned_response)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed: {e}")
                # Fallback: return raw response with error info
                extracted_data = {
                    "parsing_error": str(e),
                    "raw_extraction": raw_response,
                    "extracted_entities": {
                        "competitors_mentioned": [],
                        "partners_mentioned": [],
                        "industry_terms": []
                    }
                }
            
            # Clean financial data to ensure numeric values
            extracted_data = self._clean_financial_data(extracted_data)
            
            logger.info("Structured data extraction completed")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Data extraction failed: {e}")
            # Return empty but valid structure
            return {
                "financial_metrics": {
                    "revenue": None,
                    "burn_rate": None,
                    "runway_months": None,
                    "cash_balance": None,
                    "arr": None,
                    "mrr": None
                },
                "operational_metrics": {
                    "headcount": None,
                    "new_hires": None,
                    "customer_count": None,
                    "churn_rate": None,
                    "cac": None,
                    "ltv": None
                },
                "business_updates": {
                    "achievements": [],
                    "challenges": [],
                    "product_updates": [],
                    "partnerships": []
                },
                "extracted_entities": {
                    "competitors_mentioned": [],
                    "partners_mentioned": [],
                    "industry_terms": []
                },
                "sector": "SaaS",
                "extraction_error": str(e)[:200]
            }
    
    # ============================================================================
    # COMPARABLES SEARCH ENGINE - LLM Native Web Search
    # ============================================================================
    
    def tavily_search(self, query: str, search_depth: str = "basic", max_results: int = 5) -> Dict:
        """Perform search using Tavily API - OPTIMIZED for speed"""
        try:
            url = "https://api.tavily.com/search"
            
            payload = {
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": search_depth,  # Use 'basic' for speed
                "include_answer": False,  # Disable for speed
                "include_images": False,
                "include_raw_content": False,
                "max_results": max_results  # Reduced for speed
            }
            
            response = requests.post(url, json=payload, timeout=10)  # Reduced timeout for speed
            response.raise_for_status()
            
            results = response.json()
            logger.info(f"Tavily search completed: {query} ({len(results.get('results', []))} results)")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Tavily search failed: {e}")
            raise
    
    def find_comparable_companies(self, company_description: str, industry: str, 
                                business_model: str = "") -> List[CompanyComparable]:
        """Find comparable public companies using intelligent sector-specific search"""
        try:
            # Use the sector (industry) for targeted search
            sector = industry  # This is now the classified sector
            
            # Intelligent sector-specific search strategies
            search_strategies = self._get_sector_search_strategies(sector, company_description, business_model)
            
            all_comparables = []
            
            for strategy_name, query in search_strategies.items():
                logger.info(f"Searching for comparables using strategy '{strategy_name}': {query}")
                
                # Search with Tavily (rate-limited)
                search_results = self._rate_limited_tavily_call(query)
                
                # Analyze with sector-specific prompt
                comparables_prompt = self._get_sector_comparables_prompt(sector, strategy_name, search_results)
                
                analysis = self.analyze_search_results(comparables_prompt, search_results)
                
                # Parse and add to results
                try:
                    parsed_results = self._parse_json_response(analysis)
                    companies_data = parsed_results.get('companies', [])
                    
                    for company in companies_data:
                        relevance_score = float(company.get('relevance_score', 0))
                        if relevance_score >= 7.0:  # Stricter filtering
                            comparable = CompanyComparable(
                                name=company.get('name', ''),
                                ticker=company.get('ticker'),
                                description=company.get('description', ''),
                                industry=company.get('industry', sector),
                                market_cap=company.get('market_cap'),
                                enterprise_value=None,
                                revenue_ttm=None,
                                ev_revenue_multiple=None,
                                source=f"tavily_search_{sector}_{strategy_name}",
                                relevance_score=relevance_score,
                                key_metrics=company.get('key_metrics', {}),
                                financial_data_quality='pending'
                            )
                            all_comparables.append(comparable)
                            
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse comparables analysis for {strategy_name}: {e}")
                    continue
            
            # Remove duplicates and sort by relevance
            unique_comparables = self._deduplicate_comparables(all_comparables)
            unique_comparables.sort(key=lambda x: x.relevance_score, reverse=True)
            
            logger.info(f"Found {len(unique_comparables)} unique comparable companies in {sector} sector")
            return unique_comparables
            
        except Exception as e:
            logger.error(f"Comparable search failed: {e}")
            return []
    
    def _get_sector_search_strategies(self, sector: str, company_description: str, business_model: str) -> Dict[str, str]:
        """Generate intelligent search strategies based on sector"""
        
        strategies = {}
        
        # Sector-specific search strategies
        if sector == 'E-com':
            strategies = {
                'retail_platforms': f"public companies e-commerce retail platform stock market traded similar to {company_description}",
                'online_retail': f"public companies online retail ecommerce stock market traded business model {business_model}",
                'retail_tech': f"public companies retail technology software stock market traded comparable",
                'digital_commerce': f"public companies digital commerce platform stock market traded similar business"
            }
        elif sector == 'SaaS':
            strategies = {
                'enterprise_saas': f"public companies enterprise SaaS software stock market traded similar to {company_description}",
                'business_software': f"public companies business software platform stock market traded {business_model}",
                'cloud_software': f"public companies cloud software SaaS stock market traded comparable",
                'workflow_software': f"public companies workflow management software stock market traded similar"
            }
        elif sector == 'B2B Fintech':
            strategies = {
                'enterprise_fintech': f"public companies enterprise fintech B2B financial stock market traded similar to {company_description}",
                'corporate_payments': f"public companies corporate payments B2B stock market traded {business_model}",
                'business_financial': f"public companies business financial services stock market traded comparable",
                'enterprise_financial': f"public companies enterprise financial technology stock market traded similar"
            }
        elif sector == 'B2C Fintech':
            strategies = {
                'consumer_fintech': f"public companies consumer fintech B2C financial stock market traded similar to {company_description}",
                'personal_finance': f"public companies personal finance consumer stock market traded {business_model}",
                'consumer_payments': f"public companies consumer payments fintech stock market traded comparable",
                'digital_banking': f"public companies digital banking consumer stock market traded similar"
            }
        elif sector == 'Health':
            strategies = {
                'healthcare_software': f"public companies healthcare software medical stock market traded similar to {company_description}",
                'digital_health': f"public companies digital health technology stock market traded {business_model}",
                'medical_software': f"public companies medical software healthcare stock market traded comparable",
                'health_tech': f"public companies health technology platform stock market traded similar"
            }
        elif sector == 'Edtech':
            strategies = {
                'education_software': f"public companies education software learning stock market traded similar to {company_description}",
                'online_learning': f"public companies online learning education stock market traded {business_model}",
                'educational_tech': f"public companies educational technology stock market traded comparable",
                'learning_platform': f"public companies learning platform education stock market traded similar"
            }
        elif sector == 'Cyber':
            strategies = {
                'cybersecurity': f"public companies cybersecurity security stock market traded similar to {company_description}",
                'security_software': f"public companies security software cyber stock market traded {business_model}",
                'cyber_tech': f"public companies cyber technology security stock market traded comparable",
                'threat_detection': f"public companies threat detection security stock market traded similar"
            }
        elif sector == 'Adtech':
            strategies = {
                'advertising_tech': f"public companies advertising technology adtech stock market traded similar to {company_description}",
                'digital_advertising': f"public companies digital advertising platform stock market traded {business_model}",
                'marketing_tech': f"public companies marketing technology stock market traded comparable",
                'ad_platform': f"public companies advertising platform stock market traded similar"
            }
        elif sector == 'Marketplace':
            strategies = {
                'marketplace_platforms': f"public companies marketplace platform stock market traded similar to {company_description}",
                'two_sided_platforms': f"public companies two-sided platform marketplace stock market traded {business_model}",
                'peer_to_peer': f"public companies peer to peer marketplace stock market traded comparable",
                'platform_economy': f"public companies platform economy marketplace stock market traded similar"
            }
        elif sector == 'AI':
            strategies = {
                'ai_platforms': f"public companies artificial intelligence AI platform stock market traded similar to {company_description}",
                'machine_learning': f"public companies machine learning AI stock market traded {business_model}",
                'ai_software': f"public companies AI software artificial intelligence stock market traded comparable",
                'ai_technology': f"public companies AI technology platform stock market traded similar"
            }
        elif sector == 'Defense':
            strategies = {
                'defense_contractors': f"public companies defense contractors military aerospace stock market traded similar to {company_description}",
                'defense_technology': f"public companies defense technology military systems stock market traded {business_model}",
                'aerospace_defense': f"public companies aerospace defense military stock market traded comparable",
                'defense_software': f"public companies defense software military technology stock market traded similar"
            }
        elif sector == 'Data Infrastructure':
            strategies = {
                'data_platforms': f"public companies data infrastructure analytics platform stock market traded similar to {company_description}",
                'data_warehousing': f"public companies data warehousing analytics stock market traded {business_model}",
                'data_analytics': f"public companies data analytics infrastructure stock market traded comparable",
                'data_software': f"public companies data software infrastructure stock market traded similar"
            }
        elif sector == 'Space':
            strategies = {
                'space_companies': f"public companies space aerospace satellite stock market traded similar to {company_description}",
                'satellite_tech': f"public companies satellite technology space stock market traded {business_model}",
                'space_infrastructure': f"public companies space infrastructure aerospace stock market traded comparable",
                'space_services': f"public companies space services satellite stock market traded similar"
            }
        elif sector == 'Climate Deep' or sector == 'Climate Software':
            strategies = {
                'climate_tech': f"public companies climate technology sustainability stock market traded similar to {company_description}",
                'cleantech': f"public companies cleantech climate solutions stock market traded {business_model}",
                'sustainability': f"public companies sustainability climate software stock market traded comparable",
                'carbon_tech': f"public companies carbon technology climate stock market traded similar"
            }
        elif sector == 'Renewables':
            strategies = {
                'renewable_energy': f"public companies renewable energy clean energy stock market traded similar to {company_description}",
                'solar_wind': f"public companies solar wind energy renewable stock market traded {business_model}",
                'clean_energy': f"public companies clean energy renewable power stock market traded comparable",
                'energy_tech': f"public companies energy technology renewable stock market traded similar"
            }
        elif sector == 'Crypto':
            strategies = {
                'crypto_companies': f"public companies cryptocurrency blockchain digital assets stock market traded similar to {company_description}",
                'blockchain_tech': f"public companies blockchain technology crypto stock market traded {business_model}",
                'digital_assets': f"public companies digital assets cryptocurrency stock market traded comparable",
                'defi_web3': f"public companies DeFi Web3 blockchain stock market traded similar"
            }
        elif sector == 'Dev Tool':
            strategies = {
                'developer_tools': f"public companies developer tools software development stock market traded similar to {company_description}",
                'devops_platforms': f"public companies DevOps CI/CD development stock market traded {business_model}",
                'software_infrastructure': f"public companies software infrastructure developer stock market traded comparable",
                'development_platforms': f"public companies development platform tools stock market traded similar"
            }
        elif sector == 'Gaming':
            strategies = {
                'gaming_companies': f"public companies gaming video games stock market traded similar to {company_description}",
                'game_publishers': f"public companies game publishers gaming stock market traded {business_model}",
                'gaming_platforms': f"public companies gaming platforms video games stock market traded comparable",
                'esports_gaming': f"public companies esports gaming entertainment stock market traded similar"
            }
        elif sector == 'HR':
            strategies = {
                'hr_software': f"public companies HR software human resources stock market traded similar to {company_description}",
                'talent_management': f"public companies talent management HR stock market traded {business_model}",
                'workforce_platforms': f"public companies workforce platforms HR stock market traded comparable",
                'recruitment_tech': f"public companies recruitment technology HR stock market traded similar"
            }
        elif sector == 'Insurtech':
            strategies = {
                'insurance_tech': f"public companies insurance technology insurtech stock market traded similar to {company_description}",
                'digital_insurance': f"public companies digital insurance insurtech stock market traded {business_model}",
                'insurance_platforms': f"public companies insurance platforms insurtech stock market traded comparable",
                'insurance_software': f"public companies insurance software insurtech stock market traded similar"
            }
        elif sector == 'Legal':
            strategies = {
                'legal_tech': f"public companies legal technology legaltech stock market traded similar to {company_description}",
                'legal_software': f"public companies legal software law tech stock market traded {business_model}",
                'compliance_tech': f"public companies compliance technology legal stock market traded comparable",
                'legal_platforms': f"public companies legal platforms law stock market traded similar"
            }
        elif sector == 'Supply-Chain':
            strategies = {
                'logistics_tech': f"public companies logistics supply chain stock market traded similar to {company_description}",
                'supply_chain_software': f"public companies supply chain software logistics stock market traded {business_model}",
                'warehouse_tech': f"public companies warehouse technology logistics stock market traded comparable",
                'freight_logistics': f"public companies freight logistics supply chain stock market traded similar"
            }
        elif sector == 'Travel':
            strategies = {
                'travel_tech': f"public companies travel technology tourism stock market traded similar to {company_description}",
                'booking_platforms': f"public companies booking platforms travel stock market traded {business_model}",
                'travel_software': f"public companies travel software tourism stock market traded comparable",
                'hospitality_tech': f"public companies hospitality technology travel stock market traded similar"
            }
        elif sector == 'GTM':
            strategies = {
                'sales_tech': f"public companies sales technology go-to-market stock market traded similar to {company_description}",
                'marketing_software': f"public companies marketing software GTM stock market traded {business_model}",
                'revenue_platforms': f"public companies revenue platforms sales stock market traded comparable",
                'gtm_software': f"public companies go-to-market software sales stock market traded similar"
            }
        elif sector == 'Agtech':
            strategies = {
                'agriculture_tech': f"public companies agriculture technology agtech stock market traded similar to {company_description}",
                'farming_tech': f"public companies farming technology agriculture stock market traded {business_model}",
                'agtech_platforms': f"public companies agtech platforms agriculture stock market traded comparable",
                'precision_agriculture': f"public companies precision agriculture agtech stock market traded similar"
            }
        elif sector == 'B2C':
            strategies = {
                'consumer_companies': f"public companies consumer B2C retail stock market traded similar to {company_description}",
                'consumer_platforms': f"public companies consumer platforms B2C stock market traded {business_model}",
                'consumer_services': f"public companies consumer services B2C stock market traded comparable",
                'consumer_tech': f"public companies consumer technology B2C stock market traded similar"
            }
        elif sector == 'Capital Markets':
            strategies = {
                'trading_platforms': f"public companies trading platforms capital markets stock market traded similar to {company_description}",
                'investment_tech': f"public companies investment technology capital markets stock market traded {business_model}",
                'financial_markets': f"public companies financial markets trading stock market traded comparable",
                'securities_tech': f"public companies securities technology capital markets stock market traded similar"
            }
        elif sector == 'Deep' or sector == 'Deep Tech':
            strategies = {
                'deep_tech': f"public companies deep technology research stock market traded similar to {company_description}",
                'advanced_tech': f"public companies advanced technology deep tech stock market traded {business_model}",
                'research_tech': f"public companies research technology scientific stock market traded comparable",
                'frontier_tech': f"public companies frontier technology deep tech stock market traded similar"
            }
        elif sector == 'Grocery Delivery':
            strategies = {
                'food_delivery': f"public companies food delivery grocery stock market traded similar to {company_description}",
                'grocery_platforms': f"public companies grocery platforms delivery stock market traded {business_model}",
                'meal_delivery': f"public companies meal delivery food stock market traded comparable",
                'quick_commerce': f"public companies quick commerce grocery delivery stock market traded similar"
            }
        elif sector == 'Fintech B2B':
            # Alias for B2B Fintech
            strategies = {
                'enterprise_fintech': f"public companies enterprise fintech B2B financial stock market traded similar to {company_description}",
                'corporate_payments': f"public companies corporate payments B2B stock market traded {business_model}",
                'business_financial': f"public companies business financial services stock market traded comparable",
                'enterprise_financial': f"public companies enterprise financial technology stock market traded similar"
            }
        elif sector == 'Fintech B2C':
            # Alias for B2C Fintech
            strategies = {
                'consumer_fintech': f"public companies consumer fintech B2C financial stock market traded similar to {company_description}",
                'personal_finance': f"public companies personal finance consumer stock market traded {business_model}",
                'consumer_payments': f"public companies consumer payments fintech stock market traded comparable",
                'digital_banking': f"public companies digital banking consumer stock market traded similar"
            }
        else:
            # Generic strategies for other sectors
            strategies = {
                'sector_specific': f"public companies {sector} sector stock market traded similar to {company_description}",
                'business_model': f"public companies {sector} {business_model} stock market traded comparable",
                'industry_focus': f"public companies {sector} industry stock market traded similar business model",
                'sector_comparables': f"public companies {sector} stock market traded comparable companies"
            }
        
        return strategies
    
    def _get_sector_comparables_prompt(self, sector: str, strategy_name: str, search_results: Dict) -> str:
        """Generate sector-specific prompt for analyzing comparables"""
        
        sector_context = {
            'E-com': "Focus on e-commerce platforms, online retail software, digital commerce solutions, and retail technology companies. Look for companies with similar business models in online retail, marketplace platforms, or retail SaaS.",
            'SaaS': "Focus on enterprise software companies, cloud-based solutions, subscription software platforms, and business software providers. Look for companies with similar SaaS business models, recurring revenue, and enterprise customers.",
            'B2B Fintech': "Focus on enterprise financial technology companies, B2B payment solutions, corporate financial services, and business banking platforms. Look for companies serving enterprise customers with financial technology solutions.",
            'B2C Fintech': "Focus on consumer financial technology companies, personal finance apps, consumer payment solutions, and digital banking platforms. Look for companies serving individual consumers with financial technology.",
            'Health': "Focus on healthcare software companies, digital health platforms, medical technology solutions, and healthcare SaaS providers. Look for companies in the healthcare technology space with similar business models.",
            'Edtech': "Focus on education technology companies, online learning platforms, educational software providers, and learning management systems. Look for companies in the education technology space.",
            'Cyber': "Focus on cybersecurity companies, security software providers, threat detection platforms, and cyber technology solutions. Look for companies in the cybersecurity space with similar security-focused business models.",
            'Adtech': "Focus on advertising technology companies, digital advertising platforms, marketing technology solutions, and ad tech providers. Look for companies in the digital advertising and marketing technology space.",
            'Marketplace': "Focus on marketplace platforms, two-sided marketplaces, peer-to-peer platforms, and multi-sided platform companies. Look for companies that connect buyers and sellers or facilitate transactions.",
            'AI': "Focus on artificial intelligence companies, machine learning platforms, AI software providers, and AI technology solutions. Look for companies that primarily focus on AI/ML technology and applications.",
            'Defense': "Focus on defense contractors, military technology companies, aerospace defense firms, and defense software providers. Look for companies serving military, defense, and national security markets.",
            'Data Infrastructure': "Focus on data platform companies, data warehousing solutions, analytics infrastructure providers, and data management software. Look for companies that provide core data infrastructure and analytics capabilities.",
            'Space': "Focus on space technology companies, satellite operators, launch providers, and space infrastructure firms. Look for companies in commercial space, satellite communications, and space services.",
            'Climate Deep': "Focus on deep climate technology companies, carbon capture solutions, climate analytics platforms, and sustainability infrastructure. Look for companies addressing fundamental climate challenges.",
            'Climate Software': "Focus on climate software companies, sustainability platforms, carbon management solutions, and environmental analytics. Look for companies providing software for climate and sustainability.",
            'Renewables': "Focus on renewable energy companies, clean energy providers, solar and wind technology firms, and energy storage solutions. Look for companies in renewable power generation and clean energy infrastructure.",
            'Crypto': "Focus on cryptocurrency companies, blockchain platforms, digital asset exchanges, and Web3 infrastructure. Look for companies in crypto trading, DeFi, and blockchain technology.",
            'Dev Tool': "Focus on developer tools companies, DevOps platforms, software development infrastructure, and coding productivity solutions. Look for companies serving software developers and engineering teams.",
            'Gaming': "Focus on gaming companies, video game publishers, gaming platforms, and esports organizations. Look for companies in game development, publishing, and gaming infrastructure.",
            'HR': "Focus on HR technology companies, human capital management platforms, talent acquisition solutions, and workforce analytics. Look for companies serving HR departments and people operations.",
            'Insurtech': "Focus on insurance technology companies, digital insurance platforms, underwriting technology, and claims processing solutions. Look for companies modernizing the insurance industry.",
            'Legal': "Focus on legal technology companies, law practice management software, contract automation platforms, and compliance solutions. Look for companies serving law firms and legal departments.",
            'Supply-Chain': "Focus on supply chain technology companies, logistics platforms, warehouse management systems, and freight technology. Look for companies optimizing supply chain and logistics operations.",
            'Travel': "Focus on travel technology companies, booking platforms, hospitality software, and tourism management solutions. Look for companies in travel, hospitality, and tourism sectors.",
            'GTM': "Focus on go-to-market technology companies, sales enablement platforms, marketing automation software, and revenue operations tools. Look for companies helping businesses with sales and marketing.",
            'Agtech': "Focus on agricultural technology companies, precision farming solutions, crop management platforms, and farm automation. Look for companies modernizing agriculture and farming.",
            'B2C': "Focus on consumer-facing companies, B2C platforms, consumer services, and retail technology. Look for companies serving individual consumers directly.",
            'Capital Markets': "Focus on capital markets technology, trading platforms, investment management software, and financial markets infrastructure. Look for companies serving traders, investors, and financial institutions.",
            'Deep': "Focus on deep technology companies, advanced research firms, frontier technology developers, and scientific computing companies. Look for companies working on breakthrough technologies.",
            'Deep Tech': "Focus on deep technology companies, advanced research firms, frontier technology developers, and scientific computing companies. Look for companies working on breakthrough technologies.",
            'Grocery Delivery': "Focus on grocery delivery companies, food delivery platforms, quick commerce services, and meal delivery solutions. Look for companies in on-demand grocery and food delivery.",
            'Fintech B2B': "Focus on B2B fintech companies, enterprise payment solutions, corporate banking platforms, and business financial services. Look for fintech companies serving businesses.",
            'Fintech B2C': "Focus on B2C fintech companies, consumer banking apps, personal finance platforms, and retail payment solutions. Look for fintech companies serving consumers."
        }
        
        context = sector_context.get(sector, f"Focus on companies in the {sector} sector with similar business models and value propositions.")
        
        return f"""
Analyze these search results to find comparable public companies in the {sector} sector using strategy: {strategy_name}.

{context}

Focus on:
- Public companies (with stock tickers if available)
- Companies specifically in the {sector} sector
- Similar business models or value propositions
- Revenue/market cap data when available
- Key business metrics

For each company, provide:
- Company name
- Stock ticker (if public)
- Brief description
- Industry classification (should be {sector} or closely related)
- Market cap (if available)
- Revenue (if available)
- Why it's comparable to a {sector} company
- Relevance score (1-10, must be 7+ for inclusion)

Return ONLY valid JSON in this format:
{{
  "companies": [
    {{
      "name": "Company Name",
      "ticker": "TICK",
      "description": "Brief business description",
      "industry": "{sector}",
      "market_cap": 1000000000,
      "revenue": 500000000,
      "relevance_reasoning": "Why this is comparable to {sector}",
      "relevance_score": 8.5,
      "key_metrics": {{}}
    }}
  ],
  "search_quality": "high/medium/low",
  "total_found": 5
}}

Only include companies that are genuinely relevant to the {sector} sector with relevance scores of 7 or higher.
"""
    
    def _deduplicate_comparables(self, comparables: List[CompanyComparable]) -> List[CompanyComparable]:
        """Remove duplicate comparable companies based on name and ticker"""
        seen = set()
        unique_comparables = []
        
        for comp in comparables:
            # Create a unique identifier based on name and ticker
            identifier = f"{comp.name.lower()}_{comp.ticker.lower() if comp.ticker else 'no_ticker'}"
            
            if identifier not in seen:
                seen.add(identifier)
                unique_comparables.append(comp)
        
        return unique_comparables

    def find_ma_transactions(self, industry: str, company_type: str = "", 
                           time_period: str = "2023-2024") -> List[MATransaction]:
        """Find relevant M&A transactions using intelligent sector-specific search"""
        try:
            # Use the sector (industry) for targeted M&A search
            sector = industry  # This is now the classified sector
            
            # Generate intelligent sector-specific M&A search strategies
            search_strategies = self._get_sector_ma_strategies(sector, time_period)
            
            all_transactions = []
            
            for strategy_name, query in search_strategies.items():
                logger.info(f"Searching for M&A transactions using strategy '{strategy_name}': {query}")
                
                # Search with Tavily
                search_results = self._rate_limited_tavily_call(query)
                
                # Analyze with sector-specific prompt
                ma_prompt = self._get_sector_ma_prompt(sector, strategy_name, search_results)
                
                analysis = self.analyze_search_results(ma_prompt, search_results)
                
                # Parse and add to results
                try:
                    parsed_results = self._parse_json_response(analysis)
                    transactions_data = parsed_results.get('transactions', [])
                    
                    for transaction in transactions_data:
                        relevance_score = float(transaction.get('relevance_score', 0))
                        if relevance_score >= 6.0:  # Stricter filtering
                            ma_transaction = MATransaction(
                                target_company=transaction.get('target_company', ''),
                                acquirer=transaction.get('acquirer', ''),
                                deal_value=transaction.get('deal_value'),
                                deal_date=transaction.get('deal_date', ''),
                                industry=transaction.get('industry', sector),
                                description=transaction.get('description', ''),
                                revenue_multiple=transaction.get('revenue_multiple'),
                                source=f"tavily_search_{sector}_{strategy_name}",
                                relevance_score=relevance_score
                            )
                            all_transactions.append(ma_transaction)
                    
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse M&A analysis for {strategy_name}: {e}")
                    continue
            
            # Remove duplicates and sort by relevance
            unique_transactions = self._deduplicate_ma_transactions(all_transactions)
            unique_transactions.sort(key=lambda x: x.relevance_score, reverse=True)
            
            logger.info(f"Found {len(unique_transactions)} unique M&A transactions in {sector} sector")
            return unique_transactions
            
        except Exception as e:
            logger.error(f"M&A search failed: {e}")
            return []
    
    def _get_sector_ma_strategies(self, sector: str, time_period: str) -> Dict[str, str]:
        """Generate intelligent M&A search strategies based on sector"""
        
        strategies = {}
        
        # Sector-specific M&A search strategies
        if sector == 'E-com':
            strategies = {
                'retail_acquisitions': f"e-commerce retail platform acquisitions {time_period}",
                'online_retail_deals': f"online retail ecommerce M&A deals {time_period}",
                'retail_tech_exits': f"retail technology software startup exits {time_period}",
                'digital_commerce_ma': f"digital commerce platform M&A transactions {time_period}"
            }
        elif sector == 'SaaS':
            strategies = {
                'enterprise_saas_ma': f"enterprise SaaS software acquisitions {time_period}",
                'business_software_deals': f"business software platform M&A deals {time_period}",
                'cloud_software_exits': f"cloud software SaaS startup exits {time_period}",
                'workflow_software_ma': f"workflow management software acquisitions {time_period}"
            }
        elif sector == 'B2B Fintech':
            strategies = {
                'enterprise_fintech_ma': f"enterprise fintech B2B financial acquisitions {time_period}",
                'corporate_payments_deals': f"corporate payments B2B M&A deals {time_period}",
                'business_financial_exits': f"business financial services startup exits {time_period}",
                'enterprise_financial_ma': f"enterprise financial technology acquisitions {time_period}"
            }
        elif sector == 'B2C Fintech':
            strategies = {
                'consumer_fintech_ma': f"consumer fintech B2C financial acquisitions {time_period}",
                'personal_finance_deals': f"personal finance consumer M&A deals {time_period}",
                'consumer_payments_exits': f"consumer payments fintech startup exits {time_period}",
                'digital_banking_ma': f"digital banking consumer acquisitions {time_period}"
            }
        elif sector == 'Health':
            strategies = {
                'healthcare_software_ma': f"healthcare software medical acquisitions {time_period}",
                'digital_health_deals': f"digital health technology M&A deals {time_period}",
                'medical_software_exits': f"medical software healthcare startup exits {time_period}",
                'health_tech_ma': f"health technology platform acquisitions {time_period}"
            }
        elif sector == 'Edtech':
            strategies = {
                'education_software_ma': f"education software learning acquisitions {time_period}",
                'online_learning_deals': f"online learning education M&A deals {time_period}",
                'educational_tech_exits': f"educational technology startup exits {time_period}",
                'learning_platform_ma': f"learning platform education acquisitions {time_period}"
            }
        elif sector == 'Cyber':
            strategies = {
                'cybersecurity_ma': f"cybersecurity security acquisitions {time_period}",
                'security_software_deals': f"security software cyber M&A deals {time_period}",
                'cyber_tech_exits': f"cyber technology security startup exits {time_period}",
                'threat_detection_ma': f"threat detection security acquisitions {time_period}"
            }
        elif sector == 'Adtech':
            strategies = {
                'advertising_tech_ma': f"advertising technology adtech acquisitions {time_period}",
                'digital_advertising_deals': f"digital advertising platform M&A deals {time_period}",
                'marketing_tech_exits': f"marketing technology startup exits {time_period}",
                'ad_platform_ma': f"advertising platform acquisitions {time_period}"
            }
        elif sector == 'Marketplace':
            strategies = {
                'marketplace_platform_ma': f"marketplace platform acquisitions {time_period}",
                'two_sided_platform_deals': f"two-sided platform marketplace M&A deals {time_period}",
                'peer_to_peer_exits': f"peer to peer marketplace startup exits {time_period}",
                'platform_economy_ma': f"platform economy marketplace acquisitions {time_period}"
            }
        elif sector == 'AI':
            strategies = {
                'ai_platform_ma': f"artificial intelligence AI platform acquisitions {time_period}",
                'machine_learning_deals': f"machine learning AI M&A deals {time_period}",
                'ai_software_exits': f"AI software artificial intelligence startup exits {time_period}",
                'ai_technology_ma': f"AI technology platform acquisitions {time_period}"
            }
        else:
            # Generic strategies for other sectors
            strategies = {
                'sector_ma': f"{sector} sector M&A deals {time_period}",
                'sector_acquisitions': f"{sector} company acquisitions {time_period}",
                'sector_exits': f"{sector} startup exits {time_period}",
                'sector_transactions': f"recent {sector} acquisitions {time_period}"
            }
        
        return strategies
    
    def _get_sector_ma_prompt(self, sector: str, strategy_name: str, search_results: Dict) -> str:
        """Generate sector-specific prompt for analyzing M&A transactions"""
        
        sector_context = {
            'E-com': "Focus on e-commerce platform acquisitions, online retail software deals, digital commerce M&A, and retail technology company exits. Look for deals involving online retail platforms, marketplace acquisitions, or retail SaaS companies.",
            'SaaS': "Focus on enterprise software acquisitions, cloud-based solution deals, subscription software M&A, and business software company exits. Look for deals involving SaaS companies, enterprise software platforms, or cloud-based business solutions.",
            'B2B Fintech': "Focus on enterprise financial technology acquisitions, B2B payment solution deals, corporate financial services M&A, and business banking platform exits. Look for deals involving enterprise fintech companies or B2B financial services.",
            'B2C Fintech': "Focus on consumer financial technology acquisitions, personal finance app deals, consumer payment solution M&A, and digital banking platform exits. Look for deals involving consumer fintech companies or personal financial services.",
            'Health': "Focus on healthcare software acquisitions, digital health platform deals, medical technology M&A, and healthcare SaaS company exits. Look for deals involving healthcare technology companies or medical software platforms.",
            'Edtech': "Focus on education technology acquisitions, online learning platform deals, educational software M&A, and learning management system exits. Look for deals involving education technology companies or learning platforms.",
            'Cyber': "Focus on cybersecurity acquisitions, security software deals, threat detection platform M&A, and cyber technology company exits. Look for deals involving cybersecurity companies or security technology platforms.",
            'Adtech': "Focus on advertising technology acquisitions, digital advertising platform deals, marketing technology M&A, and ad tech company exits. Look for deals involving advertising technology companies or marketing platforms.",
            'Marketplace': "Focus on marketplace platform acquisitions, two-sided marketplace deals, peer-to-peer platform M&A, and multi-sided platform company exits. Look for deals involving marketplace companies or platform businesses.",
            'AI': "Focus on artificial intelligence acquisitions, machine learning platform deals, AI software M&A, and AI technology company exits. Look for deals involving AI companies or machine learning platforms.",
            'Defense': "Focus on defense contractor acquisitions, military technology deals, aerospace defense M&A, and defense software exits. Look for deals involving defense primes, military technology companies, or defense software platforms.",
            'Data Infrastructure': "Focus on data platform acquisitions, analytics company deals, data warehousing M&A, and data infrastructure exits. Look for deals involving data platforms, analytics companies, or data management solutions.",
            'Space': "Focus on space technology acquisitions, satellite company deals, launch provider M&A, and space infrastructure exits. Look for deals involving space companies, satellite operators, or space services.",
            'Climate Deep': "Focus on climate technology acquisitions, carbon capture deals, sustainability infrastructure M&A, and cleantech exits. Look for deals involving deep climate technology or sustainability infrastructure companies.",
            'Climate Software': "Focus on climate software acquisitions, sustainability platform deals, carbon management M&A, and environmental software exits. Look for deals involving climate software or sustainability platforms.",
            'Renewables': "Focus on renewable energy acquisitions, clean energy deals, solar/wind company M&A, and energy storage exits. Look for deals involving renewable energy companies or clean energy infrastructure.",
            'Crypto': "Focus on cryptocurrency acquisitions, blockchain company deals, digital asset platform M&A, and Web3 exits. Look for deals involving crypto exchanges, blockchain platforms, or DeFi companies.",
            'Dev Tool': "Focus on developer tools acquisitions, DevOps platform deals, development infrastructure M&A, and coding tools exits. Look for deals involving developer tools, DevOps platforms, or software development companies.",
            'Gaming': "Focus on gaming company acquisitions, game studio deals, gaming platform M&A, and esports exits. Look for deals involving game developers, publishers, or gaming infrastructure companies.",
            'HR': "Focus on HR technology acquisitions, HCM platform deals, talent management M&A, and workforce software exits. Look for deals involving HR tech companies, talent platforms, or workforce management solutions.",
            'Insurtech': "Focus on insurance technology acquisitions, digital insurance deals, underwriting platform M&A, and insurtech exits. Look for deals involving insurance technology companies or digital insurance platforms.",
            'Legal': "Focus on legal technology acquisitions, law software deals, compliance platform M&A, and legaltech exits. Look for deals involving legal tech companies, law practice management, or compliance solutions.",
            'Supply-Chain': "Focus on supply chain technology acquisitions, logistics platform deals, warehouse tech M&A, and freight software exits. Look for deals involving logistics companies, supply chain platforms, or warehouse technology.",
            'Travel': "Focus on travel technology acquisitions, booking platform deals, hospitality software M&A, and tourism tech exits. Look for deals involving travel tech companies, booking platforms, or hospitality solutions.",
            'GTM': "Focus on go-to-market technology acquisitions, sales enablement deals, marketing automation M&A, and revenue operations exits. Look for deals involving sales tech, marketing platforms, or GTM solutions.",
            'Agtech': "Focus on agricultural technology acquisitions, precision farming deals, crop management M&A, and farm tech exits. Look for deals involving agtech companies, precision agriculture, or farm management platforms.",
            'B2C': "Focus on consumer company acquisitions, B2C platform deals, consumer service M&A, and retail tech exits. Look for deals involving consumer-facing companies or B2C platforms.",
            'Capital Markets': "Focus on capital markets technology acquisitions, trading platform deals, investment tech M&A, and financial markets exits. Look for deals involving trading platforms, investment management, or capital markets infrastructure.",
            'Deep': "Focus on deep technology acquisitions, advanced research deals, frontier tech M&A, and scientific computing exits. Look for deals involving deep tech companies or breakthrough technology platforms.",
            'Deep Tech': "Focus on deep technology acquisitions, advanced research deals, frontier tech M&A, and scientific computing exits. Look for deals involving deep tech companies or breakthrough technology platforms.",
            'Grocery Delivery': "Focus on grocery delivery acquisitions, food delivery deals, quick commerce M&A, and meal delivery exits. Look for deals involving grocery delivery companies, food platforms, or quick commerce services.",
            'Fintech B2B': "Focus on B2B fintech acquisitions, enterprise payment deals, corporate banking M&A, and business financial exits. Look for deals involving B2B fintech companies or enterprise financial services.",
            'Fintech B2C': "Focus on B2C fintech acquisitions, consumer banking deals, personal finance M&A, and retail payment exits. Look for deals involving B2C fintech companies or consumer financial services."
        }
        
        context = sector_context.get(sector, f"Focus on M&A transactions in the {sector} sector involving companies with similar business models and value propositions.")
        
        return f"""
Analyze these search results to find M&A transactions in the {sector} sector using strategy: {strategy_name}.

{context}

Focus on:
- M&A deals in the {sector} sector
- Startup acquisitions and exits
- Deal values when available
- Acquirer and target company information
- Revenue multiples when available

For each transaction, provide:
- Target company name
- Acquirer company name
- Deal value (if available)
- Deal date (approximate if exact not available)
- Industry (should be {sector})
- Brief description of the deal
- Revenue multiple (if available)
- Relevance score (1-10, must be 6+ for inclusion)

Return ONLY valid JSON in this format:
{{
  "transactions": [
    {{
      "target_company": "Target Company Name",
      "acquirer": "Acquirer Company Name",
      "deal_value": 100000000,
      "deal_date": "2024-01-15",
      "industry": "{sector}",
      "description": "Brief description of the deal",
      "revenue_multiple": 5.2,
      "relevance_score": 8.5
    }}
  ],
  "search_quality": "high/medium/low",
  "total_found": 5
}}

Only include transactions that are genuinely relevant to the {sector} sector with relevance scores of 6 or higher.
"""
    
    def _deduplicate_ma_transactions(self, transactions: List[MATransaction]) -> List[MATransaction]:
        """Remove duplicate M&A transactions based on target company and acquirer"""
        seen = set()
        unique_transactions = []
        
        for transaction in transactions:
            # Create a unique identifier based on target and acquirer
            identifier = f"{transaction.target_company.lower()}_{transaction.acquirer.lower()}"
            
            if identifier not in seen:
                seen.add(identifier)
                unique_transactions.append(transaction)
        
        return unique_transactions
    
    def analyze_search_results(self, prompt: str, search_results: Dict) -> str:
        """Analyze search results with OpenAI"""
        try:
            # Format search results for analysis
            formatted_results = self._format_search_results(search_results)
            
            full_prompt = f"{prompt}\n\nSearch Results to Analyze:\n{formatted_results}"
            
            response = self.call_claude_text_only(full_prompt, max_tokens=4000)
            
            logger.info("Search results analysis completed")
            return response
            
        except Exception as e:
            logger.error(f"Search analysis failed: {e}")
            raise
    
    def _format_search_results(self, search_results: Dict) -> str:
        """Format Tavily search results for OpenAI analysis"""
        try:
            formatted = []
            
            # Add the answer if available
            if 'answer' in search_results:
                formatted.append(f"Search Answer: {search_results['answer']}\n")
            
            # Add individual results
            for i, result in enumerate(search_results.get('results', [])):
                formatted.append(f"Result {i+1}:")
                formatted.append(f"Title: {result.get('title', '')}")
                formatted.append(f"URL: {result.get('url', '')}")
                formatted.append(f"Content: {result.get('content', '')}")
                formatted.append("---")
            
            return "\n".join(formatted)
            
        except Exception as e:
            logger.error(f"Error formatting search results: {e}")
            return str(search_results)
    
    def _parse_json_response(self, response: str) -> Dict:
        """Parse JSON from OpenAI response with error handling"""
        try:
            # Clean the response
            cleaned = response.strip()
            
            # Look for JSON block
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                # Try parsing the whole response
                return json.loads(cleaned)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Raw response: {response[:500]}...")
            return {}
    
    # ============================================================================
    # YAHOO FINANCE INTEGRATION - Get Real Financial Data
    # ============================================================================
    
    def get_company_financials(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive financial data from Yahoo Finance"""
        try:
            if not ticker:
                return {}
            
            if not YFINANCE_AVAILABLE:
                logger.warning("yfinance not available, skipping financial data enhancement")
                return {'data_quality': 'missing', 'error': 'yfinance not available'}
            
            logger.info(f"Fetching financial data for {ticker}")
            
            # Get company data
            company = yf.Ticker(ticker)
            
            # Get key financial metrics
            info = company.info
            financials = {}
            
            # Basic company info
            financials['name'] = info.get('longName', info.get('shortName', ''))
            financials['sector'] = info.get('sector', '')
            financials['industry'] = info.get('industry', '')
            
            # Market data
            financials['market_cap'] = info.get('marketCap')
            financials['enterprise_value'] = info.get('enterpriseValue')
            
            # Revenue data
            financials['revenue_ttm'] = info.get('totalRevenue')
            financials['revenue_growth'] = info.get('revenueGrowth')
            
            # Calculate EV/Revenue multiple
            ev = financials.get('enterprise_value')
            revenue = financials.get('revenue_ttm')
            
            if ev and revenue and revenue > 0:
                financials['ev_revenue_multiple'] = ev / revenue
            else:
                financials['ev_revenue_multiple'] = None
            
            # Additional metrics
            financials['price_to_sales'] = info.get('priceToSalesTrailing12Months')
            financials['profit_margins'] = info.get('profitMargins')
            financials['operating_margins'] = info.get('operatingMargins')
            financials['current_price'] = info.get('currentPrice')
            financials['target_high_price'] = info.get('targetHighPrice')
            financials['target_low_price'] = info.get('targetLowPrice')
            
            # Quality assessment
            required_fields = ['enterprise_value', 'revenue_ttm', 'market_cap']
            available_fields = sum(1 for field in required_fields if financials.get(field) is not None)
            
            if available_fields == len(required_fields):
                financials['data_quality'] = 'complete'
            elif available_fields > 0:
                financials['data_quality'] = 'partial'
            else:
                financials['data_quality'] = 'missing'
            
            logger.info(f"Financial data for {ticker}: EV=${financials.get('enterprise_value')}, Revenue=${financials.get('revenue_ttm')}, Multiple={financials.get('ev_revenue_multiple')}")
            return financials
            
        except Exception as e:
            logger.error(f"Failed to get financial data for {ticker}: {e}")
            return {'data_quality': 'error', 'error': str(e)}
    
    def enhance_comparables_with_financials(self, comparables: List[CompanyComparable]) -> List[CompanyComparable]:
        """Enhance comparable companies with Yahoo Finance data"""
        try:
            enhanced_comparables = []
            
            for comp in comparables:
                if comp.ticker:
                    logger.info(f"Enhancing {comp.name} ({comp.ticker}) with financial data...")
                    
                    # Get financial data
                    financials = self.get_company_financials(comp.ticker)
                    
                    # Create enhanced comparable
                    enhanced_comp = CompanyComparable(
                        name=financials.get('name', comp.name),
                        ticker=comp.ticker,
                        description=comp.description,
                        industry=financials.get('industry', comp.industry),
                        market_cap=financials.get('market_cap', comp.market_cap),
                        enterprise_value=financials.get('enterprise_value'),
                        revenue_ttm=financials.get('revenue_ttm'),
                        ev_revenue_multiple=financials.get('ev_revenue_multiple'),
                        source=comp.source,
                        relevance_score=comp.relevance_score,
                        key_metrics={
                            **comp.key_metrics,
                            'price_to_sales': financials.get('price_to_sales'),
                            'profit_margins': financials.get('profit_margins'),
                            'operating_margins': financials.get('operating_margins'),
                            'revenue_growth': financials.get('revenue_growth'),
                            'current_price': financials.get('current_price'),
                            'target_high_price': financials.get('target_high_price'),
                            'target_low_price': financials.get('target_low_price')
                        },
                        financial_data_quality=financials.get('data_quality', 'missing')
                    )
                    
                    enhanced_comparables.append(enhanced_comp)
                    
                    # Rate limiting for Yahoo Finance
                    time.sleep(0.5)
                    
                else:
                    # Keep original if no ticker
                    enhanced_comparables.append(comp)
            
            logger.info(f"Enhanced {len(enhanced_comparables)} comparables with financial data")
            return enhanced_comparables
            
        except Exception as e:
            logger.error(f"Failed to enhance comparables with financials: {e}")
            return comparables
    
    def calculate_valuation_multiples(self, enhanced_comparables: List[CompanyComparable]) -> Dict[str, Any]:
        """Calculate valuation multiples from enhanced comparable data"""
        try:
            # Filter for companies with complete financial data
            valid_comps = [
                comp for comp in enhanced_comparables 
                if comp.ev_revenue_multiple is not None and comp.financial_data_quality == 'complete'
            ]
            
            if not valid_comps:
                return {
                    'error': 'No companies with complete financial data found',
                    'analysis': 'Unable to calculate meaningful multiples'
                }
            
            # Calculate EV/Revenue multiple statistics
            ev_multiples = [comp.ev_revenue_multiple for comp in valid_comps]
            
            multiples_analysis = {
                'ev_revenue_multiples': {
                    'count': len(ev_multiples),
                    'mean': sum(ev_multiples) / len(ev_multiples),
                    'median': sorted(ev_multiples)[len(ev_multiples) // 2],
                    'min': min(ev_multiples),
                    'max': max(ev_multiples),
                    'range': max(ev_multiples) - min(ev_multiples)
                },
                'companies_analyzed': [
                    {
                        'name': comp.name,
                        'ticker': comp.ticker,
                        'ev_revenue_multiple': comp.ev_revenue_multiple,
                        'market_cap': comp.market_cap,
                        'enterprise_value': comp.enterprise_value,
                        'revenue_ttm': comp.revenue_ttm,
                        'relevance_score': comp.relevance_score
                    } for comp in valid_comps
                ],
                'valuation_guidance': {
                    'conservative_multiple': sorted(ev_multiples)[len(ev_multiples) // 4],  # 25th percentile
                    'aggressive_multiple': sorted(ev_multiples)[3 * len(ev_multiples) // 4],  # 75th percentile
                    'peer_median': sorted(ev_multiples)[len(ev_multiples) // 2]
                }
            }
            
            logger.info(f"Calculated multiples from {len(valid_comps)} companies: Median EV/Rev = {multiples_analysis['ev_revenue_multiples']['median']:.2f}x")
            return multiples_analysis
            
        except Exception as e:
            logger.error(f"Failed to calculate valuation multiples: {e}")
            return {'error': str(e)}
    
    def run_comparables_analysis(self, extracted_data: Dict) -> Dict:
        """Run comprehensive comparable and M&A analysis"""
        try:
            # Extract key information from document data
            company_info = self._extract_company_info(extracted_data)
            
            if not company_info:
                logger.warning("No company information found for comparables analysis")
                return {"error": "Insufficient company data for comparables analysis"}
            
            logger.info(f"Running comparables analysis for: {company_info}")
            
            # Find comparable companies
            raw_comparables = self.find_comparable_companies(
                company_description=company_info.get('description', ''),
                industry=company_info.get('industry', ''),
                business_model=company_info.get('business_model', '')
            )
            
            # Enhance with Yahoo Finance data
            logger.info("Enhancing comparables with Yahoo Finance data...")
            enhanced_comparables = self.enhance_comparables_with_financials(raw_comparables)
            
            # Calculate valuation multiples
            logger.info("Calculating EV/Revenue multiples...")
            multiples_analysis = self.calculate_valuation_multiples(enhanced_comparables)
            
            # Find M&A transactions
            ma_transactions = self.find_ma_transactions(
                industry=company_info.get('industry', ''),
                company_type=company_info.get('company_type', ''),
                time_period="2023-2024"
            )
            
            # Compile results
            analysis_results = {
                'company_profile': company_info,
                'comparable_companies': [
                    {
                        'name': comp.name,
                        'ticker': comp.ticker,
                        'description': comp.description,
                        'industry': comp.industry,
                        'market_cap': comp.market_cap,
                        'enterprise_value': comp.enterprise_value,
                        'revenue_ttm': comp.revenue_ttm,
                        'ev_revenue_multiple': comp.ev_revenue_multiple,
                        'relevance_score': comp.relevance_score,
                        'financial_data_quality': comp.financial_data_quality,
                        'key_metrics': comp.key_metrics
                    } for comp in enhanced_comparables[:15]  # Top 15
                ],
                'ma_transactions': [
                    {
                        'target_company': txn.target_company,
                        'acquirer': txn.acquirer,
                        'deal_value': txn.deal_value,
                        'deal_date': txn.deal_date,
                        'industry': txn.industry,
                        'description': txn.description,
                        'revenue_multiple': txn.revenue_multiple,
                        'relevance_score': txn.relevance_score
                    } for txn in ma_transactions[:10]  # Top 10
                ],
                'valuation_multiples': multiples_analysis,
                'analysis_summary': {
                    'comparables_found': len(enhanced_comparables),
                    'companies_with_financials': len([c for c in enhanced_comparables if c.financial_data_quality == 'complete']),
                    'ma_transactions_found': len(ma_transactions),
                    'search_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'industries_analyzed': list(set([comp.industry for comp in enhanced_comparables]))
                }
            }
            
            logger.info("Comparables analysis completed")
            return analysis_results
            
        except Exception as e:
            logger.error(f"Comparables analysis failed: {e}")
            return {"error": str(e)}
    
    def _extract_company_info(self, extracted_data: Dict) -> Dict:
        """Extract relevant company information from document data with proper sector classification"""
        try:
            company_info = {}
            
            # Try to extract from different document types
            if 'company_overview' in extracted_data:
                # Board deck format
                overview = extracted_data['company_overview']
                company_info = {
                    'description': overview.get('description', ''),
                    'industry': overview.get('industry', ''),
                    'business_model': overview.get('business_model', ''),
                    'company_type': 'startup'
                }
            
            elif 'extracted_entities' in extracted_data:
                # General format - use sector classification from extracted data
                entities = extracted_data['extracted_entities']
                industry_terms = entities.get('industry_terms', [])
                
                # Get sector from the extracted data if available
                sector = 'SaaS'  # Default fallback
                if 'sector_classification' in extracted_data:
                    sector_data = extracted_data['sector_classification']
                    sector = sector_data.get('primary_sector', 'SaaS')
                    logger.info(f"Using extracted sector classification: {sector}")
                else:
                    # Fallback to keyword-based classification
                    sector = self._classify_sector(industry_terms, extracted_data)
                    logger.info(f"Using keyword-based sector classification: {sector}")
                
                company_info = {
                    'industry': sector,  # Use classified sector instead of generic terms
                    'description': self._extract_company_description(extracted_data),
                    'business_model': self._extract_business_model(extracted_data),
                    'company_type': 'company',
                    'sector': sector  # Add explicit sector field
                }
            
            # Add any competitors mentioned as context
            if 'extracted_entities' in extracted_data:
                competitors = extracted_data['extracted_entities'].get('competitors_mentioned', [])
                if competitors:
                    company_info['competitors'] = competitors
            
            return company_info
            
        except Exception as e:
            logger.error(f"Error extracting company info: {e}")
            return {}
    
    def _classify_sector(self, industry_terms: List[str], extracted_data: Dict) -> str:
        """Intelligently classify document into specific sector categories using business model analysis"""
        try:
            # Combine industry terms with any business updates for better classification
            business_updates = extracted_data.get('business_updates', {})
            achievements = business_updates.get('achievements', [])
            challenges = business_updates.get('challenges', [])
            
            # Create comprehensive text for classification
            classification_text = ' '.join([
                ' '.join(industry_terms),
                ' '.join(achievements),
                ' '.join(challenges)
            ]).lower()
            
            # Enhanced sector classification with business model understanding
            sector_patterns = {
                # Business Model Patterns (Highest Priority)
                'E-com': {
                    'keywords': ['e-commerce', 'ecommerce', 'online retail', 'digital commerce', 'retail vendors', 'retail platform', 'online store', 'digital storefront'],
                    'patterns': ['retail.*ai', 'ai.*retail', 'retail.*platform', 'vendor.*platform'],
                    'weight': 3
                },
                'SaaS': {
                    'keywords': ['saas', 'software as a service', 'cloud software', 'subscription software', 'workflow solutions', 'supply management software', 'enterprise software', 'business software'],
                    'patterns': ['software.*platform', 'platform.*software', 'workflow.*solution', 'management.*software'],
                    'weight': 3
                },
                'Marketplace': {
                    'keywords': ['marketplace', 'platform', 'two-sided', 'peer to peer', 'vendor platform', 'multi-sided platform'],
                    'patterns': ['connect.*buyer.*seller', 'buyer.*seller.*platform', 'peer.*peer'],
                    'weight': 3
                },
                'B2B Fintech': {
                    'keywords': ['b2b fintech', 'b2b financial', 'enterprise fintech', 'corporate payments', 'b2b payments', 'business payments', 'enterprise financial'],
                    'patterns': ['corporate.*payment', 'business.*financial', 'enterprise.*fintech'],
                    'weight': 3
                },
                'B2C Fintech': {
                    'keywords': ['b2c fintech', 'consumer fintech', 'personal finance', 'consumer payments', 'personal banking', 'consumer financial'],
                    'patterns': ['consumer.*payment', 'personal.*finance', 'consumer.*banking'],
                    'weight': 3
                },
                'B2C': {
                    'keywords': ['b2c', 'consumer', 'direct to consumer', 'retail', 'consumer product', 'consumer service'],
                    'patterns': ['direct.*consumer', 'consumer.*product'],
                    'weight': 3
                },
                
                # Industry-Specific Patterns (Medium Priority)
                'Adtech': {
                    'keywords': ['adtech', 'advertising', 'ad tech', 'digital advertising', 'marketing tech', 'ad platform', 'ppc', 'paid advertising'],
                    'patterns': ['advertising.*platform', 'marketing.*automation', 'ad.*tech'],
                    'weight': 2
                },
                'Health': {
                    'keywords': ['health', 'healthcare', 'medical', 'health tech', 'digital health', 'telemedicine', 'healthcare software'],
                    'patterns': ['healthcare.*platform', 'medical.*software', 'digital.*health'],
                    'weight': 2
                },
                'Edtech': {
                    'keywords': ['edtech', 'education', 'learning', 'educational', 'ed tech', 'online learning', 'education platform'],
                    'patterns': ['education.*platform', 'learning.*software', 'online.*education'],
                    'weight': 2
                },
                'Cyber': {
                    'keywords': ['cyber', 'cybersecurity', 'security', 'threat', 'vulnerability', 'penetration testing', 'security software'],
                    'patterns': ['security.*platform', 'cyber.*security', 'threat.*detection'],
                    'weight': 2
                },
                'Supply-Chain': {
                    'keywords': ['supply chain', 'logistics', 'warehouse', 'inventory', 'distribution', 'supply chain software'],
                    'patterns': ['supply.*chain', 'logistics.*platform', 'warehouse.*management'],
                    'weight': 2
                },
                'Travel': {
                    'keywords': ['travel', 'tourism', 'booking', 'accommodation', 'transportation', 'travel platform'],
                    'patterns': ['travel.*platform', 'booking.*platform', 'accommodation.*booking'],
                    'weight': 2
                },
                'Gaming': {
                    'keywords': ['gaming', 'game', 'esports', 'video game', 'gaming platform', 'game development'],
                    'patterns': ['gaming.*platform', 'video.*game', 'esports.*platform'],
                    'weight': 2
                },
                'HR': {
                    'keywords': ['hr', 'human resources', 'recruitment', 'hiring', 'talent', 'workforce', 'hr software'],
                    'patterns': ['recruitment.*platform', 'talent.*management', 'hr.*software'],
                    'weight': 2
                },
                'Legal': {
                    'keywords': ['legal', 'law', 'legal tech', 'legal software', 'legal platform'],
                    'patterns': ['legal.*platform', 'law.*software', 'legal.*tech'],
                    'weight': 2
                },
                'Climate Software': {
                    'keywords': ['climate software', 'carbon tracking', 'sustainability software', 'climate tech'],
                    'patterns': ['carbon.*tracking', 'sustainability.*software', 'climate.*software'],
                    'weight': 2
                },
                'Insurtech': {
                    'keywords': ['insurtech', 'insurance', 'insure', 'insur tech', 'insurance platform'],
                    'patterns': ['insurance.*platform', 'insur.*tech', 'insurance.*software'],
                    'weight': 2
                },
                
                # Technology Patterns (Lowest Priority - only if no business model match)
                'AI': {
                    'keywords': ['ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning', 'neural networks', 'algorithm', 'automation'],
                    'patterns': ['ai.*platform', 'machine.*learning', 'neural.*network'],
                    'weight': 1
                },
                'Deep': {
                    'keywords': ['deep tech', 'deep technology', 'research', 'scientific', 'research platform'],
                    'patterns': ['deep.*tech', 'scientific.*research', 'research.*platform'],
                    'weight': 1
                },
                'Dev Tool': {
                    'keywords': ['dev tool', 'developer', 'software development', 'coding', 'programming', 'development platform'],
                    'patterns': ['developer.*tool', 'coding.*platform', 'development.*platform'],
                    'weight': 1
                }
            }
            
            # Intelligent scoring system
            sector_scores = {}
            import re
            
            for sector, config in sector_patterns.items():
                score = 0
                weight = config['weight']
                
                # Check keywords
                for keyword in config['keywords']:
                    if keyword in classification_text:
                        score += weight
                
                # Check patterns (regex matching for more sophisticated detection)
                for pattern in config['patterns']:
                    if re.search(pattern, classification_text):
                        score += weight * 2  # Patterns get higher weight as they're more specific
                
                if score > 0:
                    sector_scores[sector] = score
            
            # Business logic for edge cases
            if sector_scores:
                # If we have multiple high-scoring sectors, apply business logic
                high_scoring = [(s, score) for s, score in sector_scores.items() if score >= 3]
                
                if len(high_scoring) > 1:
                    # Prefer business model sectors over technology sectors
                    business_model_matches = [s for s, _ in high_scoring if s in ['E-com', 'SaaS', 'Marketplace', 'B2B Fintech', 'B2C Fintech', 'B2C']]
                    if business_model_matches:
                        # Take the highest scoring business model sector
                        best_sector = max([(s, score) for s, score in high_scoring if s in business_model_matches], key=lambda x: x[1])
                        logger.info(f"Multiple high-scoring sectors found, selected business model: {best_sector[0]} (score: {best_sector[1]})")
                        return best_sector[0]
                
                # Return the highest scoring sector
                best_sector = max(sector_scores.items(), key=lambda x: x[1])
                logger.info(f"Sector classification: {best_sector[0]} (score: {best_sector[1]})")
                return best_sector[0]
            else:
                logger.info("No specific sector match found, defaulting to SaaS")
                return 'SaaS'
                
        except Exception as e:
            logger.error(f"Error in sector classification: {e}")
            return 'SaaS'  # Default fallback
    
    def _extract_company_description(self, extracted_data: Dict) -> str:
        """Extract a meaningful company description"""
        try:
            # Try to get description from business updates
            business_updates = extracted_data.get('business_updates', {})
            achievements = business_updates.get('achievements', [])
            
            if achievements:
                return f"Company focused on: {', '.join(achievements[:2])}"
            
            # Fallback to industry terms
            entities = extracted_data.get('extracted_entities', {})
            industry_terms = entities.get('industry_terms', [])
            
            if industry_terms:
                return f"Business in: {', '.join(industry_terms[:3])}"
            
            return "Business entity"
            
        except Exception as e:
            logger.error(f"Error extracting company description: {e}")
            return "Business entity"
    
    def _extract_business_model(self, extracted_data: Dict) -> str:
        """Extract business model information"""
        try:
            # Look for business model indicators in the data
            business_updates = extracted_data.get('business_updates', {})
            achievements = business_updates.get('achievements', [])
            
            # Check for B2B/B2C indicators
            text = ' '.join(achievements).lower()
            if any(term in text for term in ['b2b', 'enterprise', 'corporate']):
                return 'B2B'
            elif any(term in text for term in ['b2c', 'consumer', 'direct']):
                return 'B2C'
            
            return ''
            
        except Exception as e:
            logger.error(f"Error extracting business model: {e}")
            return ''
    
    def analyze_issues(self, extracted_text: str, extracted_data: Dict, doc_type: str) -> Dict:
        """Analyze document for issues and red flags"""
        try:
            prompt = self.issue_analysis_prompts.get(doc_type, self.issue_analysis_prompts['monthly_update'])
            
            context_text = f"""
{prompt}

Document text to analyze:
{extracted_text}

Extracted data context:
{json.dumps(extracted_data, indent=2)}
"""
            
            logger.info(f"Analyzing issues for {doc_type}")
            raw_response = self.call_claude_text_only(context_text)
            
            # Parse JSON response
            try:
                cleaned_response = raw_response.strip()
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    issue_analysis = json.loads(json_str)
                else:
                    issue_analysis = json.loads(cleaned_response)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Issue analysis JSON parsing failed: {e}")
                issue_analysis = {
                    "parsing_error": str(e),
                    "raw_analysis": raw_response,
                    "overall_sentiment": "unknown"
                }
            
            logger.info("Issue analysis completed")
            return issue_analysis
            
        except Exception as e:
            logger.error(f"Issue analysis failed: {e}")
            return {"error": str(e)}
    
    def save_results(self, filename: str, results: Dict) -> str:
        """Save all results to JSON file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"analysis_{filename.replace('.pdf', '')}_{timestamp}.json"
            
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Results saved to: {output_filename}")
            return output_filename
            
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            return None
    
    def save_intermediate_file(self, filename: str, content: str, suffix: str) -> str:
        """Save intermediate processing file for debugging (thread-safe)"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            thread_id = threading.current_thread().ident
            output_filename = f"{suffix}_{filename.replace('.pdf', '')}_{thread_id}_{timestamp}.md"
            
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Intermediate file saved: {output_filename}")
            return output_filename
            
        except Exception as e:
            logger.error(f"Failed to save intermediate file: {e}")
            return None
    
    def mark_as_processed(self, storage_path: str, job_id: str):
        """Mark file as processed in database"""
        try:
            url = f'{self.supabase_url}/rest/v1/processed_documents'
            payload = {
                'storage_path': storage_path,
                'job_id': job_id,
                'processed_at': datetime.utcnow().isoformat(),
                'status': 'completed'
            }
            
            response = requests.post(url, json=payload, headers=self.get_supabase_headers())
            
            if response.status_code in [200, 201]:
                logger.info(f"Marked {storage_path} as processed in Supabase")
            else:
                logger.warning(f"Failed to mark in Supabase, using local tracking")
                self.mark_as_processed_local(storage_path)
            
        except Exception as e:
            logger.error(f"Failed to mark as processed in Supabase: {e}")
            # Fallback to local tracking
            self.mark_as_processed_local(storage_path)
    
    def process_single_document(self, file_path: str = None) -> bool:
        """Run the complete pipeline on one document (thread-safe)"""
        try:
            sys.stderr.write(f"Processing document in thread {threading.current_thread().ident}\n")
            
            # If file_path is provided, process that specific file
            if file_path:
                # For direct file processing - check if it's a Supabase storage path
                if '/' in file_path and not os.path.exists(file_path):
                    # This is a Supabase storage path, download it first
                    logger.info(f"Downloading file from Supabase storage: {file_path}")
                    # Use the new method for downloading from storage paths
                    filename = os.path.basename(file_path)
                    pdf_content = self.download_file_from_storage_path(file_path)
                else:
                    # This is a local file path
                    filename = os.path.basename(file_path)
                    # Read file directly
                    with open(file_path, 'rb') as f:
                        pdf_content = f.read()
                
                storage_path = file_path  # Use the file path as storage path
                job_id = f"unified_{int(time.time())}"
                
            else:
                # Step 1: Get next unprocessed document from Supabase
                file_info = self.get_next_unprocessed_pdf()
                if not file_info:
                    logger.info("No documents to process")
                    return False
                
                filename = file_info['name']
                storage_path = f"{self.bucket_name}/{filename}"
                job_id = f"unified_{int(time.time())}"
                
                # Step 2: Download PDF
                logger.info("Step 1: Downloading PDF...")
                pdf_content = self.download_file(filename)
            
            logger.info("="*60)
            logger.info(f"PROCESSING: {filename}")
            logger.info("="*60)
            
            # Step 3: Classify document
            logger.info("Step 2: Classifying document...")
            doc_type, classification_details = self.classify_document(pdf_content, "", filename)
            
            # Step 4: Extract text using appropriate method
            logger.info("Step 3: Extracting text from PDF...")
            extracted_text = self.extract_text_from_pdf(pdf_content, doc_type, filename)
            
            # Save intermediate OCR result for debugging
            self.save_intermediate_file(filename, extracted_text, "raw_ocr")
            
            # Step 5: Re-classify with extracted text for better accuracy
            logger.info("Step 4: Re-classifying with extracted text...")
            doc_type, classification_details = self.classify_document(pdf_content, extracted_text, filename)
            
            # Step 6: Extract structured data
            logger.info("Step 5: Extracting structured data...")
            extracted_data = self.extract_structured_data(extracted_text, doc_type)
            
            # Step 7: Analyze issues
            logger.info("Step 6: Analyzing for issues...")
            issue_analysis = self.analyze_issues(extracted_text, extracted_data, doc_type)
            
            # Step 8: Find comparables and M&A data
            logger.info("Step 7: Finding comparable companies and M&A data...")
            comparables_analysis = self.run_comparables_analysis(extracted_data)
            
            # Step 9: Compile final results
            logger.info("Step 8: Compiling final results...")
            final_results = {
                'document_metadata': {
                    'filename': filename,
                    'processed_at': datetime.now().isoformat(),
                    'job_id': job_id,
                    'document_type': doc_type,
                    'classification_details': classification_details,
                    'thread_id': threading.current_thread().ident
                },
                'extracted_data': extracted_data,
                'issue_analysis': issue_analysis,
                'comparables_analysis': comparables_analysis,
                'processing_summary': {
                    'text_length': len(extracted_text),
                    'extraction_method': 'local' if doc_type in ['monthly_update', 'transcript'] else 'vision',
                    'classification_confidence': classification_details.get('confidence', 'unknown'),
                    'extraction_status': 'success' if 'error' not in extracted_data else 'partial',
                    'analysis_status': 'success' if 'error' not in issue_analysis else 'partial'
                },
                'raw_text_preview': extracted_text
            }
            
            # Step 10: Save results
            logger.info("Step 9: Saving results...")
            output_file = self.save_results(filename, final_results)
            
            # Step 11: Mark as processed (only for Supabase files)
            if not file_path:  # Only mark Supabase files as processed
                logger.info("Step 10: Marking as processed...")
                self.mark_as_processed(storage_path, job_id)
            
            logger.info("="*60)
            logger.info(f"COMPLETED: {filename}")
            logger.info(f"Output saved to: {output_file}")
            logger.info(f"Document type: {doc_type}")
            
            # Store results for API access
            self.processing_results = final_results
            self.processing_time = time.time()
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Always cleanup temp files
            self.cleanup()
    
    def run_continuous(self, max_documents: Optional[int] = None):
        """Run pipeline continuously"""
        processed_count = 0
        
        logger.info("Starting continuous document processing pipeline...")
        
        while True:
            try:
                if max_documents and processed_count >= max_documents:
                    logger.info(f"Reached maximum document limit: {max_documents}")
                    break
                
                success = self.process_single_document()
                if not success:
                    logger.info("No more documents to process")
                    break
                
                processed_count += 1
                logger.info(f"Pipeline completed {processed_count} documents")
                
                # Wait between documents
                time.sleep(10)
                
            except KeyboardInterrupt:
                logger.info("Stopping continuous processing...")
                break
            except Exception as e:
                logger.error(f"Error in continuous processing: {e}")
                time.sleep(30)
        
        logger.info(f"Pipeline finished. Total documents processed: {processed_count}")

    def get_processing_results(self) -> Dict:
        """Get the results from the last processing run"""
        if hasattr(self, 'processing_results'):
            return self.processing_results
        else:
            return {
                'success': False,
                'error': 'No processing results available'
            }

    def _clean_financial_data(self, extracted_data: Dict) -> Dict:
        """Clean and parse financial data to ensure numeric values"""
        if not extracted_data or 'financial_metrics' not in extracted_data:
            return extracted_data
        
        financial_metrics = extracted_data['financial_metrics']
        cleaned_metrics = {}
        
        for key, value in financial_metrics.items():
            if value is None:
                cleaned_metrics[key] = None
            elif isinstance(value, (int, float)):
                cleaned_metrics[key] = value
            elif isinstance(value, str):
                # Parse string values to numbers
                cleaned_value = self._parse_financial_string(value)
                cleaned_metrics[key] = cleaned_value
            else:
                cleaned_metrics[key] = None
        
        extracted_data['financial_metrics'] = cleaned_metrics
        
        # Also clean operational metrics
        if 'operational_metrics' in extracted_data:
            operational_metrics = extracted_data['operational_metrics']
            cleaned_operational = {}
            
            for key, value in operational_metrics.items():
                if value is None:
                    cleaned_operational[key] = None
                elif isinstance(value, (int, float)):
                    cleaned_operational[key] = value
                elif isinstance(value, str):
                    # Parse string values to numbers
                    cleaned_value = self._parse_financial_string(value)
                    cleaned_operational[key] = cleaned_value
                else:
                    cleaned_operational[key] = None
            
            extracted_data['operational_metrics'] = cleaned_operational
        
        return extracted_data
    
    def _parse_financial_string(self, value: str) -> Optional[float]:
        """Parse financial string values to numbers and convert to USD"""
        if not value or not isinstance(value, str):
            return None
        
        # Determine currency and conversion rate
        conversion_rate = 1.0  # Default to USD
        cleaned = value.strip()
        
        # Check for EUR and convert to USD
        if '€' in cleaned or 'EUR' in cleaned.upper():
            conversion_rate = 1.08  # EUR to USD
            cleaned = re.sub(r'^[€]\s*', '', cleaned)  # Remove € symbol
            cleaned = re.sub(r'^EUR\s*', '', cleaned, flags=re.IGNORECASE)  # Remove EUR prefix
        elif '£' in cleaned or 'GBP' in cleaned.upper():
            conversion_rate = 1.27  # GBP to USD
            cleaned = re.sub(r'^[£]\s*', '', cleaned)  # Remove £ symbol
            cleaned = re.sub(r'^GBP\s*', '', cleaned, flags=re.IGNORECASE)  # Remove GBP prefix
        else:
            # Remove USD symbols (no conversion needed)
            cleaned = re.sub(r'^[$]\s*', '', cleaned)  # Remove $ symbol
            cleaned = re.sub(r'^USD\s*', '', cleaned, flags=re.IGNORECASE)  # Remove USD prefix
        
        # Handle percentage values with context
        if '%' in cleaned:
            # Check if this is a burn rate percentage of revenue
            if 'revenue' in cleaned.lower() or 'burn' in cleaned.lower():
                # This is likely a burn rate as percentage of revenue
                # We can't calculate this without knowing the revenue amount
                # Return None and let the AI extraction handle it properly
                return None
            else:
                # Regular percentage - extract and convert to decimal
                match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
                if match:
                    return float(match.group(1)) / 100  # Convert to decimal
                return None
        
        # Handle ranges like "100-200"
        if '-' in cleaned and not cleaned.startswith('-'):
            parts = cleaned.split('-')
            if len(parts) == 2:
                try:
                    min_val = float(re.sub(r'[^\d.]', '', parts[0]))
                    max_val = float(re.sub(r'[^\d.]', '', parts[1]))
                    return (min_val + max_val) / 2  # Return average
                except (ValueError, TypeError):
                    pass
        
        # Handle K, M, B suffixes
        multiplier = 1
        if 'B' in cleaned.upper() or 'billion' in cleaned.lower():
            multiplier = 1000000000
        elif 'M' in cleaned.upper() or 'million' in cleaned.lower():
            multiplier = 1000000
        elif 'K' in cleaned.upper() or 'thousand' in cleaned.lower():
            multiplier = 1000
        
        # Extract numeric value
        match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', cleaned)
        if match:
            try:
                # Remove commas and convert to float
                numeric_str = match.group(1).replace(',', '')
                base_value = float(numeric_str) * multiplier
                # Apply currency conversion to USD
                return base_value * conversion_rate
            except (ValueError, TypeError):
                pass
        
        return None


# ============================================================================
# THREAD PROCESSOR CLASS (NEW)
# ============================================================================

class ThreadSafeDocumentProcessor:
    def __init__(self, max_workers=2, rate_limit_delay=20):
        """
        max_workers: Number of concurrent threads (start with 2-3)
        rate_limit_delay: Seconds between API calls to avoid rate limits
        """
        self.max_workers = max_workers
        self.rate_limit_delay = rate_limit_delay
        self.results = {}
        self.lock = threading.Lock()
        
        # Setup logging (already configured at module level, just get logger)
        self.logger = logging.getLogger(__name__)
    
    def process_single_document_safe(self, file_path: str, task_id: str):
        """Process a single document in thread-safe manner"""
        thread_id = threading.current_thread().ident
        self.logger.info(f"Thread {thread_id}: Starting processing {task_id}")
        
        try:
            # Create pipeline instance for this thread
            pipeline = FullFlowNoCompPipeline()
            
            # Process the document
            results = pipeline.process_single_document(file_path)
            
            # Thread-safe result storage
            with self.lock:
                self.results[task_id] = {
                    'status': 'completed',
                    'file_path': file_path,
                    'results': results,
                    'processed_at': time.time(),
                    'thread_id': thread_id
                }
            
            self.logger.info(f"Thread {thread_id}: Completed {task_id}")
            return results
            
        except Exception as e:
            self.logger.error(f"Thread {thread_id}: Error processing {task_id}: {e}")
            
            with self.lock:
                self.results[task_id] = {
                    'status': 'error',
                    'file_path': file_path,
        'error': str(e),
                    'processed_at': time.time(),
                    'thread_id': thread_id
                }
            raise
    
    def process_batch(self, file_paths: list):
        """Process multiple files concurrently"""
        self.logger.info(f"Starting batch processing of {len(file_paths)} files with {self.max_workers} workers")
        
        # Generate unique task IDs
        task_info = {}
        for i, file_path in enumerate(file_paths):
            task_id = f"task_{uuid.uuid4().hex[:8]}_{i}"
            task_info[task_id] = file_path
        
        # Process with ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.process_single_document_safe, file_path, task_id): task_id
                for task_id, file_path in task_info.items()
            }
            
            # Wait for completion
            completed = 0
            total = len(future_to_task)
            
            for future in concurrent.futures.as_completed(future_to_task):
                task_id = future_to_task[future]
                completed += 1
                
                try:
                    future.result()  # This will raise exception if task failed
                    self.logger.info(f"Progress: {completed}/{total} - Completed {task_id}")
                except Exception as e:
                    self.logger.error(f"Progress: {completed}/{total} - Failed {task_id}: {e}")
        
        self.logger.info(f"Batch processing complete. Processed {len(self.results)} files")
        return self.results.copy()
    
    def get_results(self):
        """Get all processing results"""
        with self.lock:
            return self.results.copy()
    
    def get_status_summary(self):
        """Get summary of processing status"""
        with self.lock:
            summary = {'completed': 0, 'error': 0, 'total': len(self.results)}
            for result in self.results.values():
                summary[result['status']] += 1
            return summary


def process_file_for_api(file_path: str, document_id: str = None, document_type: str = None) -> Dict:
    """Process a single file and return JSON results for API"""
    try:
        pipeline = FullFlowNoCompPipeline()
        
        # Process the document
        success = pipeline.process_single_document(file_path)
        
        if success:
            # Get the results from the pipeline
            results = pipeline.get_processing_results()
            
            # Add metadata
            results['document_id'] = document_id
            results['document_type'] = document_type
            results['processing_time'] = getattr(pipeline, 'processing_time', 'unknown')
            results['success'] = True
            
            # Update database with results if document_id is provided
            if document_id:
                try:
                    # Update the database with the processing results
                    supabase_url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
                    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
                    
                    if supabase_url and supabase_key:
                        import requests
                        
                        # Prepare the update data - match exact Supabase column names
                        extracted_data = results.get('extracted_data', {})
                        # Remove sector_classification if it exists (not in database schema)
                        if 'sector_classification' in extracted_data:
                            del extracted_data['sector_classification']
                        
                        update_data = {
                            'status': 'completed',
                            'processed_at': datetime.utcnow().isoformat(),
                            'document_type': results.get('document_metadata', {}).get('document_type', 'unknown'),
                            'classification_details': results.get('document_metadata', {}).get('classification_details', {}),
                            'extracted_data': extracted_data,
                            'issue_analysis': results.get('issue_analysis', {}),
                            'comparables_analysis': results.get('comparables_analysis', {}),
                            'processing_summary': results.get('processing_summary', {}),
                            'raw_text_preview': results.get('raw_text_preview', '')
                        }
                        
                        sys.stderr.write(f"Updating database for document {document_id} with data: {json.dumps(update_data, indent=2)}\n")
                        
                        # Update the database - use 'processed_documents' table
                        response = requests.patch(
                            f"{supabase_url}/rest/v1/processed_documents?id=eq.{document_id}",
                            headers={
                                'apikey': supabase_key,
                                'Authorization': f'Bearer {supabase_key}',
                                'Content-Type': 'application/json',
                                'Prefer': 'return=minimal'
                            },
                            json=update_data
                        )
                        
                        sys.stderr.write(f"Database update response: {response.status_code} - {response.text}\n")
                        
                        if response.status_code in [200, 204]:
                            sys.stderr.write(f"Database updated successfully for document {document_id}\n")
                        else:
                            sys.stderr.write(f"Failed to update database: {response.status_code} - {response.text}\n")
                            sys.stderr.write(f"Request URL: {supabase_url}/rest/v1/processed_documents?id=eq.{document_id}\n")
                            sys.stderr.write(f"Request headers: {headers}\n")
                            sys.stderr.write(f"Request data keys: {list(update_data.keys())}\n")
                            
                except Exception as e:
                    sys.stderr.write(f"Error updating database: {e}\n")
                    import traceback
                    traceback.print_exc()
            
            # Output JSON for API consumption (only the JSON, no extra logging)
            json_output = json.dumps(results, indent=2)
            print(json_output)
            return results
        else:
            error_result = {
                'success': False,
                'error': 'Document processing failed',
                'document_id': document_id,
                'document_type': document_type
            }
            print(json.dumps(error_result, indent=2))
            return error_result
            
    except Exception as e:
        error_result = {
            'success': False,
                'error': str(e),
            'document_id': document_id,
            'document_type': document_type
        }
        print(json.dumps(error_result, indent=2))
        return error_result

def main():
    """Main function"""
    try:
        # Check if we're being called from the API with specific arguments
        if len(sys.argv) > 1 and sys.argv[1] == "--process-file":
            if len(sys.argv) >= 4:
                file_path = sys.argv[2]
                document_id = sys.argv[3]
                document_type = sys.argv[4] if len(sys.argv) > 4 else 'other'
                
                # Process for API
                process_file_for_api(file_path, document_id, document_type)
                return
            else:
                sys.stderr.write("Usage: python full_flow_no_comp.py --process-file <file_path> <document_id> [document_type]\n")
                sys.exit(1) 
        
        # Check if we're being called from the API (legacy format)
        if len(sys.argv) > 1 and sys.argv[1] == "--file":
            if len(sys.argv) > 2:
                file_path = sys.argv[2]
                document_id = os.environ.get('DOCUMENT_ID')
                document_type = os.environ.get('DOCUMENT_TYPE', 'other')
                
                # Process for API
                process_file_for_api(file_path, document_id, document_type)
                return
            else:
                sys.stderr.write("Usage: python full_flow_no_comp.py --file <path_to_pdf>\n")
                sys.exit(1)
        
        pipeline = FullFlowNoCompPipeline()
        
        if len(sys.argv) > 1:
            if sys.argv[1] == "--single":
                pipeline.process_single_document()
            elif sys.argv[1] == "--continuous":
                max_docs = int(sys.argv[2]) if len(sys.argv) > 2 else None
                pipeline.run_continuous(max_documents=max_docs)
            elif sys.argv[1] == "--batch":
                # Example batch processing
                if len(sys.argv) > 2:
                    max_workers = int(sys.argv[2])
                else:
                    max_workers = 2
                
                # Get list of PDF files to process
                import glob
                pdf_files = glob.glob("*.pdf")
                
                if pdf_files:
                    processor = ThreadSafeDocumentProcessor(max_workers=max_workers)
                    results = processor.process_batch(pdf_files)
                    
                    sys.stderr.write("\n=== BATCH PROCESSING COMPLETE ===\n")
                    summary = processor.get_status_summary()
                    sys.stderr.write(f"Summary: {summary}\n")
                else:
                    sys.stderr.write("No PDF files found in current directory\n")
            else:
                sys.stderr.write("Usage: python full_flow_no_comp.py [--single|--continuous [max_count]|--file <path>|--process-file <path> <id> [type]|--batch [workers]]\n")
                sys.exit(1)
        else:
            pipeline.process_single_document()
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()