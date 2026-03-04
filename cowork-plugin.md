# LegalForensics Cowork Plugin

## Overview

The LegalForensics Cowork plugin connects Claude to the LegalForensics contract analysis platform via MCP (Model Context Protocol). Users can analyze contracts, get risk assessments, and receive decision guidance directly inside Claude conversations.

---

## What's Remaining Before Marketplace Submission

### Features to build
- [ ] **Render upgrade** — upgrade MCP server to paid plan ($7/mo starter); free tier sleeps after inactivity which breaks the plugin

### Deploy pending changes
- [x] **lf-nextgen-services** — refund endpoint committed and deployed to EC2 ✅
- [x] **lf-cowork-plugin** — `server.py` + `plugin.json` merged to `main` and deployed to Render ✅
- [ ] **lf-nextgen-ui** — commit + deploy uncommitted changes on `stripe` branch: plugin-landing payment banner, decision-brief fix, nginx.conf no-cache rule for `index.html`

### Testing to complete
See the **Testing** section below for the full structured test plan.

### Done ✅
- Stripe integration — `plugin_credits` + `stripe_payments` tables, 4 endpoints, credit gate on `upload_contract`, 1 free credit on signup, last-credit warning, idempotent webhook
- Auto-refund on failure — credit deducted upfront; auto-refunded if upload or processing fails; `POST /api/stripe/credits/refund` endpoint added to backend
- `upload_contract` MCP tool — text paste and URL, polls until ready, returns `contract_id`
- `.txt` file extraction fix in backend
- Login page — SSO only for subscription users, no email/password confusion
- `/plugin` landing page — separate signup flow for plugin users, payment success banner on return from Stripe
- Plugin user isolation — each signup gets own company, `user_type` in DB
- API key auth (`X-LF-API-Key`) wired end-to-end through MCP → backend
- `get_analysis_report` and `get_decision_guidance` tested via Python MCP client
- `plugin.json` — homepage set to `https://app.legalforensics.ai/plugin`
- CloudFront caching fix — nginx `index.html` no-cache rule added; future deploys no longer need manual cache invalidation

---

## User Journey

### 1. Discovery — Claude Marketplace
- User opens the Cowork/plugins marketplace in Claude
- Finds the **LegalForensics** listing
- Clicks **Connect** → marketplace shows the API key config field
- Instructions direct the user to `app.legalforensics.ai/plugin`

### 2. Signup at `/plugin`
- User visits `https://app.legalforensics.ai/plugin`
- Fills in name, email, company name, industry, password
- Verifies email via confirmation code
- **API key is auto-created and shown immediately** — user copies it
- Returns to Claude, pastes the key into the plugin config field
- Plugin is connected — no dashboard navigation required

### 3. Using the Plugin in Claude
- User asks Claude to analyze a contract
- Claude calls the MCP tools: `list_contracts` → `get_analysis_report` etc.
- Results appear inline in the conversation

---

---

## User Types

| | LF Subscription Users | Cowork Plugin Users |
|---|---|---|
| Entry point | `app.legalforensics.ai` (SSO or email) | `app.legalforensics.ai/plugin` |
| Auth | SSO or email/password | Email/password only |
| Post-login | LF Dashboard | API key shown immediately |
| `user_type` in DB | `subscription` | `plugin` |
| API key | Manual (via key icon in header) | Auto-created on signup |
| Dashboard access | Full LF app | Optional (link at bottom of plugin page) |
| Billing | LF subscription | Pay-per-contract via Stripe |

---

## Architecture

### MCP Server
- **URL:** `https://lf-cowork-plugin.onrender.com`
- **Transport:** `streamable-http`
- **Auth:** `X-LF-API-Key` header — user configures their key in Claude plugin settings
- **Deployed on:** Render (starter plan, `render.yaml`)
- **Backend:** Proxies to `https://app.legalforensics.ai/api`

### Auth Flow
```
Claude (Cowork) → MCP server (Render) → X-LF-API-Key header → LF backend → SHA-256 hash lookup → user context
```

### API Key Format
- Format: `lf_<40 hex chars>`
- Only SHA-256 hash stored in DB — plain key shown once at creation
- Table: `api_keys`, linked to `user.id` and `company.id`

