"""Workday REST API + RAAS client.

Fetches worker data from the Workday REST API and custom reports via
Report-as-a-Service (RAAS).

REST API base:  https://<host>/ccx/api/v1/<tenant>
RAAS reports:   https://<host>/ccx/service/customreport2/<tenant>/<owner>/<name>

The REST API uses offset-based pagination (limit/offset params).
RAAS reports return all data in a single response (no pagination).
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class WorkdayClient:
    """Async client for Workday REST API + RAAS."""

    def __init__(self, access_token: str, host: str, tenant: str):
        self.access_token = access_token
        self.host = host
        self.tenant = tenant
        self.rest_base = f"https://{host}/ccx/api/v1/{tenant}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    async def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a GET request and return parsed JSON."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    url,
                    headers=self._headers(),
                    params=params,
                )

            if response.status_code == 401:
                logger.error("Workday API 401 -- token expired or invalid")
                return None
            if response.status_code == 429:
                logger.warning("Workday API rate limited (429)")
                return None
            if response.status_code != 200:
                logger.error(
                    "Workday API error %d: %s",
                    response.status_code,
                    response.text[:500],
                )
                return None

            return response.json()
        except Exception as e:
            logger.error("Workday API request failed: %s", e)
            return None

    # -- REST API: Workers -----------------------------------------------------

    async def get_workers(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch all workers via the Workday REST API with auto-pagination.

        GET /ccx/api/v1/<tenant>/workers?limit=100&offset=0

        Returns the full list of worker records across all pages.
        """
        all_workers: List[Dict[str, Any]] = []
        current_offset = offset

        while True:
            url = f"{self.rest_base}/workers"
            result = await self._get(url, {"limit": limit, "offset": current_offset})
            if not result:
                break

            workers = result.get("data", [])
            if not workers:
                break

            all_workers.extend(workers)

            # Check if there are more pages
            total = result.get("total", 0)
            current_offset += limit
            if current_offset >= total:
                break

        logger.info("Fetched %d workers from Workday REST API", len(all_workers))
        return all_workers

    # -- RAAS Reports ----------------------------------------------------------

    async def fetch_raas_report(
        self,
        report_url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a RAAS (Report-as-a-Service) custom report.

        The customer provides the report URL during connection setup.
        The URL looks like:
          https://<host>/ccx/service/customreport2/<tenant>/<report_owner>/<report_name>

        GET <report_url>?format=json[&param=value]

        Returns the Report_Entry list from the JSON response.
        """
        request_params: Dict[str, Any] = {"format": "json"}
        if params:
            request_params.update(params)

        result = await self._get(report_url, request_params)
        if not result:
            return []

        # RAAS JSON response wraps data in Report_Entry
        entries = result.get("Report_Entry", [])
        logger.info(
            "Fetched %d entries from RAAS report: %s",
            len(entries),
            report_url.rsplit("/", 1)[-1],
        )
        return entries

    async def get_headcount_report(
        self,
        report_url: str,
        effective_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch headcount RAAS report.

        Expected report fields:
            Worker_ID, Legal_Name, Hire_Date, Supervisory_Organization,
            Cost_Center, Location, Job_Profile, Worker_Status

        Args:
            report_url: Full URL to the RAAS headcount report.
            effective_date: Optional date filter (YYYY-MM-DD).
        """
        params: Dict[str, Any] = {}
        if effective_date:
            params["Effective_Date"] = effective_date

        entries = await self.fetch_raas_report(report_url, params or None)
        logger.info("Headcount report returned %d workers", len(entries))
        return entries

    async def get_compensation_report(
        self,
        report_url: str,
        effective_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch compensation RAAS report.

        Expected report fields:
            Cost_Center, Department, Base_Pay, Bonus_Target,
            Benefits_Cost, Total_Annual_Comp

        Args:
            report_url: Full URL to the RAAS compensation report.
            effective_date: Optional date filter (YYYY-MM-DD).
        """
        params: Dict[str, Any] = {}
        if effective_date:
            params["Effective_Date"] = effective_date

        entries = await self.fetch_raas_report(report_url, params or None)
        logger.info("Compensation report returned %d entries", len(entries))
        return entries
