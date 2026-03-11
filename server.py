"""
LegalForensics MCP Server for Claude Connectors

Exposes 7 tools that proxy to the LF REST API.

Auth: supports two modes (both pass through to the LF backend):
  1. OAuth 2.0 Bearer token  — Authorization: Bearer <cognito_access_token>
  2. API key (legacy)        — X-LF-API-Key: lf_<key>

OAuth 2.0 discovery: GET /.well-known/oauth-authorization-server
  Returns Cognito endpoints + client_id for Claude to drive the auth code + PKCE flow.

Usage:
  LF_BASE_URL=https://app.legalforensics.ai python server.py
"""

import asyncio
import os
import httpx
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.server import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

LF_BASE_URL = os.environ.get("LF_BASE_URL", "https://app.legalforensics.ai").rstrip("/")
PORT = int(os.environ.get("PORT", 8001))

# ---------------------------------------------------------------------------
# Cognito OAuth 2.0 constants
# ---------------------------------------------------------------------------
COGNITO_REGION = "us-east-1"
COGNITO_USER_POOL_ID = "us-east-1_AasSqgTdR"
COGNITO_DOMAIN = "us-east-1aassqgtdr.auth.us-east-1.amazoncognito.com"
COGNITO_CLIENT_ID = "4q850suef3bj1pde4bc5gp75lt"

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


# ---------------------------------------------------------------------------
# OAuth 2.0 discovery endpoint (RFC 8414)
# ---------------------------------------------------------------------------
async def oauth_discovery(request: Request) -> JSONResponse:
    """
    Returns OAuth 2.0 Authorization Server Metadata so Claude can drive
    the authorization code + PKCE flow against AWS Cognito.
    """
    return JSONResponse({
        "issuer": f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}",
        "authorization_endpoint": f"https://{COGNITO_DOMAIN}/oauth2/authorize",
        "token_endpoint": f"https://{COGNITO_DOMAIN}/oauth2/token",
        "jwks_uri": (
            f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com"
            f"/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        ),
        "scopes_supported": ["openid", "email", "profile"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "client_id": COGNITO_CLIENT_ID,
    })


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _get_auth_headers(ctx: Context) -> dict:
    """
    Extract auth credentials from the MCP request context.

    Supports two modes:
      1. OAuth 2.0: Authorization: Bearer <cognito_access_token>
      2. API key:   X-LF-API-Key: lf_<key>

    Returns a dict ready to merge into httpx request headers.
    """
    try:
        headers = ctx.request_context.request.headers

        # OAuth 2.0 Bearer token
        auth_header = headers.get("authorization") or headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:]  # strip "Bearer "
            return {"Authorization": f"Bearer {token}"}

        # Legacy API key
        api_key = headers.get("x-lf-api-key") or headers.get("X-LF-API-Key")
        if api_key:
            return {"X-LF-API-Key": api_key}

    except AttributeError:
        pass

    raise ValueError(
        "No LegalForensics credentials found. "
        "Sign in via OAuth or generate an API key at legalforensics.ai → Settings → API Keys, "
        "then enter it in the plugin configuration."
    )


def _lf_headers(auth: dict) -> dict:
    """Merge auth headers with Content-Type for JSON requests."""
    return {**auth, "Content-Type": "application/json"}


async def _heartbeat_task(ctx: Context, interval: int = 15) -> None:
    """Sends periodic ctx.info() pings to keep the MCP SSE connection alive."""
    elapsed = 0
    _PROGRESS = {
        15: "Still analyzing... (15s)",
        30: "Still analyzing... (30s — Bedrock LLM working on your contract)",
        45: "Almost there... (45s)",
        60: "Still processing... (60s — large contracts take longer)",
        75: "Final checks... (75s)",
        90: "Nearly done... (90s)",
        120: "Extended analysis in progress... (2 min)",
        150: "Still running... (2.5 min)",
    }
    while True:
        await asyncio.sleep(interval)
        elapsed += interval
        msg = _PROGRESS.get(elapsed, f"Still analyzing... ({elapsed}s elapsed)")
        try:
            await ctx.info(msg)
        except Exception:
            pass


