"""
Macro Event Analysis Service
Dynamic, LLM-reasoned analysis of geopolitical/macro events on portfolio P&L.

NOT template-based. The LLM is the reasoning engine:
  1. Takes any natural language event ("iran war", "EU AI Act", "oil embargo")
  2. Web-searches for real-world context via Tavily
  3. LLM reasons about which of the 28 registered drivers are affected, by how much,
     and WHY — producing per-company adjustments with full audit chain
  4. Feeds adjustments into ScenarioBranchService for branched projections

Every output includes an auditable reasoning chain:
  event → search_evidence → macro_factors → driver_adjustments → scenario_branches
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.driver_registry import (
    get_all_drivers,
    get_registry_schema,
    drivers_to_assumptions,
    DriverDef,
)
from app.services.model_router import ModelRouter, ModelCapability

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MacroFactor:
    """A single macro-economic factor extracted by the LLM."""
    name: str                       # e.g. "oil price spike"
    direction: str                  # "increase" | "decrease"
    magnitude_pct: float            # estimated % change (0.25 = +25%)
    confidence: str                 # "high" | "medium" | "low"
    reasoning: str                  # LLM's reasoning for this factor
    order: int = 1                  # 1=direct, 2=indirect, 3=systemic
    caused_by: Optional[str] = None # parent factor for 2nd/3rd order effects
    source_snippets: List[str] = field(default_factory=list)  # search evidence


@dataclass
class DriverAdjustment:
    """A concrete adjustment to a registered driver, with audit trail."""
    driver_id: str
    driver_label: str
    company_name: str
    base_value: Optional[float]     # current value (if known)
    adjustment_pct: float           # e.g. -0.15 = -15%
    adjusted_value: Optional[float] # new value after adjustment
    caused_by: str                  # which MacroFactor caused this
    reasoning: str                  # LLM explanation of factor→driver link
    ripple_path: List[str]          # downstream effects via driver registry


@dataclass
class MacroEventAnalysis:
    """Complete analysis result with full audit chain."""
    event_description: str
    search_queries: List[str]
    search_evidence: List[Dict[str, str]]   # [{title, url, snippet}]
    macro_factors: List[MacroFactor]
    driver_adjustments: List[DriverAdjustment]
    scenario_branches: Dict[str, Any]       # branched projections
    reasoning_chain: List[Dict[str, str]]   # step-by-step audit
    companies_affected: List[str]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class MacroEventAnalysisService:
    """
    Dynamic macro event → portfolio impact analysis.
    No templates. LLM reasons over real search data + driver registry.
    """

    def __init__(
        self,
        model_router,
        tavily_search_fn: Optional[Callable] = None,
    ):
        self.model_router = model_router
        self._tavily_search = tavily_search_fn
        self._driver_registry = get_all_drivers()
        self._driver_schema = get_registry_schema()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyse_event(
        self,
        event: str,
        portfolio_companies: List[Dict[str, Any]],
        fund_id: Optional[str] = None,
        forecast_months: int = 12,
        existing_tree=None,
    ) -> MacroEventAnalysis:
        """
        Full pipeline: event → search → reason → drivers → branches → audit.

        Args:
            event: Natural language event description
                   e.g. "iran war", "tariffs on EU imports", "fed raises rates 200bps"
            portfolio_companies: List of company dicts with at minimum:
                   {name, sector, revenue, burn_rate, headcount, ...}
            fund_id: Optional fund context
            forecast_months: Projection horizon

        Returns:
            MacroEventAnalysis with complete audit chain
        """
        reasoning_chain: List[Dict[str, str]] = []

        # ── Step 1: Generate search queries ──────────────────────────
        reasoning_chain.append({
            "step": "event_received",
            "detail": f"Analysing: '{event}' across {len(portfolio_companies)} portfolio companies",
        })

        search_queries = await self._generate_search_queries(event)
        reasoning_chain.append({
            "step": "search_queries_generated",
            "detail": f"Generated {len(search_queries)} search queries",
            "queries": search_queries,
        })

        # ── Step 2: Web search for real-world context ────────────────
        search_evidence = await self._execute_searches(search_queries)
        reasoning_chain.append({
            "step": "web_search_complete",
            "detail": f"Found {len(search_evidence)} relevant sources",
            "sources": [e.get("title", "") for e in search_evidence[:5]],
        })

        # ── Step 3: LLM extracts macro factors from evidence ────────
        macro_factors = await self._extract_macro_factors(
            event, search_evidence
        )
        reasoning_chain.append({
            "step": "macro_factors_extracted",
            "detail": f"Identified {len(macro_factors)} macro factors "
                      f"({sum(1 for f in macro_factors if f.order == 1)} direct, "
                      f"{sum(1 for f in macro_factors if f.order == 2)} indirect, "
                      f"{sum(1 for f in macro_factors if f.order == 3)} systemic)",
            "factors": [
                {"name": f.name, "direction": f.direction,
                 "magnitude": f"{f.magnitude_pct:+.0%}", "confidence": f.confidence,
                 "order": f.order, "caused_by": f.caused_by}
                for f in macro_factors
            ],
        })

        # ── Step 4: LLM maps factors → driver adjustments per company
        driver_adjustments = await self._map_factors_to_drivers(
            event, macro_factors, portfolio_companies
        )
        reasoning_chain.append({
            "step": "driver_adjustments_mapped",
            "detail": f"Mapped to {len(driver_adjustments)} driver adjustments "
                      f"across {len(set(a.company_name for a in driver_adjustments))} companies",
        })

        # ── Step 5: Run branched scenarios ───────────────────────────
        scenario_branches = await self._run_branched_scenarios(
            event, driver_adjustments, portfolio_companies,
            forecast_months, fund_id, existing_tree=existing_tree,
        )
        reasoning_chain.append({
            "step": "scenarios_executed",
            "detail": f"Generated {len(scenario_branches.get('branches', []))} scenario branches",
        })

        companies_affected = sorted(set(a.company_name for a in driver_adjustments))

        return MacroEventAnalysis(
            event_description=event,
            search_queries=search_queries,
            search_evidence=search_evidence,
            macro_factors=macro_factors,
            driver_adjustments=driver_adjustments,
            scenario_branches=scenario_branches,
            reasoning_chain=reasoning_chain,
            companies_affected=companies_affected,
        )

    # ------------------------------------------------------------------
    # Step 1: Generate search queries
    # ------------------------------------------------------------------

    async def _generate_search_queries(self, event: str) -> List[str]:
        """LLM generates targeted search queries for the event."""
        prompt = f"""Given this geopolitical/macro event, generate 3-5 web search queries
