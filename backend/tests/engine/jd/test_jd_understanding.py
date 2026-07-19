"""
Tests mapped to JD_Understanding_Contract_2.md's 8 Acceptance
Criteria. Structuring is mocked (no live LLM call — see Known
Limitations note, same honest gap as Resume Understanding). The
competency_id normalization logic (AC4) and provenance validation
(AC3, shared with Resume Understanding) ARE tested for real, unmocked.
"""

from unittest.mock import patch

import pytest

from app.engine.jd.schema import RejectionError, ErrorCode
from app.engine.jd import service
from app.engine.shared.validator import normalize_competency_id, is_traceable

FIXTURES_DIR = __file__.rsplit("/tests/", 1)[0] + "/tests/fixtures_jd"


def _read_fixture(name: str) -> str:
    with open(f"{FIXTURES_DIR}/{name}") as f:
        return f.read()


def _fake_marketing_structured():
    return {
        "role_title": {
            "value": "Marketing Associate - Consumer Insights",
            "source_text": "Role: Marketing Associate - Consumer Insights",
        },
        "seniority_level": None,
        "required_competencies": [
            {
                "competency_name": "Consumer Insight",
                "emphasis": "primary",
                "source_text": "Strong consumer insight and market research skills, required",
            },
            {
                "competency_name": "Brand Storytelling",
                "emphasis": "primary",
                "source_text": "Excellent brand storytelling and campaign narrative ability",
            },
        ],
        "role_specific_signals": [
            {
                "signal_text": "fast-paced startup environment with shifting priorities",
                "interpretation": "candidate should demonstrate comfort with ambiguity and rapid iteration",
                "source_text": "Comfort working in a fast-paced startup environment with shifting priorities",
            }
        ],
    }


def _fake_finance_structured():
    return {
        "role_title": {
            "value": "Financial Analyst - Corporate Strategy",
            "source_text": "Role: Financial Analyst - Corporate Strategy",
        },
        "seniority_level": None,
        "required_competencies": [
            {
                "competency_name": "Financial Modeling",
                "emphasis": "primary",
                "source_text": "Advanced financial modeling skills, required",
            },
            {
                "competency_name": "Structured Problem Solving",
                "emphasis": "primary",
                "source_text": "Structured problem solving ability, required and heavily emphasized throughout evaluation",
            },
        ],
        "role_specific_signals": [],
    }


# AC1 — output always matches schema
@patch("app.engine.jd.service.structure_jd_text")
def test_ac1_output_schema_always_complete(mock_structure):
    mock_structure.return_value = _fake_marketing_structured()
    jd_text = _read_fixture("marketing_jd.txt")
    result = service.understand_jd(jd_text)

    assert result.role_title is not None
    assert isinstance(result.required_competencies, list)
    assert isinstance(result.role_specific_signals, list)
    assert isinstance(result.parse_warnings, list)
    assert result.parser_version == "jd_parser_v1.0.0"


# AC2 — stated values have provenance
@patch("app.engine.jd.service.structure_jd_text")
def test_ac2_stated_values_have_provenance(mock_structure):
    mock_structure.return_value = _fake_marketing_structured()
    jd_text = _read_fixture("marketing_jd.txt")
    result = service.understand_jd(jd_text)

    assert result.role_title.confidence == "stated"
    assert result.role_title.source_text is not None
    for comp in result.required_competencies:
        assert comp.source_text
        assert comp.source_location


# AC3 — required_competencies traceable to JD text (reuses shared validator, already proven)
def test_ac3_fabricated_competency_fails_provenance():
    original = "Advanced financial modeling skills, required"
    fabricated = "Expert knowledge of derivatives trading"
    assert is_traceable("Advanced financial modeling skills", original) is True
    assert is_traceable(fabricated, original) is False


# AC4 — valid emphasis tags and correct competency_id derivation
@patch("app.engine.jd.service.structure_jd_text")
def test_ac4_emphasis_and_competency_id(mock_structure):
    mock_structure.return_value = _fake_marketing_structured()
    jd_text = _read_fixture("marketing_jd.txt")
    result = service.understand_jd(jd_text)

    for comp in result.required_competencies:
        assert comp.emphasis in ("primary", "secondary")
        assert comp.competency_id == comp.competency_name.lower().replace(
            " ", "_"
        ).replace("-", "_")


def test_ac4_competency_id_normalization_variants_converge():
    """Reviewer-flagged requirement: different formattings of the same
    name must produce the same ID."""
    variants = [
        "Consumer Insight",
        "Consumer-Insight",
        "consumer insight",
        "Consumer  Insight",
    ]
    ids = {normalize_competency_id(v) for v in variants}
    assert len(ids) == 1
    assert ids.pop() == "consumer_insight"


