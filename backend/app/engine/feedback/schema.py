"""
Schema for Feedback Generator. Must match
docs/contracts/Feedback_Generator_Contract.md exactly.

AC1 (the merge-blocking criterion): no field here is, or derives from,
a raw confidence number. This is enforced by construction — there is
no float field anywhere in this schema. A structural test
(test_ac1_no_confidence_field_in_schema) verifies this directly
against the schema definition, not example output.
"""

from pydantic import BaseModel

from app.shared.types import Emphasis


class CompetencyFeedback(BaseModel):
    model_config = {"frozen": True}

    competency_id: str
    emphasis: Emphasis
    summary_text: str
    supporting_evidence_ids: list[str] = []
    contradictory_evidence_ids: list[str] = []
    has_unresolved_contradiction: bool = False
    insufficient_evidence: bool = False


class InterviewFeedbackReport(BaseModel):
    model_config = {"frozen": True}

    interview_id: str
    competency_feedback: list[CompetencyFeedback]
    overall_summary: str
    generated_at: str


class ErrorCode:
    NO_COMPETENCIES_INITIALIZED = "NO_COMPETENCIES_INITIALIZED"
    GENERATION_FAILED = "GENERATION_FAILED"  # not raised — per-competency fallback used


class FeedbackGeneratorError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
