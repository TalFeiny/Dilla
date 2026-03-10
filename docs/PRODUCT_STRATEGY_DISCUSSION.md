# Product Strategy Discussion — Contract Intelligence & Market Positioning

**Date:** 2026-03-10

---

## Starting Point: Redlining & Contract Analysis

The initial question: should Dilla build redlining / contract comparison capabilities?

**Key reframe:** We're not building a redlining tool. We're building a redline *interpreter*. The redline already happened — lawyers did it. The system takes that delta and answers the CFO's only question: **"what does this cost me?"**

- Input: two sets of terms (documents, manual entry, extracted clauses)
- Engine: clause diff → cascade → stakeholder map → cost of capital (all built)
- Output: a memo — "they changed 4 things, here's what each costs, here's who it favours, here's what to push back on"

The CFO never touches the redline itself. They receive the financial translation. The correct output format isn't a "redline memo" — it's a **deal terms impact memo**. The redline is just one of several inputs (term sheet comparison, amendment review, refinancing proposals — all the same engine, same output).

---

## The Mid-Market CFO Without a GC

Target user: mid-market company, no General Counsel, using external law firms.

**The pain:**
- Lawyers send back documents. It costs £500/hr to ask them what it means
- 40-page facility agreement with tracked changes — no idea which changes matter vs boilerplate
- Asking "what does this covenant change mean?" is a £2,000 phone call answered in legal language, not financial language
- Negotiating blind — lawyers say "market standard" but not what it costs *this specific company* given *their* capital structure and projections

**The value prop:**
The system sits between external lawyers and the CFO. Document comes in → extract and diff → CFO gets plain-language financial impact → calls the lawyer with specific instructions ("push back on Section 4.2, the participation costs us £4.8M at our target exit") instead of open-ended questions ("can you explain what participation means?").

Doesn't replace lawyers. Makes every hour of their time more effective. Catches what lawyers won't flag — because lawyers flag legal risk, not financial cost.

---

## Operational Contracts: The Volume Play

Beyond capital raising, what lands on the CFO's desk weekly:

- **Vendor renewals** — SaaS contracts auto-renewing with buried price escalators across 40+ vendors
- **Customer contracts** — payment terms, liability caps, indemnities, SLA penalties. Sales closes net-90 with unlimited liability because the CFO wasn't in the room
- **Leases** — break clauses, rent reviews, dilapidations. The cost isn't the rent, it's the exit
- **Insurance renewals** — coverage gaps only visible when cross-referenced against accepted indemnities
- **Employment/contractor agreements** — termination costs, IP assignment gaps
- **Partnership/channel agreements** — revenue share, exclusivity, minimum commitments

**The real risk is in the interactions between contracts.** An indemnity to a customer + a vendor's liability cap + an insurance exclusion = an uncovered gap nobody sees because each document was reviewed in isolation.

Capital raising is high-value, low-frequency. Operational contracts are lower-value individually but the aggregate is massive — 200 active contracts, each with 2-3 hidden financial implications = 500+ untracked exposure points.

---

## Competitive Landscape: Legal AI Contract Review

### The 3 Players

1. **Wordsmith AI** — AI-native contract review. London-based, $30M raised (Index Ventures Series A). "First Pass" lets anyone upload a contract for instant risk analysis, markup, key term extraction. $450/user/month. Pre-tuned playbooks, 90% acceptance rate on markups. Word plugin.

2. **Dioptra AI** — Acquired by Icertis (Nov 2025). Surgical redlining and automated playbook creation. Now part of Icertis CLM platform.

3. **Ivo AI** — Contract intelligence with grid/matrix view. Custom AI-generated columns, portfolio-level analysis, AI assistant. Targets enterprise legal teams.

### Legacy CLM Tools
- **Ironclad** — workflow automation, CRM integration, enterprise
- **Icertis** — enterprise CLM, now with Dioptra's AI capabilities
- **LinkSquares** — end-to-end CLM, mid-market/growth-stage

### Adjacent Tools
- **ERPs (NetSuite, Sage Intacct)** — track transactions once entered, don't read contracts
- **Cap table tools (Carta)** — track ownership, don't analyse cost of capital
- **Rillet** — accounting automation, doesn't touch contracts
- **FP&A tools (Runway, Mosaic, Jirav)** — revenue/expense forecasting, no instrument mechanics

### Key Insight: All Legal-First

All 3 players built inside Word — zero workflow change for lawyers. Redlining is literally replacing words, flagging risks, identifying unusual terms against playbooks.

**CLM AI is shallow.** They extract party names, dates, clause types. They can't distinguish broad-based weighted average anti-dilution from full ratchet, let alone compute what each costs. They bolted AI onto document repositories.

**Mid-market companies don't use CLMs.** Ironclad/Icertis sell to enterprises with legal teams. A 50-person company has a shared drive of PDFs. The actual competition is the folder and the spreadsheet.

---

