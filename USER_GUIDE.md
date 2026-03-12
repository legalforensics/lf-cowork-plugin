# LegalForensics Connector — User Guide

Review contracts directly inside Claude. No dashboards, no separate software.

---

## Requirements

- Claude Pro or Claude Team account (claude.ai)
- 2 minutes to connect

---

## 1. Connect LegalForensics to Claude

1. Go to **claude.ai → Settings → Connectors**
2. Click **Add custom connector**
3. Fill in:
   - **Name**: `LegalForensics`
   - **Remote MCP server URL**: `https://lf-cowork-plugin.onrender.com/mcp`
   - **OAuth Client ID**: `4q850suef3bj1pde4bc5gp75lt`
   - **OAuth Client Secret**: *(leave blank)*
4. Click **Save**
5. Click **Connect** → Cognito login page opens
6. Sign in (or create a new account — it takes 30 seconds)
7. You're connected. New accounts receive **1 free credit** automatically.

---

## 2. Quick Tests — No Upload Needed

### Check your credits
> "How many credits do I have?"

### Explain a clause (free — no credit required)
Paste any clause you find confusing:

> "Explain this clause: 'The vendor shall not be liable for any indirect, incidental, or consequential damages arising out of or related to this agreement, even if advised of the possibility of such damages.'"

Add your role to frame it from your side:

> "Explain this clause from the buyer's perspective: [paste clause]"

### List your contracts
> "Show me my contracts"

---

## 3. Upload a Contract (costs 1 credit)

### Option A — Paste contract text
> "Analyze this contract: [paste the full contract text here]"

Claude will upload it and analyze it automatically.

### Option B — Google Doc link

1. Open your contract in Google Docs
2. Click **Share** → **Change to Anyone with the link** → **Viewer**
3. Copy the link (must start with `docs.google.com/document/d/...`)
4. Ask Claude:

> "Analyze this contract: https://docs.google.com/document/d/YOUR_DOC_ID/edit"

**Important:** Google Drive file links (`drive.google.com/file/d/...`) are not supported. Use Google Docs links only. For PDF or Word files, paste the text instead.

---

## 4. Analyze a Contract

Once uploaded, Claude returns a `contract_id`. Use it with any analysis tool.

### Risk analysis
> "Analyze the risks in contract 205"
> "What are the biggest risks in contract 205 from the tenant's perspective?"

### Sign / negotiate / walk away verdict
> "Should I sign contract 205?"
> "Should I sign contract 205 as the employee — or push back?"

### Plain-English walkthrough
> "Explain contract 205 in plain English"

### Combine upload and analysis in one message
> "Analyze this contract and tell me if I should sign it as the buyer: [paste text]"

Claude will upload it and immediately run the analysis.

---

## 5. Perspectives

Add your role to any analysis to frame results from your side of the deal.

| Contract Type | Your role options |
|---|---|
| NDA | disclosing party, receiving party |
| MSA | client, vendor, service provider |
| Employment | employer, employee |
| Lease | landlord, tenant, lessor, lessee |
| SOW / Project | client, contractor, consultant |
| IP / License | licensor, licensee |
| Supply chain | buyer, seller, supplier, distributor |
| Franchise | franchisor, franchisee |
| Finance | lender, borrower, investor |
| Data processing | data controller, data processor |

**Example:**
> "Analyze contract 205 from the landlord's perspective"
> "Should I sign contract 205 as the franchisee?"

---

## 6. Credits

| Action | Cost |
|---|---|
| Upload a contract | 1 credit |
| Explain a clause | Free |
| Re-analyze an existing contract | Free (cached) |
| Force re-analysis | Free |

### Check balance
> "How many credits do I have?"

### Buy more credits
> "I need more credits"

Claude will return a checkout link. After payment, credits are added instantly.

---

## 7. Tips

**Contracts take 2–3 minutes to process on first upload.** Claude will show progress messages while it waits. Subsequent analyses on the same contract are instant (cached).

**Specify your role upfront** for the most useful output. "Analyze this NDA" gives a neutral view. "Analyze this NDA as the receiving party" gives you actionable risks specific to your position.

**Re-use contract IDs.** Once uploaded, a contract stays in your account. Ask "show me my contracts" anytime to see all contract IDs.

**Large contracts (30+ pages)** are analyzed on the first ~40,000 characters. Use `explain_clause` to analyze specific sections deeper in long documents.

---

## 8. Sample Prompts to Copy-Paste

```
Show me my contracts

How many credits do I have?

Explain this clause: "[paste clause text]"

Analyze this contract: [paste contract text or Google Doc link]

Analyze the risks in contract 205

Analyze the risks in contract 205 from the tenant's perspective

Should I sign contract 205 as the employee?

What should I push back on in contract 205?

Explain contract 205 in plain English
```

---

## Support

- Setup page: [legalforensics.ai/claude](https://legalforensics.ai/claude)
- Email: amit@legalforensics.ai

---

*LegalForensics is an AI tool, not a law firm. Analysis is for informational purposes only. Consult a qualified attorney before signing any contract.*
