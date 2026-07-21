"""
Concurrency guard — the "highest-risk item" flagged in
Session_Lifecycle_And_Persistence.md: two browser tabs (or a
double-click) hitting next-question/answer for the same interview_id
concurrently, silently corrupting interview state (two questions
generated, two turns recorded, competency confidence updated twice).

Deliberately NOT distributed locking — this is a single-process,
in-memory guard, matching every other in-memory component in this
project. Sufficient for a small, supervised pilot; would need a real
lock (e.g. Postgres advisory lock or Redis) if this system runs across
multiple processes/workers later.
"""

from contextlib import contextmanager

from fastapi import HTTPException

_processing: set[str] = set()


@contextmanager
def guard(interview_id: str):
    """Raises HTTPException(409) if this interview_id is already
    being processed by a concurrent request. Always releases the lock
    on exit, including on error, so a failed request can't permanently
    wedge an interview."""
    if interview_id in _processing:
        raise HTTPException(
            status_code=409,
            detail="This interview is already processing a request — please wait a moment and try again. (If you have this interview open in more than one tab, use only one.)",
        )
    _processing.add(interview_id)
    try:
        yield
    finally:
        _processing.discard(interview_id)
