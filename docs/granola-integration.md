# Granola Integration — Meeting Intelligence Pipeline

## TL;DR

Integrate Granola (AI meeting notes) as a first-class document source in Dilla's existing document processing pipeline. Every meeting with a portfolio company automatically becomes a processed document with signal extraction, impact estimates, and matrix suggestions — no manual upload needed.

Two integration paths, built in parallel:
1. **API Integration** — automated polling of Granola Enterprise API, auto-ingest transcripts as `meeting_transcript` documents
2. **MCP Tool** — on-demand pull via the agent, so users can say "pull my Granola notes from the Anthropic board meeting"

---

## Why Integration, Not a Separate App

Our document pipeline already handles the hard part:
- Signal-first extraction (`COMPANY_UPDATE_SIGNAL_SCHEMA`) transforms qualitative prose into quantitative impact estimates
- Suggestion emission auto-populates matrix cells with badges
- Company linking, fund linking, and time-series tracking all exist
- Board transcripts are already a supported `document_type`

Meeting transcripts are structurally identical to board transcripts — qualitative signals that need to be transformed into financial impact estimates. Building a separate app would duplicate all of this.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ GRANOLA                                                              │
│  Enterprise API: https://public-api.granola.ai/v1/                   │
│  GET /v1/notes        — list notes (paginated, date-filtered)        │
│  GET /v1/notes/{id}   — single note + transcript                     │
│  Auth: Bearer token (Enterprise plan, workspace admin)               │
│  Rate: 25 req/5s burst, 300 req/min sustained                        │
└──────────┬──────────────────────────────────┬────────────────────────┘
           │                                  │
           │ Path 1: Auto-Sync                │ Path 2: MCP / Agent
           │ (periodic poll)                  │ (on-demand)
           ▼                                  ▼
┌─────────────────────────┐     ┌─────────────────────────────────────┐
│ GranolaService          │     │ Orchestrator Skill                  │
│ (granola_service.py)    │     │ "granola-meeting-fetcher"           │
│                         │     │                                     │
│ • poll_new_notes()      │     │ Agent says:                         │
│ • match_to_company()    │     │ "pull Granola notes for Anthropic"  │
│ • format_for_pipeline() │     │ → search notes by attendee/title    │
│ • ingest_to_pipeline()  │     │ → ingest matched notes              │
└────────┬────────────────┘     └────────┬────────────────────────────┘
         │                               │
         └───────────┬───────────────────┘
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│ EXISTING DOCUMENT PIPELINE                                           │
│                                                                      │
│ 1. Create processed_documents row (status=pending)                   │
│    document_type = "meeting_transcript"                               │
│    company_id = matched company                                      │
│    storage_path = granola://{note_id}  (virtual, text already in DB) │
│                                                                      │
│ 2. run_document_process()                                            │
│    → Skip storage download (text provided directly)                  │
│    → _extract_document_structured_async()                            │
│      → Uses MEETING_TRANSCRIPT_SCHEMA (new, extends signal schema)   │
│    → _normalize_extraction()                                         │
│                                                                      │
│ 3. emit_document_suggestions()                                       │
│    → Flatten extracted data → FIELD_TO_COLUMN mapping                │
│    → Upsert to pending_suggestions                                   │
│    → Frontend badges appear on matrix cells                          │
│                                                                      │
│ 4. Company metrics history updated                                   │
│    → Time-series ARR/burn tracking from meeting signals              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## What Granola Gives Us

### API Response (GET /v1/notes/{id}?include=transcript)

```json
{
  "id": "not_abc123def456gh",
  "title": "Anthropic Series C Board Meeting",
  "owner": { "name": "Jane GP", "email": "jane@fund.com" },
  "attendees": [
    { "name": "Dario Amodei", "email": "dario@anthropic.com" },
    { "name": "Jane GP", "email": "jane@fund.com" }
  ],
  "summary_text": "Plain text summary...",
  "summary_markdown": "## Key Decisions\n- Approved Q4 hiring plan...",
  "transcript": [
    {
      "speaker": "Dario Amodei",
      "text": "ARR hit $850M this quarter, up from $600M...",
      "timestamp": "2025-01-15T14:05:00Z"
    }
  ],
  "calendar_event": {
    "title": "Anthropic Board Meeting",
    "start": "2025-01-15T14:00:00Z",
    "end": "2025-01-15T16:00:00Z"
  },
  "created_at": "2025-01-15T16:05:00Z",
  "updated_at": "2025-01-15T16:30:00Z"
}
```

