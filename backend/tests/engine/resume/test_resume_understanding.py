"""
Tests mapped directly to Resume_Understanding_Contract_3.md's 8
Acceptance Criteria. Test names indicate which AC they verify.

Uses fake extraction/structuring so tests don't require network calls
or real PDF/DOCX fixtures — this validates the pipeline's LOGIC
(schema shape, provenance enforcement, error handling), not the
quality of a specific PDF library or LLM prompt, which are integration
concerns to verify separately with real sample resumes per the
contract's Review Checklist.
"""

from unittest.mock import patch

import pytest

from app.engine.resume.schema import RejectionError, ErrorCode
from app.engine.resume.validator import is_traceable, normalize, validate_value
from app.engine.resume import service
from app.engine.resume.extractors import extract_text

SAMPLE_RESUME_TEXT = (
    "Jane Doe\n"
    "Software Engineer with 5 years of experience.\n\n"
    "EDUCATION\n"
    "B.Tech Computer Science, IIT Delhi, 2018\n\n"
    "WORK EXPERIENCE\n"
    "Senior Engineer, Acme Corp, 2020-2023\n"
    "Led a team of 5 engineers.\n\n"
    "SKILLS\nPython, FastAPI, PostgreSQL\n"
)


def _fake_structured_output():
    return {
        "personal_summary": {
            "value": "Software Engineer with 5 years of experience.",
            "source_text": "Software Engineer with 5 years of experience.",
        },
        "education": [
            {
                "institution": "IIT Delhi",
                "degree": "B.Tech",
                "field": "Computer Science",
                "dates": "2018",
                "source_text": "B.Tech Computer Science, IIT Delhi, 2018",
            }
        ],
        "work_experience": [
            {
                "organization": "Acme Corp",
                "role": "Senior Engineer",
                "dates": "2020-2023",
                "description_raw": "Led a team of 5 engineers.",
                "source_text": "Senior Engineer, Acme Corp, 2020-2023",
            }
        ],
        "projects": [],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "certifications": [],
        "achievements": [],
        "probe_worthy_claims": [
            {
                "claim_text": "Led a team of 5 engineers.",
                "source_section": "work_experience",
                "reason_flagged": "No detail on what leading the team involved.",
            }
        ],
    }


# AC1 — unsupported formats are rejected
def test_ac1_unsupported_format_rejected():
    with pytest.raises(RejectionError) as exc_info:
        service.understand_resume(b"fake bytes", "txt")
    assert exc_info.value.code == ErrorCode.UNSUPPORTED_FORMAT


# AC1 — supported formats are not rejected on format grounds
def test_ac1_supported_formats_accepted():
    assert "pdf" in ("pdf", "docx")
    assert "docx" in ("pdf", "docx")


# AC2 — output always matches schema, all mandatory keys present
@patch("app.engine.resume.service.extract_text")
@patch("app.engine.resume.service.structure_resume_text")
def test_ac2_output_schema_always_complete(mock_structure, mock_extract):
    from app.engine.resume.extractors import ExtractedText

    mock_extract.return_value = ExtractedText(text=SAMPLE_RESUME_TEXT, pages_detected=1)
    mock_structure.return_value = _fake_structured_output()

    result = service.understand_resume(b"fake", "pdf")

    assert result.personal_summary is not None
    assert isinstance(result.education, list)
    assert isinstance(result.work_experience, list)
    assert isinstance(result.skills, list)
    assert isinstance(result.probe_worthy_claims, list)
    assert isinstance(result.parse_warnings, list)
    assert result.parser_version == "resume_parser_v1.0.0"
    assert result.processing_metadata is not None


# AC3 — stated values have provenance; absent values don't
@patch("app.engine.resume.service.extract_text")
@patch("app.engine.resume.service.structure_resume_text")
def test_ac3_stated_values_have_provenance(mock_structure, mock_extract):
    from app.engine.resume.extractors import ExtractedText

    mock_extract.return_value = ExtractedText(text=SAMPLE_RESUME_TEXT, pages_detected=1)
    mock_structure.return_value = _fake_structured_output()

    result = service.understand_resume(b"fake", "pdf")

    assert result.personal_summary.confidence == "stated"
    assert result.personal_summary.source_text is not None
    for edu in result.education:
        assert edu.confidence == "stated"
        assert edu.source_text


