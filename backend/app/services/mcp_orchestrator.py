"""
MCP Orchestrator - Manages Tavily and Firecrawl API calls
Recreated from usage patterns in unified_mcp_orchestrator.py
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


# Enums for task and tool types
class TaskType(str, Enum):
    """Types of tasks in the system"""
    RESEARCH = "research"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    EXTRACTION = "extraction"
    VALIDATION = "validation"


class ToolType(str, Enum):
    """Available MCP tools"""
    TAVILY = "tavily"
    FIRECRAWL = "firecrawl"
    CLAUDE = "claude"
    DATABASE = "database"
    GITHUB = "github"


@dataclass
class Task:
    """Represents a single task in an execution plan"""
    id: str
    type: TaskType
    tool: ToolType
    description: str
    parameters: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, running, completed, failed
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Execution plan for a decomposed prompt"""
    prompt: str
    tasks: List[Task]
    dependencies: Dict[str, List[str]]
    metadata: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class PromptDecomposer:
    """
    Decomposes prompts into executable tasks using Claude
    This was the sophisticated orchestration that made everything work
    """
    
    def __init__(self):
        self.task_counter = 0
        # Import here to avoid circular dependency
        try:
            from app.services.model_router import get_model_router, ModelCapability
            self.model_router = get_model_router()
            self.model_capability = ModelCapability.ANALYSIS
        except:
            logger.warning("Model router not available for PromptDecomposer")
            self.model_router = None
    
    async def decompose(self, prompt: str, context: Optional[Dict] = None) -> ExecutionPlan:
        """
        Decompose a prompt into an execution plan using Claude
        This creates the skill chain that coordinates everything
        """
        if not self.model_router:
            # Fallback to basic decomposition
            return self._basic_decompose(prompt, context)
        
        # Claude prompt to decompose and build skill chain
        decomposition_prompt = f"""Analyze this VC investment request and decompose it into specific data gathering tasks.

Request: {prompt}

Break this down into specific tasks that need to be executed. For each task, specify:
1. What data needs to be gathered
2. Which tool to use (tavily for search, tavily_extract for website scraping)
3. What specific information to extract

Return a JSON array of tasks:
[
  {
    "id": "task_0",
    "type": "research",
    "tool": "tavily",
    "description": "Search for company information",
    "parameters": {
      "query": "specific search query",
      "search_depth": "advanced",
      "include_raw_content": true
    },
    "extract": ["funding", "revenue", "team_size", "customers"]
  }
]

Focus on getting:
- Funding history with dates and amounts
- Customer names and logos
- Team size and composition
- Revenue and growth metrics
- Pricing information
"""
        
        try:
            # Use model router to decompose
            result = await self.model_router.get_completion(
                prompt=decomposition_prompt,
                capability=self.model_capability,
                max_tokens=2000,
                temperature=0.3,
                preferred_models=["claude-sonnet-4-5"]  # Prefer Claude but allow fallback
            )
            response_text = result["response"]
            
            # Parse JSON from response
            import json
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                tasks_data = json.loads(json_match.group())
                
                tasks = []
                for task_data in tasks_data:
                    task = Task(
                        id=task_data.get('id', f"task_{self.task_counter}"),
                        type=TaskType(task_data.get('type', 'research')),
                        tool=ToolType(task_data.get('tool', 'tavily')),
                        description=task_data.get('description', ''),
                        parameters=task_data.get('parameters', {}),
                        dependencies=task_data.get('dependencies', [])
                    )
                    tasks.append(task)
                    self.task_counter += 1
                
                # Build dependency graph
                dependencies = {}
                for task in tasks:
                    if task.dependencies:
                        dependencies[task.id] = task.dependencies
                
                return ExecutionPlan(
                    prompt=prompt,
                    tasks=tasks,
                    dependencies=dependencies,
                    metadata=context or {}
                )
        except Exception as e:
            logger.error(f"Claude decomposition failed: {e}")
        
        # Fallback to basic
        return self._basic_decompose(prompt, context)
    
    def _basic_decompose(self, prompt: str, context: Optional[Dict] = None) -> ExecutionPlan:
        """Basic fallback decomposition without Claude"""
        tasks = []
        
        # Extract company names
        import re
        companies = re.findall(r'@(\w+)', prompt)
        
        for company in companies:
            # Create parallel tasks for each company
            base_id = self.task_counter
            
            # General search
            tasks.append(Task(
                id=f"task_{base_id}_general",
                type=TaskType.RESEARCH,
                tool=ToolType.TAVILY,
                description=f"General search for {company}",
                parameters={
                    "query": f"{company} startup company",
                    "search_depth": "advanced",
                    "max_results": 10,
                    "include_raw_content": True
                }
            ))
            
            # Funding search
            tasks.append(Task(
                id=f"task_{base_id}_funding",
                type=TaskType.RESEARCH,
                tool=ToolType.TAVILY,
                description=f"Funding search for {company}",
                parameters={
                    "query": f"{company} raised seed series million funding",
                    "search_depth": "advanced",
                    "max_results": 10,
                    "include_raw_content": True
                }
            ))
            
            self.task_counter += 1
        
        return ExecutionPlan(
            prompt=prompt,
            tasks=tasks,
            dependencies={},
            metadata=context or {}
        )


