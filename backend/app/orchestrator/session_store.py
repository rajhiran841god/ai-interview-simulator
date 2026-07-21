"""
Interview session store — tracks session metadata (status, resume/JD
summaries) separately from the engine's own per-interview state
(which already lives correctly inside Conversation Memory, Evidence
Graph, etc. via engine_singletons.py).

NOW PERSISTENT (Postgres via Supabase) by default, per the real
cross-process bug found during live voice testing: the FastAPI
backend and the LiveKit voice worker are separate processes — the old
in-memory dict was invisible between them. Same STORE_BACKEND switch
as engine_singletons.py lets the offline test suite use a plain
in-memory dict instead, avoiding any real Supabase dependency for
pure unit/API tests.
"""

from typing import Optional

from app.orchestrator.schema import InterviewSession
from app.core.config import settings

_in_memory_sessions: dict[str, InterviewSession] = {}


def _use_postgres() -> bool:
    return settings.STORE_BACKEND == "postgres"


def create_session(user_id: str) -> InterviewSession:
    session = InterviewSession(user_id=user_id)
    if _use_postgres():
        from app.core.supabase_data_client import get_data_client

        get_data_client().table("interview_sessions").insert(
            {"interview_id": session.interview_id, "data": session.model_dump()}
        ).execute()
    else:
        _in_memory_sessions[session.interview_id] = session
    return session


def get_session(interview_id: str) -> Optional[InterviewSession]:
    if _use_postgres():
        from app.core.supabase_data_client import get_data_client, as_json_dict

        result = (
            get_data_client()
            .table("interview_sessions")
            .select("data")
            .eq("interview_id", interview_id)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None
        return InterviewSession(**as_json_dict(result.data, "data"))
    return _in_memory_sessions.get(interview_id)


def update_session(interview_id: str, **fields) -> Optional[InterviewSession]:
    session = get_session(interview_id)
    if session is None:
        return None
    updated = session.model_copy(update=fields)
    if _use_postgres():
        from app.core.supabase_data_client import get_data_client

        get_data_client().table("interview_sessions").update(
            {"data": updated.model_dump()}
        ).eq("interview_id", interview_id).execute()
    else:
        _in_memory_sessions[interview_id] = updated
    return updated