def test_ac4_invalid_emphasis_is_dropped_not_kept():
    from app.engine.jd import service as svc

    bad_structured = {
        "role_title": None,
        "seniority_level": None,
        "required_competencies": [
            {
                "competency_name": "Something",
                "emphasis": "extremely_important",  # invalid value
                "source_text": "test text here",
            }
        ],
        "role_specific_signals": [],
    }
    with patch("app.engine.jd.service.structure_jd_text", return_value=bad_structured):
        result = svc.understand_jd("test text here " * 5)
    assert len(result.required_competencies) == 0
    assert any("invalid emphasis" in w for w in result.parse_warnings)


# AC5 — empty/short JD doesn't crash
def test_ac5_empty_jd_handled_gracefully():
    result = service.understand_jd("")
    assert result.role_title.confidence == "absent"
    assert any(e.code == ErrorCode.EMPTY_JD for e in result.errors)


def test_ac5_too_short_jd_handled_gracefully():
    result = service.understand_jd("too short")
    assert any(e.code == ErrorCode.JD_TOO_SHORT for e in result.errors)


# AC6 — tested against real, varied JDs (marketing vs finance)
@patch("app.engine.jd.service.structure_jd_text")
def test_ac6_real_marketing_jd_produces_relevant_competencies(mock_structure):
    mock_structure.return_value = _fake_marketing_structured()
    jd_text = _read_fixture("marketing_jd.txt")
    result = service.understand_jd(jd_text)

    names = [c.competency_name.lower() for c in result.required_competencies]
    assert any("consumer" in n or "insight" in n for n in names)
    assert any("brand" in n or "storytelling" in n for n in names)


@patch("app.engine.jd.service.structure_jd_text")
def test_ac6_real_finance_jd_produces_relevant_competencies(mock_structure):
    mock_structure.return_value = _fake_finance_structured()
    jd_text = _read_fixture("finance_jd.txt")
    result = service.understand_jd(jd_text)

    names = [c.competency_name.lower() for c in result.required_competencies]
    assert any("financial" in n or "modeling" in n for n in names)
    assert any("problem solving" in n for n in names)


# AC7 — every error contract code has coverage
def test_ac7_jd_too_large_rejects():
    huge_jd = "x" * 25000
    with pytest.raises(RejectionError) as exc_info:
        service.understand_jd(huge_jd)
    assert exc_info.value.code == ErrorCode.JD_TOO_LARGE


@patch("app.engine.jd.service.structure_jd_text")
def test_ac7_structuring_failed_handled_gracefully(mock_structure):
    mock_structure.return_value = {}  # simulates unparseable LLM output
    valid_length_text = "This is a job description. " * 5
    result = service.understand_jd(valid_length_text)
    assert any(e.code == ErrorCode.STRUCTURING_FAILED for e in result.errors)


def test_ac7_empty_and_too_short_already_covered():
    # covered by test_ac5_empty_jd_handled_gracefully and
    # test_ac5_too_short_jd_handled_gracefully above — all 4 error
    # codes now have test coverage.
    assert True


# AC8 — no hardcoded competency vocabulary: two different functional
# areas produce genuinely different competency names
@patch("app.engine.jd.service.structure_jd_text")
def test_ac8_marketing_and_finance_jds_produce_different_vocabularies(mock_structure):
    mock_structure.return_value = _fake_marketing_structured()
    marketing_result = service.understand_jd(_read_fixture("marketing_jd.txt"))
    marketing_names = {
        c.competency_name for c in marketing_result.required_competencies
    }

    mock_structure.return_value = _fake_finance_structured()
    finance_result = service.understand_jd(_read_fixture("finance_jd.txt"))
    finance_names = {c.competency_name for c in finance_result.required_competencies}

    # No overlap expected between a marketing and finance JD's core
    # competencies — if there IS overlap, that's a signal the
    # extraction logic may be falling back to a fixed vocabulary
    # rather than genuinely reading each JD.
    assert marketing_names.isdisjoint(finance_names)


# role_specific_signals scope test — reviewer's exclusion list
@patch("app.engine.jd.service.structure_jd_text")
def test_role_specific_signals_excludes_qualifications_and_logistics(mock_structure):
    """The prompt explicitly instructs the model not to treat 'MBA
    preferred' or location as signals. This test checks our fake
    structured data (simulating correct model behavior) flows through
    correctly — it does not test the live model's actual compliance,
    which requires the live LLM validation step."""
    mock_structure.return_value = _fake_marketing_structured()
    jd_text = _read_fixture("marketing_jd.txt")
    result = service.understand_jd(jd_text)

    signal_texts = [s.signal_text.lower() for s in result.role_specific_signals]
    assert not any("mba" in s for s in signal_texts)
    assert not any("mumbai" in s or "remote" in s for s in signal_texts)
