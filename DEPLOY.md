# Deploying the agent runtime safely

The worker handles SIGTERM as a **drain**, not a kill:

1. The orchestrator (ECS/Kubernetes) sends SIGTERM to the old worker.
2. The worker stops claiming new runs immediately; the queue holds new work.
3. In-flight runs keep executing; the worker renews their leases as it goes.
4. When they finish, the process exits 0. New workers are already claiming.
5. Any run not finished within the drain window (`terminationGracePeriodSeconds`
   must exceed `DRAIN_TIMEOUT_SECONDS`) keeps its lease. When the old worker
   exits, the lease lapses and a NEW worker reclaims and resumes it from its
   last completed step — no work is lost, because steps are idempotent.

Set `terminationGracePeriodSeconds` >= 90 (drain 60s + headroom). A shorter grace
period turns a graceful drain back into an abort.
