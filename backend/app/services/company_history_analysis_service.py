"""
Company full-history analysis pipeline: multi-doc resolution, bulk extract,
per-company aggregation, follow-on/round/ownership analytics, portfolio-relative (DPI Sankey).
Backend-agnostic: accepts DocumentBlobStorage, DocumentMetadataRepo, CompanyDataRepo.
Long-running and robust: checkpointing after each document and per-company; suitable for Celery.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.abstractions.company_data import CompanyDataRepo
from app.abstractions.document_metadata import DocumentMetadataRepo
from app.abstractions.storage import DocumentBlobStorage
from app.services.document_process_service import run_document_process

logger = logging.getLogger(__name__)


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse common date strings to datetime. Returns None if unparseable."""
    if not date_str or not isinstance(date_str, str):
        return None
    s = date_str.strip()
    try:
        if len(s) == 7 and "-" in s:  # YYYY-MM
            return datetime.strptime(s + "-01", "%Y-%m-%d")
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00").split(".")[0])
        if len(s) >= 10 and "-" in s[:10]:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    except Exception:
        pass
    return None


def months_since_date(date_str: Optional[str]) -> Optional[float]:
    """Months from a given date (e.g. round date) to now. Returns None if unparseable."""
    dt = _parse_date(date_str)
    if dt is None:
        return None
    now = datetime.now()
    months = (now.year - dt.year) * 12 + (now.month - dt.month)
    days_frac = (now.day - dt.day) / 30.0
    return max(0.0, months + days_frac)


def _build_dpi_sankey(
    fund_id: str,
    company_repo: CompanyDataRepo,
) -> Dict[str, Any]:
    """
    Build DPI Sankey data: Fund → Companies → Exits → LP Distributions.
    Uses portfolio companies + company details from company_repo.
    Returns { type, title, data: { nodes, links }, metrics } for frontend/deck.
    """
    nodes: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    total_invested = 0.0
    total_distributed = 0.0

    try:
        companies = company_repo.get_portfolio_companies(fund_id, with_company_details=True)
    except Exception as e:
        logger.warning("DPI Sankey: get_portfolio_companies failed: %s", e)
        companies = []

    fund_label = f"Fund {fund_id[:8]}..." if len(fund_id or "") > 8 else f"Fund {fund_id or '?'}"
    nodes.append({"id": 0, "name": fund_label, "level": 0})
    node_id = 1
    lp_dist_node_id = 9999
    lp_dist_added = False

    for pc in companies:
        company = pc.get("companies") or {}
        cid = pc.get("company_id") or company.get("id")
        company_name = company.get("name") or f"Company {cid or node_id}"
        investment = float(pc.get("investment_amount") or 0)
        ownership_pct = float(pc.get("ownership_pct") or 0)
        status = (pc.get("status") or company.get("status") or "active").lower()

        total_invested += investment

        nodes.append({
            "id": node_id,
            "name": company_name,
            "level": 1,
            "investment": investment,
        })
        links.append({"source": 0, "target": node_id, "value": max(0.001, investment)})

        if status == "exited":
            exit_val = float(pc.get("exit_value_usd") or company.get("exit_value_usd") or 0)
            distributed = (ownership_pct / 100.0) * exit_val if exit_val else 0.0
            total_distributed += distributed

            exit_node_id = node_id + 1000
            nodes.append({
                "id": exit_node_id,
                "name": f"{company_name} Exit",
                "level": 2,
                "exit_value": exit_val,
            })
            links.append({
                "source": node_id,
                "target": exit_node_id,
                "value": max(0.001, exit_val),
            })

            if not lp_dist_added:
                nodes.append({"id": lp_dist_node_id, "name": "LP Distributions", "level": 3})
                lp_dist_added = True
            links.append({
                "source": exit_node_id,
                "target": lp_dist_node_id,
                "value": max(0.001, distributed),
            })

        node_id += 1

    dpi = total_distributed / total_invested if total_invested > 0 else 0.0
    return {
        "type": "sankey",
        "title": f"DPI Flow: {dpi:.2f}x",
        "data": {"nodes": nodes, "links": links},
        "metrics": {
            "total_invested": total_invested,
            "total_distributed": total_distributed,
            "dpi": dpi,
        },
        "renderType": "tableau",
    }


