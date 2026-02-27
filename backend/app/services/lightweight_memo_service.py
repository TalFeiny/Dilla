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
        data_summary = self._summarize_data(available_data)

        # Build section prompts
        section_prompts = []
        narrative_keys = []
        for s in sections:
            if s["type"] in ("narrative", "metrics"):
                narrative_keys.append(s["key"])
                section_prompts.append(
                    f"### {s['heading']}\n"
                    f"Instructions: {s['prompt_hint']}\n"
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

        system_prompt = (
            "You are a senior investment analyst at a top-tier venture capital fund. "
            "Write with authority and precision — this memo drives multi-million dollar decisions. "
            f"{fund_size_str}"
            f"{company_str}"
            "\n\nFORMAT RULES — match format to data density:\n"
            f"{'1. PORTFOLIO MODE (' + str(num_companies) + ' companies): Lead with a summary TABLE showing ALL companies (Company | Stage | Sector | ARR | Valuation | Data Quality). Follow with prose commentary on patterns, themes, and outliers. Use tables for any section covering 4+ companies.' if is_portfolio else '1. DEEP-DIVE MODE: Use 3-5 dense paragraphs per section (150-400 words). Weave numbers into flowing prose with context and significance.'}\n"
            "2. NEVER skip a company because data is sparse. Show what you have:\n"
            "   - Real data: bold, cited ('$14.8M ARR, company-reported')\n"
            "   - Estimated data: labeled ('[Est: $5M ARR based on Series A benchmarks]')\n"
            "   - Unknown: '—' in tables, noted in prose as 'data pending'\n"
            "3. For portfolio analysis, lead with the BIG PICTURE before individual companies:\n"
            "   - Stage distribution, sector concentration, total capital deployed\n"
            "   - Themes and clusters (e.g., '6 of 22 are AI infrastructure')\n"
            "   - Outliers, top performers, and gaps\n"
            "4. Every section MUST have substance. If per-company data is sparse, analyze portfolio-level patterns instead.\n"
            "   A 'Financial Overview' with only 2 data-rich companies should STILL cover all — show a table, note what's known, flag what's missing.\n"
            "5. Use markdown tables for ALL structured comparisons of 3+ items.\n"
            "6. Cite key figures with source: 'per Pitchbook Q3 2024', 'company-reported', '[Est: stage benchmark]'.\n"
            "7. Lead each section with the MOST IMPORTANT finding. No filler, no preamble ('In this section...'), no hedging.\n"
            "8. For multi-company analysis: always compare and contrast — never describe companies in isolation.\n"
            "9. Calculate derived metrics where possible: revenue multiples, capital efficiency, implied burn rate.\n"
            "10. End each section with a clear takeaway or action item.\n"
            "\nSTRUCTURE RULES:\n"
            "- Bold (**text**) key metrics and company names on first mention.\n"
            "- Numbers: $XM for millions, $XB for billions, X% for percentages, Xx for multiples.\n"
            "- Separate each section with its exact ## heading as shown below. "
            "The headings are used to split your output — they MUST match exactly.\n"
            "- Within sections, use ### sub-headings, markdown tables, and bullet lists freely — "
            "they will be rendered as proper structured elements.\n"
            "- Do NOT use ---SECTION_BREAK--- delimiters.\n"
            "- For recommendations: state conviction level (High/Medium/Low) and check size."
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

            response = await asyncio.wait_for(
                self.model_router.get_completion(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    capability=ModelCapability.ANALYSIS,
                    max_tokens=12000,
                    temperature=0.25,
                    caller_context="lightweight_memo_narratives",
                ),
                timeout=90,  # 90s per LLM call — leaves headroom within the 120s outer timeout
            )

            raw_text = response.get("response", "") if isinstance(response, dict) else str(response)

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
        """Full 3-shot pipeline: detect → narratives + charts (parallel) → assemble.

        Returns docs-format dict ready for frontend rendering.
        """
        # Shot 1: Template selection + data audit
        template_id = self.detect_memo_type(prompt, memo_type)
        available_data, missing_req, missing_opt = self.audit_data(template_id)

        if missing_req:
            logger.warning(
                f"[MEMO] Template {template_id} missing required data: {missing_req}. "
                f"Proceeding with available data."
            )

        # Estimation fallback: ensure every company has revenue, valuation, growth
        # so charts and metrics never return empty due to missing fundamentals.
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
                # Revenue
                rev = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue"))
                if not rev:
                    c["revenue"] = bench["revenue"]
                    c["_revenue_estimated"] = True
                # Valuation
                val = ensure_numeric(c.get("valuation"))
                if not val:
                    c["valuation"] = bench["valuation"]
                    c["_valuation_estimated"] = True
                # Growth rate
                growth = c.get("revenue_growth")
                if not growth or not isinstance(growth, (int, float)):
                    c["revenue_growth"] = bench["growth"]
                    c["_growth_estimated"] = True

        # Shot 2: Generate narratives (LLM) + pre-build charts (CPU) IN PARALLEL
        _t0 = datetime.now()

        narrative_task = asyncio.ensure_future(
            self.generate_narratives(template_id, prompt, available_data)
        )
        loop = asyncio.get_running_loop()
        chart_task = loop.run_in_executor(
            None, self._prebuild_charts, template_id, available_data
        )

        narratives, prebuilt_charts = await asyncio.gather(narrative_task, chart_task)
        _elapsed = (datetime.now() - _t0).total_seconds()
        logger.info(f"[MEMO] Parallel narratives+charts took {_elapsed:.1f}s")

        # Validate narratives — if >50% are empty, retry with diagnostic hints
        # But only retry if the first call completed quickly enough (< 60s)
        # to avoid doubling an already-long wait.
        narrative_keys = [
            s["key"] for s in MEMO_TEMPLATES[template_id]["sections"]
            if s["type"] in ("narrative", "metrics")
        ]
        if narrative_keys and _elapsed < 60:
            empty_count = sum(1 for k in narrative_keys if not narratives.get(k, "").strip())
            if empty_count > len(narrative_keys) * 0.5:
                missing_sections = [k for k in narrative_keys if not narratives.get(k, "").strip()]
                logger.warning(
                    f"[MEMO] {empty_count}/{len(narrative_keys)} narrative sections empty — "
                    f"retrying with hint for: {missing_sections}"
                )
                retry_prompt = (
                    f"{prompt}\n\n"
                    f"IMPORTANT: The following sections were empty in a previous attempt and MUST be filled: "
                    f"{', '.join(missing_sections)}. "
                    f"Generate substantive content for ALL sections, especially these."
                )
                retry_narratives = await self.generate_narratives(template_id, retry_prompt, available_data)
                for k in narrative_keys:
                    if not narratives.get(k, "").strip() and retry_narratives.get(k, "").strip():
                        narratives[k] = retry_narratives[k]
        elif narrative_keys and _elapsed >= 60:
            logger.info(f"[MEMO] Skipping retry — first LLM call took {_elapsed:.1f}s")

        # Shot 3: Assemble final memo (no LLM) — use prebuilt charts
        memo = self.assemble_memo(
            template_id, prompt, narratives, available_data,
            prebuilt_charts=prebuilt_charts,
        )

        return memo

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
    def _parse_sections(raw_text: str, expected_count: int, section_headings: Optional[List[str]] = None) -> List[str]:
        """Parse LLM output into sections using multiple fallback strategies.

        Tries in order:
        1. Heading-match alignment (match known ## headings in output) — primary
        2. Markdown H2/H3 headings as generic splits
        3. Exact ---SECTION_BREAK--- delimiter (legacy fallback)
        4. Fuzzy regex for delimiter variations
        5. Triple-dash (---) splits
        6. Proportional text split so every section gets something
        """
        import re

        if not raw_text or expected_count <= 0:
            return [""] * expected_count

        # Strategy 1 (primary): heading-match alignment — find known section headings in output
        if section_headings and len(section_headings) >= expected_count:
            positions = []
            for heading in section_headings:
                # Match heading in markdown (## Heading or ### Heading) or bold (**Heading**)
                pattern = re.compile(
                    rf"(?:^|\n)\s*(?:#{2,4}\s+)?(?:\*\*)?{re.escape(heading)}(?:\*\*)?\s*\n",
                    re.IGNORECASE,
                )
                m = pattern.search(raw_text)
                if m:
                    positions.append(m.start())
                else:
                    positions.append(-1)

            # If we found at least 60% of headings, use them to split
            found = sum(1 for p in positions if p >= 0)
            if found >= expected_count * 0.6:
                # Sort positions and extract text between them
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

        # Strategy 2: split on whatever ## headings the LLM actually wrote.
        # Accept fewer parts than expected — pad with "" rather than
        # destroying text by forcing it into the wrong number of buckets.
        heading_splits = re.split(r"(?=\n#{2,3}\s+)", raw_text)
        # Filter out empty leading split
        heading_splits = [s for s in heading_splits if s.strip()]
        if heading_splits:
            # Pad to expected_count so callers don't index-error
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

        # Strategy 4 (last resort): return full text as first section.
        # Never chop text proportionally — that destroys content.
        result = [raw_text] + [""] * (expected_count - 1)
        return result

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
            is_inferred = not c.get("revenue") and c.get("inferred_revenue")
            label = "ARR [estimated]" if is_inferred else "ARR"
            fin_parts.append(f"{label}: ${revenue / 1e6:,.1f}M")
        if valuation > 0:
            is_inferred = not c.get("valuation") and c.get("inferred_valuation")
            label = "Valuation [estimated]" if is_inferred else "Valuation"
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
            gr_val = growth_rate * 100 if 0 < abs(growth_rate) < 1 else growth_rate
            derived.append(f"Growth: {gr_val:.0f}% YoY")
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

            if c.get("_revenue_estimated") or c.get("_valuation_estimated"):
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
            gr_pct = median_growth * 100 if 0 < abs(median_growth) < 10 else median_growth
            metrics.append(f"Median growth: ~{gr_pct:.0f}%")
        if metrics:
            parts.append(" | ".join(metrics) + ".")

        if est_count > 0:
            parts.append(
                f"*{actual_count} reported, {est_count} stage-benchmarked.*"
            )

        if not parts:
            parts.append(f"Portfolio of {n} companies — run enrichment for detailed analysis.")

        return {"type": "paragraph", "content": "\n\n".join(parts)}

    def _build_metrics(
        self, section_def: Dict, data: Dict, companies: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Build data-driven metrics sections (lists, tables)."""
        sections: List[Dict[str, Any]] = []
        data_keys = section_def.get("data_keys", [])
        key = section_def["key"]

        # Company metrics — use table for multi-company, list for single
        if "companies" in data_keys and companies:
            if len(companies) >= 2:
                # Multi-company comparison table
                header = "| Metric |"
                separator = "| --- |"
                rows = {
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
                    name = c.get("company", "Unknown")
                    header += f" **{name}** |"
                    separator += " --- |"
                    val = ensure_numeric(c.get("valuation"))
                    rev = ensure_numeric(c.get("revenue")) or ensure_numeric(c.get("inferred_revenue"))
                    funding = ensure_numeric(c.get("total_funding"))
                    growth = c.get("revenue_growth")
                    gm = (c.get("key_metrics") or {}).get("gross_margin")
                    rev_mult = val / rev if val and rev and rev > 0 else 0
                    cap_eff = rev / funding if rev and funding and funding > 0 else 0

                    rows["Stage"].append(c.get("stage", "—"))
                    rows["Valuation"].append(f"${val / 1e6:,.0f}M" if val else "—")
                    rows["Revenue (ARR)"].append(f"${rev / 1e6:,.1f}M" if rev else "—")
                    rows["Rev Multiple"].append(f"{rev_mult:.1f}x" if rev_mult else "—")
                    rows["Total Funding"].append(f"${funding / 1e6:,.0f}M" if funding else "—")
                    rows["Growth"].append(f"{growth * 100:.0f}%" if growth and isinstance(growth, (int, float)) else "—")
                    rows["Team Size"].append(str(c.get("team_size", "—")))
                    rows["Gross Margin"].append(f"{gm * 100:.0f}%" if gm and isinstance(gm, (int, float)) else "—")
                    rows["Capital Efficiency"].append(f"{cap_eff:.2f}x" if cap_eff else "—")

                table_lines = [header, separator]
                for metric, vals in rows.items():
                    # Skip rows where all values are "—"
                    if all(v == "—" for v in vals):
                        continue
                    row = f"| {metric} |"
                    for v in vals:
                        row += f" {v} |"
                    table_lines.append(row)

                if len(table_lines) > 3:  # header + separator + at least 1 data row
                    sections.append({"type": "paragraph", "content": "\n".join(table_lines)})
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
