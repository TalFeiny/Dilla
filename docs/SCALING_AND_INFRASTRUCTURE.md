# Dilla AI — Scaling & Infrastructure

## What We Ship Today

Single Railway container, 1 Gunicorn worker, Supabase Postgres, Vercel frontend.
Works for 1-2 concurrent users. Breaks at 5+.

---

## What Just Changed (CSV Upload State)

The P&L CSV upload pipeline now shows the same state as the document upload pipeline:

| Stage | Documents | CSV (before) | CSV (now) |
|-------|-----------|--------------|-----------|
| Upload start | Cell spinner: "Uploading file.pdf..." | Menu button spinner | Cell spinner: "Uploading data.csv..." |
| Processing | Chat: "document.extract running" | Nothing | Cell: "Cleaning & matching rows..." |
| Success | Cell: green check, Chat: "document.extract success" | Toast (gone in 5s) | Cell: "45 rows → 3 periods", Chat: full mapping report |
| Error | Cell: red alert (6s), Chat: error detail | Toast error (gone) | Cell: red alert (6s), Chat: error detail |
| Detail | None | None | Chat shows: periods, categories, subcategories created, unmapped labels, skipped computed rows, warnings |

**Files changed:**
- `frontend/src/components/matrix/UnifiedMatrix.tsx` — `handlePnlCsvUpload` now uses `setCellActionStatus` + `onToolCallLog`
- `frontend/src/components/agent/AgentChat.tsx` — Added `FileSpreadsheet` icon for `pnl.upload_csv`, explanation text renders inline on success entries

---

## Current Architecture

```
User → Vercel (Next.js) → Railway (1 container) → LLM APIs
                                    ↓
                              Supabase Postgres
```

### The Single Container

`Dockerfile.prod` runs:
```
gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --workers 1
```

One Python process. One event loop. Every request from every user shares:
- 1 `ModelRouter` singleton (rate limits, circuit breakers, concurrency slots)
- 1 `UnifiedMCPOrchestrator` singleton (the CFO brain)
- 1 database connection pool (2-20 connections)

### What Happens With 7 Concurrent Users

A typical CFO request (e.g., "analyze this company's P&L") triggers:

1. **Intent classification** → 1 LLM call (trivial tier: Haiku/Gemini Flash)
2. **Plan generation** → 1 LLM call (quality tier: Claude Sonnet)
3. **2-4 skill executions** → 2-4 LLM calls each (cheap/quality tier)
4. **Synthesis** → 1 LLM call (premium tier: Sonnet/GPT-5.2)

That's ~5-8 LLM calls per user request. With 7 users: **35-56 concurrent LLM calls**.

**Where it breaks:**

| Bottleneck | Current Limit | What Happens |
|-----------|---------------|--------------|
| Gunicorn workers | 1 | All 7 users share 1 event loop. CPU-bound work (JSON parsing, data transforms) blocks everyone. |
| Claude Sonnet concurrency | 3 slots | Users 4-7 poll-wait at `_wait_for_slot()` with 0.1s→1s backoff until a slot opens |
| Claude rate limit | 0.5s between calls | Sequential 0.5s gaps mean max ~120 Claude calls/min across all users |
| Per-request budget | $2.00, 500K tokens | Individual requests are capped, but 7×$2 = $14/min worst case |
| Anthropic API rate limits | Varies by tier | Tier 1: 50 req/min, 40K input tokens/min. 7 users blow through this. |

**The real killer is Anthropic API rate limits, not our code.** At Tier 1, you get 50 requests/minute. Each user needs 5-8 calls. 7 users = 35-56 calls/minute = right at the edge.

---

## Inference Provider Strategy

### What We Have

11 models across 7 providers, tiered by task:

