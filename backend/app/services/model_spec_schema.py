"""
Model Spec Schema — Pydantic types for priors-based custom forecast models.

The LLM reasons from a user prompt → builds an event chain (business events
with probabilities and causal links) → derives curve parameters FROM events.
The executor evaluates the math. The cascade handles everything downstream.

Architecture:
  User prompt → EventChain (causal reasoning) → ModelSpec (derived params) → Executor → P&L

Event chain layer:
- EventNode: a business event with probability and timing
- CausalLink: how events/metrics impact each other
- EventChain: the full reasoning graph that derives every parameter

Curve types:
- logistic: S-curve with ceiling (capacity, saturation)
- linear: constant slope
- exponential: unconstrained growth
- gompertz: asymmetric S-curve (slow start, fast middle, slow ceiling)
- constant: flat value
- ratio: fraction of another metric's output
- step_function: discrete jumps at specified periods
- composite: weighted sum of sub-curves by subcategory
- inherit: start from parent model's curve, apply modifications only
- custom_expr: safe math expression (escape hatch)

Each curve can carry:
- PriorSpec: confidence, distribution shape, floor/ceiling bounds
- ModifierSpec list: seasonal, shock, trend_break, step overlays
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Event chain — causal reasoning layer
# ---------------------------------------------------------------------------

class EventNode(BaseModel):
    """A business event identified from the prompt and actuals.

    The LLM reasons about what events matter for THIS company given
    the user's prompt. Every curve parameter traces back to events.
    """
    id: str = Field(description="Short slug: 'post-pmf', 'enterprise-pipeline', 'recession-risk'")
    event: str = Field(description="Human-readable description of what happens")
    category: str = Field(description="business | market | macro | funding | operational")
    probability: float = Field(ge=0.0, le=1.0, description="How likely this event is")
    timing: Optional[str] = Field(default=None, description="When: '2026-03', 'Q1-2026', 'ongoing'")
    duration_months: Optional[int] = Field(default=None, description="How long the event's effect lasts")
    reasoning: str = Field(default="", description="Why this event matters for THIS company")


class CausalLink(BaseModel):
    """How one event or metric causally affects another.

    This is the 'knowing what impacts what' layer. Each link says:
    source event/metric → affects target event/metric, by how much, and why.
    """
    source: str = Field(description="event_id or metric name")
    target: str = Field(description="event_id or metric name")
    effect: str = Field(
        description="amplifies | dampens | triggers | blocks | shifts_timing | "
                    "sets_ceiling | sets_floor | scales"
    )
    magnitude: Optional[float] = Field(
        default=None,
        description="Quantified impact: 0.3 = 30% increase, -0.1 = 10% decrease"
    )
    delay_months: int = Field(default=0, description="Months before effect manifests")
    reasoning: str = Field(default="", description="Why this causal connection exists")


class EventChain(BaseModel):
    """The causal reasoning chain that DERIVES model parameters.

    This is the missing layer between 'user prompt + business data' and
    'curve parameters'. Every parameter in every curve traces back to
    specific events and their causal links.
    """
    events: List[EventNode] = Field(default_factory=list)
    links: List[CausalLink] = Field(default_factory=list)
    param_origins: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Maps 'metric.param_name' → [event_ids] that derived it. "
                    "e.g. 'revenue.L' → ['tam-ceiling', 'market-expansion']"
    )
    summary: str = Field(
        default="",
        description="One-paragraph explanation of the causal reasoning"
    )


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

class PriorSpec(BaseModel):
    """Belief about how much to trust a curve's parameters."""
    confidence: float = Field(ge=0.0, le=1.0, description="0-1, how much we trust this curve")
    distribution: str = Field(default="normal", description="normal | beta | triangular")
    floor: Optional[float] = Field(default=None, description="Minimum plausible value")
    ceiling: Optional[float] = Field(default=None, description="Max capacity, saturation bound, etc.")


class ModifierSpec(BaseModel):
    """Overlay applied after base curve evaluation.

    Types:
    - seasonal: {amplitude, phase, period}
    - shock: {start_month, magnitude, duration_months, recovery: gradual|immediate|step}
    - trend_break: {month, new_slope}
    - step: {month, delta}
    """
    type: str  # seasonal | shock | trend_break | step
    params: Dict[str, Any] = Field(default_factory=dict)


