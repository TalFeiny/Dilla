# Dilla Dealflow Engine

## What This Is

An AI-native dealflow system that finds, scores, and surfaces companies using a mix of local DB, web search, and LLM reasoning. Not a CRM. Not a static database. An agent that builds lists, ranks them contextually per query, and produces deliverables (memos, decks, outreach) from the same scored data.

The core loop:

```
Query → Rubric → DB + Web → Normalize → Score → Surface
```

Every step already exists as a function somewhere in the codebase. The build is wiring them into a single loop.

---

## Architecture

```
                         USER QUERY
                    "Find me series B fintech
                     companies in LATAM"
                             │
                     ┌───────▼────────┐
                     │  RUBRIC ENGINE  │
                     │                 │
                     │  Derives weights│
                     │  from query:    │
                     │  sector: 0.30   │
                     │  stage: 0.25    │
                     │  geography: 0.20│
                     │  growth: 0.15   │
                     │  scale: 0.10    │
                     └───────┬────────┘
                             │
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
        ┌────────────┐ ┌──────────┐ ┌────────────┐
        │  LOCAL DB   │ │   WEB    │ │  PORTFOLIO │
        │             │ │  SEARCH  │ │  CONTEXT   │
        │ query_      │ │          │ │            │
        │ companies() │ │ Tavily   │ │ Already in │
        │ from        │ │ Firecrawl│ │ shared_data│
        │ Supabase    │ │ Agent    │ │            │
        │             │ │ crafts   │ │            │
        │ 1K+ rows    │ │ queries  │ │            │
        └──────┬──────┘ └────┬─────┘ └─────┬──────┘
               │             │             │
               └──────┬──────┘             │
                      ▼                    │
              ┌───────────────┐            │
              │   NORMALIZE   │            │
              │               │            │
              │ Web results → │            │
              │ company dicts │            │
              │ Same shape as │            │
              │ DB results    │            │
              └───────┬───────┘            │
                      │                    │
                      ▼                    ▼
              ┌───────────────────────────────┐
              │         SCORE + RANK          │
              │                               │
              │  score_companies(results,      │
              │                 rubric)        │
              │                               │
              │  7 dimensions × custom weights │
              │  Composite 0-100, ranked       │
              └───────────────┬───────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
         ┌───────────┐ ┌──────────┐ ┌────────────┐
         │   TABLE   │ │   MEMO   │ │  OUTREACH  │
         │           │ │          │ │            │
         │ Ranked    │ │ IC memo  │ │ Draft cold │
         │ list in   │ │ on top N │ │ email per  │
         │ Matrix UI │ │ scored   │ │ company    │
         │           │ │ companies│ │ positioned │
         │           │ │          │ │ to thesis  │
         └───────────┘ └──────────┘ └────────────┘
```

---

## Components

### 1. Rubric Engine

**What**: Make `score_companies()` accept query-derived weights instead of static `DEFAULT_WEIGHTS`.

**Where**: `backend/app/services/sourcing_service.py`

**How it works**:

```python
# Static (current) — same ranking regardless of query
score_companies(companies)  # always DEFAULT_WEIGHTS

# Contextual (rubric engine) — ranking changes per query
rubric = derive_rubric("find me Stripe competitors")
# → {"sector": 0.30, "scale": 0.25, "capital_efficiency": 0.20, ...}

score_companies(companies, weights=rubric)
```

The rubric derivation is an LLM call that maps a natural language query to weight overrides. The scoring itself stays pure math — no LLM, <1ms.

**Rubric derivation strategies**:

| Query Pattern | Auto-Rubric |
|---------------|-------------|
| "companies like X" | Match X's profile: sector HIGH, scale HIGH, stage LOW |
| "series B in [sector]" | stage HIGH, sector HIGH |
| "follow-on candidates" | growth HIGH, efficiency HIGH, recency HIGH |
| "market map for [space]" | sector HIGH, data_completeness HIGH, scale MEDIUM |
| "who's growing fastest" | growth HIGH, scale MEDIUM |
| "capital efficient companies" | capital_efficiency HIGH, growth MEDIUM |

