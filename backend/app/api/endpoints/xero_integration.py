"""Xero integration endpoints — OAuth flow, connection management, data sync.

Endpoints:
  GET  /integrations/xero/auth-url          → Generate OAuth URL
  GET  /integrations/xero/callback          → Handle OAuth callback
  GET  /integrations/xero/connections        → List connected Xero orgs
  DELETE /integrations/xero/connections/{id} → Disconnect a Xero org
  POST /integrations/xero/sync              → Pull data from Xero → fpa_actuals
  GET  /integrations/xero/sync-status/{id}  → Check sync progress
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.xero_service import (
    build_auth_url,
    delete_connection,
    exchange_code_for_tokens,
    generate_state_token,
    get_connection,
    get_connections,
    get_xero_tenants,
    save_connection,
    sync_xero_data,
    XERO_SCOPES,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/xero", tags=["xero"])

# In-memory state store for CSRF protection (replace with Redis in production)
# States expire after 10 minutes; thread-safe with lock
import time
import threading

_pending_states: Dict[str, Dict[str, Any]] = {}  # state_token → {user_id, ts}
_states_lock = threading.Lock()
_STATE_TTL = 600  # 10 minutes


def _store_state(token: str, user_id: str) -> None:
    with _states_lock:
        now = time.time()
        expired = [k for k, v in _pending_states.items() if now - v["ts"] > _STATE_TTL]
        for k in expired:
            del _pending_states[k]
        _pending_states[token] = {"user_id": user_id, "ts": now}


def _pop_state(token: str) -> Optional[str]:
    with _states_lock:
        entry = _pending_states.pop(token, None)
        if not entry:
            return None
        if time.time() - entry["ts"] > _STATE_TTL:
            return None
        return entry["user_id"]


# ---------------------------------------------------------------------------
# OAuth2 flow
# ---------------------------------------------------------------------------

class AuthUrlResponse(BaseModel):
    auth_url: str
    state: str


@router.get("/auth-url")
async def get_auth_url(user_id: str = Query(..., description="Current user ID")) -> AuthUrlResponse:
    """Generate a Xero OAuth2 authorization URL.

    Frontend opens this URL in a popup/redirect to start the OAuth flow.
    """
    if not settings.XERO_CLIENT_ID:
        raise HTTPException(status_code=500, detail="XERO_CLIENT_ID not configured")

    redirect_uri = settings.XERO_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/xero/callback"
    state = generate_state_token()
    _store_state(state, user_id)

    auth_url = build_auth_url(
        client_id=settings.XERO_CLIENT_ID,
        redirect_uri=redirect_uri,
        state=state,
    )

    return AuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/callback")
async def oauth_callback(
    code: str = Query("", description="Authorization code from Xero"),
    state: str = Query("", description="CSRF state token"),
    error: str = Query("", description="Error from Xero"),
):
    """Handle the OAuth callback from Xero.

    Exchanges the authorization code for tokens, fetches connected tenants,
    and stores the connection in the database.
    """
    if error:
        logger.warning("Xero OAuth denied: %s", error)
        # Redirect to frontend with error
        return RedirectResponse(url=f"{_frontend_url()}/settings/integrations?xero_error={error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Validate state token (thread-safe, TTL-checked)
    user_id = _pop_state(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    redirect_uri = settings.XERO_REDIRECT_URI or f"{settings.BACKEND_URL}/api/integrations/xero/callback"

    # Exchange code for tokens
    token_result = await exchange_code_for_tokens(
        code=code,
        client_id=settings.XERO_CLIENT_ID,
        client_secret=settings.XERO_CLIENT_SECRET,
        redirect_uri=redirect_uri,
    )

    if not token_result["success"]:
        logger.error("Xero token exchange failed: %s", token_result.get("error"))
        return RedirectResponse(
            url=f"{_frontend_url()}/settings/integrations?xero_error=token_exchange_failed"
        )

    # Fetch connected Xero organisations
    tenants = await get_xero_tenants(
        token_result["access_token"],
        settings.XERO_CLIENT_ID,
        settings.XERO_CLIENT_SECRET,
    )

    if not tenants:
        return RedirectResponse(
            url=f"{_frontend_url()}/settings/integrations?xero_error=no_tenants"
        )

    # Save a connection for each tenant
    saved = []
    scopes = token_result.get("scope", "").split()
    for tenant in tenants:
        conn = save_connection(
            user_id=user_id,
            tenant_id=tenant["tenant_id"],
            tenant_name=tenant["tenant_name"],
            access_token=token_result["access_token"],
            refresh_token=token_result["refresh_token"],
            expires_in=token_result["expires_in"],
            scopes=scopes,
        )
        if conn:
            saved.append(tenant["tenant_name"])

    logger.info("Xero connected: %s for user %s", saved, user_id)

    # Redirect to frontend settings page with success
    return RedirectResponse(
        url=f"{_frontend_url()}/settings/integrations?xero_connected={len(saved)}"
    )


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

@router.get("/connections")
async def list_connections(
    user_id: str = Query(..., description="Current user ID"),
) -> Dict[str, Any]:
    """List all Xero connections for the current user."""
    connections = get_connections(user_id)
    return {"success": True, "connections": connections}


@router.delete("/connections/{connection_id}")
async def remove_connection(
    connection_id: str,
    user_id: str = Query(..., description="Current user ID"),
) -> Dict[str, Any]:
    """Disconnect a Xero organisation."""
    deleted = delete_connection(connection_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"success": True, "message": "Xero connection removed"}


# ---------------------------------------------------------------------------
# Data sync
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    connection_id: str = Field(..., description="Xero connection UUID")
    user_id: str = Field(..., description="Current user ID")
    company_id: str = Field(..., description="Target company ID in fpa_actuals")
    months: int = Field(24, ge=1, le=60, description="Months of history to pull")


@router.post("/sync")
async def trigger_sync(request: SyncRequest) -> Dict[str, Any]:
    """Pull latest financial data from Xero and upsert into fpa_actuals.

    The synced data flows into the AG Grid via the existing
    get_company_actuals() → fpa_actuals pipeline.
    """
    result = await sync_xero_data(
        connection_id=request.connection_id,
        user_id=request.user_id,
        company_id=request.company_id,
        months=request.months,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Sync failed"))

    return result


@router.get("/sync-status/{connection_id}")
async def get_sync_status(
    connection_id: str,
    user_id: str = Query(..., description="Current user ID"),
) -> Dict[str, Any]:
    """Check the current sync status of a Xero connection."""
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
# Helpers
# ---------------------------------------------------------------------------

def _frontend_url() -> str:
    """Get the frontend URL for redirects."""
    # In development, frontend is on port 3000
    if settings.ENVIRONMENT == "production":
        return "https://dilla.ai"
    return "http://localhost:3000"
