"""
Redline impact endpoint — computes financial impact of clause changes in real-time.

Wires to existing ClauseDiffEngine.redline_impact() for the heavy lifting.
Used by the interactive redline editor in MemoEditor.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/legal", tags=["legal"])


class RedlineImpactRequest(BaseModel):
    """Single-clause redline impact request."""
    company_id: str = Field(..., description="Company being analyzed")
    fund_id: Optional[str] = Field(None)
    clause_type: str = Field(..., description="e.g. liquidation_preference, anti_dilution_method")
    original_value: Any = Field(..., description="Current clause value")
    new_value: Any = Field(..., description="Proposed clause value")
    stage: Optional[str] = Field(None, description="Deal stage for benchmarking")
    reference_exits: Optional[List[float]] = Field(
        None, description="Exit values to evaluate impact at"
    )


class RedlineAcceptRequest(BaseModel):
    """Accept a redlined clause change."""
    company_id: str
    fund_id: Optional[str] = None
    document_id: str
    clause_id: str
    clause_type: str
    new_value: Any


@router.post("/redline-impact")
async def compute_redline_impact(request: RedlineImpactRequest):
    """
    Compute financial impact of a single clause change.

    Returns waterfall delta, ownership delta, cost of capital change,
    and benchmark comparison for the proposed value.
    """
    try:
        # Fast path: build minimal parameter sets for before/after
        from app.services.clause_parameter_registry import ResolvedParameterSet
        from app.services.clause_diff_engine import ClauseDiffEngine

        diff_engine = ClauseDiffEngine()

        # Build before/after parameter snapshots with just this clause
        original_params = ResolvedParameterSet()
        original_params.set(request.clause_type, request.original_value, source="current")

        redlined_params = ResolvedParameterSet()
        redlined_params.set(request.clause_type, request.new_value, source="redline")

        # Load existing structure from DB if available
        existing_structure = await _load_existing_structure(
            request.company_id, request.fund_id
        )

        exits = request.reference_exits or [10e6, 25e6, 50e6, 100e6, 200e6, 500e6]

        # Compute diff
        diff_result = diff_engine.diff(
            before=existing_structure.merge(original_params) if existing_structure else original_params,
            after=existing_structure.merge(redlined_params) if existing_structure else redlined_params,
            reference_exits=exits,
        )

        # Also get benchmark comparison
        benchmark = None
        if request.stage:
            from app.services.clause_benchmark_service import benchmark_clause
            benchmark = benchmark_clause(
                request.clause_type, request.new_value, request.stage
            )

        return {
            "success": True,
            "clause_type": request.clause_type,
            "original_value": request.original_value,
            "new_value": request.new_value,
            "impact": {
                "waterfall_delta": diff_result.net_impact.waterfall_delta if diff_result.net_impact else {},
                "ownership_delta": diff_result.net_impact.ownership_delta if diff_result.net_impact else {},
                "cost_of_capital_delta": diff_result.net_impact.cost_of_capital_delta if diff_result.net_impact else None,
                "summary": diff_result.summary,
            },
            "benchmark": {
                "percentile": benchmark.percentile,
                "is_standard": benchmark.is_standard,
                "is_above_market": benchmark.is_above_market,
                "market_range": benchmark.market_range,
                "comparison": benchmark.comparison,
            } if benchmark else None,
        }
    except ImportError as e:
        logger.warning(f"Missing dependency for redline impact: {e}")
        raise HTTPException(status_code=501, detail=f"Redline impact not available: {e}")
    except Exception as e:
        logger.error(f"Redline impact error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/redline-accept")
async def accept_redline(request: RedlineAcceptRequest):
    """Accept a redlined clause — update document_clauses table."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        result = (
            sb.table("document_clauses")
            .update({
                "clause_text": str(request.new_value),
                "updated_at": "now()",
            })
            .eq("document_id", request.document_id)
            .eq("clause_id", request.clause_id)
            .execute()
        )
        return {
            "success": True,
            "updated": len(result.data) if result.data else 0,
        }
    except Exception as e:
        logger.error(f"Redline accept error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_existing_structure(
    company_id: str, fund_id: Optional[str]
):
    """Load the current resolved parameter set from DB for context."""
    try:
        from app.services.clause_parameter_registry import ClauseParameterRegistry
        registry = ClauseParameterRegistry()
        return await registry.resolve(company_id=company_id, fund_id=fund_id)
    except Exception:
        return None
