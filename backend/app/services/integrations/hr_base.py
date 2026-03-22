"""Base HR connector interface.

All HR integrations (Workday, BambooHR, etc.) implement this ABC
so the sync pipeline can work provider-agnostically for headcount data.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional


class HRConnector(ABC):
    """Interface that all HR integrations must implement."""

    provider: str  # "workday", "bamboohr"

    # -- Auth -----------------------------------------------------------------

    @abstractmethod
    async def build_auth_url(self, user_id: str, redirect_uri: str) -> str:
        """Return the OAuth authorization URL (or empty string for API-key auth)."""

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange an authorization code for tokens (no-op for API-key auth)."""

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token (no-op for API-key auth)."""

    # -- Data retrieval -------------------------------------------------------

    @abstractmethod
    async def get_headcount(
        self, access_token: str, tenant_id: str, as_of: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch active headcount grouped by department."""

    @abstractmethod
    async def get_compensation(
        self, access_token: str, tenant_id: str, as_of: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch compensation data grouped by department."""

    @abstractmethod
    async def get_departments(
        self, access_token: str, tenant_id: str,
    ) -> List[Dict[str, Any]]:
        """Fetch department/org hierarchy."""

    @abstractmethod
    async def get_hires_and_terminations(
        self, access_token: str, tenant_id: str, since: date,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch hires and terminations since a given date.

        Returns: {"hires": [...], "terminations": [...]}
        """
