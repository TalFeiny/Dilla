"""
Natural Language Scenario Composer
Takes freeform "what if" questions and builds world model scenarios
"What happens if growth decelerates in YX in year 2, but Tundex starts a commercial pilot with a tier 1 aerospace company"

Also parses multi-company growth path queries into ScenarioTree inputs:
"What happens if Tyhex grows at 30% then 20%, or Endex grows at 140%, 160%, 100%?"
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class ScenarioEvent:
    """An event in a scenario"""
    entity_name: str  # Company name (e.g., "YX", "Tundex")
    event_type: str  # "growth_change", "partnership", "pilot", "funding", "exit", etc.
    event_description: str
    timing: Optional[str] = None  # "year 2", "Q3 2025", "in 6 months"
    parameters: Dict[str, Any] = field(default_factory=dict)  # Event-specific parameters
    impact_factors: List[str] = field(default_factory=list)  # Which factors this affects


@dataclass
class ComposedScenario:
    """A scenario composed from natural language"""
    scenario_name: str
    events: List[ScenarioEvent]
    description: str
    probability: float = 0.5


class NLScenarioComposer:
    """
    Composes world model scenarios from natural language "what if" questions
    """
    
    # Event patterns
    EVENT_PATTERNS = {
        "growth_change": [
            r"growth (decelerates|accelerates|slows|increases|decreases)",
            r"(deceleration|acceleration) (in|of) growth",
            r"growth rate (drops|rises|falls|goes up|goes down)",
            r"revenue growth (slows|accelerates|stalls)"
        ],
        "partnership": [
            r"starts? (a|an) (partnership|pilot|commercial pilot|pilot program)",
            r"partners? with",
            r"signs? (a|an) (deal|agreement|contract)",
            r"launches? (a|an) (pilot|pilot program)"
        ],
        "funding": [
            r"raises? (funding|capital|money|a round)",
            r"closes? (a|an) (round|funding round)",
            r"gets? (funded|investment)"
        ],
        "exit": [
            r"gets? (acquired|bought|sold)",
            r"exits? (via|through) (acquisition|IPO|merger)",
            r"goes? (public|IPO)"
        ],
        "competitive": [
            r"competitor (enters|launches|releases)",
            r"new (competitor|player) (enters|launches)",
            r"market (share|position) (drops|increases|changes)"
        ],
        "operational": [
            r"hires? (key|senior|executive)",
            r"loses? (key|senior|executive)",
            r"opens? (office|facility)",
            r"expands? (to|into)"
        ],
        "regulatory": [
            r"regulatory (change|approval|rejection)",
            r"gets? (approved|rejected) (by|from) (regulator|FDA|SEC)"
        ]
    }
    
    # Timing patterns
    TIMING_PATTERNS = [
        (r"(in|by|during) year (\d+)", lambda m: f"year_{m.group(2)}"),
        (r"(in|by|during) (Q[1-4]) (\d{4})", lambda m: f"{m.group(2)}_{m.group(3)}"),
        (r"(in|by|during) (\d{4})", lambda m: f"year_{m.group(2)}"),
        (r"(in|within) (\d+) (months?|weeks?|years?)", lambda m: f"{m.group(2)}_{m.group(3)}"),
        (r"next (year|quarter|month)", lambda m: "next_period"),
        (r"this (year|quarter|month)", lambda m: "current_period"),
    ]
    
    # Entity extraction patterns
    ENTITY_PATTERNS = [
        r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b",  # Capitalized words (company names)
        r"(\w+)\s+(?:company|startup|firm)",  # "YX company"
    ]
    
    def __init__(self):
        pass
    
    async def parse_what_if_query(
        self,
        query: str,
        fund_id: Optional[str] = None
    ) -> ComposedScenario:
        """
        Parse a "what if" query into a composed scenario
        
        Examples:
        - "What happens if growth decelerates in YX in year 2"
        - "What happens if Tundex starts a commercial pilot with a tier 1 aerospace company"
        - "What if YX growth slows in Q2 but Tundex gets a major partnership"
        """
        # Normalize query
        query = query.lower().strip()
        
        # Remove "what happens if" / "what if" prefix
        query = re.sub(r"^(what happens if|what if|if)\s+", "", query, flags=re.IGNORECASE)
        
        # Split by conjunctions to find multiple events
        events = []
        
        # Split by "but", "and", "while", ","
        parts = re.split(r"\s+(but|and|while|,)\s+", query)
        
        for part in parts:
            part = part.strip()
            if not part or part in ["but", "and", "while", ","]:
                continue
            
            event = self._parse_event(part, fund_id)
            if event:
                events.append(event)
        
        # If no events found, try parsing the whole query as one event
        if not events:
            event = self._parse_event(query, fund_id)
            if event:
                events.append(event)
        
        # Generate scenario name
        scenario_name = self._generate_scenario_name(events)
        
        return ComposedScenario(
            scenario_name=scenario_name,
            events=events,
            description=query,
            probability=0.5  # Default probability
        )
    
    def _parse_event(self, text: str, fund_id: Optional[str] = None) -> Optional[ScenarioEvent]:
        """Parse a single event from text"""
        text_lower = text.lower()
        
        # Find event type
        event_type = None
        for evt_type, patterns in self.EVENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    event_type = evt_type
                    break
            if event_type:
                break
        
        if not event_type:
            # Default to "custom" event
            event_type = "custom"
        
        # Extract entity name
        entity_name = self._extract_entity(text)
        
        # Extract timing
        timing = self._extract_timing(text)
        
        # Extract parameters based on event type
        parameters = self._extract_parameters(text, event_type)
        
        # Determine impact factors
        impact_factors = self._determine_impact_factors(event_type, parameters)
        
        return ScenarioEvent(
            entity_name=entity_name,
            event_type=event_type,
            event_description=text,
            timing=timing,
            parameters=parameters,
            impact_factors=impact_factors
        )
    
    def _extract_entity(self, text: str) -> str:
        """Extract entity (company) name from text"""
        # Try to find capitalized words (likely company names)
        # First, try to match known company names from context
        # For now, extract capitalized words
        
        # Look for patterns like "YX", "Tundex", etc.
        capitalized = re.findall(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b", text)
        if capitalized:
            # Return the first capitalized phrase (likely company name)
            return capitalized[0]
        
        # Fallback: extract first significant word
        words = text.split()
        for word in words:
            if word[0].isupper() and len(word) > 2:
                return word
        
        return "Unknown"
    
    def _extract_timing(self, text: str) -> Optional[str]:
        """Extract timing information from text"""
        text_lower = text.lower()
        
        for pattern, formatter in self.TIMING_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    return formatter(match)
                except:
                    return match.group(0)
        
        return None
    
    def _extract_parameters(self, text: str, event_type: str) -> Dict[str, Any]:
        """Extract event-specific parameters"""
        params = {}
        text_lower = text.lower()
        
        if event_type == "growth_change":
            # Extract direction and magnitude
            if "decelerate" in text_lower or "slow" in text_lower or "drop" in text_lower:
                params["direction"] = "decrease"
            elif "accelerate" in text_lower or "increase" in text_lower or "rise" in text_lower:
                params["direction"] = "increase"
            
            # Try to extract percentage
            pct_match = re.search(r"(\d+)%", text)
            if pct_match:
                params["magnitude"] = float(pct_match.group(1))
            else:
                # Default magnitude based on direction
                params["magnitude"] = 0.3 if params.get("direction") == "decrease" else 0.2
        
        elif event_type == "partnership":
            # Extract partner type/name
            if "tier 1" in text_lower or "tier-1" in text_lower:
                params["partner_tier"] = "tier_1"
            elif "tier 2" in text_lower or "tier-2" in text_lower:
                params["partner_tier"] = "tier_2"
            
            # Extract industry
            industries = ["aerospace", "automotive", "healthcare", "finance", "tech"]
            for industry in industries:
                if industry in text_lower:
                    params["industry"] = industry
                    break
            
            # Extract pilot type
            if "commercial pilot" in text_lower:
                params["pilot_type"] = "commercial"
            elif "pilot" in text_lower:
                params["pilot_type"] = "pilot"
        
        elif event_type == "funding":
            # Extract round type
            round_types = ["seed", "series a", "series b", "series c", "growth"]
            for round_type in round_types:
                if round_type in text_lower:
                    params["round_type"] = round_type
                    break
            
            # Try to extract amount
            amount_match = re.search(r"\$?(\d+(?:\.\d+)?)\s*(million|m|billion|b)", text_lower)
            if amount_match:
                amount = float(amount_match.group(1))
                multiplier = 1_000_000 if amount_match.group(2)[0] == "m" else 1_000_000_000
                params["amount"] = amount * multiplier
        
        return params
    
    def _determine_impact_factors(
        self,
        event_type: str,
        parameters: Dict[str, Any]
    ) -> List[str]:
        """Determine which factors this event impacts"""
        impact_map = {
            "growth_change": ["growth_rate", "revenue", "revenue_projection", "valuation"],
            "partnership": ["revenue", "competitive_position", "market_sentiment", "revenue_projection"],
            "funding": ["valuation", "burn_rate", "runway", "market_sentiment"],
            "exit": ["valuation", "exit_value", "dpi", "tvpi"],
            "competitive": ["competitive_position", "market_share", "revenue", "market_sentiment"],
            "operational": ["execution_quality", "team_quality", "burn_rate"],
            "regulatory": ["market_sentiment", "operational_efficiency", "revenue"],
            "custom": ["market_sentiment"]  # Default impact
        }
        
        return impact_map.get(event_type, ["market_sentiment"])
    
    def _generate_scenario_name(self, events: List[ScenarioEvent]) -> str:
        """Generate a scenario name from events"""
        if len(events) == 1:
            event = events[0]
            return f"{event.entity_name}: {event.event_type.replace('_', ' ').title()}"
        else:
            entity_names = [e.entity_name for e in events]
            return f"Multi-Event: {', '.join(set(entity_names))}"
    
    async def compose_scenario_to_world_model(
        self,
        composed_scenario: ComposedScenario,
        model_id: str,
        fund_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert a composed scenario into a world model scenario with factor overrides
        """
        from app.services.scenario_analyzer import ScenarioAnalyzer
        from app.services.world_model_builder import WorldModelBuilder
        from app.core.database import supabase_service
        
        scenario_analyzer = ScenarioAnalyzer()
        model_builder = WorldModelBuilder()
        
        # Get world model
        model_data = await model_builder.get_model(model_id)
        entities = model_data.get("entities", [])
        factors = model_data.get("factors", [])
        
        # Map entity names to entity IDs
        entity_map = {}
        for entity in entities:
            entity_name_lower = entity.get("entity_name", "").lower()
            entity_map[entity_name_lower] = entity["id"]
        
        # Build factor overrides from events
        factor_overrides = {}
        
        for event in composed_scenario.events:
            # Find entity
            entity_id = None
            entity_name_lower = event.entity_name.lower()
            for name, eid in entity_map.items():
                if entity_name_lower in name or name in entity_name_lower:
                    entity_id = eid
                    break
            
            if not entity_id:
                # Try to find by exact match or create new entity
                # For now, skip if entity not found
                logger.warning(f"Entity {event.entity_name} not found in model")
                continue
            
            # Find factors for this entity
            entity_factors = [f for f in factors if f.get("entity_id") == entity_id]
            
            # Apply event impacts to factors
            for impact_factor_name in event.impact_factors:
                # Find matching factor
                matching_factor = next(
                    (f for f in entity_factors if f.get("factor_name") == impact_factor_name),
                    None
                )
                
                if not matching_factor:
                    continue
                
                factor_id = matching_factor["id"]
                current_value = matching_factor.get("current_value", 0) or 0
                
                # Calculate new value based on event
                new_value = self._calculate_event_impact(
                    current_value,
                    event,
                    impact_factor_name
                )
                
                factor_overrides[factor_id] = new_value
        
        # Create scenario in world model
        scenario = await scenario_analyzer.create_scenario(
            model_id=model_id,
            scenario_name=composed_scenario.scenario_name,
            scenario_type="custom",
            probability=composed_scenario.probability,
            factor_overrides=factor_overrides,
            description=composed_scenario.description
        )
        
        return {
            "scenario": scenario,
            "composed_scenario": composed_scenario,
            "factor_overrides": factor_overrides
        }
    
    def _calculate_event_impact(
        self,
        current_value: Any,
        event: ScenarioEvent,
        factor_name: str
    ) -> Any:
        """Calculate new factor value based on event impact"""
        if not isinstance(current_value, (int, float)):
            return current_value
        
        params = event.parameters
        
        if event.event_type == "growth_change":
            if factor_name == "growth_rate":
                direction = params.get("direction", "decrease")
                magnitude = params.get("magnitude", 0.3)
                
                if direction == "decrease":
                    return current_value * (1 - magnitude)
                else:
                    return current_value * (1 + magnitude)
            
            elif factor_name in ["revenue", "revenue_projection"]:
                # Revenue impact from growth change
                direction = params.get("direction", "decrease")
                magnitude = params.get("magnitude", 0.3)
                
                if direction == "decrease":
                    return current_value * (1 - magnitude * 0.5)  # Revenue impact is less than growth impact
                else:
                    return current_value * (1 + magnitude * 0.5)
        
        elif event.event_type == "partnership":
            if factor_name == "revenue":
                # Partnership could add revenue
                partner_tier = params.get("partner_tier", "tier_2")
                if partner_tier == "tier_1":
                    return current_value * 1.2  # 20% boost from tier 1 partnership
                else:
                    return current_value * 1.1  # 10% boost
            
            elif factor_name == "competitive_position":
                # Partnership improves competitive position
                return min(100, current_value + 15)  # +15 points
        
        elif event.event_type == "funding":
            if factor_name == "valuation":
                # Funding round increases valuation
                amount = params.get("amount", 0)
                if amount > 0:
                    # Rough estimate: valuation = funding amount / ownership %
                    # For now, assume 20% ownership
                    return amount / 0.2
        
        # Default: no change
        return current_value
    
    # ------------------------------------------------------------------
    # Direct NL → driver mapping (fast path for "cut burn 20%", etc.)
    # ------------------------------------------------------------------

    # Patterns that map natural language to driver_id + value extraction
    DIRECT_DRIVER_PATTERNS: List[Tuple[str, str, str]] = [
        # (regex, driver_id, value_mode)
        # value_mode: "pct_of" (extract % → decimal), "abs" (extract $ amount),
        # "shift" (extract signed number), "pct_cut" (% → negative decimal)

        # Burn rate
        (r"(?:cut|reduce|lower|decrease)\s+burn\s+(?:rate\s+)?(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "burn_rate", "pct_cut"),
        (r"(?:increase|raise|grow)\s+burn\s+(?:rate\s+)?(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "burn_rate", "pct_raise"),
        (r"set\s+burn\s+(?:rate\s+)?(?:to\s+)?\$?([\d,.]+)(?:k|K)", "burn_rate", "abs_k"),

        # Revenue growth
        (r"(?:set|make|change)\s+(?:revenue\s+)?growth\s+(?:rate\s+)?(?:to\s+)?(\d+(?:\.\d+)?)\s*%", "revenue_growth", "pct_of"),
        (r"(?:increase|raise|grow)\s+(?:revenue\s+)?growth\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "revenue_growth", "pct_of"),
        (r"(?:cut|reduce|lower|decrease|slow)\s+(?:revenue\s+)?growth\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*%", "revenue_growth", "pct_of"),

        # Headcount
        (r"(?:hire|add)\s+(\d+)\s+(?:people|employees|heads?|engineers?|staff)", "headcount_change", "shift"),
        (r"(?:cut|fire|layoff|lay off|reduce)\s+(\d+)\s+(?:people|employees|heads?|engineers?|staff)", "headcount_change", "shift_neg"),
        (r"(?:increase|grow)\s+headcount\s+(?:by\s+)?(\d+)", "headcount_change", "shift"),
        (r"(?:reduce|cut|decrease)\s+headcount\s+(?:by\s+)?(\d+)", "headcount_change", "shift_neg"),

        # Gross margin
        (r"(?:set|change|make)\s+(?:gross\s+)?margin\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*%", "gross_margin", "pct_of"),

        # R&D spend
        (r"(?:cut|reduce|lower)\s+(?:r&d|rd|R&D|research)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "rd_pct", "pct_cut"),
        (r"(?:increase|raise|grow)\s+(?:r&d|rd|R&D|research)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "rd_pct", "pct_raise"),

        # S&M spend
        (r"(?:cut|reduce|lower)\s+(?:s&m|sm|S&M|sales|marketing)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "sm_pct", "pct_cut"),
        (r"(?:increase|raise|grow)\s+(?:s&m|sm|S&M|sales|marketing)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "sm_pct", "pct_raise"),

        # G&A spend
        (r"(?:cut|reduce|lower)\s+(?:g&a|ga|G&A|admin|overhead)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "ga_pct", "pct_cut"),

        # Funding / raise
        (r"(?:raise|inject|get|close)\s+\$?([\d,.]+)\s*([mMbB])", "funding_injection", "abs_mb"),

        # Pricing
        (r"(?:increase|raise)\s+pric(?:es?|ing)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "pricing_change", "pct_of"),
        (r"(?:cut|reduce|lower|decrease)\s+pric(?:es?|ing)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%", "pricing_change", "pct_cut"),
    ]

    def parse_direct_driver_query(
        self,
        query: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Fast path: detect direct driver language and return driver changes.

        Returns a list of {driver_id, value} dicts if the query maps directly
        to driver adjustments. Returns None if no direct mapping found (caller
        should fall through to macro event pipeline).

        Examples:
            "cut burn 20%" → [{"driver_id": "burn_rate", "value": -0.20}]
            "hire 10 engineers" → [{"driver_id": "headcount_change", "value": 10}]
            "raise $5M" → [{"driver_id": "funding_injection", "value": 5_000_000}]
        """
        query_lower = query.lower().strip()
        # Strip leading "what if" etc.
        query_lower = re.sub(r"^(what\s+(?:happens?\s+)?if|if)\s+(?:we\s+)?", "", query_lower)

        results: List[Dict[str, Any]] = []
        matched_spans: List[Tuple[int, int]] = []

        # Try to split by "and" to handle compound queries
        parts = re.split(r"\s+and\s+", query_lower)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            for pattern, driver_id, value_mode in self.DIRECT_DRIVER_PATTERNS:
                match = re.search(pattern, part, re.IGNORECASE)
                if not match:
                    continue

                raw = match.group(1)
                raw_clean = raw.replace(",", "")

                try:
                    if value_mode == "pct_of":
                        value = float(raw_clean) / 100.0
                    elif value_mode == "pct_cut":
                        value = -float(raw_clean) / 100.0
                    elif value_mode == "pct_raise":
                        value = float(raw_clean) / 100.0
                    elif value_mode == "abs":
                        value = float(raw_clean)
                    elif value_mode == "abs_k":
                        value = float(raw_clean) * 1_000
                    elif value_mode == "abs_mb":
                        multiplier_char = match.group(2).lower()
                        mult = 1_000_000 if multiplier_char == "m" else 1_000_000_000
                        value = float(raw_clean) * mult
                    elif value_mode == "shift":
                        value = int(float(raw_clean))
                    elif value_mode == "shift_neg":
                        value = -int(float(raw_clean))
                    else:
                        value = float(raw_clean)
                except (ValueError, TypeError):
                    continue

                results.append({"driver_id": driver_id, "value": value})
                break  # first pattern match per part wins

        return results if results else None

    # ------------------------------------------------------------------
    # Scenario tree growth path parsing
    # ------------------------------------------------------------------

    # Patterns for "X grows at 30% then 20%" or "X at 140%, 160%, 100%"
    GROWTH_PATH_PATTERN = re.compile(
        r"(\w[\w\s]*?)\s+(?:grows?|at)\s+(?:at|by)?\s*"
        r"([\d.]+%(?:\s*(?:then|,|and)\s*[\d.]+%)*)",
        re.IGNORECASE,
    )

    # Pattern to split comma/then-separated rates
    RATE_SPLIT_PATTERN = re.compile(r"[\d.]+%")

    # Pattern to detect branching: "or Endex grows at ..."
    BRANCH_SPLIT_PATTERN = re.compile(
        r"\s+or\s+",
        re.IGNORECASE,
    )

    def parse_scenario_tree_query(
        self,
        query: str,
        known_companies: Optional[List[str]] = None,
    ) -> Optional[Dict[str, List[Any]]]:
        """
        Parse a multi-company growth path query into GrowthPath objects.

        Examples:
            "What happens if Tyhex grows at 30% then 20%, or Endex grows at 140%, 160%, 100%"
            → {"Tyhex": [GrowthPath(...)], "Endex": [GrowthPath(...)]}

            "Tyhex at 30% then 20% or 50% then 40%"
            → {"Tyhex": [GrowthPath(rates=[0.30, 0.20]), GrowthPath(rates=[0.50, 0.40])]}

        Returns None if the query doesn't look like a growth path query.
        """
        from app.services.scenario_tree_service import GrowthPath

        # Normalize
        text = query.strip()
        text = re.sub(r"^(what happens if|what if|if)\s+", "", text, flags=re.IGNORECASE)

        # Split by "or" to find branches
        branches = self.BRANCH_SPLIT_PATTERN.split(text)

        company_paths: Dict[str, List[GrowthPath]] = {}
        found_any = False

        for branch in branches:
            branch = branch.strip()
            if not branch:
                continue

            match = self.GROWTH_PATH_PATTERN.search(branch)
            if not match:
                continue

            found_any = True
            raw_name = match.group(1).strip()
            raw_rates = match.group(2)

            # Resolve company name against known companies
            company_name = self._resolve_company_name(raw_name, known_companies)

            # Extract percentage values
            rate_matches = self.RATE_SPLIT_PATTERN.findall(raw_rates)
            rates = []
            for r in rate_matches:
                val = float(r.replace("%", "")) / 100.0
                rates.append(val)

            if not rates:
                continue

            path = GrowthPath(
                company_name=company_name,
                yearly_growth_rates=rates,
                label=f"{company_name} {' → '.join(f'{r:.0%}' for r in rates)}",
                probability=0.5,
            )

            company_paths.setdefault(company_name, []).append(path)

        if not found_any:
            return None

        # Assign probabilities: if a company has N paths, each gets 1/N
        for paths in company_paths.values():
            n = len(paths)
            for p in paths:
                p.probability = 1.0 / n

        return company_paths

    def _resolve_company_name(
        self,
        raw_name: str,
        known_companies: Optional[List[str]] = None,
    ) -> str:
        """Fuzzy-match a company name from query against known portfolio companies."""
        if not known_companies:
            return raw_name.strip().title()

        raw_lower = raw_name.strip().lower()
        for kc in known_companies:
            if raw_lower == kc.lower() or raw_lower in kc.lower() or kc.lower() in raw_lower:
                return kc
        return raw_name.strip().title()

    def is_scenario_tree_query(self, query: str) -> bool:
        """Quick check: does this query look like a growth path / scenario tree query?"""
        q = query.lower()
        patterns = [
            r"\d+%\s*(?:then|,)\s*\d+%",             # "30% then 20%" or "30%, 20%"
            r"grows?\s+(?:at|by)\s+\d+%",             # "grows at 30%"
            r"what happens if.*\d+%.*\d+%",            # "what happens if ... 30% ... 20%"
            r"(?:growth|scenario)\s+(?:tree|path)",    # explicit "scenario tree"
        ]
        return any(re.search(p, q) for p in patterns)


    def is_bull_bear_base_query(self, query: str) -> bool:
        """Check if query is asking for bull/bear/base scenarios."""
        q = query.lower()
        patterns = [
            r"bull.*bear.*base",
            r"bear.*bull.*base",
            r"base.*bull.*bear",
            r"bull\s+(?:and|\/|,)\s+bear",
            r"upside.*downside",
            r"best.*worst.*case",
            r"optimistic.*pessimistic",
            r"three\s+scenario",
            r"3\s+scenario",
            r"scenario\s+analysis",
        ]
        return any(re.search(p, q) for p in patterns)

    def parse_bull_bear_base_query(self, query: str, known_companies: Optional[List[str]] = None) -> Dict[str, Any]:
        """Parse a bull/bear/base query. Returns {companies: [str], years: int}."""
        q = query.lower()
        # Extract company names
        companies = []
        if known_companies:
            for kc in known_companies:
                if kc.lower() in q:
                    companies.append(kc)
        if not companies:
            # Try capitalized words
            caps = re.findall(r"([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+)*)", query)
            companies = [self._resolve_company_name(c, known_companies) for c in caps]

        # Extract years
        yr_match = re.search(r"(\d+)\s*(?:year|yr)", q)
        years = int(yr_match.group(1)) if yr_match else 5

        return {"companies": companies or [], "years": years}

    def is_macro_shock_query(self, query: str) -> bool:
        """
        Detect if a query describes a macro/geopolitical/systemic event
        that should be routed to analyse_macro_event rather than
        company-specific what-if parsing.

        Uses semantic heuristics — checks whether the query describes an
        external force affecting the portfolio (vs a company-specific action).
        """
        q = query.lower()

        # Portfolio-impact phrasing — strongest signal regardless of event type
        impact_phrases = [
            "impact on my", "affect my portfolio", "affect my pnl",
            "impact on our", "affect our", "impact on the portfolio",
            "what does .* mean for", "how does .* affect",
            "implications for", "exposure to",
        ]
        if any(re.search(p, q) for p in impact_phrases):
            return True

        # The query describes an external event (not a company action)
        # Heuristic: does NOT mention a specific company action
        # (e.g. "Tundex gets a contract" is company-specific, not macro)
        company_action_signals = [
            r"\b\w+\s+(gets?|wins?|loses?|launches?|hires?|fires?|raises?|closes?)\b",
            r"\bgrowth (slows?|accelerates?|decelerates?)\s+(in|at|for)\s+\w+",
        ]
        has_company_action = any(re.search(p, q) for p in company_action_signals)

        # External event signals — broad semantic categories
        external_event_patterns = [
            # Geopolitical
            r"\b(war|conflict|invasion|sanctions?|embargo|blockade|coup|revolt)\b",
            r"\b(iran|china|taiwan|russia|ukraine|north korea|israel|gaza)\b.*\b(war|conflict|attack|tension)",
            # Economic/monetary
            r"\b(recession|depression|rate (hike|cut|change)|interest rate|inflation|deflation|stagflation)\b",
            r"\b(fed |ecb |central bank|monetary policy|quantitative)\b",
            r"\b(credit crunch|bank run|liquidity crisis|sovereign debt|default)\b",
            # Market
            r"\b(market (crash|correction|boom|bubble|collapse|rally))\b",
            r"\b(bear market|bull market|black swan|flash crash|melt-?up|melt-?down)\b",
            r"\b(crypto (crash|collapse|ban)|housing (crash|bubble|crisis))\b",
            # Policy/regulatory
            r"\b(tariff|trade war|ban|antitrust|break.?up|regulation|deregulat|legislation)\b",
            r"\b(ai act|section 230|gdpr|data privacy|carbon tax|green deal)\b",
            r"\b(tax (hike|cut|reform)|subsid|nationali[sz])\b",
            # Supply chain / resource
            r"\b(supply chain|chip shortage|semiconductor|suez|panama canal)\b",
            r"\b(oil (spike|shock|embargo|price)|energy crisis|commodity)\b",
            r"\b(food (crisis|shortage)|grain|wheat|fertilizer)\b",
            # Systemic
            r"\b(pandemic|epidemic|outbreak|covid|lockdown)\b",
            r"\b(ai winter|tech (bubble|crash)|dot.?com)\b",
            r"\b(climate|natural disaster|earthquake|hurricane|flood|wildfire)\b",
            # Generic macro
            r"\b(macro|geopolitical|systemic|exogenous|global)\b",
            r"\b(downturn|slowdown|contraction|tightening|easing)\b",
        ]
        has_external = any(re.search(p, q) for p in external_event_patterns)

        # If it looks like an external event and NOT a company-specific action
        if has_external and not has_company_action:
            return True

        # Catch "what if there is a ..." or "what if the [market/economy/world]..."
        if re.search(r"what (if|happens).*(there is|the (market|economy|world|fed|government))", q):
            return True

        return False

    def parse_macro_shock_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a macro event query. Returns the event description directly
        instead of mapping to hardcoded shock types — the LLM service
        does the real reasoning.

        For backwards compatibility, also infers magnitude and passes
        the raw event to analyse_macro_event.
        """
        q = query.lower()

        # Strip "what if" / "what happens if" prefix to get the event
        event = re.sub(
            r"^(what happens if|what if|if|analyse|analyze|impact of|how does)\s+",
            "", q, flags=re.IGNORECASE,
        ).strip()
        # Strip trailing "on my portfolio/pnl/companies/scenarios"
        event = re.sub(
            r"\s+(on my|on our|on the|for my|for our)\s+(portfolio|pnl|companies|scenarios|fund|investments?).*$",
            "", event, flags=re.IGNORECASE,
        ).strip()

        # Magnitude from severity language
        magnitude = 0.5
        if any(w in q for w in ["severe", "major", "deep", "worst", "catastrophic", "extreme"]):
            magnitude = 0.8
        elif any(w in q for w in ["mild", "minor", "slight", "small", "modest"]):
            magnitude = 0.3

        # Start year
        yr_match = re.search(r"(?:in |at |year\s*)(\d+)", q)
        start_year = int(yr_match.group(1)) if yr_match else 1

        return {
            "event": event,
            "magnitude": magnitude,
            "start_year": start_year,
            # Legacy field for backwards compatibility with _tool_macro_shock
            "shock_type": event,
        }

    def is_cash_flow_query(self, query: str) -> bool:
        """Check if query is asking for cash flow / P&L modeling."""
        q = query.lower()
        return any(w in q for w in [
            "cash flow", "p&l", "profit and loss", "runway",
            "burn rate", "funding gap", "ebitda", "free cash flow",
            "fcf", "opex", "operating expense",
        ])

    def is_snapshot_query(self, query: str) -> bool:
        """Check if query is asking for a point-in-time portfolio snapshot."""
        q = query.lower()
        return any(w in q for w in [
            "snapshot", "point in time", "at year", "in year",
            "what does the portfolio look like",
            "nav at", "where are we",
        ])

    async def apply_scenario_to_matrix(
        self,
        composed_scenario: ComposedScenario,
        matrix_data: Dict[str, Any],
        fund_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply a composed scenario to matrix data and return cell updates
        
        Args:
            composed_scenario: The composed scenario from parse_what_if_query
            matrix_data: Matrix data structure with rows and columns
            fund_id: Optional fund ID for context
        
        Returns:
            {
                "cell_updates": [
                    {
                        "row_id": "...",
                        "column_id": "growth_rate",
                        "old_value": 0.5,
                        "new_value": 0.35,
                        "change": -0.15,
                        "change_pct": -30
                    }
                ]
            }
        """
        from app.services.matrix_scenario_service import MatrixScenarioService
        
        # Use MatrixScenarioService for the actual application
        service = MatrixScenarioService()
        
        # Reconstruct query from scenario for service
        query = composed_scenario.description
        
        return await service.apply_scenario_to_matrix(query, matrix_data, fund_id)
