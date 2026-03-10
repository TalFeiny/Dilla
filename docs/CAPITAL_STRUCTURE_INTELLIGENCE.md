# Capital Structure Intelligence Engine

## What This Is

A legal reasoning engine that reads contracts, extracts the rules they encode, understands how those rules interact across instruments and stakeholders, and tells you what it all means in dollars — with full attribution back to the specific clause in the specific document.

The financial engines exist (waterfall, cap table, PWERM, branching, debt structures, cash flow, TP). They take parameters and run math. This system makes the legal documents the source of truth for those parameters — and reasons about the interactions between them.

It's about three things: **cost of capital** (what do these terms actually cost each party), **deal structure** (how instruments interact under different scenarios), and **multi-stakeholder dynamics** (whose interests align, diverge, and at what price points).

---

## Foundation: What Exists

### Clause Extraction (built)
- Agnostic extraction across 52+ legal doc types via `document_process_service.py`
- `LEGAL_BASE_SCHEMA` with hierarchical clause IDs (`4.2.a`), parent-child relationships
- Clause types: `liquidation_preference`, `anti_dilution`, `drag_along`, `tag_along`, `conversion_terms`, `covenant`, `board_composition`, `transfer_restriction`, etc.
- Source attribution: `section_reference`, `source_quote`, verbatim text
- Cross-references: `to_service` (cap_table, liquidation_waterfall, anti_dilution, pnl, cash_flow), `to_entity`, `field`, `relationship` (defines, modifies, constrains, overrides)
- Document lineage: `parent_document_id`, `supersedes`, `modifies_clauses`
- Red flags with verbatim quote → interpretation → impact

### Bridges (built)
- `legal_cap_table_bridge.py` — clauses → `ShareEntry` objects with full `ShareholderRights`
- `contract_pnl_bridge.py` — commercial contracts → P&L line items via ERP attribution
- `DOC_PRIORITY` map — SHA(20), side letter(30), amendment(40) — determines which doc wins

### Financial Engines (built)
- `advanced_cap_table.py` — ownership, waterfall, breakpoints, anti-dilution math, dilution scenarios
- `waterfall_advanced.py` — LIFO preference stacking, M&A game theory, IPO ratchets, participation caps
- `scenario_branch_service.py` — fork-aware branches with assumption merging, multi-branch comparison, probability-weighted expected values
- `pwerm_comprehensive.py` — 300+ scenario probability-weighted returns by funding path
- `advanced_debt_structures_service.py` — convertible conversion, debt capacity, DSCR
- `ownership_return_analyzer.py` — Bayesian returns with liquidation pref mechanics by stakeholder
- `cash_flow_planning_service.py` — monthly P&L with covenant/debt service drivers
- `transfer_pricing_engine.py` — OECD-compliant method selection, arm's length, IQR analysis
- `strategic_intelligence_service.py` — signal detection, dynamic WACC, cross-domain impact chains, LLM synthesis

