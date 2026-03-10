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
