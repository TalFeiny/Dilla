"""NetSuite data parser.

Converts SuiteQL query results into normalized FpaRow objects.
NetSuite returns flat rows (not nested report structures like QBO/Xero),
so parsing is straightforward.
"""

import logging
from typing import Dict, List, Optional

from app.services.integrations.base import FpaRow
from app.services.integrations.report_normalizer import normalize_period

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NetSuite account type → Dilla category
# ---------------------------------------------------------------------------
NS_ACCOUNT_TYPE_MAP = {
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


def _subcategorize_opex(account_name: str) -> tuple:
    """Try to break 'Expense' into opex_rd / opex_sm / opex_ga based on name."""
    name_lower = account_name.lower()

    # R&D indicators
    rd_keywords = [
        "engineering", "developer", "research", "software", "tech",
        "cloud", "hosting", "infrastructure", "devops", "r&d",
    ]
    if any(kw in name_lower for kw in rd_keywords):
        return ("opex_rd", account_name.lower().replace(" ", "_"))

    # Sales & Marketing indicators
    sm_keywords = [
        "marketing", "advertising", "sales", "promotion", "events",
        "trade show", "sponsorship", "commission", "business dev",
    ]
    if any(kw in name_lower for kw in sm_keywords):
        return ("opex_sm", account_name.lower().replace(" ", "_"))

    # Everything else → G&A
    return ("opex_ga", account_name.lower().replace(" ", "_"))


def parse_profit_and_loss(
    suiteql_rows: List[Dict],
    company_id: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Parse SuiteQL P&L results into FpaRow objects.

    Expected row format from SuiteQL:
    {
        "account_code": "4000",
        "account_name": "Product Revenue",
        "account_type": "Income",
        "period": "2025-01",
        "amount": 150000.00
    }
    """
    results: List[FpaRow] = []

    for row in suiteql_rows:
        account_name = row.get("account_name", "")
        account_type = row.get("account_type", "")
        period_raw = row.get("period", "")
        amount = row.get("amount")

        if amount is None:
            continue
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            continue
        if amount == 0:
            continue

        period = normalize_period(period_raw)
        if not period:
            continue

        category = NS_ACCOUNT_TYPE_MAP.get(account_type, "")
        if not category:
            logger.debug("Unmapped NetSuite account type: %s (%s)", account_type, account_name)
            continue

        subcategory = account_name.lower().replace(" ", "_")

        # Break opex_total into opex_rd / opex_sm / opex_ga
        if category == "opex_total":
            category, subcategory = _subcategorize_opex(account_name)

        results.append(FpaRow(
            company_id=company_id,
            period=period,
            category=category,
            subcategory=subcategory,
            amount=amount,
            source="netsuite",
            fund_id=fund_id,
            hierarchy_path=f"{category}/{subcategory}",
        ))

    return results


def parse_balance_sheet(
    suiteql_rows: List[Dict],
    company_id: str,
    as_of_date: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Parse SuiteQL Balance Sheet results into FpaRow objects.

    Expected row format:
    {
        "account_code": "1000",
        "account_name": "Checking Account",
        "account_type": "Bank",
        "balance": 500000.00
    }
    """
    period = normalize_period(as_of_date)
    if not period:
        logger.warning("Cannot parse BS date: %s", as_of_date)
        return []

    results: List[FpaRow] = []

    for row in suiteql_rows:
        account_name = row.get("account_name", "")
        account_type = row.get("account_type", "")
        balance = row.get("balance")

        if balance is None:
            continue
        try:
            balance = float(balance)
        except (ValueError, TypeError):
            continue
        if balance == 0:
            continue

        category = NS_ACCOUNT_TYPE_MAP.get(account_type, "")
        if not category:
            continue

        subcategory = account_name.lower().replace(" ", "_")

        results.append(FpaRow(
            company_id=company_id,
            period=period,
            category=category,
            subcategory=subcategory,
            amount=balance,
            source="netsuite",
            fund_id=fund_id,
            hierarchy_path=f"{category}/{subcategory}",
        ))

    return results
