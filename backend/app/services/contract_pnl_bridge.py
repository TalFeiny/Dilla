"""
Contract → P&L Bridge

Converts extracted commercial contract data (vendor MSAs, client agreements,
SaaS subscriptions) into fpa_actuals rows. Splits annual/monthly values into
per-period line items linked back to the source document.

Also handles intercompany agreements → ic_transaction_suggestions for TP engine.

Called from document_process_service.py after legal extraction completes.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

# Doc types that produce P&L line items
COMMERCIAL_DOC_TYPES = {
    "vendor_contract", "services_agreement", "msa", "sow", "lease",
    "license_agreement", "contract",
    # Client/revenue-side
    "client_agreement", "client_contract",
    # Employment → OpEx
    "employment_agreement", "employment_contract",
    # IP/Software
    "ip_agreement", "software_license",
    # Generic commercial
    "service_agreement", "product_agreement",
}

# Doc types that produce TP transactions
INTERCOMPANY_DOC_TYPES = {
    "intercompany_agreement", "management_agreement",
}

# Valid ERP categories for P&L routing
VALID_ERP_CATEGORIES = {"revenue", "cogs", "opex_rd", "opex_sm", "opex_ga"}


def _get_supabase_client():
    try:
        from app.core.supabase_client import get_supabase_client
        return get_supabase_client()
    except Exception:
        return None


def _parse_date(s: Optional[str]) -> Optional[date]:
    """Parse ISO date string to date, tolerant of formats."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def _generate_periods(
    start: date,
    end: date,
    frequency: str = "monthly",
) -> List[date]:
    """Generate period-start dates between start and end (inclusive)."""
    periods = []
    current = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)

    if frequency == "quarterly":
        step = relativedelta(months=3)
    elif frequency == "annual":
        step = relativedelta(years=1)
    else:
        step = relativedelta(months=1)

    while current <= end_month:
        periods.append(current)
        current += step

    return periods


def bridge_contract_to_pnl(
    extracted_data: Dict[str, Any],
    company_id: str,
    fund_id: Optional[str],
    document_id: str,
    document_type: str,
    document_name: str = "",
) -> Dict[str, Any]:
    """Convert extracted contract ERP attribution into fpa_actuals rows.

    Returns {"success": bool, "rows_written": int, "details": {...}}.
    """
    if not extracted_data or not company_id:
        return {"success": False, "rows_written": 0, "error": "missing data"}

    erp = extracted_data.get("erp_attribution") or {}
    category = (erp.get("category") or "").strip().lower()
    subcategory = (erp.get("subcategory") or "").strip().lower()

    if category not in VALID_ERP_CATEGORIES:
        logger.info(
            "[CONTRACT_PNL] No valid ERP category for doc %s (got: %s)",
            document_id, category,
        )
        return {"success": False, "rows_written": 0, "error": f"no valid category: {category}"}

    # Financial values
    annual_value = erp.get("annual_value")
    monthly_amount = erp.get("monthly_amount")
    payment_frequency = (erp.get("payment_frequency") or "monthly").lower()
    currency = erp.get("currency") or extracted_data.get("currency") or "USD"

    # Need at least one value
    if not annual_value and not monthly_amount:
        logger.info("[CONTRACT_PNL] No financial value for doc %s", document_id)
        return {"success": False, "rows_written": 0, "error": "no financial value"}

    # Derive monthly from annual or vice versa
    if monthly_amount and not annual_value:
        annual_value = monthly_amount * 12
    elif annual_value and not monthly_amount:
        monthly_amount = annual_value / 12

    # Determine periods to write
    committed_periods = erp.get("committed_periods") or []
    effective_date = _parse_date(extracted_data.get("effective_date"))
    expiration_date = _parse_date(extracted_data.get("expiration_date"))

    if committed_periods:
        # Explicit periods from extraction: ["2026-01", "2026-02", ...]
        periods = []
        for p in committed_periods:
            try:
                periods.append(date.fromisoformat(f"{p[:7]}-01"))
            except (ValueError, TypeError):
                continue
    elif effective_date and expiration_date:
        periods = _generate_periods(effective_date, expiration_date, payment_frequency)
    elif effective_date:
        # Cannot reliably generate periods without an expiration date
        logger.warning(
            "[CONTRACT_PNL] Only effective_date found for doc %s — "
            "no expiration_date to determine period range",
            document_id,
        )
        return {
            "success": False,
            "rows_written": 0,
            "error": "effective_date found but no expiration_date — cannot determine period range",
        }
    else:
        # No dates at all — cannot reliably generate P&L periods
        logger.warning(
            "[CONTRACT_PNL] No dates found for doc %s — cannot generate periods",
            document_id,
        )
        return {
            "success": False,
            "rows_written": 0,
            "error": "no effective_date or committed_periods in extracted data",
        }

    if not periods:
        return {"success": False, "rows_written": 0, "error": "no periods generated"}

    # Calculate per-period amount
    if payment_frequency == "quarterly":
        period_amount = annual_value / 4
    elif payment_frequency == "annual":
        period_amount = annual_value
    else:
        period_amount = monthly_amount

    # Build hierarchy path
    hierarchy_path = erp.get("hierarchy_path") or (
        f"{category}/{subcategory}" if subcategory else category
    )

    source = f"document:{document_id}"

    # Build fpa_actuals rows
    rows = []
    for period in periods:
        rows.append({
            "company_id": company_id,
            "fund_id": fund_id,
            "period": period.isoformat(),
            "category": category,
            "subcategory": subcategory,
            "hierarchy_path": hierarchy_path,
            "amount": round(period_amount, 2),
            "currency": currency,
            "source": source,
        })

    # Write to DB
    sb = _get_supabase_client()
    if not sb:
        logger.warning("[CONTRACT_PNL] Supabase unavailable")
        return {"success": False, "rows_written": 0, "error": "db unavailable"}

    try:
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            sb.table("fpa_actuals").upsert(
                chunk,
                on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
            ).execute()

        logger.info(
            "[CONTRACT_PNL] Wrote %d fpa_actuals rows for doc %s (%s/%s, $%.0f/period)",
            len(rows), document_id, category, subcategory, period_amount,
        )
        return {
            "success": True,
            "rows_written": len(rows),
            "details": {
                "category": category,
                "subcategory": subcategory,
                "hierarchy_path": hierarchy_path,
                "period_amount": round(period_amount, 2),
                "annual_value": round(annual_value, 2),
                "periods": [p.isoformat()[:7] for p in periods],
                "source": source,
                "document_name": document_name,
            },
        }
    except Exception as e:
        logger.error("[CONTRACT_PNL] fpa_actuals write failed for %s: %s", document_id, e)
        return {"success": False, "rows_written": 0, "error": str(e)}


