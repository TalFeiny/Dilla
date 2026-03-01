# Search & Extract Strategy for Company Sourcing

> Dilla AI — Dealflow Discovery Pipeline
> Feb 2026 — Based on experimental findings from `test_search_strategies.py`

---

## The Problem

The current pipeline treats Tavily like Google — it generates queries as if users will land on company homepages. In reality, **Tavily returns articles _about_ companies, not companies themselves.** The names are in the results. The pipeline throws away the context around those names and then spends 10x the cost re-discovering it.

Current flow:
```
LLM generates 6 free-form queries
  → Tavily returns snippets (articles, lists, funding news)
    → LLM extracts just the company names (throws away all context)
      → 6 Tavily searches PER company to re-find what we already had
        → Claude extracts structured data from those results
```

For 8 companies that's ~48 API calls in enrichment alone. Most of that data was already sitting in the original search results.

---

## Experimental Findings

We tested 8 query strategy groups against "Series B healthcare SaaS companies":

| Strategy | What it does | Result |
|---|---|---|
| Naive thesis queries | "Series B healthcare SaaS companies" | Poor — returns market analysis articles, not company names |
| Source-targeted | `site:crunchbase.com`, `site:techcrunch.com` | Good for funding data, limited breadth |
| Lists & roundups | "top healthcare SaaS startups 2024" | Good — hits Tracxn/Seedtable pages with 50+ names |
| **Vertical decomposition** | Break into EHR, telehealth, RCM, clinical ops | **Best — hits different list pages per vertical** |
| Portfolio mining | "a16z bio portfolio", "GV healthcare" | Moderate — useful but narrow |
| Competitor landscape | "Veeva competitors", "Epic alternatives" | Good for known-market mapping |
| Funding events | "company raised Series B 2024 healthcare" | Good — returns articles with funding data baked in |
| Breadth test | Very broad → very specific | Broad queries waste tokens, specific queries miss names |

**Key insight:** Vertical decomposition + source-targeted queries significantly outperform naive thesis queries. The best results come from queries that target **page types** (list pages, funding articles), not companies directly.

---

## Query-to-Intent Mapping

Not all queries serve the same purpose. Each query should have an explicit **intent** that determines how its results get processed.

### Intent Types

| Intent | Query Pattern | Expected Page Type | Extraction Mode | Example |
|---|---|---|---|---|
| `list_discovery` | "top {subcategory} startups {year}" | Aggregator lists (Tracxn, Seedtable, G2, CB Insights) | Bulk extract — 20-50+ names, minimal metadata | "top EHR startups 2025" |
| `funding_signal` | "{subcategory} companies funding raised {year}" | News articles (TechCrunch, Crunchbase News) | Targeted extract — 1-3 names + funding amount, stage, investors | "telehealth Series B funding 2024 2025" |
| `competitor_map` | "{known_company} competitors alternatives" | Comparison/review pages | Relational extract — names + how they relate to anchor company | "Veeva competitors healthcare SaaS" |
| `portfolio_mine` | "{investor} portfolio {sector}" | VC portfolio pages | Bulk extract — names + investor signal (tier 1 = quality proxy) | "a16z healthcare portfolio" |
| `vertical_deep` | "{niche_subcategory} software companies" | Mixed — lists + articles | Standard extract — names + sector classification | "revenue cycle management automation companies" |

### Why Intent Matters

Intent determines:
1. **How many names to expect** — a list page has 50, a funding article has 1-3
2. **What metadata is available** — a funding article has stage + amount, a list page has names only
3. **How to extract** — bulk scan vs. careful per-article parsing
4. **Whether to deep-enrich** — if the source already gave us funding + stage, skip the 6-query enrichment

---

## New Pipeline Architecture

### Step 1: Structured Query Decomposition (replaces free-form query gen)

Current: LLM generates 6 arbitrary queries.
New: LLM decomposes thesis into subcategories, then stamps them into proven templates.

```
Input: "Series B healthcare SaaS companies"

LLM Decomposition:
  subcategories: [EHR, telehealth, RCM, clinical ops, patient engagement]

Query Generation (template-based):
  list_discovery:
    - "top EHR startups 2025"
    - "top telehealth startups 2025"
    - "top revenue cycle management software companies"
  funding_signal:
    - "EHR companies funding raised 2024 2025"
    - "telehealth Series B funding 2024"
  vertical_deep:
    - "clinical operations SaaS companies"
    - "patient engagement platform startups"
```

