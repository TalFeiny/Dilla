"""
Natural Language Scenario Composer
Takes freeform "what if" questions and builds world model scenarios
"What happens if growth decelerates in YX in year 2, but Tundex starts a commercial pilot with a tier 1 aerospace company"
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
