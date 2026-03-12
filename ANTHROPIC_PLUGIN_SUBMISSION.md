# LegalForensics Plugin — Anthropic Submission

## Status: Ready for Submission

---

## End-to-End User Flow

### First-time user (OAuth signup + first tool call)

```
User on claude.ai
       │
       ▼
Finds LegalForensics in Connectors Directory → clicks Connect
       │
       ▼
Claude redirects browser to Cognito hosted UI
(us-east-1aassqgtdr.auth.us-east-1.amazoncognito.com)
       │
       ├── Returning user: enters email + password → signs in
       │
       └── New user: clicks Sign Up → enters email + password
                  → Cognito sends verification email
                  → user verifies
                  → Cognito account created
       │
       ▼
Cognito redirects back to Claude with auth code
Claude exchanges auth code for Bearer token via PKCE (behind the scenes)
       │
       ▼
User asks Claude: "analyze contract 200" (or any LF request)
       │
       ▼
Claude calls MCP tool on lf-cowork-plugin.onrender.com/mcp
with header: Authorization: Bearer <cognito_access_token>
       │
       ▼
MCP server extracts Bearer token → forwards to LF API
(app.legalforensics.ai/api/...)
with header: Authorization: Bearer <cognito_access_token>
       │
       ▼
LF backend (auth.py: get_current_user_from_token)
       │
       ├── Decodes JWT → gets cognito_id (sub)
       │
       ├── Looks up user in LF DB → NOT FOUND (first time)
       │
       └── _provision_oauth_user() fires automatically:
               → creates Company record
               → creates User record (user_type="plugin")
               → grants 1 free PluginCredit
               → fetches name + email from Cognito if not in token
       │
       ▼
Tool executes normally → result returned to Claude → shown to user
User is now fully set up. All future calls find user in DB instantly.
```

### Returning user (every call after first)

```
User asks Claude anything about contracts
       │
       ▼
Claude calls MCP tool with Authorization: Bearer <token>
       │
       ▼
LF backend decodes token → finds user in DB → executes tool
(no provisioning, no redirect, no friction)
```

### Legacy API key user (existing flow, still supported)

```
User goes to app.legalforensics.ai/plugin
       │
       ▼
Fills signup form → Cognito account created via Amplify
pre-register called → Company + User + 1 credit created in LF DB
API key generated and shown once
       │
       ▼
User pastes API key into Claude connector config
       │
       ▼
Claude calls MCP tool with X-LF-API-Key: lf_xxx
MCP server forwards X-LF-API-Key to LF API
LF backend hashes key → looks up in api_keys table → user found
Tool executes normally
```

---

## Plugin Details

| Field | Value |
|---|---|
| Plugin name | LegalForensics |
| Version | 1.0.0 |
| Author | LegalForensics.AI |
| Homepage | https://app.legalforensics.ai/plugin |
| MCP server | https://lf-cowork-plugin.onrender.com/mcp |
| Transport | streamable-http |
| Auth | API key (`X-LF-API-Key` header) |
| Plugin manifest | `plugin.json` |
| Server code | `server.py` |

---

## Tools

| Tool | Description |
|---|---|
| `upload_contract` | Upload via Google Doc link or pasted text. Costs 1 credit. Returns `contract_id`. |
| `analyze_risks` | Full risk analysis — risk posture, top risks, exposure bands, favorable terms, structural assessment. Supports perspective. |
| `sign_or_negotiate` | Sign / negotiate / walk away verdict with reasoning and priority asks. Supports perspective. |
| `explain_contract` | Plain-English narrative walkthrough of a full contract. |
| `explain_clause` | Plain-English explanation of a pasted clause. Free, no credit required. Supports perspective. |
| `my_contracts` | List all contracts in account, optionally filtered by keyword. |
| `my_credits` | Check credit balance. Returns purchase link if balance is zero. |

---

## Testing Results

All tools tested end-to-end. Both perspectives tested for all contract types.

### Contract Types Tested

