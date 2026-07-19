"""
Schema for Evidence Graph. Must match
docs/contracts/Evidence_Graph_Contract.md exactly.

Deterministic module — no ProviderAdapter, no LLM, no embeddings.
Entries are immutable after creation, per reviewer's suggestion
(consistent with Conversation Memory's immutability philosophy): if an
evaluator later decides an evidence item was wrong, the correct action
is to add NEW evidence that contradicts the old one, not edit history.
"""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

Relation = Literal["supports", "contradicts"]


class EvidenceEntry(BaseModel):
    model_config = ConfigDict(
        frozen=True
    )  # Immutability enforced at the model level, not just by convention

    evidence_id: str
    interview_id: str
    competency_id: str
    turn_id: str
    question_id: str
    evidence_excerpt: str
    relation: Relation
    contradicts_evidence_id: Optional[str] = None
    created_at: str

    # Optional character-offset metadata, per reviewer's suggestion —
    # not required by the contract, populated when the caller can
    # supply it (e.g. once Evaluation Engine does its own text search),
    # left None otherwise. Not used by any provenance check itself —
    # is_traceable() as substring matching is the actual enforcement
    # mechanism regardless of whether offsets are present.
    excerpt_start: Optional[int] = None
    excerpt_end: Optional[int] = None


class ErrorCode:
    TURN_NOT_FOUND = "TURN_NOT_FOUND"
    EXCERPT_NOT_TRACEABLE = "EXCERPT_NOT_TRACEABLE"
    CONTRADICTS_TARGET_NOT_FOUND = "CONTRADICTS_TARGET_NOT_FOUND"
    MISSING_CONTRADICTION_TARGET = "MISSING_CONTRADICTION_TARGET"


class EvidenceGraphError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
