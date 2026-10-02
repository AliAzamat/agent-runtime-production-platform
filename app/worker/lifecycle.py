"""Graceful drain. A deploy sends SIGTERM; a naive worker would die instantly and
abandon every in-flight run mid-step. Instead we flip a shutdown flag so the loop
STOPS CLAIMING, then wait for the runs already executing to finish before exiting.
Combined with idempotent steps, even a run we can't finish in time is safe — it's
reclaimed and resumes where it stopped."""
from __future__ import annotations

import asyncio
import signal

from app.worker.pool import worker_loop, _shutdown

DRAIN_TIMEOUT_SECONDS = 60


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def _request_shutdown() -> None:
        # Setting the event makes worker_loop stop claiming and start draining.
        _shutdown.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_shutdown)


async def main() -> None:
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop)
    try:
        # worker_loop returns once _shutdown is set AND in-flight tasks have drained.
        await asyncio.wait_for(worker_loop(), timeout=None)
    finally:
        # Any run still running past the drain window keeps its lease; when the
        # lease expires another worker reclaims it and resumes from the last done step.
        pass


if __name__ == "__main__":
    asyncio.run(main())
