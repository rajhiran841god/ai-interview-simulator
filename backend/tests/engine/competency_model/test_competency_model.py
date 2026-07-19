"""
Tests mapped to Competency_Model_Contract.md's 12 Acceptance Criteria.

Per reviewer's explicit warning: float comparisons use pytest.approx
(tolerance-based), not direct equality, since the incremental-mean
formula involves division that may not be exactly representable.
"""

from unittest.mock import patch

import pytest

from app.engine.competency_model.service import CompetencyModelService
from app.engine.competency_model.store import InMemoryCompetencyModelStore
from app.engine.competency_model.schema import (
    CompetencySeed,
    CompetencyModelError,
    ErrorCode,
)
from app.shared.reasoning_config import CONTRADICTION_PENALTY


@pytest.fixture
def service():
    return CompetencyModelService(InMemoryCompetencyModelStore())


def _seed(service, interview_id="int-1"):
    service.initialize_competencies(
        interview_id,
        [
            CompetencySeed(competency_id="leadership", emphasis="primary"),
            CompetencySeed(competency_id="problem_solving", emphasis="primary"),
            CompetencySeed(competency_id="communication", emphasis="secondary"),
        ],
    )


# AC1 — initial state
def test_ac1_initial_state(service):
    _seed(service)
    state = service.get_competency_state("int-1", "leadership")
    assert state.evidence_count == 0
    assert state.confidence == 0.0
    assert state.positive_evidence == []
    assert state.contradictory_evidence == []


# AC2 — first update sets confidence exactly to the contribution
def test_ac2_first_update_equals_contribution(service):
    _seed(service)
    state = service.update_from_evaluation(
        "int-1",
        "leadership",
        confidence_contribution=0.8,
        contradiction_detected=False,
        evidence_ids_created=["ev-1"],
    )
    # incremental mean with old=0.0, evidence_count=1:
    # 0.0 + (0.8 - 0.0) / 1 = 0.8
    assert state.confidence == pytest.approx(0.8, abs=1e-9)


# AC3 — second update moves toward new value without overwriting
def test_ac3_second_update_correct_incremental_mean(service):
    _seed(service)
    service.update_from_evaluation(
        "int-1",
        "leadership",
        confidence_contribution=0.8,
        contradiction_detected=False,
        evidence_ids_created=["ev-1"],
    )
    state = service.update_from_evaluation(
        "int-1",
        "leadership",
        confidence_contribution=0.4,
        contradiction_detected=False,
        evidence_ids_created=["ev-2"],
    )
    # old=0.8, evidence_count now 2: 0.8 + (0.4 - 0.8) / 2 = 0.8 - 0.2 = 0.6
    expected = 0.8 + (0.4 - 0.8) / 2
    assert state.confidence == pytest.approx(expected, abs=1e-9)
    assert state.confidence != 0.4  # not overwritten
    assert state.confidence != 0.8  # not unchanged


# AC4 — contradiction penalty, clamped at 0.0
def test_ac4_contradiction_penalty_applied(service):
    _seed(service)
    service.update_from_evaluation(
        "int-1",
        "leadership",
        confidence_contribution=0.5,
        contradiction_detected=False,
        evidence_ids_created=["ev-1"],
    )
    state = service.update_from_evaluation(
        "int-1",
        "leadership",
        confidence_contribution=0.9,  # irrelevant on contradiction path
        contradiction_detected=True,
        evidence_ids_created=["ev-2"],
    )
    expected = max(0.0, 0.5 - CONTRADICTION_PENALTY)
    assert state.confidence == pytest.approx(expected, abs=1e-9)


def test_ac4_contradiction_penalty_floors_at_zero(service):
    _seed(service)
    # confidence starts at 0.0, contradiction should not go negative
    state = service.update_from_evaluation(
        "int-1",
        "leadership",
        confidence_contribution=0.5,
        contradiction_detected=True,
        evidence_ids_created=["ev-1"],
    )
    assert state.confidence == pytest.approx(0.0, abs=1e-9)
    assert state.confidence >= 0.0


# AC5 — evidence routed to correct list
def test_ac5_evidence_routing(service):
    _seed(service)
    service.update_from_evaluation(
        "int-1",
        "leadership",
        0.8,
        contradiction_detected=False,
        evidence_ids_created=["ev-1"],
    )
    state = service.update_from_evaluation(
        "int-1",
        "leadership",
        0.5,
        contradiction_detected=True,
        evidence_ids_created=["ev-2"],
    )
    assert "ev-1" in state.positive_evidence
    assert "ev-1" not in state.contradictory_evidence
    assert "ev-2" in state.contradictory_evidence
    assert "ev-2" not in state.positive_evidence


# AC6 — uninitialized competency rejected
def test_ac6_uninitialized_competency_rejected(service):
    _seed(service)
    with pytest.raises(CompetencyModelError) as exc_info:
        service.update_from_evaluation(
            "int-1", "nonexistent_competency", 0.5, False, ["ev-1"]
        )
    assert exc_info.value.code == ErrorCode.COMPETENCY_NOT_INITIALIZED


