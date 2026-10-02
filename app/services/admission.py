"""Admission control. Before a run is accepted, we check the tenant's live
concurrency and today's spend against their caps. Rejecting at the door is far
cheaper than accepting work you'll have to kill mid-flight, and it's the
mechanism that keeps one noisy tenant from consuming the whole fleet."""
from __future__ import annotations

from dataclasses import dataclass

from app.db.postgres import cursor


@dataclass
class AdmissionResult:
    admitted: bool
    reason: str = ""


def check(tenant_id: str) -> AdmissionResult:
    with cursor() as cur:
        cur.execute(
            "SELECT daily_cost_budget, max_concurrent_runs FROM tenants WHERE id=%s",
            (tenant_id,),
        )
        tenant = cur.fetchone()
        if tenant is None:
            return AdmissionResult(False, "unknown tenant")

        # How many of this tenant's runs are in flight right now?
        cur.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE tenant_id=%s AND status IN ('queued','running')",
            (tenant_id,),
        )
        in_flight = cur.fetchone()["n"]
        if in_flight >= tenant["max_concurrent_runs"]:
            return AdmissionResult(False, "concurrency cap reached")

        # How much has this tenant spent since midnight UTC?
        cur.execute(
            """
            SELECT COALESCE(SUM(cost_usd), 0) AS spent
            FROM runs
            WHERE tenant_id=%s AND created_at >= date_trunc('day', now())
            """,
            (tenant_id,),
        )
        spent = cur.fetchone()["spent"]
        if spent >= tenant["daily_cost_budget"]:
            return AdmissionResult(False, "daily cost budget exhausted")

    return AdmissionResult(True)
