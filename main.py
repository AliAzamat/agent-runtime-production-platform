"""API entrypoint: builds the FastAPI app and mounts the routers.
Run the API with `uvicorn main:app` and the worker separately with
`python -m app.worker.lifecycle`. Both read DATABASE_URL.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import cancel, runs, slo
from app.db.postgres import _pool, cursor


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Close pooled connections cleanly when uvicorn shuts down.
    _pool.close()


app = FastAPI(title="Agent Runtime", lifespan=lifespan)

for module in (runs, cancel, slo):
    app.include_router(module.router)


@app.get("/healthz", tags=["health"])
def healthz():
    """Liveness plus a database round-trip, for load balancers and deploy checks."""
    with cursor() as cur:
        cur.execute("SELECT 1")
    return {"status": "ok"}
