"""QuickBooks Online API client.

Fetches financial reports (P&L, Balance Sheet, Cash Flow) and entity data
(Chart of Accounts, Invoices, Bills) from the QBO REST API.

API base: https://quickbooks.api.intuit.com/v3/company/{realmId}
Sandbox:  https://sandbox-quickbooks.api.intuit.com/v3/company/{realmId}
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API base URLs
# ---------------------------------------------------------------------------
QBO_API_BASE = "https://quickbooks.api.intuit.com/v3/company"
QBO_SANDBOX_BASE = "https://sandbox-quickbooks.api.intuit.com/v3/company"


class QuickBooksClient:
    """Async client for QuickBooks Online API."""

    def __init__(
        self,
        access_token: str,
        realm_id: str,
        sandbox: bool = False,
    ):
        self.access_token = access_token
        self.realm_id = realm_id
        self.base_url = f"{QBO_SANDBOX_BASE if sandbox else QBO_API_BASE}/{realm_id}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Make a GET request to the QBO API."""
        url = f"{self.base_url}/{path}"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=self._headers(), params=params)

            if response.status_code == 401:
                logger.error("QBO API 401 — token expired or invalid")
                return None
            if response.status_code == 429:
                logger.warning("QBO API rate limited (429)")
                return None
            if response.status_code != 200:
                logger.error("QBO API error %d: %s", response.status_code, response.text[:500])
                return None

            return response.json()
        except Exception as e:
            logger.error("QBO API request failed: %s", e)
            return None

    # ── Reports ───────────────────────────────────────────────────

    async def get_profit_and_loss(
        self,
        start_date: str,
        end_date: str,
        summarize_column_by: str = "Month",
    ) -> Optional[Dict[str, Any]]:
        """Fetch P&L report.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            summarize_column_by: Month, Quarter, Year, Total
        """
        return await self._get("reports/ProfitAndLoss", {
            "start_date": start_date,
            "end_date": end_date,
            "summarize_column_by": summarize_column_by,
            "minorversion": "65",
        })

    async def get_balance_sheet(
        self,
        as_of_date: str,
        summarize_column_by: str = "Total",
    ) -> Optional[Dict[str, Any]]:
        """Fetch Balance Sheet report.

        Args:
            as_of_date: YYYY-MM-DD
        """
        return await self._get("reports/BalanceSheet", {
            "date_macro": "",
            "start_date": as_of_date,
            "end_date": as_of_date,
            "summarize_column_by": summarize_column_by,
            "minorversion": "65",
        })

    async def get_cash_flow(
        self,
        start_date: str,
        end_date: str,
        summarize_column_by: str = "Month",
    ) -> Optional[Dict[str, Any]]:
        """Fetch Cash Flow statement."""
        return await self._get("reports/CashFlow", {
            "start_date": start_date,
            "end_date": end_date,
            "summarize_column_by": summarize_column_by,
            "minorversion": "65",
        })

    # ── Entities ──────────────────────────────────────────────────

    async def get_chart_of_accounts(self) -> List[Dict[str, Any]]:
        """Fetch all accounts (Chart of Accounts)."""
        result = await self._get("query", {
            "query": "SELECT * FROM Account MAXRESULTS 1000",
            "minorversion": "65",
        })
        if not result:
            return []
        qr = result.get("QueryResponse", {})
        return qr.get("Account", [])

    async def get_company_info(self) -> Optional[Dict[str, Any]]:
        """Fetch company info (name, address, etc.)."""
        result = await self._get("query", {
            "query": f"SELECT * FROM CompanyInfo WHERE Id = '{self.realm_id}'",
            "minorversion": "65",
        })
        if not result:
            return None
        qr = result.get("QueryResponse", {})
        companies = qr.get("CompanyInfo", [])
        return companies[0] if companies else None
