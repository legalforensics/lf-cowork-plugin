# LegalForensics — Claude Connector

Contract review directly inside Claude. Upload any MSA, NDA, SOW, employment, or lease agreement and get a full risk analysis, sign/negotiate/walk away verdict, and plain-English walkthrough — without leaving your conversation.

## Quick Setup

1. claude.ai → **Settings → Connectors → Add custom connector**
2. URL: `https://lf-cowork-plugin.onrender.com/mcp`
3. OAuth Client ID: `4q850suef3bj1pde4bc5gp75lt`
4. Click **Connect** → sign in → you're ready

New accounts receive 1 free credit automatically. Full setup guide: [USER_GUIDE.md](USER_GUIDE.md)

---

## Tools

| Tool | Description | Credit |
|---|---|---|
| `upload_contract` | Upload via Google Doc link or pasted text. Returns `contract_uuid`. | 1 credit |
| `analyze_risks` | Full risk analysis — posture, top risks, exposure bands, favorable terms. Accepts `contract_id` or `contract_uuid`. | Free |
| `sign_or_negotiate` | Sign / negotiate / walk away verdict with reasoning and priority asks. Accepts `contract_id` or `contract_uuid`. | Free |
| `explain_contract` | Plain-English narrative walkthrough of a full contract. | Free |
| `explain_clause` | Plain-English explanation of a pasted clause. No upload needed. | Free |
| `my_contracts` | List all contracts in account, optionally filtered by keyword. | Free |
| `my_credits` | Check credit balance. Returns purchase link if balance is zero. | Free |

---

## Auth

Supports two modes:

**OAuth 2.0 (primary)** — Authorization Code + PKCE via AWS Cognito. Claude drives the flow; users sign in via the Cognito hosted UI. New users are auto-provisioned on first call.

**API key (legacy)** — `X-LF-API-Key: lf_<key>` header. Generate a key at app.legalforensics.ai → Settings → API Keys.

---

## Architecture

```
claude.ai
    │  OAuth 2.0 Bearer token or X-LF-API-Key
    ▼
lf-cowork-plugin (this repo, Render.com)
    │  Bearer token or X-LF-API-Key forwarded
    ▼
lf-nextgen-services (LF API, app.legalforensics.ai)
    │
    ▼
PostgreSQL + AWS Bedrock (Claude 3.5 Sonnet)
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) — including planned contract history intelligence features (personal baseline comparison, portfolio outlier detection, cross-contract conflict detection).

---

## Support

- User guide: [USER_GUIDE.md](USER_GUIDE.md)
- Setup page: [legalforensics.ai/claude](https://legalforensics.ai/claude)
- Email: amit@legalforensics.ai
