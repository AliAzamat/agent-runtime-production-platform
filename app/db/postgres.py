"""Thin connection-pool wrapper around psycopg. Repositories use these helpers;
nothing else in the app touches raw SQL."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

DSN = os.environ.get("DATABASE_URL", "postgresql://localhost/agentrt")

_pool = ConnectionPool(DSN, min_size=2, max_size=20, kwargs={"row_factory": dict_row})


@contextmanager
def cursor() -> Iterator[Any]:
    """Borrow a connection, yield a dict-row cursor, commit on success."""
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            yield cur
        conn.commit()


def init_schema() -> None:
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "..", "models", "schema.sql")
    with open(sql_path, "r", encoding="utf-8") as fh:
        ddl = fh.read()
    with cursor() as cur:
        cur.execute(ddl)
