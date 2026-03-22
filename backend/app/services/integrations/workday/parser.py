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

Compensation breakdown (subcomponent level):
  Workday provides Base_Pay, Bonus_Target, Benefits_Cost separately.
  We emit BOTH the rolled-up subcategory row AND individual subcomponent
  rows so downstream services can model at whichever depth they need.

  hierarchy_path examples:
    opex_rd/engineering_salaries              -- total (sum of subcomponents)
    opex_rd/engineering_salaries/base_pay     -- base salary only
    opex_rd/engineering_salaries/bonus        -- target bonus
    opex_rd/engineering_salaries/benefits     -- employer-paid benefits
    opex_rd/engineering_salaries/payroll_tax  -- estimated employer payroll taxes
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app.services.integrations.base import FpaRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Department/Org --> (category, subcategory) mapping
# ---------------------------------------------------------------------------
DEPT_CATEGORY_MAP: Dict[str, Tuple[str, str]] = {
    # R&D
    "Engineering": ("opex_rd", "engineering_salaries"),
    "Product": ("opex_rd", "engineering_salaries"),
    "Design": ("opex_rd", "engineering_salaries"),
    "Research": ("opex_rd", "research"),
    "Data Science": ("opex_rd", "ml_engineering"),
    "Machine Learning": ("opex_rd", "ml_engineering"),
    "Data Engineering": ("opex_rd", "data_engineering"),
    "DevOps": ("opex_rd", "infra_cloud"),
    "Platform": ("opex_rd", "infra_cloud"),
    "QA": ("opex_rd", "engineering_salaries"),
    "Quality Assurance": ("opex_rd", "engineering_salaries"),
    # S&M
    "Sales": ("opex_sm", "sales_salaries"),
    "Account Executive": ("opex_sm", "sales_salaries"),
    "SDR": ("opex_sm", "sales_salaries"),
    "BDR": ("opex_sm", "sales_salaries"),
    "Sales Engineering": ("opex_sm", "sales_salaries"),
    "Revenue Operations": ("opex_sm", "sales_salaries"),
    "Marketing": ("opex_sm", "content_marketing"),
    "Growth": ("opex_sm", "paid_acquisition"),
    "Demand Gen": ("opex_sm", "paid_acquisition"),
    "Business Development": ("opex_sm", "sales_salaries"),
    "Partnerships": ("opex_sm", "partnerships"),
    # G&A
    "Finance": ("opex_ga", "finance_legal"),
    "Legal": ("opex_ga", "finance_legal"),
    "Accounting": ("opex_ga", "finance_legal"),
    "Human Resources": ("opex_ga", "admin_salaries"),
    "People Ops": ("opex_ga", "admin_salaries"),
    "Recruiting": ("opex_ga", "admin_salaries"),
    "Operations": ("opex_ga", "admin_salaries"),
    "Administration": ("opex_ga", "admin_salaries"),
    "IT": ("opex_ga", "admin_salaries"),
    "Facilities": ("opex_ga", "office"),
    # COGS
    "Customer Support": ("cogs", "support_salaries"),
    "Customer Success": ("cogs", "support_salaries"),
    "Technical Support": ("cogs", "support_salaries"),
}

_DEFAULT_CATEGORY = ("opex_ga", "other_ga")

# Estimated employer payroll tax rate (FICA + FUTA + state avg)
_PAYROLL_TAX_RATE = 0.0865

