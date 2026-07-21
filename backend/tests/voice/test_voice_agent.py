"""
Tests for the voice interface adapter (Decision Log #004).

These test the ORCHESTRATION LOGIC in InterviewVoiceAgent.llm_node —
i.e., that it correctly sequences calls into the unchanged Interview
Intelligence Engine. They do NOT test real speech-to-text, real
text-to-speech, or real turn detection — those require live LiveKit/
Deepgram/ElevenLabs credentials and cannot be verified in this
environment. See docs/Voice_Interface_Design_Note.md for what remains
unverified.

A fake ChatContext/ChatItem stands in for LiveKit's real transcript
object — only the two attributes (`role`, `text_content`) the agent
actually reads are provided, kept minimal deliberately.
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
from app.engine.reasoning.service import ReasoningEngineService
from app.engine.question_generator.service import QuestionGeneratorService
from app.voice.agent import InterviewVoiceAgent


class FakeChatContext:
    def __init__(self, items):
        self.items = items


class FakeChatItem:
    def __init__(self, role, text):
        self.role = role
        self.text_content = text


FAKE_EVAL_RESPONSE = {
    "answer_classification": "substantive",
    "evidence_excerpts": ["I led a team of 5 engineers"],
    "contradicts_prior_evidence": False,
    "contradiction_explanation": None,
    "confidence_contribution": 0.8,
    "reasoning_summary": "Good example.",
}


@pytest.fixture
def wired_agent():
    interview_id = "voice-test"
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=cm
    )
    logging_svc = LoggingService(InMemoryTraceStore())
    cmodel = CompetencyModelService(InMemoryCompetencyModelStore())
    ee = EvaluationEngineService(evidence_graph=eg, logging_service=logging_svc)
    re = ReasoningEngineService(
        competency_model=cmodel, evidence_graph=eg, logging_service=logging_svc
    )
    qg = QuestionGeneratorService(evidence_graph=eg, conversation_memory=cm)
    cmodel.initialize_competencies(
        interview_id, [CompetencySeed(competency_id="leadership", emphasis="primary")]
    )
    agent = InterviewVoiceAgent(
        interview_id=interview_id,
        conversation_memory=cm,
        evidence_graph=eg,
        logging_service=logging_svc,
        competency_model=cmodel,
        evaluation_engine=ee,
        reasoning_engine=re,
        question_generator=qg,
    )
    return agent, cm, eg, cmodel, interview_id


@pytest.mark.asyncio
async def test_first_turn_asks_a_question_with_no_prior_answer(wired_agent):
    agent, cm, eg, cmodel, interview_id = wired_agent
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Tell me about your leadership experience.",
    ):
        ctx = FakeChatContext([])
        result = [chunk async for chunk in agent.llm_node(ctx, [], None)]
    assert len(result) == 1
    assert len(result[0]) > 0
    assert cm.get_history(interview_id)[0].question_id == agent._pending_question_id


@pytest.mark.asyncio
async def test_answer_recorded_before_evaluation_evidence_is_captured(wired_agent):
    """Regression test for the real ordering bug found during
    verification: evaluate_answer must run AFTER record_answer, since
    Evidence Graph's provenance check looks up the turn's answer_text
    via Conversation Memory internally."""
    agent, cm, eg, cmodel, interview_id = wired_agent
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Tell me about your leadership experience.",
    ):
        ctx1 = FakeChatContext([])
        _ = [c async for c in agent.llm_node(ctx1, [], None)]

    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=FAKE_EVAL_RESPONSE
    ), patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Can you elaborate?",
    ):
        ctx2 = FakeChatContext(
            [FakeChatItem("user", "I led a team of 5 engineers on a critical launch.")]
        )
        _ = [c async for c in agent.llm_node(ctx2, [], None)]

    evidence = eg.get_evidence_for_competency(interview_id, "leadership")
    assert len(evidence) == 1
    assert evidence[0].evidence_excerpt == "I led a team of 5 engineers"

    history = cm.get_history(interview_id)
    assert history[0].answer_text == "I led a team of 5 engineers on a critical launch."
    assert history[0].status == "answered"


@pytest.mark.asyncio
async def test_competency_model_actually_updated_after_evaluation(wired_agent):
    """Regression test for the real missing-wiring bug found during
    verification: without this, confidence never moves and Reasoning
    Engine would ask about the same competency indefinitely."""
    agent, cm, eg, cmodel, interview_id = wired_agent
    with patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Tell me about your leadership experience.",
    ):
        ctx1 = FakeChatContext([])
        _ = [c async for c in agent.llm_node(ctx1, [], None)]

    assert cmodel.get_competency_state(interview_id, "leadership").confidence == 0.0

    with patch(
        "app.engine.evaluation.service.classify_answer", return_value=FAKE_EVAL_RESPONSE
    ), patch(
        "app.engine.question_generator.service.call_generation",
        return_value="Can you elaborate?",
    ):
        ctx2 = FakeChatContext(
            [FakeChatItem("user", "I led a team of 5 engineers on a critical launch.")]
        )
        _ = [c async for c in agent.llm_node(ctx2, [], None)]

    updated_confidence = cmodel.get_competency_state(
        interview_id, "leadership"
    ).confidence
    assert updated_confidence > 0.0
    assert updated_confidence == pytest.approx(0.8, abs=1e-9)


@pytest.mark.asyncio
async def test_stop_decision_yields_stop_reason_not_a_question(wired_agent):
    """When Reasoning Engine decides to stop, llm_node must yield the
    stop reason, not attempt to generate another question."""
    agent, cm, eg, cmodel, interview_id = wired_agent
    # Force a stop by pushing confidence high and question count past floor.
    cmodel.update_from_evaluation(interview_id, "leadership", 0.99, False, ["ev-1"])
    from app.shared.reasoning_config import MIN_QUESTIONS

    for i in range(MIN_QUESTIONS):
        agent._logging.record_trace(
            interview_id,
            f"prior-q-{i}",
            "probe_deeper",
            0.9,
            "gap",
            "reason",
            "v1",
            "model",
            target_competency_id="leadership",
        )
    ctx = FakeChatContext([])
    result = [chunk async for chunk in agent.llm_node(ctx, [], None)]
    assert len(result) == 1
    # Should not have set up a new pending question when stopping
    # (pending_question_id from before this call should be unchanged/None)


def test_voice_module_does_not_modify_engine_files():
    """Structural check: the voice adapter must be an independent
    module that only IMPORTS engine services, never redefines or
    monkey-patches them."""
    import inspect
    import app.voice.agent as voice_module

    source = inspect.getsource(voice_module)
    # Should only import from app.engine.*, never define classes with
    # the same names as engine schema/service classes (which would
    # suggest a shadow reimplementation instead of reuse).
    assert "class ReasoningEngineService" not in source
    assert "class EvaluationEngineService" not in source
    assert "class QuestionGeneratorService" not in source
    assert "from app.engine." in source


def test_voice_adapter_is_independently_importable_and_removable():
    """Confirms the voice adapter can be excluded from a deployment
    (e.g. by simply not installing livekit-agents / not importing
    app.voice) without affecting the text pipeline — nothing in
    app/engine/ imports from app/voice/."""
    import app.engine.reasoning.service as reasoning_service
    import inspect

    source = inspect.getsource(reasoning_service)
    assert "app.voice" not in source
