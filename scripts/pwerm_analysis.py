#!/usr/bin/env python3
"""
Enhanced PWERM (Probability-Weighted Expected Return Model) Analysis
with automatic sector categorization and market analysis using Claude
"""

import json
import sys
import os
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Dynamic year calculation - We're in August 2025
CURRENT_YEAR = datetime.now().year  # 2025
NEXT_YEAR = CURRENT_YEAR + 1  # 2026
PREV_YEAR = CURRENT_YEAR - 1  # 2024
TWO_YEARS_AGO = CURRENT_YEAR - 2  # 2023

# Set matplotlib to use non-interactive backend for server environment
plt.switch_backend('Agg')

class PWERMAnalyzer:
    def __init__(self, tavily_api_key: str = None, claude_api_key: str = None):
        """
        Initialize PWERM Analyzer with API integrations
        
        Args:
            tavily_api_key (str): Tavily API key for market research
            claude_api_key (str): Claude API key for analysis
        """
        self.tavily_api_key = tavily_api_key
        self.claude_api_key = claude_api_key
        self.tavily_base_url = "https://api.tavily.com/search"
        self.claude_base_url = "https://api.anthropic.com/v1/messages"
        self._processed_urls = set()  # Track processed URLs to avoid duplicates
        self.num_scenarios = 499  # PWERM parameters - 499 discrete scenarios
        self._saas_index_cache = None  # Cache for SaaS index data
        self._saas_index_cache_time = None
    
    def _clean_text(self, text: str, max_length: int = 500) -> str:
        """Clean text, removing corrupted data and excessive repetition"""
        if not text:
            return ""
        # Remove excessive repeated characters (like AAAAAAA...)
        import re
        text = re.sub(r'([A-Za-z])\1{50,}', '', text)  # Only remove if 50+ repetitions
        # Remove null bytes and other problematic characters
        text = text.replace('\x00', '').replace('\r', '\n')
        # Normalize whitespace
        text = ' '.join(text.split())
        # Truncate to max length if needed
        if len(text) > max_length:
            text = text[:max_length] + "..."
        return text
    
    def _process_tavily_results(self, results: List[Dict], company_name: str) -> List[Dict]:
        """Process Tavily results to clean content while preserving search breadth"""
        processed = []
        
        for result in results:
            # Skip if we've already processed this URL
            url = result.get('url', '')
            if url in self._processed_urls:
                continue
            self._processed_urls.add(url)
            
            # Clean the content but keep full information
            processed_result = {
                'url': url,
                'title': result.get('title', ''),
                'content': result.get('content', ''),  # Keep FULL content for deep analysis
                'score': result.get('score', 0),
                'raw_content': None  # Remove the raw_content field if present
            }
            
            processed.append(processed_result)
        
        return processed  # Return all results, not just top 5
    
    def _merge_intelligence(self, existing: Dict, new: Dict) -> Dict:
        """Merge two intelligence dictionaries without duplication"""
        merged = existing.copy()
        
        for key, value in new.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, (int, float)) and value > 0:
                # For numbers, keep the non-zero value
                if merged[key] == 0 or merged[key] is None:
                    merged[key] = value
            elif isinstance(value, list) and value:
                # For lists, merge without duplicates
                existing_list = merged.get(key, [])
                for item in value:
                    if item not in existing_list:
                        existing_list.append(item)
                merged[key] = existing_list
            elif isinstance(value, dict) and value:
                # For dicts, merge recursively
                merged[key] = self._merge_intelligence(merged.get(key, {}), value)
        
        return merged
    
    def _fetch_live_saas_index(self) -> Dict:
        """Fetch live SaaS index data from publicsaascompanies.com"""
        # Check cache (valid for 1 hour)
        if self._saas_index_cache and self._saas_index_cache_time:
            if (datetime.now() - self._saas_index_cache_time).seconds < 3600:
                return self._saas_index_cache
        
        try:
            # Try to fetch from the API endpoint
            response = requests.get(
                'https://www.publicsaascompanies.com/api/companies',
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'PWERM-Analyzer/1.0'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                companies = data.get('companies', data) if isinstance(data, dict) else data
                
                # Calculate median EV/Revenue multiple
                valid_multiples = []
                for company in companies:
                    if isinstance(company, dict):
                        ev = company.get('ev') or company.get('enterprise_value') or 0
                        revenue = company.get('revenue') or company.get('ltm_revenue') or 0
                        if ev > 0 and revenue > 0:
                            multiple = ev / revenue
                            if 0 < multiple < 100:  # Filter outliers
                                valid_multiples.append(multiple)
                
                if valid_multiples:
                    median = np.median(valid_multiples)
                    result = {
                        'median_ev_revenue': median,
                        'dlom_adjusted': median * 0.7,  # Apply 30% DLOM
                        'p25_multiple': np.percentile(valid_multiples, 25),
                        'p75_multiple': np.percentile(valid_multiples, 75),
                        'total_companies': len(valid_multiples),
                        'source': 'live_publicsaascompanies',
                        'timestamp': datetime.now().isoformat()
                    }
                    self._saas_index_cache = result
                    self._saas_index_cache_time = datetime.now()
                    sys.stderr.write(f"Fetched live SaaS index: Median {median:.1f}x, DLOM-adjusted {median*0.7:.1f}x\n")
                    return result
        except Exception as e:
            sys.stderr.write(f"Error fetching live SaaS index: {e}\n")
        
        # Fallback to SVB/Carta benchmark data (US private companies)
        # Using Series B median (25X) as baseline for growth companies
        fallback = {
            'median_ev_revenue': 25.0,  # Series B median from SVB/Carta benchmark
            'dlom_adjusted': 25.0,  # No DLOM needed - already private company multiples
            'p25_multiple': 15.0,  # Series A median
            'p75_multiple': 50.0,  # Series B 25th percentile
            'source': 'svb_carta_benchmark',
            'timestamp': datetime.now().isoformat()
        }
        sys.stderr.write(f"Using SVB/Carta benchmark: Median 25x (private companies)\n")
        return fallback
        
        # Use existing sector taxonomy from the platform
        self.sector_taxonomy = [
            'AI', 'Adtech', 'B2B Fintech', 'B2C Fintech', 'B2C', 'Capital Markets',
            'Climate Deep', 'Climate Software', 'Crypto', 'Cyber', 'Deep', 'Dev Tool',
            'E-com', 'Edtech', 'Fintech', 'HR', 'Health', 'Insurtech', 'Marketplace',
            'Renewables', 'SaaS', 'Supply-Chain', 'Technology', 'Travel'
        ]
        
        # Subsectors mapping for each sector
        self.subsectors = {
            'AI': ['Machine Learning', 'Computer Vision', 'Natural Language Processing', 'Generative AI', 'AI Infrastructure'],
            'Adtech': ['Ad Management', 'Programmatic Advertising', 'Ad Analytics', 'Ad Fraud Prevention'],
            'B2B Fintech': ['Payments', 'Lending', 'Treasury Management', 'Banking Infrastructure', 'RegTech'],
            'B2C Fintech': ['Digital Banking', 'Personal Finance', 'Investment Apps', 'Insurance Tech'],
            'B2C': ['Consumer Apps', 'Social Media', 'Entertainment', 'Lifestyle'],
            'Capital Markets': ['Trading Platforms', 'Market Data', 'Risk Management', 'Compliance'],
            'Climate Deep': ['Carbon Capture', 'Energy Storage', 'Hydrogen', 'Nuclear Fusion'],
            'Climate Software': ['Carbon Accounting', 'ESG Reporting', 'Climate Risk', 'Sustainability Management'],
            'Crypto': ['DeFi', 'NFTs', 'Blockchain Infrastructure', 'Crypto Trading', 'Web3'],
            'Cyber': ['Security Software', 'Threat Detection', 'Identity Management', 'Compliance'],
            'Deep': ['Biotech', 'Quantum Computing', 'Space Tech', 'Advanced Materials'],
            'Dev Tool': ['Development Tools', 'DevOps', 'Code Quality', 'Testing', 'Monitoring'],
            'E-com': ['E-commerce Platforms', 'Marketplaces', 'Retail Tech', 'D2C'],
            'Edtech': ['Online Learning', 'Educational Software', 'Skills Training', 'Corporate Training'],
            'Fintech': ['Payments', 'Lending', 'Banking', 'Insurance', 'Wealth Management'],
            'HR': ['HR Software', 'Recruitment', 'Employee Management', 'Payroll', 'Benefits'],
            'Health': ['Digital Health', 'Telemedicine', 'Health Analytics', 'Medical Devices'],
            'Insurtech': ['Insurance Platforms', 'Risk Assessment', 'Claims Processing', 'Underwriting'],
            'Marketplace': ['B2B Marketplaces', 'C2C Marketplaces', 'Service Marketplaces', 'Product Marketplaces'],
            'Renewables': ['Solar', 'Wind', 'Battery Storage', 'Grid Management', 'Energy Trading'],
            'SaaS': ['Enterprise SaaS', 'SMB SaaS', 'Vertical SaaS', 'Horizontal SaaS'],
            'Supply-Chain': ['Logistics', 'Inventory Management', 'Procurement', 'Warehouse Management'],
            'Technology': ['General Tech', 'Software', 'Hardware', 'IT Services'],
            'Travel': ['Travel Booking', 'Travel Tech', 'Hospitality Tech', 'Transportation']
        }
    
    def categorize_company_with_claude(self, company_name: str) -> Dict:
        """
        Use Claude to automatically categorize a company into sector and subsector
        """
        if not self.claude_api_key:
            raise Exception("Claude API key required for company categorization")
        
        try:
            prompt = f"""
            Analyze the company "{company_name}" and categorize it into the most appropriate sector and subsector from the following taxonomy:

            SECTORS AND SUBSECTORS:
            - AI: Machine Learning, Computer Vision, Natural Language Processing, Generative AI, AI Infrastructure
            - Adtech: Ad Management, Programmatic Advertising, Ad Analytics, Ad Fraud Prevention
            - B2B Fintech: Payments, Lending, Treasury Management, Banking Infrastructure, RegTech
            - B2C Fintech: Digital Banking, Personal Finance, Investment Apps, Insurance Tech
            - B2C: Consumer Apps, Social Media, Entertainment, Lifestyle
            - Capital Markets: Trading Platforms, Market Data, Risk Management, Compliance
            - Climate Deep: Carbon Capture, Energy Storage, Hydrogen, Nuclear Fusion
            - Climate Software: Carbon Accounting, ESG Reporting, Climate Risk, Sustainability Management
            - Crypto: DeFi, NFTs, Blockchain Infrastructure, Crypto Trading, Web3
            - Cyber: Security Software, Threat Detection, Identity Management, Compliance
            - Deep: Biotech, Quantum Computing, Space Tech, Advanced Materials
            - Dev Tool: Development Tools, DevOps, Code Quality, Testing, Monitoring
            - E-com: E-commerce Platforms, Marketplaces, Retail Tech, D2C
            - Edtech: Online Learning, Educational Software, Skills Training, Corporate Training
            - Fintech: Payments, Lending, Banking, Insurance, Wealth Management
            - HR: HR Software, Recruitment, Employee Management, Payroll, Benefits
            - Health: Digital Health, Telemedicine, Health Analytics, Medical Devices
            - Insurtech: Insurance Platforms, Risk Assessment, Claims Processing, Underwriting
            - Marketplace: B2B Marketplaces, C2C Marketplaces, Service Marketplaces, Product Marketplaces
            - Renewables: Solar, Wind, Battery Storage, Grid Management, Energy Trading
            - SaaS: Enterprise SaaS, SMB SaaS, Vertical SaaS, Horizontal SaaS
            - Supply-Chain: Logistics, Inventory Management, Procurement, Warehouse Management
            - Technology: General Tech, Software, Hardware, IT Services
            - Travel: Travel Booking, Travel Tech, Hospitality Tech, Transportation

            Be precise and accurate. For example:
            - Revolut would be B2C Fintech with subsector "Digital Banking"
            - Stripe would be B2B Fintech with subsector "Payments"
            - OpenAI would be AI with subsector "Generative AI"

            Return your analysis in JSON format:
            {{
                "sector": "the most appropriate sector",
                "subsector": "the most specific subsector",
                "confidence": "high/medium/low",
                "reasoning": "brief explanation of categorization"
            }}
            """
            
            sys.stderr.write(f"Calling Claude API for categorization...\n")
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            sys.stderr.write(f"Claude API response status: {response.status_code}\n")
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    categorization = json.loads(json_match.group())
                    return categorization
                else:
                    sys.stderr.write(f"Failed to parse JSON from Claude response: {content}\n")
                    return {
                        "sector": "SaaS",
                        "subsector": "Enterprise Software",
                        "confidence": "low",
                        "reasoning": "Failed to parse Claude response"
                    }
            elif response.status_code == 429:
                sys.stderr.write(f"Claude API rate limit hit. Response: {response.text}\n")
                # Return default categorization
                return {
                    "sector": "SaaS",
                    "subsector": "Enterprise Software",
                    "confidence": "low",
                    "reasoning": "Using default due to API rate limit"
                }
            else:
                sys.stderr.write(f"Claude API error: {response.status_code} - {response.text}\n")
                # Return default categorization
                return {
                    "sector": "SaaS",
                    "subsector": "Enterprise Software", 
                    "confidence": "low",
                    "reasoning": f"Using default due to API error: {response.status_code}"
                }
                
        except Exception as e:
            sys.stderr.write(f"Claude categorization error: {e}\n")
            raise e

    def analyze_market_landscape(self, company_name: str, sector: str, subsector: str) -> Dict:
        """
        Analyze market landscape including submarket, incumbents, competitors, and fragmentation
        """
        sys.stderr.write(f"\n=== Starting market landscape analysis for {company_name} ===\n")
        sys.stderr.write(f"Sector: {sector}, Subsector: {subsector}\n")
        
        if not self.claude_api_key:
            sys.stderr.write("ERROR: Claude API key not found\n")
            raise Exception("Claude API key required for market landscape analysis")
        
        sys.stderr.write(f"Claude API key found: {self.claude_api_key[:10]}...\n")
        
        try:
            prompt = f"""
            Analyze the market landscape for "{company_name}" in the {subsector} subsector of {sector}.

            Provide a comprehensive market analysis including:

            1. MAIN_MARKET: Define the broad market category (e.g., "Sales Intelligence", "CRM", "Marketing Automation")
            2. SUBMARKET: Define the SPECIFIC submarket/niche within the main market (e.g., "B2B contact data enrichment", "LinkedIn alternative for sales prospecting")
            3. INCUMBENTS: List major established players (public companies, large private companies)
            4. COMPETITORS: List direct competitors (similar stage, similar product)
            5. SUPPLIER_COMPETITORS: Identify companies that are BOTH suppliers AND competitors (e.g., LinkedIn provides data to Apollo but Sales Navigator competes with Apollo)
            6. MOATS: Identify competitive moats (data moats, network effects, technology, brand, regulatory, etc.)
            7. FRAGMENTATION: Assess market fragmentation (high/medium/low) and explain why
            8. MARKET_SIZE: Based on the search results provided, extract the actual TAM for the main market and estimate the submarket size
            9. GROWTH_RATE: Extract or estimate annual growth rate
            10. BARRIERS_TO_ENTRY: Key barriers to entry in this market
            11. TAILWINDS: Market tailwinds driving growth (regulatory, technology shifts, consumer behavior)
            12. HEADWINDS: Market headwinds limiting growth (competition, regulation, market saturation)
            13. TAM/SAM/SOM: Total Addressable Market, Serviceable Addressable Market, Serviceable Obtainable Market

            Be specific and accurate. For example:
            - For Apollo.io: Main market = "Sales Intelligence" (~$5.6B), Submarket = "B2B contact data & sales engagement platform"
            - For Revolut: Main market = "Digital Banking", Submarket = "Consumer neobanking in Europe"
            - For Stripe: Main market = "Payment Processing", Submarket = "Developer-first payment infrastructure"

            Return your analysis in JSON format:
            {{
                "main_market": {{
                    "name": "broad market category",
                    "tam": "total addressable market size with source",
                    "growth_rate": "CAGR"
                }},
                "submarket": {{
                    "name": "specific niche/segment",
                    "description": "what specific problem they solve",
                    "estimated_size": "portion of TAM",
                    "key_differentiator": "what makes this submarket unique"
                }},
                "incumbents": [
                    {{"name": "company name", "type": "public/private", "market_cap": "if public", "description": "brief description"}}
                ],
                "competitors": [
                    {{"name": "company name", "stage": "funding stage", "description": "brief description"}}
                ],
                "supplier_competitors": [
                    {{
                        "name": "company name",
                        "supplier_role": "what they supply",
                        "competitor_role": "how they compete",
                        "dependency_level": "critical/important/minor"
                    }}
                ],
                "moats": [
                    {{
                        "type": "data/network/technology/brand/scale/regulatory",
                        "description": "specific moat description",
                        "strength": "strong/medium/weak"
                    }}
                ],
                "fragmentation": {{
                    "level": "high/medium/low",
                    "explanation": "why the market is fragmented or consolidated"
                }},
                "barriers_to_entry": ["barrier 1", "barrier 2", "barrier 3"],
                "tailwinds": [
                    {{"factor": "tailwind description", "impact": "high/medium/low"}}
                ],
                "headwinds": [
                    {{"factor": "headwind description", "impact": "high/medium/low"}}
                ],
                "market_size": "TAM value",
                "sam": "Serviceable Addressable Market",
                "som": "Serviceable Obtainable Market",
                "growth_rate": "market CAGR"
            }}
            """
            
            sys.stderr.write("Making Claude API request for market landscape...\n")
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=15  # Reduced timeout
            )
            sys.stderr.write(f"Claude API response status: {response.status_code}\n")
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    market_analysis = json.loads(json_match.group())
                    return market_analysis
                else:
                    raise Exception(f"Failed to parse Claude market analysis response: {content}")
            else:
                raise Exception(f"Claude API error: {response.status_code}")
                
        except Exception as e:
            sys.stderr.write(f"Market landscape analysis error: {e}\n")
            raise e

    def _extract_funding_from_search(self, company_name: str, market_research: Dict) -> Dict:
        """Extract funding information from search results"""
        import re
        from datetime import datetime
        
        funding_info = {
            'last_round': '',
            'last_date': '',
            'total_raised': 0
        }
        
        # Look through search results for funding information
        if market_research.get('raw_company_results'):
            for result in market_research.get('raw_company_results', []):
                content = str(result.get('content', ''))
                title = str(result.get('title', ''))
                
                # Only process if it mentions the company
                if company_name.lower() not in content.lower() and company_name.lower() not in title.lower():
                    continue
                
                # Look for funding round patterns
                # Pattern: "raised $X million in Series Y"
                round_patterns = [
                    r'raised \$?([\d.]+)\s*(million|billion|M|B)?\s*in\s*(Series [A-F]|seed|pre-seed)',
                    r'(Series [A-F]|seed|pre-seed)\s*(?:round|funding).*?\$?([\d.]+)\s*(million|billion|M|B)',
                    r'closed\s*(?:a\s*)?\$?([\d.]+)\s*(million|billion|M|B)\s*(Series [A-F]|seed|pre-seed)',
                    r'(Series [A-F]|seed|pre-seed).*?valued.*?\$?([\d.]+)\s*(million|billion|M|B)'
                ]
                
                for pattern in round_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        groups = match.groups()
                        # Extract round type
                        for group in groups:
                            if group and 'series' in group.lower() or 'seed' in group.lower():
                                if not funding_info['last_round']:  # Take first match
                                    funding_info['last_round'] = group
                        
                        # Extract amount
                        for i, group in enumerate(groups):
                            if group and re.match(r'^[\d.]+$', group):
                                amount = float(group)
                                # Check for million/billion qualifier
                                if i + 1 < len(groups) and groups[i + 1]:
                                    if 'billion' in groups[i + 1].lower() or groups[i + 1].upper() == 'B':
                                        amount *= 1000  # Convert to millions
                                if amount > funding_info['total_raised']:
                                    funding_info['total_raised'] = amount
                
                # Look for dates dynamically based on current year
                date_patterns = [
                    rf'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+{TWO_YEARS_AGO}|{PREV_YEAR}|{CURRENT_YEAR}|{NEXT_YEAR}',
                    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+202[3-5]',
                    r'(?:Q[1-4]\s+)?202[3-5]',
                    r'202[3-5]'
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, content)
                    if date_match and not funding_info['last_date']:
                        date_str = date_match.group()
                        # Convert to ISO format if it's just a year
                        if re.match(r'^202[3-5]$', date_str):
                            funding_info['last_date'] = f"{date_str}-01-01"
                        else:
                            funding_info['last_date'] = date_str
                        break
        
        # Also check company intelligence if available
        if market_research.get('company_intelligence'):
            intel = market_research['company_intelligence']
            if intel.get('funding_round') and not funding_info['last_round']:
                funding_info['last_round'] = intel['funding_round']
            if intel.get('total_funding'):
                # Parse total funding if it's a string like "$50M"
                total_str = str(intel['total_funding'])
                amount_match = re.search(r'\$?([\d.]+)\s*(M|million|B|billion)?', total_str, re.IGNORECASE)
                if amount_match:
                    amount = float(amount_match.group(1))
                    if amount_match.group(2):
                        if amount_match.group(2).upper() in ['B', 'BILLION']:
                            amount *= 1000
                    if amount > funding_info['total_raised']:
                        funding_info['total_raised'] = amount
        
        return funding_info
    
    def _determine_company_stage(self, company_data: Dict, market_research: Dict = None) -> Dict:
        """Determine company stage based on last funding round from database or search results"""
        # First try to get funding data from database
        last_round = company_data.get('quarter_raised', '')  # Last funding round type
        last_funding_date = company_data.get('latest_investment_date', '')
        total_funding = company_data.get('total_invested_usd', 0) / 1000000 if company_data.get('total_invested_usd') else 0
        
        # If no funding data in database, try to extract from market research
        if (not last_round or not last_funding_date) and market_research:
            funding_info = self._extract_funding_from_search(company_data.get('name', ''), market_research)
            if funding_info:
                if not last_round:
                    last_round = funding_info.get('last_round', '')
                if not last_funding_date:
                    last_funding_date = funding_info.get('last_date', '')
                if total_funding == 0:
                    total_funding = funding_info.get('total_raised', 0)
        
        # User-provided assumptions (not used for stage determination)
        arr_millions = company_data.get('current_arr_usd', 0) / 1000000  # This is user's assumption
        growth_rate = company_data.get('revenue_growth_annual_pct', 0)
        
        # Determine stage from actual last funding round
        stage = "unknown"
        stage_confidence = "high"  # High confidence when we have actual funding data
        
        if last_round:
            round_lower = last_round.lower()
            if 'pre' in round_lower or 'angel' in round_lower:
                stage = "pre_seed"
            elif 'seed' in round_lower:
                stage = "seed"
            elif 'series a' in round_lower or 'seriesa' in round_lower or 'a round' in round_lower:
                stage = "series_a"
            elif 'series b' in round_lower or 'seriesb' in round_lower or 'b round' in round_lower:
                stage = "series_b"
            elif 'series c' in round_lower or 'seriesc' in round_lower or 'c round' in round_lower:
                stage = "series_c"
            elif 'series d' in round_lower or 'seriesd' in round_lower or 'd round' in round_lower:
                stage = "series_d"
            elif 'series e' in round_lower or 'series f' in round_lower or 'late' in round_lower:
                stage = "late_stage"
            elif 'growth' in round_lower or 'private equity' in round_lower:
                stage = "growth_equity"
            else:
                # Try to infer from total funding if round type unclear
                stage_confidence = "medium"
                if total_funding < 3:
                    stage = "seed"
                elif total_funding < 15:
                    stage = "series_a"
                elif total_funding < 50:
                    stage = "series_b"
                elif total_funding < 100:
                    stage = "series_c"
                else:
                    stage = "late_stage"
        else:
            # No funding round data - use total funding as proxy
            stage_confidence = "low"
            if total_funding == 0:
                stage = "pre_seed"
            elif total_funding < 3:
                stage = "seed"
            elif total_funding < 15:
                stage = "series_a"
            elif total_funding < 50:
                stage = "series_b"
            elif total_funding < 100:
                stage = "series_c"
            else:
                stage = "late_stage"
        
        # Calculate time since last funding
        months_since_funding = None
        funding_recency = "unknown"
        if last_funding_date:
            try:
                from datetime import datetime
                # Handle different date formats
                if 'T' in last_funding_date:
                    funding_date = datetime.fromisoformat(last_funding_date.replace('Z', '+00:00'))
                else:
                    funding_date = datetime.strptime(last_funding_date, '%Y-%m-%d')
                months_since_funding = (datetime.now() - funding_date).days / 30
                
                # Categorize funding recency
                if months_since_funding < 6:
                    funding_recency = "very_recent"
                elif months_since_funding < 12:
                    funding_recency = "recent"
                elif months_since_funding < 24:
                    funding_recency = "moderate"
                elif months_since_funding < 36:
                    funding_recency = "aging"
                else:
                    funding_recency = "stale"
            except:
                pass
        
        # Determine if likely ready for next round
        typical_months_between_rounds = {
            "pre_seed": 12,
            "seed": 18,
            "series_a": 18,
            "series_b": 24,
            "series_c": 24,
            "series_d": 30,
            "late_stage": 36,
            "growth_equity": 36
        }
        
        ready_for_next_round = False
        if months_since_funding and stage in typical_months_between_rounds:
            if months_since_funding >= typical_months_between_rounds[stage] * 0.75:
                ready_for_next_round = True
        
        # Growth category based on assumed growth rate
        growth_category = "moderate"
        if growth_rate > 200:
            growth_category = "hypergrowth"
        elif growth_rate > 100:
            growth_category = "high_growth"
        elif growth_rate > 50:
            growth_category = "strong_growth"
        elif growth_rate < 20:
            growth_category = "slow_growth"
        
        # Get next round
        next_round_map = {
            "pre_seed": "seed",
            "seed": "series_a",
            "series_a": "series_b",
            "series_b": "series_c",
            "series_c": "series_d",
            "series_d": "late_stage",
            "late_stage": "ipo_or_acquisition",
            "growth_equity": "ipo_or_acquisition"
        }
        
        return {
            "current_stage": stage,
            "stage_confidence": stage_confidence,
            "last_round": last_round if last_round else "unknown",
            "last_funding_date": last_funding_date if last_funding_date else "unknown",
            "months_since_funding": round(months_since_funding, 1) if months_since_funding else None,
            "funding_recency": funding_recency,
            "total_funding_millions": round(total_funding, 1),
            "ready_for_next_round": ready_for_next_round,
            "typical_next_round": next_round_map.get(stage, "unknown"),
            "assumed_arr_millions": round(arr_millions, 1),  # Clearly marked as assumption
            "assumed_growth_rate_pct": growth_rate,  # Clearly marked as assumption
            "growth_category": growth_category
        }
    
    def build_investment_thesis(self, company_data: Dict, market_research: Dict) -> Dict:
        """Build investment thesis using efficient staged analysis"""
        
        company_name = company_data.get('name', '')
        
        # Stage 1: Pre-process and summarize key data points with Haiku (cheap & fast)
        raw_results = market_research.get('raw_company_results', [])
        exit_comparables = market_research.get('exit_comparables', [])
        competitors = market_research.get('competitors', [])
        
        # First pass: Extract key facts from each article with Haiku
        key_facts = []
        for result in raw_results[:10]:  # Process top 10 results
            try:
                fact_extraction_prompt = f"""
                Extract ONLY the most important facts about {company_name} from this article.
                Focus on: funding amounts, revenue, growth rates, customer numbers, acquisitions, partnerships.
                Return as bullet points. Be very concise.
                
                Article: {result.get('content', '')[:3000]}  # First 3000 chars per article
                """
                
                response = requests.post(
                    self.claude_base_url,
                    headers={
                        "x-api-key": self.claude_api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",  # Cheap model for extraction
                        "max_tokens": 200,
                        "messages": [{"role": "user", "content": fact_extraction_prompt}]
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    facts = response.json()['content'][0]['text']
                    key_facts.append({
                        'source': result.get('title', ''),
                        'url': result.get('url', ''),
                        'facts': facts
                    })
            except:
                pass
        
        # Stage 2: Build comprehensive summary of key facts
        facts_summary = "\n\n".join([
            f"From {f['source']}:\n{f['facts']}"
            for f in key_facts
        ])
        
        # Stage 3: Final synthesis with Claude 4 Opus using extracted facts (more efficient)
        try:
            prompt = f"""
            You are a senior venture capital partner making a final investment decision on {company_name}.
            
            Based on the extracted facts below, provide:
            1. Investment thesis with specific evidence
            2. Valuation with detailed waterfall
            3. Expected returns analysis
            
            KEY FACTS EXTRACTED FROM SOURCES:
            {facts_summary}
            
            EXIT COMPARABLES FOUND:
            {json.dumps(exit_comparables[:10], indent=2) if exit_comparables else "None found"}
            
            COMPETITORS IDENTIFIED:
            {json.dumps(competitors[:10], indent=2) if competitors else "None found"}
            
            Provide a DEEP analysis in JSON format:
            {{
                "company_overview": "What exactly does this company do based on the sources",
                "key_metrics": {{
                    "revenue": "actual number with source",
                    "growth_rate": "actual percentage with source",
                    "funding_raised": "actual amount with source",
                    "customer_count": "actual number with source",
                    "market_share": "actual percentage if available"
                }},
                "bull_case": [
                    {{
                        "point": "SPECIFIC positive fact from sources",
                        "evidence": "Why this matters",
                        "source": "Which article mentioned this"
                    }}
                ],
                "bear_case": [
                    {{
                        "risk": "SPECIFIC concern or challenge",
                        "impact": "Why this could hurt the business",
                        "source": "Where this was mentioned"
                    }}
                ],
                "competitive_advantages": [
                    {{
                        "advantage": "SPECIFIC moat or differentiation",
                        "evidence": "Proof from sources",
                        "sustainability": "How defensible is this"
                    }}
                ],
                "market_dynamics": {{
                    "tam": "Total addressable market size",
                    "growth_rate": "Market CAGR",
                    "key_trends": ["trend1", "trend2"],
                    "disruption_potential": "Can this company disrupt incumbents?"
                }},
                "exit_analysis": {{
                    "likely_acquirers": ["company1", "company2"],
                    "exit_timeline": "years to likely exit",
                    "expected_multiple": "based on comparables",
                    "rationale": "Why these specific acquirers"
                }},
                "investment_recommendation": {{
                    "verdict": "INVEST/PASS/WATCH",
                    "conviction_level": "HIGH/MEDIUM/LOW",
                    "key_reasons": ["reason1", "reason2", "reason3"],
                    "valuation_range": "fair valuation range based on analysis",
                    "expected_return": "expected multiple on investment"
                }},
                "critical_questions": [
                    "What key questions remain unanswered?",
                    "What additional diligence is needed?"
                ]
            }}
            
            Be extremely specific. Use actual numbers, dates, and facts from the sources.
            Do not make generic statements. Every claim must be backed by the search results.
            """
            
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-4-opus",  # Use Sonnet for deep analysis
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    thesis = json.loads(json_match.group())
                    
                    # Add source URLs back to the thesis
                    if 'bull_case' in thesis:
                        for point in thesis['bull_case']:
                            # Find the source URL
                            for r in raw_results:
                                if point.get('source') and point['source'] in r.get('title', ''):
                                    point['url'] = r.get('url', '')
                                    break
                    
                    return thesis
                    
        except Exception as e:
            sys.stderr.write(f"Claude analysis error: {e}\n")
        
        # Fallback to basic extraction if Claude fails
        thesis = {
            'company_overview': f"{company_name} operates in {company_data.get('sector', 'technology')}",
            'key_metrics': {},
            'bull_case': [],
            'bear_case': [],
            'competitive_advantages': [],
            'market_dynamics': {},
            'exit_analysis': {},
            'investment_recommendation': {
                'verdict': 'REQUIRES FURTHER ANALYSIS',
                'conviction_level': 'LOW',
                'key_reasons': ['Insufficient data for deep analysis']
            },
            'critical_questions': ['Unable to perform deep analysis - check API keys']
        }
        
        return thesis
    
        # First build the investment thesis
        thesis = self.build_investment_thesis(company_data, market_research)
        
        scores = {
            'market_opportunity': 0,
            'competitive_position': 0,
            'financial_metrics': 0,
            'team_execution': 0,
            'exit_potential': 0,
            'timing_momentum': 0
        }
        
        citations = []
        
        # 1. Market Opportunity Score (0-20 points)
        tam = market_research.get('company_intelligence', {}).get('market_size', '')
        if 'billion' in str(tam).lower() or 'B' in str(tam):
            try:
                tam_str = str(tam).replace('$', '').replace('billion', '').replace('B', '').strip()
                tam_value = float(tam_str.split()[0] if ' ' in tam_str else tam_str)
                if tam_value > 100:
                    scores['market_opportunity'] = 20
                elif tam_value > 50:
                    scores['market_opportunity'] = 18
                elif tam_value > 20:
                    scores['market_opportunity'] = 15
                elif tam_value > 10:
                    scores['market_opportunity'] = 12
                else:
                    scores['market_opportunity'] = 10
                    
                # Find citation for TAM
                for result in market_research.get('raw_company_results', [])[:20]:
                    content = result.get('content', '')
                    if 'TAM' in content or 'total addressable market' in content.lower() or 'market size' in content.lower():
                        citations.append({
                            'metric': 'Market Size (TAM)',
                            'value': tam,
                            'source': result.get('title', ''),
                            'url': result.get('url', '')
                        })
                        break
            except:
                scores['market_opportunity'] = 10
        else:
            scores['market_opportunity'] = 10
            
        # 2. Competitive Position Score (0-20 points)
        competitors = market_research.get('competitors', [])
        incumbents = market_research.get('market_landscape', {}).get('incumbents', [])
        
        # Base score on competitive landscape
        if len(competitors) < 5 and len(incumbents) < 3:
            scores['competitive_position'] = 15  # Low competition
        elif len(competitors) < 10:
            scores['competitive_position'] = 12  # Moderate competition
        else:
            scores['competitive_position'] = 8   # High competition
            
        # Add outlier bonus if available
        if outlier_analysis:
            outlier_score = outlier_analysis.get('overall_outlier_score', 50)
            scores['competitive_position'] += min(5, outlier_score * 0.05)
            
        # 3. Financial Metrics Score (0-20 points)
        # Extract real revenue/ARR from search results if not in database
        revenue = company_data.get('current_arr_usd', 0)
        if revenue == 0:
            # Try to extract from search results
            for result in market_research.get('raw_company_results', [])[:10]:
                content = result.get('content', '')
                import re
                revenue_patterns = [
                    r'\$?([\d.]+)\s*(?:million|M)\s+(?:in\s+)?(?:annual\s+)?(?:revenue|ARR)',
                    r'(?:revenue|ARR)\s+of\s+\$?([\d.]+)\s*(?:million|M)',
                ]
                for pattern in revenue_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        revenue = float(match.group(1))
                        citations.append({
                            'metric': 'Annual Revenue/ARR',
                            'value': f'${revenue}M',
                            'source': result.get('title', ''),
                            'url': result.get('url', '')
                        })
                        break
                if revenue > 0:
                    break
                    
        # Score based on revenue
        if revenue > 100:
            scores['financial_metrics'] = 15
        elif revenue > 50:
            scores['financial_metrics'] = 12
        elif revenue > 20:
            scores['financial_metrics'] = 10
        elif revenue > 10:
            scores['financial_metrics'] = 8
        elif revenue > 5:
            scores['financial_metrics'] = 6
        else:
            scores['financial_metrics'] = 4
            
        # Growth rate bonus
        growth = company_data.get('revenue_growth_annual_pct', 0)
        if growth > 100:
            scores['financial_metrics'] += 5
        elif growth > 50:
            scores['financial_metrics'] += 4
        elif growth > 30:
            scores['financial_metrics'] += 3
            
        # 4. Team & Execution Score (0-15 points)
        # Extract founder/team info from search
        has_repeat_founder = False
        has_strong_team = False
        
        for result in market_research.get('raw_company_results', [])[:10]:
            content = result.get('content', '').lower()
            if 'repeat entrepreneur' in content or 'serial entrepreneur' in content or 'previously founded' in content:
                has_repeat_founder = True
                citations.append({
                    'metric': 'Founder Experience',
                    'value': 'Repeat/Serial Entrepreneur',
                    'source': result.get('title', ''),
                    'url': result.get('url', '')
                })
            if 'team from' in content and any(co in content for co in ['google', 'facebook', 'apple', 'amazon', 'microsoft']):
                has_strong_team = True
                
        scores['team_execution'] = 8  # Base score
        if has_repeat_founder:
            scores['team_execution'] += 4
        if has_strong_team:
            scores['team_execution'] += 3
            
        # 5. Exit Potential Score (0-15 points)
        acquirers = market_research.get('data_driven_acquirers', [])
        exits = market_research.get('exit_comparables', [])
        
        if len(acquirers) > 10:
            scores['exit_potential'] = 12
        elif len(acquirers) > 5:
            scores['exit_potential'] = 10
        elif len(acquirers) > 3:
            scores['exit_potential'] = 8
        else:
            scores['exit_potential'] = 6
            
        # Add exit multiple bonus
        if exits:
            multiples = [e.get('ev_revenue_multiple', 0) for e in exits[:5] if e.get('ev_revenue_multiple')]
            if multiples:
                avg_multiple = np.mean(multiples)
                if avg_multiple > 10:
                    scores['exit_potential'] += 3
                elif avg_multiple > 7:
                    scores['exit_potential'] += 2
                    
                # Add citation for exit multiples
                citations.append({
                    'metric': 'Exit Multiples',
                    'value': f'{avg_multiple:.1f}x average',
                    'source': f'Analysis of {len(exits)} comparable exits',
                    'url': ''
                })
                
        # 6. Timing & Momentum Score (0-10 points)
        # Check for recent funding or growth signals
        recent_funding = False
        for result in market_research.get('raw_company_results', [])[:10]:
            content = result.get('content', '')
            if str(PREV_YEAR) in content or str(CURRENT_YEAR) in content:
                if 'raised' in content.lower() or 'funding' in content.lower():
                    recent_funding = True
                    citations.append({
                        'metric': 'Recent Funding',
                        'value': 'Recent round completed',
                        'source': result.get('title', ''),
                        'url': result.get('url', '')
                    })
                    break
                    
        scores['timing_momentum'] = 5  # Base score
        if recent_funding:
            scores['timing_momentum'] += 5
            
        # Calculate total score
        total_score = sum(scores.values())
        
        # Determine investment grade
        if total_score >= 85:
            grade = 'A+'
            recommendation = 'Exceptional investment opportunity - strong conviction'
        elif total_score >= 75:
            grade = 'A'
            recommendation = 'Excellent investment opportunity - high conviction'
        elif total_score >= 65:
            grade = 'B+'
            recommendation = 'Very good investment opportunity - recommended'
        elif total_score >= 55:
            grade = 'B'
            recommendation = 'Good investment opportunity - consider investing'
        elif total_score >= 45:
            grade = 'C+'
            recommendation = 'Moderate opportunity - requires careful evaluation'
        elif total_score >= 35:
            grade = 'C'
            recommendation = 'Below average opportunity - proceed with caution'
        else:
            grade = 'D'
            recommendation = 'Weak opportunity - not recommended'
            
        return {
            'total_score': round(total_score, 1),
            'grade': grade,
            'recommendation': recommendation,
            'score_breakdown': {
                'market_opportunity': f"{round(scores['market_opportunity'], 1)}/20",
                'competitive_position': f"{round(scores['competitive_position'], 1)}/20",
                'financial_metrics': f"{round(scores['financial_metrics'], 1)}/20",
                'team_execution': f"{round(scores['team_execution'], 1)}/15",
                'exit_potential': f"{round(scores['exit_potential'], 1)}/15",
                'timing_momentum': f"{round(scores['timing_momentum'], 1)}/10"
            },
            'investment_thesis': thesis,  # Include the full thesis
            'citations': citations[:10]  # Top 10 citations
        }
    
    def quick_outlier_assessment(self, company_name: str, company_data: Dict, market_research: Dict) -> Dict:
        """Quick outlier assessment using Claude Haiku with real data"""
        try:
            # Use real comparables from search to assess if company is an outlier
            comparables = market_research.get('existing_comparables', [])
            
            if self.claude_api_key:
                # Quick Claude assessment
                prompt = f"""Analyze {company_name} as a potential outlier investment.

Rate on scale of -10 to +10:
+10 = Exceptional outlier (early Uber, Airbnb, OpenAI)
+5 = Strong performer (top 10% of category)
0 = Average for category
-5 = Below average
-10 = Likely to fail

Company metrics:
- ARR: ${company_data.get('current_arr_usd', 5000000)/1000000:.1f}M
- Growth: {company_data.get('revenue_growth_annual_pct', 30)}%
- Sector: {company_data.get('sector', 'SaaS')}
- Market comparables: {len(comparables)} companies

Analyze:
1. Growth rate vs peers
2. Market position & competitive advantage  
3. Scalability potential
4. Team/founder quality signals
5. Product-market fit indicators

Return JSON:
{{
  "outlier_score": <-10 to 10>,
  "reasoning": "detailed 2-3 sentence explanation",
  "strengths": ["key strength 1", "key strength 2"],
  "risks": ["key risk 1", "key risk 2"],
  "comparable_to": "similar successful company if applicable"
}}"""

                response = requests.post(
                    self.claude_base_url,
                    headers={
                        "x-api-key": self.claude_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=5  # Quick timeout
                )
                
                if response.status_code == 200:
                    content = response.json()['content'][0]['text']
                    # Parse JSON from response
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                        # Ensure all fields are present
                        result.setdefault('strengths', [])
                        result.setdefault('risks', [])
                        result.setdefault('comparable_to', '')
                    else:
                        result = {'outlier_score': 0, 'reasoning': 'Could not parse response', 'strengths': [], 'risks': []}
                    return result
            
        except Exception as e:
            sys.stderr.write(f"Quick outlier assessment failed: {e}\n")
        
        # Fallback: simple calculation based on growth
        growth = company_data.get('revenue_growth_annual_pct', 30)
        if growth > 100:
            score = 5
        elif growth > 50:
            score = 2
        else:
            score = 0
            
        return {
            'outlier_score': score,
            'reasoning': f'Based on {growth}% growth rate'
        }
    
    def calculate_outlier_score(self, company_name: str, company_data: Dict, market_landscape: Dict, tavily_data: Dict) -> Dict:
        """
        Calculate outlier score using Claude to analyze company performance relative to market context
        """
        if not self.claude_api_key:
            raise Exception("Claude API key required for outlier analysis")
        
        try:
            # Extract public comparables and acquirer data if available
            public_comparables = tavily_data.get('public_comparables', [])
            potential_acquirers = tavily_data.get('potential_acquirers', [])
            median_multiple = tavily_data.get('median_ev_multiple', 0)
            
            prompt = f"""
            Analyze "{company_name}" as a potential outlier in their market. Consider the following comprehensive context:

            COMPANY DATA:
            - Revenue: ${company_data.get('revenue', 0)}M
            - Growth Rate: {company_data.get('growth_rate', 0)*100:.1f}%
            - Sector: {company_data.get('sector', 'Unknown')}
            - Subsector: {company_data.get('subsector', 'Unknown')}

            MARKET LANDSCAPE:
            - Submarket: {market_landscape.get('submarket', 'Unknown')}
            - Market Fragmentation: {market_landscape.get('fragmentation', {}).get('level', 'Unknown')}
            - Market Growth Rate: {market_landscape.get('growth_rate', 'Unknown')}
            - Barriers to Entry: {', '.join(market_landscape.get('barriers_to_entry', []))}

            INCUMBENTS: {[inc['name'] for inc in market_landscape.get('incumbents', [])]}
            COMPETITORS: {[comp['name'] for comp in market_landscape.get('competitors', [])]}

            PUBLIC COMPARABLES:
            {json.dumps(public_comparables[:5], indent=2) if public_comparables else "No public comparables found"}
            
            MEDIAN EV/REVENUE MULTIPLE: {median_multiple:.1f}x (public SaaS companies)
            
            POTENTIAL STRATEGIC ACQUIRERS:
            {json.dumps(potential_acquirers[:3], indent=2) if potential_acquirers else "No acquirers identified"}

            TAVILY MARKET INTELLIGENCE: {json.dumps(tavily_data.get('company_intelligence', {}), indent=2)}

            ASSESSMENT CRITERIA:
            1. **Market Position**: How does this company compare to incumbents and competitors?
            2. **Growth Trajectory**: Is their growth rate exceptional for their market?
            3. **Innovation**: Are they doing something fundamentally different or better?
            4. **Execution**: Are they executing better than peers?
            5. **Market Timing**: Are they positioned well for market trends?
            6. **Founder Quality**: Any indicators of exceptional founder capabilities?
            7. **Valuation Potential**: Based on public comps and acquirer interest

            OUTLIER SCORE COMPONENTS (0-100 each):
            - Market Position Score: How well positioned vs incumbents/competitors
            - Growth Score: Growth rate vs market average and public comps
            - Innovation Score: How innovative their approach is
            - Execution Score: Quality of execution vs peers
            - Market Timing Score: How well positioned for market trends
            - Founder Score: Evidence of exceptional founder capabilities
            - Exit Potential Score: Likelihood of premium exit based on acquirer fit

            Return your analysis in JSON format:
            {{
                "overall_outlier_score": 0-100,
                "outlier_probability": 0.0-1.0,
                "outlier_reasoning": "detailed explanation of why this company is or isn't an outlier",
                "score_breakdown": {{
                    "market_position": 0-100,
                    "growth": 0-100,
                    "innovation": 0-100,
                    "execution": 0-100,
                    "market_timing": 0-100,
                    "founder_quality": 0-100,
                    "exit_potential": 0-100
                }},
                "key_outlier_factors": ["factor1", "factor2", "factor3"],
                "risk_factors": ["risk1", "risk2", "risk3"],
                "outlier_confidence": "high/medium/low",
                "valuation_insight": "expected valuation multiple vs public comps"
            }}

            Be realistic and analytical. A true outlier should be exceptional in multiple dimensions, not just high valuation.
            Consider both the Tavily market data AND the public SaaS comparables to form a comprehensive view.
            """
            
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",  # Use Claude 3.5 Sonnet for faster analysis
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=10  # Shorter timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    outlier_analysis = json.loads(json_match.group())
                    return outlier_analysis
                else:
                    raise Exception(f"Failed to parse Claude outlier analysis response: {content}")
            else:
                raise Exception(f"Claude API error: {response.status_code}")
                
        except Exception as e:
            sys.stderr.write(f"Outlier analysis error: {e}\n")
            raise e

    def calculate_investment_score(self, company_data: Dict, market_research: Dict, outlier_analysis: Dict) -> Dict:
        """Calculate comprehensive investment score (0-100) with detailed breakdown"""
        score_breakdown = {
            "market_opportunity": {"score": 0, "max": 20, "details": {}},
            "competitive_position": {"score": 0, "max": 20, "details": {}},
            "financial_metrics": {"score": 0, "max": 20, "details": {}},
            "team_execution": {"score": 0, "max": 15, "details": {}},
            "exit_potential": {"score": 0, "max": 15, "details": {}},
            "timing_momentum": {"score": 0, "max": 10, "details": {}}
        }
        
        # Market Opportunity (0-20)
        market_size = market_research.get('market_conditions', {}).get('market_size', 0)
        growth_rate = market_research.get('market_conditions', {}).get('growth_rate', 0)
        
        if market_size > 10_000_000_000:  # $10B+
            score_breakdown["market_opportunity"]["score"] += 10
            score_breakdown["market_opportunity"]["details"]["tam"] = "Large TAM ($10B+)"
        elif market_size > 1_000_000_000:  # $1B+
            score_breakdown["market_opportunity"]["score"] += 7
            score_breakdown["market_opportunity"]["details"]["tam"] = "Medium TAM ($1B-$10B)"
        else:
            score_breakdown["market_opportunity"]["score"] += 4
            score_breakdown["market_opportunity"]["details"]["tam"] = "Small TAM (<$1B)"
        
        if growth_rate > 30:
            score_breakdown["market_opportunity"]["score"] += 10
            score_breakdown["market_opportunity"]["details"]["growth"] = f"High growth ({growth_rate}%)"
        elif growth_rate > 15:
            score_breakdown["market_opportunity"]["score"] += 7
            score_breakdown["market_opportunity"]["details"]["growth"] = f"Medium growth ({growth_rate}%)"
        else:
            score_breakdown["market_opportunity"]["score"] += 4
            score_breakdown["market_opportunity"]["details"]["growth"] = f"Low growth ({growth_rate}%)"
        
        # Competitive Position (0-20)
        competitors = market_research.get('competitors', [])
        if len(competitors) < 3:
            score_breakdown["competitive_position"]["score"] += 10
            score_breakdown["competitive_position"]["details"]["competition"] = "Low competition"
        elif len(competitors) < 10:
            score_breakdown["competitive_position"]["score"] += 7
            score_breakdown["competitive_position"]["details"]["competition"] = "Moderate competition"
        else:
            score_breakdown["competitive_position"]["score"] += 4
            score_breakdown["competitive_position"]["details"]["competition"] = "High competition"
        
        # Add moat analysis
        score_breakdown["competitive_position"]["score"] += 8  # Default moat score
        score_breakdown["competitive_position"]["details"]["moat"] = "Technology differentiation"
        
        # Financial Metrics (0-20)
        revenue = company_data.get('revenue', 0)
        if revenue > 10_000_000:  # $10M+
            score_breakdown["financial_metrics"]["score"] += 10
            score_breakdown["financial_metrics"]["details"]["revenue"] = f"Strong revenue (${revenue:,.0f})"
        elif revenue > 1_000_000:  # $1M+
            score_breakdown["financial_metrics"]["score"] += 7
            score_breakdown["financial_metrics"]["details"]["revenue"] = f"Moderate revenue (${revenue:,.0f})"
        else:
            score_breakdown["financial_metrics"]["score"] += 4
            score_breakdown["financial_metrics"]["details"]["revenue"] = f"Early revenue (${revenue:,.0f})"
        
        # Growth metrics
        score_breakdown["financial_metrics"]["score"] += 8
        score_breakdown["financial_metrics"]["details"]["growth_rate"] = "YoY growth tracked"
        
        # Team & Execution (0-15)
        score_breakdown["team_execution"]["score"] = 10
        score_breakdown["team_execution"]["details"]["team"] = "Experienced founding team"
        
        # Exit Potential (0-15)
        acquirers = market_research.get('acquirers', [])
        if len(acquirers) > 5:
            score_breakdown["exit_potential"]["score"] = 12
            score_breakdown["exit_potential"]["details"]["acquirers"] = f"{len(acquirers)} potential acquirers"
        elif len(acquirers) > 2:
            score_breakdown["exit_potential"]["score"] = 9
            score_breakdown["exit_potential"]["details"]["acquirers"] = f"{len(acquirers)} potential acquirers"
        else:
            score_breakdown["exit_potential"]["score"] = 6
            score_breakdown["exit_potential"]["details"]["acquirers"] = "Limited acquirer pool"
        
        # Timing & Momentum (0-10)
        score_breakdown["timing_momentum"]["score"] = 7
        score_breakdown["timing_momentum"]["details"]["timing"] = "Market timing favorable"
        
        # Calculate total score
        total_score = sum(component["score"] for component in score_breakdown.values())
        
        # Determine grade
        if total_score >= 85:
            grade = "A"
            recommendation = "Strong Investment"
        elif total_score >= 70:
            grade = "B"
            recommendation = "Good Investment"
        elif total_score >= 55:
            grade = "C"
            recommendation = "Moderate Investment"
        else:
            grade = "D"
            recommendation = "High Risk Investment"
        
        return {
            "total_score": total_score,
            "grade": grade,
            "recommendation": recommendation,
            "breakdown": score_breakdown,
            "sources": market_research.get('sources', [])
        }

    def fetch_market_research(self, company_name: str, sector: str) -> Dict:
        """Fetch comprehensive market research using Tavily"""
        sys.stderr.write(f"\n=== Starting market research for {company_name} in sector {sector} ===\n")
        sys.stderr.write(f"Tavily API key: {'SET' if self.tavily_api_key else 'NOT SET'}\n")
        
        research = {
            "graduation_rates": {},
            "comparables": [],
            "acquirers": [],
            "competitors": [],
            "market_conditions": {},
            "sector_analysis": {}
        }
        
        try:
            # Tavily search for market data
            if self.tavily_api_key:
                research.update(self._tavily_market_search(company_name, sector))
                
        except Exception as e:
            sys.stderr.write(f"Market research error: {e}\n")
            # Use basic graduation rates (same for all sectors as requested)
            research["graduation_rates"] = {
                "seed_to_series_a": 0.25,
                "series_a_to_b": 0.20,
                "series_b_to_c": 0.35,
                "series_c_to_d": 0.70,
                "to_exit": 0.40,
                "to_ipo": 0.25,
                "to_acquisition": 0.30,
                "to_liquidation": 0.20
            }
        
        return research
    
    def _tavily_market_search(self, company_name: str, sector: str) -> Dict:
        """Search for market data using Tavily API with enhanced queries"""
        research = {}
        
        # Check if Tavily API key is valid by doing a minimal test
        tavily_available = False
        if self.tavily_api_key:
            try:
                test_response = requests.post(
                    self.tavily_base_url,
                    json={
                        "api_key": self.tavily_api_key,
                        "query": "test",
                        "max_results": 1
                    },
                    timeout=5
                )
                if test_response.status_code == 200:
                    tavily_available = True
                else:
                    sys.stderr.write(f"Tavily API unavailable: {test_response.status_code} - {test_response.text}\n")
            except:
                pass
        
        if not tavily_available:
            sys.stderr.write("Tavily API not available, using cached data only\n")
            # Return empty research to use cached data
            return research
        
        try:
            # Parse sector for more specific category research
            sector_parts = sector.split('-')
            main_sector = sector_parts[0].strip() if sector_parts else sector
            subsector = sector_parts[1].strip() if len(sector_parts) > 1 else ""
            
            # 1. DEEP DIVE INTO THE SPECIFIC SUBMARKET - ENHANCED RESEARCH
            company_queries = [
                f'"{company_name}" what specific problem solution customer segment target market',
                f'"{company_name}" platform software "provides" "offers" features use cases',
                f'"{company_name}" "raised" "$" million billion funding valuation investors',
                f'"{company_name}" competitors alternatives "competes with" "similar to"',
                # Add more competitor discovery
                f'"{company_name}" vs versus compared comparison alternative competitors',
                f'best alternatives to "{company_name}" similar companies tools platforms',
                f'companies like "{company_name}" competing startups same space market',
                # Find incumbents and enterprise players
                f'{sector} enterprise incumbents Fortune 500 market leaders established players',
                f'{sector} largest companies by revenue market share dominant players',
                # More funding and valuation searches
                f'"{company_name}" series A B C funding round valuation investors venture capital',
                f'"{company_name}" revenue ARR growth rate burn rate runway metrics',
            ]
            
            # 2. GET THE CORE SUBMARKET TAM/SAM/SOM AND DYNAMICS
            if subsector:
                # Use the FULL sector context to maintain specificity
                full_sector_context = f'{main_sector} {subsector}' if main_sector != subsector else sector
                company_queries.extend([
                    f'"{full_sector_context}" TAM "total addressable market" size billion million {CURRENT_YEAR} {NEXT_YEAR}',
                    f'"{full_sector_context}" market size SAM serviceable addressable market',
                    f'{main_sector} {subsector} market CAGR growth rate forecast 2025 2026',
                    f'"{full_sector_context}" market leaders companies "market share" percentage',
                    f'{main_sector} {subsector} pricing models ACV "annual contract value" revenue',
                    f'"{full_sector_context}" acquisitions M&A deals exit multiples valuation',
                    f'{main_sector} {subsector} industry trends innovation technology',
                    # Add specific searches that maintain sector context
                    f'"{sector}" companies valuation multiples revenue benchmarks',
                    f'"{sector}" median EV/Revenue multiple acquisitions exits',
                ])
            else:
                # Fallback for when no subsector is specified
                company_queries.extend([
                    f'{sector} TAM SAM SOM market size opportunity analysis {CURRENT_YEAR} {NEXT_YEAR}',
                    f'{sector} market growth CAGR forecast trends analysis',
                    f'{sector} competitive landscape market share leaders',
                    # Add general SaaS metrics queries
                    f'site:publicsaascompanies.com {sector} median revenue multiple benchmarks',
                    f'public SaaS {sector} valuation multiples growth rate correlation',
                ])
            
            # 3. SPECIFIC CATEGORY DEEP RESEARCH WITH PROPER CATEGORIZATION
            # Map sectors to proper PublicSaaSCompanies.com categories
            sector_lower = sector.lower()
            
            # Defense Tech - HIGHEST PRIORITY
            if any(keyword in sector_lower for keyword in ['defense', 'defence', 'military', 'autonomous system', 'drone', 'uav']):
                company_queries.extend([
                    f'defense tech companies valuations Anduril Palantir Shield AI revenue multiples',
                    f'defense contractors autonomous systems market TAM growth CAGR',
                    f'military drone UAV market size growth forecast {CURRENT_YEAR} {NEXT_YEAR}',
                    f'defense tech unicorns Series D E valuations exit multiples',
                    f'Pentagon DoD contract awards defense startups procurement',
                    f'defense prime contractors acquisitions strategic buyers Lockheed Boeing Raytheon',
                    f'autonomous weapons systems market regulations dual-use technology',
                    f'defense AI artificial intelligence military applications market size'
                ])
            
            # Space Tech
            elif any(keyword in sector_lower for keyword in ['space', 'satellite', 'orbital', 'launch']):
                company_queries.extend([
                    f'space tech companies valuations SpaceX Rocket Lab Planet Labs',
                    f'satellite industry market size TAM growth forecast {CURRENT_YEAR} {NEXT_YEAR}',
                    f'space economy commercial space market opportunities',
                    f'space tech acquisitions strategic buyers exit multiples',
                    f'NewSpace startups funding rounds valuations Series C D',
                    f'earth observation satellite data market size growth'
                ])
            
            # HR Tech
            elif any(keyword in sector_lower for keyword in ['hr', 'human resource', 'talent', 'recruiting', 'payroll']):
                company_queries.extend([
                    f'site:publicsaascompanies.com HR HCM median revenue multiple',
                    f'HR tech SaaS companies Workday ADP Paycom valuation multiples',
                    f'HCM human capital management TAM market size growth CAGR',
                    f'HR software acquisitions strategic buyers exit multiples benchmarks',
                ])
            
            # Sales & Marketing Tech
            elif any(keyword in sector_lower for keyword in ['sales', 'crm', 'marketing', 'martech']):
                company_queries.extend([
                    f'site:publicsaascompanies.com CRM sales marketing median revenue multiple',
                    f'sales tech SaaS companies Salesforce HubSpot ZoomInfo valuation multiples',
                    f'CRM martech TAM market size growth CAGR {CURRENT_YEAR} {NEXT_YEAR}',
                    f'sales marketing software acquisitions exit multiples benchmarks',
                ])
            
            # Cybersecurity
            elif any(keyword in sector_lower for keyword in ['security', 'cyber', 'identity', 'siem']):
                company_queries.extend([
                    f'site:publicsaascompanies.com security cybersecurity median revenue multiple',
                    f'cybersecurity SaaS companies CrowdStrike Palo Alto Okta valuation multiples',
                    f'cybersecurity TAM market size growth CAGR {CURRENT_YEAR} {NEXT_YEAR}',
                    f'security software acquisitions strategic buyers exit multiples',
                ])
            
            # Data & Analytics
            elif any(keyword in sector_lower for keyword in ['data', 'analytics', 'bi', 'business intelligence']):
                company_queries.extend([
                    f'site:publicsaascompanies.com data analytics BI median revenue multiple',
                    f'data analytics SaaS companies Snowflake Databricks Palantir valuation multiples',
                    f'data analytics TAM market size growth CAGR {CURRENT_YEAR} {NEXT_YEAR}',
                    f'analytics software acquisitions exit multiples benchmarks',
                ])
            
            # Developer Tools & Infrastructure
            elif any(keyword in sector_lower for keyword in ['developer', 'devops', 'infrastructure', 'api']):
                company_queries.extend([
                    f'site:publicsaascompanies.com developer tools DevOps median revenue multiple',
                    f'developer tools SaaS companies GitLab Datadog HashiCorp valuation multiples',
                    f'DevOps developer tools TAM market size growth CAGR',
                    f'developer infrastructure software acquisitions exit multiples',
                ])
            
            # Fintech & Payments
            elif any(keyword in sector_lower for keyword in ['fintech', 'payment', 'banking', 'wealth']):
                company_queries.extend([
                    f'site:publicsaascompanies.com fintech payments median revenue multiple',
                    f'fintech SaaS companies Square Block Adyen valuation multiples',
                    f'fintech payments TAM market size growth CAGR {CURRENT_YEAR} {NEXT_YEAR}',
                    f'fintech software acquisitions strategic buyers exit multiples',
                ])
            
            # Healthcare Tech
            elif any(keyword in sector_lower for keyword in ['health', 'medical', 'clinical', 'biotech']):
                company_queries.extend([
                    f'site:publicsaascompanies.com healthcare health tech median revenue multiple',
                    f'healthcare SaaS companies Veeva Doximity valuation multiples',
                    f'digital health TAM market size growth CAGR {CURRENT_YEAR} {NEXT_YEAR}',
                    f'healthcare software acquisitions exit multiples benchmarks',
                ])
            
            # E-commerce & Retail Tech
            elif any(keyword in sector_lower for keyword in ['ecommerce', 'e-commerce', 'retail', 'marketplace']):
                company_queries.extend([
                    f'site:publicsaascompanies.com ecommerce retail tech median revenue multiple',
                    f'ecommerce SaaS companies Shopify BigCommerce valuation multiples',
                    f'ecommerce platform TAM market size growth CAGR',
                    f'retail tech software acquisitions exit multiples',
                ])
            
            # Vertical SaaS (industry-specific)
            elif any(keyword in sector_lower for keyword in ['vertical', 'industry-specific', 'niche']):
                company_queries.extend([
                    f'site:publicsaascompanies.com vertical SaaS median revenue multiple',
                    f'vertical SaaS companies Toast Procore valuation multiples benchmarks',
                    f'vertical SaaS TAM market size growth by industry',
                    f'vertical SaaS acquisitions strategic buyers exit multiples',
                ])
            
            # For simulation/modeling companies (original)
            elif any(keyword in sector_lower for keyword in ['simulation', 'modeling', 'digital twin']):
                company_queries.extend([
                    f'simulation software market size TAM growth enterprise adoption',
                    f'simulation modeling companies Ansys Dassault MathWorks competitors',
                    f'simulation software acquisitions strategic buyers exit multiples',
                    f'site:publicsaascompanies.com engineering software median multiples',
                ])
            
            # For audit/compliance (original)
            elif any(keyword in sector_lower for keyword in ['audit', 'compliance', 'risk', 'governance']):
                company_queries.extend([
                    f'audit software market TAM GRC compliance technology size growth',
                    f'audit automation companies DataSnipper MindBridge competitors',
                    f'compliance software acquisitions strategic buyers Big Four',
                    f'site:publicsaascompanies.com GRC compliance median revenue multiple',
                ])
            
            # Generic fallback with PublicSaaSCompanies.com data
            else:
                company_queries.extend([
                    f'site:publicsaascompanies.com SaaS median revenue multiple {CURRENT_YEAR}',
                    f'SaaS valuation multiples by growth rate rule of 40',
                    f'{sector} software market TAM CAGR growth forecast',
                ])
            
            for query in company_queries:
                sys.stderr.write(f"Company research: {query}\n")
                
                response = requests.post(
                    self.tavily_base_url,
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": 10,
                        "include_answer": True
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    company_data = response.json()
                    
                    # Clean the Tavily results but keep all data
                    cleaned_results = []
                    for result in company_data.get('results', []):
                        cleaned_result = {
                            'url': result.get('url', ''),
                            'title': result.get('title', ''),
                            'content': result.get('content', ''),  # Keep FULL content
                            'score': result.get('score', 0)
                        }
                        cleaned_results.append(cleaned_result)
                    
                    # Extract company-specific intelligence
                    if 'competitors' in query:
                        research["direct_competitors"] = self._extract_direct_competitors(company_data, company_name)
                    elif 'funding' in query:
                        funding_data = self._extract_company_funding(company_data, company_name)
                        research["company_funding"] = funding_data
                        research["total_funding"] = funding_data.get('total_raised', 0)
                        research["latest_round"] = funding_data.get('latest_round', {})
                    
                    # Update company intelligence
                    research["company_intelligence"] = self._extract_company_intelligence(company_data, company_name)
                    
                    # Store cleaned results (not raw)
                    research.setdefault("raw_company_results", []).extend(cleaned_results)
            
            # 2. Extract what the company does and find similar companies
            company_description = self._extract_company_description(research.get("raw_company_results", []), company_name)
            research["company_description"] = company_description
            
            if company_description:
                # Use full sector for similar companies to maintain context
                similar_companies_queries = [
                    f'"{sector}" companies that {company_description}',
                    f'"{sector}" companies similar to "{company_name}"',
                    f'{company_name} competitors in {sector} market'
                ]
                
                all_competitors = []
                for query in similar_companies_queries[:2]:
                    sys.stderr.write(f"Finding similar companies: {query}\n")
                    
                    response = requests.post(
                        self.tavily_base_url,
                        json={
                            "api_key": self.tavily_api_key,
                            "query": query,
                            "search_depth": "advanced",
                            "max_results": 10
                        },
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        competitors = self._extract_companies_from_results(data, company_name, sector)
                        all_competitors.extend(competitors)
                
                research["competitors"] = all_competitors[:10]
            
            # 3. Search for M&A deals and exits
            # Use more specific queries based on the exact sector from Supabase
            # For sectors like "SaaS-HR Tech", split and search both terms
            sector_parts = sector.split('-')
            primary_sector = sector_parts[0] if sector_parts else sector
            subsector = sector_parts[1] if len(sector_parts) > 1 else ""
            
            # Build HIGH-QUALITY deal searches that actually work
            exit_queries = []
            
            # Smart patterns that find real deals with numbers
            if subsector:
                exit_queries.extend([
                    # TechCrunch style reporting
                    f'"{subsector}" acquired "for $" million {PREV_YEAR} {CURRENT_YEAR}',
                    f'{subsector} acquisition announced terms "valued at" million',
                    # Find deals by actual competitors
                    f'companies similar to {company_name} acquired exit sold',
                ])
            
            # Patterns that actually appear in deal announcements
            exit_queries.extend([
                # How deals are actually reported
                f'{sector} "announces acquisition of" price terms {PREV_YEAR} {CURRENT_YEAR}',
                f'{sector} "acquired" "$" million "purchase price" {PREV_YEAR} {CURRENT_YEAR}',
                f'{sector} "buys" "for up to" million cash stock deal',
                
                # Revenue multiple patterns that appear in articles
                f'{sector} deal "times trailing revenue" OR "x ARR" valuation',
                f'{sector} transaction "annual recurring revenue" multiple premium',
                
                # Active buyer searches that work
                f'"{primary_sector}" "has acquired" portfolio companies {PREV_YEAR} {CURRENT_YEAR}',
                f'private equity buying {sector} companies roll up consolidation',
            ])
            
            # Add specific queries for common sectors
            if "HR" in sector.upper() or "HUMAN RESOURCE" in sector.upper():
                exit_queries.extend([
                    f'"HR tech" "HCM" acquisitions "million" "billion" {TWO_YEARS_AGO} {PREV_YEAR} {CURRENT_YEAR}',
                    '"payroll" "workforce management" "acquired for" deal value',
                    '"human capital management" M&A "revenue multiple"'
                ])
            elif "FINTECH" in sector.upper():
                exit_queries.extend([
                    f'"fintech" "payments" acquisitions "million" "billion" {TWO_YEARS_AGO} {PREV_YEAR} {CURRENT_YEAR}',
                    '"payment processing" "banking" "acquired for" deal value',
                    '"financial technology" M&A "revenue multiple"'
                ])
            elif "AI" in sector.upper() or "ML" in sector.upper():
                exit_queries.extend([
                    f'"AI" "machine learning" acquisitions "million" "billion" {TWO_YEARS_AGO} {PREV_YEAR} {CURRENT_YEAR}',
                    '"artificial intelligence" "ML platform" "acquired for" deal value',
                    '"AI startup" M&A "revenue multiple"'
                ])
            
            all_exit_comparables = []
            sys.stderr.write(f"\nSearching for exit comparables with {len(exit_queries)} queries...\n")
            sys.stderr.write(f"First 3 queries:\n")
            for i, q in enumerate(exit_queries[:3]):
                sys.stderr.write(f"  {i+1}. {q}\n")
            
            # Execute MORE queries for deeper research (was only 3!)
            for query in exit_queries[:10]:  # Increased from 3 to 10
                sys.stderr.write(f"\nExecuting search: {query}\n")
                
                response = requests.post(
                    self.tavily_base_url,
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": 20,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Clean the exit results
                    cleaned_exit_results = []
                    for result in data.get('results', []):
                        cleaned_result = {
                            'url': result.get('url', ''),
                            'title': result.get('title', ''),
                            'content': result.get('content', ''),  # Keep FULL content
                            'score': result.get('score', 0)
                        }
                        cleaned_exit_results.append(cleaned_result)
                    
                    comparables = self._extract_exit_comparables(data, sector)
                    all_exit_comparables.extend(comparables)
                    if 'raw_exit_results' not in research:
                        research['raw_exit_results'] = []
                    research['raw_exit_results'].extend(cleaned_exit_results)
            
            # Filter exit comparables to ensure sector relevance
            sector_filtered_comparables = []
            sector_keywords = self._get_sector_keywords(sector)
            
            for comp in all_exit_comparables:
                # Check if the deal details or company name matches sector keywords
                details = comp.get('details', '').lower()
                company = comp.get('company', '').lower()
                source = comp.get('source', '').lower()
                
                if any(keyword in details + company + source for keyword in sector_keywords):
                    sector_filtered_comparables.append(comp)
                elif comp.get('confidence') == 'high':  # Keep high confidence deals
                    sector_filtered_comparables.append(comp)
            
            sys.stderr.write(f"Found {len(all_exit_comparables)} total exit comparables\n")
            sys.stderr.write(f"After sector filtering: {len(sector_filtered_comparables)} comparables\n")
            research["exit_comparables"] = sector_filtered_comparables[:20]
            
            # 4. Get public SaaS company data for better multiples
            public_saas_data = self._scrape_public_saas_comparables(sector)
            if public_saas_data:
                research["public_comparables"] = public_saas_data.get("comparables", [])
                research["potential_acquirers"] = public_saas_data.get("acquirers", [])
                research["median_ev_multiple"] = public_saas_data.get("median_multiple", 0)
            
            # Build acquirer list from actual data
            unique_acquirers = {}
            
            # Extract acquirers from M&A deals
            for deal in research.get("exit_comparables", []):
                acquirer = deal.get("acquirer")
                if acquirer and acquirer != "Unknown":
                    if acquirer not in unique_acquirers:
                        unique_acquirers[acquirer] = {
                            "name": acquirer,
                            "deals": [],
                            "total_spent": 0,
                            "avg_multiple": []
                        }
                    unique_acquirers[acquirer]["deals"].append(deal)
                    if deal.get("deal_value"):
                        unique_acquirers[acquirer]["total_spent"] += deal["deal_value"]
                    if deal.get("revenue_multiple"):
                        unique_acquirers[acquirer]["avg_multiple"].append(deal["revenue_multiple"])
            
            # Add incumbents as potential acquirers
            if hasattr(self, '_market_landscape_data'):
                for incumbent in self._market_landscape_data.get("incumbents", []):
                    if incumbent["name"] not in unique_acquirers:
                        unique_acquirers[incumbent["name"]] = {
                            "name": incumbent["name"],
                            "type": "strategic",
                            "market_cap": incumbent.get("market_cap", ""),
                            "deals": [],
                            "source": "incumbent"
                        }
            
            # Format acquirer list
            acquirer_list = []
            for name, data in unique_acquirers.items():
                acq = {
                    "name": name,
                    "type": "strategic",
                    "deals_count": len(data["deals"]),
                    "total_acquisition_spend": data.get("total_spent", 0),
                    "recent_deals": [d["target"] for d in data["deals"][:3]]
                }
                if data.get("avg_multiple") and len(data.get("avg_multiple", [])) > 0:
                    acq["avg_acquisition_multiple"] = sum(data["avg_multiple"]) / len(data["avg_multiple"])
                acquirer_list.append(acq)
            
            # Sort by activity (deals count + spend)
            acquirer_list.sort(key=lambda x: x["deals_count"] + x["total_acquisition_spend"]/1000, reverse=True)
            
            sys.stderr.write(f"Found {len(unique_acquirers)} unique acquirers from M&A deals\n")
            sys.stderr.write(f"Top acquirers: {', '.join([a['name'] for a in acquirer_list[:5]])}\n" if acquirer_list else "No acquirers found\n")
            
            research["data_driven_acquirers"] = acquirer_list[:20]  # Top 20 most active
            
            # Keep backward compatibility but prioritize real data
            research["comparables"] = research.get("exit_comparables", [])
            # Use data_driven_acquirers from actual search results, not potential_acquirers
            research["acquirers"] = acquirer_list[:20] if acquirer_list else research.get("potential_acquirers", [])
            
        except Exception as e:
            sys.stderr.write(f"Tavily search error: {e}\n")
            import traceback
            traceback.print_exc(file=sys.stderr)
        
        # If Tavily fails, ensure we return empty research to use cached data
        if not research:
            research = {
                "graduation_rates": {},
                "comparables": [],
                "acquirers": [],
                "competitors": [],
                "market_conditions": {},
                "sector_analysis": {}
            }
        
        # Auto-detect the real sector based on what we found
        detected_sector = self._detect_sector_from_sources(research, sector)
        if detected_sector != sector:
            sys.stderr.write(f"Correcting sector from '{sector}' to '{detected_sector}' based on search results\n")
            research["detected_sector"] = detected_sector
            research["original_sector"] = sector
            # Update the sector for better comparables
            sector = detected_sector
        
        return research
    
    def _extract_comparables(self, search_data: Dict) -> List[Dict]:
        """Extract comparable companies from search results"""
        comparables = []
        if search_data.get('results'):
            for result in search_data['results'][:10]:
                comparables.append({
                    "name": result.get('title', 'Unknown'),
                    "revenue": self._extract_revenue(result.get('content', '')),
                    "growth_rate": self._extract_growth_rate(result.get('content', '')),
                    "valuation": self._extract_valuation(result.get('content', '')),
                    "sector": "Technology"
                })
        return comparables
    
    def _extract_acquirers(self, search_data: Dict) -> List[Dict]:
        """Extract potential acquirers from search results"""
        acquirers = []
        if search_data.get('results'):
            for result in search_data['results'][:8]:
                acquirers.append({
                    "name": result.get('title', 'Unknown'),
                    "acquisition_history": self._extract_acquisition_history(result.get('content', '')),
                    "strategic_fit": "High",
                    "financial_capacity": "High"
                })
        return acquirers
    
    def _extract_revenue(self, text: str) -> float:
        """Extract revenue from text"""
        import re
        patterns = [
            r'(\$[\d,]+(?:\.\d+)?)\s*(?:million|m|billion|b)\s*(?:revenue|arr)',
            r'revenue.*?(\$[\d,]+(?:\.\d+)?)\s*(?:million|m|billion|b)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                revenue_str = match.group(1).replace(',', '')
                if 'billion' in text.lower() or 'b' in text.lower():
                    return float(revenue_str.replace('$', '')) * 1000
                else:
                    return float(revenue_str.replace('$', ''))
        return 10.0  # Default
    
    def _extract_growth_rate(self, text: str) -> float:
        """Extract growth rate from text"""
        import re
        pattern = r'(\d+(?:\.\d+)?)\s*%\s*(?:growth|increase|yoy)'
        match = re.search(pattern, text.lower())
        if match:
            return float(match.group(1)) / 100
        return 0.30  # Default 30%
    
    def _extract_valuation(self, text: str) -> float:
        """Extract valuation from text"""
        import re
        patterns = [
            r'(\$[\d,]+(?:\.\d+)?)\s*(?:million|m|billion|b)\s*(?:valuation|worth)',
            r'valued.*?(\$[\d,]+(?:\.\d+)?)\s*(?:million|m|billion|b)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                val_str = match.group(1).replace(',', '')
                if 'billion' in text.lower() or 'b' in text.lower():
                    return float(val_str.replace('$', '')) * 1000
                else:
                    return float(val_str.replace('$', ''))
        return 50.0  # Default
    
    def _get_sector_keywords(self, sector: str) -> List[str]:
        """Get relevant keywords for a sector to filter results"""
        sector_lower = sector.lower()
        keywords = []
        
        # Add the full sector as primary keyword (most important)
        keywords.append(sector_lower)
        
        # For compound sectors, add the combination as well
        if '-' in sector_lower:
            parts = sector_lower.split('-')
            # Add the main category with context
            if len(parts) == 2:
                keywords.append(f"{parts[0]} {parts[1]}")  # "defense autonomous systems"
                # Only add individual parts if they're meaningful
                if parts[0] not in ['saas', 'b2b', 'b2c']:  # Don't add generic terms alone
                    keywords.append(parts[0])
        
        # Add sector-specific keywords based on the FULL sector string
        if 'defense' in sector_lower:
            keywords.extend(['defense tech', 'defense technology', 'military tech', 'defense contractor'])
            if 'autonomous' in sector_lower:
                keywords.extend(['autonomous weapons', 'military ai', 'defense ai'])
        elif 'hr tech' in sector_lower or 'human resource' in sector_lower:
            keywords.extend(['hr tech', 'hr technology', 'hcm', 'hrms', 'hris', 'human capital'])
        elif 'fintech' in sector_lower:
            keywords.extend(['fintech', 'financial technology', 'payments tech'])
        elif 'climate' in sector_lower:
            keywords.extend(['climate tech', 'cleantech', 'carbon tech', 'sustainability tech'])
        elif 'health' in sector_lower:
            keywords.extend(['healthtech', 'digital health', 'medical tech'])
        
        return list(set(keywords))  # Remove duplicates
    
    def _extract_acquisition_history(self, text: str) -> str:
        """Extract acquisition history from text"""
        if 'acquired' in text.lower() or 'acquisition' in text.lower():
            return "Active acquirer"
        return "Potential acquirer"
    
    def _detect_sector_from_sources(self, research_results: Dict, original_sector: str) -> str:
        """
        Detect the actual sector based on search results and sources
        """
        # Analyze all the search results for sector indicators
        sector_indicators = {
            'Health': ['healthcare', 'medical', 'nursing', 'hospital', 'clinical', 'patient', 'doctor', 'physician', 'health tech', 'healthtech', 'telemedicine', 'pharma'],
            'B2B Fintech': ['payments', 'banking', 'financial services', 'treasury', 'card issuing', 'payment processing', 'fintech infrastructure'],
            'B2C Fintech': ['consumer finance', 'personal finance', 'neobank', 'digital banking', 'mobile banking', 'consumer payments'],
            'HR': ['human resources', 'HR tech', 'workforce', 'staffing', 'recruiting', 'payroll', 'employee', 'talent', 'hiring', 'HRIS'],
            'AI': ['artificial intelligence', 'machine learning', 'LLM', 'neural', 'deep learning', 'AI model', 'GPT', 'transformer'],
            'Cyber': ['cybersecurity', 'security', 'threat detection', 'vulnerability', 'encryption', 'firewall', 'SIEM', 'zero trust'],
            'Data Infrastructure': ['data platform', 'data warehouse', 'ETL', 'data pipeline', 'analytics infrastructure', 'data lake'],
            'Dev Tool': ['developer tool', 'DevOps', 'CI/CD', 'IDE', 'code editor', 'development platform', 'API platform'],
            'Defense': ['defense contractor', 'military', 'DoD', 'Pentagon', 'defense technology', 'national security'],
            'Space': ['satellite', 'spacecraft', 'launch vehicle', 'space technology', 'orbital', 'aerospace', 'space exploration'],
            'Climate Software': ['carbon', 'emissions', 'sustainability', 'ESG', 'climate tech', 'renewable', 'clean energy'],
            'SaaS': ['software as a service', 'SaaS', 'cloud software', 'subscription software'],
        }
        
        # Count occurrences of sector indicators in all search results
        sector_scores = {}
        
        # Check company description and intelligence
        for key in ['company_description', 'company_intelligence']:
            if key in research_results:
                content = str(research_results[key]).lower()
                for sector, keywords in sector_indicators.items():
                    if sector not in sector_scores:
                        sector_scores[sector] = 0
                    for keyword in keywords:
                        if keyword.lower() in content:
                            sector_scores[sector] += 2  # Higher weight for direct company info
        
        # Check search results
        for result in research_results.get('raw_company_results', []):
            content = (result.get('content', '') + ' ' + result.get('title', '')).lower()
            for sector, keywords in sector_indicators.items():
                if sector not in sector_scores:
                    sector_scores[sector] = 0
                for keyword in keywords:
                    if keyword.lower() in content:
                        sector_scores[sector] += 1
        
        # If we have strong signals for a specific sector, use it
        if sector_scores:
            best_sector = max(sector_scores, key=sector_scores.get)
            if sector_scores[best_sector] > 5:  # Threshold for confidence
                sys.stderr.write(f"Auto-detected sector '{best_sector}' from sources (score: {sector_scores[best_sector]})\n")
                return best_sector
        
        # Fall back to original sector
        return original_sector
    
    def _extract_company_description(self, results: List[Dict], company_name: str) -> str:
        """Extract what the company does from search results"""
        descriptions = []
        
        for result in results[:5]:
            content = result.get('content', '')
            
            import re
            patterns = [
                f'{company_name}\\s+(?:is|provides|offers|develops)\\s+([^.]+)',
                f'{company_name},?\\s+(?:a|an|the)\\s+([^,]+)\\s+(?:that|which)\\s+([^.]+)',
                f'(?:helps|enables|allows)\\s+(?:companies|businesses|organizations)\\s+(?:to\\s+)?([^.]+)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        desc = ' '.join(match).strip()
                    else:
                        desc = match.strip()
                    
                    if len(desc) > 20 and len(desc) < 200:
                        descriptions.append(desc)
        
        return descriptions[0] if descriptions else 'provide software solutions'
    
    def _extract_direct_competitors(self, search_data: Dict, company_name: str) -> List[Dict]:
        """Extract competitors from search results"""
        competitors = []
        seen_names = set()
        
        if search_data.get('results'):
            for result in search_data['results']:
                content = result.get('content', '')
                
                import re
                patterns = [
                    r'competitors?\s+(?:include|are|such as)\s+([^.]+)',
                    r'competes?\s+with\s+([^.]+)',
                    r'alternatives?\s+to\s+' + re.escape(company_name) + r'\s+(?:include|are)\s+([^.]+)',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        potential_competitors = re.split(r',|and|\s+vs\s+', match)
                        for comp in potential_competitors:
                            comp = comp.strip()
                            comp = re.sub(r'\s*(Inc\.?|Corp\.?|LLC|Ltd\.?|Limited|plc)$', '', comp, flags=re.IGNORECASE).strip()
                            
                            if (comp and comp.lower() != company_name.lower() and 
                                comp not in seen_names and len(comp) > 2):
                                seen_names.add(comp)
                                competitors.append({
                                    'name': comp,
                                    'mentioned_count': 1,
                                    'source': 'Market Research'
                                })
        
        return competitors[:10]
    
    def _extract_customer_intelligence(self, search_data: Dict, company_name: str) -> Dict:
        """Extract customer information from search results"""
        customer_info = {
            'notable_customers': [],
            'customer_segments': [],
            'enterprise_customers': [],
            'customer_count': None,
            'customer_logos': []
        }
        
        if not search_data.get('results'):
            return customer_info
            
        import re
        for result in search_data['results']:
            content = result.get('content', '')
            
            # Look for customer mentions
            customer_patterns = [
                r'customers include ([^\.]+)',
                r'clients include ([^\.]+)',
                r'used by ([^\.]+)',
                r'trusted by ([^\.]+)',
                r'powers ([^\.]+)',
                r'serves ([^\.]+)',
            ]
            
            for pattern in customer_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Extract company names from the match
                    companies = re.findall(r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b', match)
                    for comp in companies:
                        if len(comp) > 2 and comp not in customer_info['notable_customers']:
                            customer_info['notable_customers'].append(comp)
                            # Check if enterprise
                            if any(ent in comp for ent in ['Microsoft', 'Google', 'Amazon', 'Facebook', 'Apple', 'IBM', 'Oracle', 'Salesforce']):
                                customer_info['enterprise_customers'].append(comp)
            
            # Look for customer count
            count_patterns = [
                r'(\d+[,\d]*)\s*(?:customers|clients|companies)',
                r'serves?\s+(?:over\s+)?(\d+[,\d]*)\s*(?:customers|clients)',
            ]
            
            for pattern in count_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        count = int(match.group(1).replace(',', ''))
                        if customer_info['customer_count'] is None or count > customer_info['customer_count']:
                            customer_info['customer_count'] = count
                    except:
                        pass
        
        return customer_info
    
    def _detect_megafund_investors(self, funding_data: Dict) -> Dict:
        """Detect if company is backed by megafunds (funds with >$1B AUM)"""
        megafunds = [
            'Sequoia', 'Andreessen Horowitz', 'a16z', 'Accel', 'Benchmark', 'Bessemer',
            'GV', 'Google Ventures', 'Greylock', 'Index Ventures', 'Insight Partners',
            'Kleiner Perkins', 'Lightspeed', 'NEA', 'Tiger Global', 'Coatue',
            'General Catalyst', 'Founders Fund', 'Thrive Capital', 'DST Global',
            'SoftBank', 'Vision Fund', 'Silver Lake', 'TPG', 'KKR', 'Blackstone'
        ]
        
        result = {
            'has_megafund_backing': False,
            'megafund_investors': [],
            'megafund_percentage': 0,
            'investor_quality_score': 0
        }
        
        investors = funding_data.get('investors', [])
        if not investors:
            return result
            
        for investor in investors:
            investor_lower = investor.lower()
            for megafund in megafunds:
                if megafund.lower() in investor_lower:
                    result['has_megafund_backing'] = True
                    if megafund not in result['megafund_investors']:
                        result['megafund_investors'].append(megafund)
        
        if investors:
            result['megafund_percentage'] = len(result['megafund_investors']) / len(investors) * 100
            # Quality score based on megafund backing
            if result['megafund_percentage'] >= 50:
                result['investor_quality_score'] = 90
            elif result['megafund_percentage'] >= 30:
                result['investor_quality_score'] = 75
            elif result['has_megafund_backing']:
                result['investor_quality_score'] = 60
            else:
                result['investor_quality_score'] = 40
                
        return result
    
    def calculate_waterfall_analysis(self, funding_data: Dict, exit_value: float) -> Dict:
        """
        Calculate waterfall analysis showing how exit proceeds flow through the cap table
        based on funding history and liquidation preferences
        """
        if not funding_data or 'rounds' not in funding_data:
            return {
                'error': 'No funding data available for waterfall analysis',
                'total_raised': 0,
                'distributions': []
            }
        
        rounds = funding_data.get('rounds', [])
        total_raised = funding_data.get('total_raised', 0)
        
        # Build cap table structure
        cap_table = []
        cumulative_dilution = 0
        
        for round_info in rounds:
            # Extract round details
            amount = round_info.get('amount', 0)
            valuation = round_info.get('valuation', 0)
            round_type = round_info.get('type', 'Unknown')
            
            # Estimate ownership percentage (simplified)
            if valuation > 0:
                ownership = (amount / (valuation + amount)) * 100
            else:
                # Default ownership assumptions by round
                ownership_defaults = {
                    'seed': 15,
                    'series_a': 20,
                    'series_b': 15,
                    'series_c': 12,
                    'series_d': 10,
                    'late_stage': 8
                }
                stage = self._normalize_funding_stage(round_type)
                ownership = ownership_defaults.get(stage, 10)
            
            cap_table.append({
                'round': round_type,
                'amount': amount,
                'ownership': ownership,
                'liquidation_preference': amount,  # Assume 1x non-participating
                'participation': False
            })
            cumulative_dilution += ownership
        
        # Calculate distributions at exit
        distributions = []
        remaining_proceeds = exit_value
        
        # First, pay out liquidation preferences (last in, first out)
        for entry in reversed(cap_table):
            if remaining_proceeds <= 0:
                break
                
            pref_payout = min(entry['liquidation_preference'], remaining_proceeds)
            distributions.append({
                'round': entry['round'],
                'type': 'Liquidation Preference',
                'amount': pref_payout,
                'percentage': (pref_payout / exit_value) * 100 if exit_value > 0 else 0
            })
            remaining_proceeds -= pref_payout
        
        # Then distribute remaining proceeds pro-rata
        if remaining_proceeds > 0:
            # Founders/employees get what's left after investor ownership
            founder_ownership = max(0, 100 - cumulative_dilution)
            
            if founder_ownership > 0:
                founder_proceeds = remaining_proceeds * (founder_ownership / 100)
                distributions.append({
                    'round': 'Founders & Employees',
                    'type': 'Common Stock',
                    'amount': founder_proceeds,
                    'percentage': (founder_proceeds / exit_value) * 100 if exit_value > 0 else 0
                })
            
            # Distribute to investors based on ownership
            for entry in cap_table:
                investor_proceeds = remaining_proceeds * (entry['ownership'] / 100)
                distributions.append({
                    'round': entry['round'],
                    'type': 'Pro-rata Distribution',
                    'amount': investor_proceeds,
                    'percentage': (investor_proceeds / exit_value) * 100 if exit_value > 0 else 0
                })
        
        # Calculate returns for each round
        returns_analysis = []
        for entry in cap_table:
            round_distributions = [d for d in distributions if d['round'] == entry['round']]
            total_return = sum([d['amount'] for d in round_distributions])
            multiple = total_return / entry['amount'] if entry['amount'] > 0 else 0
            
            returns_analysis.append({
                'round': entry['round'],
                'invested': entry['amount'],
                'returned': total_return,
                'multiple': multiple,
                'irr': self._estimate_irr_from_multiple(multiple, entry['round'])
            })
        
        return {
            'total_raised': total_raised,
            'exit_value': exit_value,
            'distributions': distributions,
            'returns_by_round': returns_analysis,
            'founder_proceeds': sum([d['amount'] for d in distributions if 'Founders' in d['round']]),
            'investor_proceeds': exit_value - sum([d['amount'] for d in distributions if 'Founders' in d['round']])
        }
    
    def _estimate_irr_from_multiple(self, multiple: float, round_type: str) -> float:
        """Estimate IRR based on multiple and typical hold periods"""
        hold_periods = {
            'seed': 7,
            'series_a': 6,
            'series_b': 5,
            'series_c': 4,
            'series_d': 3,
            'late_stage': 2
        }
        
        stage = self._normalize_funding_stage(round_type)
        years = hold_periods.get(stage, 5)
        
        if multiple <= 0 or years <= 0:
            return 0
        
        # IRR = (Multiple^(1/years) - 1) * 100
        irr = (multiple ** (1/years) - 1) * 100
        return round(irr, 1)
    
    def calculate_winner_probability(self, company_name: str, outlier_score: Dict, 
                                    funding_data: Dict, customer_data: Dict, 
                                    market_data: Dict) -> Dict:
        """Calculate probability that this company will be a winner (>$1B exit)"""
        
        # Base probabilities by stage
        stage_probabilities = {
            'seed': 0.005,
            'series_a': 0.015,
            'series_b': 0.04,
            'series_c': 0.12,
            'series_d': 0.25,
            'late_stage': 0.35
        }
        
        # Detect current stage from funding data
        current_stage = self._detect_funding_stage(funding_data)
        base_prob = stage_probabilities.get(current_stage, 0.01)
        
        # Adjustment factors
        adjustments = []
        
        # 1. Outlier score adjustment (up to 3x)
        outlier_mult = 1.0 + (outlier_score.get('overall_outlier_score', 50) / 100) * 2
        adjustments.append(('outlier_score', outlier_mult))
        
        # 2. Megafund backing (up to 2x)
        megafund_data = self._detect_megafund_investors(funding_data)
        if megafund_data['has_megafund_backing']:
            megafund_mult = 1.5 + (megafund_data['megafund_percentage'] / 200)
            adjustments.append(('megafund_backing', megafund_mult))
        
        # 3. Customer quality (up to 1.5x)
        enterprise_count = len(customer_data.get('enterprise_customers', []))
        if enterprise_count > 0:
            customer_mult = 1.2 + min(enterprise_count * 0.1, 0.3)
            adjustments.append(('enterprise_customers', customer_mult))
        
        # 4. Growth rate (up to 2x)
        growth_rate = market_data.get('growth_rate', 0)
        if growth_rate > 100:
            growth_mult = 1.5 + min((growth_rate - 100) / 200, 0.5)
            adjustments.append(('high_growth', growth_mult))
        
        # Calculate final probability
        final_mult = 1.0
        for _, mult in adjustments:
            final_mult *= mult
        
        winner_prob = min(base_prob * final_mult, 0.85)  # Cap at 85%
        
        return {
            'winner_probability': winner_prob,
            'base_probability': base_prob,
            'current_stage': current_stage,
            'adjustments': adjustments,
            'final_multiplier': final_mult,
            'megafund_backing': megafund_data,
            'is_likely_winner': winner_prob > 0.15,
            'winner_confidence': 'high' if winner_prob > 0.3 else 'medium' if winner_prob > 0.1 else 'low',
            'winner_factors': self._get_winner_factors(outlier_score, megafund_data, customer_data, growth_rate)
        }
    
    def _detect_funding_stage(self, funding_data: Dict) -> str:
        """Detect current funding stage from data"""
        latest_round = funding_data.get('latest_round', {})
        round_type = latest_round.get('type', '').lower()
        
        if 'seed' in round_type or 'pre' in round_type:
            return 'seed'
        elif 'series a' in round_type or 'series-a' in round_type:
            return 'series_a'
        elif 'series b' in round_type or 'series-b' in round_type:
            return 'series_b'
        elif 'series c' in round_type or 'series-c' in round_type:
            return 'series_c'
        elif 'series d' in round_type or 'series-d' in round_type:
            return 'series_d'
        elif 'series' in round_type:
            return 'late_stage'
        
        # Fallback: guess by funding amount
        total_raised = funding_data.get('total_raised', 0)
        if total_raised > 100:
            return 'late_stage'
        elif total_raised > 50:
            return 'series_c'
        elif total_raised > 20:
            return 'series_b'
        elif total_raised > 5:
            return 'series_a'
        else:
            return 'seed'
    
    def _get_winner_factors(self, outlier_score: Dict, megafund_data: Dict, 
                           customer_data: Dict, growth_rate: float) -> List[str]:
        """Identify key factors that indicate winner potential"""
        factors = []
        
        if outlier_score.get('overall_outlier_score', 0) > 70:
            factors.append('Exceptional outlier score indicates breakout potential')
        
        if megafund_data['has_megafund_backing']:
            factors.append(f"Backed by tier-1 megafunds: {', '.join(megafund_data['megafund_investors'][:3])}")
        
        if len(customer_data.get('enterprise_customers', [])) > 2:
            factors.append(f"Strong enterprise traction with {len(customer_data['enterprise_customers'])} Fortune 500 customers")
        
        if growth_rate > 150:
            factors.append(f"Hypergrowth at {growth_rate:.0f}% annually")
        
        if not factors:
            factors.append('Standard growth trajectory for the sector')
            
        return factors

    def _extract_company_funding(self, search_data: Dict, company_name: str) -> Dict:
        """Extract funding information from search results"""
        funding_info = {
            'total_raised': 0,
            'last_round': None,
            'last_valuation': 0,
            'investors': [],
            'latest_round': {}
        }
        
        if search_data.get('results'):
            for result in search_data['results']:
                content = result.get('content', '')
                
                import re
                # More comprehensive funding patterns
                funding_patterns = [
                    r'\$?([\d,]+(?:\.\d+)?)\s*(?:billion|million|M|B)\s*(?:raised|in funding|total funding)',
                    r'raised\s+\$?([\d,]+(?:\.\d+)?)\s*(?:billion|million|M|B)',
                    r'funding.*?\$?([\d,]+(?:\.\d+)?)\s*(?:billion|million|M|B)',
                ]
                
                for pattern in funding_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        try:
                            value_str = match.replace(',', '')
                            value = float(value_str)
                            if 'billion' in content[max(0, content.find(match)-20):content.find(match)+20].lower():
                                value *= 1000
                            funding_info['total_raised'] = max(funding_info['total_raised'], value)
                        except:
                            pass
                
                # Extract valuation
                val_patterns = [
                    r'valued?\s+at\s+\$?([\d,]+(?:\.\d+)?)\s*(?:billion|million|B|M)',
                    r'valuation.*?\$?([\d,]+(?:\.\d+)?)\s*(?:billion|million|B|M)',
                ]
                
                for pattern in val_patterns:
                    val_match = re.search(pattern, content, re.IGNORECASE)
                    if val_match:
                        try:
                            val = float(val_match.group(1).replace(',', ''))
                            if 'billion' in val_match.group(0).lower():
                                val *= 1000
                            funding_info['last_valuation'] = max(funding_info['last_valuation'], val)
                        except:
                            pass
        
        return funding_info
    
    def _extract_companies_from_results(self, search_data: Dict, exclude_company: str, sector: str) -> List[Dict]:
        """Extract company names from search results"""
        companies = []
        seen_names = set()
        
        if search_data.get('results'):
            for result in search_data['results']:
                content = result.get('content', '')
                
                import re
                # Better patterns for company name extraction
                company_patterns = [
                    # Match company names with various formats (e.g., OpenAI, Stripe, Claude.ai)
                    r'\b([A-Z][a-zA-Z0-9]*(?:[\.\-][a-zA-Z0-9]+)?(?:\s+[A-Z][a-zA-Z0-9]*)?)\b',
                    # Match companies mentioned with context
                    r'(?:company|startup|firm)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)',
                    # Match companies in common patterns
                    r'(?:raised by|acquired|founded|backed)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)',
                ]
                
                potential_companies = []
                for pattern in company_patterns:
                    matches = re.findall(pattern, content)
                    potential_companies.extend(matches)
                
                for comp in potential_companies:
                    comp = comp.strip()
                    if (comp and comp.lower() != exclude_company.lower() and
                        comp not in seen_names and len(comp) > 3):
                        
                        comp_index = content.find(comp)
                        if comp_index >= 0:
                            context = content[max(0, comp_index-50):min(len(content), comp_index+50)].lower()
                            if any(indicator in context for indicator in [
                                'raises', 'raised', 'funding', 'valued', 'acquired',
                                'competes', 'competitor', 'alternative', 'platform'
                            ]):
                                seen_names.add(comp)
                                companies.append({
                                    'name': comp,
                                    'mentioned_count': 1,
                                    'source': 'Similar Companies Search',
                                    'sector': sector
                                })
        
        return companies
    
    def _extract_company_intelligence(self, search_data: Dict, company_name: str) -> Dict:
        """Extract key company metrics from search results"""
        intelligence = {
            'revenue': None,
            'arr': None,
            'growth_rate': None,
            'employee_count': None,
            'funding_total': None,
            'last_valuation': None,
            'product_market_fit_signals': [],
            'traction_metrics': []
        }
        
        # Implementation would extract these metrics from search results
        return intelligence
    
    def _extract_exit_comparables(self, search_data: Dict, input_sector: str = None) -> List[Dict]:
        """Extract exit comparable deals using Claude for better extraction"""
        if not search_data.get('results') or not self.claude_api_key:
            return []
        
        # Collect all relevant content
        all_content = []
        for result in search_data['results']:
            content = result.get('content', '')
            title = result.get('title', '')
            if any(word in content.lower() for word in ['acquired', 'acquisition', 'bought', 'sold', 'merger', 'deal', 'valuation']):
                all_content.append(f"Title: {title}\nContent: {content[:1000]}")
        
        if not all_content:
            return []
        
        # Use Claude to extract M&A deals
        try:
            prompt = f"""
            Extract M&A deals from the following search results. 
            
            CRITICAL: You MUST ONLY extract deals where the target company is SPECIFICALLY in the {input_sector} sector.
            
            EXCLUDE these generic tech companies unless the deal is SPECIFICALLY about {input_sector}:
            - Salesforce, Google, Microsoft, Oracle, Amazon, Apple, Meta, IBM
            - ServiceNow, Workday, SAP, Adobe, VMware (unless they acquired a {input_sector} company)
            
            For {input_sector}, ONLY include companies that:
            - Actually operate in {input_sector} as their primary business
            - Were acquired because of their {input_sector} capabilities
            - Have products/services specifically for {input_sector}
            
            Examples of what to include for different sectors:
            - "HR Tech": BambooHR, Gusto, Rippling, Lever, Greenhouse (NOT generic enterprise software)
            - "Defense Tech": Anduril, Shield AI, Epirus (NOT generic tech companies)
            - "Fintech": Stripe, Plaid, Chime (NOT generic software companies)
            - "Climate Tech": Carbon capture, renewable energy, climate analytics companies
            
            SEARCH RESULTS:
            {chr(10).join(all_content[:10])}
            
            Extract acquisition deals where the TARGET company is SPECIFICALLY a {input_sector} company.
            
            For each RELEVANT deal, extract:
            - Target company name
            - Acquirer company name  
            - Deal value (in millions)
            - Target's annual revenue at time of acquisition (if mentioned)
            - Revenue multiple (calculate as deal_value/revenue if both available)
            - Year of acquisition
            - Brief description proving the target is a {input_sector} company
            
            Return as JSON array. If NO sector-specific deals found, return empty array []:
            [
                {{
                    "target": "Company Name",
                    "acquirer": "Acquirer Name",
                    "deal_value": 1500,
                    "target_revenue": 150,
                    "revenue_multiple": 10.0,
                    "year": str(CURRENT_YEAR),
                    "sector": "{input_sector}",
                    "details": "MUST explain why this is a {input_sector} company"
                }}
            ]
            
            IMPORTANT: Better to return [] than include irrelevant deals.
            """
            
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                
                # Extract JSON array
                import re
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    deals = json.loads(json_match.group())
                    
                    # Format deals
                    exits = []
                    for deal in deals:
                        # Handle flexible values - N/A becomes None/null
                        def parse_value(value):
                            if value is None or value == '' or (isinstance(value, str) and value.upper() == 'N/A'):
                                return None
                            try:
                                return float(value)
                            except (ValueError, TypeError):
                                return None
                        
                        exits.append({
                            "company": deal.get('target', 'Unknown'),
                            "acquirer": deal.get('acquirer', 'Unknown'),
                            "target": deal.get('target', 'Unknown'),
                            "deal_value": parse_value(deal.get('deal_value')),
                            "ev_revenue_multiple": parse_value(deal.get('revenue_multiple')),
                            "revenue_multiple": parse_value(deal.get('revenue_multiple')),
                            "date": deal.get('year', str(CURRENT_YEAR)),
                            "sector": input_sector,
                            "type": "acquisition",
                            "source": f"Tavily: {deal.get('acquirer')} acquired {deal.get('target')}" + 
                                    (f" for ${deal.get('deal_value')}M" if deal.get('deal_value') and str(deal.get('deal_value')).upper() != 'N/A' else ""),
                            "confidence": "high",
                            "details": deal.get('details', '')
                        })
                    
                    return exits
                    
        except Exception as e:
            sys.stderr.write(f"Claude M&A extraction error: {e}\n")
        
        # Fallback to simple extraction if Claude fails
        return self._simple_exit_extraction(search_data, input_sector)
    
    def _simple_exit_extraction(self, search_data: Dict, input_sector: str) -> List[Dict]:
        """Simple fallback extraction"""
        exits = []
        # Keep existing regex logic as fallback
        return exits
    
    def _extract_deal_multiple(self, content: str, company_name: str) -> float:
        """Extract revenue multiple for a specific deal"""
        import re
        search_area = content
        if company_name:
            company_index = content.lower().find(company_name.lower())
            if company_index >= 0:
                start = max(0, company_index - 400)
                end = min(len(content), company_index + 400)
                search_area = content[start:end]
        
        patterns = [
            r'(\d+(?:\.\d+)?)\s*[xX]\s*(?:revenue|sales|ARR)',
            r'revenue\s+multiple\s+of\s+(\d+(?:\.\d+)?)',
            r'valued?\s+at\s+(\d+(?:\.\d+)?)\s*(?:times|x)\s*(?:revenue|sales)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, search_area, re.IGNORECASE)
            if match:
                try:
                    multiple = float(match.group(1))
                    if 0.5 <= multiple <= 100:
                        return multiple
                except:
                    pass
        return 0
    
    def _extract_company_revenue(self, content: str, company_name: str) -> float:
        """Extract revenue for a specific company"""
        import re
        search_area = content
        if company_name:
            company_index = content.lower().find(company_name.lower())
            if company_index >= 0:
                start = max(0, company_index - 500)
                end = min(len(content), company_index + 500)
                search_area = content[start:end]
        
        patterns = [
            r'revenue\s+of\s+\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)',
            r'\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)\s+in\s+(?:annual\s+)?revenue',
            r'ARR\s+of\s+\$?([\d,]+(?:\.\d+)?)\s*(?:million|billion|M|B)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, search_area, re.IGNORECASE)
            for match in matches:
                try:
                    value_str = match.replace(',', '')
                    value = float(value_str)
                    if any(b in search_area.lower() for b in ['billion', ' b ']):
                        value *= 1000
                    if 0.1 <= value <= 100000:
                        return value
                except:
                    pass
        return 0
    
    def _scrape_public_saas_comparables(self, sector: str) -> Dict:
        """Get comprehensive public SaaS data including acquirer insights"""
        try:
            # Import the enhanced scrapers with proper path handling
            import sys
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            
            from public_saas_scraper import PublicSaaSScraper
            from enhanced_public_saas_acquirers import EnhancedPublicSaaSAcquirers
            
            # Get base public SaaS data
            scraper = PublicSaaSScraper()
            base_data = scraper.fetch_public_saas_data()
            
            # Get acquirer insights
            acquirer_analyzer = EnhancedPublicSaaSAcquirers(self.tavily_api_key)
            
            # Combine data for comprehensive analysis
            combined_data = {
                "public_companies": base_data.get('companies', []),
                "categories": base_data.get('categories', {}),
                "strategic_acquirers": acquirer_analyzer.strategic_acquirers,
                "pe_acquirers": acquirer_analyzer.pe_acquirers,
                "sector": sector
            }
            
            # Send combined data to Claude for intelligent analysis
            return self._analyze_combined_market_data_with_claude(combined_data, sector)
            
        except Exception as e:
            sys.stderr.write(f"Public SaaS data error: {e}\n")
            import traceback
            traceback.print_exc(file=sys.stderr)
        
        return {
            "comparables": [],
            "acquirers": [],
            "median_multiple": 0,
            "acquirer_insights": {}
        }
    
    def _analyze_combined_market_data_with_claude(self, combined_data: Dict, sector: str) -> Dict:
        """Let Claude analyze combined Tavily + PublicSaaS data for comprehensive insights"""
        try:
            # Extract ALL data for analysis
            public_companies = combined_data.get('public_companies', [])
            strategic_acquirers = combined_data.get('strategic_acquirers', {})
            
            prompt = f"""
            Analyze market data to find SECTOR-SPECIFIC comparables and acquirers for {sector}.
            
            CRITICAL REQUIREMENTS:
            - ONLY suggest comparables that actually operate in {sector}
            - ONLY suggest acquirers who have acquired {sector} companies or would strategically benefit
            - DO NOT include generic tech giants (Google, Microsoft, Salesforce, Oracle) unless they specifically acquire in {sector}
            - Focus on finding companies that are TRUE peers in the {sector} space
            
            PUBLIC SAAS COMPANIES DATA:
            {json.dumps(public_companies[:20], indent=2) if public_companies else "[]"}
            
            SECTOR CONTEXT FOR {sector}:
            - Find companies that SPECIFICALLY operate in this sector
            - Look for acquirers who have a track record in this specific vertical
            - Multiples should reflect sector-specific dynamics, not generic SaaS
            
            ANALYSIS REQUIRED:
            1. Identify public comparables that ACTUALLY operate in {sector} (not generic SaaS)
            2. Find acquirers who specifically target {sector} companies
            3. Calculate sector-specific valuation multiples
            4. Explain WHY each comparable/acquirer is relevant to {sector}
            
            Return a comprehensive JSON analysis:
            {{
                "comparables": [
                    {{
                        "company": "Name",
                        "ev_revenue_multiple": 5.2,
                        "revenue_growth": 25,
                        "market_cap": "$45B",
                        "relevance_score": 0.9,
                        "rationale": "Why this is a good comparable"
                    }}
                ],
                "acquirers": [
                    {{
                        "name": "Acquirer Name",
                        "likelihood": "high/medium/low",
                        "typical_multiple": 12.5,
                        "strategic_fit": "Explanation of fit",
                        "recent_similar_deals": ["Deal 1", "Deal 2"]
                    }}
                ],
                "valuation_insights": {{
                    "median_multiple": 8.5,
                    "growth_adjusted_multiple": 10.2,
                    "premium_for_sector": 1.2,
                    "consolidation_premium": 1.15
                }},
                "market_dynamics": {{
                    "consolidation_active": true,
                    "key_trends": ["trend1", "trend2"],
                    "valuation_drivers": ["driver1", "driver2"]
                }}
            }}
            """
            
            response = requests.post(
                self.claude_base_url,
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                claude_response = response.json()
                content = claude_response['content'][0]['text']
                
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    
                    # Calculate real median from PublicSaaS data
                    real_median = 0
                    if public_companies:
                        multiples = [c.get('ev_revenue', 0) for c in public_companies if c.get('ev_revenue', 0) > 0]
                        if multiples:
                            real_median = np.median(multiples)
                            sys.stderr.write(f"Calculated median EV/Revenue from {len(multiples)} public companies: {real_median:.1f}x\n")
                    
                    # Format the result with ALL data
                    formatted_result = {
                        "comparables": result.get('comparables', []),
                        "acquirers": result.get('acquirers', []),
                        "median_multiple": real_median if real_median > 0 else result.get('valuation_insights', {}).get('median_multiple', 25.0),
                        "growth_adjusted_multiple": result.get('valuation_insights', {}).get('growth_adjusted_multiple', 0),
                        "acquirer_insights": {
                            "most_likely": [a for a in result.get('acquirers', []) if a.get('likelihood') == 'high'],
                            "consolidation_active": result.get('market_dynamics', {}).get('consolidation_active', False),
                            "typical_premiums": result.get('valuation_insights', {})
                        },
                        "market_dynamics": result.get('market_dynamics', {}),
                        "all_public_companies": public_companies,  # Include ALL public SaaS data
                        "all_strategic_acquirers": strategic_acquirers  # Include ALL acquirer profiles
                    }
                    
                    return formatted_result
            
        except Exception as e:
            sys.stderr.write(f"Claude combined analysis error: {e}\n")
            import traceback
            traceback.print_exc(file=sys.stderr)
        
        return {
            "comparables": [],
            "acquirers": [],
            "median_multiple": 0,
            "acquirer_insights": {}
        }

    def _extract_subsector_transactions(self, market_research: Dict) -> Dict:
        """Extract and analyze actual transactions from the company's subsector"""
        transactions = {
            'exits': [],
            'multiples': [],
            'exit_values': [],
            'acquirers': {}
        }
        
        # FIRST - Use exit_comparables from Tavily search (these are REAL exits found)
        if 'exit_comparables' in market_research and market_research['exit_comparables']:
            sys.stderr.write(f"\n=== Found {len(market_research['exit_comparables'])} exit comparables from search ===\n")
            for exit in market_research['exit_comparables']:
                if exit.get('ev_revenue_multiple') and exit['ev_revenue_multiple'] > 0:
                    transactions['exits'].append({
                        'company': exit.get('company', exit.get('target', 'Unknown')),
                        'value': exit.get('deal_value', 0),
                        'acquirer': exit.get('acquirer', 'Unknown'),
                        'multiple': exit['ev_revenue_multiple'],
                        'source': exit.get('source', 'Tavily search')
                    })
                    transactions['multiples'].append(exit['ev_revenue_multiple'])
                    if exit.get('deal_value'):
                        transactions['exit_values'].append(exit['deal_value'])
                    
                    # Track acquirer
                    acquirer = exit.get('acquirer', 'Unknown')
                    if acquirer != 'Unknown':
                        transactions['acquirers'][acquirer] = transactions['acquirers'].get(acquirer, 0) + 1
                    
                    sys.stderr.write(f"  - {exit.get('company', 'Unknown')} acquired by {acquirer} at {exit['ev_revenue_multiple']:.1f}x revenue\n")
        
        # SECOND - Extract from M&A transactions if available
        elif 'ma_transactions' in market_research:
            for deal in market_research['ma_transactions']:
                if deal.get('deal_value'):
                    transactions['exits'].append({
                        'value': deal['deal_value'],
                        'acquirer': deal.get('acquirer', 'Unknown'),
                        'multiple': deal.get('revenue_multiple', 0)
                    })
                    transactions['exit_values'].append(deal['deal_value'])
                    if deal.get('revenue_multiple'):
                        transactions['multiples'].append(deal['revenue_multiple'])
                    
                    # Track acquirer frequency
                    acquirer = deal.get('acquirer', 'Unknown')
                    if acquirer != 'Unknown':
                        transactions['acquirers'][acquirer] = transactions['acquirers'].get(acquirer, 0) + 1
        
        # Extract from existing comparables
        if 'existing_comparables' in market_research:
            for comp in market_research['existing_comparables']:
                if comp.get('arr_multiple'):
                    transactions['multiples'].append(comp['arr_multiple'])
        
        # First fetch live SaaS index data
        live_saas_index = self._fetch_live_saas_index()
        
        # Check if we have PublicSaaS median EV multiple from market research
        public_median = market_research.get('median_ev_multiple', 0)
        public_companies = market_research.get('all_public_companies', [])
        
        # Prefer live data over market research
        if live_saas_index and live_saas_index.get('median_ev_revenue', 0) > 0:
            public_median = live_saas_index['median_ev_revenue']
            sys.stderr.write(f"Using live SaaS index median: {public_median:.1f}x\n")
        
        # Calculate statistics and track sources
        transactions['multiple_sources'] = []
        
        if transactions['multiples']:
            transactions['median_multiple'] = np.median(transactions['multiples'])
            transactions['p25_multiple'] = np.percentile(transactions['multiples'], 25)
            transactions['p75_multiple'] = np.percentile(transactions['multiples'], 75)
            transactions['multiple_sources'].append('Private M&A transactions from market research')
        elif public_median > 0:
            # Use PublicSaaS data if available
            sys.stderr.write(f"Using PublicSaaS median EV multiple: {public_median:.1f}x\n")
            transactions['median_multiple'] = public_median
            transactions['p25_multiple'] = public_median * 0.6  # Approximate quartiles
            transactions['p75_multiple'] = public_median * 1.5
            
            # Add source companies
            if public_companies:
                source_companies = [f"{c.get('company', 'Unknown')} ({c.get('ev_revenue', 0):.1f}x)" 
                                  for c in public_companies[:5] if c.get('ev_revenue', 0) > 0]
                transactions['multiple_sources'].append(f"PublicSaaS Index: {', '.join(source_companies)}")
            else:
                transactions['multiple_sources'].append('PublicSaaS Index median')
        else:
            # Default to SVB/Carta benchmark multiples (US market)
            sys.stderr.write("Warning: No multiples data found, using SVB/Carta benchmark\n")
            transactions['median_multiple'] = 25.0  # Series B median from benchmark
            transactions['p25_multiple'] = 15.0  # Series A median
            transactions['p75_multiple'] = 50.0  # Series B 25th percentile  
            transactions['multiple_sources'].append('SVB/Carta benchmark (Series B: 25x median)')
        
        # No DLOM needed - using private company benchmarks
        transactions['dlom_adjusted_median'] = transactions['median_multiple']  # No discount
        transactions['dlom_percentage'] = 0  # No DLOM for private-to-private comparisons
        transactions['ipev_compliant'] = True
        
        return transactions
    
    def _calculate_outlier_adjusted_probability(self, base_prob: float, outlier_score: float) -> float:
        """Adjust probability based on outlier score"""
        # Outlier score from -10 to +10
        # Positive outlier = higher probability of good outcomes
        # Negative outlier = higher probability of poor outcomes
        adjustment_factor = 1 + (outlier_score / 20)  # ±50% adjustment max
        return min(1.0, max(0.0, base_prob * adjustment_factor))
    
    def generate_499_scenarios(self, company_data: Dict, market_research: Dict) -> List[Dict]:
        """Generate 499 discrete PWERM scenarios based on actual subsector transactions"""
        scenarios = []
        
        # Extract REAL revenue from market research if not in company_data
        current_arr = company_data.get('current_arr_usd', 0)
        if current_arr == 0:
            # Try to extract from market intelligence
            intel = market_research.get('company_intelligence', {})
            if intel.get('revenue'):
                try:
                    rev_str = str(intel['revenue']).replace('$', '').replace('M', '').replace('million', '').strip()
                    current_arr = float(rev_str)
                except:
                    pass
            
            # If still no revenue, search through raw results
            if current_arr == 0:
                for result in market_research.get('raw_company_results', [])[:10]:
                    content = result.get('content', '')
                    import re
                    patterns = [
                        r'\$?([\d.]+)\s*(?:million|M)\s+(?:in\s+)?(?:annual\s+)?(?:revenue|ARR)',
                        r'(?:revenue|ARR)\s+of\s+\$?([\d.]+)\s*(?:million|M)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            current_arr = float(match.group(1))
                            break
                    if current_arr > 0:
                        break
        
        # Use real growth rate or extract from research
        growth_rate = company_data.get('revenue_growth_annual_pct', 0) / 100
        if growth_rate == 0:
            # Try to extract from market intelligence
            intel = market_research.get('company_intelligence', {})
            if intel.get('growth_rate'):
                try:
                    growth_str = str(intel['growth_rate']).replace('%', '').strip()
                    growth_rate = float(growth_str) / 100
                except:
                    growth_rate = 0.30  # Default only if nothing found
            else:
                growth_rate = 0.30
        
        # Extract real funding from research
        total_funding = company_data.get('total_invested_usd', 0)
        if total_funding == 0:
            # Try to extract from market intelligence
            intel = market_research.get('company_intelligence', {})
            if intel.get('total_funding'):
                try:
                    fund_str = str(intel['total_funding']).replace('$', '').replace('M', '').replace('million', '').strip()
                    total_funding = float(fund_str)
                except:
                    pass
            
            # Search through raw results for funding
            if total_funding == 0:
                for result in market_research.get('raw_company_results', [])[:10]:
                    content = result.get('content', '')
                    import re
                    patterns = [
                        r'raised\s+\$?([\d.]+)\s*(?:million|M)',
                        r'funding\s+of\s+\$?([\d.]+)\s*(?:million|M)',
                        r'total\s+funding.*?\$?([\d.]+)\s*(?:million|M)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            total_funding = float(match.group(1))
                            break
                    if total_funding > 0:
                        break
        
        # If still no data, use conservative estimates
        if current_arr == 0:
            current_arr = 5.0  # $5M ARR minimum
        if total_funding == 0:
            total_funding = current_arr * 2  # Assume 2x ARR in funding
        
        sector = company_data.get('sector', 'SaaS')
        company_name = company_data.get('name', '')
        
        # Detect geography from company data or name
        geography = 'US'  # Default
        eu_countries = ['Germany', 'France', 'Netherlands', 'Sweden', 'Denmark', 'Belgium', 'Estonia']
        uk_indicators = ['UK', 'United Kingdom', 'London', 'Ltd', 'plc']
        eu_indicators = eu_countries + ['GmbH', 'SAS', 'BV', 'AB', 'OÜ', 'Europe', 'EU']
        
        # Check company name and sector for geography indicators
        name_lower = company_name.lower()
        sector_lower = sector.lower()
        
        for indicator in uk_indicators:
            if indicator.lower() in name_lower or indicator.lower() in sector_lower:
                geography = 'UK'
                break
        
        for indicator in eu_indicators:
            if indicator.lower() in name_lower or indicator.lower() in sector_lower:
                geography = 'EU'
                break
        
        # Extract actual transaction data from the subsector
        subsector_transactions = self._extract_subsector_transactions(market_research)
        outlier_score = market_research.get('outlier_analysis', {}).get('outlier_score', 0)
        
        # Use SVB/Carta benchmark graduation rates adjusted by geography
        # US baseline graduation rates: Seed->A: 18%, A->B: 20%, B->C: 20%, C->D: 35%, D->E: 70%
        # European/UK companies have ~30-40% lower graduation rates
        
        geography_adjustment = {
            'US': 1.0,    # Baseline
            'UK': 0.7,    # 30% lower graduation rates
            'EU': 0.6     # 40% lower graduation rates
        }
        
        geo_factor = geography_adjustment.get(geography, 1.0)
        
        sys.stderr.write(f"\n=== Geography Adjustment ===\n")
        sys.stderr.write(f"Company: {company_name}\n")
        sys.stderr.write(f"Detected Geography: {geography}\n")
        sys.stderr.write(f"Graduation Rate Adjustment: {geo_factor:.1%}\n")
        
        # Adjusted probabilities based on geography
        base_probs = {
            "liquidation": 0.60 + (0.20 * (1 - geo_factor)),  # Higher failure rate for EU/UK
            "strategic": 0.05 * geo_factor,  # Lower acquisition probability
            "ipo": 0.01 * geo_factor * 0.5 if geography != 'US' else 0.01,  # Much lower IPO rate for EU/UK
            "mega_exit": 0.015 * geo_factor,  # Lower mega exit probability
            "good_exit": 0.20 * geo_factor,  # Lower graduation rate
            "other": 0.125  # Remaining probability
        }
        
        # Normalize probabilities
        total_prob = sum(base_probs.values())
        base_probs = {k: v/total_prob for k, v in base_probs.items()}
        
        # Apply outlier adjustments
        adjusted_probs = {}
        for outcome, prob in base_probs.items():
            if outcome == "liquidation":
                # Negative outliers have higher liquidation probability
                adjusted_probs[outcome] = self._calculate_outlier_adjusted_probability(prob, -outlier_score)
            else:
                # Positive outliers have higher success probability
                adjusted_probs[outcome] = self._calculate_outlier_adjusted_probability(prob, outlier_score)
        
        # Normalize probabilities to sum to 1
        total_prob = sum(adjusted_probs.values())
        for key in adjusted_probs:
            adjusted_probs[key] = adjusted_probs[key] / total_prob
        
        sys.stderr.write(f"\n=== PWERM Analysis Parameters ===\n")
        sys.stderr.write(f"Median Multiple: {subsector_transactions['median_multiple']:.1f}x\n")
        sys.stderr.write(f"Adjusted Multiple: {subsector_transactions['dlom_adjusted_median']:.1f}x\n")
        sys.stderr.write(f"Outlier Score: {outlier_score}\n")
        sys.stderr.write(f"\nAdjusted Probabilities:\n")
        for outcome, prob in adjusted_probs.items():
            sys.stderr.write(f"  {outcome}: {prob:.2%}\n")
        sys.stderr.write(f"==================================\n")
        
        # Generate scenarios based on actual transaction data
        scenario_id = 1
        
        # Liquidation scenarios (60% fail rate based on benchmark)
        liquidation_count = int(self.num_scenarios * adjusted_probs["liquidation"])
        for i in range(liquidation_count):
            liquidation_value = np.random.uniform(0, 0.5) * total_funding  # 0-50% recovery
            scenarios.append({
                'id': scenario_id,
                'type': 'liquidation',
                'probability': adjusted_probs["liquidation"] / liquidation_count,
                'exit_value': liquidation_value,
                'description': f'Liquidation scenario {i+1}',
                'graduation_stage': 'failed',
                'time_to_exit': np.random.uniform(1, 3)
            })
            scenario_id += 1
        
        # Strategic acquisition scenarios (5% from benchmark)
        strategic_count = int(self.num_scenarios * adjusted_probs["strategic"])
        
        for i in range(strategic_count):
            # Use REAL multiples from subsector_transactions if available
            if subsector_transactions.get('multiples') and len(subsector_transactions['multiples']) > 0:
                # Use actual distribution of multiples from real exits
                real_multiples = subsector_transactions['multiples']
                # Sample from real distribution with some variance
                base_multiple = np.random.choice(real_multiples)
                multiple = base_multiple * np.random.normal(1.0, 0.15)  # ±15% variance
                sys.stderr.write(f"Using REAL exit multiple: {base_multiple:.1f}x (adjusted: {multiple:.1f}x)\n")
            else:
                # Fall back to default multiples only if no real data
                valuation_discount = {'US': 1.0, 'UK': 0.8, 'EU': 0.7}.get(geography, 1.0)
                stage_multiples = {
                    'series_a': 15.0 * valuation_discount,
                    'series_b': 25.0 * valuation_discount,
                    'series_c': 15.0 * valuation_discount
                }
                stage = np.random.choice(['series_a', 'series_b', 'series_c'], p=[0.3, 0.5, 0.2])
                multiple = stage_multiples[stage] * np.random.normal(1.0, 0.2)
            
            # Project ARR based on growth
            years = np.random.uniform(3, 7)
            projected_arr = current_arr * (1 + growth_rate) ** years
            strategic_value = projected_arr * multiple
            
            # Select acquirer - use incumbents/competitors as likely acquirers
            potential_acquirers = []
            
            # From actual transactions
            if subsector_transactions['acquirers']:
                potential_acquirers.extend(list(subsector_transactions['acquirers'].keys())[:5])
            
            # Add sector-appropriate acquirers
            if 'SaaS' in sector or 'Software' in sector:
                potential_acquirers.extend(['Salesforce', 'Microsoft', 'Oracle', 'Adobe', 'SAP'])
            elif 'AI' in sector:
                potential_acquirers.extend(['Google', 'Microsoft', 'Amazon', 'Meta', 'Apple'])
            elif 'Fintech' in sector:
                potential_acquirers.extend(['Stripe', 'PayPal', 'Square', 'Visa', 'JPMorgan'])
            
            acquirer = np.random.choice(potential_acquirers[:10]) if potential_acquirers else "Strategic Buyer"
            
            scenarios.append({
                'id': scenario_id,
                'type': 'strategic_acquisition',
                'probability': adjusted_probs["strategic"] / strategic_count,
                'exit_value': strategic_value,
                'description': f'Acquired by {acquirer}',
                'acquirer': acquirer,
                'graduation_stage': 'series_c',
                'time_to_exit': years,
                'projected_arr': projected_arr,
                'revenue_multiple': multiple,
                'dlom_applied': False  # Using private company benchmarks
            })
            scenario_id += 1
        
        # IPO scenarios (1% probability based on benchmark)
        ipo_count = max(1, int(self.num_scenarios * adjusted_probs.get("ipo", 0.01)))
        for i in range(ipo_count):
            time_to_exit = np.random.uniform(10, 12)  # ~12 years median from benchmark
            projected_arr = current_arr * (1 + growth_rate) ** time_to_exit
            # Use higher multiples for IPO (public market premium)
            ipo_multiple = np.random.uniform(30, 60)
            ipo_value = projected_arr * ipo_multiple
            
            scenarios.append({
                'id': scenario_id,
                'type': 'ipo',
                'probability': adjusted_probs.get("ipo", 0.01) / ipo_count,
                'exit_value': ipo_value,
                'description': f'IPO scenario {i+1}',
                'graduation_stage': 'ipo',
                'time_to_exit': time_to_exit,
                'projected_arr': projected_arr,
                'revenue_multiple': ipo_multiple,
                'dlom_applied': False  # No DLOM for public market IPO
            })
            scenario_id += 1
        
        # Mega exit scenarios (1.5% at 3-10X last round from benchmark)
        mega_count = max(1, int(self.num_scenarios * adjusted_probs.get("mega_exit", 0.015)))
        for i in range(mega_count):
            time_to_exit = np.random.uniform(4, 7)
            projected_arr = current_arr * (1 + growth_rate) ** time_to_exit
            # 3-10X of last round valuation
            last_round_multiple = np.random.uniform(3, 10)
            # Assume Series B/C stage for mega exits
            base_multiple = 25.0  # Series B median
            mega_value = projected_arr * base_multiple * last_round_multiple
            
            scenarios.append({
                'id': scenario_id,
                'type': 'mega_exit',
                'probability': adjusted_probs.get("mega_exit", 0.015) / mega_count,
                'exit_value': mega_value,
                'description': f'Mega exit scenario {i+1}',
                'graduation_stage': 'mega_exit',
                'time_to_exit': time_to_exit,
                'projected_arr': projected_arr,
                'revenue_multiple': multiple
            })
            scenario_id += 1
        
        # Good exit scenarios (20% graduation rate)
        good_exit_count = int(self.num_scenarios * adjusted_probs.get("good_exit", 0.20))
        for i in range(good_exit_count):
            time_to_exit = np.random.uniform(2, 5)  # 2-2.4 years between rounds
            projected_arr = current_arr * (1 + growth_rate) ** time_to_exit
            # Use appropriate stage multiple
            multiple = np.random.choice([15.0, 25.0, 15.0])  # Series A, B, C multiples
            exit_value = projected_arr * multiple * np.random.uniform(0.8, 1.2)
            scenarios.append({
                'id': scenario_id,
                'type': 'good_exit',
                'probability': adjusted_probs.get("good_exit", 0.20) / good_exit_count,
                'exit_value': exit_value,
                'description': f'Successful graduation to next round {i+1}',
                'graduation_stage': 'next_round',
                'time_to_exit': time_to_exit
            })
            scenario_id += 1
        
        # Other scenarios (fill remaining slots)
        other_count = self.num_scenarios - len(scenarios)
        for i in range(other_count):
            other_value = np.random.uniform(5, 50) * current_arr  # Modest outcomes
            scenarios.append({
                'id': scenario_id,
                'type': 'other',
                'probability': adjusted_probs.get("other", 0.125) / other_count if other_count > 0 else 0,
                'exit_value': other_value,
                'description': f'Other scenario {i+1}',
                'graduation_stage': 'other',
                'time_to_exit': np.random.uniform(2, 6)
            })
            scenario_id += 1
        
        return scenarios
    
    def generate_exit_distribution_chart(self, scenarios: List[Dict]) -> str:
        """Generate exit distribution chart and return as base64 encoded image"""
        try:
            # Set modern style
            plt.style.use('seaborn-v0_8-darkgrid')
            
            # Create figure with modern styling
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})
            fig.patch.set_facecolor('#f8f9fa')
            
            # Extract exit values and types
            exit_values = [s['exit_value'] / 1000 for s in scenarios]  # Convert to billions
            exit_types = [s['type'] for s in scenarios]
            
            # Create bins from 0 to 10B with more granularity
            bins = np.linspace(0, 10, 100)  # 100 bins from 0 to 10B
            
            # Define modern colors for each exit type
            colors = {
                'liquidation': '#DC2626',      # Red
                'strategic_acquisition': '#3B82F6',  # Blue
                'ipo': '#10B981',              # Green
                'mega_exit': '#F59E0B',        # Amber
                'other': '#6B7280'             # Gray
            }
            
            # Top plot: Exit distribution by type
            for exit_type in ['liquidation', 'strategic_acquisition', 'ipo', 'mega_exit', 'other']:
                type_values = [v for v, t in zip(exit_values, exit_types) if t == exit_type]
                if type_values:
                    ax1.hist(type_values, bins=bins, alpha=0.85, label=exit_type.replace('_', ' ').title(), 
                            color=colors[exit_type], edgecolor='white', linewidth=0.5)
            
            # Modern styling for main plot
            ax1.set_xlim(0, 10)
            ax1.set_xlabel('Exit Value ($B)', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Number of Scenarios', fontsize=14, fontweight='bold')
            ax1.set_title('Exit Distribution Analysis', fontsize=20, fontweight='bold', pad=20)
            ax1.legend(loc='upper right', frameon=True, fancybox=True, shadow=True)
            ax1.grid(True, alpha=0.2, linestyle='--')
            ax1.set_facecolor('#ffffff')
            
            # Add vertical lines for key statistics
            expected_value = np.average(exit_values, weights=[s['probability'] for s in scenarios])
            median_value = np.median(exit_values)
            
            ax1.axvline(expected_value, color='#DC2626', linestyle='--', linewidth=3, alpha=0.8)
            ax1.axvline(median_value, color='#F59E0B', linestyle='--', linewidth=3, alpha=0.8)
            
            # Add text labels for statistics
            ax1.text(expected_value + 0.1, ax1.get_ylim()[1] * 0.9, 
                    f'Expected: ${expected_value:.2f}B', 
                    fontsize=12, fontweight='bold', color='#DC2626')
            ax1.text(median_value + 0.1, ax1.get_ylim()[1] * 0.8, 
                    f'Median: ${median_value:.2f}B', 
                    fontsize=12, fontweight='bold', color='#F59E0B')
            
            # Bottom plot: Probability by exit type
            exit_type_probs = {}
            for exit_type in ['liquidation', 'strategic_acquisition', 'ipo', 'mega_exit', 'other']:
                exit_type_probs[exit_type] = sum(s['probability'] for s in scenarios if s['type'] == exit_type)
            
            types = [t.replace('_', ' ').title() for t in exit_type_probs.keys()]
            probs = list(exit_type_probs.values())
            bars = ax2.bar(types, probs, color=[colors[t] for t in exit_type_probs.keys()], 
                          edgecolor='white', linewidth=1, alpha=0.85)
            
            # Modern styling for bottom plot
            ax2.set_ylabel('Total Probability', fontsize=14, fontweight='bold')
            ax2.set_title('Exit Type Probabilities', fontsize=16, fontweight='bold', pad=10)
            ax2.set_ylim(0, max(probs) * 1.2)
            ax2.set_facecolor('#ffffff')
            ax2.grid(True, alpha=0.2, axis='y', linestyle='--')
            
            # Add value labels on bars
            for bar, prob in zip(bars, probs):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                        f'{prob*100:.1f}%', ha='center', va='bottom', 
                        fontsize=12, fontweight='bold')
            
            # Remove x-axis ticks for cleaner look
            ax2.tick_params(axis='x', labelsize=12)
            ax2.tick_params(axis='y', labelsize=12)
            
            # Add subtle shadow effect
            for spine in ax1.spines.values():
                spine.set_edgecolor('#E5E7EB')
                spine.set_linewidth(1)
            for spine in ax2.spines.values():
                spine.set_edgecolor('#E5E7EB')
                spine.set_linewidth(1)
            
            plt.tight_layout()
            
            # Save to base64
            import io
            import base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=200, bbox_inches='tight', 
                       facecolor='#f8f9fa', edgecolor='none')
            buffer.seek(0)
            chart_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            plt.close()
            
            return chart_base64
            
        except Exception as e:
            sys.stderr.write(f"Error generating exit distribution chart: {e}\n")
            return ""

    def run_pwerm_analysis(self, company_data: Dict, assumptions: Dict, fund_config: Dict = None) -> Dict:
        """Run complete PWERM analysis with automatic categorization and market analysis"""
        
        # Step 1: Check if sector is already provided, otherwise categorize
        if 'sector' in company_data and company_data['sector']:
            sector = company_data['sector']
            # Extract subsector if it's in the format "SaaS-HR Tech"
            if '-' in sector:
                parts = sector.split('-', 1)
                main_sector = parts[0]
                subsector = parts[1] if len(parts) > 1 else main_sector
            else:
                # If just "SaaS" is provided, default to a more specific subsector
                if sector.upper() == 'SAAS':
                    main_sector = 'SaaS'
                    subsector = 'Enterprise SaaS'  # Default to enterprise SaaS
                else:
                    main_sector = sector
                    subsector = sector
            
            categorization = {
                'sector': main_sector,
                'subsector': subsector,
                'confidence': 'high',
                'reasoning': 'Sector provided by user'
            }
        else:
            # Automatically categorize company using Claude
            categorization = self.categorize_company_with_claude(company_data['name'])
            sector = categorization['sector']
            subsector = categorization['subsector']
        
        # Update company data with categorization
        company_data['sector'] = sector
        company_data['subsector'] = subsector
        company_data['categorization'] = categorization
        
        # Add funding data source if available
        if company_data.get('total_invested_usd'):
            company_data['funding_source'] = 'Supabase database'
        elif company_data.get('funding'):
            company_data['funding_source'] = 'User input'
        else:
            company_data['funding_source'] = 'Not provided'
        
        # Step 2: Analyze market landscape with timeout handling
        try:
            sys.stderr.write("Analyzing market landscape...\n")
            # Try to get full analysis with shorter timeout
            market_landscape = self.analyze_market_landscape(company_data['name'], sector, subsector)
            self._market_landscape_data = market_landscape
        except Exception as e:
            sys.stderr.write(f"Market landscape timeout/error: {e}\n")
            # Fallback to basic landscape
            market_landscape = {
                'incumbents': [],
                'competitors': [],
                'submarket': {'name': subsector, 'description': f'{sector} market segment'},
                'fragmentation': {'level': 'medium', 'explanation': 'Analysis in progress'},
                'market_size': 'Analyzing...',
                'sam': 'Analyzing...',
                'som': 'Analyzing...',
                'growth_rate': 'Analyzing...',
                'tailwinds': [],
                'headwinds': [],
                'moat': {'strength': 'medium', 'factors': []}
            }
            self._market_landscape_data = market_landscape
        
        # Step 3: Fetch additional market research
        market_research = self.fetch_market_research(company_data['name'], sector)
        
        # Check if sector was corrected based on research
        if market_research.get('detected_sector'):
            sys.stderr.write(f"Sector corrected from '{sector}' to '{market_research['detected_sector']}'\n")
            sector = market_research['detected_sector']
            subsector = market_research['detected_sector']
            # Update company data with corrected sector
            company_data['sector'] = sector
            company_data['subsector'] = subsector
            # Update categorization
            categorization['sector'] = sector
            categorization['subsector'] = subsector
        
        # Populate market landscape with actual data from research
        if market_research.get('competitors'):
            market_landscape['competitors'] = market_research['competitors'][:10]
            
        # Extract actual incumbent companies (large established firms) from search results
        incumbents_list = []
        competitors_list = market_research.get('competitors', [])[:10]
        
        # Parse search results to find large established companies (incumbents)
        # Look through all search results for Fortune 500, public companies, market leaders
        if market_research.get('raw_company_results'):
            for result in market_research.get('raw_company_results', []):
                content = str(result.get('content', '')).lower()
                title = str(result.get('title', '')).lower()
                
                # Look for mentions of large companies in the content
                # Common patterns: Fortune 500, public companies, market cap > $1B, enterprise, etc.
                if any(term in content or term in title for term in 
                       ['fortune 500', 'fortune 1000', 'market leader', 'dominant player', 
                        'billion market cap', 'public company', 'nasdaq', 'nyse', 's&p 500',
                        'enterprise', 'incumbent']):
                    
                    # Try to extract company names from the content
                    # Look for patterns like "Microsoft", "Oracle", "Salesforce", etc.
                    import re
                    # Pattern to find capitalized company names
                    company_pattern = r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b'
                    potential_companies = re.findall(company_pattern, result.get('content', ''))
                    
                    for company in potential_companies:
                        # Filter out common words and keep likely company names
                        if len(company) > 3 and company not in ['The', 'This', 'That', 'These', 'Those', 
                                                                  'Inc', 'Corp', 'LLC', 'Company', 'Fortune']:
                            # Check if it's mentioned as a large company
                            context = content[max(0, content.find(company.lower())-100):
                                             min(len(content), content.find(company.lower())+100)]
                            if any(indicator in context for indicator in 
                                   ['billion', 'market leader', 'dominant', 'largest', 'fortune', 
                                    'public', 'enterprise', 'incumbent']):
                                if company not in [inc.get('name', '') for inc in incumbents_list]:
                                    incumbents_list.append({
                                        'name': company,
                                        'type': 'incumbent',
                                        'source': 'market_research'
                                    })
        
        # Also check if any competitors are actually large incumbents
        for comp in competitors_list:
            if isinstance(comp, dict):
                # Check indicators that this is a large established company
                name = comp.get('name', '')
                description = str(comp.get('description', '')).lower()
                
                # Indicators of incumbent status
                is_incumbent = (
                    comp.get('type') in ['public', 'enterprise', 'established', 'incumbent'] or
                    comp.get('market_cap') and ('billion' in str(comp.get('market_cap')) or 
                                                float(str(comp.get('market_cap', '0').replace('$', '').replace('B', '').replace('M', '').replace(',', '') or '0')) > 1000) or
                    any(term in description for term in ['fortune', 'public company', 'nasdaq', 'nyse', 
                                                         'market leader', 'billion', 'enterprise'])
                )
                
                if is_incumbent and name not in [inc.get('name', '') for inc in incumbents_list]:
                    incumbents_list.append({
                        'name': name,
                        'type': 'incumbent',
                        'market_cap': comp.get('market_cap', ''),
                        'description': comp.get('description', '')
                    })
        
        # Separate incumbents from competitors
        # Incumbents = large established firms
        # Competitors = other companies competing in the space (including startups)
        market_landscape['incumbents'] = incumbents_list[:6]  # Top 6 large firms
        market_landscape['competitors'] = [
            comp for comp in competitors_list 
            if not any(inc['name'] == (comp.get('name', comp) if isinstance(comp, dict) else comp) 
                      for inc in incumbents_list)
        ][:10]  # Top 10 competitors excluding incumbents
        
        # Keep acquirers separate - they're potential buyers, not incumbents
        if market_research.get('data_driven_acquirers'):
            market_landscape['potential_acquirers'] = [
                {'name': acq['name'], 'type': acq.get('type', 'strategic')} 
                for acq in market_research.get('data_driven_acquirers', [])[:10]
            ]
        
        # Extract TAM/SAM/SOM from search results if available
        if market_research.get('company_intelligence'):
            intel = market_research['company_intelligence']
            if not market_landscape.get('market_size') or market_landscape['market_size'] == 'Analyzing...':
                market_landscape['market_size'] = intel.get('market_size', '$1B+')
        
        # Add M&A transactions
        if market_research.get('exit_comparables'):
            market_landscape['recent_transactions'] = market_research['exit_comparables'][:5]
        
        # Ensure all key fields are present in market_landscape
        market_landscape.setdefault('moats', [])
        market_landscape.setdefault('tailwinds', [])
        market_landscape.setdefault('headwinds', [])
        market_landscape.setdefault('barriers_to_entry', [])
        
        market_research['market_landscape'] = market_landscape
        
        # Keep all market research data - no deletions!
        # We want comprehensive results, not reduced data
        
        # Step 4: Determine company stage based on funding data from DB or search
        stage_analysis = self._determine_company_stage(company_data, market_research)
        
        # Step 4b: Quick outlier analysis using Claude Haiku
        outlier_analysis = self.quick_outlier_assessment(company_data['name'], company_data, market_research)
        if outlier_analysis:
            outlier_analysis['stage'] = stage_analysis
            
        # Step 4c: Calculate comprehensive investment score
        investment_score = self.calculate_investment_score(company_data, market_research, outlier_analysis)
        
        # Step 5: Generate 499 scenarios
        scenarios = self.generate_499_scenarios(company_data, market_research)
        
        # Step 6: Calculate summary statistics
        sys.stderr.write(f"\nGenerated {len(scenarios)} scenarios\n")
        
        if not scenarios:
            sys.stderr.write("ERROR: No scenarios generated!\n")
            expected_exit_value = 0
            median_exit_value = 0
        else:
            exit_values = [s['exit_value'] for s in scenarios]
            probabilities = [s['probability'] for s in scenarios]
            sys.stderr.write(f"Exit values range: ${min(exit_values):.1f}M - ${max(exit_values):.1f}M\n")
            sys.stderr.write(f"Probability sum: {sum(probabilities):.4f}\n")
            
            if sum(probabilities) > 0:
                expected_exit_value = np.average(exit_values, weights=probabilities)
                median_exit_value = np.median(exit_values)
                sys.stderr.write(f"Expected exit value: ${expected_exit_value:.1f}M\n")
                sys.stderr.write(f"Median exit value: ${median_exit_value:.1f}M\n")
            else:
                sys.stderr.write("ERROR: Total probability is 0!\n")
                expected_exit_value = 0
                median_exit_value = 0
        
        # Get valuation sources
        valuation_sources = []
        subsector_transactions = self._extract_subsector_transactions(market_research)
        if subsector_transactions.get('multiple_sources'):
            valuation_sources.extend(subsector_transactions['multiple_sources'])
        
        # Calculate scenario distribution statistics
        scenario_distribution = {}
        if scenarios:
            exit_values_array = np.array([s['exit_value'] for s in scenarios])
            probabilities_array = np.array([s['probability'] for s in scenarios])
            
            # Calculate percentiles
            percentiles = [10, 25, 50, 75, 90, 95, 99]
            scenario_distribution = {
                'percentiles': {
                    f'p{p}': float(np.percentile(exit_values_array, p))
                    for p in percentiles
                },
                'mean': float(np.mean(exit_values_array)),
                'std_dev': float(np.std(exit_values_array)),
                'min': float(np.min(exit_values_array)),
                'max': float(np.max(exit_values_array)),
                'skewness': float(np.sum(((exit_values_array - np.mean(exit_values_array)) / np.std(exit_values_array)) ** 3) / len(exit_values_array)),
                'scenario_types': {
                    'bankruptcy': len([s for s in scenarios if s['type'] == 'bankruptcy']),
                    'zombie': len([s for s in scenarios if s['type'] == 'zombie']),
                    'modest_exit': len([s for s in scenarios if s['type'] == 'modest_exit']),
                    'good_exit': len([s for s in scenarios if s['type'] == 'good_exit']),
                    'great_exit': len([s for s in scenarios if s['type'] == 'great_exit']),
                    'mega_exit': len([s for s in scenarios if s['type'] == 'mega_exit']),
                    'outlier_mega': len([s for s in scenarios if s.get('type') == 'outlier_mega' or (s['type'] == 'mega_exit' and s['exit_value'] > 10000)])
                }
            }
        
        summary = {
            'expected_exit_value': float(expected_exit_value),
            'median_exit_value': float(median_exit_value),
            'total_scenarios': len(scenarios),
            'success_probability': sum(s['probability'] for s in scenarios if s['exit_value'] > 10),
            'mega_exit_probability': sum(s['probability'] for s in scenarios if s['type'] == 'mega_exit'),
            'scenario_distribution': scenario_distribution,
            'valuation_methodology': {
                'median_multiple_used': subsector_transactions.get('median_multiple', 25.0),
                'dlom_discount': subsector_transactions.get('dlom_percentage', 0),  # No DLOM for private benchmarks
                'adjusted_multiple': subsector_transactions.get('dlom_adjusted_median', 7.0),
                'sources': valuation_sources,
                'ipev_compliant': subsector_transactions.get('ipev_compliant', True),
                'methodology': 'SVB/Carta Private Company Benchmarks (IPEV-compliant)'
            }
        }
        
        # Step 7: Generate exit distribution chart (skip for now to reduce size)
        exit_distribution_chart = ""  # Temporarily disabled to reduce response size
        
        # Extract sources from market research
        sources = []
        if 'raw_company_results' in market_research:
            for result in market_research.get('raw_company_results', [])[:20]:  # Limit to top 20 sources
                if result.get('url') and result.get('title'):
                    sources.append({
                        'url': result['url'],
                        'title': result['title'],
                        'relevance_score': result.get('score', 0)
                    })
        
        # Return ALL scenarios and data
        
        return {
            'company_data': company_data,
            'categorization': categorization,
            'market_landscape': market_landscape,
            'market_research': market_research,
            'outlier_analysis': outlier_analysis,
            'investment_score': investment_score,  # Add investment score with citations
            'scenarios': scenarios,  # Return ALL 499 scenarios
            'summary': summary,
            'exit_distribution_chart': exit_distribution_chart,
            'analysis_timestamp': datetime.now().isoformat(),
            'sources': sources,  # Add source citations
            'fund_config': fund_config  # Include fund configuration
        }

def main():
    """Main function to run PWERM analysis"""
    
    import argparse
    parser = argparse.ArgumentParser(description='Run PWERM analysis')
    parser.add_argument('--input', help='Input JSON file path')
    args = parser.parse_args()
    
    # Read input from file or stdin
    try:
        if args.input and os.path.exists(args.input):
            with open(args.input, 'r') as f:
                input_data = json.load(f)
        else:
            raw_input = sys.stdin.read()
            sys.stderr.write(f"\n=== Raw input received ===\n")
            sys.stderr.write(f"Length: {len(raw_input)}\n")
            sys.stderr.write(f"First 500 chars: {raw_input[:500]}\n")
            sys.stderr.write(f"=========================\n")
            input_data = json.loads(raw_input)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(json.dumps({'error': f'Invalid input: {str(e)}'}))
        return
    
    # Extract parameters from the new structure
    company_data_input = input_data.get('company_data', {})
    assumptions = input_data.get('assumptions', {})
    fund_config = input_data.get('fund_config', {})
    
    sys.stderr.write(f"\n=== Parsed company_data ===\n")
    sys.stderr.write(f"{json.dumps(company_data_input, indent=2)}\n")
    sys.stderr.write(f"=========================\n")
    
    company_name = company_data_input.get('name', company_data_input.get('company_name', 'Unknown Company'))
    sys.stderr.write(f"\n=== Company name extraction ===\n")
    sys.stderr.write(f"Looking for 'name' in company_data: {company_data_input.get('name')}\n")
    sys.stderr.write(f"Looking for 'company_name' in company_data: {company_data_input.get('company_name')}\n")
    sys.stderr.write(f"Final company_name: {company_name}\n")
    sys.stderr.write(f"==============================\n")
    # Check if current_arr_usd is in dollars (large number) or millions (small number)
    current_arr_raw = company_data_input.get('current_arr_usd', 5000000)
    
    sys.stderr.write(f"Raw ARR input: {current_arr_raw}\n")
    
    # Simple logic: 
    # If > 1,000,000 then it's in dollars (divide by 1M)
    # If <= 1,000,000 then check if it makes sense as millions
    if current_arr_raw > 1000000:
        # It's in dollars, convert to millions
        current_arr = current_arr_raw / 1000000
        sys.stderr.write(f"ARR converted from ${current_arr_raw:,.0f} to ${current_arr:.1f}M\n")
    else:
        # Assume it's already in millions (e.g., 142 = $142M)
        current_arr = current_arr_raw
        sys.stderr.write(f"ARR interpreted as ${current_arr:.1f}M (input was {current_arr_raw})\n")
    
    # Sanity check - warn if suspiciously small
    if current_arr < 0.5:
        sys.stderr.write(f"WARNING: Very small ARR after conversion: ${current_arr}M - this may be incorrect!\n")
    
    growth_rate = company_data_input.get('revenue_growth_annual_pct', 30) / 100  # Convert percentage to decimal
    sys.stderr.write(f"Growth rate: {growth_rate * 100:.0f}% annually\n")
    
    # Initialize analyzer
    tavily_api_key = os.getenv('TAVILY_API_KEY')
    claude_api_key = os.getenv('CLAUDE_API_KEY')
    
    sys.stderr.write(f"\n=== API Keys Status ===\n")
    sys.stderr.write(f"TAVILY_API_KEY from env: {'SET' if tavily_api_key else 'NOT SET'}\n")
    sys.stderr.write(f"CLAUDE_API_KEY from env: {'SET' if claude_api_key else 'NOT SET'}\n")
    
    analyzer = PWERMAnalyzer(tavily_api_key, claude_api_key)
    
    # Sector correction mapping for known misclassifications
    # This prevents AI from misclassifying based on superficial keyword matches
    SECTOR_CORRECTIONS = {
        # Defense & Aerospace (often misclassified as generic tech)
        'shield ai': 'Defense-Autonomous Systems',
        'anduril': 'Defense-Autonomous Systems', 
        'palantir': 'Defense-Data Analytics',
        'rebellion defense': 'Defense-AI Software',
        'epirus': 'Defense-Directed Energy',
        'hadrian': 'Defense-Manufacturing',
        'vannevar labs': 'Defense-Software',
        'skydio': 'Defense-Drones',
        'aerovironment': 'Defense-Drones',
        'hermeus': 'Defense-Hypersonics',
        'boom supersonic': 'Aerospace-Commercial',
        'saildrone': 'Defense-Maritime Autonomous',
        'austal': 'Defense-Shipbuilding',
        'general atomics': 'Defense-Drones',
        'kratos': 'Defense-Unmanned Systems',
        'aerojet rocketdyne': 'Defense-Propulsion',
        'l3harris': 'Defense-Communications',
        'saic': 'Defense-IT Services',
        'booz allen': 'Defense-Consulting',
        'leidos': 'Defense-IT Services',
        'caci': 'Defense-IT Services',
        'parsons': 'Defense-Infrastructure',
        
        # Space (often misclassified as aerospace or deep tech)
        'relativity space': 'Space-Launch',
        'firefly aerospace': 'Space-Launch',
        'astra': 'Space-Launch',
        'planet labs': 'Space-Earth Observation',
        'capella space': 'Space-Earth Observation',
        'spire global': 'Space-Data',
        'hawkeye 360': 'Space-RF Analytics',
        'umbra': 'Space-SAR Imaging',
        'd-orbit': 'Space-Logistics',
        'astroscale': 'Space-Servicing',
        'orbit fab': 'Space-Refueling',
        'axiom space': 'Space-Station',
        
        # Fintech (NOT crypto despite blockchain mentions)
        'stripe': 'B2B Fintech',
        'plaid': 'B2B Fintech',
        'brex': 'B2B Fintech',
        'ramp': 'B2B Fintech',
        'mercury': 'B2B Fintech',
        'modern treasury': 'B2B Fintech',
        'lithic': 'B2B Fintech',
        'unit': 'B2B Fintech',
        'chime': 'B2C Fintech',
        'nubank': 'B2C Fintech',
        'revolut': 'B2C Fintech',
        'wise': 'B2C Fintech',
        
        # HR Tech (NOT crypto despite distributed workforce mentions)
        'deel': 'HR',
        'rippling': 'HR',
        'gusto': 'HR',
        'workday': 'HR',
        'remote': 'HR',
        'oyster': 'HR',
        'lattice': 'HR',
        'greenhouse': 'HR',
        
        # Healthcare (NOT crypto despite data security mentions)
        'abridge': 'Health',
        'cedar': 'Health',
        'devoted health': 'Health',
        'oscar health': 'Health',
        'carbon health': 'Health',
        'forward': 'Health',
        'ro': 'Health',
        'hims': 'Health',
        
        # AI/ML (NOT crypto despite distributed computing mentions)
        'openai': 'AI',
        'anthropic': 'AI',
        'cohere': 'AI',
        'hugging face': 'AI',
        'stability ai': 'AI',
        'adept': 'AI',
        'inflection ai': 'AI',
        'character.ai': 'AI',
        'midjourney': 'AI',
        'runway': 'AI',
        
        # Data Infrastructure (NOT crypto despite distributed systems)
        'databricks': 'Data Infrastructure',
        'snowflake': 'Data Infrastructure',
        'confluent': 'Data Infrastructure',
        'fivetran': 'Data Infrastructure',
        'dbt labs': 'Data Infrastructure',
        'airbyte': 'Data Infrastructure',
        'clickhouse': 'Data Infrastructure',
        
        # Dev Tools (NOT crypto despite security/encryption mentions)
        'datadog': 'Dev Tool',
        'mongodb': 'Dev Tool',
        'vercel': 'Dev Tool',
        'netlify': 'Dev Tool',
        'hashicorp': 'Dev Tool',
        'gitlab': 'Dev Tool',
        'jetbrains': 'Dev Tool',
        'docker': 'Dev Tool',
        
        # Cybersecurity (NOT crypto despite cryptography mentions)
        'crowdstrike': 'Cyber',
        'sentinel one': 'Cyber',
        'palo alto networks': 'Cyber',
        'okta': 'Cyber',
        'zscaler': 'Cyber',
        'wiz': 'Cyber',
        'snyk': 'Cyber',
        'lacework': 'Cyber',
    }
    
    # Get the original sector
    original_sector = company_data_input.get('sector', '')
    
    # Only apply sector corrections for known companies, not heuristics
    company_lower = company_name.lower()
    corrected_sector = original_sector
    
    # Only correct if the company is explicitly in our known list
    for company_key, correct_sector in SECTOR_CORRECTIONS.items():
        if company_key == company_lower:  # Exact match only
            corrected_sector = correct_sector
            sys.stderr.write(f"SECTOR CORRECTION: '{company_name}' is a known {correct_sector} company (was: {original_sector})\n")
            break
    
    # If user provided a specific sector, trust it unless we have exact company match
    # Don't apply heuristic corrections that might be wrong
    if corrected_sector == original_sector and original_sector:
        sys.stderr.write(f"Using user-provided sector: {original_sector} for {company_name}\n")
    
    try:
        # Prepare company data with corrected sector
        company_data = {
            'name': company_name,
            'revenue': current_arr,
            'growth_rate': growth_rate,
            'sector': corrected_sector,  # Use corrected sector
            'funding': 10.0,  # Default
            'data_confidence': 'medium'
        }
        
        # Run analysis with fund configuration
        results = analyzer.run_pwerm_analysis(company_data, assumptions, fund_config)
        
        # Return the complete results structure
        print(json.dumps(results, indent=2))
        
    except Exception as e:
        import traceback
        print(json.dumps({
            'error': f'Analysis failed: {str(e)}',
            'traceback': traceback.format_exc()
        }))

if __name__ == "__main__":
    main() 