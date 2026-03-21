"""QuickBooks Online report parser.

Converts QBO report JSON (P&L, Balance Sheet) into normalized FpaRow objects
that can be upserted into fpa_actuals.

QBO report structure:
{
    "Header": {"Time": "...", "ReportName": "ProfitAndLoss", ...},
    "Columns": {"Column": [{"ColTitle": "", "ColType": "Account"}, {"ColTitle": "Jan 2025", ...}]},
    "Rows": {
        "Row": [
            {"Header": {"ColData": [{"value": "Income"}]},
             "Rows": {"Row": [
                 {"ColData": [{"value": "Sales", "id": "1"}, {"value": "5000.00"}, ...]},
             ]},
             "Summary": {"ColData": [{"value": "Total Income"}, {"value": "5000.00"}]}
            },
        ]
    }
}
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.integrations.base import FpaRow
from app.services.integrations.report_normalizer import normalize_period

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# QBO P&L section → Dilla category mapping
# ---------------------------------------------------------------------------
QBO_PL_SECTION_MAP = {
    "Income": "revenue",
    "Total Income": "revenue",
    "Other Income": "revenue",
    "Total Other Income": "revenue",
    "Cost of Goods Sold": "cogs",
    "Total Cost of Goods Sold": "cogs",
    "Expenses": "opex_total",
    "Total Expenses": "opex_total",
    "Other Expenses": "opex_ga",
    "Total Other Expenses": "opex_ga",
}

# QBO BS section → Dilla category mapping
QBO_BS_SECTION_MAP = {
    "Bank Accounts": "bs_cash",
    "Accounts Receivable": "bs_ar",
    "Other Current Assets": "bs_other_ca",
    "Fixed Assets": "bs_ppe",
    "Other Assets": "bs_other_nca",
    "Accounts Payable": "bs_ap",
    "Credit Cards": "bs_other_cl",
    "Other Current Liabilities": "bs_other_cl",
    "Long-Term Liabilities": "bs_other_ncl",
    "Equity": "bs_other_equity",
    # Fallbacks
    "ASSETS": "bs_other_ca",
    "LIABILITIES AND EQUITY": "bs_other_cl",
}


def _extract_periods(report: Dict[str, Any]) -> List[str]:
    """Extract period headers from QBO report Columns."""
    columns = report.get("Columns", {}).get("Column", [])
    periods = []
    for col in columns:
        title = col.get("ColTitle", "")
        col_type = col.get("ColType", "")
        if col_type == "Money" or (title and col_type != "Account"):
            periods.append(title)
    return periods


def _walk_rows(
    rows_container: Any,
    current_category: str,
    iso_periods: List[Optional[str]],
    company_id: str,
    source: str,
    fund_id: Optional[str],
    section_map: Dict[str, str],
) -> List[FpaRow]:
    """Recursively walk QBO report rows and extract FpaRow entries."""
    results: List[FpaRow] = []

    if isinstance(rows_container, dict):
        row_list = rows_container.get("Row", [])
    elif isinstance(rows_container, list):
        row_list = rows_container
    else:
        return results

    for row in row_list:
        # Check for section header
        header = row.get("Header", {})
        header_data = header.get("ColData", [])
        if header_data:
            section_name = header_data[0].get("value", "")
            if section_name in section_map:
                current_category = section_map[section_name]

        # Check for group name (alternative structure)
        group = row.get("group", "")
        if group and group in section_map:
            current_category = section_map[group]

        # Data row — has ColData with account name + amounts
        col_data = row.get("ColData", [])
        if col_data and len(col_data) >= 2:
            account_name = col_data[0].get("value", "").strip()

            # Skip summary/total rows
            if account_name.startswith("Total ") or not account_name:
                pass
            elif current_category:
                for i, cell in enumerate(col_data[1:]):
                    if i >= len(iso_periods) or not iso_periods[i]:
                        continue

                    raw_value = cell.get("value", "")
                    if not raw_value:
                        continue

                    try:
                        amount = float(str(raw_value).replace(",", ""))
                    except (ValueError, TypeError):
                        continue

                    if amount == 0:
                        continue

                    results.append(FpaRow(
                        company_id=company_id,
                        period=iso_periods[i],
                        category=current_category,
                        subcategory=account_name.lower().replace(" ", "_").replace("-", "_"),
                        amount=amount,
                        source=source,
                        fund_id=fund_id,
                        hierarchy_path=f"{current_category}/{account_name.lower().replace(' ', '_')}",
                    ))

        # Recurse into nested rows
        inner_rows = row.get("Rows", {})
        if inner_rows:
            results.extend(_walk_rows(
                inner_rows, current_category, iso_periods,
                company_id, source, fund_id, section_map,
            ))

    return results


def parse_profit_and_loss(
    report: Dict[str, Any],
    company_id: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Parse a QBO P&L report into FpaRow objects."""
    if not report:
        return []

    periods = _extract_periods(report)
    if not periods:
        logger.warning("No period columns in QBO P&L report")
        return []

    iso_periods = [normalize_period(p) for p in periods]

    rows_data = report.get("Rows", {})
    return _walk_rows(
        rows_data, "opex_total", iso_periods,
        company_id, "quickbooks", fund_id, QBO_PL_SECTION_MAP,
    )


def parse_balance_sheet(
    report: Dict[str, Any],
    company_id: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Parse a QBO Balance Sheet report into FpaRow objects."""
    if not report:
        return []

    periods = _extract_periods(report)
    if not periods:
        # Single-date BS — use the report date
        report_date = report.get("Header", {}).get("EndPeriod", "")
        if report_date:
            periods = [report_date]
        else:
            logger.warning("No period in QBO BS report")
            return []

    iso_periods = [normalize_period(p) for p in periods]

    rows_data = report.get("Rows", {})
    return _walk_rows(
        rows_data, "bs_other_ca", iso_periods,
        company_id, "quickbooks", fund_id, QBO_BS_SECTION_MAP,
    )
