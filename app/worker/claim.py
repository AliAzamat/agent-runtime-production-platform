"""Claiming a run for execution. Many workers poll the same queue, so the claim
MUST be atomic: FOR UPDATE SKIP LOCKED lets each worker grab a different row
without blocking on rows another worker already holds. A lease bounds how long a
claim is valid, so a worker that dies mid-run doesn't strand the work forever."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from app.db.postgres import cursor

LEASE_SECONDS = 120


def claim_next(worker_id: str) -> Optional[dict]:
    """Atomically claim one claimable run: queued, OR running with an expired lease
    (its previous worker died). Marks it running, bumps the attempt, sets the lease."""
    with cursor() as cur:
        cur.execute(
            """
            WITH claimable AS (
                SELECT id FROM runs
                WHERE status = 'queued'
                   OR (status = 'running' AND lease_until < now())
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE runs
            SET status = 'running',
                attempt = attempt + 1,
                worker_id = %s,
                lease_until = now() + %s,
                started_at = COALESCE(started_at, now())
            FROM claimable
            WHERE runs.id = claimable.id
            RETURNING runs.*
            """,
            (worker_id, timedelta(seconds=LEASE_SECONDS)),
        )
        return cur.fetchone()


def renew_lease(run_id: str, worker_id: str) -> bool:
    """A worker still alive on a long run renews its lease so it isn't reclaimed
    out from under it. Only the current owner can renew."""
    with cursor() as cur:
        cur.execute(
            """
            UPDATE runs SET lease_until = now() + %s
            WHERE id = %s AND worker_id = %s AND status = 'running'
            RETURNING id
            """,
            (timedelta(seconds=LEASE_SECONDS), run_id, worker_id),
        )
        return cur.fetchone() is not None
