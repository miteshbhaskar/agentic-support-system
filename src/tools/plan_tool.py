"""
src/tools/plan_tool.py
──────────────────────
Tool for fetching plan details: features, limits, restrictions.
"""

import httpx
from src.tools.base import BaseTool, ToolError
from src.config import settings

API_BASE = f"http://localhost:{settings.api_port}"

VALID_PLANS = {"starter", "pro", "business", "enterprise"}


class PlanTool(BaseTool):
    """
    Fetches plan catalog details: features, limits, restrictions.
    Input:  plan_name (str)
    Output: plan dict
    """

    async def _execute(self, plan_name: str) -> dict:
        if not plan_name or plan_name.lower() not in VALID_PLANS:
            raise ToolError(
                self.name,
                f"Invalid plan '{plan_name}'. Must be one of {VALID_PLANS}",
                retryable=False,
            )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{API_BASE}/plans/{plan_name.lower()}")

        if response.status_code == 404:
            raise ToolError(self.name, f"Plan '{plan_name}' not found", retryable=False)

        if response.status_code != 200:
            raise ToolError(self.name, f"API returned {response.status_code}", retryable=True)

        data = response.json()

        required = ["plan_name", "features", "limits", "restrictions"]
        missing = [f for f in required if f not in data]
        if missing:
            raise ToolError(self.name, f"Missing fields: {missing}", retryable=False)

        return data


if __name__ == "__main__":
    import asyncio

    async def test():
        tool = PlanTool()

        print("Test 1 - valid plan:")
        result = await tool.run(plan_name="business")
        print(f"  success={result.success} latency={result.latency_ms}ms")
        if result.success:
            d = result.data
            print(f"  plan={d['plan_name']} | csv_rows={d['limits'].get('csv_export_rows')}")
            print(f"  restrictions={d['restrictions']}")

        print("\nTest 2 - invalid plan:")
        result = await tool.run(plan_name="gold")
        print(f"  success={result.success} error={result.error}")

    asyncio.run(test())