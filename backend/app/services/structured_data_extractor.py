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

logger = logging.getLogger(__name__)


class StructuredDataExtractor:
    """
    Claude-based structured data extraction from raw HTML
    Uses BeautifulSoup for parsing and Claude for intelligent extraction
    """
    
    def __init__(self):
        try:
            from app.utils.rate_limiter import create_rate_limited_claude_client
            self.claude_client = create_rate_limited_claude_client(
                api_key=settings.ANTHROPIC_API_KEY or settings.CLAUDE_API_KEY
            )
        except Exception as e:
            logger.warning(f"Claude client not available for extraction: {e}")
            self.claude_client = None
    
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
        
        # Use Claude for intelligent extraction if available
        if self.claude_client:
            return await self._claude_extract(parsed_data, company_name)
        else:
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
            r'\$[\d,]+[MBK]?\s*(million|billion|thousand)?',
            r'raised\s+\$[\d,]+',
            r'Series\s+[A-F]\d?',
            r'seed\s+(round|funding)',
            r'valuation\s+(of\s+)?\$[\d,]+[MBK]?'
        ]
        
        text = soup.get_text()
        mentions = []
        
        for pattern in funding_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            mentions.extend(matches[:3])  # Limit to 3 per pattern
        
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
    
    async def extract_from_text(self, text_sources: List[Dict], company_name: str) -> Dict[str, Any]:
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
        
        # Use Claude for intelligent extraction if available
        if self.claude_client:
            result = await self._claude_extract_from_text(combined_text, company_name)
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
    
    async def _claude_extract_from_text(self, combined_text: str, company_name: str) -> Dict[str, Any]:
        """Use Claude to extract structured data from clean text"""
        
        # Clean company name for better matching
        company_clean = company_name.replace('@', '').strip()
        
        extraction_prompt = f"""You are a venture capital analyst extracting precise data about {company_clean}.

EXTRACTION RULES:
1. Extract funding amounts that are clearly about {company_clean}, even if the company name is in a nearby sentence (within 2-3 sentences)
2. If the article/page title or main content is about {company_clean}, funding amounts mentioned are likely theirs
3. Look for context clues like "The startup", "The company", "It" that refer back to {company_clean}
4. Common patterns: "{company_clean} announced... The round was $X" or "The Series A raised $Y" (when article is about {company_clean})
5. STILL IGNORE funding that explicitly mentions OTHER company names (e.g. "Competitor XYZ raised $50M")
6. If multiple companies are discussed, prioritize funding amounts mentioned closest to {company_clean} references

SOURCES TO ANALYZE:
{combined_text}

Extract and return a JSON object with ONLY verifiable facts about {company_clean}:

**CRITICAL: ALL VALUES MUST BE SIMPLE STRINGS OR NUMBERS - NO NESTED OBJECTS!**

DO NOT return business_model as {{"model_type": "...", "reasoning": "..."}} - WRONG!
MUST return business_model as "AI-powered patient consultation analysis" - CORRECT!

DO NOT return vertical as {{"industry": "Healthcare", "segment": "..."}} - WRONG!  
MUST return vertical as "Healthcare" - CORRECT!

DO NOT return category as {{"type": "ai_first", "confidence": "high"}} - WRONG!
MUST return category as "ai_first" - CORRECT!

{{
  "company_name": "{company_clean}",
  "website_url": "actual company website if found",
  "one_liner": "concise description of what the company does",
  "funding_rounds": [
    {{
      "round": "Series B", 
      "amount": 150000000, 
      "date": "2023-09-01", 
      "investors": ["Andreessen Horowitz", "Sequoia"], 
      "valuation": 1500000000,
      "citation": {{
        "source_index": 0,
        "text": "exact text snippet mentioning this funding round",
        "confidence": "high/medium/low based on clarity"
      }}
    }}
  ],
  "total_raised": 265000000,
  "valuation": 1500000000,
  "revenue": 1000000000,
  "arr": 1000000000,
  "growth_rate": 3.0,
  "team_size": 500,
  "founder": "John Doe",
  "founder_background": "ex-Google, Stanford CS, serial entrepreneur",
  "founder_quality_signals": ["signal 1", "signal 2"],
  "customers": ["Real Company 1", "Real Company 2"],
  "customer_quality": "Enterprise",
  "investors": ["Real VC 1", "Real VC 2"],
  "business_model": "AI-powered patient consultation analysis for healthcare providers - records and analyzes doctor-patient interactions to improve diagnoses",
  "strategy": "land and expand",
  "vertical": "Healthcare",
  "customer_segment": "Enterprise",
  "category": "ai_first",
  "gpu_unit_of_work": "per medical consultation analyzed",
  "gpu_workload_description": "Real-time transcription of 30-minute consultations using Whisper, followed by GPT-4 analysis for medical insights and documentation generation",
  "compute_intensity": "high",
  "compute_signals": ["Real-time speech-to-text for 30min sessions", "GPT-4 medical analysis", "Generates 5-page clinical summaries"],
  "unit_economics": {
    "gpu_cost_per_unit": 2.50,
    "units_per_customer_per_month": 200,
    "reasoning": "Each consultation requires ~$0.50 transcription + $2.00 GPT-4 analysis. Enterprise hospitals average 200 consultations/month"
  },
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
  }}
}}

REQUIRED FIELD VALUES:
- business_model: STRING - Must be specific description like "AI-powered patient consultation analysis for healthcare" NOT a dict
- vertical: STRING - Industry like "Healthcare", "FinTech", "Legal Tech", "Defense", "Marketing", etc. 
- category: STRING - Must be one of: "ai_first", "ai_saas", "saas", "marketplace", "services", "rollup", "hardware"
- gpu_unit_of_work: STRING - The atomic unit that triggers GPU usage. Semantically derive from what the product actually does:
  * For code generation tools: "per code completion" or "per file generated"  
  * For search/RAG: "per search query" or "per research task"
  * For transcription: "per minute of audio" or "per meeting transcribed"
  * For image/video: "per image generated" or "per video rendered"
  * For chat: "per conversation" or "per message exchange"
  * For analysis: "per document analyzed" or "per dataset processed"
- gpu_workload_description: STRING - Describe the actual compute workload in technical detail
- compute_intensity: STRING - Based on the workload description, infer intensity:
  * "extreme": Full code file generation, video generation, multi-step agents
  * "high": Search with synthesis, image generation, real-time transcription
  * "moderate": Chat responses, simple completions
  * "low": Traditional ML, embeddings, classification
  * "none": No AI/GPU workload
- compute_signals: ARRAY - Specific technical signals about GPU usage extracted from description
- unit_economics: OBJECT with gpu_cost_per_unit, units_per_customer_per_month, and reasoning
- All other text fields: STRING values, use empty string "" if unknown
- All numeric fields: NUMBER values, use 0 if unknown

EXTRACTION GUIDELINES FOR {company_clean}:
1. Extract funding amounts that are about {company_clean}:
   - Direct mentions: "{company_clean} raised $X" → confidence: high
   - Context mentions: "The startup raised $X" (when article is about {company_clean}) → confidence: medium
   - Nearby mentions: Company name within 2-3 sentences of amount → confidence: medium
   - DO NOT use amounts that explicitly name other companies
2. CITATIONS - Each funding round should include:
   - source_index: Which [SOURCE N] the information came from
   - text: The relevant text snippet (50-200 chars) that mentions this funding
   - confidence: "high" if company name in same sentence, "medium" if contextually clear, "low" if inferred
3. SANITY CHECKS for funding amounts:
   - Seed: Usually $500K-$10M (rarely >$25M but possible in 2023-2024)
   - Series A: Usually $5M-$35M (rarely >$75M)
   - Series B: Usually $20M-$100M (rarely >$250M)
   - Series C: Usually $50M-$250M (rarely >$600M)
   - If amount seems VERY wrong for the stage (>3x typical max), flag with low confidence but still include
4. For revenue/ARR: Must be about {company_clean} specifically
5. Convert all amounts to raw dollars: $50M = 50000000
6. Round dates: Use "YYYY-MM-DD" format
   - If only month/year: "2024-08-01" for August 2024
   - If only year: "2024-01-01" for 2024
7. DO NOT GUESS - use null/0 for unknown values
8. IGNORE all data about companies other than {company_clean}
9. CATEGORY INFERENCE - REQUIRED: Semantically analyze the business_model to determine category:
   - "full_stack_ai": AI-enabled company that delivers the COMPLETE service (e.g., AI insurance company that underwrites/pays claims, AI law firm that files documents, AI accountant that files taxes)
   - "ai_first": Core product IS the AI model or AI capability (selling AI tools/APIs)
   - "ai_saas": Traditional SaaS enhanced with AI features
   - "rollup": Acquiring and consolidating multiple companies
   - "marketplace": Connects buyers and sellers, takes a transaction fee
   - "saas": Software delivered as a subscription service
   - "services": Human labor/consulting as primary offering
   - "hardware": Physical products or devices
   - Analyze what the company actually DOES, not keywords

ENHANCED EXTRACTION FOR INVESTMENT CASE:
9. FOUNDER QUALITY - Extract specific signals:
   - Educational background (university names)
   - Previous companies (especially exits)
   - Previous roles at notable companies
   - Technical credentials (PhD, patents, publications)
10. BUSINESS MODEL & STRATEGY:
   - Roll-up: Look for "acquisition", "consolidation", "buy and build"
11. GPU WORKLOAD ANALYSIS - CRITICAL:
   Analyze the business model to understand the actual computational work being performed:
   - What action does the user take that triggers GPU usage?
   - What is the atomic unit of work? (Not generic "transaction" but specific: "legal document review", "code file generation", "30-min meeting transcription")
   - What is the technical workload? (LLM inference, embedding generation, diffusion model, speech-to-text, etc.)
   - How frequently would a typical customer trigger this unit? (Based on the product's actual use case)
   - Estimate the GPU cost per unit based on the workload complexity and duration
12. TRACTION SIGNALS - Extract ACTUAL data:
   - Named customers (Fortune 500, specific companies)
   - Specific metrics with numbers
   - Growth percentages with timeframes
   - Market share or ranking claims
13. VERTICAL - Be specific:
   - Not just "fintech" but "payments infrastructure" or "lending platform"
   - Not just "healthtech" but "clinical trials" or "patient engagement"

VALIDATION REQUIREMENTS:
- Each funding round must pass sanity check for its stage
- Total raised must equal sum of all rounds
- Valuation must be reasonable (usually 5-20x last round amount)
- Revenue/ARR must be realistic for company stage
"""
        
        try:
            # Log that we're using Claude
            logger.info(f"Using Claude to extract data for {company_name}")
            
            # Add timeout to Claude call
            import asyncio
            response = await asyncio.wait_for(
                self.claude_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    temperature=0,
                    messages=[
                        {"role": "user", "content": extraction_prompt}
                    ]
                ),
                timeout=30.0  # 30 second timeout for complex analysis
            )
            logger.info(f"Claude extraction successful for {company_name}")
            
            # Parse Claude's response
            import json
            response_text = response.content[0].text if response.content else None
            
            if not response_text:
                logger.warning("Empty Claude response, using basic extraction")
                return self._basic_text_extract([{'text': combined_text}], company_name)
            
            # Extract JSON from the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
            else:
                result = json.loads(response_text)
            
            # Validate the data
            return self._validate_extracted_data(result)
            
        except asyncio.TimeoutError:
            logger.error(f"Claude text extraction timed out for {company_name}")
            return self._basic_text_extract([{'text': combined_text}], company_name)
        except Exception as e:
            logger.error(f"Claude text extraction failed for {company_name}: {type(e).__name__}: {e}")
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
                        result['total_raised'] = max(result['total_raised'], value)
            
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
        """Use Claude to intelligently structure the parsed data"""
        if not self.claude_client:
            return self._fallback_extract(parsed_data, company_name)
        
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
15. stage: string (Seed/Series A/Series B/etc)

