"""
Lightweight external timing utility — pilot-preparation diagnostic
tooling, same category as turn_timer.py, NOT an engine change.

Measures from OUTSIDE engine calls, deliberately not touching any of
the 10 modules' frozen contracts/schemas. Closes the latency-
measurement gap flagged in LIVE_VALIDATION_LOG.md for Evaluation
Engine, Question Generator, and Feedback Generator (which don't
expose processing_time_ms internally, unlike Resume/JD Understanding).
"""
import time
from contextlib import contextmanager


@contextmanager
def measure_latency(label: str):
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        print(f"[LATENCY] {label}: {elapsed_ms:.0f}ms")
