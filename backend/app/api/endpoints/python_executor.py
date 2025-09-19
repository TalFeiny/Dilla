"""
Python Execution API Endpoint
Safely executes Python code for analysis and calculations
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
from io import StringIO
import traceback
import json
import re
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/python", tags=["python-executor"])


class PythonExecutionRequest(BaseModel):
    """Request model for Python execution"""
    code: str
    context: Optional[Dict[str, Any]] = {}
    timeout: Optional[int] = 30


class PythonExecutionResponse(BaseModel):
    """Response model for Python execution"""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Dict] = None


@router.post("/execute", response_model=PythonExecutionResponse)
async def execute_python(request: PythonExecutionRequest):
    """
    Execute Python code in a controlled environment
    """
    try:
        # Create a restricted globals environment
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "float": float,
                "int": int,
                "str": str,
                "list": list,
                "dict": dict,
                "set": set,
                "sorted": sorted,
                "enumerate": enumerate,
                "zip": zip,
            },
            "json": json,
            "re": re,
            "np": np,
            "pd": pd,
            "context": request.context,
        }
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = output_buffer = StringIO()
        
        try:
            # Execute the code
            exec(request.code, safe_globals)
            
            # Get the output
            output = output_buffer.getvalue()
            
            # Try to parse as JSON if it looks like JSON
            data = None
            if output.strip().startswith("{") or output.strip().startswith("["):
                try:
                    data = json.loads(output.strip())
                except:
                    pass
            
            return PythonExecutionResponse(
                success=True,
                output=output,
                data=data
            )
            
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            
    except Exception as e:
        logger.error(f"Python execution error: {e}")
        return PythonExecutionResponse(
            success=False,
            error=str(e),
            output=traceback.format_exc()
        )


@router.post("/analyze-funding")
async def analyze_funding_data(data: Dict):
    """
    Specialized endpoint for analyzing funding data
    """
    try:
        # Extract funding information
        funding_pattern = r'\$?([\d,]+(?:\.\d+)?)\s*([MmBb]?)(?:illion)?'
        rounds_pattern = r'(Seed|Pre-[Ss]eed|Series\s+[A-Z])'
        
        total_raised = 0
        rounds = []
        investors = set()
        
        # Process text content
        content = str(data.get("content", ""))
        
        # Find funding amounts
        amounts = re.findall(funding_pattern, content)
        for amount, unit in amounts:
            value = float(amount.replace(',', ''))
            if unit.upper() == 'B':
                value *= 1000  # Convert to millions
            elif unit.upper() == 'M':
                pass  # Already in millions
            else:
                continue  # Skip unclear amounts
            
            if 0 < value < 10000:  # Sanity check
                total_raised = max(total_raised, value)
        
        # Find rounds
        round_matches = re.findall(rounds_pattern, content)
        rounds = list(set(round_matches))
        
        # Find investors
        investor_patterns = [
            r'led by ([A-Z][a-zA-Z\s&]+(?:Capital|Ventures|Partners|Fund))',
            r'investors include ([^.]+)',
            r'backed by ([^.]+)'
        ]
        
        for pattern in investor_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Clean up investor names
                for inv in re.split(r',|and|\s+and\s+', match):
                    inv = inv.strip()
                    if 3 < len(inv) < 50:
                        investors.add(inv)
        
        return {
            "success": True,
            "funding": {
                "total_raised_millions": round(total_raised, 1),
                "rounds": rounds,
                "num_rounds": len(rounds),
                "investors": list(investors)[:20],
                "last_round": rounds[-1] if rounds else "Unknown"
            }
        }
        
    except Exception as e:
        logger.error(f"Funding analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))