class StructuredDataExtractor:
    """
    Claude-based structured data extraction from raw HTML
    This was the sophisticated extraction that made everything work
    """
    
    def __init__(self):
        try:
            from app.services.model_router import get_model_router, ModelCapability
            self.model_router = get_model_router()
            self.model_capability = ModelCapability.ANALYSIS
        except:
            logger.warning("Model router not available for extraction")
            self.model_router = None
    
    async def extract_structured_data_from_parsed(self, parsed_data: Dict, company_name: str) -> Dict[str, Any]:
        """
        Structure pre-parsed data using Claude - much more accurate
        """
        if not self.model_router:
            return {}
        
        extraction_prompt = f"""Structure this ACTUAL extracted data for {company_name}:

ACTUAL Customers (from img alt tags): {parsed_data.get('customers', [])[:20]}
ACTUAL Investors (from funding articles): {parsed_data.get('investors', [])}
ACTUAL Pricing: {parsed_data.get('pricing', {})}
ACTUAL Team: {parsed_data.get('team', {})}
ACTUAL Product: {parsed_data.get('product', {})}
BUSINESS CONTEXT (first 2000 chars of content): {parsed_data.get('business_context', '')}

Task: Convert this REAL data into structured format. DO NOT make up data.

CRITICAL BUSINESS MODEL ANALYSIS:
Analyze the business_context to determine the company's business model. Look for:
- Recurring revenue language ("SaaS", "subscription", "per month")
- Marketplace indicators ("buyers and sellers", "two-sided", "platform")
- Roll-up patterns ("acquiring", "consolidating", "portfolio of brands")
- API/Developer focus ("API", "developers", "integration", "SDK")
- Services language ("agency", "consulting", "managed services")
- Hardware mentions ("device", "hardware", "IoT")

Business Model Categories:
- "Traditional SaaS": Pure recurring software (e.g., CRM, project management)
- "AI SaaS": AI-powered software platform (e.g., AI research tools, AI analytics)
- "Roll-up Model": Acquiring/consolidating businesses (e.g., acquiring agencies)
- "Marketplace": Two-sided platform with network effects
- "API/Infrastructure": Developer tools, usage-based pricing
- "Services with Tech": Tech-enabled services/agency model
- "Hardware + Software": Integrated hardware/software solution

CRITICAL FUNDING EXTRACTION WITH CURRENCY CONVERSION:
- Extract ANY funding amount with ANY currency symbol (£, €, $, ¥, ₹, etc.)
- CONVERT TO USD IMMEDIATELY:
  * £ (GBP) → multiply by 1.25
  * € (EUR) → multiply by 1.10  
  * ¥ (JPY) → divide by 150
  * ₹ (INR) → divide by 83
  * Default to USD if no symbol
- Examples to extract and convert:
  * "raised £8.5 million" → amount: 10625000 (8.5 * 1.25 * 1000000)
  * "€10M funding" → amount: 11000000 (10 * 1.10 * 1000000)
  * "$5 million Series A" → amount: 5000000 (already USD)

CRITICAL DATE EXTRACTION:
- Search for funding dates in the text: "raised in 2025", "March 2025", "announced today", "last year"
- Convert relative dates: "today" = "2025-09", "last year" = "2024", "Q1 2025" = "2025-01"
- Look for patterns: "raised £X in [DATE]", "[DATE] funding round", "closed [ROUND] in [DATE]"

1. For customers: Identify which are enterprise (Fortune 500, large companies) vs SMB
2. For pricing: Extract numeric amounts from strings like "$99/month"
3. For investors: First name in list is usually lead investor
4. For team: Parse founder names and employee count
5. For business model: Analyze the business_context to categorize accurately

Return structured data for IntelligentGapFiller. Format EXACTLY as:
{{
  "funding_analysis": {{
    "rounds": [
      {{
        "date": "YYYY-MM-DD" format ONLY (e.g., "2024-08-15" for August 15, 2024)
                 - If only month/year: use "YYYY-MM-01" (e.g., "2024-08-01" for August 2024)
                 - If only year: use "YYYY-01-01" (e.g., "2024-01-01" for 2024)
                 - Extract from text like "raised in August 2024" → "2024-08-01",
        "amount": numeric_value,
        "round": "Seed" or "Series A" etc,
        "investors": [list of investor names],
        "valuation": numeric_value or null
      }}
    ],
    "total_raised": sum_of_all_rounds,
    "current_stage": "latest round type"
  }},
  "company_basics": {{
    "headquarters_location": "San Francisco" or city from data,
    "founded_year": year or null,
    "industry": "SaaS" or sector
  }},
  "customers": {{
    "list": [actual customer names],
    "enterprise": [Fortune 500/large companies],
    "count": total_number
  }},
  "metrics": {{
    "employees": number from team data or 0,
    "revenue": extract from pricing if possible or 0,
    "burn_rate": 0,  // Will be inferred by IntelligentGapFiller
    "growth_rate": 0  // Will be inferred
  }},
  "pricing": {{
    "has_pricing": true/false,
    "enterprise_motion": true if "Contact Sales",
    "lowest_tier": numeric or 0,
    "model": "per-seat" or "usage" or "enterprise"
  }},
  "business_model": "Describe EXACTLY what they do: 'Automates legal document review using LLMs' or 'Manages restaurant inventory with predictive ordering'",
  "category": "ai_first" or "ai_saas" or "saas" or "marketplace" or "services" or "rollup" or "hardware",
  "vertical": "Healthcare" or "Legal Tech" or "FinTech" or "Developer Tools" or other specific industry,
  "compute_intensity": "high" or "medium" or "low",
  "careers": careers data if exists
}}"""
        
        try:
            result = await self.model_router.get_completion(
                prompt=extraction_prompt,
                capability=self.model_capability,
                max_tokens=2000,
                preferred_models=["claude-sonnet-4-5"]  # Prefer Claude but allow fallback
            )
            response_text = result["response"]
            
            # Extract JSON from response
            import json
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to structure parsed data: {e}")
            return {}
    
    async def extract_structured_data(self, raw_html: str, company_name: str) -> Dict[str, Any]:
        """
        Extract comprehensive structured data from raw HTML using Claude
        This connects Tavily searches to IntelligentGapFiller requirements
        """
        if not self.model_router or not raw_html:
            return {}
        
        extraction_prompt = f"""Extract structured data for {company_name} from this HTML content.

CRITICAL: Extract ALL of the following if present:

1. COMPANY BASICS (CRITICAL for geographic adjustments):
   - headquarters_location: Extract city name (e.g., "San Francisco", "NYC", "London", "Berlin", "Singapore")
   - founded_year: Year company was founded
   - current_stage: Company stage (Pre-Seed, Seed, Series A, etc)
   - industry: Main industry/sector

2. FUNDING HISTORY (MOST IMPORTANT - needed for IntelligentGapFiller):
   - Each round with: date (YYYY-MM-DD format), amount ($X million), round type (Seed, Series A, etc)
   - investors: EXTRACT ALL INVESTOR NAMES (e.g., "Sequoia Capital", "Andreessen Horowitz", "Accel", "Y Combinator")
   - Total raised to date
   - Last round details (amount, date, lead investor)
   - Valuation if mentioned

3. TEAM COMPOSITION (EXTRACT EVERY PERSON AND TITLE):
   - Total employee count (critical for burn estimation)
   - ALL employees with titles (extract from team pages, about us, LinkedIn links)
   - Engineering team: List every engineer with title (Senior/Staff/Principal/Junior)
   - Sales team: All sales people with titles (AE, SDR, VP Sales, etc)
   - Marketing team: All marketing people with titles
   - Product team: PMs, designers with titles
   - Founders with full backgrounds (previous companies, universities, expertise)
   - C-suite executives with backgrounds (CEO, CTO, CFO, COO, CPO, CMO)
   - Board members and advisors
   - Seniority breakdown by counting titles (Senior=5+ years, Mid=2-5, Junior=0-2)
   - Open positions by department and seniority level

3. PRODUCT DETAILS:
   - Core product description
   - Key features and capabilities
   - Tech stack (languages, frameworks, infrastructure)
   - API availability
   - Integrations with other tools
   - Mobile apps (iOS, Android)
   - Target market/ICP

4. PRICING STRUCTURE (for revenue inference):
   - Pricing tiers with exact prices
   - Pricing model (per-seat, usage-based, flat rate)
   - Free tier details
   - Enterprise pricing ("Contact Sales" = enterprise motion)
   - Billing periods (monthly vs annual)
   - Key features by tier

5. CUSTOMER DATA (CRITICAL - EXTRACT FROM IMG ALT TEXT):
   - Customer logos from <img alt="CompanyName"> tags (THIS IS WHERE LOGOS ARE!)
   - Extract EVERY img tag's alt attribute that could be a company name
   - Look for logo sections, "trusted by", "our customers" sections
   - Customer count if mentioned ("500+ customers", "trusted by 1000 companies")
   - Notable enterprise customers (Fortune 500, large companies)
   - Case studies with specific results/ROI metrics
   - Testimonials with full attribution (name, title, company)
   - Industry verticals served (Financial Services, Healthcare, etc)

6. GROWTH SIGNALS & HIRING (CHECK CAREERS/JOBS PAGE):
   - ALL job openings with titles and departments (from careers page)
   - Seniority of open roles (Senior, Staff, Principal, Manager, Director, VP)
   - Engineering roles vs sales roles ratio (indicates product vs GTM focus)
   - Remote vs office requirements
   - Revenue if mentioned (ARR, MRR, "10M ARR", "$100M revenue")
   - Growth rate or metrics ("3x growth", "200% YoY")
   - User count ("1 million users", "10,000 customers")
   - Market expansion (new geos, products, verticals)
   - Recent product launches or major features
   - Press coverage and funding announcements

7. COMPETITIVE POSITION:
   - Competitors mentioned
   - Differentiation points
   - Market positioning
   - Awards or recognition

HTML Content:
{raw_html[:15000]}

CRITICAL FORMATTING RULES:
1. ALL numeric values MUST be returned as numbers, NOT strings
2. Convert all amounts to raw numbers (e.g., "$10M" becomes 10000000)
3. Convert all percentages to decimals (e.g., "85%" becomes 0.85)
4. Dates should be in "YYYY-MM-DD" format as strings
5. Arrays should contain actual values, not descriptions
6. If a value is unknown, use 0 for numbers, empty string for text, empty array for lists

Return ONLY a JSON object where funding.rounds EXACTLY matches this format for IntelligentGapFiller:
{{
  "company_basics": {{
    "headquarters_location": "San Francisco",  // Or "NYC", "London", "Berlin", "Singapore", etc
    "founded_year": 2020,
    "current_stage": "Series A",  // Or "Pre-Seed", "Seed", etc
    "industry": "SaaS"
  }},
  "funding": {{
    "rounds": [
      {{"date": "2023-06-15", "amount": 20000000, "round": "Series A", "investors": ["Sequoia", "Accel"], "valuation": 100000000}},
      {{"date": "2022-03-10", "amount": 5000000, "round": "Seed", "investors": ["Y Combinator", "Angel"], "valuation": 20000000}}
    ],
    "total_raised": 25000000,
    "last_round": "Series A",
    "last_round_date": "2023-06-15", 
    "last_round_amount": 20000000,
    "current_valuation": 100000000
  }},
  "team": {{
    "total_employees": 45,
    "all_employees": [
      {{"name": "John Doe", "title": "Senior Software Engineer", "department": "Engineering"}},
      {{"name": "Jane Smith", "title": "VP Sales", "department": "Sales"}}
    ],
    "engineering_team": [
      {{"name": "Alice Chen", "title": "Staff Engineer", "seniority": "senior"}},
      {{"name": "Bob Wilson", "title": "Junior Developer", "seniority": "junior"}}
    ],
    "sales_team": [
      {{"name": "Sarah Lee", "title": "Account Executive", "seniority": "mid"}}
    ],
    "marketing_team": [
      {{"name": "Mike Brown", "title": "Growth Marketing Manager", "seniority": "mid"}}
    ],
    "product_team": [
      {{"name": "Lisa Zhang", "title": "Senior PM", "seniority": "senior"}}
    ],
    "founders": [
      {{"name": "Tom Anderson", "role": "CEO", "background": "Previously founder at DataCo (acquired), Stanford CS"}}
    ],
    "executives": [
      {{"name": "Emma Davis", "role": "CTO", "background": "Ex-Google L7, MIT PhD"}}
    ],
    "board_advisors": [
      {{"name": "Jim Partner", "role": "Board Member", "background": "Partner at Sequoia"}}
    ],
    "seniority_breakdown": {{
      "senior": 15,
      "mid": 20,
      "junior": 10
    }},
    "open_positions": [
      {{"title": "Senior Backend Engineer", "department": "Engineering", "location": "Remote"}},
      {{"title": "Enterprise AE", "department": "Sales", "location": "SF"}}
    ],
    "hiring_velocity": "high"
  }},
  "product": {{
    "description": "...",
    "key_features": ["feature1", "feature2"],
    "tech_stack": ["Python", "React", "AWS"],
    "has_api": true,
    "integrations": ["Slack", "Salesforce"],
    "mobile_apps": ["iOS", "Android"],
    "target_market": "B2B SaaS"
  }},
  "pricing": {{
    "model": "per-seat",
    "tiers": [
      {{"name": "Starter", "price": 29, "period": "month", "features": ["X", "Y"]}}
    ],
    "has_free_tier": true,
    "has_enterprise": true,
    "annual_discount": 0.20
  }},
  "customers": {{
    "logos": ["Company1", "Company2"],
    "count": 500,
    "notable_enterprise": ["Fortune500Co"],
    "verticals": ["Finance", "Healthcare"],
    "case_studies": [
      {{"customer": "Acme Corp", "result": "50% reduction in costs"}}
    ]
  }},
  "metrics": {{
    "revenue_arr": 10000000,
    "user_count": 50000
  }},
  "competitive": {{
    "competitors": ["Competitor1", "Competitor2"],
    "differentiators": ["First to market", "Best UX"],
    "awards": ["Best Startup 2024"]
  }}
}}

Extract ONLY verifiable information from the HTML. Use null for missing fields."""
        
        try:
            result = await self.model_router.get_completion(
                prompt=extraction_prompt,
                capability=self.model_capability,
                max_tokens=4000,
                temperature=0.1,  # Low temperature for accuracy
                preferred_models=["claude-sonnet-4-5"]  # Prefer Claude but allow fallback
            )
            response_text = result["response"]
            
            # Parse JSON from response
            import json
            import re
            
            # Log first 200 chars to debug
            logger.debug(f"Claude response for {company_name} (first 200 chars): {response_text[:200]}")
            
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                # Clean up common issues
                # Remove JavaScript-style comments
                json_str = re.sub(r'//.*?(?=\n|$)', '', json_str)
                # Remove trailing commas before closing braces/brackets
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                
                try:
                    extracted_data = json.loads(json_str)
                    logger.info(f"Extracted structured data for {company_name}: {len(extracted_data)} fields")
                    # Log what we actually extracted
                    logger.info(f"Extracted data: business_model={extracted_data.get('business_model', 'MISSING')}, "
                               f"funding={extracted_data.get('funding', {}).get('total_raised', 0)}, "
                               f"team_size={extracted_data.get('team', {}).get('total_count', 0)}")
                    return extracted_data
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error at position {e.pos}: {e}")
                    logger.error(f"JSON string around error: ...{json_str[max(0, e.pos-20):min(len(json_str), e.pos+20)]}...")
                    # Try one more time with aggressive cleaning
                    json_str = re.sub(r'[\x00-\x1f]', '', json_str)  # Remove control chars
                    try:
                        extracted_data = json.loads(json_str)
                        logger.info(f"Extracted after aggressive cleaning")
                        return extracted_data
                    except:
                        pass
                
        except Exception as e:
            logger.error(f"Claude extraction failed for {company_name}: {e}")
        
        return {}


