"""A worker process runs an asyncio loop that claims runs and executes them, but
never more than MAX_CONCURRENCY at once. The semaphore is the throttle: it bounds
how many agent runs (and thus model calls) are in flight, which is how we protect
the model API from a thundering herd and keep our own memory bounded."""
from __future__ import annotations

import asyncio
import os

from app.worker.claim import claim_next, renew_lease
from app.worker.executor import execute_run

WORKER_ID = os.environ.get("WORKER_ID", "worker-1")
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "8"))
POLL_INTERVAL = 0.5

_sem = asyncio.Semaphore(MAX_CONCURRENCY)
_shutdown = asyncio.Event()


async def _run_one(run: dict) -> None:
    async with _sem:                       # occupy one concurrency slot
        await execute_run(run, WORKER_ID, renew_lease)


async def worker_loop() -> None:
    """Poll for work only while we have a free slot. When the semaphore is full we
    stop claiming — that unclaimed work is the backpressure that keeps the queue,
    not our process, holding the overflow."""
    tasks: set[asyncio.Task] = set()
    while not _shutdown.is_set():
        if _sem.locked():                  # all slots busy -> don't claim more
            await asyncio.sleep(POLL_INTERVAL)
            continue
        run = await asyncio.to_thread(claim_next, WORKER_ID)
        if run is None:                    # nothing claimable right now
            await asyncio.sleep(POLL_INTERVAL)
            continue
        t = asyncio.create_task(_run_one(run))
        tasks.add(t)
        t.add_done_callback(tasks.discard)
    # drain: wait for in-flight runs to finish (see the shutdown step)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