| Tier | Use Case | Primary → Fallback |
|------|----------|-------------------|
| TRIVIAL | Intent classification, routing, yes/no | Haiku → Gemini Flash → GPT-5-mini → Mixtral |
| CHEAP | Extraction, enrichment, gap filling | GPT-5-mini → Haiku → Gemini Flash → Sonnet |
| QUALITY | Analysis, narratives, reasoning, document extraction | Claude Sonnet → Gemini Pro → GPT-5-mini |
| PREMIUM | Memo generation, final synthesis | Claude Sonnet → GPT-5.2 → Gemini Pro |

### Do We Need All These Providers?

**Minimum viable (2 providers):** Anthropic + one cheap fallback (OpenAI or Google)
- Anthropic handles quality/premium work
- Cheap provider handles trivial/bulk extraction
- Fallback when Anthropic rate-limits

**Recommended (3 providers):** Anthropic + OpenAI + Google
- Anthropic: quality/premium (the brain)
- OpenAI GPT-5-mini: cheap bulk work
- Gemini Flash: trivial classification (cheapest, fastest)
- Each can failover to the others

**Groq/Together/Ollama:** Nice to have but not critical. Groq is good for ultra-low-latency trivial tasks. Together/Ollama are insurance.

### What Actually Matters for 7 Users

The tier system already routes lightweight work to cheap models. The problem is **all 7 users competing for the same Anthropic rate limit** for quality/premium calls.

**Fix:** Raise Anthropic API tier. At Tier 2+ you get 2,000 req/min and 200K input tokens/min — 40x headroom.

---

## What Needs to Change (In Order)

### Phase 1: Unblock 7 Users (No New Infra)

These are config changes, not architecture changes:

**1. Increase Gunicorn workers to 2-4**
```dockerfile
# Dockerfile.prod
CMD gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
```
4 workers = 4 event loops = 4x throughput for CPU-bound work.
BUT: Each worker gets its own `ModelRouter` instance with its own concurrency tracking. This means the per-model concurrency limits multiply (3 slots × 4 workers = 12 concurrent Claude calls). This is actually fine for throughput but means you need higher Anthropic API tier.

**2. Raise Claude concurrency slots**
```python
# model_router.py line 157-168
"claude-sonnet-4-6": 5,   # was 3
"claude-haiku-4-5": 12,   # was 8
```

**3. Raise Anthropic API tier**
Apply for Tier 2+. This is the single highest-leverage change for concurrent users.

**4. Drop rate limit delays**
```python
# model_router.py line 1137-1146
"claude-sonnet-4-6": 0.2,   # was 0.5 — trust the API to rate-limit us
"claude-haiku-4-5": 0.05,   # was 0.15
```

### Phase 2: Add Redis (Coordination Layer)

Redis solves: shared state across workers, job persistence, request caching.

**What moves to Redis:**

| State | Current | Redis Key Pattern | TTL |
|-------|---------|-------------------|-----|
| Batch search jobs | `_batch_search_jobs` dict in `mcp.py` | `batch_job:{id}` | 1hr |
| Xero OAuth CSRF | `_pending_states` dict in `xero_integration.py` | `xero_oauth:{token}` | 10min |
| Deck PDF cache | `_storage` dict in `deck_storage_service.py` | `deck:{id}` | 5min |
| Model request cache | `request_cache` dict in `model_router.py` | `llm_cache:{hash}` | 5min |

