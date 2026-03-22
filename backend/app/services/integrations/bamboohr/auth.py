"""BambooHR API key authentication.

BambooHR uses simple API key auth (no OAuth):
- API key as username, literal "x" as password, via HTTP Basic auth
- Base URL: https://api.bamboohr.com/api/gateway.php/{subdomain}/v1/
- All requests require Accept: application/json header
"""

import base64
import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BambooHR API base
# ---------------------------------------------------------------------------
BAMBOOHR_API_BASE = "https://api.bamboohr.com/api/gateway.php"


def build_auth_header(api_key: str) -> str:
    """Build Basic auth header: base64(api_key:x)."""
    credentials = f"{api_key}:x"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def build_base_url(subdomain: str) -> str:
    """Build the BambooHR API base URL for a given company subdomain."""
    return f"{BAMBOOHR_API_BASE}/{subdomain}/v1"


async def validate_api_key(api_key: str, subdomain: str) -> Dict[str, Any]:
    """Validate BambooHR API key by fetching the employee directory.

    Makes a lightweight GET to /employees/directory to confirm
    the credentials are valid.

    Returns:
        {success: bool, employee_count: int, error: str?}
    """
    url = f"{build_base_url(subdomain)}/employees/directory"
    headers = {
        "Authorization": build_auth_header(api_key),
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 401:
            logger.error("BambooHR API key validation failed: 401 Unauthorized")
            return {
                "success": False,
                "employee_count": 0,
                "error": "Invalid API key or subdomain",
            }

        if response.status_code == 403:
            logger.error("BambooHR API key validation failed: 403 Forbidden")
            return {
                "success": False,
                "employee_count": 0,
                "error": "API key does not have sufficient permissions",
            }

        if response.status_code != 200:
            logger.error(
                "BambooHR API key validation failed: %d %s",
                response.status_code,
                response.text[:500],
            )
            return {
                "success": False,
                "employee_count": 0,
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }

        data = response.json()
        employees = data.get("employees", [])
        employee_count = len(employees)

        logger.info(
            "BambooHR API key validated for subdomain=%s, employees=%d",
            subdomain,
            employee_count,
        )
        return {
            "success": True,
            "employee_count": employee_count,
        }

    except httpx.TimeoutException:
        logger.error("BambooHR API key validation timed out for subdomain=%s", subdomain)
        return {
            "success": False,
            "employee_count": 0,
            "error": "Request timed out",
        }
    except Exception as e:
        logger.error("BambooHR API key validation error: %s", e)
        return {
            "success": False,
            "employee_count": 0,
            "error": str(e),
        }
