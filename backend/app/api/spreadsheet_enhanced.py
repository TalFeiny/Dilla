"""
Enhanced Spreadsheet API with advanced formula support
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from app.services.enhanced_spreadsheet_agent import spreadsheet_agent, FormulaParser

logger = logging.getLogger(__name__)

router = APIRouter()


class CellUpdate(BaseModel):
    cell_ref: str
    value: Any
    is_formula: bool = False


class SpreadsheetRequest(BaseModel):
    updates: List[CellUpdate]
    recalculate: bool = True


class FormulaRequest(BaseModel):
    formula: str
    cell_values: Optional[Dict[str, Any]] = {}
    named_ranges: Optional[Dict[str, List[Any]]] = {}


class FinancialModelRequest(BaseModel):
    company_data: Dict[str, Any]
    model_type: str = "standard"  # standard, dcf, three_statement
    years: int = 5


@router.post("/evaluate-formula")
async def evaluate_formula(request: FormulaRequest):
    """
    Evaluate a single formula with provided cell values
    """
    try:
        parser = FormulaParser()
        
        # Set cell values
        for cell_ref, value in request.cell_values.items():
            parser.set_cell_value(cell_ref, value)
            
        # Set named ranges
        for name, values in request.named_ranges.items():
            parser.set_named_range(name, values)
            
        # Parse and evaluate formula
        result = parser.parse_formula(request.formula)
        
        return {
            "formula": request.formula,
            "result": result,
            "type": type(result).__name__
        }
        
    except Exception as e:
        logger.error(f"Formula evaluation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/update-spreadsheet")
async def update_spreadsheet(request: SpreadsheetRequest):
    """
    Update multiple cells in a spreadsheet and recalculate
    """
    try:
        # Apply updates
        for update in request.updates:
            spreadsheet_agent.set_cell(
                update.cell_ref,
                update.value,
                update.is_formula
            )
            
        # Recalculate if requested
        if request.recalculate:
            spreadsheet_agent.recalculate()
            
        # Return current state
        return {
            "grid_data": spreadsheet_agent.grid_data,
            "formulas": spreadsheet_agent.formulas,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Spreadsheet update error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-financial-model")
async def create_financial_model(request: FinancialModelRequest):
    """
    Create a financial model from company data
    """
    try:
        # Create the model
        model = spreadsheet_agent.create_financial_model(request.company_data)
        
        # Generate summary metrics
        summary = {
            "revenue_projections": [],
            "profit_margins": [],
            "growth_rates": []
        }
        
        for year in range(1, request.years + 1):
            year_col = f"Y{year}"
            
            # Get revenue
            revenue = model.get(f"{year_col}_REVENUE", {}).get("value", 0)
            summary["revenue_projections"].append(revenue)
            
            # Get profit margin
            net_income = model.get(f"{year_col}_NET_INCOME", {}).get("value", 0)
            if revenue > 0:
                margin = net_income / revenue
                summary["profit_margins"].append(margin)
                
            # Calculate growth rate
            if year > 1:
                prev_revenue = summary["revenue_projections"][year - 2]
                if prev_revenue > 0:
                    growth = (revenue - prev_revenue) / prev_revenue
                    summary["growth_rates"].append(growth)
                    
        return {
            "model": model,
            "summary": summary,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Financial model creation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/formula-functions")
async def get_formula_functions():
    """
    Get list of available formula functions
    """
    from app.services.enhanced_spreadsheet_agent import FormulaParser
    
    functions = list(FormulaParser.FUNCTIONS.keys())
    
    # Group by category
    categories = {
        "Math": ["SUM", "AVERAGE", "MIN", "MAX", "COUNT", "ROUND", "ROUNDUP", 
                 "ROUNDDOWN", "ABS", "POWER", "SQRT", "LOG", "LN", "EXP", "MOD"],
        "Statistical": ["MEDIAN", "MODE", "STDEV", "VAR"],
        "Financial": ["NPV", "IRR", "PV", "FV", "PMT", "RATE"],
        "Date": ["TODAY", "NOW", "DATE", "YEAR", "MONTH", "DAY", "DAYS"],
        "Logical": ["IF", "AND", "OR", "NOT", "IFERROR"],
        "Text": ["CONCATENATE", "LEN", "UPPER", "LOWER", "TRIM", "LEFT", 
                 "RIGHT", "MID", "FIND", "REPLACE"],
        "Lookup": ["VLOOKUP", "HLOOKUP", "INDEX", "MATCH"]
    }
    
    return {
        "functions": functions,
        "categories": categories,
        "total": len(functions)
    }


@router.post("/validate-formula")
async def validate_formula(formula: str):
    """
    Validate a formula syntax without evaluating
    """
    try:
        parser = FormulaParser()
        
        # Try to parse without evaluating
        # Remove leading '=' if present
        if formula.startswith('='):
            formula = formula[1:]
            
        # Check for basic syntax issues
        issues = []
        
        # Check parentheses balance
        open_parens = formula.count('(')
        close_parens = formula.count(')')
        if open_parens != close_parens:
            issues.append(f"Unbalanced parentheses: {open_parens} open, {close_parens} close")
            
        # Check for invalid characters
        invalid_chars = set(formula) - set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-*/()[]{}:,." \'$=<>!&|%')
        if invalid_chars:
            issues.append(f"Invalid characters found: {invalid_chars}")
            
        # Check for function names
        import re
        function_pattern = r'([A-Z]+)\s*\('
        functions_used = re.findall(function_pattern, formula, re.IGNORECASE)
        
        unknown_functions = []
        for func in functions_used:
            if func.upper() not in FormulaParser.FUNCTIONS:
                unknown_functions.append(func)
                
        if unknown_functions:
            issues.append(f"Unknown functions: {unknown_functions}")
            
        return {
            "formula": formula,
            "valid": len(issues) == 0,
            "issues": issues,
            "functions_used": list(set(f.upper() for f in functions_used))
        }
        
    except Exception as e:
        return {
            "formula": formula,
            "valid": False,
            "issues": [str(e)],
            "functions_used": []
        }