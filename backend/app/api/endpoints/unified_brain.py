"""
Unified Brain API Endpoints
Single endpoint that handles all agent requests using the unified orchestrator
Supports both streaming and non-streaming responses
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Optional
from pydantic import BaseModel, Field
import json
import asyncio
import logging

from app.services.unified_mcp_orchestrator import (
    get_unified_orchestrator,
    OutputFormat
)
from app.utils.json_serializer import safe_json_dumps, clean_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["unified-brain"])


class UnifiedRequest(BaseModel):
    """Request model for unified brain processing"""
    prompt: str = Field(..., description="User prompt to process")
    output_format: str = Field("analysis", description="Output format: spreadsheet, deck, docs, analysis, matrix")
    context: Optional[Dict] = Field(None, description="Additional context")
    stream: bool = Field(False, description="Enable streaming response")
    options: Optional[Dict] = Field(default_factory=dict, description="Additional options")


@router.post("/unified-brain")
async def process_unified_request(request: UnifiedRequest):
    """
    Main endpoint for all agent requests
    Handles data gathering, analysis, and formatting
    """
    logger.info(f"[UNIFIED-BRAIN] Received request with output_format: {request.output_format}, stream: {request.stream}")
    try:
        # Validate output format - handle string conversion
        output_format_str = request.output_format.lower().replace('-', '_')
        try:
            # Try direct enum conversion first
            output_format = OutputFormat(output_format_str)
        except ValueError:
            # Map common frontend formats to backend enums
            # NOTE: deck, matrix, spreadsheet are handled specially in orchestrator
            # so we keep them as STRUCTURED enum but pass original format string
            format_map = {
                'spreadsheet': OutputFormat.STRUCTURED,  # Special handling in orchestrator
                'deck': OutputFormat.STRUCTURED,  # Special handling in orchestrator  
                'matrix': OutputFormat.STRUCTURED,  # Special handling in orchestrator
                'docs': OutputFormat.STRUCTURED,  # Map docs to structured (was markdown)
                'analysis': OutputFormat.STRUCTURED,  # Map analysis to structured
                'json': OutputFormat.JSON,
                'markdown': OutputFormat.STRUCTURED  # Map markdown to structured (fallback)
            }
            output_format = format_map.get(output_format_str, OutputFormat.STRUCTURED)
        
        # Get orchestrator
        orchestrator = get_unified_orchestrator()
        
        # Clear cache for fresh results per request (MUST be before any processing)
        orchestrator._tavily_cache.clear()
        
        logger.info(f"[DEBUG] Request output_format: {request.output_format}")
        logger.info(f"[DEBUG] Parsed OutputFormat enum: {output_format}")
        logger.info(f"[DEBUG] Enum value string: {output_format.value}")
        
        if request.stream:
            # Return streaming response
            async def generate():
                try:
                    # Track if we've sent the done signal
                    done_sent = False
                    update_count = 0
                    
                    # Stream progress updates during execution
                    # Always pass the original format string to preserve it
                    async for update in orchestrator.process_request_stream(
                        prompt=request.prompt,
                        output_format=request.output_format,  # Always pass original format string
                        context=request.context
                    ):
                        update_count += 1
                        
                        # Stream each update as it comes
                        if isinstance(update, dict):
                            # Clean the update for JSON serialization
                            cleaned_update = clean_for_json(update)
                            
                            # Use safe serializer
                            try:
                                serialized = safe_json_dumps(cleaned_update)
                                yield f"data: {serialized}\n\n"
                                
                                # Log successful serialization of complex messages
                                if update.get('type') == 'complete':
                                    logger.info(f"Successfully serialized complete message (update #{update_count})")
                                    
                            except Exception as e:
                                logger.error(f"Failed to serialize update #{update_count}: {e}")
                                logger.error(f"Update type: {type(update)}")
                                if 'result' in update:
                                    logger.error(f"Result type: {type(update['result'])}")
                                # Send error message instead
                                error_msg = safe_json_dumps({
                                    'type': 'error', 
                                    'message': f'Serialization failed: {str(e)}',
                                    'update_number': update_count
                                })
                                yield f"data: {error_msg}\n\n"
                        else:
                            # Handle non-dict updates
                            simple_msg = safe_json_dumps({
                                'type': 'message', 
                                'content': str(update),
                                'update_number': update_count
                            })
                            yield f"data: {simple_msg}\n\n"
                    
                    # Send done signal and terminate
                    if not done_sent:
                        yield f"data: [DONE]\n\n"
                        done_sent = True
                        logger.info(f"Stream completed successfully after {update_count} updates")
                    
                    # Explicit return to ensure generator terminates
                    return
                    
                except Exception as e:
                    logger.error(f"Streaming error: {e}", exc_info=True)
                    error_msg = safe_json_dumps({
                        'type': 'error', 
                        'message': str(e),
                        'fatal': True
                    })
                    yield f"data: {error_msg}\n\n"
                    # Still send done signal on error
                    yield f"data: [DONE]\n\n"
                    return
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                }
            )
        else:
            # Non-streaming response - await the coroutine directly
            # Always pass the original format string to preserve it
            result = await orchestrator.process_request(
                prompt=request.prompt,
                output_format=request.output_format,  # Always pass original format string
                context=request.context
            )
            
            # Return the result
            if result and result.get('success'):
                # With the new unified format, 'results' contains the formatted response
                formatted_results = result.get('results')
                
                # Check if we have the new unified format structure
                if isinstance(formatted_results, dict) and 'format' in formatted_results:
                    # New unified format - flatten the structure for frontend compatibility
                    response_data = {
                        "success": True,
                        "format": formatted_results.get('format'),
                        "companies": formatted_results.get('companies', []),
                        "charts": formatted_results.get('charts', []),
                        "citations": formatted_results.get('citations', []),
                        "data": formatted_results.get('data', {}),
                        "metadata": formatted_results.get('metadata', {})
                    }
                    
                    # Add format-specific fields
                    if 'investment_analysis' in formatted_results:
                        response_data['investment_analysis'] = formatted_results['investment_analysis']
                    if 'comparison' in formatted_results:
                        response_data['comparison'] = formatted_results['comparison']
                    if 'valuation' in formatted_results:
                        response_data['valuation'] = formatted_results['valuation']
                    if 'slides' in formatted_results:
                        response_data['slides'] = formatted_results['slides']
                    if 'matrix' in formatted_results:
                        response_data['matrix'] = formatted_results['matrix']
                        response_data['columns'] = formatted_results.get('columns', [])
                        response_data['rows'] = formatted_results.get('rows', [])
                    
                    return JSONResponse(content=response_data)
                
                # Legacy format handling (shouldn't happen with new code)
                elif isinstance(formatted_results, dict) and output_format.value in ["structured", "analysis", "spreadsheet", "deck", "matrix"]:
                    # Old structured data format
                    actual_format = request.output_format.lower().replace('-', '_')
                    return JSONResponse(content={
                        "success": True,
                        "format": actual_format,
                        "result": formatted_results,
                        "commands": formatted_results.get('commands', []),
                        "citations": formatted_results.get('citations', []),
                        "charts": formatted_results.get('charts', []),
                        "companies": formatted_results.get('companies', []),
                        "data": formatted_results.get('data', {}),
                        "comparison": formatted_results.get('comparison', {}),
                        "valuation": formatted_results.get('valuation', {}),
                        "metadata": formatted_results.get('metadata', {}),
                        "execution_time": result.get('execution_time', 0),
                        "errors": result.get('errors', [])
                    })
                # For markdown or other string formats
                elif isinstance(formatted_results, str):
                    return JSONResponse(content={
                        "success": True,
                        "content": formatted_results,
                        "format": output_format.value,
                        "execution_time": result.get('execution_time', 0),
                        "errors": result.get('errors', [])
                    })
                # Fallback: return the entire result
                else:
                    return JSONResponse(content=result)
            else:
                return JSONResponse(content={"success": False, "error": result.get('error', 'No results generated')})
    
    except Exception as e:
        logger.error(f"Unified brain error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unified-brain-stream")
async def process_unified_stream(request: UnifiedRequest):
    """
    Streaming-only endpoint for backwards compatibility
    Redirects to main endpoint with stream=True
    """
    request.stream = True
    return await process_unified_request(request)


@router.get("/unified-brain/health")
async def health_check():
    """Health check for unified brain"""
    return {
        "status": "healthy",
        "service": "unified-brain",
        "features": [
            "task-decomposition",
            "skill-orchestration",
            "parallel-execution",
            "streaming-support",
            "multi-format-output"
        ]
    }


@router.get("/unified-brain/skills")
async def get_available_skills():
    """Get list of available skills"""
    orchestrator = get_unified_orchestrator()
    return {
        "skills": list(orchestrator.skill_registry.keys()),
        "total": len(orchestrator.skill_registry)
    }


@router.post("/unified-brain/analyze-intent")
async def analyze_intent(request: UnifiedRequest):
    """
    Analyze prompt intent without executing
    Useful for debugging and understanding what will happen
    """
    try:
        orchestrator = get_unified_orchestrator()
        
        # Extract entities
        entities = orchestrator._extract_entities(request.prompt)
        
        # Analyze intent - handle format mapping properly
        output_format_str = request.output_format.lower().replace('-', '_')
        try:
            output_format = OutputFormat(output_format_str)
        except ValueError:
            # Use the same mapping as above
            format_map = {
                'spreadsheet': OutputFormat.STRUCTURED,
                'deck': OutputFormat.STRUCTURED,
                'matrix': OutputFormat.STRUCTURED,
                'docs': OutputFormat.STRUCTURED,
                'analysis': OutputFormat.STRUCTURED,
                'json': OutputFormat.JSON,
                'markdown': OutputFormat.STRUCTURED
            }
            output_format = format_map.get(output_format_str, OutputFormat.STRUCTURED)
        
        async with orchestrator:
            intent = await orchestrator._analyze_intent(request.prompt, entities, output_format)
        
        # Build skill chain
        async with orchestrator:
            skill_chain = await orchestrator._build_skill_chain(
                request.prompt, output_format, intent
            )
        
        return {
            "entities": entities,
            "intent": intent,
            "skill_chain": [
                {
                    "skill": node.skill,
                    "purpose": node.purpose,
                    "parallel_group": node.parallel_group,
                    "confidence": node.confidence
                }
                for node in skill_chain
            ]
        }
    
    except Exception as e:
        logger.error(f"Intent analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))