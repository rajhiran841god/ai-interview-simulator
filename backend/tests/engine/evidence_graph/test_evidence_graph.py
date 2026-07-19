"""
Tests mapped to Evidence_Graph_Contract.md's 9 Acceptance Criteria,
plus an explicit cross-module integration test with Conversation
Memory, per reviewer's request.
"""

import pytest

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.conversation_memory.store import InMemoryConversationMemoryStore
from app.engine.evidence_graph.service import EvidenceGraphService
from app.engine.evidence_graph.store import InMemoryEvidenceGraphStore
from app.engine.evidence_graph.schema import EvidenceGraphError, ErrorCode


@pytest.fixture
def conversation_memory():
    return ConversationMemoryService(InMemoryConversationMemoryStore())


@pytest.fixture
def evidence_graph(conversation_memory):
    # Explicitly share the SAME ConversationMemoryService instance —
    # this is what makes the integration real rather than accidental.
    return EvidenceGraphService(
        store=InMemoryEvidenceGraphStore(), conversation_memory=conversation_memory
    )


def _seed_answered_turn(
    conversation_memory,
    interview_id="int-1",
    question_id="q-1",
    question_text="Tell me about your leadership experience.",
    answer_text="I led a team of 5 engineers on a critical product launch.",
):
    conversation_memory.record_turn(
        interview_id,
        question_id,
        question_text,
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    return conversation_memory.record_answer(
        interview_id, question_id, answer_text, "2026-07-19T10:01:00Z"
    )


# AC1 — successful add + retrieval
def test_ac1_add_and_retrieve_evidence(evidence_graph, conversation_memory):
    turn = _seed_answered_turn(conversation_memory)
    entry = evidence_graph.add_evidence(
        interview_id="int-1",
        competency_id="leadership",
        turn_id=turn.turn_id,
        evidence_excerpt="I led a team of 5 engineers",
        relation="supports",
    )
    assert entry.evidence_id is not None

    by_competency = evidence_graph.get_evidence_for_competency("int-1", "leadership")
    assert len(by_competency) == 1
    assert by_competency[0].evidence_id == entry.evidence_id

    by_turn = evidence_graph.get_evidence_for_turn("int-1", turn.turn_id)
    assert len(by_turn) == 1


# AC2 — fabricated excerpt rejected
def test_ac2_fabricated_excerpt_rejected(evidence_graph, conversation_memory):
    turn = _seed_answered_turn(conversation_memory)
    with pytest.raises(EvidenceGraphError) as exc_info:
        evidence_graph.add_evidence(
            interview_id="int-1",
            competency_id="leadership",
            turn_id=turn.turn_id,
            evidence_excerpt="I single-handedly saved the company from bankruptcy",
            relation="supports",
        )
    assert exc_info.value.code == ErrorCode.EXCERPT_NOT_TRACEABLE


# AC3 — nonexistent turn rejected
def test_ac3_nonexistent_turn_rejected(evidence_graph, conversation_memory):
    _seed_answered_turn(conversation_memory)
    with pytest.raises(EvidenceGraphError) as exc_info:
        evidence_graph.add_evidence(
            interview_id="int-1",
            competency_id="leadership",
            turn_id="nonexistent-turn-id",
            evidence_excerpt="anything",
            relation="supports",
        )
    assert exc_info.value.code == ErrorCode.TURN_NOT_FOUND


# AC4 — contradicts without target rejected
def test_ac4_contradicts_without_target_rejected(evidence_graph, conversation_memory):
    turn = _seed_answered_turn(conversation_memory)
    with pytest.raises(EvidenceGraphError) as exc_info:
        evidence_graph.add_evidence(
            interview_id="int-1",
            competency_id="leadership",
            turn_id=turn.turn_id,
            evidence_excerpt="I led a team of 5 engineers",
            relation="contradicts",
            contradicts_evidence_id=None,
        )
    assert exc_info.value.code == ErrorCode.MISSING_CONTRADICTION_TARGET


# AC5 — contradicts with nonexistent target rejected
def test_ac5_contradicts_nonexistent_target_rejected(
    evidence_graph, conversation_memory
):
    turn = _seed_answered_turn(conversation_memory)
    with pytest.raises(EvidenceGraphError) as exc_info:
        evidence_graph.add_evidence(
            interview_id="int-1",
            competency_id="leadership",
            turn_id=turn.turn_id,
            evidence_excerpt="I led a team of 5 engineers",
            relation="contradicts",
            contradicts_evidence_id="fake-evidence-id",
        )
    assert exc_info.value.code == ErrorCode.CONTRADICTS_TARGET_NOT_FOUND


# AC6 — has_contradictions both directions
def test_ac6_has_contradictions_true_and_false(evidence_graph, conversation_memory):
    turn1 = _seed_answered_turn(conversation_memory)
    original = evidence_graph.add_evidence(
        "int-1", "leadership", turn1.turn_id, "I led a team of 5 engineers", "supports"
    )
    assert evidence_graph.has_contradictions("int-1", "leadership") is False

    conversation_memory.record_turn(
        "int-1",
        "q-2",
        "Who made the decisions on that project?",
        "cross_question",
        "2026-07-19T10:05:00Z",
        target_competency_id="leadership",
    )
    turn2 = conversation_memory.record_answer(
        "int-1",
        "q-2",
        "Actually my manager made all the calls.",
        "2026-07-19T10:06:00Z",
    )
    evidence_graph.add_evidence(
        "int-1",
        "leadership",
        turn2.turn_id,
        "my manager made all the calls",
        "contradicts",
        contradicts_evidence_id=original.evidence_id,
    )
    assert evidence_graph.has_contradictions("int-1", "leadership") is True


# AC7 — ordering derived from Conversation Memory sequence
def test_ac7_evidence_ordered_by_turn_sequence(evidence_graph, conversation_memory):
    conversation_memory.record_turn(
        "int-1",
        "q-1",
        "Question A",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    turn1 = conversation_memory.record_answer(
        "int-1", "q-1", "Answer with evidence one here.", "2026-07-19T10:01:00Z"
    )
    conversation_memory.record_turn(
        "int-1",
        "q-2",
        "Question B",
        "fresh",
        "2026-07-19T09:00:00Z",
        target_competency_id="leadership",
    )  # earlier timestamp, later call
    turn2 = conversation_memory.record_answer(
        "int-1", "q-2", "Answer with evidence two here.", "2026-07-19T09:01:00Z"
    )

    evidence_graph.add_evidence(
        "int-1", "leadership", turn2.turn_id, "evidence two", "supports"
    )
    evidence_graph.add_evidence(
        "int-1", "leadership", turn1.turn_id, "evidence one", "supports"
    )

    ordered = evidence_graph.get_evidence_for_competency("int-1", "leadership")
    # turn1 was recorded first (call order), so its evidence should come first
    # despite being added to the graph second and despite turn2 having an earlier timestamp.
    assert ordered[0].turn_id == turn1.turn_id
    assert ordered[1].turn_id == turn2.turn_id


# AC8 — no full question/answer text duplicated in this module's schema
def test_ac8_no_full_conversation_text_duplicated():
    from app.engine.evidence_graph.schema import EvidenceEntry

    fields = EvidenceEntry.model_fields.keys()
    # Structural check: no field name suggests storing full question or
    # answer content — only excerpt (short fragment) and ID references.
    forbidden_field_names = {
        "question_text",
        "answer_text",
        "full_answer",
        "full_question",
    }
    assert forbidden_field_names.isdisjoint(set(fields))


# AC9 — interview isolation
def test_ac9_evidence_isolated_between_interviews(conversation_memory):
    cm2 = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg1 = EvidenceGraphService(conversation_memory=conversation_memory)
    eg2 = EvidenceGraphService(conversation_memory=cm2)

    turn1 = _seed_answered_turn(conversation_memory, interview_id="int-1")
    turn2 = _seed_answered_turn(cm2, interview_id="int-2")

    eg1.add_evidence(
        "int-1", "leadership", turn1.turn_id, "I led a team of 5 engineers", "supports"
    )
    eg2.add_evidence(
        "int-2", "leadership", turn2.turn_id, "I led a team of 5 engineers", "supports"
    )

    assert len(eg1.get_evidence_for_competency("int-1", "leadership")) == 1
    assert len(eg1.get_evidence_for_competency("int-2", "leadership")) == 0


# Immutability check (reviewer's suggestion)
def test_evidence_entries_are_immutable():
    from app.engine.evidence_graph.schema import EvidenceEntry
    import pydantic

    entry = EvidenceEntry(
        evidence_id="e1",
        interview_id="int-1",
        competency_id="leadership",
        turn_id="t1",
        question_id="q1",
        evidence_excerpt="test",
        relation="supports",
        created_at="2026-07-19T10:00:00Z",
    )
    with pytest.raises(pydantic.ValidationError):
        entry.evidence_excerpt = "changed"


# Duplicate evidence policy — conscious decision, tested explicitly
def test_duplicate_evidence_is_allowed_not_deduplicated(
    evidence_graph, conversation_memory
):
    turn = _seed_answered_turn(conversation_memory)
    e1 = evidence_graph.add_evidence(
        "int-1", "leadership", turn.turn_id, "I led a team of 5 engineers", "supports"
    )
    e2 = evidence_graph.add_evidence(
        "int-1", "leadership", turn.turn_id, "I led a team of 5 engineers", "supports"
    )
    assert e1.evidence_id != e2.evidence_id  # distinct IDs, not deduplicated
    assert len(evidence_graph.get_evidence_for_turn("int-1", turn.turn_id)) == 2


# evidence_id is always generated internally, never caller-influenced
def test_evidence_id_generated_internally(evidence_graph, conversation_memory):
    turn = _seed_answered_turn(conversation_memory)
    evidence_graph.add_evidence(
        "int-1", "leadership", turn.turn_id, "I led a team of 5 engineers", "supports"
    )
    # add_evidence's signature has no evidence_id parameter at all —
    # structurally impossible for a caller to inject one.
    import inspect

    sig = inspect.signature(evidence_graph.add_evidence)
    assert "evidence_id" not in sig.parameters


# ============================================================
# CROSS-MODULE INTEGRATION TEST — per reviewer's explicit request.
# Exercises the real interface between two completed modules, not
# just mocked IDs.
# ============================================================
def test_full_cross_module_integration_with_conversation_memory():
    cm = ConversationMemoryService(InMemoryConversationMemoryStore())
    eg = EvidenceGraphService(conversation_memory=cm)

    # 1. Record a conversation turn.
    cm.record_turn(
        "int-1",
        "q-1",
        "Tell me about a challenge you led your team through.",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )

    # 2. Retrieve the stored answer (simulate the candidate answering).
    turn = cm.record_answer(
        "int-1",
        "q-1",
        "We had a critical outage. I coordinated the team, delegated tasks, and we resolved it in 3 hours.",
        "2026-07-19T10:05:00Z",
    )
    history = cm.get_history("int-1")
    assert history[0].answer_text == turn.answer_text

    # 3. Add evidence using an excerpt from that answer.
    evidence = eg.add_evidence(
        interview_id="int-1",
        competency_id="leadership",
        turn_id=turn.turn_id,
        evidence_excerpt="I coordinated the team, delegated tasks",
        relation="supports",
    )

    # 4. Verify the shared validator accepted it (implicitly — no
    # exception was raised; explicitly confirm via is_traceable directly too).
    from app.engine.shared.validator import is_traceable

    assert is_traceable(evidence.evidence_excerpt, turn.answer_text) is True

    # 5. Query the graph by competency and by turn.
    by_competency = eg.get_evidence_for_competency("int-1", "leadership")
    by_turn = eg.get_evidence_for_turn("int-1", turn.turn_id)
    assert len(by_competency) == 1
    assert len(by_turn) == 1
    assert by_competency[0].evidence_id == by_turn[0].evidence_id

    # 6. Confirm ordering follows Conversation Memory (single entry
    # here, but confirms the sequence lookup path executes without error).
    assert by_competency[0].turn_id == history[0].turn_id