class MCPToolExecutor:
    """
    Executes MCP tool calls - Tavily and Firecrawl APIs
    This is the core class that makes actual API calls
    """

    _firecrawl_warning_emitted = False

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Strip any whitespace from API keys
        self.tavily_api_key = settings.TAVILY_API_KEY.strip() if settings.TAVILY_API_KEY else None
        self.firecrawl_api_key = settings.FIRECRAWL_API_KEY.strip() if settings.FIRECRAWL_API_KEY else None

        if not self.tavily_api_key:
            logger.warning("TAVILY_API_KEY not set in environment")
        if not self.firecrawl_api_key and not MCPToolExecutor._firecrawl_warning_emitted:
            logger.debug("FIRECRAWL_API_KEY not set; Firecrawl tasks will be skipped")
            MCPToolExecutor._firecrawl_warning_emitted = True
    
    async def __aenter__(self):
        """Async context manager entry"""
        # Create session with default timeout
        timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def execute_tavily(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Tavily search API call
        
        Parameters:
        - query: Search query string
        - search_depth: "basic" or "advanced" (default: "basic")
        - max_results: Number of results (default: 5)
        - include_raw_content: Include raw HTML (default: False)
        - include_domains: List of domains to specifically include
        - exclude_domains: List of domains to exclude
        """
        if not self.tavily_api_key:
            logger.error("TAVILY_API_KEY not configured")
            return {
                "success": False,
                "error": "TAVILY_API_KEY not configured",
                "data": {"results": []}
            }
        
        # Ensure we have a session with timeout
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        
        try:
            headers = {
                "Authorization": f"Bearer {self.tavily_api_key}",
                "Content-Type": "application/json"
            }
            
            # Build request payload
            payload = {
                "query": params.get("query", ""),
                "search_depth": params.get("search_depth", "basic"),
                "max_results": params.get("max_results", 5),
                "include_raw_content": params.get("include_raw_content", False),
                "include_answer": params.get("include_answer", False),
                "include_images": params.get("include_images", False),
            }
            
            # Add domain filters if provided
            if params.get("include_domains"):
                payload["include_domains"] = params.get("include_domains", [])
            if params.get("exclude_domains"):
                payload["exclude_domains"] = params.get("exclude_domains", [])
            
            logger.info(f"Executing Tavily search: {payload['query'][:100]}...")
            
            # Add timeout for Tavily API calls (10 seconds)
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with self.session.post(
                "https://api.tavily.com/search",
                json=payload,
                headers=headers,
                timeout=timeout
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    logger.info(f"Tavily search successful: {len(data.get('results', []))} results")
                    return {
                        "success": True,
                        "data": data
                    }
                else:
                    logger.error(f"Tavily API error: {response.status} - {data}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status}",
                        "data": data
                    }
        
        except Exception as e:
            logger.error(f"Tavily execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {"results": []}
            }
    
    async def execute_tavily_extract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Tavily Extract API call for website content extraction
        
        Parameters:
        - urls: List of URLs to extract content from
        """
        if not self.tavily_api_key:
            logger.error("TAVILY_API_KEY not configured")
            return {
                "success": False,
                "error": "TAVILY_API_KEY not configured",
                "data": {"results": []}
            }
        
        # Ensure we have a session with timeout
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        
        try:
            headers = {
                "Authorization": f"Bearer {self.tavily_api_key}",
                "Content-Type": "application/json"
            }
            
            # Build request payload
            payload = {
                "urls": params.get("urls", [])
            }
            
            logger.info(f"Executing Tavily Extract for {len(payload['urls'])} URLs")
            
            async with self.session.post(
                "https://api.tavily.com/extract",
                json=payload,
                headers=headers
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    logger.info(f"Tavily Extract successful")
                    return {
                        "success": True,
                        "data": data
                    }
                else:
                    logger.error(f"Tavily Extract API error: {response.status} - {data}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status}",
                        "data": data
                    }
        
        except Exception as e:
            logger.error(f"Tavily Extract execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {"results": []}
            }
    
    async def execute_firecrawl(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Firecrawl API call for advanced web scraping
        
        Parameters:
        - url: URL to scrape
        - formats: List of formats (markdown, html, rawHtml, links)
        """
        if not self.firecrawl_api_key:
            logger.error("FIRECRAWL_API_KEY not configured")
            return {
                "success": False,
                "error": "FIRECRAWL_API_KEY not configured",
                "data": {}
            }
        
        # Ensure we have a session with timeout
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        
        try:
            headers = {
                "Authorization": f"Bearer {self.firecrawl_api_key}",
                "Content-Type": "application/json"
            }
            
            # Build request payload
            payload = {
                "url": params.get("url", ""),
                "formats": params.get("formats", ["markdown", "html"])
            }
            
            logger.info(f"Executing Firecrawl scrape: {payload['url']}")
            
            async with self.session.post(
                "https://api.firecrawl.dev/v0/scrape",
                json=payload,
                headers=headers
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    logger.info(f"Firecrawl scrape successful")
                    return {
                        "success": True,
                        "data": data
                    }
                else:
                    logger.error(f"Firecrawl API error: {response.status} - {data}")
                    return {
                        "success": False,
                        "error": f"API error: {response.status}",
                        "data": data
                    }
        
        except Exception as e:
            logger.error(f"Firecrawl execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    async def execute_github_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute GitHub API calls to get repository stats
        
        Parameters:
        - org: Organization or username
        - repo: Repository name (optional, gets org stats if not provided)
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            org = params.get("org", "")
            repo = params.get("repo", "")
            
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Dilla-VC-Analysis"
            }
            
            # Add token if available
            github_token = settings.GITHUB_TOKEN if hasattr(settings, 'GITHUB_TOKEN') else None
            if github_token:
                headers["Authorization"] = f"token {github_token}"
            
            result = {
                "success": True,
                "data": {}
            }
            
            # Get repository data
            if repo:
                url = f"https://api.github.com/repos/{org}/{repo}"
            else:
                # Get org repos
                url = f"https://api.github.com/orgs/{org}/repos"
            
            logger.info(f"Fetching GitHub data: {url}")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if repo:
                        # Single repo stats
                        result["data"] = {
                            "stars": data.get("stargazers_count", 0),
                            "forks": data.get("forks_count", 0),
                            "watchers": data.get("watchers_count", 0),
                            "open_issues": data.get("open_issues_count", 0),
                            "language": data.get("language", ""),
                            "created_at": data.get("created_at", ""),
                            "updated_at": data.get("updated_at", ""),
                            "description": data.get("description", ""),
                            "topics": data.get("topics", []),
                            "license": data.get("license", {}).get("name", "") if data.get("license") else "",
                            "default_branch": data.get("default_branch", "main")
                        }
                        
                        # Get recent commits for activity
                        commits_url = f"https://api.github.com/repos/{org}/{repo}/commits"
                        async with self.session.get(commits_url, headers=headers) as commits_response:
                            if commits_response.status == 200:
                                commits = await commits_response.json()
                                result["data"]["recent_commits"] = len(commits[:30])  # Last 30 commits
                                result["data"]["last_commit"] = commits[0]["commit"]["author"]["date"] if commits else None
                        
                        # Get contributors
                        contributors_url = f"https://api.github.com/repos/{org}/{repo}/contributors"
                        async with self.session.get(contributors_url, headers=headers) as contrib_response:
                            if contrib_response.status == 200:
                                contributors = await contrib_response.json()
                                result["data"]["contributor_count"] = len(contributors)
                                result["data"]["top_contributors"] = [
                                    {"login": c["login"], "contributions": c["contributions"]} 
                                    for c in contributors[:5]
                                ]
                    else:
                        # Org repos summary
                        result["data"] = {
                            "repo_count": len(data),
                            "repos": []
                        }
                        
                        for repo_data in data[:10]:  # Top 10 repos
                            result["data"]["repos"].append({
                                "name": repo_data.get("name", ""),
                                "stars": repo_data.get("stargazers_count", 0),
                                "language": repo_data.get("language", ""),
                                "updated_at": repo_data.get("updated_at", "")
                            })
                        
                        # Calculate total stars
                        result["data"]["total_stars"] = sum(r.get("stargazers_count", 0) for r in data)
                    
                    logger.info(f"GitHub API successful for {org}/{repo if repo else 'org'}")
                else:
                    logger.error(f"GitHub API error: {response.status}")
                    result = {
                        "success": False,
                        "error": f"GitHub API returned {response.status}",
                        "data": {}
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"GitHub API execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }
    
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute a single task based on its tool type"""
        if task.tool == ToolType.TAVILY:
            return await self.execute_tavily(task.parameters)
        elif task.tool == ToolType.FIRECRAWL:
            return await self.execute_firecrawl(task.parameters)
        elif task.tool == ToolType.GITHUB:
            return await self.execute_github_api(task.parameters)
        else:
            return {
                "success": False,
                "error": f"Unsupported tool type: {task.tool}"
            }


# Singleton instance for backward compatibility
mcp_orchestrator = MCPToolExecutor()


class SingleAgentOrchestrator:
    """
    Single agent orchestrator - stub for now
    Can be expanded to use Claude with tool calls
    """
    
    def __init__(self):
        self.executor = MCPToolExecutor()
        self.decomposer = PromptDecomposer()
    
    async def execute_as_single_agent(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        output_format: str = "analysis",
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Execute using a single agent approach
        For now, just returns a basic result
        """
        # This would be where Claude with tool calls would go
        # For now, just return a stub response
        return {
            "success": True,
            "result": {
                "analysis": f"Analysis for: {prompt}",
                "format": output_format
            },
            "metadata": {
                "prompt": prompt,
                "context": context
            }
        }
