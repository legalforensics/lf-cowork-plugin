# LegalForensics Cowork Plugin

Contract risk analysis for Claude Cowork — analyze any MSA, NDA, or SOW directly from your workspace.

## What it does

The LegalForensics plugin gives Claude access to your contract library via 7 MCP tools:

| Tool | What it returns |
|---|---|
| `upload_contract` | Upload a contract and get back a contract_id |
| `my_contracts` | All contracts in your LF account |
| `analyze_risks` | Full AI risk analysis with risk posture + top risks |
| `sign_or_negotiate` | Sign / negotiate / walk away decision brief |
| `explain_contract` | Plain-English contract walkthrough for non-lawyers |
| `explain_clause` | Explain pasted clause text without uploading a contract |
| `my_credits` | Check credit balance and get a purchase link if needed |

## Setup

### 1. Create a LegalForensics account

Sign up at [legalforensics.ai/plugin](https://legalforensics.ai/plugin) — takes 2 minutes.

### 2. Generate an API key

Go to **Settings → API Keys** → click **Generate New Key**.

Copy the key — it's shown once. Store it securely.

### 3. Configure the Cowork plugin

In Claude Cowork plugin settings, paste your API key in the **API Key** field.

### 4. Upload your contracts

Upload MSAs, NDAs, SOWs, or any agreement. LF processes and analyzes them automatically.

### 5. Start analyzing

```
/lf:analyze 42
/lf:brief 42
/lf:narrative 42
/lf:perspective 42 buyer
```

Or just ask Claude naturally:

> "Analyze contract 42 and tell me what the biggest risks are."

---

## Slash Commands

| Command | Description |
|---|---|
| `/lf:analyze <id>` | Full risk analysis |
| `/lf:brief <id>` | One-page decision brief |
| `/lf:narrative <id>` | Plain-English walkthrough |
| `/lf:perspective <id> <perspective>` | Switch negotiating perspective |

---

## Architecture

```
Cowork → Claude → MCP protocol (HTTP + SSE)
                      ↓
              lf-cowork-plugin (this repo, Render.com)
                      ↓ REST + X-LF-API-Key
              lf-nextgen-services (LF API)
                      ↓
              PostgreSQL (your contracts, multi-tenant isolated)
```

---

## Self-Hosting

```bash
git clone https://github.com/legalforensics/lf-cowork-plugin
cd lf-cowork-plugin
pip install -r requirements.txt
LF_BASE_URL=https://api.legalforensics.ai python server.py
```

Or deploy to Render using the included `render.yaml`.

---

## Support

- Documentation: [legalforensics.ai/docs](https://legalforensics.ai/docs)
- Issues: [github.com/legalforensics/lf-cowork-plugin/issues](https://github.com/legalforensics/lf-cowork-plugin/issues)
- Email: support@legalforensics.ai
