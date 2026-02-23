"""
Abstract CRM provider interface — MCP-based.

CRM integrations (Attio, Affinity) are accessed via their MCP servers.
The orchestrator calls tool names on the MCP connection rather than REST directly.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class CRMCompany:
    """Canonical company record synced to/from CRM."""
    external_id: Optional[str] = None
    name: str = ""
    domain: Optional[str] = None
    stage: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    arr: Optional[float] = None
    valuation: Optional[float] = None
    total_funding: Optional[float] = None
    employee_count: Optional[int] = None
    hq_location: Optional[str] = None
    founded_year: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CRMNote:
    """A note/activity attached to a company in the CRM."""
    external_id: Optional[str] = None
    company_external_id: Optional[str] = None
    title: str = ""
    body: str = ""
    note_type: str = "general"
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CRMDeal:
    """A deal / opportunity record in the CRM."""
    external_id: Optional[str] = None
    company_external_id: Optional[str] = None
    name: str = ""
    stage: str = ""
    value: Optional[float] = None
    currency: str = "USD"
    owner: Optional[str] = None
    closed_at: Optional[datetime] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CRMSyncResult:
    """Result of a sync operation."""
    success: bool = True
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)


class CRMProvider(ABC):
    """Abstract CRM provider — backed by MCP tool calls."""

    @abstractmethod
    async def test_connection(self) -> bool:
        ...

    @abstractmethod
    async def list_companies(self, limit: int = 100, offset: int = 0) -> List[CRMCompany]:
        ...

    @abstractmethod
    async def get_company(self, external_id: str) -> Optional[CRMCompany]:
        ...

    @abstractmethod
    async def search_companies(self, query: str, limit: int = 10) -> List[CRMCompany]:
        ...

    @abstractmethod
    async def upsert_company(self, company: CRMCompany) -> CRMCompany:
        ...

    @abstractmethod
    async def sync_companies_from_matrix(self, companies: List[Dict[str, Any]]) -> CRMSyncResult:
        ...

    @abstractmethod
    async def add_note(self, note: CRMNote) -> CRMNote:
        ...

    @abstractmethod
    async def list_notes(self, company_external_id: str, limit: int = 20) -> List[CRMNote]:
        ...

    @abstractmethod
    async def list_deals(self, limit: int = 50) -> List[CRMDeal]:
        ...

    @abstractmethod
    async def upsert_deal(self, deal: CRMDeal) -> CRMDeal:
        ...

    @abstractmethod
    async def pull_all(self, limit: int = 500) -> Dict[str, Any]:
        ...
