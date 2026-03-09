"""
LegalForensics MCP Server for Claude Cowork

Exposes 7 tools that proxy to the LF REST API using an API key
passed from the Cowork plugin configuration.

Usage:
  LF_BASE_URL=https://api.legalforensics.ai python server.py

The API key is configured by each user in their Cowork plugin settings.
Cowork passes it to the MCP server via the X-LF-API-Key header (per plugin.json).
The server extracts it from the request context and forwards it to the LF API.
"""

import asyncio
import os
import httpx
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.server import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware

LF_BASE_URL = os.environ.get("LF_BASE_URL", "https://app.legalforensics.ai").rstrip("/")
PORT = int(os.environ.get("PORT", 8001))

DISCLAIMER = (
    "⚠️ AI-generated analysis. For informational purposes only — not legal advice. "
    "Consult qualified legal counsel before signing or acting on any contract. "
    "User Agreement: https://app.legalforensics.ai/assets/docs/user-agreement.pdf"
)

mcp = FastMCP(
    name="LegalForensics",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    instructions=(
        "Analyze contracts using LegalForensics AI. "
        "Use my_contracts to discover contract IDs, then pass the ID "
        "to analysis tools. Start with analyze_risks for a full risk "
        "overview, sign_or_negotiate for a sign/negotiate/walk-away decision, or "
        "explain_contract for a plain-English explanation."
    ),
)


def _lf_headers(api_key: str) -> dict:
    """Build request headers for the LF API."""
    return {
        "X-LF-API-Key": api_key,
        "Content-Type": "application/json",
    }


def _get_api_key(ctx: Context) -> str:
    """
    Extract the LF API key from the MCP request context.

    In Cowork, the user configures their API key in plugin settings.
    Cowork forwards it to this MCP server via the X-LF-API-Key HTTP header.
    FastMCP exposes request headers via ctx.request_context.request.headers.
    """
    try:
        headers = ctx.request_context.request.headers
        api_key = headers.get("x-lf-api-key") or headers.get("X-LF-API-Key")
        if api_key:
            return api_key
    except AttributeError:
        pass

    raise ValueError(
        "No LegalForensics API key found. "
        "Generate one at legalforensics.ai → Settings → API Keys, "
        "then enter it in the Cowork plugin configuration."
    )


# ---------------------------------------------------------------------------
# Tool 1: List contracts
# ---------------------------------------------------------------------------
@mcp.tool()
async def my_contracts(ctx: Context, search: str = "") -> list[dict]:
    """
    List all contracts in your LegalForensics account.

    Args:
        search: Optional keyword to filter contracts by title or type.

    Returns a list of contracts with id, title, contract_type, and status.
    Use the returned 'id' values with the other analysis tools.
    """
    api_key = _get_api_key(ctx)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/my-contracts",
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        contracts = resp.json().get("contracts", [])

    if search:
        q = search.lower()
        contracts = [
            c for c in contracts
            if q in (c.get("title") or "").lower()
            or q in (c.get("contract_type") or "").lower()
        ]

    return [
        {
            "id": c.get("id"),
            "title": c.get("title"),
            "contract_type": c.get("contract_type"),
            "status": c.get("status"),
            "created_at": c.get("created_at"),
        }
        for c in contracts
    ]


# ---------------------------------------------------------------------------
# Tool 2: Credits
# ---------------------------------------------------------------------------
@mcp.tool()
async def my_credits(ctx: Context) -> dict:
    """
    Check your LegalForensics credit balance.

    Each contract upload costs 1 credit. Subscription users have unlimited uploads.
    Returns credits remaining, credits used, and a purchase link if balance is zero.
    """
    api_key = _get_api_key(ctx)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/stripe/credits",
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        credits = resp.json()

    remaining = credits.get("credits_remaining", 0)

    if credits.get("subscription_user"):
        return {"plan": "subscription", "uploads": "unlimited"}

    result: dict = {
        "credits_remaining": remaining,
        "credits_used": credits.get("credits_used", 0),
    }

    if remaining == 0:
        checkout_url = await _get_checkout_url(api_key)
        result["message"] = "No credits remaining."
        if checkout_url:
            result["purchase_url"] = checkout_url
            result["message"] += f" Purchase more at: {checkout_url}"
    else:
        result["message"] = f"You have {remaining} credit{'s' if remaining != 1 else ''} remaining."

    return result


