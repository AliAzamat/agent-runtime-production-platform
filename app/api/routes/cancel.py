from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from app.db.postgres import cursor

router = APIRouter(prefix="/runs", tags=["cancel"])


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, x_tenant_id: str = Header(...)):
    """Request cancellation. We don't stop anything ourselves — we record the
    INTENT, and the worker honors it at its next safe checkpoint. A run that has
    already finished can't be cancelled; a queued run is cancelled outright."""
    with cursor() as cur:
        # Only the owning tenant can cancel, and only a run that isn't finished.
        cur.execute(
            """
            UPDATE runs
            SET status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                cancel_requested = true
            WHERE id = %s AND tenant_id = %s AND status IN ('queued','running')
            RETURNING status
            """,
            (run_id, x_tenant_id),
        )
        row = cur.fetchone()
    if row is None:
        return JSONResponse(status_code=409, content={"error": {
            "code": "not_cancellable", "message": "run is finished or not yours"}})
    return {"run_id": run_id, "status": row["status"]}