def bridge_contract_to_tp(
    extracted_data: Dict[str, Any],
    company_id: str,
    document_id: str,
    document_name: str = "",
) -> Dict[str, Any]:
    """Convert intercompany agreement clauses into ic_transaction_suggestions.

    The TP engine picks these up for benchmarking.
    Returns {"success": bool, "suggestions_written": int}.
    """
    if not extracted_data or not company_id:
        return {"success": False, "suggestions_written": 0, "error": "missing data"}

    erp = extracted_data.get("erp_attribution") or {}
    parties = extracted_data.get("parties") or []
    clauses = extracted_data.get("clauses") or []

    # Try to determine transaction type from clauses
    transaction_type = _infer_tp_transaction_type(clauses, extracted_data)

    # Build description from summary + key clauses
    summary = extracted_data.get("summary") or document_name
    description = summary[:500]

    # Annual value
    annual_value = erp.get("annual_value")

    # Try to extract pricing method from clauses
    pricing_method = _extract_pricing_method(clauses)
    pricing_basis = _extract_pricing_basis(clauses)

    # Dates
    effective_date = _parse_date(extracted_data.get("effective_date"))
    expiration_date = _parse_date(extracted_data.get("expiration_date"))

    # Currency: prefer explicit extraction, then ERP, then document-level
    currency = (
        erp.get("currency")
        or extracted_data.get("currency")
        or "USD"
    )

    suggestion = {
        "company_id": company_id,
        "transaction_type": transaction_type,
        "description": description,
        "annual_value": annual_value,
        "currency": currency,
        "source": "document_extracted",
        "source_detail": {
            "document_id": document_id,
            "document_name": document_name,
            "parties": parties,
            "pricing_method": pricing_method,
            "pricing_basis": pricing_basis,
            "effective_date": effective_date.isoformat() if effective_date else None,
            "expiration_date": expiration_date.isoformat() if expiration_date else None,
        },
        "status": "pending",
    }

    sb = _get_supabase_client()
    if not sb:
        return {"success": False, "suggestions_written": 0, "error": "db unavailable"}

    try:
        sb.table("ic_transaction_suggestions").insert(suggestion).execute()
        logger.info(
            "[CONTRACT_TP] Created IC transaction suggestion for doc %s (%s, $%s)",
            document_id, transaction_type, annual_value,
        )
        return {"success": True, "suggestions_written": 1, "transaction_type": transaction_type}
    except Exception as e:
        logger.error("[CONTRACT_TP] IC suggestion write failed for %s: %s", document_id, e)
        return {"success": False, "suggestions_written": 0, "error": str(e)}


