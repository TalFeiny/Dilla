"""QuickBooks Online integration endpoints — OAuth flow, connection management, data sync.

Endpoints:
  GET  /integrations/quickbooks/auth-url          → Generate OAuth URL
  GET  /integrations/quickbooks/callback           → Handle OAuth callback
  GET  /integrations/quickbooks/connections         → List connected QBO companies
  DELETE /integrations/quickbooks/connections/{id}  → Disconnect
  POST /integrations/quickbooks/sync               → Pull data → fpa_actuals
  GET  /integrations/quickbooks/sync-status/{id}   → Check sync progress
  GET  /integrations/quickbooks/accounts/{id}       → Fetch chart of accounts
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict

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
from app.services.integrations.quickbooks.auth import (
    build_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
)
from app.services.integrations.quickbooks.client import QuickBooksClient
from app.services.integrations.quickbooks.parser import (
    parse_balance_sheet,
    parse_profit_and_loss,
)
from app.services.integrations.report_normalizer import compute_ebitda_rows

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/quickbooks", tags=["quickbooks"])

PROVIDER = "quickbooks"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class AuthUrlResponse(BaseModel):
    auth_url: str
    state: str


@router.get("/auth-url")
async def get_auth_url(user_id: str = Query(..., description="Current user ID")) -> AuthUrlResponse:
    """Generate a QuickBooks OAuth2 authorization URL."""
    if not settings.QBO_CLIENT_ID:
        raise HTTPException(status_code=500, detail="QBO_CLIENT_ID not configured")

    redirect_uri = settings.QBO_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/quickbooks/callback"
    state = generate_state_token()
    store_state(state, user_id, PROVIDER)

    auth_url = build_auth_url(
        client_id=settings.QBO_CLIENT_ID,
        redirect_uri=redirect_uri,
        state=state,
    )

    return AuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/callback")
async def oauth_callback(
    code: str = Query("", description="Authorization code"),
    state: str = Query("", description="CSRF state token"),
    realmId: str = Query("", description="QuickBooks company ID (realm)"),
    error: str = Query("", description="Error from Intuit"),
):
    """Handle the OAuth callback from QuickBooks."""
    if error:
        logger.warning("QBO OAuth denied: %s", error)
        return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?qbo_error={error}")

    if not code or not realmId:
        raise HTTPException(status_code=400, detail="Missing code or realmId")

    state_data = pop_state(state)
    if not state_data or state_data.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    user_id = state_data["user_id"]
    redirect_uri = settings.QBO_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/quickbooks/callback"

    token_result = await exchange_code_for_tokens(
        code=code,
        client_id=settings.QBO_CLIENT_ID,
        client_secret=settings.QBO_CLIENT_SECRET,
        redirect_uri=redirect_uri,
    )

    if not token_result["success"]:
        logger.error("QBO token exchange failed: %s", token_result.get("error"))
        return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?qbo_error=token_exchange_failed")

    # Fetch company name
    sandbox = getattr(settings, "QBO_ENVIRONMENT", "production") == "sandbox"
    qbo_client = QuickBooksClient(token_result["access_token"], realmId, sandbox=sandbox)
    company_info = await qbo_client.get_company_info()
    company_name = company_info.get("CompanyName", realmId) if company_info else realmId

    conn = save_connection(
        user_id=user_id,
        provider=PROVIDER,
        tenant_id=realmId,
        tenant_name=company_name,
        access_token=token_result["access_token"],
        refresh_token=token_result["refresh_token"],
        expires_in=token_result["expires_in"],
        scopes=["com.intuit.quickbooks.accounting"],
    )

    logger.info("QBO connected: %s (realm %s) for user %s", company_name, realmId, user_id)
    return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?qbo_connected=1")


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
    return {"success": True, "message": "QuickBooks connection removed"}


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
    """Pull latest financial data from QuickBooks → fpa_actuals."""
    from app.core.supabase_client import get_supabase_client

    connection = get_connection(request.connection_id, request.user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Not a QuickBooks connection")

    update_sync_status(request.connection_id, "syncing")

    # Build a lightweight connector for token refresh
    class _QBORefresher:
        async def refresh_token(self, refresh_tok):
            return await refresh_access_token(
                refresh_tok, settings.QBO_CLIENT_ID, settings.QBO_CLIENT_SECRET,
            )

    access_token = await ensure_valid_token(connection, _QBORefresher())
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to refresh QBO token")

    realm_id = connection["tenant_id"]
    sandbox = getattr(settings, "QBO_ENVIRONMENT", "production") == "sandbox"
    client = QuickBooksClient(access_token, realm_id, sandbox=sandbox)

    today = date.today()
    from_date = (today - timedelta(days=request.months * 30)).replace(day=1)

    # Fetch P&L
    pl_report = await client.get_profit_and_loss(
        start_date=from_date.isoformat(),
        end_date=today.isoformat(),
    )

    pl_rows = []
    if pl_report:
        pl_rows = parse_profit_and_loss(pl_report, request.company_id, connection.get("fund_id"))

    # Fetch Balance Sheet
    bs_report = await client.get_balance_sheet(as_of_date=today.isoformat())
    bs_rows = []
    if bs_report:
        bs_rows = parse_balance_sheet(bs_report, request.company_id, connection.get("fund_id"))

    all_rows = pl_rows + bs_rows

    if not all_rows:
        update_sync_status(request.connection_id, "idle")
        return {"success": True, "rows_synced": 0, "periods": []}

    # Compute EBITDA
    ebitda_rows = compute_ebitda_rows(pl_rows, request.company_id, PROVIDER, connection.get("fund_id"))
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

    logger.info(
        "QBO sync complete: %d P&L + %d BS + %d EBITDA rows across %d periods for company %s",
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
# Chart of Accounts
# ---------------------------------------------------------------------------

@router.get("/accounts/{connection_id}")
async def get_accounts(connection_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    """Fetch the chart of accounts from QuickBooks for mapping review."""
    connection = get_connection(connection_id, user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    class _QBORefresher:
        async def refresh_token(self, refresh_tok):
            return await refresh_access_token(
                refresh_tok, settings.QBO_CLIENT_ID, settings.QBO_CLIENT_SECRET,
            )

    access_token = await ensure_valid_token(connection, _QBORefresher())
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to refresh QBO token")

    sandbox = getattr(settings, "QBO_ENVIRONMENT", "production") == "sandbox"
    client = QuickBooksClient(access_token, connection["tenant_id"], sandbox=sandbox)
    accounts = await client.get_chart_of_accounts()

    return {
        "success": True,
        "accounts": [
            {
                "id": a.get("Id"),
                "name": a.get("Name"),
                "type": a.get("AccountType"),
                "sub_type": a.get("AccountSubType"),
                "active": a.get("Active", True),
            }
            for a in accounts
        ],
    }


def _frontend_url() -> str:
    if settings.ENVIRONMENT == "production":
        return "https://dilla.ai"
    return "http://localhost:3000"
