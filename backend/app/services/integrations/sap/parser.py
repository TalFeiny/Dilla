"""SAP data parsers for S/4HANA Cloud and Business One.

Converts raw SAP API responses into FpaRow objects that flow into the
fpa_actuals table.  No separate SAP-specific tables — everything normalizes
through FpaRow.

Two parse paths:
1. S/4HANA trial balance → parse_s4_trial_balance()
2. B1 journal entries + chart of accounts → parse_b1_journal_entries()
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from app.services.integrations.base import FpaRow
from app.services.actuals_ingestion import classify_label_to_subcategory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SAP account type → Dilla FPA category mapping
# ---------------------------------------------------------------------------

SAP_ACCOUNT_TYPE_MAP: Dict[str, str] = {
    # S/4HANA — GLAccountType
    "P": "revenue",
    "X": "opex_total",
    "S": "bs_other_equity",
    "A": "bs_other_ca",
    "L": "bs_other_cl",
    # B1 Account Types (AcctType enum values)
    "it_Revenue": "revenue",
    "it_Expenditure": "opex_total",
    "it_FixedAssets": "bs_ppe",
    "it_CashAndBank": "bs_cash",
    "it_AccountsReceivable": "bs_ar",
    "it_AccountsPayable": "bs_ap",
}


def _fiscal_period_to_iso(fiscal_year: int, fiscal_period: int) -> str:
    """Convert fiscal year + period to ISO period string 'YYYY-MM-01'.

    Assumes standard calendar-aligned fiscal periods (period 1 = January).
    Clamps to 1-12 range.
    """
    month = max(1, min(12, fiscal_period))
    return f"{fiscal_year}-{str(month).zfill(2)}-01"


def _safe_float(value) -> float:
    """Safely convert a value to float, returning 0.0 on failure."""
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════
# S/4HANA Cloud: Trial Balance → FpaRow
# ═══════════════════════════════════════════════════════════════════════════

def parse_s4_trial_balance(
    rows: List[Dict],
    company_id: str,
    fiscal_year: int,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Convert S/4HANA trial balance rows to FpaRow objects.

    Each row in the trial balance CDS view contains:
        GLAccount, GLAccountName, GLAccountType,
        CompanyCode, FiscalYear, FiscalPeriod,
        StartingBalanceAmtInCoCodeCrcy,
        DebitAmountInCoCodeCrcy,
        CreditAmountInCoCodeCrcy,
        EndingBalanceAmtInCoCodeCrcy,
        ProfitCenter, CostCenter

    Mapping logic:
    - Amount: EndingBalanceAmtInCoCodeCrcy
    - Period: FiscalYear + FiscalPeriod -> "YYYY-MM-01"
    - Category: GLAccountType via SAP_ACCOUNT_TYPE_MAP
    - Subcategory: classify_label_to_subcategory(GLAccountName)
    """
    if not rows:
        return []

    results: List[FpaRow] = []

    for row in rows:
        gl_account = row.get("GLAccount", "")
        gl_name = row.get("GLAccountName", "") or gl_account
        gl_type = row.get("GLAccountType", "")

        # Amount — use ending balance in company code currency
        amount = _safe_float(row.get("EndingBalanceAmtInCoCodeCrcy"))
        if amount == 0:
            continue

        # Period
        fy = row.get("FiscalYear", fiscal_year)
        fp = row.get("FiscalPeriod", 1)
        try:
            fy = int(fy)
            fp = int(fp)
        except (ValueError, TypeError):
            fy = fiscal_year
            fp = 1
        period = _fiscal_period_to_iso(fy, fp)

        # Category from GL account type
        category = SAP_ACCOUNT_TYPE_MAP.get(gl_type, "opex_total")

        # Subcategory from account name classification
        classified_cat, subcategory = classify_label_to_subcategory(gl_name)
        if classified_cat:
            category = classified_cat
        if not subcategory:
            subcategory = gl_name.lower().replace(" ", "_").replace("-", "_")

        # Hierarchy path — include profit/cost center if available
        profit_center = row.get("ProfitCenter", "")
        cost_center = row.get("CostCenter", "")
        hierarchy_parts = [category]
        if profit_center:
            hierarchy_parts.append(f"pc:{profit_center}")
        if cost_center:
            hierarchy_parts.append(f"cc:{cost_center}")
        hierarchy_parts.append(subcategory)
        hierarchy_path = "/".join(hierarchy_parts)

        results.append(FpaRow(
            company_id=company_id,
            period=period,
            category=category,
            subcategory=subcategory,
            amount=amount,
            source="sap_s4hana",
            fund_id=fund_id,
            hierarchy_path=hierarchy_path,
        ))

    logger.info(
        "Parsed %d FpaRow objects from %d S/4 trial balance rows",
        len(results), len(rows),
    )
    return results


