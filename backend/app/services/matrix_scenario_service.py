"""
Matrix Scenario Service
Integrates NLScenarioComposer with matrix data and calculates cell impacts
"""

import logging
from typing import Dict, List, Any, Optional
from app.services.nl_scenario_composer import NLScenarioComposer, ComposedScenario, ScenarioEvent

logger = logging.getLogger(__name__)


class MatrixScenarioService:
    """
    Service that applies scenarios to matrix data and calculates cell impacts
    """
    
    def __init__(self):
        self.scenario_composer = NLScenarioComposer()
    
    async def apply_scenario_to_matrix(
        self,
        query: str,
        matrix_data: Dict[str, Any],
        fund_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply scenario to matrix data
        
        Args:
            query: Natural language "what if" query
            matrix_data: Matrix data structure with rows and columns
            fund_id: Optional fund ID for context
        
        Returns:
            {
                "scenario_id": "...",
                "cell_updates": [
                    {
                        "row_id": "...",
                        "column_id": "growth_rate",
                        "old_value": 0.5,
                        "new_value": 0.35,
                        "change": -0.15,
                        "change_pct": -30
                    }
                ],
                "model_outputs": {
                    "nav_change": -1000000,
                    "valuation_changes": {...}
                }
            }
        """
        # Parse the scenario query
        composed_scenario = await self.scenario_composer.parse_what_if_query(query, fund_id)
        
        # Get matrix rows and columns
        rows = matrix_data.get("rows", [])
        columns = matrix_data.get("columns", [])
        
        # Map company names to row IDs
        company_to_row = {}
        for row in rows:
            company_name = row.get("companyName") or row.get("name") or ""
            if company_name:
                company_to_row[company_name.lower()] = row.get("id")
                # Also try matching without spaces/case
                company_to_row[company_name.replace(" ", "").lower()] = row.get("id")
        
        # Calculate cell updates from scenario events
        cell_updates = []
        valuation_changes = {}
        nav_change = 0
        
        for event in composed_scenario.events:
            # Find matching row
            entity_name_lower = event.entity_name.lower()
            row_id = None
            
            # Try exact match first
            if entity_name_lower in company_to_row:
                row_id = company_to_row[entity_name_lower]
            else:
                # Try partial match
                for company_name, rid in company_to_row.items():
                    if entity_name_lower in company_name or company_name in entity_name_lower:
                        row_id = rid
                        break
            
            if not row_id:
                logger.warning(f"Could not find row for entity: {event.entity_name}")
                continue
            
            # Find the row
            row = next((r for r in rows if r.get("id") == row_id), None)
            if not row:
                continue
            
            # Calculate impacts for each affected factor
            for impact_factor in event.impact_factors:
                # Map impact factor to column ID
                column_id = self._map_factor_to_column(impact_factor, columns)
                if not column_id:
                    continue
                
                # Get current cell value
                cells = row.get("cells", {})
                cell = cells.get(column_id, {})
                old_value = cell.get("value", 0)
                
                # Calculate new value
                new_value = self._calculate_cell_impact(
                    old_value,
                    event,
                    impact_factor
                )
                
                # Calculate change
                change = new_value - old_value if isinstance(old_value, (int, float)) else 0
                change_pct = (change / old_value * 100) if old_value != 0 else 0
                
                cell_updates.append({
                    "row_id": row_id,
                    "column_id": column_id,
                    "old_value": old_value,
                    "new_value": new_value,
                    "change": change,
                    "change_pct": change_pct,
                    "event": event.event_description,
                    "entity": event.entity_name
                })
                
                # Track valuation changes
                if "valuation" in impact_factor.lower() or column_id == "valuation":
                    company_name = row.get("companyName") or row.get("name") or "Unknown"
                    valuation_changes[company_name] = {
                        "old": old_value,
                        "new": new_value,
                        "change": change
                    }
                    nav_change += change
        
        # Generate scenario ID
        scenario_id = f"scenario_{composed_scenario.scenario_name.replace(' ', '_').lower()}"
        
        return {
            "scenario_id": scenario_id,
            "scenario_name": composed_scenario.scenario_name,
            "description": composed_scenario.description,
            "cell_updates": cell_updates,
            "model_outputs": {
                "nav_change": nav_change,
                "valuation_changes": valuation_changes,
                "events_count": len(composed_scenario.events)
            },
            "composed_scenario": {
                "scenario_name": composed_scenario.scenario_name,
                "events": [
                    {
                        "entity_name": e.entity_name,
                        "event_type": e.event_type,
                        "event_description": e.event_description,
                        "timing": e.timing,
                        "impact_factors": e.impact_factors
                    }
                    for e in composed_scenario.events
                ]
            }
        }
    
    def _map_factor_to_column(self, factor_name: str, columns: List[Dict[str, Any]]) -> Optional[str]:
        """Map impact factor name to matrix column ID"""
        # Common mappings
        factor_to_column = {
            "growth_rate": "growth_rate",
            "revenue": "revenue",
            "revenue_projection": "revenue_projection",
            "valuation": "valuation",
            "competitive_position": "competitive_position",
            "market_sentiment": "market_sentiment",
            "burn_rate": "burn_rate",
            "runway": "runway",
            "exit_value": "exit_value",
            "dpi": "dpi",
            "tvpi": "tvpi"
        }
        
        # Try direct mapping
        column_id = factor_to_column.get(factor_name.lower())
        if column_id:
            # Verify column exists
            if any(c.get("id") == column_id for c in columns):
                return column_id
        
        # Try fuzzy match on column names
        factor_lower = factor_name.lower()
        for col in columns:
            col_id = col.get("id", "").lower()
            col_name = col.get("name", "").lower()
            
            if factor_lower in col_id or factor_lower in col_name:
                return col.get("id")
            
            # Check for common variations
            if "growth" in factor_lower and "growth" in col_id:
                return col.get("id")
            if "revenue" in factor_lower and "revenue" in col_id:
                return col.get("id")
            if "valuation" in factor_lower and "valuation" in col_id:
                return col.get("id")
        
        return None
    
    def _calculate_cell_impact(
        self,
        current_value: Any,
        event: ScenarioEvent,
        factor_name: str
    ) -> Any:
        """Calculate new cell value based on event impact"""
        # Use the same logic from NLScenarioComposer
        return self.scenario_composer._calculate_event_impact(
            current_value,
            event,
            factor_name
        )