### What We Extract

| Granola Field | Pipeline Use |
|---|---|
| `title` | Document title, company matching signal |
| `attendees` | Match to portfolio companies by email domain |
| `summary_markdown` | Primary text for signal extraction |
| `transcript` | Full text for deep extraction (speaker-attributed) |
| `calendar_event.start` | `period_date` for the document |
| `attendees[].name` | People mentioned → team intelligence |

---

## New Components

### 1. `backend/app/services/granola_service.py`

Core service that handles all Granola API interaction and company matching.

```python
class GranolaService:
    """Granola API client + company matching + pipeline ingestion."""

    BASE_URL = "https://public-api.granola.ai/v1"

    def __init__(self, api_key: str, supabase_client):
        self.api_key = api_key
        self.supabase = supabase_client
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def list_notes(
        self,
        created_after: str = None,
        updated_after: str = None,
        page_size: int = 30,
    ) -> list[dict]:
        """Paginate through all notes since last sync."""
        ...

    async def get_note_with_transcript(self, note_id: str) -> dict:
        """Fetch single note with full transcript."""
        ...

    def match_to_company(self, note: dict, fund_id: str) -> str | None:
        """Match a Granola note to a portfolio company.

        Strategy (ordered by confidence):
        1. Attendee email domain → company domain in portfolio
        2. Note title contains company name
        3. Transcript mentions company name in first 500 chars

        Returns company_id or None.
        """
        ...

    def format_for_pipeline(self, note: dict) -> str:
        """Convert Granola note to text for extraction pipeline.

        Format:
        ---
        MEETING: {title}
        DATE: {calendar_event.start}
        ATTENDEES: {attendees list}
        ---

        ## AI Summary
        {summary_markdown}

        ## Full Transcript
        [{timestamp}] {speaker}: {text}
        ...
        """
        ...

    async def ingest_note(
        self,
        note: dict,
        fund_id: str,
        company_id: str = None,
    ) -> dict:
        """Push a Granola note through the document pipeline.

        1. Check dedup (granola_note_id already processed?)
        2. Match to company if not provided
        3. Create processed_documents row
        4. Run extraction (text provided directly, no storage download)
        5. Return processing result
        """
        ...

    async def sync_new_notes(self, fund_id: str) -> dict:
        """Poll for new notes since last sync, ingest all.

        Returns { synced: int, matched: int, unmatched: int, errors: int }
        """
        ...
```

### 2. `MEETING_TRANSCRIPT_SCHEMA` — New extraction schema

Extends `COMPANY_UPDATE_SIGNAL_SCHEMA` with meeting-specific fields:

```python
MEETING_TRANSCRIPT_SCHEMA = {
    # All fields from COMPANY_UPDATE_SIGNAL_SCHEMA, plus:

    "meeting_metadata": {
        "meeting_type": "string (board_meeting, partner_check_in, quarterly_review, pitch, other)",
        "attendees_by_role": "object { founders: [], investors: [], operators: [] }",
        "meeting_duration_minutes": "number or null",
        "next_meeting_date": "string (ISO date) or null",
    },

    "action_items": [
        {
            "description": "string",
            "owner": "string (attendee name)",
            "due_date": "string (ISO date) or null",
            "priority": "string (high, medium, low)",
        }
    ],

    "decisions_made": "array of strings (concrete decisions, not discussion points)",

    "founder_sentiment": {
        "overall": "string (confident, cautious, concerned, defensive, evasive)",
        "confidence_signals": "array of strings (specific quotes showing confidence)",
        "concern_signals": "array of strings (specific quotes showing concern)",
        "body_language_proxy": "string or null (tone analysis from transcript — hedging, energy, etc.)",
    },

    "information_asymmetry": {
        "things_founder_volunteered": "array of strings (proactively shared, not asked)",
        "things_we_had_to_ask": "array of strings (only disclosed when directly questioned)",
        "things_not_answered": "array of strings (dodged, deferred, or vague responses)",
    },

    # Standard signal schema fields inherited:
    # business_updates, operational_metrics, extracted_entities,
    # financial_metrics, impact_estimates, impact_reasoning,
    # red_flags, implications, value_explanations
}
```

This schema is the real value-add. We're not just transcribing — we're extracting **what the founder volunteered vs. what they hid**, **concrete decisions**, and **action items with owners**. That's intelligence you can't get from a PDF memo.

