"""Salesforce data → FpaRow parser.

Converts Salesforce Opportunity data into FpaRow objects for the
``fpa_actuals`` table.  All CRM data flows into ``fpa_actuals`` as
revenue subcategories — NO separate tables.

Key mapping:
- Closed-Won opportunities → actual revenue  (source="salesforce")
- Open pipeline            → weighted revenue (source="salesforce_pipeline")
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from app.services.integrations.base import FpaRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Opportunity Type → subcategory mapping
# ---------------------------------------------------------------------------
_TYPE_TO_SUBCATEGORY = {
    "New Business": "new_business_bookings",
    "New Customer": "new_business_bookings",
    "Renewal": "renewal_bookings",
    "Expansion": "expansion_bookings",
    "Upsell": "expansion_bookings",
    "Add-On": "expansion_bookings",
}

_DEFAULT_SUBCATEGORY = "bookings"

# ---------------------------------------------------------------------------
# ForecastCategory → subcategory mapping
# ---------------------------------------------------------------------------
_FORECAST_TO_SUBCATEGORY = {
    "Commit": "pipeline_commit",
    "Best Case": "pipeline_best_case",
    "BestCase": "pipeline_best_case",
    "Pipeline": "pipeline_pipeline",
}

_OMITTED_FORECAST_CATEGORIES = {"Omitted", "Closed"}


def _close_date_to_period(close_date: str) -> Optional[str]:
    """Convert a CloseDate (YYYY-MM-DD) to a period string (YYYY-MM-01).

    Returns None if the date cannot be parsed.
    """
    if not close_date or not isinstance(close_date, str):
        return None
    parts = close_date.split("-")
    if len(parts) < 2:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
        return f"{year:04d}-{month:02d}-01"
    except (ValueError, IndexError):
        return None


def _safe_float(value) -> float:
    """Safely convert a value to float, returning 0.0 on failure."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Won opportunities → actual revenue
# ---------------------------------------------------------------------------

def parse_won_opportunities_to_fpa_rows(
    opportunities: List[Dict],
    company_id: str,
    fund_id: str = None,
) -> List[FpaRow]:
    """Convert closed-won Salesforce opportunities to FpaRow objects.

    Logic:
    1. Group by CloseDate month (period)
    2. Sub-group by Type → subcategory:
       - "New Business" / "New Customer" → "new_business_bookings"
       - "Renewal"                       → "renewal_bookings"
       - "Expansion" / "Upsell" / "Add-On" → "expansion_bookings"
       - Other / None                    → "bookings"
    3. Sum Amount per group
    4. Return FpaRow with category="revenue", source="salesforce"
    """
    # {(period, subcategory): total_amount}
    grouped: Dict[tuple, float] = defaultdict(float)

    for opp in opportunities:
        # Only process won deals
        if not opp.get("IsWon"):
            continue

        amount = _safe_float(opp.get("Amount"))
        if amount == 0.0:
            continue

        period = _close_date_to_period(opp.get("CloseDate"))
        if not period:
            logger.warning(
                "Skipping opportunity %s — invalid CloseDate: %s",
                opp.get("Id", "?"),
                opp.get("CloseDate"),
            )
            continue

        opp_type = (opp.get("Type") or "").strip()
        subcategory = _TYPE_TO_SUBCATEGORY.get(opp_type, _DEFAULT_SUBCATEGORY)

        grouped[(period, subcategory)] += amount

    rows: List[FpaRow] = []
    for (period, subcategory), total in sorted(grouped.items()):
        rows.append(
            FpaRow(
                company_id=company_id,
                period=period,
                category="revenue",
                subcategory=subcategory,
                amount=round(total, 2),
                source="salesforce",
                fund_id=fund_id,
                hierarchy_path=f"revenue/{subcategory}",
            )
        )

    logger.info(
        "Parsed %d won opportunities into %d FpaRow(s) for company %s",
        len(opportunities),
        len(rows),
        company_id,
    )
    return rows


# ---------------------------------------------------------------------------
# Open pipeline → weighted revenue forecast
# ---------------------------------------------------------------------------

def parse_pipeline_to_fpa_rows(
    opportunities: List[Dict],
    company_id: str,
    fund_id: str = None,
) -> List[FpaRow]:
    """Convert open Salesforce pipeline to weighted revenue FpaRow objects.

    Logic:
    1. Group by expected CloseDate month (period)
    2. Weighted amount = Amount * (Probability / 100)
    3. Map ForecastCategory → subcategory:
       - "Commit"    → "pipeline_commit"
       - "Best Case" → "pipeline_best_case"
       - "Pipeline"  → "pipeline_pipeline"
       - "Omitted"   → skip entirely
    4. Return FpaRow with category="revenue", source="salesforce_pipeline"
    """
    # {(period, subcategory): weighted_total}
    grouped: Dict[tuple, float] = defaultdict(float)
    skipped = 0

    for opp in opportunities:
        # Skip closed opportunities
        if opp.get("IsClosed"):
            continue

        amount = _safe_float(opp.get("Amount"))
        if amount == 0.0:
            continue

        probability = _safe_float(opp.get("Probability"))
        weighted_amount = amount * (probability / 100.0)
        if weighted_amount == 0.0:
            continue

        period = _close_date_to_period(opp.get("CloseDate"))
        if not period:
            logger.warning(
                "Skipping pipeline opportunity %s — invalid CloseDate: %s",
                opp.get("Id", "?"),
                opp.get("CloseDate"),
            )
            continue

        forecast_category = (opp.get("ForecastCategory") or "").strip()

        # Skip omitted / closed forecast categories
        if forecast_category in _OMITTED_FORECAST_CATEGORIES:
            skipped += 1
            continue

        subcategory = _FORECAST_TO_SUBCATEGORY.get(forecast_category, "pipeline_pipeline")

        grouped[(period, subcategory)] += weighted_amount

    rows: List[FpaRow] = []
    for (period, subcategory), total in sorted(grouped.items()):
        rows.append(
            FpaRow(
                company_id=company_id,
                period=period,
                category="revenue",
                subcategory=subcategory,
                amount=round(total, 2),
                source="salesforce_pipeline",
                fund_id=fund_id,
                hierarchy_path=f"revenue/{subcategory}",
            )
        )

    logger.info(
        "Parsed %d pipeline opportunities into %d FpaRow(s) for company %s "
        "(skipped %d omitted)",
        len(opportunities),
        len(rows),
        company_id,
        skipped,
    )
    return rows
