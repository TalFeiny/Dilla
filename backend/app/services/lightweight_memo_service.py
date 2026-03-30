"""Lightweight Memo Service — 3-4 shot memo generation.

Shot 1 (no LLM): Detect memo type → select template → gather available data
Shot 2 (1 LLM call): Generate all narrative sections in one call
Shot 3 (no LLM): Inject charts/tables from shared_data artifacts
Shot 4 (optional, 1 LLM call): Polish pass if user requests edits

No Supabase persistence — memos are ephemeral session artifacts.
Plan memos are the exception: they serialize to the documents table
for cross-session resumption.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.data_validator import ensure_numeric
from app.services.chart_data_service import (
    format_sankey_chart,
    format_waterfall_chart,
    format_bar_chart,
    format_line_chart,
    format_pie_chart,
)
from app.services.memo_templates import (
    INTENT_TO_TEMPLATE,
    MEMO_TEMPLATES,
)

logger = logging.getLogger(__name__)


class LightweightMemoService:
    """Fast, template-driven memo generation."""

    def __init__(self, model_router, shared_data: Dict[str, Any]):
        self.model_router = model_router
        self.shared_data = shared_data
        self._chart_data_service = None

    def _get_chart_data_service(self):
        """Lazy accessor — one CDS instance per memo instead of per chart."""
        if self._chart_data_service is None:
            try:
                from app.services.chart_data_service import ChartDataService
                self._chart_data_service = ChartDataService()
            except Exception:
                logger.debug("[MEMO] ChartDataService unavailable")
        return self._chart_data_service

    # ------------------------------------------------------------------
    # Shot 1: Intent → Template → Data Audit
    # ------------------------------------------------------------------

    def detect_memo_type(self, prompt: str, explicit_type: Optional[str] = None) -> str:
        """Return template ID from explicit type or prompt keywords."""
        # PE model data is authoritative — always use PE template regardless
        # of explicit_type or keywords. The VC ic_memo template is wrong for PE.
        if self.shared_data.get("pe_model_data"):
            return "pe_ic_memo"

        if explicit_type and explicit_type in MEMO_TEMPLATES:
            return explicit_type

        prompt_lower = prompt.lower()

        # Check keyword map (longest match first to avoid "compare" matching before "comparison")
        for keyword in sorted(INTENT_TO_TEMPLATE, key=len, reverse=True):
            if keyword in prompt_lower:
                return INTENT_TO_TEMPLATE[keyword]

        # Fallback: if companies are mentioned, default to IC memo; else bespoke LP
        companies = self.shared_data.get("companies", [])
        if companies:
            return "ic_memo"
        return "bespoke_lp"

    @staticmethod
    def _has_data(val: Any) -> bool:
        """Return False only for None and empty collections; 0, False, '' are valid data."""
        if val is None:
            return False
        if isinstance(val, (list, dict, set)) and len(val) == 0:
            return False
        return True

    def audit_data(self, template_id: str) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Check what data is available vs needed for this template.

        Returns (available_data, missing_required, missing_optional).
        """
        template = MEMO_TEMPLATES[template_id]
        available: Dict[str, Any] = {}
        missing_required: List[str] = []
        missing_optional: List[str] = []

        for key in template.get("required_data", []):
            val = self.shared_data.get(key)
            if self._has_data(val):
                available[key] = val
            else:
                missing_required.append(key)

        for key in template.get("optional_data", []):
            val = self.shared_data.get(key)
            if self._has_data(val):
                available[key] = val
            else:
                missing_optional.append(key)

        # Also collect all data_keys referenced by sections
        for section in template.get("sections", []):
            for dk in section.get("data_keys", []):
                if dk not in available:
                    val = self.shared_data.get(dk)
                    if self._has_data(val):
                        available[dk] = val

        # ── Always pull in fund-level keys that are useful for any memo ──
        # These feed charts (DPI Sankey, waterfall, NAV, MOIC bar) even when
        # the template doesn't explicitly list them.
        _always_pull = [
            "fund_metrics", "portfolio_health", "fund_scenarios",
            "portfolio_analysis", "fund_context",
        ]
        for key in _always_pull:
            if key not in available:
                val = self.shared_data.get(key)
                if self._has_data(val):
                    available[key] = val

        return available, missing_required, missing_optional

    # ------------------------------------------------------------------
    # Template variable auto-fill (contract drafting)
    # ------------------------------------------------------------------

    def _autofill_template(self, template: Dict[str, Any], available_data: Dict[str, Any]) -> None:
        """Replace {{variable}} placeholders in template with actual company data.

        Mutates the template dict in place — prompt_hints and preamble get concrete values
        so the LLM sees real company names, dates, and jurisdictions instead of placeholders.
        """
        company_ctx = available_data.get("company_context", {})
        if not company_ctx:
            companies = available_data.get("companies", [])
            if companies:
                c = companies[0]
                company_ctx = {
                    "company_name": c.get("company", c.get("name", "")),
                    "jurisdiction": c.get("jurisdiction", ""),
                    "company_address": c.get("address", ""),
                }

        variables = {
            "company_name": company_ctx.get("company_name") or "[COMPANY NAME]",
            "counterparty_name": company_ctx.get("counterparty_name") or "[COUNTERPARTY]",
            "employee_name": company_ctx.get("employee_name") or "[EMPLOYEE NAME]",
            "effective_date": company_ctx.get("effective_date") or datetime.now().strftime("%B %d, %Y"),
            "jurisdiction": company_ctx.get("jurisdiction") or template.get("governing_law_default", "Delaware"),
            "term_months": str(company_ctx.get("term_months", 24)),
            "company_address": company_ctx.get("company_address") or "[ADDRESS]",
            "counterparty_address": company_ctx.get("counterparty_address") or "[ADDRESS]",
            "position_title": company_ctx.get("position_title") or "[POSITION TITLE]",
            "base_salary": company_ctx.get("base_salary") or "[BASE SALARY]",
            "reporting_to": company_ctx.get("reporting_to") or "[REPORTING MANAGER]",
            "probation_months": str(company_ctx.get("probation_months", 6)),
            "notice_period_months": str(company_ctx.get("notice_period_months", 3)),
            "contract_term_months": str(company_ctx.get("contract_term_months", 12)),
            "service_description": company_ctx.get("service_description") or "[DESCRIPTION OF SERVICES]",
            "document_title": company_ctx.get("document_title") or "[DOCUMENT]",
        }

        def _replace_vars(text: str) -> str:
            for var, val in variables.items():
                text = text.replace(f"{{{{{var}}}}}", val)
            return text

        if template.get("preamble"):
            template["preamble"] = _replace_vars(template["preamble"])

        for section in template.get("sections", []):
            if section.get("prompt_hint"):
                section["prompt_hint"] = _replace_vars(section["prompt_hint"])

        if template.get("title_pattern"):
            template["title_pattern"] = _replace_vars(template["title_pattern"])

    # ------------------------------------------------------------------
    # Shot 2: Generate all narrative sections in one LLM call
    # ------------------------------------------------------------------

    async def generate_narratives(
        self,
        template_id: str,
        prompt: str,
        available_data: Dict[str, Any],
    ) -> Dict[str, str]:
        """One LLM call → all narrative sections for the template.

        Returns dict of {section_key: narrative_text}.
        """
        template = MEMO_TEMPLATES[template_id]
        sections = template["sections"]

        # Build the data context (truncated to fit in one call)
        logger.info("[MEMO] generate_narratives: building data summary...")
        data_summary = self._summarize_data(available_data)
        logger.info(f"[MEMO] generate_narratives: data summary built ({len(data_summary)} chars)")

        # Build section prompts — include "clause" type for contract templates
        section_prompts = []
        narrative_keys = []
        for s in sections:
            if s["type"] in ("narrative", "metrics", "clause"):
                narrative_keys.append(s["key"])
                hint = s.get("prompt_hint", "")
                if s["type"] == "clause":
                    clause_meta = f"[Clause type: {s.get('clause_type', 'general')} | Risk: {s.get('risk_level', 'medium')}]"
                    hint = f"{clause_meta}\n{hint}"
                section_prompts.append(
                    f"### {s['heading']}\n"
                    f"Instructions: {hint}\n"
                    f"Data keys available: {', '.join(s['data_keys']) or 'general context'}"
                )

        if not section_prompts:
            return {}

        # Build fund context for system prompt
        fund_ctx = available_data.get("fund_context", {})
        fund_size_str = ""
        if fund_ctx:
            fs = fund_ctx.get("fund_size", 0)
            rem = fund_ctx.get("remaining_capital", 0)
            fn = fund_ctx.get("fund_name", "")
            if fs and isinstance(fs, (int, float)) and fs > 0:
                fund_size_str = f"Fund: {fn + ' — ' if fn else ''}${fs / 1e6:,.0f}M total, ${rem / 1e6:,.0f}M remaining. "

        # Build company names for context
        companies = available_data.get("companies", [])
        company_names = [c.get("company", "Unknown") for c in companies[:5]]
        company_str = f"Companies under analysis: {', '.join(company_names)}. " if company_names else ""

        # Determine if this is a large portfolio (changes format guidance)
        num_companies = len(companies)
        is_portfolio = num_companies > 3

        # Check template type — PE, contract, or default VC
        is_pe = template.get("pe_mode", False)
        is_contract = template.get("contract_type") is not None

        if is_pe:
            # PE system prompt — adapts language to deal type
            pe_data = available_data.get("pe_model_data", {})
            dp = pe_data.get("deal_profile", {})
            deal_type = dp.get("deal_type", "unknown")
            target_name = dp.get("target_name", "the target")
            total_inv = dp.get("total_investment", 0)
            strategy = dp.get("strategy", "")

            pe_context = f"Deal type: {deal_type.replace('_', ' ').title()}. "
            if total_inv:
                pe_context += f"Total Investment: ${total_inv / 1e6:,.0f}M. "
            if strategy:
                pe_context += f"Strategy: {strategy} "

            # Adapt firm style and language by deal type
            deal_type_lower = deal_type.lower()
            if deal_type_lower in ("lbo", "buyout"):
                style_guidance = (
                    "\nDEAL-TYPE GUIDANCE (LBO/Buyout):\n"
                    "- Value multiples are EV/EBITDA, never EV/Revenue.\n"
                    "- Value creation = revenue growth + margin expansion + multiple expansion + de-leveraging.\n"
                    "- Returns = IRR and MOIC, always show both.\n"
                    "- Debt = leverage ratios, covenant headroom, interest coverage, paydown trajectory.\n"
                    "- Use PE language: EBITDA, leverage, de-leveraging, value creation levers, bolt-ons, "
                    "add-backs, quality of earnings, management rollover, covenant package.\n"
                )
            elif deal_type_lower in ("real_asset", "infrastructure"):
                style_guidance = (
                    "\nDEAL-TYPE GUIDANCE (Real Asset / Infrastructure):\n"
                    "- Key metrics: NOI, cap rate, occupancy, FFO, yield, replacement cost.\n"
                    "- Write like Brookfield or Global Infrastructure Partners.\n"
                    "- Value creation = NOI growth + cap rate compression + asset enhancement.\n"
                    "- Returns = IRR, equity multiple, cash-on-cash yield.\n"
                    "- Asset quality, location, lease structure, tenant concentration.\n"
                )
            elif deal_type_lower in ("structured_equity",):
                style_guidance = (
                    "\nDEAL-TYPE GUIDANCE (Structured Equity):\n"
                    "- Key metrics: preferred return, cash yield, warrant coverage, downside protection.\n"
                    "- Returns = IRR, MOIC, cash yield, equity upside via warrants/conversion.\n"
                    "- Instrument interactions: preferred vs common, waterfall mechanics, conversion triggers.\n"
                    "- Focus on downside protection and yield floor.\n"
                )
            else:
                style_guidance = (
                    "\nDEAL-TYPE GUIDANCE:\n"
                    "- Adapt your language to the deal type identified in the model.\n"
                    "- Focus on the return metrics and instruments that exist in the data.\n"
                    "- Use the primary metric from the model as the key valuation anchor.\n"
                )

            system_prompt = (
                "You are a senior investment professional at a top-tier investment firm. "
                "Write with authority and precision — "
                "this memo drives multi-hundred-million dollar investment decisions. "
                f"Target: {target_name}. {pe_context}"
                f"{fund_size_str}"
                "\n\nYOU ARE WRITING AN INVESTMENT COMMITTEE MEMO, NOT A MARKDOWN DOCUMENT.\n"
                "Write the way top investment firms write IC memos: "
                "clean prose, structured tables, clear section flow. Think printed PDF, not a README.\n"
                f"{style_guidance}"
                "\n- Do NOT use VC language: no TAM/SAM/SOM, no 'burn rate', no 'runway', no 'dilution rounds'.\n"
                "\nFORMATTING — CRITICAL:\n"
                "- DO NOT use ** or * for bold/italic. Ever. No exceptions.\n"
                "- DO NOT use ### sub-headings inside sections. Each section already has its heading.\n"
                "- Write plain prose. Emphasize through word choice and sentence structure.\n"
                "- Numbers inline naturally: $142M, 8.5x entry multiple, 22% IRR.\n"
                "- Cite data source: 'management projections', 'the model', 'comparable transactions'.\n"
                "- Use markdown tables for structured data (scenarios, instruments, comps).\n"
                "\nCONTENT:\n"
                "- DEEP DIVE: 2-4 dense paragraphs per section (150-400 words).\n"
                "- Lead each section with the single most important finding.\n"
                "- End each section with a clear takeaway.\n"
                "- All numbers must come from the model data provided.\n"
                "- For risk factors: severity table with specific mitigants.\n"
                "\nSECTION STRUCTURE:\n"
                "- Separate each section with its exact ## heading as shown below.\n"
                "- The headings split your output — they MUST match exactly.\n"
                "- Within each section: prose paragraphs, tables where data warrants."
            )
        elif is_contract:
            contract_type = template.get("contract_type", "agreement")
            governing_law = template.get("governing_law_default", "Delaware")
            preamble_text = template.get("preamble", "")
            preamble_ctx = f"\nPREAMBLE (already filled — reference this context):\n{preamble_text}\n" if preamble_text else ""

            system_prompt = (
                "You are a senior corporate attorney at a top-tier law firm (Wachtell, Skadden, or equivalent). "
                f"Draft precise, enforceable legal clauses for a {contract_type.replace('_', ' ')}. "
                f"Jurisdiction: {governing_law}."
                f"{preamble_ctx}"
                "\n\nYOU ARE DRAFTING A REAL CONTRACT, NOT A SUMMARY.\n"
                "Write the way elite law firms draft agreements: precise defined terms, "
                "clear obligations, enforceable language. Think signed legal document, not a memo.\n"
                "\nCRITICAL RULES:\n"
                "- Write actual contract language — numbered clauses, defined terms, operative provisions.\n"
                "- DO NOT use ** or * for bold/italic. Write plain legal prose.\n"
                "- DO NOT use ### sub-headings. Each section already has its heading.\n"
                "- Use defined terms consistently: capitalize and define in quotes on first use "
                '(e.g., the "Receiving Party").\n'
                "- Include section cross-references where appropriate (e.g., 'as defined in Section 1').\n"
                "- Every obligation must specify WHICH PARTY bears it.\n"
                "- Include specific time periods, notice requirements, and thresholds — "
                "never leave these vague.\n"
                "- Where the user must fill in specifics, use [SPECIFY] as placeholder.\n"
                "- Cite market standards where relevant: [Standard: Delaware law requires...] or "
                "[Standard: typical for Series A SHAs].\n"
                "- For contract review templates: when providing negotiation redlines, use this exact format:\n"
                "  ORIGINAL: [verbatim current language]\n"
                "  REVISED: [your recommended revision]\n"
                "  REASONING: [why — cite market standard, risk, or commercial impact]\n"
                "\nSECTION STRUCTURE:\n"
                "- Separate each section with its exact ## heading as shown below.\n"
                "- The headings split your output — they MUST match exactly.\n"
                "- Within each section: contract clauses with sub-numbering (a), (b), (c) as appropriate."
            )
        else:
            system_prompt = (
                "You are a senior investment analyst at a top-tier venture capital fund. "
                "Write with authority and precision — this memo drives multi-million dollar decisions. "
                f"{fund_size_str}"
                f"{company_str}"
                "\n\nYOU ARE WRITING A PROFESSIONAL MEMO, NOT A MARKDOWN DOCUMENT.\n"
                "Write the way Goldman Sachs, McKinsey, or a top VC fund writes investment memos: "
                "clean prose, structured tables, clear section flow. Think printed PDF, not a README.\n"
                "\nFORMATTING — CRITICAL:\n"
                "- DO NOT use ** or * for bold/italic. Ever. No exceptions.\n"
                "- DO NOT use ### sub-headings inside sections. Each section already has its heading.\n"
                "- Write plain prose. Emphasize through word choice and sentence structure.\n"
                "- Numbers inline naturally: $14.8M ARR, 2.3x revenue multiple, 47% gross margin.\n"
                "- Cite sources inline: '$14.8M ARR (company-reported)' or '$5M ARR (est. Series A benchmark)' or '$4.2M ARR (TechCrunch)'. Always cite the source of every key number.\n"
                "- Use bullet points (- item) only for short lists of 3-5 actionable items like key risks or next steps.\n"
                "- Use markdown tables (| col | col |) when comparing structured data across companies or scenarios. "
                "Tables are great — just keep them clean with no bold/italic markup inside cells.\n"
                "\nCONTENT:\n"
                f"{'- PORTFOLIO (' + str(num_companies) + ' companies): Lead with the big picture — stage distribution, sector themes, total deployed. Compare and contrast, never describe companies in isolation. Group by theme or performance tier.' if is_portfolio else '- DEEP DIVE: 2-4 dense paragraphs per section (150-400 words). Weave numbers into flowing prose with context.'}\n"
                "- Lead each section with the single most important finding. No preamble, no filler.\n"
                "- End each section with a clear takeaway or recommended action.\n"
                "- Never skip a company for sparse data. State what is known, estimate what is not, flag confidence.\n"
                "- Fields marked [ESTIMATED] must be presented as estimates, never as facts.\n"
                "- Calculate derived metrics: revenue multiples, capital efficiency, implied burn.\n"
                "- Every claim must trace to the data. Count before you claim.\n"
                "- Work with what you have. Sparse data means analyze harder, not less.\n"
                "- When data is missing, infer using stage benchmarks and say why.\n"
                "- For recommendations: state conviction (High/Medium/Low) and check size.\n"
                "\nSECTION STRUCTURE:\n"
                "- Separate each section with its exact ## heading as shown below.\n"
                "- The headings split your output — they MUST match exactly.\n"
                "- Do NOT use ---SECTION_BREAK--- delimiters.\n"
                "- Within each section: prose paragraphs, tables where data warrants, bullet lists for actions only."
            )

        user_prompt = (
            f"User request: {prompt}\n\n"
            f"## Available Data\n{data_summary}\n\n"
            f"## Generate these sections (use the EXACT ## heading shown for each):\n\n"
            + "\n\n".join(section_prompts)
        )

        try:
            # Import here to avoid circular import at module level
            from app.services.model_router import ModelCapability

            logger.info(f"[MEMO] generate_narratives: calling LLM ({len(user_prompt)} char prompt, {len(system_prompt)} char system)...")
            # No wrapper timeout here — model_router already calculates a
            # per-call timeout based on max_tokens + prompt size (~260s for 12K tokens).
            # The old 90s timeout was killing the call before Sonnet could finish.
            response = await self.model_router.get_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                capability=ModelCapability.ANALYSIS,
                max_tokens=12000,
                temperature=0.25,
                caller_context="lightweight_memo_narratives",
            )

            raw_text = response.get("response", "") if isinstance(response, dict) else str(response)

            logger.info(f"[MEMO] LLM returned {len(raw_text)} chars for {len(narrative_keys)} sections")
            if len(raw_text) < 200:
                logger.warning(f"[MEMO] LLM response suspiciously short: {raw_text[:500]!r}")
            else:
                logger.debug(f"[MEMO] LLM response preview: {raw_text[:300]!r}...")

            # Collect headings for heading-match parsing strategy
            section_headings = [
                s["heading"] for s in sections
                if s["type"] in ("narrative", "metrics")
            ]

            # Parse sections with fallback strategies
            parts = self._parse_sections(raw_text, len(narrative_keys), section_headings=section_headings)
            result: Dict[str, str] = {}
            for i, key in enumerate(narrative_keys):
                if i < len(parts):
                    result[key] = parts[i].strip()
                else:
                    result[key] = ""
                # Log what each section got
                content_len = len(result[key])
                logger.debug(f"[MEMO] Section '{key}': {content_len} chars{' (EMPTY)' if content_len == 0 else ''}")

            empty_count = sum(1 for v in result.values() if not v)
            if empty_count > 0:
                logger.warning(f"[MEMO] {empty_count}/{len(result)} sections are EMPTY after parsing")

            return result

        except Exception as e:
            logger.error(f"[MEMO] Narrative generation failed: {e}", exc_info=True)
            # Return empty narratives — the memo will still have metrics/charts
            return {key: "" for key in narrative_keys}

    # ------------------------------------------------------------------
    # Shot 3: Assemble final memo — inject charts, tables, metrics
    # ------------------------------------------------------------------

    def assemble_memo(
        self,
        template_id: str,
        prompt: str,
        narratives: Dict[str, str],
        available_data: Dict[str, Any],
        prebuilt_charts: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """Combine narratives + data-driven sections + charts into final docs format."""
        template = MEMO_TEMPLATES[template_id]
        title = self._format_title(template, available_data, prompt)

        memo_sections: List[Dict[str, Any]] = []

        # Title + date
        memo_sections.append({"type": "heading1", "content": title})
        memo_sections.append({
            "type": "paragraph",
            "content": f"Prepared {datetime.now().strftime('%B %d, %Y')}",
        })

        companies = available_data.get("companies", [])

        for section_def in template["sections"]:
            key = section_def["key"]
            heading = section_def["heading"]
            sec_type = section_def["type"]

            memo_sections.append({"type": "heading2", "content": heading})

            if sec_type == "chart":
                # Use prebuilt chart if available, otherwise build on the fly
                chart = (
                    (prebuilt_charts or {}).get(key)
                    if prebuilt_charts is not None
                    else self._build_chart(section_def, available_data, companies)
                )
                if chart:
                    memo_sections.append({"type": "chart", "chart": chart})
                else:
                    memo_sections.append({
                        "type": "paragraph",
                        "content": f"*Chart data not available — run relevant analysis tools first.*",
                    })

            elif sec_type == "metrics":
                # Metrics sections get structured data; narrative only if it
                # adds prose beyond what the table/list already shows.
                metrics = self._build_metrics(section_def, available_data, companies)
                if metrics:
                    memo_sections.extend(metrics)
                narrative = narratives.get(key, "")
                if narrative:
                    parsed = self._parse_markdown_to_sections(narrative)
                    # If structured metrics already exist, only keep narrative
                    # paragraphs and lists (skip tables that duplicate metrics)
                    if metrics and parsed:
                        for ps in parsed:
                            if ps.get("type") in ("paragraph", "list", "heading3"):
                                memo_sections.append(ps)
                    elif parsed:
                        memo_sections.extend(parsed)
                    else:
                        memo_sections.append({"type": "paragraph", "content": narrative})

            elif sec_type == "clause":
                # Contract clause — same as narrative but with clause metadata as citation
                narrative = narratives.get(key, "")
                if narrative:
                    parsed = self._parse_markdown_to_sections(narrative)
                    if parsed:
                        memo_sections.extend(parsed)
                    else:
                        memo_sections.append({"type": "paragraph", "content": narrative})
                    # Attach clause metadata as citation badge on last section
                    clause_type = section_def.get("clause_type", "")
                    risk_level = section_def.get("risk_level", "medium")
                    if clause_type and memo_sections:
                        if "citations" not in memo_sections[-1]:
                            memo_sections[-1]["citations"] = []
                        memo_sections[-1]["citations"].append({
                            "type": "reasoning",
                            "title": f"Clause: {clause_type.replace('_', ' ').title()} | Risk: {risk_level}",
                        })
                else:
                    memo_sections.append({
                        "type": "paragraph",
                        "content": f"[Draft clause: {section_def.get('clause_type', 'general')}]",
                    })

            elif sec_type == "context":
                # Plan memo context snapshot — machine-readable JSON
                context_data = self._build_context_snapshot(available_data)
                memo_sections.append({
                    "type": "code",
                    "content": json.dumps(context_data, indent=2, default=str),
                })

            else:  # narrative
                narrative = narratives.get(key, "")
                if narrative:
                    parsed = self._parse_markdown_to_sections(narrative)
                    if parsed:
                        memo_sections.extend(parsed)
                    else:
                        memo_sections.append({"type": "paragraph", "content": narrative})
                else:
                    # Try fallback metrics, but never strip the heading —
                    # it anchors chart slots and keeps the document structure.
                    _fallback = self._build_section_fallback(section_def, companies)
                    if _fallback:
                        memo_sections.append(_fallback)
                    logger.debug(f"[MEMO] Empty narrative for section {key} — used fallback: {bool(_fallback)}")

        # Post-process: convert ORIGINAL/REVISED/REASONING markers to redline sections
        if template.get("contract_type") == "review":
            memo_sections = self._convert_negotiations_to_redlines(memo_sections)

        return {
            "format": "docs",
            "title": title,
            "date": datetime.now().strftime("%B %d, %Y"),
            "sections": memo_sections,
            "memo_type": template_id,
            "is_resumable": template.get("is_resumable", False),
            "metadata": {
                "word_count": sum(
                    len(str(s.get("content", "") or s.get("items", [])).split())
                    for s in memo_sections
                ),
                "section_count": len(memo_sections),
                "generated_at": datetime.now().isoformat(),
                "company_count": len(companies),
                "has_charts": any(s.get("type") == "chart" for s in memo_sections),
                "has_tables": any(s.get("type") == "table" for s in memo_sections),
                "memo_type": template_id,
                "template_sections": [s["key"] for s in template["sections"]],
            },
        }

    # ------------------------------------------------------------------
    # Contract redline conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_negotiations_to_redlines(
        sections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert ORIGINAL/REVISED/REASONING markers from LLM output to redline sections.

        The contract review template instructs the LLM to output negotiation points
        in this format:
            ORIGINAL: [verbatim current language]
            REVISED: [recommended revision]
            REASONING: [why this change matters]

        This method scans paragraph sections for these markers and converts them
        to {type: "redline", redline: {original, revised, reasoning}} sections
        that the MemoEditor renders with strikethrough/green styling.
        """
        import re

        result = []
        for s in sections:
            if s.get("type") != "paragraph" or not s.get("content"):
                result.append(s)
                continue

            content = s["content"]
            # Check for redline markers
            orig_match = re.search(
                r"ORIGINAL:\s*(.+?)(?=\s*REVISED:|$)", content, re.DOTALL
            )
            rev_match = re.search(
                r"REVISED:\s*(.+?)(?=\s*REASONING:|$)", content, re.DOTALL
            )
            reason_match = re.search(
                r"REASONING:\s*(.+?)$", content, re.DOTALL
            )

            if orig_match and rev_match:
                result.append({
                    "type": "redline",
                    "redline": {
                        "original": orig_match.group(1).strip(),
                        "revised": rev_match.group(1).strip(),
                        "reasoning": reason_match.group(1).strip() if reason_match else "",
                    },
                })
            else:
                result.append(s)

        return result

    # ------------------------------------------------------------------
    # Shot 4 (optional): Polish pass
    # ------------------------------------------------------------------

    async def polish(self, memo: Dict[str, Any], user_feedback: str) -> Dict[str, Any]:
        """Refine memo in-place based on user feedback.

        Asks the LLM to output ---UPDATE_SECTION <index>--- markers so we can
        replace sections at the correct positions rather than appending.
        """
        import re
        from app.services.model_router import ModelCapability

        sections = memo.get("sections", [])
        # Build an indexed view of editable sections for the LLM
        indexed_sections: List[str] = []
        for i, s in enumerate(sections):
            if s["type"] in ("heading1", "heading2", "heading3", "paragraph", "list"):
                prefix = f"[{i}] " + (f"## {s.get('content', '')}" if s["type"].startswith("heading") else s.get("content", ""))
                indexed_sections.append(prefix)

        sections_text = "\n".join(indexed_sections)

        response = await self.model_router.get_completion(
            prompt=(
                f"Current memo (each section prefixed with [index]):\n{sections_text[:4000]}\n\n"
                f"User feedback: {user_feedback}\n\n"
                f"Rewrite ONLY the affected sections. For each changed section output:\n"
                f"---UPDATE_SECTION <index>---\n<new content>\n\n"
                f"Use the exact index numbers from above. Do not output unchanged sections."
            ),
            system_prompt=(
                "You are a portfolio CFO refining an investment memo. "
                "Preserve existing numbers and citations. Write prose, not bullets. "
                "Do not add filler or hedging. Only use numbers already in the memo "
                "or explicitly provided in the feedback. "
                "Output ONLY changed sections using the ---UPDATE_SECTION <index>--- format."
            ),
            capability=ModelCapability.FAST,
            max_tokens=2048,
            temperature=0.3,
            caller_context="lightweight_memo_polish",
        )

        polished = response.get("response", "") if isinstance(response, dict) else str(response)
        if not polished:
            return memo

        # Parse ---UPDATE_SECTION <index>--- markers and replace in-place
        updates = re.split(r"---\s*UPDATE_SECTION\s+(\d+)\s*---", polished)
        replaced = 0
        # updates[0] is text before first marker (usually empty), then alternating: index, content
        for j in range(1, len(updates) - 1, 2):
            try:
                idx = int(updates[j].strip())
                content = updates[j + 1].strip()
                if 0 <= idx < len(sections) and content:
                    sections[idx]["content"] = content
                    replaced += 1
            except (ValueError, IndexError):
                continue

        # Fallback: if LLM didn't follow the format, find the last paragraph
        # section that matches the feedback topic and replace it
        if replaced == 0 and polished.strip():
            feedback_lower = user_feedback.lower()
            best_idx = -1
            for i, s in enumerate(sections):
                if s["type"] == "paragraph" and s.get("content"):
                    # Check if nearby heading relates to the feedback
                    for hi in range(i - 1, max(i - 3, -1), -1):
                        if sections[hi]["type"].startswith("heading"):
                            heading_text = (sections[hi].get("content") or "").lower()
                            # Simple word overlap check
                            feedback_words = set(feedback_lower.split())
                            heading_words = set(heading_text.split())
                            if feedback_words & heading_words:
                                best_idx = i
                                break
            if best_idx >= 0:
                sections[best_idx]["content"] = polished.strip()
            else:
                # Last resort: replace the last paragraph section
                for i in range(len(sections) - 1, -1, -1):
                    if sections[i]["type"] == "paragraph" and sections[i].get("content"):
                        sections[i]["content"] = polished.strip()
                        break

        memo["sections"] = sections
        return memo

    # ------------------------------------------------------------------
    # Top-level orchestration: run the full pipeline
    # ------------------------------------------------------------------

    def _prebuild_charts(
        self, template_id: str, available_data: Dict[str, Any]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Pre-build all charts for the template (no LLM, CPU-only).

        Returns {section_key: chart_config_or_None}.
        Called in parallel with narrative generation to hide chart latency.
        """
        template = MEMO_TEMPLATES[template_id]
        companies = available_data.get("companies", [])
        charts: Dict[str, Optional[Dict[str, Any]]] = {}
        for section_def in template["sections"]:
            if section_def["type"] == "chart":
                try:
                    charts[section_def["key"]] = self._build_chart(
                        section_def, available_data, companies
                    )
                except Exception as exc:
                    logger.warning("[MEMO] Pre-build chart %s failed: %s", section_def["key"], exc)
                    charts[section_def["key"]] = None
        return charts

    async def generate(
        self,
        prompt: str,
        memo_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate memo using the 3-shot template pipeline.

        Shot 1 (no LLM): detect_memo_type → pick template → audit_data
        Shot 2 (1 LLM call): generate_narratives — LLM writes NARRATIVE ONLY
        Shot 3 (no LLM): assemble_memo — inject charts/tables from Python services

        Returns docs-format dict ready for frontend rendering.
        """
        # Shot 1: Detect type → pick template → audit data
        template_id = self.detect_memo_type(prompt, memo_type)

        # Bulletproof: if pe_model_data exists, force pe_ic_memo
        if template_id != "pe_ic_memo" and self.shared_data.get("pe_model_data"):
            logger.warning("[MEMO] detect_memo_type returned %s but pe_model_data exists — forcing pe_ic_memo", template_id)
            template_id = "pe_ic_memo"

        available_data, missing_req, missing_opt = self.audit_data(template_id)

        # Auto-fill template variables for contract templates
        import copy
        template = copy.deepcopy(MEMO_TEMPLATES[template_id])
        if template.get("template_variables"):
            self._autofill_template(template, available_data)

        # Estimation fallback: ensure every company has revenue, valuation, growth
        companies = available_data.get("companies", [])
        if companies:
            _STAGE_BENCHMARKS = {
                "pre-seed": {"revenue": 200_000, "valuation": 5_000_000, "growth": 3.0},
                "seed": {"revenue": 1_000_000, "valuation": 15_000_000, "growth": 2.5},
                "series a": {"revenue": 5_000_000, "valuation": 80_000_000, "growth": 1.5},
                "series b": {"revenue": 20_000_000, "valuation": 300_000_000, "growth": 0.8},
                "series c": {"revenue": 60_000_000, "valuation": 800_000_000, "growth": 0.5},
                "growth": {"revenue": 100_000_000, "valuation": 2_000_000_000, "growth": 0.3},
            }
            for c in companies:
                stage = str(c.get("stage") or "series a").lower().strip()
                bench = _STAGE_BENCHMARKS.get(stage, _STAGE_BENCHMARKS["series a"])
                if c.get("_revenue_is_estimated"):
                    c["_revenue_estimated"] = True
                if c.get("_valuation_is_estimated"):
                    c["_valuation_estimated"] = True
                rev = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue"))
                if not rev:
                    c["inferred_revenue"] = bench["revenue"]
                    c["_revenue_estimated"] = True
                val = ensure_numeric(c.get("valuation")) or ensure_numeric(c.get("inferred_valuation"))
                if not val:
                    c["inferred_valuation"] = bench["valuation"]
                    c["_valuation_estimated"] = True
                growth = c.get("revenue_growth")
                if not growth or not isinstance(growth, (int, float)):
                    c["revenue_growth"] = bench["growth"]
                    c["_growth_estimated"] = True

        logger.info(f"[MEMO] Template pipeline: type={template_id}, companies={len(companies)}, missing_req={missing_req}")

        # Shot 2 + chart pre-build in parallel
        # LLM writes narrative only; charts built from Python service data (no LLM)
        # Charts are sync (no LLM) so build first — they must survive even if narratives fail.
        _t0 = datetime.now()
        logger.info("[MEMO] Running _prebuild_charts...")
        prebuilt_charts = self._prebuild_charts(template_id, available_data)
        logger.info(f"[MEMO] Charts done ({len(prebuilt_charts)}), starting narratives...")
        try:
            narratives = await self.generate_narratives(template_id, prompt, available_data)
        except Exception as e:
            logger.error(f"[MEMO] Narrative generation failed: {e}", exc_info=True)
            narratives = {}

        _elapsed = (datetime.now() - _t0).total_seconds()
        logger.info(f"[MEMO] Template pipeline took {_elapsed:.1f}s — narratives={len(narratives)}, charts={len(prebuilt_charts)}")

        # Shot 3: Assemble — inject charts/tables from Python services (no LLM)
        result = self.assemble_memo(template_id, prompt, narratives, available_data, prebuilt_charts)

        # Post-process: inject inline [N] citation markers and build bibliography
        result = self._inject_inline_citations(result, available_data)

        # Attach citations from shared_data so frontend can render Sources section
        citations = self.shared_data.get("citations", [])
        if citations:
            # Merge with any citations generated by inline processing
            existing = result.get("citations", [])
            if existing:
                # Deduplicate by URL
                existing_urls = {c.get("url") for c in existing if c.get("url")}
                for c in citations:
                    if c.get("url") not in existing_urls:
                        existing.append(c)
                result["citations"] = existing
            else:
                result["citations"] = citations

        # Attach company data for document viewer sidebar
        if companies:
            result["companies"] = companies

        # Attach cap table if available
        cap_table = self.shared_data.get("cap_table_history", {})
        if cap_table:
            result["cap_table_history"] = cap_table

        return result

    # ------------------------------------------------------------------
    # Inline citation post-processing
    # ------------------------------------------------------------------

    def _inject_inline_citations(
        self,
        result: Dict[str, Any],
        available_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Replace inline source references with numbered [N] markers.

        Scans paragraph/list sections for patterns like:
          - (company-reported), (TechCrunch, 2024), (est. benchmark)
          - Tavily/Firecrawl source URLs already in shared_data
        Creates a numbered bibliography appended as a dedicated section.
        """
        import re

        try:
            from app.services.enhanced_citation_manager import EnhancedCitationManager
        except ImportError:
            return result  # Enhanced manager not available — skip

        cm = EnhancedCitationManager()

        # Pre-populate from shared_data citations (Tavily search results, docs, etc.)
        existing_citations = self.shared_data.get("citations", [])
        for c in existing_citations:
            cm.add_citation(
                source=c.get("source", c.get("title", "Unknown")),
                date=c.get("date", ""),
                content=c.get("content", ""),
                url=c.get("url"),
                title=c.get("title"),
                metadata=c.get("metadata", {}),
            )

        # Also pull per-company sources
        for company in available_data.get("companies", []):
            for src in company.get("sources", []) + company.get("tavily_sources", []):
                if isinstance(src, dict) and src.get("url"):
                    cm.add_citation(
                        source=src.get("title", src.get("url", "")),
                        date=src.get("date", ""),
                        content=src.get("snippet", src.get("content", "")),
                        url=src.get("url"),
                        title=src.get("title"),
                    )

        # Patterns for inline source references the LLM generates
        # (source-type) or (Source Name, YYYY)
        _INLINE_PATTERN = re.compile(
            r'\(('
            r'company[- ]reported'
            r'|est\.?\s+[^)]{3,40}'
            r'|[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*(?:,\s*\d{4})?'
            r'|source:\s*[^)]{3,60}'
            r'|per\s+[^)]{3,40}'
            r')\)',
            re.IGNORECASE,
        )

        sections = result.get("sections", [])
        for section in sections:
            if section.get("type") not in ("paragraph", "list"):
                continue

            if section.get("type") == "paragraph" and section.get("content"):
                text = section["content"]
                new_text = self._replace_inline_refs(text, cm, _INLINE_PATTERN)
                section["content"] = new_text

            elif section.get("type") == "list" and section.get("items"):
                new_items = []
                for item in section["items"]:
                    if isinstance(item, str):
                        new_items.append(self._replace_inline_refs(item, cm, _INLINE_PATTERN))
                    else:
                        new_items.append(item)
                section["items"] = new_items

        # Add bibliography section if we have citations
        all_cites = cm.get_all_citations()
        if all_cites:
            result["sections"].append({"type": "heading2", "content": "Sources"})
            bib_items = []
            for c in sorted(all_cites, key=lambda x: x.get("number", 0)):
                num = c.get("number", c.get("citation_number", ""))
                title = c.get("title", c.get("source", ""))
                url = c.get("url", "")
                if url and url.startswith("http"):
                    bib_items.append(f"[{num}] [{title}]({url})")
                else:
                    bib_items.append(f"[{num}] {title}")
            result["sections"].append({"type": "list", "items": bib_items})

            # Also attach structured citations for frontend CitationDisplay
            result["citations"] = all_cites

        return result

    @staticmethod
    def _replace_inline_refs(text: str, cm, pattern) -> str:
        """Replace (source reference) with [N] citation markers."""
        import re

        def _replace(match):
            source_text = match.group(1).strip()
            # Try to find existing citation by source name
            existing = cm.get_citations_by_source(source_text)
            if existing:
                num = existing[0].get("number", existing[0].get("citation_number", "?"))
                return f"[{num}]"

            # Create new citation
            num, marker = cm.add_citation(
                source=source_text,
                date="",
                content=f"Referenced as: {source_text}",
            )
            return marker

        return pattern.sub(_replace, text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_markdown_to_sections(markdown: str) -> List[Dict[str, Any]]:
        """Parse LLM markdown into properly typed section dicts.

        Splits on:
        - ### headings → heading3
        - markdown tables → table (with headers/rows)
        - bullet/numbered lists → list (with items)
        - everything else → paragraph

        Returns list of section dicts ready for the frontend.
        """
        import re

        if not markdown or not markdown.strip():
            return []

        sections: List[Dict[str, Any]] = []
        current_paragraph_lines: List[str] = []
        current_list_items: List[str] = []
        in_table = False
        table_lines: List[str] = []

        def _flush_paragraph():
            text = "\n".join(current_paragraph_lines).strip()
            if text:
                sections.append({"type": "paragraph", "content": text})
            current_paragraph_lines.clear()

        def _flush_list():
            if current_list_items:
                sections.append({"type": "list", "items": list(current_list_items)})
                current_list_items.clear()

        def _flush_table():
            if len(table_lines) < 2:
                # Not a real table — put lines back as paragraph
                current_paragraph_lines.extend(table_lines)
                table_lines.clear()
                return
            # Parse header row
            header_line = table_lines[0]
            headers = [c.strip() for c in header_line.strip().strip("|").split("|") if c.strip()]
            if not headers:
                current_paragraph_lines.extend(table_lines)
                table_lines.clear()
                return
            # Skip separator line (index 1), parse data rows
            rows: List[List[Any]] = []
            for row_line in table_lines[2:]:
                if not row_line.strip() or not "|" in row_line:
                    continue
                cells = [c.strip() for c in row_line.strip().strip("|").split("|")]
                # Try numeric conversion
                parsed_cells: List[Any] = []
                for c in cells:
                    cleaned = c.replace("$", "").replace(",", "").replace("%", "").strip()
                    try:
                        parsed_cells.append(float(cleaned) if "." in cleaned else int(cleaned))
                    except (ValueError, TypeError):
                        parsed_cells.append(c)
                rows.append(parsed_cells)
            if rows:
                sections.append({
                    "type": "table",
                    "table": {"headers": headers, "rows": rows},
                })
            else:
                current_paragraph_lines.extend(table_lines)
            table_lines.clear()

        lines = markdown.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # --- Heading (### only — ## is used for section splitting) ---
            if re.match(r"^#{3,4}\s+", stripped):
                _flush_paragraph()
                _flush_list()
                heading_text = re.sub(r"^#{3,4}\s+", "", stripped).strip()
                if heading_text:
                    sections.append({"type": "heading3", "content": heading_text})
                i += 1
                continue

            # --- Table start: line has pipes and next line is separator ---
            if (
                not in_table
                and "|" in stripped
                and i + 1 < len(lines)
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1].strip())
            ):
                _flush_paragraph()
                _flush_list()
                in_table = True
                table_lines = [stripped]
                i += 1
                continue

            # --- Inside table ---
            if in_table:
                if "|" in stripped:
                    table_lines.append(stripped)
                    i += 1
                    continue
                else:
                    in_table = False
                    _flush_table()
                    # Don't increment — re-process this line
                    continue

            # --- Bullet or numbered list ---
            list_match = re.match(r"^\s*(?:[-*+]|\d+[.)]) \s*(.*)", stripped)
            if list_match:
                _flush_paragraph()
                current_list_items.append(list_match.group(1).strip())
                i += 1
                continue

            # --- If we were in a list and hit non-list, flush ---
            if current_list_items and stripped:
                _flush_list()

            # --- Empty line = paragraph break ---
            if not stripped:
                if current_paragraph_lines:
                    _flush_paragraph()
                if current_list_items:
                    _flush_list()
                i += 1
                continue

            # --- Regular text ---
            current_paragraph_lines.append(line)
            i += 1

        # Flush remaining
        if in_table:
            in_table = False
            _flush_table()
        _flush_paragraph()
        _flush_list()

        return sections

    @staticmethod
    def _normalize_heading(text: str) -> str:
        """Normalize a heading for fuzzy comparison."""
        import re
        text = re.sub(r'#{1,6}\s*', '', text)          # strip markdown #
        text = re.sub(r'\*+', '', text)                 # strip bold markers
        text = re.sub(r'^\d+[.)]\s*', '', text)         # strip numbering "1. ", "2) "
        text = re.sub(r'[:\-—–|/\\]+$', '', text)      # strip trailing punctuation
        text = re.sub(r'\s+', ' ', text).strip().lower()
        return text

    @staticmethod
    def _heading_similarity(a: str, b: str) -> float:
        """Token-overlap similarity between two normalized headings (0-1)."""
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a or not tokens_b:
            return 0.0
        overlap = tokens_a & tokens_b
        return len(overlap) / max(len(tokens_a), len(tokens_b))

    @staticmethod
    def _parse_sections(raw_text: str, expected_count: int, section_headings: Optional[List[str]] = None) -> List[str]:
        """Parse LLM output into sections using multiple fallback strategies.

        Tries in order:
        1. Fuzzy heading-match alignment (match known headings in output) — primary
        2. Markdown H2/H3 headings mapped to expected headings by similarity
        3. Exact ---SECTION_BREAK--- delimiter (legacy fallback)
        4. Fuzzy regex for delimiter variations
        5. Triple-dash (---) splits
        6. Full text replicated to all sections so nothing gets lost
        """
        import re

        if not raw_text or expected_count <= 0:
            return [""] * expected_count

        # Helper: find all ## / ### headings the LLM actually wrote
        def _find_llm_headings(text: str) -> List[tuple]:
            """Return [(start_pos, raw_heading_text), ...] for all markdown headings."""
            results = []
            for m in re.finditer(r'(?:^|\n)\s*(#{2,4}\s+.+?)(?:\n|$)', text):
                results.append((m.start(), m.group(1).strip()))
            # Also match bold-only headings on their own line: **Some Heading**
            for m in re.finditer(r'(?:^|\n)\s*(\*\*[^*\n]{4,}\*\*)\s*(?:\n|$)', text):
                # Skip if we already captured this position
                pos = m.start()
                if not any(abs(pos - p) < 3 for p, _ in results):
                    results.append((pos, m.group(1).strip()))
            results.sort(key=lambda x: x[0])
            return results

        normalize = LightweightMemoService._normalize_heading
        similarity = LightweightMemoService._heading_similarity

        # Strategy 1 (primary): fuzzy heading-match alignment
        if section_headings and len(section_headings) >= expected_count:
            llm_headings = _find_llm_headings(raw_text)
            if llm_headings:
                norm_expected = [normalize(h) for h in section_headings[:expected_count]]
                positions = [-1] * expected_count
                used_llm = set()  # avoid double-matching

                # Pass 1: exact substring match (most reliable)
                for i, norm_exp in enumerate(norm_expected):
                    for j, (pos, raw_h) in enumerate(llm_headings):
                        if j in used_llm:
                            continue
                        norm_llm = normalize(raw_h)
                        if norm_exp == norm_llm or norm_exp in norm_llm or norm_llm in norm_exp:
                            positions[i] = pos
                            used_llm.add(j)
                            break

                # Pass 2: token-overlap fuzzy match for remaining
                for i, norm_exp in enumerate(norm_expected):
                    if positions[i] >= 0:
                        continue
                    best_score = 0.0
                    best_j = -1
                    for j, (pos, raw_h) in enumerate(llm_headings):
                        if j in used_llm:
                            continue
                        score = similarity(norm_exp, normalize(raw_h))
                        if score > best_score:
                            best_score = score
                            best_j = j
                    if best_score >= 0.5 and best_j >= 0:
                        positions[i] = llm_headings[best_j][0]
                        used_llm.add(best_j)

                found = sum(1 for p in positions if p >= 0)
                logger.debug(f"[MEMO] _parse_sections Strategy 1: matched {found}/{expected_count} headings")
                if found >= max(expected_count * 0.4, 1):  # lower threshold — even 40% is useful
                    indexed = sorted(
                        [(pos, i) for i, pos in enumerate(positions) if pos >= 0],
                        key=lambda x: x[0],
                    )
                    result = [""] * expected_count
                    for idx, (pos, sec_idx) in enumerate(indexed):
                        end_pos = indexed[idx + 1][0] if idx + 1 < len(indexed) else len(raw_text)
                        result[sec_idx] = raw_text[pos:end_pos]
                    if any(r.strip() for r in result):
                        return result

        # Strategy 2: split on whatever ## headings the LLM wrote, then
        # map each chunk to the best-matching expected section by heading similarity.
        heading_splits = re.split(r'(?=\n#{2,3}\s+)', raw_text)
        heading_splits = [s for s in heading_splits if s.strip()]

        if heading_splits and section_headings and len(section_headings) >= expected_count:
            norm_expected = [normalize(h) for h in section_headings[:expected_count]]
            result = [""] * expected_count
            used = set()

            for chunk in heading_splits:
                # Extract the heading from this chunk
                hm = re.match(r'\s*#{2,3}\s+(.+?)(?:\n|$)', chunk)
                if hm:
                    chunk_heading = normalize(hm.group(1))
                else:
                    chunk_heading = normalize(chunk[:80])

                best_i = -1
                best_score = 0.0
                for i, norm_exp in enumerate(norm_expected):
                    if i in used:
                        continue
                    # Exact/substring first
                    if norm_exp == chunk_heading or norm_exp in chunk_heading or chunk_heading in norm_exp:
                        best_i = i
                        best_score = 1.0
                        break
                    score = similarity(norm_exp, chunk_heading)
                    if score > best_score:
                        best_score = score
                        best_i = i

                if best_i >= 0 and best_score >= 0.4:
                    result[best_i] = chunk.strip()
                    used.add(best_i)
                elif best_i >= 0:
                    # Low confidence — assign to first unused slot
                    for i in range(expected_count):
                        if i not in used and not result[i]:
                            result[i] = chunk.strip()
                            used.add(i)
                            break

            if any(r.strip() for r in result):
                logger.debug(f"[MEMO] _parse_sections Strategy 2: mapped {len(used)}/{len(heading_splits)} chunks")
                return result

        # Strategy 2b: heading splits without mapping (original behavior, still useful)
        if heading_splits:
            while len(heading_splits) < expected_count:
                heading_splits.append("")
            return heading_splits[:expected_count]

        # Strategy 3: delimiter-based splits (legacy)
        for splitter in [
            lambda t: t.split("---SECTION_BREAK---"),
            lambda t: re.split(r"-{2,}\s*SECTION[_\s]*BREAK\s*-{2,}", t, flags=re.IGNORECASE),
            lambda t: re.split(r"\n\s*---+\s*\n", t),
        ]:
            parts = splitter(raw_text)
            if len(parts) >= expected_count:
                return parts[:expected_count]

        # Strategy 4 (last resort): give full text to ALL sections rather than
        # only slot 0 — this way assemble_memo can at least render something
        # everywhere instead of empty fallbacks.
        logger.warning(f"[MEMO] _parse_sections: all strategies failed, broadcasting full text ({len(raw_text)} chars) to all sections")
        return [raw_text] * expected_count

    def _summarize_company(self, c: Dict[str, Any]) -> str:
        """Summarize a single company as a self-contained text block with derived metrics."""
        lines = []
        name = c.get("company", "Unknown")

        # Pre-calculate key derived metrics
        revenue = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue")) or 0
        valuation = ensure_numeric(c.get("valuation")) or ensure_numeric(c.get("inferred_valuation")) or 0
        total_funding = ensure_numeric(c.get("total_funding")) or 0
        growth_rate = c.get("revenue_growth") or c.get("growth_rate") or c.get("inferred_growth_rate")
        gross_margin = ensure_numeric((c.get("key_metrics") or {}).get("gross_margin")) or ensure_numeric(c.get("gross_margin"))

        rev_multiple = valuation / revenue if valuation > 0 and revenue > 0 else None
        capital_efficiency = revenue / total_funding if revenue > 0 and total_funding > 0 else None
        burn_rate = ensure_numeric(c.get("burn_rate")) or ensure_numeric(c.get("monthly_burn"))
        runway = ensure_numeric(c.get("runway_months")) or ensure_numeric(c.get("estimated_runway_months"))

        # Build narrative-style summary instead of raw field dump
        stage = c.get("stage", "Unknown")
        sector = c.get("sector", "")
        description = c.get("product_description") or c.get("description") or ""
        biz_model = c.get("business_model") or ""
        target_market = c.get("target_market") or ""

        lines.append(f"**{name}** ({stage}{' — ' + sector if sector else ''}):")
        if description:
            lines.append(f"  What they do: {description}")
        if biz_model:
            lines.append(f"  Business model: {biz_model}")
        if target_market:
            lines.append(f"  Target market: {target_market}")

        # Key financials block
        fin_parts = []
        if revenue > 0:
            is_estimated = c.get("_revenue_estimated") or (not c.get("revenue") and c.get("inferred_revenue"))
            label = "ARR [ESTIMATED — stage benchmark, not company-reported]" if is_estimated else "ARR"
            fin_parts.append(f"{label}: ${revenue / 1e6:,.1f}M")
        if valuation > 0:
            is_estimated = c.get("_valuation_estimated") or (not c.get("valuation") and c.get("inferred_valuation"))
            label = "Valuation [ESTIMATED — stage benchmark, not company-reported]" if is_estimated else "Valuation"
            fin_parts.append(f"{label}: ${valuation / 1e6:,.1f}M")
        if total_funding > 0:
            fin_parts.append(f"Total Funding: ${total_funding / 1e6:,.1f}M")
        if fin_parts:
            lines.append(f"  Financials: {' | '.join(fin_parts)}")

        # Derived metrics block
        derived = []
        if rev_multiple:
            derived.append(f"Revenue Multiple: {rev_multiple:.1f}x")
        if capital_efficiency:
            derived.append(f"Capital Efficiency: {capital_efficiency:.2f}x")
        if gross_margin and isinstance(gross_margin, (int, float)):
            gm_val = gross_margin * 100 if 0 < gross_margin < 1 else gross_margin
            derived.append(f"Gross Margin: {gm_val:.0f}%")
        if growth_rate and isinstance(growth_rate, (int, float)):
            derived.append(f"Growth: {growth_rate * 100:.0f}% YoY")
        if derived:
            lines.append(f"  Key Metrics: {' | '.join(derived)}")

        # Operational
        ops = []
        if c.get("team_size"):
            ops.append(f"Team: {c['team_size']}")
        if c.get("founded_year"):
            ops.append(f"Founded: {c['founded_year']}")
        if burn_rate and burn_rate > 0:
            ops.append(f"Monthly Burn: ${burn_rate / 1e6:,.1f}M" if burn_rate > 1_000_000 else f"Monthly Burn: ${burn_rate / 1e3:,.0f}K")
        if runway and runway > 0:
            ops.append(f"Runway: {runway:.0f} months")
        if ops:
            lines.append(f"  Operations: {' | '.join(ops)}")

        # Additional valuation fields
        for field in ("ltv_cac_ratio", "net_dollar_retention"):
            val = c.get(field)
            if val is not None and isinstance(val, (int, float)):
                lines.append(f"  {field}: {val:.2f}")

        # Valuation details — method, multiples, scenarios
        for vfield in ("valuation_method", "revenue_multiple",
                       "ev_revenue_multiple", "gross_margin",
                       "burn_rate", "runway_months", "ltv_cac_ratio"):
            vval = c.get(vfield)
            if vval is not None:
                if isinstance(vval, (int, float)) and abs(vval) > 1_000_000:
                    lines.append(f"  {vfield}: ${vval / 1e6:,.1f}M")
                elif isinstance(vval, (int, float)) and 0 < abs(vval) < 1:
                    lines.append(f"  {vfield}: {vval * 100:.1f}%")
                elif isinstance(vval, (int, float)):
                    lines.append(f"  {vfield}: {vval:.2f}x" if "multiple" in vfield else f"  {vfield}: {vval}")
                else:
                    lines.append(f"  {vfield}: {vval}")
        # Investment scoring rubric — moat / momentum / market / team / fund_fit
        inv_scoring = c.get("_investment_scoring")
        comp_scores = c.get("investment_component_scores") or (inv_scoring or {}).get("component_scores")
        total_inv_score = ensure_numeric(c.get("investment_total_score"))
        inv_rec = c.get("investment_recommendation", "")
        inv_action = c.get("investment_action", "")

        if comp_scores and isinstance(comp_scores, dict):
            lines.append(f"  **Investment Score: {total_inv_score:.0f}/100 — {inv_rec}**")
            score_parts = [f"{dim.title()}: {val:.0f}" for dim, val in comp_scores.items() if isinstance(val, (int, float))]
            if score_parts:
                lines.append(f"    Dimensions: {' | '.join(score_parts)}")
            if inv_action:
                lines.append(f"    Action: {inv_action}")
            inv_methodology = c.get("investment_methodology", "")
            if inv_methodology:
                lines.append(f"    Methodology: {inv_methodology}")
            inv_reasoning = c.get("investment_reasoning", "")
            if inv_reasoning:
                lines.append(f"    Thesis: {inv_reasoning}")

        # Fund fit details (from @ flow deep dive)
        fund_fit = ensure_numeric(c.get("fund_fit_score"))
        if fund_fit and fund_fit > 0 and not comp_scores:
            # Only show standalone fund_fit if we don't have the full rubric above
            fit_parts = [f"Fund Fit: {fund_fit:.0f}/100"]
            if c.get("fund_fit_recommendation"):
                fit_parts.append(c["fund_fit_recommendation"])
            lines.append(f"  {' | '.join(fit_parts)}")

        # Check size / ownership targets
        check_parts = []
        if c.get("optimal_check_size") and ensure_numeric(c.get("optimal_check_size")) > 0:
            check_parts.append(f"Check: ${ensure_numeric(c['optimal_check_size']) / 1e6:,.1f}M")
        if c.get("target_ownership_pct") and isinstance(c["target_ownership_pct"], (int, float)):
            check_parts.append(f"Target Ownership: {c['target_ownership_pct'] * 100:.1f}%")
        if c.get("expected_irr") and isinstance(c["expected_irr"], (int, float)) and c["expected_irr"] > 0:
            check_parts.append(f"Expected IRR: {c['expected_irr'] * 100:.0f}%")
        if check_parts:
            lines.append(f"  Deal Terms: {' | '.join(check_parts)}")

        # Sourcing-flow scoring (thesis_match from source_companies)
        thesis_score = ensure_numeric(c.get("thesis_match_score"))
        if thesis_score and thesis_score > 0:
            lines.append(f"  Thesis Match Score: {thesis_score:.0f}/100")
        score_breakdown = c.get("score_breakdown")
        if isinstance(score_breakdown, dict) and score_breakdown:
            top_dims = sorted(score_breakdown.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True)[:5]
            bd_parts = [f"{k}: {v}" for k, v in top_dims if isinstance(v, (int, float))]
            if bd_parts:
                lines.append(f"  Sourcing Breakdown: {' | '.join(bd_parts)}")
        if c.get("semantic_reason"):
            lines.append(f"  Thesis Rationale: {c['semantic_reason']}")

        # PWERM / exit scenario summaries
        scenarios = c.get("exit_scenarios") or c.get("pwerm_scenarios") or []
        if isinstance(scenarios, list) and scenarios:
            lines.append("  Exit Scenarios:")
            for sc in scenarios[:4]:
                if isinstance(sc, dict):
                    sc_name = sc.get("name", sc.get("scenario_name", "Scenario"))
                    sc_val = sc.get("exit_value") or sc.get("value")
                    sc_prob = sc.get("probability", 0)
                    sc_moic = sc.get("moic", "")
                    parts = [sc_name]
                    if sc_val and isinstance(sc_val, (int, float)):
                        parts.append(f"${sc_val / 1e6:,.0f}M")
                    if sc_prob:
                        parts.append(f"{sc_prob * 100:.0f}%")
                    if sc_moic:
                        parts.append(f"{sc_moic}x MOIC")
                    lines.append(f"    - {' | '.join(parts)}")
        # Comparables
        comps = c.get("comparables") or c.get("comparable_companies") or []
        if isinstance(comps, list) and comps:
            comp_names = [cp.get("name", str(cp)) if isinstance(cp, dict) else str(cp) for cp in comps[:5]]
            lines.append(f"  Comparables: {', '.join(comp_names)}")
        km = c.get("key_metrics", {})
        if isinstance(km, dict):
            for mk, mv in km.items():
                if mv is not None:
                    lines.append(f"  {mk}: {mv}")
        # Pass source citations so the memo LLM can reference them
        sources = c.get("sources") or c.get("citations") or c.get("data_sources") or []
        if isinstance(sources, list) and sources:
            lines.append("  Sources:")
            for src in sources[:5]:
                if isinstance(src, dict):
                    lines.append(f"    - {src.get('title', '')} ({src.get('url', '')})")
                elif isinstance(src, str):
                    lines.append(f"    - {src}")
        tavily = c.get("tavily_sources") or c.get("search_results") or []
        if isinstance(tavily, list) and tavily:
            for t in tavily[:3]:
                if isinstance(t, dict):
                    lines.append(f"    - {t.get('title', '')} ({t.get('url', '')})")
        return "\n".join(lines)

    @staticmethod
    def _summarize_pe_model(pe_data: Dict[str, Any], max_chars: int = 20000) -> str:
        """Create a compact text summary of PE model data for LLM context.

        Reads from the flexible EXTRACTION_SCHEMA — works for any deal type.
        """
        parts: List[str] = []

        # Deal Profile
        dp = pe_data.get("deal_profile") or {}
        if dp:
            parts.append("\n**Deal Profile**:")
            for k, label in [("target_name", "Target"), ("deal_type", "Deal Type"),
                             ("strategy", "Strategy"), ("sponsor", "Sponsor"),
                             ("total_investment", "Total Investment"),
                             ("hold_period", "Hold Period"), ("primary_metric", "Primary Metric")]:
                v = dp.get(k)
                if v is not None and v != 0 and v != "":
                    if k == "total_investment" and isinstance(v, (int, float)):
                        parts.append(f"  {label}: ${v / 1e6:,.1f}M")
                    elif k == "hold_period":
                        parts.append(f"  {label}: {v} years")
                    elif k == "deal_type":
                        parts.append(f"  {label}: {str(v).replace('_', ' ').title()}")
                    else:
                        parts.append(f"  {label}: {v}")

        # Instruments
        instruments = pe_data.get("instruments") or []
        if instruments:
            parts.append(f"\n**Instruments** ({len(instruments)}):")
            parts.append("  | Name | Type | Amount | Key Terms |")
            parts.append("  |------|------|--------|-----------|")
            for inst in instruments:
                amt = inst.get("amount", 0)
                amt_str = f"${amt / 1e6:,.0f}M" if amt else "—"
                inst_type = inst.get("type", "?").replace("_", " ").title()
                terms = inst.get("terms") or {}
                term_strs = [f"{k}: {v}" for k, v in list(terms.items())[:3]]
                terms_str = "; ".join(term_strs) if term_strs else "—"
                parts.append(f"  | {inst.get('name', '?')} | {inst_type} | {amt_str} | {terms_str} |")

        # Sources & Uses
        su = pe_data.get("sources_uses") or {}
        sources = su.get("sources") or []
        uses = su.get("uses") or []
        if sources or uses:
            parts.append("\n**Sources & Uses**:")
            if sources:
                parts.append("  Sources:")
                for item in sources:
                    amt = item.get("amount", 0)
                    parts.append(f"    {item.get('name', '?')}: ${amt / 1e6:,.1f}M" if amt else f"    {item.get('name', '?')}")
            if uses:
                parts.append("  Uses:")
                for item in uses:
                    amt = item.get("amount", 0)
                    parts.append(f"    {item.get('name', '?')}: ${amt / 1e6:,.1f}M" if amt else f"    {item.get('name', '?')}")

        # Operating Model — flexible metrics
        om = pe_data.get("operating_model") or {}
        periods = om.get("periods") or []
        metrics = om.get("metrics") or {}
        if periods and metrics:
            parts.append(f"\n**Operating Model** ({len(periods)} periods: {', '.join(str(p) for p in periods)}):")
            for metric_name, metric_data in metrics.items():
                if not isinstance(metric_data, dict):
                    continue
                values = metric_data.get("values") or []
                fmt = metric_data.get("format", "number")
                if values:
                    if fmt == "dollar":
                        vals = ", ".join(f"${v / 1e6:,.1f}M" for v in values)
                    elif fmt == "pct":
                        vals = ", ".join(f"{v:.1f}%" for v in values)
                    elif fmt == "multiple":
                        vals = ", ".join(f"{v:.1f}x" for v in values)
                    else:
                        vals = ", ".join(f"{v:,.1f}" for v in values)
                    parts.append(f"  {metric_name}: [{vals}]")

        # Debt Schedule
        sched = pe_data.get("debt_schedule") or {}
        if sched.get("periods"):
            parts.append("\n**Debt Schedule**:")
            parts.append(f"  Periods: {', '.join(str(p) for p in sched['periods'])}")
            total_bal = sched.get("total_balance") or []
            if total_bal:
                vals = ", ".join(f"${v / 1e6:,.1f}M" for v in total_bal)
                parts.append(f"  Total Balance: [{vals}]")
            leverage = sched.get("leverage_ratio") or []
            if leverage:
                vals = ", ".join(f"{v:.1f}x" for v in leverage)
                parts.append(f"  Leverage: [{vals}]")
            interest = sched.get("interest_expense") or []
            if interest:
                vals = ", ".join(f"${v / 1e6:,.1f}M" for v in interest)
                parts.append(f"  Interest: [{vals}]")

        # Returns — flexible scenarios
        returns = pe_data.get("returns") or {}
        scenarios = returns.get("scenarios") or {}
        for sc_name, sc_data in scenarios.items():
            if not isinstance(sc_data, dict):
                continue
            parts.append(f"\n**{sc_name.replace('_', ' ').title()} Returns**:")
            for k, v in sc_data.items():
                if v is None or v == 0:
                    continue
                k_lower = k.lower()
                if "irr" in k_lower or "yield" in k_lower:
                    display = f"{v * 100:.1f}%" if abs(v) < 1 else f"{v:.1f}%"
                elif "moic" in k_lower or "multiple" in k_lower:
                    display = f"{v:.2f}x"
                elif "value" in k_lower or "equity" in k_lower or "ev" in k_lower:
                    display = f"${v / 1e6:,.1f}M"
                elif "year" in k_lower:
                    display = str(int(v))
                else:
                    display = f"{v:,.2f}"
                parts.append(f"  {k.replace('_', ' ').title()}: {display}")

        # Sensitivity matrix
        sm = returns.get("sensitivity_matrix")
        if sm and isinstance(sm, dict) and sm.get("irr_grid"):
            parts.append(f"\n**Sensitivity Matrix** ({sm.get('row_label', 'Row')} × {sm.get('col_label', 'Col')}):")
            row_vals = sm.get("row_values", [])
            col_vals = sm.get("col_values", [])
            irr_grid = sm.get("irr_grid", [])
            if col_vals:
                parts.append("  | " + " | ".join([""] + [str(c) for c in col_vals]) + " |")
                parts.append("  | " + " | ".join(["---"] * (len(col_vals) + 1)) + " |")
            for i, row in enumerate(irr_grid):
                label = str(row_vals[i]) if i < len(row_vals) else str(i)
                cells = [f"{v * 100:.1f}%" if abs(v) < 1 else f"{v:.1f}%" for v in row]
                parts.append("  | " + label + " | " + " | ".join(cells) + " |")

        # Append validation results so LLM knows about data quality issues
        validation = pe_data.get("_validation") or {}
        v_warnings = validation.get("warnings") or []
        v_errors = validation.get("errors") or []
        if v_errors or v_warnings:
            parts.append("\n**Data Quality Notes**:")
            for e in v_errors:
                parts.append(f"  ERROR: {e}")
            for w in v_warnings:
                parts.append(f"  WARNING: {w}")
        else:
            parts.append("\n**Data Quality**: All extraction checks passed.")

        result = "\n".join(parts)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n... (truncated)"
        return result

    def _summarize_company_compact(self, c: Dict[str, Any]) -> str:
        """Single markdown table row for compact portfolio mode."""
        name = c.get("company", "Unknown")
        stage = c.get("stage", "—")
        sector = c.get("sector", c.get("industry", "—")) or "—"

        rev = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue")) or 0
        val = ensure_numeric(c.get("valuation")) or ensure_numeric(c.get("inferred_valuation")) or 0
        growth = c.get("revenue_growth") or c.get("growth_rate") or c.get("inferred_growth_rate")
        total_funding = ensure_numeric(c.get("total_funding")) or 0

        est_r = c.get("_revenue_estimated", False)
        est_v = c.get("_valuation_estimated", False)
        est_g = c.get("_growth_estimated", False)

        def _fmt_money(v, est):
            if not v:
                return "—"
            label = f"${v / 1e6:,.1f}M" if v >= 1_000_000 else f"${v / 1e3:,.0f}K"
            return f"[Est] {label}" if est else label

        def _fmt_growth(g, est):
            if not g or not isinstance(g, (int, float)):
                return "—"
            pct = g * 100 if 0 < abs(g) < 10 else g
            return f"[Est] {pct:.0f}%" if est else f"{pct:.0f}%"

        # Data quality: count non-empty real (non-estimated) fields
        _real_fields = sum(1 for f in ("revenue", "valuation", "total_funding", "description",
                                        "team_size", "burn_rate") if c.get(f))
        quality = "High" if _real_fields >= 4 else "Med" if _real_fields >= 2 else "Low"

        return (
            f"| **{name}** | {stage} | {sector} | {_fmt_money(rev, est_r)} | "
            f"{_fmt_money(val, est_v)} | {_fmt_growth(growth, est_g)} | "
            f"{_fmt_money(total_funding, False)} | {quality} |"
        )

    def _summarize_data(self, data: Dict[str, Any], max_chars: int = 60000) -> str:
        """Create a compact text summary of available data for LLM context.

        For portfolios with >8 companies, uses a compact TABLE format so the LLM
        sees ALL companies in ~3-5K chars instead of narrative blocks that eat budget.
        For ≤8 companies, uses the detailed narrative format.

        Budget: 5% for aggregate stats, 65% for companies, 30% for fund/portfolio data.
        Respects company boundaries — never truncates mid-company.
        """
        # ── Portfolio aggregate stats (always included) ──
        companies = data.get("companies", [])
        agg_parts: List[str] = []
        if companies:
            from collections import Counter
            stages = Counter(c.get("stage", "Unknown") for c in companies)
            sectors = Counter(c.get("sector", c.get("industry", "Unknown")) for c in companies)
            total_deployed = sum(
                ensure_numeric(c.get("total_funding") or c.get("inferred_total_funding"), 0)
                for c in companies
            )
            # Count data quality tiers
            data_rich = [c for c in companies if c.get("revenue") and not c.get("_revenue_estimated")]
            sparse = [c for c in companies if c not in data_rich]

            agg_parts.append(f"\n**Portfolio Aggregate** ({len(companies)} companies):")
            agg_parts.append(f"  Stages: {dict(stages.most_common(8))}")
            agg_parts.append(f"  Sectors: {dict(sectors.most_common(8))}")
            if total_deployed:
                agg_parts.append(f"  Total deployed: ${total_deployed / 1e6:,.0f}M")
            agg_parts.append(f"  Data quality: {len(data_rich)} data-rich, {len(sparse)} sparse/estimated")

            # Approximate fund-level metrics from whatever data exists (including estimates)
            total_val = sum(ensure_numeric(c.get("valuation") or c.get("inferred_valuation"), 0) for c in companies)
            total_rev = sum(ensure_numeric(c.get("revenue") or c.get("inferred_revenue"), 0) for c in companies)
            if total_val:
                has_est = any(c.get("_valuation_estimated") for c in companies)
                est_label = " [includes stage-based estimates]" if has_est else ""
                agg_parts.append(f"  Approx. total portfolio NAV: ${total_val / 1e6:,.0f}M{est_label}")
            if total_rev:
                has_est = any(c.get("_revenue_estimated") for c in companies)
                est_label = " [includes stage-based estimates]" if has_est else ""
                agg_parts.append(f"  Approx. total portfolio ARR: ${total_rev / 1e6:,.0f}M{est_label}")
            if total_deployed and total_val:
                agg_parts.append(f"  Approx. portfolio TVPI: {total_val / total_deployed:.2f}x")
            if total_deployed and total_rev:
                agg_parts.append(f"  Approx. portfolio revenue multiple (deployed): {total_rev / total_deployed:.2f}x")

        agg_block = "\n".join(agg_parts) + "\n" if agg_parts else ""

        # ── PE model data (replaces company data for PE memos) ─────────
        pe_data = data.get("pe_model_data")
        if pe_data:
            return agg_block + self._summarize_pe_model(pe_data, max_chars - len(agg_block))

        company_budget = int((max_chars - len(agg_block)) * 0.7)
        fund_budget = max_chars - len(agg_block) - company_budget

        # ── Companies: compact table for >8 companies, narrative for ≤8 ──
        company_parts: List[str] = []
        chars_used = 0
        companies_included = 0

        if len(companies) > 8:
            # COMPACT TABLE MODE — every company visible in ~3-5K chars
            company_parts.append("\n**All Portfolio Companies**:")
            company_parts.append("| Company | Stage | Sector | ARR | Valuation | Growth | Funding | Data |")
            company_parts.append("|---------|-------|--------|-----|-----------|--------|---------|------|")
            for c in companies:
                company_parts.append(self._summarize_company_compact(c))

            # Add detailed narrative for all companies, data-rich first
            data_rich = [c for c in companies
                         if c.get("revenue") and not c.get("_revenue_estimated")]
            sparse = [c for c in companies if c not in data_rich]
            ordered = data_rich + sparse  # data-rich first, then rest

            company_parts.append(f"\n**Detailed Profiles ({len(ordered)} companies)**:")
            profiled = 0
            for c in ordered:
                block = self._summarize_company(c)
                if chars_used + len(block) > company_budget * 0.6 and profiled > 0:
                    remaining = len(ordered) - profiled
                    company_parts.append(f"\n... (+{remaining} more, see table above)")
                    break
                company_parts.append(block)
                chars_used += len(block)
                profiled += 1
            companies_included = len(companies)
        else:
            # NARRATIVE MODE — detailed per-company blocks (original behavior)
            for c in companies:
                block = self._summarize_company(c)
                if chars_used + len(block) > company_budget and companies_included > 0:
                    remaining = len(companies) - companies_included
                    if remaining > 0:
                        company_parts.append(f"\n... (+{remaining} companies omitted)")
                    break
                company_parts.append(block)
                chars_used += len(block)
                companies_included += 1

        # ── Fund & portfolio data (30% budget) ──
        fund_parts: List[str] = []

        fund_ctx = data.get("fund_context", {})
        if fund_ctx:
            fund_parts.append("\n**Fund Context**:")
            for k in ("fund_name", "fund_size", "remaining_capital", "fund_id"):
                v = fund_ctx.get(k)
                if v is not None:
                    if isinstance(v, (int, float)) and abs(v) > 1_000_000:
                        fund_parts.append(f"  {k}: ${v / 1e6:,.0f}M")
                    else:
                        fund_parts.append(f"  {k}: {v}")

        fund_metrics = data.get("fund_metrics", {})
        if fund_metrics:
            perf = fund_metrics.get("metrics", fund_metrics)
            fund_parts.append("\n**Fund Metrics**:")
            for k in ("tvpi", "dpi", "irr", "total_nav", "total_invested", "total_committed"):
                v = perf.get(k)
                if v is not None:
                    fund_parts.append(f"  {k}: {v}")

        followon = data.get("followon_strategy", {})
        if followon:
            fund_parts.append("\n**Follow-On Strategy**:")
            for cid, fo in (followon.items() if isinstance(followon, dict) else []):
                if isinstance(fo, dict):
                    fund_parts.append(f"  {fo.get('company_name', cid)}:")
                    for fk in ("recommendation", "pro_rata_amount", "current_ownership_pct",
                               "ownership_with_followon", "ownership_without_followon"):
                        fv = fo.get(fk)
                        if fv is not None:
                            fund_parts.append(f"    {fk}: {fv}")

        # Sourcing results from the source_companies flow (includes full scoring)
        sourcing_results = data.get("sourcing_results", {})
        if sourcing_results:
            sr_companies = sourcing_results.get("companies", [])
            sr_thesis = sourcing_results.get("thesis", "")
            if sr_companies:
                fund_parts.append(f"\n**Sourcing Results** ({len(sr_companies)} scored companies{', thesis: ' + sr_thesis if sr_thesis else ''}):")
                fund_parts.append("| Rank | Company | Sector | Stage | ARR | Score | Top Dimensions |")
                fund_parts.append("|------|---------|--------|-------|-----|-------|----------------|")
                for comp in sr_companies[:15]:
                    arr = comp.get("arr") or 0
                    arr_str = f"${arr / 1e6:.1f}M" if arr > 0 else "—"
                    breakdown = comp.get("score_breakdown", {})
                    top_dims = ""
                    if isinstance(breakdown, dict):
                        sorted_dims = sorted(breakdown.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True)[:3]
                        top_dims = ", ".join(f"{k}:{v}" for k, v in sorted_dims if isinstance(v, (int, float)))
                    sem = comp.get("semantic_reason", "")
                    rank = comp.get("rank", "—")
                    fund_parts.append(
                        f"| {rank} | {comp.get('name', '?')} | {comp.get('sector', '?')} | "
                        f"{comp.get('stage', '?')} | {arr_str} | {comp.get('score', 0):.0f} | {top_dims} |"
                    )
                    if sem:
                        fund_parts.append(f"|  |  |  |  |  |  | _{sem}_ |")

        sourcing_ctx = data.get("sourcing_context", {})
        if sourcing_ctx:
            comps = sourcing_ctx.get("comparables", [])
            if comps:
                fund_parts.append(f"\n**Sourcing Context** ({sourcing_ctx.get('total_in_db', 0)} companies in DB, sectors: {', '.join(sourcing_ctx.get('sectors_queried', [])[:5])}):")
                fund_parts.append("| Company | Sector | Stage | ARR | Score |")
                fund_parts.append("|---------|--------|-------|-----|-------|")
                for comp in comps[:10]:
                    arr = comp.get("arr") or 0
                    arr_str = f"${arr / 1e6:.1f}M" if arr > 0 else "—"
                    fund_parts.append(
                        f"| {comp.get('name', '?')} | {comp.get('sector', '?')} | "
                        f"{comp.get('stage', '?')} | {arr_str} | {comp.get('score', 0):.0f} |"
                    )

        portfolio_health = data.get("portfolio_health", {})
        if portfolio_health:
            analytics = portfolio_health.get("company_analytics", {})
            if analytics:
                fund_parts.append("\n**Portfolio Health**:")
                items = analytics.items() if isinstance(analytics, dict) else []
                for cid, a in list(items)[:5]:
                    fund_parts.append(
                        f"  {a.get('company_name', cid)}: "
                        f"ARR=${a.get('current_arr', 0) / 1e6:.1f}M, "
                        f"growth={a.get('growth_rate', 0) * 100:.0f}%, "
                        f"runway={a.get('estimated_runway_months', 0):.0f}mo"
                    )

        fund_text = "\n".join(fund_parts)
        if len(fund_text) > fund_budget:
            fund_text = fund_text[:fund_budget] + "\n... (fund data truncated)"

        return agg_block + "\n".join(company_parts) + "\n" + fund_text

    def _format_title(self, template: Dict, data: Dict, prompt: str) -> str:
        """Format the title pattern with available data."""
        pattern = template["title_pattern"]

        companies = data.get("companies", [])
        company_names = ", ".join(c.get("company", "?") for c in companies[:3])
        if len(companies) > 3:
            company_names += f" +{len(companies) - 3} more"

        fund_ctx = data.get("fund_context", {})
        now = datetime.now()

        return pattern.format(
            companies=company_names or "Portfolio",
            fund_name=fund_ctx.get("fund_name", "Fund"),
            quarter=str((now.month - 1) // 3 + 1),
            year=str(now.year),
            query_summary=prompt[:60] if prompt else "Analysis",
        )

    def _suggest_chart_type(self, section_def: Dict, data: Dict, companies: List[Dict]) -> Optional[str]:
        """Inspect what data actually exists and pick the best chart.

        Doesn't trust template data_keys — looks at real values in ``data``
        and ``companies``.  Designed to always return *something* useful even
        when fund-level data is incomplete or estimated.
        """
        # PE deals have their own chart set — never suggest VC charts
        if data.get("pe_model_data"):
            return None

        fund_metrics = data.get("fund_metrics") or {}
        fund_ctx = data.get("fund_context") or {}
        heading = (section_def.get("heading") or "").lower()
        num_companies = len(companies) if companies else 0

        # ── Score each candidate by how much real data backs it ──────────
        candidates: List[tuple] = []  # (score, chart_type)

        # DPI / distribution flow — works even with estimates (strategy 3
        # in _build_chart synthesizes from companies with total_funding)
        if fund_metrics.get("investments") or fund_metrics.get("dpi_sankey"):
            candidates.append((3, "dpi_sankey"))
        elif num_companies >= 1 and any(
            ensure_numeric(c.get("total_funding")) for c in companies
        ):
            # Strategy 3 can synthesize from companies alone
            candidates.append((1, "dpi_sankey"))

        # NAV waterfall — needs at least company valuations
        if fund_metrics.get("nav_by_company"):
            candidates.append((3, "waterfall"))
        elif num_companies >= 2 and any(
            ensure_numeric(c.get("valuation")) for c in companies
        ):
            candidates.append((1, "waterfall"))

        # Scenario / exit data
        scenario_analysis = data.get("scenario_analysis") or {}
        if scenario_analysis:
            has_breakpoints = any(
                isinstance(sc, dict) and sc.get("breakpoints")
                for sc in scenario_analysis.values()
                if isinstance(sc, dict)
            )
            candidates.append((3, "breakpoint_chart" if has_breakpoints else "probability_cloud"))
        elif num_companies == 1:
            # CDS can generate probability_cloud from a single company
            candidates.append((1, "probability_cloud"))

        # Cap table evolution — works from company stage alone (CDS synthesizes)
        cap_history = data.get("cap_table_history") or {}
        if cap_history:
            candidates.append((3, "cap_table_evolution"))
        elif num_companies >= 1 and any(c.get("stage") for c in companies):
            candidates.append((1, "cap_table_evolution"))

        # Revenue scatter — needs 2+ companies with some revenue signal
        cos_with_rev = sum(
            1 for c in (companies or [])
            if ensure_numeric(c.get("revenue") or c.get("inferred_revenue"))
        )
        if cos_with_rev >= 3:
            candidates.append((2, "scatter_multiples"))
        if cos_with_rev >= 1:
            candidates.append((1, "revenue_forecast"))

        # Radar — needs 2+ companies for meaningful comparison
        if num_companies >= 2:
            candidates.append((1, "radar_comparison"))

        # Heatmap — needs 3+ companies with multiple metrics
        if num_companies >= 3:
            candidates.append((1, "heatmap"))

        # Market map — needs 4+ companies for a meaningful map
        if num_companies >= 4:
            candidates.append((1, "market_map"))

        # Stacked bar — needs 2+ companies with stage or sector data
        if num_companies >= 2 and any(c.get("stage") or c.get("sector") for c in companies):
            candidates.append((1, "stacked_bar"))

        # NAV live — needs fund metrics with NAV data
        if fund_metrics.get("nav_by_company") or fund_metrics.get("nav"):
            candidates.append((2, "nav_live"))

        # Tornado / sensitivity — needs FPA or scenario results
        if data.get("fpa_result"):
            candidates.append((2, "sensitivity_tornado"))

        # Monte carlo — needs pre-computed monte carlo results
        if data.get("monte_carlo_result"):
            candidates.append((2, "monte_carlo_histogram"))

        # Bar comparison — needs 2+ companies
        if num_companies >= 2:
            candidates.append((1, "bar_comparison"))

        # LTM/NTM regression — needs 3+ companies with revenue
        if cos_with_rev >= 3:
            candidates.append((1, "ltm_ntm_regression"))

        if not candidates:
            return None

        # ── Pick best candidate, use heading as tiebreaker hint ──────────
        # If the section heading hints at a specific domain, boost matching types
        heading_boosts = {
            "dpi": "dpi_sankey", "distribution": "dpi_sankey", "flow": "dpi_sankey",
            "nav": "waterfall", "waterfall": "waterfall",
            "exit": "probability_cloud", "scenario": "probability_cloud", "return": "probability_cloud",
            "cap table": "cap_table_evolution", "ownership": "cap_table_evolution", "dilution": "cap_table_evolution",
            "revenue": "revenue_forecast", "growth": "revenue_forecast", "forecast": "revenue_forecast",
            "market": "scatter_multiples", "positioning": "scatter_multiples", "landscape": "scatter_multiples",
            "moat": "radar_comparison", "team": "radar_comparison", "scoring": "radar_comparison",
            "heatmap": "heatmap", "heat map": "heatmap", "matrix": "heatmap",
            "map": "market_map", "sector map": "market_map",
            "sensitivity": "sensitivity_tornado", "tornado": "sensitivity_tornado",
            "monte carlo": "monte_carlo_histogram", "simulation": "monte_carlo_histogram",
            "bar": "bar_comparison", "comparison": "bar_comparison",
            "ltm": "ltm_ntm_regression", "ntm": "ltm_ntm_regression", "regression": "ltm_ntm_regression",
            "stacked": "stacked_bar", "allocation": "stacked_bar",
        }
        for hint_word, boosted_type in heading_boosts.items():
            if hint_word in heading:
                for i, (score, ctype) in enumerate(candidates):
                    if ctype == boosted_type:
                        candidates[i] = (score + 2, ctype)
                break

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _build_chart(
        self, section_def: Dict, data: Dict, companies: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Build chart config from available data.

        Uses ChartDataService for company-derived charts and shared format
        helpers for artifact-derived charts.  All numeric access goes through
        ensure_numeric so None / InferenceResult never cause silent failures.

        When chart_type="auto", inspects available data to pick the best chart.
        """
        chart_type = section_def.get("chart_type")
        if not chart_type:
            return None

        data_keys = section_def.get("data_keys", [])

        # ── PE model charts — dispatch to pe_chart_generators ──────────
        pe_data = data.get("pe_model_data")
        if pe_data:
            # PE deals use PE-specific charts; skip VC-only charts like probability_cloud
            _VC_ONLY_CHARTS = {"probability_cloud", "scatter_multiples", "revenue_multiple_scatter",
                               "next_round_treemap", "cap_table_sankey", "bull_bear_base"}
            if chart_type in _VC_ONLY_CHARTS:
                logger.debug("[MEMO] Skipping VC-only chart %s for PE deal", chart_type)
                return None
            if chart_type in ("ebitda_bridge", "sources_uses", "debt_paydown", "returns_sensitivity", "capital_stack"):
                try:
                    from app.services.pe_chart_generators import build_pe_chart
                    result = build_pe_chart(section_def["key"], pe_data)
                    if result:
                        return result
                except Exception as exc:
                    logger.warning("[MEMO] PE chart build failed for %s: %s", chart_type, exc)

        # Dynamic chart selection — inspect data and pick the best chart
        if chart_type == "auto":
            chart_type = self._suggest_chart_type(section_def, data, companies)
            if not chart_type:
                return None
            # Update section_def so downstream code sees the resolved type
            section_def = {**section_def, "chart_type": chart_type}

        data_keys = section_def.get("data_keys", [])
        heading = section_def.get("heading", "Chart")

        # ── ChartDataService charts (work directly from companies) ────────
        cds = self._get_chart_data_service()

        if cds and companies:
            fund_ctx = data.get("fund_context") or {}
            check_size = ensure_numeric(fund_ctx.get("avg_check_size"), 10_000_000)
            fund_size = ensure_numeric(
                fund_ctx.get("fund_size") or fund_ctx.get("total_committed"),
                260_000_000,
            )

            # Hydrate company dicts from pre-computed shared_data so CDS methods
            # see complete data (pwerm_scenarios, revenue, growth_rate) instead of
            # trying to regenerate from scratch and failing on incomplete inputs.
            scenario_analysis = data.get("scenario_analysis") or {}
            revenue_projections = data.get("revenue_projections") or {}
            cap_table_history = data.get("cap_table_history") or {}

            for _co in companies:
                _name = _co.get("company") or _co.get("name", "")

                # Revenue: prefer actual, then inferred
                if not ensure_numeric(_co.get("revenue")):
                    _inferred = ensure_numeric(_co.get("inferred_revenue"))
                    if _inferred:
                        _co["revenue"] = _inferred

                # PWERM scenarios: inject from scenario_analysis if missing
                if not _co.get("pwerm_scenarios") and _name in scenario_analysis:
                    sc = scenario_analysis[_name]
                    if isinstance(sc, dict) and sc.get("scenarios"):
                        _co["full_exit_distribution"] = sc["scenarios"]
                        if sc.get("pwerm_valuation"):
                            _co["pwerm_valuation"] = sc["pwerm_valuation"]

                # Growth rate: inject from revenue_projections if missing
                if not _co.get("growth_rate") and _name in revenue_projections:
                    rp = revenue_projections[_name]
                    if isinstance(rp, dict) and rp.get("growth_rate"):
                        _co["growth_rate"] = rp["growth_rate"]

                # Valuation: ensure numeric so CDS probability_cloud can compute
                if not ensure_numeric(_co.get("valuation")):
                    _inferred_val = ensure_numeric(_co.get("inferred_valuation"))
                    if _inferred_val:
                        _co["valuation"] = _inferred_val

            cds_dispatch = {
                # ── Company-derived charts ─────────────────────────────────
                "probability_cloud": lambda: cds.generate_probability_cloud(
                    companies[0], check_size
                ),
                "scatter_multiples": lambda: cds.generate_revenue_multiple_scatter(companies),
                "revenue_multiple_scatter": lambda: cds.generate_revenue_multiple_scatter(companies),
                "treemap": lambda: cds.generate_revenue_treemap(companies),
                "revenue_treemap": lambda: cds.generate_revenue_treemap(companies),
                "revenue_forecast": lambda: (
                    self._build_revenue_decay_chart(cds, data, companies)
                    or cds.generate_path_to_100m(companies)
                ),
                "growth_decay": lambda: (
                    self._build_revenue_decay_chart(cds, data, companies)
                    or cds.generate_cashflow_projection(companies)
                ),
                "path_to_100m": lambda: cds.generate_path_to_100m(companies),
                "next_round_treemap": lambda: cds.generate_next_round_treemap(companies),
                "revenue_growth_treemap": lambda: cds.generate_revenue_growth_treemap(companies),
                "product_velocity": lambda: cds.generate_product_velocity_ranking(companies),
                "cashflow_projection": lambda: cds.generate_cashflow_projection(companies),
                "dpi_sankey": lambda: cds.generate_dpi_sankey(companies, fund_size),
                "bar_comparison": lambda: cds.generate_bar_comparison(companies),
                "bull_bear_base": lambda: cds.generate_bull_bear_base(companies),
                "radar_comparison": lambda: cds.generate_radar_comparison(companies) if hasattr(cds, "generate_radar_comparison") else None,
                "heatmap": lambda: cds.generate_heatmap(companies) if hasattr(cds, "generate_heatmap") else None,
                "market_map": lambda: cds.generate_market_map(companies) if hasattr(cds, "generate_market_map") else None,
                "stacked_bar": lambda: cds.generate_stacked_bar(companies) if hasattr(cds, "generate_stacked_bar") else None,
                "nav_live": lambda: cds.generate_nav_live(companies) if hasattr(cds, "generate_nav_live") else None,
                "cap_table_sankey": lambda: cds.generate_cap_table_sankey(companies[0]) if hasattr(cds, "generate_cap_table_sankey") else None,
                "waterfall_cds": lambda: cds.generate_waterfall(companies) if hasattr(cds, "generate_waterfall") else None,
                "fpa_stress_test": lambda: cds.generate_fpa_stress_test(
                    data.get("fpa_result", {})) if hasattr(cds, "generate_fpa_stress_test") else None,
                # ── Analytics-bridge charts (use stored results from shared_data) ──
                "sensitivity_tornado": lambda: cds.generate_sensitivity_tornado(
                    data.get("fpa_result", {})),
                "tornado": lambda: cds.generate_sensitivity_tornado(
                    data.get("fpa_result", {})),
                "regression_line": lambda: cds.generate_regression_line(
                    data.get("fpa_result", {})),
                "monte_carlo_histogram": lambda: cds.generate_monte_carlo_histogram(
                    data.get("monte_carlo_result", {})),
                "monte_carlo": lambda: cds.generate_monte_carlo_histogram(
                    data.get("monte_carlo_result", {})),
                "revenue_forecast_decay": lambda: self._build_revenue_decay_chart(cds, data, companies),
                "fund_scenarios": lambda: cds.generate_fund_scenario_comparison(
                    data.get("scenario_all_charts", {})),
                "fund_scenario_comparison": lambda: cds.generate_fund_scenario_comparison(
                    data.get("scenario_all_charts", {})),
                "ltm_ntm_regression": lambda: cds.generate_ltm_ntm_regression(companies),
                "revenue_forecast_line": lambda: cds.generate_revenue_forecast(companies) if hasattr(cds, "generate_revenue_forecast") else None,
            }
            generator = cds_dispatch.get(chart_type)
            if generator:
                try:
                    result = generator()
                    if result:
                        return result
                except Exception as exc:
                    logger.warning("[MEMO] ChartDataService error for %s: %s", chart_type, exc)

        # ── Fund-level pre-computed charts (from _populate_memo_service_data) ──
        fund_metrics = data.get("fund_metrics") or {}
        if chart_type in fund_metrics:
            precomputed = fund_metrics[chart_type]
            if isinstance(precomputed, dict) and precomputed.get("type"):
                return precomputed

        # ── Artifact-derived charts (read from shared_data analysis results) ──

        if chart_type == "sankey":
            cap_history = data.get("cap_table_history") or {}
            if isinstance(cap_history, dict):
                sankey = cap_history.get("sankey_data")
                if sankey and isinstance(sankey, dict):
                    nodes = sankey.get("nodes", [])
                    links = sankey.get("links", [])
                    if nodes and links:
                        return format_sankey_chart(nodes, links, title=heading)
                for name, ch in cap_history.items():
                    if isinstance(ch, dict) and ch.get("sankey_data"):
                        sd = ch["sankey_data"]
                        nodes = sd.get("nodes", [])
                        links = sd.get("links", [])
                        if nodes and links:
                            return format_sankey_chart(
                                nodes, links, title=f"{name} — Ownership Flow"
                            )

        elif chart_type == "waterfall":
            fund_metrics = data.get("fund_metrics") or {}
            investments = fund_metrics.get("investments", [])
            if investments:
                items = [
                    {
                        "label": inv.get("company_name", "Unknown"),
                        "value": ensure_numeric(inv.get("nav_contribution")),
                        "type": "positive" if ensure_numeric(inv.get("nav_contribution")) >= 0 else "negative",
                    }
                    for inv in sorted(
                        investments,
                        key=lambda x: ensure_numeric(x.get("nav_contribution")),
                        reverse=True,
                    )[:10]
                ]
                return format_waterfall_chart(items, title="NAV Contribution by Company")

            exit_modeling = data.get("exit_modeling") or {}
            scenarios = exit_modeling.get("scenarios", [])
            if scenarios:
                items = [
                    {
                        "label": ex.get("company_name", "Unknown"),
                        "value": ensure_numeric(
                            (ex.get("hold_vs_sell") or {}).get("hold_2yr_moic")
                        ),
                        "type": "positive",
                    }
                    for ex in scenarios[:10]
                ]
                return format_waterfall_chart(items, title="Exit Proceeds by Company")

        elif chart_type == "bar":
            if "followon_strategy" in data_keys:
                fo_data = data.get("followon_strategy") or {}
                if isinstance(fo_data, dict):
                    labels, values_current, values_with, values_without = [], [], [], []
                    for cid, fo in fo_data.items():
                        if not isinstance(fo, dict):
                            continue
                        name = fo.get("company_name", cid)
                        current = ensure_numeric(fo.get("current_ownership_pct"))
                        with_fo = ensure_numeric(fo.get("ownership_with_followon"))
                        without_fo = ensure_numeric(fo.get("ownership_without_followon"))
                        if current or with_fo:
                            labels.append(name)
                            values_current.append(current)
                            values_with.append(with_fo)
                            values_without.append(without_fo)
                    if labels:
                        return format_bar_chart(
                            labels=labels,
                            datasets=[
                                {"label": "Current", "data": values_current},
                                {"label": "With Follow-on", "data": values_with},
                                {"label": "Without Follow-on", "data": values_without},
                            ],
                            title=heading,
                        )

            if "portfolio_health" in data_keys:
                ph = data.get("portfolio_health") or {}
                analytics = ph.get("company_analytics") or {}
                returns = ph.get("company_returns") or {}
                if isinstance(analytics, dict) and analytics:
                    pairs = [
                        (
                            v.get("company_name", k),
                            ensure_numeric((returns.get(k) or {}).get("moic")),
                        )
                        for k, v in analytics.items()
                    ]
                    pairs.sort(key=lambda p: p[1], reverse=True)
                    if pairs:
                        return format_bar_chart(
                            labels=[p[0] for p in pairs],
                            datasets=[{"label": "MOIC", "data": [p[1] for p in pairs]}],
                            title="Portfolio MOIC by Company",
                        )

            if "fund_scenarios" in data_keys:
                fs = data.get("fund_scenarios") or {}
                scenarios = fs.get("portfolio_scenarios", []) or fs.get("scenarios", [])
                if scenarios:
                    return format_bar_chart(
                        labels=[s.get("scenario_name", "Unknown") for s in scenarios],
                        datasets=[{
                            "label": "Fund MOIC",
                            "data": [ensure_numeric(s.get("fund_moic")) for s in scenarios],
                        }],
                        title="Fund MOIC by Scenario",
                    )

        elif chart_type == "portfolio_scatter":
            # Fallback scatter that works from just companies list
            if companies and len(companies) >= 2:
                scatter_points = []
                for c in companies:
                    rev = ensure_numeric(c.get("revenue") or c.get("inferred_revenue"), 0)
                    val = ensure_numeric(c.get("valuation") or c.get("inferred_valuation"), 0)
                    name = c.get("company") or c.get("name", "Unknown")
                    if rev > 0 or val > 0:
                        scatter_points.append({
                            "x": rev / 1e6,
                            "y": val / 1e6,
                            "label": name,
                            "r": 8,
                        })
                if scatter_points:
                    return {
                        "type": "scatter",
                        "title": heading,
                        "data": {
                            "datasets": [{
                                "label": "Portfolio Companies",
                                "data": scatter_points,
                            }],
                        },
                        "options": {
                            "scales": {
                                "x": {"title": {"display": True, "text": "Revenue ($M)"}},
                                "y": {"title": {"display": True, "text": "Valuation ($M)"}},
                            }
                        },
                        "renderType": "chartjs",
                    }

        elif chart_type == "portfolio_bar":
            # Fallback bar chart built from companies list — sector or stage distribution
            if companies:
                from collections import Counter
                sectors = Counter(
                    c.get("sector") or c.get("industry") or "Other"
                    for c in companies
                )
                if len(sectors) >= 2:
                    top = sectors.most_common(10)
                    return format_bar_chart(
                        labels=[s[0] for s in top],
                        datasets=[{"label": "Companies", "data": [s[1] for s in top]}],
                        title="Portfolio by Sector",
                    )

        elif chart_type == "cohort_revenue_chart":
            # Revenue by stage cohort from companies list
            if companies:
                from collections import defaultdict
                cohorts: Dict[str, List[float]] = defaultdict(list)
                for c in companies:
                    stage = c.get("stage") or "Unknown"
                    rev = ensure_numeric(c.get("revenue") or c.get("inferred_revenue"), 0)
                    cohorts[stage].append(rev / 1e6)
                if cohorts:
                    labels = sorted(cohorts.keys())
                    datasets = [{
                        "label": "Median Revenue ($M)",
                        "data": [
                            sorted(cohorts[s])[len(cohorts[s]) // 2] if cohorts[s] else 0
                            for s in labels
                        ],
                    }]
                    return format_bar_chart(labels=labels, datasets=datasets, title=heading)

        elif chart_type == "fund_return_waterfall_chart":
            # Build from companies + scenario data
            if companies:
                items = []
                for c in companies:
                    rev = ensure_numeric(c.get("revenue") or c.get("inferred_revenue"), 0)
                    name = c.get("company") or c.get("name", "Unknown")
                    # Use a simple 5x multiple estimate if no scenario data
                    est_proceeds = rev * 5 / 1e6  # rough $M
                    items.append({
                        "label": name,
                        "value": round(est_proceeds, 1),
                        "type": "positive" if est_proceeds > 0 else "negative",
                    })
                items.sort(key=lambda x: x["value"], reverse=True)
                if items:
                    return format_waterfall_chart(items[:12], title=heading)

        elif chart_type == "cap_table_evolution":
            cap_history = data.get("cap_table_history") or {}
            if isinstance(cap_history, dict):
                for name, ch in cap_history.items():
                    if isinstance(ch, dict):
                        rounds = ch.get("evolution") or ch.get("rounds", [])
                        if rounds:
                            return {
                                "type": "cap_table_evolution",
                                "title": heading,
                                "data": {"evolution": rounds},
                                "renderType": "tableau",
                            }

        elif chart_type == "breakpoint_chart":
            scenarios = data.get("scenario_analysis") or {}
            if isinstance(scenarios, dict):
                for name, sc in scenarios.items():
                    breakpoints = sc.get("breakpoints", []) if isinstance(sc, dict) else []
                    if breakpoints:
                        return {
                            "type": "breakpoint_chart",
                            "title": heading,
                            "data": {"breakpoints": breakpoints},
                            "renderType": "tableau",
                        }

        elif chart_type == "dpi_sankey":
            fund_metrics = data.get("fund_metrics") or {}
            exit_modeling = data.get("exit_modeling") or {}

            # Strategy 1: pre-computed dpi_sankey artifact
            sankey_data = fund_metrics.get("dpi_sankey") or exit_modeling.get("dpi_sankey")
            if sankey_data and isinstance(sankey_data, dict):
                nodes = sankey_data.get("nodes", [])
                links = sankey_data.get("links", [])
                if nodes and links:
                    return format_sankey_chart(nodes, links, title=heading)

            # Strategy 2: synthesize from fund_metrics.investments
            investments = fund_metrics.get("investments", [])
            if isinstance(investments, list) and investments:
                result = self._synthesize_dpi_sankey(investments, fund_metrics, heading)
                if result:
                    return result

            # Strategy 3: synthesize from companies list with estimated ownership
            if companies:
                result = self._synthesize_dpi_sankey_from_companies(companies, fund_metrics, heading)
                if result:
                    return result

        elif chart_type == "radar_comparison":
            if companies and len(companies) >= 2:
                dimensions = ["Technical", "Domain", "Execution", "Fundraising", "Leadership"]
                radar_data = []
                company_names = [
                    c.get("company", c.get("name", f"Co{i}"))
                    for i, c in enumerate(companies)
                ]
                for dim in dimensions:
                    entry: Dict[str, Any] = {"dimension": dim}
                    for i, c in enumerate(companies):
                        entry[company_names[i]] = ensure_numeric(
                            c.get(f"{dim.lower()}_score"), 5
                        )
                    radar_data.append(entry)
                return {
                    "type": "radar_comparison",
                    "title": heading,
                    "data": {"dimensions": radar_data, "companies": company_names},
                    "renderType": "tableau",
                }

        elif chart_type == "funnel_pipeline":
            if companies:
                stages: Dict[str, int] = {}
                for c in companies:
                    stage = c.get("stage") or c.get("funnel_status") or "Unknown"
                    stages[stage] = stages.get(stage, 0) + 1
                stage_order = [
                    "Sourced", "First Meeting", "Diligence",
                    "Term Sheet", "Closed", "Monitoring",
                ]
                ordered: List[Dict[str, Any]] = []
                matched_keys: set = set()
                for s in stage_order:
                    s_norm = s.lower().replace(" ", "_")
                    for k, v in stages.items():
                        if k.lower().replace(" ", "_") == s_norm:
                            ordered.append({"name": s, "value": v})
                            matched_keys.add(k)
                            break
                # Append any stages not in the standard order
                for k, v in stages.items():
                    if k not in matched_keys:
                        ordered.append({"name": k, "value": v})
                if ordered:
                    return {
                        "type": "funnel_pipeline",
                        "title": heading,
                        "data": {"stages": ordered},
                        "renderType": "tableau",
                    }

        elif chart_type == "bull_bear_base":
            exit_data = data.get("exit_scenarios_data") or data.get("exit_modeling") or {}
            scenario_analysis = data.get("scenario_analysis") or {}
            labels: List[str] = []
            bear_vals: List[float] = []
            base_vals: List[float] = []
            bull_vals: List[float] = []

            if isinstance(exit_data, dict):
                for name, company_exits in exit_data.items():
                    if not isinstance(company_exits, dict):
                        continue
                    scenarios = company_exits.get("scenarios", [])
                    if not scenarios:
                        continue
                    buckets: Dict[str, float] = {"Bear": 0, "Base": 0, "Bull": 0}
                    for s in scenarios:
                        sn = (s.get("scenario_name") or s.get("name") or "").lower()
                        exit_val = ensure_numeric(s.get("exit_value")) / 1e6
                        if "bear" in sn or "down" in sn or "worst" in sn:
                            buckets["Bear"] = max(buckets["Bear"], exit_val)
                        elif "bull" in sn or "up" in sn or "best" in sn:
                            buckets["Bull"] = max(buckets["Bull"], exit_val)
                        else:
                            buckets["Base"] = max(buckets["Base"], exit_val)
                    if any(v > 0 for v in buckets.values()):
                        labels.append(name)
                        bear_vals.append(buckets["Bear"])
                        base_vals.append(buckets["Base"])
                        bull_vals.append(buckets["Bull"])

            if not labels and isinstance(scenario_analysis, dict):
                for name, sc in scenario_analysis.items():
                    if not isinstance(sc, dict):
                        continue
                    sc_list = sc.get("scenarios", [])
                    bbb: Dict[str, float] = {"Bear": 0, "Base": 0, "Bull": 0}
                    for s in sc_list[:6]:
                        sn = (s.get("name") or s.get("scenario_name") or "").lower()
                        exit_val = ensure_numeric(s.get("exit_value")) / 1e6
                        moic = ensure_numeric(s.get("moic", s.get("moic_base")))
                        val = exit_val if exit_val > 0 else moic
                        if "bear" in sn or "down" in sn or "worst" in sn:
                            bbb["Bear"] = max(bbb["Bear"], val)
                        elif "bull" in sn or "up" in sn or "best" in sn:
                            bbb["Bull"] = max(bbb["Bull"], val)
                        else:
                            bbb["Base"] = max(bbb["Base"], val)
                    if any(v > 0 for v in bbb.values()):
                        labels.append(name)
                        bear_vals.append(bbb["Bear"])
                        base_vals.append(bbb["Base"])
                        bull_vals.append(bbb["Bull"])

            if labels:
                return format_bar_chart(
                    labels=labels,
                    datasets=[
                        {"label": "Bear", "data": bear_vals},
                        {"label": "Base", "data": base_vals},
                        {"label": "Bull", "data": bull_vals},
                    ],
                    title=heading,
                )

        # ── Portfolio-level charts ────────────────────────────────────────────

        elif chart_type == "portfolio_scatter":
            # Bubble chart: x=revenue($M), y=valuation($M), z=ownership%, name=company
            points = []
            for i, c in enumerate(companies):
                name = c.get("company", c.get("name", f"Co{i}"))
                rev = ensure_numeric(c.get("revenue") or c.get("inferred_revenue"), 0) / 1e6
                val = ensure_numeric(c.get("valuation") or c.get("inferred_valuation"), 0) / 1e6
                ownership = ensure_numeric(c.get("our_ownership_pct") or c.get("ownership_pct"), 5.0)
                if val > 0:
                    points.append({
                        "name": name,
                        "x": round(rev, 2),
                        "y": round(val, 2),
                        "z": round(max(ownership, 0.5), 2),
                        "category": i,
                    })
            if points:
                return {
                    "type": "bubble",
                    "data": points,
                    "title": heading,
                    "renderType": "tableau",
                }

        elif chart_type == "cohort_revenue_chart":
            # Line chart: one series per stage cohort, x=year index, y=median ARR ($M)
            stage_groups: Dict[str, List[float]] = {}
            for c in companies:
                stage = (c.get("stage") or "Unknown").replace("-", " ").title()
                rev = ensure_numeric(c.get("revenue") or c.get("inferred_revenue"), 0) / 1e6
                stage_groups.setdefault(stage, []).append(rev)

            rev_proj = data.get("revenue_projections") or {}
            # Build a 4-year forward projection per cohort using median growth
            COHORT_GROWTH = {"Seed": 2.5, "Pre Seed": 3.0, "Series A": 1.8, "Series B": 1.3, "Series C": 1.0}
            labels = [f"Y{i}" for i in range(5)]
            datasets = []
            COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]
            for idx, (stage, revs) in enumerate(sorted(stage_groups.items())):
                median_rev = sorted(revs)[len(revs) // 2] if revs else 0
                growth = COHORT_GROWTH.get(stage, 1.2)
                yearly = [round(median_rev * (growth ** yr), 2) for yr in range(5)]
                datasets.append({
                    "label": stage,
                    "data": yearly,
                    "borderColor": COLORS[idx % len(COLORS)],
                    "backgroundColor": COLORS[idx % len(COLORS)] + "33",
                })
            if datasets:
                return {
                    "type": "line",
                    "data": {"labels": labels, "datasets": datasets},
                    "title": heading,
                    "renderType": "tableau",
                }

        elif chart_type == "fund_return_waterfall_chart":
            # Waterfall: one bar per company showing base-case proceeds ($M)
            portfolio_analysis = data.get("portfolio_analysis") or {}
            scenario_analysis = data.get("scenario_analysis") or {}

            items = []
            # Prefer pre-computed portfolio_analysis company data
            company_returns = (portfolio_analysis.get("company_returns") or {})
            for c in sorted(companies, key=lambda x: ensure_numeric(
                (company_returns.get(x.get("company", "")) or {}).get("base_proceeds", 0),
            ), reverse=True)[:12]:
                name = c.get("company", "Unknown")
                cr = company_returns.get(name) or {}
                proceeds = ensure_numeric(cr.get("base_proceeds"), 0) / 1e6

                # Fallback: synthesize from scenario_analysis
                if proceeds == 0 and name in scenario_analysis:
                    sc_list = (scenario_analysis[name].get("scenarios") or [])
                    base_sc = next(
                        (s for s in sc_list if "base" in (s.get("scenario") or s.get("name") or "").lower()),
                        sc_list[0] if sc_list else None,
                    )
                    if base_sc:
                        exit_val = ensure_numeric(base_sc.get("exit_value"), 0)
                        ownership = ensure_numeric(c.get("our_ownership_pct") or c.get("ownership_pct"), 0.08)
                        proceeds = exit_val * ownership / 1e6

                # Final fallback: estimate from valuation × 3x step-up × ownership
                if proceeds == 0:
                    val = ensure_numeric(c.get("valuation") or c.get("inferred_valuation"), 0)
                    ownership = ensure_numeric(c.get("our_ownership_pct") or c.get("ownership_pct"), 0.08)
                    proceeds = val * 3.0 * ownership / 1e6

                if proceeds > 0:
                    items.append({
                        "label": name,
                        "value": round(proceeds, 2),
                        "type": "positive",
                    })

            if items:
                return format_waterfall_chart(items, title=heading)

        elif chart_type == "pie":
            # Cap table ownership pie — prefer real cap_table_history, fall back to stage-based estimate
            cap_history = data.get("cap_table_history") or {}

            # Strategy 1: real ownership_summary or current_cap_table from cap table service
            if isinstance(cap_history, dict):
                for name, ch in cap_history.items():
                    if not isinstance(ch, dict):
                        continue
                    # Prefer ownership_summary (pre-computed buckets)
                    summary = ch.get("ownership_summary")
                    if isinstance(summary, dict):
                        labels = []
                        values = []
                        founders = summary.get("founders_total", 0)
                        employees = summary.get("employees_total", 0)
                        if founders > 0:
                            labels.append("Founders")
                            values.append(round(founders, 1))
                        if employees > 0:
                            labels.append("Employees/ESOP")
                            values.append(round(employees, 1))
                        for inv in (summary.get("investor_breakdown") or []):
                            inv_name = inv.get("name", "Investor")
                            inv_own = ensure_numeric(inv.get("ownership"), 0)
                            if inv_own > 0.5:
                                labels.append(inv_name)
                                values.append(round(inv_own, 1))
                        if labels and values:
                            return format_pie_chart(labels, values, title=f"{name} — Ownership")

                    # Fallback: current_cap_table (raw stakeholder → pct dict)
                    current = ch.get("current_cap_table")
                    if isinstance(current, dict) and current:
                        labels = list(current.keys())
                        values = [round(ensure_numeric(v, 0), 1) for v in current.values()]
                        if any(v > 0 for v in values):
                            return format_pie_chart(labels, values, title=f"{name} — Ownership")

            # Strategy 2: synthesize from company stage data
            if companies:
                for c in companies:
                    name = c.get("company", c.get("name", "Company"))
                    stage = (c.get("stage") or "").lower()
                    # Stage-based typical ownership splits
                    if "seed" in stage or "pre" in stage:
                        labels = ["Founders", "ESOP", "Seed Investors"]
                        values = [70.0, 10.0, 20.0]
                    elif "series a" in stage:
                        labels = ["Founders", "ESOP", "Seed Investors", "Series A"]
                        values = [45.0, 12.0, 13.0, 30.0]
                    elif "series b" in stage:
                        labels = ["Founders", "ESOP", "Seed", "Series A", "Series B"]
                        values = [30.0, 12.0, 8.0, 22.0, 28.0]
                    elif "series c" in stage or "growth" in stage or "late" in stage:
                        labels = ["Founders", "ESOP", "Early Investors", "Series B", "Series C+"]
                        values = [20.0, 10.0, 18.0, 20.0, 32.0]
                    else:
                        labels = ["Founders", "ESOP", "Investors"]
                        values = [50.0, 10.0, 40.0]
                    return format_pie_chart(labels, values, title=f"{name} — Estimated Ownership")

        logger.info("[MEMO] No chart data for type=%s, available_keys=%s", chart_type, list(data.keys()))
        return None

    @staticmethod
    def _build_revenue_decay_chart(cds, data: Dict, companies: List[Dict]) -> Optional[Dict]:
        """Build revenue forecast decay chart from enriched revenue_projections.

        Uses yearly decay data populated by RevenueProjectionService in
        _populate_memo_service_data().  Falls back to first company's data
        if projections exist, or returns None.
        """
        rev_proj = data.get("revenue_projections") or {}
        if not rev_proj:
            return None

        # Try to build a multi-company overlay chart
        from app.services.chart_data_service import format_line_chart
        all_labels = None
        datasets = []
        COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]

        for idx, (company_name, rp) in enumerate(rev_proj.items()):
            if not isinstance(rp, dict):
                continue
            yearly = rp.get("yearly", [])
            if not yearly:
                continue
            labels = [str(p.get("year", i + 1)) for i, p in enumerate(yearly)]
            if all_labels is None:
                all_labels = labels
            revenues = [round(ensure_numeric(p.get("revenue"), 0) / 1e6, 2) for p in yearly]
            datasets.append({
                "label": company_name,
                "data": revenues,
                "borderColor": COLORS[idx % len(COLORS)],
                "backgroundColor": COLORS[idx % len(COLORS)] + "22",
                "fill": idx == 0,
                "tension": 0.3,
            })

        if datasets and all_labels:
            return format_line_chart(
                labels=all_labels,
                datasets=datasets,
                title="Revenue Forecast with Growth Decay",
            )

        # Single company fallback via CDS
        for company_name, rp in rev_proj.items():
            if isinstance(rp, dict):
                yearly = rp.get("yearly", [])
                if yearly:
                    return cds.generate_revenue_forecast(yearly, company_name=company_name)
        return None

    def _synthesize_dpi_sankey(
        self, investments: List[Dict], fund_metrics: Dict, title: str
    ) -> Optional[Dict[str, Any]]:
        """Synthesize DPI Sankey from fund_metrics.investments list.

        Flow: Fund → Companies → Exits/Unrealized → LP Distributions
        """
        nodes = [{"id": "fund", "label": "Fund"}]
        links = []
        total_invested = 0
        total_realized = 0
        total_unrealized = 0

        for inv in investments:
            name = inv.get("company_name") or inv.get("name", "Unknown")
            node_id = f"co_{name.lower().replace(' ', '_')[:20]}"
            invested = ensure_numeric(inv.get("invested") or inv.get("cost_basis"), 0)
            nav = ensure_numeric(inv.get("nav_contribution") or inv.get("current_nav") or inv.get("fair_value"), 0)
            realized = ensure_numeric(inv.get("realized") or inv.get("distributions"), 0)
            unrealized = nav if nav > 0 else invested  # fallback

            if invested <= 0:
                continue

            nodes.append({"id": node_id, "label": name})
            links.append({"source": "fund", "target": node_id, "value": invested})
            total_invested += invested

            if realized > 0:
                links.append({"source": node_id, "target": "realized", "value": realized})
                total_realized += realized
            if unrealized > 0:
                links.append({"source": node_id, "target": "unrealized", "value": unrealized})
                total_unrealized += unrealized

        if not links:
            return None

        # Add terminal nodes
        if total_realized > 0:
            nodes.append({"id": "realized", "label": "Realized Exits"})
            nodes.append({"id": "lp_dist", "label": "LP Distributions"})
            links.append({"source": "realized", "target": "lp_dist", "value": total_realized})
        if total_unrealized > 0:
            nodes.append({"id": "unrealized", "label": "Unrealized NAV"})

        return format_sankey_chart(nodes, links, title=title)

    def _synthesize_dpi_sankey_from_companies(
        self, companies: List[Dict], fund_metrics: Dict, title: str
    ) -> Optional[Dict[str, Any]]:
        """Fallback DPI Sankey synthesis from companies list with estimated ownership."""
        fund_size = ensure_numeric(
            (fund_metrics.get("metrics") or fund_metrics).get("total_committed")
            or (fund_metrics.get("metrics") or fund_metrics).get("fund_size"),
            0,
        )
        nodes = [{"id": "fund", "label": "Fund"}]
        links = []
        total_deployed = 0

        for c in companies[:15]:
            name = c.get("company", c.get("name", "Unknown"))
            node_id = f"co_{name.lower().replace(' ', '_')[:20]}"
            funding = ensure_numeric(c.get("total_funding"), 0)
            valuation = ensure_numeric(c.get("valuation"), 0)

            # Estimate our investment: ~10% of total funding or proportional to fund size
            est_invested = funding * 0.1 if funding > 0 else (fund_size * 0.05 if fund_size > 0 else 0)
            if est_invested <= 0:
                continue

            nodes.append({"id": node_id, "label": name})
            links.append({"source": "fund", "target": node_id, "value": est_invested})
            total_deployed += est_invested

            # Estimate current value
            if valuation > 0 and funding > 0:
                est_nav = est_invested * (valuation / funding)
            else:
                est_nav = est_invested
            links.append({"source": node_id, "target": "unrealized", "value": est_nav})

        if not links:
            return None

        nodes.append({"id": "unrealized", "label": "Unrealized NAV"})
        est_title = title if "(Estimated)" in title else f"{title} (Estimated)"
        return format_sankey_chart(nodes, links, title=est_title)

    def _build_section_fallback(
        self, section_def: Dict[str, Any], companies: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Build a fund-level fallback when the LLM produces no narrative.

        By this point the gap-filler has run — every company has revenue,
        valuation, and growth (actual or stage-benchmark estimate).  This
        method aggregates those into rough fund-level metrics: NAV, TVPI,
        implied IRR, portfolio ARR.  The heading stays alive so any
        adjacent chart slot still renders.
        """
        if not companies:
            return None

        key = section_def.get("key", "")
        n = len(companies)

        # ── Fund context for ownership / deployed estimates ──────────
        fund_ctx = self.shared_data.get("fund_context", {})
        fund_size = ensure_numeric(
            fund_ctx.get("fund_size") or fund_ctx.get("total_committed")
        ) or 0
        avg_check = ensure_numeric(fund_ctx.get("avg_check_size")) or 0
        if not avg_check and fund_size:
            avg_check = (fund_size / max(n, 1)) * 0.6

        # ── Aggregate all companies (actual + estimated) ─────────────
        stages: Dict[str, int] = {}
        sectors: Dict[str, int] = {}
        total_rev = 0.0
        total_val = 0.0
        total_funding = 0.0
        total_nav = 0.0
        est_count = 0
        actual_count = 0
        growth_rates: List[float] = []

        for c in companies:
            st = c.get("stage", "Unknown")
            stages[st] = stages.get(st, 0) + 1
            sec = c.get("sector") or c.get("industry") or ""
            if sec:
                sectors[sec] = sectors.get(sec, 0) + 1

            rev = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue")) or 0
            val = ensure_numeric(c.get("valuation")) or ensure_numeric(c.get("inferred_valuation")) or 0
            funding = ensure_numeric(c.get("total_funding")) or 0

            total_rev += rev
            total_val += val
            total_funding += funding

            if c.get("_revenue_estimated") or c.get("_valuation_estimated") or c.get("_revenue_is_estimated") or c.get("_valuation_is_estimated"):
                est_count += 1
            else:
                actual_count += 1

            # Rough per-co NAV: our check × markup from entry
            if val > 0 and funding > 0:
                ownership = min((avg_check / funding) if avg_check else 0.10, 0.30)
                total_nav += val * ownership
            elif val > 0:
                total_nav += val * 0.10

            gr = c.get("revenue_growth")
            if gr and isinstance(gr, (int, float)):
                growth_rates.append(gr)

        total_deployed = total_funding if total_funding > 0 else (avg_check * n if avg_check else 0)
        median_growth = sorted(growth_rates)[len(growth_rates) // 2] if growth_rates else None

        # ── Fund-level metrics ───────────────────────────────────────
        tvpi = total_nav / total_deployed if total_nav > 0 and total_deployed > 0 else None
        irr = None
        if tvpi and tvpi > 0:
            irr = (tvpi ** (1.0 / 3.0) - 1.0) * 100  # ~3yr avg hold assumption

        est_tag = " [includes estimates]" if est_count > 0 else ""

        # ── Build paragraph ──────────────────────────────────────────
        parts: List[str] = []

        # Shape
        if stages:
            top = sorted(stages.items(), key=lambda x: -x[1])[:4]
            parts.append(
                f"**{n} companies** — "
                + ", ".join(f"{s} ({ct})" for s, ct in top) + "."
            )
        if sectors and len(sectors) > 1:
            top_sec = sorted(sectors.items(), key=lambda x: -x[1])[:3]
            parts.append("Sectors: " + ", ".join(f"{s} ({ct})" for s, ct in top_sec) + ".")

        # Fund metrics
        metrics = []
        if total_nav > 0:
            metrics.append(f"Portfolio NAV: ~${total_nav / 1e6:,.0f}M{est_tag}")
        if tvpi is not None:
            metrics.append(f"TVPI: ~{tvpi:.1f}x")
        if irr is not None:
            metrics.append(f"Implied IRR: ~{irr:.0f}%")
        if total_rev > 0:
            metrics.append(f"Portfolio ARR: ~${total_rev / 1e6:,.0f}M")
        if total_deployed > 0:
            metrics.append(f"Deployed: ~${total_deployed / 1e6:,.0f}M")
        if median_growth is not None:
            metrics.append(f"Median growth: ~{median_growth * 100:.0f}%")
        if metrics:
            parts.append(" | ".join(metrics) + ".")

        if est_count > 0:
            parts.append(
                f"*{actual_count} reported, {est_count} stage-benchmarked.*"
            )

        if not parts:
            parts.append(f"Portfolio of {n} companies — run enrichment for detailed analysis.")

        return {"type": "paragraph", "content": "\n\n".join(parts)}

    @staticmethod
    def _format_metric_value(v, fmt):
        """Format a single metric value for table display."""
        if v is None or v == 0:
            return "—"
        if fmt == "dollar":
            return f"${v / 1e9:,.1f}B" if abs(v) >= 1e9 else f"${v / 1e6:,.1f}M"
        elif fmt == "pct":
            return f"{v:.1f}%"
        elif fmt == "multiple":
            return f"{v:.1f}x"
        return f"{v:,.1f}"

    @staticmethod
    def _format_return_metric(name, v):
        """Format a return metric value based on the metric name."""
        if v is None or v == 0:
            return "—"
        name_lower = name.lower()
        if "irr" in name_lower or "yield" in name_lower:
            return f"{v * 100:.1f}%" if abs(v) < 1 else f"{v:.1f}%"
        elif "moic" in name_lower or "multiple" in name_lower:
            return f"{v:.2f}x"
        elif "value" in name_lower or "equity" in name_lower:
            return f"${v / 1e9:,.1f}B" if abs(v) >= 1e9 else f"${v / 1e6:,.1f}M"
        elif "year" in name_lower:
            return str(int(v))
        return f"{v:,.2f}"

    def _build_metrics(
        self, section_def: Dict, data: Dict, companies: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Build data-driven metrics sections (lists, tables)."""
        sections: List[Dict[str, Any]] = []
        data_keys = section_def.get("data_keys", [])
        key = section_def["key"]

        # ── PE model data — adaptive metrics from flexible schema ──────
        if "pe_model_data" in data_keys:
            pe_data = data.get("pe_model_data") or {}

            if key == "historical_performance":
                # Operating model table: periods as columns, metrics as rows
                om = pe_data.get("operating_model") or {}
                periods = om.get("periods") or []
                metrics = om.get("metrics") or {}
                if periods and metrics:
                    headers = ["Metric"] + [str(p) for p in periods]
                    rows = []
                    for metric_name, metric_data in metrics.items():
                        if not isinstance(metric_data, dict):
                            continue
                        values = metric_data.get("values") or []
                        fmt = metric_data.get("format", "number")
                        row = [metric_name] + [self._format_metric_value(v, fmt) for v in values]
                        while len(row) < len(headers):
                            row.append("—")
                        rows.append(row)
                    if rows:
                        sections.append({"type": "table", "table": {"headers": headers, "rows": rows}})

            elif key == "capital_structure":
                # Instruments table: one row per instrument
                instruments = pe_data.get("instruments") or []
                if instruments:
                    # Collect unique term keys across all instruments (up to 4 most common)
                    term_freq: Dict[str, int] = {}
                    for inst in instruments:
                        for k2 in (inst.get("terms") or {}):
                            if not k2.startswith("_"):
                                term_freq[k2] = term_freq.get(k2, 0) + 1
                    term_cols = sorted(term_freq, key=lambda x: term_freq[x], reverse=True)[:4]

                    headers = ["Instrument", "Type", "Amount"] + [tc.replace("_", " ").title() for tc in term_cols]
                    rows = []
                    for inst in instruments:
                        row = [
                            inst.get("name", "—"),
                            inst.get("type", "—").replace("_", " ").title(),
                            self._format_metric_value(inst.get("amount", 0), "dollar"),
                        ]
                        terms = inst.get("terms") or {}
                        for tc in term_cols:
                            row.append(str(terms.get(tc, "—")))
                        rows.append(row)
                    sections.append({"type": "table", "table": {"headers": headers, "rows": rows}})

            elif key == "returns_analysis":
                # Returns scenario table: scenarios as columns, metrics as rows
                returns = pe_data.get("returns") or {}
                scenarios = returns.get("scenarios") or {}
                if scenarios:
                    all_metrics: List[str] = []
                    for sc_data in scenarios.values():
                        if isinstance(sc_data, dict):
                            for k2 in sc_data:
                                if k2 not in all_metrics:
                                    all_metrics.append(k2)

                    scenario_names = list(scenarios.keys())
                    headers = ["Metric"] + [n.replace("_", " ").title() for n in scenario_names]
                    rows = []
                    for metric in all_metrics:
                        row = [metric.replace("_", " ").title()]
                        for sc_name in scenario_names:
                            sc = scenarios.get(sc_name) or {}
                            row.append(self._format_return_metric(metric, sc.get(metric, 0)))
                        rows.append(row)
                    if rows:
                        sections.append({"type": "table", "table": {"headers": headers, "rows": rows}})

        # Company metrics — use table for multi-company, list for single
        if "companies" in data_keys and companies:
            if len(companies) >= 2:
                # Multi-company comparison table — emit as structured table
                company_names = [c.get("company", "Unknown") for c in companies[:6]]
                table_headers = ["Metric"] + company_names
                metric_defs = {
                    "Stage": [],
                    "Valuation": [],
                    "Revenue (ARR)": [],
                    "Rev Multiple": [],
                    "Total Funding": [],
                    "Growth": [],
                    "Team Size": [],
                    "Gross Margin": [],
                    "Capital Efficiency": [],
                }
                for c in companies[:6]:
                    val = ensure_numeric(c.get("valuation"))
                    rev = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue"))
                    funding = ensure_numeric(c.get("total_funding"))
                    growth = c.get("revenue_growth")
                    gm = (c.get("key_metrics") or {}).get("gross_margin")
                    rev_mult = val / rev if val and rev and rev > 0 else 0
                    cap_eff = rev / funding if rev and funding and funding > 0 else 0

                    metric_defs["Stage"].append(c.get("stage", "—"))
                    metric_defs["Valuation"].append(f"${val / 1e6:,.0f}M" if val else "—")
                    metric_defs["Revenue (ARR)"].append(f"${rev / 1e6:,.1f}M" if rev else "—")
                    metric_defs["Rev Multiple"].append(f"{rev_mult:.1f}x" if rev_mult else "—")
                    metric_defs["Total Funding"].append(f"${funding / 1e6:,.0f}M" if funding else "—")
                    metric_defs["Growth"].append(f"{growth * 100:.0f}%" if growth and isinstance(growth, (int, float)) else "—")
                    metric_defs["Team Size"].append(str(c.get("team_size", "—")))
                    metric_defs["Gross Margin"].append(f"{gm * 100:.0f}%" if gm and isinstance(gm, (int, float)) else "—")
                    metric_defs["Capital Efficiency"].append(f"{cap_eff:.2f}x" if cap_eff else "—")

                table_rows = []
                for metric, vals in metric_defs.items():
                    if all(v == "—" for v in vals):
                        continue
                    table_rows.append([metric] + vals)

                if table_rows:
                    sections.append({
                        "type": "table",
                        "table": {"headers": table_headers, "rows": table_rows},
                    })
            else:
                # Single company — detailed list
                for c in companies:
                    name = c.get("company", "Unknown")
                    items = []
                    val = ensure_numeric(c.get("valuation"))
                    rev = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue"))
                    stage = c.get("stage", "Unknown")
                    funding = ensure_numeric(c.get("total_funding"))
                    rev_mult = val / rev if val and rev and rev > 0 else 0
                    cap_eff = rev / funding if rev and funding and funding > 0 else 0

                    overview = f"**{name}** — {stage}"
                    if val:
                        overview += f" | ${val / 1e6:,.1f}M valuation"
                    if rev:
                        overview += f" | ${rev / 1e6:,.1f}M ARR"
                    if rev_mult:
                        overview += f" | {rev_mult:.1f}x revenue multiple"
                    items.append(overview)

                    if funding:
                        items.append(f"Total Funding: ${funding / 1e6:,.1f}M")
                    if cap_eff:
                        items.append(f"Capital Efficiency: {cap_eff:.2f}x (ARR / Funding)")
                    if c.get("team_size"):
                        items.append(f"Team: {c['team_size']}")
                    growth = c.get("revenue_growth")
                    if growth and isinstance(growth, (int, float)):
                        items.append(f"Growth: {growth * 100:.0f}% YoY")
                    gm = (c.get("key_metrics") or {}).get("gross_margin")
                    if gm and isinstance(gm, (int, float)):
                        items.append(f"Gross Margin: {gm * 100:.0f}%")
                    burn = ensure_numeric(c.get("monthly_burn"))
                    if burn:
                        items.append(f"Monthly Burn: ${burn / 1e6:,.2f}M")
                    runway = ensure_numeric(c.get("runway_months"))
                    if runway:
                        items.append(f"Runway: {runway:.0f} months")

                    if items:
                        sections.append({"type": "list", "items": items})

        # Follow-on metrics
        if "followon_strategy" in data_keys:
            fo_data = data.get("followon_strategy", {})
            if isinstance(fo_data, dict):
                for cid, fo in fo_data.items():
                    if not isinstance(fo, dict):
                        continue
                    name = fo.get("company_name", cid)
                    items = [f"**{name}**"]
                    if fo.get("our_invested"):
                        items.append(f"Our Investment: ${fo['our_invested'] / 1e6:,.1f}M")
                    if fo.get("current_ownership_pct"):
                        items.append(f"Current Ownership: {fo['current_ownership_pct']:.1f}%")
                    if fo.get("pro_rata_amount"):
                        items.append(f"Pro-Rata: ${fo['pro_rata_amount'] / 1e6:,.1f}M")
                    if fo.get("ownership_with_followon"):
                        items.append(f"With Follow-On: {fo['ownership_with_followon']:.1f}%")
                    if fo.get("ownership_without_followon"):
                        items.append(f"Without: {fo['ownership_without_followon']:.1f}%")
                    if fo.get("recommendation"):
                        items.append(f"**Recommendation: {fo['recommendation']}**")
                    if len(items) > 1:
                        sections.append({"type": "list", "items": items})

        # Fund metrics
        if "fund_metrics" in data_keys:
            fm = data.get("fund_metrics", {})
            perf = fm.get("metrics", fm) if isinstance(fm, dict) else {}
            items = []
            if perf.get("total_committed"):
                items.append(f"Fund Size: ${perf['total_committed'] / 1e6:,.0f}M")
            if perf.get("total_invested"):
                items.append(f"Invested: ${perf['total_invested'] / 1e6:,.0f}M")
            if perf.get("total_nav"):
                items.append(f"NAV: ${perf['total_nav'] / 1e6:,.0f}M")
            if perf.get("tvpi"):
                items.append(f"TVPI: {perf['tvpi']:.2f}x")
            if perf.get("dpi"):
                items.append(f"DPI: {perf['dpi']:.2f}x")
            if perf.get("irr"):
                items.append(f"IRR: {perf['irr']:.1f}%")
            if items:
                sections.append({"type": "list", "items": items})

        # Fund context
        if "fund_context" in data_keys and "fund_metrics" not in data_keys:
            fc = data.get("fund_context", {})
            items = []
            if fc.get("fund_size"):
                items.append(f"Fund Size: ${fc['fund_size'] / 1e6:,.0f}M")
            if fc.get("remaining_capital"):
                items.append(f"Remaining: ${fc['remaining_capital'] / 1e6:,.0f}M")
            if items:
                sections.append({"type": "list", "items": items})

        # Portfolio health
        if "portfolio_health" in data_keys:
            ph = data.get("portfolio_health", {})
            analytics = ph.get("company_analytics", {})
            if isinstance(analytics, dict):
                items = []
                for cid, a in list(analytics.items())[:8]:
                    name = a.get("company_name", cid)
                    arr = a.get("current_arr", 0)
                    growth = a.get("growth_rate", 0)
                    runway = a.get("estimated_runway_months", 0)
                    items.append(
                        f"**{name}**: ${arr / 1e6:,.1f}M ARR, "
                        f"{growth * 100:.0f}% growth, {runway:.0f}mo runway"
                    )
                if items:
                    sections.append({"type": "list", "items": items})

        # Scenario analysis metrics
        if "scenario_analysis" in data_keys:
            sc = data.get("scenario_analysis", {})
            if isinstance(sc, dict):
                for name, sc_data in sc.items():
                    if isinstance(sc_data, dict) and sc_data.get("scenarios"):
                        items = [f"**{name} Exit Scenarios**:"]
                        for s in sc_data["scenarios"][:5]:
                            s_name = s.get("name", s.get("scenario_name", "Scenario"))
                            prob = s.get("probability", 0)
                            items.append(f"  {s_name}: {prob * 100:.0f}% probability")
                        sections.append({"type": "list", "items": items})

        return sections

    def _build_context_snapshot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build machine-readable context snapshot for plan memos."""
        snapshot: Dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "data_keys_present": list(data.keys()),
        }

        # Serialize company summaries (compact)
        companies = data.get("companies", [])
        if companies:
            snapshot["companies"] = [
                {
                    "name": c.get("company"),
                    "stage": c.get("stage"),
                    "valuation": c.get("valuation"),
                    "revenue": c.get("revenue") or c.get("inferred_revenue"),
                    "total_funding": c.get("total_funding"),
                }
                for c in companies
            ]

        fund_ctx = data.get("fund_context", {})
        if fund_ctx:
            snapshot["fund_context"] = {
                k: fund_ctx[k] for k in ("fund_name", "fund_size", "fund_id", "remaining_capital")
                if k in fund_ctx
            }

        # Compact fund metrics
        fm = data.get("fund_metrics", {})
        if fm:
            perf = fm.get("metrics", fm)
            snapshot["fund_metrics"] = {
                k: perf.get(k) for k in ("tvpi", "dpi", "irr", "total_nav")
                if perf.get(k) is not None
            }

        # Preserve analysis artifacts for chart generation on resume
        for key in ("cap_table_history", "scenario_analysis", "revenue_projections", "followon_strategy", "portfolio_health"):
            val = data.get(key)
            if val:
                snapshot[key] = val

        return snapshot

    # ------------------------------------------------------------------
    # Plan Persistence: save / load / hydrate via processed_documents
    # ------------------------------------------------------------------

    @staticmethod
    def save_to_documents(
        memo: Dict[str, Any],
        document_repo,
    ) -> Optional[Dict[str, Any]]:
        """Persist a memo to the processed_documents table.

        Uses document_type = "plan_memo" for resumable plans,
        "generated_memo" for explicitly saved memos.

        Returns the inserted row dict or None on failure.
        """
        if document_repo is None:
            logger.warning("[MEMO] No document_repo available — skipping save")
            return None

        is_plan = memo.get("is_resumable", False)
        doc_type = "plan_memo" if is_plan else "generated_memo"

        payload = {
            "document_type": doc_type,
            "status": "completed",
            "extracted_data": memo.get("sections", []),
            "processing_summary": {
                "memo_type": memo.get("memo_type"),
                "title": memo.get("title"),
                "metadata": memo.get("metadata", {}),
            },
        }

        try:
            row = document_repo.insert(payload)
            logger.info(
                "[MEMO] Saved %s '%s' → id=%s",
                doc_type,
                memo.get("title", "Untitled"),
                row.get("id"),
            )
            return row
        except Exception as e:
            logger.error("[MEMO] Failed to save memo: %s", e, exc_info=True)
            return None

    @staticmethod
    def load_recent_plans(
        document_repo,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Load recent plan memos for session resumption.

        Returns list of compact dicts: {id, title, memo_type, generated_at, context_snapshot}.
        """
        if document_repo is None:
            return []

        try:
            rows = document_repo.list_(
                filters={"document_type": "plan_memo", "status": "completed"},
                limit=limit,
            )
            plans: List[Dict[str, Any]] = []
            for row in rows:
                summary = row.get("processing_summary") or {}
                metadata = summary.get("metadata") or {}
                sections = row.get("extracted_data") or []

                # Extract context_snapshot from the last "code" section (context type)
                context_snapshot: Dict[str, Any] = {}
                for sec in reversed(sections):
                    if sec.get("type") == "code":
                        try:
                            context_snapshot = json.loads(sec.get("content", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            pass
                        break

                plans.append({
                    "id": row.get("id"),
                    "title": summary.get("title", "Untitled Plan"),
                    "memo_type": summary.get("memo_type", "plan_memo"),
                    "generated_at": metadata.get("generated_at", row.get("processed_at")),
                    "context_snapshot": context_snapshot,
                })
            return plans
        except Exception as e:
            logger.error("[MEMO] Failed to load plans: %s", e, exc_info=True)
            return []

    @staticmethod
    def hydrate_shared_data(
        plan_doc: Dict[str, Any],
        shared_data: Dict[str, Any],
    ) -> None:
        """Restore shared_data from a plan's context_snapshot. No LLM calls."""
        snapshot = plan_doc.get("context_snapshot", {})
        if not snapshot:
            return

        restorable_keys = [
            "companies", "fund_context", "fund_metrics", "portfolio_health",
            "cap_table_history", "scenario_analysis", "revenue_projections", "followon_strategy",
        ]
        for key in restorable_keys:
            if key in snapshot and snapshot[key]:
                shared_data[key] = snapshot[key]

        logger.info(
            "[MEMO] Hydrated shared_data from plan: keys=%s",
            [k for k in restorable_keys if k in snapshot and snapshot[k]],
        )

    @staticmethod
    def _safe_num(val) -> float:
        """Extract numeric value, handling InferenceResult objects."""
        if val is None:
            return 0
        if hasattr(val, "value"):
            return val.value if val.value is not None else 0
        if isinstance(val, (int, float)):
            return val
        return 0
