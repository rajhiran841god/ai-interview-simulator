"""
Interview session schema — the orchestration layer that ties Resume
Understanding, JD Understanding, and the rest of the engine together
into an actual usable interview lifecycle over HTTP.

This is NEW — it did not exist before. The 10 engine modules were
always exercised by tests directly; nothing previously wired them
together behind an API a frontend could call. This is that layer.
"""

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

SessionStatus = Literal[
    "created", "resume_uploaded", "jd_uploaded", "ready", "in_progress", "completed"
]


class InterviewSession(BaseModel):
    interview_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: SessionStatus = "created"
    resume_summary: Optional[dict] = None  # ResumeUnderstandingOutput, dumped
    jd_summary: Optional[dict] = None  # JDUnderstandingOutput, dumped
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CreateSessionRequest(BaseModel):
    pass  # user_id comes from auth context, not the request body


class SessionResponse(BaseModel):
    interview_id: str
    status: SessionStatus
    created_at: str


class NextQuestionResponse(BaseModel):
    decision_type: Literal["continue", "stop"]
    question_id: str
    question_text: Optional[str] = None
    target_competency_id: Optional[str] = None
    stop_reason: Optional[str] = None


class SubmitAnswerRequest(BaseModel):
    question_id: str
    answer_text: str


class SubmitAnswerResponse(BaseModel):
    accepted: bool
    answer_classification: Optional[str] = None


class EvidenceDetail(BaseModel):
    """
    Presentation-layer shape exposing existing Evidence Graph data for
    the frontend's evidence-footnote interaction. Per Decision Log #006:
    this is orchestration/API infrastructure, not an engine change —
    it exposes EvidenceEntry + TurnRecord fields that already exist,
    joined and reshaped for display, without modifying either module's
    schema or Feedback Generator's prompt/output at all.
    """

    evidence_id: str
    evidence_excerpt: str
    relation: str
    question_number: int
