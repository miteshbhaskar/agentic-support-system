"""src/api/routes/diagnostics.py — Simulated diagnostic checks."""

import random
from fastapi import APIRouter, HTTPException
from src.api.db import fetchone, parse_json_fields
from src.models.schemas import DiagnosticsResponse, DiagnosticResult

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _simulate_check(check_name: str, features: dict, limits: dict) -> DiagnosticResult:
    """Simulate a diagnostic check result based on customer features."""
    latency = random.randint(10, 120)

    if check_name == "export_health":
        enabled = features.get("csv_export", False)
        return DiagnosticResult(
            check="export_health",
            status="ok" if enabled else "disabled",
            latency_ms=latency,
            detail=f"CSV export {'enabled' if enabled else 'disabled for this account'}. "
                   f"Row limit: {limits.get('csv_export_rows', 'N/A')}",
        )

    if check_name == "auth_config":
        sso = features.get("saml_sso", False)
        return DiagnosticResult(
            check="auth_config",
            status="ok",
            latency_ms=latency,
            detail=f"SAML SSO: {'enabled' if sso else 'disabled'}. Standard auth: active.",
        )

    if check_name == "webhooks":
        enabled = features.get("webhooks", False)
        return DiagnosticResult(
            check="webhooks",
            status="ok" if enabled else "disabled",
            latency_ms=latency,
            detail=f"Webhook delivery: {'active' if enabled else 'not available on this plan'}",
        )

    if check_name == "dashboard_latency":
        status = "ok" if latency < 100 else "degraded"
        return DiagnosticResult(
            check="dashboard_latency",
            status=status,
            latency_ms=latency,
            detail=f"Dashboard response time: {latency}ms",
        )

    return DiagnosticResult(
        check=check_name,
        status="unknown",
        latency_ms=latency,
        detail="Unknown check type",
    )


@router.post("/{customer_id}", response_model=DiagnosticsResponse)
async def run_diagnostics(customer_id: str):
    row = await fetchone(
        "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")

    customer = parse_json_fields(row, ["features", "limits"])
    features = customer.get("features", {})
    limits = customer.get("limits", {})

    checks = [
        _simulate_check("export_health", features, limits),
        _simulate_check("auth_config", features, limits),
        _simulate_check("webhooks", features, limits),
        _simulate_check("dashboard_latency", features, limits),
    ]

    return DiagnosticsResponse(customer_id=customer_id, checks=checks)
