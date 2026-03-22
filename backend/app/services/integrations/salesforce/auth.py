"""Salesforce OAuth 2.0 authentication (Web Server Flow).

Implements the Salesforce Authorization Code Grant:
1. Generate auth URL → user authorizes in browser
2. Callback with code → exchange for tokens
3. Refresh before expiry (access tokens last ~2 hours)

Supports both Production and Sandbox orgs.
"""

import logging
from typing import Any, Dict
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Salesforce OAuth2 endpoints
# ---------------------------------------------------------------------------
SF_AUTH_URL_PROD = "https://login.salesforce.com/services/oauth2/authorize"
SF_AUTH_URL_SANDBOX = "https://test.salesforce.com/services/oauth2/authorize"
SF_TOKEN_URL_PROD = "https://login.salesforce.com/services/oauth2/token"
SF_TOKEN_URL_SANDBOX = "https://test.salesforce.com/services/oauth2/token"

SF_SCOPES = ["api", "refresh_token"]


def build_auth_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    sandbox: bool = False,
) -> str:
    """Generate the Salesforce OAuth2 authorization URL."""
    base = SF_AUTH_URL_SANDBOX if sandbox else SF_AUTH_URL_PROD
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(SF_SCOPES),
        "state": state,
    }
    return f"{base}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    sandbox: bool = False,
) -> Dict[str, Any]:
    """Exchange authorization code for access + refresh tokens.

    Salesforce token response includes ``instance_url`` (the org's API host)
    and ``id`` (the identity URL for the authenticated user).
    """
    token_url = SF_TOKEN_URL_SANDBOX if sandbox else SF_TOKEN_URL_PROD
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                token_url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
            )

        if response.status_code != 200:
            logger.error(
                "Salesforce token exchange failed: %d %s",
                response.status_code,
                response.text,
            )
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
            }

        data = response.json()
        return {
            "success": True,
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "instance_url": data["instance_url"],
            "expires_in": 7200,  # Salesforce access tokens last ~2 hours
        }
    except Exception as e:
        logger.error("Salesforce token exchange error: %s", e)
        return {"success": False, "error": str(e)}


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    sandbox: bool = False,
) -> Dict[str, Any]:
    """Refresh an expired Salesforce access token.

    Note: Salesforce does NOT return a new refresh_token on refresh.
    The original refresh_token remains valid until explicitly revoked.
    """
    token_url = SF_TOKEN_URL_SANDBOX if sandbox else SF_TOKEN_URL_PROD
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                token_url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

        if response.status_code != 200:
            logger.error(
                "Salesforce token refresh failed: %d %s",
                response.status_code,
                response.text,
            )
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
            }

        data = response.json()
        return {
            "success": True,
            "access_token": data["access_token"],
            "expires_in": 7200,
        }
    except Exception as e:
        logger.error("Salesforce token refresh error: %s", e)
        return {"success": False, "error": str(e)}
