"""
Deal Sourcing API Routes
Endpoints for intelligent investment opportunity discovery.

Wired to sourcing_service.py (query_companies, score_companies, generate_rubric)
instead of the non-existent IntelligentDealSourcing stub.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from ..services.sourcing_service import (
    query_companies,
    score_companies,
    generate_rubric,
)

router = APIRouter(prefix="/deal-sourcing", tags=["deal-sourcing"])


# ---------------------------------------------------------------------------
# Request model (replaces the old DealSourcingRequest from the dead module)
# ---------------------------------------------------------------------------
class DealSourcingRequest(BaseModel):
    target_stage: Optional[str] = None
    sectors: Optional[List[str]] = None
    geography: Optional[str] = None
    min_revenue: Optional[float] = None
    max_revenue: Optional[float] = None
    thesis: Optional[str] = None
    limit: int = Field(default=25, le=100)


# ---------------------------------------------------------------------------
# Funding stage timing benchmarks (static reference data)
# ---------------------------------------------------------------------------
FUNDING_PATTERNS: Dict[str, Dict[str, Any]] = {
    "Seed":     {"from_stage": "Pre-Seed", "min_months": 6,  "max_months": 18},
    "Series A": {"from_stage": "Seed",     "min_months": 12, "max_months": 24},
    "Series B": {"from_stage": "Series A", "min_months": 18, "max_months": 30},
    "Series C": {"from_stage": "Series B", "min_months": 18, "max_months": 36},
    "Growth":   {"from_stage": "Series C", "min_months": 24, "max_months": 48},
}


@router.post("/find-candidates")
async def find_investment_candidates(request: DealSourcingRequest) -> Dict[str, Any]:
    """
    Find companies matching investment criteria.

    Builds filters from the request, queries the DB, scores results with the
    rubric engine, and returns ranked candidates.

    Example bodies:
    - {"target_stage": "Series A", "sectors": ["SaaS", "AI"], "geography": "NYC"}
    - {"thesis": "Capital-efficient B2B SaaS in healthcare", "limit": 20}
    """
    try:
        # Build filters from request fields
        filters: Dict[str, Any] = {}
        if request.sectors:
            filters["sector"] = request.sectors[0]  # primary sector filter
        if request.geography:
            filters["geography"] = request.geography
        if request.target_stage:
            filters["stage"] = request.target_stage
        if request.min_revenue is not None:
            filters["arr_min"] = request.min_revenue
        if request.max_revenue is not None:
            filters["arr_max"] = request.max_revenue

        # If a thesis is provided, generate a rubric and merge its filters
        rubric = None
        weights = None
        if request.thesis:
            rubric = generate_rubric(
                thesis_description=request.thesis,
                target_stage=request.target_stage,
                filters=filters,
            )
            rubric_filters = rubric.get("filters", {})
            for key in ("sector", "stage", "geography", "arr_min", "arr_max"):
                if rubric_filters.get(key) and not filters.get(key):
                    filters[key] = rubric_filters[key]
            weights = rubric.get("weights")

        # Query DB
        db_result = await query_companies(
            filters=filters,
            sort_by="name",
            sort_desc=True,
            limit=request.limit * 2,
        )
        companies = db_result.get("companies", [])

        # Score and rank
        scored = score_companies(
            companies,
            weights=weights,
            target_stage=request.target_stage,
        )

        # Trim to requested limit
        scored = scored[: request.limit]

        return {
            "success": True,
            "data": {
                "companies": scored,
                "count": len(scored),
                "filters_applied": filters,
            },
            "message": f"Found {len(scored)} candidates"
            + (f" for {request.target_stage}" if request.target_stage else ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding-patterns")
async def get_funding_patterns() -> Dict[str, Any]:
    """Get funding stage patterns and timing benchmarks."""
    return {
        "patterns": FUNDING_PATTERNS,
        "description": "Typical time between funding rounds by stage",
    }


@router.post("/search-preview")
async def preview_search_strategy(
    target_stage: str = Query(...),
    sectors: Optional[List[str]] = Query(default=None),
    geography: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """
    Preview the search strategy without executing searches.
    Shows what filters and rubric would be generated for the given criteria.
    """
    try:
        pattern = FUNDING_PATTERNS.get(target_stage)
        if not pattern:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown stage: {target_stage}. Valid: {list(FUNDING_PATTERNS.keys())}",
            )

        filters: Dict[str, Any] = {"stage": pattern["from_stage"]}
        if sectors:
            filters["sector"] = sectors[0]
        if geography:
            filters["geography"] = geography

        thesis = f"{target_stage} companies"
        if sectors:
            thesis += f" in {', '.join(sectors)}"
        if geography:
            thesis += f" based in {geography}"

        rubric = generate_rubric(
            thesis_description=thesis,
            target_stage=target_stage,
            filters=filters,
        )

        return {
            "target_stage": target_stage,
            "previous_stage": pattern["from_stage"],
            "timing_window": f"{pattern['min_months']}-{pattern['max_months']} months between rounds",
            "filters": rubric.get("filters", filters),
            "weights": rubric.get("weights", {}),
            "intent": rubric.get("intent", "dealflow"),
            "data_sources": ["Supabase companies table", "Web discovery (if invoked via orchestrator)"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
