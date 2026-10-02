"""Cooperative cancellation. The worker never gets killed from outside mid-step;
instead it POLLS the durable cancel flag between steps and stops there. Checking
only at step boundaries means a cancel can never interrupt a step's atomic
result-and-cost write — the run stops clean, at a state we can reason about."""
from __future__ import annotations

from app.db.postgres import cursor


class Cancelled(Exception):
    """Raised at a safe checkpoint when the tenant has requested cancellation."""


def check_cancelled(run_id: str) -> None:
    """Read the durable cancel flag. Called between steps only — never inside one."""
    with cursor() as cur:
        cur.execute("SELECT cancel_requested FROM runs WHERE id=%s", (run_id,))
        row = cur.fetchone()
    if row and row["cancel_requested"]:
        raise Cancelled()


def mark_cancelled(run_id: str) -> None:
    with cursor() as cur:
        cur.execute(
            "UPDATE runs SET status='cancelled', finished_at=now() WHERE id=%s AND status='running'",
            (run_id,),
        )
