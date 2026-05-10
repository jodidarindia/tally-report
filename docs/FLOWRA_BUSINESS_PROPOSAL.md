# FLOWRA Insights — Business Proposal
**Version 1.0 · February 2026 · Confidential**

---

## 1 · Executive Summary

**FLOWRA Insights** is a Tally-native business intelligence and operations
SaaS purpose-built for Indian SMEs (₹5 Cr – ₹500 Cr turnover). It turns the
data already trapped inside Tally ERP 9 / Tally Prime / Busy ERP into
real-time dashboards, salesman tracking, dispatch terminals, customer
health monitoring, GST-ready CA reports, and automated digests — without
asking the customer to migrate off Tally.

**Why this exists.** India has ~22 lakh active Tally licenses and ~6 lakh
Busy users. ~95% of these run their entire business on a single
accountant's desktop. They have no dashboards, no mobile access for
owners, no salesman visibility, no dispatch tracking, no customer-health
alerts. The data is there — they just can't see it.

**The product.** A web app + Windows agent that:
1. Auto-syncs Tally/Busy data every 20 minutes (no schema migration)
2. Renders dashboards, BI, dispatch terminal, salesman beat plans
3. Provides AI-powered insights (GPT-5.2)
4. Sends WhatsApp/email digests of overdue payments, sales, stock alerts
5. Supports multi-company, multi-user, role-based access

**The opportunity.** Capturing **0.05%** of the Tally + Busy installed
base at our ₹2,499 average ARPU = **₹42 Cr ARR**. Capturing **0.5%** = **₹420
Cr ARR**. The market is large enough that even modest execution funds a
profitable business.

**The ask** (placeholder for investor/partner edition): ₹4 Cr seed at
₹16–20 Cr post-money to fund 24 months of go-to-market: GST/WhatsApp/sync
hardening, a 12-person team, and customer acquisition to 2,000 paying
tenants by month 24.

---

## 2 · The Problem

Indian SMEs run their books on Tally / Busy because their CA insists on
it. But the moment the owner asks "how are we doing?", Tally answers with
500-line reports designed for an accountant, not for a decision-maker.

| Owner question | Reality with Tally alone |
|---|---|
| "How much is overdue from my top 10 customers?" | Run a 4-step report, export to Excel, manually sort |
| "Where is my salesman right now? What did he sell yesterday?" | Phone call. Maybe a WhatsApp screenshot. |
| "Which 20 SKUs are dead inventory?" | Custom report from CA, billed at ₹2,000 |
| "Did the dispatch boy actually deliver invoice 5421?" | Phone call to godown |
| "How does this month compare to same month last year?" | Two reports, side by side, on paper |

These are 5-second questions that take 30 minutes today. **FLOWRA reduces
each to a tap.**

The problem is not that owners don't have data. It is that they cannot
**see** it without phoning their CA. We are not replacing Tally — we are
the dashboard Tally never built.

---

## 3 · The Product

### 3.1 What's already built (Feb 2026)

**18 production-grade modules**, all passing >120 regression tests:

- **Dashboard:** revenue, outstanding, overdue digest, plan distribution
- **Sales:** voucher analytics, customer-level revenue, FY-wise comparison
- **Inventory:** SKU dashboard, fuzzy search, dead-stock & ageing analysis
- **Inventory Analytics:** Pareto A/B/C/D classification, movement velocity
- **CRM:** customer outstanding with FIFO ageing, payment-behaviour scoring
- **Salesman:** targets, achievement %, beat plans, mobile-friendly view
- **Dispatch Terminal:** Kanban tracker (new → in-transit → delivered)
- **CA Corner:** P&L, Balance Sheet, Cash Flow with Tally parity
- **AI Insights:** GPT-5.2 expense narratives & forecasts
- **Insider Result:** BI charts, trend lines, predictive analytics
- **Sync History & Setup:** transparent agent telemetry
- **SuperAdmin Command Center:** customer health, billing, prospects, staff

### 3.2 The Tally Sync Agent (the moat)

A Windows tray application that:
- Reads Tally via XML/TDL — zero footprint on customer's books
- 20-minute auto-sync; first-run full sync, then incremental delta
- Encrypted JWT auth, per-tenant data isolation
- Auto-update channel (planned) so 1,000 agents update overnight
- Single .exe, ~30 MB, runs on a 4 GB Tally workstation