def _infer_tp_transaction_type(clauses: List[Dict], extracted_data: Dict) -> str:
    """Infer intercompany transaction type from clause types."""
    clause_types = {c.get("clause_type", "") for c in clauses if isinstance(c, dict)}

    if "ip_assignment" in clause_types or "ip_license" in clause_types:
        return "ip_licensing"
    if "intercompany_pricing" in clause_types:
        erp_cat = (extracted_data.get("erp_attribution") or {}).get("category", "")
        if erp_cat == "cogs":
            return "goods"
        return "services"

    doc_type = (extracted_data.get("document_type") or "").lower()
    if "management" in doc_type:
        return "services"
    if "license" in doc_type or "ip" in doc_type:
        return "ip_licensing"
    if "loan" in doc_type or "financ" in doc_type:
        return "financing"

    return "services"


def _extract_pricing_method(clauses: List[Dict]) -> Optional[str]:
    """Extract pricing method from intercompany pricing clauses."""
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        if clause.get("clause_type") == "intercompany_pricing":
            text = (clause.get("text") or "").lower()
            if "cost plus" in text or "cost-plus" in text:
                return "cost_plus"
            if "royalty" in text:
                return "royalty"
            if "fixed fee" in text or "fixed-fee" in text:
                return "fixed_fee"
            if "arm" in text and "length" in text:
                return "arm_length"
    return None


def _extract_pricing_basis(clauses: List[Dict]) -> Optional[str]:
    """Extract pricing basis from clauses."""
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        if clause.get("clause_type") in ("intercompany_pricing", "payment_terms"):
            text = (clause.get("text") or "").lower()
            if "cost plus" in text or "cost-plus" in text or "markup" in text:
                return "cost_plus"
            if "% of revenue" in text or "percentage of revenue" in text:
                return "percentage_of_revenue"
            if "fixed" in text:
                return "fixed_fee"
            if "per unit" in text or "per-unit" in text:
                return "unit_price"
    return None


# ---------------------------------------------------------------------------
# Query helpers — used by agent tools for contract attribution & lifecycle
# ---------------------------------------------------------------------------

# P&L side labels for human-readable output
_SIDE_LABEL = {
    "revenue": "revenue",
    "cogs": "cost",
    "opex_rd": "cost",
    "opex_sm": "cost",
    "opex_ga": "cost",
}


