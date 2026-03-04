"""
FAR Analysis Service — Functions/Assets/Risks profiling for transfer pricing.

Multi-pass LLM analysis with OECD-aligned methodology:
  Pass 1: Extract raw economic activities from all available data
  Pass 2: Structured FAR classification with DEMPE overlay for intangibles
  Pass 3: Group context — position entity relative to other group entities

Comparison uses significance-weighted scoring, not naive set intersection.
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.database import supabase_service

logger = logging.getLogger(__name__)

# ── Taxonomy codes (for machine comparability) ──────────────────────
# These are reference codes, NOT a closed set. The LLM can add custom
# function/asset/risk descriptions beyond these codes.

FUNCTION_TAXONOMY = {
    "r_and_d": "Research & Development",
    "manufacturing": "Manufacturing / Production",
    "contract_manufacturing": "Contract Manufacturing (toll/limited risk)",
    "distribution": "Distribution / Sales",
    "limited_risk_distribution": "Limited-Risk Distribution",
    "marketing": "Marketing & Brand Management",
    "management_services": "Group Management / Strategic Direction",
    "ip_development": "IP Development & Maintenance (DEMPE active)",
    "ip_holding": "IP Holding (passive / legal ownership)",
    "financing": "Intra-group Financing / Treasury",
    "procurement": "Centralized Procurement",
    "shared_services": "Shared Services (HR, IT, Finance)",
    "commissionaire": "Commissionaire / Sales Agent",
    "quality_control": "Quality Control & Assurance",
    "logistics": "Logistics & Supply Chain Management",
    "regulatory_affairs": "Regulatory Affairs & Compliance",
    "customer_support": "Customer Support / After-Sales Service",
    "data_processing": "Data Processing & Analytics",
    "treasury": "Cash Pooling / Treasury Management",
}

ASSET_TAXONOMY = {
    "patents": "Patents & Technical IP",
    "trademarks": "Trademarks & Brand IP",
    "trade_secrets": "Trade Secrets / Know-how",
    "software_ip": "Software / Source Code / Algorithms",
    "customer_lists": "Customer Relationships / Lists",
    "customer_contracts": "Long-term Customer Contracts",
    "supplier_contracts": "Key Supplier Agreements",
    "physical_plant": "Manufacturing Plant & Equipment",
    "inventory": "Inventory / Work-in-Progress",
    "financial_assets": "Financial Assets / Intercompany Loans",
    "data": "Proprietary Data Assets",
    "licenses": "Third-party Licenses & Permits",
    "goodwill": "Assembled Workforce / Goodwill",
}

RISK_TAXONOMY = {
    "market_risk": "Market / Demand Risk",
    "credit_risk": "Credit / Collection Risk",
    "rd_risk": "R&D / Technology Obsolescence Risk",
    "inventory_risk": "Inventory / Obsolescence Risk",
    "fx_risk": "Foreign Exchange Risk",
    "product_liability": "Product Liability Risk",
    "regulatory_risk": "Regulatory / Compliance Risk",
    "financial_risk": "Financial / Funding Risk",
    "concentration_risk": "Customer / Supplier Concentration Risk",
    "country_risk": "Country / Political Risk",
    "operational_risk": "Operational / Execution Risk",
    "cybersecurity_risk": "Cybersecurity / Data Breach Risk",
}

_INTANGIBLE_ASSETS = {
    "patents", "trademarks", "trade_secrets", "software_ip",
    "customer_lists", "customer_contracts", "data", "licenses", "goodwill",
}

_SIGNIFICANCE_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}

# ── DEMPE framework labels ──────────────────────────────────────────
DEMPE_FUNCTIONS = ["development", "enhancement", "maintenance", "protection", "exploitation"]


def _parse_json_response(raw: str) -> Optional[Dict]:
    """Extract JSON from an LLM response, handling markdown fences."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    # Find first { or [
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            text = text[i:]
            break
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _ensure_list(val: Any) -> List:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
    return val if isinstance(val, list) else []


