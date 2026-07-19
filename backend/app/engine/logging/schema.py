"""
Schema for Logging / Trace Recorder. Must match
docs/contracts/Logging_Trace_Recorder_Contract.md exactly.

Deterministic module — no ProviderAdapter, no LLM, no embeddings.
Zero reasoning logic: this module stores what it's told, validates
domain (confidence range, enum values), and does not evaluate or judge
the reasoning that produced the data.

First module to import from app.shared.types, per Decision Log #003.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

from app.shared.types import DecisionStrategy

CONTRACT_VERSION = "v1"


class TraceRecord(BaseModel):
    # Frozen, same immutability discipline as Evidence Graph's
    # EvidenceEntry. update_trace_outcome() creates a NEW record via
    # model_copy(update=...) rather than mutating in place — same
    # pattern as Conversation Memory's record_answer().
    model_config = ConfigDict(frozen=True)

    trace_id: str
    interview_id: str
    question_id: str
    target_competency_id: Optional[str] = None
    decision_strategy: DecisionStrategy
    confidence_pre: float
    confidence_post: Optional[float] = None
    evidence_missing: str
    reason_for_asking: str
    evidence_ids_referenced: list[str] = []
    prompt_version: str
    model_version: str
    sequence_number: int
    created_at: str
    contract_version: str = CONTRACT_VERSION

    @field_validator("confidence_pre")
    @classmethod
    def validate_confidence_pre_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"confidence_pre {v} is outside the valid range [0.0, 1.0]"
            )
        return v

    @field_validator("confidence_post")
    @classmethod
    def validate_confidence_post_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError(
                f"confidence_post {v} is outside the valid range [0.0, 1.0]"
            )
        return v


class ErrorCode:
    DUPLICATE_QUESTION_ID = "DUPLICATE_QUESTION_ID"
    TRACE_NOT_FOUND = "TRACE_NOT_FOUND"
    OUTCOME_ALREADY_RECORDED = "OUTCOME_ALREADY_RECORDED"
    CONFIDENCE_OUT_OF_RANGE = "CONFIDENCE_OUT_OF_RANGE"
    INTERVIEW_NOT_FOUND = "INTERVIEW_NOT_FOUND"  # reads degrade gracefully; not raised


class LoggingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
