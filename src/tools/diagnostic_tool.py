"""
src/tools/diagnostic_tool.py
─────────────────────────────
Tool for running simulated diagnostic checks on a customer account.
"""

import httpx
from src.tools.base import BaseTool, ToolError
from src.config import settings

API_BASE = f"http://localhost:{settings.api_port}"


class DiagnosticTool(BaseTool):
    """
    Runs simulated diagnostic checks for a customer.
    Checks: export_health, auth_config, webhooks, dashboard_latency
    Input:  customer_id (str)
    Output: dict with customer_id and list of check results
    """

    async def _execute(self, customer_id: str) -> dict:
        if not customer_id:
            raise ToolError(self.name, "customer_id is required", retryable=False)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{API_BASE}/diagnostics/{customer_id}")

        if response.status_code == 404:
            raise ToolError(self.name, f"Customer '{customer_id}' not found", retryable=False)

        if response.status_code != 200:
            raise ToolError(self.name, f"API returned {response.status_code}", retryable=True)

        data = response.json()

        if "checks" not in data:
            raise ToolError(self.name, "Missing checks in response", retryable=False)

        return data


if __name__ == "__main__":
    import asyncio

    async def test():
        tool = DiagnosticTool()

        print("Test 1 - valid customer diagnostics:")
        result = await tool.run(customer_id="cust_1001")
        print(f"  success={result.success} latency={result.latency_ms}ms")
        if result.success:
            for check in result.data["checks"]:
                print(f"  {check['check']:<20} status={check['status']:<10} latency={check['latency_ms']}ms")
                print(f"    {check['detail']}")

        print("\nTest 2 - invalid customer:")
        result = await tool.run(customer_id="cust_INVALID")
        print(f"  success={result.success} error={result.error}")

    asyncio.run(test())