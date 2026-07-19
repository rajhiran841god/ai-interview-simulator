"""
Logging storage abstraction. Small interface, same pattern as
Conversation Memory and Evidence Graph stores.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from app.engine.logging.schema import TraceRecord


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
