"""QuickBooks Online OAuth2 authentication.

Implements the Intuit OAuth2 flow:
1. Generate auth URL → user authorizes in browser
2. Callback with code → exchange for tokens
3. Auto-refresh before expiry (access tokens last ~60 min)
"""

import base64
import logging
from typing import Any, Dict
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intuit OAuth2 endpoints
# ---------------------------------------------------------------------------
QBO_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# Discovery document (for reference):
# https://developer.api.intuit.com/.well-known/openid_configuration

QBO_SCOPES = ["com.intuit.quickbooks.accounting"]


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Generate the QuickBooks OAuth2 authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(QBO_SCOPES),
        "state": state,
    }
    return f"{QBO_AUTH_URL}?{urlencode(params)}"


def _auth_header(client_id: str, client_secret: str) -> str:
    """Build Basic auth header for Intuit token endpoint."""
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> Dict[str, Any]:
    """Exchange authorization code for access + refresh tokens."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                QBO_TOKEN_URL,
                headers={
                    "Authorization": _auth_header(client_id, client_secret),
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )

        if response.status_code != 200:
            logger.error("QBO token exchange failed: %d %s", response.status_code, response.text)
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        data = response.json()
        return {
            "success": True,
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data.get("expires_in", 3600),
            "realm_id": data.get("realmId", ""),
        }
    except Exception as e:
        logger.error("QBO token exchange error: %s", e)
        return {"success": False, "error": str(e)}


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> Dict[str, Any]:
    """Refresh an expired QuickBooks access token."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                QBO_TOKEN_URL,
                headers={
                    "Authorization": _auth_header(client_id, client_secret),
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )

        if response.status_code != 200:
            logger.error("QBO token refresh failed: %d %s", response.status_code, response.text)
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        data = response.json()
        return {
            "success": True,
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data.get("expires_in", 3600),
        }
    except Exception as e:
        logger.error("QBO token refresh error: %s", e)
        return {"success": False, "error": str(e)}