that would find the most relevant economic impact data.

Event: "{event}"

Focus on:
- Direct economic/market impacts (commodity prices, trade flows, supply chains)
- Sector-specific effects (which industries hit hardest/benefit)
- Historical analogues if available
- Quantitative estimates (% GDP impact, price changes, etc.)

Return ONLY a JSON array of search query strings. No other text.
Example: ["iran war oil price impact 2024", "middle east conflict supply chain disruption"]"""

        try:
            response = await self.model_router.get_completion(
                prompt=prompt,
                capability=ModelCapability.ANALYSIS,
                max_tokens=500,
                temperature=0.3,
                json_mode=True,
                caller_context="macro_event_search_queries",
            )
            raw = response.get("response", "[]") if isinstance(response, dict) else str(response)
            queries = _parse_json_safe(raw)
            if isinstance(queries, list) and queries:
                return queries[:5]
        except Exception as e:
            logger.warning(f"[MACRO] Search query generation failed: {e}")

        # Fallback: construct basic queries from the event text
        return [
            f"{event} economic impact",
            f"{event} market sectors affected",
            f"{event} supply chain impact startups",
        ]

    # ------------------------------------------------------------------
    # Step 2: Web search
    # ------------------------------------------------------------------

    async def _execute_searches(
        self, queries: List[str]
    ) -> List[Dict[str, str]]:
        """Run Tavily searches in parallel, deduplicate results."""
        if not self._tavily_search:
            logger.warning("[MACRO] No search function provided — skipping web search")
            return []

        tasks = [self._tavily_search(q) for q in queries]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        seen_urls = set()
        evidence: List[Dict[str, str]] = []

        for result in raw_results:
            if isinstance(result, Exception):
                continue
            for item in (result or {}).get("results", []):
                url = item.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                evidence.append({
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("content", "")[:500],
                })

        return evidence[:15]  # Cap at 15 sources

    # ------------------------------------------------------------------
    # Step 3: Extract macro factors from search evidence
    # ------------------------------------------------------------------

    async def _extract_macro_factors(
        self,
        event: str,
        evidence: List[Dict[str, str]],
    ) -> List[MacroFactor]:
        """LLM reasons over search evidence to extract structured macro factors."""

        evidence_text = "\n\n".join(
            f"[{e['title']}] ({e['url']})\n{e['snippet']}"
            for e in evidence[:10]
        ) if evidence else "(No search results available — reason from general knowledge)"

        prompt = f"""You are an economic analyst at a PE/VC fund. Analyse this event and the
