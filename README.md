# Agent Runtime — A Production Platform for Long-Running AI Agents

An advanced production-engineering capstone for a team operating agentic AI at scale. You build the runtime that stands between "the agent works in a notebook" and "the agent serves thousands of tenants reliably" — a durable run/step state machine in Postgres, a submit API with per-tenant admission control and cost budgets, a worker pool that claims runs with row-level locking and executes multi-step agent work with a bounded concurrency semaphore and backpressure, idempotent step execution so a retried non-deterministic LLM step never double-charges or double-acts, an SLO layer that measures run latency and success against error budgets, and a graceful-drain shutdown so a deploy never abandons an in-flight legal task. It mirrors the production-engineering reality of running agents that take minutes, cost real money per run, and must not silently fail on someone's contract review.

## Stack
- Python
- FastAPI
- PostgreSQL
- asyncio
- Worker Pools
- SLOs
