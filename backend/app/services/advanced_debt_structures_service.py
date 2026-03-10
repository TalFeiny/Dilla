"""
Advanced Debt Structures Service

Full instrument modelling for debt, convertibles, SAFEs, warrants, and PIK.
Consumes ResolvedParameterSet from clause_parameter_registry — every term
traced back to the specific clause in the specific document.

Instruments handled:
  - Term loans (senior, subordinated, mezzanine)
  - Revolving credit facilities
  - Venture debt (with warrant kicker, end-of-term payment)
  - Convertible notes (discount, cap, MFN, interest-on-conversion)
  - SAFEs (post-money, pre-money, MFN, pro-rata)
  - Warrants (exercise price, coverage, cashless exercise, expiry)
  - PIK instruments (mandatory, toggle, PIK/cash split, compounding)
  - Revenue-based financing (repayment cap, revenue share)
  - Intercreditor dynamics (priority, subordination, standstill, blockage)

Every output: dollar amounts, full attribution, integration with cascade/waterfall.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.services.clause_parameter_registry import (
    ClauseParameter,
    InstrumentSummary,
    ResolvedParameterSet,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Instrument data structures
# ---------------------------------------------------------------------------

@dataclass
class AmortizationPeriod:
    """Single period in an amortization schedule."""
    period: int                     # 1-indexed
    date: Optional[str] = None
    opening_balance: float = 0.0
    principal_payment: float = 0.0
    interest_payment: float = 0.0
    pik_capitalized: float = 0.0    # PIK interest added to balance
    total_payment: float = 0.0      # cash actually paid this period
    closing_balance: float = 0.0
    cumulative_interest: float = 0.0
    cumulative_principal: float = 0.0


@dataclass
class TermLoan:
    """Senior, subordinated, or mezzanine term loan."""
    instrument_id: str
    holder: str
    principal: float
    interest_rate: float            # annual, decimal (0.12 = 12%)
    maturity_date: Optional[str] = None
    seniority: str = "senior"       # "senior", "subordinated", "mezzanine"
    secured: bool = True
    collateral: Optional[str] = None
    amortization_type: str = "bullet"  # "bullet", "equal_installment",
                                       # "interest_only_then_bullet", "custom"
    interest_only_months: int = 0
    amortization_months: Optional[int] = None  # total amort period
    prepayment_penalty_pct: float = 0.0
    prepayment_lockout_months: int = 0
    make_whole: bool = False
    end_of_term_payment_pct: float = 0.0  # venture debt final payment
    covenants: Dict[str, Any] = field(default_factory=dict)
    # {"dscr": 1.2, "leverage": 3.0, "min_cash": 500000, ...}
    restricted_payments: Optional[str] = None
    cross_default: bool = False
    change_of_control_acceleration: bool = False
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class RevolvingFacility:
    """Revolving credit facility."""
    instrument_id: str
    holder: str
    commitment_amount: float
    drawn_amount: float = 0.0
    interest_rate: float = 0.0      # on drawn portion
    undrawn_fee_rate: float = 0.0   # commitment fee on undrawn
    maturity_date: Optional[str] = None
    covenants: Dict[str, Any] = field(default_factory=dict)
    borrowing_base: Optional[str] = None  # formula for max draw
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class ConvertibleNote:
    """Convertible note with discount, cap, and conversion mechanics."""
    instrument_id: str
    holder: str
    principal: float
    interest_rate: float = 0.0
    interest_type: str = "cash"     # "cash", "pik", "forgiven_on_conversion"
    maturity_date: Optional[str] = None
    conversion_discount: float = 0.0  # decimal (0.20 = 20% discount)
    valuation_cap: Optional[float] = None
    qualified_financing_threshold: Optional[float] = None
    auto_convert_on_qualified: bool = True
    optional_convert_at_maturity: bool = True
    interest_converts: bool = True  # accrued interest converts to equity too
    mfn: bool = False               # most favored nation provision
    maturity_conversion_discount: Optional[float] = None  # different discount at maturity
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class SAFEInstrument:
    """Simple Agreement for Future Equity."""
    instrument_id: str
    holder: str
    investment_amount: float
    safe_type: str = "post_money"   # "post_money", "pre_money", "mfn"
    valuation_cap: Optional[float] = None
    discount_rate: float = 0.0      # decimal
    pro_rata_rights: bool = False
    pro_rata_amount: Optional[float] = None
    mfn: bool = False
    qualified_financing_threshold: Optional[float] = None
    dissolution_priority: str = "before_common"  # "before_common", "with_preferred", "after_preferred"
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class WarrantInstrument:
    """Warrant to purchase shares."""
    instrument_id: str
    holder: str
    shares: Optional[int] = None
    exercise_price: float = 0.0
    coverage_pct: float = 0.0       # % of associated debt principal
    associated_debt_id: Optional[str] = None
    underlying_class: str = "common"  # "common", "preferred"
    expiry_date: Optional[str] = None
    cashless_exercise: bool = True
    vesting_schedule: Optional[str] = None
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class PIKInstrument:
    """Payment-in-Kind debt instrument."""
    instrument_id: str
    holder: str
    principal: float
    pik_rate: float = 0.0           # annual PIK rate
    cash_rate: float = 0.0          # annual cash interest rate
    toggle_type: str = "mandatory_pik"  # "mandatory_pik", "pik_toggle", "pik_cash_split"
    toggle_threshold: Optional[Dict[str, Any]] = None
    # e.g. {"metric": "dscr", "below": 1.5, "force_pik": True}
    capitalization_frequency: str = "quarterly"  # "monthly", "quarterly", "semi_annual", "annual"
    pik_margin_step_up: float = 0.0  # additional spread if PIK elected
    maturity_date: Optional[str] = None
    max_pik_periods: Optional[int] = None  # cap on consecutive PIK periods
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class RevenueBasedFinancing:
    """Revenue-based / royalty-based financing."""
    instrument_id: str
    holder: str
    advance_amount: float
    repayment_cap: float = 1.5      # total repayment as multiple of advance
    revenue_share_pct: float = 0.0  # % of monthly revenue
    minimum_monthly_payment: float = 0.0
    repayment_period_months: Optional[int] = None
    source_clauses: List[ClauseParameter] = field(default_factory=list)


@dataclass
class IntercreditorTerms:
    """Intercreditor agreement terms between two facilities."""
    senior_facility_id: str
    junior_facility_id: str
    subordination_type: str = "full"  # "full", "structural", "contractual"
    standstill_period_months: int = 0
    payment_blockage_triggers: List[str] = field(default_factory=list)
    # e.g. ["senior_default", "covenant_breach"]
    turnover_provisions: bool = False  # junior must turn over payments to senior
    enforcement_standstill: bool = False
    shared_collateral: bool = False
    source_clauses: List[ClauseParameter] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analysis result structures
# ---------------------------------------------------------------------------

@dataclass
class DebtServiceAnalysis:
    """Debt service coverage analysis."""
    total_annual_debt_service: float = 0.0
    total_annual_interest: float = 0.0
    total_annual_principal: float = 0.0
    dscr: Optional[float] = None
    interest_coverage_ratio: Optional[float] = None
    fixed_charge_coverage: Optional[float] = None
    covenant_headroom: Dict[str, float] = field(default_factory=dict)
    # covenant_name → headroom (positive = OK, negative = breach)
    months_to_breach: Dict[str, Optional[float]] = field(default_factory=dict)
    tightest_covenant: Optional[str] = None
    description: str = ""


@dataclass
class ConversionScenario:
    """Conversion analysis for a single instrument at a single valuation."""
    instrument_id: str
    instrument_type: str            # "convertible_note", "safe"
    holder: str
    principal: float
    accrued_interest: float = 0.0
    converts: bool = False
    conversion_price: Optional[float] = None
    shares_issued: Optional[float] = None
    dilution_pct: float = 0.0
    conversion_method: str = ""     # "cap", "discount", "cap_and_discount"
    effective_valuation: Optional[float] = None
    interest_treatment: str = ""    # "converts", "forgiven", "repaid"
    source_clauses: List[str] = field(default_factory=list)


@dataclass
class ConversionAnalysis:
    """Complete conversion analysis across instruments and exit scenarios."""
    scenarios: Dict[float, List[ConversionScenario]] = field(default_factory=dict)
    # valuation → list of conversion scenarios per instrument
    total_dilution_by_valuation: Dict[float, float] = field(default_factory=dict)
    cash_repayment_by_valuation: Dict[float, float] = field(default_factory=dict)
    description: str = ""


@dataclass
class WarrantAnalysis:
    """Warrant dilution analysis across valuations."""
    instrument_id: str
    holder: str
    exercise_price: float
    shares: Optional[int] = None
    in_the_money_above: float = 0.0
    dilution_by_valuation: Dict[float, float] = field(default_factory=dict)
    # valuation → dilution %
    value_transfer_by_valuation: Dict[float, float] = field(default_factory=dict)
    # valuation → dollar value to warrant holder
    cashless_shares_by_valuation: Dict[float, int] = field(default_factory=dict)
    description: str = ""


@dataclass
class PIKProjection:
    """PIK balance projection over time."""
    instrument_id: str
    holder: str
    initial_principal: float
    periods: List[AmortizationPeriod] = field(default_factory=list)
    final_balance: float = 0.0
    total_pik_capitalized: float = 0.0
    effective_annual_rate: float = 0.0  # including compounding
    description: str = ""


@dataclass
class IntercreditorAnalysis:
    """Priority waterfall and recovery analysis for debt stack."""
    priority_order: List[str] = field(default_factory=list)
    # instrument_id in payment priority order
    recovery_by_instrument: Dict[str, Dict[float, float]] = field(default_factory=dict)
    # instrument_id → {liquidation_value → recovery_pct}
    subordination_impact: Dict[str, float] = field(default_factory=dict)
    # instrument_id → basis points of yield premium for subordination risk
    standstill_risks: List[str] = field(default_factory=list)
    payment_blockage_scenarios: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class DebtCapacityAnalysis:
    """Debt capacity evaluation."""
    current_total_debt: float = 0.0
    max_debt_capacity: float = 0.0
    available_capacity: float = 0.0
    limiting_factor: str = ""       # "dscr_covenant", "leverage_covenant", "revenue_multiple"
    incremental_dscr_impact: Optional[float] = None
    runway_impact_months: Optional[float] = None
    recommendation: str = ""
    description: str = ""


@dataclass
class EffectiveCostBreakdown:
    """All-in cost of a single instrument."""
    instrument_id: str
    headline_rate: float = 0.0
    warrant_cost_annualized: float = 0.0
    pik_spread_cost: float = 0.0
    end_of_term_payment_cost: float = 0.0
    commitment_fee_cost: float = 0.0
    covenant_cost_estimate: float = 0.0  # embedded option cost of covenants
    effective_annual_rate: float = 0.0
    components: List[str] = field(default_factory=list)


@dataclass
class DebtStructureAnalysis:
    """Complete analysis of a company's debt/convertible/SAFE/warrant/PIK structure."""
    company_id: str
    term_loans: List[TermLoan] = field(default_factory=list)
    revolving_facilities: List[RevolvingFacility] = field(default_factory=list)
    convertible_notes: List[ConvertibleNote] = field(default_factory=list)
    safes: List[SAFEInstrument] = field(default_factory=list)
    warrants: List[WarrantInstrument] = field(default_factory=list)
    pik_instruments: List[PIKInstrument] = field(default_factory=list)
    rbf_instruments: List[RevenueBasedFinancing] = field(default_factory=list)
    intercreditor: List[IntercreditorTerms] = field(default_factory=list)

    # Aggregates
    total_debt_outstanding: float = 0.0
    total_convertible_outstanding: float = 0.0
    total_safe_outstanding: float = 0.0
    total_warrant_exposure: float = 0.0
    total_pik_outstanding: float = 0.0
    weighted_average_interest: float = 0.0

    # Analyses
    debt_service: Optional[DebtServiceAnalysis] = None
    conversion: Optional[ConversionAnalysis] = None
    warrant_analyses: List[WarrantAnalysis] = field(default_factory=list)
    pik_projections: List[PIKProjection] = field(default_factory=list)
    intercreditor_analysis: Optional[IntercreditorAnalysis] = None
    debt_capacity: Optional[DebtCapacityAnalysis] = None
    effective_costs: List[EffectiveCostBreakdown] = field(default_factory=list)

    def all_instruments_count(self) -> int:
        return (
            len(self.term_loans) + len(self.revolving_facilities)
            + len(self.convertible_notes) + len(self.safes)
            + len(self.warrants) + len(self.pik_instruments)
            + len(self.rbf_instruments)
        )


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class AdvancedDebtStructures:
    """
    Full-spectrum debt structure analysis.

    Reads resolved clause parameters. Every term traced to its source clause.
    Produces: amortization schedules, DSCR analysis, conversion scenarios,
    warrant dilution, PIK projections, intercreditor waterfalls, effective cost.
    """

    def __init__(self):
        logger.info("AdvancedDebtStructures service initialized")

    # ------------------------------------------------------------------
    # Primary entry point: build from resolved parameters
    # ------------------------------------------------------------------

    def analyze_from_params(
        self,
        params: ResolvedParameterSet,
        financial_state: Optional[Any] = None,
        reference_valuations: Optional[List[float]] = None,
    ) -> DebtStructureAnalysis:
        """
        Build complete debt structure analysis from resolved clause parameters.

        Every instrument is constructed from document-derived parameters
        with full attribution. No manual inputs required.
        """
        valuations = reference_valuations or [
            10e6, 25e6, 50e6, 100e6, 200e6, 500e6,
        ]
        analysis = DebtStructureAnalysis(company_id=params.company_id)

        # Phase 1: Extract typed instruments from parameters
        self._extract_term_loans(analysis, params)
        self._extract_revolving_facilities(analysis, params)
        self._extract_convertible_notes(analysis, params)
        self._extract_safes(analysis, params)
        self._extract_warrants(analysis, params)
        self._extract_pik_instruments(analysis, params)
        self._extract_rbf_instruments(analysis, params)
        self._extract_intercreditor(analysis, params)

        # Phase 2: Compute aggregates
        self._compute_aggregates(analysis)

        # Phase 3: Run analyses
        analysis.debt_service = self.compute_debt_service(analysis, financial_state)
        analysis.conversion = self.model_conversion_scenarios(analysis, valuations)
        analysis.warrant_analyses = [
            self.model_warrant_dilution(w, valuations) for w in analysis.warrants
        ]
        analysis.pik_projections = [
            self.project_pik_balance(p) for p in analysis.pik_instruments
        ]
        if analysis.intercreditor:
            analysis.intercreditor_analysis = self.analyze_intercreditor(analysis)
        analysis.debt_capacity = self.evaluate_debt_capacity(analysis, financial_state)
        analysis.effective_costs = [
            self._compute_effective_cost(loan) for loan in analysis.term_loans
        ]

        logger.info(
            f"Debt structure analysis complete: {analysis.all_instruments_count()} "
            f"instruments, ${analysis.total_debt_outstanding:,.0f} debt outstanding"
        )

        return analysis

    # ------------------------------------------------------------------
    # Instrument extraction from ResolvedParameterSet
    # ------------------------------------------------------------------

    def _extract_term_loans(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract term loans from resolved parameters."""
        # Find all debt instruments with interest rates
        rate_params = params.get_all("interest_rate")
        for rate_param in rate_params:
            if rate_param.instrument not in ("debt", "mezzanine"):
                continue

            holder = rate_param.applies_to
            instrument_id = f"term_loan_{holder}"

            # Gather all params for this holder
            maturity = params.get("maturity_date", holder)
            amort = params.get("amortization_schedule", holder)
            prepay = params.get("prepayment_terms", holder)
            covenant = params.get("covenant_threshold", holder)
            dscr_cov = params.get("covenant_dscr_threshold", holder)
            lev_cov = params.get("covenant_leverage_threshold", holder)
            cross_def = params.get("cross_default", holder)
            coc = params.get("change_of_control", holder)
            restricted = params.get("restricted_payment", holder)
            accel = params.get("acceleration_trigger", holder)
            step_in = params.get("step_in_rights", holder)

            covenants: Dict[str, Any] = {}
            if covenant and isinstance(covenant.value, dict):
                covenants.update(covenant.value)
            if dscr_cov:
                covenants["dscr"] = dscr_cov.value
            if lev_cov:
                covenants["leverage"] = lev_cov.value

            # Determine seniority from instrument type or context
            seniority = "senior"
            if rate_param.instrument == "mezzanine":
                seniority = "mezzanine"
            elif any("subordinat" in str(getattr(c, "source_quote", "")).lower()
                      for c in [rate_param]):
                seniority = "subordinated"

            # Determine principal from instrument summary
            principal = self._find_principal(params, holder)

            # Prepayment terms
            prepay_penalty = 0.0
            prepay_lockout = 0
            make_whole = False
            if prepay and isinstance(prepay.value, dict):
                prepay_penalty = prepay.value.get("penalty_pct", 0.0)
                prepay_lockout = prepay.value.get("lockout_months", 0)
                make_whole = prepay.value.get("make_whole", False)

            # Amortization type
            amort_type = "bullet"
            io_months = 0
            amort_months = None
            if amort and isinstance(amort.value, dict):
                amort_type = amort.value.get("type", "bullet")
                io_months = amort.value.get("interest_only_months", 0)
                amort_months = amort.value.get("total_months")
            elif amort and isinstance(amort.value, str):
                amort_type = amort.value

            # End-of-term payment (common in venture debt)
            eot_pct = 0.0
            eot_param = params.get("end_of_term_payment", holder)
            if eot_param and isinstance(eot_param.value, (int, float)):
                eot_pct = eot_param.value

            source_clauses = [
                c for c in [rate_param, maturity, amort, prepay, covenant,
                            dscr_cov, lev_cov, cross_def, coc, restricted]
                if c is not None
            ]

            loan = TermLoan(
                instrument_id=instrument_id,
                holder=holder,
                principal=principal,
                interest_rate=rate_param.value if isinstance(rate_param.value, (int, float)) else 0.0,
                maturity_date=maturity.value if maturity else None,
                seniority=seniority,
                amortization_type=amort_type,
                interest_only_months=io_months,
                amortization_months=amort_months,
                prepayment_penalty_pct=prepay_penalty,
                prepayment_lockout_months=prepay_lockout,
                make_whole=make_whole,
                end_of_term_payment_pct=eot_pct,
                covenants=covenants,
                cross_default=bool(cross_def and cross_def.value),
                change_of_control_acceleration=bool(
                    coc and isinstance(coc.value, dict) and coc.value.get("acceleration")
                ),
                restricted_payments=restricted.value if restricted else None,
                source_clauses=source_clauses,
            )
            analysis.term_loans.append(loan)

    def _extract_revolving_facilities(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract revolving credit facilities from resolved parameters."""
        for inst in params.instruments:
            if inst.instrument_type != "debt":
                continue
            terms = inst.terms or {}
            if terms.get("facility_type") != "revolving":
                continue

            holder = inst.holder
            rate_param = params.get("interest_rate", holder)
            rate = rate_param.value if rate_param and isinstance(rate_param.value, (int, float)) else 0.0

            facility = RevolvingFacility(
                instrument_id=f"revolver_{holder}",
                holder=holder,
                commitment_amount=inst.principal_or_value,
                drawn_amount=terms.get("drawn_amount", 0.0),
                interest_rate=rate,
                undrawn_fee_rate=terms.get("undrawn_fee", 0.0025),
                maturity_date=inst.maturity_date,
                source_clauses=[rate_param] if rate_param else [],
            )
            analysis.revolving_facilities.append(facility)

    def _extract_convertible_notes(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract convertible notes from resolved parameters."""
        # Find instruments of type "convertible"
        discount_params = params.get_all("conversion_discount")
        cap_params = params.get_all("valuation_cap")

        # Gather all holders with convertible terms
        convertible_holders: Dict[str, Dict[str, Any]] = {}
        for p in discount_params:
            if p.instrument == "convertible":
                convertible_holders.setdefault(p.applies_to, {})["discount"] = p
        for p in cap_params:
            if p.instrument in ("convertible", "safe"):
                # Only add to convertible holders if they also have a discount or
                # are explicitly convertible instrument type
                if p.instrument == "convertible":
                    convertible_holders.setdefault(p.applies_to, {})["cap"] = p

        for holder, terms in convertible_holders.items():
            discount_p = terms.get("discount")
            cap_p = terms.get("cap")
            rate_param = params.get("interest_rate", holder)
            maturity = params.get("maturity_date", holder)
            qf = params.get("qualified_financing_threshold", holder)
            mfn_param = params.get("mfn", holder)
            principal = self._find_principal(params, holder)

            # Interest treatment on conversion
            interest_type = "cash"
            interest_converts = True
            int_treatment_param = params.get("interest_treatment", holder)
            if int_treatment_param:
                val = int_treatment_param.value
                if val in ("pik", "forgiven_on_conversion"):
                    interest_type = val
                if val == "forgiven_on_conversion":
                    interest_converts = False

            note = ConvertibleNote(
                instrument_id=f"convertible_{holder}",
                holder=holder,
                principal=principal,
                interest_rate=(
                    rate_param.value if rate_param
                    and isinstance(rate_param.value, (int, float)) else 0.0
                ),
                interest_type=interest_type,
                maturity_date=maturity.value if maturity else None,
                conversion_discount=(
                    discount_p.value if discount_p
                    and isinstance(discount_p.value, (int, float)) else 0.0
                ),
                valuation_cap=(
                    cap_p.value if cap_p
                    and isinstance(cap_p.value, (int, float)) else None
                ),
                qualified_financing_threshold=(
                    qf.value if qf
                    and isinstance(qf.value, (int, float)) else None
                ),
                interest_converts=interest_converts,
                mfn=bool(mfn_param and mfn_param.value),
                source_clauses=[
                    c for c in [discount_p, cap_p, rate_param, maturity, qf, mfn_param]
                    if c is not None
                ],
            )
            analysis.convertible_notes.append(note)

    def _extract_safes(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract SAFE instruments from resolved parameters."""
        # SAFEs have valuation_cap and/or discount but instrument type = "safe"
        cap_params = [p for p in params.get_all("valuation_cap") if p.instrument == "safe"]
        discount_params = [p for p in params.get_all("conversion_discount") if p.instrument == "safe"]

        safe_holders: Dict[str, Dict[str, Any]] = {}
        for p in cap_params:
            safe_holders.setdefault(p.applies_to, {})["cap"] = p
        for p in discount_params:
            safe_holders.setdefault(p.applies_to, {})["discount"] = p

        for holder, terms in safe_holders.items():
            cap_p = terms.get("cap")
            discount_p = terms.get("discount")
            qf = params.get("qualified_financing_threshold", holder)
            pro_rata = params.get("pro_rata_rights", holder)
            mfn_param = params.get("mfn", holder)
            principal = self._find_principal(params, holder)

            # Determine SAFE type
            safe_type = "post_money"
            if mfn_param and mfn_param.value:
                safe_type = "mfn"

            safe = SAFEInstrument(
                instrument_id=f"safe_{holder}",
                holder=holder,
                investment_amount=principal,
                safe_type=safe_type,
                valuation_cap=(
                    cap_p.value if cap_p
                    and isinstance(cap_p.value, (int, float)) else None
                ),
                discount_rate=(
                    discount_p.value if discount_p
                    and isinstance(discount_p.value, (int, float)) else 0.0
                ),
                pro_rata_rights=bool(pro_rata and pro_rata.value),
                mfn=bool(mfn_param and mfn_param.value),
                qualified_financing_threshold=(
                    qf.value if qf
                    and isinstance(qf.value, (int, float)) else None
                ),
                source_clauses=[
                    c for c in [cap_p, discount_p, qf, pro_rata, mfn_param]
                    if c is not None
                ],
            )
            analysis.safes.append(safe)

    def _extract_warrants(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract warrant instruments from resolved parameters."""
        coverage_params = params.get_all("warrant_coverage")
        exercise_params = params.get_all("warrant_exercise_price")
        expiry_params = params.get_all("warrant_expiry")

        warrant_holders: Dict[str, Dict[str, ClauseParameter]] = {}
        for p in coverage_params:
            warrant_holders.setdefault(p.applies_to, {})["coverage"] = p
        for p in exercise_params:
            warrant_holders.setdefault(p.applies_to, {})["exercise"] = p
        for p in expiry_params:
            warrant_holders.setdefault(p.applies_to, {})["expiry"] = p

        for holder, terms in warrant_holders.items():
            cov_p = terms.get("coverage")
            ex_p = terms.get("exercise")
            exp_p = terms.get("expiry")

            warrant = WarrantInstrument(
                instrument_id=f"warrant_{holder}",
                holder=holder,
                coverage_pct=(
                    cov_p.value if cov_p
                    and isinstance(cov_p.value, (int, float)) else 0.0
                ),
                exercise_price=(
                    ex_p.value if ex_p
                    and isinstance(ex_p.value, (int, float)) else 0.0
                ),
                expiry_date=exp_p.value if exp_p else None,
                cashless_exercise=True,  # default for startup warrants
                source_clauses=[
                    c for c in [cov_p, ex_p, exp_p] if c is not None
                ],
            )
            analysis.warrants.append(warrant)

    def _extract_pik_instruments(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract PIK instruments from resolved parameters."""
        pik_params = params.get_all("pik_toggle")
        for pik_param in pik_params:
            holder = pik_param.applies_to
            pik_rate_param = params.get("pik_rate", holder)
            cash_rate_param = params.get("interest_rate", holder)
            maturity = params.get("maturity_date", holder)
            principal = self._find_principal(params, holder)

            # Determine toggle type from clause
            toggle_type = "mandatory_pik"
            if isinstance(pik_param.value, dict):
                toggle_type = pik_param.value.get("type", "pik_toggle")
            elif isinstance(pik_param.value, str):
                toggle_type = pik_param.value
            elif pik_param.value is True:
                toggle_type = "pik_toggle"

            # Toggle threshold
            toggle_threshold = None
            if isinstance(pik_param.value, dict) and "threshold" in pik_param.value:
                toggle_threshold = pik_param.value["threshold"]

            # Step-up margin
            step_up = 0.0
            if isinstance(pik_param.value, dict):
                step_up = pik_param.value.get("step_up", 0.0)

            pik = PIKInstrument(
                instrument_id=f"pik_{holder}",
                holder=holder,
                principal=principal,
                pik_rate=(
                    pik_rate_param.value if pik_rate_param
                    and isinstance(pik_rate_param.value, (int, float)) else 0.0
                ),
                cash_rate=(
                    cash_rate_param.value if cash_rate_param
                    and isinstance(cash_rate_param.value, (int, float)) else 0.0
                ),
                toggle_type=toggle_type,
                toggle_threshold=toggle_threshold,
                pik_margin_step_up=step_up,
                maturity_date=maturity.value if maturity else None,
                source_clauses=[
                    c for c in [pik_param, pik_rate_param, cash_rate_param, maturity]
                    if c is not None
                ],
            )
            analysis.pik_instruments.append(pik)

    def _extract_rbf_instruments(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract revenue-based financing from resolved parameters."""
        for inst in params.instruments:
            if inst.instrument_type != "revenue_based":
                continue
            terms = inst.terms or {}
            rbf = RevenueBasedFinancing(
                instrument_id=f"rbf_{inst.holder}",
                holder=inst.holder,
                advance_amount=inst.principal_or_value,
                repayment_cap=terms.get("repayment_cap", 1.5),
                revenue_share_pct=terms.get("revenue_share_pct", 0.0),
                minimum_monthly_payment=terms.get("minimum_monthly", 0.0),
                repayment_period_months=terms.get("repayment_months"),
            )
            analysis.rbf_instruments.append(rbf)

    def _extract_intercreditor(
        self, analysis: DebtStructureAnalysis, params: ResolvedParameterSet
    ) -> None:
        """Extract intercreditor terms from resolved parameters."""
        for inst in params.instruments:
            if inst.instrument_type != "intercreditor":
                continue
            terms = inst.terms or {}
            ic = IntercreditorTerms(
                senior_facility_id=terms.get("senior_facility", ""),
                junior_facility_id=terms.get("junior_facility", ""),
                subordination_type=terms.get("subordination_type", "contractual"),
                standstill_period_months=terms.get("standstill_months", 0),
                payment_blockage_triggers=terms.get("blockage_triggers", []),
                turnover_provisions=terms.get("turnover", False),
                enforcement_standstill=terms.get("enforcement_standstill", False),
                shared_collateral=terms.get("shared_collateral", False),
            )
            analysis.intercreditor.append(ic)

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def _compute_aggregates(self, analysis: DebtStructureAnalysis) -> None:
        """Compute aggregate debt metrics."""
        total_debt = 0.0
        weighted_rate_sum = 0.0

        for loan in analysis.term_loans:
            total_debt += loan.principal
            weighted_rate_sum += loan.principal * loan.interest_rate

        for revolver in analysis.revolving_facilities:
            total_debt += revolver.drawn_amount
            weighted_rate_sum += revolver.drawn_amount * revolver.interest_rate

        analysis.total_debt_outstanding = total_debt
        analysis.weighted_average_interest = (
            weighted_rate_sum / total_debt if total_debt > 0 else 0.0
        )

        analysis.total_convertible_outstanding = sum(
            n.principal for n in analysis.convertible_notes
        )
        analysis.total_safe_outstanding = sum(
            s.investment_amount for s in analysis.safes
        )
        analysis.total_pik_outstanding = sum(
            p.principal for p in analysis.pik_instruments
        )

        # Warrant exposure = total associated debt * coverage %
        for w in analysis.warrants:
            if w.associated_debt_id:
                assoc = next(
                    (l for l in analysis.term_loans if l.instrument_id == w.associated_debt_id),
                    None,
                )
                if assoc:
                    analysis.total_warrant_exposure += assoc.principal * w.coverage_pct
            else:
                analysis.total_warrant_exposure += w.coverage_pct  # already a dollar value

    # ------------------------------------------------------------------
    # Amortization schedule
    # ------------------------------------------------------------------

    def compute_amortization_schedule(
        self, loan: TermLoan, periods: Optional[int] = None
    ) -> List[AmortizationPeriod]:
        """
        Build period-by-period amortization schedule.

        Handles: bullet, interest-only-then-bullet, equal installment.
        """
        if not periods:
            periods = loan.amortization_months or 36

        schedule: List[AmortizationPeriod] = []
        balance = loan.principal
        monthly_rate = loan.interest_rate / 12
        cum_interest = 0.0
        cum_principal = 0.0

        for i in range(1, periods + 1):
            interest = balance * monthly_rate
            cum_interest += interest

            if loan.amortization_type == "bullet":
                # Interest-only, bullet at maturity
                principal_pmt = loan.principal if i == periods else 0.0
            elif loan.amortization_type == "interest_only_then_bullet":
                if i <= loan.interest_only_months:
                    principal_pmt = 0.0
                elif i == periods:
                    principal_pmt = balance
                else:
                    # Equal installments for remaining periods
                    remaining = periods - loan.interest_only_months
                    principal_pmt = loan.principal / remaining if remaining > 0 else balance
            elif loan.amortization_type == "equal_installment":
                # Standard amortization formula
                if monthly_rate > 0 and periods > 0:
                    pmt = loan.principal * (
                        monthly_rate * (1 + monthly_rate) ** periods
                    ) / ((1 + monthly_rate) ** periods - 1)
                    principal_pmt = pmt - interest
                else:
                    principal_pmt = loan.principal / periods
            else:
                principal_pmt = 0.0

            principal_pmt = min(principal_pmt, balance)
            cum_principal += principal_pmt
            total_pmt = interest + principal_pmt

            # End-of-term payment
            if i == periods and loan.end_of_term_payment_pct > 0:
                eot = loan.principal * loan.end_of_term_payment_pct
                total_pmt += eot

            schedule.append(AmortizationPeriod(
                period=i,
                opening_balance=balance,
                principal_payment=principal_pmt,
                interest_payment=interest,
                total_payment=total_pmt,
                closing_balance=balance - principal_pmt,
                cumulative_interest=cum_interest,
                cumulative_principal=cum_principal,
            ))

            balance -= principal_pmt
            if balance <= 0:
                break

        return schedule

    # ------------------------------------------------------------------
    # Debt service coverage
    # ------------------------------------------------------------------

    def compute_debt_service(
        self,
        analysis: DebtStructureAnalysis,
        financial_state: Optional[Any] = None,
    ) -> DebtServiceAnalysis:
        """
        Compute real DSCR from actual obligations.

        Uses: all term loans, revolvers (drawn), PIK (cash portion),
        RBF minimum payments.
        """
        result = DebtServiceAnalysis()

        # Annual interest
        for loan in analysis.term_loans:
            annual_interest = loan.principal * loan.interest_rate
            result.total_annual_interest += annual_interest
            # Principal amortization (first year)
            if loan.amortization_type == "equal_installment" and loan.amortization_months:
                result.total_annual_principal += loan.principal / (loan.amortization_months / 12)
            # End-of-term: amortize over life
            if loan.end_of_term_payment_pct > 0 and loan.amortization_months:
                eot_annual = (loan.principal * loan.end_of_term_payment_pct) / (loan.amortization_months / 12)
                result.total_annual_interest += eot_annual

        for revolver in analysis.revolving_facilities:
            result.total_annual_interest += revolver.drawn_amount * revolver.interest_rate
            result.total_annual_interest += (
                (revolver.commitment_amount - revolver.drawn_amount) * revolver.undrawn_fee_rate
            )

        # PIK instruments — only cash portion counts for debt service
        for pik in analysis.pik_instruments:
            result.total_annual_interest += pik.principal * pik.cash_rate

        # RBF minimum payments
        for rbf in analysis.rbf_instruments:
            result.total_annual_principal += rbf.minimum_monthly_payment * 12

        result.total_annual_debt_service = (
            result.total_annual_interest + result.total_annual_principal
        )

        # Compute DSCR if we have financial state
        if financial_state:
            ebitda = getattr(financial_state, "ebitda", None)
            if ebitda is None:
                revenue = getattr(financial_state, "revenue", 0) or 0
                burn = getattr(financial_state, "burn_rate", 0) or 0
                # Rough EBITDA estimate
                ebitda = revenue - (burn * 12) if revenue > burn * 12 else 0

            if isinstance(ebitda, (int, float)) and ebitda > 0 and result.total_annual_debt_service > 0:
                result.dscr = ebitda / result.total_annual_debt_service
                result.interest_coverage_ratio = ebitda / result.total_annual_interest if result.total_annual_interest > 0 else None

        # Covenant headroom
        all_covenants: Dict[str, float] = {}
        for loan in analysis.term_loans:
            for cov_name, cov_val in loan.covenants.items():
                if isinstance(cov_val, (int, float)):
                    all_covenants[f"{cov_name}:{loan.holder}"] = cov_val

        tightest_headroom = float("inf")
        for cov_key, threshold in all_covenants.items():
            metric_name = cov_key.split(":")[0]
            if metric_name == "dscr" and result.dscr is not None:
                headroom = result.dscr - threshold
                result.covenant_headroom[cov_key] = headroom
                if headroom < tightest_headroom:
                    tightest_headroom = headroom
                    result.tightest_covenant = cov_key
            elif metric_name == "leverage" and analysis.total_debt_outstanding > 0:
                if financial_state:
                    ebitda = getattr(financial_state, "ebitda", 0) or 1
                    actual_leverage = analysis.total_debt_outstanding / max(ebitda, 1)
                    headroom = threshold - actual_leverage
                    result.covenant_headroom[cov_key] = headroom
                    if headroom < tightest_headroom:
                        tightest_headroom = headroom
                        result.tightest_covenant = cov_key

        result.description = (
            f"Total debt service: ${result.total_annual_debt_service:,.0f}/yr "
            f"(interest: ${result.total_annual_interest:,.0f}, "
            f"principal: ${result.total_annual_principal:,.0f}). "
            + (f"DSCR: {result.dscr:.2f}x. " if result.dscr else "DSCR: N/A. ")
            + (f"Tightest covenant: {result.tightest_covenant} "
               f"(headroom: {tightest_headroom:.2f}x)." if result.tightest_covenant else "")
        )

        return result

    # ------------------------------------------------------------------
    # Conversion scenarios
    # ------------------------------------------------------------------

    def model_conversion_scenarios(
        self,
        analysis: DebtStructureAnalysis,
        valuations: List[float],
    ) -> ConversionAnalysis:
        """
        For each convertible/SAFE, at each valuation:
        does it convert? At what price? How many shares? What dilution?
        """
        result = ConversionAnalysis()

        for valuation in valuations:
            scenarios: List[ConversionScenario] = []

            # Convertible notes
            for note in analysis.convertible_notes:
                scenario = self._model_note_conversion(note, valuation)
                scenarios.append(scenario)

            # SAFEs
            for safe in analysis.safes:
                scenario = self._model_safe_conversion(safe, valuation)
                scenarios.append(scenario)

            result.scenarios[valuation] = scenarios
            result.total_dilution_by_valuation[valuation] = sum(
                s.dilution_pct for s in scenarios if s.converts
            )
            result.cash_repayment_by_valuation[valuation] = sum(
                s.principal + s.accrued_interest
                for s in scenarios if not s.converts
            )

        # Description
        if result.scenarios:
            mid_val = valuations[len(valuations) // 2]
            mid_scenarios = result.scenarios.get(mid_val, [])
            converting = [s for s in mid_scenarios if s.converts]
            result.description = (
                f"At ${mid_val/1e6:.0f}M: {len(converting)} instruments convert, "
                f"{result.total_dilution_by_valuation.get(mid_val, 0)*100:.1f}% total dilution."
            )

        return result

    def _model_note_conversion(
        self, note: ConvertibleNote, valuation: float
    ) -> ConversionScenario:
        """Model conversion of a single convertible note at a given valuation."""
        scenario = ConversionScenario(
            instrument_id=note.instrument_id,
            instrument_type="convertible_note",
            holder=note.holder,
            principal=note.principal,
            source_clauses=[c.source_clause_id for c in note.source_clauses],
        )

        # Accrued interest estimate (assume 2 years for illustration)
        scenario.accrued_interest = note.principal * note.interest_rate * 2

        # Check if qualified financing triggers auto-conversion
        if note.qualified_financing_threshold and valuation < note.qualified_financing_threshold:
            # Below threshold — no auto-conversion, holder can choose at maturity
            scenario.converts = note.optional_convert_at_maturity
            if not scenario.converts:
                scenario.interest_treatment = "repaid"
                return scenario

        scenario.converts = True

        # Compute conversion price = min(cap price, discounted price)
        conversion_prices: List[Tuple[float, str]] = []

        if note.valuation_cap and note.valuation_cap > 0:
            # Price per share at cap (assume 10M shares outstanding for illustration)
            cap_price = note.valuation_cap
            conversion_prices.append((cap_price, "cap"))

        if note.conversion_discount > 0:
            discounted_price = valuation * (1 - note.conversion_discount)
            conversion_prices.append((discounted_price, "discount"))

        if conversion_prices:
            best = min(conversion_prices, key=lambda x: x[0])
            scenario.conversion_price = best[0]
            scenario.conversion_method = best[1]
            if len(conversion_prices) > 1 and best[0] == min(p[0] for p in conversion_prices):
                scenario.conversion_method = "cap_and_discount"
            scenario.effective_valuation = best[0]
        else:
            # No cap or discount — converts at round valuation
            scenario.conversion_price = valuation
            scenario.effective_valuation = valuation
            scenario.conversion_method = "at_round_price"

        # Shares and dilution
        converting_amount = note.principal
        if note.interest_converts:
            converting_amount += scenario.accrued_interest
            scenario.interest_treatment = "converts"
        else:
            scenario.interest_treatment = "repaid" if note.interest_type != "forgiven_on_conversion" else "forgiven"

        if scenario.conversion_price and scenario.conversion_price > 0:
            scenario.dilution_pct = converting_amount / (valuation + converting_amount)

        return scenario

    def _model_safe_conversion(
        self, safe: SAFEInstrument, valuation: float
    ) -> ConversionScenario:
        """Model conversion of a SAFE at a given valuation."""
        scenario = ConversionScenario(
            instrument_id=safe.instrument_id,
            instrument_type="safe",
            holder=safe.holder,
            principal=safe.investment_amount,
            source_clauses=[c.source_clause_id for c in safe.source_clauses],
        )

        # SAFEs always convert on qualified financing (no interest)
        scenario.accrued_interest = 0.0
        scenario.interest_treatment = "n/a"

        # Check qualified financing threshold
        if safe.qualified_financing_threshold and valuation < safe.qualified_financing_threshold:
            scenario.converts = False
            return scenario

        scenario.converts = True

        # Conversion price
        conversion_prices: List[Tuple[float, str]] = []

        if safe.valuation_cap and safe.valuation_cap > 0:
            if safe.safe_type == "post_money":
                # Post-money SAFE: cap IS the post-money valuation
                cap_price = safe.valuation_cap
            else:
                # Pre-money: cap is pre-money
                cap_price = safe.valuation_cap
            conversion_prices.append((cap_price, "cap"))

        if safe.discount_rate > 0:
            discounted = valuation * (1 - safe.discount_rate)
            conversion_prices.append((discounted, "discount"))

        if conversion_prices:
            best = min(conversion_prices, key=lambda x: x[0])
            scenario.conversion_price = best[0]
            scenario.conversion_method = best[1]
            scenario.effective_valuation = best[0]
        else:
            scenario.conversion_price = valuation
            scenario.effective_valuation = valuation
            scenario.conversion_method = "at_round_price"

        # Dilution
        if scenario.conversion_price and scenario.conversion_price > 0:
            scenario.dilution_pct = safe.investment_amount / (valuation + safe.investment_amount)

        return scenario

    # ------------------------------------------------------------------
    # Warrant analysis
    # ------------------------------------------------------------------

    def model_warrant_dilution(
        self, warrant: WarrantInstrument, valuations: List[float]
    ) -> WarrantAnalysis:
        """
        At each valuation: in the money? Cashless net shares? Dilution?
        Value transfer to warrant holder?
        """
        result = WarrantAnalysis(
            instrument_id=warrant.instrument_id,
            holder=warrant.holder,
            exercise_price=warrant.exercise_price,
            shares=warrant.shares,
            in_the_money_above=warrant.exercise_price,
        )

        for val in valuations:
            if val <= 0:
                continue

            # Assume price per share = valuation / 10M shares (illustrative)
            assumed_shares = 10_000_000
            price_per_share = val / assumed_shares

            if price_per_share <= warrant.exercise_price:
                result.dilution_by_valuation[val] = 0.0
                result.value_transfer_by_valuation[val] = 0.0
                result.cashless_shares_by_valuation[val] = 0
                continue

            # Coverage-based warrants: shares = coverage_pct * fully diluted
            if warrant.coverage_pct > 0 and not warrant.shares:
                warrant_shares = int(assumed_shares * warrant.coverage_pct)
            else:
                warrant_shares = warrant.shares or 0

            if warrant.cashless_exercise and price_per_share > warrant.exercise_price:
                # Cashless: net shares = shares × (price - exercise) / price
                net_shares = int(
                    warrant_shares * (price_per_share - warrant.exercise_price) / price_per_share
                )
                result.cashless_shares_by_valuation[val] = net_shares
                dilution = net_shares / (assumed_shares + net_shares)
            else:
                dilution = warrant_shares / (assumed_shares + warrant_shares)
                result.cashless_shares_by_valuation[val] = warrant_shares

            result.dilution_by_valuation[val] = dilution
            result.value_transfer_by_valuation[val] = (
                warrant_shares * (price_per_share - warrant.exercise_price)
            )

        result.description = (
            f"Warrant for {warrant.holder}: exercise at ${warrant.exercise_price:,.2f}. "
            f"{'Cashless exercise. ' if warrant.cashless_exercise else ''}"
            f"Coverage: {warrant.coverage_pct*100:.2f}%."
        )

        return result

    # ------------------------------------------------------------------
    # PIK projection
    # ------------------------------------------------------------------

    def project_pik_balance(
        self, pik: PIKInstrument, periods: int = 20
    ) -> PIKProjection:
        """
        Period-by-period PIK balance projection showing compounding effect.

        Shows: how much the debt grows if PIK is elected every period.
        """
        result = PIKProjection(
            instrument_id=pik.instrument_id,
            holder=pik.holder,
            initial_principal=pik.principal,
        )

        balance = pik.principal
        total_pik = 0.0

        freq_map = {
            "monthly": 12, "quarterly": 4, "semi_annual": 2, "annual": 1,
        }
        periods_per_year = freq_map.get(pik.capitalization_frequency, 4)
        periodic_rate = (pik.pik_rate + pik.pik_margin_step_up) / periods_per_year
        cash_periodic_rate = pik.cash_rate / periods_per_year

        for i in range(1, periods + 1):
            opening = balance

            if pik.toggle_type == "mandatory_pik":
                # All interest capitalizes
                pik_amount = opening * periodic_rate
                cash_payment = 0.0
            elif pik.toggle_type == "pik_toggle":
                # Assume worst case: PIK elected every period
                pik_amount = opening * periodic_rate
                cash_payment = 0.0
            elif pik.toggle_type == "pik_cash_split":
                # Split: some cash, some PIK
                pik_amount = opening * periodic_rate
                cash_payment = opening * cash_periodic_rate
            else:
                pik_amount = opening * periodic_rate
                cash_payment = 0.0

            balance += pik_amount
            total_pik += pik_amount

            # Check max PIK periods
            if pik.max_pik_periods and i > pik.max_pik_periods:
                # Forced to pay cash after max PIK periods
                pik_amount = 0.0
                cash_payment = opening * (periodic_rate + cash_periodic_rate)

            result.periods.append(AmortizationPeriod(
                period=i,
                opening_balance=opening,
                pik_capitalized=pik_amount,
                interest_payment=cash_payment,
                total_payment=cash_payment,
                closing_balance=balance,
                cumulative_interest=total_pik + cash_payment * i,
            ))

        result.final_balance = balance
        result.total_pik_capitalized = total_pik

        # Effective rate including compounding
        if pik.principal > 0 and periods > 0:
            years = periods / periods_per_year
            if years > 0:
                result.effective_annual_rate = (
                    (balance / pik.principal) ** (1 / years) - 1
                )

        result.description = (
            f"PIK {pik.holder}: ${pik.principal:,.0f} initial → "
            f"${balance:,.0f} after {periods} periods "
            f"(+${total_pik:,.0f} capitalized). "
            f"Effective rate: {result.effective_annual_rate*100:.1f}%/yr."
        )

        return result

    # ------------------------------------------------------------------
    # Intercreditor analysis
    # ------------------------------------------------------------------

    def analyze_intercreditor(
        self, analysis: DebtStructureAnalysis
    ) -> IntercreditorAnalysis:
        """
        Priority waterfall for debt payoff. Recovery rates by seniority.
        Subordination impact. Standstill and blockage scenarios.
        """
        result = IntercreditorAnalysis()

        # Build priority order
        seniority_order = {"senior": 0, "subordinated": 1, "mezzanine": 2}
        sorted_loans = sorted(
            analysis.term_loans,
            key=lambda l: seniority_order.get(l.seniority, 99),
        )
        result.priority_order = [l.instrument_id for l in sorted_loans]

        # Recovery analysis at different liquidation values
        total_debt = sum(l.principal for l in sorted_loans)
        test_values = [
            total_debt * 0.25, total_debt * 0.5, total_debt * 0.75,
            total_debt, total_debt * 1.5,
        ]

        for loan in sorted_loans:
            result.recovery_by_instrument[loan.instrument_id] = {}

        for liq_val in test_values:
            remaining = liq_val
            for loan in sorted_loans:
                recovery = min(remaining, loan.principal)
                recovery_pct = recovery / loan.principal if loan.principal > 0 else 0
                result.recovery_by_instrument[loan.instrument_id][liq_val] = recovery_pct
                remaining -= recovery
                if remaining <= 0:
                    remaining = 0

        # Subordination yield premium estimate
        for loan in sorted_loans:
            if loan.seniority == "subordinated":
                result.subordination_impact[loan.instrument_id] = 200  # ~200bps premium
            elif loan.seniority == "mezzanine":
                result.subordination_impact[loan.instrument_id] = 400  # ~400bps premium

        # Standstill and blockage
        for ic in analysis.intercreditor:
            if ic.standstill_period_months > 0:
                result.standstill_risks.append(
                    f"Junior facility {ic.junior_facility_id}: {ic.standstill_period_months}-month "
                    f"standstill on enforcement after senior default."
                )
            for trigger in ic.payment_blockage_triggers:
                result.payment_blockage_scenarios.append(
                    f"Payment to {ic.junior_facility_id} blocked on {trigger} "
                    f"of senior facility {ic.senior_facility_id}."
                )

        result.description = (
            f"Debt stack: {len(sorted_loans)} facilities. "
            f"Priority: {' > '.join(result.priority_order)}. "
            f"Total: ${total_debt:,.0f}."
        )

        return result

    # ------------------------------------------------------------------
    # Debt capacity
    # ------------------------------------------------------------------

    def evaluate_debt_capacity(
        self,
        analysis: DebtStructureAnalysis,
        financial_state: Optional[Any] = None,
    ) -> DebtCapacityAnalysis:
        """
        Max additional debt given current covenants and financial state.
        """
        result = DebtCapacityAnalysis()
        result.current_total_debt = analysis.total_debt_outstanding

        if not financial_state:
            result.description = "Cannot evaluate debt capacity without financial state."
            return result

        revenue = getattr(financial_state, "revenue", 0) or 0
        ebitda = getattr(financial_state, "ebitda", None)
        if ebitda is None:
            burn = getattr(financial_state, "burn_rate", 0) or 0
            ebitda = revenue - (burn * 12) if revenue > burn * 12 else 0

        # Method 1: Revenue multiple (venture debt typically 3-4x ARR)
        revenue_capacity = revenue * 3.5

        # Method 2: DSCR-constrained
        # Find tightest DSCR covenant
        min_dscr = 999.0
        for loan in analysis.term_loans:
            dscr_cov = loan.covenants.get("dscr")
            if isinstance(dscr_cov, (int, float)):
                min_dscr = min(min_dscr, dscr_cov)

        dscr_capacity = float("inf")
        if min_dscr < 999 and isinstance(ebitda, (int, float)) and ebitda > 0:
            # Max debt service = EBITDA / min_DSCR
            max_debt_service = ebitda / min_dscr
            current_service = analysis.debt_service.total_annual_debt_service if analysis.debt_service else 0
            incremental_service = max_debt_service - current_service
            # Assume incremental debt at 12% rate
            if incremental_service > 0:
                dscr_capacity = result.current_total_debt + (incremental_service / 0.12)
            else:
                dscr_capacity = result.current_total_debt  # Already at limit

        # Method 3: Leverage-constrained
        leverage_capacity = float("inf")
        for loan in analysis.term_loans:
            lev_cov = loan.covenants.get("leverage")
            if isinstance(lev_cov, (int, float)) and isinstance(ebitda, (int, float)) and ebitda > 0:
                leverage_capacity = min(leverage_capacity, lev_cov * ebitda)

        # Take the most restrictive
        capacities = {
            "revenue_multiple": revenue_capacity,
            "dscr_covenant": dscr_capacity,
            "leverage_covenant": leverage_capacity,
        }

        result.max_debt_capacity = min(
            c for c in capacities.values() if c != float("inf")
        ) if any(c != float("inf") for c in capacities.values()) else revenue_capacity

        result.available_capacity = max(0, result.max_debt_capacity - result.current_total_debt)
        result.limiting_factor = min(capacities, key=capacities.get)

        # DSCR impact of incremental $1M
        if analysis.debt_service and analysis.debt_service.dscr:
            incremental_service = 1_000_000 * 0.12  # 12% assumed
            new_total_service = (
                analysis.debt_service.total_annual_debt_service + incremental_service
            )
            if isinstance(ebitda, (int, float)) and new_total_service > 0:
                result.incremental_dscr_impact = ebitda / new_total_service

        # Runway impact
        burn = getattr(financial_state, "burn_rate", 0) or 0
        if burn > 0 and result.available_capacity > 0:
            result.runway_impact_months = result.available_capacity / burn

        result.recommendation = (
            f"{'Can support' if result.available_capacity > 0 else 'At'} "
            f"{'additional' if result.available_capacity > 0 else ''} debt"
            f"{f' up to ${result.available_capacity:,.0f}' if result.available_capacity > 0 else ' capacity limit'}. "
            f"Limiting factor: {result.limiting_factor}."
        )

        result.description = (
            f"Current: ${result.current_total_debt:,.0f}. "
            f"Max capacity: ${result.max_debt_capacity:,.0f}. "
            f"Available: ${result.available_capacity:,.0f}. "
            f"{result.recommendation}"
        )

        return result

    # ------------------------------------------------------------------
    # Effective cost computation
    # ------------------------------------------------------------------

    def _compute_effective_cost(self, loan: TermLoan) -> EffectiveCostBreakdown:
        """
        All-in cost including warrant kicker, end-of-term payment,
        covenant cost, prepayment cost.
        """
        result = EffectiveCostBreakdown(instrument_id=loan.instrument_id)
        result.headline_rate = loan.interest_rate
        result.components.append(f"Headline interest: {loan.interest_rate*100:.1f}%")

        effective = loan.interest_rate

        # End-of-term payment cost (amortize over life)
        if loan.end_of_term_payment_pct > 0:
            months = loan.amortization_months or 36
            annual_eot = loan.end_of_term_payment_pct / (months / 12)
            result.end_of_term_payment_cost = annual_eot
            effective += annual_eot
            result.components.append(
                f"End-of-term payment ({loan.end_of_term_payment_pct*100:.1f}%): "
                f"+{annual_eot*100:.2f}%/yr"
            )

        # Covenant cost estimate
        if loan.covenants:
            cov_cost = 0.02  # ~2% embedded option cost
            result.covenant_cost_estimate = cov_cost
            effective += cov_cost
            result.components.append("Covenant constraints: ~2.0% embedded cost")

        result.effective_annual_rate = effective
        return result

    def compute_effective_cost_with_warrants(
        self,
        loan: TermLoan,
        warrant: Optional[WarrantInstrument],
        company_valuation: float,
    ) -> EffectiveCostBreakdown:
        """
        Full effective cost including warrant dilution value.
        """
        result = self._compute_effective_cost(loan)

        if warrant and company_valuation > 0:
            warrant_value = company_valuation * warrant.coverage_pct
            months = loan.amortization_months or 36
            annual_warrant_cost = warrant_value / (months / 12) / loan.principal
            result.warrant_cost_annualized = annual_warrant_cost
            result.effective_annual_rate += annual_warrant_cost
            result.components.append(
                f"Warrant coverage ({warrant.coverage_pct*100:.2f}%): "
                f"+{annual_warrant_cost*100:.2f}%/yr at ${company_valuation/1e6:.0f}M valuation"
            )

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_principal(
        self, params: ResolvedParameterSet, holder: str
    ) -> float:
        """Find principal amount for a holder from instrument summaries."""
        for inst in params.instruments:
            if inst.holder == holder:
                return inst.principal_or_value
        return 0.0

    # ------------------------------------------------------------------
    # Legacy API compatibility
    # ------------------------------------------------------------------

    def analyze_debt_structure(self, company_data: Dict[str, Any]) -> DebtStructureAnalysis:
        """Legacy entry point for backward compatibility."""
        # Build a minimal ResolvedParameterSet from raw company data
        params = ResolvedParameterSet(
            company_id=company_data.get("company", "unknown"),
        )
        # Extract instruments from funding rounds
        for round_data in company_data.get("funding_rounds", []):
            round_name = round_data.get("round", "").lower()
            if "debt" in round_name or "note" in round_name:
                amount = round_data.get("amount", 0)
                holder = round_data.get("investor", round_name)
                params.instruments.append(InstrumentSummary(
                    instrument_id=f"legacy_{holder}",
                    instrument_type="debt" if "debt" in round_name else "convertible",
                    holder=holder,
                    principal_or_value=amount,
                    source_documents=[],
                ))
                if "convertible" in round_name:
                    params.parameters[f"conversion_discount:{holder}"] = ClauseParameter(
                        param_type="conversion_discount",
                        value=0.20,
                        applies_to=holder,
                        instrument="convertible",
                        source_document_id="legacy",
                        source_clause_id="legacy",
                        section_reference="Legacy import",
                        source_quote="",
                        document_type="legacy",
                    )
                else:
                    params.parameters[f"interest_rate:{holder}"] = ClauseParameter(
                        param_type="interest_rate",
                        value=0.08,
                        applies_to=holder,
                        instrument="debt",
                        source_document_id="legacy",
                        source_clause_id="legacy",
                        section_reference="Legacy import",
                        source_quote="",
                        document_type="legacy",
                    )
        return self.analyze_from_params(params)