This agent is the **product moat**. Competitors who try to copy us face
6+ months of XML-parsing edge cases (FY changes, voucher type variations,
multi-company, ledger sign conventions). We've already eaten that cost.

### 3.3 Pricing (live)

| Plan | ₹/month | ₹/annual | Companies | Employees | Modules |
|------|--------:|--------:|----------:|---------:|---------|
| Starter | ₹999 | ₹9,990 | 1 | 2 | Dashboard + Sales + Inventory + Sync + Setup |
| **Professional** | **₹2,499** | **₹24,990** | 3 | 5 | + CRM + Analytics |
| **Enterprise** | **₹3,799** | **₹37,990** | 10 | 20 | + Salesman + Dispatch + AI + Insider + CA |

Average revenue per user (ARPU) blended: **₹2,499 / month**.

### 3.4 Roadmap (next 12 months)

| Quarter | Theme |
|---------|-------|
| Q1 (Mar–May 26) | Production hardening: Atlas + DigitalOcean + Sentry + CI/CD |
| Q2 (Jun–Aug 26) | GST Portal integration, WhatsApp BSP integration, Audit logs |
| Q3 (Sep–Nov 26) | Mobile app (React Native), advanced beat/salesman analytics |
| Q4 (Dec 26–Feb 27) | Multi-tenant white-label, partner program for CAs |

---

## 4 · Target Market

### 4.1 Total Addressable Market (TAM) — India only

| Segment | Tally seats | Busy seats | FLOWRA-fit % | Addressable |
|---|---:|---:|---:|---:|
| Manufacturing SMEs (₹5–₹500 Cr) | ~3.5 L | ~1.0 L | 70% | ~3.2 L |
| Distribution / FMCG | ~5.0 L | ~1.5 L | 80% | ~5.2 L |
| Retail chains | ~4.0 L | ~1.0 L | 40% | ~2.0 L |
| Pharma / Chemicals | ~1.0 L | ~0.5 L | 75% | ~1.1 L |
| **Total Indian addressable** | **~13.5 L** | **~4.0 L** | — | **~11.5 L** |

At ₹2,499 ARPU, **TAM = ₹3,450 Cr ARR**. Even capturing **0.05% = 575
tenants = ₹1.7 Cr ARR**. **0.5% = 5,750 tenants = ₹17 Cr ARR**.

### 4.2 Serviceable Addressable Market (SAM)

We narrow to **multi-location SMEs with field salesmen and distribution
operations** — the segment where dashboards + dispatch + salesman tracking
deliver clear ROI:

- ~3.5 L Tally + Busy users in distribution / FMCG / pharma
- Average 2 paid users per company
- **SAM ARR potential: ₹1,050 Cr**

### 4.3 Initial Beachhead (Year 1 focus)

**Maharashtra + Gujarat + Karnataka distribution sector**, 50–500 lakh
turnover. Reasons:
1. Highest density of multi-salesman distribution businesses
2. Existing Tally/Busy adoption ~98%
3. Founder network access
4. WhatsApp-native sales culture (our digest channel)

Targeted 50,000 SMEs in this beachhead. Capturing **2% = 1,000 paying
tenants = ₹3 Cr ARR by month 12**.

### 4.4 Customer Personas

**1. The Owner (decision-maker, primary buyer)**
- 38–55, tier-2/3 city, knows Tally numbers vaguely
- Uses WhatsApp + Excel daily
- Wants: visibility, control, "everything on phone"
- Pays: ₹2,500–₹4,000/month if it saves a CA call

**2. The CA (gatekeeper / influencer)**
- Wants Tally parity (P&L, Balance Sheet, GSTR exports)
- Hates anything that "writes to Tally"
- We are read-only, so we're his ally, not threat
- **Distribution channel:** CA partner programme (Year 2)

**3. The Salesman (daily user, retention driver)**
- 22–40, mobile-first, never logs into desktops
- Wants beat plans, target visibility, easy order-punching
- We win retention if his daily life gets easier

**4. The Dispatch Manager (operational user)**
- 28–45, godown floor, kanban-board mindset
- Wants delivery tracking, invoice-change alerts

---

## 5 · Competitive Landscape

