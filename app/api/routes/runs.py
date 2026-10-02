from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.repositories.runs import RunRepo
from app.services.admission import check

router = APIRouter(prefix="/runs", tags=["runs"])
repo = RunRepo()


class SubmitRun(BaseModel):
    task_type: str
    input: dict


@router.post("")
def submit_run(body: SubmitRun,
               x_tenant_id: str = Header(...),
               idempotency_key: str = Header(...)):
    """Admit-or-reject, then submit. A rejection is a 429 with a reason and a
    Retry-After so the caller backs off instead of hammering."""
    admission = check(x_tenant_id)
    if not admission.admitted:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": "30"},
            content={"error": {"code": "not_admitted", "message": admission.reason}},
        )
    run_id, created = repo.submit(x_tenant_id, idempotency_key, body.task_type, body.input)
    return JSONResponse(status_code=201 if created else 200, content={"run_id": run_id, "created": created})