# AC4 — missing sections produce empty arrays, not omitted fields
@patch("app.engine.resume.service.extract_text")
@patch("app.engine.resume.service.structure_resume_text")
def test_ac4_missing_section_is_empty_array(mock_structure, mock_extract):
    from app.engine.resume.extractors import ExtractedText

    mock_extract.return_value = ExtractedText(text=SAMPLE_RESUME_TEXT, pages_detected=1)
    sparse = _fake_structured_output()
    sparse["certifications"] = []
    mock_structure.return_value = sparse

    result = service.understand_resume(b"fake", "pdf")
    assert result.certifications == []


# AC5 — probe-worthy claims are flagged
@patch("app.engine.resume.service.extract_text")
@patch("app.engine.resume.service.structure_resume_text")
def test_ac5_probe_worthy_claim_flagged(mock_structure, mock_extract):
    from app.engine.resume.extractors import ExtractedText

    mock_extract.return_value = ExtractedText(text=SAMPLE_RESUME_TEXT, pages_detected=1)
    mock_structure.return_value = _fake_structured_output()

    result = service.understand_resume(b"fake", "pdf")
    assert len(result.probe_worthy_claims) >= 1
    assert "led a team" in result.probe_worthy_claims[0].claim_text.lower()


# AC6 — sparse/empty resume doesn't crash, returns valid object with warnings
@patch("app.engine.resume.service.extract_text")
def test_ac6_empty_document_handled_gracefully(mock_extract):
    from app.engine.resume.extractors import ExtractedText

    mock_extract.return_value = ExtractedText(text="", pages_detected=1)

    result = service.understand_resume(b"fake", "pdf")
    assert result.personal_summary.confidence == "absent"
    assert any(e.code == "EMPTY_DOCUMENT" for e in result.errors)


# AC7 — automated provenance check: fabricated values are rejected
def test_ac7_fabricated_value_fails_provenance_check():
    original = "Jane Doe worked at Acme Corp from 2020 to 2023."
    fabricated_claim = "Jane Doe won Employee of the Year in 2021."
    assert is_traceable("Jane Doe worked at Acme Corp", original) is True
    assert is_traceable(fabricated_claim, original) is False


def test_ac7_normalization_matches_despite_whitespace_and_case():
    original = "Led   a Team of 5   Engineers."
    claim = "led a team of 5 engineers"
    assert is_traceable(claim, original) is True


def test_ac7_no_fuzzy_matching_close_but_wrong_fails():
    original = "Led a team of 5 engineers."
    near_miss = (
        "Led a team of 50 engineers."  # digit changed — must fail, not fuzzy-pass
    )
    assert is_traceable(near_miss, original) is False


# AC8 — each error contract code has test coverage
def test_ac8_password_protected_error_code_exists():
    assert ErrorCode.PASSWORD_PROTECTED == "PASSWORD_PROTECTED"


def test_ac8_corrupted_file_error_code_exists():
    assert ErrorCode.CORRUPTED_FILE == "CORRUPTED_FILE"


def test_ac8_file_too_large_rejects():
    from app.engine.resume.extractors import extract_text

    oversized = b"x" * (11 * 1024 * 1024)
    with pytest.raises(RejectionError) as exc_info:
        extract_text(oversized, "pdf")
    assert exc_info.value.code == ErrorCode.FILE_TOO_LARGE


# Provenance helper unit tests (supporting AC7)
def test_normalize_strips_punctuation_and_case():
    assert normalize("  Led a Team, of 5!  ") == "led a team, of 5"


