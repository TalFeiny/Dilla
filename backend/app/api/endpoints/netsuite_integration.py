"""NetSuite integration endpoints — OAuth flow, TBA setup, connection management, data sync.

Endpoints:
  GET  /integrations/netsuite/auth-url            → Generate OAuth2 URL
  GET  /integrations/netsuite/callback             → Handle OAuth2 callback
  POST /integrations/netsuite/connect-tba          → Connect via Token-Based Auth
  GET  /integrations/netsuite/connections           → List connections
  DELETE /integrations/netsuite/connections/{id}    → Disconnect
  POST /integrations/netsuite/sync                 → Pull data → fpa_actuals
  GET  /integrations/netsuite/sync-status/{id}     → Check sync progress
  GET  /integrations/netsuite/subsidiaries/{id}    → List subsidiaries
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.integrations.connection_manager import (
    delete_connection,
    ensure_valid_token,
    generate_state_token,
    get_connection,
    get_connections,
    pop_state,
    save_connection,
    store_state,
    update_sync_status,
)
from app.services.integrations.netsuite.auth import (
    build_oauth2_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
)
from app.services.integrations.netsuite.client import NetSuiteClient
from app.services.integrations.netsuite.parser import (
    parse_balance_sheet,
    parse_profit_and_loss,
)
from app.services.integrations.report_normalizer import compute_ebitda_rows

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/netsuite", tags=["netsuite"])

PROVIDER = "netsuite"


# ---------------------------------------------------------------------------
# OAuth 2.0 Auth
# ---------------------------------------------------------------------------

class AuthUrlRequest(BaseModel):
    user_id: str
    account_id: str = Field(..., description="NetSuite account ID (e.g. '1234567' or '1234567_SB1')")


class AuthUrlResponse(BaseModel):
    auth_url: str
    state: str


@router.get("/auth-url")
async def get_auth_url(
    user_id: str = Query(...),
    account_id: str = Query(..., description="NetSuite account ID"),
) -> AuthUrlResponse:
    """Generate a NetSuite OAuth2 authorization URL."""
    if not settings.NETSUITE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="NETSUITE_CLIENT_ID not configured")

    redirect_uri = settings.NETSUITE_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/netsuite/callback"
    state = generate_state_token()
    # Encode account_id in state for callback
    store_state(f"{state}:{account_id}", user_id, PROVIDER)

    auth_url = build_oauth2_auth_url(
        account_id=account_id,
        client_id=settings.NETSUITE_CLIENT_ID,
        redirect_uri=redirect_uri,
        state=f"{state}:{account_id}",
    )

    return AuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/callback")
async def oauth_callback(
    code: str = Query(""),
    state: str = Query(""),
    error: str = Query(""),
):
    """Handle the OAuth2 callback from NetSuite."""
    if error:
        logger.warning("NetSuite OAuth denied: %s", error)
        return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?netsuite_error={error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    state_data = pop_state(state)
    if not state_data or state_data.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    user_id = state_data["user_id"]

    # Extract account_id from state
    parts = state.rsplit(":", 1)
    account_id = parts[1] if len(parts) == 2 else ""
    if not account_id:
        raise HTTPException(status_code=400, detail="Account ID not found in state")

    redirect_uri = settings.NETSUITE_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/netsuite/callback"

    token_result = await exchange_code_for_tokens(
        code=code,
        account_id=account_id,
        client_id=settings.NETSUITE_CLIENT_ID,
        client_secret=settings.NETSUITE_CLIENT_SECRET,
        redirect_uri=redirect_uri,
    )

    if not token_result["success"]:
        logger.error("NetSuite token exchange failed: %s", token_result.get("error"))
        return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?netsuite_error=token_exchange_failed")

    conn = save_connection(
        user_id=user_id,
        provider=PROVIDER,
        tenant_id=account_id,
        tenant_name=f"NetSuite {account_id}",
        access_token=token_result["access_token"],
        refresh_token=token_result.get("refresh_token"),
        expires_in=token_result.get("expires_in", 3600),
        scopes=["rest_webservices"],
    )

    logger.info("NetSuite connected: account %s for user %s", account_id, user_id)
    return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?netsuite_connected=1")


# ---------------------------------------------------------------------------
# Token-Based Auth (TBA) — direct credential setup
# ---------------------------------------------------------------------------

class TBAConnectRequest(BaseModel):
    user_id: str
    account_id: str = Field(..., description="NetSuite account ID")
    account_name: str = Field("", description="Display name")
    consumer_key: str
    consumer_secret: str
    token_key: str
    token_secret: str


@router.post("/connect-tba")
async def connect_tba(request: TBAConnectRequest) -> Dict[str, Any]:
    """Connect to NetSuite via Token-Based Auth (OAuth 1.0).

    For customers who already have TBA credentials set up in NetSuite.
    """
    # Verify credentials by making a test API call
    client = NetSuiteClient(
        account_id=request.account_id,
        consumer_key=request.consumer_key,
        consumer_secret=request.consumer_secret,
        token_key=request.token_key,
        token_secret=request.token_secret,
    )

    # Test: fetch subsidiaries (lightweight query)
    test_result = await client.execute_suiteql("SELECT id, name FROM subsidiary FETCH NEXT 1 ROWS ONLY")

    conn = save_connection(
        user_id=request.user_id,
        provider=PROVIDER,
        tenant_id=request.account_id,
        tenant_name=request.account_name or f"NetSuite {request.account_id}",
        access_token="tba",  # placeholder — TBA doesn't use bearer tokens
        refresh_token=None,
        expires_in=999999999,  # TBA tokens don't expire
        scopes=["tba"],
        extra_fields={
            "consumer_key": request.consumer_key,
            "consumer_secret": request.consumer_secret,
            "token_key": request.token_key,
            "token_secret": request.token_secret,
        },
    )

    if not conn:
        raise HTTPException(status_code=500, detail="Failed to save connection")

    return {
        "success": True,
        "connection_id": conn.get("id"),
        "message": f"Connected to NetSuite {request.account_id} via TBA",
        "test_query_worked": len(test_result) > 0,
    }


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
    return {"success": True, "message": "NetSuite connection removed"}


# ---------------------------------------------------------------------------
# Data sync
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    connection_id: str
    user_id: str
    company_id: str
    months: int = Field(24, ge=1, le=60)
    subsidiary_id: Optional[str] = Field(None, description="Filter by subsidiary")


@router.post("/sync")
async def trigger_sync(request: SyncRequest) -> Dict[str, Any]:
    """Pull financial data from NetSuite via SuiteQL → fpa_actuals."""
    from app.core.supabase_client import get_supabase_client

    connection = get_connection(request.connection_id, request.user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Not a NetSuite connection")

    update_sync_status(request.connection_id, "syncing")

    account_id = connection["tenant_id"]

    # Build client based on auth method
    if connection.get("consumer_key"):
        # TBA auth
        client = NetSuiteClient(
            account_id=account_id,
            consumer_key=connection["consumer_key"],
            consumer_secret=connection["consumer_secret"],
            token_key=connection["token_key"],
            token_secret=connection["token_secret"],
        )
    else:
        # OAuth 2.0
        class _NSRefresher:
            async def refresh_token(self, refresh_tok):
                return await refresh_access_token(
                    refresh_tok, account_id,
                    settings.NETSUITE_CLIENT_ID, settings.NETSUITE_CLIENT_SECRET,
                )

        access_token = await ensure_valid_token(connection, _NSRefresher())
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to refresh NetSuite token")

        client = NetSuiteClient(account_id=account_id, access_token=access_token)

    today = date.today()
    from_date = (today - timedelta(days=request.months * 30)).replace(day=1)

    # Fetch P&L via SuiteQL
    pl_data = await client.get_profit_and_loss(
        from_date=from_date.isoformat(),
        to_date=today.isoformat(),
        subsidiary_id=request.subsidiary_id,
    )
    pl_rows = parse_profit_and_loss(pl_data, request.company_id, connection.get("fund_id"))

    # Fetch Balance Sheet
    bs_data = await client.get_balance_sheet(
        as_of_date=today.isoformat(),
        subsidiary_id=request.subsidiary_id,
    )
    bs_rows = parse_balance_sheet(bs_data, request.company_id, today.isoformat(), connection.get("fund_id"))

    all_rows = pl_rows + bs_rows

    if not all_rows:
        update_sync_status(request.connection_id, "idle")
        return {"success": True, "rows_synced": 0, "periods": []}

    # Compute EBITDA
    ebitda_rows = compute_ebitda_rows(pl_rows, request.company_id, PROVIDER, connection.get("fund_id"))
    all_rows.extend(ebitda_rows)

    # Upsert
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

    logger.info(
        "NetSuite sync complete: %d P&L + %d BS + %d EBITDA rows across %d periods for company %s",
        len(pl_rows), len(bs_rows), len(ebitda_rows), len(unique_periods), request.company_id,
    )

    return {
        "success": True,
        "rows_synced": len(all_rows),
        "pl_rows": len(pl_rows),
        "bs_rows": len(bs_rows),
        "periods": unique_periods,
    }


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


# ---------------------------------------------------------------------------
# Subsidiaries
# ---------------------------------------------------------------------------

@router.get("/subsidiaries/{connection_id}")
async def get_subsidiaries(connection_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    """List NetSuite subsidiaries for multi-entity sync."""
    connection = get_connection(connection_id, user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    account_id = connection["tenant_id"]

    if connection.get("consumer_key"):
        client = NetSuiteClient(
            account_id=account_id,
            consumer_key=connection["consumer_key"],
            consumer_secret=connection["consumer_secret"],
            token_key=connection["token_key"],
            token_secret=connection["token_secret"],
        )
    else:
        class _NSRefresher:
            async def refresh_token(self, refresh_tok):
                return await refresh_access_token(
                    refresh_tok, account_id,
                    settings.NETSUITE_CLIENT_ID, settings.NETSUITE_CLIENT_SECRET,
                )
        access_token = await ensure_valid_token(connection, _NSRefresher())
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to refresh token")
        client = NetSuiteClient(account_id=account_id, access_token=access_token)

    subsidiaries = await client.get_subsidiaries()
    return {
        "success": True,
        "subsidiaries": [
            {"id": s.get("id"), "name": s.get("name")}
            for s in subsidiaries
        ],
    }


def _frontend_url() -> str:
    if settings.ENVIRONMENT == "production":
        return "https://dilla.ai"
    return "http://localhost:3000"
