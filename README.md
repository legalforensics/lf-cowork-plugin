# LegalForensics Cowork Plugin

Contract risk analysis for Claude Cowork — analyze any MSA, NDA, or SOW directly from your workspace.

## What it does

The LegalForensics plugin gives Claude access to your contract library via 8 MCP tools:

| Tool | What it returns |
|---|---|
| `list_contracts` | All contracts in your LF account |
| `get_analysis_report` | Full AI risk analysis with risk posture + top risks |
| `get_decision_guidance` | Sign / negotiate / walk away decision brief |
| `get_narrative_walkthrough` | Plain-English contract walkthrough for non-lawyers |
| `run_standards_review` | Compliance check against your company playbook |
| `set_perspective` | Re-analyze from buyer / seller / vendor perspective |
| `get_clause_details` | Deep dive on a single clause with AI rewrite suggestion |
| `explain_clause` | Explain pasted clause text without uploading a contract |

## Setup

### 1. Create a LegalForensics account

Sign up at [legalforensics.ai](https://legalforensics.ai) — takes 2 minutes.

### 2. Upload your contracts

Upload MSAs, NDAs, SOWs, or any agreement. LF processes and analyzes them automatically.

### 3. Generate an API key

Go to **Settings → API Keys** → click **Generate New Key**.

Copy the key — it's shown once. Store it securely.

### 4. Configure the Cowork plugin

In Claude Cowork plugin settings, paste your API key in the **API Key** field.

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
| `/lf:standards-check <id>` | Playbook compliance review |
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