| Player | Type | Where they win | Where we win |
|---|---|---|---|
| **Zoho Books** | Cloud accounting | All-in-one | Customer must migrate off Tally — non-starter for 95% |
| **Vyapar / Marg** | Tally alternative | Mobile billing | Same — replaces Tally |
| **Khatabook / OkCredit** | Khata / receivables | Free tier | No analytics, no inventory, no dispatch |
| **Tally on Cloud** (third-party hosting) | Lift-and-shift | Same UI as Tally | Still no dashboards, no mobile |
| **Custom CA Excel reports** | Manual | Cheap | Slow, error-prone, no real-time |
| **Power BI / Tableau on Tally export** | BI tools | Powerful | Needs IT team; ₹50k+ implementation |

**Our wedge:** we don't ask the customer to change anything. The Tally
agent reads silently in the background. Owner gets dashboards on his
phone in 20 minutes. CA stays on Tally. Nobody is upset.

---

## 6 · Business Model

### 6.1 Revenue model

- **SaaS subscription**, monthly or annual (16% annual discount)
- 14-day free trial, no credit card required
- Trial-to-paid target: 18% (industry SaaS benchmark: 15-22%)
- Monthly churn target: <2% (annual: ~22%)

### 6.2 Unit economics (assumed steady state, year 2)

| Metric | Value |
|---|---:|
| Blended ARPU | ₹2,499 / month |
| Annual revenue per customer | ₹29,988 |
| Gross margin | 78% (after Atlas, DO, BSP, Resend, Emergent LLM costs) |
| CAC (paid + organic blend) | ₹6,500 |
| Payback period | ~3.5 months |
| LTV (5-year, 2% monthly churn) | ₹85,000 |
| **LTV / CAC** | **13×** |

### 6.3 Pricing strategy notes

- ₹999 Starter is a **trojan horse**, not a profit centre — gets the agent
  installed; upgrades happen organically when the team grows
- ₹3,799 Enterprise is **anchored against ₹50k+ Excel/CA bills**, not
  against ₹999 Starter — the customer is comparing us to a CA's monthly
  retainer, not to other SaaS
- Annual prepay (16% discount) drives 30%+ of revenue and cuts churn 40%

---

## 7 · Go-to-Market Strategy

### 7.1 Channel mix (year 1)

| Channel | % of new tenants | CAC | Notes |
|---|---:|---:|---|
| Meta Ads (FB + IG lead forms) | 40% | ₹4,000 | Geo-targeted to MH/GJ/KA, B2B intent |
| WhatsApp organic + referral | 25% | ₹500 | Founder network + early-customer referrals |
| YouTube content (Tally tutorials) | 15% | ₹1,200 | SEO long-tail; "how to see overdue in Tally" |
| CA partner programme | 10% | ₹3,500 | Revenue-share; activates Year 2 |
| Trade shows + Tally events | 5% | ₹8,000 | High-trust but expensive |
| Outbound (cold call + WA) | 5% | ₹6,000 | Reps closing inbound demos |
| **Blended CAC** | 100% | **₹3,200** | Falls to ₹2,400 by month 18 |

### 7.2 Conversion funnel

```
10,000 Meta-ad impressions
    ↓ 4% CTR
   400 lead-form submissions
    ↓ 50% qualification (right industry, right size)
   200 demo calls booked
    ↓ 60% demo → trial activation
   120 free trials
    ↓ 18% trial → paid
    22 paying tenants
```

22 tenants × ₹2,499 = **₹54,978 / month new MRR per ₹50,000 ad spend** —
3.6-month payback at 78% gross margin.

### 7.3 Trial activation playbook

A trial that doesn't get the agent installed in 24 hours is lost. So:

1. Demo call (30 min) → screen-share-installs the agent live
2. Trial day 1: WhatsApp message "your dashboard is ready"
3. Trial day 3: digest with their actual overdue customers
4. Trial day 7: outreach — "shall I send the invoice?"
5. Trial day 12: final outreach + 14-day-grace offer

Expected: **18% activation → paid**, dropping to **8%** if step 1 is
skipped.

---

## 8 · Manpower & Org Plan

### 8.1 Today (Month 0)

- 1 founder-engineer (full-stack)
- 0 sales / support / ops

### 8.2 Month 6 (post-seed, 200 paying tenants)

