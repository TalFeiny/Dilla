"""SAP authentication for S/4HANA Cloud and Business One.

Two auth modes:
1. S/4HANA Cloud: OAuth 2.0 client credentials grant (Communication Scenario SAP_COM_0087)
   - Token URL: https://<tenant>.authentication.<region>.hana.ondemand.com/oauth/token
   - Tokens last ~12 hours; refresh = re-fetch with same credentials
   - Credentials are per-connection (not from env)

2. Business One: Session-based auth via Service Layer v2
   - Login: POST /b1s/v2/Login  (CompanyDB + user/pass)
   - Returns B1SESSION + ROUTEID cookies (30-min lifetime)
   - Logout: POST /b1s/v2/Logout
"""

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# S/4HANA Cloud — OAuth 2.0 client credentials
# ---------------------------------------------------------------------------

async def s4_get_token(
    client_id: str,
    client_secret: str,
    token_url: str,
) -> Dict[str, Any]:
    """Get S/4HANA Cloud access token via client credentials.

    Args:
        client_id: OAuth client ID from Communication Arrangement (SAP_COM_0087).
        client_secret: OAuth client secret.
        token_url: Full token endpoint, e.g.
            https://<tenant>.authentication.<region>.hana.ondemand.com/oauth/token

    Returns:
        {success, access_token, expires_in, token_type} or {success: False, error}.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )

        if response.status_code != 200:
            logger.error(
                "S/4HANA token request failed: %d %s",
                response.status_code,
                response.text[:500],
            )
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        data = response.json()
        return {
            "success": True,
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 43200),  # ~12 hours default
            "token_type": data.get("token_type", "bearer"),
        }
    except Exception as e:
        logger.error("S/4HANA token request error: %s", e)
        return {"success": False, "error": str(e)}


async def s4_refresh_token(
    client_id: str,
    client_secret: str,
    token_url: str,
) -> Dict[str, Any]:
    """Re-fetch S/4HANA Cloud access token.

    S/4 uses client credentials grant, so there is no separate refresh token.
    Refreshing simply means obtaining a new token with the same credentials.
    """
    return await s4_get_token(client_id, client_secret, token_url)


# ---------------------------------------------------------------------------
# SAP Business One — Service Layer v2 session auth
# ---------------------------------------------------------------------------

async def b1_login(
    server_url: str,
    company_db: str,
    username: str,
    password: str,
) -> Dict[str, Any]:
    """Login to SAP Business One Service Layer.

    Args:
        server_url: Base URL, e.g. "https://server:50000" (no trailing slash).
        company_db: Company database name.
        username: Service Layer username.
        password: Service Layer password.

    Returns:
        {success, session_id, route_id} or {success: False, error}.
        session_id = B1SESSION cookie, route_id = ROUTEID cookie.
        Session lasts 30 minutes.
    """
    url = f"{server_url.rstrip('/')}/b1s/v2/Login"
    payload = {
        "CompanyDB": company_db,
        "UserName": username,
        "Password": password,
    }

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        if response.status_code != 200:
            logger.error(
                "B1 login failed: %d %s",
                response.status_code,
                response.text[:500],
            )
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        # Extract session cookies
        session_id = None
        route_id = None
        for cookie_name, cookie_value in response.cookies.items():
            if cookie_name == "B1SESSION":
                session_id = cookie_value
            elif cookie_name == "ROUTEID":
                route_id = cookie_value

        if not session_id:
            # Some B1 versions return SessionId in the JSON body
            data = response.json()
            session_id = data.get("SessionId", "")

        if not session_id:
            logger.error("B1 login succeeded but no B1SESSION cookie or SessionId found")
            return {"success": False, "error": "No session ID in login response"}

        return {
            "success": True,
            "session_id": session_id,
            "route_id": route_id or "",
        }
    except Exception as e:
        logger.error("B1 login error: %s", e)
        return {"success": False, "error": str(e)}


async def b1_logout(
    server_url: str,
    session_id: str,
    route_id: str,
) -> None:
    """Logout from SAP Business One Service Layer.

    Args:
        server_url: Base URL, e.g. "https://server:50000".
        session_id: B1SESSION cookie value.
        route_id: ROUTEID cookie value.
    """
    url = f"{server_url.rstrip('/')}/b1s/v2/Logout"
    cookies = {"B1SESSION": session_id}
    if route_id:
        cookies["ROUTEID"] = route_id

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            await client.post(url, cookies=cookies)
        logger.info("B1 session logged out")
    except Exception as e:
        # Logout failure is non-critical — session will expire in 30 min anyway
        logger.warning("B1 logout error (non-critical): %s", e)