## The Gap: Legal Intelligence vs Financial Intelligence

**What Wordsmith/Ivo/Dioptra tell you:**
"This indemnity clause is broader than market standard. This liability cap is uncapped for IP infringement."

**What they DON'T tell you:**
"This indemnity exposes you to £2M uncovered because your insurance excludes this category, and the uncapped liability creates a contingent obligation that pushes your leverage ratio past your facility covenant at Q3 projections."

They track what's IN the contracts. They don't compute what the contracts COST YOU given your specific financial position.

Nobody is doing financial intelligence on contracts because it requires two things that don't usually coexist: deep financial modelling capability AND document understanding. Legal AI has document understanding without financial depth. FP&A tools have models but don't read instruments.

**Dilla has both.** The capital structure cascade IS the financial model. The extraction layer feeds it.

---

## Decision: Contract Review as a Module, Not the Product

The contract review / redlining functionality is a solved problem (3 well-funded players). The core mechanics (extraction, flagging, comparison) overlap with what Dilla's engine already does.

**Approach:** Add a contract review module — flag risks, unusual terms, deviations. Table stakes feature. Not the selling point. The financial intelligence layer on top is the differentiator — and the reason nobody else can replicate it without building the capital structure engine.

---

## The Workflow Problem

### Where the CFO Lives (Not Word)
- Excel/Sheets — modelling, projections
- Email/Outlook — where documents arrive
- The ERP — where financial reality lives

### The Negotiation Reality
The CFO doesn't sit in the lawyer-to-lawyer negotiation. The email chain insight (reading threads to reconstruct negotiation context) was speculative and may not match reality.

For significant deals — lawyers negotiate directly, CFO gets a summary. For smaller stuff — maybe email, maybe calls. The actual workflow is unclear and building for an assumed workflow is risky.

### Implication
Don't build for the negotiation process. Don't build a Word plugin competing with Wordsmith. The CFO's job isn't the negotiation — it's the **decision**. They get terms (however they arrive) and need to make a call: accept, push back, walk away.

---

## The "Too Narrow" Problem

If the product is only the decision moment ("terms in, financial impact out"), that's maybe 5-10 times/year for a founder, 20-30 for a CFO. Not enough for retention or subscription justification.

Going broad (operational contracts) runs into CLM/legal AI competition. Going deep (capital structure decisions) is too infrequent.

---

## The Answer: Forecasting & Planning

The product isn't backwards-looking ("what do my instruments say") or point-in-time ("what does this term sheet cost"). It's **forwards-looking: "given everything in place, what happens next?"**

- When do I breach my covenants based on projections?
- What does my Series A participation cost at different exit scenarios?
- Where's the cash gap in Q3 given vendor commitments and customer payment terms?
- What does each fundraising structure do to existing stakeholders at projected growth?

### The Real Competitive Position

| Tool | What it does | What it doesn't do |
|------|-------------|-------------------|
| Runway/Mosaic/Jirav | Revenue & expense forecasting | Doesn't understand instrument mechanics |
| Carta | Cap table management | Can't model forward scenarios against full capital structure |
| Anaplan | Enterprise planning | No legal instrument awareness |
| Wordsmith/Ivo | Contract review & risk flagging | No financial modelling |
| Spreadsheets | Everything, badly | No instrument interaction modelling |

**None of them model the interaction between financial instruments and the forecast.** Runway tells you when you run out of cash. It can't tell you when you breach your leverage covenant, what your effective cost of capital is across all instruments, or which stakeholder gets hurt most in a downside scenario.

### Product = Live Capital Structure Model + Planning Engine

Not "upload a document when you need an answer." All instruments in the system, always modelled, always current:
- Covenant headroom right now
- Cap table at different exit valuations right now
- Total contingent liability exposure right now

When a decision moment arrives — new term sheet, refinancing proposal, vendor commitment — drop the new terms into the existing model and instantly see the impact against the actual position. No starting from zero.

**"Abacum + Runway + Carta in one agent"** — not three products stitched together. One planning engine that understands capital structure natively.

### Where Everything Else Fits

The contract review, deal analysis, negotiation prep, covenant monitoring — all inputs and outputs of the planning engine:

- **Contract review module** → extracts terms → feeds the model
- **Deal terms memo** → runs new terms against the model → outputs impact
- **Covenant monitoring** → model + projections → alerts before breach
- **Board reporting** → model outputs → investor-ready summaries
- **Scenario planning** → "what if" against the live model

The planning engine is the product. Everything else is a feature.

---

## Open Questions

1. How much of the forecasting/planning layer is built vs the capital structure analysis side?
2. What's the onboarding path — how does the model get populated initially?
3. Pricing model — is this subscription SaaS, usage-based, or advisory-adjacent?
4. Go-to-market — founders raising capital (acute pain, clear moment) vs CFOs managing ongoing operations (broader, harder to reach)?
5. How does the contract review module integrate — is it V2/V3, or does it need to exist at launch for credibility?
