"""NetSuite REST API + SuiteQL client.

Uses SuiteQL (SQL-like queries) for financial data extraction, which is
more flexible than the standard REST record API for reporting.

API base: https://{account_id}.suitetalk.api.netsuite.com/services/rest
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.services.integrations.netsuite.auth import build_tba_authorization_header

logger = logging.getLogger(__name__)


class NetSuiteClient:
    """Async client for NetSuite REST API and SuiteQL."""

    def __init__(
        self,
        account_id: str,
        access_token: Optional[str] = None,
        # TBA credentials (OAuth 1.0)
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        token_key: Optional[str] = None,
        token_secret: Optional[str] = None,
    ):
        self.account_id = account_id
        self.access_token = access_token
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token_key = token_key
        self.token_secret = token_secret
        self.base_url = f"https://{account_id}.suitetalk.api.netsuite.com/services/rest"

    @property
    def _uses_tba(self) -> bool:
        return bool(self.consumer_key and self.token_key)

    def _headers(self, url: str, method: str = "GET") -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "transient",
        }
        if self._uses_tba:
            headers["Authorization"] = build_tba_authorization_header(
                self.account_id,
                self.consumer_key,
                self.consumer_secret,
                self.token_key,
                self.token_secret,
                method,
                url,
            )
        elif self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _get(self, path: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{path}"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    url,
                    headers=self._headers(url, "GET"),
                    params=params,
                )

            if response.status_code == 401:
                logger.error("NetSuite API 401 — auth failed")
                return None
            if response.status_code == 429:
                logger.warning("NetSuite API rate limited")
                return None
            if response.status_code != 200:
                logger.error("NetSuite API %d: %s", response.status_code, response.text[:500])
                return None

            return response.json()
        except Exception as e:
            logger.error("NetSuite API request failed: %s", e)
            return None

    # ── SuiteQL ───────────────────────────────────────────────────

    async def execute_suiteql(
        self,
        query: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Execute a SuiteQL query and return all results (with pagination).

        POST /services/rest/query/v1/suiteql
        Body: {"q": "SELECT ..."}
        """
        url = f"{self.base_url}/query/v1/suiteql"
        all_items: List[Dict[str, Any]] = []
        current_offset = offset

        while True:
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(
                        url,
                        headers={
                            **self._headers(url, "POST"),
                            "Prefer": f"transient, resultOffset={current_offset}, resultLimit={limit}",
                        },
                        json={"q": query},
                    )

                if response.status_code not in (200, 204):
                    logger.error("SuiteQL error %d: %s", response.status_code, response.text[:500])
                    break

                if response.status_code == 204:
                    break

                data = response.json()
                items = data.get("items", [])
                if not items:
                    break

                all_items.extend(items)

                # Check if there are more pages
                if data.get("hasMore", False):
                    current_offset += limit
                else:
                    break

            except Exception as e:
                logger.error("SuiteQL execution failed: %s", e)
                break

        return all_items

    # ── Financial Data Queries ────────────────────────────────────

    async def get_profit_and_loss(
        self,
        from_date: str,
        to_date: str,
        subsidiary_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch P&L data via SuiteQL — GL transactions grouped by account and month.

        Args:
            from_date: YYYY-MM-DD
            to_date: YYYY-MM-DD
            subsidiary_id: Optional subsidiary filter (for multi-entity)
        """
        sub_filter = f"AND tl.subsidiary = {subsidiary_id}" if subsidiary_id else ""

        query = f"""
            SELECT
                a.acctnumber AS account_code,
                a.acctname AS account_name,
                a.accttype AS account_type,
                TO_CHAR(t.trandate, 'YYYY-MM') AS period,
                SUM(tl.amount) AS amount
            FROM transactionLine tl
            JOIN transaction t ON t.id = tl.transaction
            JOIN account a ON a.id = tl.account
            WHERE t.trandate >= '{from_date}'
              AND t.trandate <= '{to_date}'
              AND a.accttype IN ('Income', 'COGS', 'Expense', 'OthIncome', 'OthExpense')
              AND t.posting = 'T'
              {sub_filter}
            GROUP BY a.acctnumber, a.acctname, a.accttype, TO_CHAR(t.trandate, 'YYYY-MM')
            ORDER BY TO_CHAR(t.trandate, 'YYYY-MM'), a.acctnumber
        """
        return await self.execute_suiteql(query)

    async def get_balance_sheet(
        self,
        as_of_date: str,
        subsidiary_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch Balance Sheet data — cumulative account balances as of a date.

        Args:
            as_of_date: YYYY-MM-DD
        """
        sub_filter = f"AND tl.subsidiary = {subsidiary_id}" if subsidiary_id else ""

        query = f"""
            SELECT
                a.acctnumber AS account_code,
                a.acctname AS account_name,
                a.accttype AS account_type,
                SUM(tl.amount) AS balance
            FROM transactionLine tl
            JOIN transaction t ON t.id = tl.transaction
            JOIN account a ON a.id = tl.account
            WHERE t.trandate <= '{as_of_date}'
              AND a.accttype IN (
                  'Bank', 'AcctRec', 'OthCurrAsset', 'FixedAsset', 'OthAsset',
                  'AcctPay', 'OthCurrLiab', 'LongTermLiab', 'Equity'
              )
              AND t.posting = 'T'
              {sub_filter}
            GROUP BY a.acctnumber, a.acctname, a.accttype
            ORDER BY a.acctnumber
        """
        return await self.execute_suiteql(query)

    async def get_chart_of_accounts(self) -> List[Dict[str, Any]]:
        """Fetch the full chart of accounts via REST record API."""
        result = await self._get("record/v1/account", {"limit": 1000})
        if not result:
            return []
        return result.get("items", [])

    async def get_subsidiaries(self) -> List[Dict[str, Any]]:
        """Fetch list of subsidiaries (for multi-entity NetSuite)."""
        query = """
            SELECT id, name, isinactive
            FROM subsidiary
            WHERE isinactive = 'F'
            ORDER BY name
        """
        return await self.execute_suiteql(query)
