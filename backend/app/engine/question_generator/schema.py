"""
Schema for Question Generator. Must match
docs/contracts/Question_Generator_Contract.md exactly.
"""

from typing import Literal
from pydantic import BaseModel

from app.shared.types import QuestionType

GenerationMethod = Literal["llm", "fallback_template"]


class GeneratedQuestion(BaseModel):
    model_config = {"frozen": True}

    question_id: str
    question_text: str
    question_type: QuestionType
    target_competency_id: str
    generation_method: GenerationMethod


class ErrorCode:
    INVALID_DECISION_TYPE = "INVALID_DECISION_TYPE"
    GENERATION_FAILED = "GENERATION_FAILED"  # not raised — fallback used
    TURN_RECORDING_FAILED = "TURN_RECORDING_FAILED"


class QuestionGeneratorError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
