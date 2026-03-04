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
These are working features that need to be verified end-to-end:
- [ ] **Stripe flow** — run the 6-step test sequence in the Testing section below
- [ ] **Signup flow** — visit `/plugin`, sign up, verify email, copy API key, paste into Claude, confirm tools work
- [ ] **`upload_contract` via URL** — test with a real direct-download PDF link
- [ ] **`get_narrative_walkthrough`** — call with a real contract ID, verify response
- [ ] **`run_standards_review`** — call with a real contract ID, verify response
- [ ] **`get_clause_details`** — call with a real clause ID from an analysis report
- [ ] **`explain_clause`** — paste a clause, verify plain-English explanation returned
- [ ] **`list_contracts`** — verify returns list; test keyword filter
- [ ] **Error cases** — bad API key returns clear message; unsupported file type returns clear message

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

## Testing the Plugin Locally

### Test against the live Render server (recommended)

```bash
cd C:\Users\amitn\repos\lf-cowork-plugin
npx @modelcontextprotocol/inspector https://lf-cowork-plugin.onrender.com/mcp
```

This opens a web UI where you can:
- Set the `X-LF-API-Key` header with a real API key
- Call each tool individually and inspect the raw response
- Simulate exactly what Claude Cowork does

### Test the MCP endpoint directly with curl

The MCP server uses streamable-http (SSE). **You must include both `application/json` and `text/event-stream` in the `Accept` header** or the server returns a 406 error.

```bash
# MCP endpoint
https://lf-cowork-plugin.onrender.com/mcp

# List available tools
curl -X POST https://lf-cowork-plugin.onrender.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Call upload_contract with pasted text
curl -X POST https://lf-cowork-plugin.onrender.com/mcp \
  -H "X-LF-API-Key: lf_your_api_key_here" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"upload_contract","arguments":{"text_content":"This NDA binds both parties to confidentiality for 5 years.","title":"Test NDA"}},"id":1}'

# Call upload_contract with a URL
curl -X POST https://lf-cowork-plugin.onrender.com/mcp \
  -H "X-LF-API-Key: lf_your_api_key_here" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"upload_contract","arguments":{"file_url":"https://example.com/contract.pdf","title":"My Contract"}},"id":1}'
```

### Alternative — Test LF API directly with curl

The MCP tools are thin proxies over the LF API, so testing the API directly validates the same logic. Fastest option, no extra headers needed.

```bash
# list_contracts
curl -H "X-LF-API-Key: lf_your_api_key_here" \
  https://app.legalforensics.ai/api/contracts/my-contracts

# upload_contract (text)
curl -X POST https://app.legalforensics.ai/api/contracts/upload \
  -H "X-LF-API-Key: lf_your_api_key_here" \
  -F "file=@/path/to/contract.pdf" \
  -F "title=Test Contract"

# explain_clause (no upload needed — best for quick smoke test)
curl -X POST https://app.legalforensics.ai/api/simplification/explain-clause \
  -H "X-LF-API-Key: lf_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"clause_text": "Either party may terminate this agreement with 30 days written notice."}'
```

> **Note:** The MCP Inspector requires Node v22+. On Windows, install via [nvm-windows](https://github.com/coreybutler/nvm-windows) — standard `nvm` is not available on Windows. The inspector v0.9.0 (Node 20) only supports SSE transport which is incompatible with our streamable-http server.

### Test Stripe credit flow

#### Prerequisites
1. Backend is running (EC2) with `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET` set
2. You have a plugin user's API key — either:
   - Sign up at `https://app.legalforensics.ai/plugin` and copy the key shown at step 3, or
   - Use an existing key from a user with `user_type = "plugin"` in the DB
3. Replace `lf_your_api_key_here` with your actual key in every command below
4. For webhook tests (steps 4–6): install [Stripe CLI](https://stripe.com/docs/stripe-cli) and run `stripe login`

Run the steps **in order** — each step depends on the state left by the previous one.

---

#### 1. Check credit balance
```bash
curl -H "X-LF-API-Key: lf_your_api_key_here" \
  https://app.legalforensics.ai/api/stripe/credits
# Expected: {"credits_remaining": 1, "credits_used": 0}  (new plugin user gets 1 free)
```

#### 2. Trigger upload with credits (should succeed + warn)
```bash
# Upload a short contract as text — uses the 1 free credit
curl -X POST https://lf-cowork-plugin.onrender.com/mcp \
  -H "X-LF-API-Key: lf_your_api_key_here" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"upload_contract","arguments":{"text_content":"This NDA binds both parties to confidentiality for 5 years.","title":"Credit Test NDA"}},"id":1}'
# Expected: success + "warning": "This was your last credit..."
```

#### 3. Trigger upload with no credits (should return checkout URL)
```bash
# Run upload again — should block and return Stripe URL
curl -X POST https://lf-cowork-plugin.onrender.com/mcp \
  -H "X-LF-API-Key: lf_your_api_key_here" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"upload_contract","arguments":{"text_content":"Test contract text","title":"No Credit Test"}},"id":2}'
# Expected: ValueError with "Purchase a contract analysis credit here: https://checkout.stripe.com/..."
```

#### 4. Test Stripe webhook with Stripe CLI
```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli
# Forward webhooks to local backend:
stripe listen --forward-to localhost:8000/api/stripe/webhook

# In another terminal, trigger a test checkout.session.completed event:
stripe trigger checkout.session.completed \
  --override checkout_session:client_reference_id=<your_user_id> \
  --override checkout_session:metadata.user_id=<your_user_id> \
  --override checkout_session:metadata.company_id=<your_company_id> \
  --override checkout_session:metadata.credits=1

# Expected: credit balance increments by 1
curl -H "X-LF-API-Key: lf_your_api_key_here" \
  https://app.legalforensics.ai/api/stripe/credits
# Expected: {"credits_remaining": 1, "credits_used": 1}
```

#### 5. Idempotency check (webhook sent twice)
```bash
# Send the same webhook event twice — credits should only increment once
# Re-trigger same session ID — second call should be a no-op
# Check credits_remaining hasn't doubled
```

#### 6. Full end-to-end with real Stripe test card
1. Get checkout URL from step 3 above
2. Open it in browser
3. Use test card: `4242 4242 4242 4242`, any future date, any CVC
4. Complete payment
5. Stripe sends webhook → credits_remaining goes back to 1
6. Retry upload → succeeds

---

### Test against a local server

```bash
# Terminal 1 — start the plugin server locally
cd C:\Users\amitn\repos\lf-cowork-plugin
python server.py

# Terminal 2 — open the inspector
npx @modelcontextprotocol/inspector http://localhost:8001/mcp
```

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

### User signup flow
- [ ] `/plugin` page works end-to-end: signup → email verify → API key shown immediately
- [ ] API key pasted into Claude plugin config works on first try

### Tools — end-to-end with a real contract
- [x] `upload_contract` — text paste (tested via Python MCP client)
- [ ] `upload_contract` — URL (direct download link)
- [x] `get_analysis_report` (tested via Python MCP client)
- [x] `get_decision_guidance` (tested via Python MCP client)
- [ ] `get_narrative_walkthrough`
- [ ] `run_standards_review`
- [ ] `get_clause_details`
- [ ] `explain_clause`
- [ ] `list_contracts`

### Error handling
- [ ] Bad API key → clear error message to user
- [ ] Duplicate filename → clear error message
- [ ] Unsupported file type → clear error message

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