# Compensation component fields from Workday RAAS reports
_COMP_COMPONENTS = [
    ("Base_Pay", "base_pay"),
    ("Bonus_Target", "bonus"),
    ("Benefits_Cost", "benefits"),
    ("Equity_Value", "equity_comp"),
    ("Commission_Target", "commissions"),
    ("Allowances", "allowances"),
]


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
# Headcount --> FpaRow (with comp component breakdown)
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

    Emits THREE levels of rows:
      1. Subcategory total (e.g. engineering_salaries = total comp)
      2. Comp subcomponents (base_pay, bonus, benefits, payroll_tax)
      3. Headcount count row (for headcount-driven forecasting)

    Args:
        workers: List of worker dicts from the headcount RAAS report.
        company_id: Company identifier for the FpaRow.
        period: Budget period in "YYYY-MM-01" format.
        fund_id: Optional fund identifier.

    Returns:
        List of FpaRow objects ready for ``fpa_actuals`` upsert.
    """
    # Aggregate by department: {dept: {component: annual_total}}
    dept_comp: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dept_headcount: Dict[str, int] = defaultdict(int)

    for worker in workers:
        dept = (
            worker.get("Supervisory_Organization")
            or worker.get("Cost_Center")
            or ""
        )

        # If individual comp components are available, use them
        has_components = any(worker.get(field) for field, _ in _COMP_COMPONENTS)

        if has_components:
            for field, comp_key in _COMP_COMPONENTS:
                val = _safe_float(worker.get(field))
                if val > 0:
                    dept_comp[dept][comp_key] += val

            # Estimate payroll tax on base pay
            base = _safe_float(worker.get("Base_Pay"))
            if base > 0:
                dept_comp[dept]["payroll_tax"] += base * _PAYROLL_TAX_RATE
        else:
            # Fallback: only Total_Annual_Comp available
            annual_comp = _safe_float(worker.get("Total_Annual_Comp"))
            dept_comp[dept]["total_comp"] += annual_comp

        dept_headcount[dept] += 1

    # Build FpaRow objects
    rows: List[FpaRow] = []
    for dept_name in dept_comp:
        category, subcategory = _match_department(dept_name)
        components = dept_comp[dept_name]

        # Compute total monthly comp for this dept
        if "total_comp" in components:
            # No component breakdown available
            total_annual = components["total_comp"]
            monthly_total = total_annual / 12.0
            if monthly_total == 0.0:
                continue

            rows.append(
                FpaRow(
                    company_id=company_id,
                    period=period,
                    category=category,
                    subcategory=subcategory,
                    amount=round(monthly_total, 2),
                    source="workday",
                    fund_id=fund_id,
                    hierarchy_path=f"{category}/{subcategory}",
                )
            )
        else:
            # We have component breakdown — emit each subcomponent
            total_annual = sum(components.values())
            monthly_total = total_annual / 12.0
            if monthly_total == 0.0:
                continue

            # 1. Rolled-up subcategory total
            rows.append(
                FpaRow(
                    company_id=company_id,
                    period=period,
                    category=category,
                    subcategory=subcategory,
                    amount=round(monthly_total, 2),
                    source="workday",
                    fund_id=fund_id,
                    hierarchy_path=f"{category}/{subcategory}",
                )
            )

            # 2. Individual comp subcomponents
            for comp_key, annual_amount in components.items():
                monthly_amount = annual_amount / 12.0
                if monthly_amount == 0.0:
                    continue
                rows.append(
                    FpaRow(
                        company_id=company_id,
                        period=period,
                        category=category,
                        subcategory=f"{subcategory}/{comp_key}",
                        amount=round(monthly_amount, 2),
                        source="workday",
                        fund_id=fund_id,
                        hierarchy_path=f"{category}/{subcategory}/{comp_key}",
                    )
                )

        # 3. Headcount row for this department
        hc = dept_headcount.get(dept_name, 0)
        if hc > 0:
            rows.append(
                FpaRow(
                    company_id=company_id,
                    period=period,
                    category="headcount",
                    subcategory=subcategory,
                    amount=float(hc),
                    source="workday",
                    fund_id=fund_id,
                    hierarchy_path=f"headcount/{subcategory}",
                )
            )

    logger.info(
        "Parsed %d workers into %d FpaRow objects for period=%s "
        "(incl. comp subcomponents and headcount)",
        len(workers),
        len(rows),
        period,
    )
    return rows


# ---------------------------------------------------------------------------
# Compensation report --> FpaRow (with comp component breakdown)
# ---------------------------------------------------------------------------

def parse_compensation_to_fpa_rows(
    comp_data: List[Dict],
    company_id: str,
    period: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Convert Workday compensation report to FpaRow objects.

    Each row in the compensation report has a ``Cost_Center`` or
    ``Department`` field with compensation fields.  When individual
    comp components (Base_Pay, Bonus_Target, Benefits_Cost) are present,
    they are emitted as subcomponent-level rows.

    Args:
        comp_data: List of compensation dicts from the RAAS report.
        company_id: Company identifier for the FpaRow.
        period: Budget period in "YYYY-MM-01" format.
        fund_id: Optional fund identifier.

    Returns:
        List of FpaRow objects ready for ``fpa_actuals`` upsert.
    """
    # Aggregate by department: {dept: {component: annual_total}}
    dept_comp: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for entry in comp_data:
        dept = (
            entry.get("Department")
            or entry.get("Cost_Center")
            or ""
        )

        has_components = any(entry.get(field) for field, _ in _COMP_COMPONENTS)

        if has_components:
            for field, comp_key in _COMP_COMPONENTS:
                val = _safe_float(entry.get(field))
                if val > 0:
                    dept_comp[dept][comp_key] += val

            base = _safe_float(entry.get("Base_Pay"))
            if base > 0:
                dept_comp[dept]["payroll_tax"] += base * _PAYROLL_TAX_RATE
        else:
            annual_comp = _safe_float(entry.get("Total_Annual_Comp"))
            dept_comp[dept]["total_comp"] += annual_comp

    # Build FpaRow objects
    rows: List[FpaRow] = []
    for dept_name in dept_comp:
        category, subcategory = _match_department(dept_name)
        components = dept_comp[dept_name]

        if "total_comp" in components:
            monthly_total = components["total_comp"] / 12.0
            if monthly_total == 0.0:
                continue
            rows.append(
                FpaRow(
                    company_id=company_id,
                    period=period,
                    category=category,
                    subcategory=subcategory,
                    amount=round(monthly_total, 2),
                    source="workday",
                    fund_id=fund_id,
                    hierarchy_path=f"{category}/{subcategory}",
                )
            )
        else:
            total_annual = sum(components.values())
            monthly_total = total_annual / 12.0
            if monthly_total == 0.0:
                continue

            # Rolled-up total
            rows.append(
                FpaRow(
                    company_id=company_id,
                    period=period,
                    category=category,
                    subcategory=subcategory,
                    amount=round(monthly_total, 2),
                    source="workday",
                    fund_id=fund_id,
                    hierarchy_path=f"{category}/{subcategory}",
                )
            )

            # Individual comp subcomponents
            for comp_key, annual_amount in components.items():
                monthly_amount = annual_amount / 12.0
                if monthly_amount == 0.0:
                    continue
                rows.append(
                    FpaRow(
                        company_id=company_id,
                        period=period,
                        category=category,
                        subcategory=f"{subcategory}/{comp_key}",
                        amount=round(monthly_amount, 2),
                        source="workday",
                        fund_id=fund_id,
                        hierarchy_path=f"{category}/{subcategory}/{comp_key}",
                    )
                )

    logger.info(
        "Parsed %d compensation entries into %d FpaRow objects for period=%s "
        "(incl. comp subcomponents)",
        len(comp_data),
        len(rows),
        period,
    )
    return rows
