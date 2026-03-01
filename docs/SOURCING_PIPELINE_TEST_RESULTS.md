# Sourcing Pipeline Test Results — March 1, 2026 (Run 2)

## TL;DR

After fixing the model router (SDK upgrade + error handling + capability routing), **LLM calls now work** — Claude is first in line and returning real structured JSON. But **0 web companies are extracted** because bulk extraction JSON gets truncated (max_tokens too low). DB results are garbage for 3 of 4 tests because the query builder doesn't map rubric sector/intent into Supabase filters.

**What's fixed:** Model router, client init, Claude routing, rubric classification, LLM decomposition.
**What's still broken:** Extraction (JSON truncation), DB filtering (no NL→SQL), grid persistence, scoring on DB-only results.

---

## What We Tested (Run 2 Results)

| Test Case | Thesis | Pattern-Match Intent | LLM Intent | LLM Sector |
|---|---|---|---|---|
| Healthcare Series A | "Series A healthcare technology companies building AI-powered diagnostics..." | `dealflow` | `dealflow` | Healthcare Technology |
| GTM Leads | "B2B SaaS companies building sales enablement, revenue intelligence..." | `dealflow` (wrong) | `gtm_leads` (correct) | B2B SaaS - Sales Enablement / Revenue Intelligence / CRM |
| Acquirer Search | "Private equity firms or strategic acquirers actively acquiring healthcare IT..." | `acquirer` | `acquirer` | Healthcare IT / Healthtech |
| Acquisition Targets | "Small to mid-size logistics and supply chain software companies..." | `dealflow` (wrong) | `dealflow` (wrong — should be acquisition target) | Logistics and Supply Chain Software |

---

## FIXED: Bug #1 — Model Router (was CRITICAL, now resolved)

**Three issues found and fixed:**

1. **OpenAI SDK v1.7.1 → v2.24.0 upgrade** — old SDK crashed on init (`proxies` TypeError) AND returned 0-char responses for gpt-5-mini with `max_completion_tokens` + `json_mode`. Both issues gone after upgrade.

2. **Outer except nuked all clients** — if any provider init threw, the handler reset `_clients_initialized = False` and set all clients to `None`. Changed to preserve successfully initialized clients and still mark `_clients_initialized = True`.

3. **`capability=ModelCapability.FAST` excluded Claude** — all 4 sourcing LLM calls used `FAST`, which filtered the model list to `['gpt-5-mini', 'mixtral-8x7b', 'gemini-pro', 'llama2-70b', 'llama-3-70b']`. Claude and gpt-5.2 don't have `FAST`. Changed to `STRUCTURED`. Model order is now `['claude-sonnet-4-5', 'gpt-5.2', 'gpt-5-mini']`.

**Status:** Claude now returns real JSON for rubric (1050 chars), decomposition (449 chars), and extraction (2308 chars before truncation).

---

## Bug #2: Bulk Extraction JSON Truncation (CRITICAL — blocks all web companies)

**File:** `backend/app/services/unified_mcp_orchestrator.py`

All 4 tests fail extraction with JSON parse errors:
```
bulk extraction round 1 failed: Unterminated string starting at: line 71 column 21 (char 2297)
bulk extraction round 1 failed: Unterminated string starting at: line 76 column 7 (char 2343)
bulk extraction round 1 failed: Unterminated string starting at: line 66 column 21 (char 2362)
bulk extraction round 1 failed: Expecting ',' delimiter: line 51 column 169 (char 2229)
```

Claude's JSON response is ~2300 chars when extracting company names from 10 Tavily search results. `max_tokens=800` (roughly 3200 chars) should be enough in theory, but the assistant prefill `{` and Claude's token-to-char ratio for JSON (lots of quotes, brackets) means it runs out.

**Fix applied:** Bumped `max_tokens` from 800→2000 (bulk) and 1000→2000 (rich). Needs re-test.

**Impact:** 0 web companies extracted across all 4 tests. The pipeline runs 10 Tavily queries, gets results, but can't parse them into company names.

---

## Bug #3: DB Query Builder Ignores Rubric Sector/Intent

**File:** DB query construction in the orchestrator/sourcing service

The Supabase queries generated:

| Test | Query URL Filters | DB Returned | Problem |
|---|---|---|---|
| Healthcare Series A | `stage.ilike.%Series A%` | 17 | Stage filter works, but NO sector filter — returns Provectus Algae (Data Infra), Arcee AI (AI/ML), Thea Energy (Environment) |
| GTM Leads | **none** | 100 | Zero filters. Returns alphabetical dump: Zopa, Zepz, Zapier |
| Acquirer Search | **none** | 100 | Zero filters. Same Zopa/Zepz/Zapier dump |
| Acquisition Targets | **none** | 100 | Zero filters. Same dump |

Tests 2-4 also hit: `DB query failed: unsupported format string passed to NoneType.__format__` — a string formatting bug where a None value is passed to an f-string or `.format()` call.

**Root cause:** The DB query builder only applies filters from explicit `filters` parameter (e.g. `{"stage": "Series A"}`). The rubric's `sector` field from LLM classification is never mapped into a Supabase `sector.ilike` clause. For queries with no explicit stage (GTM, acquirer), there are zero filters.

**What needs to happen:**
- Extract sector from rubric → map to `sector.ilike.%{sector}%` Supabase filter
- Extract stage from rubric → map to `stage.ilike.%{stage}%`
- Fix the NoneType format string bug (likely in scoring or query construction)
- For acquirer intent, query a different table or add `entity_type` filter

---

## Bug #4: Pattern-Match Rubric Still Too Generic (Fallback Path)

**File:** `backend/app/services/sourcing_service.py`, `generate_rubric()`

