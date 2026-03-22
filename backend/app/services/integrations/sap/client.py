"""SAP API clients for S/4HANA Cloud and Business One.

Two client classes:
- SAPS4Client: OData APIs on S/4HANA Cloud (OAuth bearer token)
- SAPB1Client: Service Layer v2 on Business One (B1SESSION cookies)

Both handle OData pagination (nextLink / $skiptoken), 60-second timeouts,
error responses, and 429 rate limiting with Retry-After backoff.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared pagination / retry helpers
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 60  # seconds
_MAX_RETRIES = 3
_MAX_PAGES = 100  # safety cap on pagination loops


async def _retry_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Execute an HTTP request with retry logic for 429 / 5xx errors."""
    last_exc: Optional[Exception] = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.request(method, url, **kwargs)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5))
                logger.warning(
                    "SAP API 429 rate limited, retrying after %ds (attempt %d/%d)",
                    retry_after, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(retry_after)
                continue

            if response.status_code >= 500 and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(
                    "SAP API %d server error, retrying in %ds (attempt %d/%d)",
                    response.status_code, wait, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(wait)
                continue

            return response

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(
                    "SAP API connection error, retrying in %ds: %s", wait, e,
                )
                await asyncio.sleep(wait)
                continue
            raise

    # Should not reach here, but just in case
    if last_exc:
        raise last_exc
    raise RuntimeError("Exhausted retries without response")


# ═══════════════════════════════════════════════════════════════════════════
# S/4HANA Cloud OData Client
# ═══════════════════════════════════════════════════════════════════════════

class SAPS4Client:
    """Async client for SAP S/4HANA Cloud OData APIs."""

    def __init__(self, access_token: str, base_url: str):
        """
        Args:
            access_token: OAuth2 bearer token from s4_get_token().
            base_url: S/4HANA tenant URL, e.g. "https://<tenant>.s4hana.cloud.sap".
        """
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    async def _odata_get_all(
        self, url: str, params: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """GET an OData collection, following @odata.nextLink for pagination.

        S/4 uses $skiptoken-based pagination — the next page URL is returned
        in the response body as ``@odata.nextLink`` (or ``d.__next`` for
        older OData v2 responses).  We do NOT use $top/$skip.
        """
        results: List[Dict[str, Any]] = []
        page = 0

        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            next_url: Optional[str] = url

            while next_url and page < _MAX_PAGES:
                response = await _retry_with_backoff(
                    client, "GET", next_url,
                    headers=self._headers(),
                    params=params if page == 0 else None,  # params only on first call
                )

                if response.status_code == 401:
                    logger.error("S/4 OData 401 — token expired or invalid")
                    break
                if response.status_code != 200:
                    logger.error(
                        "S/4 OData error %d: %s",
                        response.status_code, response.text[:500],
                    )
                    break

                data = response.json()

                # OData v4 structure: {"value": [...], "@odata.nextLink": "..."}
                if "value" in data:
                    results.extend(data["value"])
                    next_url = data.get("@odata.nextLink")
                # OData v2 structure: {"d": {"results": [...], "__next": "..."}}
                elif "d" in data:
                    d = data["d"]
                    if isinstance(d, dict) and "results" in d:
                        results.extend(d["results"])
                        next_url = d.get("__next")
                    elif isinstance(d, list):
                        results.extend(d)
                        next_url = None
                    else:
                        # Single entity
                        results.append(d)
                        next_url = None
                else:
                    break

                page += 1

        logger.info("S/4 OData fetched %d records in %d pages from %s", len(results), page, url)
        return results

    # ── Trial Balance ─────────────────────────────────────────────

    async def get_trial_balance(
        self,
        company_code: str,
        fiscal_year: int,
        fiscal_period: int,
    ) -> List[Dict]:
        """Fetch trial balance from S/4HANA CDS view.

        API: GET /sap/opu/odata/sap/C_TRIALBALANCE_CDS/C_TRIALBALANCE
        Filters: CompanyCode, FiscalYear, FiscalPeriod

        Key fields in response:
            GLAccount, GLAccountName, CompanyCode, FiscalYear, FiscalPeriod,
            StartingBalanceAmtInCoCodeCrcy, DebitAmountInCoCodeCrcy,
            CreditAmountInCoCodeCrcy, EndingBalanceAmtInCoCodeCrcy,
            ProfitCenter, CostCenter
        """
        url = f"{self.base_url}/sap/opu/odata/sap/C_TRIALBALANCE_CDS/C_TRIALBALANCE"
        period_str = str(fiscal_period).zfill(3)
        params = {
            "$filter": (
                f"CompanyCode eq '{company_code}' "
                f"and FiscalYear eq '{fiscal_year}' "
                f"and FiscalPeriod eq '{period_str}'"
            ),
            "$format": "json",
        }
        return await self._odata_get_all(url, params)

    # ── Chart of Accounts ─────────────────────────────────────────

    async def get_chart_of_accounts(
        self, chart_of_accounts: str = "YCOA",
    ) -> List[Dict]:
        """Fetch GL accounts from S/4HANA.

        API: GET /sap/opu/odata/sap/API_GLACCOUNTINCHARTOFACCOUNTS_SRV
                 /A_GLAccountInChartOfAccounts

        GLAccountType values:
            P = Revenue (Profit & Loss)
            X = Expense (Profit & Loss)
            S = Equity (Balance Sheet)
            A = Asset (Balance Sheet)
            L = Liability (Balance Sheet)
        """
        url = (
            f"{self.base_url}/sap/opu/odata/sap/"
            f"API_GLACCOUNTINCHARTOFACCOUNTS_SRV/A_GLAccountInChartOfAccounts"
        )
        params = {
            "$filter": f"ChartOfAccounts eq '{chart_of_accounts}'",
            "$format": "json",
        }
        return await self._odata_get_all(url, params)

    # ── Journal Entries ───────────────────────────────────────────

    async def get_journal_entries(
        self,
        company_code: str,
        from_date: str,
        to_date: str,
    ) -> List[Dict]:
        """Fetch journal entry line items from S/4HANA.

        API: GET /sap/opu/odata/sap/API_JOURNALENTRYITEMBASIC_SRV
                 /A_JournalEntryItemBasic
        Filters: CompanyCode, PostingDate range.

        Args:
            company_code: SAP company code.
            from_date: Start date, "YYYY-MM-DD".
            to_date: End date, "YYYY-MM-DD".
        """
        url = (
            f"{self.base_url}/sap/opu/odata/sap/"
            f"API_JOURNALENTRYITEMBASIC_SRV/A_JournalEntryItemBasic"
        )
        params = {
            "$filter": (
                f"CompanyCode eq '{company_code}' "
                f"and PostingDate ge datetime'{from_date}T00:00:00' "
                f"and PostingDate le datetime'{to_date}T23:59:59'"
            ),
            "$format": "json",
        }
        return await self._odata_get_all(url, params)

    # ── Cost Centers ──────────────────────────────────────────────

    async def get_cost_centers(self, company_code: str) -> List[Dict]:
        """Fetch cost centers from S/4HANA.

        API: GET /sap/opu/odata/sap/API_COSTCENTER_SRV/A_CostCenter
        """
        url = f"{self.base_url}/sap/opu/odata/sap/API_COSTCENTER_SRV/A_CostCenter"
        params = {
            "$filter": f"CompanyCode eq '{company_code}'",
            "$format": "json",
        }
        return await self._odata_get_all(url, params)


# ═══════════════════════════════════════════════════════════════════════════
# SAP Business One Service Layer v2 Client
# ═══════════════════════════════════════════════════════════════════════════

class SAPB1Client:
    """Async client for SAP Business One Service Layer v2."""

    def __init__(self, server_url: str, session_id: str, route_id: str):
        """
        Args:
            server_url: Base URL, e.g. "https://server:50000".
            session_id: B1SESSION cookie from b1_login().
            route_id: ROUTEID cookie from b1_login().
        """
        self.server_url = server_url.rstrip("/")
        self.session_id = session_id
        self.route_id = route_id

    def _cookies(self) -> Dict[str, str]:
        cookies = {"B1SESSION": self.session_id}
        if self.route_id:
            cookies["ROUTEID"] = self.route_id
        return cookies

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _sl_get_all(
        self, path: str, params: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """GET a Service Layer collection, following odata.nextLink for pagination.

        B1 Service Layer v2 uses OData v4-style pagination with
        ``@odata.nextLink`` containing a ``$skiptoken`` parameter.
        """
        results: List[Dict[str, Any]] = []
        url: Optional[str] = f"{self.server_url}{path}"
        page = 0

        async with httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT, verify=False,
        ) as client:
            while url and page < _MAX_PAGES:
                response = await _retry_with_backoff(
                    client, "GET", url,
                    headers=self._headers(),
                    cookies=self._cookies(),
                    params=params if page == 0 else None,
                )

                if response.status_code == 401:
                    logger.error("B1 Service Layer 401 — session expired")
                    break
                if response.status_code != 200:
                    logger.error(
                        "B1 Service Layer error %d: %s",
                        response.status_code, response.text[:500],
                    )
                    break

                data = response.json()

                if "value" in data:
                    results.extend(data["value"])
                    next_link = data.get("@odata.nextLink", data.get("odata.nextLink"))
                    if next_link:
                        # nextLink can be relative or absolute
                        if next_link.startswith("http"):
                            url = next_link
                        else:
                            url = f"{self.server_url}{next_link}"
                    else:
                        url = None
                else:
                    # Single entity or unexpected format
                    if isinstance(data, list):
                        results.extend(data)
                    elif isinstance(data, dict):
                        results.append(data)
                    url = None

                page += 1

        logger.info("B1 SL fetched %d records in %d pages from %s", len(results), page, path)
        return results

    # ── Journal Entries ───────────────────────────────────────────

    async def get_journal_entries(
        self, from_date: str, to_date: str,
    ) -> List[Dict]:
        """Fetch journal entries from Business One.

        API: GET /b1s/v2/JournalEntries
        Filter: ReferenceDate range.

        Returns journal entry headers with JournalEntryLines array
        containing AccountCode, Debit, Credit, ShortName, etc.

        Args:
            from_date: Start date, "YYYY-MM-DD".
            to_date: End date, "YYYY-MM-DD".
        """
        params = {
            "$filter": (
                f"ReferenceDate ge '{from_date}' "
                f"and ReferenceDate le '{to_date}'"
            ),
            "$select": (
                "JournalEntryCode,ReferenceDate,Memo,Reference,"
                "JournalEntryLines"
            ),
        }
        return await self._sl_get_all("/b1s/v2/JournalEntries", params)

    # ── Chart of Accounts ─────────────────────────────────────────

    async def get_chart_of_accounts(self) -> List[Dict]:
        """Fetch chart of accounts from Business One.

        API: GET /b1s/v2/ChartOfAccounts

        Key fields: AcctCode, AcctName, AcctType
        AcctType values:
            it_Revenue, it_Expenditure, it_FixedAssets, it_CashAndBank,
            it_AccountsReceivable, it_AccountsPayable, etc.
        """
        params = {
            "$select": (
                "AcctCode,AcctName,AcctType,ActiveAccount,"
                "FatherAccountKey,GroupCode,ExternalCode"
            ),
        }
        return await self._sl_get_all("/b1s/v2/ChartOfAccounts", params)

    # ── Cost Centers ──────────────────────────────────────────────

    async def get_cost_centers(self) -> List[Dict]:
        """Fetch cost centers (dimensions) from Business One.

        API: GET /b1s/v2/CostCenters
        """
        return await self._sl_get_all("/b1s/v2/CostCenters")

    # ── Profit Centers ────────────────────────────────────────────

    async def get_profit_centers(self) -> List[Dict]:
        """Fetch profit centers from Business One.

        API: GET /b1s/v2/ProfitCenters
        """
        return await self._sl_get_all("/b1s/v2/ProfitCenters")
