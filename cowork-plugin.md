# LegalForensics Cowork Plugin

## Overview

The LegalForensics Cowork plugin connects Claude to the LegalForensics contract analysis platform via MCP (Model Context Protocol). Users can analyze contracts, get risk assessments, and receive decision guidance directly inside Claude conversations.

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

## Current Gap — Contract Upload

**The plugin can only analyze contracts already uploaded via the LF dashboard.**

The current flow has an extra step:
> Sign up → get API key → **upload contract at LF dashboard** → return to Claude → analyze

This breaks the seamless experience. The fix is an `upload_contract` MCP tool (see Roadmap below).

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
| Billing | LF subscription | Pay-per-contract via Stripe (planned) |

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

## Roadmap

### ~~Priority 1 — `upload_contract` MCP tool~~ ✅ Done
Users can now upload contract text or a URL directly from Claude. Plugin is fully self-contained — no LF dashboard required.

### Priority 2 — Stripe integration
- Plugin users (`user_type: "plugin"`) pay per contract processed
- LF subscription users are unaffected
- Gate MCP analysis tools behind a credit/payment check
- Use Stripe Checkout for one-time payments or usage-based billing

### Priority 3 — Email vs SSO clarity on login page
- Login page should clearly separate the two paths
- Plugin users always use email/password — no SSO confusion

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

### plugin.json
- [x] `auth.instructions` directs users to `app.legalforensics.ai/plugin`
- [x] All 9 tools listed
- [x] `mcp_server.url` points to live Render URL
- [ ] `homepage` and `author` are final/accurate

### User signup flow
- [ ] `/plugin` page works end-to-end: signup → email verify → API key shown immediately
- [ ] API key pasted into Claude plugin config works on first try

### Tools — end-to-end with a real contract
- [x] `upload_contract` — text paste (tested via Python MCP client)
- [ ] `upload_contract` — URL
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
- [ ] Render service on paid plan (starter+) — free tier sleeps after inactivity
- [ ] Response times acceptable (< 3s for non-analysis tools)

### Final step
- [ ] Submit `plugin.json` to Anthropic via claude.ai/plugins
