"""BambooHR REST API client.

Async client for the BambooHR API v1.  Handles employee directory lookups,
custom report generation, and incremental change detection.

API docs: https://documentation.bamboohr.com/reference
Rate limit: keep requests under 1/sec to avoid throttling.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.services.integrations.bamboohr.auth import build_auth_header, build_base_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default fields for the custom compensation report
# ---------------------------------------------------------------------------
DEFAULT_COMP_FIELDS = [
    "id",
    "firstName",
    "lastName",
    "department",
    "division",
    "location",
    "jobTitle",
    "status",
    "hireDate",
    "terminationDate",
    "payRate",
    "payType",
    "payPer",
]

# Rate-limit delay between consecutive requests (seconds)
_RATE_LIMIT_DELAY = 1.1


class BambooHRClient:
    """Async client for BambooHR REST API v1."""

    def __init__(self, api_key: str, subdomain: str):
        self.base_url = build_base_url(subdomain)
        self.auth_header = build_auth_header(api_key)
        self.subdomain = subdomain
        self._last_request_at: float = 0

    # ── Internal helpers ──────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.auth_header,
            "Accept": "application/json",
        }

    async def _throttle(self) -> None:
        """Ensure at least _RATE_LIMIT_DELAY seconds between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_at
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        self._last_request_at = asyncio.get_event_loop().time()

    async def _get(
        self, path: str, params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Make a throttled GET request to the BambooHR API."""
        await self._throttle()
        url = f"{self.base_url}/{path}"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    url, headers=self._headers(), params=params
                )

            if response.status_code == 401:
                logger.error("BambooHR API 401 — API key expired or invalid")
                return None
            if response.status_code == 429:
                logger.warning("BambooHR API rate limited (429)")
                return None
            if response.status_code != 200:
                logger.error(
                    "BambooHR API error %d: %s",
                    response.status_code,
                    response.text[:500],
                )
                return None

            return response.json()
        except Exception as e:
            logger.error("BambooHR API GET request failed: %s", e)
            return None

    async def _post(
        self,
        path: str,
        json_body: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a throttled POST request to the BambooHR API."""
        await self._throttle()
        url = f"{self.base_url}/{path}"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    url,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json=json_body,
                    params=params,
                )

            if response.status_code == 401:
                logger.error("BambooHR API 401 — API key expired or invalid")
                return None
            if response.status_code == 429:
                logger.warning("BambooHR API rate limited (429)")
                return None
            if response.status_code != 200:
                logger.error(
                    "BambooHR API error %d: %s",
                    response.status_code,
                    response.text[:500],
                )
                return None

            return response.json()
        except Exception as e:
            logger.error("BambooHR API POST request failed: %s", e)
            return None

    # ── Public API methods ────────────────────────────────────────

    async def get_employee_directory(self) -> List[Dict[str, Any]]:
        """Fetch the employee directory.

        GET /v1/employees/directory

        Returns all active employees with fields:
        id, displayName, department, division, jobTitle, location, workEmail.
        """
        data = await self._get("employees/directory")
        if not data:
            return []
        return data.get("employees", [])

    async def get_custom_report(
        self, fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Run a custom report to fetch specific employee fields.

        POST /v1/reports/custom?format=JSON

        The request body specifies which fields to include.
        Default fields cover headcount + compensation data:
        id, firstName, lastName, department, division, location,
        jobTitle, status, hireDate, terminationDate, payRate,
        payType, payPer.

        Args:
            fields: List of BambooHR field names.  Falls back to
                     DEFAULT_COMP_FIELDS when not provided.

        Returns:
            List of employee dicts with the requested fields.
        """
        report_fields = fields or DEFAULT_COMP_FIELDS

        body = {
            "title": "Dilla AI Compensation Report",
            "fields": [{"id": f} for f in report_fields],
        }

        data = await self._post("reports/custom", json_body=body, params={"format": "JSON"})
        if not data:
            return []
        return data.get("employees", [])

    async def get_changed_employees(self, since: str) -> List[str]:
        """Get IDs of employees changed since a given timestamp.

        GET /v1/employees/changed/?since=YYYY-MM-DDTHH:MM:SSZ

        Useful for incremental sync — only re-process employees
        whose records changed since the last sync.

        Args:
            since: ISO-8601 timestamp, e.g. "2024-01-15T00:00:00Z".

        Returns:
            List of employee ID strings that have been modified.
        """
        data = await self._get("employees/changed", params={"since": since})
        if not data:
            return []

        # Response shape: {"employees": {"123": {...}, "456": {...}}}
        employees = data.get("employees", {})
        return list(employees.keys())

    async def get_employee(self, employee_id: str, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single employee by ID.

        GET /v1/employees/{id}/?fields=field1,field2,...

        Args:
            employee_id: BambooHR employee ID.
            fields: Specific fields to request.  Defaults to
                     DEFAULT_COMP_FIELDS.

        Returns:
            Employee dict or None on failure.
        """
        field_list = ",".join(fields or DEFAULT_COMP_FIELDS)
        return await self._get(
            f"employees/{employee_id}",
            params={"fields": field_list},
        )