**What stays in-memory (per-worker, and that's fine):**
- Circuit breaker state — each worker tracks its own provider health. If Anthropic is down, all workers discover it independently within seconds.
- Concurrency slots — per-worker tracking is actually better than shared. Shared Redis-based slots add latency to every LLM call.
- Rate limit timestamps — same reasoning. Per-worker is simpler and sufficient.

**Redis setup:**
- Railway Redis add-on ($5/mo) or Upstash Redis (free tier: 10K commands/day)
- Already have `redis==5.0.1` in requirements.txt
- Already have `REDIS_URL` in config.py
- `redis_client.py` already written in `backend/app/core/` — falls back to in-memory when no REDIS_URL

### Phase 3: Async Job Queue (For Heavy Operations)

Celery is configured (`celery_app.py`) but not deployed on Railway. The Celery tasks exist for:
- PWERM analysis
- Document processing
- Market research
- Company history

**When this matters:** When a single request takes >30 seconds. The CFO brain can trigger valuations, multi-company analysis, memo generation — these can take 60-120 seconds. With 7 users, a 120s request blocks a Gunicorn worker for 2 minutes.

**Solution:** Move long-running operations to Celery workers. Railway can run a separate Celery worker container using the same codebase:
```
# Worker container
celery -A app.core.celery_app worker --loglevel=info --queues=analysis,documents
```

This requires Redis (Phase 2) as the broker.

### Phase 4: Horizontal Scaling

When Phase 1-3 aren't enough (20+ concurrent users):

- Railway auto-scaling: Multiple API containers behind Railway's load balancer
- Redis becomes mandatory for shared state
- Database connection pool sizing: Each worker opens 2-20 connections. 4 workers × 3 containers = up to 240 connections to Supabase. May need pgBouncer.
- CDN/edge caching for static API responses (company metadata, taxonomy lookups)

---

## Cost Model

### Per-Request Cost

| Tier | Model | Input Cost/1K | Output Cost/1K | Typical Tokens | Cost |
|------|-------|--------------|----------------|----------------|------|
| TRIVIAL | Haiku | $0.001 | $0.005 | 500 in / 100 out | $0.001 |
| CHEAP | GPT-5-mini | $0.00025 | $0.002 | 2K in / 500 out | $0.002 |
| QUALITY | Claude Sonnet | $0.003 | $0.015 | 5K in / 2K out | $0.045 |
| PREMIUM | Claude Sonnet | $0.003 | $0.015 | 8K in / 3K out | $0.069 |

Typical CFO request (intent + plan + 3 skills + synthesis):
- 1 trivial ($0.001) + 1 quality ($0.045) + 3 cheap ($0.006) + 1 premium ($0.069) = **~$0.12/request**

7 users × 10 requests/hour = 70 requests/hour = **~$8.40/hour**

Budget cap per request: $2.00 (hard limit in `RequestBudget`).

### Monthly Estimates

| Users | Requests/Day | LLM Cost/Day | LLM Cost/Month | Infra/Month |
|-------|-------------|-------------|---------------|-------------|
| 1-2 | 50 | $6 | $180 | Railway $5 + Supabase $25 = $30 |
| 7 | 350 | $42 | $1,260 | Railway $20 + Redis $5 + Supabase $25 = $50 |
| 20 | 1,000 | $120 | $3,600 | Railway $50 + Redis $10 + Supabase $75 = $135 |

LLM costs dominate. Infrastructure is cheap. The tier routing system is doing its job — most calls hit cheap/trivial models.

---

## What's Actually Blocking You Right Now

Not Redis. Not scaling. Not infrastructure.

1. **Data ingestion UX** — CSV upload now has proper state (just built). Document upload already works. But the first-mile experience of getting a company's data into the matrix is still friction-heavy.

2. **The cleaning pipeline is backend-only** — `fpa_query.py` has 3-pass cleaning (header cleaning, label matching, hierarchy detection, fuzzy fallback, computed row skipping). The frontend now surfaces what happened, but the backend response needs to include all the detail (`mapped_categories`, `skipped_rows`, `warnings`). Verify the backend actually returns these fields.

3. **Anthropic API tier** — If you're on Tier 1, 7 concurrent users will rate-limit. This is a billing/account change, not a code change.

---

## Decision Points

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Redis provider | Railway add-on / Upstash / Skip for now | Skip until Phase 2. In-memory is fine for <5 users. |
| Gunicorn workers | 1 / 2 / 4 | Change to 4. Zero-risk, immediate throughput gain. |
| Anthropic tier | Stay Tier 1 / Apply for Tier 2 | Apply now. Highest leverage for concurrent users. |
| Celery deployment | Skip / Deploy worker container | Skip until requests routinely timeout at 120s. |
| Multiple providers | Anthropic only / +OpenAI / +Google | Anthropic + OpenAI minimum. Google nice-to-have. |
