"""
Schema for Resume Understanding output. Must match
docs/contracts/Resume_Understanding_Contract_3.md exactly.

Do not add fields not in the contract. Do not add an "inferred"
confidence state — it was deliberately removed in v2/v3.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

Confidence = Literal["stated", "absent"]

PARSER_VERSION = "resume_parser_v1.0.0"


class PersonalSummary(BaseModel):
    value: Optional[str] = None
    confidence: Confidence = "absent"
    source_text: Optional[str] = None
    source_location: Optional[str] = None


class EducationEntry(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    dates: Optional[str] = None
    confidence: Confidence = "stated"
    source_text: str
    source_location: str


class WorkExperienceEntry(BaseModel):
    organization: Optional[str] = None
    role: Optional[str] = None
    dates: Optional[str] = None
    description_raw: str
    confidence: Confidence = "stated"
    source_text: str
    source_location: str


class ProjectEntry(BaseModel):
    name: Optional[str] = None
    description_raw: str
    source_location: str


class SimpleValueEntry(BaseModel):
    value: str
    source_location: str


class ProbeWorthyClaim(BaseModel):
    claim_text: str
    source_section: Literal[
        "work_experience", "projects", "achievements", "personal_summary"
    ]
    source_location: str
    reason_flagged: str


class ErrorEntry(BaseModel):
    code: str
    message: str


class ProcessingMetadata(BaseModel):
    processing_time_ms: int
    text_length: int
    pages_detected: int
    ocr_used: bool = False


class ResumeUnderstandingOutput(BaseModel):
    personal_summary: PersonalSummary
    education: list[EducationEntry] = Field(default_factory=list)
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[SimpleValueEntry] = Field(default_factory=list)
    certifications: list[SimpleValueEntry] = Field(default_factory=list)
    achievements: list[SimpleValueEntry] = Field(default_factory=list)
    probe_worthy_claims: list[ProbeWorthyClaim] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    errors: list[ErrorEntry] = Field(default_factory=list)
    parser_version: str = PARSER_VERSION
    processing_metadata: ProcessingMetadata


# Error Contract codes — must match the contract exactly.
class ErrorCode:
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    CORRUPTED_FILE = "CORRUPTED_FILE"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    TEXT_EXTRACTION_FAILED = "TEXT_EXTRACTION_FAILED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"


class RejectionError(Exception):
    """Raised for errors that mean no resume object is returned at all
    (UNSUPPORTED_FORMAT, CORRUPTED_FILE, PASSWORD_PROTECTED, FILE_TOO_LARGE)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
