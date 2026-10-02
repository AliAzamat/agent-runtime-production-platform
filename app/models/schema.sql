-- A tenant is a customer of the platform. Its budget and concurrency cap are the
-- levers that stop one tenant from starving the fleet or blowing the model bill.
CREATE TABLE IF NOT EXISTS tenants (
    id                   TEXT PRIMARY KEY,           -- e.g. "acme-legal"
    daily_cost_budget    NUMERIC(10,2) NOT NULL DEFAULT 50.00,   -- USD/day
    max_concurrent_runs  INTEGER NOT NULL DEFAULT 5,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- An agent run: one long-running task for a tenant (e.g. "review this contract").
-- status is a state machine: queued -> running -> (succeeded | failed | cancelled).
-- attempt/lease let many workers coordinate without stepping on each other.
CREATE TABLE IF NOT EXISTS runs (
    id            UUID PRIMARY KEY,
    tenant_id     TEXT        NOT NULL REFERENCES tenants (id),
    idempotency_key TEXT      NOT NULL,              -- client-supplied; dedupes submits
    task_type     TEXT        NOT NULL,              -- 'contract_review' | 'research' | ...
    input         JSONB       NOT NULL,
    status        TEXT        NOT NULL DEFAULT 'queued',
    attempt       INTEGER     NOT NULL DEFAULT 0,
    lease_until   TIMESTAMPTZ,                       -- worker's lock expiry while running
    worker_id     TEXT,
    cost_usd      NUMERIC(10,4) NOT NULL DEFAULT 0,  -- accumulated model cost
    cancel_requested BOOLEAN     NOT NULL DEFAULT false,  -- cooperative-cancel intent flag
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    -- The same tenant + idempotency key is the SAME run, never a duplicate submit.
    UNIQUE (tenant_id, idempotency_key)
);

-- One step within a run's plan. Steps execute in order; each is individually
-- durable and idempotent so a resumed run re-does only what didn't finish.
CREATE TABLE IF NOT EXISTS run_steps (
    id            UUID PRIMARY KEY,
    run_id        UUID        NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    seq           INTEGER     NOT NULL,              -- order within the run
    name          TEXT        NOT NULL,              -- 'retrieve' | 'draft' | 'cite-check' | ...
    step_key      TEXT        NOT NULL,              -- stable idempotency key for this step
    status        TEXT        NOT NULL DEFAULT 'pending',  -- pending|done|failed
    output        JSONB,                             -- the step's result, once done
    cost_usd      NUMERIC(10,4) NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, seq),
    -- Re-executing the same step (a retry) upserts on this key, never duplicates.
    UNIQUE (run_id, step_key)
);

-- An append-only event log for observability and SLO measurement.
CREATE TABLE IF NOT EXISTS run_events (
    id            BIGSERIAL PRIMARY KEY,
    run_id        UUID        NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
    kind          TEXT        NOT NULL,              -- 'submitted'|'claimed'|'step_done'|'succeeded'|'failed'|...
    detail        JSONB,
    at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runs_claimable ON runs (status, created_at);