The pattern matcher extracts only single-word sectors:
```
"healthcare AI diagnostics" → sector: "ai"
"B2B SaaS sales enablement" → sector: "saas"
```

This matters because:
1. The decomposition fallback uses it (`subcategories: ["ai"]` instead of real subcategories)
2. The DB query uses it for sector filtering (if it ever gets wired up)
3. Template stamping references it for query generation

The LLM rubric returns much better sectors (`Healthcare Technology`, `B2B SaaS - Sales Enablement / Revenue Intelligence / CRM`), but the pattern-match fallback should be improved too.

---

## Bug #5: Template Stamping Uses Stale/Wrong Queries

The test output shows test cases 2-4 reusing test case 1's template stamps:
```
[1] top clinical AI startups 2026              ← this is test 1's query, not test 2's
[2] clinical AI platform startups
[3] fastest growing diagnostics AI companies
```

This appears to be a test script issue (the "mock decomposition" section), not the actual pipeline — the real pipeline generates correct queries from LLM decomposition. But the decomposition prompt fed to the LLM shows `SECTOR: saas` and `INTENT: dealflow` from the pattern-match rubric, when the LLM rubric already returned better values. The decomposition prompt should use the LLM rubric output, not the pattern-match fallback.

---

## Bug #6: No Grid Commands / No Persistence

All 4 tests: `grid_commands: 0`, `persist_results: False`.

Results appear as a markdown table in chat but aren't saved anywhere. Users can't filter, sort, or act on sourced companies through the grid UI.

---

## What Works Now (Post-Fix)

| Component | Status | Notes |
|---|---|---|
| Model router init | Fixed | Both Anthropic + OpenAI clients initialize. Groq/Google gracefully skipped |
| Claude as primary model | Fixed | Model order: claude-sonnet-4-5 → gpt-5.2 → gpt-5-mini |
| LLM rubric classification | Works | Correctly returns intent, entity_type, sector, completeness_fields |
| LLM decomposition | Works | 5 specific subcategories per test (e.g. "AI medical imaging and radiology diagnostics") |
| Tavily search | Works | 10 queries per test, results returned |
| Template stamping | Works | Generates list_discovery, vertical_deep, funding_signal, competitor_map queries |
| Deduplication | Works | Name normalization handles Inc/Ltd/LLC |
| Markdown table output | Works | Clean formatting |

## What Still Doesn't Work

| Component | Status | Blocker | Fix |
|---|---|---|---|
| Bulk extraction | Broken | JSON truncated at ~2300 chars | Bump max_tokens to 2000 (applied, needs re-test) |
| Rich extraction | Broken | Same truncation | Bump max_tokens to 2000 (applied, needs re-test) |
| DB sector filtering | Missing | Rubric sector not mapped to Supabase query | Wire `rubric.sector` → `sector.ilike` filter |
| DB stage filtering | Partial | Only works when explicit `stage` filter passed | Wire `rubric.target_stage` → `stage.ilike` filter |
| DB NoneType crash | Bug | `unsupported format string passed to NoneType.__format__` | Find and fix the None in the format string |
| Pattern-match intent (GTM) | Wrong | "sales enablement" not detected as `gtm_leads` | Add GTM keyword patterns |
| Pattern-match intent (acq targets) | Wrong | "acquisition targets" maps to `dealflow` | Add acquisition target patterns |
| Grid persistence | Not triggered | Display mode always `ranked_list` | Default to emitting grid_commands for sourcing |
| DB persistence | Not triggered | `persist_results` defaults to False | Consider defaulting to True for sourcing |
| Scoring on DB results | Poor | Top scores 14-30 out of 100 | Improve once sector/stage filtering reduces noise |

---

## Priority Fixes

### P0 — Immediate (re-test after applying)
1. ~~Fix model router~~ DONE
2. ~~Fix OpenAI SDK version~~ DONE
3. ~~Fix capability routing (FAST→STRUCTURED)~~ DONE
4. **Re-test with max_tokens bump** (800→2000) — already applied, need to verify extraction works

### P1 — Unblocks Useful Results
5. **Wire rubric sector/stage into DB query** — the LLM rubric returns `sector: "Healthcare Technology"` but the Supabase query ignores it. Map `rubric.filters.sector` → `sector.ilike.%{value}%` and `rubric.target_stage` → `stage.ilike.%{value}%`.
6. **Fix NoneType format string bug** — `unsupported format string passed to NoneType.__format__` in DB query path for tests 2-4. Find the `.format()` or f-string that receives None.
7. **Feed LLM rubric into decomposition prompt** — currently the decomposition prompt shows pattern-match values (`INTENT: dealflow, SECTOR: saas`) even when the LLM rubric returned better ones (`intent: gtm_leads, sector: B2B SaaS...`).

### P2 — Quality Improvements
8. **Add GTM intent patterns** — "sales", "CRM", "enablement", "revenue intelligence", "outbound", "prospecting" → `gtm_leads`
9. **Add acquisition target intent** — "acquisition target", "companies to acquire", "bolt-on" → `acquisition_target` or map to `acquirer` with different weights
10. **Make grid persistence default** for sourcing results
11. **Improve pattern-match sector extraction** — extract multi-word sectors ("healthcare AI", "sales enablement SaaS") not just single words ("ai", "saas")
12. **Budget caps** — `max_tavily_calls` param (default 50)

---

## Test Reproduction

```bash
cd /Users/admin/code/dilla-ai/backend
source venv/bin/activate
python test_sourcing_pipeline.py
```

The test script runs 4 queries and traces every stage: rubric → decomposition → template stamping → Tavily → extraction → enrichment → scoring → output.