| Role | Count | Cost (incl. tax + benefits) |
|---|---:|---:|
| Founder/CEO | 1 | ₹0 (deferred) |
| Senior Full-stack Engineer | 1 | ₹2.0 L/mo |
| Junior Full-stack Engineer | 1 | ₹1.0 L/mo |
| QA + Tally-domain Engineer | 1 | ₹0.9 L/mo |
| Sales / Demo Caller | 2 | ₹0.7 L/mo each |
| Customer Success | 1 | ₹0.6 L/mo |
| Content / Marketing | 1 (part-time) | ₹0.4 L/mo |
| **Total monthly burn** | **8 FTE** | **~₹6.3 L/mo** |

### 8.3 Month 12 (1,000 tenants, ₹2.5 Cr ARR)

| Role | Count | Cost |
|---|---:|---:|
| Engineering (Sr FS, Jr FS, Mobile, QA, DevOps) | 5 | ₹6.5 L/mo |
| Sales (Inside Sales lead, 4 callers) | 5 | ₹3.5 L/mo |
| Customer Success (lead + 2 reps) | 3 | ₹2.0 L/mo |
| Marketing / Content | 2 | ₹1.5 L/mo |
| Operations / Finance / HR | 1 | ₹1.0 L/mo |
| **Total monthly burn** | **16 + 1 founder** | **~₹14.5 L/mo** |

### 8.4 Month 24 (2,500 tenants, ₹6.25 Cr ARR)

| Role | Count | Cost |
|---|---:|---:|
| Engineering (incl. Mobile + Data + DevOps) | 10 | ₹14 L/mo |
| Sales (geo-pods MH/GJ/KA + Tier-2 expansion) | 12 | ₹8 L/mo |
| Customer Success | 6 | ₹4 L/mo |
| Marketing | 4 | ₹3 L/mo |
| Operations / Finance / HR | 3 | ₹2.5 L/mo |
| **Total monthly burn** | **35 + founder** | **~₹31.5 L/mo** |

### 8.5 Org chart (Month 24)

```
                       Founder/CEO
                            │
        ┌───────────────────┼─────────────────────┐
        │                   │                     │
    VP Engineering    VP Revenue (Sales+CS)   VP Operations
        │                   │                     │
   ┌────┴────┐          ┌───┴───┐            ┌───┴────┐
  Eng leads     Sales leads  CS leads    Finance / HR /
  (Web, Mobile,  (geo-pods)              Compliance
   Data, DevOps)
```

---

## 9 · Technical Scalability

### 9.1 Current architecture (Feb 2026)

- React frontend (single SPA, ~2 MB gzipped)
- FastAPI backend (Python 3.11, async)
- MongoDB (single instance, will move to Atlas M10)
- Tally Sync Agent (Windows .exe, customer-side)
- Hosted on Emergent for development; production target = DO + Atlas

### 9.2 Scale milestones

| Tenants | Architecture stance | Bottleneck |
|--------:|---|---|
| 100 | Single droplet + Atlas M10, no caching | None — over-provisioned |
| 500 | Add Redis cache layer for dashboards | DB read traffic |
| 2,000 | Atlas M20 + read replica, CDN for static assets | DB write traffic on sync ingest |
| 5,000 | Backend horizontally scaled (3 nodes), queue-based sync ingest (BullMQ/Celery), per-tenant DB sharding | Sync ingest throughput |
| 10,000 | Per-region (MH/GJ/KA) data residency clusters, multi-master DB | Compliance + latency |

### 9.3 Sync ingest throughput

The hottest path is the agent → backend sync. At 2,000 tenants × 20-min
interval × 50,000 vouchers per full sync, peak is ~150 inserts/second
across the cluster — well within MongoDB's headroom. Beyond 5,000 tenants
we move agent uploads to a queue (Cloudflare R2 raw XML drop → async
worker) so the API stays responsive.

### 9.4 Cost-per-tenant at scale

| Tenants | Infra ₹/mo | ₹ per tenant per month |
|--------:|---:|---:|
| 100 | 13,000 | ₹130 |
| 500 | 35,000 | ₹70 |
| 2,000 | 95,000 | ₹47 |
| 10,000 | 4,50,000 | ₹45 |

Hosting cost asymptotes near ~₹45/tenant. Gross margin therefore
**improves with scale**.

### 9.5 Reliability targets

- **99.5%** uptime year 1 (≈3.5 hours downtime/month allowed)
- **99.9%** by year 2 (≈45 min/month)
- RPO (Recovery Point Objective): 1 hour (Atlas continuous backup)
- RTO (Recovery Time Objective): 30 minutes (Docker rebuild + restore)

