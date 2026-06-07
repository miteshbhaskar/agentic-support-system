"""
src/tools/incident_tool.py
──────────────────────────
Tool for checking active/recent incidents filtered by region.
"""

import httpx
from src.tools.base import BaseTool, ToolError
from src.config import settings

API_BASE = f"http://localhost:{settings.api_port}"


class IncidentTool(BaseTool):
    """
    Fetches active or recent incidents, optionally filtered by region.
    Input:  region (str, optional), active_only (bool, default True)
    Output: list of incident dicts
    """

    async def _execute(self, region: str | None = None, active_only: bool = True) -> list[dict]:
        params = {"active_only": str(active_only).lower()}
        if region:
            params["region"] = region

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{API_BASE}/incidents/", params=params)

        if response.status_code != 200:
            raise ToolError(self.name, f"API returned {response.status_code}", retryable=True)

        data = response.json()

        if not isinstance(data, list):
            raise ToolError(self.name, "Unexpected response format", retryable=False)

        return data


if __name__ == "__main__":
    import asyncio

    async def test():
        tool = IncidentTool()

        print("Test 1 - active incidents in ap-south-1:")
        result = await tool.run(region="ap-south-1", active_only=True)
        print(f"  success={result.success} latency={result.latency_ms}ms")
        if result.success:
            for inc in result.data:
                print(f"  {inc['incident_id']} | {inc['status']} | {inc['severity']} | {inc['title']}")

        print("\nTest 2 - all incidents globally:")
        result = await tool.run(active_only=False)
        print(f"  success={result.success} | total={len(result.data)}")
        for inc in result.data:
            print(f"  {inc['incident_id']} | {inc['status']} | {inc['region']}")

    asyncio.run(test())