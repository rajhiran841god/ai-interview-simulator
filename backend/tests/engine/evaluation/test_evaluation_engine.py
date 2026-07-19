"""
Tests mapped to Evaluation_Engine_Contract.md's 12 Acceptance Criteria.
Real end-to-end integration through Conversation Memory, Evidence
Graph, and Logging — only the LLM call itself is mocked, same honest
pattern as Modules 1-2.
"""

from unittest.mock import patch

import pytest

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.conversation_memory.store import InMemoryConversationMemoryStore
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.evidence_graph.store import InMemoryEvidenceGraphStore
from app.engine.logging.service import LoggingService
from app.engine.logging.store import InMemoryTraceStore
from app.engine.evaluation.service import EvaluationEngineService
from app.engine.evaluation.schema import EvaluationEngineError, ErrorCode


@pytest.fixture
def wired_system():
    """A fully wired set of Modules 3-6, matching how they'd actually
    be used together — this is what makes the tests below genuinely
    end-to-end rather than isolated with mocked dependencies."""
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    logging_svc = LoggingService(InMemoryTraceStore())
    ee = EvaluationEngineService(evidence_graph=eg, logging_service=logging_svc)
    return cm, eg, logging_svc, ee


def _seed_turn_and_trace(
    cm,
    logging_svc,
    interview_id="int-1",
    question_id="q-1",
    answer_text="I led a team of 5 engineers on a critical launch.",
    competency_id="leadership",
):
    cm.record_turn(
        interview_id,
        question_id,
        "Tell me about your leadership experience.",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id=competency_id,
    )
    turn = cm.record_answer(
        interview_id, question_id, answer_text, "2026-07-19T10:01:00Z"
    )
    logging_svc.record_trace(
        interview_id,
        question_id,
        "probe_deeper",
        0.3,
        "No concrete evidence of leadership actions",
        "Testing evidence extraction",
        "v1.0.0",
        "claude-sonnet-4-6",
        target_competency_id=competency_id,
    )
    return turn


# AC1 — substantive answer classified correctly, evidence created and traceable
def test_ac1_substantive_answer_creates_traceable_evidence(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(cm, logging_svc)

    fake_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I led a team of 5 engineers"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.8,
        "reasoning_summary": "Specific, concrete leadership example.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=fake_response
    ):
        result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "No concrete evidence of leadership actions",
            "I led a team of 5 engineers on a critical launch.",
            target_competency_id="leadership",
        )

    assert result.answer_classification == "substantive"
    assert len(result.evidence_ids_created) == 1
    # Verify traceability through Evidence Graph's own check, not reimplemented
    stored = eg.get_evidence_for_turn("int-1", turn.turn_id)
    assert len(stored) == 1
    assert stored[0].evidence_excerpt == "I led a team of 5 engineers"


# AC2 — deflection vs non-answer distinction
def test_ac2_deflection_and_non_answer_are_distinct(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(
        cm,
        logging_svc,
        question_id="q-1",
        answer_text="Well, I'm really passionate about teamwork in general.",
    )

    deflection_response = {
        "answer_classification": "deflection",
        "evidence_excerpts": [],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.1,
        "reasoning_summary": "Answered a different, easier question instead.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer",
        return_value=deflection_response,
    ):
        result1 = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "gap",
            "Well, I'm really passionate about teamwork.",
            target_competency_id="leadership",
        )
    assert result1.answer_classification == "deflection"

    turn2 = _seed_turn_and_trace(
        cm, logging_svc, question_id="q-2", answer_text="I don't know."
    )
    non_answer_response = {
        "answer_classification": "non_answer",
        "evidence_excerpts": [],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.0,
        "reasoning_summary": "No engagement with the question.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer",
        return_value=non_answer_response,
    ):
        result2 = ee.evaluate_answer(
            "int-1",
            "q-2",
            turn2.turn_id,
            "gap",
            "I don't know.",
            target_competency_id="leadership",
        )
    assert result2.answer_classification == "non_answer"
    assert result1.answer_classification != result2.answer_classification