class FARAnalysisService:
    """Multi-pass FAR profiling aligned with OECD TP Guidelines Ch. I & VI."""

    def __init__(self, llm_fn: Optional[Callable] = None):
        """
        Args:
            llm_fn: async (prompt: str, system: str) -> str
                     If None, uses model_router. If model_router unavailable, rule-based fallback.
        """
        self.llm_fn = llm_fn

    async def _llm_call(self, prompt: str, system: str, json_mode: bool = False) -> str:
        """Route LLM calls through injected fn or model_router."""
        if self.llm_fn:
            return await self.llm_fn(prompt, system)
        try:
            from app.services.model_router import get_model_router, ModelCapability
            router = get_model_router()
            result = await router.get_completion(
                prompt=prompt,
                system_prompt=system,
                capability=ModelCapability.ANALYSIS,
                max_tokens=4096,
                temperature=0.3,
                json_mode=json_mode,
                caller_context="far_analysis",
            )
            return result.get("response", "")
        except Exception as e:
            logger.warning(f"[FAR] LLM call failed: {e}")
            return ""

    # ── Data gathering ───────────────────────────────────────────────

    async def _gather_entity_context(self, entity_id: str) -> Dict[str, Any]:
        """Pull entity metadata, financials, IC transactions, and group siblings."""
        client = supabase_service.get_client()

        entity = client.from_("company_entities").select("*").eq("id", entity_id).single().execute().data
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        company_id = entity["company_id"]

        # Financials — latest period, grouped by category+subcategory
        fin_resp = client.from_("entity_financials") \
            .select("category, subcategory, amount, currency, period") \
            .eq("entity_id", entity_id) \
            .order("period", desc=True) \
            .limit(100) \
            .execute()

        # IC transactions (both directions)
        txn_resp = client.from_("intercompany_transactions") \
            .select("*") \
            .or_(f"from_entity_id.eq.{entity_id},to_entity_id.eq.{entity_id}") \
            .execute()

        # Sibling entities in the same group
        siblings_resp = client.from_("company_entities") \
            .select("id, name, jurisdiction, entity_type, functional_role") \
            .eq("company_id", company_id) \
            .neq("id", entity_id) \
            .execute()

        # All group IC transactions (for value chain context)
        all_txn_resp = client.from_("intercompany_transactions") \
            .select("from_entity_id, to_entity_id, transaction_type, description, annual_value, currency") \
            .eq("company_id", company_id) \
            .execute()

        return {
            "entity": entity,
            "financials": fin_resp.data or [],
            "transactions": txn_resp.data or [],
            "siblings": siblings_resp.data or [],
            "all_group_transactions": all_txn_resp.data or [],
        }

    def _build_financial_profile(self, financials: List[Dict]) -> Dict[str, Any]:
        """Aggregate financials into a structured profile with ratios."""
        by_category: Dict[str, float] = {}
        by_sub: Dict[str, float] = {}
        for f in financials:
            cat = f.get("category", "")
            sub = f.get("subcategory", "")
            amt = float(f.get("amount", 0) or 0)
            by_category[cat] = by_category.get(cat, 0) + amt
            if sub:
                by_sub[f"{cat}/{sub}"] = by_sub.get(f"{cat}/{sub}", 0) + amt

        revenue = by_category.get("revenue", 0)
        cogs = abs(by_category.get("cogs", 0))
        opex = abs(by_category.get("opex", 0))
        gp = by_category.get("gross_profit", revenue - cogs)
        op = by_category.get("operating_profit", gp - opex)
        total_assets = by_category.get("total_assets", 0)
        headcount = by_category.get("headcount", 0)

        # IC revenue split
        ic_rev = by_sub.get("revenue/intercompany_revenue", 0)
        tp_rev = by_sub.get("revenue/third_party_revenue", revenue - ic_rev)

        ratios = {}
        if revenue is not None and revenue != 0:
            ratios["gross_margin"] = round(gp / revenue, 4)
            ratios["operating_margin"] = round(op / revenue, 4)
            ratios["ic_revenue_pct"] = round(ic_rev / revenue, 4) if ic_rev else 0
        if opex is not None and opex != 0:
            ratios["berry_ratio"] = round(gp / opex, 4)
        total_costs = cogs + opex
        if total_costs is not None and total_costs != 0:
            ratios["markup_on_total_costs"] = round(op / total_costs, 4)
        if total_assets is not None and total_assets != 0:
            ratios["return_on_assets"] = round(op / total_assets, 4)

        # R&D intensity
        rd_cost = by_sub.get("opex/r&d_costs", by_sub.get("opex/rd_costs", 0))
        if revenue is not None and revenue != 0 and rd_cost:
            ratios["rd_intensity"] = round(abs(rd_cost) / revenue, 4)

        return {
            "revenue": revenue,
            "cogs": cogs,
            "opex": opex,
            "gross_profit": gp,
            "operating_profit": op,
            "total_assets": total_assets,
            "headcount": headcount,
            "ic_revenue": ic_rev,
            "third_party_revenue": tp_rev,
            "rd_cost": abs(rd_cost) if rd_cost else 0,
            "ratios": ratios,
            "by_category": by_category,
            "by_subcategory": by_sub,
        }

    def _build_transaction_context(
        self, entity_id: str, transactions: List[Dict], siblings: List[Dict]
    ) -> List[Dict[str, str]]:
        """Build human-readable IC transaction summaries with counterparty context."""
        sibling_map = {s["id"]: s for s in siblings}
        summaries = []
        for t in transactions:
            from_id = t.get("from_entity_id")
            to_id = t.get("to_entity_id")
            direction = "outbound" if from_id == entity_id else "inbound"
            counterparty_id = to_id if direction == "outbound" else from_id
            counterparty = sibling_map.get(counterparty_id, {})
            cp_name = counterparty.get("name", "unknown entity")
            cp_type = counterparty.get("entity_type", "")
            cp_jurisdiction = counterparty.get("jurisdiction", "")

            summaries.append({
                "direction": direction,
                "type": t.get("transaction_type", ""),
                "description": t.get("description", ""),
                "value": f"{t.get('currency', 'USD')} {t.get('annual_value', 'N/A'):,}" if t.get("annual_value") else "N/A",
                "counterparty": f"{cp_name} ({cp_type}, {cp_jurisdiction})" if cp_type else cp_name,
                "pricing_method": t.get("pricing_method_current", "unknown"),
                "pricing_basis": t.get("pricing_basis", ""),
            })
        return summaries

    def _build_group_map(
        self, entity: Dict, siblings: List[Dict], all_transactions: List[Dict]
    ) -> str:
        """Build a text description of the group structure and value chain."""
        lines = [f"GROUP STRUCTURE (parent company_id: {entity['company_id']})"]
        all_entities = [entity] + siblings
        entity_map = {e["id"]: e for e in all_entities}

        for e in all_entities:
            marker = " <-- THIS ENTITY" if e["id"] == entity["id"] else ""
            lines.append(
                f"  - {e.get('name', '?')} | {e.get('entity_type', '?')} | "
                f"{e.get('jurisdiction', '?')} | Role: {e.get('functional_role', 'not specified')}{marker}"
            )

        lines.append("\nINTERCOMPANY FLOWS:")
        for t in all_transactions:
            from_name = entity_map.get(t["from_entity_id"], {}).get("name", "?")
            to_name = entity_map.get(t["to_entity_id"], {}).get("name", "?")
            lines.append(
                f"  {from_name} --> {to_name}: {t.get('transaction_type', '')} "
                f"({t.get('currency', 'USD')} {t.get('annual_value', 'N/A')})"
            )

        return "\n".join(lines)

    # ── LLM Pass 1: Extract economic activities ──────────────────────

    async def _pass1_extract_activities(self, ctx: Dict) -> Dict:
        """Extract raw economic activities, decision-making, and risk control from data."""
        entity = ctx["entity"]
        fin_profile = self._build_financial_profile(ctx["financials"])
        txn_context = self._build_transaction_context(
            entity["id"], ctx["transactions"], ctx["siblings"]
        )

        fin_text = json.dumps(fin_profile, indent=2, default=str)
        txn_text = json.dumps(txn_context, indent=2, default=str)
        group_map = self._build_group_map(entity, ctx["siblings"], ctx["all_group_transactions"])

        prompt = f"""You are analyzing a legal entity for transfer pricing purposes. Extract its economic activities from the data below.

ENTITY:
  Name: {entity.get('name', '')}
  Type: {entity.get('entity_type', '')}
  Jurisdiction: {entity.get('jurisdiction', '')}
  Described role: {entity.get('functional_role', 'Not specified')}
  Tax ID: {entity.get('tax_id', 'N/A')}
  Tested party flag: {entity.get('is_tested_party', False)}

FINANCIAL PROFILE:
{fin_text}

INTERCOMPANY TRANSACTIONS:
{txn_text}

{group_map}

Based on this data, extract:

1. **Economic activities**: What does this entity actually DO? Not just its legal type — what activities generate its revenue, what costs does it incur, what value does it create? Consider the financial ratios (R&D intensity, IC revenue %, margins).

2. **Decision-making & control**: Based on the transaction flows and financial profile, who appears to control key risks? Does this entity make strategic decisions or execute instructions? Is it a principal, entrepreneur, or limited-risk entity?

3. **People functions**: What key people functions does this entity likely perform? (OECD: "people functions" = humans who control risk, make decisions about asset use, perform DEMPE activities)

4. **Contractual vs economic reality**: Based on the financial data, does the entity's economic behavior match what you'd expect from its declared type? Flag any mismatches (e.g., entity typed as "services" but with significant R&D costs and IP-like margins).

5. **Intangible involvement**: Does this entity appear to develop, enhance, maintain, protect, or exploit any intangibles? Which DEMPE functions apply?

Return JSON:
{{
  "activities": ["<activity description>", ...],
  "decision_authority": "principal|entrepreneur|limited_risk|routine",
  "decision_evidence": "<1-2 sentences explaining why>",
  "people_functions": ["<function description>", ...],
  "type_mismatch_flags": ["<mismatch>", ...] or [],
  "dempe_involvement": {{
    "development": {{"active": bool, "evidence": "..."}},
    "enhancement": {{"active": bool, "evidence": "..."}},
    "maintenance": {{"active": bool, "evidence": "..."}},
    "protection": {{"active": bool, "evidence": "..."}},
    "exploitation": {{"active": bool, "evidence": "..."}}
  }},
  "value_drivers": ["<what drives this entity's economic value>", ...],
  "data_quality_notes": "<what data was missing or uncertain>"
}}"""

        system = (
            "You are an OECD-trained transfer pricing economist. "
            "Analyze economic substance, not just legal form. "
            "Be specific — reference actual numbers from the data. "
            "Return ONLY valid JSON, no markdown fences."
        )

        raw = await self._llm_call(prompt, system, json_mode=True)
        parsed = _parse_json_response(raw)
        if not parsed:
            logger.warning("[FAR] Pass 1 failed to parse, returning empty extraction")
            return {
                "activities": [],
                "decision_authority": "routine",
                "decision_evidence": "Insufficient data",
                "people_functions": [],
                "type_mismatch_flags": [],
                "dempe_involvement": {f: {"active": False, "evidence": ""} for f in DEMPE_FUNCTIONS},
                "value_drivers": [],
                "data_quality_notes": "LLM extraction failed",
            }
        return parsed

    # ── LLM Pass 2: Structured FAR classification ────────────────────

    async def _pass2_classify_far(
        self, entity: Dict, extraction: Dict, fin_profile: Dict
    ) -> Dict[str, Any]:
        """Classify extracted activities into structured FAR with significance and DEMPE."""

        prompt = f"""Given the economic activity extraction below, produce a structured FAR (Functions/Assets/Risks) profile.

ENTITY: {entity.get('name', '')} ({entity.get('entity_type', '')}, {entity.get('jurisdiction', '')})

EXTRACTED ACTIVITIES:
{json.dumps(extraction, indent=2)}

FINANCIAL RATIOS:
{json.dumps(fin_profile.get('ratios', {}), indent=2)}

KEY FINANCIALS:
  Revenue: {fin_profile.get('revenue', 0):,.0f}
  Operating profit: {fin_profile.get('operating_profit', 0):,.0f}
  IC revenue: {fin_profile.get('ic_revenue', 0):,.0f}
  R&D cost: {fin_profile.get('rd_cost', 0):,.0f}
  Headcount: {fin_profile.get('headcount', 0)}

TAXONOMY CODES (use these where applicable, but you MAY add custom entries with code "custom_<name>"):
  Functions: {json.dumps(FUNCTION_TAXONOMY)}
  Assets: {json.dumps(ASSET_TAXONOMY)}
  Risks: {json.dumps(RISK_TAXONOMY)}

INSTRUCTIONS:
- Significance MUST be justified by data: "high" = core to value creation / >20% of revenue/costs, "medium" = significant but supporting, "low" = minimal / incidental
- For each function, state whether it's a DEMPE function and which DEMPE category
- For each risk, state who CONTROLS it (this entity, parent, or shared) and who BEARS the financial consequence
- For assets, distinguish: owned vs used-under-license, and whether the entity performed DEMPE on it

Return JSON:
{{
  "functions": [
    {{
      "code": "<taxonomy_code or custom_xxx>",
      "label": "<human readable>",
      "significance": "high|medium|low",
      "significance_rationale": "<why this level — cite numbers>",
      "description": "<2-3 sentences on what this entity specifically does>",
      "is_dempe": bool,
      "dempe_category": "development|enhancement|maintenance|protection|exploitation|null",
      "personnel_involved": "<who performs this — management, engineers, sales team, etc.>"
    }}
  ],
  "assets": [
    {{
      "code": "<taxonomy_code or custom_xxx>",
      "label": "<human readable>",
      "type": "tangible|intangible|financial",
      "significance": "high|medium|low",
      "ownership": "legal_owner|economic_owner|licensee|user",
      "dempe_performed": bool,
      "description": "<specifics about this asset>"
    }}
  ],
  "risks": [
    {{
      "code": "<taxonomy_code or custom_xxx>",
      "label": "<human readable>",
      "significance": "high|medium|low",
      "controlled_by": "this_entity|parent|shared|contractual",
      "borne_by": "this_entity|parent|shared",
      "mitigation": "<how is this risk managed>",
      "description": "<specifics>"
    }}
  ],
  "characterization": {{
    "entity_characterization": "<e.g., limited-risk distributor, full-fledged manufacturer, IP principal, routine service provider>",
    "economic_substance_level": "high|medium|low",
    "substance_evidence": "<what proves substance: headcount, decision-making, asset ownership, risk bearing>",
    "suggested_tp_methods": ["<method code: cup, tnmm, cost_plus, resale_price, profit_split>"],
    "tested_party_suitability": "suitable|unsuitable|possible",
    "tested_party_reasoning": "<why suitable or not as tested party>"
  }},
  "dempe_summary": {{
    "has_significant_dempe": bool,
    "primary_dempe_functions": ["<D/E/M/P/E labels that apply>"],
    "intangible_value_split_estimate": "<who captures intangible value in this group structure>"
  }},
  "narrative": "<3-5 sentence analytical summary: entity's role, economic substance, key functions, risk profile, and position in the value chain>",
  "confidence": float 0-1
}}"""

        system = (
            "You are a senior transfer pricing economist preparing a FAR analysis for regulatory submission. "
            "Every classification must be justified by evidence from the data. "
            "Do not guess — if data is insufficient, say so and lower confidence. "
            "Return ONLY valid JSON."
        )

        raw = await self._llm_call(prompt, system, json_mode=True)
        parsed = _parse_json_response(raw)
        if not parsed:
            logger.warning("[FAR] Pass 2 classification failed")
            return None
        return parsed

    # ── Rule-based fallback (enhanced) ───────────────────────────────

    def _rule_based_infer(self, entity: Dict, fin_profile: Optional[Dict] = None) -> Dict[str, Any]:
        """Fallback when LLM is unavailable. Uses entity type + financial signals."""
        entity_type = entity.get("entity_type", "operating")
        ratios = (fin_profile or {}).get("ratios", {})
        revenue = (fin_profile or {}).get("revenue", 0)
        rd_cost = (fin_profile or {}).get("rd_cost", 0)
        ic_rev_pct = ratios.get("ic_revenue_pct", 0)

        # Base from entity type
        type_map = {
            "operating": {
                "functions": [
                    ("r_and_d", "high" if ratios.get("rd_intensity", 0) > 0.1 else "medium"),
                    ("distribution", "high" if ic_rev_pct < 0.5 else "medium"),
                    ("management_services", "medium"),
                ],
                "assets": [("software_ip", "medium"), ("customer_lists", "medium")],
                "risks": [("market_risk", "high"), ("rd_risk", "medium" if rd_cost > 0 else "low")],
            },
            "ip_holding": {
                "functions": [
                    ("ip_holding", "high"),
                    ("ip_development", "high" if rd_cost > 0 else "low"),
                ],
                "assets": [("patents", "high"), ("trademarks", "high"), ("software_ip", "medium"), ("trade_secrets", "medium")],
                "risks": [("rd_risk", "high"), ("regulatory_risk", "medium")],
            },
            "distribution": {
                "functions": [
                    ("distribution", "high"),
                    ("marketing", "medium"),
                    ("limited_risk_distribution", "high" if ic_rev_pct > 0.8 else "low"),
                ],
                "assets": [("customer_lists", "high"), ("inventory", "medium")],
                "risks": [("market_risk", "high"), ("credit_risk", "medium"), ("inventory_risk", "medium")],
            },
            "services": {
                "functions": [("shared_services", "high"), ("management_services", "medium")],
                "assets": [("data", "medium")],
                "risks": [("regulatory_risk", "medium"), ("operational_risk", "medium")],
            },
            "financing": {
                "functions": [("financing", "high"), ("treasury", "medium")],
                "assets": [("financial_assets", "high")],
                "risks": [("credit_risk", "high"), ("financial_risk", "high"), ("fx_risk", "medium")],
            },
            "dormant": {"functions": [], "assets": [], "risks": []},
        }

        defaults = type_map.get(entity_type, type_map["operating"])

        functions = [
            {
                "code": code,
                "label": FUNCTION_TAXONOMY.get(code, code),
                "significance": sig,
                "significance_rationale": "Inferred from entity type and available financial ratios",
                "description": FUNCTION_TAXONOMY.get(code, code),
                "is_dempe": code in ("ip_development", "r_and_d"),
                "dempe_category": "development" if code in ("ip_development", "r_and_d") else None,
                "personnel_involved": "unknown",
            }
            for code, sig in defaults["functions"]
        ]

        assets = [
            {
                "code": code,
                "label": ASSET_TAXONOMY.get(code, code),
                "type": "intangible" if code in _INTANGIBLE_ASSETS else ("financial" if code == "financial_assets" else "tangible"),
                "significance": sig,
                "ownership": "legal_owner",
                "dempe_performed": False,
                "description": ASSET_TAXONOMY.get(code, code),
            }
            for code, sig in defaults["assets"]
        ]

        risks = [
            {
                "code": code,
                "label": RISK_TAXONOMY.get(code, code),
                "significance": sig,
                "controlled_by": "this_entity",
                "borne_by": "this_entity",
                "mitigation": "unknown",
                "description": RISK_TAXONOMY.get(code, code),
            }
            for code, sig in defaults["risks"]
        ]

        om = ratios.get("operating_margin")
        margin_note = f" Operating margin: {om:.1%}." if om is not None else ""

        return {
            "functions": functions,
            "assets": assets,
            "risks": risks,
            "characterization": {
                "entity_characterization": f"{entity_type} entity (rule-based — review required)",
                "economic_substance_level": "medium" if revenue > 0 else "low",
                "substance_evidence": f"Revenue: {revenue:,.0f}.{margin_note}" if revenue else "No financial data available",
                "suggested_tp_methods": [],
                "tested_party_suitability": "possible",
                "tested_party_reasoning": "Rule-based profile — requires AI analysis for proper determination",
            },
            "dempe_summary": {
                "has_significant_dempe": entity_type in ("ip_holding", "operating") and rd_cost > 0,
                "primary_dempe_functions": [],
                "intangible_value_split_estimate": "Unknown — requires full group analysis",
            },
            "narrative": (
                f"Rule-based FAR profile for {entity.get('name', entity_type)} "
                f"({entity_type}, {entity.get('jurisdiction', 'unknown')}).{margin_note} "
                f"This profile should be refined with AI analysis when LLM access is available."
            ),
            "confidence": 0.25 if not revenue else 0.35,
        }

    # ── Main entry point ─────────────────────────────────────────────

    async def infer_far_profile(self, entity_id: str) -> Dict[str, Any]:
        """Multi-pass FAR inference. Returns the saved profile dict."""
        ctx = await self._gather_entity_context(entity_id)
        entity = ctx["entity"]
        fin_profile = self._build_financial_profile(ctx["financials"])

        # Try LLM multi-pass
        profile = None
        try:
            extraction = await self._pass1_extract_activities(ctx)
            if extraction and extraction.get("activities"):
                profile = await self._pass2_classify_far(entity, extraction, fin_profile)
                if profile:
                    # Attach the raw extraction for auditability
                    profile["_extraction"] = extraction
        except Exception as e:
            logger.warning(f"[FAR] LLM analysis failed for {entity.get('name', entity_id)}: {e}")

        if not profile:
            logger.info(f"[FAR] Using rule-based fallback for {entity.get('name', entity_id)}")
            profile = self._rule_based_infer(entity, fin_profile)

        source = "ai_inferred" if profile.get("_extraction") else "rule_based"

        # Save to DB
        profile_row = {
            "entity_id": entity_id,
            "functions": json.dumps(profile.get("functions", [])),
            "assets": json.dumps(profile.get("assets", [])),
            "risks": json.dumps(profile.get("risks", [])),
            "narrative": profile.get("narrative", ""),
            "source": source,
            "confidence": profile.get("confidence", 0.3),
        }

        client = supabase_service.get_client()
        client.from_("entity_far_profiles").delete().eq("entity_id", entity_id).execute()
        result = client.from_("entity_far_profiles").insert(profile_row).execute()

        saved = result.data[0] if result.data else profile_row
        # Return the full rich profile (not just the DB row)
        saved["_full_profile"] = profile
        return saved

    # ── Batch inference for entire group ──────────────────────────────

    async def infer_group_profiles(self, company_id: str) -> List[Dict[str, Any]]:
        """Run FAR analysis on all entities under a portfolio company."""
        client = supabase_service.get_client()
        entities = client.from_("company_entities") \
            .select("id, name, entity_type") \
            .eq("company_id", company_id) \
            .execute().data or []

        results = []
        for e in entities:
            try:
                profile = await self.infer_far_profile(e["id"])
                results.append({"entity_id": e["id"], "name": e["name"], "status": "ok", "profile": profile})
            except Exception as ex:
                logger.error(f"[FAR] Failed for entity {e['id']} ({e['name']}): {ex}")
                results.append({"entity_id": e["id"], "name": e["name"], "status": "error", "error": str(ex)})
        return results

    # ── Comparison (significance-weighted) ───────────────────────────

    def compare_far_profiles(self, profile_a: Dict, profile_b: Dict) -> Dict[str, Any]:
        """Significance-weighted FAR comparison for functional comparability (OECD factor #2).

        Returns a score 0-10 with detailed breakdown. High-significance items
        dominate the score — a shared "high" R&D function is worth more than
        three shared "low" functions.
        """

        def _extract_weighted(profile: Dict, key: str, code_key: str) -> Dict[str, float]:
            """Returns {code: weight} where weight reflects significance."""
            items = _ensure_list(profile.get(key, []))
            result = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                code = item.get(code_key) or item.get("code", "")
                if not code:
                    continue
                sig = item.get("significance", "medium")
                result[code] = _SIGNIFICANCE_WEIGHT.get(sig, 2.0)
            return result

        def _weighted_similarity(wa: Dict[str, float], wb: Dict[str, float]) -> float:
            """Weighted Jaccard: sum of min(weights) / sum of max(weights) for union of codes."""
            all_codes = set(wa) | set(wb)
            if not all_codes:
                return 1.0
            numerator = sum(min(wa.get(c, 0), wb.get(c, 0)) for c in all_codes)
            denominator = sum(max(wa.get(c, 0), wb.get(c, 0)) for c in all_codes)
            return numerator / denominator if denominator > 0 else 0.0

        funcs_a = _extract_weighted(profile_a, "functions", "function")
        funcs_b = _extract_weighted(profile_b, "functions", "function")
        assets_a = _extract_weighted(profile_a, "assets", "asset")
        assets_b = _extract_weighted(profile_b, "assets", "asset")
        risks_a = _extract_weighted(profile_a, "risks", "risk")
        risks_b = _extract_weighted(profile_b, "risks", "risk")

        # Also support the new "code" key format
        if not funcs_a:
            funcs_a = _extract_weighted(profile_a, "functions", "code")
        if not funcs_b:
            funcs_b = _extract_weighted(profile_b, "functions", "code")
        if not assets_a:
            assets_a = _extract_weighted(profile_a, "assets", "code")
        if not assets_b:
            assets_b = _extract_weighted(profile_b, "assets", "code")
        if not risks_a:
            risks_a = _extract_weighted(profile_a, "risks", "code")
        if not risks_b:
            risks_b = _extract_weighted(profile_b, "risks", "code")

        func_sim = _weighted_similarity(funcs_a, funcs_b)
        asset_sim = _weighted_similarity(assets_a, assets_b)
        risk_sim = _weighted_similarity(risks_a, risks_b)

        # Weighted composite: functions 55%, risks 30%, assets 15%
        composite = func_sim * 0.55 + risk_sim * 0.30 + asset_sim * 0.15
        score = round(composite * 10, 1)

        # Characterization match bonus/penalty
        char_a = (profile_a.get("characterization") or {}).get("entity_characterization", "")
        char_b = (profile_b.get("characterization") or {}).get("entity_characterization", "")
        characterization_match = bool(char_a and char_b and char_a.lower() == char_b.lower())

        shared_funcs = set(funcs_a) & set(funcs_b)
        only_a = set(funcs_a) - set(funcs_b)
        only_b = set(funcs_b) - set(funcs_a)

        # Build narrative
        narrative_parts = []
        if shared_funcs:
            high_shared = [c for c in shared_funcs if funcs_a.get(c, 0) >= 3 or funcs_b.get(c, 0) >= 3]
            if high_shared:
                labels = [FUNCTION_TAXONOMY.get(f, f) for f in high_shared]
                narrative_parts.append(f"Key shared functions: {', '.join(labels)}")
            other_shared = shared_funcs - set(high_shared)
            if other_shared:
                labels = [FUNCTION_TAXONOMY.get(f, f) for f in other_shared]
                narrative_parts.append(f"Also shared: {', '.join(labels)}")

        divergent = only_a | only_b
        if divergent:
            labels = [FUNCTION_TAXONOMY.get(f, f) for f in divergent]
            narrative_parts.append(f"Divergent functions: {', '.join(labels)}")

        if characterization_match:
            narrative_parts.append(f"Matching characterization: {char_a}")

        # DEMPE comparison
        dempe_a = profile_a.get("dempe_summary", {})
        dempe_b = profile_b.get("dempe_summary", {})
        if dempe_a.get("has_significant_dempe") != dempe_b.get("has_significant_dempe"):
            narrative_parts.append("DEMPE mismatch: one entity has significant intangible involvement, the other does not")

        return {
            "score": score,
            "func_similarity": round(func_sim, 3),
            "asset_similarity": round(asset_sim, 3),
            "risk_similarity": round(risk_sim, 3),
            "characterization_match": characterization_match,
            "narrative": ". ".join(narrative_parts) if narrative_parts else "Insufficient data for comparison",
            "shared_functions": list(shared_funcs),
            "divergent_functions_a": list(only_a),
            "divergent_functions_b": list(only_b),
            "dempe_compatible": dempe_a.get("has_significant_dempe") == dempe_b.get("has_significant_dempe"),
        }

    # ── LLM-powered deep comparison ─────────────────────────────────

    async def compare_far_profiles_deep(
        self, profile_a: Dict, profile_b: Dict, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """LLM-assisted comparison that goes beyond code matching.

        Considers functional nuance (e.g., pharma distribution vs consumer goods distribution),
        risk allocation differences, DEMPE alignment, and economic circumstance fit.
        """
        # Start with quantitative score
        quant = self.compare_far_profiles(profile_a, profile_b)

        prompt = f"""Compare these two FAR profiles for transfer pricing comparability. Go beyond code matching — consider functional nuance, industry context, risk allocation, and DEMPE alignment.

ENTITY A:
{json.dumps(profile_a, indent=2, default=str)}

ENTITY B:
{json.dumps(profile_b, indent=2, default=str)}

{"CONTEXT: " + context if context else ""}

Quantitative similarity score: {quant['score']}/10

Assess:
1. Are the functions genuinely comparable or just nominally similar? (e.g., "distribution" of software vs hardware is very different)
2. Do the risk profiles align? Is risk allocated similarly between entity and parent?
3. Are the DEMPE functions comparable? Does one entity create intangible value the other doesn't?
4. Would an OECD examiner accept these as comparable for benchmarking?

Return JSON:
{{
  "adjusted_score": float 0-10,
  "comparability_assessment": "highly_comparable|comparable|marginally_comparable|not_comparable",
  "key_similarities": ["..."],
  "key_differences": ["..."],
  "adjustments_needed": ["<comparability adjustments an economist would make>"],
  "examiner_risk": "low|medium|high — likelihood of tax authority challenge",
  "reasoning": "<2-3 sentences>"
}}"""

        raw = await self._llm_call(prompt, "You are a senior TP economist. Be specific and critical.", json_mode=True)
        parsed = _parse_json_response(raw)
        if parsed:
            return {**quant, **parsed}
        return quant

    # ── DB operations ────────────────────────────────────────────────

    async def get_profile(self, entity_id: str) -> Optional[Dict]:
        """Fetch existing FAR profile for an entity."""
        client = supabase_service.get_client()
        resp = client.from_("entity_far_profiles").select("*").eq("entity_id", entity_id).execute()
        if resp.data:
            profile = resp.data[0]
            for key in ("functions", "assets", "risks"):
                profile[key] = _ensure_list(profile.get(key))
            return profile
        return None

    async def get_group_profiles(self, company_id: str) -> List[Dict]:
        """Fetch all FAR profiles for entities under a company."""
        client = supabase_service.get_client()
        entities = client.from_("company_entities") \
            .select("id, name, entity_type, jurisdiction") \
            .eq("company_id", company_id) \
            .execute().data or []

        entity_ids = [e["id"] for e in entities]
        if not entity_ids:
            return []

        profiles_resp = client.from_("entity_far_profiles") \
            .select("*") \
            .in_("entity_id", entity_ids) \
            .execute()

        profile_map = {}
        for p in (profiles_resp.data or []):
            for key in ("functions", "assets", "risks"):
                p[key] = _ensure_list(p.get(key))
            profile_map[p["entity_id"]] = p

        return [
            {**e, "far_profile": profile_map.get(e["id"])}
            for e in entities
        ]

    async def update_profile(self, entity_id: str, updates: Dict) -> Dict:
        """Manually update a FAR profile (user overrides)."""
        client = supabase_service.get_client()
        row = {}
        for key in ("functions", "assets", "risks"):
            if key in updates:
                row[key] = json.dumps(updates[key]) if isinstance(updates[key], list) else updates[key]
        if "narrative" in updates:
            row["narrative"] = updates["narrative"]
        row["source"] = "manual"

        resp = client.from_("entity_far_profiles") \
            .update(row) \
            .eq("entity_id", entity_id) \
            .execute()
        return resp.data[0] if resp.data else row
