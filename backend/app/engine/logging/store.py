"""
Logging storage abstraction. Small interface, same pattern as
Conversation Memory and Evidence Graph stores.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from app.engine.logging.schema import TraceRecord
from app.core.supabase_data_client import get_data_client, as_json_dict


class TraceStore(ABC):
    @abstractmethod
    def next_sequence_number(self, interview_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def append_trace(self, trace: TraceRecord) -> TraceRecord:
        raise NotImplementedError

    @abstractmethod
    def update_outcome(
        self,
        interview_id: str,
        question_id: str,
        confidence_post: float,
        evidence_ids_referenced: list[str],
    ) -> TraceRecord:
        raise NotImplementedError

    @abstractmethod
    def get_trace(self, interview_id: str, question_id: str) -> Optional[TraceRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_traces_for_interview(self, interview_id: str) -> list[TraceRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_traces_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[TraceRecord]:
        raise NotImplementedError


class InMemoryTraceStore(TraceStore):
    def __init__(self):
        self._traces: dict[str, list[TraceRecord]] = {}
        self._question_index: dict[tuple[str, str], int] = {}
        self._sequence_counters: dict[str, int] = {}

    def next_sequence_number(self, interview_id: str) -> int:
        current = self._sequence_counters.get(interview_id, 0)
        self._sequence_counters[interview_id] = current + 1
        return current + 1

    def append_trace(self, trace: TraceRecord) -> TraceRecord:
        from app.engine.logging.schema import LoggingError, ErrorCode

        key = (trace.interview_id, trace.question_id)
        if key in self._question_index:
            raise LoggingError(
                ErrorCode.DUPLICATE_QUESTION_ID,
                f"A trace for question_id '{trace.question_id}' already exists for interview '{trace.interview_id}'.",
            )
        self._traces.setdefault(trace.interview_id, [])
        self._traces[trace.interview_id].append(trace)
        self._question_index[key] = len(self._traces[trace.interview_id]) - 1
        return trace

    def update_outcome(
        self,
        interview_id: str,
        question_id: str,
        confidence_post: float,
        evidence_ids_referenced: list[str],
    ) -> TraceRecord:
        from app.engine.logging.schema import LoggingError, ErrorCode

        key = (interview_id, question_id)
        if key not in self._question_index:
            raise LoggingError(
                ErrorCode.TRACE_NOT_FOUND,
                f"No trace found for question_id '{question_id}' in interview '{interview_id}'.",
            )
        idx = self._question_index[key]
        existing = self._traces[interview_id][idx]
        if existing.confidence_post is not None:
            raise LoggingError(
                ErrorCode.OUTCOME_ALREADY_RECORDED,
                f"Outcome already recorded for question_id '{question_id}'.",
            )
        # Immutable model -> create a NEW record via model_copy, only
        # touching confidence_post and evidence_ids_referenced, same
        # pattern as Conversation Memory's update_answer().
        updated = existing.model_copy(
            update={
                "confidence_post": confidence_post,
                "evidence_ids_referenced": evidence_ids_referenced,
            }
        )
        self._traces[interview_id][idx] = updated
        return updated

    def get_trace(self, interview_id: str, question_id: str) -> Optional[TraceRecord]:
        key = (interview_id, question_id)
        if key not in self._question_index:
            return None
        idx = self._question_index[key]
        return self._traces[interview_id][idx]

    def get_traces_for_interview(self, interview_id: str) -> list[TraceRecord]:
        return list(self._traces.get(interview_id, []))

    def get_traces_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[TraceRecord]:
        return [
            t
            for t in self._traces.get(interview_id, [])
            if t.target_competency_id == competency_id
        ]


def generate_trace_id() -> str:
    return str(uuid.uuid4())


class PostgresTraceStore(TraceStore):
    """Persistent implementation — see PostgresConversationMemoryStore
    for the full rationale (Decision Log #006, cross-process bug fix)."""

    def __init__(self):
        self._client = get_data_client()

    def next_sequence_number(self, interview_id: str) -> int:
        result = (
            self._client.table("logging_traces")
            .select("sequence_number")
            .eq("interview_id", interview_id)
            .order("sequence_number", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return 1
        first_row = result.data[0]
        assert isinstance(
            first_row, dict
        ), "Expected a row object from the query result"
        return int(first_row["sequence_number"]) + 1

    def append_trace(self, trace: TraceRecord) -> TraceRecord:
        from app.engine.logging.schema import LoggingError, ErrorCode

        existing = self.get_trace(trace.interview_id, trace.question_id)
        if existing is not None:
            raise LoggingError(
                ErrorCode.DUPLICATE_QUESTION_ID,
                f"A trace already exists for question_id '{trace.question_id}'.",
            )
        self._client.table("logging_traces").insert(
            {
                "interview_id": trace.interview_id,
                "question_id": trace.question_id,
                "sequence_number": trace.sequence_number,
                "competency_id": trace.target_competency_id,
                "data": trace.model_dump(),
            }
        ).execute()
        return trace

    def update_outcome(
        self,
        interview_id: str,
        question_id: str,
        confidence_post: float,
        evidence_ids_referenced: list[str],
    ) -> TraceRecord:
        from app.engine.logging.schema import LoggingError, ErrorCode

        existing = self.get_trace(interview_id, question_id)
        if existing is None:
            raise LoggingError(
                ErrorCode.TRACE_NOT_FOUND,
                f"No trace found for question_id '{question_id}' in interview '{interview_id}'.",
            )
        if existing.confidence_post is not None:
            raise LoggingError(
                ErrorCode.OUTCOME_ALREADY_RECORDED,
                f"Outcome already recorded for question_id '{question_id}'.",
            )
        updated = existing.model_copy(
            update={
                "confidence_post": confidence_post,
                "evidence_ids_referenced": evidence_ids_referenced,
            }
        )
        self._client.table("logging_traces").update({"data": updated.model_dump()}).eq(
            "interview_id", interview_id
        ).eq("question_id", question_id).execute()
        return updated

    def get_trace(self, interview_id: str, question_id: str) -> Optional[TraceRecord]:
        result = (
            self._client.table("logging_traces")
            .select("data")
            .eq("interview_id", interview_id)
            .eq("question_id", question_id)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None
        return TraceRecord(**as_json_dict(result.data, "data"))

    def get_traces_for_interview(self, interview_id: str) -> list[TraceRecord]:
        result = (
            self._client.table("logging_traces")
            .select("data")
            .eq("interview_id", interview_id)
            .order("sequence_number")
            .execute()
        )
        return [TraceRecord(**as_json_dict(row, "data")) for row in result.data]

    def get_traces_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[TraceRecord]:
        result = (
            self._client.table("logging_traces")
            .select("data")
            .eq("interview_id", interview_id)
            .eq("competency_id", competency_id)
            .order("sequence_number")
            .execute()
        )
        return [TraceRecord(**as_json_dict(row, "data")) for row in result.data]