# ═══════════════════════════════════════════════════════════════════════════
# SAP Business One: Journal Entries + COA → FpaRow
# ═══════════════════════════════════════════════════════════════════════════

def parse_b1_journal_entries(
    entries: List[Dict],
    coa: List[Dict],
    company_id: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Convert B1 journal entries + chart of accounts to FpaRow objects.

    Steps:
    1. Build account type lookup from COA (AcctCode -> AcctType, AcctName).
    2. Walk journal entry lines, summing debits/credits per account per month.
    3. Map each account to FPA category via SAP_ACCOUNT_TYPE_MAP.
    4. Classify subcategory via classify_label_to_subcategory(AcctName).

    Args:
        entries: Raw journal entries from SAPB1Client.get_journal_entries().
            Each entry has ReferenceDate and JournalEntryLines array.
        coa: Raw chart of accounts from SAPB1Client.get_chart_of_accounts().
        company_id: Dilla company ID.
        fund_id: Optional fund ID.
    """
    if not entries:
        return []

    # Step 1: Build account lookup from chart of accounts
    #   AcctCode -> {"name": AcctName, "type": AcctType}
    acct_lookup: Dict[str, Dict[str, str]] = {}
    for account in coa:
        code = str(account.get("AcctCode", ""))
        acct_lookup[code] = {
            "name": account.get("AcctName", code),
            "type": account.get("AcctType", ""),
        }

    # Step 2: Aggregate amounts per account per month
    #   Key: (account_code, "YYYY-MM-01") -> net amount (debit - credit)
    monthly_totals: Dict[tuple, float] = defaultdict(float)

    for entry in entries:
        ref_date = entry.get("ReferenceDate", "")
        if not ref_date or len(ref_date) < 7:
            continue

        # Normalize to "YYYY-MM-01"
        period = ref_date[:7] + "-01"

        lines = entry.get("JournalEntryLines", [])
        for line in lines:
            acct_code = str(line.get("AccountCode", ""))
            if not acct_code:
                continue

            debit = _safe_float(line.get("Debit"))
            credit = _safe_float(line.get("Credit"))
            net = debit - credit

            if net != 0:
                monthly_totals[(acct_code, period)] += net

    # Step 3: Convert aggregated totals to FpaRow objects
    results: List[FpaRow] = []

    for (acct_code, period), amount in monthly_totals.items():
        if amount == 0:
            continue

        acct_info = acct_lookup.get(acct_code, {"name": acct_code, "type": ""})
        acct_name = acct_info["name"]
        acct_type = acct_info["type"]

        # Category from B1 account type
        category = SAP_ACCOUNT_TYPE_MAP.get(acct_type, "opex_total")

        # Subcategory from account name classification
        classified_cat, subcategory = classify_label_to_subcategory(acct_name)
        if classified_cat:
            category = classified_cat
        if not subcategory:
            subcategory = acct_name.lower().replace(" ", "_").replace("-", "_")

        hierarchy_path = f"{category}/{subcategory}"

        results.append(FpaRow(
            company_id=company_id,
            period=period,
            category=category,
            subcategory=subcategory,
            amount=amount,
            source="sap_b1",
            fund_id=fund_id,
            hierarchy_path=hierarchy_path,
        ))

    logger.info(
        "Parsed %d FpaRow objects from %d B1 journal entries (%d unique account-periods)",
        len(results), len(entries), len(monthly_totals),
    )
    return results
