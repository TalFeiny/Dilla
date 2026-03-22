"""BambooHR data → FpaRow parser.

Converts BambooHR employee/compensation data into FpaRow objects that flow
into the fpa_actuals table as OpEx subcategories.  No separate HR tables —
everything lands in the unified FPA pipeline.

Mapping logic:
    Employee compensation grouped by department → OpEx categories
    Department → (category, subcategory) via DEPT_CATEGORY_MAP
    Unknown departments default to opex_ga / other_ga
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.services.integrations.base import FpaRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Department → (FPA category, subcategory) mapping
# ---------------------------------------------------------------------------
DEPT_CATEGORY_MAP: Dict[str, Tuple[str, str]] = {
    # R&D
    "Engineering": ("opex_rd", "engineering_salaries"),
    "Product": ("opex_rd", "engineering_salaries"),
    "Design": ("opex_rd", "engineering_salaries"),
    "Research": ("opex_rd", "research"),
    # S&M
    "Sales": ("opex_sm", "sales_salaries"),
    "Marketing": ("opex_sm", "content_marketing"),
    "Business Development": ("opex_sm", "sales_salaries"),
    # G&A
    "Finance": ("opex_ga", "finance_legal"),
    "Legal": ("opex_ga", "finance_legal"),
    "Human Resources": ("opex_ga", "admin_salaries"),
    "Operations": ("opex_ga", "admin_salaries"),
    "Administration": ("opex_ga", "admin_salaries"),
    # COGS
    "Customer Support": ("cogs", "support_salaries"),
    "Customer Success": ("cogs", "support_salaries"),
}

# Default for departments not found in the map
_DEFAULT_CATEGORY = ("opex_ga", "other_ga")

# ---------------------------------------------------------------------------
# Pay-period annualization multipliers
# ---------------------------------------------------------------------------
_PAY_PERIOD_MULTIPLIERS: Dict[str, float] = {
    "Year": 1.0,
    "Month": 12.0,
    "Week": 52.0,
    "Day": 260.0,       # ~52 weeks * 5 days
    "Hour": 2080.0,     # ~52 weeks * 40 hours
    "Pay Period": 26.0, # bi-weekly default
}


def _annualize_comp(pay_rate: float, pay_per: str) -> float:
    """Convert a pay rate to an annualized amount.

    Args:
        pay_rate: The raw numeric rate from BambooHR.
        pay_per: The pay period string — "Year", "Hour", "Month", etc.

    Returns:
        Annual compensation as a float.  Returns 0.0 if the
        pay_per value is unrecognized (logged as a warning).
    """
    if not pay_rate or pay_rate <= 0:
        return 0.0

    multiplier = _PAY_PERIOD_MULTIPLIERS.get(pay_per)
    if multiplier is None:
        logger.warning(
            "Unknown pay_per value '%s' — defaulting to annual (1x)", pay_per
        )
        multiplier = 1.0

    return pay_rate * multiplier


def _resolve_category(department: Optional[str]) -> Tuple[str, str]:
    """Map a department name to (category, subcategory).

    Performs a case-insensitive lookup against DEPT_CATEGORY_MAP.
    Falls back to _DEFAULT_CATEGORY for unknown departments.
    """
    if not department:
        return _DEFAULT_CATEGORY

    # Exact match first
    if department in DEPT_CATEGORY_MAP:
        return DEPT_CATEGORY_MAP[department]

    # Case-insensitive fallback
    dept_lower = department.lower().strip()
    for key, value in DEPT_CATEGORY_MAP.items():
        if key.lower() == dept_lower:
            return value

    logger.info(
        "Department '%s' not in DEPT_CATEGORY_MAP — defaulting to %s",
        department,
        _DEFAULT_CATEGORY,
    )
    return _DEFAULT_CATEGORY


def _safe_float(value: Any) -> float:
    """Coerce a value to float, returning 0.0 on failure."""
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (ValueError, TypeError):
        return 0.0


def parse_employees_to_fpa_rows(
    employees: List[Dict[str, Any]],
    company_id: str,
    period: str,
    fund_id: Optional[str] = None,
) -> List[FpaRow]:
    """Convert BambooHR employee data to FpaRow objects.

    Pipeline:
        1. Filter to active employees (status == "Active")
        2. Annualize comp: payRate + payPer -> annual comp
        3. Group by department
        4. Map department -> (category, subcategory) via DEPT_CATEGORY_MAP
        5. Divide annual total by 12 -> monthly amount per department
        6. Return one FpaRow per department with source="bamboohr"

    For departments not in DEPT_CATEGORY_MAP, default to opex_ga/other_ga.

    Args:
        employees: List of employee dicts from BambooHRClient.get_custom_report().
        company_id: The Dilla company UUID.
        period: Month string in "YYYY-MM-01" format.
        fund_id: Optional fund UUID.

    Returns:
        List of FpaRow objects ready for upsert into fpa_actuals.
    """
    # ── 1. Filter to active employees ────────────────────────────
    active = [
        emp for emp in employees
        if str(emp.get("status", "")).strip().lower() == "active"
    ]

    if not active:
        logger.warning(
            "No active employees found in BambooHR data for company_id=%s",
            company_id,
        )
        return []

    logger.info(
        "Processing %d active employees (of %d total) for company_id=%s",
        len(active),
        len(employees),
        company_id,
    )

    # ── 2-3. Annualize comp & group by department ────────────────
    # dept_key -> {category, subcategory, annual_total, headcount}
    dept_totals: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"category": "", "subcategory": "", "annual_total": 0.0, "headcount": 0}
    )

    for emp in active:
        department = emp.get("department", "") or ""
        pay_rate = _safe_float(emp.get("payRate"))
        pay_per = str(emp.get("payPer", "Year")).strip()

        annual_comp = _annualize_comp(pay_rate, pay_per)
        category, subcategory = _resolve_category(department)

        # Use (category, subcategory) as key to aggregate across
        # departments that map to the same FPA bucket
        key = f"{category}::{subcategory}"
        bucket = dept_totals[key]
        bucket["category"] = category
        bucket["subcategory"] = subcategory
        bucket["annual_total"] += annual_comp
        bucket["headcount"] += 1

    # ── 4-6. Build FpaRow per aggregated bucket ──────────────────
    rows: List[FpaRow] = []

    for key, bucket in dept_totals.items():
        annual_total = bucket["annual_total"]
        monthly_amount = annual_total / 12.0

        if monthly_amount <= 0:
            logger.debug(
                "Skipping bucket %s with zero/negative monthly amount", key
            )
            continue

        row = FpaRow(
            company_id=company_id,
            period=period,
            category=bucket["category"],
            subcategory=bucket["subcategory"],
            amount=round(monthly_amount, 2),
            source="bamboohr",
            fund_id=fund_id,
            hierarchy_path=f"{bucket['category']}/{bucket['subcategory']}",
        )
        rows.append(row)

        logger.debug(
            "FpaRow: %s/%s = $%.2f/mo (%d employees)",
            bucket["category"],
            bucket["subcategory"],
            monthly_amount,
            bucket["headcount"],
        )

    logger.info(
        "Parsed %d FpaRow(s) from %d active employees for company_id=%s, period=%s",
        len(rows),
        len(active),
        company_id,
        period,
    )

    return rows
