from __future__ import annotations

import asyncio
import json

from app.db.postgres import cursor
from app.worker.retry import TransientError, TerminalError, backoff_seconds
from app.agent.steps import STEP_HANDLERS, plan_steps

MAX_STEP_ATTEMPTS = 4


def _load_or_plan_steps(run: dict) -> list[dict]:
    """Return this run's steps, creating the plan once. Idempotent: a resumed run
    reads back the steps it already has instead of re-planning."""
    with cursor() as cur:
        cur.execute("SELECT * FROM run_steps WHERE run_id=%s ORDER BY seq", (run["id"],))
        rows = cur.fetchall()
        if rows:
            return list(rows)
        steps = plan_steps(run["task_type"], run["input"])
        for s in steps:
            cur.execute(
                """
                INSERT INTO run_steps (id, run_id, seq, name, step_key)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id, seq) DO NOTHING
                """,
                (s["id"], run["id"], s["seq"], s["name"], s["step_key"]),
            )
        cur.execute("SELECT * FROM run_steps WHERE run_id=%s ORDER BY seq", (run["id"],))
        return list(cur.fetchall())


def _finish_step(run_id: str, step: dict, output: dict, cost: float) -> None:
    """Persist a step's result and add its cost to the run — atomically, so a crash
    can't record the output without the cost or vice versa."""
    with cursor() as cur:
        cur.execute(
            "UPDATE run_steps SET status='done', output=%s::jsonb, cost_usd=%s WHERE id=%s",
            (json.dumps(output), cost, step["id"]),
        )
        cur.execute("UPDATE runs SET cost_usd = cost_usd + %s WHERE id=%s", (cost, run_id))


async def _run_step(run: dict, step: dict) -> None:
    """Execute one step with retries. A step already 'done' is skipped — that skip
    is what makes a resumed run resume instead of repeat."""
    if step["status"] == "done":
        return
    handler = STEP_HANDLERS[step["name"]]
    for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
        try:
            output, cost = await handler(run["input"], step)
            _finish_step(run["id"], step, output, cost)
            return
        except TransientError:
            if attempt == MAX_STEP_ATTEMPTS:
                raise
            await asyncio.sleep(backoff_seconds(attempt))
        except TerminalError:
            raise  # never retry a terminal error


async def execute_run(run: dict, worker_id: str, renew_lease) -> None:
    steps = _load_or_plan_steps(run)
    for step in steps:
        renew_lease(run["id"], worker_id)     # long step -> keep our claim alive
        await _run_step(run, step)
    with cursor() as cur:
        cur.execute(
            "UPDATE runs SET status='succeeded', finished_at=now() WHERE id=%s",
            (run["id"],),
        )
