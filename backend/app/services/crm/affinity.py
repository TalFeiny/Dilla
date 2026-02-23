"""
Affinity CRM provider — MCP-based.

Uses the Affinity MCP server which exposes tools:
  - search_organizations, get_organization, create_organization, update_organization
  - search_notes, create_note
  - list_lists, get_list_entries

Env vars:
  AFFINITY_MCP_SERVER_URL — URL of the Affinity MCP server (default: stdio)
  AFFINITY_API_KEY        — passed to MCP server as config
"""
import logging
import os
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .base import (
    CRMProvider,
    CRMCompany,
    CRMNote,
    CRMDeal,
    CRMSyncResult,
)

logger = logging.getLogger(__name__)

# MCP tool name constants — match the Affinity MCP server tool names
TOOL_SEARCH_ORGS = "search_organizations"
TOOL_GET_ORG = "get_organization"
TOOL_CREATE_ORG = "create_organization"
TOOL_UPDATE_ORG = "update_organization"
TOOL_CREATE_NOTE = "create_note"
TOOL_SEARCH_NOTES = "search_notes"
TOOL_LIST_LISTS = "list_lists"
TOOL_GET_LIST_ENTRIES = "get_list_entries"

# Type alias for MCP tool caller
MCPToolCaller = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]


class AffinityCRMProvider(CRMProvider):
    """Affinity CRM via MCP server.

    Requires an MCP tool caller function that the orchestrator provides.
    Signature: async def call_tool(tool_name: str, arguments: dict) -> dict
    """

    def __init__(self, call_tool: Optional[MCPToolCaller] = None):
        self.call_tool = call_tool
        self._connected = False

    def set_tool_caller(self, call_tool: MCPToolCaller):
        """Set the MCP tool caller after initialization."""
        self.call_tool = call_tool

    async def _call(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if not self.call_tool:
            raise RuntimeError("Affinity MCP tool caller not configured. Set AFFINITY_API_KEY and register the Affinity MCP server.")
        return await self.call_tool(tool, args)

    # ----- Connection -----

    async def test_connection(self) -> bool:
        if not self.call_tool:
            return False
        try:
            result = await self._call(TOOL_LIST_LISTS, {})
            self._connected = bool(result)
            return self._connected
        except Exception as e:
            logger.warning(f"[Affinity MCP] Connection test failed: {e}")
            return False

    # ----- Companies (Organizations) -----

    async def list_companies(self, limit: int = 100, offset: int = 0) -> List[CRMCompany]:
        result = await self._call(TOOL_SEARCH_ORGS, {
            "limit": limit,
            "offset": offset,
        })
        return [self._parse_org(r) for r in (result.get("organizations") or result.get("data") or [])]

    async def get_company(self, external_id: str) -> Optional[CRMCompany]:
        try:
            result = await self._call(TOOL_GET_ORG, {
                "organization_id": external_id,
            })
            return self._parse_org(result.get("organization") or result)
        except Exception:
            return None

    async def search_companies(self, query: str, limit: int = 10) -> List[CRMCompany]:
        result = await self._call(TOOL_SEARCH_ORGS, {
            "term": query,
            "limit": limit,
        })
        return [self._parse_org(r) for r in (result.get("organizations") or result.get("data") or [])]

    async def upsert_company(self, company: CRMCompany) -> CRMCompany:
        attrs = self._company_to_attrs(company)
        if company.external_id:
            result = await self._call(TOOL_UPDATE_ORG, {
                "organization_id": company.external_id,
                **attrs,
            })
        else:
            result = await self._call(TOOL_CREATE_ORG, attrs)
        return self._parse_org(result.get("organization") or result)

    async def sync_companies_from_matrix(self, companies: List[Dict[str, Any]]) -> CRMSyncResult:
        result = CRMSyncResult()
        for comp_data in companies:
            try:
                company = CRMCompany(
                    name=comp_data.get("companyName") or comp_data.get("name", ""),
                    domain=comp_data.get("domain"),
                    stage=comp_data.get("stage"),
                    sector=comp_data.get("sector"),
                    description=comp_data.get("description"),
                    arr=comp_data.get("arr"),
                    valuation=comp_data.get("valuation"),
                )
                await self.upsert_company(company)
                result.created += 1
            except Exception as e:
                result.errors.append(f"{comp_data.get('companyName', '?')}: {e}")
        result.success = len(result.errors) == 0
        return result

    # ----- Notes -----

    async def add_note(self, note: CRMNote) -> CRMNote:
        result = await self._call(TOOL_CREATE_NOTE, {
            "organization_ids": [note.company_external_id] if note.company_external_id else [],
            "content": note.body,
        })
        note.external_id = (result.get("note") or result).get("id")
        return note

    async def list_notes(self, company_external_id: str, limit: int = 20) -> List[CRMNote]:
        result = await self._call(TOOL_SEARCH_NOTES, {
            "organization_id": company_external_id,
            "limit": limit,
        })
        return [
            CRMNote(
                external_id=n.get("id"),
                company_external_id=company_external_id,
                title=n.get("title", ""),
                body=n.get("content", ""),
                created_at=n.get("created_at"),
            )
            for n in (result.get("notes") or result.get("data") or [])
        ]

    # ----- Deals (List Entries) -----

    async def list_deals(self, limit: int = 50) -> List[CRMDeal]:
        lists_result = await self._call(TOOL_LIST_LISTS, {})
        lists = lists_result.get("lists") or lists_result.get("data") or []
        if not lists:
            return []
        deal_list = lists[0]
        list_id = deal_list.get("id")
        if not list_id:
            return []
        entries_result = await self._call(TOOL_GET_LIST_ENTRIES, {
            "list_id": list_id,
            "limit": limit,
        })
        entries = entries_result.get("entries") or entries_result.get("data") or []
        return [
            CRMDeal(
                external_id=str(e.get("id", "")),
                company_external_id=str((e.get("entity") or {}).get("id", "")),
                name=(e.get("entity") or {}).get("name", ""),
            )
            for e in entries[:limit]
        ]

    async def upsert_deal(self, deal: CRMDeal) -> CRMDeal:
        logger.warning("[Affinity MCP] upsert_deal requires list_id — not yet implemented for dynamic lists")
        return deal

    # ----- Bulk -----

    async def pull_all(self, limit: int = 500) -> Dict[str, Any]:
        companies = await self.list_companies(limit=limit)
        deals = await self.list_deals(limit=limit)
        return {
            "companies": [c.__dict__ for c in companies],
            "deals": [d.__dict__ for d in deals],
            "notes_count": 0,
        }

    # ----- Helpers -----

    @staticmethod
    def _parse_org(org: Dict[str, Any]) -> CRMCompany:
        return CRMCompany(
            external_id=str(org.get("id", "")),
            name=org.get("name", ""),
            domain=org.get("domain") or org.get("domains", ""),
        )

    @staticmethod
    def _company_to_attrs(company: CRMCompany) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {"name": company.name}
        if company.domain:
            attrs["domain"] = company.domain
        if company.description:
            attrs["description"] = company.description
        return attrs
