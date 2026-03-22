"""Salesforce REST API client.

Fetches CRM data (Opportunities, Accounts, Contacts) from the Salesforce
REST API v66.0.  All queries use SOQL with automatic pagination.

API base: {instance_url}/services/data/v66.0
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SF_API_VERSION = "v66.0"
REQUEST_TIMEOUT = 60  # seconds


class SalesforceClient:
    """Async client for Salesforce REST API v66.0."""

    def __init__(self, access_token: str, instance_url: str):
        self.access_token = access_token
        # Strip trailing slash for clean URL joins
        self.instance_url = instance_url.rstrip("/")
        self.base_url = f"{self.instance_url}/services/data/{SF_API_VERSION}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    # ── Low-level helpers ─────────────────────────────────────────

    async def _get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Make a GET request to the Salesforce API.

        Handles 401 (token expired), 429 (rate limited), and timeouts.
        """
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, headers=self._headers(), params=params)

            if response.status_code == 401:
                logger.error("Salesforce API 401 — token expired or invalid")
                return None
            if response.status_code == 429:
                logger.warning("Salesforce API rate limited (429)")
                return None
            if response.status_code != 200:
                logger.error(
                    "Salesforce API error %d: %s",
                    response.status_code,
                    response.text[:500],
                )
                return None

            return response.json()
        except httpx.TimeoutException:
            logger.error("Salesforce API request timed out after %ds", REQUEST_TIMEOUT)
            return None
        except Exception as e:
            logger.error("Salesforce API request failed: %s", e)
            return None

    async def _query(self, soql: str) -> List[Dict]:
        """Execute a SOQL query with auto-pagination via nextRecordsUrl.

        Salesforce returns up to 2,000 records per page.  If ``done`` is
        False, the response contains a ``nextRecordsUrl`` to fetch the
        next page.
        """
        url = f"{self.base_url}/query/"
        result = await self._get(url, params={"q": soql})
        if result is None:
            return []

        records: List[Dict] = result.get("records", [])

        # Paginate until done
        while not result.get("done", True):
            next_url = result.get("nextRecordsUrl")
            if not next_url:
                break
            # nextRecordsUrl is a relative path like /services/data/v66.0/query/...
            full_url = f"{self.instance_url}{next_url}"
            result = await self._get(full_url)
            if result is None:
                break
            records.extend(result.get("records", []))

        return records

    # ── Opportunities ─────────────────────────────────────────────

    async def get_opportunities(self, since: str = None) -> List[Dict]:
        """Fetch Opportunity records via SOQL.

        Args:
            since: ISO datetime string (e.g. '2024-01-01T00:00:00Z').
                   If provided, only returns records modified after this date.
        """
        soql = (
            "SELECT Id, Name, AccountId, Account.Name, Amount, StageName, "
            "CloseDate, Probability, ForecastCategory, ExpectedRevenue, Type, "
            "IsClosed, IsWon, OwnerId, CreatedDate, LastModifiedDate, "
            "FiscalQuarter, FiscalYear "
            "FROM Opportunity"
        )
        if since:
            soql += f" WHERE LastModifiedDate > '{since}'"
        return await self._query(soql)

    async def get_won_opportunities(self, from_date: str, to_date: str) -> List[Dict]:
        """Fetch closed-won deals for revenue reconciliation.

        Args:
            from_date: YYYY-MM-DD
            to_date:   YYYY-MM-DD
        """
        soql = (
            "SELECT Id, Name, AccountId, Account.Name, Amount, StageName, "
            "CloseDate, Probability, ForecastCategory, ExpectedRevenue, Type, "
            "IsClosed, IsWon, OwnerId, CreatedDate, LastModifiedDate, "
            "FiscalQuarter, FiscalYear "
            "FROM Opportunity "
            f"WHERE IsWon = true AND CloseDate >= {from_date} AND CloseDate <= {to_date}"
        )
        return await self._query(soql)

    async def get_pipeline(self) -> List[Dict]:
        """Fetch open pipeline (opportunities not yet closed)."""
        soql = (
            "SELECT Id, Name, AccountId, Account.Name, Amount, StageName, "
            "CloseDate, Probability, ForecastCategory, ExpectedRevenue, Type, "
            "IsClosed, IsWon, OwnerId, CreatedDate, LastModifiedDate, "
            "FiscalQuarter, FiscalYear "
            "FROM Opportunity "
            "WHERE IsClosed = false"
        )
        return await self._query(soql)

    # ── Accounts ──────────────────────────────────────────────────

    async def get_accounts(self, since: str = None) -> List[Dict]:
        """Fetch Account records via SOQL.

        Args:
            since: ISO datetime string.  If provided, filters by CreatedDate.
        """
        soql = (
            "SELECT Id, Name, Industry, Type, AnnualRevenue, BillingCountry, "
            "NumberOfEmployees, Rating, OwnerId, ParentId, CreatedDate "
            "FROM Account"
        )
        if since:
            soql += f" WHERE CreatedDate > '{since}'"
        return await self._query(soql)

    # ── Contacts ──────────────────────────────────────────────────

    async def get_contacts(self, since: str = None) -> List[Dict]:
        """Fetch Contact records via SOQL.

        Args:
            since: ISO datetime string.  If provided, filters by CreatedDate.
        """
        soql = (
            "SELECT Id, FirstName, LastName, Email, Phone, Title, Department, "
            "AccountId, Account.Name, OwnerId, CreatedDate "
            "FROM Contact"
        )
        if since:
            soql += f" WHERE CreatedDate > '{since}'"
        return await self._query(soql)

    # ── API Limits ────────────────────────────────────────────────

    async def get_api_limits(self) -> Dict:
        """Check Salesforce API usage / rate limits.

        GET /services/data/v66.0/limits/
        """
        url = f"{self.base_url}/limits/"
        result = await self._get(url)
        return result or {}
