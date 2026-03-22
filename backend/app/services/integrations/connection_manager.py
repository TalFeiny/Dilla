"""Unified connection manager for all P&L data sources.

Manages OAuth2 token storage, refresh, and sync state in the
`accounting_connections` table.  Provider-agnostic — works for
QuickBooks, NetSuite, Xero, SAP, Salesforce, Workday, and BambooHR.
All are components of the P&L feeding fpa_actuals subcategories.
"""

import logging
import secrets
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TABLE = "accounting_connections"

# Providers that use API keys instead of OAuth (no token refresh needed)
API_KEY_PROVIDERS = {"bamboohr"}

# ---------------------------------------------------------------------------
# CSRF state store (in-memory, replace with Redis in production)
# ---------------------------------------------------------------------------
_pending_states: Dict[str, Dict[str, Any]] = {}
_states_lock = threading.Lock()
_STATE_TTL = 600  # 10 minutes


def generate_state_token() -> str:
    return secrets.token_urlsafe(32)


def store_state(token: str, user_id: str, provider: str) -> None:
    with _states_lock:
        now = time.time()
        expired = [k for k, v in _pending_states.items() if now - v["ts"] > _STATE_TTL]
        for k in expired:
            del _pending_states[k]
        _pending_states[token] = {"user_id": user_id, "provider": provider, "ts": now}


def pop_state(token: str) -> Optional[Dict[str, str]]:
    """Pop and return {user_id, provider} if state is valid, else None."""
    with _states_lock:
        entry = _pending_states.pop(token, None)
        if not entry:
            return None
        if time.time() - entry["ts"] > _STATE_TTL:
            return None
        return {"user_id": entry["user_id"], "provider": entry["provider"]}


# ---------------------------------------------------------------------------
# DB helpers (integration_connections table)
# ---------------------------------------------------------------------------

def _get_sb():
    from app.core.supabase_client import get_supabase_client
    return get_supabase_client()


def save_connection(
    user_id: str,
    provider: str,
    tenant_id: str,
    tenant_name: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
    scopes: Optional[List[str]] = None,
    fund_id: Optional[str] = None,
    company_id: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Upsert a connection in integration_connections."""
    sb = _get_sb()
    if not sb:
        logger.error("Supabase unavailable — cannot save %s connection", provider)
        return None

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    row: Dict[str, Any] = {
        "user_id": user_id,
        "provider": provider,
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": expires_at.isoformat(),
        "scopes": scopes or [],
        "sync_status": "idle",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if fund_id:
        row["fund_id"] = fund_id
    if company_id:
        row["company_id"] = company_id
    if extra_fields:
        row.update(extra_fields)

    result = (
        sb.table(_TABLE)
        .upsert(row, on_conflict="user_id,provider,tenant_id")
        .execute()
    )
    return result.data[0] if result.data else None


def get_connections(user_id: str, provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """List connections, optionally filtered by provider."""
    sb = _get_sb()
    if not sb:
        return []

    query = (
        sb.table(_TABLE)
        .select("id, provider, tenant_id, tenant_name, last_sync_at, sync_status, sync_error, created_at")
        .eq("user_id", user_id)
    )
    if provider:
        query = query.eq("provider", provider)

    result = query.order("created_at", desc=True).execute()
    return result.data or []


def get_connection(connection_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a single connection with tokens."""
    sb = _get_sb()
    if not sb:
        return None

    result = (
        sb.table(_TABLE)
        .select("*")
        .eq("id", connection_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    return result.data


def delete_connection(connection_id: str, user_id: str) -> bool:
    sb = _get_sb()
    if not sb:
        return False
    sb.table(_TABLE).delete().eq("id", connection_id).eq("user_id", user_id).execute()
    return True


def update_tokens(
    connection_id: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
) -> None:
    sb = _get_sb()
    if not sb:
        return
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    update: Dict[str, Any] = {
        "access_token": access_token,
        "token_expires_at": expires_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if refresh_token:
        update["refresh_token"] = refresh_token
    sb.table(_TABLE).update(update).eq("id", connection_id).execute()


def update_sync_status(connection_id: str, status: str, error: Optional[str] = None) -> None:
    sb = _get_sb()
    if not sb:
        return
    update: Dict[str, Any] = {
        "sync_status": status,
        "sync_error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if status == "idle" and error is None:
        update["last_sync_at"] = datetime.now(timezone.utc).isoformat()
    sb.table(_TABLE).update(update).eq("id", connection_id).execute()


async def ensure_valid_token(
    connection: Dict[str, Any],
    connector=None,
) -> Optional[str]:
    """Return a valid access token, refreshing if expired.

    For API-key providers (BambooHR), the access_token never expires — return as-is.
    For session providers (SAP B1), the connector handles re-login.
    For OAuth providers, refresh via connector.refresh_token().
    """
    provider = connection.get("provider", "")

    # API-key providers: token never expires
    if provider in API_KEY_PROVIDERS:
        return connection.get("access_token")

    expires_at_str = connection.get("token_expires_at", "")
    try:
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        # Can't parse — force refresh
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

    now = datetime.now(timezone.utc)

    if expires_at - now < timedelta(minutes=5):
        if connector is None:
            update_sync_status(connection["id"], "error", "No connector for token refresh")
            return None

        refresh = connection.get("refresh_token")
        if not refresh:
            update_sync_status(connection["id"], "error", "No refresh token available")
            return None

        result = await connector.refresh_token(refresh)
        if not result.get("success"):
            update_sync_status(connection["id"], "error", result.get("error", "Token refresh failed"))
            return None

        update_tokens(
            connection["id"],
            result["access_token"],
            result.get("refresh_token"),
            result.get("expires_in", 3600),
        )
        return result["access_token"]

    return connection["access_token"]