# ---------------------------------------------------------------------------
# Tool 3: Analysis report
# ---------------------------------------------------------------------------
_VALID_PERSPECTIVES = {
    # NDA
    "disclosing party", "receiving party",
    # buyer / seller
    "buyer", "seller", "purchaser", "vendor",
    # property
    "tenant", "landlord", "lessor", "lessee",
    # employment
    "employer", "employee",
    # IP / licensing
    "licensor", "licensee",
    # services
    "client", "contractor", "service provider", "consultant",
    # franchise
    "franchisor", "franchisee",
    # finance
    "lender", "borrower", "investor",
    # supply chain / manufacturing
    "manufacturer", "distributor", "reseller", "supplier",
    # semiconductor / foundry
    "foundry", "fabless",
    # data
    "data controller", "data processor",
    # neutral
    "neutral",
}


@mcp.tool()
async def analyze_risks(
    ctx: Context,
    contract_id: int,
    perspective: str = "",
    force_refresh: bool = False,
) -> dict:
    """
    Get the full AI risk analysis report for a contract.

    Returns overall risk posture, top risk items with clause citations,
    financial/operational/regulatory exposure bands, and recommended next steps.

    Args:
        contract_id: LF contract ID (get from my_contracts).
        perspective: Optional. Your role in this contract. Frames all risks and
            recommendations from your side of the deal. Leave blank for neutral.
            Common roles by contract type:
            - NDA: disclosing party, receiving party
            - MSA / SOW: client, service provider, contractor, consultant
            - Employment: employer, employee
            - Lease: landlord, tenant, lessor, lessee
            - IP / License: licensor, licensee
            - Supply chain: buyer, seller, supplier, manufacturer, distributor
            - Foundry / semiconductor: foundry, fabless
            - Finance: lender, borrower, investor
            - Data processing: data controller, data processor
            - Franchise: franchisor, franchisee
            Full list: buyer, seller, purchaser, vendor, tenant, landlord,
            lessor, lessee, employer, employee, licensor, licensee, client,
            contractor, service provider, consultant, franchisor, franchisee,
            lender, borrower, investor, manufacturer, distributor, reseller,
            supplier, foundry, fabless, data controller, data processor, neutral.
        force_refresh: Set to true to regenerate the analysis from scratch,
            discarding the cached result. Use when switching perspective for
            the first time or after a contract is re-uploaded.
    """
    api_key = _get_api_key(ctx)

    # Validate and set perspective before fetching analysis
    if perspective and perspective.strip():
        p = perspective.strip().lower()
        if p not in _VALID_PERSPECTIVES:
            valid_list = ", ".join(sorted(_VALID_PERSPECTIVES))
            raise ValueError(
                f"'{perspective}' is not a recognised contract role. "
                f"Please use one of: {valid_list}."
            )
        # Set perspective on the backend (persists for this contract)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LF_BASE_URL}/api/contracts/{contract_id}/perspective",
                json={"party": p},
                headers=_lf_headers(api_key),
            )
            if resp.status_code == 404:
                raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
            if resp.status_code == 401:
                raise ValueError("Invalid or missing API key.")
            resp.raise_for_status()
        await ctx.info(f"Perspective set to '{p}'. Fetching analysis...")
    else:
        await ctx.info("Fetching risk analysis...")

    params = {"force_refresh": "true"} if force_refresh else {}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/analysis-report",
            headers=_lf_headers(api_key),
            params=params,
        )
        if resp.status_code == 404:
            raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
        if resp.status_code == 401:
            raise ValueError("Invalid or missing API key.")
        resp.raise_for_status()
        result = resp.json()
        result["disclaimer"] = DISCLAIMER
        return result