---

## MCP Tools (9 total)

| Tool | Description |
|---|---|
| `list_contracts` | List all contracts, optionally filtered by keyword |
| `get_analysis_report` | Full AI risk analysis: posture, top risks, exposure bands |
| `get_decision_guidance` | Decision brief: sign, negotiate, or walk away |
| `get_narrative_walkthrough` | Plain-English explanation of the contract |
| `run_standards_review` | Check against company negotiation playbook |
| `set_perspective` | Re-analyze from a specific party's perspective |
| `get_clause_details` | Deep dive on a single clause with AI rewrite |
| `explain_clause` | Analyze pasted clause text without uploading a contract |
| `upload_contract` | Upload a contract via URL or pasted text; polls until done and returns `contract_id` |

### `upload_contract` — details

Accepts **either** a direct download URL **or** raw pasted text — not both.

```
file_url      Direct download URL (PDF, DOCX, DOC, TXT). Must return the file directly
              e.g. Dropbox ?dl=1 link, S3 pre-signed URL, direct PDF URL.

text_content  Raw contract text pasted into the conversation. Uploaded as .txt.

title         Optional display title (defaults to filename or "contract").
contract_type Optional type override e.g. "NDA", "SaaS Agreement". LF auto-classifies if omitted.
```

On success returns `contract_id` — use it directly with any analysis tool in the same conversation.

---

## Stripe / Pricing

### Pricing Q&A

**Q: Should different contract types be priced differently?**
Possible but creates complexity — multiple SKUs in Stripe, classification logic before charging, harder to explain to users. Start uniform. Can introduce tiering later once you know which contract types drive the most value.
_Decision: uniform pricing for now_

**Q: Will I get locked in to a price?**
No. Stripe lets you change prices any time. Existing users on a purchase aren't affected (they already paid). New purchases use the new price. You can also run discount codes without changing the base price.
_Decision: TBD_

**Q: What to give free initially?**
Standard approach: 1 free contract on signup. Enough to experience the full value, not enough to abuse. Can be implemented as 1 free credit added at registration.
_Decision: TBD — 1 free contract on signup?_

**Q: Can I use existing Stripe keys (pk_live for legalforensics-lite)?**
Yes. Same Stripe account, same keys. Just create a new Product/Price for the plugin in the same Stripe dashboard. Keeps billing consolidated. Webhooks can be shared too (route by product).
_Decision: yes, reuse existing Stripe account_

**Q: Should I issue refunds?**
Stripe makes refunds easy (one click in dashboard). Policy suggestion: refund if analysis fails or errors out, no refund if analysis completes even if user didn't like the result. Handle failed analyses automatically in the webhook/credit logic.
_Decision: Yes — auto-refund if upload or processing fails. Credit deducted upfront; `POST /api/stripe/credits/refund` called automatically by MCP server on failure. Manual refunds (Stripe dashboard) for exceptional cases._

**Q: What about discounts?**
Stripe Checkout supports promo codes natively — just enable it on the Checkout session. No extra code needed. Good for launch outreach ("use code EARLYBIRD").
_Decision: enable promo codes on Checkout_

---

**Questions still to answer**

| Question | Answer |
|---|---|
| Who is the target plugin user? | Anyone — freelancer, writer, rental tenant, in-house counsel, lawyer, startup founder. Not optimised for all verticals yet but extensible. |
| What would they pay a lawyer for the same insight? | Most individuals never go to a lawyer at all. Businesses go for some contracts, not others. Lawyers charge $500+/hr. So even $10-20 is a dramatic saving vs the alternative. |
| What does one analysis cost you in LLM tokens/compute? | See cost estimate below — approx $0.15–0.30 per contract. |
| One-time buyers or repeat customers? | Mix, but encourage repeat. Plugin subscriptions kept separate from LF subscriptions for now. |
| Grow volume first or margin first at launch? | Volume first. |
| Free tier permanently or just a launch promo? | Permanent free tier (1 contract). Strategy: expand to multiple plugins and build user base across them. |
| Ever want a monthly unlimited plugin subscription? | Possibly — revisit later. |
| When free credit runs out — hard wall or warning first? | Warning first — nobody likes being surprised. Show remaining credits and a heads-up before they hit zero. |
| Price point per contract? | See pricing recommendation below. |

