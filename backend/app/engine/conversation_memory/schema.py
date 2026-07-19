"""
Schema for Conversation Memory. Must match
docs/contracts/Conversation_Memory_Contract_2.md exactly.

This module is deterministic — see the contract's enforceable
constraint. Nothing in this package may import ProviderAdapter, an
LLM SDK, or an embeddings/semantic-search library. That rule is
enforced by review (and could be enforced by a lint rule later), not
by anything in this file itself.
"""

from typing import Literal, Optional
from pydantic import BaseModel

QuestionType = Literal["fresh", "cross_question"]
TurnStatus = Literal["asked", "answered"]

DEFAULT_SIMILARITY_THRESHOLD = 0.85


class TurnRecord(BaseModel):
    turn_id: str
    interview_id: str
    question_id: str
    sequence_number: int
    question_text: str
    question_type: QuestionType
    target_competency_id: Optional[str] = None
    question_timestamp: str
    answer_text: Optional[str] = None
    answer_timestamp: Optional[str] = None
    status: TurnStatus = "asked"

    # Internal-only fields, not part of the public contract schema but
    # useful for debugging/operations per reviewer's suggestion. Not
    # required in equality checks against the public schema.
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ErrorCode:
    DUPLICATE_QUESTION_ID = "DUPLICATE_QUESTION_ID"
    ANSWER_WITHOUT_QUESTION = "ANSWER_WITHOUT_QUESTION"
    ALREADY_ANSWERED = "ALREADY_ANSWERED"
    INTERVIEW_NOT_FOUND = "INTERVIEW_NOT_FOUND"  # not raised — reads degrade gracefully; kept for reference/logging use


class ConversationMemoryError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
