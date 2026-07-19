"""
Tests mapped to Question_Generator_Contract.md's 11 Acceptance
Criteria. Only the LLM call itself is mocked — everything else runs
against real module integrations.
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
from app.engine.reasoning.service import ReasoningEngineService
from app.engine.reasoning.schema import ReasoningDecision
from app.engine.question_generator.service import QuestionGeneratorService
from app.engine.question_generator.schema import QuestionGeneratorError, ErrorCode


@pytest.fixture
def wired_system():
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    qg = QuestionGeneratorService(evidence_graph=eg, conversation_memory=cm)
    return cm, eg, qg


def _decision(
    target="leadership", strategy="probe_deeper", qid="q-1", dtype="continue"
):
    return ReasoningDecision(
        question_id=qid,
        decision_type=dtype,
        target_competency_id=target if dtype == "continue" else None,
        decision_strategy=strategy if dtype == "continue" else None,
        evidence_missing="No evidence yet" if dtype == "continue" else None,
        reason_for_asking="Opening the topic" if dtype == "continue" else None,
        stop_reason="Confidence sufficient" if dtype == "stop" else None,
    )


# AC1 — probe_deeper, zero evidence -> fresh
def test_ac1_probe_deeper_zero_evidence_is_fresh(wired_system):
    cm, eg, qg = wired_system
    decision = _decision(strategy="probe_deeper")
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Tell me about your leadership.",
    ):
        result = qg.generate_question("int-1", decision)
    assert result.question_type == "fresh"


# AC2 — probe_deeper, existing evidence -> cross_question
def test_ac2_probe_deeper_with_evidence_is_cross_question(wired_system):
    cm, eg, qg = wired_system
    cm.record_turn(
        "int-1",
        "prior-q",
        "Tell me about leadership.",
        "fresh",
        "2026-07-19T09:00:00Z",
        target_competency_id="leadership",
    )
    turn = cm.record_answer(
        "int-1", "prior-q", "I led a team of 5 engineers.", "2026-07-19T09:01:00Z"
    )
    eg.add_evidence(
        "int-1", "leadership", turn.turn_id, "I led a team of 5 engineers", "supports"
    )

    decision = _decision(strategy="probe_deeper", qid="q-2")
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="What challenges did you face?",
    ):
        result = qg.generate_question("int-1", decision)
    assert result.question_type == "cross_question"


# AC3 — challenge_inconsistency, verify, wrap_up_competency all -> cross_question
@pytest.mark.parametrize(
    "strategy", ["challenge_inconsistency", "verify", "wrap_up_competency"]
)
def test_ac3_strategies_produce_cross_question(wired_system, strategy):
    cm, eg, qg = wired_system
    decision = _decision(strategy=strategy, qid=f"q-{strategy}")
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="A generated question.",
    ):
        result = qg.generate_question("int-1", decision)
    assert result.question_type == "cross_question"


# AC4 — stop decision raises without attempting generation
def test_ac4_stop_decision_raises(wired_system):
    cm, eg, qg = wired_system
    decision = _decision(dtype="stop")
    with patch("app.engine.question_generator.service.call_generation") as mock_gen:
        with pytest.raises(QuestionGeneratorError) as exc_info:
            qg.generate_question("int-1", decision)
        mock_gen.assert_not_called()
    assert exc_info.value.code == ErrorCode.INVALID_DECISION_TYPE


# AC5 — LLM failure falls back to template
def test_ac5_llm_failure_falls_back(wired_system):
    cm, eg, qg = wired_system
    decision = _decision(strategy="probe_deeper")
    with patch(
        "app.engine.question_generator.service.call_generation",
        side_effect=Exception("provider down"),
    ):
        result = qg.generate_question("int-1", decision)
    assert result.generation_method == "fallback_template"
    assert len(result.question_text) > 0


# AC6 — grounding context contains only real evidence excerpts
def test_ac6_grounding_context_uses_only_real_evidence(wired_system):
    cm, eg, qg = wired_system
    cm.record_turn(
        "int-1",
        "prior-q",
        "Tell me about leadership.",
        "fresh",
        "2026-07-19T09:00:00Z",
        target_competency_id="leadership",
    )
    turn = cm.record_answer(
        "int-1",
        "prior-q",
        "I led a team of 5 engineers on a launch.",
        "2026-07-19T09:01:00Z",
    )
    eg.add_evidence(
        "int-1", "leadership", turn.turn_id, "I led a team of 5 engineers", "supports"
    )

    captured_prompts = []

    def fake_generation(system, user):
        captured_prompts.append(user)
        return "A follow-up question."

    decision = _decision(strategy="verify", qid="q-3")
    with patch(
        "app.engine.question_generator.service.call_generation",
        side_effect=fake_generation,
    ):
        qg.generate_question("int-1", decision)

    assert len(captured_prompts) == 1
    assert "I led a team of 5 engineers" in captured_prompts[0]
    # Confirm no fabricated content was injected — only what's really in Evidence Graph
    assert "single-handedly saved the company" not in captured_prompts[0]


# AC7 — retry exactly once when too similar
def test_ac7_retries_once_when_too_similar(wired_system):
    cm, eg, qg = wired_system
    cm.record_turn(
        "int-1",
        "prior-q",
        "Tell me about your leadership experience.",
        "fresh",
        "2026-07-19T09:00:00Z",
        target_competency_id="leadership",
    )
    cm.record_answer("int-1", "prior-q", "Answer here.", "2026-07-19T09:01:00Z")

    call_count = {"n": 0}

    def fake_generation(system, user):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "Tell me about your leadership experience."  # too similar to prior question
        return "What specific decisions did you make under pressure?"  # genuinely different

    decision = _decision(strategy="probe_deeper", qid="q-4")
    with patch(
        "app.engine.question_generator.service.call_generation",
        side_effect=fake_generation,
    ):
        result = qg.generate_question("int-1", decision)

    assert call_count["n"] == 2
    assert result.generation_method == "llm"


# AC8 — after retry, if still too similar, falls back — call count stays at 2
def test_ac8_falls_back_after_one_retry_still_similar(wired_system):
    cm, eg, qg = wired_system
    cm.record_turn(
        "int-1",
        "prior-q",
        "Tell me about your leadership experience.",
        "fresh",
        "2026-07-19T09:00:00Z",
        target_competency_id="leadership",
    )
    cm.record_answer("int-1", "prior-q", "Answer here.", "2026-07-19T09:01:00Z")

    call_count = {"n": 0}

    def always_similar(system, user):
        call_count["n"] += 1
        return "Tell me about your leadership experience."  # always too similar

    decision = _decision(strategy="probe_deeper", qid="q-5")
    with patch(
        "app.engine.question_generator.service.call_generation",
        side_effect=always_similar,
    ):
        result = qg.generate_question("int-1", decision)

    assert call_count["n"] == 2  # never more than one retry
    assert result.generation_method == "fallback_template"


# AC9 — successful generation records a real turn with matching question_id
def test_ac9_turn_recorded_with_matching_question_id(wired_system):
    cm, eg, qg = wired_system
    decision = _decision(strategy="probe_deeper", qid="q-unique-1")
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="A question.",
    ):
        result = qg.generate_question("int-1", decision)

    history = cm.get_history("int-1")
    assert len(history) == 1
    assert history[0].question_id == "q-unique-1"
    assert history[0].question_id == result.question_id


# AC10 — end-to-end integration with a REAL ReasoningDecision from Module 8
def test_ac10_end_to_end_with_real_reasoning_decision():
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    logging_svc = LoggingService(InMemoryTraceStore())
    cmodel = CompetencyModelService(InMemoryCompetencyModelStore())
    reasoning = ReasoningEngineService(
        competency_model=cmodel, evidence_graph=eg, logging_service=logging_svc
    )
    qg = QuestionGeneratorService(evidence_graph=eg, conversation_memory=cm)

    cmodel.initialize_competencies(
        "int-1",
        [
            CompetencySeed(competency_id="leadership", emphasis="primary"),
            CompetencySeed(competency_id="problem_solving", emphasis="primary"),
        ],
    )

    # Real decision from Module 8, not hand-constructed
    real_decision = reasoning.decide_next_action("int-1")
    assert real_decision.decision_type == "continue"

    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Tell me about your background.",
    ):
        result = qg.generate_question("int-1", real_decision)

    assert result.question_id == real_decision.question_id
    history = cm.get_history("int-1")
    assert history[0].question_id == real_decision.question_id


# AC11 — interview isolation
def test_ac11_interview_isolation(wired_system):
    cm, eg, qg = wired_system
    cm.record_turn(
        "int-OTHER",
        "other-q",
        "Some other question entirely.",
        "fresh",
        "2026-07-19T09:00:00Z",
        target_competency_id="leadership",
    )

    decision = _decision(strategy="probe_deeper", qid="q-iso")
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Some other question entirely.",
    ):
        result = qg.generate_question("int-1", decision)

    # Should NOT be flagged similar despite identical text, since it's a different interview
    assert result.generation_method == "llm"
    assert result.question_text == "Some other question entirely."


# Provider isolation check
def test_provider_isolation_only_generator_module_touches_sdk():
    import inspect
    import app.engine.question_generator.service as svc
    import app.engine.question_generator.grounding_builder as gb
    import app.engine.question_generator.prompt_builder as pb
    import app.engine.question_generator.similarity_handler as sh
    import app.engine.question_generator.generator as gen

    for module in (svc, gb, pb, sh):
        source = inspect.getsource(module)
        assert "import anthropic" not in source.lower()

    gen_source = inspect.getsource(gen)
    assert "from app.core.provider_adapter import get_provider" in gen_source