# ---------------------------------------------------------------------------
# Tool 3: Decision guidance
# ---------------------------------------------------------------------------
@mcp.tool()
async def sign_or_negotiate(
    ctx: Context,
    contract_id: int,
    perspective: str = "",
    force_refresh: bool = False,
) -> dict:
    """
    Get a decision brief: should you sign, negotiate, or walk away?

    Returns verdict (sign / negotiate / walk away), reasoning, negotiation
    priorities, structural risk assessment, and top 3 actions.

    Args:
        contract_id: LF contract ID (get from my_contracts).
        perspective: Optional. Your role in this contract. Frames the verdict
            and all recommendations from your side of the deal. Leave blank to
            use the perspective already set via analyze_risks, or for neutral.
            Common roles by contract type:
            - NDA: disclosing party, receiving party
            - MSA / SOW: client, service provider, contractor, consultant
            - Employment: employer, employee
            - Lease: landlord, tenant, lessor, lessee
            - IP / License: licensor, licensee
            - Supply chain: buyer, seller, supplier, manufacturer, distributor
            - Foundry / semiconductor: foundry, fabless
            - Finance: lender, borrower, investor
            - Data processing: data controller, data processor
            - Franchise: franchisor, franchisee
        force_refresh: Set to true to regenerate the verdict from scratch,
            discarding the cached result.
    """
    api_key = _get_api_key(ctx)

    if perspective and perspective.strip():
        p = perspective.strip().lower()
        if p not in _VALID_PERSPECTIVES:
            valid_list = ", ".join(sorted(_VALID_PERSPECTIVES))
            raise ValueError(
                f"'{perspective}' is not a recognised contract role. "
                f"Please use one of: {valid_list}."
            )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LF_BASE_URL}/api/contracts/{contract_id}/perspective",
                json={"party": p},
                headers=_lf_headers(api_key),
            )
            if resp.status_code == 404:
                raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
            if resp.status_code == 401:
                raise ValueError("Invalid or missing API key.")
            resp.raise_for_status()
        await ctx.info(f"Perspective set to '{p}'. Generating verdict...")
    else:
        await ctx.info("Generating verdict...")

    params = {"force_refresh": "true"} if force_refresh else {}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/decision-guidance",
            headers=_lf_headers(api_key),
            params=params,
        )
        if resp.status_code == 404:
            raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
        if resp.status_code == 401:
            raise ValueError("Invalid or missing API key.")
        resp.raise_for_status()
        result = resp.json()
        result["disclaimer"] = DISCLAIMER
        return result


# ---------------------------------------------------------------------------
# Tool 4: Narrative walkthrough
# ---------------------------------------------------------------------------
@mcp.tool()
async def explain_contract(ctx: Context, contract_id: int) -> str:
    """
    Get a plain-English narrative walkthrough of a contract.

    Explains what the contract does, who holds the risk, what breaks if things
    go wrong, and what a CEO or non-lawyer needs to understand before signing.

    Args:
        contract_id: LF contract ID.
    """
    api_key = _get_api_key(ctx)
    await ctx.info("Generating plain-English explanation — this takes 30-60 seconds...")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/narrative-walkthrough",
            headers=_lf_headers(api_key),
        )
        if resp.status_code == 404:
            raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
        if resp.status_code == 401:
            raise ValueError("Invalid or missing API key.")
        resp.raise_for_status()
        data = resp.json()
        narrative = data.get("narrative") or str(data)
        return f"{narrative}\n\n---\n{DISCLAIMER}"


