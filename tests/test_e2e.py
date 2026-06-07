"""
tests/test_e2e.py
─────────────────
End-to-end evaluation against sample-requests/example-queries.json.
Runs all 25 queries against the live API and validates responses.

Usage:
    python -m tests.test_e2e

Requirements:
    - API server running on localhost:8001
    - .env configured with valid OPENAI_API_KEY
"""

import json
import time
import httpx
from pathlib import Path
from datetime import datetime

API_URL = "http://localhost:8001/support/query"
QUERIES_FILE = Path("sample-requests/example-queries.json")
TIMEOUT = 60.0
MIN_PASS_RATE = 15  # minimum passing tests required


def load_queries() -> list[dict]:
    with open(QUERIES_FILE) as f:
        return json.load(f)


def run_query(customer_id: str, query: str) -> dict | None:
    try:
        response = httpx.post(
            API_URL,
            json={"customer_id": customer_id, "query": query},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"HTTP {response.status_code}", "detail": response.text}
    except Exception as e:
        return {"error": str(e)}


def validate(test_case: dict, response: dict) -> tuple[bool, list[str]]:
    """
    Validates response against expected fields in test case.
    Returns (passed, list_of_failures).
    """
    failures = []

    if "error" in response:
        return False, [f"Request failed: {response['error']}"]

    # Check escalation matches expectation
    expected_escalation = test_case.get("expected_escalation")
    actual_escalation = response.get("escalation_required", False)
    if expected_escalation is not None and actual_escalation != expected_escalation:
        failures.append(
            f"Escalation mismatch: expected={expected_escalation} actual={actual_escalation}"
        )

    # Check status is valid
    status = response.get("status")
    if status not in ("resolved", "escalated", "rejected", "error"):
        failures.append(f"Invalid status: {status}")

    # Check status aligns with escalation
    if expected_escalation and status not in ("escalated", "rejected"):
        failures.append(f"Expected escalated/rejected status but got: {status}")
    if not expected_escalation and status not in ("resolved",):
        failures.append(f"Expected resolved status but got: {status}")

    # Check answer is not empty
    answer = response.get("answer", "")
    if not answer or len(answer.strip()) < 10:
        failures.append("Answer is empty or too short")

    # Check confidence is present and valid
    confidence = response.get("confidence")
    if confidence is None or not (0.0 <= confidence <= 1.0):
        failures.append(f"Invalid confidence score: {confidence}")

    # Check tools_used is present
    tools_used = response.get("tools_used", [])
    if not isinstance(tools_used, list):
        failures.append("tools_used must be a list")

    # Check execution_trace is present
    trace = response.get("execution_trace", [])
    if not isinstance(trace, list) or len(trace) == 0:
        failures.append("execution_trace is empty")

    return len(failures) == 0, failures


def print_result(test_case: dict, response: dict, passed: bool, failures: list, latency: float):
    status_icon = "✓" if passed else "✗"
    difficulty = test_case.get("difficulty", "?").upper()
    print(f"\n  {status_icon} [{difficulty}] {test_case['id']}")
    print(f"    Query     : {test_case['query'][:80]}...")
    print(f"    Customer  : {test_case['customer_id']}")

    if "error" not in response:
        print(f"    Status    : {response.get('status')} | "
              f"Escalated: {response.get('escalation_required')} | "
              f"Confidence: {response.get('confidence', 0):.2f}")
        print(f"    Tools     : {[t['tool'] for t in response.get('tools_used', [])]}")
        print(f"    Latency   : {latency:.1f}s")

    if failures:
        for f in failures:
            print(f"    ✗ FAIL    : {f}")


def main():
    print("=" * 65)
    print(" FlowDesk E2E Evaluation")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    queries = load_queries()
    print(f"\nLoaded {len(queries)} test cases from {QUERIES_FILE}\n")

    results = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "by_difficulty": {"easy": [], "medium": [], "hard": []},
        "details": [],
    }

    for i, test_case in enumerate(queries, 1):
        print(f"  Running {i}/{len(queries)}: {test_case['id']}...", end="", flush=True)

        start = time.time()
        response = run_query(test_case["customer_id"], test_case["query"])
        print("Response json:------------------------------",response)
        latency = time.time() - start

        passed, failures = validate(test_case, response)

        if "error" in response and "HTTP" not in response.get("error", ""):
            results["errors"] += 1
        elif passed:
            results["passed"] += 1
        else:
            results["failed"] += 1

        difficulty = test_case.get("difficulty", "medium")
        results["by_difficulty"][difficulty].append(passed)

        results["details"].append({
            "id": test_case["id"],
            "passed": passed,
            "failures": failures,
            "latency": round(latency, 2),
            "response_status": response.get("status"),
            "escalated": response.get("escalation_required"),
            "confidence": response.get("confidence"),
            "answer":response.get("answer"),
            "execution_trace":response.get("execution_trace"),
            "tools_used":response.get("tools_used"),
        })

        print(f" {'PASS' if passed else 'FAIL'}")
        print_result(test_case, response, passed, failures, latency)
        print(f"    Answer    : {response.get('answer', '')[:150]}...")

    # ── Summary ───────────────────────────────────────────────────
    total = len(queries)
    passed = results["passed"]

    print("\n" + "=" * 65)
    print(" RESULTS SUMMARY")
    print("=" * 65)
    print(f"  Total    : {total}")
    print(f"  Passed   : {passed} ({passed/total*100:.1f}%)")
    print(f"  Failed   : {results['failed']}")
    print(f"  Errors   : {results['errors']}")

    print("\n  By Difficulty:")
    for diff, outcomes in results["by_difficulty"].items():
        if outcomes:
            p = sum(outcomes)
            print(f"    {diff.upper():<8}: {p}/{len(outcomes)} passed")

    print(f"\n  Minimum required : {MIN_PASS_RATE}")
    print(f"  Result           : {'✓ PASSED' if passed >= MIN_PASS_RATE else '✗ FAILED'}")

    # ── Save report ───────────────────────────────────────────────
    report_path = Path("test_report.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "failed": results["failed"],
            "errors": results["errors"],
            "pass_rate": round(passed / total * 100, 1),
            "meets_requirement": passed >= MIN_PASS_RATE,
            "details": results["details"]
        }, f, indent=2)

    print(f"\n  Report saved to: {report_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()