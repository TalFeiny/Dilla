"""Base accounting connector interface.

All ERP/accounting integrations implement this ABC so the sync pipeline,
connection management, and report normalizer can work provider-agnostically.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FpaRow:
    """A single row destined for the fpa_actuals table."""
    company_id: str
    period: str            # "YYYY-MM-01"
    category: str          # revenue, cogs, opex_rd, opex_sm, opex_ga, bs_cash, …
    subcategory: str       # e.g. "engineering_salaries", or ""
    amount: float
    source: str            # "quickbooks", "netsuite", "xero"
    fund_id: Optional[str] = None
    hierarchy_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "company_id": self.company_id,
            "period": self.period,
            "category": self.category,
            "subcategory": self.subcategory or "",
            "amount": self.amount,
            "source": self.source,
        }
        if self.fund_id:
            d["fund_id"] = self.fund_id
        d["hierarchy_path"] = self.hierarchy_path or self.category
        return d


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    rows_synced: int = 0
    pl_rows: int = 0
    bs_rows: int = 0
    periods: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class AccountInfo:
    """A chart-of-accounts entry from the ERP."""
    code: str
    name: str
    account_type: str          # provider's native type string
    classification: Optional[str] = None  # provider's class (Asset, Liability, etc.)


class AccountingConnector(ABC):
    """Interface that all accounting integrations must implement."""

    provider: str  # "quickbooks", "netsuite", "xero"

    # ── OAuth / Auth ──────────────────────────────────────────────

    @abstractmethod
    async def build_auth_url(self, user_id: str, redirect_uri: str) -> str:
        """Return the OAuth authorization URL to redirect the user to."""

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange an authorization code for tokens.

        Returns: {success, access_token, refresh_token, expires_in, ...}
        """

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token.

        Returns: {success, access_token, refresh_token, expires_in, ...}
        """

    # ── Data retrieval ────────────────────────────────────────────

    @abstractmethod
    async def fetch_chart_of_accounts(
        self, access_token: str, tenant_id: str
    ) -> List[AccountInfo]:
        """Fetch the full chart of accounts."""

    @abstractmethod
    async def fetch_profit_and_loss(
        self,
        access_token: str,
        tenant_id: str,
        from_date: str,
        to_date: str,
        company_id: str,
        fund_id: Optional[str] = None,
    ) -> List[FpaRow]:
        """Fetch P&L data and return normalized FPA rows."""

    @abstractmethod
    async def fetch_balance_sheet(
        self,
        access_token: str,
        tenant_id: str,
        as_of_date: str,
        company_id: str,
        fund_id: Optional[str] = None,
    ) -> List[FpaRow]:
        """Fetch balance sheet data and return normalized FPA rows."""