### Vanilla Waterfall Assumptions (built into `waterfall_advanced.py`)
These are the defaults when no documents exist:
- 1x liquidation preference, non-participating
- No pari passu — strict seniority by round (LIFO)
- IPO: liquidation preferences convert to common (don't apply)
- Late stage (Series D+): IPO ratchet guaranteeing 20% return, non-compounding. 14% of late-stage rounds carry 1.5x preference
- M&A: any preferred investor can block, will negotiate. 50:50 cash/stock mix (unless buyout or roll-up)
- Growth stage (Series B/C): some non-vanilla structures — capped participating or cumulative dividends
- Down rounds / extensions: investors push for >1x or participating
- No pay-to-play provisions

**The legal intelligence layer overrides these defaults with what the actual documents say.**

---

## Layer 1: Clause Parameter Registry

Every financially-material clause gets resolved to a typed parameter that the engines consume. This replaces manual inputs with document-derived inputs.

### `clause_parameter_registry.py`

```python
@dataclass
class ClauseParameter:
    """A single financially-material clause resolved to a typed engine input."""
    param_type: str            # "liquidation_preference", "anti_dilution_method",
                               # "covenant_dscr_threshold", "conversion_discount", etc.
    value: Any                 # 2.0, "full_ratchet", 1.2, 0.20, etc.
    applies_to: str            # "series_a", "all_preferred", "founder_x", "lender_xyz"
    instrument: str            # "equity", "debt", "convertible", "safe", "warrant", "option"

    # Attribution
    source_document_id: str
    source_clause_id: str      # hierarchical ID "4.2.a"
    section_reference: str     # "Section 4.2(a)"
    source_quote: str          # verbatim from document
    document_type: str         # "sha", "side_letter", "term_sheet", "loan_agreement"
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None

    # Resolution state
    confidence: float = 1.0
    overridden_by: Optional[str] = None    # clause_id of overriding clause
    override_reason: Optional[str] = None  # "Side letter S.2 grants participation rights"


@dataclass
class ClauseConflict:
    """Two clauses that contradict each other with no clear resolution."""
    param_type: str
    clause_a: ClauseParameter
    clause_b: ClauseParameter
    conflict_description: str   # "SHA S.4.2 says 1x non-participating.
                                #  Side letter S.2 says participating. Which governs?"
    financial_impact_range: Tuple[float, float]  # dollar range of the disagreement


@dataclass
class ResolvedParameterSet:
    """Complete resolved legal parameters for a company's capital structure.

    This is what the financial engines consume instead of manual inputs.
    """
    company_id: str
    parameters: Dict[str, ClauseParameter]    # keyed by f"{param_type}:{applies_to}"
    conflicts: List[ClauseConflict]           # unresolved — need human review
    override_chain: List[Dict]                # full audit trail
    gaps: List[str]                           # expected params not found in any doc
    instruments: List[InstrumentSummary]      # all instruments in the structure
    last_resolved: datetime
```

### Resolution Logic

```python
def resolve_parameters(
    company_id: str,
    extracted_docs: List[ExtractedDocument],
) -> ResolvedParameterSet:
    """
    Walk all extracted clauses across all documents for a company.

    For each financially-material clause:
      1. Map clause_type + cross_reference → param_type
      2. Check document lineage — does a later doc supersede this?
      3. Check DOC_PRIORITY — side letter (30) beats SHA (20), amendment (40) beats both
      4. Check effective/expiry dates — is this clause currently active?
      5. If two docs at same priority disagree — flag as conflict (don't guess)
      6. Register resolved parameter with full provenance

    For each expected parameter not found:
      - Fall back to vanilla waterfall assumptions
      - Flag as gap: "No anti-dilution clause found for Series A.
        Using default: broad-based weighted average."
    """
```

---

## Layer 2: Cascade Engine

Instruments don't exist in isolation. Anti-dilution reprices shares. Repricing shifts ownership. Ownership shifts change governance thresholds. Covenant breaches accelerate repayment. Conversion triggers create new cap table entries. One change cascades through the entire structure.

### `cascade_engine.py`

```python
@dataclass
class CascadeEdge:
    """A legal dependency between two parameters."""
    trigger_param: str         # "round_price:series_c"
    affected_param: str        # "conversion_price:series_a"
    relationship: str          # "triggers_repricing", "accelerates_payment",
                               # "forces_conversion", "requires_consent", "creates_default"
    conditions: Dict           # {"when": "new_price < original_price"}
    source_clause: ClauseParameter  # the clause that creates this dependency
    computation: str           # which engine function computes the effect


class CascadeGraph:
    """Directed graph of parameter dependencies built from legal clauses.

    Each node is a ClauseParameter. Each edge is a legal relationship
    between instruments that can trigger downstream effects.
    """

    def build_from_clauses(self, params: ResolvedParameterSet) -> None:
        """
        Walk resolved parameters and build edges:

        ANTI-DILUTION EDGES:
          round_price:new_round → conversion_price:series_X
          Condition: new_price < original_price
          Effect: reprices shares per method (full ratchet / weighted average)
          Source: e.g. "Series A SPA S.3.1 — broad-based weighted average"

        CONVERSION TRIGGER EDGES:
          qualified_financing:any → conversion:safe_X
          Condition: raise_amount > qualified_financing_threshold
          Effect: SAFE converts to equity at min(cap, discount)
          Source: e.g. "SAFE S.2 — converts on qualified financing of $3M+"

          maturity_date:note_X → repayment_or_conversion:note_X
          Condition: date >= maturity_date AND no qualified_financing
          Effect: lender can demand repayment OR convert
          Source: e.g. "Convertible Note S.4.1 — maturity 24 months"

        COVENANT EDGES:
          financial_metric:actual → covenant_breach:loan_X
          Condition: metric < threshold (DSCR, leverage, etc.)
          Effect: acceleration, step-in rights, default
          Source: e.g. "Credit Facility S.9.2 — DSCR must exceed 1.2x"

        CROSS-DEFAULT EDGES:
          default:instrument_X → default:instrument_Y
          Condition: default on X
          Effect: automatic default on Y
          Source: e.g. "Loan B S.11.3 — cross-default with any other facility"

        CHANGE-OF-CONTROL EDGES:
          ownership_change:any → acceleration:options
          ownership_change:any → consent_required:lender_X
          ownership_change:any → termination_right:counterparty_X
          Condition: >50% ownership transfer (or per specific threshold)
          Source: e.g. "Option Agreement S.6 — single trigger acceleration"

        DRAG-ALONG / TAG-ALONG EDGES:
          sale_vote:preferred → forced_sale:common
          Condition: vote exceeds threshold (e.g. 75% of preferred)
          Source: e.g. "SHA S.15.1 — drag-along at 75% preferred vote"

          sale:majority → tag_right:minority
          Condition: majority selling
          Source: e.g. "SHA S.16 — tag-along on any founder transfer"

        GUARANTEE EDGES:
          default:company → personal_liability:founder_X
          default:subsidiary → parent_liability:holdco
          Source: e.g. "Personal Guarantee S.2 — founder liable up to $500K"

        PREEMPTION / ROFR EDGES:
          new_issuance:any → preemption_right:investor_X
          share_transfer:any → rofr:existing_investors
          Source: e.g. "SHA S.12.4 — ROFR on any common transfer"
        """

    def simulate(
        self,
        trigger: str,               # e.g. "round_price:series_c"
        new_value: Any,             # e.g. 0.50 (down round price)
        current_params: ResolvedParameterSet,
        financial_state: Any,       # UnifiedFinancialState for covenant checks
    ) -> CascadeResult:
        """
        Fire a trigger and trace every downstream effect through the graph.

        Returns CascadeResult:
          steps: List[CascadeStep] — ordered chain of effects
            Each step:
              - param affected, old value, new value
              - clause that caused this step (with attribution)
              - financial impact (dollar amount where computable)
              - downstream triggers (what this step fires next)
          terminal_effects:
              - cap_table_delta: Dict[stakeholder, ownership_change]
              - waterfall_delta: Dict[stakeholder, proceeds_change] at reference exits
              - cash_flow_delta: change in periodic obligations
              - governance_changes: List[str] — board composition, veto rights, etc.
              - exposure_changes: Dict[person, liability_change]
        """

    def identify_constraints(self) -> List[Constraint]:
        """
        Walk the graph and surface all constraints on the company's actions.

        Returns actionable constraints like:
          - "Cannot raise debt above $2M without lender consent
             (Credit Facility S.7.1, effective until 2026-03-01)"
          - "Cannot transfer shares without 30-day ROFR to existing investors
             (SHA S.12.4)"
          - "Must maintain DSCR above 1.2x quarterly
             (Credit Facility S.9.2, next test: 2025-06-30)"
          - "Any equity raise above $3M triggers SAFE conversion
             (SAFE S.2, outstanding principal: $750K)"
          - "Board approval required for any single transaction above $500K
             (SHA S.8.1, current board: 2 founders, 1 investor)"
        """

    def find_breakpoints(
        self,
        variable: str,      # e.g. "exit_value", "round_price", "revenue"
        range_min: float,
        range_max: float,
        steps: int = 100,
    ) -> List[Breakpoint]:
        """
        Sweep a variable across a range and find where cascade behavior changes.

        Returns exit values (or prices, or revenue levels) where:
          - A preference stack gets fully paid
          - Participation caps kick in
          - Conversion becomes more valuable than preference
          - A covenant triggers
          - Anti-dilution fires
          - Stakeholder interests flip (founder vs investor alignment changes)

        Each breakpoint has: value, description, clauses involved, stakeholder impact.
        """
```

### Example Cascade

**Trigger**: Down round at $0.50/share (Series C)

```
Step 1: Series A anti-dilution fires (full ratchet, SHA S.4.2)
        → Series A price reprices from $1.00 to $0.50
        → Series A shares double (1M → 2M)
        → Series A ownership: 20% → 31%

Step 2: Series B anti-dilution fires (broad-based weighted average, SPA S.3.1)
        → Series B price adjusts from $2.00 to $1.44
        → Series B gets additional 195K shares
        → Series B ownership: 15% → 18%

Step 3: SAFE conversion triggered (qualified financing, SAFE S.2)
        → Converts $500K at $0.50 cap
        → Creates 1M new shares
        → Additional 8% dilution to all existing

Step 4: Ownership recalculation
        → Founders: 35% → 19.2%
        → Option pool effective strike ($1.50) now above share price
        → All options underwater

Step 5: Governance impact
        → Drag-along threshold: 75% of preferred (SHA S.15.1)
        → Series A (31%) + Series B (18%) + new Series C = could force sale
        → Founders lose blocking position

Step 6: Waterfall impact at $50M exit
        → Founder proceeds: $11.8M → $3.1M
        → Series A proceeds: $10.0M → $18.2M
        → Common breakeven shifts from $28M to $47M

Every step attributed. Every dollar traceable to a clause.
```

---

## Layer 3: Legal Signal Detection

New signal source for `strategic_intelligence_service.py`. Same `StrategicSignal` data structure. Fires alongside financial signals (runway, burn, growth) to give the CFO brain legal awareness.

### `legal_signal_detector.py`

```python
def detect_legal_signals(
    params: ResolvedParameterSet,
    financial_state: UnifiedFinancialState,
    cascade_graph: CascadeGraph,
) -> List[StrategicSignal]:
    """
    COVENANT PROXIMITY
      Compare current financial metrics against covenant thresholds from loan/facility clauses.
      "DSCR at 1.28x, covenant triggers at 1.20x (Credit Facility S.9.2).
       At current burn trajectory, breach in 4 months."
      Severity: high if <3mo to breach, medium if <6mo

    CONVERSION TRIGGERS APPROACHING
      SAFE/note maturity dates, qualified financing thresholds.
      "Convertible note matures in 5 months. No qualified financing yet.
       Lender can demand repayment of $750K (Note S.4.1)"

    CLAUSE CONFLICTS
      Unresolved conflicts from parameter resolution.
      "SHA S.4.2: 1x non-participating for all Series A.
       Side Letter with Investor X S.2: participating preferred.
       Financial impact: $800K-$2.4M depending on exit value."

    GOVERNANCE SHIFTS
      Ownership changes approaching protective provision thresholds.
      "If proposed Series C takes 25%+, they gain board seat (Term Sheet S.6.2).
       Board shifts from 2-1 (founder control) to 2-2 (deadlock risk)."

    EXPOSURE ALERTS
      Personal guarantees, cross-defaults, uncapped liability.
      "Founder personal guarantee exposure: $1.2M across 3 instruments.
       Cross-default between Loan A and Loan B — single trigger = full exposure."

    COST OF CAPITAL SIGNALS
      Terms that materially affect effective cost of capital.
      "Cumulative dividends on Series B accruing at 8% for 3 years.
       Unpaid dividends now $2.4M — adds to preference stack before common sees anything.
       Effective cost of this equity: not the headline valuation."
      "Warrant coverage on venture debt: 0.5% fully diluted.
       At current valuation = $250K of free equity to lender.
       Effective interest rate including warrants: 16.2%, not 12%."

    MISSING PROTECTIONS
      Standard clauses absent from the structure, benchmarked by stage.
      "No D&O insurance. No key-man provision. No tag-along on common shares.
       Standard for Series B stage."

    EXPIRY / RENEWAL / DEADLINES
      Option exercise windows, exclusivity periods, auto-renewals.
      "Vendor contract auto-renews in 45 days with 12-month lock-in.
       30-day notice window closing. Annual cost: $180K (Contract S.8.1)"
    """
```

### Integration

```python
# strategic_intelligence_service.py — extend detect_signals()

def detect_signals(
    state: UnifiedFinancialState,
    legal_params: Optional[ResolvedParameterSet] = None,
) -> List[StrategicSignal]:
    signals = []

    # Existing: financial signals from KPIs
    signals.extend(_detect_financial_signals(state))

    # New: legal signals from clause analysis
    if legal_params:
        cascade = CascadeGraph()
        cascade.build_from_clauses(legal_params)
        signals.extend(detect_legal_signals(legal_params, state, cascade))

    return signals
```

---

## Layer 4: Clause Diff Engine

The redlining layer. Compare two sets of terms and compute what every change costs, for every stakeholder, at multiple exit values. Works for: term sheet vs term sheet, pre-redline vs post-redline, current structure vs proposed restructuring, pre-amendment vs post-amendment.

### `clause_diff_engine.py`

```python
@dataclass
class ClauseDelta:
    """A single change between two clause sets."""
    param_type: str
    applies_to: str
    old_value: Any                          # None if new clause
    new_value: Any                          # None if removed clause
    old_source: Optional[ClauseParameter]   # with full attribution
    new_source: Optional[ClauseParameter]
    cascade_effects: List[CascadeStep]      # what this change triggers downstream
    impact: DeltaImpact


@dataclass
class DeltaImpact:
    """Financial impact of a single clause change across exit scenarios."""
    waterfall_delta: Dict[float, Dict[str, float]]
        # exit_value → stakeholder → change in proceeds
        # e.g. {50M: {"founders": -4.8M, "series_b": +4.8M}}
    ownership_delta: Dict[str, float]
        # stakeholder → change in ownership %
    cost_of_capital_delta: Optional[float]
        # change in effective cost of this instrument
    breakpoint_shift: Optional[float]
        # how the common-breakeven exit value moves
    constraint_changes: List[str]
        # new constraints added or removed


@dataclass
class StakeholderImpact:
    """Per-stakeholder summary across all deltas."""
    stakeholder: str
    proceeds_delta_by_exit: Dict[float, float]   # at each reference exit
    ownership_delta: float
    new_rights_gained: List[str]
    rights_lost: List[str]
    alignment_shift: str                          # "better", "worse", "unchanged"
    breakeven_exit_delta: float                   # how their breakeven moves


@dataclass
class DiffResult:
    """Full comparison between two clause sets."""
    deltas: List[ClauseDelta]                     # every individual change
    net_impact: DeltaImpact                       # aggregated
    stakeholder_impacts: Dict[str, StakeholderImpact]
    cascade_summary: CascadeResult                # full cascade of combined changes
    cost_of_capital_comparison: Dict[str, Any]    # effective cost under each set of terms
    alignment_matrix: Dict[Tuple[str, str], str]  # stakeholder pair → aligned/divergent at what exit


class ClauseDiffEngine:

    def diff(
        self,
        version_a: ResolvedParameterSet,
        version_b: ResolvedParameterSet,
        reference_exits: List[float] = [10e6, 25e6, 50e6, 100e6, 200e6, 500e6],
    ) -> DiffResult:
        """
        Compare two complete parameter sets.

        For each parameter that differs:
          1. Identify the change with full clause attribution
          2. Run cascade on the delta — what else does this trigger?
          3. Run waterfall at each reference exit with version_a params vs version_b params
          4. Compute per-stakeholder impact: who gains, who loses, how much, at what exit
          5. Compute breakpoint shifts — where does common start getting paid?
          6. Compute effective cost of capital under each set of terms

        Aggregate all deltas into net impact.
        Build stakeholder alignment matrix: at what exit values do interests align/diverge?
        """

    def compare_term_sheets(
        self,
        term_sheets: List[ExtractedDocument],
        existing_structure: ResolvedParameterSet,
        reference_exits: List[float] = [10e6, 25e6, 50e6, 100e6, 200e6, 500e6],
    ) -> TermSheetComparison:
        """
        Compare N term sheets against each other and against current structure.

        Each term sheet is layered onto the existing structure to produce a
        hypothetical ResolvedParameterSet.

        Returns comparison matrix:
          - current vs A, current vs B, current vs C
          - A vs B, A vs C, B vs C
          - Per-stakeholder: which term sheet is best for founders? For Series A?
            For employees? At what exit values does the answer change?
          - Cost of capital: effective cost of each term sheet's capital
            (not just the headline valuation — include preferences, anti-dilution,
             warrants, dividends, ratchets)
          - Constraint comparison: what new constraints does each term sheet add?
        """

    def redline_impact(
        self,
        original: ExtractedDocument,
        redlined: ExtractedDocument,
        existing_structure: ResolvedParameterSet,
    ) -> DiffResult:
        """
        Two versions of the same document (pre-redline and post-redline).
        Extract clauses from both. Diff. Show the financial impact of every change.

        "They changed Section 4.2 from 1x non-participating to 2x participating.
         At $50M exit: founders −$4.8M, Series B +$4.8M.
         At $100M exit: founders −$2.1M (participation cap kicks in at 3x).
         They changed Section 7.1: added DSCR covenant at 1.5x.
         At current trajectory, this covenant binds in month 14."
        """
```

---

## Layer 5: Legal Branches

Extends `scenario_branch_service.py` to carry legal parameters alongside financial assumptions. A branch becomes: "what if we accept these terms" not just "what if revenue grows 30%."

### Integration with existing branching

```python
@dataclass
class LegalBranchOverride:
    """Legal parameter changes for this branch."""
    param_overrides: Dict[str, Any]        # param_type:applies_to → new value
    new_documents: List[str]               # document IDs layered in (term sheet, amendment)
    removed_documents: List[str]           # documents superseded
    description: str                       # "Accept Investor X term sheet as-is"


# In scenario_branch_service.py merge_assumptions():

def merge_assumptions(chain: List[Dict]) -> Dict:
    # Existing: merge financial overrides (revenue, burn, etc.)
    financial = _merge_financial(chain)

    # New: merge legal overrides (clause parameters)
    legal = _merge_legal(chain)

    # Child legal overrides beat parent legal overrides
    # Same DOC_PRIORITY logic as document resolution
    return {**financial, "legal_overrides": legal}


def execute_branch(branch_id, company_id, ...):
    assumptions = merge_assumptions(chain)

    # Resolve parameters for THIS branch
    # Base company params + branch legal overrides
    branch_params = resolve_parameters_with_overrides(
        company_id, assumptions.get("legal_overrides")
    )

    # Run cascade with branch params
    cascade = CascadeGraph()
    cascade.build_from_clauses(branch_params)

    # Feed into financial engines
    # Waterfall uses branch_params instead of manual inputs
    # Cap table uses branch_params.anti_dilution instead of defaults
    # Cash flow uses branch_params.covenant_thresholds + debt_terms
    # PWERM uses branch_params for scenario-specific return calculations

    # Run financial forecast
    forecast = build_forecast(company_id, assumptions, branch_params)

    # Detect legal signals specific to this branch
    signals = detect_legal_signals(branch_params, financial_state, cascade)

    return {
        "forecast": forecast,
        "legal_params": branch_params,
        "cascade_graph": cascade,
        "legal_signals": signals,
        "constraints": cascade.identify_constraints(),
    }
```

### Branch Comparison Table

```
                    | Branch A: Equity      | Branch B: Counter     | Branch C: Debt
                    | (their term sheet)    | (our redline)         | (venture debt)
--------------------|----------------------|----------------------|----------------------
Terms               | 2x part. preferred   | 1.5x non-part.       | $3M, 12%, 1.2x DSCR
                    | Full ratchet         | Broad-based WA        | 0.5% warrant coverage
                    | Board seat           | Observer seat          | No governance
Source              | Term Sheet S.4,5,6   | Counter S.4,5,6       | Facility S.2,9,11
--------------------|----------------------|----------------------|----------------------
Founder own. post   | 28.3%                | 31.1%                 | 35.0%
@ $30M exit         | $1.2M                | $4.8M                 | $7.1M
@ $50M exit         | $4.2M                | $8.1M                 | $12.4M
@ $100M exit        | $18.7M               | $22.3M                | $28.1M
@ $200M exit        | $48.2M               | $52.1M                | $58.0M
Common breakeven    | $38M                 | $29M                  | $22M
--------------------|----------------------|----------------------|----------------------
Effective CoC       | 42% (incl. prefs)    | 28%                   | 16.2% (incl. warrants)
Runway impact       | +18mo                | +18mo                 | +12mo
New constraints     | Ratchet exposure,    | Pro-rata only          | DSCR covenant,
                    | board veto, drag     |                        | warrant dilution
--------------------|----------------------|----------------------|----------------------
Cascade risk        | Down round reprices  | Investor may walk      | Covenant breach mo.9
                    | everything (S.4.2)   |                        | (Facility S.9.2)
--------------------|----------------------|----------------------|----------------------
Series A view       | Ratchet protects     | Less protection        | No dilution
                    | them on downside     | but cleaner cap table  | Debt is senior to them
Employee view       | Options likely       | Options have value     | No dilution
                    | underwater           | above $29M             | above $22M
```

---

## Layer 6: Decision Engine

Given the constraints, cascades, and branch comparisons — frame actual decisions with quantified trade-offs per stakeholder.

### `decision_engine.py`

```python
@dataclass
class DecisionOption:
    name: str
    branch_id: str
    waterfall_by_exit: Dict[float, Dict[str, float]]  # exit → stakeholder → proceeds
    ownership_impact: Dict[str, float]
    effective_cost_of_capital: float
    runway_impact_months: float
    new_constraints: List[str]
    cascade_risks: List[str]                           # downstream triggers with attribution
    breakeven_exit: float
    pwerm_return: float                                # probability-weighted expected return
    stakeholder_preference: Dict[str, str]             # stakeholder → "prefers" / "opposes" / "neutral"


@dataclass
class Decision:
    question: str                                       # "Raise equity, take debt, or bridge?"
    viable_options: List[DecisionOption]                 # filtered by constraint_map
    blocked_options: List[Tuple[str, str]]               # (option, reason) — legally blocked
    stakeholder_alignment: Dict[str, Dict[str, str]]    # stakeholder → option → stance
    divergence_points: List[str]                         # exit values where stakeholder interests flip


class DecisionEngine:

    def frame_decision(
        self,
        company_id: str,
        decision_type: str,     # "raise_equity", "take_debt", "sell", "restructure",
                                # "refinance", "secondary", "bridge", "down_round"
        candidates: List[LegalBranchOverride],
    ) -> Decision:
        """
        1. Constraint check — which options are legally possible?
           (consent requirements, restrictive covenants, preemption rights)
        2. For each viable option, create a legal branch
        3. Run cascade on each branch — what triggers?
        4. Run waterfall at multiple exits — who gets what?
        5. Run PWERM with branch-specific params — probability-weighted outcome
        6. Compute effective cost of capital for each option
           (not headline valuation — include preferences, anti-dilution cost,
            warrant dilution, dividend accrual, covenant cost)
        7. Map stakeholder preferences — who benefits from which option?
        8. Find divergence points — at what exit values do interests flip?
        """

    def negotiate(
        self,
        company_id: str,
        our_position: ResolvedParameterSet,
        their_position: ResolvedParameterSet,
        our_objectives: List[str],
            # ["maximize founder ownership at $50-100M exit range",
            #  "maintain board control",
            #  "minimize ratchet exposure",
            #  "keep covenant headroom above 6 months"]
    ) -> NegotiationAnalysis:
        """
        Multi-stakeholder game theory.

        1. Diff the two positions (clause_diff_engine)
        2. For each delta, compute:
           - Cost to us (dollar impact across exit scenarios)
           - Value to them (what they gain)
           - Cost asymmetry: things cheap for us but valuable to them (concede)
                            things expensive for us (fight)
        3. Identify their likely priorities from what they changed:
           "They pushed hardest on anti-dilution (full ratchet) and participation.
            They didn't touch board composition or information rights.
            Pattern: downside protection focus. They're worried about a down round."
        4. Generate counter-proposal:
           - Accept: low-cost items they care about (observer seat, information rights)
           - Counter: expensive items with cheaper alternatives
             "Full ratchet → broad-based weighted average.
              Costs them $1.2M of protection at a 50% down round.
              Costs us $8M less exposure."
           - Fight: items that cross our objectives
             "Participating preferred non-negotiable — shifts $4.8M at our target exit range"
        5. Run counter-proposal through waterfall + cascade to verify it meets objectives
        6. Map multi-stakeholder dynamics:
           "Series A will support our counter because broad-based WA protects them too.
            New investor is isolated on the full ratchet ask."
        """

    def analyze_cost_of_capital(
        self,
        company_id: str,
        instrument_options: List[ResolvedParameterSet],
    ) -> CostOfCapitalAnalysis:
        """
        True cost of capital comparison across instrument types.

        Equity at $50M pre with 1x non-participating:
          Headline cost: 20% dilution
          Real cost: 20% dilution + anti-dilution exposure + preference stack impact
          Effective annual cost: ~35% (factoring probability of down round)

        Venture debt at $3M, 12%, 0.5% warrants:
          Headline cost: 12% annual
          Real cost: 12% + warrant dilution ($150K) + covenant risk
          Effective annual cost: ~16% (including warrant cost amortized)

        Convertible at $500K, 20% discount, $10M cap:
          Headline cost: 20% discount to next round
          Real cost: depends entirely on next round price
          At $5M pre: converts at $4M effective → 11% dilution
          At $15M pre: converts at $10M cap → 4.8% dilution
          Expected cost: probability-weighted across round scenarios

        Revenue-based financing at $1M, 1.5x repayment:
          Headline cost: 50% total return
          Real cost: depends on repayment speed
          At current revenue: 18 month repayment → ~33% annualized
          Non-dilutive but constrains cash flow by $83K/mo

        The system computes effective cost including all clause-derived effects,
        not just the headline terms.
        """
```

---

## Layer 7: Multi-Stakeholder Interaction Map

Every instrument creates a stakeholder with specific rights, preferences, and economic interests that change at different exit values. The interaction map shows where interests align and where they diverge.

### `stakeholder_map.py`

```python
@dataclass
class StakeholderPosition:
    """A stakeholder's complete position in the capital structure."""
    name: str
    instruments: List[str]                  # what they hold
    total_invested: float
    ownership_pct: float
    liquidation_preference_total: float     # their total preference claim
    participation_rights: bool
    anti_dilution_protection: str
    governance_rights: List[str]            # board seats, vetoes, information rights
    transfer_restrictions: List[str]        # lockup, ROFR, drag/tag
    breakeven_exit: float                   # minimum exit for them to get money back
    optimal_exit_range: Tuple[float, float] # where their return is maximized relative to others


class StakeholderInteractionMap:

    def build(self, params: ResolvedParameterSet) -> None:
        """Build positions for every stakeholder from resolved clause parameters."""

    def alignment_analysis(
        self,
        exit_range: Tuple[float, float] = (0, 500_000_000),
    ) -> AlignmentMatrix:
        """
        At each exit value in the range, compute each stakeholder's:
          - Absolute return
          - Return multiple
          - Marginal $ per additional $1M of exit value

        Find inflection points where:
          - Stakeholder A prefers to sell but B prefers to hold
          - Preferences are fully covered (remainder goes to common)
          - Participation caps trigger
          - Conversion becomes better than preference for specific investors
          - Drag-along can be forced (threshold met)
          - One stakeholder's return goes to zero

        Output:
          "Below $30M: founders get nothing. Series A gets 80c on the dollar.
           Series B gets their 1.5x preference. Nobody wants to sell.

           $30M-$60M: founders start getting paid. Series A is whole.
           Series B wants to sell (2x+). Founders want to hold (only getting $2-8M).
           CONFLICT ZONE — Series B has drag-along power with Series A.

           $60M-$120M: alignment returns. Everyone benefits from higher exit.
           Series B participation cap triggers at $80M — they convert to common.

           Above $120M: full alignment. All stakeholders are pro-rata.
           This is where the cap table acts like a simple ownership table."
        """

    def coalition_analysis(self) -> List[Coalition]:
        """
        Which stakeholders can act together to force outcomes?

        Based on voting thresholds, consent requirements, drag-along thresholds:
          "Series A (20%) + Series B (15%) = 35% of preferred.
           Drag-along requires 75%. They need founders (35%) to force a sale.
           But founders won't vote to sell below $60M (they get <$5M).
           Effective drag-along floor: $60M."

          "Lender can block any M&A (consent right, Facility S.7.1).
           Lender is indifferent above $15M (fully repaid).
           Below $15M: lender blocks unless carve-out for debt repayment."

          "Series A + founders = 55% of total. Can block any action requiring
           simple majority. Aligned on: no down round, no cheap sale.
           Diverge on: Series A wants preference protection, founders want common value."
        """
```

---

## Layer 8: Group Structure Intelligence

For companies with holdco/subsidiary structures. The legal relationships between entities determine how cash moves, where value sits, and what restructuring options exist.

### Integration with existing TP engine

```python
def resolve_group_structure(
    company_id: str,
    params: ResolvedParameterSet,
) -> GroupStructure:
    """
    From extracted intercompany agreements, management agreements,
    IP licenses, guarantee agreements, loan agreements:

    1. Entity relationship map
       parent → subsidiary, sub → sub, with ownership %
       From: articles of association, SHA, SPV docs

    2. Cash flow rules between entities
       - Management fees: % or fixed (management agreement S.X)
       - IP royalties: % of revenue (IP license S.Y)
       - Intercompany loans: rate, repayment (loan agreement S.Z)
       - Dividends: policy, restrictions (SHA/articles)
       - Cost recharges: methodology (service agreement S.W)

    3. Cash flow constraints
       - Restricted payments (loan covenant S.X)
       - Thin cap rules (TP compliance)
       - Guarantee chains (parent guarantees sub's debt)
       - Ring-fencing provisions

    4. TP validation
       → Feed pricing terms into transfer_pricing_engine.py
       → Check arm's length via tp_comparable_service.py
       → Flag where contract terms don't match TP policy

    5. Restructuring options
       Given the legal constraints, what CAN be changed?
       - Management fee within permitted range (contract says "up to 8%", currently at 5%)
       - IP can be reassigned (if no restriction in current license)
       - Intercompany loan rate adjustable (within arm's length range)
       - Dividend extraction blocked by covenant until [date]

    This answers questions like:
      "Can I move $500K from SubCo to HoldCo?"
      → "Management agreement permits up to $600K/yr (S.3.1),
         but loan covenant restricts distributions above $400K (Facility S.9.4).
         Max: $400K. To move more, renegotiate covenant or wait until [date]."

      "What's the most tax-efficient structure?"
      → "Current: 5% management fee, 3% royalty. Permitted: up to 8% and 5%.
         Moving to 7% / 4% shifts $300K/yr to lower-tax jurisdiction.
         Within arm's length range (IQR: 4-9% for comparable management fees).
         Legal docs already permit it. No amendment needed."
    """
```

---

## Implementation Sequence

| Step | What | Depends On |
|------|------|------------|
| 1 | `ClauseParameter` + `ResolvedParameterSet` — typed parameter extraction from existing clause data | Existing extraction pipeline | BUILT |
| 2 | Resolution logic — override chains, DOC_PRIORITY, conflict detection, gap identification | Step 1 | BUILT |
| 3 | Wire resolved params into `advanced_cap_table.py`, `waterfall_advanced.py` — engines consume clause params alongside manual inputs | Step 2 | BUILT |
| 4 | `CascadeGraph` — build dependency graph from resolved params, simulate triggers, find breakpoints | Step 2 | BUILT |
| 5 | `detect_legal_signals()` — integrate into `strategic_intelligence_service.py` | Steps 2, 4 | BUILT |
| 6 | `StakeholderInteractionMap` — alignment analysis, coalition analysis, divergence points | Steps 2, 3 | BUILT |
| 7 | `ClauseDiffEngine` — diff two parameter sets, compute financial delta per stakeholder | Steps 2, 3, 4, 6 | BUILT |
| 8 | Legal branch overrides — extend `scenario_branch_service.py` | Steps 2, 7 | BUILT |
| 9 | `DecisionEngine` — frame decisions, cost of capital analysis, negotiation game theory | Steps 4, 6, 7, 8 | BUILT |
| 10 | Group structure resolution — entity map, cash flow rules/constraints, TP integration | Steps 2, 4 | BUILT |

### Critical Gates

**Step 2**: Resolution must be correct. If the system resolves "1x non-participating" when the side letter grants "1.5x participating", every downstream calculation is wrong. Test against real document sets with known answers.

**Step 4**: The cascade graph must correctly model legal relationships between instruments. Test with synthetic multi-instrument structures where you can hand-calculate the correct cascade. Get the anti-dilution → conversion → ownership → governance chain right before building anything on top.

**Step 6**: Stakeholder alignment must reflect actual clause-derived positions, not assumptions. The vanilla waterfall assumptions are the fallback. The docs are the truth.

---

## What This Is Not

- **Not a document management system.** The extraction pipeline handles that.
- **Not a legal review tool.** Doesn't replace lawyers. Quantifies what the lawyers' work means financially.
- **Not startup-specific.** Same architecture handles any complexity — preference stacks, mezzanine debt, intercreditor agreements, PIK toggles, holdco structures. More complex = more valuable.

## What This Is

A capital structure reasoning engine. It reads the legal documents, extracts the rules, models how they interact across instruments and stakeholders, and tells every party what it means in dollars — under any scenario, at any exit value, with full attribution to the specific clause in the specific document.

Cost of capital. Deal structure. Multi-stakeholder dynamics. The capital structure war room.
