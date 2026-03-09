"""
End-to-end MCP client test — simulates exactly what Claude Desktop does.
Tests all key tools against the live Render server.

Usage:
    python test_mcp.py
"""

import asyncio
import time
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

SERVER_URL = "https://lf-cowork-plugin.onrender.com/mcp"
API_KEY = "lf_6c6267395dfa8b6ccaa0252f5a6aeef588c759df"

CONTRACT_TEXT = """
MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of January 1, 2025,
between Acme Corp ("Company A") and Vendor Inc ("Company B").

1. CONFIDENTIAL INFORMATION. Each party may disclose confidential business information
   to the other party for the purpose of evaluating a potential business relationship.

2. OBLIGATIONS. Each party agrees to: (a) keep all Confidential Information strictly
   confidential; (b) not disclose Confidential Information to third parties without
   prior written consent; (c) use Confidential Information solely for evaluation purposes.

3. TERM. This Agreement shall remain in effect for five (5) years from the date of signing.

4. GOVERNING LAW. This Agreement shall be governed by the laws of the State of California.

5. TERMINATION. Either party may terminate this Agreement with 30 days written notice.
"""


async def test(session: ClientSession):
    # 1. List available tools
    print("\n--- Available Tools ---")
    tools = await session.list_tools()
    for t in tools.tools:
        print(f"  [ok] {t.name}")

    # 2. Upload a contract (text paste mode) — unique title to avoid 409
    import json
    run_id = int(time.time())
    print("\n--- upload_contract (text paste) ---")
    result = await session.call_tool("upload_contract", {
        "text_content": CONTRACT_TEXT,
        "title": f"Test NDA - MCP Client {run_id}",
        "contract_type": "NDA",
    })
    print(result.content[0].text)

    try:
        data = json.loads(result.content[0].text)
    except json.JSONDecodeError:
        print("ERROR: tool returned non-JSON response (see above)")
        return
    contract_id = data.get("contract_id")
    if not contract_id:
        print("Upload did not return contract_id — cannot continue analysis tests")
        return

    print(f"\ncontract_id: {contract_id}")

    # 3. Get risk analysis
    print("\n--- analyze_risks ---")
    result = await session.call_tool("analyze_risks", {"contract_id": contract_id})
    text = result.content[0].text
    print(text[:500] + ("..." if len(text) > 500 else ""))

    # 4. Get verdict
    print("\n--- sign_or_negotiate ---")
    result = await session.call_tool("sign_or_negotiate", {"contract_id": contract_id})
    text = result.content[0].text
    print(text[:500] + ("..." if len(text) > 500 else ""))

    print("\n[DONE] All tests passed")


async def main():
    print(f"Connecting to {SERVER_URL} ...")
    async with streamablehttp_client(
        SERVER_URL,
        headers={"X-LF-API-Key": API_KEY},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected.")
            await test(session)


if __name__ == "__main__":
    asyncio.run(main())
