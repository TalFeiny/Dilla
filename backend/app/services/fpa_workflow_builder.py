"""
FPA Workflow Builder
Builds workflow steps from parsed queries
"""

import logging
from typing import List, Dict, Any
from pydantic import BaseModel

from app.services.nl_fpa_parser import ParsedQuery, ParsedStep

logger = logging.getLogger(__name__)


class WorkflowStep(BaseModel):
    """A single step in an FPA workflow"""
    step_id: str
    name: str
    inputs: Dict[str, Any]  # references to prior outputs or literals
    outputs: List[str]
    formula: str  # human-readable; maps to service call
    editable: bool
    assumptions: Dict[str, Any]
    service_call: Dict[str, Any]  # e.g. {"service": "revenue_projection", "method": "project_revenue_with_decay", "kwargs": {...}}


# ---------------------------------------------------------------------------
# Service mapping table
# ---------------------------------------------------------------------------

_SERVICE_MAP = {
    "revenue_projection": {
        "service": "revenue_projection",
        "method": "time_series_forecast",
    },
    "growth_change": {
        "service": "revenue_projection",
        "method": "time_series_forecast",
    },
    "valuation": {
        "service": "valuation_engine",
        "method": "calculate_valuation",
    },
    "exit_event": {
        "service": "pwerm",
        "method": "calculate_exit_scenario",
    },
    "funding_event": {
        "service": "gap_filler",
        "method": "fill_gaps",
    },
    "custom": {
        "service": "custom",
        "method": "execute",
    },
}

_FORMULA_TEMPLATES = {
    "revenue_projection": "time_series_forecast({metric}, periods={periods})",
    "growth_change": "apply_growth_change({metric}, delta={change_pct}%)",
    "valuation": "calculate_valuation(method={method})",
    "exit_event": "model_exit({exit_type})",
    "funding_event": "model_funding_round(amount={amount})",
    "custom": "custom_step()",
}


class FPAWorkflowBuilder:
    """Builds workflow steps from parsed queries"""

    def __init__(self):
        pass

    def build(self, parsed: ParsedQuery, handler: str) -> List[WorkflowStep]:
        """
        Build workflow steps from a parsed query.

        Args:
            parsed: ParsedQuery object
            handler: Handler type (from classifier)

        Returns:
            List of WorkflowStep objects
        """
        logger.info(f"Building workflow for handler: {handler}")

        workflow = []

        for idx, step in enumerate(parsed.steps):
            workflow_step = self._build_step(step, idx, parsed)
            workflow.append(workflow_step)

        return workflow

    def _build_step(self, parsed_step: ParsedStep, index: int, parsed_query: ParsedQuery) -> WorkflowStep:
        """Build a single workflow step from a parsed step"""

        step_id = f"step_{index + 1}"
        step_type = parsed_step.type.value

        service_call = self._map_step_to_service(parsed_step)

        return WorkflowStep(
            step_id=step_id,
            name=self._generate_step_name(parsed_step),
            inputs=self._extract_inputs(parsed_step, index, parsed_query),
            outputs=self._extract_outputs(parsed_step, step_id),
            formula=self._generate_formula(parsed_step),
            editable=True,
            assumptions=parsed_step.payload,
            service_call=service_call
        )

    def _map_step_to_service(self, step: ParsedStep) -> Dict[str, Any]:
        """Map a parsed step to a service call configuration"""
        step_type = step.type.value
        mapping = _SERVICE_MAP.get(step_type, _SERVICE_MAP["custom"])

        return {
            "service": mapping["service"],
            "method": mapping["method"],
            "kwargs": step.payload,
        }

    def _generate_step_name(self, step: ParsedStep) -> str:
        """Generate a human-readable name for a step"""
        companies = step.payload.get("companies", [])
        suffix = f" ({', '.join(companies)})" if companies else ""
        return f"{step.type.value.replace('_', ' ').title()}{suffix}"

    def _extract_inputs(self, step: ParsedStep, index: int, parsed_query: ParsedQuery) -> Dict[str, Any]:
        """Extract input references from a step.

        If this step depends on a previous step's output, reference it with $step_N.
        Otherwise pass through the payload values.
        """
        inputs: Dict[str, Any] = {}

        # Carry forward literal values from payload
        for key, val in step.payload.items():
            inputs[key] = val

        # If this isn't the first step, reference previous step's output
        if index > 0:
            prev_step_id = f"step_{index}"
            inputs["previous_result"] = f"${prev_step_id}_result"

        return inputs

    def _extract_outputs(self, step: ParsedStep, step_id: str) -> List[str]:
        """Extract output names from a step, named by step type + id."""
        step_type = step.type.value
        return [f"{step_id}_{step_type}_result"]

    def _generate_formula(self, step: ParsedStep) -> str:
        """Generate a human-readable formula description"""
        step_type = step.type.value
        template = _FORMULA_TEMPLATES.get(step_type, "custom_step()")
        payload = step.payload

        try:
            return template.format(**{
                "metric": payload.get("metric", "arr"),
                "periods": payload.get("periods", 12),
                "change_pct": payload.get("change_pct", "N/A"),
                "method": payload.get("method", "comparables"),
                "exit_type": payload.get("exit_type", "ipo"),
                "amount": payload.get("amount", "N/A"),
            })
        except (KeyError, IndexError):
            return f"{step_type}({payload})"
