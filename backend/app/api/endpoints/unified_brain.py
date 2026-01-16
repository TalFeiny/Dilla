"""
Unified Brain API Endpoints
Single endpoint that handles all agent requests using the unified orchestrator
Supports both streaming and non-streaming responses
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from typing import Dict, Optional
from pydantic import BaseModel, Field
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
    options: Optional[Dict] = Field(default_factory=dict, description="Additional options")


@router.post("/unified-brain")
async def process_unified_request(request: UnifiedRequest):
    """
    Main endpoint for all agent requests
    Handles data gathering, analysis, and formatting
    """
    logger.error(f"[UNIFIED-BRAIN] ⭐⭐⭐ ENDPOINT HIT ⭐⭐⭐ Received request with output_format: {request.output_format}")
    logger.error(f"[UNIFIED-BRAIN] Prompt: {request.prompt[:100]}")
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
        readiness_info = getattr(orchestrator, "readiness_status", lambda: {"ready": True})()
        if not readiness_info.get("ready", True):
            logger.error(f"[UNIFIED-BRAIN] Orchestrator not ready: {readiness_info.get('error')}")
            raise HTTPException(status_code=503, detail="Orchestrator dependencies not ready")
        else:
            logger.info(f"[UNIFIED-BRAIN] Orchestrator readiness: {readiness_info}")
        
        # Cache clearing now happens inside process_request_stream
        
        logger.info(f"[DEBUG] Request output_format: {request.output_format}")
        logger.info(f"[DEBUG] Parsed OutputFormat enum: {output_format}")
        logger.info(f"[DEBUG] Enum value string: {output_format.value}")
        
        # Non-streaming response - await the coroutine directly
        # Always pass the original format string to preserve it
        logger.info(f"[API] About to call orchestrator.process_request with output_format: {request.output_format}")
        try:
            result = await orchestrator.process_request(
                prompt=request.prompt,
                output_format=request.output_format,  # Always pass original format string
                context=request.context
            )
            # #region agent log
            import json
            with open('/Users/admin/code/dilla-ai/.cursor/debug.log','a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"unified_brain.py:86","message":"Orchestrator result received","data":{"resultType":str(type(result)),"isDict":isinstance(result,dict),"isNone":result is None,"hasSuccess":result.get('success') if isinstance(result,dict) else False,"keys":list(result.keys()) if isinstance(result,dict) else []},"timestamp":int(__import__('time').time()*1000)})+'\n')
            # #endregion
            logger.info(f"[API] Received result from orchestrator: {type(result)}")
            logger.info(f"[API] Result success: {result.get('success') if isinstance(result, dict) else 'not_dict'}")
            logger.info(f"[API] Result keys: {list(result.keys()) if isinstance(result, dict) else 'not_dict'}")
            
            # For deck format, check if slides are directly in result
            if isinstance(result, dict) and result.get('format') == 'deck' and 'slides' in result:
                logger.info(f"[API] Deck format detected with {len(result.get('slides', []))} slides at top level")
        except Exception as e:
            logger.error(f"[API] Exception calling orchestrator: {e}")
            logger.error(f"[API] Exception type: {type(e)}")
            import traceback
            logger.error(f"[API] Traceback: {traceback.format_exc()}")
            # #region agent log
            import json
            with open('/Users/admin/code/dilla-ai/.cursor/debug.log','a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"unified_brain.py:97","message":"Orchestrator exception","data":{"error":str(e),"errorType":str(type(e))},"timestamp":int(__import__('time').time()*1000)})+'\n')
            # #endregion
            raise HTTPException(status_code=500, detail=f"Orchestrator error: {str(e)}")
        
        # CRITICAL: Clean all numpy types from result before returning
        from app.utils.numpy_converter import convert_numpy_to_native
        if result:
            result = convert_numpy_to_native(result)
        
        # CRITICAL: Convert infinity values to None before JSON serialization
        def convert_inf_to_none(obj):
            """Recursively convert infinity values to None"""
            if isinstance(obj, float):
                if obj == float('inf') or obj == float('-inf'):
                    return None
                if obj != obj:  # NaN
                    return None
            elif isinstance(obj, dict):
                return {k: convert_inf_to_none(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_inf_to_none(item) for item in obj]
            return obj
        
        if result:
            try:
                result = convert_inf_to_none(result)
            except Exception as e:
                logger.warning(f"[ENDPOINT] Error converting inf values: {e}")
        
        # #region agent log
        import json
        with open('/Users/admin/code/dilla-ai/.cursor/debug.log','a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"unified_brain.py:125","message":"After inf conversion - before success check","data":{"resultType":str(type(result)),"isTruthy":bool(result),"isDict":isinstance(result,dict),"hasSuccess":result.get('success') if isinstance(result,dict) else False,"keys":list(result.keys()) if isinstance(result,dict) else []},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        
        # Debug logging before success check
        logger.info(f"[ENDPOINT] After inf conversion - result type: {type(result)}")
        logger.info(f"[ENDPOINT] After inf conversion - result is truthy: {bool(result)}")
        if isinstance(result, dict):
            logger.info(f"[ENDPOINT] After inf conversion - result.get('success'): {result.get('success')}")
            logger.info(f"[ENDPOINT] After inf conversion - result keys: {list(result.keys())}")
        
        # Return the result  
        # #region agent log
        import json
        with open('/Users/admin/code/dilla-ai/.cursor/debug.log','a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"unified_brain.py:132","message":"Before success check","data":{"resultExists":result is not None,"resultSuccess":result.get('success') if isinstance(result,dict) else False,"resultType":str(type(result))},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        
        if result and result.get('success'):
            # Check if slides are already at top level (new structure from process_request)
            if isinstance(result, dict) and 'slides' in result and result.get('format') == 'deck':
                logger.info(f"[ENDPOINT] ✅ Found slides at top level with {len(result.get('slides', []))} slides")
                logger.info(f"[ENDPOINT] ✅ Returning deck data in result field for frontend")
                
                # Package deck data for frontend - it expects data in 'result' field
                deck_data = {
                    "format": "deck",
                    "slides": result.get('slides') or [],  # Ensures never None
                    "theme": result.get('theme', 'professional'),
                    "metadata": result.get('metadata', {}),
                    "citations": result.get('citations', []),
                    "charts": result.get('charts', []),
                    "companies": result.get('companies', [])
                }
                
                response_data = {
                    "success": True,
                    "result": deck_data  # Frontend expects 'result' field
                }
                
                # #region agent log
                import json
                with open('/Users/admin/code/dilla-ai/.cursor/debug.log','a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"unified_brain.py:155","message":"Returning deck response","data":{"hasSuccess":response_data.get('success'),"hasResult":'result' in response_data,"resultKeys":list(response_data.get('result',{}).keys()) if isinstance(response_data.get('result'),dict) else [],"slidesCount":len(response_data.get('result',{}).get('slides',[])) if isinstance(response_data.get('result'),dict) else 0},"timestamp":int(__import__('time').time()*1000)})+'\n')
                # #endregion
                
                try:
                    cleaned_response = clean_for_json(response_data)
                    return JSONResponse(content=cleaned_response)
                except Exception as e:
                    logger.error(f"[ENDPOINT] JSON serialization error for deck: {e}")
                    import traceback
                    logger.error(f"[ENDPOINT] Traceback: {traceback.format_exc()}")
                    # #region agent log
                    import json
                    with open('/Users/admin/code/dilla-ai/.cursor/debug.log','a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"unified_brain.py:165","message":"Deck serialization error","data":{"error":str(e)},"timestamp":int(__import__('time').time()*1000)})+'\n')
                    # #endregion
                    error_response = clean_for_json({
                        "success": False,
                        "error": f"Serialization error: {str(e)}"
                    })
                    return JSONResponse(content=error_response, status_code=500)
            
            # With the new unified format, 'results' contains the formatted response
            formatted_results = result.get('results') or result.get('result')  # Try both
            
            # Add debug logging for deck response construction
            logger.info(f"[ENDPOINT] result.success: {result.get('success')}")
            logger.info(f"[ENDPOINT] formatted_results type: {type(formatted_results)}")
            logger.info(f"[ENDPOINT] formatted_results keys: {list(formatted_results.keys()) if isinstance(formatted_results, dict) else 'not_dict'}")
            if isinstance(formatted_results, dict):
                logger.info(f"[ENDPOINT] formatted_results.format: {formatted_results.get('format')}")
                logger.info(f"[ENDPOINT] formatted_results.slides count: {len(formatted_results.get('slides', []))}")
            
            # REMOVED: No need to check for nested deck-storytelling
            # The orchestrator now returns deck data at top level
            
            # Add debug logging for deck data structure
            logger.info(f"[API] Deck data structure: format={formatted_results.get('format') if isinstance(formatted_results, dict) else 'not_dict'}, slides_count={len(formatted_results.get('slides', [])) if isinstance(formatted_results, dict) else 0}")
            if isinstance(formatted_results, dict) and formatted_results.get('slides'):
                logger.info(f"[API] First slide structure: {list(formatted_results.get('slides')[0].keys()) if formatted_results.get('slides') else 'no slides'}")
                # Normalize slides to ensure it's a list
                slides = formatted_results.get('slides') or []
                if not isinstance(slides, list):
                    slides = []
                formatted_results['slides'] = slides
            
            # SPECIAL CASE: Check if this is a deck request but format field is missing
            if request.output_format == 'deck' and isinstance(formatted_results, dict):
                if 'format' not in formatted_results and 'slides' in formatted_results:
                    logger.info(f"[ENDPOINT] 🔧 FIXING: Deck request but missing format field, adding it")
                    formatted_results['format'] = 'deck'
                    if 'theme' not in formatted_results:
                        formatted_results['theme'] = 'professional'
            
            # Check if we have the new unified format structure
            # Also check for 'type' field as fallback (analysis format uses 'type' instead of 'format')
            has_format = isinstance(formatted_results, dict) and ('format' in formatted_results or 'type' in formatted_results)
            if has_format:
                # Normalize 'type' to 'format' if needed
                if 'format' not in formatted_results and 'type' in formatted_results:
                    formatted_results['format'] = formatted_results['type']
                logger.info(f"[ENDPOINT] Found format field: {formatted_results.get('format')}")
                # For deck format, return it directly as 'result' for frontend compatibility
                if formatted_results.get('format') == 'deck':
                    logger.info(f"[ENDPOINT] ✅ Deck format detected, wrapping response")
                    # Ensure we have a properly structured deck response
                    # Normalize slides to ensure it's always an array
                    slides = formatted_results.get('slides') or []
                    if not isinstance(slides, list):
                        slides = []
                    formatted_results['slides'] = slides
                    
                    deck_response = {
                        "success": True,
                        "result": formatted_results  # Frontend expects 'result' not 'results'
                    }
                    logger.info(f"[DECK_RESPONSE] Returning deck with {len(slides)} slides")
                    logger.info(f"[DECK_RESPONSE] deck_response.result.format: {deck_response['result'].get('format')}")
                    try:
                        cleaned = clean_for_json(deck_response)
                        logger.info(f"[DECK_RESPONSE] Serialization test successful")
                        return JSONResponse(content=cleaned)
                    except Exception as e:
                        logger.error(f"[DECK_RESPONSE] Serialization failed: {e}")
                        # Return a minimal deck response
                        minimal_response = {
                            "success": True,
                            "result": {
                                "format": "deck",
                                "slides": formatted_results.get('slides') or [],  # Ensures never None
                                "theme": "professional",
                                "metadata": {"error": "Serialization issue resolved"},
                                "companies": formatted_results.get('companies', [])
                            }
                        }
                        cleaned_minimal = clean_for_json(minimal_response)
                        return JSONResponse(content=cleaned_minimal)
                else:
                    logger.info(f"[ENDPOINT] Non-deck format: {formatted_results.get('format')}")
                # New unified format - wrap in result object for frontend compatibility
                logger.info(f"[ENDPOINT] Wrapping non-deck format as structured response")
                result_data = {
                    "format": formatted_results.get('format'),
                    "companies": formatted_results.get('companies', []),
                    "charts": formatted_results.get('charts', []),
                    "citations": formatted_results.get('citations', []),
                    "data": formatted_results.get('data', {}),
                    "metadata": formatted_results.get('metadata', {}),
                    "commands": formatted_results.get('commands', [])  # Include commands for spreadsheet format
                }
                
                # Add format-specific fields
                if 'investment_analysis' in formatted_results:
                    result_data['investment_analysis'] = formatted_results['investment_analysis']
                if 'comparison' in formatted_results:
                    result_data['comparison'] = formatted_results['comparison']
                if 'valuation' in formatted_results:
                    result_data['valuation'] = formatted_results['valuation']
                if 'valuations' in formatted_results:
                    result_data['valuations'] = formatted_results['valuations']  # Bull/bear/base scenarios
                if 'cap_tables' in formatted_results:
                    result_data['cap_tables'] = formatted_results['cap_tables']
                if 'portfolio_analysis' in formatted_results:
                    result_data['portfolio_analysis'] = formatted_results['portfolio_analysis']
                if 'exit_modeling' in formatted_results:
                    result_data['exit_modeling'] = formatted_results['exit_modeling']
                if 'fund_metrics' in formatted_results:
                    result_data['fund_metrics'] = formatted_results['fund_metrics']
                if 'stage_analysis' in formatted_results:
                    result_data['stage_analysis'] = formatted_results['stage_analysis']
                if 'market_analysis' in formatted_results:
                    result_data['market_analysis'] = formatted_results['market_analysis']  # Market sizing
                if 'slides' in formatted_results:
                    result_data['slides'] = formatted_results['slides']
                if 'matrix' in formatted_results:
                    result_data['matrix'] = formatted_results['matrix']
                    result_data['columns'] = formatted_results.get('columns', [])
                    result_data['rows'] = formatted_results.get('rows', [])
                
                # Wrap in result object for frontend compatibility
                response_data = {
                    "success": True,
                    "result": result_data
                }
                    
                # Clean the response for JSON serialization and return as pre-serialized string
                try:
                    cleaned_response = clean_for_json(response_data)
                    return JSONResponse(content=cleaned_response)
                except Exception as e:
                    logger.error(f"[ENDPOINT] JSON serialization error: {e}")
                    logger.error(f"[ENDPOINT] Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'not_dict'}")
                    import traceback
                    logger.error(f"[ENDPOINT] Traceback: {traceback.format_exc()}")
                    # Return a minimal error response
                    error_response = clean_for_json({
                        "success": False,
                        "error": f"Serialization error: {str(e)}",
                        "partial_data": True
                    })
                    return JSONResponse(content=error_response, status_code=500)
                
                # Legacy format handling (shouldn't happen with new code)
                if isinstance(formatted_results, dict) and output_format.value in ["structured", "analysis", "spreadsheet", "deck", "matrix"]:
                    # Old structured data format
                    actual_format = request.output_format.lower().replace('-', '_')
                    # Clean the response for JSON serialization
                    response_data = {
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
                        "valuations": formatted_results.get('valuations', {}),  # Bull/bear/base
                        "cap_tables": formatted_results.get('cap_tables', {}),
                        "portfolio_analysis": formatted_results.get('portfolio_analysis', {}),
                        "exit_modeling": formatted_results.get('exit_modeling', {}),
                        "fund_metrics": formatted_results.get('fund_metrics', {}),
                        "stage_analysis": formatted_results.get('stage_analysis', {}),
                        "market_analysis": formatted_results.get('market_analysis', {}),  # Market sizing
                        "metadata": formatted_results.get('metadata', {}),
                        "execution_time": result.get('execution_time', 0),
                        "errors": result.get('errors', [])
                    }
                    cleaned_response = clean_for_json(response_data)
                    return JSONResponse(content=cleaned_response)
                # For markdown or other string formats
                elif isinstance(formatted_results, str):
                    # Clean the response for JSON serialization
                    response_data = {
                        "success": True,
                        "content": formatted_results,
                        "format": output_format.value,
                        "execution_time": result.get('execution_time', 0),
                        "errors": result.get('errors', [])
                    }
                    cleaned_response = clean_for_json(response_data)
                    return JSONResponse(content=cleaned_response)
                # Fallback: return the entire result
                else:
                    logger.info(f"[ENDPOINT] Fallback: No format field found, returning entire result")
                    logger.info(f"[ENDPOINT] result keys: {list(result.keys()) if isinstance(result, dict) else 'not_dict'}")
                    # Clean the result for JSON serialization
                    cleaned_result = clean_for_json(result)
                    return JSONResponse(content=cleaned_result)
            else:
                logger.error(f"[ENDPOINT] No success in result: {result}")
                logger.error(f"[ENDPOINT] Result type: {type(result)}")
                logger.error(f"[ENDPOINT] Result keys: {list(result.keys()) if isinstance(result, dict) else 'not_dict'}")
                logger.error(f"[ENDPOINT] Result success value: {result.get('success') if isinstance(result, dict) else 'N/A'}")
                logger.error(f"[ENDPOINT] Result error value: {result.get('error') if isinstance(result, dict) else 'N/A'}")
                # #region agent log
                import json
                with open('/Users/admin/code/dilla-ai/.cursor/debug.log','a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"unified_brain.py:345","message":"No success in result - returning error","data":{"resultType":str(type(result)),"isDict":isinstance(result,dict),"keys":list(result.keys()) if isinstance(result,dict) else [],"success":result.get('success') if isinstance(result,dict) else None,"error":result.get('error') if isinstance(result,dict) else None},"timestamp":int(__import__('time').time()*1000)})+'\n')
                # #endregion
                error_response = clean_for_json({"success": False, "error": result.get('error', 'No results generated') if isinstance(result, dict) else 'Invalid result format'})
                return JSONResponse(content=error_response, status_code=500)
    
    except Exception as e:
        logger.error(f"Unified brain error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return error as pre-serialized JSON response
        error_response = clean_for_json({
            "success": False,
            "error": str(e),
            "type": type(e).__name__
        })
        return JSONResponse(content=error_response, status_code=500)


@router.post("/unified-brain-stream")
async def process_unified_stream(request: UnifiedRequest):
    """
    STREAMING DISABLED - This endpoint now returns non-streaming results
    """
    logger.info(f"[UNIFIED-BRAIN-STREAM] Streaming disabled, using non-streaming endpoint")
    # Just call the non-streaming endpoint
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


@router.get("/unified-brain/diagnostics")
async def diagnostics():
    """
    Diagnostic endpoint to check Tavily and ModelRouter status
    Returns detailed information about API key availability and service health
    """
    from app.core.config import settings
    from app.services.model_router import get_model_router
    
    diagnostics_data = {
        "timestamp": None,
        "tavily": {
            "configured": False,
            "api_key_present": False,
            "api_key_preview": None,
            "status": "unknown"
        },
        "model_router": {
            "initialized": False,
            "available_models": [],
            "api_keys": {},
            "status": "unknown"
        },
        "orchestrator": {
            "ready": False,
            "error": None
        }
    }
    
    try:
        from datetime import datetime
        diagnostics_data["timestamp"] = datetime.utcnow().isoformat()
        
        # Check Tavily
        tavily_key = settings.TAVILY_API_KEY
        diagnostics_data["tavily"]["api_key_present"] = bool(tavily_key)
        diagnostics_data["tavily"]["configured"] = bool(tavily_key)
        if tavily_key:
            diagnostics_data["tavily"]["api_key_preview"] = f"{tavily_key[:10]}...{tavily_key[-4:]}" if len(tavily_key) > 14 else "***"
            diagnostics_data["tavily"]["status"] = "configured"
        else:
            diagnostics_data["tavily"]["status"] = "missing_api_key"
        
        # Check ModelRouter
        try:
            router = get_model_router()
            diagnostics_data["model_router"]["initialized"] = True
            
            # Check API keys
            api_keys_status = {
                "anthropic": bool(router.anthropic_key),
                "openai": bool(router.openai_key),
                "google": bool(router.google_key),
                "groq": bool(router.groq_key),
                "together": bool(router.together_key),
                "perplexity": bool(router.perplexity_key),
                "anyscale": bool(router.anyscale_key)
            }
            diagnostics_data["model_router"]["api_keys"] = api_keys_status
            
            # Count available models (models that have API keys)
            available_models = []
            for model_name, config in router.model_configs.items():
                provider = config.get("provider")
                if provider:
                    # Get provider value (enum.value or string)
                    try:
                        provider_name = provider.value if hasattr(provider, 'value') else str(provider)
                    except:
                        provider_name = str(provider)
                    
                    # Check if we have the API key for this provider
                    provider_name_lower = provider_name.lower()
                    if provider_name_lower == "anthropic" and router.anthropic_key:
                        available_models.append(model_name)
                    elif provider_name_lower == "openai" and router.openai_key:
                        available_models.append(model_name)
                    elif provider_name_lower == "google" and router.google_key:
                        available_models.append(model_name)
                    elif provider_name_lower == "groq" and router.groq_key:
                        available_models.append(model_name)
                    elif provider_name_lower == "together" and router.together_key:
                        available_models.append(model_name)
                    elif provider_name_lower == "perplexity" and router.perplexity_key:
                        available_models.append(model_name)
                    elif provider_name_lower == "anyscale" and router.anyscale_key:
                        available_models.append(model_name)
            
            diagnostics_data["model_router"]["available_models"] = available_models
            
            # Determine status
            if any(api_keys_status.values()):
                diagnostics_data["model_router"]["status"] = "ready"
            else:
                diagnostics_data["model_router"]["status"] = "no_api_keys"
                
        except Exception as e:
            diagnostics_data["model_router"]["status"] = f"error: {str(e)}"
            logger.error(f"Error checking ModelRouter: {e}")
        
        # Check Orchestrator
        try:
            orchestrator = get_unified_orchestrator()
            diagnostics_data["orchestrator"]["ready"] = getattr(orchestrator, "_is_ready", False)
            diagnostics_data["orchestrator"]["error"] = getattr(orchestrator, "_readiness_error", None)
        except Exception as e:
            diagnostics_data["orchestrator"]["error"] = str(e)
            logger.error(f"Error checking orchestrator: {e}")
        
        return diagnostics_data
    
    except Exception as e:
        logger.error(f"Diagnostics error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        diagnostics_data["error"] = str(e)
        return diagnostics_data


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