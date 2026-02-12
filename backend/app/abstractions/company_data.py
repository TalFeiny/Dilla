"""
Company and portfolio data abstraction (companies, portfolio_companies, funding_rounds).
Implementations: Supabase; later SQL/Warehouse for client DW.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


class CompanyDataRepo(ABC):
    """Interface for company and portfolio data."""

    @abstractmethod
    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Get company by id. Returns None if not found."""
        pass

    @abstractmethod
    def get_funding_rounds(self, company_id: str) -> List[Dict[str, Any]]:
        """Get funding rounds for a company, ordered by date."""
        pass

    @abstractmethod
    def get_portfolio_companies(
        self,
        fund_id: str,
        with_company_details: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get portfolio companies for a fund. Optionally join company details."""
        pass

    def get_portfolio_company(
        self,
        fund_id: str,
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single portfolio-company link. Optional."""
        try:
            all_ = self.get_portfolio_companies(fund_id, with_company_details=True)
            for pc in all_:
                cid = pc.get("company_id") or (pc.get("companies") or {}).get("id")
                if cid == company_id:
                    return pc
            return None
        except Exception as e:
            logger.warning("get_portfolio_company: %s", e)
            return None


class SupabaseCompanyDataRepo(CompanyDataRepo):
    """Supabase implementation using companies, funding_rounds, portfolio_companies."""

    def __init__(self, client):
        self._client = client

    def get_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        try:
            r = self._client.from_("companies").select("*").eq("id", company_id).single().execute()
            return r.data if r.data else None
        except Exception as e:
            logger.debug("get_company %s: %s", company_id, e)
            return None

    def get_funding_rounds(self, company_id: str) -> List[Dict[str, Any]]:
        try:
            r = (
                self._client.from_("funding_rounds")
                .select("*")
                .eq("company_id", company_id)
                .order("date", desc=False)
                .execute()
            )
            if r.data:
                return list(r.data)
            # Fallback: funding_rounds JSONB on companies
            company = self.get_company(company_id)
            if company and company.get("funding_rounds"):
                return list(company["funding_rounds"])
            return []
        except Exception as e:
            logger.warning("get_funding_rounds %s: %s", company_id, e)
            return []

    def get_portfolio_companies(
        self,
        fund_id: str,
        with_company_details: bool = True,
    ) -> List[Dict[str, Any]]:
        try:
            select = "*, companies(*)" if with_company_details else "*"
            r = (
                self._client.from_("portfolio_companies")
                .select(select)
                .eq("fund_id", fund_id)
                .execute()
            )
            return list(r.data or [])
        except Exception as e:
            logger.warning("get_portfolio_companies %s: %s", fund_id, e)
            return []

    def get_portfolio_company(
        self,
        fund_id: str,
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            r = (
                self._client.from_("portfolio_companies")
                .select("*, companies(*)")
                .eq("fund_id", fund_id)
                .eq("company_id", company_id)
                .single()
                .execute()
            )
            return r.data if r.data else None
        except Exception as e:
            logger.debug("get_portfolio_company: %s", e)
            return None