---

### Cost estimate per contract

Assumes Claude Sonnet for analysis, average contract ~10 pages (~7,000 tokens).

| Item | Tokens | Cost |
|---|---|---|
| Input per analysis call (contract + prompt) | ~8,000 | ~$0.024 |
| Output per analysis call | ~1,500 | ~$0.023 |
| Calls per contract (risk + decision + narrative) | 3 | × 3 |
| LLM subtotal | | ~$0.14 |
| S3 storage + Render compute overhead | | ~$0.05 |
| **Total per contract** | | **~$0.20** |

> Note: verify against actual AWS/Anthropic bills once volume picks up. Cost per contract drops as contracts get shorter or if only 1-2 tools are called.

---

### Pricing recommendation

| Option | Price | Notes |
|---|---|---|
| Free | 1 contract | Permanent. Enough to experience full value. |
| Single contract | $4.99 | ~25x cost margin. Low enough to be impulse-buy. |
| 5-pack | $19 ($3.80 each) | Encourages repeat. ~10% discount vs single. |
| 10-pack | $34 ($3.40 each) | Best value tier. ~30% discount vs single. |

- Launch promo code (e.g. `EARLYBIRD`) for 50% off via Stripe discount — no code changes needed
- Lawyers/in-house users will still find this very cheap vs $500+/hr alternative
- Revisit if cost per contract turns out higher than estimated

---

**Who gets charged**
- Plugin users (`user_type: "plugin"`) — yes
- Subscription users (`user_type: "subscription"`) — no, fully bypassed

---

## Roadmap

### ~~Priority 1 — `upload_contract` MCP tool~~ ✅ Done
### ~~Priority 2 — Stripe integration~~ ✅ Done
### ~~Priority 3 — Login page clarity~~ ✅ Done

---

## Large Contract Handling

### Background
Long contracts (30+ pages) originally took 10+ minutes to process. A series of optimizations brought this down significantly:

| Optimization | Impact |
|---|---|
| FieldExtraction chunking (20,000 char threshold) | Head + key sections + tail sent to LLM instead of full text |
| Classification + SectionExtraction run in parallel | Saved ~1-2s per upload |
| FieldExtraction + FastRiskAssessment run in parallel | Saves ~5-15s for long contracts |
| Analysis report cached in DB after first generation | Subsequent `get_analysis_report` calls are sub-millisecond |
| Fire-and-forget pre-generation after upload | Report is ready by the time user calls `get_analysis_report` |

### Current pipeline (post-optimization)
```
FileValidation
    → DocumentExtraction (Textract, ~2-5s)
        → [PARALLEL] Classification + SectionExtraction (~1-2s)
            → [PARALLEL] FieldExtraction + FastRiskAssessment (~5-15s, was sequential)
                → MetadataResolution
                    → DatabaseSave
                        → [FIRE-AND-FORGET] Analysis pre-generation (cached for instant retrieval)
```

### Remaining limitations
- **FastRiskAssessment** still does full-text pattern scan (no truncation) — main bottleneck for very long contracts
- **Analysis report** truncates at 12,000 chars for the LLM call — may miss clauses in 40+ page contracts
- **Quality**: contracts over ~30 pages may have reduced clause-level detail due to LLM context limits

### MCP plugin handling
- Contracts >500KB get a 4-minute poll window instead of 2 minutes
- Success response includes `large_contract_notice` advising users to use `explain_clause` for specific sections
- Timeout message explicitly tells users to check back via `list_contracts`

### Roadmap
Full long-contract support (multi-pass chunked analysis, per-section risk aggregation) is planned. Prioritized based on user demand — track requests via support.

---

## Known Limitations

