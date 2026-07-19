"""
Public API for JD Understanding. Only function other modules should
call: understand_jd(jd_text). Everything else in this package is
internal.
"""

import time

from app.engine.jd.structurer import structure_jd_text
from app.engine.jd.schema import (
    JDUnderstandingOutput,
    RoleTitle,
    SeniorityLevelField,
    RequiredCompetency,
    RoleSpecificSignal,
    ProcessingMetadata,
    ErrorEntry,
    RejectionError,
    ErrorCode,
    PARSER_VERSION,
)
from app.engine.shared.validator import validate_value, normalize_competency_id

JD_TOO_LARGE_CHARS = (
    20000  # configurable — implementation default, not hardcoded contract value
)
JD_TOO_SHORT_CHARS = 50


def understand_jd(jd_text: str) -> JDUnderstandingOutput:
    """
    Public API. Raises RejectionError only for JD_TOO_LARGE — the
    sole rejection-tier error per the contract. All other conditions
    (empty, too short, structuring failure) return a valid,
    mostly-absent output object with errors/parse_warnings populated,
    per the contract's Error Contract.
    """
    start = time.monotonic()

    if len(jd_text) > JD_TOO_LARGE_CHARS:
        raise RejectionError(
            ErrorCode.JD_TOO_LARGE,
            f"JD text exceeds the {JD_TOO_LARGE_CHARS} character limit.",
        )

    parse_warnings: list[str] = []
    errors: list[ErrorEntry] = []

    if len(jd_text.strip()) == 0:
        errors.append(
            ErrorEntry(code=ErrorCode.EMPTY_JD, message="No JD text was provided.")
        )
        return _empty_output(jd_text, start, parse_warnings, errors)

    if len(jd_text.strip()) < JD_TOO_SHORT_CHARS:
        errors.append(
            ErrorEntry(
                code=ErrorCode.JD_TOO_SHORT,
                message="JD text is too short to meaningfully extract competencies from.",
            )
        )
        return _empty_output(jd_text, start, parse_warnings, errors)

    structured = structure_jd_text(jd_text)
    if not structured:
        errors.append(
            ErrorEntry(
                code=ErrorCode.STRUCTURING_FAILED,
                message="Semantic structuring failed to produce valid output.",
            )
        )
        parse_warnings.append(
            "Falling back to minimal extraction due to structuring failure."
        )
        return _empty_output(jd_text, start, parse_warnings, errors)

    return _build_validated_output(structured, jd_text, start, parse_warnings, errors)


def _empty_output(jd_text, start, parse_warnings, errors) -> JDUnderstandingOutput:
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return JDUnderstandingOutput(
        role_title=RoleTitle(),
        seniority_level=SeniorityLevelField(),
        required_competencies=[],
        role_specific_signals=[],
        parse_warnings=parse_warnings,
        errors=errors,
        parser_version=PARSER_VERSION,
        processing_metadata=ProcessingMetadata(
            processing_time_ms=elapsed_ms, text_length=len(jd_text)
        ),
    )


def _build_validated_output(
    structured: dict, jd_text: str, start, parse_warnings, errors
) -> JDUnderstandingOutput:
    # Role title
    rt_raw = structured.get("role_title")
    if rt_raw and isinstance(rt_raw, dict):
        result = validate_value(dict(rt_raw), jd_text, fallback_location="Role Summary")
        parse_warnings.extend(result.warnings)
        v = result.value
        role_title = RoleTitle(
            value=v.get("value"),
            confidence=v.get("confidence", "absent"),
            source_text=v.get("source_text"),
            source_location=v.get("source_location"),
        )
    else:
        role_title = RoleTitle()

    # Seniority level
    sl_raw = structured.get("seniority_level")
    if sl_raw and isinstance(sl_raw, dict):
        result = validate_value(dict(sl_raw), jd_text, fallback_location="Role Summary")
        parse_warnings.extend(result.warnings)
        v = result.value
        allowed_levels = {"entry", "associate", "mid", "senior", "leadership"}
        raw_value = v.get("value")
        if raw_value not in allowed_levels:
            raw_value = None
        seniority_level = SeniorityLevelField(
            value=raw_value,
            confidence=v.get("confidence", "absent") if raw_value else "absent",
            source_text=v.get("source_text") if raw_value else None,
            source_location=v.get("source_location") if raw_value else None,
        )
    else:
        seniority_level = SeniorityLevelField()

    # Required competencies
    required_competencies = []
    for entry in structured.get("required_competencies", []) or []:
        result = validate_value(
            dict(entry), jd_text, fallback_location="Requirements section"
        )
        parse_warnings.extend(result.warnings)
        if result.accepted:
            v = result.value
            competency_name = v.get("competency_name", "")
            emphasis = v.get("emphasis")
            if emphasis not in ("primary", "secondary"):
                parse_warnings.append(
                    f"Competency '{competency_name}' had an invalid emphasis value; dropped."
                )
                continue
            required_competencies.append(
                RequiredCompetency(
                    competency_id=normalize_competency_id(competency_name),
                    competency_name=competency_name,
                    emphasis=emphasis,
                    source_text=v["source_text"],
                    source_location=v.get("source_location", "Requirements section"),
                )
            )

    # Role-specific signals
    role_specific_signals = []
    for entry in structured.get("role_specific_signals", []) or []:
        result = validate_value(
            dict(entry), jd_text, fallback_location="Role Description"
        )
        parse_warnings.extend(result.warnings)
        if result.accepted:
            v = result.value
            role_specific_signals.append(
                RoleSpecificSignal(
                    signal_text=v.get("signal_text", ""),
                    interpretation=v.get("interpretation", ""),
                    source_text=v["source_text"],
                    source_location=v.get("source_location", "Role Description"),
                )
            )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return JDUnderstandingOutput(
        role_title=role_title,
        seniority_level=seniority_level,
        required_competencies=required_competencies,
        role_specific_signals=role_specific_signals,
        parse_warnings=parse_warnings,
        errors=errors,
        parser_version=PARSER_VERSION,
        processing_metadata=ProcessingMetadata(
            processing_time_ms=elapsed_ms, text_length=len(jd_text)
        ),
    )
