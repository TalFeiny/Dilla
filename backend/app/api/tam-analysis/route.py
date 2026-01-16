"""
TAM Analysis API Endpoint

Provides comprehensive market definition and TAM/SAM/SOM analysis
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging

from app.services.intelligent_gap_filler import IntelligentGapFiller
from app.services.tavily_service import tavily_service
from app.core.dependencies import get_intelligent_gap_filler

logger = logging.getLogger(__name__)

router = APIRouter()

class TAMAnalysisRequest(BaseModel):
    """Request model for TAM analysis"""
    company_name: str
    sector: Optional[str] = None
    business_model: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = None
    team_size: Optional[int] = None
    revenue: Optional[float] = None
    competitors: Optional[List[str]] = None
    target_customer: Optional[str] = None
    use_search: bool = True
    search_queries: Optional[List[str]] = None

class TAMAnalysisResponse(BaseModel):
    """Response model for TAM analysis"""
    company_name: str
    market_definition: str
    tam_value: Optional[float]
    sam_value: Optional[float]
    som_value: Optional[float]
    calculation_method: str
    confidence: float
    year: int
    growth_rate: Optional[float]
    sources: List[Dict[str, Any]]
    assumptions: List[str]
    market_segments: List[str]
    customer_segments: List[str]
    competitive_landscape: List[str]
    searchable_terms: List[str]
    tam_search_queries: List[str]
    geographic_scope: str
    search_content_used: bool
    search_results_count: int

@router.post("/analyze", response_model=TAMAnalysisResponse)
async def analyze_tam(
    request: TAMAnalysisRequest,
    gap_filler: IntelligentGapFiller = Depends(get_intelligent_gap_filler)
):
    """
    Analyze TAM/SAM/SOM for a company
    
    Args:
        request: Company data and analysis preferences
        
    Returns:
        Comprehensive market analysis including TAM/SAM/SOM calculations
    """
    try:
        # Prepare company data
        company_data = {
            'company_name': request.company_name,
            'sector': request.sector or 'Unknown',
            'business_model': request.business_model or 'Unknown',
            'description': request.description or '',
            'stage': request.stage or 'Seed',
            'team_size': request.team_size or 10,
            'revenue': request.revenue,
            'competitors': request.competitors or [],
            'target_customer': request.target_customer or 'businesses'
        }
        
        search_content = None
        search_results_count = 0
        
        # Perform search if requested
        if request.use_search:
            try:
                # Use provided queries or generate them
                queries = request.search_queries or []
                if not queries:
                    # Generate search queries from company data
                    queries = gap_filler._generate_tam_search_queries(company_data)
                
                # Perform searches
                all_search_results = []
                for query in queries[:2]:  # Limit to 2 queries
                    try:
                        results = await tavily_service.search(query, max_results=3)
                        all_search_results.extend(results)
                    except Exception as e:
                        logger.warning(f"Search failed for query '{query}': {e}")
                        continue
                
                # Combine search results
                if all_search_results:
                    search_content = "\n\n".join([
                        f"[Title] {result.get('title', '')}\n[Content] {result.get('content', '')}"
                        for result in all_search_results
                    ])
                    search_results_count = len(all_search_results)
                    logger.info(f"Combined {search_results_count} search results for TAM analysis")
                
            except Exception as e:
                logger.warning(f"Search failed: {e}")
                search_content = None
        
        # Perform TAM analysis
        market_analysis = await gap_filler.extract_market_definition(company_data, search_content)
        
        # Format response
        response = TAMAnalysisResponse(
            company_name=request.company_name,
            market_definition=market_analysis.get('market_definition', ''),
            tam_value=market_analysis.get('tam_value'),
            sam_value=market_analysis.get('sam_value'),
            som_value=market_analysis.get('som_value'),
            calculation_method=market_analysis.get('calculation_method', 'Unknown'),
            confidence=market_analysis.get('confidence', 0.0),
            year=market_analysis.get('year', 2024),
            growth_rate=market_analysis.get('growth_rate'),
            sources=market_analysis.get('sources', []),
            assumptions=market_analysis.get('assumptions', []),
            market_segments=market_analysis.get('market_segments', []),
            customer_segments=market_analysis.get('customer_segments', []),
            competitive_landscape=market_analysis.get('competitive_landscape', []),
            searchable_terms=market_analysis.get('searchable_terms', []),
            tam_search_queries=market_analysis.get('tam_search_queries', []),
            geographic_scope=market_analysis.get('geographic_scope', 'Global'),
            search_content_used=search_content is not None,
            search_results_count=search_results_count
        )
        
        logger.info(f"TAM analysis completed for {request.company_name}: TAM=${response.tam_value:,.0f}")
        
        return response
        
    except Exception as e:
        logger.error(f"TAM analysis failed for {request.company_name}: {e}")
        raise HTTPException(status_code=500, detail=f"TAM analysis failed: {str(e)}")

@router.post("/search-terms")
async def generate_search_terms(
    request: TAMAnalysisRequest,
    gap_filler: IntelligentGapFiller = Depends(get_intelligent_gap_filler)
):
    """
    Generate searchable terms and queries for TAM research
    
    Args:
        request: Company data
        
    Returns:
        Searchable terms and optimized queries
    """
    try:
        company_data = {
            'company_name': request.company_name,
            'sector': request.sector or 'Unknown',
            'business_model': request.business_model or 'Unknown',
            'description': request.description or '',
            'stage': request.stage or 'Seed',
            'team_size': request.team_size or 10,
            'revenue': request.revenue,
            'competitors': request.competitors or [],
            'target_customer': request.target_customer or 'businesses'
        }
        
        searchable_terms = gap_filler._generate_searchable_terms(company_data)
        tam_search_queries = gap_filler._generate_tam_search_queries(company_data)
        
        return {
            'company_name': request.company_name,
            'searchable_terms': searchable_terms,
            'tam_search_queries': tam_search_queries,
            'total_terms': len(searchable_terms),
            'total_queries': len(tam_search_queries)
        }
        
    except Exception as e:
        logger.error(f"Search terms generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search terms generation failed: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "tam-analysis"}
