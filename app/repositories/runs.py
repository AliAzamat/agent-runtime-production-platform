from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from app.db.postgres import cursor


class RunRepo:
    def submit(self, tenant_id: str, idempotency_key: str, task_type: str,
               input_data: dict[str, Any]) -> tuple[str, bool]:
        """Insert a queued run. If (tenant, idempotency_key) already exists, return
        the existing run id and created=False — a retried submit is not a new run."""
        run_id = str(uuid.uuid4())
        with cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (id, tenant_id, idempotency_key, task_type, input)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                RETURNING id
                """,
                (run_id, tenant_id, idempotency_key, task_type, json.dumps(input_data)),
            )
            row = cur.fetchone()
            if row is not None:
                cur.execute("INSERT INTO run_events (run_id, kind) VALUES (%s, 'submitted')", (run_id,))
                return run_id, True
            cur.execute(
                "SELECT id FROM runs WHERE tenant_id=%s AND idempotency_key=%s",
                (tenant_id, idempotency_key),
            )
            return cur.fetchone()["id"], False

    def get(self, run_id: str) -> Optional[dict[str, Any]]:
        with cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE id=%s", (run_id,))
            return cur.fetchone()

    def log(self, run_id: str, kind: str, detail: Optional[dict] = None) -> None:
        with cursor() as cur:
            cur.execute(
                "INSERT INTO run_events (run_id, kind, detail) VALUES (%s, %s, %s::jsonb)",
                (run_id, kind, json.dumps(detail or {})),
            )
