"""Shared ERP → fpa_actuals normalizer.

Converts raw account-level rows from any provider into fpa_actuals-shaped
dicts, using a cascade of mapping strategies:
1. User-overridden mappings (erp_account_mappings table)
2. Provider account_type → category mapping
3. Keyword matching via actuals_ingestion.classify_label_to_subcategory()
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.integrations.base import FpaRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider-specific account type → Dilla category maps
# ---------------------------------------------------------------------------

QBO_ACCOUNT_TYPE_MAP = {
    # P&L
    "Income": "revenue",
    "Other Income": "revenue",
    "Cost of Goods Sold": "cogs",
    "Expense": "opex_total",
    "Other Expense": "opex_ga",
    # Balance Sheet
    "Bank": "bs_cash",
    "Accounts Receivable": "bs_ar",
    "Other Current Asset": "bs_other_ca",
    "Fixed Asset": "bs_ppe",
    "Other Asset": "bs_other_nca",
    "Accounts Payable": "bs_ap",
    "Credit Card": "bs_other_cl",
    "Other Current Liability": "bs_other_cl",
    "Long Term Liability": "bs_other_ncl",
    "Equity": "bs_other_equity",
}

NETSUITE_ACCOUNT_TYPE_MAP = {
    # P&L
    "Income": "revenue",
    "OthIncome": "revenue",
    "COGS": "cogs",
    "Expense": "opex_total",
    "OthExpense": "opex_ga",
    # Balance Sheet
    "Bank": "bs_cash",
    "AcctRec": "bs_ar",
    "OthCurrAsset": "bs_other_ca",
    "FixedAsset": "bs_ppe",
    "OthAsset": "bs_other_nca",
    "AcctPay": "bs_ap",
    "OthCurrLiab": "bs_other_cl",
    "LongTermLiab": "bs_other_ncl",
    "Equity": "bs_other_equity",
}

XERO_ACCOUNT_TYPE_MAP = {
    "REVENUE": "revenue",
    "OTHERINCOME": "revenue",
    "DIRECTCOSTS": "cogs",
    "EXPENSE": "opex_total",
    "OVERHEADS": "opex_ga",
    "BANK": "bs_cash",
    "CURRENT": "bs_other_ca",
    "CURRLIAB": "bs_other_cl",
    "FIXED": "bs_ppe",
    "EQUITY": "bs_other_equity",
    "NONCURRENT": "bs_other_nca",
    "TERMLIAB": "bs_other_ncl",
}

PROVIDER_TYPE_MAPS = {
    "quickbooks": QBO_ACCOUNT_TYPE_MAP,
    "netsuite": NETSUITE_ACCOUNT_TYPE_MAP,
    "xero": XERO_ACCOUNT_TYPE_MAP,
}


def normalize_period(period_str: str) -> Optional[str]:
    """Convert various period formats to 'YYYY-MM-01'.

    Handles: '2025-01', '2025-01-01', 'Jan 2025', 'January 2025', '1 Jan 2025', 'Q1 2025'
    """
    if not period_str:
        return None

    period_str = period_str.strip()

    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", period_str):
        return period_str[:7] + "-01"
    if re.match(r"^\d{4}-\d{2}$", period_str):
        return period_str + "-01"

    # Quarter format: Q1 2025 → 2025-01-01
    q_match = re.match(r"^Q([1-4])\s*(\d{4})$", period_str, re.IGNORECASE)
    if q_match:
        q, year = int(q_match.group(1)), q_match.group(2)
        month = (q - 1) * 3 + 1
        return f"{year}-{month:02d}-01"

    # Month name formats
    for fmt in ("%b %Y", "%B %Y", "%d %b %Y", "%d %B %Y"):
        try:
            parsed = datetime.strptime(period_str, fmt)
            return parsed.strftime("%Y-%m-01")
        except ValueError:
            continue

    logger.warning("Could not parse period: %s", period_str)
    return None


def map_account_to_category(
    account_name: str,
    account_type: str,
    provider: str,
    account_mappings: Optional[Dict[str, Dict[str, str]]] = None,
) -> tuple:
    """Map an ERP account to (category, subcategory).

    Returns: (category, subcategory) — subcategory may be empty string.
    """
    # 1. Check user-overridden mappings
    if account_mappings:
        override = account_mappings.get(account_name) or account_mappings.get(account_type)
        if override:
            return (override.get("category", ""), override.get("subcategory", ""))

    # 2. Provider account_type → category
    type_map = PROVIDER_TYPE_MAPS.get(provider, {})
    category = type_map.get(account_type, "")

    # 3. Try keyword matching for subcategory
    subcategory = ""
    if category:
        try:
            from app.services.actuals_ingestion import classify_label_to_subcategory
            matched_cat, matched_sub = classify_label_to_subcategory(account_name)
            if matched_sub:
                subcategory = matched_sub
                # If keyword match gives a more specific category, prefer it
                if matched_cat and matched_cat != category and category == "opex_total":
                    category = matched_cat
        except ImportError:
            pass

    return (category, subcategory)


def normalize_to_fpa_rows(
    raw_rows: List[Dict[str, Any]],
    company_id: str,
    source: str,
    fund_id: Optional[str] = None,
    account_mappings: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[FpaRow]:
    """Convert raw ERP rows to FpaRow objects.

    Each raw_row should have: {account_name, account_type, period, amount}
    Optional: {account_code}
    """
    results: List[FpaRow] = []

    for row in raw_rows:
        account_name = row.get("account_name", "")
        account_type = row.get("account_type", "")
        period_raw = row.get("period", "")
        amount = row.get("amount")

        if amount is None:
            continue

        try:
            amount = float(str(amount).replace(",", ""))
        except (ValueError, TypeError):
            continue

        if amount == 0:
            continue

        period = normalize_period(period_raw)
        if not period:
            continue

        category, subcategory = map_account_to_category(
            account_name, account_type, source, account_mappings
        )

        if not category:
            logger.debug("No category mapping for %s (type=%s, provider=%s)", account_name, account_type, source)
            continue

        results.append(FpaRow(
            company_id=company_id,
            period=period,
            category=category,
            subcategory=subcategory or account_name.lower().replace(" ", "_"),
            amount=amount,
            source=source,
            fund_id=fund_id,
            hierarchy_path=f"{category}/{account_name.lower().replace(' ', '_')}" if subcategory else category,
        ))

    return results


def compute_ebitda_rows(
    rows: List[FpaRow],
    company_id: str,
    source: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Compute EBITDA per period from P&L rows and return additional rows."""
    period_totals: Dict[str, Dict[str, float]] = {}

    for row in rows:
        if row.category not in ("revenue", "cogs", "opex_total", "opex_rd", "opex_sm", "opex_ga"):
            continue
        if row.period not in period_totals:
            period_totals[row.period] = {"revenue": 0, "cogs": 0, "opex": 0}

        if row.category == "revenue":
            period_totals[row.period]["revenue"] += row.amount
        elif row.category == "cogs":
            period_totals[row.period]["cogs"] += row.amount
        else:
            period_totals[row.period]["opex"] += row.amount

    ebitda_rows = []
    for period, totals in period_totals.items():
        ebitda = totals["revenue"] - totals["cogs"] - totals["opex"]
        ebitda_rows.append(FpaRow(
            company_id=company_id,
            period=period,
            category="ebitda",
            subcategory="",
            amount=ebitda,
            source=source,
            fund_id=fund_id,
        ))

    return ebitda_rows
