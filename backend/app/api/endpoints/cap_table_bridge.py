"""
Cap Table Bridge API Endpoints

Builds cap tables from document extraction, supports recalculation from
edited share entries, and scenario simulation (new rounds, exit waterfalls).

Also serves the cap_table_entries ledger (CRUD + CSV import).
"""

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
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


class EntryUpsertRequest(BaseModel):
    company_id: str
    entry: Dict[str, Any]


class BulkUpsertRequest(BaseModel):
    company_id: str
    fund_id: Optional[str] = None
    entries: List[Dict[str, Any]]
    source: str = "manual"


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


# ---------------------------------------------------------------------------
# Cap Table Entries Ledger — CRUD + CSV import
# ---------------------------------------------------------------------------

@router.get("/cap-table-entries")
async def get_cap_table_entries(
    company_id: str = Query(...),
    fund_id: Optional[str] = Query(None),
    view: str = Query("company"),
):
    """Load all cap table entries for a company with computed aggregates."""
    try:
        from app.services.cap_table_ledger import CapTableLedger
        ledger = CapTableLedger()
        result = ledger.load(company_id=company_id, fund_id=fund_id, view=view)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("[CAP_TABLE_ENTRIES] Load failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cap-table-entries")
async def upsert_cap_table_entry(req: EntryUpsertRequest):
    """Upsert a single cap table entry (manual grid edit)."""
    try:
        from app.services.cap_table_ledger import CapTableLedger
        ledger = CapTableLedger()
        result = ledger.upsert_row(company_id=req.company_id, entry=req.entry)
        if not result.get("success"):
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("[CAP_TABLE_ENTRIES] Upsert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cap-table-entries/bulk")
async def bulk_upsert_cap_table_entries(req: BulkUpsertRequest):
    """Bulk upsert cap table entries (programmatic import)."""
    try:
        from app.services.cap_table_ledger import CapTableLedger
        ledger = CapTableLedger()
        result = ledger.bulk_upsert(
            company_id=req.company_id,
            entries=req.entries,
            fund_id=req.fund_id,
            source=req.source,
        )
        if not result.get("success"):
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("[CAP_TABLE_ENTRIES] Bulk upsert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cap-table-entries/upload-csv")
async def upload_cap_table_csv(
    company_id: str = Form(...),
    fund_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """Parse a cap table CSV and bulk-insert into cap_table_entries."""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        from app.services.cap_table_csv_parser import parse_cap_table_csv
        from app.services.cap_table_ledger import CapTableLedger

        entries = parse_cap_table_csv(content)
        if not entries:
            return JSONResponse(
                status_code=200,
                content={"success": False, "reason": "no_entries_parsed", "rows_parsed": 0},
            )

        ledger = CapTableLedger()
        result = ledger.bulk_upsert(
            company_id=company_id,
            entries=entries,
            fund_id=fund_id,
            source="csv",
        )
        result["rows_parsed"] = len(entries)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[CAP_TABLE_ENTRIES] CSV upload failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cap-table-entries/{entry_id}")
async def delete_cap_table_entry(entry_id: str):
    """Delete a single cap table entry."""
    try:
        from app.services.cap_table_ledger import CapTableLedger
        ledger = CapTableLedger()
        result = ledger.delete_row(entry_id=entry_id)
        if not result.get("success"):
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("[CAP_TABLE_ENTRIES] Delete failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
