# Sathyabama_Hackathon

<!-- Existing content above is preserved; the backend section below documents
     Levels 2-4. The file was re-saved as UTF-8 (it was UTF-16) so both the
     frontend and backend sections stay readable in one document. -->

## PRAHARI backend - Levels 2, 3 and 4

PRAHARI scores a job posting for fraud risk across four levels. **Level 1
(poster / text analysis) is a separate teammate module.** This backend
implements the three levels that verify the world outside the advert:

| Level | What it does |
| --- | --- |
| **Level 2 - Company background** | Verifies the employer exists: job location, public footprint, website (WHOIS age, reachability, typosquat), customer-care contact, and recruiter email (domain match, free-mail, MX). |
| **Level 3 - The opportunity** | Verifies the vacancy: cross-posting on other job platforms, presence on the official careers page, payment demanded inside the application flow, and the shape of the selection process. |
| **Level 4 - External evidence** | Verifies what others say: public scam/fraud/complaint reports and employer-review footprint, plus listing freshness and recycled-posting detection. |

Scoring is **deterministic**. Groq is called once at the end only to phrase the
finished result in plain English; it never decides a number, and if it fails the
service falls back to a template summary.

### How Level 1 and Level 3.3 stay separate

Level 1 scans the **raw posting text** for payment *language* ("registration
fee", "refundable deposit"). Level 3.3 looks for a payment *instrument or
instruction in the application flow*: a UPI VPA, IFSC/bank account, QR request,
or a payment-gateway collect link, plus fee wording served by the application
URL itself. The split is enforced in code, so the same sentence is never counted
twice across levels.

### Score direction

The candidate-facing number is `risk_score`: **0-100, higher = riskier**, which
is the direction the dashboard already uses. Internally each level holds its
mirror, a `level_score` that starts at 100 and loses points, so every response
carries both and nothing has to be inverted in the UI.

Bands: `0-24 LOW`, `25-49 MEDIUM`, `50-74 HIGH`, `75-100 CRITICAL`.

### Priority-driven scoring

Every check declares a priority tier, and the tier sets how many points a
failure removes:

| Priority | Points | Examples |
| --- | --- | --- |
| `critical` | 45 | payment instrument in the application flow, international contact on an India-based role, public fraud reports |
| `high` | 22 | domain age, recruiter email domain mismatch, free-mail HR, MX records, cross-platform contradiction |
| `medium` | 14 | job location, website content match, careers page, selection-process phrases, repost pattern |
| `low` | 8 | public contact match, review-site presence, listing age |

A warning charges 45% of the tier, a pass and an unavailable charge nothing, and
the whole charge is scaled by the check's confidence. `l3_payment_instrument` is
the one deliberate override at 60 points, so a confirmed payee handle sinks its
level on its own.

### Why is this risky? The breakdown

Every response makes the basis of the score inspectable rather than asking
anyone to trust a number:

* `EvidenceItem.priority` and `.points` - what each check was allowed to matter
  and what it actually cost;
* `LevelReport.contributors` - that level's drivers, worst first, each with its
  share as a percentage;
* `LevelReport.basis` - one line, e.g. *"10 checks: 1 passed, 5 failed, 2 warned,
  2 unavailable. 100 of 100 points deducted, led by Contact Number Country Code
  (critical, -45)"*;
* `FinalVerdict.level_breakdown` - per level: its weight, score, share of the
  final risk and its basis line.

### The final verdict: Level 1 + Levels 2-4

`POST /api/verify/final` produces the single number a candidate sees. Level 1
(the teammate's poster/text analysis) is weighted **40%** and Levels 2-4 **60%**,
because a scammer writes their own advert but does not control WHOIS, DNS, job
boards or public complaints. Inside that 60%, Level 2 takes 40%, Level 3 35% and
Level 4 25%.

Level 1 hands over a `Level1Report`: either score field (`risk_score` higher =
riskier, or `level_score` lower = riskier) plus its `flags`. With no score at all
the score is derived from the flags using the same priority table above, so a
half-built Level 1 still merges. The endpoint also accepts the shape already in
`frontend/src/data/mockJobData.js` (`score` + `riskFactors` with upper-case
severities) and converts it.

Omit `level1` entirely and the verdict runs on Levels 2-4 alone: its 40% is
redistributed rather than treated as a pass, and `level1_included` says so.

```bash
curl -s -X POST http://127.0.0.1:8000/api/verify/final -H "Content-Type: application/json" -d '{"claims":{"company_name":"Apex Global Innovators Inc.","job_title":"Junior Data Entry Assistant","location":"Remote (Pan India)","salary":"Rs 85,000 per month","recruiter_email":"jobsoffers2026.apex@gmail.com","recruiter_phone":"+44 7911 123456","website_url":"https://apex-global-innovators.site","posting_text":"No interview needed. Instant selection. Deposit a refundable registration fee of Rs 1,500 to UPI ID apexhr2026@okaxis. Contact us on WhatsApp at +44 7911 123456. Join immediately after payment."},"level1":{"score":74,"riskFactors":[{"id":"upfront_payment","title":"Upfront Payment","severity":"CRITICAL","evidence":"registration fee of Rs 1,500"}]}}'
```

Returns `risk_score`, `safety_score`, `band`, `band_label`, `recommendation`,
`contributors`, `level_breakdown`, `weights_used`, `hard_floors_applied`,
`low_confidence`, `level1_included`, `summary` and the four `LevelReport`s.

### Running it

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
cp .env.example .env          # optional: add GROQ_API_KEY for LLM-written summaries
uvicorn app.main:app --reload
```

Interactive docs: <http://127.0.0.1:8000/docs>

### Example request

```bash
curl -s -X POST http://127.0.0.1:8000/api/verify/company-opportunity -H "Content-Type: application/json" -d '{"company_name":"Apex Global Innovators Inc.","job_title":"Junior Data Entry Assistant","location":"Remote (Pan India)","salary":"Rs 85,000 per month","recruiter_email":"jobsoffers2026.apex@gmail.com","recruiter_phone":"+44 7911 123456","website_url":"https://apex-global-innovators.site","posting_text":"No interview needed. Instant selection. Deposit a refundable registration fee of Rs 1,500 to UPI ID apexhr2026@okaxis. Contact us on WhatsApp at +44 7911 123456. Join immediately after payment."}'
```

The response contains `level2`, `level3`, `level4` (each a `LevelReport` with its
own evidence list), `combined_score`, `combined_risk_score`, `combined_summary`,
`hard_floors_applied`, `low_confidence` and `processing_time_ms`.

### Health check

```bash
curl -s http://127.0.0.1:8000/api/verify/health
```

Probes outbound HTTP, DuckDuckGo search, WHOIS, DNS and whether a Groq key is
configured, and reports `degraded` when any of them is unreachable. Useful
before a live demo: verification keeps working when these are down, it just
reports more checks as `unavailable`.

### Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | No | Groq key for the plain-English summary. Without it, summaries are template-generated. |
| `GROQ_MODEL` | No | Groq model id (default `llama-3.3-70b-versatile`). |
| `CORS_ALLOW_ORIGINS` | No | Extra comma-separated origins; `http://localhost:5173` is allowed already. |
| `LOG_LEVEL` | No | `DEBUG` / `INFO` / `WARNING` (default `INFO`). |
| `PRAHARI_SEARCH_TIMEOUT` | No | Seconds per web search (default 8). |
| `PRAHARI_FETCH_TIMEOUT` | No | Seconds per HTTP fetch (default 5). |
| `PRAHARI_CHECK_TIMEOUT` | No | Seconds per check, i.e. per wave (default 9). |

No keys are hardcoded anywhere. See `backend/.env.example`.

### The shared contract

Level 1 produces `ExtractedClaims`; Levels 2-4 consume it and never recompute
its signals. Both live in `backend/app/core/schemas.py`:

```python
ExtractedClaims(company_name, job_title, location, salary, recruiter_name,
                recruiter_email, recruiter_phone, website_url, posting_text,
                application_url)

EvidenceItem(level, check_id, label, status, finding, raw_data, risk_weight,
             confidence)   # status: pass | warning | fail | unavailable

LevelReport(level, checks_run, checks_passed, checks_failed, checks_warning,
            checks_unavailable, evidence, level_score, degraded)
```

### Check registry

The 11 checks below emit 20 fixed evidence items, plus one extra item per
matched selection-process phrase (a check that measures several independent
things emits one item per thing, so nothing is blended):

| Check | Evidence ids |
| --- | --- |
| 2.1 Job location | `l2_location` |
| 2.2 Company existence | `l2_company_existence` |
| 2.3 Official website | `l2_domain_age`, `l2_website_live`, `l2_domain_name_match` |
| 2.4 Official contact | `l2_contact_intl_prefix`, `l2_contact_public_match` |
| 2.5 HR email | `l2_email_domain_match`, `l2_email_free_provider`, `l2_email_mx` |
| 3.1 Other job platforms | `l3_cross_platform_presence`, `l3_cross_platform_consistency` |
| 3.2 Official careers page | `l3_careers_page` |
| 3.3 Payment in application flow | `l3_payment_instrument`, `l3_payment_gateway_link`, `l3_payment_flow_instruction` |
| 3.4 Selection process | `l3_process_*` (one per matched phrase) |
| 4.1 Reviews and complaints | `l4_fraud_mentions`, `l4_review_presence` |
| 4.2 Freshness and reposting | `l4_repost_pattern`, `l4_listing_age` |

### Hard floors

Applied after weighted scoring; a strong showing elsewhere cannot lift them:

| Condition | Maximum score |
| --- | --- |
| Payment instrument confirmed in the application flow (3.3) | 15 |
| Domain under 30 days old **and** recruiter email mismatch (2.3 + 2.5) | 25 |
| International contact number on an unverified company (2.4) | 30 |

### Graceful degradation

Every external call has a 6-second timeout and one retry, and every check
catches its own failures. A dead lookup becomes `status="unavailable"` with
`confidence=0.0` and costs the posting **no** points - "we could not check" is
never scored as guilt. With every lookup dead the endpoint still returns a valid
response built from the offline rule-based checks, flagged `low_confidence`.

### Speed

A full run is roughly **8 seconds**. Checks do not run level by level: they run
in two waves, everything independent at once, then the one or two checks that
genuinely need an earlier result (`l4_repost_pattern` reuses Level 3.1's
listings; the careers check waits only when the posting gave no website). One
search cache is shared per request, each level's searches were collapsed to a
single query, and WHOIS runs alongside the page fetch instead of before it.

Budgets are env-tunable, because venue wifi decides how much evidence fits:

| Variable | Default | Meaning |
| --- | --- | --- |
| `PRAHARI_SEARCH_TIMEOUT` | 8s | hard ceiling on one web search |
| `PRAHARI_FETCH_TIMEOUT` | 5s | hard ceiling on one HTTP fetch |
| `PRAHARI_CHECK_TIMEOUT` | 9s | ceiling on one check, and so on a whole wave |

Raise them on a good connection to convert `unavailable` checks into real
evidence; lower them for a faster, thinner run.

### Tuning

Priorities, the points each tier is worth, level weightings, the 40/60 split
with Level 1, the risk bands and the hard-floor ceilings all live in one place:
`backend/app/core/scoring.py`. Change a check's tier and its weight, its
breakdown percentage and its severity badge all follow.

### Tests

```bash
cd backend
.venv/Scripts/python -m pytest
```

131 tests, all offline: every search, HTTP fetch, WHOIS and DNS call is patched,
so the suite passes with the network unplugged. They cover each check in
isolation, the hard floors, the Level 1 / Level 3.3 boundary, and a fully
offline end-to-end run through the API.
