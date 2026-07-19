"""
Schema for Reasoning Engine. Must match
docs/contracts/Reasoning_Engine_Contract.md exactly.
"""

from typing import Optional, Literal
from pydantic import BaseModel

from app.shared.types import DecisionStrategy

DecisionType = Literal["continue", "stop"]


class ReasoningDecision(BaseModel):
    model_config = {"frozen": True}

    question_id: str
    decision_type: DecisionType
    target_competency_id: Optional[str] = None
    decision_strategy: Optional[DecisionStrategy] = None
    evidence_missing: Optional[str] = None
    reason_for_asking: Optional[str] = None
    stop_reason: Optional[str] = None


class ErrorCode:
    NO_COMPETENCIES_INITIALIZED = "NO_COMPETENCIES_INITIALIZED"
    TRACE_WRITE_FAILED = "TRACE_WRITE_FAILED"


class ReasoningEngineError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
