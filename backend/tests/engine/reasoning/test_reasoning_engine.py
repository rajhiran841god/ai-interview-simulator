"""
Tests mapped to Reasoning_Engine_Contract.md's 12 Acceptance Criteria.
Fully deterministic module — no LLM mocking needed anywhere in this suite.
"""

import copy

import pytest

from app.engine.competency_model.service import CompetencyModelService
from app.engine.competency_model.store import InMemoryCompetencyModelStore
from app.engine.competency_model.schema import CompetencySeed
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.evidence_graph.store import InMemoryEvidenceGraphStore
from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.conversation_memory.store import InMemoryConversationMemoryStore
from app.engine.logging.service import LoggingService
from app.engine.logging.store import InMemoryTraceStore
from app.engine.reasoning.service import ReasoningEngineService
from app.engine.reasoning.schema import ReasoningEngineError, ErrorCode
from app.shared.reasoning_config import (
    MIN_QUESTIONS,
    MAX_QUESTIONS,
)


@pytest.fixture
def wired_system():
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    logging_svc = LoggingService(InMemoryTraceStore())
    cmodel = CompetencyModelService(InMemoryCompetencyModelStore())
    reasoning = ReasoningEngineService(
        competency_model=cmodel, evidence_graph=eg, logging_service=logging_svc
    )
    return cm, eg, logging_svc, cmodel, reasoning


def _seed_competencies(cmodel, interview_id="int-1"):
    cmodel.initialize_competencies(
        interview_id,
        [
            CompetencySeed(competency_id="leadership", emphasis="primary"),
            CompetencySeed(competency_id="problem_solving", emphasis="primary"),
        ],
    )


def _fill_traces(logging_svc, interview_id, count):
    """Simulate N prior questions already having been asked, by
    writing N trace records directly."""
    for i in range(count):
        logging_svc.record_trace(
            interview_id,
            f"prior-q-{i}",
            "probe_deeper",
            0.5,
            "gap",
            "reason",
            "v1",
            "model",
        )


# AC1 — floor overrides high confidence
def test_ac1_min_questions_floor_overrides_high_confidence(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    cmodel.update_from_evaluation("int-1", "leadership", 0.95, False, ["ev-1"])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.95, False, ["ev-2"])
    _fill_traces(logging_svc, "int-1", MIN_QUESTIONS - 1)  # below floor

    decision = reasoning.decide_next_action("int-1")
    assert decision.decision_type == "continue"


# AC2 — ceiling overrides low confidence
def test_ac2_max_questions_ceiling_overrides_low_confidence(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    cmodel.update_from_evaluation("int-1", "leadership", 0.1, False, ["ev-1"])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.1, False, ["ev-2"])
    _fill_traces(logging_svc, "int-1", MAX_QUESTIONS)

    decision = reasoning.decide_next_action("int-1")
    assert decision.decision_type == "stop"