Each query carries its intent tag. 6-10 queries total, guaranteed diverse, hitting the right page types.

**What to stop generating:**
- Landscape/market map queries ("healthcare SaaS market landscape") — returns zero names
- Over-constrained queries ("Series B healthcare SaaS EHR >$10M ARR Bay Area") — too specific for Tavily
- Generic VC trend queries ("healthcare investment trends 2025") — returns analysis, not companies

### Step 2: Two-Tier Extraction (replaces one-size-fits-all name extraction)

Current: every Tavily result gets the same name-extraction prompt.
New: extraction mode is determined by the query's intent.

#### Tier A — Bulk List Extraction (for `list_discovery`, `portfolio_mine`)

Input: Tracxn page "Top 69 EHR Startups"
Output:
```json
[
  {"name": "Heidi Health", "sector": "EHR", "source_url": "tracxn.com/..."},
  {"name": "Canvas Medical", "sector": "EHR", "source_url": "tracxn.com/..."},
  // ... up to 50+ names
]
```

Light metadata only. Goal is **maximum name yield** per API call. One LLM call handles the whole page.

#### Tier B — Rich Article Extraction (for `funding_signal`, `competitor_map`)

Input: TechCrunch article "Heidi Health raises $65M Series B led by Spark Capital"
Output:
```json
[
  {
    "name": "Heidi Health",
    "sector": "clinical AI",
    "stage": "Series B",
    "last_funding_amount": 65000000,
    "investors": ["Spark Capital"],
    "description": "AI-powered clinical documentation",
    "source_url": "techcrunch.com/...",
    "data_completeness": 0.7
  }
]
```

Fewer names but **rich data extracted on first pass**. The funding amount, investors, and stage are right there in the article — don't throw them away.

### Step 3: Selective Deep Enrichment (replaces enrich-everything)

Current: every discovered company gets `_execute_company_fetch()` — 6 Tavily searches + Claude extraction per name.
New: score completeness first, only enrich what's missing.

```
For each discovered company:
  completeness = count_non_null([name, sector, stage, funding, description, investors]) / 6

  if completeness >= 0.6:
    → Skip deep enrichment. Score with what we have.

  if completeness < 0.6 AND company looks promising (from list context):
    → Run lightweight diligence (1 Tavily + 1 LLM) to fill gaps

  if completeness < 0.3 AND company is just a name:
    → Run full microskills enrichment (5 parallel Tavily searches)
```

**Expected cost reduction:** For a typical sourcing run finding 30 companies:
- ~10 come from funding articles (completeness 0.6+) → 0 extra searches
- ~15 come from list pages (completeness 0.2) → 15 lightweight searches
- ~5 are ambiguous names → 25 full searches (5 each)

Total: ~40 Tavily calls vs. current ~180 (6 per company × 30). **~4.5x reduction.**

---

## Pipeline Flow (End to End)

```
User thesis: "Series B healthcare SaaS companies"
  │
  ▼
┌─────────────────────────────────────┐
│  1. RUBRIC GENERATION               │
│  generate_rubric(thesis)            │
│  → intent, weights, filters,        │
│    search_context                    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. STRUCTURED DECOMPOSITION        │
│  LLM decomposes → 3-5 subcategories │
│  Templates stamp → 6-10 queries     │
│  Each query tagged with intent      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  3. PARALLEL TAVILY SEARCH          │
│  Run all queries concurrently       │
│  Each result carries its intent tag │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  4. INTENT-ROUTED EXTRACTION        │
│                                     │
│  list_discovery → Tier A (bulk)     │
│  funding_signal → Tier B (rich)     │
│  competitor_map → Tier B (rich)     │
│  portfolio_mine → Tier A (bulk)     │
│  vertical_deep  → Tier A (bulk)    │
│                                     │
│  Output: [{name, sector, stage,     │
│    funding, source, completeness}]  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  5. DEDUPE & MERGE                  │
│  Same company from multiple sources │
│  → merge fields, keep highest       │
│    completeness version             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  6. SELECTIVE ENRICHMENT            │
│                                     │
│  completeness >= 0.6 → skip         │
│  completeness 0.3-0.6 → lightweight │
│  completeness < 0.3 → full enrich   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  7. SCORE & RANK                    │
│  score_companies() with rubric      │
│  weights (existing logic, no change)│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  8. SURFACE                         │
│  Top N → matrix UI / markdown table │
│  Optional: persist to Supabase      │
│  Optional: outreach queue           │
└─────────────────────────────────────┘
```

