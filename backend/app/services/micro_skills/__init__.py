"""
Micro-Skills Module — Small, composable, fast skills for data gap resolution.

Each micro-skill is an async function that:
1. Takes company_data dict + optional context
2. Returns MicroSkillResult with field_updates, suggestions, memo sections
3. Runs independently or chained via gap_resolver

Tiers:
- Tier 1 (Benchmark): Pure computation, <100ms, no network
- Tier 2 (Search): 1 Tavily search each, <5s, parallel
- Tier 3 (Compute): Valuations/projections, needs Tier 1/2 data first
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CitationSource:
    """Rich citation with metadata — replaces bare URL strings."""
    url: str = ""
    title: str = ""
    snippet: str = ""
    date: str = ""               # ISO date if available
    document_id: str = ""        # For internal docs
    line_range: str = ""         # "L42-L51" for doc citations
    source_type: str = "web"     # "web" | "document" | "benchmark"

    def to_dict(self) -> Dict[str, str]:
        return {k: v for k, v in {
            "url": self.url, "title": self.title, "snippet": self.snippet,
            "date": self.date, "document_id": self.document_id,
            "line_range": self.line_range, "source_type": self.source_type,
        }.items() if v}


@dataclass
class MicroSkillResult:
    """Standard return type for all micro-skills."""
    field_updates: Dict[str, Any] = field(default_factory=dict)  # {column_id: value} for grid
    suggestions: List[Dict] = field(default_factory=list)        # Ready for pending_suggestions insert
    confidence: float = 0.0                                      # 0-1
    reasoning: str = ""                                          # Human-readable explanation
    citations: List[CitationSource] = field(default_factory=list)  # Rich citation objects
    source: str = ""                                             # Skill name for tracking
    memo_section: Optional[Dict] = None                          # Structured narrative section
    chart_data: Optional[Dict] = None                            # Chart-ready data for frontend
    metadata: Dict[str, Any] = field(default_factory=dict)       # Extra metadata (is_correction, old_value, etc.)

    def has_data(self) -> bool:
        """True if skill produced any usable data."""
        return bool(self.field_updates) or bool(self.suggestions)

    def merge_into(self, company: dict) -> dict:
        """Apply field_updates to company dict, only filling gaps (not overwriting)."""
        for k, v in self.field_updates.items():
            if v is not None and not company.get(k):
                company[k] = v
        return company


def detect_missing(company: dict, needed_fields: List[str]) -> List[str]:
    """Return list of fields that are missing/empty/None in company data."""
    missing = []
    for f in needed_fields:
        val = company.get(f)
        if val is None or val == "" or val == 0:
            missing.append(f)
    return missing


# Standard fields the gap resolver checks
CORE_FIELDS = [
    "stage", "description", "business_model", "sector",
    "arr", "revenue", "inferred_revenue",
    "valuation", "inferred_valuation",
    "total_funding", "last_round_amount", "last_round_date",
    "funding_rounds",
    "team_size", "employee_count",
    "growth_rate", "gross_margin",
    "burn_rate", "runway_months",
    "founders", "hq_location",
    "competitors",
]

# Fields needed for specific analyses
VALUATION_FIELDS = ["arr", "revenue", "inferred_revenue", "stage", "growth_rate", "valuation"]
CAP_TABLE_FIELDS = ["stage", "total_funding", "last_round_amount", "valuation"]
FOLLOWON_FIELDS = VALUATION_FIELDS + CAP_TABLE_FIELDS + ["burn_rate", "runway_months"]
ENRICHMENT_FIELDS = ["description", "sector", "stage", "arr", "team_size", "total_funding"]
