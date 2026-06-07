"""
src/tools/ticket_tool.py
────────────────────────
Tool for creating escalation tickets with idempotency support.
"""

import httpx
from src.tools.base import BaseTool, ToolError
from src.config import settings

API_BASE = f"http://localhost:{settings.api_port}"

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_CATEGORIES = {"billing", "technical", "security", "access", "general"}


class TicketTool(BaseTool):
    """
    Creates a support escalation ticket.
    Idempotency key prevents duplicate tickets on retry.
    Input:  customer_id, category, priority, summary, evidence, idempotency_key
    Output: created ticket dict
    """

    async def _execute(
        self,
        customer_id: str,
        summary: str,
        category: str = "general",
        priority: str = "medium",
        evidence: list[str] = None,
        assigned_team: str = "support",
        idempotency_key: str | None = None,
    ) -> dict:
        if not customer_id:
            raise ToolError(self.name, "customer_id is required", retryable=False)
        if not summary:
            raise ToolError(self.name, "summary is required", retryable=False)
        if priority not in VALID_PRIORITIES:
            raise ToolError(self.name, f"Invalid priority '{priority}'", retryable=False)

        payload = {
            "customer_id": customer_id,
            "category": category,
            "priority": priority,
            "summary": summary,
            "evidence": evidence or [],
            "assigned_team": assigned_team,
            "idempotency_key": idempotency_key,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{API_BASE}/tickets/", json=payload)

        if response.status_code == 404:
            raise ToolError(self.name, f"Customer '{customer_id}' not found", retryable=False)

        if response.status_code not in (200, 201):
            raise ToolError(self.name, f"API returned {response.status_code}", retryable=True)

        data = response.json()

        if "ticket_id" not in data:
            raise ToolError(self.name, "Missing ticket_id in response", retryable=False)

        return data


if __name__ == "__main__":
    import asyncio

    async def test():
        tool = TicketTool()

        print("Test 1 - create ticket:")
        result = await tool.run(
            customer_id="cust_1001",
            summary="Customer requesting refund for last invoice",
            category="billing",
            priority="high",
            evidence=["Customer on business plan", "Billing policy requires manual approval"],
            idempotency_key="cust_1001_refund_test_001",
        )
        print(f"  success={result.success} latency={result.latency_ms}ms")
        if result.success:
            print(f"  ticket_id={result.data['ticket_id']} status={result.data['status']}")

        print("\nTest 2 - same idempotency key (should return same ticket):")
        result2 = await tool.run(
            customer_id="cust_1001",
            summary="Customer requesting refund for last invoice",
            category="billing",
            priority="high",
            evidence=[],
            idempotency_key="cust_1001_refund_test_001",
        )
        print(f"  success={result2.success}")
        if result2.success:
            print(f"  ticket_id={result2.data['ticket_id']} (same as above = idempotency works)")

    asyncio.run(test())