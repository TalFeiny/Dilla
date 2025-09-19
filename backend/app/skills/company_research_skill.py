"""
Company Research Skill - Uses Tavily + Firecrawl + Database
Gathers comprehensive company data from multiple sources
"""

from typing import Dict, Any, List
from app.core.base_skill import DataGatheringSkill, SkillCategory
import logging

logger = logging.getLogger(__name__)


class CompanyResearchSkill(DataGatheringSkill):
    """Comprehensive company research using multiple MCP tools"""
    
    def __init__(self, mcp_orchestrator=None):
        super().__init__(
            skill_id="company-research",
            config=None  # Use defaults
        )
        self.mcp_orchestrator = mcp_orchestrator
    
    @property
    def description(self) -> str:
        return "Gathers comprehensive company data using web search, scraping, and database queries"
    
    @property
    def required_inputs(self) -> List[str]:
        return ["company"]
    
    @property
    def output_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "basic_info": {
                    "type": "object", 
                    "properties": {
                        "description": {"type": "string"},
                        "website": {"type": "string"},
                        "founded": {"type": "string"},
                        "employees": {"type": "string"}
                    }
                },
                "financial_data": {
                    "type": "object",
                    "properties": {
                        "revenue": {"type": "string"},
                        "valuation": {"type": "string"},
                        "funding_total": {"type": "string"}
                    }
                },
                "recent_news": {"type": "array"},
                "sources": {"type": "array"}
            },
            "required": ["company", "basic_info"]
        }
    
    async def _execute_core(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute company research using MCP tools"""
        company = inputs['company'].strip('@')
        results = {
            "company": company,
            "basic_info": {},
            "financial_data": {},
            "recent_news": [],
            "sources": []
        }
        
        if not self.mcp_orchestrator:
            logger.error("MCP Orchestrator not available")
            return results
        
        try:
            # Step 1: Web search for basic company info
            search_result = await self.mcp_orchestrator.execute_tavily({
                "query": f"{company} company information website funding valuation",
                "search_depth": "advanced",
                "max_results": 5
            })
            
            if search_result.get('success'):
                search_data = search_result['data']
                results['sources'].extend([
                    {"type": "web_search", "query": f"{company} company information"}
                ])
                
                # Extract basic info from search results
                if 'results' in search_data:
                    for result in search_data['results'][:3]:
                        content = result.get('content', '')
                        results['recent_news'].append({
                            "title": result.get('title', ''),
                            "url": result.get('url', ''),
                            "snippet": content[:200] + "..." if len(content) > 200 else content
                        })
            
            # Step 2: Scrape company website for detailed info
            if search_result.get('success') and 'results' in search_result['data']:
                company_urls = []
                for result in search_result['data']['results']:
                    url = result.get('url', '')
                    if company.lower() in url.lower() or any(
                        domain in url for domain in ['.com', '.ai', '.io']
                    ):
                        company_urls.append(url)
                
                if company_urls:
                    scrape_result = await self.mcp_orchestrator.execute_firecrawl({
                        "url": company_urls[0],
                        "extractorOptions": {
                            "extractionSchema": {
                                "type": "object",
                                "properties": {
                                    "company_description": {"type": "string"},
                                    "product_description": {"type": "string"}, 
                                    "team_size": {"type": "string"},
                                    "founded_year": {"type": "string"}
                                }
                            }
                        }
                    })
                    
                    if scrape_result.get('success'):
                        extracted_data = scrape_result.get('data', {}).get('extract', {})
                        results['basic_info'].update({
                            "description": extracted_data.get('company_description', ''),
                            "website": company_urls[0],
                            "founded": extracted_data.get('founded_year', ''),
                            "product": extracted_data.get('product_description', '')
                        })
                        results['sources'].append({
                            "type": "website_scrape", 
                            "url": company_urls[0]
                        })
            
            # Step 3: Database lookup for financial data
            db_result = await self.mcp_orchestrator.execute_database({
                "query": f"SELECT * FROM companies WHERE name ILIKE '%{company}%' LIMIT 1",
                "type": "companies_lookup"
            })
            
            if db_result.get('success') and db_result.get('data'):
                db_data = db_result['data']
                if isinstance(db_data, list) and db_data:
                    company_record = db_data[0]
                    results['financial_data'].update({
                        "revenue": company_record.get('revenue', ''),
                        "valuation": company_record.get('valuation', ''),
                        "funding_total": company_record.get('funding_total', ''),
                        "employees": company_record.get('employees', '')
                    })
                    results['sources'].append({
                        "type": "database",
                        "table": "companies"
                    })
            
            # Step 4: Get recent funding news
            funding_search = await self.mcp_orchestrator.execute_tavily({
                "query": f"{company} funding round investment recent news",
                "search_depth": "basic",
                "max_results": 3
            })
            
            if funding_search.get('success'):
                funding_data = funding_search['data']
                if 'results' in funding_data:
                    for result in funding_data['results']:
                        results['recent_news'].append({
                            "title": result.get('title', ''),
                            "url": result.get('url', ''),
                            "snippet": result.get('content', '')[:150] + "...",
                            "type": "funding_news"
                        })
                
                results['sources'].append({
                    "type": "web_search",
                    "query": f"{company} funding news"
                })
            
            logger.info(f"Successfully researched company: {company}")
            return results
            
        except Exception as e:
            logger.error(f"Company research failed for {company}: {str(e)}")
            results['error'] = str(e)
            return results