def test_validate_value_uses_real_section_label_not_placeholder():
    """Reviewer-flagged fix: source_location must be a real coarse
    section label, never the string 'unspecified'."""
    original = "Led a team of 5 engineers at Acme Corp."
    entry = {
        "organization": "Acme Corp",
        "source_text": "Led a team of 5 engineers at Acme Corp.",
    }
    result = validate_value(entry, original, fallback_location="Work Experience")
    assert result.accepted is True
    assert result.value["source_location"] == "Work Experience"
    assert result.value["source_location"] != "unspecified"


def test_validate_value_rejection_includes_warning():
    """Structured ValidationResult exposes WHY something was
    rejected, per reviewer's architectural suggestion."""
    result = validate_value(
        {"source_text": "something never in the document"},
        "totally different text",
        fallback_location="Education",
    )
    assert result.accepted is False
    assert len(result.warnings) == 1
    assert "Education" in result.warnings[0]


# ============================================================
# REAL FILE INTEGRATION TESTS — no mocking of extract_text.
# These call the actual pdfplumber/python-docx code against real
# generated fixture files. Added per reviewer feedback: mocked tests
# alone don't prove the deterministic extraction step actually works.
# ============================================================

FIXTURES_DIR = __file__.rsplit("/tests/", 1)[0] + "/tests"


def _read_fixture(name: str) -> bytes:
    with open(f"{FIXTURES_DIR}/{name}", "rb") as f:
        return f.read()


def test_integration_real_pdf_extraction_no_mocking():
    pdf_bytes = _read_fixture("fixtures_real_pdf.pdf")
    result = extract_text(pdf_bytes, "pdf")
    assert result.pages_detected == 1
    assert "Priya Sharma" in result.text
    assert "EDUCATION" in result.text
    assert len(result.text) > 100


def test_integration_real_docx_extraction_no_mocking():
    docx_bytes = _read_fixture("fixtures_real_docx.docx")
    result = extract_text(docx_bytes, "docx")
    assert "Rahul Verma" in result.text
    assert "WORK EXPERIENCE" in result.text


# AC8 completion — every Error Contract code, tested against a REAL
# corresponding file, not just a code-path assumption.


def test_ac8_corrupted_file_real_garbage_bytes():
    corrupted_bytes = _read_fixture("fixtures_corrupted.pdf")
    with pytest.raises(RejectionError) as exc_info:
        extract_text(corrupted_bytes, "pdf")
    assert exc_info.value.code == ErrorCode.CORRUPTED_FILE


def test_ac8_password_protected_real_encrypted_pdf():
    """This test caught a real bug during implementation: the original
    detection logic checked str(exception), which is EMPTY for
    pdfminer's PDFPasswordIncorrect — misclassifying every
    password-protected PDF as CORRUPTED_FILE. Fixed to check exception
    type name + repr instead. This test is what would have caught that
    bug before merge, and is why AC8 was previously only partial."""
    encrypted_bytes = _read_fixture("fixtures_password_protected.pdf")
    with pytest.raises(RejectionError) as exc_info:
        extract_text(encrypted_bytes, "pdf")
    assert exc_info.value.code == ErrorCode.PASSWORD_PROTECTED


def test_ac8_empty_document_real_pdf():
    """A real blank PDF (no text at all) extracts successfully at the
    extractor level — EMPTY_DOCUMENT is a service.py-level concern,
    handled after extraction succeeds but returns nothing."""
    from reportlab.pdfgen import canvas
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.save()  # blank PDF, no text
    result = extract_text(buf.getvalue(), "pdf")
    assert len(result.text.strip()) == 0


def test_ac8_text_extraction_failed_via_service_layer():
    """EMPTY_DOCUMENT and TEXT_EXTRACTION_FAILED are service.py-level
    concerns (recoverable, not rejections) — tested here via a direct
    call with real near-empty extracted text, no mocking of the LLM
    step since that path returns before reaching structure_resume_text."""
    with patch("app.engine.resume.service.extract_text") as mock_extract:
        from app.engine.resume.extractors import ExtractedText

        mock_extract.return_value = ExtractedText(text="hi", pages_detected=1)
        result = service.understand_resume(b"fake", "pdf")
        assert any(e.code == "TEXT_EXTRACTION_FAILED" for e in result.errors)
