"""HTTP client for Dilla AI backend API."""

from __future__ import annotations

import os
import httpx
from typing import Any


class DillaClient:
    """Thin async HTTP client wrapping the Dilla AI backend."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        backend_secret: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = (
            base_url or os.environ.get("DILLA_API_URL", "http://localhost:8000")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("DILLA_API_KEY", "")
        self.backend_secret = backend_secret or os.environ.get(
            "DILLA_BACKEND_SECRET", ""
        )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            if self.backend_secret:
                headers["X-Backend-Secret"] = self.backend_secret
            headers["Content-Type"] = "application/json"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        resp = await client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    async def _get(self, path: str) -> dict[str, Any]:
        client = await self._get_client()
        resp = await client.get(path)
        resp.raise_for_status()
        return resp.json()

    # ── High-level API methods ──────────────────────────────────────────

    async def unified_brain(
        self,
        prompt: str,
        output_format: str = "analysis",
        context: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call the unified brain endpoint — the main orchestrator."""
        return await self._post(
            "/api/agent/unified-brain",
            json={
                "prompt": prompt,
                "output_format": output_format,
                "context": context or {},
                "options": options or {},
            },
        )

    async def cfo_brain(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call the CFO brain endpoint for FP&A / budgeting queries."""
        return await self._post(
            "/api/agent/cfo-brain",
            json={"prompt": prompt, "context": context or {}},
        )

    async def mcp_process(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call the raw MCP orchestrator."""
        return await self._post(
            "/api/mcp/process",
            json={"prompt": prompt, "context": context or {}},
        )

    async def export_deck(
        self,
        deck_data: dict[str, Any],
        format: str = "pptx",
    ) -> bytes:
        """Export a deck to PPTX or PDF. Returns raw file bytes."""
        client = await self._get_client()
        resp = await client.post(
            "/api/export/deck",
            json={"deck_data": deck_data, "format": format},
        )
        resp.raise_for_status()
        return resp.content

    async def run_valuation(
        self,
        company_name: str,
        company_data: dict[str, Any],
        method: str = "pwerm",
    ) -> dict[str, Any]:
        """Run valuation via the valuation engine endpoint."""
        return await self._post(
            "/api/valuation/calculate",
            json={
                "company_name": company_name,
                "company_data": company_data,
                "method": method,
            },
        )

    async def scenario_analysis(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run scenario analysis via the NL scenarios endpoint."""
        return await self._post(
            "/api/nl-scenarios/compose",
            json={"prompt": prompt, "context": context or {}},
        )

    async def fund_modeling(
        self,
        prompt: str,
        fund_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run fund-level modeling."""
        return await self._post(
            "/api/fund-modeling/analyze",
            json={"prompt": prompt, "fund_data": fund_data or {}},
        )

    async def health(self) -> dict[str, Any]:
        """Check backend health."""
        return await self._get("/api/health")
