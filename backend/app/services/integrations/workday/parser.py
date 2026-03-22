"""Workday data parser -- maps HR data to FpaRow objects.

All Workday data flows into the ``fpa_actuals`` table as OpEx subcategories.
There are NO separate HR tables. The same department-to-category mapping
used by BambooHR applies here.

Department/Org --> (category, subcategory):
  Engineering    --> (opex_rd, engineering_salaries)
  Sales          --> (opex_sm, sales_salaries)
  Finance        --> (opex_ga, finance_legal)
  Customer Supp. --> (cogs,    support_salaries)
  ...etc.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.services.integrations.base import FpaRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Department/Org --> (category, subcategory) mapping
# ---------------------------------------------------------------------------
DEPT_CATEGORY_MAP: Dict[str, Tuple[str, str]] = {
    "Engineering": ("opex_rd", "engineering_salaries"),
    "Product": ("opex_rd", "engineering_salaries"),
    "Design": ("opex_rd", "engineering_salaries"),
    "Research": ("opex_rd", "research"),
    "Sales": ("opex_sm", "sales_salaries"),
    "Marketing": ("opex_sm", "content_marketing"),
    "Business Development": ("opex_sm", "sales_salaries"),
    "Finance": ("opex_ga", "finance_legal"),
    "Legal": ("opex_ga", "finance_legal"),
    "Human Resources": ("opex_ga", "admin_salaries"),
    "Operations": ("opex_ga", "admin_salaries"),
    "Administration": ("opex_ga", "admin_salaries"),
    "Customer Support": ("cogs", "support_salaries"),
    "Customer Success": ("cogs", "support_salaries"),
}

_DEFAULT_CATEGORY = ("opex_ga", "other_ga")


def _match_department(dept_name: str) -> Tuple[str, str]:
    """Fuzzy-match a department name to DEPT_CATEGORY_MAP.

    Matching strategy:
      1. Exact match (case-insensitive).
      2. Substring match -- e.g. "Engineering - Backend" matches "Engineering".
      3. Default to ("opex_ga", "other_ga") if nothing matches.
    """
    if not dept_name:
        return _DEFAULT_CATEGORY

    normalized = dept_name.strip()

    # 1. Exact match (case-insensitive)
    for key, value in DEPT_CATEGORY_MAP.items():
        if normalized.lower() == key.lower():
            return value

    # 2. Substring match -- check if any key appears in the department name
    for key, value in DEPT_CATEGORY_MAP.items():
        if key.lower() in normalized.lower():
            return value

    logger.debug(
        "No department match for '%s', defaulting to %s",
        dept_name,
        _DEFAULT_CATEGORY,
    )
    return _DEFAULT_CATEGORY


def _safe_float(value, default: float = 0.0) -> float:
    """Safely convert a value to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Headcount --> FpaRow
# ---------------------------------------------------------------------------

def parse_headcount_to_fpa_rows(
    workers: List[Dict],
    company_id: str,
    period: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Convert Workday headcount data to FpaRow objects.

    Groups workers by ``Supervisory_Organization`` (falling back to
    ``Cost_Center``) and maps each group to an OpEx subcategory.

    Compensation is calculated as ``Total_Annual_Comp / 12`` for the
    monthly amount.

    Args:
        workers: List of worker dicts from the headcount RAAS report.
        company_id: Company identifier for the FpaRow.
        period: Budget period in "YYYY-MM-01" format.
        fund_id: Optional fund identifier.

    Returns:
        List of FpaRow objects ready for ``fpa_actuals`` upsert.
    """
    # Aggregate compensation by department
    dept_totals: Dict[str, float] = {}

    for worker in workers:
        # Determine department: prefer Supervisory_Organization, fall back to Cost_Center
        dept = (
            worker.get("Supervisory_Organization")
            or worker.get("Cost_Center")
            or ""
        )

        annual_comp = _safe_float(worker.get("Total_Annual_Comp"))
        monthly_comp = annual_comp / 12.0

        if dept in dept_totals:
            dept_totals[dept] += monthly_comp
        else:
            dept_totals[dept] = monthly_comp

    # Build FpaRow objects
    rows: List[FpaRow] = []
    for dept_name, monthly_amount in dept_totals.items():
        if monthly_amount == 0.0:
            continue

        category, subcategory = _match_department(dept_name)
        rows.append(
            FpaRow(
                company_id=company_id,
                period=period,
                category=category,
                subcategory=subcategory,
                amount=round(monthly_amount, 2),
                source="workday",
                fund_id=fund_id,
                hierarchy_path=f"{category}/{subcategory}",
            )
        )

    logger.info(
        "Parsed %d workers into %d FpaRow objects for period=%s",
        len(workers),
        len(rows),
        period,
    )
    return rows


# ---------------------------------------------------------------------------
# Compensation report --> FpaRow
# ---------------------------------------------------------------------------

def parse_compensation_to_fpa_rows(
    comp_data: List[Dict],
    company_id: str,
    period: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Convert Workday compensation report to FpaRow objects.

    Each row in the compensation report has a ``Cost_Center`` or
    ``Department`` field with ``Total_Annual_Comp``.  We divide by 12
    for the monthly amount.

    Args:
        comp_data: List of compensation dicts from the RAAS report.
        company_id: Company identifier for the FpaRow.
        period: Budget period in "YYYY-MM-01" format.
        fund_id: Optional fund identifier.

    Returns:
        List of FpaRow objects ready for ``fpa_actuals`` upsert.
    """
    # Aggregate compensation by department
    dept_totals: Dict[str, float] = {}

    for entry in comp_data:
        dept = (
            entry.get("Department")
            or entry.get("Cost_Center")
            or ""
        )

        annual_comp = _safe_float(entry.get("Total_Annual_Comp"))
        monthly_comp = annual_comp / 12.0

        if dept in dept_totals:
            dept_totals[dept] += monthly_comp
        else:
            dept_totals[dept] = monthly_comp

    # Build FpaRow objects
    rows: List[FpaRow] = []
    for dept_name, monthly_amount in dept_totals.items():
        if monthly_amount == 0.0:
            continue

        category, subcategory = _match_department(dept_name)
        rows.append(
            FpaRow(
                company_id=company_id,
                period=period,
                category=category,
                subcategory=subcategory,
                amount=round(monthly_amount, 2),
                source="workday",
                fund_id=fund_id,
                hierarchy_path=f"{category}/{subcategory}",
            )
        )

    logger.info(
        "Parsed %d compensation entries into %d FpaRow objects for period=%s",
        len(comp_data),
        len(rows),
        period,
    )
    return rows
