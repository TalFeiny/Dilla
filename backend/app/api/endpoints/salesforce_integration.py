"""Salesforce CRM integration endpoints — OAuth flow, connection management, pipeline sync.

Endpoints:
  GET  /integrations/salesforce/auth-url          → Generate OAuth URL
  GET  /integrations/salesforce/callback           → Handle OAuth callback
  GET  /integrations/salesforce/connections         → List connections
  DELETE /integrations/salesforce/connections/{id}  → Disconnect
  POST /integrations/salesforce/sync               → Pull pipeline → fpa_actuals
  GET  /integrations/salesforce/sync-status/{id}   → Check sync progress
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/salesforce", tags=["salesforce"])

PROVIDER = "salesforce"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class AuthUrlResponse(BaseModel):
    auth_url: str
    state: str


@router.get("/auth-url")
async def get_auth_url(user_id: str = Query(..., description="Current user ID")) -> AuthUrlResponse:
    """Generate a Salesforce OAuth2 authorization URL."""
    if not settings.SALESFORCE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="SALESFORCE_CLIENT_ID not configured")

    from app.services.integrations.salesforce.auth import build_auth_url

    redirect_uri = settings.SALESFORCE_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/salesforce/callback"
    state = generate_state_token()
    store_state(state, user_id, PROVIDER)

    auth_url = build_auth_url(
        client_id=settings.SALESFORCE_CLIENT_ID,
        redirect_uri=redirect_uri,
        state=state,
        sandbox=settings.SALESFORCE_SANDBOX,
    )

    return AuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/callback")
async def oauth_callback(
    code: str = Query("", description="Authorization code"),
    state: str = Query("", description="CSRF state token"),
    error: str = Query("", description="Error from Salesforce"),
):
    """Handle the OAuth callback from Salesforce."""
    if error:
        logger.warning("Salesforce OAuth denied: %s", error)
        return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?sf_error={error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    state_data = pop_state(state)
    if not state_data or state_data.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    user_id = state_data["user_id"]

    from app.services.integrations.salesforce.auth import exchange_code_for_tokens

    redirect_uri = settings.SALESFORCE_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/salesforce/callback"

    token_result = await exchange_code_for_tokens(
        code=code,
        client_id=settings.SALESFORCE_CLIENT_ID,
        client_secret=settings.SALESFORCE_CLIENT_SECRET,
        redirect_uri=redirect_uri,
        sandbox=settings.SALESFORCE_SANDBOX,
    )

    if not token_result["success"]:
        logger.error("Salesforce token exchange failed: %s", token_result.get("error"))
        return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?sf_error=token_exchange_failed")

    instance_url = token_result.get("instance_url", "")

    conn = save_connection(
        user_id=user_id,
        provider=PROVIDER,
        tenant_id=instance_url,
        tenant_name=instance_url.replace("https://", "").split(".")[0],
        access_token=token_result["access_token"],
        refresh_token=token_result.get("refresh_token"),
        expires_in=token_result.get("expires_in", 7200),
        scopes=["api", "refresh_token"],
        extra_fields={
            "extra_data": {"instance_url": instance_url},
        },
    )

    logger.info("Salesforce connected: %s for user %s", instance_url, user_id)
    return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?sf_connected=1")


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
    return {"success": True, "message": "Salesforce connection removed"}


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
    """Pull Salesforce pipeline data → fpa_actuals as revenue subcategories."""
    from app.core.supabase_client import get_supabase_client
    from app.services.integrations.salesforce.auth import refresh_access_token
    from app.services.integrations.salesforce.client import SalesforceClient
    from app.services.integrations.salesforce.parser import (
        parse_pipeline_to_fpa_rows,
        parse_won_opportunities_to_fpa_rows,
    )

    connection = get_connection(request.connection_id, request.user_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.get("provider") != PROVIDER:
        raise HTTPException(status_code=400, detail="Not a Salesforce connection")

    update_sync_status(request.connection_id, "syncing")

    # Token refresh
    class _SFRefresher:
        async def refresh_token(self, refresh_tok):
            return await refresh_access_token(
                refresh_tok, settings.SALESFORCE_CLIENT_ID, settings.SALESFORCE_CLIENT_SECRET,
                sandbox=settings.SALESFORCE_SANDBOX,
            )

    access_token = await ensure_valid_token(connection, _SFRefresher())
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to refresh Salesforce token")

    extra = connection.get("extra_data") or {}
    instance_url = extra.get("instance_url", connection["tenant_id"])

    client = SalesforceClient(access_token, instance_url)

    today = date.today()
    from_date = (today - timedelta(days=request.months * 30)).replace(day=1)

    try:
        # Fetch closed-won opportunities → actual revenue
        won_opps = await client.get_won_opportunities(from_date.isoformat(), today.isoformat())
        won_rows = parse_won_opportunities_to_fpa_rows(
            won_opps, request.company_id, fund_id=connection.get("fund_id"),
        )

        # Fetch open pipeline → weighted forecast
        pipeline = await client.get_pipeline()
        pipeline_rows = parse_pipeline_to_fpa_rows(
            pipeline, request.company_id, fund_id=connection.get("fund_id"),
        )

        all_rows = won_rows + pipeline_rows
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
    unique_periods = sorted(set(r.period[:7] for r in all_rows))

    logger.info(
        "Salesforce sync: %d won + %d pipeline rows across %d periods",
        len(won_rows), len(pipeline_rows), len(unique_periods),
    )

    return {
        "success": True,
        "rows_synced": len(all_rows),
        "won_rows": len(won_rows),
        "pipeline_rows": len(pipeline_rows),
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


def _frontend_url() -> str:
    if settings.ENVIRONMENT == "production":
        return "https://dilla.ai"
    return "http://localhost:3000"