class ComponentSpec(BaseModel):
    """A sub-curve within a composite (e.g. revenue:saas, revenue:services)."""
    subcategory: str            # "revenue:saas", "cogs:hosting"
    base: str                   # curve type
    params: Dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(ge=0.0, le=1.0, description="Contribution to parent")
    prior: Optional[PriorSpec] = None
    modifiers: List[ModifierSpec] = Field(default_factory=list)


class CurveSpec(BaseModel):
    """Definition of a single metric's forecast curve."""
    type: str  # logistic | linear | exponential | gompertz | constant |
               # ratio | step_function | composite | inherit | custom_expr
    params: Dict[str, Any] = Field(default_factory=dict)
    prior: Optional[PriorSpec] = None
    modifiers: List[ModifierSpec] = Field(default_factory=list)
    # Only for composite type
    components: List[ComponentSpec] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Macro & funding events
# ---------------------------------------------------------------------------

class MacroShockSpec(BaseModel):
    """A world event with probability-weighted impacts on specific metrics."""
    event: str                                     # "iran_war", "recession", "rate_hike"
    probability: float = Field(ge=0.0, le=1.0)
    impacts: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="metric → {magnitude, duration_months, recovery}",
    )
    reasoning: str = ""  # Why this impact on THIS business


class FundingEventSpec(BaseModel):
    """A planned capital event injected into the forecast timeline."""
    type: str                   # equity | debt | safe | convertible_note
    amount: float
    period: str                 # "2026-01"
    terms: Dict[str, Any] = Field(
        default_factory=dict,
        description="interest_rate, preference, covenant_dscr, etc.",
    )


class MilestoneSpec(BaseModel):
    """A target the forecast should hit (or miss) at a given period."""
    period: str
    metric: str
    target: float
    label: str = ""  # "Series A ready", "Break even"


# ---------------------------------------------------------------------------
# Top-level model spec
# ---------------------------------------------------------------------------

class ModelSpec(BaseModel):
    """Complete specification for a custom forecast model.

    Built FROM an EventChain — every parameter traces back to events.
    The executor evaluates the math. The cascade handles P&L downstream.
    """
    model_id: str
    parent_model: Optional[str] = None              # Inherit curves from another spec
    narrative: str = ""                              # Agent explains WHY this model
    event_chain: Optional[EventChain] = None        # Causal reasoning that derived this spec
    curves: Dict[str, CurveSpec] = Field(            # metric → curve definition
        default_factory=dict,
    )
    macro_shocks: List[MacroShockSpec] = Field(default_factory=list)
    funding_events: List[FundingEventSpec] = Field(default_factory=list)
    milestones: List[MilestoneSpec] = Field(default_factory=list)
    priors: Dict[str, float] = Field(                # Named beliefs: {growth_sustainability: 0.75}
        default_factory=dict,
    )
    driver_overrides: Dict[str, Any] = Field(        # Existing driver keys to set on cascade
        default_factory=dict,
    )
    metadata: Dict[str, Any] = Field(                # Reasoning trace, construction context
        default_factory=dict,
    )


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------

class ExecutionResult(BaseModel):
    """Output of ModelSpecExecutor.execute()."""
    model_id: str
    narrative: str = ""
    event_chain: Optional[EventChain] = None                        # Pass through for frontend
    forecast: List[Dict[str, Any]] = Field(default_factory=list)   # Monthly P&L rows
    confidence_bands: Dict[str, List[float]] = Field(              # p10/p25/p50/p75/p90
        default_factory=dict,
    )
    cascade_ripple: Dict[str, List[Dict[str, float]]] = Field(     # metric → [{period, delta, source}]
        default_factory=dict,
        description="How each metric change ripples through the P&L cascade"
    )
    milestones: List[Dict[str, Any]] = Field(default_factory=list) # Hit/miss results
    curves: Dict[str, List[float]] = Field(default_factory=dict)   # Raw curve arrays for charting
    spec: Optional[ModelSpec] = None                                # Keep spec for comparison/inheritance
