"""
Schema for Evaluation Engine. Must match
docs/contracts/Evaluation_Engine_Contract.md exactly.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

from app.shared.types import AnswerClassification


class EvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer_classification: AnswerClassification
    evidence_ids_created: list[str] = []
    contradiction_detected: bool = False
    contradicted_evidence_id: Optional[str] = None
    confidence_contribution: float
    reasoning_summary: str

    @field_validator("confidence_contribution")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(
                f"confidence_contribution {v} is outside the valid range [0.0, 1.0]"
            )
        return v


class ErrorCode:
    EMPTY_ANSWER = "EMPTY_ANSWER"  # not raised — handled internally, see service.py
    EVALUATION_FAILED = "EVALUATION_FAILED"  # not raised — degraded result returned
    TRACE_NOT_FOUND = "TRACE_NOT_FOUND"


class EvaluationEngineError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def degraded_result(reasoning_summary: str) -> EvaluationResult:
    """The single degraded-path result used for EMPTY_ANSWER,
    EVALUATION_FAILED, and out-of-range confidence (reject-not-clamp
    policy) — one consistent shape for every recoverable failure mode."""
    return EvaluationResult(
        answer_classification="non_answer",
        evidence_ids_created=[],
        contradiction_detected=False,
        contradicted_evidence_id=None,
        confidence_contribution=0.0,
        reasoning_summary=reasoning_summary,
    )
