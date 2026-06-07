"""
src/tools/customer_tool.py
──────────────────────────
Tool for fetching customer account details from the REST API.
"""

import httpx
from src.tools.base import BaseTool, ToolError
from src.config import settings

API_BASE = f"http://localhost:{settings.api_port}"


class CustomerTool(BaseTool):
    """
    Fetches customer account: plan, version, region, features, limits.
    Input:  customer_id (str)
    Output: customer dict
    """

    async def _execute(self, customer_id: str) -> dict:
        if not customer_id or not customer_id.strip():
            raise ToolError(self.name, "customer_id is required", retryable=False)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{API_BASE}/customers/{customer_id}")

        if response.status_code == 404:
            raise ToolError(self.name, f"Customer '{customer_id}' not found", retryable=False)

        if response.status_code != 200:
            raise ToolError(
                self.name,
                f"API returned {response.status_code}",
                retryable=True,
            )

        data = response.json()

        # Validate required fields present
        required = ["customer_id", "plan", "product_version", "region", "features", "limits"]
        missing = [f for f in required if f not in data]
        if missing:
            raise ToolError(self.name, f"Missing fields in response: {missing}", retryable=False)

        return data


if __name__ == "__main__":
    import asyncio

    async def test():
        tool = CustomerTool()

        print("Test 1 - valid customer:")
        result = await tool.run(customer_id="cust_1001")
        print(f"  success={result.success} latency={result.latency_ms}ms")
        if result.success:
            d = result.data
            print(f"  {d['customer_id']} | {d['plan']} | v{d['product_version']} | {d['region']}")

        print("\nTest 2 - invalid customer:")
        result = await tool.run(customer_id="cust_9999")
        print(f"  success={result.success} error={result.error}")

    asyncio.run(test())