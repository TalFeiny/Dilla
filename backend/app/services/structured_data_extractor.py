"""
Structured Data Extractor using Claude for accurate HTML parsing
Extracts real company data with proper schemas instead of regex patterns
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import re
from datetime import datetime

from app.core.config import settings
from app.services.model_router import ModelRouter, ModelCapability

logger = logging.getLogger(__name__)


class StructuredDataExtractor:
    """
    Claude-based structured data extraction from raw HTML
    Uses BeautifulSoup for parsing and Claude for intelligent extraction
    """
    
    def __init__(self):
        # Initialize ModelRouter for premium model support with automatic fallback
        try:
            self.model_router = ModelRouter()
            logger.info("ModelRouter initialized with multi-provider fallback support")
        except Exception as e:
            logger.warning(f"ModelRouter initialization failed: {e}")
            self.model_router = None
            # Model router is the single source of truth - no direct client fallback
    
    async def extract_from_html(self, html_content: str, company_name: str) -> Dict[str, Any]:
        """
        Extract structured data from raw HTML using BeautifulSoup + Claude
        """
        if not html_content:
            return {}
            
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract basic elements
        parsed_data = {
            'text': soup.get_text()[:5000],  # First 5000 chars of text
            'links': self._extract_links(soup, company_name),
            'funding_mentions': self._extract_funding_mentions(soup),
            'metrics': self._extract_metrics(soup),
            'team': self._extract_team_info(soup),
            'customers': self._extract_customer_logos(soup),
            'investors': self._extract_investors(soup)
        }
        
        # Use ModelRouter for intelligent extraction - single source of truth
        if self.model_router:
            return await self._claude_extract(parsed_data, company_name)
        else:
            logger.warning(f"No model router available, using basic extraction for {company_name}")
            return self._fallback_extract(parsed_data, company_name)
    
    def _extract_links(self, soup: BeautifulSoup, company_name: str) -> List[Dict]:
        """Extract relevant links from HTML"""
        links = []
        skip_domains = [
            'twitter.com', 'linkedin.com', 'facebook.com', 'instagram.com',
            'crunchbase.com', 'techcrunch.com', 'forbes.com', 'bloomberg.com',
            'reuters.com', 'wsj.com', 'nytimes.com', 'wikipedia.org'
        ]
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text().strip()
            
            # Skip social/news sites
            if any(domain in href.lower() for domain in skip_domains):
                continue
                
            # Score link relevance
            score = 0
            company_clean = company_name.lower().replace('@', '')
            
            if company_clean[:4] in href.lower():
                score += 100
            if 'website' in text.lower() or 'visit' in text.lower():
                score += 50
            if href.startswith('http') and score > 30:
                links.append({
                    'url': href,
                    'text': text,
                    'score': score
                })
        
        return sorted(links, key=lambda x: x['score'], reverse=True)[:5]
    
    def _extract_funding_mentions(self, soup: BeautifulSoup) -> List[str]:
        """Extract funding-related text snippets"""
        funding_patterns = [
            r'\$[\d,]+(?:\.\d+)?[MBK]?(?:\s*(?:million|billion|thousand))?',
            r'raised\s+\$[\d,]+(?:\.\d+)?',
            r'Series\s+[A-F]\d?',
            r'seed\s+(round|funding)',
            r'valuation\s+(of\s+)?\$[\d,]+(?:\.\d+)?[MBK]?'
        ]
        
        text = soup.get_text()
        mentions = []
        
        for pattern in funding_patterns:
            match_count = 0
            for match in re.finditer(pattern, text, re.IGNORECASE):
                full_match = match.group(0).strip()
                if not full_match:
                    continue
                mentions.append(full_match)
                match_count += 1
                if match_count >= 3:
                    break
        
        return mentions
    
    def _extract_metrics(self, soup: BeautifulSoup) -> Dict:
        """Extract business metrics from HTML"""
        metrics = {}
        text = soup.get_text()
        
        # Revenue patterns
        revenue_match = re.search(r'revenue\s+of\s+\$?([\d,]+)[MBK]?', text, re.IGNORECASE)
        if revenue_match:
            metrics['revenue'] = self._parse_number(revenue_match.group(1))
        
        # ARR patterns
        arr_match = re.search(r'ARR\s+of\s+\$?([\d,]+)[MBK]?', text, re.IGNORECASE)
        if arr_match:
            metrics['arr'] = self._parse_number(arr_match.group(1))
        
        # Growth rate
        growth_match = re.search(r'([\d]+)%\s+growth', text, re.IGNORECASE)
        if growth_match:
            metrics['growth_rate'] = float(growth_match.group(1)) / 100
        
        # Customer count
        customer_match = re.search(r'([\d,]+)\s+customers', text, re.IGNORECASE)
        if customer_match:
            metrics['customer_count'] = self._parse_number(customer_match.group(1))
        
        return metrics
    
    def _extract_team_info(self, soup: BeautifulSoup) -> Dict:
        """Extract team/founder information"""
        team = {}
        text = soup.get_text()
        
        # Look for founder mentions
        founder_patterns = [
            r'founder\s+(\w+\s+\w+)',
            r'CEO\s+(\w+\s+\w+)',
            r'(\w+\s+\w+),\s+CEO',
            r'(\w+\s+\w+),\s+founder'
        ]
        
        for pattern in founder_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                team['founder'] = match.group(1)
                break
        
        # Look for team size
        team_size_match = re.search(r'([\d,]+)\s+employees', text, re.IGNORECASE)
        if team_size_match:
            team['size'] = self._parse_number(team_size_match.group(1))
        
        return team
    
    def _extract_customer_logos(self, soup: BeautifulSoup) -> List[str]:
        """Extract customer names from img alt tags and text"""
        customers = []
        
        # Check img alt tags
        for img in soup.find_all('img', alt=True):
            alt = img.get('alt', '').strip()
            if alt and len(alt) < 50 and not any(x in alt.lower() for x in ['logo', 'icon', 'image']):
                customers.append(alt)
        
        # Look for customer mentions in text
        text = soup.get_text()
        customer_patterns = [
            r'customers\s+include\s+([^.]+)',
            r'trusted\s+by\s+([^.]+)',
            r'clients\s+include\s+([^.]+)'
        ]
        
        for pattern in customer_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Split by commas and clean
                names = match.group(1).split(',')
                customers.extend([n.strip() for n in names[:5]])
        
        return list(set(customers))[:10]  # Dedupe and limit
    
    def _extract_investors(self, soup: BeautifulSoup) -> List[str]:
        """Extract investor names from HTML"""
        investors = []
        text = soup.get_text()
        
        # Common investor mention patterns
        investor_patterns = [
            r'led\s+by\s+([^,\.]+)',
            r'investors\s+include\s+([^\.]+)',
            r'backed\s+by\s+([^\.]+)',
            r'participation\s+from\s+([^\.]+)'
        ]
        
        for pattern in investor_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:3]:
                # Split by commas/and
                names = re.split(r',|\sand\s', match)
                investors.extend([n.strip() for n in names if len(n.strip()) < 50])
        
        return list(set(investors))[:10]
    
    async def extract_from_text(self, text_sources: List[Dict], company_name: str, fund_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract structured data from clean text instead of HTML
        Uses source attribution for better context
        """
        if not text_sources:
            return {}
        
        # Combine text with source attribution (limit each to 4000 chars for better context)
        # Total max ~20K chars which is well within Claude's context
        # Include source index for citation tracking
        combined_text = "\n\n".join([
            f"[SOURCE {idx}] From {source.get('source', 'Unknown')} ({source.get('url', 'N/A')}):\n{source.get('text', '')[:4000]}"
            for idx, source in enumerate(text_sources[:5])  # Use top 5 sources with index
        ])
        
        # Keep source URLs for citation
        source_urls = [source.get('url', '') for source in text_sources[:5]]
        
        # Use ModelRouter or Claude for intelligent extraction
        if self.model_router:
            result = await self._claude_extract_from_text(combined_text, company_name, fund_context)
            # Add source URLs to citations
            if 'funding_rounds' in result:
                for round_data in result['funding_rounds']:
                    if 'citation' in round_data and 'source_index' in round_data['citation']:
                        idx = round_data['citation'].get('source_index', 0)
                        if 0 <= idx < len(source_urls):
                            round_data['citation']['url'] = source_urls[idx]
            return result
        else:
            # Fallback to basic extraction
            return self._basic_text_extract(text_sources, company_name)
    
    async def _claude_extract_from_text(self, combined_text: str, company_name: str, fund_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Use Claude to extract structured data from clean text"""
        
        # Clean company name for better matching
        company_clean = company_name.replace('@', '').strip()
        
        logger.info(f"[EXTRACTION] Starting Claude extraction for {company_clean}")
        logger.info(f"[STRUCTURED_TEXT][{company_clean}] Combined text length: {len(combined_text)} characters")
        logger.info(f"[STRUCTURED_TEXT][{company_clean}] First 500 chars: {(combined_text[:500] or '').replace(chr(10), ' ')}")
        
        # Add fund context if available
        fund_info = ""
        if fund_context:
            fund_size = fund_context.get('fund_size', 0)
            if fund_size:
                fund_info += f"\n**FUND CONTEXT**: You are evaluating for a ${fund_size/1e6:.0f}M fund"
            
            # Detect fund stage from context
            if 'seed' in str(fund_context).lower():
                fund_info += " focused on SEED stage investments"
                fund_info += "\n**IMPORTANT**: Prioritize seed/pre-seed stage companies. Series C+ companies are likely irrelevant."
            elif 'series a' in str(fund_context).lower():
                fund_info += " focused on Series A investments"
            
        extraction_prompt = f"""You are a venture capital analyst extracting ONLY verified data about {company_clean}.{fund_info}

**CRITICAL EXTRACTION RULES - NO KEYWORDS OR BUZZWORDS**:
- Describe EXACTLY what the company does, no buzzwords
- DO NOT add "AI-powered", "platform", "SaaS" unless that's literally what they do  
- CoreWeave operates data centers → Say "operates data centers", NOT "AI cloud platform"
- nScale builds data centers → Say "builds data centers", NOT "infrastructure platform"
- Example WRONG: "AI-powered GPU cloud platform for machine learning" (adds keywords)
- Example RIGHT: "Operates 14 data centers with 45,000 GPUs for rent" (factual)

CRITICAL RULES - EXTRACT WHAT EXISTS, NEVER FABRICATE:

**EXTRACT ALL NUMBERS YOU SEE IN THE SOURCES** - For funding amounts, revenue figures, and valuations:
1. If you SEE a number mentioned in the sources about {company_clean}, EXTRACT IT even if citation is imperfect
2. PREFER to include the EXACT SENTENCE from the source containing that number when available
3. PREFER to include the SOURCE INDEX showing which source it came from
4. If you cannot find an exact sentence citation, STILL EXTRACT with a partial citation like "Mentioned in [SOURCE X]"
5. **CRITICAL**: Only extract numbers that actually appear in the provided sources - DO NOT make up or estimate numbers
6. **DO NOT SKIP extraction just because you can't find the perfect citation** - but also DO NOT invent numbers

FUNDING EXTRACTION - EXTRACT WHAT YOU FIND (NOT WHAT YOU GUESS):
1. **Find ALL funding mentions**: Search the ENTIRE text for ANY mention of {company_clean} + funding/raised/series/seed/round
2. **Look for patterns**: "$X million", "raised $X", "Series [A-F]", "seed round", "funding round", "closed $X"
3. **DATE EXTRACTION - CRITICAL**:
   - **LOOK FOR THE `PUBLISHED: YYYY-MM-DD` LINE** at the start of each article block
   - Extract the EXACT date from the `PUBLISHED:` line for the funding round
   - Example: `PUBLISHED: 2024-09-15` → use "2024-09-15" as the round date
   - **THIS IS MANDATORY** - The date is RIGHT THERE in the metadata!
   - Only fall back to URL parsing if `PUBLISHED:` line is completely missing
   - DO NOT use vague dates from article text ("last month", "Q1 2024")
4. **Extract with citation**: 
   - amount: 15000000 (parse M/million/B/billion properly)
   - date: Use the source article's publication date
   - exact_sentence: "Lunio raised $15 million in Series A funding led by Insight Partners."
   - source_index: 2 (which source this came from)
5. **EXTRACT EVEN IF INCOMPLETE**: If you find "Series B funding" but no amount, STILL EXTRACT IT with amount: 0
6. **Citation sources**: Use the source_index to reference which search result (0, 1, 2, etc.)

WHAT TO EXTRACT (be aggressive):
- ANY funding round mention with company name
- Partial data is OK - we'll fill gaps later
- Series rounds, seed rounds, pre-seed, bridge rounds
- Investor names even without amounts
- Dates even without amounts

REJECT ONLY THESE:
- Clearly about a DIFFERENT company (not {company_clean})
- Market sizes / TAM (not funding)
- Customer revenue (not funding raised)

SOURCES TO ANALYZE:
{combined_text}

Extract and return a JSON object with ONLY verifiable facts about {company_clean}:

**CRITICAL: ALL VALUES MUST BE SIMPLE STRINGS OR NUMBERS - NO NESTED OBJECTS!**

DO NOT return business_model as {{"model_type": "...", "reasoning": "..."}} - WRONG!
MUST return business_model as "Records and analyzes medical consultations to improve diagnoses" - CORRECT!

DO NOT return vertical as {{"industry": "Healthcare", "segment": "..."}} - WRONG!  
MUST return vertical as "Healthcare" - CORRECT!

DO NOT return category as {{"type": "ai_first", "confidence": "high"}} - WRONG!
MUST return category as "ai_first" - CORRECT!

{{
  "company_name": "{company_clean}",
  "website_url": "actual company website if found",
  "one_liner": "concise description of what the company does",
  "product_description": "detailed description of their product/service and how it works",
  "who_they_sell_to": "specific description of their target customers (e.g. 'Fortune 500 retailers', 'SMB SaaS companies', 'Series A-C startups')",
  "how_they_grow": "their growth strategy and go-to-market approach",
  "funding_rounds": [
    {{
      "round": "Series B", 
      "amount": 150000000, 
      "date": "2023-09-01", 
      "investors": ["Andreessen Horowitz", "Sequoia"], 
      "valuation": 1500000000,
      "citation": {{
        "source_index": 0,
        "exact_sentence": "REQUIRED - The COMPLETE sentence like 'Lunio raised $150M in Series B funding in September 2023.'",
        "confidence": "high_exact_match"
      }}
    }}
  ],
  "total_raised": 265000000,
  "funding_extraction_note": "",
  "valuation": 1500000000,
  "valuation_citation": "REQUIRED if valuation provided - exact sentence mentioning valuation",
  "revenue": 1000000000,
  "revenue_citation": "REQUIRED if revenue provided - exact sentence mentioning revenue/ARR",
  "arr": 1000000000,
  "growth_rate": 3.0,
  "team_size": 500,
  "founder": "John Doe",
  "founder_background": "ex-Google, Stanford CS, serial entrepreneur",
  "founder_quality_signals": ["signal 1", "signal 2"],
  "customers": ["Real Company 1", "Real Company 2"],
  "customer_quality": "Enterprise",
  "investors": ["Real VC 1", "Real VC 2"],
  "business_model": "Records and analyzes doctor-patient consultations to improve medical diagnoses and documentation",
  "strategy": "land and expand",
  "vertical": "Healthcare",
  "customer_segment": "Enterprise",
  "category": "ai_first",
  "gpu_unit_of_work": "per medical consultation analyzed",
  "gpu_workload_description": "Real-time transcription of 30-minute consultations using Whisper, followed by GPT-4 analysis for medical insights and documentation generation",
  "compute_intensity": "high",
  "compute_signals": ["Real-time speech-to-text for 30min sessions", "GPT-4 medical analysis", "Generates 5-page clinical summaries"],
  "unit_economics": {{
    "gpu_cost_per_unit": 2.5,
    "units_per_customer_per_month": 200,
    "reasoning": "Each consultation requires ~$0.50 transcription + $2.00 GPT-4 analysis. Enterprise hospitals average 200 consultations/month"
  }},
  "stage": "Series B",
  "burn_rate": 2000000,
  "runway_months": 18,
  "market_position": {{
    "TAM": "900000000000",
    "SAM": "50000000000",
    "SOM": "5000000000",
    "labor_replacement_value": "Replaces 2 FTE medical scribes at $150K total",
    "competitive_position": "leader",
    "market_growth_rate": "15% CAGR"
  }},
  "traction_signals": ["Kaiser Permanente customer", "$50M ARR"],
  "key_metrics": {{
    "consultations_analyzed": 1000000,
    "accuracy_rate": 0.95
  }},
  "market_data": {{
    "tam": 50000000000,
    "tam_citation": "Gartner 2024: Healthcare AI market $50B by 2028",
    "sam": 5000000000,
    "som": 500000000,
    "market_growth_rate": 25,
    "market_category": "Healthcare AI",
    "market_subcategory": "Clinical documentation"
  }},
  "labor_statistics": {{
    "number_of_workers": 500000,
    "avg_salary_per_role": 35000,
    "total_addressable_labor_spend": 17500000000,
    "labor_citation": "BLS: 500K medical scribes @ $35K avg salary"
  }},
  "customer_segment": "enterprise",
  "geographies": ["US", "Europe"],
  "competitors_mentioned": [
    {{"name": "Nuance", "market_share": 15}},
    {{"name": "Epic", "market_share": 31}}
  ]
}}

FUNDING REQUIREMENTS (MANDATORY):
- **EXTRACT WHAT YOU SEE**: For every funding amount or round type that actually appears in the sources for {company_clean}, create a funding_round entry. Use "" for missing dates and [] for missing investors instead of skipping the round.
- Extract even if citation is imperfect - use partial citations when exact sentences aren't available (as long as you actually saw the number in the sources)
- **NEVER INVENT NUMBERS** - Only extract amounts that are explicitly mentioned in the provided sources
- total_raised MUST equal the sum of the funding_round amounts. Only use 0 if NO funding is mentioned anywhere in ANY source.
- Set funding_extraction_note to "" when you provide funding data. If no funding can be found at all, set funding_rounds: [], total_raised: 0, and explain briefly in funding_extraction_note (e.g., "No funding disclosed in provided sources").
- Do not fabricate amounts. If multiple amounts conflict, choose the most recent or clearly cited value and note the decision in funding_extraction_note if needed.

REQUIRED FIELD VALUES:
- business_model: STRING - Describe EXACTLY what the company does without buzzwords. Example: "Operates 14 data centers with 45,000 GPUs for rent" NOT "AI cloud platform"
- vertical: STRING - WHO they sell to (target customer industry). Examples: "Healthcare" (sells to hospitals), "Financial Services" (sells to banks), "Legal" (sells to law firms), "Retail" (sells to retailers), "Manufacturing" (sells to factories). Use "Horizontal" ONLY if they sell across ALL industries. Use "SMB" or "Enterprise" if that's their primary segmentation rather than industry. 
- category: STRING - Must be one of: "industrial", "deeptech_hardware", "materials", "manufacturing", "ai_first", "ai_saas", "saas", "marketplace", "services", "tech_enabled_services", "rollup", "hardware", "gtm_software"
- funding_extraction_note: STRING - "" when funding_rounds are populated; otherwise explain briefly why funding is empty.
- gpu_unit_of_work: STRING - The atomic unit that triggers GPU usage. Be VERY SPECIFIC based on what they actually sell:
  * Example: "per 30-minute medical consultation analyzed" not "per analysis"
  * Example: "per pull request code review (avg 500 lines)" not "per code review"
  * Example: "per sales call transcribed and summarized (avg 45 min)" not "per transcription"
- gpu_workload_description: STRING - Describe the actual compute workload in technical detail
- compute_intensity: STRING - MUST be one of these based on actual workload:
  * "extreme": Full code file generation (>1000 tokens out), video generation, multi-step agents
  * "high": Search with synthesis, image generation, real-time voice/transcription
  * "moderate": Chat responses, simple completions, document Q&A
  * "low": Traditional ML, embeddings, classification
  * "none": No AI/GPU workload
- gpu_passthrough_percentage: NUMBER - What % of revenue goes to OpenAI/Anthropic/GPU providers (0-100)
- actual_customers: ARRAY - Extract SPECIFIC customer names mentioned, especially enterprise logos
- customer_acv: NUMBER - If mentioned, actual contract values (e.g., "Harvey charges $500K/year")
- labor_job_titles: ARRAY - Jobs being replaced (e.g., ["medical scribes", "receptionists"])
- labor_worker_count: NUMBER - Total workers in these roles (e.g., 500000)
- labor_avg_salary: NUMBER - Average annual salary (e.g., 35000)
- labor_data_citation: STRING - Source (e.g., "BLS reports 500K medical scribes earning $35K/year")
- labor_total_spend: NUMBER - Total addressable labor spend (workers × salary)
- software_market_tam: NUMBER - Total software market size in dollars
- software_market_year: NUMBER - Year of the market report (e.g., 2024)
- software_market_source: STRING - Who published it (e.g., "Gartner", "Forrester")
- software_market_citation: STRING - Exact quote from report
- software_market_cagr: NUMBER - Growth rate if mentioned (as decimal, e.g., 0.15 for 15%)
- competitors_mentioned: ARRAY of OBJECTS - Extract any competitors with their market share if mentioned
- market_data: OBJECT with:
  * tam: NUMBER - Total addressable market in dollars (NOT string)
  * tam_citation: STRING - Source and date (e.g., "Gartner 2024 report")
  * sam: NUMBER - Serviceable addressable market if mentioned
  * som: NUMBER - Serviceable obtainable market if mentioned
  * market_growth_rate: NUMBER - CAGR as percentage (e.g., 25 for 25%)
  * market_category: STRING - Main market they operate in
  * market_subcategory: STRING - Specific segment within market
- labor_statistics: OBJECT with:
  * number_of_workers: NUMBER - Workers in roles being replaced
  * avg_salary_per_role: NUMBER - Average annual salary
  * total_addressable_labor_spend: NUMBER - Total labor spend (workers × salary)
  * labor_citation: STRING - Source (e.g., "BLS: 500K workers @ $35K")
- customer_segment: STRING - "enterprise", "mid-market", "SME", or "mixed"
- geographies: ARRAY - Markets they operate in (e.g., ["US", "Europe"])
- unit_economics: OBJECT with:
  * what_they_sell: STRING - Specific product/service (NOT generic "platform" or "solution")
  * who_they_sell_to: STRING - Specific customer segments
  * price_per_unit: NUMBER - Actual pricing if mentioned
  * gpu_cost_per_unit: NUMBER - Estimated GPU cost for that unit
  * units_per_customer_per_month: NUMBER - Usage frequency
  * gross_margin_per_unit: NUMBER - (price - gpu_cost) / price
- All other text fields: STRING values, use empty string "" if unknown
- All numeric fields: NUMBER values, use 0 if unknown

EXTRACTION GUIDELINES FOR {company_clean}:
1. FUNDING EXTRACTION - EXTRACT WHAT EXISTS:
   - ✓ Extract if {company_clean} AND dollar amount are mentioned in the sources (same article/section, don't require exact same sentence)
   - ✓ PREFER to provide the exact_sentence field with the FULL SENTENCE when you can find it
   - ✓ Example: "Lunio raised $15M in Series A funding in 2022" → extract 15000000 with this sentence as citation
   - ✓ If you can't find the exact sentence but you SAW the number in the sources, extract with partial citation: "Mentioned in source [X] about {company_clean} funding"
   - ✓ If no explicit amount but round type mentioned (e.g., "Series A"), extract with amount: 0 and round type
   - ✗ DO NOT extract if the number is NOT in the sources (don't make up amounts)
   - ✗ ONLY REJECT if clearly about a DIFFERENT company or if the number doesn't exist in any source
   - confidence: "high_exact_match" if exact sentence found, "medium" if you saw it in source but citation is partial, "low" if round type only
2. REVENUE/ARR EXTRACTION:
   - Extract if {company_clean} and revenue amount are mentioned in the same article/source
   - Include citation when possible, but extract even without perfect citation
   - Distinguish revenue from funding: "revenue", "ARR", "sales" vs "raised", "funding", "round"
3. VALUATION vs FUNDING:
   - Valuation: "valued at", "valuation of", "worth"
   - Funding: "raised", "secured", "closed", "funding round"
   - DO NOT confuse these - they are different numbers
4. Convert all amounts to raw numbers: 
   - $15M = 15000000
   - £93M = 115000000 (convert to USD)
   - $119K = 119000
5. Dates: Use "YYYY-MM-DD" format
   - If only month/year: "2024-08-01" for August 2024
   - If only year: "2024-01-01" for 2024
7. DO NOT GUESS - use null/0 for unknown values
8. IGNORE all data about companies other than {company_clean}
9. CATEGORY INFERENCE - REQUIRED: Semantically analyze the business_model to determine category:
   - "industrial": Manufacturing, production, or processing of physical materials/goods at scale
   - "deeptech_hardware": Advanced physical technology (robotics, semiconductors, quantum, biotech hardware)
   - "materials": New materials science, chemicals, composites, metals innovation
   - "manufacturing": Production facilities, factories, assembly operations
   - "gtm_software": Go-to-market, sales, or distribution software for reaching customers (especially in traditional industries)
   - "full_stack_ai": AI-enabled company that delivers the COMPLETE service (e.g., AI insurance company that underwrites/pays claims)
   - "ai_first": Core product IS the AI model or AI capability (selling AI tools/APIs)
   - "ai_saas": Traditional SaaS enhanced with AI features
   - "rollup": Acquiring and consolidating multiple companies
   - "marketplace": Connects buyers and sellers, takes a transaction fee
   - "saas": Software delivered as a subscription service
   - "services": Human labor/consulting as primary offering
   - "hardware": Consumer electronics or computing devices
   - Analyze what the company actually DOES (makes metal = materials, sells to factories = gtm_software)

ENHANCED EXTRACTION FOR INVESTMENT CASE:
9. FOUNDER QUALITY - CRITICAL EXTRACTION:
   - Extract actual founder/CEO/CTO names (REQUIRED)
   - LinkedIn profiles if mentioned (look for "linkedin.com/in/")
   - Educational background (university names)
   - Previous companies (especially exits)
   - Previous roles at notable companies
   - Technical credentials (PhD, patents, publications)
   - Work history timeline
   Format as founders array with objects containing:
   {
     "name": "John Smith",
     "role": "CEO/Founder",
     "linkedin_url": "https://linkedin.com/in/johnsmith",
     "education": "MIT Computer Science",
     "previous_companies": ["Google", "Meta"],
     "previous_exits": true/false,
     "technical_background": true/false,
     "work_history": "10 years at Google as Senior Engineer"
   }
10. BUSINESS MODEL & STRATEGY:
   - Roll-up: Look for "acquisition", "consolidation", "buy and build"
11. UNIT ECONOMICS & GPU ANALYSIS - CRITICAL:
   Extract the ACTUAL business transaction:
   - What specific service/product is sold? (e.g., "AI medical scribe that documents doctor visits")
   - Who are the actual customers? (Extract company names like "Kaiser", "Mayo Clinic")
   - What's the unit of work? (e.g., "per 30-min consultation documented")
   - How much GPU/API cost per unit? (e.g., 10K tokens = $0.20 to Anthropic)
   - What's the pricing model? (per seat, per usage, per month?)
   - Extract ACTUAL pricing if available: "$50/user/month", "$0.10/API call", "$5000/enterprise"
   - Look for pricing pages, plans, tiers mentioned
   - Store in pricing_model field with actual numbers
   - Calculate: If they charge $X and pay $Y to GPU, gross margin = (X-Y)/X
12. LABOR STATISTICS (CRITICAL - look for BLS/labor data):
   - What human jobs does this replace? (e.g., "medical scribes", "junior lawyers")
   - Extract NUMBERS: "X million medical scribes in US" 
   - Extract SALARIES: "average salary $35,000/year"
   - Look for citations like "According to BLS..." or "Labor statistics show..."
   - Calculate total labor pool: num_workers × avg_salary
13. SOFTWARE MARKET SIZE (look for analyst reports):
   - Extract market size from: Gartner, Forrester, IDC, McKinsey, etc.
   - Look for: "healthcare IT market worth $X billion"
   - Note the YEAR of the report (critical for growth calculations)
   - Extract CAGR/growth rates if mentioned
14. COMPETITION & OLIGOPOLIES:
   - Extract ALL competitors mentioned by name
   - Note any market share percentages
   - Identify oligopolies (e.g., "Epic has 31% of EHR market")
   - Calculate addressable = total market - oligopoly controlled
14. TRACTION WITH SPECIFICS:
   - Named customers with contract values if mentioned
   - Actual metrics (not "growing fast" but "100K users, 50% MoM growth")
   - Revenue/ARR if mentioned explicitly
15. MARKET DATA EXTRACTION - CRITICAL FOR TAM:
   - Extract TAM from analyst reports (Gartner, Forrester, IDC, McKinsey)
   - Look for phrases like "market worth $X billion", "TAM of $X", "market size"
   - Note the YEAR and SOURCE (critical for growth calculations)
   - Extract CAGR/growth rates if mentioned
   - Identify market category and subcategory
16. CUSTOMER SEGMENTATION:
   - Extract who they sell to: "enterprise", "mid-market", "SME", "mixed"
   - Look for customer size indicators in descriptions
   - Extract geographic markets they operate in
17. COMPETITIVE LANDSCAPE:
   - Extract ALL competitors mentioned by name
   - Note market share percentages if provided
   - Identify if there are dominant players (oligopolies)

INTELLIGENT MARKET ESTIMATION (when data not found in sources):
If you cannot find explicit market/labor data in the sources, provide your best estimates:

FOR LABOR STATISTICS (if not found):
- Estimate workforce size based on industry knowledge:
  * Medical scribes: ~500K workers in US healthcare
  * Receptionists: ~1M in healthcare settings
  * Junior lawyers: ~200K associates in US law firms
  * Financial analysts: ~300K in investment banks/PE firms
  * Customer service reps: ~3M across all industries
- Estimate average salaries by role:
  * Medical scribe: $35,000/year
  * Medical receptionist: $38,000/year
  * Junior lawyer: $65,000-$190,000 (varies by firm size)
  * Financial analyst: $85,000/year
  * Customer service rep: $35,000/year
- Use labor_data_citation: "Claude estimate based on industry patterns"

FOR SOFTWARE MARKET (if not found):
- Estimate TAM based on vertical and use case:
  * Healthcare AI voice/transcription: $15-30B
  * Legal document automation: $20-40B
  * Financial analysis/M&A tools: $10-25B
  * Defense/GovTech: $30-100B
  * Marketing automation: $50-100B
  * Developer tools: $30-60B
  * HR/Recruiting tech: $25-50B
- Use software_market_source: "Claude estimate"
- Use software_market_citation: "Estimated based on [vertical] software spending patterns"
- Estimate CAGR: 0.15-0.25 for AI sectors, 0.08-0.12 for mature markets

ESTIMATION RULES:
1. Always provide estimates even if no explicit data found
2. Use conservative estimates (lower end of reasonable range)
3. Mark clearly as estimates in citations
4. Base on comparable markets and standard industry multiples
5. Consider company stage when estimating (Series A companies in $5-20B TAMs)

VALIDATION REQUIREMENTS:
- Each funding round must pass sanity check for its stage
- Total raised must equal sum of all rounds
- Valuation must be reasonable (usually 5-20x last round amount)
- Revenue/ARR must be realistic for company stage
"""
        
        try:
            # Try ModelRouter first for automatic fallback across premium models
            if self.model_router:
                logger.info(f"Using ModelRouter with premium models for {company_name}")
                
                # Use premium models only - no cheap/mini models for production quality
                result_dict = await self.model_router.get_completion(
                    prompt=extraction_prompt,
                    capability=ModelCapability.STRUCTURED,
                    max_tokens=8000,  # Increased to prevent truncation before funding_rounds
                    temperature=0,
                    preferred_models=[
                        "claude-sonnet-4-5",     # Primary: Claude Sonnet 4.5
                        "gpt-5-mini"             # Secondary: GPT-5-Mini with JSON mode
                    ],
                    fallback_enabled=True,
                    json_mode=True  # Enable JSON mode for GPT-4 structured output
                )
                
                response_text = result_dict.get('response', '')
                model_used = result_dict.get('model', 'unknown')
                cost = result_dict.get('cost', 0)
                logger.info(f"Extraction successful using {model_used} for {company_name} (cost: ${cost:.4f})")
                
            else:
                logger.warning(f"No LLM available for extraction, using basic extraction")
                return self._basic_text_extract([{'text': combined_text}], company_name)
            
            # Parse response
            import json
            
            if not response_text:
                logger.warning(f"Empty {model_used} response, using basic extraction")
                return self._basic_text_extract([{'text': combined_text}], company_name)
            
            logger.info(f"[EXTRACTION] {model_used} response length: {len(response_text)} chars for {company_clean}")
            logger.info(f"[EXTRACTION] Raw response preview: {response_text[:500]}...")
            
            # Extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
            else:
                result = json.loads(response_text)
            
            logger.info(f"[EXTRACTION] Parsed result keys: {list(result.keys())}")
            logger.info(f"[EXTRACTION] Revenue: {result.get('revenue', 'None')}, Valuation: {result.get('valuation', 'None')}")
            logger.info(f"[EXTRACTION] Business model: {result.get('business_model', 'None')}")
            logger.info(f"[EXTRACTION] Funding rounds: {len(result.get('funding_rounds', []))}")
            
            # DEBUG: Log the actual funding rounds
            if 'funding_rounds' in result:
                logger.info(f"[EXTRACTION] Funding rounds data: {result['funding_rounds']}")
            
            # Log market and labor extraction
            logger.info(f"[EXTRACTION] Software market TAM: ${result.get('software_market_tam', 0)/1e9:.1f}B")
            logger.info(f"[EXTRACTION] Software market source: {result.get('software_market_source', 'None')}")
            logger.info(f"[EXTRACTION] Labor worker count: {result.get('labor_worker_count', 0):,}")
            logger.info(f"[EXTRACTION] Labor avg salary: ${result.get('labor_avg_salary', 0):,}")
            logger.info(f"[EXTRACTION] Labor job titles: {result.get('labor_job_titles', [])}")
            
            # Validate the data
            validated_result = self._validate_extracted_data(result)
            logger.info(f"[EXTRACTION] After validation - keys: {list(validated_result.keys())}")
            return validated_result
            
        except asyncio.TimeoutError:
            logger.error(f"LLM extraction timed out for {company_name}")
            return self._basic_text_extract([{'text': combined_text}], company_name)
        except Exception as e:
            logger.error(f"LLM extraction failed for {company_name}: {type(e).__name__}: {e}")
            # Log specific error types for monitoring
            if "529" in str(e) or "overloaded" in str(e).lower():
                logger.warning(f"Model overloaded - ModelRouter should have handled fallback")
            elif "401" in str(e) or "403" in str(e):
                logger.error(f"Authentication error - check API keys")
            elif "rate" in str(e).lower() or "429" in str(e):
                logger.warning(f"Rate limit hit - ModelRouter should retry")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._basic_text_extract([{'text': combined_text}], company_name)
    
    def _basic_text_extract(self, text_sources: List[Dict], company_name: str) -> Dict[str, Any]:
        """Basic extraction from text without Claude"""
        result = {
            'company_name': company_name,
            'website_url': '',
            'funding_rounds': [],
            'total_raised': 0,
            'valuation': 0,
            'revenue': 0,
            'arr': 0,
            'growth_rate': 0,
            'team_size': 0,
            'founder': '',
            'customers': [],
            'investors': [],
            'business_model': '',
            'stage': ''
        }
        
        # Extract from all text sources
        for source in text_sources:
            text = source.get('text', '')
            
            # Extract revenue run rate FIRST (highest priority)
            revenue_patterns = [
                r'\$(\d+(?:\.\d+)?)\s*(billion|bn|B)\s+(?:revenue\s+)?run\s*rate',
                r'revenue\s+run\s*rate\s+of\s+\$(\d+(?:\.\d+)?)\s*(billion|bn|B)',
                r'\$(\d+(?:\.\d+)?)\s*(million|M)\s+(?:annual\s+)?(?:revenue|ARR)',
                r'ARR\s+of\s+\$(\d+(?:\.\d+)?)\s*(million|billion|M|B)'
            ]
            
            for pattern in revenue_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for amount, unit in matches:
                    multiplier = 1000000 if unit.lower() in ['million', 'm'] else 1000000000
                    value = float(amount) * multiplier
                    # Update both revenue and ARR for run rate
                    if 'run rate' in pattern.lower() or 'arr' in pattern.lower():
                        result['arr'] = max(result['arr'], value)
                        result['revenue'] = max(result['revenue'], value)
                    else:
                        result['revenue'] = max(result['revenue'], value)
            
            # Extract funding amounts with support for multiple currencies
            # Support $, £, € symbols
            funding_patterns = [
                r'raised\s+[$£€](\d+(?:\.\d+)?)\s*(million|billion|M|B)',
                r'[$£€](\d+(?:\.\d+)?)\s*(million|billion|M|B)\s+(?:funding|raised|investment)',
                r'secured?\s+[$£€](\d+(?:\.\d+)?)\s*(million|billion|M|B)',
                r'closed?\s+[$£€](\d+(?:\.\d+)?)\s*(million|billion|M|B)',
                r'£(\d+(?:\.\d+)?)\s*(million|m)\s+(?:funding|raised|round)',  # Specific for UK pounds
                r'€(\d+(?:\.\d+)?)\s*(million|m)\s+(?:funding|raised|round)'   # Specific for euros
            ]
            
            for pattern in funding_patterns:
                funding_matches = re.findall(pattern, text, re.IGNORECASE)
                for amount, unit in funding_matches:
                    multiplier = 1000000 if unit.lower() in ['million', 'm'] else 1000000000
                    value = float(amount) * multiplier
                    if value < 10000000000:  # Less than 10B
                        current_total = result.get('total_raised', 0) or 0
                        result['total_raised'] = max(current_total, value)
            
            # Extract stage
            stage_matches = re.findall(r'Series\s+([A-F]\d?)', text, re.IGNORECASE)
            if stage_matches and not result['stage']:
                result['stage'] = f"Series {stage_matches[0]}"
            elif 'seed' in text.lower() and not result['stage']:
                result['stage'] = 'Seed'
            
            # Extract team size
            team_patterns = [
                r'(\d+(?:,\d{3})?)\+?\s*(?:employees|people|team\s*members)',
                r'team\s*of\s*(\d+(?:,\d{3})?)\+?',
                r'grown\s+to\s+(\d+(?:,\d{3})?)\+?\s*team'
            ]
            for pattern in team_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    size = int(match.replace(',', ''))
                    if 10 <= size <= 100000:  # Reasonable team size
                        result['team_size'] = max(result['team_size'], size)
            
            # Extract customers
            customer_patterns = [
                r'customers[,\s]+including\s+([^\.]+)',
                r'clients\s+include\s+([^\.]+)',
                r'trusted\s+by\s+([^\.]+)'
            ]
            for pattern in customer_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Split by commas and 'and'
                    customers = re.split(r',|\sand\s', match)
                    for customer in customers[:10]:  # Limit to 10 customers
                        customer = customer.strip()
                        if customer and len(customer) < 50:
                            result['customers'].append(customer)
        
        return result
    
    async def _claude_extract(self, parsed_data: Dict, company_name: str) -> Dict[str, Any]:
        """Use ModelRouter or Claude to intelligently structure the parsed data"""
        if not self.model_router:
            return self._fallback_extract(parsed_data, company_name)
        
        funding_mentions = parsed_data.get('funding_mentions', [])
        logger.info(f"[STRUCTURED_EXTRACT][{company_name}] Funding mentions passed to Claude: {funding_mentions}")
        text_sample = (parsed_data.get('text', '') or '')[:500].replace('\n', ' ')
        logger.info(f"[STRUCTURED_EXTRACT][{company_name}] Text sample (first 500 chars): {text_sample}")

        extraction_prompt = f"""Analyze this data for {company_name} and extract structured information.

Raw data:
- Text excerpt: {parsed_data.get('text', '')[:2000]}
- Funding mentions: {parsed_data.get('funding_mentions', [])}
- Metrics found: {parsed_data.get('metrics', {})}
- Team info: {parsed_data.get('team', {})}
- Potential customers: {parsed_data.get('customers', [])}
- Potential investors: {parsed_data.get('investors', [])}

Return ONLY a valid JSON object (no markdown, no explanation) with:
1. company_name: string
2. website_url: string (best guess from links)
3. funding_rounds: array of {{round, amount, date, investors}}
   - date MUST be in "YYYY-MM-DD" format (e.g., "2024-08-15")
   - If only month/year known, use "YYYY-MM-01" (e.g., "2024-08-01" for August 2024)
   - If only year known, use "YYYY-01-01" (e.g., "2024-01-01" for 2024)
4. total_raised: number (in dollars, not millions)
5. valuation: number (in dollars, validate it's reasonable for a startup)
6. revenue: number (LATEST annual revenue in dollars, e.g., if they hit $1B in 2024, use 1000000000)
7. arr: number (Annual Recurring Revenue in dollars)
8. growth_rate: float (year-over-year growth as decimal - if revenue went from $300M to $1B, that's 2.33 for 233% growth)
9. team_size: number
10. founder: string
11. customers: array of company names (real companies only)
12. investors: array of investor names (real VCs only)
13. business_model: string - BE SPECIFIC about what the company does. Not just "SaaS" but describe their actual business. Examples:
    - "AI-powered patient consultation analysis for healthcare" (Corti)
    - "ML infrastructure and deployment platform" (AdaptiveML)
    - "Defense technology and autonomous systems" (for defense companies)
    - "Vertical SaaS for X industry" (be specific about the industry)
14. sector: string - The industry/vertical they serve. Examples:
    - "Healthcare" / "HealthTech" for medical companies
    - "Defense" / "DefenseTech" for military/defense companies
    - "Financial Services" / "FinTech" for banking/payments
    - "Infrastructure" / "Developer Tools" for tech infrastructure
    - Be specific - not just "Technology"
15. stage: string - MUST be one of: Pre-seed, Seed, Series A, Series B, Series C, Series D, Series E, Late Stage, IPO
    - Map any grant funding, NSF grants, SBIR, etc to "Pre-seed"
    - Map accelerator/incubator to "Pre-seed" 
    - NEVER use "Grant" as a stage
16. product_description: string - Describe the actual product/service (what does it do?)
17. who_they_sell_to: string - Target customer profile (enterprises, SMBs, consumers, specific verticals)
18. how_they_grow: string - Growth strategy (PLG, enterprise sales, partner channels, viral, etc)
19. funding_extraction_note: string - "" if you reported funding; otherwise explain why funding is blank.

FUNDING REQUIREMENTS:
- For EVERY funding amount you find for {company_name}, you MUST add a funding_round entry. Use "" for unknown dates and [] for unknown investors rather than omitting the round.
- total_raised MUST equal the sum of all funding_round.amount values (0 only if no funding found).
- If no funding is mentioned anywhere, set funding_rounds: [] and total_raised: 0, and set funding_extraction_note to a short explanation like "No funding information in sources."
- Never fabricate amounts. If multiple sources cite different figures, choose the most recent or most precise amount you can cite.

Example structure (adjust values to match the company, do not copy):
{{
  "funding_rounds": [
    {{"round": "Series B", "amount": 45000000, "date": "2024-05-01", "investors": ["Sequoia", "Index Ventures"]}},
    {{"round": "Seed", "amount": 5000000, "date": "2021-09-01", "investors": []}}
  ],
  "total_raised": 50000000,
  "funding_extraction_note": ""
}}

IMPORTANT: 
- BE SPECIFIC about business_model and sector - describe what they actually do
- Only include data you can verify from the provided text
- Valuations should be reasonable for startups (not trillions)
- Convert all money to raw numbers (1M = 1000000)
- Return empty/0 for missing data rather than guessing
"""
        
        try:
            # Use ModelRouter for consistent error handling, rate limiting, and fallback
            if self.model_router:
                logger.info(f"Using ModelRouter for funding extraction for {company_name}")
                
                result_dict = await self.model_router.get_completion(
                    prompt=extraction_prompt,
                    capability=ModelCapability.STRUCTURED,
                    max_tokens=2000,
                    temperature=0,
                    preferred_models=["claude-sonnet-4-5", "gpt-5-mini"],  # Claude 4.5 primary, GPT-5-Mini secondary
                    fallback_enabled=True,
                    json_mode=True  # Enable JSON mode for structured output
                )
                
                response_text = result_dict.get('response', '')
                model_used = result_dict.get('model', 'unknown')
                logger.info(f"Funding extraction successful using {model_used} for {company_name}")
            else:
                logger.warning(f"No model router available, falling back to basic extraction")
                return self._fallback_extract(parsed_data, company_name)
            
            # Parse JSON response - handle both wrapped and unwrapped JSON
            import json
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
            else:
                # If no JSON found, try parsing the whole response
                result = json.loads(response_text)

            logger.info(
                f"[STRUCTURED_EXTRACT][{company_name}] Funding output: rounds={len(result.get('funding_rounds', []) or [])}, total_raised={result.get('total_raised')}"
            )
            
            # Infer compute_intensity if not extracted
            if not result.get('compute_intensity') or result.get('compute_intensity') == 'Unknown':
                inferred_intensity = self._infer_compute_intensity_from_signals(result)
                if inferred_intensity:
                    result['compute_intensity'] = inferred_intensity
                    logger.info(f"[COMPUTE_INTENSITY] Inferred {inferred_intensity} for {company_name} from signals")
            
            # Validate the data
            return self._validate_extracted_data(result)
            
        except Exception as e:
            logger.error(f"Funding extraction failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._fallback_extract(parsed_data, company_name)
    
    def _infer_compute_intensity_from_signals(self, data: Dict) -> Optional[str]:
        """Infer compute intensity from gpu_unit_of_work and compute_signals"""
        
        gpu_unit = data.get('gpu_unit_of_work', '').lower()
        compute_signals = data.get('compute_signals', [])
        workload_desc = data.get('gpu_workload_description', '').lower()
        business_model = data.get('business_model', '').lower()
        
        # Combine all signals
        all_text = f"{gpu_unit} {workload_desc} {business_model} {' '.join(compute_signals)}".lower()
        
        # EXTREME: Full code generation, video generation, multi-step agents
        extreme_patterns = [
            'full code file', 'complete implementation', 'video generation', 
            'multi-step agent', 'autonomous agent', 'entire codebase',
            'full application', 'complete project', 'hours of processing'
        ]
        if any(pattern in all_text for pattern in extreme_patterns):
            return 'extreme'
        
        # HIGH: Search with synthesis, image generation, real-time voice
        high_patterns = [
            'search with synthesis', 'search and synthesis', 'image generation',
            'real-time voice', 'real-time transcription', 'voice assistant',
            'live translation', 'streaming', 'per consultation analyzed',
            'medical consultation', 'legal document review', 'code review'
        ]
        if any(pattern in all_text for pattern in high_patterns):
            return 'high'
        
        # MODERATE: Chat responses, simple completions, document Q&A  
        moderate_patterns = [
            'chat response', 'simple completion', 'document q&a', 'question answer',
            'summarization', 'extraction', 'classification', 'sentiment',
            'per message', 'per query', 'per request'
        ]
        if any(pattern in all_text for pattern in moderate_patterns):
            return 'moderate'
        
        # LOW: Traditional ML, embeddings, classification
        low_patterns = [
            'traditional ml', 'embedding', 'vector', 'classification only',
            'batch processing', 'offline', 'pre-computed', 'cached'
        ]
        if any(pattern in all_text for pattern in low_patterns):
            return 'low'
        
        # NONE: No AI/GPU workload
        none_patterns = [
            'no ai', 'no gpu', 'traditional software', 'pure saas',
            'marketplace', 'payments', 'crm', 'erp'
        ]
        if any(pattern in all_text for pattern in none_patterns):
            return 'none'
        
        # Default: Don't infer if no clear signals
        return None
    
    def _fallback_extract(self, parsed_data: Dict, company_name: str) -> Dict[str, Any]:
        """Fallback extraction without Claude"""
        result = {
            'company_name': company_name,
            'website_url': '',
            'funding_rounds': [],
            'total_raised': 0,
            'valuation': 0,
            'revenue': parsed_data.get('metrics', {}).get('revenue', 0),
            'arr': parsed_data.get('metrics', {}).get('arr', 0),
            'growth_rate': parsed_data.get('metrics', {}).get('growth_rate', 0),
            'team_size': parsed_data.get('team', {}).get('size', 0),
            'founder': parsed_data.get('team', {}).get('founder', ''),
            'customers': parsed_data.get('customers', []),
            'investors': parsed_data.get('investors', []),
            'business_model': 'Unknown',
            'sector': 'Unknown',
            'stage': 'Unknown'
        }
        
        # Try to get website from links
        links = parsed_data.get('links', [])
        if links:
            result['website_url'] = links[0].get('url', '')
        
        # Parse funding mentions for amounts (best effort when Claude unavailable)
        for mention in parsed_data.get('funding_mentions', []):
            amount_match = re.search(r'\$?([\d,]+(?:\.\d+)?)([MBK])?', mention)
            if amount_match:
                amount = self._parse_number(amount_match.group(1))
                multiplier = {'M': 1000000, 'B': 1000000000, 'K': 1000}.get(
                    amount_match.group(2), 1
                )
                existing_total = result.get('total_raised', 0) or 0
                result['total_raised'] = existing_total + (amount * multiplier)

        return self._validate_extracted_data(result)
    
    def _validate_extracted_data(self, data: Dict) -> Dict[str, Any]:
        """Validate and clean extracted data with enhanced validation"""
        
        # Log what Claude extracted BEFORE validation
        company_name = data.get('company_name', 'Unknown')
        # Safe formatting with None checks
        revenue = data.get('revenue', 0) or 0
        growth_rate = data.get('growth_rate', 0) or 0
        arr = data.get('arr', 0) or 0
        valuation = data.get('valuation', 0) or 0

        if 'total_raised' not in data or data['total_raised'] is None:
            data['total_raised'] = 0
        if 'funding_extraction_note' not in data or data['funding_extraction_note'] is None:
            data['funding_extraction_note'] = "" if data.get('total_raised') else "No funding information provided"

        logger.info(f"[CLAUDE RAW EXTRACTION] {company_name}: revenue=${revenue:,.0f}, growth_rate={growth_rate:.2f}, arr=${arr:,.0f}, valuation=${valuation:,.0f}")
        
        # Log semantic fields
        logger.info(f"[SEMANTIC EXTRACTION] {company_name}:")
        logger.info(f"  business_model: {data.get('business_model', 'MISSING')}")
        logger.info(f"  sector: {data.get('sector', 'MISSING')}")
        logger.info(f"  product_description: {data.get('product_description', 'MISSING')}")
        logger.info(f"  who_they_sell_to: {data.get('who_they_sell_to', 'MISSING')}")
        logger.info(f"  how_they_grow: {data.get('how_they_grow', 'MISSING')}")
        
        # CRITICAL FIX: Handle dict responses from Claude that shouldn't happen
        # If business_model is a dict, extract the string value
        if isinstance(data.get('business_model'), dict):
            bm_dict = data['business_model']
            data['business_model'] = bm_dict.get('model_type') or bm_dict.get('description') or bm_dict.get('value', 'Unknown')
            logger.warning(f"[DICT FIX] {company_name}: business_model was dict, extracted: {data['business_model']}")
        
        # If vertical is a dict, extract the string value
        if isinstance(data.get('vertical'), dict):
            v_dict = data['vertical']
            data['vertical'] = v_dict.get('industry') or v_dict.get('name') or v_dict.get('vertical') or v_dict.get('value', 'Unknown')
            logger.warning(f"[DICT FIX] {company_name}: vertical was dict, extracted: {data['vertical']}")
        
        # If category is a dict, extract the string value
        if isinstance(data.get('category'), dict):
            c_dict = data['category']
            data['category'] = c_dict.get('type') or c_dict.get('category') or c_dict.get('value', 'Unknown')
            logger.warning(f"[DICT FIX] {company_name}: category was dict, extracted: {data['category']}")
        
        # If compute_intensity is a dict, extract the string value
        if isinstance(data.get('compute_intensity'), dict):
            ci_dict = data['compute_intensity']
            data['compute_intensity'] = ci_dict.get('level') or ci_dict.get('intensity') or ci_dict.get('value', 'low')
            logger.warning(f"[DICT FIX] {company_name}: compute_intensity was dict, extracted: {data['compute_intensity']}")
        
        # Infer compute_intensity from gpu_unit_of_work if missing
        if not data.get('compute_intensity') or data.get('compute_intensity') == 'Unknown':
            gpu_unit = str(data.get('gpu_unit_of_work', '')).lower()
            gpu_workload = str(data.get('gpu_workload_description', '')).lower()
            
            # Infer based on the actual workload
            if any(x in gpu_unit for x in ['video', 'code generation', 'full file', 'entire codebase']):
                data['compute_intensity'] = 'extreme'
                logger.info(f"[INFERRED] {company_name}: compute_intensity='extreme' from unit: {gpu_unit[:50]}")
            elif any(x in gpu_unit for x in ['image', 'search', 'synthesis', 'voice', 'real-time', 'transcri']):
                data['compute_intensity'] = 'high'
                logger.info(f"[INFERRED] {company_name}: compute_intensity='high' from unit: {gpu_unit[:50]}")
            elif any(x in gpu_unit for x in ['chat', 'message', 'completion', 'document', 'q&a']):
                data['compute_intensity'] = 'moderate'
                logger.info(f"[INFERRED] {company_name}: compute_intensity='moderate' from unit: {gpu_unit[:50]}")
            elif any(x in gpu_unit for x in ['embed', 'classification', 'traditional ml']):
                data['compute_intensity'] = 'low'
                logger.info(f"[INFERRED] {company_name}: compute_intensity='low' from unit: {gpu_unit[:50]}")
            elif gpu_unit and 'no ai' not in gpu_unit:
                # Has some GPU work but not clear what intensity
                data['compute_intensity'] = 'moderate'
                logger.info(f"[INFERRED] {company_name}: compute_intensity='moderate' as default for GPU workload")
            else:
                data['compute_intensity'] = 'none'
                logger.info(f"[INFERRED] {company_name}: compute_intensity='none' - no GPU workload detected")
        
        # Trust Claude's extraction - don't override with keywords
        business_model = data.get('business_model', '')
        category = data.get('category', '')
        
        # Only set a default if completely missing
        if not category:
            data['category'] = 'Unknown'
            logger.info(f"[CATEGORY] {company_name}: No category extracted, keeping Claude's business_model: {business_model[:100]}")
        
        # Funding round sanity checks
        stage_limits = {
            'seed': {'min': 100_000, 'max': 10_000_000, 'typical': 2_000_000},
            'series a': {'min': 2_000_000, 'max': 50_000_000, 'typical': 15_000_000},
            'series b': {'min': 10_000_000, 'max': 200_000_000, 'typical': 40_000_000},
            'series c': {'min': 30_000_000, 'max': 500_000_000, 'typical': 100_000_000},
            'series d': {'min': 50_000_000, 'max': 1_000_000_000, 'typical': 200_000_000},
            'series e': {'min': 100_000_000, 'max': 2_000_000_000, 'typical': 350_000_000},
            'series f': {'min': 150_000_000, 'max': 5_000_000_000, 'typical': 500_000_000}
        }
        
        # Validate funding rounds
        if 'funding_rounds' in data and isinstance(data['funding_rounds'], list):
            validated_rounds = []
            for round_data in data['funding_rounds']:
                if not isinstance(round_data, dict):
                    continue
                
                amount = round_data.get('amount', 0)
                # Handle None explicitly from Claude's response
                if amount is None:
                    amount = 0
                # CRITICAL: Update the dict to ensure the cleaned value is stored
                round_data['amount'] = amount
                round_type = str(round_data.get('round', '')).lower()
                
                # Find matching stage limits
                stage_limit = None
                for stage_key, limits in stage_limits.items():
                    if stage_key in round_type:
                        stage_limit = limits
                        break
                
                # Validate amount against stage limits - WARN but don't reject
                if stage_limit and amount is not None and amount > 0:
                    if amount > stage_limit['max']:
                        citation_text = round_data.get('citation', {}).get('text', 'NO CITATION')
                        logger.warning(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} exceeds typical max ${stage_limit['max']:,.0f}")
                        logger.warning(f"  Citation: {citation_text[:200]}")
                        logger.warning(f"  Source URL: {round_data.get('citation', {}).get('url', 'NO URL')}")
                        logger.warning(f"  KEEPING this round (trusting extracted data)")
                        round_data['confidence'] = 'high'  # Trust the extracted data
                    elif amount < stage_limit['min']:
                        logger.warning(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} below typical min ${stage_limit['min']:,.0f}")
                        logger.warning(f"  KEEPING this round (trusting extracted data)")
                        round_data['confidence'] = 'medium'
                    else:
                        # Within normal range
                        round_data['confidence'] = 'high'
                    
                    # Check if citation exists
                    if 'citation' not in round_data or not round_data['citation']:
                        logger.info(f"[FUNDING VALIDATION] {company_name} {round_type}: No citation provided - marking as unverified")
                        if not round_data.get('confidence'):
                            round_data['confidence'] = 'low'
                    else:
                        # Log successful validation with citation
                        logger.info(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} VALIDATED")
                        logger.info(f"  Citation: {round_data['citation'].get('text', '')[:100]}...")
                        if not round_data.get('confidence'):
                            round_data['confidence'] = round_data['citation'].get('confidence', 'medium')
                    
                    # Always add the round (trust extracted data)
                    validated_rounds.append(round_data)
                elif amount > 0:
                    # No stage limit found but has amount - keep it
                    logger.info(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} - no stage limit, keeping")
                    validated_rounds.append(round_data)
                else:
                    # Amount is 0 or None - check if we have ANY useful data
                    if round_data.get('investors') or round_data.get('citation') or round_data.get('date'):
                        logger.info(f"[FUNDING VALIDATION] {company_name} {round_type}: No amount but has investors/citation/date, KEEPING")
                        validated_rounds.append(round_data)
                    else:
                        logger.warning(f"[FUNDING VALIDATION] {company_name} {round_type}: No amount, investors, or citation - rejecting as empty shell")
            
            data['funding_rounds'] = validated_rounds
            
            # Recalculate total raised from validated rounds
            total_raised = sum(r.get('amount', 0) or 0 for r in validated_rounds)
            if total_raised > 0:
                data['total_raised'] = total_raised
                logger.info(f"[FUNDING VALIDATION] {company_name}: Validated total raised = ${total_raised:,.0f}")
            else:
                # Fall back to stage-based benchmarks so downstream consumers have a usable value
                stage = str(data.get('stage', '')).lower()
                stage_defaults = {
                    'pre-seed': 2_000_000,
                    'seed': 5_000_000,
                    'series a': 20_000_000,
                    'series b': 60_000_000,
                    'series c': 125_000_000,
                    'series d': 250_000_000,
                    'series e': 400_000_000,
                }
                for stage_key, default_amount in stage_defaults.items():
                    if stage_key in stage:
                        data['total_raised'] = default_amount
                        logger.info(
                            f"[FUNDING VALIDATION] {company_name}: No disclosed totals, using stage benchmark ${default_amount:,.0f}"
                        )
                        break
            
            # Extract all investors from funding rounds to top-level field
            all_investors = []
            for round_data in validated_rounds:
                if 'investors' in round_data and round_data['investors']:
                    # Handle both list and string investors
                    if isinstance(round_data['investors'], list):
                        all_investors.extend(round_data['investors'])
                    else:
                        all_investors.append(round_data['investors'])
            
            # Deduplicate and add to top-level if not already present
            unique_investors = list(set(str(inv) for inv in all_investors if inv))
            if unique_investors and not data.get('investors'):
                data['investors'] = unique_investors
                logger.info(f"[INVESTOR EXTRACTION] {company_name}: Found {len(unique_investors)} investors from funding rounds")
        
        # Ensure reasonable valuations (not trillions for startups)
        valuation = data.get('valuation')
        if valuation is not None and valuation > 100_000_000_000:  # > $100B is suspicious
            logger.warning(f"Suspicious valuation {valuation}, capping at $10B")
            data['valuation'] = min(valuation, 10_000_000_000)
        
        # Ensure reasonable revenue (convert None to 0 for gap filler)
        revenue = data.get('revenue')
        if revenue is None:
            data['revenue'] = 0  # Gap filler will infer from stage
        elif revenue > 10_000_000_000:  # > $10B revenue is suspicious
            logger.warning(f"Suspicious revenue {revenue}, capping at $1B")
            data['revenue'] = min(revenue, 1_000_000_000)
        
        # Ensure ARR <= revenue (convert None to 0)
        if data.get('arr') is None:
            data['arr'] = 0
        arr_value = data.get('arr', 0)
        revenue_value = data.get('revenue', 0)
        
        if arr_value > revenue_value:
            data['arr'] = revenue_value
        
        # Validate growth rate (convert None to 0)
        growth_rate = data.get('growth_rate')
        if growth_rate is None:
            data['growth_rate'] = 0
        elif growth_rate > 10:  # > 1000% is suspicious
            data['growth_rate'] = min(growth_rate, 3.0)  # Cap at 300%
        
        # Ensure other numeric fields are not None
        numeric_fields = ['total_raised', 'valuation', 'team_size', 'burn_rate', 'runway_months']
        for field in numeric_fields:
            if data.get(field) is None:
                data[field] = 0
        
        # Clean and deduplicate funding rounds
        if 'funding_rounds' in data and isinstance(data['funding_rounds'], list):
            seen_rounds = {}
            clean_rounds = []
            
            for round_data in data['funding_rounds']:
                if not isinstance(round_data, dict):
                    continue
                    
                # Extract amount (handle None from Claude)
                amount = round_data.get('amount', 0)
                if amount is None:
                    amount = 0
                
                # ROOT CAUSE FIX: Parse from alternative fields if amount is missing
                # Round sizes are what's listed in articles, so extract from amount_millions or amount_text
                if amount == 0 or amount is None:
                    # Try to parse from amount_millions first (common extraction format)
                    if 'amount_millions' in round_data and round_data['amount_millions']:
                        amount = float(round_data['amount_millions']) * 1_000_000
                    elif 'amount_text' in round_data:
                        # Parse from text like "$3M" or "$3 million"
                        import re
                        text = str(round_data['amount_text'])
                        # Try patterns: "$3M", "$3 million", "3M", "3 million"
                        match = re.search(r'\$?\s*([\d,]+\.?\d*)\s*([MBK]|million|billion|thousand)', text, re.IGNORECASE)
                        if match:
                            num = float(match.group(1).replace(',', ''))
                            unit = match.group(2).upper()
                            if unit in ['B', 'BILLION']:
                                amount = num * 1_000_000_000
                            elif unit in ['M', 'MILLION']:
                                amount = num * 1_000_000
                            elif unit in ['K', 'THOUSAND']:
                                amount = num * 1_000
                
                # Update the dict to ensure clean data - CRITICAL: set amount back to round_data
                round_data['amount'] = amount
                
                # Skip only if no amount AND no useful data
                if (amount is None or amount <= 0) and not round_data.get('investors') and not round_data.get('round'):
                    continue  # Skip only if we have NO useful data at all
                
                # Get round type with intelligent detection
                round_type = round_data.get('round', round_data.get('series'))
                if not round_type:
                    # Extract from any text in the round data
                    text = str(round_data).upper()
                    if 'SERIES E' in text:
                        round_type = 'Series E'
                    elif 'SERIES D' in text:
                        round_type = 'Series D'
                    elif 'SERIES C' in text:
                        round_type = 'Series C'
                    elif 'SERIES B' in text:
                        round_type = 'Series B'
                    elif 'SERIES A' in text:
                        round_type = 'Series A'
                    elif 'SEED' in text:
                        round_type = 'Seed'
                    elif 'PRE-SEED' in text or 'PRESEED' in text:
                        round_type = 'Pre-seed'
                    else:
                        round_type = 'Unknown'
                
                # Create deduplication key
                amount_range = int(amount / 1_000_000)  # Round to nearest million
                round_key = f"{round_type.lower()}_{amount_range}M"
                
                # Check for duplicates
                if round_key in seen_rounds:
                    # Keep the one with more info
                    existing = seen_rounds[round_key]
                    if len(str(round_data.get('date', ''))) > len(str(existing.get('date', ''))):
                        seen_rounds[round_key] = round_data
                else:
                    seen_rounds[round_key] = round_data
                    # Ensure round_data is a dict before accessing its properties
                    if isinstance(round_data, dict):
                        clean_rounds.append({
                            'round': round_type,
                            'amount': amount,
                            'date': round_data.get('date', ''),
                            'investors': round_data.get('investors', [])[:5] if round_data.get('investors') else []
                        })
                    else:
                        clean_rounds.append({
                            'round': round_type,
                            'amount': amount,
                            'date': '',
                            'investors': []
                        })
            
            # Cap at 15 funding rounds maximum
            if len(clean_rounds) > 15:
                logger.warning(f"Found {len(clean_rounds)} funding rounds, capping at 15")
                clean_rounds = sorted(clean_rounds, key=lambda x: x['amount'], reverse=True)[:15]
            
            data['funding_rounds'] = clean_rounds
            data['total_raised'] = sum((r or {}).get('amount', 0) for r in clean_rounds)
        
        # Clean customer list
        if 'customers' in data and data['customers'] is not None:
            data['customers'] = [c for c in data['customers'] if c and len(c) < 50][:20]
        elif 'customers' in data:
            data['customers'] = []
        
        # Clean investor list  
        if 'investors' in data and data['investors'] is not None:
            data['investors'] = [i for i in data['investors'] if i and len(i) < 50][:20]
        elif 'investors' in data:
            data['investors'] = []
        
        # Trust Claude's extraction - no keyword overrides
        category = data.get('category')
        if not category or category.strip() == '' or category.lower() == 'unknown':
            data['category'] = 'Unknown'
            logger.warning(f"[CATEGORY] {company_name}: Category was empty/invalid ('{category}'), setting to Unknown")
        
        logger.info(f"[CATEGORY VALIDATION] {data.get('company_name')}: business_model='{data.get('business_model')}' → category='{data.get('category')}'")
        
        # FINAL VALIDATION: Only set to Unknown if Claude didn't extract anything
        critical_fields = {
            'vertical': 'Unknown',  # Don't assume Technology
            'category': 'Unknown',  # Don't default to saas
            'compute_intensity': None,  # Don't default - should be extracted or inferred
            'business_model': None,  # Keep what Claude extracted
            'customer_segment': 'Unknown',  # Don't assume
            'strategy': 'Unknown'  # Don't assume
        }
        
        for field, default_value in critical_fields.items():
            current_value = data.get(field)
            # Only set default if field is truly missing or None
            if current_value is None or current_value == '':
                if default_value is not None:
                    data[field] = default_value
                    logger.info(f"[FIELD] {company_name}: {field} not extracted by Claude, setting to {default_value}")
            elif current_value == 'Unknown' and default_value and default_value != 'Unknown':
                # If Claude said Unknown but we have a better default, use it
                data[field] = default_value
                logger.info(f"[FIELD] {company_name}: Replacing Unknown with {default_value} for {field}")
        
        # REASSEMBLE flat fields into nested structures for backward compatibility
        # Assemble labor_statistics from flat fields
        if any(data.get(f) for f in ['labor_job_titles', 'labor_worker_count', 'labor_avg_salary']):
            data['labor_statistics'] = {
                'job_titles': data.get('labor_job_titles', []),
                'number_of_workers': data.get('labor_worker_count', 0),
                'avg_salary_per_role': data.get('labor_avg_salary', 0),
                'labor_citation': data.get('labor_data_citation', ''),
                'total_addressable_labor_spend': data.get('labor_total_spend', 0)
            }
            # Clean up flat fields after assembling
            for field in ['labor_job_titles', 'labor_worker_count', 'labor_avg_salary', 'labor_data_citation', 'labor_total_spend']:
                data.pop(field, None)
        
        # Assemble software_market_size from flat fields
        if any(data.get(f) for f in ['software_market_tam', 'software_market_source', 'software_market_citation']):
            data['software_market_size'] = {
                'market_size': data.get('software_market_tam', 0),
                'year': data.get('software_market_year', 2025),
                'source': data.get('software_market_source', ''),
                'citation': data.get('software_market_citation', ''),
                'cagr': data.get('software_market_cagr', 0)
            }
            # Clean up flat fields after assembling
            for field in ['software_market_tam', 'software_market_year', 'software_market_source', 'software_market_citation', 'software_market_cagr']:
                data.pop(field, None)
        
        return data
    
    async def extract_structured_data_from_parsed(self, parsed_data: Dict, company_name: str) -> Dict[str, Any]:
        """
        Extract structured data from pre-parsed data with business context
        This method bridges the gap between MCPOrchestrator and StructuredDataExtractor
        """
        # Convert parsed data to text sources format and use the proper extraction method
        if parsed_data.get('business_context'):
            # Create a text source from the business context
            text_sources = [{
                'source': 'business_context',
                'text': parsed_data.get('business_context', ''),
                'url': 'internal'
            }]
            
            # Use the comprehensive extraction method
            return await self._claude_extract_from_text(
                parsed_data.get('business_context', ''),
                company_name
            )
        else:
            # Fallback: return empty dict if no business_context
            logger.warning(f"No business_context provided for {company_name}, returning empty extraction")
            return {}
    
    def _clean_extracted_data(self, data: Dict[str, Any], company_name: str) -> Dict[str, Any]:
        """
        Clean and preserve all extracted data without overwriting
        Ensures data flows through the pipeline intact
        """
        # Start with all original data
        cleaned = data.copy()
        
        # Ensure company name
        if not cleaned.get('company_name'):
            cleaned['company_name'] = company_name
        
        # Preserve business_model details if it's a dict
        if isinstance(cleaned.get('business_model'), dict):
            # Keep the full details in a separate field
            cleaned['business_model_details'] = cleaned['business_model']
            # Use the model_type or description as the main business_model
            cleaned['business_model'] = cleaned['business_model_details'].get('model_type') or cleaned['business_model_details'].get('description', 'Unknown')
        
        # Preserve vertical details if it's a dict  
        if isinstance(cleaned.get('vertical'), dict):
            cleaned['vertical_details'] = cleaned['vertical']
            cleaned['vertical'] = cleaned['vertical_details'].get('name') or cleaned['vertical_details'].get('vertical', 'Unknown')
        
        # Ensure numeric fields are numbers (not None or strings)
        numeric_fields = ['revenue', 'arr', 'growth_rate', 'valuation', 'total_raised', 
                         'team_size', 'burn_rate', 'runway_months']
        for field in numeric_fields:
            if field in cleaned:
                val = cleaned[field]
                if val is None:
                    cleaned[field] = 0
                elif isinstance(val, str):
                    try:
                        cleaned[field] = float(val.replace(',', '').replace('$', ''))
                    except:
                        cleaned[field] = 0
        
        # Ensure lists are lists
        list_fields = ['customers', 'investors', 'funding_rounds', 'founder_quality_signals', 'traction_signals', 'compute_signals']
        for field in list_fields:
            if field in cleaned and cleaned[field] is None:
                cleaned[field] = []
            elif field in cleaned and not isinstance(cleaned[field], list):
                cleaned[field] = [cleaned[field]]
        
        # Preserve all market position data
        if 'market_position' in cleaned and isinstance(cleaned['market_position'], dict):
            # Keep the full market analysis
            for key, value in cleaned['market_position'].items():
                cleaned[f'market_{key}'] = value
        
        # Preserve key metrics
        if 'key_metrics' in cleaned and isinstance(cleaned['key_metrics'], dict):
            for key, value in cleaned['key_metrics'].items():
                cleaned[f'metric_{key}'] = value
        
        # Log what we're preserving
        logger.info(f"[DATA PRESERVATION] {company_name}: Preserved {len(cleaned)} fields including business_model='{cleaned.get('business_model')}', vertical='{cleaned.get('vertical')}', category='{cleaned.get('category')}'")
        
        return cleaned
    
    def _parse_number(self, text: str) -> float:
        """Parse number from text, handling commas and suffixes"""
        if not text:
            return 0
        
        # Remove commas
        text = text.replace(',', '')
        
        try:
            return float(text)
        except:
            return 0
