"""Workday HR integration endpoints — connection management, headcount sync.

Endpoints:
  POST /integrations/workday/connect              → Connect via refresh token
  GET  /integrations/workday/connections            → List connections
  DELETE /integrations/workday/connections/{id}     → Disconnect
  POST /integrations/workday/sync                  → Pull HR data → fpa_actuals
  GET  /integrations/workday/sync-status/{id}      → Check sync progress
"""

import logging
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.integrations.connection_manager import (
    delete_connection,
    ensure_valid_token,
    get_connection,
    get_connections,
    save_connection,
    update_sync_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/workday", tags=["workday"])

PROVIDER = "workday"


# ---------------------------------------------------------------------------
# Connect (no OAuth redirect — admin provides refresh token)
# ---------------------------------------------------------------------------

class ConnectRequest(BaseModel):
    user_id: str = Field(..., description="Current user ID")
    host: str = Field(..., description="Workday host, e.g. wd5-impl-services1.workday.com")
    tenant: str = Field(..., description="Workday tenant ID")
    client_id: str = Field(..., description="API Client ID")
    client_secret: str = Field(..., description="API Client Secret")
    refresh_token: str = Field(..., description="Refresh token from Workday admin")
    headcount_report_url: str = Field("", description="RAAS headcount report URL")
    compensation_report_url: str = Field("", description="RAAS compensation report URL")
    company_name: str = Field("", description="Display name")


@router.post("/connect")
async def connect_workday(request: ConnectRequest) -> Dict[str, Any]:
    """Connect to Workday via refresh token exchange."""
    from app.services.integrations.workday.auth import refresh_access_token

    # Exchange refresh token for access token to validate
    token_result = await refresh_access_token(
        refresh_token=request.refresh_token,
        client_id=request.client_id,
        client_secret=request.client_secret,
        host=request.host,
        tenant=request.tenant,
    )

    if not token_result.get("success"):
        raise HTTPException(status_code=400, detail=token_result.get("error", "Token exchange failed"))

    conn = save_connection(
        user_id=request.user_id,
        provider=PROVIDER,
        tenant_id=request.tenant,
        tenant_name=request.company_name or request.tenant,
        access_token=token_result["access_token"],
        refresh_token=token_result.get("refresh_token", request.refresh_token),
        expires_in=token_result.get("expires_in", 3600),
        extra_fields={
            "extra_data": {
                "host": request.host,
                "tenant": request.tenant,
                "client_id": request.client_id,
                "client_secret": request.client_secret,
                "headcount_report_url": request.headcount_report_url,
                "compensation_report_url": request.compensation_report_url,
            },
        },
    )

    logger.info("Workday connected: %s for user %s", request.tenant, request.user_id)
    return {"success": True, "connection": conn}


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
    return {"success": True, "message": "Workday connection removed"}


# ---------------------------------------------------------------------------
# Data sync
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    connection_id: str = Field(..., description="Connection UUID")
    user_id: str = Field(..., description="Current user ID")
    company_id: str = Field(..., description="Target company ID in fpa_actuals")


@router.post("/sync")
async def trigger_sync(request: SyncRequest) -> Dict[str, Any]:
    """Pull Workday headcount/comp data → fpa_actuals as OpEx subcategories."""
    from app.core.supabase_client import get_supabase_client
    from app.services.integrations.workday.auth import refresh_access_token
    from app.services.integrations.workday.client import WorkdayClient
    from app.services.integrations.workday.parser import (
        parse_compensation_to_fpa_rows,
        parse_headcount_to_fpa_rows,
    )

    connection = get_connection(request.connection_id, request.user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Not a Workday connection")

    update_sync_status(request.connection_id, "syncing")
    extra = connection.get("extra_data") or {}

    # Token refresh
    class _WDRefresher:
        async def refresh_token(self, refresh_tok):
            return await refresh_access_token(
                refresh_tok,
                extra.get("client_id", settings.WORKDAY_CLIENT_ID or ""),
                extra.get("client_secret", settings.WORKDAY_CLIENT_SECRET or ""),
                extra.get("host", ""),
                extra.get("tenant", ""),
            )

    access_token = await ensure_valid_token(connection, _WDRefresher())
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to refresh Workday token")

    client = WorkdayClient(access_token, extra.get("host", ""), extra.get("tenant", ""))

    today = date.today()
    period = today.strftime("%Y-%m-01")

    try:
        all_rows = []

        # Fetch headcount via RAAS or REST
        headcount_url = extra.get("headcount_report_url", "")
        if headcount_url:
            workers = await client.get_headcount_report(headcount_url, today.isoformat())
            all_rows.extend(parse_headcount_to_fpa_rows(
                workers, request.company_id, period, fund_id=connection.get("fund_id"),
            ))

        # Fetch compensation via RAAS
        comp_url = extra.get("compensation_report_url", "")
        if comp_url:
            comp_data = await client.get_compensation_report(comp_url, today.isoformat())
            all_rows.extend(parse_compensation_to_fpa_rows(
                comp_data, request.company_id, period, fund_id=connection.get("fund_id"),
            ))

        # Fallback: use REST API workers if no RAAS reports configured
        if not headcount_url and not comp_url:
            workers = await client.get_workers()
            all_rows.extend(parse_headcount_to_fpa_rows(
                workers, request.company_id, period, fund_id=connection.get("fund_id"),
            ))

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

    logger.info("Workday sync: %d rows for period %s", len(all_rows), period)
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