**Implementation**: ~200 lines. One function that takes a query string and returns a weights dict. Can be LLM-derived or pattern-matched — start with patterns, add LLM later.

**Status**: Not built. This is the foundation for everything below.

---

### 2. Search Loop

**What**: When DB doesn't have enough results, the agent searches the web, normalizes results, scores them, and merges.

**Where**: `backend/app/services/unified_mcp_orchestrator.py` — inside `_tool_build_company_list` or `_tool_source_companies`

**Current behavior**:
```
query_companies(filters) → score → return
```

**Target behavior**:
```
query_companies(filters) → score → enough? → YES → return
                                            → NO  → web search
                                                     → normalize
                                                     → score
                                                     → merge + dedupe
                                                     → return
```

**What "enough" means**: Configurable threshold. Default: if scored results < 10, search web. The agent can also decide based on score distribution — if top score is < 40, the DB doesn't have good matches and web search makes sense.

**Web search strategy**: The agent crafts search queries from the rubric context. Not one generic search — multiple targeted queries:

```
Query: "Series B fintech LATAM"

Agent searches:
  1. "series B fintech startup Latin America 2024 2025 funding"
  2. "fintech company Brazil Mexico Colombia series B raised"
  3. "LATAM payments lending neobank series B"
```

**Normalization**: Web results (titles, snippets, URLs) → LLM extraction → company dict with same shape as DB rows (`name`, `sector`, `stage`, `arr`, `valuation`, `total_funding`, etc.)

**Existing tools that do this**:
- `search_and_extract` — Tavily search + structured extraction
- `fetch_company_data` — 6 parallel Tavily searches + full profile extraction
- `lightweight_diligence` — single search + quick extraction
- `enrich_company_proactive` — auto-fetch + push to grid

The loop just orchestrates calls to these existing tools.

**Implementation**: ~50 lines of orchestration logic + ~20 lines of system prompt update telling the agent when to search web.

**Status**: Tools exist. Loop doesn't.

---

### 3. Surfaces

Three output formats on the same scored data:

#### Table (exists)
Ranked list in Matrix UI. `format_as_markdown_table()` in sourcing_service.py already does this.

#### Memo (exists, now with sourcing context)
`generate_memo()` → LightweightMemoService. As of the latest fix, the memo pipeline now calls SourcingService in pre-flight, so memos include comparable companies and sector benchmarks.

#### Outreach (new)
Agent drafts personalized outreach per scored company. Positioned to fund thesis.

```
Input: scored company + fund_context (thesis, check size, stage focus)
Output: cold email / LinkedIn message / intro request template

"Hi [founder], I'm with [fund] — we write $10-20M checks in Series A-C
[sector] companies. [Company] caught our attention because [specific thing
from scored data — growth rate, market position, recent round].
Would love to learn more about [specific angle]."
```

This is a new skill/template, not a new pipeline. Same data, different format string.

**Implementation**: ~100 lines as a new memo template or skill.

**Status**: Not built.

---

## What Already Exists (Inventory)

