"""
LegalForensics MCP Server for Claude Cowork

Exposes 8 tools that proxy to the LF REST API using an API key
passed from the Cowork plugin configuration.

Usage:
  LF_BASE_URL=https://api.legalforensics.ai python server.py

The API key is configured by each user in their Cowork plugin settings.
Cowork passes it to the MCP server via the X-LF-API-Key header (per plugin.json).
The server extracts it from the request context and forwards it to the LF API.
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP, Context

LF_BASE_URL = os.environ.get("LF_BASE_URL", "https://app.legalforensics.ai").rstrip("/")
PORT = int(os.environ.get("PORT", 8001))

mcp = FastMCP(
    name="LegalForensics",
    instructions=(
        "Analyze contracts using LegalForensics AI. "
        "Use list_contracts to discover contract IDs, then pass the ID "
        "to analysis tools. Start with get_analysis_report for a quick risk "
        "overview before deeper dives with get_narrative_walkthrough or "
        "get_decision_guidance."
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
async def list_contracts(ctx: Context, search: str = "") -> list[dict]:
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
        contracts = resp.json()

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
# Tool 2: Analysis report
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_analysis_report(ctx: Context, contract_id: int) -> dict:
    """
    Get the full AI risk analysis report for a contract.

    Returns overall risk posture, top risk items with clause citations,
    financial/operational/regulatory exposure bands, and recommended next steps.

    Args:
        contract_id: LF contract ID (get from list_contracts).
    """
    api_key = _get_api_key(ctx)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/analysis-report",
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 3: Decision guidance
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_decision_guidance(ctx: Context, contract_id: int) -> dict:
    """
    Get a decision brief: should you sign, negotiate, or walk away?

    Returns the recommended decision, negotiation priorities, risk-based reasoning,
    and estimated exposure if signed as-is.

    Args:
        contract_id: LF contract ID.
    """
    api_key = _get_api_key(ctx)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/decision-guidance",
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 4: Narrative walkthrough
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_narrative_walkthrough(ctx: Context, contract_id: int) -> str:
    """
    Get a plain-English narrative walkthrough of a contract.

    Explains what the contract does, who holds the risk, what breaks if things
    go wrong, and what a CEO or non-lawyer needs to understand before signing.

    Args:
        contract_id: LF contract ID.
    """
    api_key = _get_api_key(ctx)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/narrative-walkthrough",
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("narrative") or str(data)


# ---------------------------------------------------------------------------
# Tool 5: Standards review
# ---------------------------------------------------------------------------
@mcp.tool()
async def run_standards_review(
    ctx: Context,
    contract_id: int,
    playbook_id: int | None = None,
) -> dict:
    """
    Check a contract against your company's negotiation playbook standards.

    Returns which standards are met or violated, specific clauses that deviate
    from policy, and suggested language fixes.

    Args:
        contract_id: LF contract ID.
        playbook_id: Optional playbook to use. Defaults to company default.
    """
    api_key = _get_api_key(ctx)
    payload: dict = {}
    if playbook_id is not None:
        payload["playbook_id"] = playbook_id

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/standards-review",
            json=payload,
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 6: Set perspective
# ---------------------------------------------------------------------------
@mcp.tool()
async def set_perspective(
    ctx: Context,
    contract_id: int,
    perspective: str,
) -> dict:
    """
    Re-analyze a contract from a specific negotiating perspective.

    Changes which party's interests the AI prioritizes when assessing risk
    and recommending changes.

    Args:
        contract_id: LF contract ID.
        perspective: One of: buyer, seller, licensor, licensee, vendor, customer, neutral.
    """
    valid = {"buyer", "seller", "licensor", "licensee", "vendor", "customer", "neutral"}
    if perspective.lower() not in valid:
        raise ValueError(f"perspective must be one of: {', '.join(sorted(valid))}")

    api_key = _get_api_key(ctx)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{LF_BASE_URL}/api/contracts/{contract_id}/perspective",
            json={"perspective": perspective.lower()},
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 7: Clause details
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_clause_details(ctx: Context, clause_id: int) -> dict:
    """
    Get detailed analysis and AI rewrite suggestion for a specific clause.

    Returns risk level, risk factors, plain-English explanation, AI-suggested
    improved language, and interaction history.

    Args:
        clause_id: Clause ID visible in the analysis report output.
    """
    api_key = _get_api_key(ctx)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            f"{LF_BASE_URL}/api/clause/{clause_id}/details",
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 8: Explain clause (ad-hoc, no contract upload needed)
# ---------------------------------------------------------------------------
@mcp.tool()
async def explain_clause(
    ctx: Context,
    clause_text: str,
    contract_context: str = "",
) -> dict:
    """
    Explain what a clause means in plain English and identify its risks.

    Useful for analyzing pasted contract language without uploading a contract.

    Args:
        clause_text: The raw clause text to analyze.
        contract_context: Optional context such as contract type or governing law
                          to improve analysis accuracy.
    """
    api_key = _get_api_key(ctx)
    payload: dict = {"clause_text": clause_text}
    if contract_context:
        payload["context"] = contract_context

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{LF_BASE_URL}/api/simplification/explain-clause",
            json=payload,
            headers=_lf_headers(api_key),
        )
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    print(f"Starting LegalForensics MCP server on port {PORT}")
    print(f"LF API base: {LF_BASE_URL}")
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = PORT
    mcp.run(transport="sse")