### 3. Orchestrator Skill: `granola-meeting-fetcher`

Register in `_initialize_skill_registry()`:

```python
"granola-meeting-fetcher": {
    "category": SkillCategory.DATA_GATHERING,
    "handler": self._execute_granola_fetch,
    "description": "Fetch and process meeting notes from Granola"
},
```

The handler:

```python
async def _execute_granola_fetch(self, companies, prompt_data, shared_data):
    """Fetch Granola meeting notes for specified companies or date range.

    Supports:
    - "pull Granola notes for Anthropic" → search by company name
    - "sync my latest meetings" → poll all new notes
    - "get board meeting notes from last week" → date-filtered search
    """
    ...
```

### 4. MCP Server Integration

Granola's official MCP server at `https://mcp.granola.ai/mcp` can also be registered as an external tool in the orchestrator, giving the agent direct access to search/read Granola notes alongside Tavily and Firecrawl.

### 5. API Endpoint: `POST /api/granola/sync`

```python
@router.post("/api/granola/sync")
async def sync_granola(fund_id: str, api_key: str = Header(...)):
    """Trigger manual sync of new Granola notes."""
    service = GranolaService(api_key, supabase)
    result = await service.sync_new_notes(fund_id)
    return result
```

### 6. Frontend: Granola Settings

Minimal UI in fund settings:
- API key input (stored encrypted)
- Toggle auto-sync on/off
- Sync frequency (every 15min / 30min / 1hr / manual)
- Company matching rules (by email domain, by title keyword)
- Last sync timestamp + stats

---

## Company Matching Strategy

This is the critical piece — automatically linking a Granola meeting to the right portfolio company.

```
Priority 1: Email domain match (highest confidence)
  attendee email "dario@anthropic.com" → domain "anthropic.com"
  → lookup companies table WHERE domain = "anthropic.com"
  → confidence: 0.95

Priority 2: Title match
  note title "Anthropic Q4 Board Meeting"
  → fuzzy match against company names in portfolio
  → confidence: 0.85

Priority 3: Transcript mention
  first 500 chars of transcript mention "Anthropic" or "Claude"
  → match against company names + product names
  → confidence: 0.70

Priority 4: Calendar event metadata
  calendar invite includes company-domain attendees
  → confidence: 0.90

Unmatched: Create document without company_id
  → User can manually link in UI
  → Or agent can match later: "link my unmatched meetings"
```

---

## Extraction Prompt Enhancement

The existing `_signal_first_prompt()` handles board transcripts well. For meeting transcripts, we add a preamble:

```
This is a MEETING TRANSCRIPT from a portfolio company interaction.
Unlike board decks (which are curated), meeting transcripts reveal
unfiltered signals. Pay special attention to:

1. INFORMATION ASYMMETRY: What did the founder volunteer vs. what
   was only disclosed when asked? Evasive or defensive answers on
   burn, churn, or runway are red flags.

2. FOUNDER SENTIMENT: Read tone, not just words. "We're cautiously
   optimistic" = concerned. "Growth is tracking" without numbers =
   growth is slowing.

3. ACTION ITEMS: Extract every commitment with owner and timeline.
   Undelivered action items from previous meetings = execution risk.

4. DECISIONS: Separate concrete decisions from discussion points.
   "We decided to raise Series C in Q2" ≠ "We discussed raising."
```

---

## Database Changes

### New columns on `processed_documents`:

```sql
ALTER TABLE processed_documents
  ADD COLUMN source_integration text DEFAULT NULL,
  ADD COLUMN external_id text DEFAULT NULL;

-- For dedup: don't re-process the same Granola note
CREATE UNIQUE INDEX idx_processed_documents_external_id
  ON processed_documents (source_integration, external_id)
  WHERE external_id IS NOT NULL;
```

- `source_integration`: `"granola"` | `"upload"` | `"email"` (future) | `null` (legacy)
- `external_id`: Granola note ID (`not_abc123def456gh`)

### New table: `integration_configs`

```sql
CREATE TABLE integration_configs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fund_id uuid REFERENCES funds(id),
  integration_name text NOT NULL,       -- 'granola'
  config jsonb NOT NULL DEFAULT '{}',   -- { api_key_encrypted, sync_frequency, enabled, ... }
  last_sync_at timestamptz,
  last_sync_result jsonb,               -- { synced: 5, matched: 4, errors: 0 }
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (fund_id, integration_name)
);
```