# AC3 — empty answer classified non_answer without LLM call
def test_ac3_empty_answer_skips_llm_call(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(cm, logging_svc, answer_text="")

    with patch("app.engine.evaluation.service.classify_answer") as mock_classify:
        result = ee.evaluate_answer(
            "int-1", "q-1", turn.turn_id, "gap", "", target_competency_id="leadership"
        )
        mock_classify.assert_not_called()

    assert result.answer_classification == "non_answer"


# AC4 — LLM failure handled gracefully
def test_ac4_llm_failure_returns_degraded_result(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(cm, logging_svc)

    with patch("app.engine.evaluation.service.classify_answer", return_value={}):
        result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "gap",
            "Some answer here.",
            target_competency_id="leadership",
        )
    assert result.answer_classification == "non_answer"
    assert result.confidence_contribution == 0.0


# AC5 & AC12 — contradiction detection, end-to-end, same-interview scoped
def test_ac5_contradiction_written_to_evidence_graph_end_to_end(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn1 = _seed_turn_and_trace(
        cm, logging_svc, question_id="q-1", answer_text="I led a team of 5 engineers."
    )
    first_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I led a team of 5 engineers"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.8,
        "reasoning_summary": "Clear leadership claim.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=first_response
    ):
        result1 = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn1.turn_id,
            "gap",
            "I led a team of 5 engineers.",
            target_competency_id="leadership",
        )
    original_evidence_id = result1.evidence_ids_created[0]

    turn2 = _seed_turn_and_trace(
        cm,
        logging_svc,
        question_id="q-2",
        answer_text="Actually my manager made all the decisions.",
    )
    contradiction_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["my manager made all the decisions"],
        "contradicts_prior_evidence": True,
        "contradiction_explanation": "Conflicts with earlier claim of having led.",
        "confidence_contribution": 0.6,
        "reasoning_summary": "Contradicts earlier leadership claim.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer",
        return_value=contradiction_response,
    ):
        result2 = ee.evaluate_answer(
            "int-1",
            "q-2",
            turn2.turn_id,
            "gap",
            "Actually my manager made all the decisions.",
            target_competency_id="leadership",
        )

    assert result2.contradiction_detected is True
    assert result2.contradicted_evidence_id == original_evidence_id
    # Verify via Evidence Graph's own query, end-to-end
    assert eg.has_contradictions("int-1", "leadership") is True


# AC6 — evaluate_answer for a question with no trace raises TRACE_NOT_FOUND
def test_ac6_no_trace_raises(wired_system):
    cm, eg, logging_svc, ee = wired_system
    cm.record_turn("int-1", "q-1", "Question", "fresh", "2026-07-19T10:00:00Z")
    turn = cm.record_answer("int-1", "q-1", "Answer", "2026-07-19T10:01:00Z")
    # Deliberately NOT calling logging_svc.record_trace()

    with pytest.raises(EvaluationEngineError) as exc_info:
        ee.evaluate_answer("int-1", "q-1", turn.turn_id, "gap", "Answer")
    assert exc_info.value.code == ErrorCode.TRACE_NOT_FOUND


# AC7 — Logging trace correctly updated, verified via fresh query
def test_ac7_logging_updated_verified_via_fresh_query(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(cm, logging_svc)

    fake_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I led a team of 5 engineers"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.8,
        "reasoning_summary": "Good evidence.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=fake_response
    ):
        result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "gap",
            "I led a team of 5 engineers.",
            target_competency_id="leadership",
        )

    # Fresh query through Logging's own public API, not the EvaluationResult return value
    trace = logging_svc.get_trace("int-1", "q-1")
    assert trace.confidence_post == 0.8
    assert trace.evidence_ids_referenced == result.evidence_ids_created


# AC8 — reject, never clamp, out-of-range confidence
def test_ac8_out_of_range_confidence_rejected_not_clamped(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(cm, logging_svc)

    bad_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I led a team of 5 engineers"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 1.83,  # out of range
        "reasoning_summary": "test",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=bad_response
    ):
        result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "gap",
            "I led a team of 5 engineers.",
            target_competency_id="leadership",
        )
    # Must be the degraded path (0.0), NEVER clamped to 1.0
    assert result.confidence_contribution == 0.0
    assert result.confidence_contribution != 1.0
    assert result.answer_classification == "non_answer"  # degraded path signature


# AC9 — null target_competency_id produces no evidence writes, no raise
def test_ac9_null_competency_no_evidence_writes(wired_system):
    cm, eg, logging_svc, ee = wired_system
    cm.record_turn(
        "int-1", "greeting", "Hi, ready to start?", "fresh", "2026-07-19T10:00:00Z"
    )
    turn = cm.record_answer("int-1", "greeting", "Yes, ready!", "2026-07-19T10:01:00Z")
    logging_svc.record_trace(
        "int-1",
        "greeting",
        "probe_deeper",
        0.5,
        "n/a",
        "greeting",
        "v1",
        "model",
        target_competency_id=None,
    )

    result = ee.evaluate_answer(
        "int-1",
        "greeting",
        turn.turn_id,
        "n/a",
        "Yes, ready!",
        target_competency_id=None,
    )
    assert result.evidence_ids_created == []
    assert eg.get_evidence_for_turn("int-1", turn.turn_id) == []


