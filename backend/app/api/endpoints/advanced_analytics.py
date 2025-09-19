"""
Advanced Analytics API Endpoint
Bridges frontend institutional research capabilities with backend MCP orchestrator
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import asyncio

from app.services.mcp_orchestrator import MCPOrchestrator
from app.services.analytics_bridge import AnalyticsBridge
from app.core.database import supabase_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
mcp_orchestrator = MCPOrchestrator()
analytics_bridge = AnalyticsBridge()


class AnalyticsRequest(BaseModel):
    """Request model for advanced analytics"""
    company: str
    analysis_type: str = Field(
        default="full_research",
        description="Type of analysis: full_research, comps, valuation, pwerm, market, dd"
    )
    depth: str = Field(
        default="deep",
        description="Analysis depth: quick, standard, deep, exhaustive"
    )
    context: Optional[Dict[str, Any]] = None
    previous_analysis: Optional[Dict[str, Any]] = None
    mcp_coordination: Optional[Dict[str, Any]] = None
    output_format: Optional[str] = "json"


class AnalyticsResponse(BaseModel):
    """Response model for advanced analytics"""
    success: bool
    analysis_type: str
    depth: str
    execution_time: float
    confidence: float
    
    # Core outputs
    report: Optional[Dict[str, Any]] = None
    comparables: Optional[Dict[str, Any]] = None
    valuation: Optional[Dict[str, Any]] = None
    pwerm: Optional[Dict[str, Any]] = None
    market_analysis: Optional[Dict[str, Any]] = None
    due_diligence: Optional[Dict[str, Any]] = None
    
    # Integration data
    data_for_spreadsheet: Optional[Dict[str, Any]] = None
    slides_for_deck: Optional[Dict[str, Any]] = None
    markdown_for_docs: Optional[str] = None
    
    # MCP metadata
    mcp_metadata: Optional[Dict[str, Any]] = None
    data_sources: Optional[List[str]] = None
    
    # Errors
    error: Optional[str] = None


@router.post("/analyze", response_model=AnalyticsResponse)
async def perform_advanced_analytics(
    request: AnalyticsRequest,
    background_tasks: BackgroundTasks
):
    """
    Perform advanced institutional-grade analytics
    Integrates with MCP orchestrator for data gathering and tool coordination
    """
    start_time = datetime.now()
    
    try:
        logger.info(f"Starting advanced analytics for {request.company} - Type: {request.analysis_type}")
        
        # Step 1: Use MCP orchestrator to gather comprehensive data
        mcp_prompt = f"""
        Gather comprehensive data for {request.company}:
        1. Latest financial metrics and funding information
        2. Market position and competitive landscape
        3. Team and leadership information
        4. Product offerings and technology
        5. Customer base and traction metrics
        6. Recent news and developments
        """
        
        mcp_result = await mcp_orchestrator.process_prompt(
            prompt=mcp_prompt,
            context={
                "company": request.company,
                "analysis_type": request.analysis_type,
                "depth": request.depth
            },
            auto_decompose=True
        )
        
        # Step 2: Bridge to advanced analytics processing
        analytics_result = await analytics_bridge.process_analysis(
            company=request.company,
            analysis_type=request.analysis_type,
            depth=request.depth,
            mcp_data=mcp_result.get("synthesis", {}),
            context=request.context
        )
        
        # Step 3: Format results based on analysis type
        formatted_result = await format_analytics_result(
            analytics_result,
            request.analysis_type,
            request.output_format
        )
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Build response
        response = AnalyticsResponse(
            success=True,
            analysis_type=request.analysis_type,
            depth=request.depth,
            execution_time=execution_time,
            confidence=analytics_result.get("confidence", 85.0),
            **formatted_result,
            mcp_metadata={
                "tasks_executed": len(mcp_result.get("tasks", [])),
                "data_sources": mcp_result.get("sources", []),
                "tools_used": mcp_result.get("tools_used", [])
            },
            data_sources=analytics_result.get("data_sources", [])
        )
        
        # Store results in database for future reference
        background_tasks.add_task(
            store_analytics_result,
            request.company,
            request.analysis_type,
            response.dict()
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Advanced analytics error: {str(e)}")
        return AnalyticsResponse(
            success=False,
            analysis_type=request.analysis_type,
            depth=request.depth,
            execution_time=(datetime.now() - start_time).total_seconds(),
            confidence=0.0,
            error=str(e)
        )


@router.post("/compare")
async def perform_comparable_analysis(
    companies: List[str],
    target_company: str,
    metrics: Optional[List[str]] = None
):
    """
    Perform comparable company analysis
    """
    try:
        # Use MCP to gather data for all companies
        all_data = {}
        for company in companies + [target_company]:
            mcp_result = await mcp_orchestrator.process_prompt(
                prompt=f"Get financial metrics and business overview for {company}",
                context={"company": company},
                auto_decompose=True
            )
            all_data[company] = mcp_result.get("synthesis", {})
        
        # Perform comparative analysis
        comparison = await analytics_bridge.compare_companies(
            target=target_company,
            peers=companies,
            data=all_data,
            metrics=metrics
        )
        
        return {
            "success": True,
            "target": target_company,
            "peers": companies,
            "comparison": comparison
        }
        
    except Exception as e:
        logger.error(f"Comparable analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pwerm")
async def perform_pwerm_analysis(
    company: str,
    scenarios: Optional[int] = 100,
    include_monte_carlo: bool = True
):
    """
    Perform PWERM (Probability-Weighted Expected Return) analysis
    """
    try:
        # Gather comprehensive data
        mcp_result = await mcp_orchestrator.process_prompt(
            prompt=f"Get financial projections, market dynamics, and risk factors for {company}",
            context={"company": company, "analysis": "pwerm"},
            auto_decompose=True
        )
        
        # Run PWERM analysis
        pwerm_result = await analytics_bridge.run_pwerm(
            company=company,
            data=mcp_result.get("synthesis", {}),
            num_scenarios=scenarios,
            include_monte_carlo=include_monte_carlo
        )
        
        return {
            "success": True,
            "company": company,
            "scenarios_run": scenarios,
            "pwerm": pwerm_result
        }
        
    except Exception as e:
        logger.error(f"PWERM analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/valuation")
async def perform_valuation_analysis(
    company: str,
    methodologies: Optional[List[str]] = None
):
    """
    Perform comprehensive valuation analysis
    """
    if methodologies is None:
        methodologies = ["dcf", "multiples", "precedents"]
    
    try:
        # Gather valuation data
        mcp_result = await mcp_orchestrator.process_prompt(
            prompt=f"Get financial statements, comparables, and market data for {company} valuation",
            context={"company": company, "analysis": "valuation"},
            auto_decompose=True
        )
        
        # Run valuation models
        valuation = await analytics_bridge.calculate_valuation(
            company=company,
            data=mcp_result.get("synthesis", {}),
            methodologies=methodologies
        )
        
        return {
            "success": True,
            "company": company,
            "methodologies": methodologies,
            "valuation": valuation
        }
        
    except Exception as e:
        logger.error(f"Valuation analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{company}")
async def get_analytics_report(company: str):
    """
    Get stored analytics report for a company
    """
    try:
        # Fetch from database
        result = await supabase_service.get_analytics_report(company)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"No report found for {company}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-deck")
async def generate_investment_deck(
    company: str,
    deck_type: str = "pitch",
    include_analytics: bool = True
):
    """
    Generate investment deck with advanced analytics
    """
    try:
        # Run comprehensive analysis
        analytics = await perform_advanced_analytics(
            AnalyticsRequest(
                company=company,
                analysis_type="full_research",
                depth="deep"
            ),
            BackgroundTasks()
        )
        
        if not analytics.success:
            raise HTTPException(status_code=500, detail="Analytics failed")
        
        # Generate deck with analytics data
        deck = await analytics_bridge.generate_deck(
            company=company,
            deck_type=deck_type,
            analytics_data=analytics.dict() if include_analytics else None
        )
        
        return {
            "success": True,
            "company": company,
            "deck": deck,
            "analytics_included": include_analytics
        }
        
    except Exception as e:
        logger.error(f"Deck generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions

async def format_analytics_result(
    result: Dict[str, Any],
    analysis_type: str,
    output_format: str
) -> Dict[str, Any]:
    """Format analytics result based on type and format"""
    
    formatted = {}
    
    if analysis_type == "full_research":
        formatted["report"] = result
    elif analysis_type == "comps":
        formatted["comparables"] = result
    elif analysis_type == "valuation":
        formatted["valuation"] = result
    elif analysis_type == "pwerm":
        formatted["pwerm"] = result
    elif analysis_type == "market":
        formatted["market_analysis"] = result
    elif analysis_type == "dd":
        formatted["due_diligence"] = result
    
    # Add format-specific outputs
    if output_format == "spreadsheet":
        formatted["data_for_spreadsheet"] = convert_to_spreadsheet_format(result)
    elif output_format == "deck":
        formatted["slides_for_deck"] = convert_to_deck_format(result)
    elif output_format == "markdown":
        formatted["markdown_for_docs"] = convert_to_markdown(result)
    
    return formatted


def convert_to_spreadsheet_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert analytics data to spreadsheet format"""
    # Implementation for spreadsheet conversion
    return {
        "sheets": [],
        "formulas": [],
        "charts": []
    }


def convert_to_deck_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert analytics data to deck slide format"""
    # Implementation for deck conversion
    return {
        "slides": [],
        "theme": "professional",
        "charts": []
    }


def convert_to_markdown(data: Dict[str, Any]) -> str:
    """Convert analytics data to markdown documentation"""
    # Implementation for markdown conversion
    return "# Analytics Report\n\n..."


async def store_analytics_result(
    company: str,
    analysis_type: str,
    result: Dict[str, Any]
):
    """Store analytics result in database"""
    try:
        await supabase_service.store_analytics(
            company=company,
            analysis_type=analysis_type,
            result=result,
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Failed to store analytics result: {str(e)}")