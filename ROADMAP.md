# LegalForensics Connector — Roadmap

## Shipped

- OAuth 2.0 via AWS Cognito (Authorization Code + PKCE)
- Auto-provisioning: new OAuth users get Company + User + 1 free credit on first call
- Legacy API key support (X-LF-API-Key header)
- 7 MCP tools: upload_contract, analyze_risks, sign_or_negotiate, explain_contract, explain_clause, my_contracts, my_credits
- Perspective framing: 30+ roles across 11 contract types
- Heartbeat keep-alive for long-running Bedrock analysis
- Non-blocking upload: upload_contract returns immediately, analysis tools wait with progress messages
- Stripe credit billing with checkout link generation
- Anthropic Connectors Directory submission

---

## Near-Term

### legalforensics.ai/claude — User Setup Page
A dedicated how-to page for connecting LegalForensics to Claude.
- Step-by-step setup instructions
- Quick-start prompts to copy-paste
- Google Doc sharing instructions
- FAQ

### Stripe Testing via Connector
End-to-end test of the zero-credit flow from claude.ai:
- Upload attempt with 0 credits → purchase link returned
- Post-payment credit refresh → retry upload succeeds

---

## Contract History Intelligence (Moat Features)

These features leverage the user's existing contract portfolio — something Claude alone can never replicate. Every contract reviewed makes the next review smarter.

### Tier 1 — Personal Baseline Comparison
Compare new contracts against the user's own history.

- "This liability cap ($50K) is lower than your last 3 vendor agreements (avg $250K)"
- "You've never signed a non-compete this broad before"
- "Auto-renewal clause detected — you've been caught by this in 2 prior contracts"
- "This NDA is 5 years — your typical is 2"
- "You always get 30-day termination notice — this gives you 7"

Implementation: on analyze_risks, fetch user's prior contracts of same type and diff key fields.

### Tier 2 — Portfolio Outlier Detection
Flag statistically unusual terms across the user's full contract library.

- Liability caps significantly below/above personal average
- Unusually short or long termination notice periods
- Jurisdiction changes (governing law switched from user's usual state)
- Payment terms outside normal range

Implementation: aggregate field extraction results across company_id, compute percentiles.

### Tier 3 — Cross-Contract Conflict Detection
Identify obligations in new contracts that conflict with existing active contracts.

- Exclusivity clauses conflicting with existing distributor agreements
- IP ownership terms conflicting with existing employment agreements
- Confidentiality obligations that overlap with existing NDAs

Implementation: LLM comparison pass across active contracts filtered by clause type.

### Tier 4 — Renewal and Expiry Calendar
Surface contracts expiring or auto-renewing in the next 30/60/90 days.

- Proactive alerts before auto-renewal windows close
- "You have 3 contracts renewing in the next 30 days"

Implementation: scheduled job on term_duration + effective_date fields already extracted.

### Tier 5 — Negotiation Memory
Learn from the user's own negotiation history.

- "You pushed back on this indemnification clause with Acme — here's the language you used"
- "You've successfully removed non-solicitation clauses in 2 prior agreements"
- Build a personal playbook from won and lost negotiation points

Implementation: store accepted/rejected clause variants with negotiation outcome labels.

---

## Platform Expansion

- **Claude Code integration** — slash commands for developers reviewing API/SDK agreements
- **Slack integration** — contract review triggered by Slack message or file share
- **Email integration** — forward a contract PDF to review@legalforensics.ai, get analysis back
- **Multi-user company accounts** — shared contract library across a team

---

## Pricing Evolution

- Current: 1 credit per upload, pay-as-you-go
- Planned: subscription tier with unlimited uploads + playbook review + history intelligence features
- Enterprise: volume pricing + SSO + dedicated contract library