search evidence to identify the concrete macro-economic factors it creates.

Think through the CAUSAL CHAIN — trace how the event propagates through the economy:

EVENT: "{event}"

SEARCH EVIDENCE:
{evidence_text}

For each macro factor, provide:
- name: short label (e.g. "oil price spike", "shipping cost increase", "defense spending surge")
- direction: "increase" or "decrease"
- magnitude_pct: estimated percentage change as a decimal (0.25 = +25%, -0.10 = -10%)
  Base this on the evidence. Be specific, not generic.
- confidence: "high" (strong evidence), "medium" (reasonable inference), "low" (speculative)
- order: 1, 2, or 3 — the causal depth:
    1 = DIRECT effect of the event (e.g. event is a war → oil prices spike)
    2 = INDIRECT effect caused by a 1st-order factor (e.g. oil spike → higher COGS for logistics companies)
    3 = SYSTEMIC effect caused by 2nd-order factors (e.g. higher costs → inflation → rate hikes → tighter funding)
- caused_by: for order 2 and 3, the name of the parent factor that causes this one. null for order 1.
- reasoning: 1-2 sentences explaining the causal mechanism, citing evidence
- source_snippets: 1-2 key quotes from the evidence supporting this

Return JSON array. Structure your thinking as a causal chain — start with direct impacts, then trace
what those impacts cause, and what THOSE cause. Example:

[
  {{
    "name": "oil price spike",
    "direction": "increase",
    "magnitude_pct": 0.35,
    "confidence": "high",
    "order": 1,
    "caused_by": null,
    "reasoning": "Historical precedent shows Middle East conflicts cause 25-40% oil price spikes. Current Brent crude at $82 would likely rise to $110+.",
    "source_snippets": ["Oil prices surged 35% during the 2022 Russia-Ukraine escalation..."]
  }},
  {{
    "name": "logistics cost surge",
    "direction": "increase",
    "magnitude_pct": 0.20,
    "confidence": "medium",
    "order": 2,
    "caused_by": "oil price spike",
    "reasoning": "Fuel is 30-40% of freight cost. A 35% oil spike translates to ~20% increase in shipping and logistics costs.",
    "source_snippets": ["Freight rates rose 22% in the months following the 2022 energy crisis..."]
  }},
  {{
    "name": "consumer spending contraction",
    "direction": "decrease",
    "magnitude_pct": -0.08,
    "confidence": "low",
    "order": 3,
    "caused_by": "logistics cost surge",
    "reasoning": "Higher goods prices from logistics costs reduce real purchasing power, compressing discretionary spending.",
    "source_snippets": []
  }}
]

