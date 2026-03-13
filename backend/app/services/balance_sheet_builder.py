"""
Dynamic Balance Sheet builder.

Discovers line items from real fpa_actuals data (bs_* categories),
assembles hierarchical rows with computed totals and balance checks.

Mirrors PnlBuilder pattern — reuses fpa_actuals table with bs_ prefix.
Supports full chart of accounts: current/non-current assets, current/non-current
liabilities, equity, with debtors, creditors, interest, deferred items, leases,
provisions, OCI, minority interest, etc.

ERP-compatible: maps Xero/QBO/NetSuite/SAP account names to canonical categories.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section ordering — controls how rows are grouped in the waterfall
# ---------------------------------------------------------------------------

BS_SECTION_ORDER = [
    "current_assets",
    "non_current_assets",
    "total_assets",
    "current_liabilities",
    "non_current_liabilities",
    "total_liabilities",
    "equity",
    "total_liabilities_equity",
    "balance_check",
]

BS_SECTION_LABELS = {
    "current_assets": "Current Assets",
    "non_current_assets": "Non-Current Assets",
    "total_assets": "Total Assets",
    "current_liabilities": "Current Liabilities",
    "non_current_liabilities": "Non-Current Liabilities",
    "total_liabilities": "Total Liabilities",
    "equity": "Equity",
    "total_liabilities_equity": "Total Liabilities & Equity",
    "balance_check": "Balance Check",
}

# ---------------------------------------------------------------------------
# Category → section mapping
# ---------------------------------------------------------------------------

BS_CATEGORY_SECTION = {
    # Current Assets
    "bs_cash": "current_assets",
    "bs_receivables": "current_assets",
    "bs_other_receivables": "current_assets",
    "bs_prepayments": "current_assets",
    "bs_inventory": "current_assets",
    "bs_st_investments": "current_assets",
    "bs_tax_receivable": "current_assets",
    "bs_other_ca": "current_assets",
    # Non-Current Assets
    "bs_ppe": "non_current_assets",
    "bs_intangibles": "non_current_assets",
    "bs_rou_assets": "non_current_assets",
    "bs_lt_investments": "non_current_assets",
    "bs_deferred_tax_asset": "non_current_assets",
    "bs_other_nca": "non_current_assets",
    # Current Liabilities
    "bs_payables": "current_liabilities",
    "bs_accrued_expenses": "current_liabilities",
    "bs_st_debt": "current_liabilities",
    "bs_current_ltd": "current_liabilities",
    "bs_deferred_revenue": "current_liabilities",
    "bs_tax_payable": "current_liabilities",
    "bs_interest_payable": "current_liabilities",
    "bs_dividends_payable": "current_liabilities",
    "bs_other_cl": "current_liabilities",
    # Non-Current Liabilities
    "bs_lt_debt": "non_current_liabilities",
    "bs_convertible_notes": "non_current_liabilities",
    "bs_lease_liabilities": "non_current_liabilities",
    "bs_deferred_tax_liability": "non_current_liabilities",
    "bs_provisions": "non_current_liabilities",
    "bs_pension": "non_current_liabilities",
    "bs_other_ncl": "non_current_liabilities",
    # Equity
    "bs_share_capital": "equity",
    "bs_apic": "equity",
    "bs_retained_earnings": "equity",
    "bs_current_pnl": "equity",
    "bs_oci": "equity",
    "bs_treasury_stock": "equity",
    "bs_minority_interest": "equity",
    "bs_other_equity": "equity",
}

BS_CATEGORY_LABELS = {
    # Current Assets
    "bs_cash": "Cash & Cash Equivalents",
    "bs_receivables": "Accounts Receivable (Trade Debtors)",
    "bs_other_receivables": "Other Receivables",
    "bs_prepayments": "Prepayments & Accrued Income",
    "bs_inventory": "Inventory / Stock",
    "bs_st_investments": "Short-term Investments",
    "bs_tax_receivable": "Tax Receivable",
    "bs_other_ca": "Other Current Assets",
    # Non-Current Assets
    "bs_ppe": "Property, Plant & Equipment",
    "bs_intangibles": "Intangible Assets",
    "bs_rou_assets": "Right-of-Use Assets",
    "bs_lt_investments": "Long-term Investments",
    "bs_deferred_tax_asset": "Deferred Tax Assets",
    "bs_other_nca": "Other Non-Current Assets",
    # Current Liabilities
    "bs_payables": "Accounts Payable (Trade Creditors)",
    "bs_accrued_expenses": "Accrued Expenses",
    "bs_st_debt": "Short-term Debt",
    "bs_current_ltd": "Current Portion of Long-term Debt",
    "bs_deferred_revenue": "Deferred Revenue",
    "bs_tax_payable": "Tax Payable",
    "bs_interest_payable": "Interest Payable",
    "bs_dividends_payable": "Dividends Payable",
    "bs_other_cl": "Other Current Liabilities",
    # Non-Current Liabilities
    "bs_lt_debt": "Long-term Debt",
    "bs_convertible_notes": "Convertible Notes",
    "bs_lease_liabilities": "Lease Liabilities",
    "bs_deferred_tax_liability": "Deferred Tax Liabilities",
    "bs_provisions": "Provisions",
    "bs_pension": "Pension Obligations",
    "bs_other_ncl": "Other Non-Current Liabilities",
    # Equity
    "bs_share_capital": "Share Capital / Common Stock",
    "bs_apic": "Additional Paid-in Capital",
    "bs_retained_earnings": "Retained Earnings",
    "bs_current_pnl": "Current Period P&L",
    "bs_oci": "Other Comprehensive Income",
    "bs_treasury_stock": "Treasury Stock",
    "bs_minority_interest": "Minority Interest",
    "bs_other_equity": "Other Equity",
}

# Assets sections (positive = debit balance)
ASSET_SECTIONS = {"current_assets", "non_current_assets"}
# Liability + Equity sections (positive = credit balance)
CREDIT_SECTIONS = {"current_liabilities", "non_current_liabilities", "equity"}

# Categories where negative values are normal (treasury stock, etc.)
CONTRA_CATEGORIES = {"bs_treasury_stock"}

# ---------------------------------------------------------------------------
# ERP Account Name → bs_ category mapping (fuzzy-matchable)
# ---------------------------------------------------------------------------

ERP_ACCOUNT_MAP: Dict[str, str] = {
    # Cash
    "cash": "bs_cash",
    "cash and cash equivalents": "bs_cash",
    "cash at bank": "bs_cash",
    "bank": "bs_cash",
    "bank accounts": "bs_cash",
    "petty cash": "bs_cash",
    "checking": "bs_cash",
    "savings": "bs_cash",
    # Receivables
    "accounts receivable": "bs_receivables",
    "trade debtors": "bs_receivables",
    "trade receivables": "bs_receivables",
    "debtors": "bs_receivables",
    "sundry debtors": "bs_receivables",
    "other receivables": "bs_other_receivables",
    "other debtors": "bs_other_receivables",
    "employee advances": "bs_other_receivables",
    "loans to employees": "bs_other_receivables",
    "intercompany receivable": "bs_other_receivables",
    "intercompany receivables": "bs_other_receivables",
    # Prepayments
    "prepayments": "bs_prepayments",
    "prepaid expenses": "bs_prepayments",
    "accrued income": "bs_prepayments",
    "accrued revenue": "bs_prepayments",
    # Inventory
    "inventory": "bs_inventory",
    "stock": "bs_inventory",
    "stock on hand": "bs_inventory",
    "raw materials": "bs_inventory",
    "work in progress": "bs_inventory",
    "finished goods": "bs_inventory",
    "merchandise": "bs_inventory",
    # Short-term investments
    "short-term investments": "bs_st_investments",
    "short term investments": "bs_st_investments",
    "marketable securities": "bs_st_investments",
    "current investments": "bs_st_investments",
    # Tax receivable
    "tax receivable": "bs_tax_receivable",
    "vat receivable": "bs_tax_receivable",
    "gst receivable": "bs_tax_receivable",
    "input tax": "bs_tax_receivable",
    "income tax receivable": "bs_tax_receivable",
    "corporation tax receivable": "bs_tax_receivable",
    # PP&E
    "property plant and equipment": "bs_ppe",
    "property, plant & equipment": "bs_ppe",
    "fixed assets": "bs_ppe",
    "land and buildings": "bs_ppe",
    "plant and machinery": "bs_ppe",
    "furniture and fixtures": "bs_ppe",
    "motor vehicles": "bs_ppe",
    "computer equipment": "bs_ppe",
    "office equipment": "bs_ppe",
    "leasehold improvements": "bs_ppe",
    "accumulated depreciation": "bs_ppe",
    "less accumulated depreciation": "bs_ppe",
    # Intangibles
    "intangible assets": "bs_intangibles",
    "goodwill": "bs_intangibles",
    "patents": "bs_intangibles",
    "trademarks": "bs_intangibles",
    "software": "bs_intangibles",
    "capitalised development": "bs_intangibles",
    "capitalized software": "bs_intangibles",
    "intellectual property": "bs_intangibles",
    "amortization": "bs_intangibles",
    "accumulated amortization": "bs_intangibles",
    # Right-of-use assets
    "right-of-use assets": "bs_rou_assets",
    "right of use assets": "bs_rou_assets",
    "rou assets": "bs_rou_assets",
    "operating lease assets": "bs_rou_assets",
    # Long-term investments
    "long-term investments": "bs_lt_investments",
    "long term investments": "bs_lt_investments",
    "investments in subsidiaries": "bs_lt_investments",
    "investments in associates": "bs_lt_investments",
    "equity method investments": "bs_lt_investments",
    # Deferred tax assets
    "deferred tax assets": "bs_deferred_tax_asset",
    "deferred tax asset": "bs_deferred_tax_asset",
    # Payables
    "accounts payable": "bs_payables",
    "trade creditors": "bs_payables",
    "trade payables": "bs_payables",
    "creditors": "bs_payables",
    "sundry creditors": "bs_payables",
    # Accrued expenses
    "accrued expenses": "bs_accrued_expenses",
    "accrued liabilities": "bs_accrued_expenses",
    "accruals": "bs_accrued_expenses",
    "wages payable": "bs_accrued_expenses",
    "salaries payable": "bs_accrued_expenses",
    # Short-term debt
    "short-term debt": "bs_st_debt",
    "short term debt": "bs_st_debt",
    "bank overdraft": "bs_st_debt",
    "revolving credit": "bs_st_debt",
    "line of credit": "bs_st_debt",
    "credit line": "bs_st_debt",
    "short-term borrowings": "bs_st_debt",
    # Current portion of LTD
    "current portion of long-term debt": "bs_current_ltd",
    "current portion of long term debt": "bs_current_ltd",
    "current maturities": "bs_current_ltd",
    # Deferred revenue
    "deferred revenue": "bs_deferred_revenue",
    "unearned revenue": "bs_deferred_revenue",
    "unearned income": "bs_deferred_revenue",
    "contract liabilities": "bs_deferred_revenue",
    "customer deposits": "bs_deferred_revenue",
    "prepaid revenue": "bs_deferred_revenue",
    # Tax payable
    "tax payable": "bs_tax_payable",
    "vat payable": "bs_tax_payable",
    "gst payable": "bs_tax_payable",
    "output tax": "bs_tax_payable",
    "income tax payable": "bs_tax_payable",
    "corporation tax": "bs_tax_payable",
    "payroll tax payable": "bs_tax_payable",
    "sales tax payable": "bs_tax_payable",
    # Interest payable
    "interest payable": "bs_interest_payable",
    "accrued interest": "bs_interest_payable",
    # Dividends payable
    "dividends payable": "bs_dividends_payable",
    # Long-term debt
    "long-term debt": "bs_lt_debt",
    "long term debt": "bs_lt_debt",
    "term loan": "bs_lt_debt",
    "term loans": "bs_lt_debt",
    "bonds payable": "bs_lt_debt",
    "notes payable": "bs_lt_debt",
    "mortgage": "bs_lt_debt",
    "long-term borrowings": "bs_lt_debt",
    # Convertible notes
    "convertible notes": "bs_convertible_notes",
    "convertible debt": "bs_convertible_notes",
    "convertible loan": "bs_convertible_notes",
    "safe": "bs_convertible_notes",
    "safe notes": "bs_convertible_notes",
    # Lease liabilities
    "lease liabilities": "bs_lease_liabilities",
    "lease liability": "bs_lease_liabilities",
    "finance lease": "bs_lease_liabilities",
    "operating lease liability": "bs_lease_liabilities",
    "operating lease liabilities": "bs_lease_liabilities",
    # Deferred tax liabilities
    "deferred tax liabilities": "bs_deferred_tax_liability",
    "deferred tax liability": "bs_deferred_tax_liability",
    # Provisions
    "provisions": "bs_provisions",
    "warranty provision": "bs_provisions",
    "legal provision": "bs_provisions",
    "restructuring provision": "bs_provisions",
    "contingent liabilities": "bs_provisions",
    # Pension
    "pension obligations": "bs_pension",
    "pension liability": "bs_pension",
    "retirement benefit obligations": "bs_pension",
    "post-employment benefits": "bs_pension",
    "defined benefit obligation": "bs_pension",
    # Share capital
    "share capital": "bs_share_capital",
    "common stock": "bs_share_capital",
    "ordinary shares": "bs_share_capital",
    "issued capital": "bs_share_capital",
    "paid-up capital": "bs_share_capital",
    # APIC
    "additional paid-in capital": "bs_apic",
    "share premium": "bs_apic",
    "capital surplus": "bs_apic",
    "paid-in capital in excess of par": "bs_apic",
    # Retained earnings
    "retained earnings": "bs_retained_earnings",
    "accumulated profits": "bs_retained_earnings",
    "retained profits": "bs_retained_earnings",
    "profit and loss reserve": "bs_retained_earnings",
    # Current period P&L
    "current year earnings": "bs_current_pnl",
    "net income": "bs_current_pnl",
    "current period earnings": "bs_current_pnl",
    "profit for the period": "bs_current_pnl",
    # OCI
    "other comprehensive income": "bs_oci",
    "accumulated other comprehensive income": "bs_oci",
    "revaluation reserve": "bs_oci",
    "foreign currency translation": "bs_oci",
    "hedging reserve": "bs_oci",
    # Treasury stock
    "treasury stock": "bs_treasury_stock",
    "treasury shares": "bs_treasury_stock",
    "own shares": "bs_treasury_stock",
    # Minority interest
    "minority interest": "bs_minority_interest",
    "non-controlling interest": "bs_minority_interest",
    "non controlling interest": "bs_minority_interest",
}


def match_erp_account(account_name: str) -> Optional[str]:
    """Map an ERP account name to a bs_ category via fuzzy matching."""
    normalized = account_name.strip().lower()
    # Remove common prefixes/suffixes
    for prefix in ("total ", "net ", "less: ", "less "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]

    # Direct match
    if normalized in ERP_ACCOUNT_MAP:
        return ERP_ACCOUNT_MAP[normalized]

    # Substring match — find longest matching key
    best_match = None
    best_len = 0
    for key, cat in ERP_ACCOUNT_MAP.items():
        if key in normalized and len(key) > best_len:
            best_match = cat
            best_len = len(key)

    return best_match


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

class BalanceSheetBuilder:
    """Builds a dynamic Balance Sheet from fpa_actuals (bs_* categories)."""

    def __init__(self, company_id: Optional[str] = None):
        self.company_id = company_id

    def build(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full balance sheet build: pull actuals → discover items → assemble rows with totals.

        Returns:
            {
                "periods": ["2025-01", "2025-02", ...],
                "rows": [{"id", "label", "depth", "section", "values", ...}, ...],
                "totals": {
                    "total_current_assets": {...},
                    "total_non_current_assets": {...},
                    "total_assets": {...},
                    "total_current_liabilities": {...},
                    "total_non_current_liabilities": {...},
                    "total_liabilities": {...},
                    "total_equity": {...},
                    "total_liabilities_equity": {...},
                    "balance_check": {...},
                },
            }
        """
        # 1. Pull actuals
        actuals, periods = self._pull_bs_actuals(start, end)

        # 2. Try to link current period P&L from income statement
        actuals = self._link_current_pnl(actuals, periods)

        # 3. Discover line items
        line_items = self._discover_line_items(actuals)

        # 4. Assemble rows with section headers and computed totals
        rows, totals = self._assemble_rows(line_items, actuals, periods)

        return {
            "periods": periods,
            "rows": rows,
            "totals": totals,
        }

    # ------------------------------------------------------------------
    # Step 1: Pull actuals from fpa_actuals (bs_* categories)
    # ------------------------------------------------------------------

    def _pull_bs_actuals(
        self,
        start: Optional[str],
        end: Optional[str],
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        Returns:
            actuals_by_key_period: {"bs_cash": {"2025-01": 500000, ...}, ...}
            periods: sorted list of period strings
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            logger.warning("Supabase client unavailable — cannot fetch BS actuals")
            return {}, []

        query = (
            sb.table("fpa_actuals")
            .select("period, category, subcategory, amount")
        )
        if self.company_id:
            query = query.eq("company_id", self.company_id)
        query = query.like("category", "bs_%")
        if start:
            query = query.gte("period", f"{start}-01")
        if end:
            query = query.lte("period", f"{end}-01")

        result = query.order("period").execute()

        if not result.data:
            return {}, []

        actuals: Dict[str, Dict[str, float]] = {}
        periods_set: set = set()

        for row in result.data:
            period = row["period"][:7]
            cat = row["category"]
            sub = row.get("subcategory")
            amount = float(row["amount"])

            key = f"{cat}:{sub}" if sub else cat
            periods_set.add(period)
            actuals.setdefault(key, {})[period] = (
                actuals.get(key, {}).get(period, 0) + amount
            )

        periods = sorted(periods_set)
        return actuals, periods

    # ------------------------------------------------------------------
    # Step 2: Link current period P&L from income statement
    # ------------------------------------------------------------------

    def _link_current_pnl(
        self,
        actuals: Dict[str, Dict[str, float]],
        periods: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """
        If bs_current_pnl is not in actuals, derive net income from P&L
        actuals (revenue − all cost categories) to link the income statement
        to the balance sheet.
        """
        if "bs_current_pnl" in actuals:
            return actuals

        from app.core.supabase_client import get_supabase_client
        sb = get_supabase_client()
        if not sb or not periods:
            return actuals

        try:
            # Pull all P&L categories (everything that isn't bs_* prefixed)
            result = (
                sb.table("fpa_actuals")
                .select("period, category, amount")
                .eq("company_id", self.company_id)
                .not_("category", "like", "bs_%")
                .order("period")
                .execute()
            )
            if not result.data:
                return actuals

            # Revenue categories are positive, cost categories are negative
            REVENUE_CATS = {"revenue"}
            periods_set = set(periods)
            pnl_by_period: Dict[str, float] = {}

            for row in result.data:
                p = row["period"][:7]
                if p not in periods_set:
                    continue
                cat = row["category"]
                amount = float(row["amount"])
                # Revenue adds, everything else (cogs, opex_*, tax, interest,
                # depreciation, amortization) subtracts
                if cat in REVENUE_CATS:
                    pnl_by_period[p] = pnl_by_period.get(p, 0) + amount
                elif cat.startswith(("cogs", "opex", "tax", "interest", "depreciation", "amortization")):
                    pnl_by_period[p] = pnl_by_period.get(p, 0) - abs(amount)

            if pnl_by_period:
                actuals["bs_current_pnl"] = pnl_by_period
        except Exception as e:
            logger.debug(f"Could not link current period P&L: {e}")

        return actuals

    # ------------------------------------------------------------------
    # Step 3: Discover line items
    # ------------------------------------------------------------------

    def _discover_line_items(
        self, actuals: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """Build row definitions from actual data, or fall back to full skeleton."""
        if not actuals:
            return self._fallback_skeleton()

        items: List[Dict[str, Any]] = []
        cats_with_subs: set = set()

        for key in actuals.keys():
            if ":" in key:
                cats_with_subs.add(key.split(":", 1)[0])

        # When a category has subcategories but also has un-subcategoried
        # amounts (e.g. "bs_cash" alongside "bs_cash:checking"), distribute
        # the parent amounts into a synthetic "other" subcategory so they
        # aren't silently dropped from the sum.
        for cat in list(cats_with_subs):
            if cat in actuals:
                other_key = f"{cat}:other"
                if other_key not in actuals:
                    actuals[other_key] = actuals.pop(cat)
                else:
                    # Merge into existing other bucket
                    for p, v in actuals.pop(cat).items():
                        actuals[other_key][p] = actuals[other_key].get(p, 0) + v

        for key in sorted(actuals.keys()):
            cat, sub = (key.split(":", 1) + [None])[:2]
            section = BS_CATEGORY_SECTION.get(cat, "current_assets")

            if sub:
                items.append({
                    "id": key,
                    "label": sub.replace("_", " ").title(),
                    "category": cat,
                    "subcategory": sub,
                    "section": section,
                    "depth": 2,
                    "parentId": cat,
                })
            else:
                items.append({
                    "id": key,
                    "label": BS_CATEGORY_LABELS.get(cat, cat.replace("bs_", "").replace("_", " ").title()),
                    "category": cat,
                    "subcategory": None,
                    "section": section,
                    "depth": 1,
                    "parentId": None,
                })

        return items if items else self._fallback_skeleton()

    def _fallback_skeleton(self) -> List[Dict[str, Any]]:
        """Full chart of accounts skeleton when no data exists."""
        skeleton = []
        for cat, section in BS_CATEGORY_SECTION.items():
            skeleton.append({
                "id": cat,
                "label": BS_CATEGORY_LABELS.get(cat, cat.replace("bs_", "").replace("_", " ").title()),
                "category": cat,
                "subcategory": None,
                "section": section,
                "depth": 1,
                "parentId": None,
            })
        return skeleton

    # ------------------------------------------------------------------
    # Step 4: Assemble rows with computed totals
    # ------------------------------------------------------------------

    def _assemble_rows(
        self,
        line_items: List[Dict[str, Any]],
        actuals: Dict[str, Dict[str, float]],
        periods: List[str],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Optional[float]]]]:
        """
        Build final row list with section headers, data rows, subtotals,
        and balance check.
        """
        rows: List[Dict[str, Any]] = []
        totals: Dict[str, Dict[str, Optional[float]]] = {}

        # Group items by section
        by_section: Dict[str, List[Dict[str, Any]]] = {}
        for item in line_items:
            sec = item.get("section", "current_assets")
            by_section.setdefault(sec, []).append(item)

        # --- Current Assets ---
        rows.append(self._section_header("current_assets"))
        rows.extend(self._data_rows(by_section.get("current_assets", []), actuals, periods))
        total_ca = self._sum_section(by_section.get("current_assets", []), actuals, periods)
        totals["total_current_assets"] = total_ca
        rows.append(self._total_row("total_current_assets", "Total Current Assets", "current_assets", total_ca))

        # --- Non-Current Assets ---
        rows.append(self._section_header("non_current_assets"))
        rows.extend(self._data_rows(by_section.get("non_current_assets", []), actuals, periods))
        total_nca = self._sum_section(by_section.get("non_current_assets", []), actuals, periods)
        totals["total_non_current_assets"] = total_nca
        rows.append(self._total_row("total_non_current_assets", "Total Non-Current Assets", "non_current_assets", total_nca))

        # --- Total Assets ---
        total_assets = self._add_totals(total_ca, total_nca, periods)
        totals["total_assets"] = total_assets
        rows.append({
            "id": "total_assets",
            "label": "Total Assets",
            "depth": 0,
            "section": "total_assets",
            "isComputed": True,
            "isTotal": True,
            "values": total_assets,
        })

        # --- Current Liabilities ---
        rows.append(self._section_header("current_liabilities"))
        rows.extend(self._data_rows(by_section.get("current_liabilities", []), actuals, periods))
        total_cl = self._sum_section(by_section.get("current_liabilities", []), actuals, periods)
        totals["total_current_liabilities"] = total_cl
        rows.append(self._total_row("total_current_liabilities", "Total Current Liabilities", "current_liabilities", total_cl))

        # --- Non-Current Liabilities ---
        rows.append(self._section_header("non_current_liabilities"))
        rows.extend(self._data_rows(by_section.get("non_current_liabilities", []), actuals, periods))
        total_ncl = self._sum_section(by_section.get("non_current_liabilities", []), actuals, periods)
        totals["total_non_current_liabilities"] = total_ncl
        rows.append(self._total_row("total_non_current_liabilities", "Total Non-Current Liabilities", "non_current_liabilities", total_ncl))

        # --- Total Liabilities ---
        total_liabilities = self._add_totals(total_cl, total_ncl, periods)
        totals["total_liabilities"] = total_liabilities
        rows.append({
            "id": "total_liabilities",
            "label": "Total Liabilities",
            "depth": 0,
            "section": "total_liabilities",
            "isComputed": True,
            "isTotal": True,
            "values": total_liabilities,
        })

        # --- Equity ---
        rows.append(self._section_header("equity"))
        rows.extend(self._data_rows(by_section.get("equity", []), actuals, periods))
        total_equity = self._sum_section(by_section.get("equity", []), actuals, periods)
        totals["total_equity"] = total_equity
        rows.append(self._total_row("total_equity", "Total Equity", "equity", total_equity))

        # --- Total Liabilities & Equity ---
        total_le = self._add_totals(total_liabilities, total_equity, periods)
        totals["total_liabilities_equity"] = total_le
        rows.append({
            "id": "total_liabilities_equity",
            "label": "Total Liabilities & Equity",
            "depth": 0,
            "section": "total_liabilities_equity",
            "isComputed": True,
            "isTotal": True,
            "values": total_le,
        })

        # --- Balance Check (Assets - Liabilities - Equity = 0) ---
        balance_check: Dict[str, Optional[float]] = {}
        for p in periods:
            a = total_assets.get(p)
            le = total_le.get(p)
            if a is not None and le is not None:
                balance_check[p] = round(a - le, 2)
            else:
                balance_check[p] = None
        totals["balance_check"] = balance_check
        rows.append({
            "id": "balance_check",
            "label": "Balance Check (should be 0)",
            "depth": 0,
            "section": "balance_check",
            "isComputed": True,
            "values": balance_check,
        })

        return rows, totals

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _section_header(self, section: str) -> Dict[str, Any]:
        return {
            "id": f"{section}_header",
            "label": BS_SECTION_LABELS.get(section, section.replace("_", " ").title()),
            "depth": 0,
            "isHeader": True,
            "section": section,
            "values": {},
        }

    def _data_rows(
        self,
        items: List[Dict[str, Any]],
        actuals: Dict[str, Dict[str, float]],
        periods: List[str],
    ) -> List[Dict[str, Any]]:
        rows = []
        for item in items:
            row_id = item["id"]
            values: Dict[str, Optional[float]] = {}
            for p in periods:
                values[p] = actuals.get(row_id, {}).get(p)
            row = {
                "id": row_id,
                "label": item["label"],
                "depth": item.get("depth", 1),
                "section": item["section"],
                "values": values,
            }
            if item.get("parentId"):
                row["parentId"] = item["parentId"]
            rows.append(row)
        return rows

    def _total_row(
        self,
        row_id: str,
        label: str,
        section: str,
        values: Dict[str, Optional[float]],
    ) -> Dict[str, Any]:
        return {
            "id": row_id,
            "label": label,
            "depth": 0,
            "section": section,
            "isTotal": True,
            "values": values,
        }

    def _sum_section(
        self,
        items: List[Dict[str, Any]],
        actuals: Dict[str, Dict[str, float]],
        periods: List[str],
    ) -> Dict[str, Optional[float]]:
        """Sum all items in a section for each period."""
        result: Dict[str, Optional[float]] = {}
        for p in periods:
            total = 0.0
            has_any = False
            for item in items:
                val = actuals.get(item["id"], {}).get(p)
                if val is not None:
                    total += val
                    has_any = True
            result[p] = round(total, 2) if has_any else None
        return result

    @staticmethod
    def _add_totals(
        a: Dict[str, Optional[float]],
        b: Dict[str, Optional[float]],
        periods: List[str],
    ) -> Dict[str, Optional[float]]:
        """Add two total dicts period by period."""
        result: Dict[str, Optional[float]] = {}
        for p in periods:
            va, vb = a.get(p), b.get(p)
            if va is not None and vb is not None:
                result[p] = round(va + vb, 2)
            elif va is not None:
                result[p] = va
            elif vb is not None:
                result[p] = vb
            else:
                result[p] = None
        return result
