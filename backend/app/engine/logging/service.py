"""
Public API for Logging / Trace Recorder. Deterministic, zero reasoning
logic. Records decisions; never makes them.
"""

import datetime
from typing import Optional

import pydantic

from app.engine.logging.schema import TraceRecord, LoggingError, ErrorCode
from app.engine.logging.store import TraceStore, InMemoryTraceStore, generate_trace_id
from app.shared.types import DecisionStrategy


class LoggingService:
    def __init__(self, store: Optional[TraceStore] = None):
        self._store = store or InMemoryTraceStore()

    def record_trace(
        self,
        interview_id: str,
        question_id: str,
        decision_strategy: DecisionStrategy,
        confidence_pre: float,
        evidence_missing: str,
        reason_for_asking: str,
        prompt_version: str,
        model_version: str,
        target_competency_id: Optional[str] = None,
    ) -> TraceRecord:
        seq = self._store.next_sequence_number(interview_id)
        try:
            trace = TraceRecord(
                trace_id=generate_trace_id(),
                interview_id=interview_id,
                question_id=question_id,
                target_competency_id=target_competency_id,
                decision_strategy=decision_strategy,
                confidence_pre=confidence_pre,
                confidence_post=None,
                evidence_missing=evidence_missing,
                reason_for_asking=reason_for_asking,
                evidence_ids_referenced=[],
                prompt_version=prompt_version,
                model_version=model_version,
                sequence_number=seq,
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        except pydantic.ValidationError as e:
            # Translate the schema-level domain validation (confidence
            # range) into the contract's own error code, so callers
            # deal with LoggingError consistently rather than needing
            # to know about Pydantic internals.
            if "confidence_pre" in str(e):
                raise LoggingError(
                    ErrorCode.CONFIDENCE_OUT_OF_RANGE,
                    f"confidence_pre must be within [0.0, 1.0]: {e}",
                )
            raise

        return self._store.append_trace(trace)

    def update_trace_outcome(
        self,
        interview_id: str,
        question_id: str,
        confidence_post: float,
        evidence_ids_referenced: list[str],
    ) -> TraceRecord:
        if not (0.0 <= confidence_post <= 1.0):
            raise LoggingError(
                ErrorCode.CONFIDENCE_OUT_OF_RANGE,
                f"confidence_post {confidence_post} is outside the valid range [0.0, 1.0]",
            )
        return self._store.update_outcome(
            interview_id, question_id, confidence_post, evidence_ids_referenced
        )

    def get_trace(self, interview_id: str, question_id: str):
        return self._store.get_trace(interview_id, question_id)

    def get_traces_for_interview(self, interview_id: str) -> list[TraceRecord]:
        return self._store.get_traces_for_interview(interview_id)

    def get_traces_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[TraceRecord]:
        return self._store.get_traces_for_competency(interview_id, competency_id)