---

## What Changes in the Code

| Component | File | Change |
|---|---|---|
| Query generation | `sourcing_service.py` → `build_query_gen_prompt()` | Replace free-form prompt with decomposition + template stamping. Add intent tags to each query. |
| Name extraction | `sourcing_service.py` → `build_name_extraction_prompt()` | Split into two extraction prompts: bulk (Tier A) and rich (Tier B). Route by intent. |
| Enrichment trigger | `unified_mcp_orchestrator.py` → `_tool_source_companies()` | Add completeness scoring before enrichment. Gate `_execute_company_fetch()` behind completeness threshold. |
| Merge logic | New | Dedupe companies by name across multiple search results. Merge partial records into most-complete version. |
| Lightweight diligence | `unified_mcp_orchestrator.py` → `_execute_lightweight_diligence()` | Already exists. Wire it into the selective enrichment path for mid-completeness companies. |

### What Doesn't Change

- `generate_rubric()` — still produces intent, weights, filters
- `score_companies()` — still pure math, same 7 dimensions
- `_execute_company_fetch()` — still exists for deep enrichment, just called less often
- Microskills schemas — FUNDING_SCHEMA, TEAM_SCHEMA etc. still used when deep enrichment fires
- IntelligentGapFiller — still used for inference, just on fewer companies

---

## Query Template Library

### List Discovery Templates
```
"top {subcategory} startups {year}"
"best {subcategory} companies {year}"
"{subcategory} startups to watch {year}"
"fastest growing {subcategory} companies"
```

### Funding Signal Templates
```
"{subcategory} companies funding raised {year-1} {year}"
"{subcategory} {target_stage} funding {year}"
"site:techcrunch.com {subcategory} funding"
"site:crunchbase.com {subcategory} funding round"
```

### Competitor Map Templates
```
"{known_company} competitors alternatives"
"{known_company} vs"
"companies like {known_company}"
```

### Portfolio Mine Templates
```
"{investor} portfolio {sector}"
"{investor} {sector} investments"
```

### Vertical Deep Templates
```
"{niche_subcategory} software companies"
"{niche_subcategory} platform startups"
"{niche_subcategory} automation tools"
```

---

## Metrics to Track

| Metric | Current (estimated) | Target |
|---|---|---|
| Tavily calls per sourcing run (30 companies) | ~180 | ~40 |
| Names extracted per Tavily call | ~1-2 | ~5-10 (list pages boost this) |
| Data completeness at extraction (before enrichment) | ~0.15 | ~0.45 |
| Companies needing full enrichment | 100% | ~15-20% |
| End-to-end latency (30 companies) | ~90s | ~30s |
| Cost per sourcing run | ~$2-3 (Tavily + Claude) | ~$0.50-0.80 |

---

## Round 2: Adaptive Follow-Up (Existing, Keep)

The current Round 2 logic (4 adaptive queries based on Round 1 gaps) is good. Keep it, but:
- Tag Round 2 queries with intents too
- Use Round 1 extraction results (not just names) to identify gaps
- If Round 1 found 40 names but all from EHR, Round 2 should target underrepresented subcategories (telehealth, RCM)

---

## Open Questions

1. **Crawl depth:** Should we follow links from list pages to individual company pages? Adds latency but could boost completeness for Tier A extractions.
2. **Cache strategy:** Company data has a half-life. How long before we re-enrich? Current Tavily cache is 5 minutes — should extracted company data be cached longer (days/weeks)?
3. **Dedup quality:** Name matching is hard ("Heidi Health" vs "Heidi" vs "heidihealth.com"). Do we need fuzzy matching or is exact + domain sufficient?
4. **Budget caps:** Should the selective enrichment respect a per-run budget? e.g., max 50 Tavily calls regardless of completeness scores.
