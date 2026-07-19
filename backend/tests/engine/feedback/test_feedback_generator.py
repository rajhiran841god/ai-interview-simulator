"""
Tests mapped to Feedback_Generator_Contract.md's 10 Acceptance
Criteria. AC1 is the merge-blocking criterion — verified structurally
against the schema definition itself, not example output.
"""

from unittest.mock import patch

import pytest

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.conversation_memory.store import InMemoryConversationMemoryStore
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.evidence_graph.store import InMemoryEvidenceGraphStore
from app.engine.logging.service import LoggingService
from app.engine.logging.store import InMemoryTraceStore
from app.engine.competency_model.service import CompetencyModelService
from app.engine.competency_model.store import InMemoryCompetencyModelStore
from app.engine.competency_model.schema import CompetencySeed
from app.engine.evaluation.service import EvaluationEngineService
from app.engine.feedback.service import FeedbackGeneratorService
from app.engine.feedback.schema import (
    FeedbackGeneratorError,
    ErrorCode,
    InterviewFeedbackReport,
)


@pytest.fixture
def wired_system():
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    cmodel = CompetencyModelService(InMemoryCompetencyModelStore())
    fg = FeedbackGeneratorService(
        competency_model=cmodel, evidence_graph=eg, conversation_memory=cm
    )
    return cm, eg, cmodel, fg


def _seed_with_evidence(cm, eg, cmodel, interview_id="int-1"):
    cmodel.initialize_competencies(
        interview_id,
        [
            CompetencySeed(competency_id="leadership", emphasis="primary"),
            CompetencySeed(competency_id="communication", emphasis="secondary"),
        ],
    )
    cm.record_turn(
        interview_id,
        "q-1",
        "Tell me about your leadership experience.",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    turn = cm.record_answer(
        interview_id,
        "q-1",
        "I led a team of 5 engineers on a critical launch.",
        "2026-07-19T10:01:00Z",
    )
    evidence = eg.add_evidence(
        interview_id,
        "leadership",
        turn.turn_id,
        "I led a team of 5 engineers",
        "supports",
    )
    cmodel.update_from_evaluation(
        interview_id, "leadership", 0.8, False, [evidence.evidence_id]
    )
    return evidence


# AC1 — THE merge-blocking criterion: structural schema check
def test_ac1_no_confidence_field_in_schema():
    from app.engine.feedback.schema import CompetencyFeedback

    for model in (CompetencyFeedback, InterviewFeedbackReport):
        for field_name, field_info in model.model_fields.items():
            annotation = field_info.annotation
            # No float field anywhere, and no field name suggesting a
            # score/confidence/percentage.
            assert (
                annotation is not float
            ), f"{model.__name__}.{field_name} is a float — possible confidence leak"
            forbidden_names = {"confidence", "score", "percentage", "rating", "grade"}
            assert not any(
                f in field_name.lower() for f in forbidden_names
            ), f"{model.__name__}.{field_name} name suggests a confidence-derived value"


# AC2 — real supporting evidence produces grounded (not generic) feedback
def test_ac2_grounded_feedback_for_real_evidence(wired_system):
    cm, eg, cmodel, fg = wired_system
    _seed_with_evidence(cm, eg, cmodel)
    cmodel.update_from_evaluation(
        "int-1", "communication", 0.5, False, []
    )  # no-op update, still zero evidence

    def fake_generation(plan):
        if plan.competency_id == "leadership":
            return {
                "summary_text": "You demonstrated clear leadership by describing how you led a team of 5 engineers through a critical launch.",
                "cited_evidence_ids": [plan.supporting_items[0].evidence_id],
            }
        return {
            "summary_text": "No evidence was discussed for this area.",
            "cited_evidence_ids": [],
        }

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        side_effect=fake_generation,
    ):
        report = fg.generate_feedback_report("int-1")

    leadership_fb = next(
        f for f in report.competency_feedback if f.competency_id == "leadership"
    )
    assert (
        "team of 5" in leadership_fb.summary_text
        or "led" in leadership_fb.summary_text.lower()
    )
    assert len(leadership_fb.supporting_evidence_ids) == 1


# AC3 — zero evidence produces honest insufficient_evidence
def test_ac3_zero_evidence_produces_honest_gap(wired_system):
    cm, eg, cmodel, fg = wired_system
    cmodel.initialize_competencies(
        "int-1", [CompetencySeed(competency_id="problem_solving", emphasis="primary")]
    )

    def fake_generation(plan):
        assert plan.insufficient_evidence is True
        return {
            "summary_text": "There wasn't enough discussion of problem solving to provide meaningful feedback.",
            "cited_evidence_ids": [],
        }

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        side_effect=fake_generation,
    ):
        report = fg.generate_feedback_report("int-1")

    fb = report.competency_feedback[0]
    assert fb.insufficient_evidence is True
    assert (
        "not enough" in fb.summary_text.lower()
        or "wasn't enough" in fb.summary_text.lower()
    )
    assert fb.supporting_evidence_ids == []