| Limitation | Detail | Workaround |
|---|---|---|
| Long contracts (30+ pages) | Analysis may miss clauses due to LLM context limits; processing takes longer | Use `explain_clause` or `get_clause_details` to analyze specific sections |
| Processing timeout | Contracts taking >4 min return a "still processing" message — credit is NOT refunded | Call `list_contracts` after a few minutes, then `get_analysis_report` with the ID |
| Local files | Cannot upload files from your computer via `file_url` | Paste text via `text_content`, or share via Google Drive / Dropbox |
| Google Docs | Must be shared as "Anyone with the link" | Change sharing settings before uploading |
| Classification confidence | Some niche contract types may not get specialized analysis | Pass `contract_type` explicitly; unsupported types are processed as general contracts |

> **Roadmap:** Long contract support (chunking + multi-pass analysis) is prioritized based on demand. If you regularly work with 30+ page agreements, contact us.

---

## Production Stability

Once the plugin is live in the marketplace, `app.legalforensics.ai` becomes production infrastructure. Users will depend on it.

### Key risks
| Risk | Impact | Mitigation |
|---|---|---|
| EC2 goes down overnight | All plugin tools fail | UptimeRobot alert on `/health` endpoint |
| Deploy causes ~30s downtime | In-flight requests fail | Deploy during off-peak hours |
| Backend API endpoint renamed/removed | Plugin breaks for all users | Don't change the 5 endpoints the plugin calls without a coordinated plugin update |
| Schema change breaks DB | Backend crash | Test on dev before merging to EC2 |

### Endpoints the plugin depends on (do not break)
- `GET /api/contracts/my-contracts`
- `POST /api/contracts/upload`
- `GET /api/contracts/{id}/status`
- `GET /api/contracts/{id}/analysis-report`
- `GET /api/contracts/{id}/decision-guidance`
- `GET /api/contracts/{id}/narrative-walkthrough`
- `GET /api/stripe/credits`
- `POST /api/stripe/credits/deduct`
- `POST /api/stripe/credits/refund`