---

## 10 · Financial Projections (24-month)

### 10.1 Tenant growth

| Month | New tenants | Cumulative paying | Monthly churn | MRR |
|------:|--------:|-------:|---:|-----:|
| 1 | 15 | 15 | 0% | ₹37,485 |
| 3 | 45 | 95 | 1% | ₹2,37,405 |
| 6 | 90 | 280 | 1.5% | ₹6,99,720 |
| 9 | 130 | 580 | 2% | ₹14,49,420 |
| 12 | 175 | 1,000 | 2% | ₹24,99,000 |
| 18 | 220 | 1,750 | 2% | ₹43,73,250 |
| 24 | 250 | 2,500 | 2% | ₹62,47,500 |

### 10.2 Revenue summary

| Period | MRR | ARR | Cumulative revenue |
|---|---:|---:|---:|
| End of Year 1 | ₹25 L | ₹3.0 Cr | ₹1.5 Cr |
| End of Year 2 | ₹62.5 L | ₹7.5 Cr | ₹5.5 Cr |

### 10.3 P&L (₹ in Lakhs)

| Line | Year 1 | Year 2 |
|---|---:|---:|
| **Revenue** | **150** | **550** |
| Hosting infra | (10) | (35) |
| BSP / SMS / WhatsApp | (8) | (25) |
| Payment gateway (2%) | (3) | (11) |
| **Gross profit** | **129** | **479** |
| Salaries & contractors | (110) | (330) |
| Marketing & sales spend | (120) | (200) |
| Office / legal / misc | (20) | (40) |
| **EBITDA** | **(121)** | **(91)** |
| Cumulative loss | (121) | (212) |

Path to EBITDA-positive: **month 30** at current trajectory. Faster if
margin improvements (annual prepay mix, partner channel) hit faster.

### 10.4 Funding required

| Round | Quantum | Use |
|---|---:|---|
| Seed (now) | ₹4 Cr | 24 months runway, hire to 16, build to ₹7.5 Cr ARR |
| Series A (month 24) | ₹15-20 Cr | Mobile app, partner channel, 5x sales, expand to N. India |

### 10.5 Sensitivity analysis

| Scenario | M24 tenants | M24 ARR |
|---|---:|---:|
| Bear: 0.6× plan execution | 1,500 | ₹4.5 Cr |
| **Base: as plan** | **2,500** | **₹7.5 Cr** |
| Bull: 1.4× (CA partner unlocks) | 3,500 | ₹10.5 Cr |

---

## 11 · Two-Year Plan (Quarter by Quarter)

### Year 1

**Q1 (Mar–May 26)** — *Foundation*
- Migrate to MongoDB Atlas + DigitalOcean
- Set up CI/CD, Sentry, BetterStack (per Production Playbook)
- Hire: 1 Senior FS engineer, 1 demo caller
- Target: 50 paying tenants

**Q2 (Jun–Aug 26)** — *GTM ignition*
- Launch GST Portal integration (CA stickiness)
- Launch WhatsApp digest (AiSensy or direct Meta Cloud API)
- Hire: QA, second sales caller, Customer Success
- Target: 250 paying tenants

**Q3 (Sep–Nov 26)** — *Salesman product wedge*
- Mobile-responsive overhaul of Salesman + Dispatch
- Beat plan optimiser
- Hire: Junior FS, marketing/content
- Target: 550 paying tenants

**Q4 (Dec 26–Feb 27)** — *Year 1 close*
- React Native mobile app (alpha)
- Audit log CSV export, advanced filters
- CA partner programme launch (closed beta)
- Target: 1,000 paying tenants, ₹3 Cr ARR

### Year 2

**Q5 (Mar–May 27)** — *Mobile + partner*
- Mobile app GA (Android first, iOS later)
- CA partner programme open
- Code-signing certificate for Tally agent (drops install friction 30%)
- Hire: Mobile lead, DevOps, 2 sales reps
- Target: 1,400 tenants

**Q6 (Jun–Aug 27)** — *Geographic expansion*
- Push to N. India (Delhi, UP, Punjab) + Tamil Nadu
- Localised marketing (Hindi, Tamil)
- Target: 1,800 tenants

**Q7 (Sep–Nov 27)** — *Enterprise tier*
- Multi-company group consolidations
- Custom SSO, API access, white-label option
- Target: 2,200 tenants + first ₹10 Cr ACV enterprise customer