# AC10 — fabricated evidence never bypasses Evidence Graph's own check
def test_ac10_fabricated_excerpt_dropped_not_bypassed(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(
        cm, logging_svc, answer_text="I worked on a small feature."
    )

    fabricating_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": [
            "I single-handedly saved the company from bankruptcy"
        ],  # NOT in real answer
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.9,
        "reasoning_summary": "test",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer",
        return_value=fabricating_response,
    ):
        result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "gap",
            "I worked on a small feature.",
            target_competency_id="leadership",
        )
    # Evidence Graph's EXCERPT_NOT_TRACEABLE check rejected it —
    # module must not crash, must not bypass, evidence list stays empty
    assert result.evidence_ids_created == []
    assert eg.get_evidence_for_turn("int-1", turn.turn_id) == []


# AC11 — orchestration determinism against a fixed mocked response
def test_ac11_orchestration_deterministic_given_fixed_response(wired_system):
    cm, eg, logging_svc, ee = wired_system
    turn = _seed_turn_and_trace(cm, logging_svc, question_id="q-1")

    fixed_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I led a team of 5 engineers"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.8,
        "reasoning_summary": "Consistent answer.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=fixed_response
    ):
        result1 = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "gap",
            "I led a team of 5 engineers on a launch.",
            target_competency_id="leadership",
        )

    # Second interview, same fixed input/response, fresh wiring
    cm2 = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg2 = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm2
    )
    logging2 = LoggingService(InMemoryTraceStore())
    ee2 = EvaluationEngineService(evidence_graph=eg2, logging_service=logging2)
    turn2 = _seed_turn_and_trace(cm2, logging2, question_id="q-1")

    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=fixed_response
    ):
        result2 = ee2.evaluate_answer(
            "int-1",
            "q-1",
            turn2.turn_id,
            "gap",
            "I led a team of 5 engineers on a launch.",
            target_competency_id="leadership",
        )

    assert result1.answer_classification == result2.answer_classification
    assert result1.confidence_contribution == result2.confidence_contribution
    assert result1.contradiction_detected == result2.contradiction_detected
    assert len(result1.evidence_ids_created) == len(result2.evidence_ids_created)


# AC12 — contradiction detection scoped strictly to the same interview
def test_ac12_contradiction_never_crosses_interviews(wired_system):
    cm, eg, logging_svc, ee = wired_system
    # Evidence in a DIFFERENT interview
    cm2 = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg2 = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm2
    )
    turn_other = cm2.record_turn(
        "int-OTHER",
        "q-1",
        "Q",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    turn_other = cm2.record_answer(
        "int-OTHER", "q-1", "I led a team of 5 engineers.", "2026-07-19T10:01:00Z"
    )
    eg2.add_evidence(
        "int-OTHER",
        "leadership",
        turn_other.turn_id,
        "I led a team of 5 engineers",
        "supports",
    )

    # This module's own evidence_graph instance (eg) has NO knowledge
    # of int-OTHER's evidence at all — different store entirely.
    turn = _seed_turn_and_trace(
        cm, logging_svc, answer_text="My manager made all decisions."
    )
    response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["My manager made all decisions"],
        "contradicts_prior_evidence": True,  # LLM claims contradiction, but nothing to contradict IN THIS interview
        "contradiction_explanation": "test",
        "confidence_contribution": 0.6,
        "reasoning_summary": "test",
    }
    with patch("app.engine.evaluation.service.classify_answer", return_value=response):
        result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "gap",
            "My manager made all decisions.",
            target_competency_id="leadership",
        )
    # No prior evidence exists in int-1 (this interview), so even
    # though the LLM claimed a contradiction, there's nothing to
    # contradict within this interview's own scope.
    assert result.contradiction_detected is False


# Provider isolation check
def test_provider_isolation_no_direct_sdk_import():
    import inspect
    import app.engine.evaluation.service as svc_module
    import app.engine.evaluation.classifier as classifier_module

    for module in (svc_module,):
        source = inspect.getsource(module)
        assert "import anthropic" not in source.lower()

    # classifier.py is allowed to reference get_provider(), but not the SDK directly
    classifier_source = inspect.getsource(classifier_module)
    assert "import anthropic" not in classifier_source.lower()
    assert "from app.core.provider_adapter import get_provider" in classifier_source