async def _fetch_with_heartbeat(
    ctx: Context,
    url: str,
    headers: dict,
    params: dict | None = None,
    timeout: int = 180,
    heartbeat_interval: int = 15,
) -> httpx.Response:
    """
    GET a URL while sending periodic progress pings via ctx.info().

    Keeps the MCP SSE connection alive on Render (30s idle timeout)
    during long-running Bedrock analysis calls (30-90s).
    """
    beat = asyncio.create_task(_heartbeat_task(ctx, heartbeat_interval))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, headers=headers, params=params or {})
    finally:
        beat.cancel()


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
    auth = _get_auth_headers(ctx)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/my-contracts",
            headers=_lf_headers(auth),
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
    auth = _get_auth_headers(ctx)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/stripe/credits",
            headers=_lf_headers(auth),
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
        checkout_url = await _get_checkout_url(auth)
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
    "client", "contractor", "service provider", "provider", "consultant",
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
        perspective: Optional. Your role in this contract — frames all risks,
            verdict, and recommendations from your side of the deal.
            Use the role name (e.g. "landlord", "employee"), not your company name.
            Leave blank for a balanced view without a specific party's perspective.
            Roles grouped by which side of the deal they represent:
            - NDA:                  [disclosing party] vs [receiving party]
            - MSA:                  [client] vs [vendor, service provider]
            - SOW / project:        [client] vs [contractor, consultant, subcontractor]
            - Employment:           [employer] vs [employee, executive]
            - Lease:                [landlord, lessor] vs [tenant, lessee]
            - IP / License:         [licensor] vs [licensee]
            - Supply chain:         [buyer] vs [seller, supplier, distributor, manufacturer]
            - Foundry:              [foundry] vs [fabless]
            - Finance:              [lender, investor] vs [borrower]
            - Data processing:      [data controller] vs [data processor]
            - Franchise:            [franchisor] vs [franchisee]
        force_refresh: Set to true to regenerate the analysis from scratch,
            discarding the cached result. Use when switching perspective for
            the first time or after a contract is re-uploaded.
    """
    auth = _get_auth_headers(ctx)

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
                headers=_lf_headers(auth),
            )
            if resp.status_code == 404:
                raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
            if resp.status_code == 401:
                raise ValueError("Invalid or missing credentials.")
            resp.raise_for_status()
        await ctx.info(f"Perspective set to '{p}'. Generating risk analysis — please wait 30-90 seconds...")
    else:
        await ctx.info("Generating risk analysis — please wait 30-90 seconds...")

    params = {"force_refresh": "true"} if force_refresh else {}
    resp = await _fetch_with_heartbeat(
        ctx,
        f"{LF_BASE_URL}/api/contracts/{contract_id}/analysis-report",
        headers=_lf_headers(auth),
        params=params,
    )
    if resp.status_code == 404:
        raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
    if resp.status_code == 401:
        raise ValueError("Invalid or missing credentials.")
    resp.raise_for_status()
    result = resp.json()
    result["disclaimer"] = DISCLAIMER
    return result


# ---------------------------------------------------------------------------
# Tool 4: Decision guidance
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
        perspective: Optional. Your role in this contract — frames the verdict
            and all recommendations from your side of the deal.
            Use the role name (e.g. "landlord", "employee"), not your company name.
            Leave blank to use the perspective already set via analyze_risks,
            or for a balanced view without a specific party's perspective.
            Roles grouped by which side of the deal they represent:
            - NDA:                  [disclosing party] vs [receiving party]
            - MSA:                  [client] vs [vendor, service provider]
            - SOW / project:        [client] vs [contractor, consultant, subcontractor]
            - Employment:           [employer] vs [employee, executive]
            - Lease:                [landlord, lessor] vs [tenant, lessee]
            - IP / License:         [licensor] vs [licensee]
            - Supply chain:         [buyer] vs [seller, supplier, distributor, manufacturer]
            - Foundry:              [foundry] vs [fabless]
            - Finance:              [lender, investor] vs [borrower]
            - Data processing:      [data controller] vs [data processor]
            - Franchise:            [franchisor] vs [franchisee]
        force_refresh: Set to true to regenerate the verdict from scratch,
            discarding the cached result.
    """
    auth = _get_auth_headers(ctx)

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
                headers=_lf_headers(auth),
            )
            if resp.status_code == 404:
                raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
            if resp.status_code == 401:
                raise ValueError("Invalid or missing credentials.")
            resp.raise_for_status()
        await ctx.info(f"Perspective set to '{p}'. Generating verdict — please wait 30-90 seconds...")
    else:
        await ctx.info("Generating verdict — please wait 30-90 seconds...")

    params = {"force_refresh": "true"} if force_refresh else {}
    resp = await _fetch_with_heartbeat(
        ctx,
        f"{LF_BASE_URL}/api/contracts/{contract_id}/decision-guidance",
        headers=_lf_headers(auth),
        params=params,
    )
    if resp.status_code == 404:
        raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
    if resp.status_code == 401:
        raise ValueError("Invalid or missing credentials.")
    resp.raise_for_status()
    result = resp.json()
    result["disclaimer"] = DISCLAIMER
    return result


# ---------------------------------------------------------------------------
# Tool 5: Narrative walkthrough
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
    auth = _get_auth_headers(ctx)
    await ctx.info("Generating plain-English explanation — this takes 30-60 seconds...")
    resp = await _fetch_with_heartbeat(
        ctx,
        f"{LF_BASE_URL}/api/contracts/{contract_id}/narrative-walkthrough",
        headers=_lf_headers(auth),
        timeout=120,
    )
    if resp.status_code == 404:
        raise ValueError(f"Contract {contract_id} not found or you don't have access to it.")
    if resp.status_code == 401:
        raise ValueError("Invalid or missing credentials.")
    resp.raise_for_status()
    data = resp.json()
    narrative = data.get("narrative") or str(data)
    return f"{narrative}\n\n---\n{DISCLAIMER}"


