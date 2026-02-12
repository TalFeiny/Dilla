"""
Natural Language FP&A Parser
Parses natural language queries into structured ParsedQuery objects
Uses keyword extraction + pattern matching (no LLM call — this runs on the hot path)
"""

import logging
import re
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    """Types of FPA workflow steps"""
    FUNDING_EVENT = "funding_event"
    GROWTH_CHANGE = "growth_change"
    EXIT_EVENT = "exit_event"
    REVENUE_PROJECTION = "revenue_projection"
    VALUATION = "valuation"
    CUSTOM = "custom"


class ParsedStep(BaseModel):
    """A single parsed step from a natural language query"""
    type: StepType
    payload: Dict[str, Any]  # e.g. {"event": "seed_extension", "rd_extension": True}
    step_id: Optional[str] = None
    temporal_order: Optional[int] = None


class ParsedQuery(BaseModel):
    """Parsed natural language query with structured steps"""
    query_type: str  # "multi_step_scenario" | "forecast" | "valuation" | ...
    steps: List[ParsedStep]
    temporal_sequence: List[str]  # ["step1", "step2", "step3"]
    entities: Dict[str, List[str]]  # companies, funds, metrics
    inferred_params: Dict[str, Any]
    original_query: str


# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------

_QUERY_TYPE_PATTERNS = {
    "forecast": [
        r"\bforecast\b", r"\bproject\b", r"\bpredict\b",
        r"\bnext\s+\d+\s+(year|month|quarter)", r"\bgrow(th)?\b.*\b(for|over|next)\b",
    ],
    "valuation": [
        r"\bvalu(e|ation)\b", r"\bworth\b", r"\bmultiple\b", r"\bmark[\s-]to[\s-]market\b",
    ],
    "stress_test": [
        r"\bstress\b", r"\bworst[\s-]case\b", r"\bdownside\b",
    ],
    "sensitivity": [
        r"\bsensitiv(e|ity)\b", r"\btornado\b", r"\bwhat[\s-]if\b",
    ],
    "regression": [
        r"\bregress(ion)?\b", r"\bcorrelat(e|ion)\b", r"\btrend\b",
    ],
    "scenario": [
        r"\bscenario\b", r"\bwhat happens\b", r"\bif\s+.+\s+then\b",
    ],
}

_STEP_PATTERNS: Dict[str, List[str]] = {
    "revenue_projection": [
        r"\b(forecast|project|predict)\b.*\b(arr|revenue|sales|mrr)\b",
        r"\b(arr|revenue|sales|mrr)\b.*\b(forecast|project|predict|grow|next)\b",
    ],
    "growth_change": [
        r"\bgrowth\b.*\b(slow|decelerat|accelerat|change|drop|increase)\b",
        r"\b(decelerat|accelerat)\b.*\bgrowth\b",
    ],
    "valuation": [
        r"\bvalu(e|ation)\b", r"\bmultiple\b",
    ],
    "exit_event": [
        r"\bexit\b", r"\bipo\b", r"\bacquisition\b", r"\bm&a\b",
    ],
    "funding_event": [
        r"\brais(e|ing)\b", r"\bfunding\b", r"\bround\b", r"\bseries\b",
    ],
}

# Metrics the user might mention
_METRIC_KEYWORDS = [
    "arr", "revenue", "mrr", "growth", "margin", "ebitda",
    "burn", "runway", "dpi", "tvpi", "irr", "nav", "valuation",
    "churn", "nrr", "ltv", "cac", "arpu",
]


