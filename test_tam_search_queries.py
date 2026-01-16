#!/usr/bin/env python3
"""
TAM Search Query Testing & Analysis Script

This script tests real TAM search queries through Tavily API to understand:
1. What types of sources are being returned (analyst reports, news articles, PDFs, etc.)
2. What content structure we're getting (titles, snippets, full content, URLs)
3. How market size data appears in these results
4. Whether we're getting PDFs/reports that need special extraction

Based on the current implementation in:
- unified_mcp_orchestrator.py:770-806 (TAM query generation)
- intelligent_gap_filler.py:5351-5508 (TAM extraction logic)
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import aiohttp

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TAMSearchTester:
    """Test TAM search queries and analyze response patterns"""
    
    def __init__(self):
        # Try to get API key from backend settings
        try:
            from app.core.config import settings
            self.tavily_api_key = settings.TAVILY_API_KEY
        except ImportError:
            # Fallback to environment variable
            self.tavily_api_key = os.getenv('TAVILY_API_KEY')
        
        if not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY not found in settings or environment")
        
        self.session = None
        self.results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_tavily(self, query: str) -> Dict[str, Any]:
        """Execute Tavily search with same configuration as production"""
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": 5
        }
        
        logger.info(f"[TAVILY] Searching: {query[:100]}")
        
        try:
            async with self.session.post(url, json=payload, headers=headers) as response:
                logger.info(f"[TAVILY] Response status: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"[TAVILY] Response keys: {list(result.keys()) if result else 'None'}")
                    logger.info(f"[TAVILY] Results count: {len(result.get('results', [])) if result else 0}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Tavily search failed: {response.status}, Query: {query[:50]}, Error: {error_text[:200]}")
                    return {"results": []}
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return {"results": []}
    
    async def extract_tam_categories_from_description(self, description: str, what_they_do: str = "") -> List[str]:
        """Extract specific software market categories with more precise reasoning"""
        if not description and not what_they_do:
            return []
        
        combined = f"{description} {what_they_do}".strip()
        combined_lower = combined.lower()
        
        # More precise category mapping for better TAM targeting
        precise_categories = {
            # Healthcare specific
            "healthcare_ai": ["healthcare AI", "medical AI", "healthcare analytics"],
            "healthcare_workflow": ["healthcare workflow", "clinical workflow", "hospital operations"],
            
            # Collaboration specific  
            "collaboration_software": ["collaboration software", "team collaboration", "workplace collaboration"],
            "productivity_software": ["productivity software", "workplace productivity", "team productivity"],
            
            # Payments specific
            "payment_processing": ["payment processing", "payment infrastructure", "online payments"],
            "fintech_infrastructure": ["fintech infrastructure", "financial infrastructure", "payment APIs"],
            
            # AI specific
            "ai_platforms": ["AI platforms", "artificial intelligence platforms", "AI infrastructure"],
            "ai_search": ["AI search", "conversational search", "AI-powered search"],
            
            # Analytics specific
            "business_analytics": ["business analytics", "data analytics", "business intelligence"]
        }
        
        categories = []
        
        # Look for most specific matches first
        for category_key, category_terms in precise_categories.items():
            if any(term in combined_lower for term in category_terms):
                # Return the most specific category terms
                categories.extend(category_terms[:1])  # Take only the most specific term
                break
        
        # Fallback to broader categories if no specific match
        if not categories:
            broad_categories = {
                "healthcare": ["healthcare software", "medical technology"],
                "collaboration": ["collaboration software", "productivity tools"], 
                "payments": ["payment processing", "fintech"],
                "ai": ["artificial intelligence", "AI platforms"],
                "analytics": ["data analytics", "business intelligence"]
            }
            
            for key, values in broad_categories.items():
                if any(keyword in combined_lower for keyword in [key, *values]):
                    categories.extend(values[:1])  # Take only first broad category
                    break
        
        return categories[:2] if categories else []  # Max 2 categories for precision
    
    async def build_tam_queries(self, company_data: Dict[str, Any]) -> List[str]:
        """Build TAM search queries using same logic as production"""
        company = company_data['name']
        vertical = company_data.get('vertical', '')
        business_model = company_data.get('business_model', '')
        description = company_data.get('description', '')
        what_they_do = company_data.get('what_they_do', '')
        
        tam_search_queries = []
        
        # Determine company type
        is_vertical = vertical and 'horizontal' not in vertical.lower()
        is_horizontal = not is_vertical or 'horizontal' in vertical.lower()
        is_ai = any(keyword in (description + what_they_do).lower() 
                   for keyword in ['ai', 'artificial intelligence', 'machine learning', 'ML'])
        
        logger.info(f"[COMPANY_TYPE] {company}: vertical={is_vertical}, horizontal={is_horizontal}, ai={is_ai}")
        
        # 1. VERTICAL-SPECIFIC TAM (if vertical company) - PRIORITIZE ANALYSTS
        if is_vertical and vertical:
            tam_search_queries.append(f'"{vertical}" market size TAM 2024 2025 billion Gartner Forrester IDC McKinsey')
        
        # 2. HORIZONTAL TECHNOLOGY TAM (if horizontal company) - MORE PRECISE CATEGORIES
        if is_horizontal:
            # Extract software categories from description
            software_categories = await self.extract_tam_categories_from_description(
                description, what_they_do
            )
            
            # Build TAM searches for each extracted category - PRIORITIZE ANALYSTS
            for category_term in software_categories:
                tam_search_queries.append(f'"{category_term}" market size TAM 2024 2025 billion Gartner Forrester IDC McKinsey BCG')
                logger.info(f"[TAM_CATEGORY] Extracted category: {category_term}")
            
            # Fallback to business_model if no categories extracted
            if not software_categories and business_model and business_model not in ['Unknown', '', 'unknown']:
                tam_search_queries.append(f'"{business_model}" market size TAM 2024 2025 Gartner Forrester IDC McKinsey billion')
        
        # 3. LABOR REPLACEMENT TAM (if AI-first/AI SaaS) - MORE SPECIFIC
        if is_ai:
            # More specific labor replacement queries
            labor_queries = [
                f'"{company}" AI automation workforce replacement TAM',
                f'AI software engineer productivity market size',
                f'AI-powered workforce automation market TAM'
            ]
            tam_search_queries.extend(labor_queries[:1])  # Take first one
        
        # 4. Company-specific TAM (always) - MORE SPECIFIC
        tam_search_queries.append(f'{company} market opportunity TAM addressable market size')
        
        # 5. Analyst reports (always) - PRIORITIZE TOP ANALYSTS
        tam_search_queries.append(f'"{business_model or vertical}" market research report Gartner Forrester IDC McKinsey BCG Bain')
        
        return tam_search_queries
    
    def extract_tam_data(self, result: Dict[str, Any], query: str, company_context: str = "") -> Dict[str, Any]:
        """Extract core TAM data: market size, CAGR, and source URL - define the RIGHT market"""
        # Prioritize snippets over content for more focused extraction
        snippet = result.get('snippet', '')
        content = result.get('content', '')
        title = result.get('title', '')
        
        # Combine snippets + title first, fallback to content if no snippet
        search_text = f"{snippet} {title}".strip() if snippet else f"{content} {title}".strip()
        url = result.get('url', '')
        
        # Extract market size numbers
        market_numbers = self.extract_market_numbers(search_text)
        
        # Extract CAGR
        cagr = self.extract_cagr(search_text)
        
        # Only return data if we found market numbers
        if not market_numbers:
            return None
        
        # Define the RIGHT market based on query context
        market_definition = self.define_market_from_query(query, company_context)
        
        # Select the most relevant market size for this specific market
        best_market_size = self.select_best_market_size(market_numbers, market_definition, search_text)
        
        return {
            'query': query,
            'url': url,
            'title': title,
            'snippet': snippet,
            'market_definition': market_definition,
            'market_size': best_market_size,
            'all_market_numbers': market_numbers,  # All numbers found
            'cagr': cagr,
            'source_domain': self.extract_domain(url),
            'source_type': self.classify_source_type(result)
        }
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        if not url:
            return ''
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return ''
    
    def has_tam_keywords(self, text: str) -> bool:
        """Check if text contains TAM-related keywords"""
        tam_keywords = [
            'market size', 'TAM', 'total addressable market', 'market worth',
            'billion', 'trillion', 'market opportunity', 'addressable market',
            'market value', 'industry size', 'market forecast'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in tam_keywords)
    
    def find_tam_data_location(self, result: Dict[str, Any]) -> str:
        """Determine where TAM data appears (title, content, raw_content)"""
        title = result.get('title', '')
        content = result.get('content', '')
        raw_content = result.get('raw_content', '')
        
        if self.has_tam_keywords(title):
            return 'title'
        elif self.has_tam_keywords(content):
            return 'content'
        elif self.has_tam_keywords(raw_content):
            return 'raw_content'
        else:
            return 'none'
    
    def extract_market_numbers(self, text: str) -> List[Dict[str, Any]]:
        """Extract market size numbers from text"""
        import re
        
        # Patterns for market size numbers
        patterns = [
            r'\$(\d+(?:\.\d+)?)\s*(billion|B|trillion|T|million|M)',
            r'(\d+(?:\.\d+)?)\s*(billion|B|trillion|T|million|M)',
            r'market.*?(\$?\d+(?:\.\d+)?)\s*(billion|B|trillion|T|million|M)',
            r'TAM.*?(\$?\d+(?:\.\d+)?)\s*(billion|B|trillion|T|million|M)'
        ]
        
        numbers = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = float(match.group(1).replace('$', ''))
                unit = match.group(2).upper()
                
                # Convert to billions
                multiplier = {'B': 1, 'BILLION': 1, 'T': 1000, 'TRILLION': 1000, 'M': 0.001, 'MILLION': 0.001}
                value_billions = value * multiplier.get(unit, 1)
                
                numbers.append({
                    'value': value,
                    'unit': unit,
                    'value_billions': value_billions,
                    'context': match.group(0),
                    'position': match.start()
                })
        
        return numbers
    
    def extract_cagr(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract CAGR (Compound Annual Growth Rate) from text"""
        import re
        
        # Patterns for CAGR
        patterns = [
            r'CAGR.*?(\d+(?:\.\d+)?)\s*%',
            r'compound annual growth.*?(\d+(?:\.\d+)?)\s*%',
            r'annual growth.*?(\d+(?:\.\d+)?)\s*%',
            r'growth rate.*?(\d+(?:\.\d+)?)\s*%',
            r'(\d+(?:\.\d+)?)\s*%\s*CAGR',
            r'(\d+(?:\.\d+)?)\s*%\s*annual growth'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                cagr_value = float(match.group(1))
                return {
                    'value': cagr_value,
                    'context': match.group(0),
                    'position': match.start()
                }
        
        return None
    
    def classify_source_type(self, result: Dict[str, Any]) -> str:
        """Classify the type of source"""
        url = result.get('url', '').lower()
        title = result.get('title', '').lower()
        
        if any(domain in url for domain in ['gartner.com', 'forrester.com', 'idc.com', 'mckinsey.com']):
            return 'analyst_report'
        elif any(keyword in url for keyword in ['pdf', '.pdf']):
            return 'pdf_report'
        elif any(keyword in url for keyword in ['news', 'reuters', 'bloomberg', 'techcrunch']):
            return 'news_article'
        elif any(keyword in url for keyword in ['company', 'corp', 'inc']):
            return 'company_page'
        elif any(keyword in title for keyword in ['research', 'study', 'analysis']):
            return 'research_report'
        else:
            return 'other'
    
    def define_market_from_query(self, query: str, company_context: str = "") -> str:
        """Define the market based on query context"""
        query_lower = query.lower()
        
        if 'healthcare' in query_lower:
            return 'Healthcare Technology'
        elif 'collaboration' in query_lower:
            return 'Collaboration Software'
        elif 'payment' in query_lower:
            return 'Payment Processing'
        elif 'ai' in query_lower or 'artificial intelligence' in query_lower:
            return 'Artificial Intelligence'
        elif 'search' in query_lower:
            return 'Search Technology'
        else:
            return 'Technology Market'
    
    def select_best_market_size(self, market_numbers: List[Dict[str, Any]], market_definition: str, search_text: str) -> Dict[str, Any]:
        """Select the most relevant market size from the found numbers"""
        if not market_numbers:
            return None
        
        # Prefer larger market sizes (more comprehensive)
        # Sort by value_billions descending
        sorted_numbers = sorted(market_numbers, key=lambda x: x['value_billions'], reverse=True)
        
        # Return the largest market size found
        return sorted_numbers[0]
    
    async def test_company_queries(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test all TAM queries for a single company and extract core market data"""
        company_name = company_data['name']
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing TAM queries for: {company_name}")
        logger.info(f"{'='*60}")
        
        # Build queries using same logic as production
        queries = await self.build_tam_queries(company_data)
        
        company_results = {
            'company': company_name,
            'company_data': company_data,
            'queries': queries,
            'tam_sources': [],  # Multiple sources with market data
            'summary': {
                'total_queries': len(queries),
                'successful_searches': 0,
                'sources_with_market_data': 0,
                'total_market_numbers': 0,
                'sources_with_cagr': 0
            }
        }
        
        for i, query in enumerate(queries, 1):
            logger.info(f"\n[QUERY {i}/{len(queries)}] {query}")
            
            # Execute search
            search_response = await self.search_tavily(query)
            results = search_response.get('results', []) if search_response else []
            
            if not results:
                logger.warning(f"No results for query: {query}")
                continue
            
            company_results['summary']['successful_searches'] += 1
            
            # Extract TAM data from each result
            for result in results:
                tam_data = self.extract_tam_data(result, query)
                if tam_data:
                    company_results['tam_sources'].append(tam_data)
                    company_results['summary']['sources_with_market_data'] += 1
                    company_results['summary']['total_market_numbers'] += len(tam_data['all_market_numbers'])
                    
                    if tam_data['cagr']:
                        company_results['summary']['sources_with_cagr'] += 1
                    
                    # Log the extracted data
                    market_size = tam_data['market_size']
                    cagr_info = f", CAGR: {tam_data['cagr']['value']}%" if tam_data['cagr'] else ""
                    logger.info(f"    ✓ Market: ${market_size['value_billions']:.1f}B ({market_size['unit']}){cagr_info}")
                    logger.info(f"      Source: {tam_data['source_domain']} ({tam_data['source_type']})")
                    logger.info(f"      URL: {tam_data['url']}")
        
        return company_results
    

async def main():
    """Main testing function"""
    
    # Test companies from the plan
    test_companies = [
        {
            'name': 'Gradient Labs',
            'vertical': 'Healthcare',
            'business_model': 'Healthcare AI',
            'description': 'AI-powered healthcare analytics platform',
            'what_they_do': 'provides machine learning tools for medical diagnosis and treatment optimization'
        },
        {
            'name': 'Fyxer',
            'vertical': 'Healthcare',
            'business_model': 'Healthcare workflow',
            'description': 'Healthcare workflow automation platform',
            'what_they_do': 'streamlines hospital operations and patient care workflows'
        },
        {
            'name': 'Notion',
            'vertical': 'Horizontal',
            'business_model': 'Collaboration software',
            'description': 'All-in-one workspace for notes, docs, and collaboration',
            'what_they_do': 'provides productivity and collaboration tools for teams'
        },
        {
            'name': 'Stripe',
            'vertical': 'Horizontal',
            'business_model': 'Payments infrastructure',
            'description': 'Online payment processing platform',
            'what_they_do': 'enables businesses to accept payments online'
        },
        {
            'name': 'Anthropic',
            'vertical': 'Horizontal',
            'business_model': 'AI research',
            'description': 'AI safety research company',
            'what_they_do': 'develops safe and beneficial artificial intelligence systems'
        },
        {
            'name': 'Perplexity',
            'vertical': 'Horizontal',
            'business_model': 'AI search',
            'description': 'AI-powered search engine',
            'what_they_do': 'provides conversational search with AI-generated answers'
        }
    ]
    
    logger.info("Starting TAM Search Query Testing")
    logger.info(f"Testing {len(test_companies)} companies")
    
    async with TAMSearchTester() as tester:
        all_results = []
        
        for company_data in test_companies:
            try:
                result = await tester.test_company_queries(company_data)
                all_results.append(result)
            except Exception as e:
                logger.error(f"Error testing {company_data['name']}: {e}")
                continue
        
        # Print market data summary
        print("\n" + "="*60)
        print("TAM MARKET DATA EXTRACTION SUMMARY")
        print("="*60)
        
        total_sources = sum(len(r['tam_sources']) for r in all_results)
        total_cagr_sources = sum(r['summary']['sources_with_cagr'] for r in all_results)
        
        print(f"Companies tested: {len(all_results)}")
        print(f"Total market data sources: {total_sources}")
        print(f"Sources with CAGR data: {total_cagr_sources}")
        print()
        
        # Show market data for each company
        for result in all_results:
            company = result['company']
            sources = result['tam_sources']
            
            print(f"\n{company}:")
            if sources:
                for i, source in enumerate(sources, 1):
                    market_size = source['market_size']
                    cagr_info = f" (CAGR: {source['cagr']['value']}%)" if source['cagr'] else ""
                    print(f"  {i}. ${market_size['value_billions']:.1f}B {market_size['unit']}{cagr_info}")
                    print(f"     Source: {source['source_domain']} ({source['source_type']})")
                    print(f"     URL: {source['url']}")
            else:
                print("  No market data found")
        
        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