# AC7 — duplicate initialization rejected
def test_ac7_duplicate_initialization_rejected(service):
    _seed(service)
    with pytest.raises(CompetencyModelError) as exc_info:
        _seed(service)
    assert exc_info.value.code == ErrorCode.DUPLICATE_INITIALIZATION


# AC8 — out-of-range confidence rejected, not clamped
def test_ac8_out_of_range_confidence_rejected(service):
    _seed(service)
    with pytest.raises(CompetencyModelError) as exc_info:
        service.update_from_evaluation("int-1", "leadership", 1.5, False, ["ev-1"])
    assert exc_info.value.code == ErrorCode.CONFIDENCE_CONTRIBUTION_OUT_OF_RANGE

    # confirm nothing was silently written
    state = service.get_competency_state("int-1", "leadership")
    assert state.confidence == 0.0
    assert state.evidence_count == 0


# AC9 — lowest confidence identification
def test_ac9_lowest_confidence_competency(service):
    _seed(service)
    service.update_from_evaluation("int-1", "leadership", 0.9, False, ["ev-1"])
    service.update_from_evaluation("int-1", "problem_solving", 0.3, False, ["ev-2"])
    service.update_from_evaluation("int-1", "communication", 0.6, False, ["ev-3"])

    lowest = service.get_lowest_confidence_competency("int-1")
    assert lowest == "problem_solving"


# AC10 — None for uninitialized interview
def test_ac10_lowest_confidence_none_when_uninitialized(service):
    result = service.get_lowest_confidence_competency("nonexistent-interview")
    assert result is None


# AC11 — interview isolation
def test_ac11_interview_isolation(service):
    _seed(service, interview_id="int-1")
    service.initialize_competencies(
        "int-2", [CompetencySeed(competency_id="leadership", emphasis="primary")]
    )
    service.update_from_evaluation("int-1", "leadership", 0.9, False, ["ev-1"])

    state_1 = service.get_competency_state("int-1", "leadership")
    state_2 = service.get_competency_state("int-2", "leadership")
    assert state_1.confidence == pytest.approx(0.9, abs=1e-9)
    assert state_2.confidence == pytest.approx(0.0, abs=1e-9)  # untouched


# AC12 — end-to-end integration using a REAL EvaluationResult from Module 6
def test_ac12_end_to_end_integration_with_real_evaluation_engine():
    from app.engine.conversation_memory.service import ConversationMemoryService
    from app.engine.conversation_memory.store import InMemoryConversationMemoryStore
    from app.engine.evidence_graph.service import EvidenceGraphService
    from app.engine.evidence_graph.store import InMemoryEvidenceGraphStore
    from app.engine.logging.service import LoggingService
    from app.engine.logging.store import InMemoryTraceStore
    from app.engine.evaluation.service import EvaluationEngineService

    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    logging_svc = LoggingService(InMemoryTraceStore())
    ee = EvaluationEngineService(evidence_graph=eg, logging_service=logging_svc)
    cmodel = CompetencyModelService(InMemoryCompetencyModelStore())

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
        "No leadership evidence yet",
        "Testing",
        "v1",
        "model",
        target_competency_id="leadership",
    )

    fake_llm_response = {
        "answer_classification": "substantive",
        "evidence_excerpts": ["I led a team of 5 engineers"],
        "contradicts_prior_evidence": False,
        "contradiction_explanation": None,
        "confidence_contribution": 0.75,
        "reasoning_summary": "Concrete leadership example.",
    }
    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=fake_llm_response
    ):
        # This is a REAL EvaluationResult, not a hand-constructed mock
        evaluation_result = ee.evaluate_answer(
            "int-1",
            "q-1",
            turn.turn_id,
            "No leadership evidence yet",
            "I led a team of 5 engineers on a launch.",
            target_competency_id="leadership",
        )

    # Feed the real result directly into Competency Model
    state = cmodel.update_from_evaluation(
        "int-1",
        "leadership",
        confidence_contribution=evaluation_result.confidence_contribution,
        contradiction_detected=evaluation_result.contradiction_detected,
        evidence_ids_created=evaluation_result.evidence_ids_created,
    )

    assert state.confidence == pytest.approx(0.75, abs=1e-9)
    assert state.evidence_count == 1
    assert len(state.positive_evidence) == 1
    assert state.positive_evidence[0] in evaluation_result.evidence_ids_created


# Configuration check
def test_contradiction_penalty_is_configurable_not_hardcoded():
    import app.engine.competency_model.store as store_module
    import inspect

    source = inspect.getsource(store_module)
    assert "from app.shared.reasoning_config import CONTRADICTION_PENALTY" in source
    assert "CONTRADICTION_PENALTY = 0.3" not in source  # not redefined locally
