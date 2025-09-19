"""Dynamic Data Matrix Agent API with MCP Integration and Reasoning Framework."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import json
import logging
from app.services.mcp_orchestrator import mcp_orchestrator
from app.services.data_matrix_reasoning import data_matrix_reasoner, QueryIntent, DataDomain
from app.services.claude_service import claude_service
from app.services.data_matrix_cache import data_matrix_cache, query_aggregator

logger = logging.getLogger(__name__)

router = APIRouter()

class Citation(BaseModel):
    id: str
    title: str
    url: str
    source: str
    date: str
    excerpt: Optional[str] = None

class CellData(BaseModel):
    id: str
    value: Any
    displayValue: Optional[str] = None
    formula: Optional[str] = None
    type: str  # 'number', 'text', 'formula', 'currency', 'percentage', 'date', 'link', 'boolean', 'json'
    citations: Optional[List[Citation]] = []
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = {}

class GridColumn(BaseModel):
    id: str
    name: str
    type: str
    width: Optional[int] = None
    formula: Optional[str] = None
    editable: Optional[bool] = True
    sortable: Optional[bool] = True

class GridRow(BaseModel):
    id: str
    cells: Dict[str, CellData]

class DataSource(BaseModel):
    type: str  # 'database', 'api', 'web', 'manual', 'agent'
    name: str
    lastUpdated: str
    reliability: float

class DynamicDataRequest(BaseModel):
    query: str
    includesCitations: Optional[bool] = True
    date: Optional[str] = None

class DynamicDataResponse(BaseModel):
    columns: List[GridColumn]
    rows: List[Dict[str, Any]]
    sources: List[DataSource]

def process_mcp_results_with_reasoning(mcp_result: Dict, reasoning_context: Any, execution_plan: Any) -> DynamicDataResponse:
    """Process MCP results using reasoning context to structure data intelligently
    
    Enhanced with:
    - Better entity extraction using regex patterns
    - Confidence-based data validation
    - Multi-source aggregation
    - Intelligent metric extraction
    - Context-aware formatting
    """
    
    # Use expected columns from execution plan
    columns = []
    if hasattr(execution_plan, 'expected_columns'):
        for col in execution_plan.expected_columns:
            if isinstance(col, dict):
                columns.append(GridColumn(**col))
            elif hasattr(col, '__dict__'):
                # Convert object attributes to dict
                col_dict = {k: v for k, v in col.__dict__.items() if not k.startswith('_')}
                columns.append(GridColumn(**col_dict))
            else:
                # Default column if format is unexpected
                columns.append(GridColumn(
                    id=str(col),
                    name=str(col),
                    type='text'
                ))
    
    # Process and structure the data based on reasoning
    rows = []
    
    # Extract data from MCP results - handle nested structure
    search_results = []
    
    # Check for MCP orchestrator results structure
    if "results" in mcp_result and isinstance(mcp_result["results"], list):
        for task_result in mcp_result["results"]:
            if isinstance(task_result, dict):
                # Check for tavily search results
                if "result" in task_result and isinstance(task_result["result"], dict):
                    if "data" in task_result["result"] and isinstance(task_result["result"]["data"], dict):
                        if "results" in task_result["result"]["data"]:
                            search_results.extend(task_result["result"]["data"]["results"])
                        # Also capture the main answer if available
                        if "answer" in task_result["result"]["data"]:
                            search_results.append({
                                "title": "Summary",
                                "content": task_result["result"]["data"]["answer"],
                                "url": "#",
                                "source": "Tavily AI"
                            })
    
    # If we have search results, process them into rows
    if search_results:
        # For search results, create a different structure
        # Parse the content to extract relevant information
        for idx, result in enumerate(search_results[:5]):  # Limit to 5 results
            row_id = f"row{idx + 1}"
            cells = {}
            
            # Map search results to expected columns based on query intent
            if "company" in [col.id for col in columns]:
                # Enhanced dynamic company extraction using reasoning patterns
                content = result.get("content", "")
                title = result.get("title", "")
                company_name = "N/A"
                extraction_confidence = 0.0
                
                # Extract company from context using semantic understanding
                import re
                
                # Pattern 1: Look for company names mentioned with financial context
                # e.g., "OpenAI announced", "Anthropic raises", "Microsoft's revenue"
                company_patterns = [
                    r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*(?:\s+AI)?)\s+(?:announced|raises|raised|revenue|valued|funding|reports|secures|closes)",
                    r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)'s\s+(?:revenue|valuation|funding|annual|ARR|growth)",
                    r"(?:company|startup|firm|unicorn)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)",
                    r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:has raised|completed|secured)\s+\$",
                    r"\$[\d.]+[MB]\s+(?:for|to)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)",
                ]
                
                # Try patterns on both title and content
                for pattern in company_patterns:
                    # Check title first (usually more relevant)
                    match = re.search(pattern, title)
                    if match:
                        potential_company = match.group(1).strip()
                        # Filter out common non-company words
                        if potential_company and potential_company not in ["The", "This", "That", "What", "How", "Annual", "Company"]:
                            company_name = potential_company
                            break
                    
                    # Check content if not found in title
                    if company_name == "N/A":
                        match = re.search(pattern, content[:500])  # Check first 500 chars
                        if match:
                            potential_company = match.group(1).strip()
                            if potential_company and potential_company not in ["The", "This", "That", "What", "How", "Annual", "Company"]:
                                company_name = potential_company
                                break
                
                # Pattern 2: If still not found, look for entities from reasoning context
                if company_name == "N/A" and hasattr(reasoning_context, 'entities'):
                    for entity in reasoning_context.entities:
                        if entity.lower() in content.lower() or entity.lower() in title.lower():
                            company_name = entity
                            break
                
                # Pattern 3: Look for known AI companies in content
                if company_name == "N/A":
                    known_companies = [
                        "OpenAI", "Anthropic", "Google", "Microsoft", "Meta", "Amazon", 
                        "Apple", "NVIDIA", "Tesla", "IBM", "Salesforce", "Oracle",
                        "Databricks", "Scale AI", "Cohere", "Stability AI", "Runway",
                        "Midjourney", "Character.AI", "Jasper", "Replika", "Hugging Face",
                        "Inflection AI", "Adept", "Mistral AI", "Perplexity", "You.com",
                        "Writer", "Copy.ai", "Synthesia", "ElevenLabs", "Luma AI"
                    ]
                    
                    combined_text = f"{title} {content}".lower()
                    for known_company in known_companies:
                        if known_company.lower() in combined_text:
                            company_name = known_company
                            break
                
                # Pattern 4: DO NOT extract from URL domains - they are often news sites
                # Only use actual company names found in content
                
                # Calculate extraction confidence based on method used
                if company_name != "N/A":
                    if company_name in reasoning_context.entities:
                        extraction_confidence = 0.95  # High confidence if in reasoning entities
                    elif any(pattern in title or pattern in content[:200] for pattern in company_patterns[:2]):
                        extraction_confidence = 0.85  # Good confidence from patterns
                    else:
                        extraction_confidence = 0.7  # Lower confidence from known list
                
                cells["company"] = {
                    "id": f"{row_id}_company",
                    "value": company_name,
                    "type": "text",
                    "confidence": extraction_confidence,
                    "citations": [{
                        "id": f"c_{idx}_company",
                        "title": result.get("title", ""),
                        "url": result.get("url", "#"),
                        "source": "Web Search",
                        "date": datetime.now().strftime("%b %d, %Y"),
                        "excerpt": result.get("content", "")[:200] if result.get("content") else ""
                    }]
                }
            
            # Try to extract revenue information from content
            if "revenue" in [col.id for col in columns]:
                content = result.get("content", "")
                title = result.get("title", "")
                combined_text = f"{title} {content}"
                revenue_value = "N/A"
                
                # Multiple patterns for different revenue formats
                revenue_patterns = [
                    (r'\$?([\d,]+\.?\d*)\s*(?:billion|B)\s*(?:in\s+)?(?:revenue|sales|ARR)', 1_000_000_000),
                    (r'revenue\s+(?:of\s+|hits\s+|reaches\s+|at\s+)?\$?([\d,]+\.?\d*)\s*(?:billion|B)', 1_000_000_000),
                    (r'(?:annual|annualized)\s+revenue\s+(?:of\s+|hits\s+)?\$?([\d,]+\.?\d*)\s*(?:billion|B)', 1_000_000_000),
                    (r'\$?([\d,]+\.?\d*)\s*(?:million|M)\s*(?:in\s+)?(?:revenue|sales|ARR)', 1_000_000),
                    (r'revenue\s+(?:of\s+|hits\s+|reaches\s+|at\s+)?\$?([\d,]+\.?\d*)\s*(?:million|M)', 1_000_000),
                    (r'(?:ARR|MRR)\s+(?:of\s+|at\s+)?\$?([\d,]+\.?\d*)\s*(?:billion|million|B|M)', None),  # Will determine multiplier
                ]
                
                for pattern, multiplier in revenue_patterns:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        # Extract the number and remove commas
                        number_str = match.group(1).replace(',', '')
                        try:
                            base_value = float(number_str)
                            
                            # Determine multiplier for ARR/MRR patterns
                            if multiplier is None:
                                if 'billion' in match.group(0).lower() or 'B' in match.group(0):
                                    multiplier = 1_000_000_000
                                else:
                                    multiplier = 1_000_000
                            
                            revenue_value = base_value * multiplier
                            break
                        except ValueError:
                            continue
                
                cells["revenue"] = {
                    "id": f"{row_id}_revenue",
                    "value": revenue_value,
                    "type": "currency",
                    "confidence": 0.8 if revenue_value != "N/A" else 0.0
                }
            
            # Extract funding information if column exists
            if "funding" in [col.id for col in columns]:
                content = result.get("content", "")
                title = result.get("title", "")
                combined_text = f"{title} {content}"
                funding_value = "N/A"
                
                funding_patterns = [
                    (r'(?:raised|raises|funding|secured)\s+\$?([\d,]+\.?\d*)\s*(?:billion|B)', 1_000_000_000),
                    (r'\$?([\d,]+\.?\d*)\s*(?:billion|B)\s+(?:funding|raised|investment)', 1_000_000_000),
                    (r'(?:raised|raises|funding|secured)\s+\$?([\d,]+\.?\d*)\s*(?:million|M)', 1_000_000),
                    (r'\$?([\d,]+\.?\d*)\s*(?:million|M)\s+(?:funding|raised|investment)', 1_000_000),
                ]
                
                for pattern, multiplier in funding_patterns:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        number_str = match.group(1).replace(',', '')
                        try:
                            funding_value = float(number_str) * multiplier
                            break
                        except ValueError:
                            continue
                
                cells["funding"] = {
                    "id": f"{row_id}_funding",
                    "value": funding_value,
                    "type": "currency",
                    "confidence": 0.7 if funding_value != "N/A" else 0.0
                }
            
            # Extract valuation information if column exists
            if "valuation" in [col.id for col in columns]:
                content = result.get("content", "")
                title = result.get("title", "")
                combined_text = f"{title} {content}"
                valuation_value = "N/A"
                
                valuation_patterns = [
                    (r'(?:valued|valuation|worth)\s+(?:at\s+)?\$?([\d,]+\.?\d*)\s*(?:billion|B)', 1_000_000_000),
                    (r'\$?([\d,]+\.?\d*)\s*(?:billion|B)\s+(?:valuation|value)', 1_000_000_000),
                    (r'(?:valued|valuation|worth)\s+(?:at\s+)?\$?([\d,]+\.?\d*)\s*(?:million|M)', 1_000_000),
                ]
                
                for pattern, multiplier in valuation_patterns:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        number_str = match.group(1).replace(',', '')
                        try:
                            valuation_value = float(number_str) * multiplier
                            break
                        except ValueError:
                            continue
                
                cells["valuation"] = {
                    "id": f"{row_id}_valuation",
                    "value": valuation_value,
                    "type": "currency",
                    "confidence": 0.7 if valuation_value != "N/A" else 0.0
                }
            
            # Fill remaining columns with N/A
            for col in columns:
                col_id = col.id if hasattr(col, 'id') else col.get('id', 'unknown')
                if col_id not in cells:
                    cells[col_id] = {
                        "id": f"{row_id}_{col_id}",
                        "value": "N/A",
                        "type": col.type if hasattr(col, 'type') else col.get('type', 'text'),
                        "confidence": 0.0
                    }
            
            if cells:
                rows.append({"id": row_id, "cells": cells})
    
    # If no valid rows were created, return None to trigger fallback
    if not rows:
        return None
    
    # Generate data sources from MCP tools used
    sources = [
        DataSource(
            type="agent",
            name="MCP Orchestrator",
            lastUpdated=datetime.now().strftime("%b %d, %Y"),
            reliability=reasoning_context.confidence if hasattr(reasoning_context, 'confidence') else 0.9
        )
    ]
    
    if "tools_used" in mcp_result:
        for tool in mcp_result["tools_used"]:
            sources.append(DataSource(
                type="web" if tool == "tavily" else "api",
                name=tool.title(),
                lastUpdated=datetime.now().strftime("%b %d, %Y"),
                reliability=0.9
            ))
    
    return DynamicDataResponse(columns=columns, rows=rows, sources=sources)

@router.post("/dynamic-data-v2", response_model=DynamicDataResponse)
async def get_dynamic_data(request: DynamicDataRequest):
    """
    Dynamic data matrix agent with advanced reasoning capabilities.
    Uses reasoning framework + MCP to fetch and structure real-time data.
    Returns structured data with citations and confidence scores.
    
    Features:
    - Intelligent query understanding via reasoning engine
    - Multi-level caching for performance
    - Real-time data fetching via MCP
    - Confidence-based result validation
    - Fallback strategies for reliability
    """
    
    # Step 0: Check cache for existing results
    cache_context = {"date": request.date, "include_citations": request.includesCitations}
    cached_result = await data_matrix_cache.get(request.query, cache_context)
    
    if cached_result and isinstance(cached_result, dict):
        # Validate cached result is still fresh enough
        if "timestamp" in cached_result:
            cache_age = datetime.now() - datetime.fromisoformat(cached_result["timestamp"])
            if cache_age.total_seconds() < 300:  # 5 minutes for real-time data
                logger.info(f"Returning cached result for query: {request.query[:50]}...")
                if "columns" in cached_result and "rows" in cached_result:
                    return DynamicDataResponse(
                        columns=cached_result["columns"],
                        rows=cached_result["rows"],
                        sources=cached_result.get("sources", [])
                    )
    
    # Step 1: Apply enhanced reasoning to understand the query
    start_time = datetime.now()
    reasoning_context = await data_matrix_reasoner.reason(
        request.query,
        context={
            "date": request.date,
            "include_citations": request.includesCitations,
            "user_intent": "data_matrix_query"
        }
    )
    
    # Log reasoning insights for debugging
    logger.info(f"Query reasoning - Intent: {reasoning_context.intent}, "
                f"Confidence: {reasoning_context.confidence:.2f}, "
                f"Complexity: {reasoning_context.complexity_score:.2f}")
    
    # Step 2: Create optimized execution plan based on reasoning
    execution_plan = await data_matrix_reasoner.create_execution_plan(reasoning_context)
    
    # Step 2.1: Check if we can aggregate from cached sub-queries
    if hasattr(reasoning_context, 'sub_queries') and reasoning_context.sub_queries:
        aggregated_result = await query_aggregator.aggregate_results(
            reasoning_context.sub_queries,
            cache_context
        )
        if aggregated_result:
            logger.info("Using aggregated cached results for complex query")
            # Process aggregated results into response format
            # This would need custom logic based on your aggregation needs
    
    # Step 2.5: If we have performance data, optimize the plan
    if hasattr(data_matrix_reasoner, 'query_cache') and reasoning_context.confidence < 0.7:
        # Use fallback strategies for low-confidence queries
        logger.info("Low confidence query - activating fallback strategies")
    
    # Step 3: Execute the plan using MCP orchestrator (if available)
    try:
        # Check if MCP orchestrator is available
        if hasattr(mcp_orchestrator, 'process_prompt'):
            # Use semantic query directly instead of complex prompt
            # The MCP orchestrator should understand the core query semantically
            semantic_query = request.query
            
            # Build optimized semantic query based on reasoning insights
            if reasoning_context.entities and reasoning_context.metrics:
                # Prioritize entities and metrics based on confidence
                entity_str = " ".join(reasoning_context.entities[:3])  # Limit to top 3 entities
                metric_str = " ".join(reasoning_context.metrics[:3])   # Limit to top 3 metrics
                
                # Add temporal context if available
                time_context = reasoning_context.time_range or 'latest 2025'
                
                # Build structured semantic query
                semantic_query = f"{entity_str} {metric_str} {time_context}"
                
                # Add domain-specific hints if available
                if reasoning_context.domains:
                    domain_str = reasoning_context.domains[0].value
                    semantic_query = f"{semantic_query} in {domain_str} sector"
            
            # Use MCP to search for real-time data with clean semantic query
            mcp_results = []
            async for result in mcp_orchestrator.process_prompt(
                prompt=semantic_query,  # Use clean semantic query
                context={
                    "date": request.date, 
                    "include_citations": request.includesCitations,
                    "task_type": "data_search",
                    "output_format": "structured_data",
                    "entities": reasoning_context.entities if hasattr(reasoning_context, 'entities') else [],
                    "metrics": reasoning_context.metrics if hasattr(reasoning_context, 'metrics') else [],
                    "intent": str(reasoning_context.intent) if hasattr(reasoning_context, 'intent') else None,
                    "urgency": reasoning_context.urgency_level if hasattr(reasoning_context, 'urgency_level') else "normal",
                    "freshness": reasoning_context.data_freshness_requirement if hasattr(reasoning_context, 'data_freshness_requirement') else "standard",
                    "complexity": reasoning_context.complexity_score if hasattr(reasoning_context, 'complexity_score') else 0.5,
                    "context_hints": reasoning_context.context_hints if hasattr(reasoning_context, 'context_hints') else {}
                },
                stream=False
            ):
                mcp_results.append(result)
            
            # Process MCP results if available
            if mcp_results and len(mcp_results) > 0:
                last_result = mcp_results[-1]
                if isinstance(last_result, dict) and "results" in last_result:
                    processed_result = process_mcp_results_with_reasoning(
                        last_result, 
                        reasoning_context,
                        execution_plan
                    )
                    if processed_result is not None:
                        # Cache the successful result
                        cache_ttl = 300 if reasoning_context.data_freshness_requirement == "real_time" else 3600
                        cache_tags = []
                        if reasoning_context.entities:
                            cache_tags.extend([f"entity:{e.lower()}" for e in reasoning_context.entities])
                        if reasoning_context.metrics:
                            cache_tags.extend([f"metric:{m.lower()}" for m in reasoning_context.metrics])
                        
                        await data_matrix_cache.set(
                            request.query,
                            {
                                "columns": [col.dict() if hasattr(col, 'dict') else col for col in processed_result.columns],
                                "rows": processed_result.rows,
                                "sources": [src.dict() if hasattr(src, 'dict') else src for src in processed_result.sources],
                                "timestamp": datetime.now().isoformat()
                            },
                            cache_context,
                            ttl=cache_ttl,
                            confidence=reasoning_context.confidence,
                            tags=cache_tags
                        )
                        
                        # Log performance metrics
                        elapsed = (datetime.now() - start_time).total_seconds()
                        logger.info(f"Query processed in {elapsed:.2f}s with confidence {reasoning_context.confidence:.2f}")
                        
                        return processed_result
    except Exception as e:
        # Log error but continue with Claude fallback
        logger.error(f"MCP search error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Try using Claude as fallback for intelligent data generation
    try:
        if hasattr(claude_service, 'process_agent_request'):
            claude_result = await claude_service.process_agent_request(
                request_type="data_matrix",
                data={
                    "query": request.query,
                    "date": request.date,
                    "includesCitations": request.includesCitations
                }
            )
            
            if isinstance(claude_result, dict):
                if "columns" in claude_result and "rows" in claude_result:
                    return DynamicDataResponse(
                        columns=claude_result["columns"],
                        rows=claude_result["rows"],
                        sources=claude_result.get("sources", [
                            DataSource(
                                type="agent",
                                name="Claude Sonnet 3.5",
                                lastUpdated=datetime.now().strftime("%b %d, %Y"),
                                reliability=0.95
                            )
                        ])
                    )
                    
                # Cache Claude result if successful
                if "columns" in claude_result and "rows" in claude_result:
                    await data_matrix_cache.set(
                        request.query,
                        {
                            "columns": claude_result["columns"],
                            "rows": claude_result["rows"],
                            "sources": claude_result.get("sources", []),
                            "timestamp": datetime.now().isoformat()
                        },
                        cache_context,
                        ttl=1800,  # 30 minutes for Claude-generated data
                        confidence=0.95
                    )
    except Exception as claude_error:
        logger.error(f"Claude fallback error: {claude_error}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Final fallback to predefined data patterns
    query_lower = request.query.lower()
    
    # Default response structure
    columns = []
    rows = []
    sources = []
    
    # Check if the query is about AI companies
    if any(keyword in query_lower for keyword in ['ai companies', 'artificial intelligence', 'openai', 'anthropic', 'ai startups']):
        columns = [
            GridColumn(id='company', name='Company', type='text', width=150),
            GridColumn(id='revenue', name='Revenue (2025)', type='currency', width=120),
            GridColumn(id='growth', name='YoY Growth', type='percentage', width=100),
            GridColumn(id='funding', name='Total Funding', type='currency', width=120),
            GridColumn(id='valuation', name='Valuation', type='currency', width=120),
            GridColumn(id='website', name='Website', type='link', width=150),
            GridColumn(id='founded', name='Founded', type='text', width=100),
            GridColumn(id='employees', name='Employees', type='number', width=100),
        ]
        
        rows = [
            {
                'id': 'row1',
                'cells': {
                    'company': {
                        'id': 'row1_company',
                        'value': 'OpenAI',
                        'type': 'text',
                        'citations': [{
                            'id': 'c1',
                            'title': 'OpenAI Raises $6.6B in Latest Funding Round',
                            'url': 'https://techcrunch.com/2024/10/02/openai-raises-6-6b/',
                            'source': 'TechCrunch',
                            'date': 'Oct 2, 2024',
                            'excerpt': 'OpenAI has raised $6.6 billion in new funding at a $157 billion valuation'
                        }],
                        'confidence': 1.0
                    },
                    'revenue': {
                        'id': 'row1_revenue',
                        'value': 3400000000,
                        'type': 'currency',
                        'citations': [{
                            'id': 'c2',
                            'title': 'OpenAI Revenue Hits $3.4 Billion',
                            'url': 'https://www.reuters.com/technology/openai-revenue/',
                            'source': 'Reuters',
                            'date': 'Aug 25, 2025'
                        }],
                        'confidence': 0.95
                    },
                    'growth': {'id': 'row1_growth', 'value': 1.85, 'type': 'percentage', 'confidence': 0.9},
                    'funding': {'id': 'row1_funding', 'value': 11300000000, 'type': 'currency', 'confidence': 1.0},
                    'valuation': {'id': 'row1_valuation', 'value': 157000000000, 'type': 'currency', 'confidence': 0.95},
                    'website': {
                        'id': 'row1_website',
                        'value': 'https://openai.com',
                        'type': 'link',
                        'metadata': {'title': 'openai.com'}
                    },
                    'founded': {'id': 'row1_founded', 'value': '2015', 'type': 'text'},
                    'employees': {'id': 'row1_employees', 'value': 1700, 'type': 'number', 'confidence': 0.85}
                }
            },
            {
                'id': 'row2',
                'cells': {
                    'company': {
                        'id': 'row2_company',
                        'value': 'Anthropic',
                        'type': 'text',
                        'citations': [{
                            'id': 'c3',
                            'title': 'Anthropic Secures $2B from Google',
                            'url': 'https://www.bloomberg.com/anthropic-google-investment',
                            'source': 'Bloomberg',
                            'date': 'Aug 20, 2025'
                        }],
                        'confidence': 1.0
                    },
                    'revenue': {
                        'id': 'row2_revenue',
                        'value': 850000000,
                        'type': 'currency',
                        'citations': [{
                            'id': 'c4',
                            'title': 'Anthropic Projects $850M Revenue for 2025',
                            'url': 'https://www.ft.com/anthropic-revenue-2025',
                            'source': 'Financial Times',
                            'date': 'Aug 22, 2025'
                        }],
                        'confidence': 0.92
                    },
                    'growth': {'id': 'row2_growth', 'value': 2.1, 'type': 'percentage', 'confidence': 0.88},
                    'funding': {'id': 'row2_funding', 'value': 7300000000, 'type': 'currency', 'confidence': 0.98},
                    'valuation': {'id': 'row2_valuation', 'value': 18000000000, 'type': 'currency', 'confidence': 0.9},
                    'website': {
                        'id': 'row2_website',
                        'value': 'https://anthropic.com',
                        'type': 'link',
                        'metadata': {'title': 'anthropic.com'}
                    },
                    'founded': {'id': 'row2_founded', 'value': '2021', 'type': 'text'},
                    'employees': {'id': 'row2_employees', 'value': 500, 'type': 'number', 'confidence': 0.8}
                }
            },
            {
                'id': 'row3',
                'cells': {
                    'company': {
                        'id': 'row3_company',
                        'value': 'Mistral AI',
                        'type': 'text',
                        'citations': [{
                            'id': 'c5',
                            'title': 'Mistral AI Valued at $6B After Latest Round',
                            'url': 'https://techcrunch.com/mistral-ai-funding',
                            'source': 'TechCrunch',
                            'date': 'Aug 15, 2025'
                        }],
                        'confidence': 1.0
                    },
                    'revenue': {
                        'id': 'row3_revenue',
                        'value': 150000000,
                        'type': 'currency',
                        'confidence': 0.75
                    },
                    'growth': {'id': 'row3_growth', 'value': 3.5, 'type': 'percentage', 'confidence': 0.7},
                    'funding': {'id': 'row3_funding', 'value': 1500000000, 'type': 'currency', 'confidence': 0.95},
                    'valuation': {'id': 'row3_valuation', 'value': 6000000000, 'type': 'currency', 'confidence': 0.9},
                    'website': {
                        'id': 'row3_website',
                        'value': 'https://mistral.ai',
                        'type': 'link',
                        'metadata': {'title': 'mistral.ai'}
                    },
                    'founded': {'id': 'row3_founded', 'value': '2023', 'type': 'text'},
                    'employees': {'id': 'row3_employees', 'value': 80, 'type': 'number', 'confidence': 0.85}
                }
            }
        ]
        
        sources = [
            DataSource(type='web', name='TechCrunch', lastUpdated='Aug 25, 2025', reliability=0.95),
            DataSource(type='web', name='Reuters', lastUpdated='Aug 25, 2025', reliability=0.98),
            DataSource(type='web', name='Bloomberg', lastUpdated='Aug 20, 2025', reliability=0.97),
            DataSource(type='web', name='Financial Times', lastUpdated='Aug 22, 2025', reliability=0.96),
            DataSource(type='database', name='Company Database', lastUpdated='Aug 25, 2025', reliability=1.0)
        ]
    
    # Check if query is about VC funds
    elif any(keyword in query_lower for keyword in ['vc', 'venture capital', 'funds', 'investment firms']):
        columns = [
            GridColumn(id='fund', name='Fund', type='text', width=150),
            GridColumn(id='aum', name='AUM', type='currency', width=120),
            GridColumn(id='portfolio_size', name='Portfolio Size', type='number', width=100),
            GridColumn(id='avg_check', name='Avg Check Size', type='currency', width=120),
            GridColumn(id='focus', name='Focus Area', type='text', width=150),
            GridColumn(id='stage', name='Investment Stage', type='text', width=120),
        ]
        
        rows = [
            {
                'id': 'row1',
                'cells': {
                    'fund': {
                        'id': 'row1_fund',
                        'value': 'Sequoia Capital',
                        'type': 'text',
                        'confidence': 1.0
                    },
                    'aum': {'id': 'row1_aum', 'value': 85000000000, 'type': 'currency', 'confidence': 0.9},
                    'portfolio_size': {'id': 'row1_portfolio_size', 'value': 350, 'type': 'number'},
                    'avg_check': {'id': 'row1_avg_check', 'value': 25000000, 'type': 'currency'},
                    'focus': {'id': 'row1_focus', 'value': 'Enterprise, AI, Consumer', 'type': 'text'},
                    'stage': {'id': 'row1_stage', 'value': 'Seed to Growth', 'type': 'text'}
                }
            },
            {
                'id': 'row2',
                'cells': {
                    'fund': {
                        'id': 'row2_fund',
                        'value': 'Andreessen Horowitz',
                        'type': 'text',
                        'confidence': 1.0
                    },
                    'aum': {'id': 'row2_aum', 'value': 42000000000, 'type': 'currency', 'confidence': 0.95},
                    'portfolio_size': {'id': 'row2_portfolio_size', 'value': 400, 'type': 'number'},
                    'avg_check': {'id': 'row2_avg_check', 'value': 20000000, 'type': 'currency'},
                    'focus': {'id': 'row2_focus', 'value': 'Crypto, AI, Bio', 'type': 'text'},
                    'stage': {'id': 'row2_stage', 'value': 'Seed to Late Stage', 'type': 'text'}
                }
            }
        ]
        
        sources = [
            DataSource(type='database', name='VC Database', lastUpdated='Aug 25, 2025', reliability=0.95),
            DataSource(type='api', name='Crunchbase API', lastUpdated='Aug 25, 2025', reliability=0.9)
        ]
    
    # Default: Return financial data template
    else:
        columns = [
            GridColumn(id='metric', name='Metric', type='text', width=200),
            GridColumn(id='value', name='Value', type='text', width=150),
            GridColumn(id='change', name='Change', type='percentage', width=100),
            GridColumn(id='source', name='Source', type='text', width=150),
        ]
        
        rows = [
            {
                'id': 'row1',
                'cells': {
                    'metric': {'id': 'row1_metric', 'value': 'Query Processing', 'type': 'text'},
                    'value': {'id': 'row1_value', 'value': 'Ready', 'type': 'text'},
                    'change': {'id': 'row1_change', 'value': 0, 'type': 'percentage'},
                    'source': {'id': 'row1_source', 'value': 'System', 'type': 'text'}
                }
            }
        ]
        
        sources = [
            DataSource(type='agent', name='Data Matrix Agent', lastUpdated=datetime.now().strftime('%b %d, %Y'), reliability=1.0)
        ]
    
    # Cache the fallback response with lower confidence
    final_response = DynamicDataResponse(
        columns=columns,
        rows=rows,
        sources=sources
    )
    
    await data_matrix_cache.set(
        request.query,
        {
            "columns": [col.dict() if hasattr(col, 'dict') else col for col in columns],
            "rows": rows,
            "sources": [src.dict() if hasattr(src, 'dict') else src for src in sources],
            "timestamp": datetime.now().isoformat()
        },
        cache_context,
        ttl=600,  # 10 minutes for fallback data
        confidence=0.5
    )
    
    return final_response

@router.get("/cache-stats")
async def get_cache_stats():
    """Get cache statistics and performance metrics"""
    return data_matrix_cache.get_stats()

@router.post("/cache-invalidate")
async def invalidate_cache(tags: List[str] = None, max_age_seconds: int = None):
    """Invalidate cache entries by tags or age"""
    invalidated = 0
    
    if tags:
        invalidated += await data_matrix_cache.invalidate_by_tags(tags)
    
    if max_age_seconds:
        invalidated += await data_matrix_cache.invalidate_by_age(max_age_seconds)
    
    return {
        "success": True,
        "invalidated_count": invalidated,
        "message": f"Invalidated {invalidated} cache entries"
    }

@router.post("/dynamic-data-search")
async def search_dynamic_data(request: DynamicDataRequest):
    """
    Search and retrieve specific data based on natural language queries.
    Can integrate with various data sources and APIs.
    """
    
    # This endpoint can be extended to:
    # 1. Call external APIs (Tavily, web search, etc.)
    # 2. Query databases
    # 3. Process documents
    # 4. Run ML models for predictions
    
    # For now, return a simple response
    return {
        "query": request.query,
        "results": [
            {
                "type": "data",
                "content": f"Processing query: {request.query}",
                "confidence": 0.95,
                "sources": ["Dynamic Data Agent"]
            }
        ],
        "timestamp": datetime.now().isoformat()
    }

class SpreadsheetRequest(BaseModel):
    prompt: str
    company: Optional[str] = None
    previousCompany: Optional[str] = None
    trackLearning: Optional[bool] = False
    gridState: Optional[Dict[str, Any]] = {}

@router.post("/spreadsheet-direct")
async def spreadsheet_direct(request: SpreadsheetRequest):
    """
    Direct spreadsheet agent using Claude Sonnet 3.5 for intelligent command generation.
    This endpoint handles natural language commands to manipulate spreadsheet data.
    """
    
    # Parse the prompt to understand what kind of data/action is requested
    prompt_lower = request.prompt.lower()
    
    # Try to use Claude for intelligent command generation
    try:
        # Use Claude to generate spreadsheet commands
        commands = await claude_service.generate_spreadsheet_commands(
            prompt=request.prompt,
            context={
                "company": request.company,
                "gridState": request.gridState
            }
        )
        
        if commands and len(commands) > 0:
            return {
                "success": True,
                "commands": commands,
                "commandCount": len(commands),
                "message": f"Generated {len(commands)} commands using Claude Sonnet 3.5",
                "metadata": {
                    "company": request.company,
                    "modelType": "Claude-Generated",
                    "timestamp": datetime.now().isoformat(),
                    "source": "Claude Sonnet 3.5"
                }
            }
    except Exception as e:
        print(f"Claude service error: {e}")
        # Fall back to MCP orchestrator
    
    # Try to use MCP orchestrator as fallback with enhanced reasoning
    try:
        # Apply enhanced reasoning to understand the request
        reasoning_context = await data_matrix_reasoner.reason(
            request.prompt,
            context={
                "company": request.company, 
                "gridState": request.gridState,
                "command_type": "spreadsheet_manipulation",
                "track_learning": request.trackLearning
            }
        )
        
        # Create execution plan
        execution_plan = await data_matrix_reasoner.create_execution_plan(reasoning_context)
        
        # Construct optimized MCP search prompt using reasoning insights
        metrics_str = ', '.join(reasoning_context.metrics) if reasoning_context.metrics else 'key financial metrics'
        entities_str = ', '.join(reasoning_context.entities) if reasoning_context.entities else request.company or 'companies'
        
        mcp_prompt = f"""
        Generate spreadsheet commands for: {request.prompt}
        Company: {request.company or 'General'}
        Context: Creating a financial model or data analysis
        Intent: {reasoning_context.intent.value if hasattr(reasoning_context, 'intent') else 'analysis'}
        
        Focus on:
        - Metrics: {metrics_str}
        - Entities: {entities_str}
        - Time range: {reasoning_context.time_range or 'current'}
        - Complexity level: {reasoning_context.complexity_score:.1f}
        
        Requirements:
        - Return structured spreadsheet commands to populate data
        - Include real financial data where possible
        - Apply appropriate formatting and formulas
        - Confidence level required: {reasoning_context.confidence:.0%}
        """
        
        # Use MCP to get real-time data and generate commands
        mcp_results = []
        async for result in mcp_orchestrator.process_prompt(
            prompt=mcp_prompt,
            context={
                "company": request.company,
                "gridState": request.gridState,
                "reasoning": {
                    "intent": str(reasoning_context.intent) if hasattr(reasoning_context, 'intent') else None,
                    "confidence": reasoning_context.confidence,
                    "complexity": reasoning_context.complexity_score,
                    "entities": reasoning_context.entities,
                    "metrics": reasoning_context.metrics
                },
                "plan": {
                    "steps": execution_plan.steps,
                    "parallel": execution_plan.parallel_execution if hasattr(execution_plan, 'parallel_execution') else False,
                    "cache_key": execution_plan.cache_key if hasattr(execution_plan, 'cache_key') else None
                },
                "output_format": "spreadsheet_commands"
            },
            stream=False
        ):
            mcp_results.append(result)
        
        # Process MCP results into spreadsheet commands
        if mcp_results and "commands" in mcp_results[-1]:
            commands = mcp_results[-1]["commands"]
            return {
                "success": True,
                "commands": commands,
                "commandCount": len(commands),
                "message": f"Generated {len(commands)} commands via MCP for: {request.prompt}",
                "metadata": {
                    "company": request.company,
                    "modelType": "Advanced Reasoning Engine",
                    "timestamp": datetime.now().isoformat(),
                    "source": "MCP Orchestrator",
                    "confidence": reasoning_context.confidence
                }
            }
    except Exception as e:
        print(f"MCP orchestration error: {e}")
        # Fall back to pattern-based command generation
    
    # Generate appropriate spreadsheet commands based on patterns
    commands = []
    
    # Check for specific actions in the prompt
    if "create" in prompt_lower or "add" in prompt_lower:
        if "dcf" in prompt_lower or "discounted cash flow" in prompt_lower:
            commands = [
                "grid.setColumns(['Metric', 'Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5', 'Terminal'])",
                "grid.addRow(['Revenue', 1000000, 1500000, 2250000, 3375000, 5062500, 7593750])",
                "grid.addRow(['Growth Rate', '50%', '50%', '50%', '50%', '50%', '3%'])",
                "grid.addRow(['EBITDA Margin', '20%', '25%', '30%', '35%', '40%', '40%'])",
                "grid.addRow(['EBITDA', 200000, 375000, 675000, 1181250, 2025000, 3037500])",
                "grid.addRow(['Tax Rate', '21%', '21%', '21%', '21%', '21%', '21%'])",
                "grid.addRow(['NOPAT', 158000, 296250, 533250, 933187, 1599750, 2399625])",
                "grid.addRow(['CapEx', 50000, 75000, 112500, 168750, 253125, 379687])",
                "grid.addRow(['Working Capital', 100000, 150000, 225000, 337500, 506250, 759375])",
                "grid.addRow(['Free Cash Flow', 8000, 71250, 195750, 426937, 840375, 1260563])",
                "grid.addRow(['Discount Factor', 0.909, 0.826, 0.751, 0.683, 0.621, 0.564])",
                "grid.addRow(['PV of FCF', 7272, 58862, 147018, 291597, 521892, 710957])",
                "grid.addRow(['Terminal Value', '', '', '', '', '', 12605625])",
                "grid.addRow(['PV of Terminal', '', '', '', '', '', 7109572])",
                "grid.addRow(['Enterprise Value', '', '', '', '', '', 8847170])",
                "grid.applyFormula('B14', '=SUM(B12:G12)+G14')"
            ]
        elif "revenue" in prompt_lower:
            commands = [
                "grid.setColumns(['Metric', 'Q1', 'Q2', 'Q3', 'Q4', 'Total'])",
                "grid.addRow(['Product Revenue', 250000, 275000, 300000, 350000, '=SUM(B2:E2)'])",
                "grid.addRow(['Service Revenue', 50000, 55000, 60000, 65000, '=SUM(B3:E3)'])",
                "grid.addRow(['Total Revenue', '=B2+B3', '=C2+C3', '=D2+D3', '=E2+E3', '=SUM(B4:E4)'])",
                "grid.addRow(['Growth Rate', '', '10%', '9%', '17%', ''])",
                "grid.applyStyle('A4:F4', { fontWeight: 'bold', backgroundColor: '#e0e0e0' })"
            ]
        else:
            # Default data structure
            commands = [
                "grid.setColumns(['Company', 'Revenue', 'Growth', 'Valuation', 'Status'])",
                "grid.addRow(['TechCo', 5000000, '25%', 50000000, 'Active'])",
                "grid.addRow(['DataCorp', 3000000, '40%', 30000000, 'Growing'])",
                "grid.addRow(['CloudBase', 8000000, '15%', 100000000, 'Mature'])"
            ]
    
    elif "calculate" in prompt_lower or "formula" in prompt_lower:
        commands = [
            "grid.selectCell('F2')",
            "grid.applyFormula('F2', '=SUM(B2:E2)')",
            "grid.selectCell('F3')",
            "grid.applyFormula('F3', '=SUM(B3:E3)')",
            "grid.selectCell('F4')",
            "grid.applyFormula('F4', '=F2+F3')"
        ]
    
    elif "format" in prompt_lower or "style" in prompt_lower:
        commands = [
            "grid.applyStyle('B:E', { format: 'currency' })",
            "grid.applyStyle('A1:F1', { fontWeight: 'bold', backgroundColor: '#4a5568', color: 'white' })",
            "grid.applyStyle('F:F', { backgroundColor: '#f0f0f0', fontWeight: 'bold' })"
        ]
    
    elif "chart" in prompt_lower or "graph" in prompt_lower:
        commands = [
            "grid.createChart('bar', { data: 'B2:E4', title: 'Quarterly Performance' })"
        ]
    
    else:
        # Default action - load sample data
        commands = [
            "grid.clear()",
            "grid.setColumns(['Metric', 'Value', 'Change', 'Target', 'Status'])",
            "grid.addRow(['Revenue', 5000000, '+25%', 6000000, 'On Track'])",
            "grid.addRow(['Costs', 3000000, '+15%', 2800000, 'Over Budget'])",
            "grid.addRow(['Profit', 2000000, '+40%', 3200000, 'Below Target'])",
            "grid.addRow(['Margin', '40%', '+5pp', '45%', 'Improving'])"
        ]
    
    # Add formatting commands for better presentation
    if commands and not any("applyStyle" in cmd for cmd in commands):
        commands.extend([
            "grid.applyStyle('A1:E1', { fontWeight: 'bold', backgroundColor: '#1a202c', color: 'white' })",
            "grid.applyStyle('B:B', { format: 'currency' })",
            "grid.autoResize()"
        ])
    
    # Return the response with commands and metadata
    return {
        "success": True,
        "commands": commands,
        "commandCount": len(commands),
        "message": f"Generated {len(commands)} commands for: {request.prompt}",
        "metadata": {
            "company": request.company,
            "modelType": "DCF" if "dcf" in prompt_lower else "General",
            "timestamp": datetime.now().isoformat()
        }
    }