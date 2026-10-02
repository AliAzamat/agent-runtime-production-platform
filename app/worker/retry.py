"""Retry policy. Transient failures (a timeout, a 429, a 503 from the model) are
worth retrying with capped exponential backoff. Terminal failures (a 400, a
validation error, a budget-exhausted signal) will never succeed on retry, so we
fail them fast instead of burning attempts and money."""
from __future__ import annotations


class TransientError(Exception):
    """Worth retrying: timeouts, rate limits, upstream 5xx."""


class TerminalError(Exception):
    """Not worth retrying: bad input, policy violation, exhausted budget."""


def backoff_seconds(attempt: int) -> float:
    """Exponential backoff, capped, so retries spread out instead of hammering:
    attempt 1 -> 1s, 2 -> 2s, 3 -> 4s, ... capped at 30s."""
    return float(min(30, 2 ** (attempt - 1)))