| Component | File | Function | Status |
|-----------|------|----------|--------|
| DB query with filters | `sourcing_service.py` | `query_companies()` | Working |
| 7-dimension scoring | `sourcing_service.py` | `score_companies()` | Working, needs rubric |
| Tavily web search | `mcp_orchestrator.py` | `execute_tavily()` | Working |
| Firecrawl scraping | `mcp_orchestrator.py` | `execute_firecrawl()` | Working |
| Company profile extraction | `unified_mcp_orchestrator.py` | `_execute_company_fetch()` | Working |
| Lightweight diligence | `unified_mcp_orchestrator.py` | `_execute_lightweight_diligence()` | Working |
| List building tool | `unified_mcp_orchestrator.py` | `_tool_build_company_list` | Registered, basic |
| Search + extract combo | `unified_mcp_orchestrator.py` | `_tool_search_extract` | Registered |
| Proactive enrichment | `unified_mcp_orchestrator.py` | `_tool_enrich_proactive` | Registered |
| Gap resolution | `micro_skills/gap_resolver.py` | `resolve_gaps()` | Working |
| Memo generation | `lightweight_memo_service.py` | `generate()` | Working |
| Deck generation | `unified_mcp_orchestrator.py` | `_execute_deck_generation()` | Working |
| Chart dispatch | `chart_data_service.py` | `_build_chart()` | Working (23+ types) |
| Markdown table format | `sourcing_service.py` | `format_as_markdown_table()` | Working |
| Display mode picker | `sourcing_service.py` | `pick_display_mode()` | Working |
| Company persistence | `sourcing_service.py` | `upsert_sourced_companies()` | Working |

---

## Build Sequence

### Week 1: Rubric Engine + Search Loop (Monday beta)

**Day 1-2**: Rubric engine
- Add `derive_rubric(query: str) -> Dict[str, float]` to `sourcing_service.py`
- Pattern-match common query types to weight presets
- Wire into `_tool_source_companies` so every query gets contextual scoring
- ~200 lines

**Day 3**: Search loop
- In `_tool_build_company_list`, add: if DB results < threshold, call `search_and_extract` with crafted queries
- Normalize web results into company dicts
- Score with same rubric, merge with DB results, dedupe
- ~50 lines of logic

**Day 4**: System prompt update
- Tell agent: "When building company lists, always score with a query-contextual rubric. If DB returns < 10 results or top score < 40, search the web for more."
- ~20 lines of prompt

**Day 5**: Test with real queries
- "Find me 20 series B SaaS companies"
- "Who's similar to [portfolio company]?"
- "Market map for vertical AI in healthcare"
- Verify: DB query → scoring → web fallback → merged results

### Week 2: Outreach Surface + Polish

**Day 1-2**: Outreach template
- New skill or memo template: takes scored company + fund thesis → drafts outreach
- Multiple formats: cold email, LinkedIn, intro request
- ~100 lines

**Day 3-4**: Persistence loop
- Agent finds companies via web → option to "add to pipeline" → `upsert_sourced_companies()`
- Next query against same sector returns cached web-sourced companies from DB
- DB grows organically from agent's research

**Day 5**: Agent autonomy
- Agent can run the full loop without user prompting each step
- "Build me a list of 30 companies in [space]" → agent does everything → returns ranked list with option to memo/outreach

---

## How This Differs From Off-The-Shelf

| Feature | Typical Dealflow Tool | Dilla |
|---------|----------------------|-------|
| Data source | Fixed database (Crunchbase, PitchBook) | DB + web + agent research |
| Scoring | Static filters | Query-contextual rubric engine |
| List building | Manual search + filter | Agent builds list autonomously |
| Enrichment | API connector per source | Agent searches + LLM extracts |
| Output | Table / CSV export | Table + memo + deck + outreach |
| Intelligence | None — just a database | Agent reasons about what to search |
| Cost | $30-80K/year API fees | Tavily ($0.01/search) + LLM tokens |

The key difference: there's no fixed data provider. The agent IS the data provider. It thinks about what to search, evaluates what comes back, and funnels everything through scoring. The DB is a cache that gets smarter over time as the agent researches more companies.

---

## Metrics for Monday Beta

| Metric | Target |
|--------|--------|
| DB query + score | < 500ms for 1K companies |
| Rubric derivation | < 2s (pattern match) or < 5s (LLM) |
| Web search + normalize | < 15s for 5 searches |
| Full list build (DB + web) | < 30s for 20 results |
| Memo on scored results | < 60s |
| Companies in DB after 1 week of use | 2K+ (organic growth from searches) |