class NLFPAParser:
    """Parser for natural language FP&A queries"""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, query: str) -> ParsedQuery:
        """
        Parse a natural language query into a structured ParsedQuery.

        Extracts query type, entities (companies, metrics), and builds
        ordered workflow steps.
        """
        logger.info(f"Parsing FP&A query: {query[:100]}...")
        q = query.strip()
        q_lower = q.lower()

        # 1. Determine query type
        query_type = self._classify_query_type(q_lower)

        # 2. Extract entities
        companies = self._extract_companies(q)
        metrics = self._extract_metrics(q_lower)

        # 3. Extract numeric parameters (periods, percentages, amounts)
        params = self._extract_params(q_lower)

        # 4. Build steps
        steps = self._build_steps(q_lower, query_type, companies, metrics, params)

        temporal_sequence = [s.step_id for s in steps if s.step_id]

        return ParsedQuery(
            query_type=query_type,
            steps=steps,
            temporal_sequence=temporal_sequence,
            entities={
                "companies": companies,
                "funds": [],
                "metrics": metrics,
            },
            inferred_params=params,
            original_query=query,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _classify_query_type(self, q: str) -> str:
        for qtype, patterns in _QUERY_TYPE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, q, re.IGNORECASE):
                    return qtype
        return "forecast"  # safe default

    def _extract_companies(self, q: str) -> List[str]:
        """Extract @-mentioned company names."""
        return re.findall(r"@(\w+)", q)

    def _extract_metrics(self, q: str) -> List[str]:
        found = []
        for m in _METRIC_KEYWORDS:
            if re.search(rf"\b{m}\b", q, re.IGNORECASE):
                found.append(m)
        return found

    def _extract_params(self, q: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        # Periods: "next 3 years", "5 quarters"
        m = re.search(r"(\d+)\s*(year|month|quarter)s?", q)
        if m:
            params["periods"] = int(m.group(1))
            params["period_unit"] = m.group(2)

        # Percentages: "20%", "growth of 30%"
        pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", q)
        if pcts:
            params["percentages"] = [float(p) for p in pcts]

        # Dollar amounts: "$50M", "$2B"
        amounts = re.findall(r"\$(\d+(?:\.\d+)?)\s*([MBKmkb])?", q)
        if amounts:
            parsed_amounts = []
            for val, suffix in amounts:
                multiplier = {"m": 1e6, "b": 1e9, "k": 1e3}.get((suffix or "").lower(), 1)
                parsed_amounts.append(float(val) * multiplier)
            params["amounts"] = parsed_amounts

        return params

    def _build_steps(
        self,
        q: str,
        query_type: str,
        companies: List[str],
        metrics: List[str],
        params: Dict[str, Any],
    ) -> List[ParsedStep]:
        """Build workflow steps from the parsed query."""
        steps: List[ParsedStep] = []
        step_idx = 0

        # Match explicit step patterns first
        matched_types: set = set()
        for step_type, patterns in _STEP_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, q, re.IGNORECASE):
                    if step_type not in matched_types:
                        matched_types.add(step_type)
                        step_idx += 1
                        steps.append(ParsedStep(
                            type=StepType(step_type),
                            payload=self._build_step_payload(step_type, companies, metrics, params),
                            step_id=f"step_{step_idx}",
                            temporal_order=step_idx,
                        ))
                    break

        # If no explicit steps matched, infer from query_type
        if not steps:
            step_idx += 1
            default_type = {
                "forecast": StepType.REVENUE_PROJECTION,
                "valuation": StepType.VALUATION,
                "stress_test": StepType.REVENUE_PROJECTION,
                "sensitivity": StepType.REVENUE_PROJECTION,
                "regression": StepType.REVENUE_PROJECTION,
                "scenario": StepType.CUSTOM,
            }.get(query_type, StepType.REVENUE_PROJECTION)

            steps.append(ParsedStep(
                type=default_type,
                payload=self._build_step_payload(default_type.value, companies, metrics, params),
                step_id=f"step_{step_idx}",
                temporal_order=step_idx,
            ))

        # For forecasts that mention valuation, chain a valuation step
        if query_type == "forecast" and "valuation" not in matched_types:
            has_val_keyword = any(re.search(r"\bvalu", q))
            if has_val_keyword:
                step_idx += 1
                steps.append(ParsedStep(
                    type=StepType.VALUATION,
                    payload={"companies": companies, "method": "comparables"},
                    step_id=f"step_{step_idx}",
                    temporal_order=step_idx,
                ))

        return steps

    def _build_step_payload(
        self,
        step_type: str,
        companies: List[str],
        metrics: List[str],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"companies": companies}

        if step_type == "revenue_projection":
            payload["metric"] = metrics[0] if metrics else "arr"
            payload["periods"] = params.get("periods", 3)
            payload["period_unit"] = params.get("period_unit", "year")
        elif step_type == "valuation":
            payload["method"] = "comparables"
        elif step_type == "growth_change":
            payload["metric"] = metrics[0] if metrics else "growth"
            payload["change_pct"] = params.get("percentages", [0])[0] if params.get("percentages") else None
        elif step_type == "exit_event":
            payload["exit_type"] = "ipo"  # could refine from query
        elif step_type == "funding_event":
            payload["amount"] = params.get("amounts", [0])[0] if params.get("amounts") else None

        return payload
