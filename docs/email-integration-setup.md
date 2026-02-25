# Email Integration Setup — Dilla AI Portfolio Manager

Your fund gets an AI analyst that lives in your inbox. Forward pitch decks, ask portfolio questions, request memos — it replies with full analysis and PDF attachments.

**Stack**: Cloudflare Email Workers (inbound, free) → FastAPI backend → Resend (outbound, free tier)

---

## Architecture

```
partner@fund.com
    │  forwards pitch deck or asks a question
    ▼
acme-capital@dilla.ai
    │  Cloudflare catches inbound email
    ▼
Cloudflare Email Worker (workers/email-inbound/)
    │  Parses email, computes HMAC signature
    │  POSTs structured JSON to backend
    ▼
POST /api/email/inbound
    │  Verifies signature, resolves tenant, checks sender allowlist
    ▼
UnifiedMCPOrchestrator.process_request()
    │  Same brain as the frontend — fetch, score, value, memo, deck
    ▼
EmailComposer
    │  Converts orchestrator output to HTML email + PDF/PNG attachments
    ▼
Resend API
    │  Sends reply from acme-capital@dilla.ai
    ▼
partner@fund.com gets analysis in ~2 minutes
```

---

## Prerequisites

- Cloudflare account with DNS for `dilla.ai` (or your domain)
- Resend account (free tier: 100 emails/day)
- Backend deployed and accessible via HTTPS

---

## Step 1: Resend Setup

### 1.1 Get API Key

