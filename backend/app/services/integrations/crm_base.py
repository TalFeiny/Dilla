"""Base CRM connector interface.

All CRM integrations (Salesforce, HubSpot, etc.) implement this ABC
so the sync pipeline can work provider-agnostically for pipeline data.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional


class CRMConnector(ABC):
    """Interface that all CRM integrations must implement."""

    provider: str  # "salesforce"

    # -- Auth -----------------------------------------------------------------

    @abstractmethod
    async def build_auth_url(self, user_id: str, redirect_uri: str) -> str:
        """Return the OAuth authorization URL to redirect the user to."""

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange an authorization code for tokens."""

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token."""

    # -- Data retrieval -------------------------------------------------------

    @abstractmethod
    async def get_opportunities(
        self, access_token: str, instance_url: str, since: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch CRM opportunities (deals)."""

    @abstractmethod
    async def get_accounts(
        self, access_token: str, instance_url: str, since: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch CRM accounts (companies)."""

    @abstractmethod
    async def get_contacts(
        self, access_token: str, instance_url: str, since: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch CRM contacts."""

    @abstractmethod
    async def get_activities(
        self, access_token: str, instance_url: str, since: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch CRM activities (tasks, events)."""

    @abstractmethod
    async def get_forecasts(
        self, access_token: str, instance_url: str, fiscal_year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch CRM forecast data."""