def months_since_last_round(enriched: Dict[str, Any]) -> Optional[float]:
    """
    Months since the company's most recent funding round (by date).
    Uses enriched['funding_rounds']; returns None if no rounds or no dates.
    """
    rounds = enriched.get("funding_rounds") or []
    if not rounds:
        return None
    with_dates = [(r, r.get("date") or r.get("announced_date")) for r in rounds if r.get("date") or r.get("announced_date")]
    if not with_dates:
        return None
    # Sort by date descending, take latest
    def sort_key(item):
        dt = _parse_date(item[1])
        return dt or datetime.min

    with_dates.sort(key=sort_key, reverse=True)
    return months_since_date(with_dates[0][1])


def run(
    fund_id: str,
    company_ids: Optional[List[str]] = None,
    document_ids: Optional[List[str]] = None,
    *,
    storage: DocumentBlobStorage,
    document_repo: DocumentMetadataRepo,
    company_repo: CompanyDataRepo,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run the company full-history pipeline: resolve docs → bulk extract → aggregate per company
    → per-company analytics (follow-on, round projection, ownership) → portfolio-relative (DPI Sankey).
    All I/O goes through the three abstractions.
    progress_callback: optional callable(progress: dict) for checkpointing (e.g. documents_done, companies_done).
    """
    progress: Dict[str, Any] = {
        "documents_done": 0,
        "companies_done": 0,
        "current_step": "resolve_documents",
        "pending_document_ids": [],
        "enriched_company_ids": [],
    }
    result: Dict[str, Any] = {
        "fund_id": fund_id,
        "documents_processed": 0,
        "companies_enriched": [],
        "follow_on": {},
        "round_projections": {},
        "ownership_scenarios": {},
        "memo_assumptions": {},
        "cap_table_history": {},
        "exit_waterfall_summary": {},
        "dpi_sankey": None,
        "progress": progress,
    }

    def report_progress():
        if progress_callback:
            try:
                progress_callback(progress)
            except Exception as e:
                logger.warning("progress_callback failed: %s", e)

    # —— Step 1: Resolve documents ——
    if document_ids:
        pending_docs = []
        for doc_id in document_ids:
            doc = document_repo.get(doc_id)
            if doc and doc.get("status") != "completed" and doc.get("storage_path"):
                pending_docs.append(doc)
            elif doc and doc.get("status") == "completed":
                progress["documents_done"] += 1
        progress["pending_document_ids"] = [d["id"] for d in pending_docs]
    else:
        # By fund: get portfolio company_ids then list docs (any status), filter pending in Python
        if not company_ids and company_repo:
            pcs = company_repo.get_portfolio_companies(fund_id, with_company_details=False)
            company_ids = [pc.get("company_id") for pc in pcs if pc.get("company_id")]
        company_ids = company_ids or []
        filters: Dict[str, Any] = {"fund_id": fund_id} if fund_id else {}
        if company_ids:
            filters["company_id"] = company_ids
        all_docs = document_repo.list_(filters=filters, limit=1000, offset=0)
        pending_docs = [
            d for d in all_docs
            if d.get("status") != "completed" and d.get("storage_path")
        ]
        progress["pending_document_ids"] = [d["id"] for d in pending_docs]

    progress["current_step"] = "bulk_extract"
    report_progress()

    # —— Step 2: Bulk extract (parallel, deck agent pattern) ——
    def process_one(doc: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = doc.get("id")
        storage_path = doc.get("storage_path")
        if not doc_id or not storage_path:
            return {"success": False, "doc": doc}
        return run_document_process(
            document_id=doc_id,
            storage_path=storage_path,
            document_type=doc.get("document_type") or "other",
            storage=storage,
            document_repo=document_repo,
            company_id=doc.get("company_id"),
            fund_id=doc.get("fund_id") or fund_id,
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_one, doc): doc
            for doc in pending_docs
            if doc.get("id") and doc.get("storage_path")
        }
        for future in as_completed(futures):
            doc = futures[future]
            try:
                out = future.result()
                if out.get("success"):
                    progress["documents_done"] += 1
                    report_progress()
            except Exception as e:
                logger.warning("Bulk extract doc %s failed: %s", doc.get("id"), e)

    progress["current_step"] = "aggregate_per_company"
    report_progress()

    # —— Step 3: Aggregate per company ——
    filters_comp = {"status": "completed"}
    if fund_id:
        filters_comp["fund_id"] = fund_id
    if company_ids:
        filters_comp["company_id"] = company_ids
    completed_docs = document_repo.list_(filters=filters_comp, limit=500, offset=0)
    if not company_ids and fund_id and company_repo:
        pcs = company_repo.get_portfolio_companies(fund_id, with_company_details=False)
        company_ids = list({pc.get("company_id") for pc in pcs if pc.get("company_id")})

    enriched_by_company: Dict[str, Dict[str, Any]] = {}
    for doc in completed_docs:
        cid = doc.get("company_id")
        if not cid:
            continue
        company_data = company_repo.get_company(cid)
        if not company_data:
            continue
        extracted = doc.get("extracted_data") or {}
        if isinstance(extracted, str):
            try:
                import json
                extracted = json.loads(extracted)
            except Exception:
                extracted = {}
        item = {
            "extracted_data": extracted,
            "document_type": doc.get("document_type") or "other",
            "document_id": doc.get("id"),
            "processed_at": doc.get("processed_at"),
        }
        if cid not in enriched_by_company:
            funding_rounds = company_repo.get_funding_rounds(cid)
            merged = dict(company_data)
            merged["funding_rounds"] = funding_rounds
            merged["extracted_data_from_docs"] = [item]
            enriched_by_company[cid] = merged
        else:
            enriched_by_company[cid]["extracted_data_from_docs"].append(item)

    # Pick one investment_memo per company (latest by processed_at) and set memo_assumptions + deal fields
    for cid, enriched in enriched_by_company.items():
        memo_items = [
            it for it in enriched.get("extracted_data_from_docs", [])
            if (it.get("document_type") or "").strip().lower() == "investment_memo"
        ]
        if memo_items:
            memo_items_sorted = sorted(
                memo_items,
                key=lambda x: (x.get("processed_at") or "") or "0",
                reverse=True,
            )
            chosen = memo_items_sorted[0]
            ed = chosen.get("extracted_data") or {}
            enriched["memo_assumptions"] = ed.get("memo_assumptions") or {}
            deal = {}
            for key in ("company_name", "investment_date", "round", "valuation_pre_money", "deal_terms_summary"):
                if key in ed and ed[key] is not None:
                    deal[key] = ed[key]
            if deal:
                enriched["memo_deal"] = deal
            result["memo_assumptions"][cid] = {
                "memo_assumptions": enriched["memo_assumptions"],
                **enriched.get("memo_deal", {}),
            }
        progress["companies_done"] += 1
        progress["enriched_company_ids"] = list(enriched_by_company.keys())
        result["companies_enriched"].append({"company_id": cid, "enriched": True})
    report_progress()

    # —— Step 4: Per-company analytics (follow-on, round projection, ownership) ——
    progress["current_step"] = "follow_on"
    report_progress()
    try:
        from app.services.pre_post_cap_table import PrePostCapTable
        from app.services.ownership_return_analyzer import OwnershipReturnAnalyzer, InvestmentType
        cap_table = PrePostCapTable()
        analyzer = OwnershipReturnAnalyzer()
        try:
            from app.services.advanced_cap_table import CapTableCalculator
            advanced_cap = CapTableCalculator()
        except Exception:
            advanced_cap = None
        for cid, enriched in enriched_by_company.items():
            pc = company_repo.get_portfolio_company(fund_id, cid) if company_repo else None
            if not pc:
                result["follow_on"][cid] = {"strategy": "unknown", "recommendation": "Portfolio company not found"}
                continue
            funding_rounds = enriched.get("funding_rounds") or []
            # Past rounds and pref stack: cap table history from real funding_rounds
            try:
                cap_history = cap_table.calculate_full_cap_table_history(enriched)
                result["cap_table_history"][cid] = {
                    "current_cap_table": cap_history.get("current_cap_table"),
                    "waterfall_data": cap_history.get("waterfall_data", []),
                    "total_raised": cap_history.get("total_raised"),
                    "num_rounds": cap_history.get("num_rounds"),
                }
            except Exception as cap_err:
                logger.debug("Cap table history for %s: %s", cid, cap_err)
                result["cap_table_history"][cid] = {}
            # Exit waterfall from past + pref terms when available
            if advanced_cap and funding_rounds:
                try:
                    memo_deal = enriched.get("memo_deal") or {}
                    upcoming_pre_money = (
                        memo_deal.get("valuation_pre_money")
                        or enriched.get("current_valuation_usd")
                        or 10_000_000
                    )
                    exit_value = float(upcoming_pre_money) * 3
                    waterfall = advanced_cap.calculate_liquidation_waterfall(
                        exit_value, {}, None, funding_rounds
                    )
                    result["exit_waterfall_summary"][cid] = {
                        "exit_value": exit_value,
                        "distributions": waterfall.get("distributions", []),
                        "total_distributed": waterfall.get("total_distributed", 0),
                        "summary": waterfall.get("summary"),
                    }
                except Exception as wf_err:
                    logger.debug("Exit waterfall for %s: %s", cid, wf_err)
            current_ownership_pct = (pc.get("ownership_pct") or 0) or 0
            current_investment = (pc.get("investment_amount") or 0) or 0
            memo_deal = enriched.get("memo_deal") or {}
            upcoming_round_size = (
                memo_deal.get("valuation_pre_money")
                or enriched.get("current_valuation_usd")
                or 5_000_000
            )
            upcoming_pre_money = (
                memo_deal.get("valuation_pre_money")
                or enriched.get("current_valuation_usd")
                or 10_000_000
            )
            from decimal import Decimal
            pro_rata_calc = cap_table.calculate_pro_rata_investment(
                current_ownership=Decimal(str(current_ownership_pct / 100)),
                new_money_raised=Decimal(str(upcoming_round_size)),
                pre_money_valuation=Decimal(str(upcoming_pre_money)),
            )
            company_data_for_scenarios = {
                **enriched,
                "our_previous_ownership": current_ownership_pct / 100,
                "valuation": upcoming_pre_money,
            }
            ownership_scenarios = analyzer.calculate_ownership_scenarios(
                company_data=company_data_for_scenarios,
                investment_amount=float(pro_rata_calc.get("pro_rata_investment_needed", 0)),
                investment_type=InvestmentType.PRO_RATA if current_ownership_pct >= 10 else InvestmentType.FOLLOW,
                fund_size=100_000_000,
            )
            months_since_round = months_since_last_round(enriched)
            result["follow_on"][cid] = {
                "strategy": "pro-rata" if current_ownership_pct >= 5 else "selective",
                "recommendation": f"Ownership {current_ownership_pct:.1f}%",
                "pro_rata_amount": float(pro_rata_calc.get("pro_rata_investment_needed", 0)),
                "current_ownership": current_ownership_pct,
                "months_since_last_round": months_since_round,
            }
            result["round_projections"][cid] = {
                "round_size": upcoming_round_size,
                "pre_money": upcoming_pre_money,
                "months_since_last_round": months_since_round,
            }
            result["ownership_scenarios"][cid] = ownership_scenarios
    except Exception as e:
        logger.warning("Per-company analytics failed: %s", e)
        result["follow_on_error"] = str(e)

    # —— Step 5: Portfolio-relative (DPI Sankey) ——
    progress["current_step"] = "dpi_sankey"
    report_progress()
    if company_repo:
        try:
            result["dpi_sankey"] = _build_dpi_sankey(fund_id, company_repo)
        except Exception as e:
            logger.warning("DPI Sankey build failed: %s", e)
            result["dpi_sankey"] = {
                "type": "sankey",
                "title": "DPI Flow",
                "data": {"nodes": [], "links": []},
                "metrics": {"total_invested": 0, "total_distributed": 0, "dpi": 0},
                "error": str(e),
            }
    else:
        result["dpi_sankey"] = {
            "type": "sankey",
            "title": "DPI Flow",
            "data": {"nodes": [], "links": []},
            "metrics": {"total_invested": 0, "total_distributed": 0, "dpi": 0},
            "error": "No company_repo available",
        }

    progress["current_step"] = "completed"
    report_progress()
    result["documents_processed"] = progress["documents_done"]
    return result


class CompanyHistoryAnalysisService:
    """Thin class wrapper so the orchestrator can import and instantiate."""

    async def run(self, *args, **kwargs):
        return await asyncio.to_thread(run, *args, **kwargs)

    async def analyze_full_history(self, company_id: str, fund_id: str = None) -> dict:
        """Analyze full company history -- funding rounds, metrics evolution, key events."""
        try:
            from app.core.adapters import get_storage, get_document_repo, get_company_repo
            storage = get_storage()
            document_repo = get_document_repo()
            company_repo = get_company_repo()
            if not all([storage, document_repo, company_repo]):
                return {
                    "company_id": company_id,
                    "error": "Storage adapters not available",
                    "funding_rounds": [],
                    "metrics_history": [],
                }
            return await asyncio.to_thread(
                run,
                fund_id=fund_id or "",
                company_ids=[company_id],
                storage=storage,
                document_repo=document_repo,
                company_repo=company_repo,
            )
        except Exception as e:
            return {
                "company_id": company_id,
                "error": str(e),
                "funding_rounds": [],
                "metrics_history": [],
            }
