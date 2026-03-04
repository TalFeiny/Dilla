"""Xero integration service — OAuth2 via SDK, API client, data sync.

Uses the official xero-python SDK (pip install xero-python) for:
- OAuth2 token exchange and refresh
- AccountingApi calls (P&L, Balance Sheet, Trial Balance, Accounts)

Handles:
- Token storage and refresh via xero_connections table
- Mapping Xero report rows → fpa_actuals format for AG Grid consumption
"""

import logging
import secrets
from datetime import datetime, timedelta, date, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.accounting import AccountingApi
from xero_python.identity import IdentityApi

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Xero constants
# ---------------------------------------------------------------------------
XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"

XERO_SCOPES = [
    "openid",
    "profile",
    "email",
    "accounting.reports.read",
    "accounting.settings.read",
    "accounting.transactions.read",
    "offline_access",
]

# P&L section headers → FPA categories
PL_SECTION_MAP = {
    "Income": "revenue",
    "Revenue": "revenue",
    "Trading Income": "revenue",
    "Other Income": "revenue",
    "Less Cost of Sales": "cogs",
    "Cost of Sales": "cogs",
    "Direct Costs": "cogs",
    "Less Operating Expenses": "opex_total",
    "Operating Expenses": "opex_total",
    "Expenses": "opex_total",
}


# ---------------------------------------------------------------------------
# SDK client factory
# ---------------------------------------------------------------------------

def _build_api_client(client_id: str, client_secret: str) -> ApiClient:
    """Create a configured xero-python ApiClient."""
    api_client = ApiClient(
        Configuration(
            oauth2_token=OAuth2Token(
                client_id=client_id,
                client_secret=client_secret,
            ),
        ),
    )
    return api_client


def _set_token_on_client(api_client: ApiClient, token: Dict[str, Any]) -> None:
    """Set an existing OAuth2 token dict on the ApiClient."""
    api_client.set_oauth2_token(token)


def _build_token_dict(access_token: str, refresh_token: str, expires_in: int) -> Dict[str, Any]:
    """Build the token dict the SDK expects."""
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "token_type": "Bearer",
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).timestamp(),
    }


# ---------------------------------------------------------------------------
# OAuth2 flow
# ---------------------------------------------------------------------------

def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Generate the Xero OAuth2 authorization URL."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(XERO_SCOPES),
        "state": state,
    }
    return f"{XERO_AUTH_URL}?{urlencode(params)}"


def generate_state_token() -> str:
    """Generate a random state token for CSRF protection."""
    return secrets.token_urlsafe(32)


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> Dict[str, Any]:
    """Exchange authorization code for access + refresh tokens using the SDK."""
    try:
        api_client = _build_api_client(client_id, client_secret)
        token = api_client.get_oauth2_token(code=code, redirect_uri=redirect_uri)

        if not token or "access_token" not in token:
            return {"success": False, "error": "No access token in response"}

        return {
            "success": True,
            "access_token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "expires_in": token.get("expires_in", 1800),
            "scope": token.get("scope", ""),
        }
    except Exception as e:
        logger.error("Xero token exchange failed: %s", e)
        return {"success": False, "error": str(e)}


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> Dict[str, Any]:
    """Refresh an expired Xero access token using the SDK."""
    try:
        api_client = _build_api_client(client_id, client_secret)
        token = api_client.refresh_oauth2_token(refresh_token=refresh_token)

        if not token or "access_token" not in token:
            return {"success": False, "error": "No access token in refresh response"}

        return {
            "success": True,
            "access_token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "expires_in": token.get("expires_in", 1800),
        }
    except Exception as e:
        logger.error("Xero token refresh failed: %s", e)
        return {"success": False, "error": str(e)}


async def get_xero_tenants(
    access_token: str,
    client_id: str,
    client_secret: str,
) -> List[Dict[str, Any]]:
    """Fetch connected Xero organisations (tenants) using the SDK."""
    try:
        api_client = _build_api_client(client_id, client_secret)
        _set_token_on_client(api_client, _build_token_dict(access_token, "", 1800))

        identity_api = IdentityApi(api_client)
        connections = identity_api.get_connections()

        return [
            {
                "tenant_id": c.tenant_id,
                "tenant_name": c.tenant_name or "",
                "tenant_type": c.tenant_type or "",
            }
            for c in connections
        ]
    except Exception as e:
        logger.error("Failed to fetch Xero tenants: %s", e)
        return []


