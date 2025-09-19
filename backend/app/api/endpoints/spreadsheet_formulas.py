"""
Spreadsheet Formulas Engine Endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from app.services.spreadsheet_formula_engine import SpreadsheetFormulaEngine

router = APIRouter()
logger = logging.getLogger(__name__)


class FormulaCalculationRequest(BaseModel):
    formula: str
    data: Dict[str, Any] = {}
    context: Dict[str, Any] = {}


class BatchFormulaRequest(BaseModel):
    formulas: List[Dict[str, Any]]
    data: Dict[str, Any] = {}
    context: Dict[str, Any] = {}


@router.post("/calculate")
async def calculate_formula(request: FormulaCalculationRequest):
    """Calculate a single spreadsheet formula"""
    try:
        formula_engine = SpreadsheetFormulaEngine()
        
        result = await formula_engine.calculate(
            formula=request.formula,
            data=request.data,
            context=request.context
        )
        
        return {
            "success": True,
            "formula": request.formula,
            "result": result,
            "data_used": request.data
        }
        
    except Exception as e:
        logger.error(f"Formula calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-batch")
async def calculate_batch_formulas(request: BatchFormulaRequest):
    """Calculate multiple formulas in batch"""
    try:
        formula_engine = SpreadsheetFormulaEngine()
        results = []
        
        for formula_item in request.formulas:
            try:
                result = await formula_engine.calculate(
                    formula=formula_item.get("formula", ""),
                    data={**request.data, **formula_item.get("data", {})},
                    context={**request.context, **formula_item.get("context", {})}
                )
                results.append({
                    "success": True,
                    "formula": formula_item.get("formula"),
                    "result": result,
                    "cell": formula_item.get("cell", "")
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "formula": formula_item.get("formula"),
                    "error": str(e),
                    "cell": formula_item.get("cell", "")
                })
        
        return {
            "success": True,
            "results": results,
            "total_formulas": len(request.formulas),
            "successful": len([r for r in results if r["success"]])
        }
        
    except Exception as e:
        logger.error(f"Batch formula calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/functions")
async def get_supported_functions():
    """Get list of supported spreadsheet functions"""
    return {
        "categories": {
            "Math": ["SUM", "AVERAGE", "COUNT", "MIN", "MAX", "ROUND", "ABS", "POWER"],
            "Financial": ["NPV", "IRR", "PMT", "PV", "FV", "RATE"],
            "Logical": ["IF", "AND", "OR", "NOT", "IFERROR"],
            "Text": ["CONCATENATE", "LEN", "LEFT", "RIGHT", "MID", "UPPER", "LOWER"],
            "Date": ["TODAY", "NOW", "DATE", "YEAR", "MONTH", "DAY"],
            "Lookup": ["VLOOKUP", "INDEX", "MATCH", "OFFSET"]
        },
        "examples": {
            "NPV": "=NPV(0.1, 1000, 1200, 1440)",
            "IRR": "=IRR(-1000, 300, 420, 680)",
            "SUM": "=SUM(A1:A10)",
            "IF": "=IF(A1>100, 'High', 'Low')"
        }
    }


@router.post("/validate")
async def validate_formula(formula: str):
    """Validate formula syntax without executing"""
    try:
        formula_engine = SpreadsheetFormulaEngine()
        
        # Basic validation (could be enhanced)
        is_valid = formula.startswith("=") and len(formula) > 1
        
        return {
            "formula": formula,
            "valid": is_valid,
            "message": "Valid formula syntax" if is_valid else "Invalid formula syntax"
        }
        
    except Exception as e:
        logger.error(f"Formula validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))