"""
Full Scale Analyst API Endpoints
Unified interface for spreadsheet and deck agents to access all financial capabilities
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.services.full_scale_analyst import (
    get_analyst,
    AnalystQuery,
    analyze_for_spreadsheet,
    analyze_for_deck,
    quick_financial_analysis
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyst")


# ==================== REQUEST MODELS ====================

class SpreadsheetRequest(BaseModel):
    """Request from spreadsheet agent"""
    formula: str = Field(..., description="Excel formula or function to execute")
    context: Dict[str, Any] = Field(default_factory=dict, description="Cell values and context")
    return_format: str = Field(default="value", description="value, detailed, or formatted")


class DeckRequest(BaseModel):
    """Request from deck agent"""
    slide_type: str = Field(..., description="Type of slide content needed")
    company_data: Dict[str, Any] = Field(..., description="Company information")
    style: str = Field(default="professional", description="Content style")


class QuickAnalysisRequest(BaseModel):
    """Natural language analysis request"""
    question: str = Field(..., description="Natural language question")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Supporting data")
    output_format: str = Field(default="summary", description="summary, detailed, or raw")


class ComprehensiveAnalysisRequest(BaseModel):
    """Full analysis request with all options"""
    query_type: str = Field(..., description="Type of analysis")
    context: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    output_format: str = Field(default="detailed")
    include_visualizations: bool = Field(default=False)
    include_recommendations: bool = Field(default=True)


class BatchAnalysisRequest(BaseModel):
    """Multiple analyses in one request"""
    analyses: List[Dict[str, Any]] = Field(..., description="List of analysis requests")
    aggregate_results: bool = Field(default=False)


# ==================== SPREADSHEET ENDPOINTS ====================

@router.post("/spreadsheet/formula")
async def execute_spreadsheet_formula(request: SpreadsheetRequest):
    """
    Execute Excel-like formula with full financial capabilities
    
    Examples:
    - Basic: "=SUM(A1:A10)"
    - Financial: "=NPV(0.1, A1:A10)"
    - VC: "=OWNERSHIP(1000000, 10000000)"
    - Fund: "=FUND_RETURN()"
    """
    try:
        result = analyze_for_spreadsheet(request.formula, request.context)
        
        if request.return_format == "detailed":
            return {
                "status": "success",
                "formula": request.formula,
                "result": result,
                "type": type(result).__name__,
                "context_used": bool(request.context)
            }
        elif request.return_format == "formatted":
            # Format numbers nicely
            if isinstance(result, (int, float)):
                if result > 1_000_000:
                    formatted = f"${result/1_000_000:.2f}M"
                elif result > 1_000:
                    formatted = f"${result/1_000:.2f}K"
                else:
                    formatted = f"{result:.2f}"
            else:
                formatted = str(result)
            
            return {
                "status": "success",
                "value": result,
                "formatted": formatted
            }
        else:
            # Just return the value
            return {"value": result}
            
    except Exception as e:
        logger.error(f"Spreadsheet formula error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/spreadsheet/financial_model")
async def build_financial_model(data: Dict[str, Any]):
    """
    Build a complete financial model from inputs
    Returns a spreadsheet-ready model with all calculations
    """
    try:
        analyst = get_analyst()
        
        # Build comprehensive model
        model = {
            'revenue_projections': analyst.spreadsheet_function('PROJECTION', data.get('revenue'), data.get('growth_rate')),
            'dcf_valuation': analyst.spreadsheet_function('DCF', cash_flows=data.get('cash_flows')),
            'irr': analyst.spreadsheet_function('IRR', data.get('cash_flows')),
            'ownership_table': analyst.spreadsheet_function('OWNERSHIP', data.get('investment'), data.get('valuation'))
        }
        
        return {
            "status": "success",
            "model": model,
            "formulas_available": [
                "NPV", "IRR", "XIRR", "PMT", "PV", "FV",
                "OWNERSHIP", "FUND_RETURN", "POSITION_SIZE",
                "DCF", "COMPARABLES", "LBO_MODEL"
            ]
        }
        
    except Exception as e:
        logger.error(f"Financial model error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== DECK ENDPOINTS ====================

@router.post("/deck/slide_content")
async def generate_slide_content(request: DeckRequest):
    """
    Generate intelligent content for deck slides
    
    Slide types:
    - financials: Financial overview with metrics and projections
    - valuation: Multi-method valuation analysis
    - market_analysis: Market size and dynamics
    - investment_thesis: Investment rationale and returns
    - exit_scenarios: Exit analysis with multiples
    - portfolio_fit: How it fits in the portfolio
    """
    try:
        content = analyze_for_deck(request.slide_type, request.company_data)
        
        # Apply styling if requested
        if request.style == "concise":
            content = _make_concise(content)
        elif request.style == "detailed":
            content = _add_details(content)
        
        return {
            "status": "success",
            "slide_type": request.slide_type,
            "content": content,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Deck content error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deck/full_analysis")
async def generate_full_deck_analysis(company_data: Dict[str, Any]):
    """
    Generate complete analysis for an entire deck
    Returns content for all standard slides
    """
    try:
        analyst = get_analyst()
        
        slide_types = [
            'financials', 'valuation', 'market_analysis',
            'investment_thesis', 'exit_scenarios', 'portfolio_fit'
        ]
        
        deck_content = {}
        for slide_type in slide_types:
            deck_content[slide_type] = analyst.deck_content(slide_type, company_data)
        
        # Add executive summary
        deck_content['executive_summary'] = _generate_executive_summary(deck_content)
        
        return {
            "status": "success",
            "slides": deck_content,
            "total_slides": len(deck_content),
            "company": company_data.get('name', 'Unknown')
        }
        
    except Exception as e:
        logger.error(f"Full deck analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== NATURAL LANGUAGE ENDPOINTS ====================

@router.post("/quick")
async def quick_analysis(request: QuickAnalysisRequest):
    """
    Natural language interface for quick financial analysis
    
    Examples:
    - "What's the IRR of this investment?"
    - "How much should we invest in this opportunity?"
    - "Will this deal return our fund?"
    """
    try:
        result = quick_financial_analysis(request.question, request.data)
        
        if request.output_format == "raw":
            return result
        elif request.output_format == "detailed":
            return {
                "status": "success",
                "question": request.question,
                "analysis": result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Summary format
            return {
                "answer": result.get('answer'),
                "confidence": result.get('confidence', 0.8),
                "recommendations": result.get('recommendations', [])
            }
            
    except Exception as e:
        logger.error(f"Quick analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== COMPREHENSIVE ANALYSIS ENDPOINTS ====================

@router.post("/analyze")
async def comprehensive_analysis(request: ComprehensiveAnalysisRequest):
    """
    Full-featured analysis endpoint with all capabilities
    """
    try:
        analyst = get_analyst()
        
        query = AnalystQuery(
            query_type=request.query_type,
            context=request.context,
            parameters=request.parameters,
            output_format=request.output_format
        )
        
        insight = analyst.analyze(query)
        
        response = {
            "status": "success",
            "primary_answer": insight.primary_answer,
            "supporting_data": insight.supporting_data,
            "calculations": insight.calculations,
            "confidence_score": insight.confidence_score,
            "sources": insight.sources
        }
        
        if request.include_recommendations:
            response["recommendations"] = insight.recommendations
        
        if request.include_visualizations and insight.visualizations:
            response["visualizations"] = insight.visualizations
        
        return response
        
    except Exception as e:
        logger.error(f"Comprehensive analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def batch_analysis(request: BatchAnalysisRequest):
    """
    Execute multiple analyses in one request
    Useful for comprehensive reports
    """
    try:
        analyst = get_analyst()
        results = []
        
        for analysis_request in request.analyses:
            query = AnalystQuery(
                query_type=analysis_request.get('query_type', 'vc_analysis'),
                context=analysis_request.get('context', {}),
                parameters=analysis_request.get('parameters', {}),
                output_format=analysis_request.get('output_format', 'summary')
            )
            
            insight = analyst.analyze(query)
            results.append({
                'query_type': query.query_type,
                'result': insight.primary_answer,
                'confidence': insight.confidence_score
            })
        
        response = {
            "status": "success",
            "total_analyses": len(results),
            "results": results
        }
        
        if request.aggregate_results:
            response["aggregate"] = _aggregate_results(results)
        
        return response
        
    except Exception as e:
        logger.error(f"Batch analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SPECIALIZED ENDPOINTS ====================

@router.post("/fund/return_path")
async def analyze_fund_return_path(portfolio_data: Dict[str, Any]):
    """
    Analyze how current portfolio can return the fund
    """
    try:
        analyst = get_analyst()
        
        query = AnalystQuery(
            query_type='fund_return_path',
            context={'portfolio_data': portfolio_data},
            parameters={},
            output_format='detailed'
        )
        
        insight = analyst.analyze(query)
        
        return {
            "status": "success",
            "fund_analysis": insight.primary_answer,
            "recommendations": insight.recommendations,
            "confidence": insight.confidence_score
        }
        
    except Exception as e:
        logger.error(f"Fund return path error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position/sizing")
async def calculate_position_sizing(opportunities: List[Dict[str, Any]], 
                                   fund_size: float,
                                   strategy: str = "kelly_criterion"):
    """
    Calculate optimal position sizes for opportunities
    """
    try:
        analyst = get_analyst()
        
        query = AnalystQuery(
            query_type='position_sizing',
            context={'fund_size': fund_size},
            parameters={
                'opportunities': opportunities,
                'strategy': strategy,
                'total_capital': fund_size
            },
            output_format='detailed'
        )
        
        insight = analyst.analyze(query)
        
        return {
            "status": "success",
            "position_sizes": insight.primary_answer,
            "metrics": insight.supporting_data,
            "recommendations": insight.recommendations
        }
        
    except Exception as e:
        logger.error(f"Position sizing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/valuation/multi_method")
async def multi_method_valuation(company_data: Dict[str, Any]):
    """
    Value a company using multiple methods
    """
    try:
        analyst = get_analyst()
        
        # DCF Valuation
        dcf_query = AnalystQuery(
            query_type='dcf_valuation',
            context=company_data,
            parameters=company_data,
            output_format='summary'
        )
        dcf_result = analyst.analyze(dcf_query)
        
        # Comparables
        comps_query = AnalystQuery(
            query_type='comparables_valuation',
            context=company_data,
            parameters=company_data,
            output_format='summary'
        )
        comps_result = analyst.analyze(comps_query)
        
        # VC Method
        vc_query = AnalystQuery(
            query_type='vc_valuation',
            context=company_data,
            parameters=company_data,
            output_format='summary'
        )
        vc_result = analyst.analyze(vc_query)
        
        return {
            "status": "success",
            "valuations": {
                "dcf": dcf_result.primary_answer,
                "comparables": comps_result.primary_answer,
                "vc_method": vc_result.primary_answer
            },
            "weighted_average": _calculate_weighted_valuation([
                dcf_result.primary_answer,
                comps_result.primary_answer,
                vc_result.primary_answer
            ]),
            "confidence": min(
                dcf_result.confidence_score,
                comps_result.confidence_score,
                vc_result.confidence_score
            )
        }
        
    except Exception as e:
        logger.error(f"Multi-method valuation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CAPABILITIES ENDPOINT ====================

@router.get("/capabilities")
async def get_analyst_capabilities():
    """
    Get list of all available analyst capabilities
    """
    return {
        "status": "success",
        "capabilities": {
            "investment_analysis": [
                "vc_analysis", "pe_analysis", "credit_analysis", "ma_analysis"
            ],
            "fund_mathematics": [
                "fund_return_path", "portfolio_construction", "position_sizing"
            ],
            "ownership_returns": [
                "ownership_journey", "exit_scenarios", "waterfall"
            ],
            "financial_calculations": [
                "dcf_valuation", "lbo_model", "cap_table"
            ],
            "spreadsheet_functions": [
                "NPV", "IRR", "XIRR", "PMT", "PV", "FV",
                "OWNERSHIP", "FUND_RETURN", "POSITION_SIZE"
            ],
            "deck_content_types": [
                "financials", "valuation", "market_analysis",
                "investment_thesis", "exit_scenarios", "portfolio_fit"
            ]
        },
        "integration_points": {
            "spreadsheet_agent": "/api/analyst/spreadsheet/*",
            "deck_agent": "/api/analyst/deck/*",
            "natural_language": "/api/analyst/quick"
        }
    }


# ==================== HELPER FUNCTIONS ====================

def _make_concise(content: Dict) -> Dict:
    """Make content more concise"""
    # Simplify nested structures
    if 'details' in content:
        content.pop('details')
    if 'calculations' in content:
        content['calculations'] = content['calculations'][:3]  # Top 3 only
    return content


def _add_details(content: Dict) -> Dict:
    """Add more details to content"""
    content['detailed_analysis'] = True
    content['generated_at'] = datetime.now().isoformat()
    return content


def _generate_executive_summary(deck_content: Dict) -> Dict:
    """Generate executive summary from all slides"""
    return {
        'title': 'Executive Summary',
        'key_points': [
            f"Valuation: {deck_content.get('valuation', {}).get('summary', 'TBD')}",
            f"Market: {deck_content.get('market_analysis', {}).get('summary', 'TBD')}",
            f"Thesis: {deck_content.get('investment_thesis', {}).get('summary', 'TBD')}"
        ]
    }


def _aggregate_results(results: List[Dict]) -> Dict:
    """Aggregate multiple analysis results"""
    return {
        'total_analyses': len(results),
        'average_confidence': sum(r['confidence'] for r in results) / len(results),
        'query_types': list(set(r['query_type'] for r in results))
    }


def _calculate_weighted_valuation(valuations: List[Any]) -> float:
    """Calculate weighted average valuation"""
    # Extract numeric values
    values = []
    for val in valuations:
        if isinstance(val, dict):
            values.append(val.get('value', 0))
        elif isinstance(val, (int, float)):
            values.append(val)
    
    if values:
        return sum(values) / len(values)
    return 0