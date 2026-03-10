"""
Cap Table Bridge API Endpoints

Builds cap tables from document extraction, supports recalculation from
edited share entries, and scenario simulation (new rounds, exit waterfalls).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["cap-table-bridge"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class BuildRequest(BaseModel):
    company_id: str
    fund_id: str
    document_id: Optional[str] = None


class RecalculateRequest(BaseModel):
    share_entries: List[Dict[str, Any]]


class SimulateRequest(BaseModel):
    share_entries: List[Dict[str, Any]]
    investment_amount: float
    pre_money_valuation: float
    option_pool_increase: float = 0
    exit_value: Optional[float] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/cap-table-bridge")
async def build_cap_table(req: BuildRequest):
    """Build cap table from all extracted documents for a company."""
    try:
        from app.services.legal_cap_table_bridge import LegalCapTableBridge
        bridge = LegalCapTableBridge()
        result = bridge.build_from_documents(
            company_id=req.company_id,
            fund_id=req.fund_id,
            trigger_document_id=req.document_id,
        )
        if not result.get("success"):
            return JSONResponse(
                status_code=200,
                content={"success": False, "reason": result.get("reason", "unknown")},
            )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("[CAP_TABLE_BRIDGE] Build failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cap-table-bridge/recalculate")
async def recalculate_cap_table(req: RecalculateRequest):
    """Re-run ownership calculation from edited share entries."""
    try:
        from app.services.legal_cap_table_bridge import LegalCapTableBridge
        bridge = LegalCapTableBridge()
        result = bridge.recalculate(share_entries_json=req.share_entries)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("[CAP_TABLE_BRIDGE] Recalculate failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cap-table-bridge/simulate")
async def simulate_scenario(req: SimulateRequest):
    """Simulate a new financing round and optional exit waterfall."""
    try:
        from app.services.legal_cap_table_bridge import LegalCapTableBridge
        bridge = LegalCapTableBridge()
        result = bridge.simulate(
            share_entries_json=req.share_entries,
            investment_amount=req.investment_amount,
            pre_money_valuation=req.pre_money_valuation,
            option_pool_increase=req.option_pool_increase,
            exit_value=req.exit_value,
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("[CAP_TABLE_BRIDGE] Simulate failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cap-table-bridge/health")
async def health():
    return {"status": "ok", "service": "cap_table_bridge"}
