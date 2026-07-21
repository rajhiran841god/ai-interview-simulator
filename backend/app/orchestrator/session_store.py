"""
Interview session store — tracks session metadata (status, resume/JD
summaries) separately from the engine's own per-interview state
(which already lives correctly inside Conversation Memory, Evidence
Graph, etc. via engine_singletons.py).

In-memory, single-process — same documented limitation as every other
storage component in this project. Swap for Postgres before the pilot.
"""

from typing import Optional

from app.orchestrator.schema import InterviewSession

_sessions: dict[str, InterviewSession] = {}


def create_session(user_id: str) -> InterviewSession:
    session = InterviewSession(user_id=user_id)
    _sessions[session.interview_id] = session
    return session


def get_session(interview_id: str) -> Optional[InterviewSession]:
    return _sessions.get(interview_id)


def update_session(interview_id: str, **fields) -> Optional[InterviewSession]:
    session = _sessions.get(interview_id)
    if session is None:
        return None
    updated = session.model_copy(update=fields)
    _sessions[interview_id] = updated
    return updated