IMPORTANT: 
- BE SPECIFIC about business_model and sector - describe what they actually do
- Only include data you can verify from the provided text
- Valuations should be reasonable for startups (not trillions)
- Convert all money to raw numbers (1M = 1000000)
- Return empty/0 for missing data rather than guessing
"""
        
        try:
            response = await asyncio.to_thread(
                self.claude_client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": extraction_prompt}]
            )
            
            # Parse Claude's response
            import json
            response_text = response.content[0].text
            
            # Try to extract JSON from the response
            # Sometimes Claude returns JSON wrapped in markdown or with explanation
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
            else:
                # If no JSON found, try parsing the whole response
                result = json.loads(response_text)
            
            # Validate the data
            return self._validate_extracted_data(result)
            
        except Exception as e:
            logger.error(f"Claude extraction failed: {e}")
            return self._fallback_extract(parsed_data, company_name)
    
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
        
        # Parse funding mentions for amounts
        for mention in parsed_data.get('funding_mentions', []):
            amount_match = re.search(r'\$?([\d,]+)([MBK])?', mention)
            if amount_match:
                amount = self._parse_number(amount_match.group(1))
                multiplier = {'M': 1000000, 'B': 1000000000, 'K': 1000}.get(
                    amount_match.group(2), 1
                )
                result['total_raised'] += amount * multiplier
        
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
        
        logger.info(f"[CLAUDE RAW EXTRACTION] {company_name}: revenue=${revenue:,.0f}, growth_rate={growth_rate:.2f}, arr=${arr:,.0f}, valuation=${valuation:,.0f}")
        
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
        
        # CRITICAL: Infer category from business_model if missing or generic
        business_model = data.get('business_model', '')
        category = data.get('category', '')
        
        # Only override if category is missing, 'Unknown', or generic 'saas'
        if not category or category.lower() in ['unknown', 'saas', '']:
            # Semantic category inference based on business model description
            business_model_lower = business_model.lower()
            
            if any(term in business_model_lower for term in ['ai agent', 'llm', 'foundation model', 'generative ai', 'machine learning model', 'ai-powered', 'ai platform']):
                data['category'] = 'ai_first'
                logger.info(f"[CATEGORY INFERENCE] {company_name}: Inferred 'ai_first' from business_model: {business_model[:100]}")
            elif any(term in business_model_lower for term in ['roll-up', 'acquisition', 'consolidation', 'buy and build']):
                if 'ai' in business_model_lower:
                    data['category'] = 'ai_enhanced_rollup'
                else:
                    data['category'] = 'rollup'
                logger.info(f"[CATEGORY INFERENCE] {company_name}: Inferred rollup category from business_model")
            elif any(term in business_model_lower for term in ['marketplace', 'two-sided', 'platform connecting']):
                data['category'] = 'marketplace'
                logger.info(f"[CATEGORY INFERENCE] {company_name}: Inferred 'marketplace' from business_model")
            elif any(term in business_model_lower for term in ['hardware', 'device', 'equipment', 'robotics']):
                data['category'] = 'hardware'
                logger.info(f"[CATEGORY INFERENCE] {company_name}: Inferred 'hardware' from business_model")
            elif any(term in business_model_lower for term in ['consulting', 'agency', 'services', 'professional services']):
                data['category'] = 'services'
                logger.info(f"[CATEGORY INFERENCE] {company_name}: Inferred 'services' from business_model")
            elif 'saas' in business_model_lower or 'software' in business_model_lower:
                # Check if it's AI-enhanced SaaS
                if 'ai' in business_model_lower:
                    data['category'] = 'ai_saas'
                else:
                    data['category'] = 'saas'
                logger.info(f"[CATEGORY INFERENCE] {company_name}: Inferred SaaS category from business_model")
            else:
                # Default to saas if we have some business model but can't categorize
                if business_model and business_model != 'Unknown':
                    data['category'] = 'saas'
                    logger.info(f"[CATEGORY INFERENCE] {company_name}: Defaulted to 'saas' for business_model: {business_model[:100]}")
        
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
                round_type = str(round_data.get('round', '')).lower()
                
                # Find matching stage limits
                stage_limit = None
                for stage_key, limits in stage_limits.items():
                    if stage_key in round_type:
                        stage_limit = limits
                        break
                
                # Validate amount against stage limits
                if stage_limit and amount is not None and amount > 0:
                    if amount > stage_limit['max']:
                        citation_text = round_data.get('citation', {}).get('text', 'NO CITATION')
                        logger.warning(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} exceeds max ${stage_limit['max']:,.0f}")
                        logger.warning(f"  Citation: {citation_text[:200]}")
                        logger.warning(f"  Source URL: {round_data.get('citation', {}).get('url', 'NO URL')}")
                        logger.warning(f"  REJECTING this funding round")
                        continue  # Skip this round entirely
                    elif amount < stage_limit['min']:
                        logger.warning(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} below min ${stage_limit['min']:,.0f} - REJECTING")
                        continue  # Skip this round entirely
                    
                    # Check if citation exists
                    if 'citation' not in round_data or not round_data['citation']:
                        logger.warning(f"[FUNDING VALIDATION] {company_name} {round_type}: No citation provided - marking as unverified")
                        round_data['confidence'] = 'low'
                    else:
                        # Log successful validation with citation
                        logger.info(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} VALIDATED")
                        logger.info(f"  Citation: {round_data['citation'].get('text', '')[:100]}...")
                        round_data['confidence'] = round_data['citation'].get('confidence', 'medium')
                    
                    # Only add if validation passed (we didn't continue above)
                    validated_rounds.append(round_data)
                elif amount > 0:
                    # No stage limit found but has amount - keep it
                    logger.info(f"[FUNDING VALIDATION] {company_name} {round_type}: ${amount:,.0f} - no stage limit, keeping")
                    validated_rounds.append(round_data)
                else:
                    # Amount is 0 or None - check if we have investors at least
                    if round_data.get('investors'):
                        logger.info(f"[FUNDING VALIDATION] {company_name} {round_type}: No amount but has investors, keeping")
                        validated_rounds.append(round_data)
                    else:
                        logger.warning(f"[FUNDING VALIDATION] {company_name} {round_type}: No amount and no investors - REJECTING")
            
            data['funding_rounds'] = validated_rounds
            
            # Recalculate total raised from validated rounds
            total_raised = sum(r.get('amount', 0) or 0 for r in validated_rounds)
            if total_raised > 0:
                data['total_raised'] = total_raised
                logger.info(f"[FUNDING VALIDATION] {company_name}: Validated total raised = ${total_raised:,.0f}")
            
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
                if amount == 0:
                    # Try to parse from text if amount is missing
                    if 'amount_millions' in round_data:
                        amount = round_data['amount_millions'] * 1_000_000
                    elif 'amount_text' in round_data:
                        # Parse from text like "$150M"
                        import re
                        match = re.search(r'\$?([\d,]+\.?\d*)\s*([MBK])', str(round_data['amount_text']))
                        if match:
                            num = float(match.group(1).replace(',', ''))
                            unit = match.group(2)
                            if unit == 'B':
                                amount = num * 1_000_000_000
                            elif unit == 'M':
                                amount = num * 1_000_000
                            elif unit == 'K':
                                amount = num * 1_000
                
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
            data['total_raised'] = sum(r['amount'] for r in clean_rounds)
        
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
        
        # Semantic category inference from business model description
        if not data.get('category') or data.get('category') == 'Unknown':
            business_model = str(data.get('business_model', '')).lower()
            strategy = str(data.get('strategy', '')).lower()
            vertical = str(data.get('vertical', '')).lower()
            compute_intensity = str(data.get('compute_intensity', '')).lower()
            
            # Semantic inference based on actual business description
            # AI-first: Companies building AI/ML models, inference engines, or AI infrastructure
            if any(term in business_model for term in ['foundation model', 'llm', 'inference engine', 'ai model', 
                                                        'machine learning platform', 'generative ai', 'neural network',
                                                        'image generation', 'text generation', 'ai infrastructure']):
                if any(term in business_model or term in strategy for term in ['roll-up', 'acquisition', 'consolidat']):
                    data['category'] = 'ai_enhanced_rollup'
                else:
                    data['category'] = 'ai_first'
                    
            # AI-SaaS: Traditional SaaS enhanced with AI features
            elif 'ai' in business_model and any(term in business_model for term in ['saas', 'software', 'platform', 'automation']):
                data['category'] = 'ai_saas'
                
            # API/Infrastructure: Companies providing APIs or developer infrastructure
            elif any(term in business_model for term in ['api', 'infrastructure', 'developer tools', 'devops', 
                                                         'backend service', 'cloud service', 'data pipeline']):
                # Special case for AI inference APIs
                if 'inference' in business_model or 'ai' in business_model or compute_intensity == 'high':
                    data['category'] = 'ai_first'  # AI infrastructure companies
                else:
                    data['category'] = 'saas'  # Traditional infrastructure SaaS
                    
            # Roll-up/M&A strategies
            elif any(term in business_model or term in strategy for term in ['roll-up', 'roll up', 'acquisition', 
                                                                               'consolidation', 'buy and build', 'm&a']):
                data['category'] = 'rollup'
                
            # Marketplace/Platform
            elif any(term in business_model for term in ['marketplace', 'two-sided', 'connects buyers', 
                                                         'matching platform', 'exchange']):
                data['category'] = 'marketplace'
                
            # Services/Consulting
            elif any(term in business_model for term in ['consulting', 'agency', 'professional services', 
                                                         'managed service', 'outsourcing']):
                # Special case: Digitally-enabled services (like Sidekick's IFA model)
                if any(term in business_model for term in ['platform', 'digital', 'automated', 'tech-enabled']):
                    data['category'] = 'saas'  # Tech-enabled services are more like SaaS
                else:
                    data['category'] = 'services'
                    
            # Hardware
            elif any(term in business_model for term in ['hardware', 'device', 'equipment', 'physical product']):
                data['category'] = 'hardware'
                
            # Default to SaaS for software companies
            elif any(term in business_model for term in ['software', 'platform', 'app', 'application', 'system']):
                data['category'] = 'saas'
                
            else:
                # Use vertical as a hint for category
                if vertical in ['fintech', 'healthtech', 'edtech', 'legal tech', 'martech']:
                    data['category'] = 'saas'  # Most verticals are SaaS
                else:
                    data['category'] = 'saas'  # Default
                    logger.warning(f"Could not semantically infer category from business_model '{data.get('business_model')}', defaulting to 'saas'")
        
        logger.info(f"[CATEGORY VALIDATION] {data.get('company_name')}: business_model='{data.get('business_model')}' → category='{data.get('category')}'")
        
        # FINAL VALIDATION: Ensure critical fields are NEVER missing
        critical_fields = {
            'vertical': 'Technology',  # Default if we can't determine
            'category': 'saas',  # Default category
            'compute_intensity': 'medium',  # Default compute intensity
            'business_model': 'Software platform',  # Generic default
            'customer_segment': 'Mid-market',  # Default segment
            'strategy': 'organic growth'  # Default strategy
        }
        
        for field, default_value in critical_fields.items():
            current_value = data.get(field)
            # Check if field is missing, None, empty string, or "Unknown"
            if not current_value or current_value in ['Unknown', '', None]:
                # Try to infer from other fields before using default
                if field == 'vertical' and data.get('business_model'):
                    # Infer vertical from business model
                    bm_lower = data['business_model'].lower()
                    if 'healthcare' in bm_lower or 'medical' in bm_lower or 'patient' in bm_lower:
                        data[field] = 'Healthcare'
                    elif 'legal' in bm_lower or 'law' in bm_lower or 'contract' in bm_lower:
                        data[field] = 'Legal Tech'
                    elif 'finance' in bm_lower or 'payment' in bm_lower or 'banking' in bm_lower:
                        data[field] = 'FinTech'
                    elif 'defense' in bm_lower or 'military' in bm_lower or 'weapon' in bm_lower:
                        data[field] = 'Defense'
                    elif 'marketing' in bm_lower or 'advertising' in bm_lower or 'market research' in bm_lower:
                        data[field] = 'Marketing'
                    elif 'developer' in bm_lower or 'infrastructure' in bm_lower or 'api' in bm_lower:
                        data[field] = 'Developer Tools'
                    else:
                        data[field] = default_value
                    logger.info(f"[FIELD INFERENCE] {company_name}: Inferred {field}='{data[field]}' from business_model")
                else:
                    data[field] = default_value
                    logger.warning(f"[FIELD DEFAULT] {company_name}: Missing {field}, using default: {default_value}")
        
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