# ---------------------------------------------------------------------------
# Tool 7: Explain clause (ad-hoc, no contract upload needed)
# ---------------------------------------------------------------------------
@mcp.tool()
async def explain_clause(
    ctx: Context,
    clause_text: str,
    contract_context: str = "",
    perspective: str = "",
) -> dict:
    """
    Explain what a clause means in plain English and identify its risks.

    Useful for analyzing pasted contract language without uploading a contract.

    Args:
        clause_text: The raw clause text to analyze.
        contract_context: Optional. Contract type to improve accuracy
                          (e.g. "NDA", "MSA", "employment agreement").
        perspective: Optional. Your role in this contract. Frames the explanation
            and negotiation hints from your side of the deal. Leave blank for neutral.
            Common roles by contract type:
            - NDA: disclosing party, receiving party
            - MSA / SOW: client, service provider, contractor, consultant
            - Employment: employer, employee
            - Lease: landlord, tenant, lessor, lessee
            - IP / License: licensor, licensee
            - Supply chain: buyer, seller, supplier, manufacturer, distributor
            - Foundry / semiconductor: foundry, fabless
            - Finance: lender, borrower, investor
            - Data processing: data controller, data processor
            - Franchise: franchisor, franchisee
    """
    if not clause_text or not clause_text.strip():
        raise ValueError("clause_text cannot be empty.")

    api_key = _get_api_key(ctx)
    payload: dict = {"clause_text": clause_text}
    if contract_context:
        payload["context"] = contract_context
    if perspective and perspective.strip():
        p = perspective.strip().lower()
        if p not in _VALID_PERSPECTIVES:
            valid_list = ", ".join(sorted(_VALID_PERSPECTIVES))
            raise ValueError(
                f"'{perspective}' is not a recognised contract role. "
                f"Please use one of: {valid_list}."
            )
        payload["perspective"] = p

    await ctx.info("Analyzing clause — generating plain-English explanation (30-90 seconds)...")

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{LF_BASE_URL}/api/plugin/explain-clause",
            json=payload,
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 9: Upload contract
# ---------------------------------------------------------------------------
async def _get_checkout_url(api_key: str) -> str | None:
    """Best-effort Stripe checkout URL fetch."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{LF_BASE_URL}/api/stripe/create-checkout",
                headers=_lf_headers(api_key),
            )
            return resp.json().get("url")
    except Exception:
        return None


async def _refund_credit(api_key: str) -> None:
    """Best-effort credit refund — called when upload or processing fails."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{LF_BASE_URL}/api/stripe/credits/refund",
                headers=_lf_headers(api_key),
            )
    except Exception:
        pass  # Logged server-side — don't mask the original error


def _normalize_file_url(url: str) -> str:
    """Convert Google Docs share URLs to direct DOCX export URLs."""
    import re
    # Reject Google Drive file links — they serve an auth/redirect page, not raw bytes
    if re.search(r"drive\.google\.com/file/d/", url):
        raise ValueError(
            "Google Drive file links are not supported. "
            "Please share the file as a Google Doc (docs.google.com/document/...) "
            "or paste the contract text directly using text_content."
        )
    # https://docs.google.com/document/d/FILE_ID/edit...
    m = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return f"https://docs.google.com/document/d/{m.group(1)}/export?format=docx"
    return url


def _infer_content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
    }.get(ext, "application/octet-stream")


