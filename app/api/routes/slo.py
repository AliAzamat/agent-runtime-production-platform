from __future__ import annotations

from fastapi import APIRouter

from app.observability.slo import compute

router = APIRouter(prefix="/slo", tags=["slo"])


@router.get("")
def slo(window_hours: int = 1):
    """The SLO report the dashboard reads and the alerting rule scrapes. A fast
    burn on either budget is the page-worthy symptom — not any single failed run."""
    r = compute(window_hours)
    return {
        "window_runs": r.window_runs,
        "success_rate": r.success_rate,
        "latency_slo_rate": r.latency_slo_rate,
        "success_budget_burn": r.success_budget_burn,
        "latency_budget_burn": r.latency_budget_burn,
        "page": r.success_budget_burn > 0.5 or r.latency_budget_burn > 0.5,
    }