Be specific and quantitative. Cite the evidence. Do NOT make up numbers — if uncertain, say confidence is "low".
Include at least 1-2 factors at each order level where the causal chain is credible."""

        try:
            response = await self.model_router.get_completion(
                prompt=prompt,
                capability=ModelCapability.ANALYSIS,
                max_tokens=3000,
                temperature=0.2,
                json_mode=True,
                caller_context="macro_event_factor_extraction",
            )
            raw = response.get("response", "[]") if isinstance(response, dict) else str(response)
            parsed = _parse_json_safe(raw)

            if not isinstance(parsed, list):
                return []

            factors = []
            for item in parsed:
                try:
                    factors.append(MacroFactor(
                        name=item.get("name", "unknown"),
                        direction=item.get("direction", "increase"),
                        magnitude_pct=float(item.get("magnitude_pct", 0)),
                        confidence=item.get("confidence", "low"),
                        reasoning=item.get("reasoning", ""),
                        order=int(item.get("order", 1)),
                        caused_by=item.get("caused_by"),
                        source_snippets=item.get("source_snippets", []),
                    ))
                except (TypeError, ValueError):
                    continue
            return factors

        except Exception as e:
            logger.error(f"[MACRO] Factor extraction failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Step 4: Map macro factors → driver adjustments per company
    # ------------------------------------------------------------------

    async def _map_factors_to_drivers(
        self,
        event: str,
        factors: List[MacroFactor],
        companies: List[Dict[str, Any]],
    ) -> List[DriverAdjustment]:
        """LLM maps macro factors to specific driver adjustments per company."""

        # Build company summary for context
        company_summaries = []
        for c in companies:
            name = c.get("name") or c.get("company_name", "Unknown")
            sector = c.get("sector", "Unknown")
            revenue = c.get("revenue") or c.get("annual_revenue", 0)
            headcount = c.get("headcount", 0)
            company_summaries.append(
                f"- {name} (sector: {sector}, revenue: ${revenue:,.0f}, headcount: {headcount})"
            )

        # Build driver registry summary (only adjustable drivers)
        driver_info = []
        for d in self._driver_registry.values():
            if d.computed:
                continue
            driver_info.append(
                f"  {d.id}: {d.label} ({d.unit}, level={d.level}) — {d.nl_hint}"
            )

        order_labels = {1: "DIRECT", 2: "INDIRECT", 3: "SYSTEMIC"}
        factors_text = "\n".join(
            f"- [{order_labels.get(f.order, '?')}] {f.name}: {f.direction} {f.magnitude_pct:+.0%} "
            f"(confidence: {f.confidence}"
            f"{', caused by: ' + f.caused_by if f.caused_by else ''}"
            f") — {f.reasoning}"
            for f in factors
        )

        prompt = f"""You are a PE/VC CFO analyst. Given macro factors from "{event}",
determine how each factor impacts each portfolio company's drivers.

MACRO FACTORS:
{factors_text}

PORTFOLIO COMPANIES:
{chr(10).join(company_summaries)}

AVAILABLE DRIVERS (from our driver registry):
{chr(10).join(driver_info)}

For each company, determine which drivers are affected and by how much.
Consider:
- Sector exposure (e.g. energy companies hit differently than SaaS)
- Revenue sensitivity (B2B vs B2C, geography exposure)
- Cost structure (energy-intensive operations, imported inputs)
- Second-order effects (customer purchasing power, supply chain)

Return JSON array. Each entry:
{{
  "company_name": "CompanyX",
  "driver_id": "revenue_growth",
  "adjustment_pct": -0.15,
  "caused_by": "oil price spike",
  "reasoning": "CompanyX's logistics customers will face 20% higher fuel costs, reducing their IT budgets and slowing CompanyX's sales pipeline"
}}

