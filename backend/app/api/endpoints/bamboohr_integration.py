"""BambooHR integration endpoints — API key connection, headcount/comp sync.

Endpoints:
  POST /integrations/bamboohr/connect              → Connect via API key
  GET  /integrations/bamboohr/connections            → List connections
  DELETE /integrations/bamboohr/connections/{id}     → Disconnect
  POST /integrations/bamboohr/sync                  → Pull HR data → fpa_actuals
  GET  /integrations/bamboohr/sync-status/{id}      → Check sync progress
"""

import logging
from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.integrations.connection_manager import (
    delete_connection,
    ensure_valid_token,
    get_connection,
    get_connections,
    save_connection,
    update_sync_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/bamboohr", tags=["bamboohr"])

PROVIDER = "bamboohr"


# ---------------------------------------------------------------------------
# Connect (API key — no OAuth)
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    user_id: str = Field(..., description="Current user ID")
    api_key: str = Field(..., description="BambooHR API key")
    subdomain: str = Field(..., description="BambooHR subdomain, e.g. mycompany")
    company_name: str = Field("", description="Display name")


@router.post("/connect")
async def connect_bamboohr(request: ConnectRequest) -> Dict[str, Any]:
    """Connect to BambooHR via API key validation."""
    from app.services.integrations.bamboohr.auth import validate_api_key

    validation = await validate_api_key(request.api_key, request.subdomain)
    if not validation.get("success"):
        raise HTTPException(status_code=400, detail=validation.get("error", "API key validation failed"))

    conn = save_connection(
        user_id=request.user_id,
        provider=PROVIDER,
        tenant_id=request.subdomain,
        tenant_name=request.company_name or request.subdomain,
        access_token=request.api_key,
        refresh_token=None,
        expires_in=365 * 24 * 3600,  # API keys don't expire
        extra_fields={
            "extra_data": {"subdomain": request.subdomain},
        },
    )

    logger.info(
        "BambooHR connected: %s (%d employees) for user %s",
        request.subdomain, validation.get("employee_count", 0), request.user_id,
    )
    return {"success": True, "connection": conn, "employee_count": validation.get("employee_count", 0)}


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

@router.get("/connections")
async def list_connections(user_id: str = Query(...)) -> Dict[str, Any]:
    connections = get_connections(user_id, provider=PROVIDER)
    return {"success": True, "connections": connections}


@router.delete("/connections/{connection_id}")
async def remove_connection(connection_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    deleted = delete_connection(connection_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"success": True, "message": "BambooHR connection removed"}


# ---------------------------------------------------------------------------
# Data sync
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    connection_id: str = Field(..., description="Connection UUID")
    user_id: str = Field(..., description="Current user ID")
    company_id: str = Field(..., description="Target company ID in fpa_actuals")


@router.post("/sync")
async def trigger_sync(request: SyncRequest) -> Dict[str, Any]:
    """Pull BambooHR headcount/comp data → fpa_actuals as OpEx subcategories."""
    from app.core.supabase_client import get_supabase_client
    from app.services.integrations.bamboohr.client import BambooHRClient
    from app.services.integrations.bamboohr.parser import parse_employees_to_fpa_rows

    connection = get_connection(request.connection_id, request.user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Not a BambooHR connection")

    update_sync_status(request.connection_id, "syncing")

    # API key auth — no token refresh needed
    api_key = connection["access_token"]
    extra = connection.get("extra_data") or {}
    subdomain = extra.get("subdomain", connection["tenant_id"])

    client = BambooHRClient(api_key, subdomain)

    today = date.today()
    period = today.strftime("%Y-%m-01")

    try:
        # Fetch employee data via custom report (headcount + comp fields)
        employees = await client.get_custom_report([
            "id", "firstName", "lastName", "department", "division",
            "location", "jobTitle", "status", "hireDate", "terminationDate",
            "payRate", "payType", "payPer",
        ])

        all_rows = parse_employees_to_fpa_rows(
            employees, request.company_id, period,
            fund_id=connection.get("fund_id"),
        )
    except Exception as e:
        update_sync_status(request.connection_id, "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))

    if not all_rows:
        update_sync_status(request.connection_id, "idle")
        return {"success": True, "rows_synced": 0, "periods": []}

    # Upsert into fpa_actuals
    sb = get_supabase_client()
    if not sb:
        update_sync_status(request.connection_id, "error", "Database unavailable")
        raise HTTPException(status_code=500, detail="Database unavailable")

    row_dicts = [r.to_dict() for r in all_rows]
    sb.table("fpa_actuals").upsert(
        row_dicts,
        on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
    ).execute()

    update_sync_status(request.connection_id, "idle")

    logger.info("BambooHR sync: %d rows for period %s", len(all_rows), period)
    return {"success": True, "rows_synced": len(all_rows), "periods": [period]}


@router.get("/sync-status/{connection_id}")
async def get_sync_status(connection_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    connection = get_connection(connection_id, user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {
        "success": True,
        "sync_status": connection.get("sync_status", "idle"),
        "sync_error": connection.get("sync_error"),
        "last_sync_at": connection.get("last_sync_at"),
    }