# ---------------------------------------------------------------------------
# Connection management (DB operations)
# ---------------------------------------------------------------------------

def save_connection(
    user_id: str,
    tenant_id: str,
    tenant_name: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    scopes: List[str],
    fund_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Upsert a Xero connection in the database."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        logger.error("Supabase client unavailable — cannot save Xero connection")
        return None

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    row = {
        "user_id": user_id,
        "xero_tenant_id": tenant_id,
        "xero_tenant_name": tenant_name,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": expires_at.isoformat(),
        "scopes": scopes,
        "sync_status": "idle",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if fund_id:
        row["fund_id"] = fund_id

    result = (
        sb.table("xero_connections")
        .upsert(row, on_conflict="user_id,xero_tenant_id")
        .execute()
    )
    return result.data[0] if result.data else None


def get_connections(user_id: str) -> List[Dict[str, Any]]:
    """List all Xero connections for a user."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return []

    result = (
        sb.table("xero_connections")
        .select("id, xero_tenant_id, xero_tenant_name, last_sync_at, sync_status, sync_error, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def get_connection(connection_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a single Xero connection with tokens (for sync operations)."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return None

    result = (
        sb.table("xero_connections")
        .select("*")
        .eq("id", connection_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    return result.data


def delete_connection(connection_id: str, user_id: str) -> bool:
    """Delete a Xero connection."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return False

    sb.table("xero_connections").delete().eq("id", connection_id).eq("user_id", user_id).execute()
    return True


def update_connection_tokens(
    connection_id: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> None:
    """Update tokens after a refresh."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    sb.table("xero_connections").update({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires_at": expires_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", connection_id).execute()


def update_sync_status(
    connection_id: str,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Update sync status on a connection."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return

    update = {
        "sync_status": status,
        "sync_error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if status == "idle" and error is None:
        update["last_sync_at"] = datetime.now(timezone.utc).isoformat()

    sb.table("xero_connections").update(update).eq("id", connection_id).execute()


# ---------------------------------------------------------------------------
# Ensure valid token (refresh if needed)
# ---------------------------------------------------------------------------

async def ensure_valid_token(connection: Dict[str, Any]) -> Optional[str]:
    """Return a valid access token, refreshing if expired."""
    from app.core.config import settings

    expires_at = datetime.fromisoformat(connection["token_expires_at"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    # Refresh if expiring within 5 minutes
    if expires_at - now < timedelta(minutes=5):
        result = await refresh_access_token(
            refresh_token=connection["refresh_token"],
            client_id=settings.XERO_CLIENT_ID,
            client_secret=settings.XERO_CLIENT_SECRET,
        )
        if not result["success"]:
            update_sync_status(connection["id"], "error", result.get("error", "Token refresh failed"))
            return None

        update_connection_tokens(
            connection["id"],
            result["access_token"],
            result["refresh_token"],
            result["expires_in"],
        )
        return result["access_token"]

    return connection["access_token"]


# ---------------------------------------------------------------------------
# Xero API calls via SDK
# ---------------------------------------------------------------------------

def _get_accounting_api(access_token: str) -> AccountingApi:
    """Create an AccountingApi instance with a valid token."""
    from app.core.config import settings

    api_client = _build_api_client(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET)
    _set_token_on_client(api_client, _build_token_dict(access_token, "", 1800))
    return AccountingApi(api_client)


def fetch_chart_of_accounts(access_token: str, tenant_id: str) -> List[Dict[str, Any]]:
    """Fetch the chart of accounts using the SDK."""
    try:
        api = _get_accounting_api(access_token)
        result = api.get_accounts(tenant_id)
        return [
            {
                "code": a.code,
                "name": a.name,
                "type": a.type,
                "class": getattr(a, "class_type", None) or getattr(a, "_class", None),
            }
            for a in (result.accounts or [])
        ]
    except Exception as e:
        logger.error("Failed to fetch chart of accounts: %s", e)
        return []


def fetch_profit_and_loss(
    access_token: str,
    tenant_id: str,
    from_date: str,
    to_date: str,
    periods: int = 12,
    timeframe: str = "MONTH",
) -> Optional[Dict[str, Any]]:
    """Fetch P&L report using the SDK."""
    try:
        api = _get_accounting_api(access_token)
        result = api.get_report_profit_and_loss(
            tenant_id,
            from_date=from_date,
            to_date=to_date,
            periods=periods,
            timeframe=timeframe,
        )
        # SDK returns model objects — convert to dict for parsing
        return result.to_dict() if result else None
    except Exception as e:
        logger.error("Failed to fetch P&L report: %s", e)
        return None


def fetch_balance_sheet(
    access_token: str,
    tenant_id: str,
    report_date: str,
) -> Optional[Dict[str, Any]]:
    """Fetch balance sheet using the SDK."""
    try:
        api = _get_accounting_api(access_token)
        result = api.get_report_balance_sheet(tenant_id, date=report_date)
        return result.to_dict() if result else None
    except Exception as e:
        logger.error("Failed to fetch balance sheet: %s", e)
        return None


def fetch_trial_balance(
    access_token: str,
    tenant_id: str,
    report_date: str,
) -> Optional[Dict[str, Any]]:
    """Fetch trial balance using the SDK."""
    try:
        api = _get_accounting_api(access_token)
        result = api.get_report_trial_balance(tenant_id, date=report_date)
        return result.to_dict() if result else None
    except Exception as e:
        logger.error("Failed to fetch trial balance: %s", e)
        return None


# ---------------------------------------------------------------------------
# Report parsing → fpa_actuals rows
# ---------------------------------------------------------------------------

def _parse_report_header_dates(report: Dict[str, Any]) -> List[str]:
    """Extract period column headers from a Xero report.

    Xero reports have a header row with cells like:
    [{"Value": ""}, {"Value": "Jan 2025"}, {"Value": "Feb 2025"}, ...]

    SDK to_dict() may use "value" (lowercase) or "Value" (uppercase).
    """
    rows = report.get("reports", report.get("Reports", [{}]))
    if isinstance(rows, list) and rows:
        rows = rows[0].get("rows", rows[0].get("Rows", []))
    else:
        return []

    for row in rows:
        row_type = row.get("row_type", row.get("RowType", ""))
        if row_type == "Header":
            cells = row.get("cells", row.get("Cells", []))
            return [c.get("value", c.get("Value", "")) for c in cells[1:]]
    return []


def _normalize_period(period_str: str) -> Optional[str]:
    """Convert Xero period string to ISO format.

    Handles: "Jan 2025", "1 Jan 2025", "January 2025", "2025-01", etc.
    """
    import re
    from datetime import datetime as dt

    if not period_str:
        return None

    # Already ISO: "2025-01" or "2025-01-01"
    if re.match(r"^\d{4}-\d{2}", period_str):
        return period_str[:7]

    # "Jan 2025" or "January 2025"
    for fmt in ("%b %Y", "%B %Y", "%d %b %Y", "%d %B %Y"):
        try:
            parsed = dt.strptime(period_str.strip(), fmt)
            return parsed.strftime("%Y-%m")
        except ValueError:
            continue

    logger.warning("Could not parse Xero period: %s", period_str)
    return None


def parse_profit_and_loss(
    report: Dict[str, Any],
    company_id: str,
    fund_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Parse a Xero P&L report into fpa_actuals rows.

    Walks the report row tree, mapping section headers to FPA categories
    and extracting amounts per period.
    """
    if not report:
        return []

    periods = _parse_report_header_dates(report)
    if not periods:
        logger.warning("No period columns found in P&L report")
        return []

    iso_periods = [_normalize_period(p) for p in periods]

    rows_out: List[Dict[str, Any]] = []

    # Handle both SDK dict keys (snake_case) and raw API keys (PascalCase)
    top_reports = report.get("reports", report.get("Reports", [{}]))
    report_rows = top_reports[0].get("rows", top_reports[0].get("Rows", [])) if top_reports else []

    current_category = "opex_total"

    for section in report_rows:
        row_type = section.get("row_type", section.get("RowType", ""))
        title = section.get("title", section.get("Title", ""))

        if row_type == "Section" and title:
            current_category = PL_SECTION_MAP.get(title, current_category)

        inner_rows = section.get("rows", section.get("Rows", []))
        for row in inner_rows:
            rt = row.get("row_type", row.get("RowType", ""))
            if rt != "Row":
                continue

            cells = row.get("cells", row.get("Cells", []))
            if len(cells) < 2:
                continue

            subcategory = cells[0].get("value", cells[0].get("Value", "")).strip()
            if not subcategory:
                continue

            for i, cell in enumerate(cells[1:]):
                if i >= len(iso_periods) or not iso_periods[i]:
                    continue

                raw_value = cell.get("value", cell.get("Value", ""))
                if not raw_value:
                    continue

                try:
                    amount = float(str(raw_value).replace(",", ""))
                except (ValueError, TypeError):
                    continue

                if amount == 0:
                    continue

                rows_out.append({
                    "company_id": company_id,
                    "fund_id": fund_id,
                    "period": f"{iso_periods[i]}-01",
                    "category": current_category,
                    "subcategory": subcategory.lower().replace(" ", "_"),
                    "amount": amount,
                    "source": "xero",
                })

    _compute_ebitda(rows_out, company_id, fund_id)
    return rows_out


def _compute_ebitda(
    rows: List[Dict[str, Any]],
    company_id: str,
    fund_id: Optional[str],
) -> None:
    """Compute EBITDA per period from existing rows and append."""
    period_totals: Dict[str, Dict[str, float]] = {}

    for row in rows:
        period = row["period"]
        cat = row["category"]
        if period not in period_totals:
            period_totals[period] = {"revenue": 0, "cogs": 0, "opex_total": 0}
        if cat in period_totals[period]:
            period_totals[period][cat] += row["amount"]

    for period, totals in period_totals.items():
        ebitda = totals["revenue"] - totals["cogs"] - totals["opex_total"]
        rows.append({
            "company_id": company_id,
            "fund_id": fund_id,
            "period": period,
            "category": "ebitda",
            "subcategory": None,
            "amount": ebitda,
            "source": "xero",
        })


# ---------------------------------------------------------------------------
# Full sync operation
# ---------------------------------------------------------------------------

async def sync_xero_data(
    connection_id: str,
    user_id: str,
    company_id: str,
    months: int = 24,
) -> Dict[str, Any]:
    """Run a full sync: pull Xero P&L data → upsert into fpa_actuals.

    Args:
        connection_id: UUID of the xero_connections row
        user_id: Owner user ID (for auth check)
        company_id: Target company in fpa_actuals
        months: How many months of history to pull (default 24)

    Returns:
        {success, rows_synced, periods, error?}
    """
    from app.core.supabase_client import get_supabase_client

    connection = get_connection(connection_id, user_id)
    if not connection:
        return {"success": False, "error": "Connection not found"}

    update_sync_status(connection_id, "syncing")

    access_token = await ensure_valid_token(connection)
    if not access_token:
        return {"success": False, "error": "Failed to refresh Xero token"}

    tenant_id = connection["xero_tenant_id"]

    today = date.today()
    from_date = (today - timedelta(days=months * 30)).replace(day=1)
    to_date = today

    report = fetch_profit_and_loss(
        access_token=access_token,
        tenant_id=tenant_id,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        periods=months,
        timeframe="MONTH",
    )

    if not report:
        update_sync_status(connection_id, "error", "Failed to fetch P&L report from Xero")
        return {"success": False, "error": "Failed to fetch P&L report"}

    rows = parse_profit_and_loss(
        report=report,
        company_id=company_id,
        fund_id=connection.get("fund_id"),
    )

    if not rows:
        update_sync_status(connection_id, "idle")
        return {"success": True, "rows_synced": 0, "periods": []}

    sb = get_supabase_client()
    if not sb:
        update_sync_status(connection_id, "error", "Database unavailable")
        return {"success": False, "error": "Database unavailable"}

    sb.table("fpa_actuals").upsert(
        rows,
        on_conflict="company_id,period,category,source",
    ).execute()

    update_sync_status(connection_id, "idle")

    unique_periods = sorted(set(r["period"][:7] for r in rows))

    logger.info(
        "Xero sync complete: %d rows across %d periods for company %s",
        len(rows), len(unique_periods), company_id,
    )

    return {
        "success": True,
        "rows_synced": len(rows),
        "periods": unique_periods,
    }
