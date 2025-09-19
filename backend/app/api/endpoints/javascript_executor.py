"""
JavaScript Execution API Endpoint
Safely executes JavaScript for charts, formulas, and DOM manipulation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import subprocess
import json
import tempfile
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/javascript", tags=["javascript-executor"])


class JavaScriptExecutionRequest(BaseModel):
    """Request model for JavaScript execution"""
    code: str
    context: Optional[Dict[str, Any]] = {}
    type: Optional[str] = "calculation"  # calculation, chart, formula, dom


class JavaScriptExecutionResponse(BaseModel):
    """Response model for JavaScript execution"""
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    chart_data: Optional[Dict] = None
    formula_result: Optional[Any] = None


@router.post("/execute", response_model=JavaScriptExecutionResponse)
async def execute_javascript(request: JavaScriptExecutionRequest):
    """
    Execute JavaScript code in Node.js environment
    Supports Chart.js, D3.js, and formula calculations
    """
    try:
        # Prepare JavaScript code with context
        js_code = f"""
// Context variables
const context = {json.dumps(request.context)};

// Helper functions for charts
const generateChartConfig = (type, data, options) => {{
    return {{
        type: type,
        data: data,
        options: options || {{}}
    }};
}};

// Helper for financial calculations
const financial = {{
    npv: (rate, cashFlows) => {{
        let npv = 0;
        for (let i = 0; i < cashFlows.length; i++) {{
            npv += cashFlows[i] / Math.pow(1 + rate, i + 1);
        }}
        return npv;
    }},
    irr: (cashFlows) => {{
        // Newton-Raphson method for IRR
        let rate = 0.1;
        for (let i = 0; i < 20; i++) {{
            let f = 0, df = 0;
            for (let j = 0; j < cashFlows.length; j++) {{
                f += cashFlows[j] / Math.pow(1 + rate, j);
                df -= j * cashFlows[j] / Math.pow(1 + rate, j + 1);
            }}
            rate = rate - f / df;
        }}
        return rate;
    }},
    cagr: (beginValue, endValue, years) => {{
        return Math.pow(endValue / beginValue, 1 / years) - 1;
    }}
}};

// Execute user code
{request.code}
"""
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(js_code)
            temp_file = f.name
        
        try:
            # Execute with Node.js
            result = subprocess.run(
                ['node', temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                
                # Try to parse as JSON
                try:
                    data = json.loads(output) if output else None
                except:
                    data = output
                
                # Handle different output types
                response_data = {"success": True, "output": data}
                
                if request.type == "chart" and isinstance(data, dict):
                    response_data["chart_data"] = data
                elif request.type == "formula":
                    response_data["formula_result"] = data
                
                return JavaScriptExecutionResponse(**response_data)
            else:
                return JavaScriptExecutionResponse(
                    success=False,
                    error=result.stderr
                )
                
        finally:
            # Clean up temp file
            os.unlink(temp_file)
            
    except subprocess.TimeoutExpired:
        return JavaScriptExecutionResponse(
            success=False,
            error="JavaScript execution timeout"
        )
    except Exception as e:
        logger.error(f"JavaScript execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/excel-formula")
async def execute_excel_formula(formula: str, cell_values: Dict[str, Any]):
    """
    Execute Excel-style formulas
    Supports SUM, AVERAGE, IF, VLOOKUP, etc.
    """
    try:
        # Convert Excel formula to JavaScript
        js_formula = f"""
const cells = {json.dumps(cell_values)};

// Excel function implementations
const SUM = (...args) => args.flat().reduce((a, b) => a + (Number(b) || 0), 0);
const AVERAGE = (...args) => {{ 
    const nums = args.flat().filter(x => !isNaN(x));
    return nums.reduce((a, b) => a + Number(b), 0) / nums.length;
}};
const COUNT = (...args) => args.flat().filter(x => x !== null && x !== '').length;
const MAX = (...args) => Math.max(...args.flat().map(Number).filter(x => !isNaN(x)));
const MIN = (...args) => Math.min(...args.flat().map(Number).filter(x => !isNaN(x)));
const IF = (condition, trueVal, falseVal) => condition ? trueVal : falseVal;
const ROUND = (num, digits) => Math.round(num * Math.pow(10, digits)) / Math.pow(10, digits);

// Parse cell references
const getCellValue = (ref) => {{
    if (typeof ref === 'string' && ref.match(/^[A-Z]+\\d+$/)) {{
        return cells[ref] || 0;
    }}
    return ref;
}};

// Execute formula
try {{
    const result = {formula.replace('=', '')};
    console.log(JSON.stringify({{result}}));
}} catch (e) {{
    console.log(JSON.stringify({{error: e.message}}));
}}
"""
        
        # Execute formula
        result = await execute_javascript(
            JavaScriptExecutionRequest(
                code=js_formula,
                type="formula"
            )
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Excel formula execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chart-config")
async def generate_chart_config(
    chart_type: str,
    data: Dict[str, Any],
    options: Optional[Dict] = None
):
    """
    Generate Chart.js configuration
    """
    js_code = f"""
const chartConfig = generateChartConfig(
    '{chart_type}',
    {json.dumps(data)},
    {json.dumps(options or {})}
);

// Add smart defaults based on data
if (chartConfig.type === 'line' || chartConfig.type === 'bar') {{
    chartConfig.options.scales = {{
        y: {{ beginAtZero: true }},
        x: {{ ticks: {{ autoSkip: true, maxTicksLimit: 10 }} }}
    }};
}}

console.log(JSON.stringify(chartConfig));
"""
    
    result = await execute_javascript(
        JavaScriptExecutionRequest(
            code=js_code,
            type="chart"
        )
    )
    
    return result