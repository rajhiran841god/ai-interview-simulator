"""
Schema for JD Understanding output. Must match
docs/contracts/JD_Understanding_Contract_2.md exactly.

Same two-state confidence model as Resume Understanding — no
"inferred" state here either.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

Confidence = Literal["stated", "absent"]
Emphasis = Literal["primary", "secondary"]
SeniorityLevel = Literal["entry", "associate", "mid", "senior", "leadership"]

PARSER_VERSION = "jd_parser_v1.0.0"


class RoleTitle(BaseModel):
    value: Optional[str] = None
    confidence: Confidence = "absent"
    source_text: Optional[str] = None
    source_location: Optional[str] = None


class SeniorityLevelField(BaseModel):
    value: Optional[SeniorityLevel] = None
    confidence: Confidence = "absent"
    source_text: Optional[str] = None
    source_location: Optional[str] = None


class RequiredCompetency(BaseModel):
    competency_id: str
    competency_name: str
    emphasis: Emphasis
    source_text: str
    source_location: str


class RoleSpecificSignal(BaseModel):
    signal_text: str
    interpretation: str
    source_text: str
    source_location: str


class ErrorEntry(BaseModel):
    code: str
    message: str


class ProcessingMetadata(BaseModel):
    processing_time_ms: int
    text_length: int


class JDUnderstandingOutput(BaseModel):
    role_title: RoleTitle
    seniority_level: SeniorityLevelField
    required_competencies: list[RequiredCompetency] = Field(default_factory=list)
    role_specific_signals: list[RoleSpecificSignal] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    errors: list[ErrorEntry] = Field(default_factory=list)
    parser_version: str = PARSER_VERSION
    processing_metadata: ProcessingMetadata


class ErrorCode:
    EMPTY_JD = "EMPTY_JD"
    JD_TOO_SHORT = "JD_TOO_SHORT"
    JD_TOO_LARGE = "JD_TOO_LARGE"
    STRUCTURING_FAILED = "STRUCTURING_FAILED"


class RejectionError(Exception):
    """Raised only for JD_TOO_LARGE per the contract — the sole
    rejection-tier error for this module."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