def query_contract_attribution(
    company_id: str,
    fund_id: Optional[str] = None,
    category: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Show which contracts drive each P&L line — both revenue and cost side.

    Returns per-contract P&L breakdown with lifecycle metadata from
    processed_documents, plus a by_category summary.
    """
    sb = _get_supabase_client()
    if not sb:
        return {"error": "db unavailable"}

    # 1. Pull contract-attributed actuals
    q = (
        sb.table("fpa_actuals")
        .select("period, category, subcategory, hierarchy_path, amount, source")
        .eq("company_id", company_id)
        .like("source", "document:%")
    )
    if fund_id:
        q = q.eq("fund_id", fund_id)
    if category:
        q = q.eq("category", category)
    if period_start:
        q = q.gte("period", f"{period_start}-01")
    if period_end:
        q = q.lte("period", f"{period_end}-01")

    result = q.order("period").execute()
    if not result.data:
        return {"contracts": [], "by_category": {}}

    # 2. Group by source (contract) → category/subcategory
    from collections import defaultdict

    by_source: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    cat_totals: Dict[str, float] = defaultdict(float)
    cat_contract_totals: Dict[str, float] = defaultdict(float)

    for row in result.data:
        source = row["source"]
        cat = row["category"]
        sub = row.get("subcategory") or ""
        hp = row.get("hierarchy_path") or (f"{cat}/{sub}" if sub else cat)
        amount = float(row["amount"])

        by_source[source][hp] = by_source[source].get(hp, 0) + amount
        cat_contract_totals[cat] += amount

    # 3. Get total actuals per category (including non-contract) for % calc
    total_q = (
        sb.table("fpa_actuals")
        .select("category, amount")
        .eq("company_id", company_id)
    )
    if period_start:
        total_q = total_q.gte("period", f"{period_start}-01")
    if period_end:
        total_q = total_q.lte("period", f"{period_end}-01")
    total_result = total_q.execute()
    for row in (total_result.data or []):
        cat_totals[row["category"]] += float(row["amount"])

    # 4. Fetch document metadata for lifecycle info
    doc_ids = [s.replace("document:", "") for s in by_source.keys()]
    doc_meta: Dict[str, Dict] = {}
    if doc_ids:
        docs_result = (
            sb.table("processed_documents")
            .select("id, document_name, extracted_data")
            .in_("id", doc_ids)
            .execute()
        )
        for doc in (docs_result.data or []):
            ext = doc.get("extracted_data") or {}
            doc_meta[doc["id"]] = {
                "document_name": doc.get("document_name", ""),
                "expiration_date": ext.get("expiration_date"),
                "effective_date": ext.get("effective_date"),
                "auto_renewal": ext.get("auto_renewal"),
                "notice_days": ext.get("notice_days"),
                "contract_type": ext.get("document_type") or ext.get("contract_type"),
            }

    # 5. Also pull clauses for richer lifecycle data
    clause_meta: Dict[str, List[Dict]] = defaultdict(list)
    if doc_ids:
        clauses_result = (
            sb.table("document_clauses")
            .select("document_id, clause_type, extracted_value")
            .in_("document_id", doc_ids)
            .in_("clause_type", [
                "auto_renewal", "termination", "minimum_commitment",
                "break_clause", "notice_period", "renewal",
                "price_escalation", "volume_discount",
            ])
            .execute()
        )
        for c in (clauses_result.data or []):
            clause_meta[c["document_id"]].append({
                "type": c["clause_type"],
                "value": c.get("extracted_value"),
            })

    # 6. Build output
    contracts = []
    for source, pnl_map in by_source.items():
        doc_id = source.replace("document:", "")
        meta = doc_meta.get(doc_id, {})
        annual_total = sum(pnl_map.values())

        # Determine P&L side from the categories this contract touches
        categories_touched = set()
        for hp in pnl_map.keys():
            root = hp.split("/")[0].split(":")[0]
            categories_touched.add(root)

        side = "revenue" if "revenue" in categories_touched else "cost"

        contracts.append({
            "document_id": doc_id,
            "document_name": meta.get("document_name", ""),
            "contract_type": meta.get("contract_type"),
            "side": side,
            "expiration_date": meta.get("expiration_date"),
            "effective_date": meta.get("effective_date"),
            "auto_renewal": meta.get("auto_renewal"),
            "notice_days": meta.get("notice_days"),
            "clauses": clause_meta.get(doc_id, []),
            "pnl_impact": {k: round(v, 2) for k, v in pnl_map.items()},
            "total_annual": round(annual_total, 2),
        })

    # Sort: revenue contracts first, then by total descending
    contracts.sort(key=lambda c: (0 if c["side"] == "revenue" else 1, -abs(c["total_annual"])))

    by_category = {}
    for cat in set(list(cat_totals.keys()) + list(cat_contract_totals.keys())):
        total = cat_totals.get(cat, 0)
        contracted = cat_contract_totals.get(cat, 0)
        by_category[cat] = {
            "contract_attributed": round(contracted, 2),
            "total": round(total, 2),
            "pct": round(contracted / total, 4) if total else 0,
            "side": _SIDE_LABEL.get(cat, "cost"),
        }

    return {"contracts": contracts, "by_category": by_category}


def query_contract_lifecycle(
    company_id: str,
    fund_id: Optional[str] = None,
    expiring_before: Optional[str] = None,
    expiring_after: Optional[str] = None,
    auto_renewal_only: bool = False,
    side: Optional[str] = None,
    clause_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Query contracts by lifecycle attributes — expiration, renewal, break clauses.

    Works for both revenue contracts (sales, SaaS, services) and cost contracts
    (vendors, leases, software). Filter by side='revenue' or side='cost'.

    Returns contracts with lifecycle metadata + P&L exposure.
    """
    sb = _get_supabase_client()
    if not sb:
        return {"error": "db unavailable"}

    # 1. Get distinct document sources from fpa_actuals
    q = (
        sb.table("fpa_actuals")
        .select("source, category, amount")
        .eq("company_id", company_id)
        .like("source", "document:%")
    )
    if fund_id:
        q = q.eq("fund_id", fund_id)

    result = q.execute()
    if not result.data:
        return {"contracts": [], "summary": {}}

    # Aggregate by source
    from collections import defaultdict

    source_totals: Dict[str, float] = defaultdict(float)
    source_categories: Dict[str, set] = defaultdict(set)
    for row in result.data:
        src = row["source"]
        source_totals[src] += float(row["amount"])
        source_categories[src].add(row["category"])

    doc_ids = [s.replace("document:", "") for s in source_totals.keys()]

    # 2. Fetch document metadata
    docs_result = (
        sb.table("processed_documents")
        .select("id, document_name, extracted_data")
        .in_("id", doc_ids)
        .execute()
    )
    doc_meta: Dict[str, Dict] = {}
    for doc in (docs_result.data or []):
        ext = doc.get("extracted_data") or {}
        doc_meta[doc["id"]] = {
            "document_name": doc.get("document_name", ""),
            "expiration_date": ext.get("expiration_date"),
            "effective_date": ext.get("effective_date"),
            "auto_renewal": ext.get("auto_renewal"),
            "notice_days": ext.get("notice_days"),
            "contract_type": ext.get("document_type") or ext.get("contract_type"),
        }

    # 3. Fetch clauses
    clause_meta: Dict[str, List[Dict]] = defaultdict(list)
    clause_q = (
        sb.table("document_clauses")
        .select("document_id, clause_type, extracted_value")
        .in_("document_id", doc_ids)
    )
    if clause_type:
        clause_q = clause_q.eq("clause_type", clause_type)
    clauses_result = clause_q.execute()
    for c in (clauses_result.data or []):
        clause_meta[c["document_id"]].append({
            "type": c["clause_type"],
            "value": c.get("extracted_value"),
        })

    # 4. Filter and build output
    contracts = []
    for source, total in source_totals.items():
        doc_id = source.replace("document:", "")
        meta = doc_meta.get(doc_id, {})
        cats = source_categories.get(source, set())

        # Determine side
        contract_side = "revenue" if "revenue" in cats else "cost"
        if side and contract_side != side:
            continue

        # Filter by expiration
        exp = meta.get("expiration_date")
        if expiring_before and (not exp or exp > expiring_before):
            continue
        if expiring_after and (not exp or exp < expiring_after):
            continue

        # Filter by auto-renewal
        if auto_renewal_only and not meta.get("auto_renewal"):
            continue

        # Filter by clause type (already filtered in query, but skip if no matching clauses)
        if clause_type and doc_id not in clause_meta:
            continue

        contracts.append({
            "document_id": doc_id,
            "document_name": meta.get("document_name", ""),
            "contract_type": meta.get("contract_type"),
            "side": contract_side,
            "categories": sorted(cats),
            "expiration_date": exp,
            "effective_date": meta.get("effective_date"),
            "auto_renewal": meta.get("auto_renewal"),
            "notice_days": meta.get("notice_days"),
            "clauses": clause_meta.get(doc_id, []),
            "total_pnl_exposure": round(total, 2),
        })

    # Sort by expiration date (soonest first), nulls last
    contracts.sort(key=lambda c: (c["expiration_date"] or "9999", -abs(c["total_pnl_exposure"])))

    # Summary
    revenue_exposure = sum(c["total_pnl_exposure"] for c in contracts if c["side"] == "revenue")
    cost_exposure = sum(c["total_pnl_exposure"] for c in contracts if c["side"] == "cost")
    expiring_soon = [c for c in contracts if c["expiration_date"] and c["expiration_date"] <= _quarter_ahead()]
    auto_renewing = [c for c in contracts if c.get("auto_renewal")]

    return {
        "contracts": contracts,
        "summary": {
            "total_contracts": len(contracts),
            "revenue_contracts": len([c for c in contracts if c["side"] == "revenue"]),
            "cost_contracts": len([c for c in contracts if c["side"] == "cost"]),
            "total_revenue_exposure": round(revenue_exposure, 2),
            "total_cost_exposure": round(cost_exposure, 2),
            "expiring_next_quarter": len(expiring_soon),
            "auto_renewing": len(auto_renewing),
        },
    }


def _quarter_ahead() -> str:
    """Return date string ~90 days from now."""
    return (date.today() + timedelta(days=90)).isoformat()