---

## Deduplication

We never process the same Granola note twice:

1. Before ingestion, check: `SELECT 1 FROM processed_documents WHERE source_integration = 'granola' AND external_id = ?`
2. If exists and status = `completed` → skip
3. If exists and status = `failed` → retry
4. If not exists → create and process

For updated notes (Granola's `updated_after` parameter), we compare `updated_at` timestamps and re-process if the note was edited after our last extraction.

---

## Sync Flow

### Auto-Sync (Background Worker)

```
Every {sync_frequency}:
  1. Read integration_configs WHERE integration_name = 'granola' AND enabled = true
  2. For each fund:
     a. GET /v1/notes?created_after={last_sync_at}&page_size=30
     b. For each note:
        - Check dedup (external_id)
        - Match to company (email domain → title → transcript)
        - Format text (summary + transcript)
        - Create processed_documents row (document_type = 'meeting_transcript')
        - Queue for extraction (Celery async)
     c. Update last_sync_at and last_sync_result
  3. Log: "Synced 5 notes, 4 matched to companies, 1 unmatched"
```

### On-Demand (Agent Skill)

```
User: "pull my recent meetings with Anthropic"
  → Agent calls granola-meeting-fetcher skill
  → Skill searches notes by attendee domain (anthropic.com)
  → Filters to last 30 days
  → Ingests matched notes through pipeline
  → Returns: "Found 3 meetings with Anthropic. Extracted signals:
     - ARR mentioned as $850M (up from $600M)
     - Hiring plan approved for 200 engineers
     - Series C discussion, targeting $60B valuation"
```

---

## Implementation Order

### Phase 1: Core Service (Week 1)
1. `granola_service.py` — API client, note fetching, pagination
2. `MEETING_TRANSCRIPT_SCHEMA` — add to `document_process_service.py`
3. Meeting-specific extraction prompt preamble
4. DB migration: `source_integration`, `external_id` columns + index
5. Modify `run_document_process()` to accept text directly (skip storage download when `source_integration` is set)

### Phase 2: Pipeline Integration (Week 1-2)
6. Company matching logic (email domain → title → transcript)
7. `POST /api/granola/sync` endpoint
8. Dedup logic
9. `integration_configs` table + migration
10. Wire suggestion emission (already works, just needs the new schema fields mapped)

### Phase 3: Orchestrator Skill (Week 2)
11. Register `granola-meeting-fetcher` skill
12. Handler: search by company, date range, or "sync all"
13. Add to skill builder so agent auto-invokes when user mentions meetings
14. MCP server registration (optional, for direct Granola tool access)

### Phase 4: Frontend + Auto-Sync (Week 2-3)
15. Granola settings UI (API key, sync toggle, frequency)
16. Background sync worker (Celery beat or cron)
17. Document list: show Granola source badge + meeting metadata
18. Unmatched meetings UI (manual company linking)

---

## What This Unlocks

Once meetings flow through the pipeline automatically:

- **"What did the Anthropic team commit to last quarter?"** → agent searches meeting_transcript documents for Anthropic, extracts action items across meetings
- **"Which portfolio companies mentioned churn in their last meeting?"** → signal search across all meeting transcripts for churn-related red flags
- **"Compare what Mercury told us vs. their actual numbers"** → cross-reference meeting transcripts (what they said) with financial data (what happened)
- **"Show me founder sentiment trend for Cursor over the last 6 months"** → time-series of `founder_sentiment.overall` from meeting documents
- **Information asymmetry detection** → flag companies where founders consistently avoid certain topics or only disclose under pressure

The meeting transcript becomes the richest signal source in the portfolio — richer than board decks (which are curated) and richer than monthly updates (which are one-directional).

---

## Open Questions

1. **Enterprise API access** — Do our users have Granola Enterprise plans? If not, we could use the local cache approach (`~/Library/Application Support/Granola/cache-v3.json`) for desktop users, but that's less clean.

2. **Transcript consent** — Some meeting attendees may not know they're being recorded. We should surface this in the UI and let users opt specific meetings out of ingestion.

3. **Granola MCP vs. direct API** — The MCP server gives us search capabilities the API doesn't have. Worth registering both? MCP for agent-driven search, API for bulk sync.

4. **Multi-user** — If multiple team members use Granola, do we merge notes from the same meeting? Or keep separate perspectives? (Different people capture different things.)
