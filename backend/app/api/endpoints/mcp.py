"""
MCP API Endpoints
Endpoints for MCP tool orchestration (Tavily & Firecrawl)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
import json
import asyncio

from app.services.mcp_orchestrator import mcp_orchestrator, TaskType, ToolType
from app.core.config import settings

router = APIRouter(prefix="/mcp", tags=["MCP"])


class MCPRequest(BaseModel):
    """Request model for MCP processing"""
    prompt: str = Field(..., description="User prompt to process")
    context: Optional[Dict] = Field(None, description="Additional context")
    stream: bool = Field(False, description="Stream results")
    auto_decompose: bool = Field(True, description="Automatically decompose prompt")
    tools: Optional[List[str]] = Field(None, description="Specific tools to use")


class TaskRequest(BaseModel):
    """Request model for specific task execution"""
    task_type: TaskType = Field(..., description="Type of task")
    tool: ToolType = Field(..., description="Tool to use")
    parameters: Dict = Field(..., description="Task parameters")
    description: Optional[str] = Field(None, description="Task description")


class SynthesisRequest(BaseModel):
    """Request model for result synthesis"""
    plan_id: str = Field(..., description="Execution plan ID")
    synthesis_prompt: Optional[str] = Field(None, description="Custom synthesis prompt")


@router.post("/process")
async def process_prompt(request: MCPRequest):
    """
    Process a user prompt using a single Claude agent with MCP tools
    
    This endpoint uses ONE continuous Claude conversation that:
    1. Decomposes the prompt internally
    2. Gathers data using tool calls
    3. Analyzes data using tool calls
    4. Formats and returns the final result
    
    All in a single API call with tool usage.
    """
    try:
        # Determine output format from context
        output_format = "analysis"  # default
        if request.context:
            output_format = request.context.get("output_format", "analysis")
        
        # STREAMING DISABLED - Always use non-streaming response
        # if request.stream:
        #     # Streaming functionality has been disabled
        #     # Fall through to non-streaming response
        
        # Execute with single agent (non-streaming)
        result = await single_agent.execute_as_single_agent(
            prompt=request.prompt,
            context=request.context,
            output_format=output_format,
            stream=False
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decompose")
async def decompose_prompt(request: MCPRequest):
    """
    Decompose a prompt into tasks without executing
    
    Useful for:
    - Understanding how the system will process a prompt
    - Reviewing task plan before execution
    - Custom task modification
    """
    try:
        tasks = await mcp_orchestrator.decomposer.decompose(
            prompt=request.prompt,
            context=request.context
        )
        
        return {
            "prompt": request.prompt,
            "task_count": len(tasks),
            "tasks": [
                {
                    "id": task.id,
                    "type": task.type.value,
                    "description": task.description,
                    "tool": task.tool.value,
                    "parameters": task.parameters,
                    "dependencies": task.dependencies,
                    "priority": task.priority
                }
                for task in tasks
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent")
async def single_agent_endpoint(request: MCPRequest):
    """
    Direct endpoint for single agent execution
    Uses one Claude conversation with tool calls for the entire analysis chain
    """
    try:
        output_format = request.context.get("output_format", "analysis") if request.context else "analysis"
        
        result = await single_agent.execute_as_single_agent(
            prompt=request.prompt,
            context=request.context,
            output_format=output_format,
            stream=request.stream
        )
        
        if request.stream and hasattr(result, '__aiter__'):
            async def generate():
                async for chunk in result:
                    yield f"data: {json.dumps(chunk)}\n\n"
            return StreamingResponse(generate(), media_type="text/event-stream")
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-task")
async def execute_single_task(request: TaskRequest):
    """
    Execute a single task directly
    
    Allows fine-grained control over task execution
    """
    try:
        from app.services.mcp_orchestrator import MCPToolExecutor, Task
        
        # Create task
        task = Task(
            id="manual_task",
            type=request.task_type,
            description=request.description or f"Manual {request.task_type.value}",
            tool=request.tool,
            parameters=request.parameters
        )
        
        # Execute
        async with MCPToolExecutor() as executor:
            if task.tool == ToolType.TAVILY:
                result = await executor.execute_tavily(task.parameters)
            elif task.tool == ToolType.FIRECRAWL:
                result = await executor.execute_firecrawl(task.parameters)
            else:
                result = await executor.execute_hybrid(task.parameters)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan/{plan_id}")
async def get_plan_status(plan_id: str):
    """Get status of an execution plan"""
    result = await mcp_orchestrator.get_plan_status(plan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result


@router.post("/synthesize")
async def synthesize_results(request: SynthesisRequest):
    """
    Synthesize results from an execution plan
    
    Combines results from multiple tasks into a coherent summary
    """
    try:
        result = await mcp_orchestrator.synthesize_results(
            plan_id=request.plan_id,
            synthesis_prompt=request.synthesis_prompt
        )
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/status")
async def get_tools_status():
    """Check status of MCP tools"""
    return {
        "tavily": {
            "configured": bool(settings.TAVILY_API_KEY),
            "api_key_prefix": settings.TAVILY_API_KEY[:10] + "..." if settings.TAVILY_API_KEY else None
        },
        "firecrawl": {
            "configured": bool(settings.FIRECRAWL_API_KEY),
            "api_key_prefix": settings.FIRECRAWL_API_KEY[:10] + "..." if settings.FIRECRAWL_API_KEY else None
        }
    }


@router.get("/task-types")
async def get_task_types():
    """Get available task types and their configurations"""
    return {
        "task_types": [
            {
                "type": task_type.value,
                "description": f"Perform {task_type.value.replace('_', ' ')}"
            }
            for task_type in TaskType
        ],
        "tool_types": [tool.value for tool in ToolType]
    }


@router.post("/test")
async def test_mcp_integration():
    """Test MCP integration with a simple example"""
    try:
        # Test prompt that uses both tools
        test_prompt = "Research the AI startup landscape and analyze Anthropic's website"
        
        # Collect results from async generator
        results = []
        async for result in mcp_orchestrator.process_prompt(
            prompt=test_prompt,
            context={"test": True},
            stream=False
        ):
            results.append(result)
        
        # Get the final result
        final_result = results[-1] if results else {}
        
        return {
            "success": True,
            "test_prompt": test_prompt,
            "tasks_executed": final_result.get("tasks_executed", 0),
            "execution_time": final_result.get("execution_time", 0),
            "summary": "MCP integration test completed successfully"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "MCP integration test failed"
        }