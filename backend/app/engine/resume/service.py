"""
Public API for the Resume Understanding module. This is the ONLY
function other modules (or API routes) should call — everything else
in this package is an internal implementation detail.

Orchestrates: deterministic extraction -> LLM structuring ->
provenance validation -> contract-compliant output.
"""

import time

from app.engine.resume.extractors import extract_text
from app.engine.resume.structurer import structure_resume_text
from app.engine.resume.validator import validate_value
from app.engine.resume.schema import (
    ResumeUnderstandingOutput,
    PersonalSummary,
    EducationEntry,
    WorkExperienceEntry,
    ProjectEntry,
    SimpleValueEntry,
    ProbeWorthyClaim,
    ProcessingMetadata,
    ErrorEntry,
    PARSER_VERSION,
)


def understand_resume(file_bytes: bytes, file_format: str) -> ResumeUnderstandingOutput:
    """
    Public API. Raises RejectionError for UNSUPPORTED_FORMAT,
    CORRUPTED_FILE, PASSWORD_PROTECTED, FILE_TOO_LARGE (per contract,
    these return no resume object at all — caller/API layer should
    catch and translate to an HTTP error).

    For EMPTY_DOCUMENT / TEXT_EXTRACTION_FAILED, does NOT raise —
    returns a valid, mostly-absent ResumeUnderstandingOutput with
    parse_warnings/errors populated, per the contract's distinction
    between rejection and recoverable errors.
    """
    start = time.monotonic()

    extracted = extract_text(
        file_bytes, file_format
    )  # raises RejectionError if applicable
    raw_text = extracted.text

    parse_warnings: list[str] = []
    errors: list[ErrorEntry] = []

    if len(raw_text.strip()) == 0:
        errors.append(
            ErrorEntry(
                code="EMPTY_DOCUMENT",
                message="No extractable text was found in this document.",
            )
        )
        return _empty_output(extracted, start, parse_warnings, errors)

    if len(raw_text.strip()) < 20:
        errors.append(
            ErrorEntry(
                code="TEXT_EXTRACTION_FAILED",
                message="Very little text could be extracted. This may be a scanned or image-based document; OCR is not supported in v0.1.",
            )
        )
        return _empty_output(extracted, start, parse_warnings, errors)

    structured = structure_resume_text(raw_text)
    if not structured:
        parse_warnings.append(
            "Semantic structuring failed to produce valid output; falling back to minimal extraction."
        )
        return _empty_output(extracted, start, parse_warnings, errors)

    output = _build_validated_output(
        structured, raw_text, extracted, start, parse_warnings, errors
    )
    return output


def _empty_output(
    extracted, start, parse_warnings, errors
) -> ResumeUnderstandingOutput:
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return ResumeUnderstandingOutput(
        personal_summary=PersonalSummary(),
        education=[],
        work_experience=[],
        projects=[],
        skills=[],
        certifications=[],
        achievements=[],
        probe_worthy_claims=[],
        parse_warnings=parse_warnings,
        errors=errors,
        parser_version=PARSER_VERSION,
        processing_metadata=ProcessingMetadata(
            processing_time_ms=elapsed_ms,
            text_length=len(extracted.text),
            pages_detected=extracted.pages_detected,
            ocr_used=extracted.ocr_used,
        ),
    )


def _build_validated_output(
    structured: dict, raw_text: str, extracted, start, parse_warnings, errors
) -> ResumeUnderstandingOutput:
    # Personal summary
    ps_raw = structured.get("personal_summary")
    if ps_raw and isinstance(ps_raw, dict):
        result = validate_value(
            dict(ps_raw), raw_text, fallback_location="Personal Summary"
        )
        parse_warnings.extend(result.warnings)
        v = result.value
        personal_summary = PersonalSummary(
            value=v.get("value"),
            confidence=v.get("confidence", "absent"),
            source_text=v.get("source_text"),
            source_location=v.get("source_location"),
        )
    else:
        personal_summary = PersonalSummary()

    education = []
    for entry in structured.get("education", []) or []:
        result = validate_value(dict(entry), raw_text, fallback_location="Education")
        parse_warnings.extend(result.warnings)
        if result.accepted:
            v = result.value
            education.append(
                EducationEntry(
                    institution=v.get("institution"),
                    degree=v.get("degree"),
                    field=v.get("field"),
                    dates=v.get("dates"),
                    confidence="stated",
                    source_text=v["source_text"],
                    source_location=v.get("source_location", "Education"),
                )
            )

    work_experience = []
    for entry in structured.get("work_experience", []) or []:
        result = validate_value(
            dict(entry), raw_text, fallback_location="Work Experience"
        )
        parse_warnings.extend(result.warnings)
        if result.accepted:
            v = result.value
            work_experience.append(
                WorkExperienceEntry(
                    organization=v.get("organization"),
                    role=v.get("role"),
                    dates=v.get("dates"),
                    description_raw=v.get("description_raw", ""),
                    confidence="stated",
                    source_text=v["source_text"],
                    source_location=v.get("source_location", "Work Experience"),
                )
            )

    projects = [
        ProjectEntry(
            name=p.get("name"),
            description_raw=p.get("description_raw", ""),
            source_location=p.get("source_location") or "Projects",
        )
        for p in (structured.get("projects", []) or [])
    ]

    def _simple_list(key: str, section_label: str) -> list[SimpleValueEntry]:
        return [
            SimpleValueEntry(value=v, source_location=section_label)
            for v in (structured.get(key, []) or [])
            if isinstance(v, str)
        ]

    skills = _simple_list("skills", "Skills")
    certifications = _simple_list("certifications", "Certifications")
    achievements = _simple_list("achievements", "Achievements")

    probe_worthy_claims = [
        ProbeWorthyClaim(
            claim_text=c.get("claim_text", ""),
            source_section=c.get("source_section", "work_experience"),
            source_location=c.get("source_section", "work_experience")
            .replace("_", " ")
            .title(),
            reason_flagged=c.get("reason_flagged", ""),
        )
        for c in (structured.get("probe_worthy_claims", []) or [])
    ]

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return ResumeUnderstandingOutput(
        personal_summary=personal_summary,
        education=education,
        work_experience=work_experience,
        projects=projects,
        skills=skills,
        certifications=certifications,
        achievements=achievements,
        probe_worthy_claims=probe_worthy_claims,
        parse_warnings=parse_warnings,
        errors=errors,
        parser_version=PARSER_VERSION,
        processing_metadata=ProcessingMetadata(
            processing_time_ms=elapsed_ms,
            text_length=len(raw_text),
            pages_detected=extracted.pages_detected,
            ocr_used=extracted.ocr_used,
        ),
    )
