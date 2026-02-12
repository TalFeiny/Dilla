"""
Scenario Analysis Engine
Multi-dimensional scenario modeling with probability weighting
Handles market, competitive, operational, and financial scenarios
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from app.core.database import supabase_service
from app.services.world_model_builder import WorldModelBuilder
from app.services.pwerm_comprehensive import ComprehensivePWERM

logger = logging.getLogger(__name__)


class ScenarioType(str, Enum):
    BASE_CASE = "base_case"
    UPSIDE = "upside"
    DOWNSIDE = "downside"
    STRESS = "stress"
    CUSTOM = "custom"


@dataclass
class ScenarioFactorOverride:
    """Override for a factor in a scenario"""
    factor_id: str
    new_value: Any
    reason: str = ""


@dataclass
class ScenarioDefinition:
    """Complete scenario definition"""
    scenario_name: str
    scenario_type: ScenarioType
    probability: float
    factor_overrides: List[ScenarioFactorOverride] = field(default_factory=list)
    relationship_changes: Dict[str, Any] = field(default_factory=dict)
    temporal_changes: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


class ScenarioAnalyzer:
    """
    Analyzes scenarios across multiple dimensions (market, competitive, operational, financial)
    """
    
    def __init__(self):
        self.model_builder = WorldModelBuilder()
        self.pwerm = ComprehensivePWERM()
    
    async def create_scenario(
        self,
        model_id: str,
        scenario_name: str,
        scenario_type: ScenarioType,
        probability: float = 0.33,
        factor_overrides: Optional[Dict[str, Any]] = None,
        relationship_changes: Optional[Dict[str, Any]] = None,
        temporal_changes: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a scenario for a world model
        
        Args:
            model_id: World model ID
            scenario_name: Name of the scenario
            scenario_type: Type of scenario
            probability: Probability of this scenario (should sum to 1.0 for all scenarios)
            factor_overrides: { factor_id: new_value } - factor value overrides
            relationship_changes: Changes to relationships
            temporal_changes: Changes to temporal dynamics
            description: Scenario description
            
        Returns:
            Created scenario record
        """
        scenario_data = {
            "model_id": model_id,
            "scenario_name": scenario_name,
            "scenario_type": scenario_type.value,
            "probability": probability,
            "factor_overrides": factor_overrides or {},
            "relationship_changes": relationship_changes or {},
            "temporal_changes": temporal_changes or {},
            "description": description or ""
        }
        
        result = supabase_service.client.table("world_model_scenarios").insert(scenario_data).execute()
        return result.data[0] if result.data else {}
    
    async def execute_scenario(
        self,
        scenario_id: str
    ) -> Dict[str, Any]:
        """
        Execute a scenario and calculate results
        
        Args:
            scenario_id: Scenario ID to execute
            
        Returns:
            Scenario results with factor values and model outputs
        """
        # Get scenario
        scenario_result = supabase_service.client.table("world_model_scenarios").select("*").eq("id", scenario_id).execute()
        if not scenario_result.data:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        scenario = scenario_result.data[0]
        model_id = scenario["model_id"]
        
        # Get world model
        model_data = await self.model_builder.get_model(model_id)
        factors = model_data.get("factors", [])
        factor_map = {f["id"]: f for f in factors}
        
        # Apply factor overrides
        factor_overrides = scenario.get("factor_overrides", {})
        scenario_factors = {}
        
        for factor in factors:
            factor_id = factor["id"]
            if factor_id in factor_overrides:
                # Use override value
                scenario_factors[factor_id] = {
                    "factor_id": factor_id,
                    "factor_name": factor["factor_name"],
                    "base_value": factor.get("current_value"),
                    "scenario_value": factor_overrides[factor_id],
                    "change": self._calculate_change(factor.get("current_value"), factor_overrides[factor_id])
                }
            else:
                # Use base value
                scenario_factors[factor_id] = {
                    "factor_id": factor_id,
                    "factor_name": factor["factor_name"],
                    "base_value": factor.get("current_value"),
                    "scenario_value": factor.get("current_value"),
                    "change": 0
                }
        
        # Calculate model outputs (e.g., valuation, NAV)
        model_outputs = await self._calculate_model_outputs(
            model_data,
            scenario_factors,
            scenario
        )
        
        # Perform sensitivity analysis
        sensitivity = await self._analyze_sensitivity(
            model_data,
            scenario_factors,
            model_outputs
        )
        
        # Store results
        result_data = {
            "scenario_id": scenario_id,
            "factor_results": {k: v["scenario_value"] for k, v in scenario_factors.items()},
            "model_outputs": model_outputs,
            "sensitivity_analysis": sensitivity
        }
        
        result = supabase_service.client.table("world_model_scenario_results").insert(result_data).execute()
        
        return {
            "scenario": scenario,
            "results": result.data[0] if result.data else {},
            "factor_changes": scenario_factors,
            "model_outputs": model_outputs,
            "sensitivity": sensitivity
        }
    
    async def _calculate_model_outputs(
        self,
        model_data: Dict[str, Any],
        scenario_factors: Dict[str, Any],
        scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate final model outputs for a scenario"""
        outputs = {}
        
        # Extract key factors
        valuation_factor = None
        revenue_factor = None
        growth_factor = None
        
        for factor_id, factor_data in scenario_factors.items():
            factor_name = factor_data["factor_name"]
            if factor_name == "valuation":
                valuation_factor = factor_data["scenario_value"]
            elif factor_name == "revenue":
                revenue_factor = factor_data["scenario_value"]
            elif factor_name == "growth_rate":
                growth_factor = factor_data["scenario_value"]
        
        # Calculate valuation if we have revenue and growth
        if revenue_factor and growth_factor:
            # Simple valuation estimate: revenue * multiple
            # Multiple based on growth rate
            if growth_factor > 1.0:  # >100% growth
                multiple = 15
            elif growth_factor > 0.5:  # >50% growth
                multiple = 10
            else:
                multiple = 7
            
            estimated_valuation = revenue_factor * multiple
            outputs["estimated_valuation"] = estimated_valuation
        
        # Use provided valuation if available
        if valuation_factor:
            outputs["valuation"] = valuation_factor
        
        # Calculate other outputs
        # TODO: Add more sophisticated output calculations
        
        return outputs
    
    async def _analyze_sensitivity(
        self,
        model_data: Dict[str, Any],
        scenario_factors: Dict[str, Any],
        model_outputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze which factors drive the results"""
        sensitivity = {
            "key_drivers": [],
            "factor_impacts": {}
        }
        
        # Calculate impact of each factor change on outputs
        base_outputs = {}  # Would need to calculate base case outputs
        scenario_outputs = model_outputs
        
        # For now, identify factors with largest changes
        factor_changes = []
        for factor_id, factor_data in scenario_factors.items():
            change = factor_data.get("change", 0)
            if change != 0:
                factor_changes.append({
                    "factor_id": factor_id,
                    "factor_name": factor_data["factor_name"],
                    "change_magnitude": abs(change),
                    "change_pct": self._calculate_pct_change(
                        factor_data["base_value"],
                        factor_data["scenario_value"]
                    )
                })
        
        # Sort by change magnitude
        factor_changes.sort(key=lambda x: x["change_magnitude"], reverse=True)
        sensitivity["key_drivers"] = factor_changes[:5]  # Top 5 drivers
        
        return sensitivity
    
    def _calculate_change(self, base_value: Any, new_value: Any) -> float:
        """Calculate change between base and new value"""
        try:
            if isinstance(base_value, (int, float)) and isinstance(new_value, (int, float)):
                return new_value - base_value
            return 0
        except:
            return 0
    
    def _calculate_pct_change(self, base_value: Any, new_value: Any) -> float:
        """Calculate percentage change"""
        try:
            if isinstance(base_value, (int, float)) and isinstance(new_value, (int, float)):
                if base_value == 0:
                    return 0
                return ((new_value - base_value) / base_value) * 100
            return 0
        except:
            return 0
    
    async def compare_scenarios(
        self,
        model_id: str
    ) -> Dict[str, Any]:
        """
        Compare all scenarios for a model
        
        Returns:
            Comparison of all scenarios with probability-weighted expected values
        """
        # Get all scenarios
        scenarios_result = supabase_service.client.table("world_model_scenarios").select("*").eq("model_id", model_id).execute()
        scenarios = scenarios_result.data or []
        
        if not scenarios:
            return {"error": "No scenarios found for model"}
        
        # Execute all scenarios
        scenario_results = []
        for scenario in scenarios:
            result = await self.execute_scenario(scenario["id"])
            scenario_results.append({
                "scenario": scenario,
                "results": result
            })
        
        # Calculate probability-weighted expected values
        expected_outputs = {}
        for scenario_result in scenario_results:
            scenario = scenario_result["scenario"]
            results = scenario_result["results"]
            probability = scenario.get("probability", 0)
            outputs = results.get("model_outputs", {})
            
            for output_name, output_value in outputs.items():
                if isinstance(output_value, (int, float)):
                    if output_name not in expected_outputs:
                        expected_outputs[output_name] = 0
                    expected_outputs[output_name] += output_value * probability
        
        # Calculate scenario ranges
        scenario_ranges = {}
        for output_name in expected_outputs.keys():
            values = [
                sr["results"]["model_outputs"].get(output_name, 0)
                for sr in scenario_results
                if isinstance(sr["results"]["model_outputs"].get(output_name), (int, float))
            ]
            if values:
                scenario_ranges[output_name] = {
                    "min": min(values),
                    "max": max(values),
                    "expected": expected_outputs[output_name],
                    "std_dev": self._calculate_std_dev(values)
                }
        
        return {
            "scenarios": scenario_results,
            "expected_values": expected_outputs,
            "ranges": scenario_ranges,
            "comparison": self._create_comparison_table(scenario_results)
        }
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def _create_comparison_table(self, scenario_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create a comparison table of scenarios"""
        comparison = []
        
        for sr in scenario_results:
            scenario = sr["scenario"]
            results = sr["results"]
            
            comparison.append({
                "scenario_name": scenario["scenario_name"],
                "scenario_type": scenario["scenario_type"],
                "probability": scenario["probability"],
                "outputs": results.get("model_outputs", {}),
                "key_changes": [
                    {
                        "factor": fc["factor_name"],
                        "change": fc.get("change", 0)
                    }
                    for fc in results.get("factor_changes", {}).values()
                    if fc.get("change", 0) != 0
                ][:3]  # Top 3 changes
            })
        
        return comparison
    
    async def create_standard_scenarios(
        self,
        model_id: str
    ) -> Dict[str, Any]:
        """
        Create standard base case, upside, and downside scenarios
        
        Returns:
            Created scenarios
        """
        # Get model to understand factors
        model_data = await self.model_builder.get_model(model_id)
        factors = model_data.get("factors", [])
        
        # Find key factors
        revenue_factor = next((f for f in factors if f["factor_name"] == "revenue"), None)
        growth_factor = next((f for f in factors if f["factor_name"] == "growth_rate"), None)
        valuation_factor = next((f for f in factors if f["factor_name"] == "valuation"), None)
        
        scenarios = []
        
        # Base case (50% probability)
        base_overrides = {}
        if revenue_factor:
            base_overrides[revenue_factor["id"]] = revenue_factor.get("current_value")
        if growth_factor:
            base_overrides[growth_factor["id"]] = growth_factor.get("current_value")
        
        base_scenario = await self.create_scenario(
            model_id=model_id,
            scenario_name="Base Case",
            scenario_type=ScenarioType.BASE_CASE,
            probability=0.50,
            factor_overrides=base_overrides,
            description="Base case scenario with current assumptions"
        )
        scenarios.append(base_scenario)
        
        # Upside case (25% probability)
        upside_overrides = {}
        if revenue_factor:
            base_revenue = revenue_factor.get("current_value", 0) or 0
            upside_overrides[revenue_factor["id"]] = base_revenue * 1.3  # 30% higher
        if growth_factor:
            base_growth = growth_factor.get("current_value", 0) or 0
            upside_overrides[growth_factor["id"]] = base_growth * 1.2  # 20% higher
        
        upside_scenario = await self.create_scenario(
            model_id=model_id,
            scenario_name="Upside Case",
            scenario_type=ScenarioType.UPSIDE,
            probability=0.25,
            factor_overrides=upside_overrides,
            description="Upside scenario with accelerated growth"
        )
        scenarios.append(upside_scenario)
        
        # Downside case (25% probability)
        downside_overrides = {}
        if revenue_factor:
            base_revenue = revenue_factor.get("current_value", 0) or 0
            downside_overrides[revenue_factor["id"]] = base_revenue * 0.7  # 30% lower
        if growth_factor:
            base_growth = growth_factor.get("current_value", 0) or 0
            downside_overrides[growth_factor["id"]] = base_growth * 0.8  # 20% lower
        
        downside_scenario = await self.create_scenario(
            model_id=model_id,
            scenario_name="Downside Case",
            scenario_type=ScenarioType.DOWNSIDE,
            probability=0.25,
            factor_overrides=downside_overrides,
            description="Downside scenario with slower growth"
        )
        scenarios.append(downside_scenario)
        
        return {
            "scenarios": scenarios,
            "total_probability": sum(s.get("probability", 0) for s in scenarios)
        }
