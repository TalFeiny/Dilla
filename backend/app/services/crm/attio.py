"""
Attio CRM provider — MCP-based.

Uses the Attio MCP server (attio/mcp-server) which exposes tools:
  - search_records, get_record, create_record, update_record
  - search_notes, create_note
  - list_objects, list_attributes

Env vars:
  ATTIO_MCP_SERVER_URL — URL of the Attio MCP server (default: stdio)
  ATTIO_API_KEY        — passed to MCP server as config
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

# MCP tool name constants — match the Attio MCP server tool names
TOOL_SEARCH_RECORDS = "search_records"
TOOL_GET_RECORD = "get_record"
TOOL_CREATE_RECORD = "create_record"
TOOL_UPDATE_RECORD = "update_record"
TOOL_CREATE_NOTE = "create_note"
TOOL_SEARCH_NOTES = "search_notes"
TOOL_LIST_OBJECTS = "list_objects"

# Type alias for MCP tool caller
MCPToolCaller = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]


class AttioCRMProvider(CRMProvider):
    """Attio CRM via MCP server.

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
            raise RuntimeError("Attio MCP tool caller not configured. Set ATTIO_API_KEY and register the Attio MCP server.")
        return await self.call_tool(tool, args)

    # ----- Connection -----

    async def test_connection(self) -> bool:
        if not self.call_tool:
            return False
        try:
            result = await self._call(TOOL_LIST_OBJECTS, {})
            self._connected = bool(result)
            return self._connected
        except Exception as e:
            logger.warning(f"[Attio MCP] Connection test failed: {e}")
            return False

    # ----- Companies -----

    async def list_companies(self, limit: int = 100, offset: int = 0) -> List[CRMCompany]:
        result = await self._call(TOOL_SEARCH_RECORDS, {
            "object": "companies",
            "limit": limit,
            "offset": offset,
        })
        return [self._parse_record(r) for r in (result.get("records") or result.get("data") or [])]

    async def get_company(self, external_id: str) -> Optional[CRMCompany]:
        try:
            result = await self._call(TOOL_GET_RECORD, {
                "object": "companies",
                "record_id": external_id,
            })
            return self._parse_record(result.get("record") or result)
        except Exception:
            return None

    async def search_companies(self, query: str, limit: int = 10) -> List[CRMCompany]:
        result = await self._call(TOOL_SEARCH_RECORDS, {
            "object": "companies",
            "query": query,
            "limit": limit,
        })
        return [self._parse_record(r) for r in (result.get("records") or result.get("data") or [])]

    async def upsert_company(self, company: CRMCompany) -> CRMCompany:
        attrs = self._company_to_attrs(company)
        if company.external_id:
            result = await self._call(TOOL_UPDATE_RECORD, {
                "object": "companies",
                "record_id": company.external_id,
                "attributes": attrs,
            })
        else:
            result = await self._call(TOOL_CREATE_RECORD, {
                "object": "companies",
                "attributes": attrs,
                "matching_attribute": "name",
            })
        return self._parse_record(result.get("record") or result)

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
            "parent_object": "companies",
            "parent_record_id": note.company_external_id,
            "title": note.title,
            "content": note.body,
        })
        note.external_id = (result.get("note") or result).get("id")
        return note

    async def list_notes(self, company_external_id: str, limit: int = 20) -> List[CRMNote]:
        result = await self._call(TOOL_SEARCH_NOTES, {
            "parent_object": "companies",
            "parent_record_id": company_external_id,
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

    # ----- Deals -----

    async def list_deals(self, limit: int = 50) -> List[CRMDeal]:
        result = await self._call(TOOL_SEARCH_RECORDS, {
            "object": "deals",
            "limit": limit,
        })
        return [
            CRMDeal(
                external_id=r.get("id") or r.get("record_id"),
                name=self._attr(r, "name"),
                stage=self._attr(r, "stage"),
                value=self._num_attr(r, "value"),
            )
            for r in (result.get("records") or result.get("data") or [])
        ]

    async def upsert_deal(self, deal: CRMDeal) -> CRMDeal:
        attrs = {"name": deal.name}
        if deal.stage:
            attrs["stage"] = deal.stage
        if deal.value is not None:
            attrs["value"] = deal.value
        if deal.external_id:
            result = await self._call(TOOL_UPDATE_RECORD, {
                "object": "deals",
                "record_id": deal.external_id,
                "attributes": attrs,
            })
        else:
            result = await self._call(TOOL_CREATE_RECORD, {
                "object": "deals",
                "attributes": attrs,
            })
        deal.external_id = (result.get("record") or result).get("id")
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
    def _parse_record(record: Dict[str, Any]) -> CRMCompany:
        attrs = record.get("attributes") or record.get("values") or record
        return CRMCompany(
            external_id=record.get("id") or record.get("record_id"),
            name=attrs.get("name", ""),
            domain=attrs.get("domains") or attrs.get("domain", ""),
            description=attrs.get("description", ""),
            employee_count=attrs.get("team_size") or attrs.get("employee_count"),
        )

    @staticmethod
    def _company_to_attrs(company: CRMCompany) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {"name": company.name}
        if company.domain:
            attrs["domains"] = company.domain
        if company.description:
            attrs["description"] = company.description
        if company.employee_count:
            attrs["team_size"] = company.employee_count
        return attrs

    @staticmethod
    def _attr(record: Dict, key: str) -> str:
        attrs = record.get("attributes") or record.get("values") or record
        v = attrs.get(key)
        if isinstance(v, list):
            return v[0].get("value", "") if v else ""
        return str(v) if v else ""

    @staticmethod
    def _num_attr(record: Dict, key: str) -> Optional[float]:
        attrs = record.get("attributes") or record.get("values") or record
        v = attrs.get(key)
        if isinstance(v, list):
            v = v[0].get("value") or v[0].get("currency_value") if v else None
        try:
            return float(v) if v is not None else None
        except (ValueError, TypeError):
            return None
