"""SLOs computed from the durable run history. Two SLIs: the fraction of runs that
succeeded, and the fraction that finished within a latency target. Each has an
objective; the gap between objective and reality is the error budget, and how fast
that budget is burning is what you actually alert on."""
from __future__ import annotations

from dataclasses import dataclass

from app.db.postgres import cursor

SUCCESS_OBJECTIVE = 0.99      # 99% of runs should succeed
LATENCY_OBJECTIVE = 0.95      # 95% of runs should finish within...
LATENCY_TARGET_SECONDS = 180  # ...3 minutes


@dataclass
class SLOReport:
    window_runs: int
    success_rate: float
    latency_slo_rate: float
    success_budget_burn: float   # fraction of the success error budget consumed
    latency_budget_burn: float


def _budget_burn(observed: float, objective: float) -> float:
    """How much of the error budget is consumed. Budget = 1 - objective. If the
    objective is 0.99, the budget is 0.01; observing 0.985 burns half of it."""
    budget = 1.0 - objective
    if budget <= 0:
        return 0.0
    consumed = max(0.0, objective - observed)
    return round(min(1.0, consumed / budget), 4)


def compute(window_hours: int = 1) -> SLOReport:
    with cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*)                                                       AS n,
              AVG((status='succeeded')::int)::float                          AS success_rate,
              AVG((EXTRACT(EPOCH FROM (finished_at - started_at)) <= %s)::int)
                FILTER (WHERE finished_at IS NOT NULL)::float                 AS latency_rate
            FROM runs
            WHERE created_at >= now() - (%s || ' hours')::interval
              AND status IN ('succeeded','failed')
            """,
            (LATENCY_TARGET_SECONDS, window_hours),
        )
        row = cur.fetchone()

    n = row["n"] or 0
    success = row["success_rate"] or 0.0
    latency = row["latency_rate"] or 0.0
    return SLOReport(
        window_runs=n,
        success_rate=round(success, 4),
        latency_slo_rate=round(latency, 4),
        success_budget_burn=_budget_burn(success, SUCCESS_OBJECTIVE),
        latency_budget_burn=_budget_burn(latency, LATENCY_OBJECTIVE),
    )