# ---------------------------------------------------------------------------
# Tool 6: Explain clause (ad-hoc, no contract upload needed)
# ---------------------------------------------------------------------------
@mcp.tool()
async def explain_clause(
    ctx: Context,
    clause_text: str,
    perspective: str = "",
) -> dict:
    """
    Explain what a clause means in plain English and identify its risks.

    Useful for analyzing pasted contract language without uploading a contract.

    Args:
        clause_text: The raw clause text to analyze.
        perspective: Optional. Your role in this contract — frames the explanation
            and negotiation hints from your side of the deal.
            Use the role name (e.g. "landlord", "employee"), not your company name.
            Leave blank for a balanced view without a specific party's perspective.
            Roles grouped by which side of the deal they represent:
            - NDA:                  [disclosing party] vs [receiving party]
            - MSA:                  [client] vs [vendor, service provider]
            - SOW / project:        [client] vs [contractor, consultant, subcontractor]
            - Employment:           [employer] vs [employee, executive]
            - Lease:                [landlord, lessor] vs [tenant, lessee]
            - IP / License:         [licensor] vs [licensee]
            - Supply chain:         [buyer] vs [seller, supplier, distributor, manufacturer]
            - Foundry:              [foundry] vs [fabless]
            - Finance:              [lender, investor] vs [borrower]
            - Data processing:      [data controller] vs [data processor]
            - Franchise:            [franchisor] vs [franchisee]
    """
    if not clause_text or not clause_text.strip():
        raise ValueError("clause_text cannot be empty.")

    auth = _get_auth_headers(ctx)
    payload: dict = {"clause_text": clause_text}
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

    beat = asyncio.create_task(_heartbeat_task(ctx))
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{LF_BASE_URL}/api/plugin/explain-clause",
                json=payload,
                headers=_lf_headers(auth),
            )
            resp.raise_for_status()
            return resp.json()
    finally:
        beat.cancel()


# ---------------------------------------------------------------------------
# Tool 7: Upload contract
# ---------------------------------------------------------------------------
async def _get_checkout_url(auth: dict) -> str | None:
    """Best-effort Stripe checkout URL fetch."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{LF_BASE_URL}/api/stripe/create-checkout",
                headers=_lf_headers(auth),
            )
            return resp.json().get("url")
    except Exception:
        return None


async def _refund_credit(auth: dict) -> None:
    """Best-effort credit refund — called when upload or processing fails."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{LF_BASE_URL}/api/stripe/credits/refund",
                headers=_lf_headers(auth),
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

    auth = _get_auth_headers(ctx)

    # --- Credit check: ensure user has credits before expensive processing ---
    async with httpx.AsyncClient(timeout=10) as client:
        credit_resp = await client.get(
            f"{LF_BASE_URL}/api/stripe/credits",
            headers=_lf_headers(auth),
        )
        credit_resp.raise_for_status()
        credits = credit_resp.json()
        remaining = credits.get("credits_remaining", 0)

    # remaining == -1 means subscription user (unlimited) — skip credit gate
    if remaining == 0:
        checkout_url = await _get_checkout_url(auth)
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
                    headers=_lf_headers(auth),
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
                headers=auth,  # no Content-Type — httpx sets multipart boundary
            )
            resp.raise_for_status()
            body = resp.json()
    except Exception as e:
        if not is_subscription:
            await _refund_credit(auth)
        raise RuntimeError(f"Upload failed: {e}." + ("" if is_subscription else " Your credit has been refunded."))

    contract_uuid = body.get("contract_uuid")
    if not contract_uuid:
        if not is_subscription:
            await _refund_credit(auth)
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

    status_url = f"{LF_BASE_URL}/api/contracts/{contract_uuid}/status"

    for attempt in range(_poll_attempts):
        # Fast polling for first 15s (attempts 0-4), then 3s intervals
        await asyncio.sleep(1 if attempt < 15 else 3)

        if attempt in _progress_messages:
            await ctx.info(_progress_messages[attempt])

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                sr = await client.get(status_url, headers=auth)
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
                last_credit_url = await _get_checkout_url(auth)
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
                                headers=_lf_headers(auth),
                            )
                        result["perspective"] = p
                    except Exception:
                        pass  # non-fatal

            return result

        if status.get("status") == "failed":
            if not is_subscription:
                await _refund_credit(auth)
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
    mcp_app = mcp.streamable_http_app()

    # Wrap MCP app with a discovery endpoint for OAuth 2.0
    app = Starlette(
        routes=[
            Route("/.well-known/oauth-authorization-server", oauth_discovery),
            Mount("/", app=mcp_app),
        ]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    uvicorn.run(app, host="0.0.0.0", port=PORT)
