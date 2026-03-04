"""
TP Document Service — Generate OECD-compliant transfer pricing reports.

Report types:
  - benchmark:   Per-transaction benchmark study (most common deliverable)
  - local_file:  Per-entity local file (OECD Chapter V, Annex II)
  - master_file: Group-level master file (OECD Chapter V, Annex I)
  - cbcr:        Country-by-Country Report data (OECD Chapter V, Annex III)
  - full_pack:   All of the above bundled

All reports produce structured JSON stored in tp_reports.content.
LLM generates narrative sections; data sections are computed from DB.
"""

import json
import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

from app.core.database import supabase_service
from app.services.transfer_pricing_engine import (
    PLI_DEFINITIONS,
    TransferPricingEngine,
    compute_all_plis,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Report section builders — pure data, no LLM
# ═══════════════════════════════════════════════════════════════════════

def _build_executive_summary_data(
    company: Dict, entities: List[Dict], transactions: List[Dict], analyses: List[Dict],
) -> Dict:
    """Data payload for the executive summary section."""
    in_range = sum(1 for a in analyses if a.get("in_range"))
    out_of_range = sum(1 for a in analyses if a.get("in_range") is False)
    needs_review = sum(1 for a in analyses if a.get("in_range") is None)

    jurisdictions = list({e.get("jurisdiction", "??") for e in entities})

    return {
        "group_name": company.get("name", ""),
        "fiscal_year": analyses[0].get("_fiscal_year", str(date.today().year)) if analyses else str(date.today().year),
        "entity_count": len(entities),
        "jurisdictions": jurisdictions,
        "transaction_count": len(transactions),
        "total_ic_value": sum(float(t.get("annual_value") or 0) for t in transactions),
        "currency": transactions[0].get("currency", "USD") if transactions else "USD",
        "results_summary": {
            "in_range": in_range,
            "out_of_range": out_of_range,
            "needs_review": needs_review,
        },
    }


def _build_entity_overview(entities: List[Dict], far_profiles: Dict[str, Dict]) -> List[Dict]:
    """Per-entity summary with FAR characterization."""
    result = []
    for e in entities:
        far = far_profiles.get(e["id"], {})
        result.append({
            "entity_id": e["id"],
            "name": e.get("name", ""),
            "jurisdiction": e.get("jurisdiction", ""),
            "entity_type": e.get("entity_type", ""),
            "functional_role": e.get("functional_role", ""),
            "is_tested_party": e.get("is_tested_party", False),
            "local_currency": e.get("local_currency", "USD"),
            "far_narrative": far.get("narrative", ""),
            "far_functions": far.get("functions", []),
            "far_assets": far.get("assets", []),
            "far_risks": far.get("risks", []),
            "far_confidence": far.get("confidence", 0),
        })
    return result


def _build_transaction_detail(txn: Dict, analysis: Optional[Dict]) -> Dict:
    """Single transaction section data."""
    section = {
        "transaction_id": txn["id"],
        "transaction_type": txn.get("transaction_type", ""),
        "description": txn.get("description", ""),
        "annual_value": txn.get("annual_value"),
        "currency": txn.get("currency", "USD"),
        "from_entity": txn.get("_from_name", txn.get("from_entity_id", "")),
        "to_entity": txn.get("_to_name", txn.get("to_entity_id", "")),
        "pricing_method_current": txn.get("pricing_method_current", ""),
        "pricing_basis": txn.get("pricing_basis", ""),
        "benchmark_status": txn.get("benchmark_status", "not_assessed"),
    }

    if analysis:
        # Method selection
        section["method"] = analysis.get("method", "")
        section["method_name"] = {
            "cup": "Comparable Uncontrolled Price (CUP)",
            "tnmm": "Transactional Net Margin Method (TNMM)",
            "cost_plus": "Cost Plus Method",
            "resale_price": "Resale Price Method",
            "profit_split": "Transactional Profit Split Method",
        }.get(analysis.get("method", ""), analysis.get("method", ""))
        section["method_reasoning"] = analysis.get("method_reasoning", "")
        section["profit_level_indicator"] = analysis.get("profit_level_indicator", "")
        section["pli_name"] = PLI_DEFINITIONS.get(
            analysis.get("profit_level_indicator", ""), {}
        ).get("name", analysis.get("profit_level_indicator", ""))

        # Tested party results
        section["tested_party_pli"] = analysis.get("tested_party_pli")
        pli_by_year = analysis.get("tested_party_pli_by_year", {})
        if isinstance(pli_by_year, str):
            try:
                pli_by_year = json.loads(pli_by_year)
            except (json.JSONDecodeError, TypeError):
                pli_by_year = {}
        section["tested_party_pli_by_year"] = pli_by_year

        # IQR results
        section["iqr"] = {
            "q1": analysis.get("iqr_low"),
            "median": analysis.get("median"),
            "q3": analysis.get("iqr_high"),
            "full_range_low": analysis.get("full_range_low"),
            "full_range_high": analysis.get("full_range_high"),
        }

        # Arm's-length assessment
        section["in_range"] = analysis.get("in_range")
        section["adjustment_needed"] = analysis.get("adjustment_needed")
        section["adjustment_direction"] = analysis.get("adjustment_direction")

        # Comparable set
        comp_results = analysis.get("comparable_results", [])
        if isinstance(comp_results, str):
            try:
                comp_results = json.loads(comp_results)
            except (json.JSONDecodeError, TypeError):
                comp_results = []
        section["comparables"] = comp_results

        # Alternative methods
        alt_methods = analysis.get("alternative_methods", [])
        if isinstance(alt_methods, str):
            try:
                alt_methods = json.loads(alt_methods)
            except (json.JSONDecodeError, TypeError):
                alt_methods = []
        section["alternative_methods"] = alt_methods

    return section


def _build_comparable_rejection_log(comparables: List[Dict]) -> List[Dict]:
    """Rejection log required by OECD — every excluded company needs a reason."""
    rejected = []
    for c in comparables:
        if not c.get("accepted", True):
            rejected.append({
                "name": c.get("candidate_name", ""),
                "source": c.get("candidate_source", ""),
                "composite_score": c.get("composite_score"),
                "rejection_reason": c.get("rejection_reason", ""),
            })
    return rejected


def _build_cbcr_data(
    company: Dict, entities: List[Dict], financials_by_entity: Dict[str, Dict],
) -> List[Dict]:
    """CbCR Table 1 data — per-jurisdiction aggregation."""
    by_jurisdiction: Dict[str, Dict] = {}

    for e in entities:
        j = e.get("jurisdiction", "XX")
        if j not in by_jurisdiction:
            by_jurisdiction[j] = {
                "jurisdiction": j,
                "entities": [],
                "revenue_third_party": 0,
                "revenue_related_party": 0,
                "profit_before_tax": 0,
                "tax_paid": 0,
                "tax_accrued": 0,
                "stated_capital": 0,
                "accumulated_earnings": 0,
                "employees": 0,
                "tangible_assets": 0,
            }

        by_jurisdiction[j]["entities"].append(e.get("name", ""))

        fin = financials_by_entity.get(e["id"], {})
        by_jurisdiction[j]["revenue_third_party"] += float(fin.get("third_party_revenue", 0) or fin.get("revenue", 0) or 0)
        by_jurisdiction[j]["revenue_related_party"] += float(fin.get("intercompany_revenue", 0) or 0)
        by_jurisdiction[j]["profit_before_tax"] += float(fin.get("operating_profit", 0) or 0)
        by_jurisdiction[j]["employees"] += int(fin.get("headcount", 0) or 0)
        by_jurisdiction[j]["tangible_assets"] += float(fin.get("total_assets", 0) or 0)

    return list(by_jurisdiction.values())


# ═══════════════════════════════════════════════════════════════════════
# LLM Narrative Generator
# ═══════════════════════════════════════════════════════════════════════

async def _generate_narrative(
    section_key: str,
    data: Dict,
    llm_fn: Optional[Callable],
    report_type: str = "benchmark",
) -> str:
    """Generate OECD-style narrative for a report section using LLM."""
    if not llm_fn:
        return ""

    prompts = {
        "executive_summary": (
            "Write a concise executive summary (3-5 paragraphs) for a transfer pricing benchmark report.\n\n"
            "DATA:\n{data}\n\n"
            "Cover: group structure, number of IC transactions tested, overall compliance status "
            "(how many in/out of arm's-length range), key jurisdictions, and any adjustments recommended.\n"
            "Tone: formal, suitable for tax authority review. Reference OECD Transfer Pricing Guidelines."
        ),
        "far_analysis": (
            "Write a Functions, Assets, and Risks (FAR) analysis section for a transfer pricing report.\n\n"
            "ENTITY DATA:\n{data}\n\n"
            "For each entity, describe: key functions performed, significant assets employed/used, "
            "and material risks assumed. Characterize each entity per OECD guidelines (e.g., limited-risk "
            "distributor, contract manufacturer, IP entrepreneur). Keep formal, analytical tone."
        ),
        "method_selection": (
            "Write the method selection rationale section for a transfer pricing benchmark report.\n\n"
            "TRANSACTION & METHOD DATA:\n{data}\n\n"
            "Explain: why this method was selected as the Most Appropriate Method (MAM) per OECD Ch. II, "
            "why the tested party was chosen, why the PLI is appropriate, and briefly address why "
            "alternative methods were considered but not selected. Reference OECD Guidelines paragraphs where relevant."
        ),
        "comparable_analysis": (
            "Write the comparable analysis section for a transfer pricing benchmark report.\n\n"
            "COMPARABLE SET DATA:\n{data}\n\n"
            "Cover: search strategy (sources used), selection criteria (OECD 5 comparability factors), "
            "accepted set summary, and rejection rationale for excluded companies. "
            "Present the IQR results and arm's-length assessment. Formal tone for tax authority review."
        ),
        "adjustment_recommendation": (
            "Write the adjustment recommendation section for a transfer pricing report.\n\n"
            "ANALYSIS DATA:\n{data}\n\n"
            "If the tested party is within the IQR, confirm arm's-length compliance. "
            "If outside, quantify the required adjustment to the median and recommend specific pricing changes. "
            "Reference OECD Guidelines Ch. III on adjustments. Keep precise and actionable."
        ),
        "local_file_overview": (
            "Write the overview section of an OECD Local File (Annex II to Chapter V).\n\n"
            "ENTITY DATA:\n{data}\n\n"
            "Cover: local entity description, management structure, business strategy, "
            "key competitors, and the business restructurings context (if any). "
            "This is a regulatory filing document — formal, precise, complete."
        ),
        "master_file_overview": (
            "Write the organizational structure and business overview sections of an OECD Master File "
            "(Annex I to Chapter V).\n\n"
            "GROUP DATA:\n{data}\n\n"
            "Cover: group organizational structure, description of each entity's principal activities, "
            "supply chain for top products/services, major service arrangements, key intangibles and "
            "their ownership, intercompany financial arrangements, and the group's financial and tax positions.\n"
            "Regulatory filing tone."
        ),
    }

    template = prompts.get(section_key, "Summarize this data:\n{data}")
    prompt = template.format(data=json.dumps(data, indent=2, default=str)[:6000])

    try:
        result = await llm_fn(
            prompt,
            "You are an OECD-trained transfer pricing economist writing formal compliance documentation. "
            "Write clearly, precisely, and with appropriate references to OECD Transfer Pricing Guidelines. "
            "Do not use markdown formatting — plain text with paragraph breaks only.",
        )
        return result.strip() if result else ""
    except Exception as e:
        logger.warning(f"[TP_DOC] Narrative generation failed for {section_key}: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════
# Main Document Service
# ═══════════════════════════════════════════════════════════════════════

class TPDocumentService:
    """Generate and store OECD-compliant TP reports."""

    def __init__(self, llm_fn: Optional[Callable] = None):
        self.llm_fn = llm_fn
        self.engine = TransferPricingEngine(llm_fn=llm_fn)

    async def _llm_call(self, prompt: str, system: str) -> str:
        if self.llm_fn:
            return await self.llm_fn(prompt, system)
        try:
            from app.services.model_router import get_model_router, ModelCapability
            router = get_model_router()
            result = await router.get_completion(
                prompt=prompt, system_prompt=system,
                capability=ModelCapability.ANALYSIS,
                max_tokens=4096, temperature=0.3,
                caller_context="tp_document",
            )
            return result.get("response", "")
        except Exception as e:
            logger.warning(f"[TP_DOC] LLM call failed: {e}")
            return ""

    # ── Data loaders ──────────────────────────────────────────────────

    def _load_company(self, company_id: str) -> Dict:
        client = supabase_service.get_client()
        return client.from_("companies").select("*").eq("id", company_id).single().execute().data or {}

    def _load_entities(self, company_id: str) -> List[Dict]:
        client = supabase_service.get_client()
        return client.from_("company_entities").select("*").eq("company_id", company_id).order("name").execute().data or []

    def _load_transactions(self, company_id: str) -> List[Dict]:
        client = supabase_service.get_client()
        txns = client.from_("intercompany_transactions").select("*").eq("company_id", company_id).execute().data or []
        # Resolve entity names
        entities = {e["id"]: e.get("name", "") for e in self._load_entities(company_id)}
        for t in txns:
            t["_from_name"] = entities.get(t.get("from_entity_id", ""), "")
            t["_to_name"] = entities.get(t.get("to_entity_id", ""), "")
        return txns

    def _load_far_profiles(self, entity_ids: List[str]) -> Dict[str, Dict]:
        if not entity_ids:
            return {}
        client = supabase_service.get_client()
        rows = client.from_("entity_far_profiles").select("*").in_("entity_id", entity_ids).execute().data or []
        result = {}
        for r in rows:
            for key in ("functions", "assets", "risks"):
                if isinstance(r.get(key), str):
                    try:
                        r[key] = json.loads(r[key])
                    except (json.JSONDecodeError, TypeError):
                        r[key] = []
            result[r["entity_id"]] = r
        return result

    def _load_analyses(self, transaction_ids: List[str]) -> Dict[str, Dict]:
        """Load latest analysis per transaction."""
        if not transaction_ids:
            return {}
        client = supabase_service.get_client()
        rows = client.from_("tp_analyses").select("*").in_("transaction_id", transaction_ids).order("created_at", desc=True).execute().data or []
        result = {}
        for r in rows:
            tid = r["transaction_id"]
            if tid not in result:  # keep latest only
                for key in ("tested_party_pli_by_year", "comparable_results", "alternative_methods"):
                    if isinstance(r.get(key), str):
                        try:
                            r[key] = json.loads(r[key])
                        except (json.JSONDecodeError, TypeError):
                            pass
                result[tid] = r
        return result

    def _load_comparables_for_search(self, search_id: str) -> List[Dict]:
        client = supabase_service.get_client()
        rows = client.from_("tp_comparables").select("*").eq("search_id", search_id).order("composite_score", desc=True).execute().data or []
        for c in rows:
            for key in ("financials", "financial_years"):
                if isinstance(c.get(key), str):
                    try:
                        c[key] = json.loads(c[key])
                    except (json.JSONDecodeError, TypeError):
                        pass
        return rows

    def _load_entity_financials_map(self, entity_ids: List[str]) -> Dict[str, Dict]:
        """Aggregate financials per entity (latest year)."""
        if not entity_ids:
            return {}
        client = supabase_service.get_client()
        rows = client.from_("entity_financials").select("entity_id, category, subcategory, amount").in_("entity_id", entity_ids).execute().data or []
        result: Dict[str, Dict] = {}
        for r in rows:
            eid = r["entity_id"]
            if eid not in result:
                result[eid] = {}
            cat = r.get("category", "")
            subcat = r.get("subcategory")
            key = subcat if subcat else cat
            result[eid][key] = result[eid].get(key, 0) + float(r.get("amount", 0) or 0)
            # Also aggregate into main category
            if subcat:
                result[eid][cat] = result[eid].get(cat, 0) + float(r.get("amount", 0) or 0)
        return result

    # ── Report builders ───────────────────────────────────────────────

    async def generate_benchmark_report(
        self,
        company_id: str,
        fiscal_year: Optional[str] = None,
        transaction_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a TP benchmark report for a portfolio company.

        This is the primary deliverable — covers all (or specified) IC transactions
        with method selection, comparable analysis, IQR results, and arm's-length assessment.
        """
        fiscal_year = fiscal_year or str(date.today().year)
        company = self._load_company(company_id)
        entities = self._load_entities(company_id)
        entity_ids = [e["id"] for e in entities]
        far_profiles = self._load_far_profiles(entity_ids)
        all_transactions = self._load_transactions(company_id)

        if transaction_ids:
            transactions = [t for t in all_transactions if t["id"] in transaction_ids]
        else:
            transactions = all_transactions

        txn_ids = [t["id"] for t in transactions]
        analyses = self._load_analyses(txn_ids)
        analyses_list = list(analyses.values())
        for a in analyses_list:
            a["_fiscal_year"] = fiscal_year

        # Build report sections
        sections = []

        # 1. Executive Summary
        exec_data = _build_executive_summary_data(company, entities, transactions, analyses_list)
        exec_narrative = await _generate_narrative("executive_summary", exec_data, self._llm_call)
        sections.append({
            "key": "executive_summary",
            "heading": "Executive Summary",
            "data": exec_data,
            "narrative": exec_narrative,
        })

        # 2. Group Structure & Entity Overview
        entity_overview = _build_entity_overview(entities, far_profiles)
        sections.append({
            "key": "group_structure",
            "heading": "Group Structure and Entity Overview",
            "data": entity_overview,
            "narrative": "",  # Descriptive data is self-explanatory
        })

        # 3. FAR Analysis
        far_narrative = await _generate_narrative("far_analysis", entity_overview, self._llm_call)
        sections.append({
            "key": "far_analysis",
            "heading": "Functional Analysis (Functions, Assets, and Risks)",
            "data": entity_overview,
            "narrative": far_narrative,
        })

        # 4. Per-transaction analysis sections
        for txn in transactions:
            analysis = analyses.get(txn["id"])
            txn_detail = _build_transaction_detail(txn, analysis)

            # Method selection narrative
            method_narrative = await _generate_narrative("method_selection", txn_detail, self._llm_call)

            # Comparable analysis narrative
            comparables = []
            rejection_log = []
            if analysis and analysis.get("search_id"):
                comparables = self._load_comparables_for_search(analysis["search_id"])
                rejection_log = _build_comparable_rejection_log(comparables)

            comp_data = {
                "transaction": txn_detail,
                "accepted_comparables": [c for c in comparables if c.get("accepted")],
                "rejection_log": rejection_log,
            }
            comp_narrative = await _generate_narrative("comparable_analysis", comp_data, self._llm_call)

            # Adjustment narrative
            adj_narrative = ""
            if analysis:
                adj_data = {
                    "tested_party_pli": analysis.get("tested_party_pli"),
                    "pli_name": PLI_DEFINITIONS.get(analysis.get("profit_level_indicator", ""), {}).get("name", ""),
                    "iqr_low": analysis.get("iqr_low"),
                    "iqr_high": analysis.get("iqr_high"),
                    "median": analysis.get("median"),
                    "in_range": analysis.get("in_range"),
                    "adjustment_needed": analysis.get("adjustment_needed"),
                    "adjustment_direction": analysis.get("adjustment_direction"),
                }
                adj_narrative = await _generate_narrative("adjustment_recommendation", adj_data, self._llm_call)

            sections.append({
                "key": f"transaction_{txn['id'][:8]}",
                "heading": f"Transaction Analysis: {txn.get('description', txn.get('transaction_type', ''))}",
                "subsections": [
                    {
                        "key": "overview",
                        "heading": "Transaction Overview",
                        "data": txn_detail,
                    },
                    {
                        "key": "method_selection",
                        "heading": "Selection of Most Appropriate Method",
                        "data": {
                            "method": txn_detail.get("method", ""),
                            "method_name": txn_detail.get("method_name", ""),
                            "pli": txn_detail.get("profit_level_indicator", ""),
                            "pli_name": txn_detail.get("pli_name", ""),
                            "reasoning": txn_detail.get("method_reasoning", ""),
                            "alternatives": txn_detail.get("alternative_methods", []),
                        },
                        "narrative": method_narrative,
                    },
                    {
                        "key": "comparable_analysis",
                        "heading": "Comparable Company Analysis",
                        "data": comp_data,
                        "narrative": comp_narrative,
                    },
                    {
                        "key": "iqr_results",
                        "heading": "Interquartile Range Analysis",
                        "data": txn_detail.get("iqr", {}),
                        "tested_party_pli": txn_detail.get("tested_party_pli"),
                        "pli_by_year": txn_detail.get("tested_party_pli_by_year", {}),
                    },
                    {
                        "key": "arm_length_assessment",
                        "heading": "Arm's-Length Assessment and Adjustment",
                        "data": {
                            "in_range": txn_detail.get("in_range"),
                            "adjustment_needed": txn_detail.get("adjustment_needed"),
                            "adjustment_direction": txn_detail.get("adjustment_direction"),
                        },
                        "narrative": adj_narrative,
                    },
                ],
            })

        # 5. Conclusion
        sections.append({
            "key": "conclusion",
            "heading": "Conclusion",
            "data": exec_data["results_summary"],
            "narrative": "",  # LLM will fill via memo template
        })

        # Store report
        title = f"Transfer Pricing Benchmark Report — {company.get('name', '')} — FY{fiscal_year}"
        report = self._store_report(
            company_id=company_id,
            report_type="benchmark",
            fiscal_year=fiscal_year,
            title=title,
            content={"sections": sections, "metadata": {"generated_at": datetime.utcnow().isoformat(), "version": "1.0"}},
        )

        return {
            "report_id": report.get("id"),
            "report_type": "benchmark",
            "title": title,
            "fiscal_year": fiscal_year,
            "sections": len(sections),
            "transactions_covered": len(transactions),
            "content": {"sections": sections},
        }

    async def generate_local_file(
        self,
        company_id: str,
        entity_id: str,
        fiscal_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate OECD Local File (Annex II to Chapter V) for a specific entity.

        Sections per OECD Annex II:
          1. Local entity overview
          2. Controlled transactions
          3. Financial information
          4. Comparability analysis (per transaction)
        """
        fiscal_year = fiscal_year or str(date.today().year)
        company = self._load_company(company_id)

        client = supabase_service.get_client()
        entity = client.from_("company_entities").select("*").eq("id", entity_id).single().execute().data
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        far_profiles = self._load_far_profiles([entity_id])
        far = far_profiles.get(entity_id, {})

        # Transactions involving this entity
        all_txns = self._load_transactions(company_id)
        entity_txns = [t for t in all_txns if t.get("from_entity_id") == entity_id or t.get("to_entity_id") == entity_id]
        txn_ids = [t["id"] for t in entity_txns]
        analyses = self._load_analyses(txn_ids)

        # Entity financials
        fin_map = self._load_entity_financials_map([entity_id])
        entity_fin = fin_map.get(entity_id, {})

        sections = []

        # 1. Local Entity Overview (Annex II, Part A)
        entity_data = {
            "name": entity.get("name", ""),
            "jurisdiction": entity.get("jurisdiction", ""),
            "entity_type": entity.get("entity_type", ""),
            "functional_role": entity.get("functional_role", ""),
            "tax_id": entity.get("tax_id", ""),
            "local_currency": entity.get("local_currency", "USD"),
            "far_narrative": far.get("narrative", ""),
            "far_functions": far.get("functions", []),
            "far_assets": far.get("assets", []),
            "far_risks": far.get("risks", []),
            "group_name": company.get("name", ""),
        }
        overview_narrative = await _generate_narrative("local_file_overview", entity_data, self._llm_call)
        sections.append({
            "key": "local_entity",
            "heading": "A. Local Entity",
            "subsections": [
                {"key": "description", "heading": "Description of Management Structure", "data": entity_data, "narrative": overview_narrative},
                {"key": "business_strategy", "heading": "Business Strategy", "data": entity_data, "narrative": ""},
            ],
        })

        # 2. Controlled Transactions (Annex II, Part B)
        txn_sections = []
        for txn in entity_txns:
            analysis = analyses.get(txn["id"])
            txn_detail = _build_transaction_detail(txn, analysis)

            comparables = []
            rejection_log = []
            if analysis and analysis.get("search_id"):
                comparables = self._load_comparables_for_search(analysis["search_id"])
                rejection_log = _build_comparable_rejection_log(comparables)

            txn_sections.append({
                "key": f"txn_{txn['id'][:8]}",
                "heading": f"{txn.get('transaction_type', '').title()}: {txn.get('description', '')}",
                "transaction": txn_detail,
                "comparables": [c for c in comparables if c.get("accepted")],
                "rejection_log": rejection_log,
            })

        sections.append({
            "key": "controlled_transactions",
            "heading": "B. Controlled Transactions",
            "subsections": txn_sections,
        })

        # 3. Financial Information (Annex II, Part C)
        plis = compute_all_plis(entity_fin) if entity_fin else {}
        sections.append({
            "key": "financial_information",
            "heading": "C. Financial Information",
            "data": {
                "financials": entity_fin,
                "profit_level_indicators": plis,
                "currency": entity.get("local_currency", "USD"),
            },
        })

        title = f"Local File — {entity.get('name', '')} ({entity.get('jurisdiction', '')}) — FY{fiscal_year}"
        report = self._store_report(
            company_id=company_id,
            report_type="local_file",
            fiscal_year=fiscal_year,
            title=title,
            content={"sections": sections, "metadata": {"entity_id": entity_id, "generated_at": datetime.utcnow().isoformat()}},
            entity_id=entity_id,
        )

        return {
            "report_id": report.get("id"),
            "report_type": "local_file",
            "title": title,
            "entity": entity.get("name", ""),
            "jurisdiction": entity.get("jurisdiction", ""),
            "fiscal_year": fiscal_year,
            "sections": len(sections),
            "transactions_covered": len(entity_txns),
            "content": {"sections": sections},
        }

    async def generate_master_file(
        self,
        company_id: str,
        fiscal_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate OECD Master File (Annex I to Chapter V).

        Sections per OECD Annex I:
          A. Organizational structure
          B. Description of MNE business
          C. MNE intangibles
          D. Intercompany financial activities
          E. Financial and tax positions
        """
        fiscal_year = fiscal_year or str(date.today().year)
        company = self._load_company(company_id)
        entities = self._load_entities(company_id)
        entity_ids = [e["id"] for e in entities]
        far_profiles = self._load_far_profiles(entity_ids)
        transactions = self._load_transactions(company_id)
        fin_map = self._load_entity_financials_map(entity_ids)

        entity_overview = _build_entity_overview(entities, far_profiles)

        # Group-level data
        group_data = {
            "group_name": company.get("name", ""),
            "entities": entity_overview,
            "transactions": [
                {
                    "type": t.get("transaction_type", ""),
                    "description": t.get("description", ""),
                    "from": t.get("_from_name", ""),
                    "to": t.get("_to_name", ""),
                    "value": t.get("annual_value"),
                    "currency": t.get("currency", "USD"),
                }
                for t in transactions
            ],
            "jurisdictions": list({e.get("jurisdiction", "") for e in entities}),
        }

        overview_narrative = await _generate_narrative("master_file_overview", group_data, self._llm_call)

        sections = [
            {
                "key": "organizational_structure",
                "heading": "A. Organizational Structure",
                "data": {
                    "group_name": company.get("name", ""),
                    "entities": [
                        {"name": e.get("name", ""), "jurisdiction": e.get("jurisdiction", ""), "type": e.get("entity_type", ""), "role": e.get("functional_role", "")}
                        for e in entities
                    ],
                },
                "narrative": overview_narrative,
            },
            {
                "key": "business_description",
                "heading": "B. Description of MNE's Business",
                "data": {
                    "principal_activities": [
                        {"entity": e.get("name", ""), "type": e.get("entity_type", ""), "role": e.get("functional_role", "")}
                        for e in entities if e.get("entity_type") != "dormant"
                    ],
                    "supply_chain": [
                        {"from": t.get("_from_name", ""), "to": t.get("_to_name", ""), "type": t.get("transaction_type", "")}
                        for t in transactions
                    ],
                },
            },
            {
                "key": "intangibles",
                "heading": "C. MNE's Intangibles",
                "data": {
                    "ip_entities": [
                        {
                            "entity": e.get("name", ""),
                            "jurisdiction": e.get("jurisdiction", ""),
                            "ip_assets": [a for a in (far_profiles.get(e["id"], {}).get("assets", [])) if isinstance(a, dict) and a.get("type") == "intangible"],
                        }
                        for e in entities if e.get("entity_type") in ("ip_holding", "operating")
                    ],
                    "ip_transactions": [t for t in transactions if t.get("transaction_type") in ("ip_licensing", "cost_sharing")],
                },
            },
            {
                "key": "financial_activities",
                "heading": "D. MNE's Intercompany Financial Activities",
                "data": {
                    "financing_transactions": [t for t in transactions if t.get("transaction_type") == "financing"],
                    "total_ic_value": sum(float(t.get("annual_value") or 0) for t in transactions),
                    "currency": "USD",
                },
            },
            {
                "key": "financial_tax_positions",
                "heading": "E. MNE's Financial and Tax Positions",
                "data": {
                    "consolidated_financials": {
                        cat: sum(fin.get(cat, 0) for fin in fin_map.values())
                        for cat in ("revenue", "cogs", "opex", "operating_profit", "total_assets")
                    },
                    "entity_financials": {
                        eid: fin for eid, fin in fin_map.items()
                    },
                },
            },
        ]

        title = f"Master File — {company.get('name', '')} — FY{fiscal_year}"
        report = self._store_report(
            company_id=company_id,
            report_type="master_file",
            fiscal_year=fiscal_year,
            title=title,
            content={"sections": sections, "metadata": {"generated_at": datetime.utcnow().isoformat()}},
        )

        return {
            "report_id": report.get("id"),
            "report_type": "master_file",
            "title": title,
            "fiscal_year": fiscal_year,
            "sections": len(sections),
            "entity_count": len(entities),
            "content": {"sections": sections},
        }

    async def generate_cbcr(
        self,
        company_id: str,
        fiscal_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate Country-by-Country Report data (OECD Annex III to Chapter V).

        Produces CbCR Table 1 (per-jurisdiction) and Table 2 (entity list).
        """
        fiscal_year = fiscal_year or str(date.today().year)
        company = self._load_company(company_id)
        entities = self._load_entities(company_id)
        entity_ids = [e["id"] for e in entities]
        fin_map = self._load_entity_financials_map(entity_ids)

        # Table 1: Per-jurisdiction aggregation
        table1 = _build_cbcr_data(company, entities, fin_map)

        # Table 2: Entity list per jurisdiction
        table2 = {}
        for e in entities:
            j = e.get("jurisdiction", "XX")
            if j not in table2:
                table2[j] = []
            table2[j].append({
                "name": e.get("name", ""),
                "entity_type": e.get("entity_type", ""),
                "tax_id": e.get("tax_id", ""),
                "principal_activity": e.get("functional_role") or e.get("entity_type", ""),
            })

        sections = [
            {
                "key": "table1",
                "heading": "Table 1: Overview of Allocation of Income, Taxes and Business Activities by Tax Jurisdiction",
                "data": table1,
            },
            {
                "key": "table2",
                "heading": "Table 2: List of All Constituent Entities of the MNE Group",
                "data": table2,
            },
            {
                "key": "table3",
                "heading": "Table 3: Additional Information",
                "data": {
                    "notes": "Data sourced from entity-level financial records. Figures are in the reporting currency of each entity, converted to USD using period-average exchange rates where applicable.",
                    "reporting_entity": company.get("name", ""),
                    "fiscal_year": fiscal_year,
                },
            },
        ]

        title = f"Country-by-Country Report — {company.get('name', '')} — FY{fiscal_year}"
        report = self._store_report(
            company_id=company_id,
            report_type="cbcr",
            fiscal_year=fiscal_year,
            title=title,
            content={"sections": sections, "metadata": {"generated_at": datetime.utcnow().isoformat()}},
        )

        return {
            "report_id": report.get("id"),
            "report_type": "cbcr",
            "title": title,
            "fiscal_year": fiscal_year,
            "jurisdictions": len(table1),
            "entities": len(entities),
            "content": {"sections": sections},
        }

    async def generate_full_pack(
        self,
        company_id: str,
        fiscal_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate complete TP documentation pack: master file + local files + benchmark + CbCR."""
        fiscal_year = fiscal_year or str(date.today().year)
        entities = self._load_entities(company_id)

        results = {
            "report_type": "full_pack",
            "fiscal_year": fiscal_year,
            "reports": [],
        }

        # Master file
        master = await self.generate_master_file(company_id, fiscal_year)
        results["reports"].append({"type": "master_file", "report_id": master.get("report_id"), "title": master.get("title")})

        # Benchmark report
        benchmark = await self.generate_benchmark_report(company_id, fiscal_year)
        results["reports"].append({"type": "benchmark", "report_id": benchmark.get("report_id"), "title": benchmark.get("title")})

        # Local files per entity
        for e in entities:
            if e.get("entity_type") == "dormant":
                continue
            try:
                local = await self.generate_local_file(company_id, e["id"], fiscal_year)
                results["reports"].append({"type": "local_file", "report_id": local.get("report_id"), "title": local.get("title")})
            except Exception as ex:
                logger.warning(f"[TP_DOC] Local file failed for {e.get('name')}: {ex}")
                results["reports"].append({"type": "local_file", "entity": e.get("name"), "error": str(ex)})

        # CbCR
        cbcr = await self.generate_cbcr(company_id, fiscal_year)
        results["reports"].append({"type": "cbcr", "report_id": cbcr.get("report_id"), "title": cbcr.get("title")})

        # Store the pack as its own report entry
        company = self._load_company(company_id)
        title = f"Full TP Documentation Pack — {company.get('name', '')} — FY{fiscal_year}"
        pack_report = self._store_report(
            company_id=company_id,
            report_type="full_pack",
            fiscal_year=fiscal_year,
            title=title,
            content={"reports": results["reports"], "metadata": {"generated_at": datetime.utcnow().isoformat()}},
        )
        results["report_id"] = pack_report.get("id")
        results["title"] = title

        return results

    # ── Retrieve existing reports ─────────────────────────────────────

    async def get_report(self, report_id: str) -> Dict:
        client = supabase_service.get_client()
        row = client.from_("tp_reports").select("*").eq("id", report_id).single().execute().data
        if not row:
            raise ValueError(f"Report {report_id} not found")
        if isinstance(row.get("content"), str):
            try:
                row["content"] = json.loads(row["content"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row

    async def list_reports(self, company_id: str, fiscal_year: Optional[str] = None) -> List[Dict]:
        client = supabase_service.get_client()
        q = client.from_("tp_reports").select("id, report_type, entity_id, fiscal_year, title, status, created_at").eq("company_id", company_id)
        if fiscal_year:
            q = q.eq("fiscal_year", fiscal_year)
        return q.order("created_at", desc=True).execute().data or []

    # ── Storage ───────────────────────────────────────────────────────

    def _store_report(
        self,
        company_id: str,
        report_type: str,
        fiscal_year: str,
        title: str,
        content: Dict,
        entity_id: Optional[str] = None,
    ) -> Dict:
        client = supabase_service.get_client()
        row = {
            "company_id": company_id,
            "report_type": report_type,
            "fiscal_year": fiscal_year,
            "title": title,
            "content": json.dumps(content, default=str),
            "status": "draft",
            "generated_by": "ai",
        }
        if entity_id:
            row["entity_id"] = entity_id
        resp = client.from_("tp_reports").insert(row).execute()
        return resp.data[0] if resp.data else row
