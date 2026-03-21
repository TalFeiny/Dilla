"""NetSuite authentication — OAuth 2.0 and Token-Based Auth (TBA).

OAuth 2.0 is the recommended path for new integrations.
TBA (OAuth 1.0) is supported for existing customer setups but deprecated from 2027.1.
"""

import base64
import hashlib
import hmac
import logging
import time
import uuid
from typing import Any, Dict
from urllib.parse import quote, urlencode

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OAuth 2.0
# ---------------------------------------------------------------------------

def build_oauth2_auth_url(
    account_id: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str = "rest_webservices",
) -> str:
    """Generate the NetSuite OAuth 2.0 authorization URL.

    account_id: NetSuite account ID (e.g. "1234567" or "1234567_SB1" for sandbox)
    """
    base = f"https://{account_id}.suitetalk.api.netsuite.com"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    return f"{base}/services/rest/auth/oauth2/v1/authorize?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    account_id: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> Dict[str, Any]:
    """Exchange authorization code for OAuth 2.0 tokens."""
    token_url = (
        f"https://{account_id}.suitetalk.api.netsuite.com"
        "/services/rest/auth/oauth2/v1/token"
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

        if response.status_code != 200:
            logger.error("NetSuite token exchange failed: %d %s", response.status_code, response.text)
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        data = response.json()
        return {
            "success": True,
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_in": data.get("expires_in", 3600),
        }
    except Exception as e:
        logger.error("NetSuite token exchange error: %s", e)
        return {"success": False, "error": str(e)}


async def refresh_access_token(
    refresh_token: str,
    account_id: str,
    client_id: str,
    client_secret: str,
) -> Dict[str, Any]:
    """Refresh an expired NetSuite OAuth 2.0 access token."""
    token_url = (
        f"https://{account_id}.suitetalk.api.netsuite.com"
        "/services/rest/auth/oauth2/v1/token"
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

        if response.status_code != 200:
            logger.error("NetSuite token refresh failed: %d %s", response.status_code, response.text)
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        data = response.json()
        return {
            "success": True,
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", refresh_token),
            "expires_in": data.get("expires_in", 3600),
        }
    except Exception as e:
        logger.error("NetSuite token refresh error: %s", e)
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Token-Based Auth (TBA) — OAuth 1.0 HMAC-SHA256
# ---------------------------------------------------------------------------

def build_tba_authorization_header(
    account_id: str,
    consumer_key: str,
    consumer_secret: str,
    token_key: str,
    token_secret: str,
    http_method: str,
    url: str,
) -> str:
    """Build OAuth 1.0 Authorization header for NetSuite TBA.

    Uses HMAC-SHA256 signature method as required by NetSuite.
    """
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))

    # Base parameters (sorted alphabetically)
    params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": timestamp,
        "oauth_token": token_key,
        "oauth_version": "1.0",
    }

    # Build signature base string
    param_string = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}"
        for k, v in sorted(params.items())
    )
    base_string = f"{http_method.upper()}&{quote(url, safe='')}&{quote(param_string, safe='')}"

    # Sign with HMAC-SHA256
    signing_key = f"{quote(consumer_secret, safe='')}&{quote(token_secret, safe='')}"
    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    # Build header
    params["oauth_signature"] = signature
    auth_parts = ", ".join(
        f'{quote(k, safe="")}="{quote(v, safe="")}"'
        for k, v in sorted(params.items())
    )
    realm = account_id.replace("_", "-")
    return f'OAuth realm="{realm}", {auth_parts}'