**Q8 (Dec 27–Feb 28)** — *Series A close, scale-out*
- Close ₹15-20 Cr Series A
- Hire-out the org chart in Section 8.4
- Target: 2,500 tenants, ₹7.5 Cr ARR, EBITDA-near-breakeven

---

## 12 · Risks & Mitigations

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| Tally Solutions launches a competing dashboard | High | Medium | We own the read-pipeline + dispatch + salesman product surface they don't care about (Tally focuses on accounting) |
| Customer's Tally version too old to read | Med | Med | Already supports Tally ERP 9 + Prime; agent gracefully degrades |
| Meta WhatsApp policy tightens | Med | Med | Diversify into SMS + email digests; user-initiated WA only |
| MongoDB Atlas cost runaway | Low | Low | Per-tenant cost analysis monthly; sharding playbook ready at 5k tenants |
| Founder bus factor | High | Low | Hire technical co-lead by Month 6; document everything (already doing — see Production Playbook) |
| CAC inflation (Meta ad cost) | Med | High | Diversify to YouTube + organic + CA partner; reduce % via referral |
| GST policy change breaks sync | Med | Med | We're a read-only consumer; we follow Tally's adaptation, not the GSTN's |
| Customer data breach | Catastrophic | Low | Atlas encryption-at-rest + TLS-everywhere + pen-test in Month 4; cyber-liability insurance |

---

## 13 · Why Now (the macro tailwind)

1. **GST + e-invoicing mandate** is forcing every ₹5 Cr+ business to keep
   accurate Tally books. Quality of source data is rising.
2. **DPDP Act** (Indian data privacy law) is making lift-and-shift cloud
   migrations harder — incumbents (Zoho/Marg) lose advantage. We are
   data-residency-friendly: customer's books stay in India.
3. **WhatsApp Business API** maturing in India enables zero-friction
   notifications — was clunky 18 months ago.
4. **Mobile-first owners** in tier-2/3 cities — ~70% of SME owners now
   prefer phone over desktop for daily insights.
5. **Tally Solutions is moving slowly.** Their cloud play "Tally on
   AWS" launched in 2023 but offers no analytics or mobile UX — leaving
   a wedge for us.

The window for this product is **24–36 months**. After that, either we
own the segment or someone else does.

---

## 14 · Why Us (Team & Track Record)

[Founder bio placeholder — to be filled with founder's accountancy/Tally
domain experience, prior ventures, technical credentials, and any early
customers / LOIs.]

**What we have already shipped (Feb 2026):**
- 18 production modules, ~120 pytest regression tests, end-to-end
- Tally Sync Agent v9.8.9 with Day-Book fallback, deployed to early users
- Multi-tenant infrastructure with role-based access (admin / dispatch /
  salesman / employee / super_admin / flowra_staff)
- Comprehensive 18-page Production Operations Playbook (this document's
  sibling)

**What we are building next:**
- Code-signed Windows installer
- WhatsApp BSP integration
- Mobile app (React Native)
- CA partner programme

---

## 15 · The Ask

**₹4 Crore Seed at ₹16-20 Cr post-money**

| Use of funds | Amount | % |
|---|---:|---:|
| Engineering hires (5 FTE × 24 months) | ₹1.6 Cr | 40% |
| Sales + CS hires (8 FTE × 24 months) | ₹1.0 Cr | 25% |
| Marketing & customer acquisition | ₹0.8 Cr | 20% |
| Infra + tooling + compliance | ₹0.2 Cr | 5% |
| Working capital buffer | ₹0.4 Cr | 10% |
| **Total** | **₹4 Cr** | **100%** |

**Milestones funded:**
- Month 12: 1,000 paying tenants, ₹3 Cr ARR
- Month 24: 2,500 paying tenants, ₹7.5 Cr ARR, Series A ready
- Default-alive by Month 30

---

## 16 · Closing

FLOWRA Insights is not a moonshot. It is a **execution play** in a market
where the customer base, the demand, the price-elasticity, and the
distribution channels are all known and proven. The risk is not "will
people pay?" — they already are. The risk is "can we ship and sell fast
enough to win the segment before someone else does?"

We have the product. We have the playbook. We need the team and the
runway.

**— FLOWRA Insights · February 2026**

---

*This document is confidential and is shared on the understanding that it
will not be reproduced or distributed without prior written consent.*