| Contract Type | upload | analyze_risks | sign_or_negotiate | explain_contract | explain_clause |
|---|---|---|---|---|---|
| NDA | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | ✓ both perspectives |
| MSA | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |
| SOW / Project | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |
| Employment | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |
| Lease | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | ✓ both perspectives |
| IP / License | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |
| Foundry | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |
| Franchise | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |
| Data Processing | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |
| Supply Chain | ✓ | ✓ both perspectives | ✓ both perspectives | ✓ | — |

### Contract-Agnostic Tools

| Tool | Status |
|---|---|
| `explain_clause` — neutral | ✓ |
| `explain_clause` — with perspective | ✓ |
| `my_contracts` — list | ✓ |
| `my_contracts` — search filter | ✓ |
| `my_credits` — with balance | ✓ |
| `my_credits` — zero balance + purchase link | ✓ |

### Perspective Framing Verified

Both stronger-party and weaker-party perspectives produce correctly inverted analysis:
- verdict, favorable_terms, risk_items, top_3_actions, decision_summary all flip correctly
- plain_english_summary uses correct "you" framing for the selected role
- Tested representative pairs: landlord/tenant, employer/employee, franchisor/franchisee, data controller/data processor, buyer/supplier

---

## Next Steps (In Order)

### 1. Tester Account Setup
- [x] Create dedicated test account: `amit+anthropic@legalforensics.ai`
- [x] Generate API key via LF app → Settings → API Keys
- [x] Manually set credit balance to 5 in DB
- [x] Pre-load 2 sample contracts:
  - Contract 1: NDA — contract_id: 200
  - Contract 2: Employment Agreement — contract_id: 201
- [x] Note contract IDs for inclusion in submission notes

### 2. Submission Notes / Getting Started Guide
- [x] Draft getting started guide for Anthropic tester (see template below)
- [x] Include: API key, contract IDs, suggested test prompts

### 3. Plugin Submission
- [ ] Submit `plugin.json` via Anthropic plugin submission form
- [ ] Attach getting started guide
- [ ] Provide tester account credentials separately (not in plugin.json)

---

## Tester Getting Started Guide (Draft)

### Credentials
- **API key**: `lf_016ebbcbcd6eadcb5ea27d95bd2f50a8a69ba416`
- Sign up page (for reference): https://app.legalforensics.ai/plugin

### Configure the Plugin
Paste the API key above into the LegalForensics plugin configuration field in Claude.

### Quick Tests (No Upload Needed)

**1. Check credits**
> "How many credits do I have?"

**2. Explain a clause (free, no credit)**
> "Explain this clause: 'The vendor shall not be liable for any indirect, incidental, or consequential damages arising out of or related to this agreement, even if advised of the possibility of such damages.'"

> With perspective: "Explain this clause from the buyer's perspective: [same clause]"

**3. List pre-loaded contracts**
> "Show me my contracts"

### Full Analysis Tests (Uses Credits)

**Pre-loaded Contract 1 — NDA (contract_id: 200)**
> "Analyze the risks in contract 200"
> "Analyze the risks in contract 200 from the disclosing party's perspective"
> "Should I sign contract 200 as the receiving party?"
> "Explain contract 200 in plain English"

**Pre-loaded Contract 2 — Employment Agreement (contract_id: 201)**
> "Analyze the risks in contract 201 from the employer's perspective"
> "Analyze the risks in contract 201 from the employee's perspective"
> "Should I sign contract 201 as the employee?"

### Upload Test (Uses 1 Credit)
> "Analyze this contract: [paste any contract text]"

---

## Supported Perspective Roles

Roles grouped by side of the deal:

| Contract Type | Side A | Side B |
|---|---|---|
| NDA | disclosing party | receiving party |
| MSA | client | vendor, service provider |
| SOW / project | client | contractor, consultant, subcontractor |
| Employment | employer | employee, executive |
| Lease | landlord, lessor | tenant, lessee |
| IP / License | licensor | licensee |
| Supply chain | buyer | seller, supplier, distributor, manufacturer |
| Foundry | foundry | fabless |
| Finance | lender, investor | borrower |
| Data processing | data controller | data processor |
| Franchise | franchisor | franchisee |

---

## Connectors Directory Submission Form (Google Form Answers)