RULES:
- adjustment_pct is the percentage CHANGE to apply (−0.15 = reduce by 15%)
- Only include drivers where there's a real causal chain. Don't force-fit.
- A company with zero exposure to a factor should NOT have adjustments for it.
- Be specific in reasoning — generic "macro headwinds" is not acceptable.
- Include both direct (revenue, COGS) and indirect (hiring freezes, funding environment) effects."""

        try:
            response = await self.model_router.get_completion(
                prompt=prompt,
                capability=ModelCapability.ANALYSIS,
                max_tokens=4000,
                temperature=0.2,
                json_mode=True,
                caller_context="macro_event_driver_mapping",
            )
            raw = response.get("response", "[]") if isinstance(response, dict) else str(response)
            parsed = _parse_json_safe(raw)

            if not isinstance(parsed, list):
                return []

            adjustments = []
            for item in parsed:
                driver_id = item.get("driver_id", "")
                driver_def = self._driver_registry.get(driver_id)
                if not driver_def:
                    continue

                adjustments.append(DriverAdjustment(
                    driver_id=driver_id,
                    driver_label=driver_def.label,
                    company_name=item.get("company_name", "Unknown"),
                    base_value=None,  # filled during scenario execution
                    adjustment_pct=float(item.get("adjustment_pct", 0)),
                    adjusted_value=None,
                    caused_by=item.get("caused_by", ""),
                    reasoning=item.get("reasoning", ""),
                    ripple_path=driver_def.ripple,
                ))

            return adjustments

        except Exception as e:
            logger.error(f"[MACRO] Driver mapping failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Step 5: Run branched scenarios through the engine
    # ------------------------------------------------------------------

    async def _run_branched_scenarios(
        self,
        event: str,
        adjustments: List[DriverAdjustment],
        companies: List[Dict[str, Any]],
        forecast_months: int,
        fund_id: Optional[str],
        existing_tree=None,
    ) -> Dict[str, Any]:
        """
        Build 3 branches (severe / moderate / mild) by scaling the LLM-derived
        adjustments, then run each through ScenarioBranchService.

        If existing_tree is provided, overlays adjustments onto tree nodes instead
        of building standalone branches (the "purple overlay" path).
        """
        # ── Overlay path: apply to existing scenario tree ──────────────
        if existing_tree is not None:
            return self._overlay_on_existing_tree(
                event, adjustments, existing_tree
            )

        # ── Standalone path: build new branches from actuals ───────────
        from app.services.scenario_branch_service import ScenarioBranchService
        from app.services.actuals_ingestion import seed_forecast_from_actuals
        from app.services.liquidity_management_service import LiquidityManagementService

        sbs = ScenarioBranchService()
        lms = LiquidityManagementService()

        # Group adjustments by company
        by_company: Dict[str, List[DriverAdjustment]] = {}
        for adj in adjustments:
            by_company.setdefault(adj.company_name, []).append(adj)

        severity_scales = {
            "severe": 1.5,    # 150% of LLM-estimated impact
            "moderate": 1.0,  # LLM's base estimate
            "mild": 0.5,      # 50% of estimated impact
        }

        branches = []
        today = date.today()
        start_period = f"{today.year}-{today.month:02d}"

        for severity_label, scale in severity_scales.items():
            branch_companies = {}

            for company_name, adjs in by_company.items():
                # Find matching company data
                company_data = next(
                    (c for c in companies
                     if (c.get("name") or c.get("company_name", "")) == company_name),
                    None,
                )
                if not company_data:
                    continue

                company_id = company_data.get("id") or company_data.get("company_id", "")

                # Get base forecast data
                try:
                    base_data = seed_forecast_from_actuals(company_id) if company_id else {}
                except Exception:
                    base_data = {}

                if not base_data:
                    # Use what we have from the company dict
                    base_data = {
                        "revenue": company_data.get("revenue") or company_data.get("annual_revenue", 0),
                        "burn_rate": company_data.get("burn_rate", 0),
                        "cash_balance": company_data.get("cash_balance", 0),
                        "headcount": company_data.get("headcount", 0),
                    }

                # Build driver assumption overrides for this severity
                driver_values = {}
                adj_details = []
                for adj in adjs:
                    scaled_pct = adj.adjustment_pct * scale
                    driver_values[adj.driver_id] = scaled_pct
                    adj_details.append({
                        "driver": adj.driver_label,
                        "adjustment": f"{scaled_pct:+.1%}",
                        "caused_by": adj.caused_by,
                        "reasoning": adj.reasoning,
                        "ripple": adj.ripple_path,
                    })

                # Convert to assumption dict format
                assumptions = drivers_to_assumptions(driver_values)

                # Project
                try:
                    # Apply overrides to base data
                    projected_data = sbs._apply_overrides({**base_data}, assumptions)
                    lms_result = lms.build_liquidity_model(
                        company_id=company_id,
                        months=forecast_months,
                        start_period=start_period,
                        scenario_overrides=projected_data,
                    )
                    forecast = lms_result.get("monthly", [])
                except Exception as e:
                    logger.warning(f"[MACRO] Projection failed for {company_name}: {e}")
                    forecast = None

                branch_companies[company_name] = {
                    "adjustments": adj_details,
                    "assumptions": assumptions,
                    "forecast": forecast,
                    "base_data": {
                        k: v for k, v in base_data.items()
                        if isinstance(v, (int, float, str))
                    },
                }

            branches.append({
                "severity": severity_label,
                "scale": scale,
                "companies": branch_companies,
                "label": f"{event} — {severity_label.title()} impact",
            })

        # Build chart data for the frontend
        chart_data = self._build_impact_chart(branches, forecast_months)

        return {
            "event": event,
            "branches": branches,
            "chart": chart_data,
            "summary": self._build_summary(branches, adjustments),
        }

    # ------------------------------------------------------------------
    # Overlay: apply adjustments to existing scenario tree
    # ------------------------------------------------------------------

    def _overlay_on_existing_tree(
        self,
        event: str,
        adjustments: List[DriverAdjustment],
        tree,
    ) -> Dict[str, Any]:
        """
        Apply LLM-derived driver adjustments onto an existing ScenarioTree.
        Instead of building new branches, we create a shocked copy of the tree
        where each company snapshot is adjusted according to the macro factors.

        Returns the same branched format for consistency, but with overlay metadata.
        """
        from copy import deepcopy

        # Group adjustments by company
        by_company: Dict[str, List[DriverAdjustment]] = {}
        for adj in adjustments:
            by_company.setdefault(adj.company_name, []).append(adj)

        severity_scales = {
            "severe": 1.5,
            "moderate": 1.0,
            "mild": 0.5,
        }

        branches = []
        for severity_label, scale in severity_scales.items():
            shocked_tree = deepcopy(tree)

            for path in shocked_tree.paths:
                for node in path.nodes:
                    for company_name, snapshot in node.companies.items():
                        adjs = by_company.get(company_name, [])
                        if not adjs:
                            continue

                        for adj in adjs:
                            scaled = adj.adjustment_pct * scale
                            # Map driver_id to snapshot attribute
                            if adj.driver_id in ("revenue_growth", "revenue"):
                                snapshot.revenue *= (1 + scaled)
                            elif adj.driver_id in ("valuation_multiple", "valuation"):
                                snapshot.valuation *= (1 + scaled)
                            elif adj.driver_id in ("burn_rate", "opex_growth"):
                                if snapshot.burn_rate > 0:
                                    snapshot.burn_rate *= (1 + scaled)
                                    snapshot.runway_months = (
                                        snapshot.cash_balance / snapshot.burn_rate
                                        if snapshot.burn_rate > 0 else 36
                                    )
                            elif adj.driver_id == "gross_margin":
                                snapshot.gross_margin = max(
                                    0, snapshot.gross_margin + scaled
                                )
                            elif adj.driver_id == "headcount_growth":
                                # Indirect: affects burn via headcount cost
                                pass  # handled through ripple
                            elif adj.driver_id in ("cogs_pct", "cogs"):
                                snapshot.gross_margin = max(
                                    0, snapshot.gross_margin - scaled
                                )
                            # For any driver that maps to revenue sensitivity
                            elif "revenue" in adj.driver_id:
                                snapshot.revenue *= (1 + scaled)
                            elif "cost" in adj.driver_id or "expense" in adj.driver_id:
                                if snapshot.burn_rate > 0:
                                    snapshot.burn_rate *= (1 + scaled)

            # Recompute tree metrics
            try:
                from app.services.scenario_tree_service import ScenarioTreeService
                svc = ScenarioTreeService()
                shocked_tree.expected_value = svc.evaluate_expected_value(shocked_tree)
                shocked_tree.sensitivity = svc.sensitivity_by_company(shocked_tree)
            except Exception as e:
                logger.warning(f"[MACRO] Tree recompute failed: {e}")

            branches.append({
                "severity": severity_label,
                "scale": scale,
                "overlay": True,
                "tree": shocked_tree,
                "label": f"{event} — {severity_label.title()} overlay",
                "adjustments_applied": [
                    {
                        "company": adj.company_name,
                        "driver": adj.driver_label,
                        "adjustment": f"{adj.adjustment_pct * scale:+.1%}",
                        "caused_by": adj.caused_by,
                    }
                    for adj in adjustments
                ],
            })

        # Build comparison chart: original vs overlayed EVs
        chart_data = self._build_overlay_chart(tree, branches)

        return {
            "event": event,
            "mode": "overlay",
            "branches": branches,
            "chart": chart_data,
            "summary": self._build_summary(branches, adjustments),
            "original_ev": {
                "nav": getattr(tree.expected_value, "nav", 0),
                "tvpi": getattr(tree.expected_value, "tvpi", 0),
            } if tree.expected_value else {},
        }

    def _build_overlay_chart(
        self,
        original_tree,
        branches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Chart comparing original tree EV vs shocked overlays."""
        chart = {
            "type": "macro_overlay_comparison",
            "x_axis": "severity",
            "series": [],
        }

        # Original baseline
        orig_ev = original_tree.expected_value
        orig_nav = getattr(orig_ev, "nav", 0) if orig_ev else 0
        orig_tvpi = getattr(orig_ev, "tvpi", 0) if orig_ev else 0

        nav_series = {"name": "NAV", "type": "bar", "data": [
            {"x": "baseline", "y": round(orig_nav, 0), "color": "#6366f1"},
        ]}
        tvpi_series = {"name": "TVPI", "type": "bar", "data": [
            {"x": "baseline", "y": round(orig_tvpi, 2), "color": "#6366f1"},
        ]}

        colors = {"severe": "#ef4444", "moderate": "#f59e0b", "mild": "#10b981"}

        for branch in branches:
            sev = branch["severity"]
            shocked = branch.get("tree")
            if not shocked or not shocked.expected_value:
                continue
            nav_series["data"].append({
                "x": sev,
                "y": round(shocked.expected_value.nav, 0),
                "color": colors.get(sev, "#888"),
            })
            tvpi_series["data"].append({
                "x": sev,
                "y": round(shocked.expected_value.tvpi, 2),
                "color": colors.get(sev, "#888"),
            })

        chart["series"] = [nav_series, tvpi_series]
        return chart

    # ------------------------------------------------------------------
    # Chart builder
    # ------------------------------------------------------------------

    def _build_impact_chart(
        self,
        branches: List[Dict[str, Any]],
        forecast_months: int,
    ) -> Dict[str, Any]:
        """Build grouped chart data: revenue, cash, runway per severity per month."""
        chart = {
            "type": "macro_impact_branched",
            "x_axis": "month",
            "series": [],
        }

        colors = {"severe": "#ef4444", "moderate": "#f59e0b", "mild": "#10b981"}

        for branch in branches:
            severity = branch["severity"]

            # Aggregate across companies per month
            monthly_revenue = {}
            monthly_cash = {}

            for company_name, data in branch.get("companies", {}).items():
                forecast = data.get("forecast")
                if not forecast:
                    continue
                for row in forecast:
                    period = row.get("period", "")
                    monthly_revenue[period] = (
                        monthly_revenue.get(period, 0)
                        + (row.get("revenue", 0) or 0)
                    )
                    monthly_cash[period] = (
                        monthly_cash.get(period, 0)
                        + (row.get("cash_balance", 0) or 0)
                    )

            periods = sorted(monthly_revenue.keys())

            chart["series"].append({
                "name": f"Revenue ({severity})",
                "type": "line",
                "color": colors.get(severity, "#888"),
                "data": [
                    {"x": p, "y": round(monthly_revenue.get(p, 0), 0)}
                    for p in periods
                ],
            })
            chart["series"].append({
                "name": f"Cash ({severity})",
                "type": "line",
                "color": colors.get(severity, "#888"),
                "dash": "dashed",
                "data": [
                    {"x": p, "y": round(monthly_cash.get(p, 0), 0)}
                    for p in periods
                ],
            })

        return chart

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        branches: List[Dict[str, Any]],
        adjustments: List[DriverAdjustment],
    ) -> Dict[str, Any]:
        """Build a human-readable summary of the analysis."""
        companies_affected = sorted(set(a.company_name for a in adjustments))
        drivers_affected = sorted(set(a.driver_id for a in adjustments))

        # Find most impacted company (most adjustments)
        from collections import Counter
        impact_counts = Counter(a.company_name for a in adjustments)
        most_impacted = impact_counts.most_common(1)[0] if impact_counts else ("N/A", 0)

        return {
            "companies_affected": companies_affected,
            "total_driver_adjustments": len(adjustments),
            "drivers_touched": drivers_affected,
            "most_impacted_company": most_impacted[0],
            "severity_levels": [b["severity"] for b in branches],
            "audit_note": (
                "All adjustments are LLM-reasoned from web search evidence "
                "and mapped through the driver registry. "
                "No hardcoded templates were used."
            ),
        }

    # ------------------------------------------------------------------
    # Serialization helper
    # ------------------------------------------------------------------

    def to_dict(self, analysis: MacroEventAnalysis) -> Dict[str, Any]:
        """Serialize full analysis to JSON-safe dict for API response."""
        return {
            "event": analysis.event_description,
            "search_queries": analysis.search_queries,
            "search_evidence": analysis.search_evidence,
            "macro_factors": [
                {
                    "name": f.name,
                    "direction": f.direction,
                    "magnitude_pct": f.magnitude_pct,
                    "confidence": f.confidence,
                    "reasoning": f.reasoning,
                    "order": f.order,
                    "caused_by": f.caused_by,
                    "source_snippets": f.source_snippets,
                }
                for f in analysis.macro_factors
            ],
            "driver_adjustments": [
                {
                    "driver_id": a.driver_id,
                    "driver_label": a.driver_label,
                    "company_name": a.company_name,
                    "adjustment_pct": a.adjustment_pct,
                    "caused_by": a.caused_by,
                    "reasoning": a.reasoning,
                    "ripple_path": a.ripple_path,
                }
                for a in analysis.driver_adjustments
            ],
            "scenario_branches": analysis.scenario_branches,
            "reasoning_chain": analysis.reasoning_chain,
            "companies_affected": analysis.companies_affected,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_safe(raw: str) -> Any:
    """Parse JSON from LLM response, tolerating markdown fences and prose."""
    if not isinstance(raw, str):
        return raw if isinstance(raw, (list, dict)) else []

    text = raw.strip()

    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    # Find first [ or {
    for i, ch in enumerate(text):
        if ch in ("[", "{"):
            text = text[i:]
            break
    else:
        return []

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try progressively shorter substrings
        for end in range(len(text), max(0, len(text) - 300), -1):
            try:
                return json.loads(text[:end])
            except json.JSONDecodeError:
                continue
    return []
