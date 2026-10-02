"""The agent's step plan and per-step handlers. A task type decomposes into an
ordered, named list of steps, each with a STABLE step_key so a resumed run maps
back to the same durable rows. Handlers do the real agent work (retrieve, draft,
cite-check) and return (output, cost); they raise TransientError / TerminalError
so the executor's retry policy can act on them."""
from __future__ import annotations

import uuid

from app.worker.retry import TransientError, TerminalError

# Each task type is a fixed plan of step names, in order.
PLANS: dict[str, list[str]] = {
    "contract_review": ["retrieve", "draft", "cite_check"],
    "research": ["retrieve", "draft"],
}


def plan_steps(task_type: str, input_data: dict) -> list[dict]:
    """Build the durable step list for a run. step_key is stable per (task, seq)
    so re-planning the same run would produce the same keys — the idempotency anchor."""
    names = PLANS.get(task_type)
    if names is None:
        raise TerminalError(f"unknown task_type: {task_type}")
    return [
        {"id": str(uuid.uuid4()), "seq": i, "name": name, "step_key": f"{task_type}:{i}:{name}"}
        for i, name in enumerate(names)
    ]


async def _retrieve(input_data: dict, step: dict) -> tuple[dict, float]:
    # In production this calls the retrieval service / vector store.
    return {"docs": ["doc-1", "doc-2"]}, 0.002


async def _draft(input_data: dict, step: dict) -> tuple[dict, float]:
    # In production this is the expensive LLM generation call.
    return {"draft": "..."}, 0.05


async def _cite_check(input_data: dict, step: dict) -> tuple[dict, float]:
    return {"citations_ok": True}, 0.01


STEP_HANDLERS = {
    "retrieve": _retrieve,
    "draft": _draft,
    "cite_check": _cite_check,
}