Submission form: https://docs.google.com/forms/d/e/1FAIpQLSeafJF2NDI7oYx1r8o0ycivCSVLNq92Mpc1FPxMKSw1CzDkqA/viewform

### Company Information

| Field | Answer |
|---|---|
| Company/Organization Name | LegalForensics.AI |
| Company/Organization URL | legalforensics.ai |
| Primary Contact Name | Amit Nagar |
| Primary Contact Email | amit@legalforensics.ai |
| Primary Contact Role | Founder |
| Anthropic Point of Contact | — |

### Server Details

**MCP Server Name**
`LegalForensics`

**URL Type**
`Universal URL`

**MCP Server URL**
`https://lf-cowork-plugin.onrender.com/mcp`

**Tagline (55 chars)**
`AI contract review — risks, verdict, plain English`

**MCP Server Description (50-100 words)**
```
LegalForensics analyzes contracts directly inside Claude. Upload any MSA, NDA, SOW,
employment, or lease agreement and get a full risk analysis, a sign/negotiate/walk away
verdict, and a plain-English walkthrough — without leaving your conversation. Designed
for founders, operators, and small teams who sign contracts without in-house legal support.
Supports perspective framing (buyer, seller, employer, tenant, etc.) to frame results from
your side of the deal. Clause analysis is free; full contract review costs 1 credit per upload.
```

**Use Cases + Examples**
```
1. Contract risk analysis
   "What are the biggest risks in contract 200 from the tenant's perspective?"

2. Sign or negotiate decision
   "Should I sign contract 201 as the employee — or push back?"

3. Plain-English walkthrough
   "Explain contract 200 in plain English. What do I need to know before signing?"

4. Clause analysis (free, no upload needed)
   "What does this clause mean: 'The vendor shall not be liable for any indirect,
   incidental, or consequential damages...'"

5. Upload and analyze
   "Analyze this contract: [paste contract text or Google Doc link]"
```

**Connection Requirements**
```
Requires a free LegalForensics account. Sign up at app.legalforensics.ai/plugin — takes
2 minutes. New accounts receive 1 free credit. An API key is generated at signup and
entered in the plugin configuration field in Claude.
```

**Read/Write Capabilities**
`Read + Write`

**Is this an MCP App**
`No`

**Third-party Connections**
`Third-party AI model integration` (AWS Bedrock Claude 3.5 Sonnet used for contract analysis)

**Data Handling**
- ✅ Server only accesses data explicitly requested by user
- ✅ Data transmission is encrypted (HTTPS/TLS)

**Personal Health Data**
`No`

**Categories**
`Business & Productivity` + `Other: Legal`

**Sponsored Content**
`No`

### Authentication

**Current status**: OAuth 2.0 implemented (Authorization Code + PKCE via AWS Cognito).
Server also accepts `X-LF-API-Key` header for legacy API key users.

**OAuth endpoints (Cognito)**
- Authorization: `https://us-east-1aassqgtdr.auth.us-east-1.amazoncognito.com/oauth2/authorize`
- Token: `https://us-east-1aassqgtdr.auth.us-east-1.amazoncognito.com/oauth2/token`
- Discovery: `https://lf-cowork-plugin.onrender.com/.well-known/oauth-authorization-server`
- Scopes: `openid email profile`
- PKCE: S256, no client secret

**Auth Type (once OAuth implemented)**
`OAuth 2.0`

**Auth Client**
`Static OAuth Client`

**Static Client ID**
`4q850suef3bj1pde4bc5gp75lt`

**Static Client Secret**
`(none — PKCE only, no client secret)`

### Transport

`Streamable HTTP`

---

## Known Limitations

- Google Doc links must be shared publicly ("Anyone with the link")
- Google Drive file links not supported (use Google Docs links or paste text)
- Large contracts (30+ pages) are analyzed on the first ~40,000 characters
- Analysis takes 30–90 seconds (Bedrock Claude claude-3-5-sonnet-20241022-v2:0 on AWS)
- First analysis of a contract is cached; subsequent calls use cache unless `force_refresh=true`
- Supply chain contract type auto-classified as "Distribution Agreement" — functionally correct