### Monitoring
- **UptimeRobot** (free) — monitors `https://app.legalforensics.ai/health` every 5 min, alerts via email/SMS
  - Sign up at [uptimerobot.com](https://uptimerobot.com), add HTTP monitor, paste the health URL
- **Render dashboard** — Render paid plan shows MCP server uptime and logs

### Deploy discipline
- Backend changes: merge to `dev` → test on EC2 → PR to `main` for production
- Plugin changes: push to `main` on `lf-cowork-plugin` → Render auto-deploys
- Avoid deploying both at the same time

---

## Testing

### Setup

**MCP Inspector (recommended)**
```bash
npx @modelcontextprotocol/inspector https://lf-cowork-plugin.onrender.com/mcp
```
- Requires Node v22+ (Windows: use [nvm-windows](https://github.com/coreybutler/nvm-windows))
- In the inspector UI: set `X-LF-API-Key` header with a real plugin user API key
- Use **Via Proxy** mode — Direct mode has CORS issues with streamable-http

**Direct curl** (MCP must include both Accept headers)
```bash
curl -X POST https://lf-cowork-plugin.onrender.com/mcp \
  -H "X-LF-API-Key: lf_your_key" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"TOOL_NAME","arguments":{...}},"id":1}'
```

**Local server**
```bash
# Terminal 1
python server.py
# Terminal 2
npx @modelcontextprotocol/inspector http://localhost:8001/mcp
```

---

### Test Plan

> **How to use:** Run each test case, fill in Actual Result and set Status to Pass or Fail.

#### A — Authentication

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| A1 | Valid API key | Call `list_contracts` with a valid plugin user key | Returns contract list (empty or populated) | | |
| A2 | Invalid API key | Call `list_contracts` with `lf_invalid123` | Clear error: "Invalid API key" or 401 | | |
| A3 | Missing API key | Call `list_contracts` with no `X-LF-API-Key` header | Clear auth error | | |
| A4 | Revoked API key | Revoke a key in the UI, then call `list_contracts` with it | Clear error: "Invalid API key" | | |

---

#### B — upload_contract

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| B1 | Text paste (NDA) | `text_content` = short NDA text, `title` = "Test NDA" | Returns `contract_id`, status completed | | |
| B2 | Google Doc URL | `file_url` = public Google Doc share link, `title` = "Google Doc NDA" | Converted to DOCX export, extracted, returns `contract_id` | | |
| B3 | Direct PDF URL | `file_url` = public PDF URL, `title` = "PDF Contract" | Downloaded, extracted, returns `contract_id` | | |
| B4 | Missing title | Call with `text_content` but no `title` | Error: "title is required" — before credit deducted | | |
| B5 | Unsupported file type | `file_url` pointing to a `.zip` file | Error: "Unsupported file type" | | |
| B6 | Duplicate filename | Upload same title twice | Second upload returns 409 Conflict with clear message | | |
| B7 | No credits remaining | Upload with plugin user who has 0 credits | Error with Stripe checkout URL to purchase | | |
| B8 | Last credit warning | Upload with plugin user who has exactly 1 credit | Success + `warning`: "This was your last credit..." | | |
| B9 | Large contract (30+ pages) | Upload a 30+ page PDF or DOCX | Processes with 4min timeout, returns `large_contract_notice` in result | | |
| B10 | Private Google Doc | `file_url` = Google Doc not shared publicly | Clear error: 401 Unauthorized — doc must be shared | | |
| B11 | Text paste — empty | `text_content` = "" | Error before credit deducted | | |
| B12 | Auto-refund on failure | Upload file that causes processing failure | Credit refunded, error message says "Your credit has been refunded" | | |

---

#### C — list_contracts

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| C1 | List all contracts | Call `list_contracts` with no filter | Returns array of all contracts for the user | | |
| C2 | Keyword filter — match | Call with `keyword` = word in a contract title | Returns only matching contracts | | |
| C3 | Keyword filter — no match | Call with `keyword` = "xyznotexist" | Returns empty list, no error | | |
| C4 | Empty account | Call with a brand new user with no contracts | Returns empty list, no error | | |

---

#### D — get_analysis_report

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| D1 | Valid contract | Call with a processed `contract_id` | Returns full risk analysis: posture, risk items, exposure, decision guidance, disclaimer | | |
| D2 | Cached response | Call `get_analysis_report` twice on same ID | Second call returns instantly (sub-second) | | |
| D3 | Wrong contract ID | Call with `contract_id` = 99999 | Clear error: "Contract not found" | | |
| D4 | Another user's contract | Call with a contract ID belonging to a different company | Clear error: "Contract not found or access denied" | | |

---

#### E — get_decision_guidance

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| E1 | Valid contract | Call with a processed `contract_id` | Returns decision (sign/negotiate/walk away), reasoning, priority asks, disclaimer | | |
| E2 | Wrong contract ID | Call with `contract_id` = 99999 | Clear error | | |

---

#### F — get_narrative_walkthrough

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| F1 | Valid contract | Call with a processed `contract_id` | Returns plain-English narrative + disclaimer at end | | |
| F2 | Wrong contract ID | Call with `contract_id` = 99999 | Clear error | | |

---

#### G — run_standards_review

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| G1 | Valid contract | Call with a processed `contract_id` | Returns standards review result | | |
| G2 | No playbook configured | Call with user who has no company playbook | Graceful response (no crash) | | |

---

#### H — get_clause_details

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| H1 | Valid clause ID | Get a `clause_id` from `get_analysis_report` output, call `get_clause_details` | Returns clause risk factors, explanation, AI rewrite suggestion | | |
| H2 | Invalid clause ID | Call with `clause_id` = 99999 | Clear error | | |

---

#### I — explain_clause

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| I1 | Standard clause | `clause_text` = "Either party may terminate with 30 days written notice." | Plain-English explanation + risk assessment | | |
| I2 | With context | Same clause + `contract_context` = "NDA, governed by California law" | More precise explanation using context | | |
| I3 | Empty text | `clause_text` = "" | Clear error | | |
| I4 | No credit needed | Call with a user who has 0 credits | Should succeed — explain_clause is free | | |

---

#### J — set_perspective

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| J1 | Valid perspective | `contract_id` + `perspective` = "buyer" | Re-analysis from buyer's perspective, returned successfully | | |
| J2 | All valid values | Test: buyer, seller, vendor, customer, licensor, licensee, employer, employee | Each returns analysis without error | | |
| J3 | Invalid value | `perspective` = "alien" | Clear error listing valid values | | |

---

#### K — Stripe / Credits

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| K1 | New plugin user credit | Sign up at `/plugin`, check credit balance | `credits_remaining: 1` | | |
| K2 | Credit deducted on upload | Upload with 1 credit, check balance after | `credits_remaining: 0, credits_used: 1` | | |
| K3 | No credits — checkout URL returned | Upload with 0 credits | Error message includes valid Stripe checkout URL | | |
| K4 | Purchase via Stripe test card | Open checkout URL, use card `4242 4242 4242 4242` | Payment succeeds, `credits_remaining` increments by 1 | | |
| K5 | Webhook idempotency | Trigger same `checkout.session.completed` event twice | Credit only added once | | |
| K6 | Subscription user — no credit gate | Call `upload_contract` with subscription user key | Upload proceeds without credit check | | |
| K7 | Refund on processing failure | Force a processing failure (bad file) | Credit refunded automatically, error message confirms | | |

---

#### L — Signup Flow

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| L1 | Full signup flow | Visit `/plugin`, fill form, verify email, copy API key | API key shown immediately after email verification | | |
| L2 | API key works in Claude | Paste key into Claude plugin config | `list_contracts` succeeds on first call | | |
| L3 | Free credit on signup | Check credit balance immediately after signup | `credits_remaining: 1` | | |

---

#### M — Edge Cases

| ID | Test Case | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| M1 | Cold start (Render free tier) | Wait 15 min, then call any tool | First call may take 10-30s to wake up; subsequent calls fast | | |
| M2 | Server wake via curl | `curl https://lf-cowork-plugin.onrender.com/health` | Returns 200, wakes server before user hits it | | |
| M3 | Concurrent uploads | Upload two contracts simultaneously | Both complete successfully, no credit double-deduction | | |
| M4 | 30+ page contract | Upload a real 30+ page agreement | Processes within 4 min, `large_contract_notice` in response | | |
| M5 | Non-English contract | Upload a contract in French or Spanish | Processes without crashing; quality may vary | | |

---

## Files

| File | Purpose |
|---|---|
| `server.py` | FastMCP server — 9 tools proxying to LF API |
| `plugin.json` | Plugin manifest for Anthropic marketplace submission |
| `render.yaml` | Render deployment config |
| `commands/` | Slash command definitions for Claude |

---

## Submission Checklist (Anthropic Marketplace)

### Remaining feature work
- [x] Stripe integration — gate analysis tools behind payment for plugin users ✅
- [x] Auto-refund on failure — credit deducted upfront, refunded if upload/processing fails ✅

### plugin.json
- [x] `auth.instructions` directs users to `app.legalforensics.ai/plugin`
- [x] All 9 tools listed
- [x] `mcp_server.url` points to live Render URL
- [x] `homepage` set to `https://app.legalforensics.ai/plugin` ✅
- [x] `author` confirmed as `LegalForensics.AI` ✅

### Deploy pending changes
- [x] lf-nextgen-services — refund endpoint deployed to EC2 ✅
- [x] lf-cowork-plugin — `server.py` + `plugin.json` deployed to Render ✅
- [ ] lf-nextgen-ui `stripe` — commit + deploy plugin-landing, decision-brief fix, nginx.conf

### Testing
- [ ] All test cases in the Testing section pass (sections A–M)

### Infrastructure
- [ ] Render service upgraded to paid plan ($7/mo starter) — free tier sleeps after inactivity
- [ ] Response times acceptable (< 3s for non-analysis tools)
- [ ] UptimeRobot monitoring set up on `https://app.legalforensics.ai/health` (free, alerts via email/SMS if EC2 goes down)

### Final step
- [ ] Submit `plugin.json` to Anthropic:
  1. Go to **claude.ai/plugins**
  2. Click **Submit a plugin**
  3. Upload or paste `plugin.json`
  4. Anthropic reviews the manifest and tests the live MCP server URL
  5. Approval notification sent by email — no fixed SLA but typically days not weeks
  6. After approval, plugin appears in Claude marketplace under your name