# AC3 — the case developers most commonly get wrong: high average, one weak competency
def test_ac3_high_average_one_weak_competency_still_continues(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    cmodel.update_from_evaluation("int-1", "leadership", 0.99, False, ["ev-1"])
    cmodel.update_from_evaluation(
        "int-1", "problem_solving", 0.30, False, ["ev-2"]
    )  # below floor
    # average = 0.645, well above threshold if checked alone, but min (0.30) is below floor
    _fill_traces(logging_svc, "int-1", MIN_QUESTIONS + 2)  # in the checked range

    decision = reasoning.decide_next_action("int-1")
    assert (
        decision.decision_type == "continue"
    )  # minimum-confidence safeguard must fire


def test_ac3_both_average_and_minimum_sufficient_stops(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    cmodel.update_from_evaluation("int-1", "leadership", 0.9, False, ["ev-1"])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.9, False, ["ev-2"])
    _fill_traces(logging_svc, "int-1", MIN_QUESTIONS + 2)

    decision = reasoning.decide_next_action("int-1")
    assert decision.decision_type == "stop"


# AC4 — target matches lowest-confidence competency
def test_ac4_target_matches_lowest_confidence(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    cmodel.update_from_evaluation("int-1", "leadership", 0.9, False, ["ev-1"])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.2, False, ["ev-2"])

    decision = reasoning.decide_next_action("int-1")
    assert decision.target_competency_id == "problem_solving"


# AC5 — challenge_inconsistency selected on real contradiction
def test_ac5_contradiction_selects_challenge_inconsistency(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)

    cm.record_turn(
        "int-1",
        "q-1",
        "Tell me about leadership.",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    turn1 = cm.record_answer(
        "int-1", "q-1", "I led a team of 5 engineers.", "2026-07-19T10:01:00Z"
    )
    ev1 = eg.add_evidence(
        "int-1", "leadership", turn1.turn_id, "I led a team of 5 engineers", "supports"
    )

    cm.record_turn(
        "int-1",
        "q-2",
        "Who made the decisions?",
        "cross_question",
        "2026-07-19T10:05:00Z",
        target_competency_id="leadership",
    )
    turn2 = cm.record_answer(
        "int-1", "q-2", "My manager made all decisions.", "2026-07-19T10:06:00Z"
    )
    eg.add_evidence(
        "int-1",
        "leadership",
        turn2.turn_id,
        "My manager made all decisions",
        "contradicts",
        contradicts_evidence_id=ev1.evidence_id,
    )

    cmodel.update_from_evaluation("int-1", "leadership", 0.5, False, [ev1.evidence_id])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.9, False, ["ev-x"])

    decision = reasoning.decide_next_action("int-1")
    assert (
        decision.target_competency_id == "leadership"
    )  # lowest confidence AND has contradiction
    assert decision.decision_strategy == "challenge_inconsistency"


# AC6 — probe_deeper for zero evidence
def test_ac6_probe_deeper_for_zero_evidence(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    # Neither competency has any evidence — both at confidence 0.0, evidence_count 0
    decision = reasoning.decide_next_action("int-1")
    assert decision.decision_strategy == "probe_deeper"


# AC7 — verify for borderline confidence
def test_ac7_verify_for_borderline_confidence(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    cmodel.update_from_evaluation(
        "int-1", "leadership", 0.7, False, ["ev-1"]
    )  # between floor and threshold
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.99, False, ["ev-2"])

    decision = reasoning.decide_next_action("int-1")
    assert decision.target_competency_id == "leadership"
    assert decision.decision_strategy == "verify"


# AC8 — question_id generated, unique, written to Logging, verified via fresh query
def test_ac8_question_id_generated_and_logged(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)

    decision1 = reasoning.decide_next_action("int-1")
    trace1 = logging_svc.get_trace("int-1", decision1.question_id)
    assert trace1 is not None
    assert trace1.decision_strategy == decision1.decision_strategy

    # Different interview, confirm a second decision gets a distinct ID
    cmodel.initialize_competencies(
        "int-2", [CompetencySeed(competency_id="leadership", emphasis="primary")]
    )
    decision2 = reasoning.decide_next_action("int-2")
    assert decision1.question_id != decision2.question_id


# AC9 — no competencies initialized raises
def test_ac9_no_competencies_raises(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    with pytest.raises(ReasoningEngineError) as exc_info:
        reasoning.decide_next_action("never-initialized-interview")
    assert exc_info.value.code == ErrorCode.NO_COMPETENCIES_INITIALIZED


# AC10 — end-to-end integration using REAL Competency Model state built through actual updates
def test_ac10_end_to_end_with_real_competency_model_state(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)

    # Build up real state through actual update_from_evaluation calls,
    # not hand-constructed CompetencyState objects.
    cmodel.update_from_evaluation("int-1", "leadership", 0.6, False, ["ev-1"])
    cmodel.update_from_evaluation("int-1", "leadership", 0.7, False, ["ev-2"])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.2, False, ["ev-3"])

    decision = reasoning.decide_next_action("int-1")
    # problem_solving (0.2) is genuinely lower than leadership's
    # real computed incremental-mean value — verify against the
    # actual state, not an assumed one.
    real_state = cmodel.get_competency_state("int-1", "problem_solving")
    assert decision.target_competency_id == "problem_solving"
    assert (
        real_state.confidence
        < cmodel.get_competency_state("int-1", "leadership").confidence
    )


# AC11 — interview isolation
def test_ac11_interview_isolation(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel, interview_id="int-1")
    cmodel.initialize_competencies(
        "int-2", [CompetencySeed(competency_id="leadership", emphasis="primary")]
    )
    cmodel.update_from_evaluation("int-1", "leadership", 0.95, False, ["ev-1"])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.95, False, ["ev-2"])

    decision_1 = reasoning.decide_next_action("int-1")
    decision_2 = reasoning.decide_next_action("int-2")
    # int-2's untouched leadership (confidence 0.0) should still
    # trigger continue/probe_deeper independent of int-1's high state
    assert decision_2.decision_strategy in (None, "probe_deeper")
    assert decision_1.question_id != decision_2.question_id


# AC12 — read-only guarantee on Competency Model and Evidence Graph
def test_ac12_read_only_on_competency_model_and_evidence_graph(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel)
    cmodel.update_from_evaluation("int-1", "leadership", 0.5, False, ["ev-1"])

    states_before = copy.deepcopy(cmodel.get_all_competency_states("int-1"))
    evidence_before = copy.deepcopy(
        eg.get_evidence_for_competency("int-1", "leadership")
    )

    reasoning.decide_next_action("int-1")

    states_after = cmodel.get_all_competency_states("int-1")
    evidence_after = eg.get_evidence_for_competency("int-1", "leadership")

    assert states_before == states_after
    assert evidence_before == evidence_after


# Determinism check — identical state produces identical decisions (excluding question_id)
def test_decision_determinism_given_identical_state(wired_system):
    cm, eg, logging_svc, cmodel, reasoning = wired_system
    _seed_competencies(cmodel, interview_id="int-1")
    cmodel.update_from_evaluation("int-1", "leadership", 0.4, False, ["ev-1"])
    cmodel.update_from_evaluation("int-1", "problem_solving", 0.9, False, ["ev-2"])

    decision = reasoning.decide_next_action("int-1")

    # Independent second system, identical state
    cm2 = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg2 = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm2
    )
    logging2 = LoggingService(InMemoryTraceStore())
    cmodel2 = CompetencyModelService(InMemoryCompetencyModelStore())
    reasoning2 = ReasoningEngineService(
        competency_model=cmodel2, evidence_graph=eg2, logging_service=logging2
    )
    _seed_competencies(cmodel2, interview_id="int-1")
    cmodel2.update_from_evaluation("int-1", "leadership", 0.4, False, ["ev-1"])
    cmodel2.update_from_evaluation("int-1", "problem_solving", 0.9, False, ["ev-2"])

    decision2 = reasoning2.decide_next_action("int-1")

    assert decision.decision_type == decision2.decision_type
    assert decision.target_competency_id == decision2.target_competency_id
    assert decision.decision_strategy == decision2.decision_strategy
    # question_id is intentionally unique, excluded from this comparison


# Threshold centralization check
def test_thresholds_imported_from_shared_config_not_duplicated():
    import inspect
    import app.engine.reasoning.stopping_policy as sp_module
    import app.engine.reasoning.strategy_policy as st_module

    sp_source = inspect.getsource(sp_module)
    st_source = inspect.getsource(st_module)
    assert "from app.shared.reasoning_config import" in sp_source
    assert "from app.shared.reasoning_config import" in st_source
    # No hardcoded numeric threshold duplicates like "0.85" or "0.60" inline
    assert "0.85" not in sp_source
    assert "0.60" not in sp_source or "STOP_CONFIDENCE_FLOOR" in st_source
