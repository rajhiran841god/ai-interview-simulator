"""
Schema for Competency Model. Must match
docs/contracts/Competency_Model_Contract.md exactly.
"""

from typing import Optional
from pydantic import BaseModel, field_validator

from app.shared.types import Emphasis


class CompetencyState(BaseModel):
    interview_id: str
    competency_id: str
    emphasis: Emphasis
    evidence_count: int = 0
    positive_evidence: list[str] = []
    contradictory_evidence: list[str] = []
    confidence: float = 0.0
    last_updated: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence {v} is outside the valid range [0.0, 1.0]")
        return v


class CompetencySeed(BaseModel):
    """Input shape for initialize_competencies — matches JD
    Understanding's required_competencies entries closely, but only
    the two fields this module actually needs."""

    competency_id: str
    emphasis: Emphasis


class ErrorCode:
    COMPETENCY_NOT_INITIALIZED = "COMPETENCY_NOT_INITIALIZED"
    DUPLICATE_INITIALIZATION = "DUPLICATE_INITIALIZATION"
    CONFIDENCE_CONTRIBUTION_OUT_OF_RANGE = "CONFIDENCE_CONTRIBUTION_OUT_OF_RANGE"
    INTERVIEW_NOT_FOUND = "INTERVIEW_NOT_FOUND"  # not raised — reads degrade gracefully


class CompetencyModelError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