# AC4 — contradictory evidence flagged and addressed
def test_ac4_contradiction_flagged(wired_system):
    cm, eg, cmodel, fg = wired_system
    evidence1 = _seed_with_evidence(cm, eg, cmodel)

    cm.record_turn(
        "int-1",
        "q-2",
        "Who made the final call?",
        "cross_question",
        "2026-07-19T10:05:00Z",
        target_competency_id="leadership",
    )
    turn2 = cm.record_answer(
        "int-1", "q-2", "My manager made all the decisions.", "2026-07-19T10:06:00Z"
    )
    evidence2 = eg.add_evidence(
        "int-1",
        "leadership",
        turn2.turn_id,
        "My manager made all the decisions",
        "contradicts",
        contradicts_evidence_id=evidence1.evidence_id,
    )
    cmodel.update_from_evaluation(
        "int-1", "leadership", 0.4, True, [evidence2.evidence_id]
    )

    def fake_generation(plan):
        if plan.competency_id == "leadership":
            assert plan.has_unresolved_contradiction is True
            return {
                "summary_text": "Your answers gave differing accounts of who made the final decision — it would help to clarify this.",
                "cited_evidence_ids": [evidence1.evidence_id, evidence2.evidence_id],
            }
        # communication has zero evidence in this test — different path, not part of this assertion
        return {"summary_text": "No evidence collected.", "cited_evidence_ids": []}

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        side_effect=fake_generation,
    ):
        report = fg.generate_feedback_report("int-1")

    fb = next(f for f in report.competency_feedback if f.competency_id == "leadership")
    assert fb.has_unresolved_contradiction is True
    assert (
        "differing accounts" in fb.summary_text or "clarify" in fb.summary_text.lower()
    )
    assert evidence2.evidence_id in fb.contradictory_evidence_ids


# AC5 — fabricated evidence_id rejected
def test_ac5_fabricated_evidence_id_rejected(wired_system):
    cm, eg, cmodel, fg = wired_system
    real_evidence = _seed_with_evidence(cm, eg, cmodel)

    def fake_generation_with_hallucination(plan):
        return {
            "summary_text": "Good leadership example.",
            "cited_evidence_ids": [
                real_evidence.evidence_id,
                "fabricated-id-that-does-not-exist",
            ],
        }

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        side_effect=fake_generation_with_hallucination,
    ):
        report = fg.generate_feedback_report("int-1")

    fb = next(f for f in report.competency_feedback if f.competency_id == "leadership")
    assert real_evidence.evidence_id in fb.supporting_evidence_ids
    assert "fabricated-id-that-does-not-exist" not in fb.supporting_evidence_ids
    assert "fabricated-id-that-does-not-exist" not in fb.contradictory_evidence_ids


# AC6 — one competency's failure doesn't abort the whole report
def test_ac6_partial_failure_does_not_abort_report(wired_system):
    cm, eg, cmodel, fg = wired_system
    _seed_with_evidence(cm, eg, cmodel)  # leadership has evidence
    # communication has zero evidence, seeded via initialize_competencies in _seed_with_evidence

    def fake_generation(plan):
        if plan.competency_id == "leadership":
            raise Exception("simulated LLM failure for this competency")
        return {"summary_text": "No evidence collected.", "cited_evidence_ids": []}

    def wrapped(plan):
        try:
            return fake_generation(plan)
        except Exception:
            return (
                {}
            )  # simulates GENERATION_FAILED -> empty dict, same as real call_feedback_generation's failure mode

    with patch(
        "app.engine.feedback.service.call_feedback_generation", side_effect=wrapped
    ):
        report = fg.generate_feedback_report("int-1")

    assert len(report.competency_feedback) == 2  # both competencies present
    leadership_fb = next(
        f for f in report.competency_feedback if f.competency_id == "leadership"
    )
    communication_fb = next(
        f for f in report.competency_feedback if f.competency_id == "communication"
    )
    assert len(leadership_fb.summary_text) > 0  # fallback text, not empty
    assert len(communication_fb.summary_text) > 0


# AC7 — no competencies initialized raises
def test_ac7_no_competencies_raises(wired_system):
    cm, eg, cmodel, fg = wired_system
    with pytest.raises(FeedbackGeneratorError) as exc_info:
        fg.generate_feedback_report("never-initialized-interview")
    assert exc_info.value.code == ErrorCode.NO_COMPETENCIES_INITIALIZED


