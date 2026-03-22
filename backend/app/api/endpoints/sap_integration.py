"""SAP S/4HANA Cloud + Business One integration endpoints.

Endpoints:
  POST /integrations/sap-s4/connect             → Connect via client credentials
  POST /integrations/sap-b1/connect              → Connect via session login
  GET  /integrations/sap/connections              → List SAP connections
  DELETE /integrations/sap/connections/{id}       → Disconnect
  POST /integrations/sap/sync                    → Pull data → fpa_actuals
  GET  /integrations/sap/sync-status/{id}        → Check sync progress
  GET  /integrations/sap/accounts/{id}           → Fetch chart of accounts
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

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

router = APIRouter(prefix="/integrations/sap", tags=["sap"])


# ---------------------------------------------------------------------------
# S/4HANA Cloud — Connect via client credentials
# ---------------------------------------------------------------------------

class S4ConnectRequest(BaseModel):
    user_id: str = Field(..., description="Current user ID")
    base_url: str = Field(..., description="S/4HANA Cloud base URL, e.g. https://tenant.s4hana.cloud.sap")
    client_id: str = Field(..., description="BTP OAuth client ID")
    client_secret: str = Field(..., description="BTP OAuth client secret")
    token_url: str = Field(..., description="BTP token URL")
    company_code: str = Field(..., description="SAP company code")
    company_name: str = Field("", description="Display name")


@router.post("/s4/connect")
async def connect_s4(request: S4ConnectRequest) -> Dict[str, Any]:
    """Connect to SAP S/4HANA Cloud via OAuth2 client credentials."""
    from app.services.integrations.sap.auth import s4_get_token

    token_result = await s4_get_token(
        client_id=request.client_id,
        client_secret=request.client_secret,
        token_url=request.token_url,
    )

    if not token_result.get("success"):
        raise HTTPException(status_code=400, detail=token_result.get("error", "Token fetch failed"))

    conn = save_connection(
        user_id=request.user_id,
        provider="sap_s4",
        tenant_id=request.company_code,
        tenant_name=request.company_name or request.company_code,
        access_token=token_result["access_token"],
        refresh_token=None,
        expires_in=token_result.get("expires_in", 43200),
        extra_fields={
            "extra_data": {
                "base_url": request.base_url,
                "client_id": request.client_id,
                "client_secret": request.client_secret,
                "token_url": request.token_url,
                "company_code": request.company_code,
            },
        },
    )

    logger.info("SAP S/4 connected: %s for user %s", request.company_code, request.user_id)
    return {"success": True, "connection": conn}


# ---------------------------------------------------------------------------
# Business One — Connect via session login
# ---------------------------------------------------------------------------

class B1ConnectRequest(BaseModel):
    user_id: str = Field(..., description="Current user ID")
    server_url: str = Field(..., description="B1 Service Layer URL, e.g. https://server:50000")
    company_db: str = Field(..., description="Company database name")
    username: str = Field(..., description="B1 username")
    password: str = Field(..., description="B1 password")
    company_name: str = Field("", description="Display name")


@router.post("/b1/connect")
async def connect_b1(request: B1ConnectRequest) -> Dict[str, Any]:
    """Connect to SAP Business One via Service Layer session."""
    from app.services.integrations.sap.auth import b1_login

    login_result = await b1_login(
        server_url=request.server_url,
        company_db=request.company_db,
        username=request.username,
        password=request.password,
    )

    if not login_result.get("success"):
        raise HTTPException(status_code=400, detail=login_result.get("error", "Login failed"))

    conn = save_connection(
        user_id=request.user_id,
        provider="sap_b1",
        tenant_id=request.company_db,
        tenant_name=request.company_name or request.company_db,
        access_token=login_result["session_id"],
        refresh_token=None,
        expires_in=1800,  # 30-min session
        extra_fields={
            "extra_data": {
                "server_url": request.server_url,
                "company_db": request.company_db,
                "username": request.username,
                "password": request.password,
                "route_id": login_result.get("route_id", ""),
            },
        },
    )

    logger.info("SAP B1 connected: %s for user %s", request.company_db, request.user_id)
    return {"success": True, "connection": conn}


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

@router.get("/connections")
async def list_connections(user_id: str = Query(...)) -> Dict[str, Any]:
    s4_conns = get_connections(user_id, provider="sap_s4")
    b1_conns = get_connections(user_id, provider="sap_b1")
    return {"success": True, "connections": s4_conns + b1_conns}


@router.delete("/connections/{connection_id}")
async def remove_connection(connection_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    deleted = delete_connection(connection_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"success": True, "message": "SAP connection removed"}


# ---------------------------------------------------------------------------
# Data sync
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    connection_id: str = Field(..., description="Connection UUID")
    user_id: str = Field(..., description="Current user ID")
    company_id: str = Field(..., description="Target company ID in fpa_actuals")
    months: int = Field(24, ge=1, le=60, description="Months of history")


@router.post("/sync")
async def trigger_sync(request: SyncRequest) -> Dict[str, Any]:
    """Pull latest financial data from SAP → fpa_actuals."""
    from app.core.supabase_client import get_supabase_client
    from app.services.integrations.report_normalizer import compute_ebitda_rows

    connection = get_connection(request.connection_id, request.user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    provider = connection.get("provider")
    if provider not in ("sap_s4", "sap_b1"):
        raise HTTPException(status_code=400, detail="Not a SAP connection")

    update_sync_status(request.connection_id, "syncing")
    extra = connection.get("extra_data") or {}

    try:
        if provider == "sap_s4":
            all_rows = await _sync_s4(connection, extra, request)
        else:
            all_rows = await _sync_b1(connection, extra, request)
    except Exception as e:
        update_sync_status(request.connection_id, "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))

    if not all_rows:
        update_sync_status(request.connection_id, "idle")
        return {"success": True, "rows_synced": 0, "periods": []}

    # Compute EBITDA
    ebitda_rows = compute_ebitda_rows(all_rows, request.company_id, provider, connection.get("fund_id"))
    all_rows.extend(ebitda_rows)

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
    unique_periods = sorted(set(r.period[:7] for r in all_rows))

    logger.info("SAP sync complete: %d rows across %d periods", len(all_rows), len(unique_periods))
    return {"success": True, "rows_synced": len(all_rows), "periods": unique_periods}


async def _sync_s4(connection, extra, request):
    """Sync from SAP S/4HANA Cloud."""
    from app.services.integrations.sap.auth import s4_get_token
    from app.services.integrations.sap.client import SAPS4Client
    from app.services.integrations.sap.parser import parse_s4_trial_balance

    # Re-fetch token (client credentials)
    token_result = await s4_get_token(
        client_id=extra.get("client_id", ""),
        client_secret=extra.get("client_secret", ""),
        token_url=extra.get("token_url", ""),
    )
    if not token_result.get("success"):
        raise Exception(f"S/4 token failed: {token_result.get('error')}")

    from app.services.integrations.connection_manager import update_tokens
    update_tokens(connection["id"], token_result["access_token"], None, token_result.get("expires_in", 43200))

    client = SAPS4Client(token_result["access_token"], extra.get("base_url", ""))
    company_code = extra.get("company_code", connection["tenant_id"])

    today = date.today()
    start_year = today.year - (request.months // 12) - 1
    all_rows = []

    for year in range(start_year, today.year + 1):
        max_period = 12 if year < today.year else today.month
        for period in range(1, max_period + 1):
            tb_data = await client.get_trial_balance(company_code, year, period)
            if tb_data:
                rows = parse_s4_trial_balance(
                    tb_data, request.company_id, year,
                    fund_id=connection.get("fund_id"),
                )
                all_rows.extend(rows)

    return all_rows


async def _sync_b1(connection, extra, request):
    """Sync from SAP Business One."""
    from app.services.integrations.sap.auth import b1_login
    from app.services.integrations.sap.client import SAPB1Client
    from app.services.integrations.sap.parser import parse_b1_journal_entries

    # Re-login (sessions are 30 min)
    login_result = await b1_login(
        server_url=extra.get("server_url", ""),
        company_db=extra.get("company_db", connection["tenant_id"]),
        username=extra.get("username", ""),
        password=extra.get("password", ""),
    )
    if not login_result.get("success"):
        raise Exception(f"B1 login failed: {login_result.get('error')}")

    client = SAPB1Client(
        extra.get("server_url", ""),
        login_result["session_id"],
        login_result.get("route_id", ""),
    )

    today = date.today()
    from_date = (today - timedelta(days=request.months * 30)).replace(day=1)

    # Fetch COA + journal entries
    coa = await client.get_chart_of_accounts()
    entries = await client.get_journal_entries(from_date.isoformat(), today.isoformat())

    all_rows = parse_b1_journal_entries(
        entries, coa, request.company_id,
        fund_id=connection.get("fund_id"),
    )

    return all_rows


# ---------------------------------------------------------------------------
# Sync status + Chart of Accounts
# ---------------------------------------------------------------------------

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


@router.get("/accounts/{connection_id}")
async def get_accounts(connection_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    """Fetch chart of accounts from SAP for mapping review."""
    connection = get_connection(connection_id, user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    provider = connection.get("provider")
    extra = connection.get("extra_data") or {}

    if provider == "sap_s4":
        from app.services.integrations.sap.auth import s4_get_token
        from app.services.integrations.sap.client import SAPS4Client

        token_result = await s4_get_token(
            client_id=extra.get("client_id", ""),
            client_secret=extra.get("client_secret", ""),
            token_url=extra.get("token_url", ""),
        )
        if not token_result.get("success"):
            raise HTTPException(status_code=400, detail="Token refresh failed")

        client = SAPS4Client(token_result["access_token"], extra.get("base_url", ""))
        accounts = await client.get_chart_of_accounts()
    elif provider == "sap_b1":
        from app.services.integrations.sap.auth import b1_login
        from app.services.integrations.sap.client import SAPB1Client

        login_result = await b1_login(
            server_url=extra.get("server_url", ""),
            company_db=extra.get("company_db", ""),
            username=extra.get("username", ""),
            password=extra.get("password", ""),
        )
        if not login_result.get("success"):
            raise HTTPException(status_code=400, detail="B1 login failed")

        client = SAPB1Client(extra.get("server_url", ""), login_result["session_id"], login_result.get("route_id", ""))
        accounts = await client.get_chart_of_accounts()
    else:
        raise HTTPException(status_code=400, detail="Not a SAP connection")

    return {"success": True, "accounts": accounts}