1. Go to [resend.com](https://resend.com) → Sign up / Log in
2. Go to **API Keys** → **Create API Key**
3. Copy the key (starts with `re_`)
4. Add to your backend `.env`:

```env
RESEND_API_KEY=re_your_key_here
```

### 1.2 Add Your Domain

1. In Resend dashboard → **Domains** → **Add Domain**
2. Enter `dilla.ai` (or your domain)
3. Resend gives you DNS records to add. Go to Cloudflare DNS and add:

| Type  | Name                          | Value                          | Purpose |
|-------|-------------------------------|--------------------------------|---------|
| TXT   | `@`                           | `v=spf1 include:resend.com ~all` | SPF — authorizes Resend to send |
| CNAME | `resend._domainkey`           | *(from Resend dashboard)*      | DKIM signature 1 |
| CNAME | `resend2._domainkey`          | *(from Resend dashboard)*      | DKIM signature 2 |
| CNAME | `resend3._domainkey`          | *(from Resend dashboard)*      | DKIM signature 3 |

4. Wait for verification (usually 5-30 minutes)

---

## Step 2: Webhook Secret

Generate a shared secret for authenticating the Cloudflare Worker → Backend connection:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to your backend `.env`:

```env
EMAIL_WEBHOOK_SECRET=your_generated_secret_here
EMAIL_FROM_DOMAIN=dilla.ai
```

This same secret goes into the Cloudflare Worker (Step 3).

---

## Step 3: Deploy Cloudflare Email Worker

### 3.1 Install Wrangler (if not already)

```bash
npm install -g wrangler
wrangler login
```

### 3.2 Set Worker Secrets

```bash
cd workers/email-inbound

# Your backend URL (where the worker sends parsed emails)
npx wrangler secret put BACKEND_URL
# Enter: https://api.dilla.ai (or your backend URL)

# Same secret from Step 2
npx wrangler secret put WEBHOOK_SECRET
# Enter: your_generated_secret_here
```

### 3.3 Deploy

```bash
npx wrangler deploy
```

### 3.4 Enable Email Routing

1. Cloudflare Dashboard → your domain → **Email Routing**
2. Click **Enable Email Routing** (Cloudflare auto-configures MX records)
3. Go to **Routing Rules** → **Catch-all address**
4. Set action to **Send to a Worker** → select `dilla-email-inbound`
5. Save

---

## Step 4: Register Your First Tenant

Each fund/user gets their own email address. Register via API:

```bash
curl -X POST https://api.dilla.ai/api/email/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "acme-capital",
    "fund_name": "Acme Capital",
    "allowed_senders": [
      "partner@acmecap.com",
      "analyst@acmecap.com"
    ],
    "fund_context": {
      "fund_size": 260000000,
      "remaining_capital": 109000000,
      "fund_name": "Acme Capital Fund II"
    }
  }'
```

Response:

```json
{
  "status": "registered",
  "slug": "acme-capital",
  "email": "acme-capital@dilla.ai"
}
```

Now `acme-capital@dilla.ai` is live. Only emails from the allowed senders will be processed. All others are silently dropped.

---

## Step 5: Test It

Send an email from an allowed sender address to your tenant email:

```
To: acme-capital@dilla.ai
Subject: Compare Cursor and Anthropic on capital efficiency

What's the revenue multiple and growth rate for each?
Which is a better Series B bet for our fund?
```

You should receive a formatted analysis reply within ~2 minutes.

---

## How It Works

### What You Can Ask

| Use Case | Example Email |
|----------|--------------|
| **Company analysis** | "Analyze Cursor — what's the valuation, growth, and fund fit?" |
| **Comparisons** | "Compare Mercury and Brex on capital efficiency" |
| **IC memo** | "Draft an IC memo for our Anthropic position" |
| **Portfolio questions** | "What's our exposure to healthcare AI?" |
| **Deck generation** | "Build me a deck comparing Toast and Procore" |
| **Forward a pitch deck** | Forward a cold inbound with PDF attachment |
| **Follow-on analysis** | "Should we follow on in Deel's Series D?" |
| **Market sizing** | "What's the TAM for legal document automation?" |

### What You Get Back

- **HTML email body** — formatted analysis with tables, metrics, comparisons
- **PDF attachment** — full investment deck (when deck is requested)
- **PNG attachments** — charts (Sankey, waterfall, probability cloud) that can't render in email

### Email Threading

Replies include `In-Reply-To` and `References` headers, so the conversation threads properly in Gmail/Outlook. Reply to a Dilla email to continue the analysis.

---

## Security Model

| Layer | Implementation |
|-------|---------------|
| **Webhook authentication** | HMAC-SHA256 signature on every request from CF Worker |
| **Sender allowlist** | Per-tenant list — unknown senders silently dropped |
| **No raw email storage** | Emails processed in memory only — never saved to disk/DB |
| **Audit logging** | Who sent, when, what intent — no email content logged |
| **Tenant isolation** | Each tenant's orchestrator context is fully scoped |
| **TLS in transit** | Cloudflare → Backend over HTTPS; Resend sends via TLS |
| **DKIM/SPF** | Outbound emails signed via Resend's DNS records |

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/email/inbound` | Receives emails from Cloudflare Worker |
| `POST` | `/api/email/tenants` | Register a new tenant |
| `GET` | `/api/email/tenants/{slug}` | Get tenant info |
| `GET` | `/api/email/audit` | View email audit log |
| `GET` | `/api/email/health` | Health check — Resend + webhook config status |

---

## Files

```
backend/
├── app/
│   ├── api/endpoints/
│   │   └── email_inbound.py        # FastAPI route — inbound webhook + tenant mgmt
│   ├── core/
│   │   └── config.py               # RESEND_API_KEY, EMAIL_WEBHOOK_SECRET, EMAIL_FROM_DOMAIN
│   └── services/
│       └── email_composer.py        # HTML rendering, Resend sender, tenant registry, audit
├── .env.example                     # Email config template
└── requirements.txt                 # resend>=2.0.0

workers/
└── email-inbound/
    ├── worker.js                    # Cloudflare Email Worker
    └── wrangler.toml                # Deployment config
```

---

## Troubleshooting

### Emails not arriving at backend

1. Check Cloudflare Email Routing is enabled: Dashboard → Email Routing → Status
2. Verify catch-all rule points to the worker: Routing Rules → Catch-all
3. Check worker logs: `npx wrangler tail` (in `workers/email-inbound/`)

### Replies landing in spam

1. Verify domain in Resend dashboard shows "Verified"
2. Check DNS records are correct: Resend dashboard → Domains → your domain
3. SPF and DKIM both need to pass — Resend shows status per record

### "Resend API key not configured"

1. Check `.env` has `RESEND_API_KEY=re_...`
2. Restart backend: the config loads at startup
3. Hit `/api/email/health` to verify

### Emails rejected (silent drop)

1. Check sender is in the tenant's allowlist
2. Check the audit log: `GET /api/email/audit`
3. Common issue: email address casing — allowlist comparison is case-insensitive

### Backend webhook signature fails

1. Ensure `EMAIL_WEBHOOK_SECRET` in `.env` matches `WEBHOOK_SECRET` in Cloudflare Worker
2. Re-set the worker secret: `npx wrangler secret put WEBHOOK_SECRET`
3. Redeploy worker: `npx wrangler deploy`

---

## Cost

| Service | Free Tier | Paid |
|---------|-----------|------|
| Cloudflare Email Routing | Free | Free |
| Cloudflare Workers | 100K requests/day | $5/mo unlimited |
| Resend | 100 emails/day, 1 domain | $20/mo for 50K emails |
| **Total at launch** | **$0** | |