# AC8 — deterministic ordering (primary before secondary, then alphabetical)
def test_ac8_deterministic_ordering(wired_system):
    cm, eg, cmodel, fg = wired_system
    cmodel.initialize_competencies(
        "int-1",
        [
            CompetencySeed(competency_id="zeta_skill", emphasis="secondary"),
            CompetencySeed(competency_id="alpha_skill", emphasis="primary"),
            CompetencySeed(competency_id="beta_skill", emphasis="primary"),
        ],
    )

    def fake_generation(plan):
        return {"summary_text": "No evidence collected.", "cited_evidence_ids": []}

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        side_effect=fake_generation,
    ):
        report1 = fg.generate_feedback_report("int-1")
        report2 = fg.generate_feedback_report("int-1")

    ids_order_1 = [f.competency_id for f in report1.competency_feedback]
    ids_order_2 = [f.competency_id for f in report2.competency_feedback]
    assert ids_order_1 == [
        "alpha_skill",
        "beta_skill",
        "zeta_skill",
    ]  # primary alpha, primary beta, then secondary
    assert ids_order_1 == ids_order_2  # deterministic across calls


# AC9 — end-to-end integration through the REAL multi-module pipeline
def test_ac9_end_to_end_real_pipeline():
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    logging_svc = LoggingService(InMemoryTraceStore())
    cmodel = CompetencyModelService(InMemoryCompetencyModelStore())
    ee = EvaluationEngineService(evidence_graph=eg, logging_service=logging_svc)
    fg = FeedbackGeneratorService(
        competency_model=cmodel, evidence_graph=eg, conversation_memory=cm
    )

    cmodel.initialize_competencies(
        "int-1", [CompetencySeed(competency_id="leadership", emphasis="primary")]
    )

    cm.record_turn(
        "int-1",
        "q-1",
        "Tell me about your leadership experience.",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    turn = cm.record_answer(
        "int-1",
        "q-1",
        "I led a team of 5 engineers on a launch.",
        "2026-07-19T10:01:00Z",
    )
    logging_svc.record_trace(
        "int-1",
        "q-1",
        "probe_deeper",
        0.3,
        "No evidence yet",
        "test",
        "v1",
        "model",
        target_competency_id="leadership",
    )

    fake_eval_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I led a team of 5 engineers"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.8,
        "reasoning_summary": "Strong example.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=fake_eval_response
    ):
        eval_result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "No evidence yet",
            "I led a team of 5 engineers on a launch.",
            target_competency_id="leadership",
        )

    cmodel.update_from_evaluation(
        "int-1",
        "leadership",
        eval_result.confidence_contribution,
        eval_result.contradiction_detected,
        eval_result.evidence_ids_created,
    )

    def fake_feedback_generation(plan):
        return {
            "summary_text": f"Strong evidence of leadership: {plan.supporting_items[0].evidence_excerpt}",
            "cited_evidence_ids": [plan.supporting_items[0].evidence_id],
        }

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        side_effect=fake_feedback_generation,
    ):
        report = fg.generate_feedback_report("int-1")

    assert len(report.competency_feedback) == 1
    fb = report.competency_feedback[0]
    assert fb.competency_id == "leadership"
    assert len(fb.supporting_evidence_ids) == 1
    assert fb.supporting_evidence_ids[0] in eval_result.evidence_ids_created


# AC10 — interview isolation
def test_ac10_interview_isolation(wired_system):
    cm, eg, cmodel, fg = wired_system
    _seed_with_evidence(cm, eg, cmodel, interview_id="int-1")
    cmodel.initialize_competencies(
        "int-2", [CompetencySeed(competency_id="leadership", emphasis="primary")]
    )

    def fake_generation(plan):
        return {"summary_text": "No evidence collected.", "cited_evidence_ids": []}

    with patch(
        "app.engine.feedback.service.call_feedback_generation",
        side_effect=fake_generation,
    ):
        report_2 = fg.generate_feedback_report("int-2")

    fb = report_2.competency_feedback[0]
    assert (
        fb.insufficient_evidence is True
    )  # int-2 genuinely has no evidence, untouched by int-1's data


# Provider isolation check
def test_provider_isolation_only_generator_touches_sdk():
    import inspect
    import app.engine.feedback.service as svc
    import app.engine.feedback.evidence_collector as ec
    import app.engine.feedback.feedback_planner as fp
    import app.engine.feedback.evidence_verifier as ev
    import app.engine.feedback.fallback_formatter as ff
    import app.engine.feedback.generator as gen

    for module in (svc, ec, fp, ev, ff):
        source = inspect.getsource(module)
        assert "import anthropic" not in source.lower()

    gen_source = inspect.getsource(gen)
    assert "from app.core.provider_adapter import get_provider" in gen_source