@mcp.tool()
async def upload_contract(
    ctx: Context,
    file_url: str = "",
    text_content: str = "",
    title: str = "",
    contract_type: str = "",
    perspective: str = "",
) -> dict:
    """
    Upload a contract to LegalForensics and wait for it to finish processing.

    Provide EITHER a URL to the contract file OR the raw contract text — not both.

    After upload completes, returns the contract_id which you can pass directly
    to analyze_risks, sign_or_negotiate, explain_contract, etc.

    Args:
        file_url: URL to the contract file. Currently supported:
                  - Google Docs share link (docs.google.com/document/d/...) — automatically
                    exported as DOCX. The document must be shared publicly ("Anyone with link").
                  NOT supported: Google Drive file links, Dropbox, SharePoint, OneDrive,
                  or local files — paste the contract text using text_content instead.
        text_content: Raw contract text to upload as a .txt file.
                      Use this when the user pastes contract language into the chat.
        title: Required display title for the contract (e.g. "Acme NDA 2026").
        contract_type: Optional contract type hint.

                       Fully supported (deepest risk analysis, clause-level detail):
                         - "NDA" — Non-Disclosure Agreement
                         - "MSA" — Master Services Agreement
                         - "SOW" — Statement of Work
                         - "DPA" — Data Processing Agreement
                         - "IP Agreement" — IP / Software Licensing
                         - "Healthcare Procurement" — Medical supply and distribution

                       Any other type is accepted and processed with general contract analysis
                       (same risk posture, verdict, and renegotiation asks — just without
                       type-specific clause patterns). Common examples:
                         - "Lease" — commercial or residential
                         - "Employment Agreement" — offer letters, employment contracts
                         - "Consulting Agreement"
                         - "Contractor Agreement" — freelancer / independent contractor
                         - "Service Agreement"
                         - "Distribution Agreement"
                         - "Franchise Agreement"
                         - "Partnership Agreement"
                       If you frequently need a specific type not listed above, let us know —
                       we prioritize specialized support based on demand.

                       If omitted, LF auto-classifies the contract type.
        perspective: Your role in this contract as free text (e.g. "buyer", "tenant",
                     "employee", "licensee", "franchisee"). Sets the perspective for
                     all subsequent analysis tools. If omitted, analysis is neutral.
                     You can also change this later by passing a new perspective to
                     analyze_risks or sign_or_negotiate.
    """
    if not title or not title.strip():
        raise ValueError("title is required. Provide a short name for the contract (e.g. 'Acme NDA 2026').")
    if not file_url and not text_content:
        raise ValueError("Provide either file_url or text_content.")
    if file_url and text_content:
        raise ValueError("Provide only one of file_url or text_content, not both.")

    api_key = _get_api_key(ctx)

    # --- Credit check: ensure user has credits before expensive processing ---
    async with httpx.AsyncClient(timeout=10) as client:
        credit_resp = await client.get(
            f"{LF_BASE_URL}/api/stripe/credits",
            headers=_lf_headers(api_key),
        )
        credit_resp.raise_for_status()
        credits = credit_resp.json()
        remaining = credits.get("credits_remaining", 0)

    # remaining == -1 means subscription user (unlimited) — skip credit gate
    if remaining == 0:
        checkout_url = await _get_checkout_url(api_key)
        msg = "You have no credits remaining.\n\n"
        if checkout_url:
            msg += f"👉 Purchase a credit: {checkout_url}\n\n"
        else:
            msg += "Visit legalforensics.ai to purchase credits.\n\n"
        msg += "Once payment is complete, come back and retry the upload."
        raise ValueError(msg)

    # --- Resolve file bytes and filename ---
    if file_url:
        file_url = _normalize_file_url(file_url)
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            dl = await client.get(file_url)
            dl.raise_for_status()
            file_bytes = dl.content
        # Derive filename — Google and other URLs often have no usable filename in path
        import re as _re
        base = title.replace(" ", "_")[:50]
        fmt_match = _re.search(r"[?&]format=(\w+)", file_url)
        if fmt_match:
            # Google Docs export: ?format=docx
            filename = f"{base}.{fmt_match.group(1)}"
        else:
            raw_name = file_url.split("/")[-1].split("?")[0]
            filename = raw_name if "." in raw_name else f"{base}.pdf"
    else:
        file_bytes = text_content.encode("utf-8")
        slug = (title or "contract").replace(" ", "_")[:50]
        filename = f"{slug}.txt"

    content_type = _infer_content_type(filename)

    # --- Validate file type before spending a credit ---
    _supported_exts = {".pdf", ".docx", ".doc", ".txt"}
    _ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if _ext not in _supported_exts:
        raise ValueError(
            f"Unsupported file type '{_ext}'. Supported formats: PDF, DOCX, DOC, TXT. "
            "For other formats, copy and paste the contract text using text_content."
        )

    # --- Deduct credit upfront (skip for subscription users) ---
    is_subscription = remaining == -1
    if not is_subscription:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{LF_BASE_URL}/api/stripe/credits/deduct",
                    headers=_lf_headers(api_key),
                )
        except Exception as e:
            raise RuntimeError(f"Failed to reserve credit before upload: {e}")

    # --- POST multipart to LF API ---
    await ctx.info(f"Uploading '{title}' ({len(file_bytes):,} bytes)...")
    form_data: dict = {}
    if title:
        form_data["title"] = title
    if contract_type:
        form_data["contract_type"] = contract_type

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{LF_BASE_URL}/api/contracts/upload",
                files={"file": (filename, file_bytes, content_type)},
                data=form_data,
                headers={"X-LF-API-Key": api_key},
            )
            resp.raise_for_status()
            body = resp.json()
    except Exception as e:
        if not is_subscription:
            await _refund_credit(api_key)
        raise RuntimeError(f"Upload failed: {e}." + ("" if is_subscription else " Your credit has been refunded."))

    contract_uuid = body.get("contract_uuid")
    if not contract_uuid:
        if not is_subscription:
            await _refund_credit(api_key)
        return body

    # --- Poll status until done ---
    # Poll for up to 90s then return early — contract continues processing in
    # the background and user can retrieve it with my_contracts.
    # Poll schedule: 1s for first 15 attempts, then 3s.
    _large_contract = len(file_bytes) > 500_000  # ~5-6 pages of text PDF
    _poll_attempts = 30  # ~60s max (15×1s + 15×3s)
    _progress_messages = {
        0:  "Contract uploaded. Extracting text and structure...",
        5:  "Classifying contract type and identifying clauses...",
        10: "Running risk assessment and field extraction...",
        20: "Finalizing analysis...",
    }

    await ctx.info("Contract received. Starting AI analysis pipeline...")

    poll_headers = {"X-LF-API-Key": api_key}
    status_url = f"{LF_BASE_URL}/api/contracts/{contract_uuid}/status"

    for attempt in range(_poll_attempts):
        # Fast polling for first 15s (attempts 0-4), then 3s intervals
        await asyncio.sleep(1 if attempt < 15 else 3)

        if attempt in _progress_messages:
            await ctx.info(_progress_messages[attempt])

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                sr = await client.get(status_url, headers=poll_headers)
                sr.raise_for_status()
                status = sr.json()
            except httpx.HTTPError:
                continue  # transient network hiccup — keep polling

        if status.get("status") == "completed":
            result = {
                "contract_id": status.get("contract_id"),
                "title": status.get("title"),
                "contract_type": status.get("contract_type"),
                "filename": status.get("filename"),
                "message": (
                    "Contract uploaded and processed. "
                    "Use the contract_id with analyze_risks, "
                    "sign_or_negotiate, or explain_contract."
                ),
            }
            # Warn for large contracts (quality may be reduced)
            if _large_contract:
                result["large_contract_notice"] = (
                    "This contract is large. Risk analysis and AI summary cover the first "
                    "~5-6 pages of the document. Substantive clauses deeper in the contract "
                    "(termination, liability, performance, export controls) may not be fully "
                    "captured. Use explain_clause to analyse specific sections you are "
                    "concerned about."
                )
            # Warn when this was the last credit
            if remaining == 1:
                last_credit_url = await _get_checkout_url(api_key)
                warning = "This was your last credit. "
                warning += f"Purchase more at: {last_credit_url}" if last_credit_url else "Visit legalforensics.ai to purchase credits."
                result["warning"] = warning
            # Auto-set perspective if provided and valid
            if perspective and perspective.strip() and result.get("contract_id"):
                p = perspective.strip().lower()
                if p in _VALID_PERSPECTIVES:
                    try:
                        async with httpx.AsyncClient(timeout=15) as pclient:
                            await pclient.post(
                                f"{LF_BASE_URL}/api/contracts/{result['contract_id']}/perspective",
                                json={"party": p},
                                headers=_lf_headers(api_key),
                            )
                        result["perspective"] = p
                    except Exception:
                        pass  # non-fatal

            return result

        if status.get("status") == "failed":
            if not is_subscription:
                await _refund_credit(api_key)
            raise RuntimeError(
                f"Contract processing failed: {status.get('error', 'unknown error')}."
                + ("" if is_subscription else " Your credit has been refunded.")
            )

    # Processing still running after timeout — credit already deducted, no refund
    # (contract may still complete in background)
    return {
        "status": "processing",
        "contract_uuid": contract_uuid,
        "message": (
            "Contract uploaded and being processed in the background. "
            "Large contracts (30+ pages) can take 2–5 minutes. "
            "Run my_contracts in 2–3 minutes to find your contract, "
            "then call analyze_risks with the contract_id."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    print(f"Starting LegalForensics MCP server on port {PORT}")
    print(f"LF API base: {LF_BASE_URL}")
    mcp.settings.port = PORT
    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    uvicorn.run(app, host="0.0.0.0", port=PORT)
