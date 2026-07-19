"""
Tests mapped to Conversation_Memory_Contract_2.md's 11 Acceptance
Criteria. This module is deterministic — these tests require no
mocking of any external provider, unlike Modules 1 and 2.
"""

import pytest

from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.conversation_memory.store import InMemoryConversationMemoryStore
from app.engine.conversation_memory.schema import ConversationMemoryError, ErrorCode


@pytest.fixture
def service():
    # Fresh store per test — avoids shared state between tests, which
    # the module-level default store would otherwise cause.
    return ConversationMemoryService(InMemoryConversationMemoryStore())


# AC1 — record_turn produces correct initial state
def test_ac1_record_turn_initial_state(service):
    turn = service.record_turn(
        interview_id="int-1",
        question_id="q-1",
        question_text="Tell me about a time you led a team.",
        question_type="fresh",
        question_timestamp="2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    assert turn.status == "asked"
    assert turn.answer_text is None
    assert turn.turn_id is not None
    assert len(turn.turn_id) > 0

    history = service.get_history("int-1")
    assert len(history) == 1
    assert history[0].turn_id == turn.turn_id


# AC2 — record_answer transitions status and populates answer
def test_ac2_record_answer_transitions_status(service):
    service.record_turn(
        "int-1", "q-1", "Tell me about leadership.", "fresh", "2026-07-19T10:00:00Z"
    )
    service.record_answer("int-1", "q-1", "I led a team of 5.", "2026-07-19T10:01:00Z")

    history = service.get_history("int-1")
    assert history[0].status == "answered"
    assert history[0].answer_text == "I led a team of 5."


# AC3 — sequence_number monotonic regardless of timestamp order, never changes
def test_ac3_sequence_number_monotonic_despite_timestamp_order(service):
    # Second turn has an EARLIER timestamp than the first — order of
    # calls should still determine sequence_number, not timestamps.
    t1 = service.record_turn(
        "int-1", "q-1", "Question A", "fresh", "2026-07-19T10:05:00Z"
    )
    t2 = service.record_turn(
        "int-1", "q-2", "Question B", "fresh", "2026-07-19T10:00:00Z"
    )

    assert t1.sequence_number == 1
    assert t2.sequence_number == 2  # call order, not timestamp order

    history = service.get_history("int-1")
    assert history[0].question_id == "q-1"
    assert history[1].question_id == "q-2"


def test_ac3_sequence_number_never_changes_after_assignment(service):
    turn = service.record_turn(
        "int-1", "q-1", "Question A", "fresh", "2026-07-19T10:00:00Z"
    )
    original_seq = turn.sequence_number
    updated = service.record_answer("int-1", "q-1", "answer", "2026-07-19T10:01:00Z")
    assert updated.sequence_number == original_seq


# AC4 — duplicate question_id rejected
def test_ac4_duplicate_question_id_rejected(service):
    service.record_turn("int-1", "q-1", "Question A", "fresh", "2026-07-19T10:00:00Z")
    with pytest.raises(ConversationMemoryError) as exc_info:
        service.record_turn(
            "int-1", "q-1", "Different text", "fresh", "2026-07-19T10:05:00Z"
        )
    assert exc_info.value.code == ErrorCode.DUPLICATE_QUESTION_ID

    # Original record must be unmodified
    history = service.get_history("int-1")
    assert len(history) == 1
    assert history[0].question_text == "Question A"


# AC5 — answering nonexistent question rejected
def test_ac5_answer_without_question_rejected(service):
    with pytest.raises(ConversationMemoryError) as exc_info:
        service.record_answer(
            "int-1", "nonexistent-q", "answer", "2026-07-19T10:00:00Z"
        )
    assert exc_info.value.code == ErrorCode.ANSWER_WITHOUT_QUESTION


# AC6 — double-answering rejected, first answer preserved
def test_ac6_already_answered_rejected(service):
    service.record_turn("int-1", "q-1", "Question A", "fresh", "2026-07-19T10:00:00Z")
    service.record_answer("int-1", "q-1", "First answer", "2026-07-19T10:01:00Z")

    with pytest.raises(ConversationMemoryError) as exc_info:
        service.record_answer("int-1", "q-1", "Second answer", "2026-07-19T10:02:00Z")
    assert exc_info.value.code == ErrorCode.ALREADY_ANSWERED

    history = service.get_history("int-1")
    assert history[0].answer_text == "First answer"  # unchanged


# AC7 — empty interview returns empty list, not an error
def test_ac7_empty_interview_returns_empty_list(service):
    history = service.get_history("interview-that-does-not-exist")
    assert history == []


# AC8 — competency filtering
def test_ac8_get_turns_by_competency_filters_correctly(service):
    service.record_turn(
        "int-1",
        "q-1",
        "Leadership question",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    service.record_turn(
        "int-1",
        "q-2",
        "Problem solving question",
        "fresh",
        "2026-07-19T10:01:00Z",
        target_competency_id="problem_solving",
    )
    leadership_turns = service.get_turns_by_competency("int-1", "leadership")
    assert len(leadership_turns) == 1
    assert leadership_turns[0].question_id == "q-1"


# AC9 — has_asked_similar: both positive and negative cases
def test_ac9_has_asked_similar_detects_near_duplicate(service):
    service.record_turn(
        "int-1",
        "q-1",
        "Tell me about a time you led a team.",
        "fresh",
        "2026-07-19T10:00:00Z",
    )
    # Near-duplicate: minor rewording
    assert (
        service.has_asked_similar("int-1", "Tell me about a time you led a team")
        is True
    )


def test_ac9_has_asked_similar_does_not_flag_genuinely_different_questions(service):
    service.record_turn(
        "int-1",
        "q-1",
        "Tell me about a time you led a team.",
        "fresh",
        "2026-07-19T10:00:00Z",
    )
    # Genuinely different question, same competency territory
    assert (
        service.has_asked_similar(
            "int-1", "How do you handle conflict within a team you're leading?"
        )
        is False
    )


def test_ac9_default_threshold_used_when_not_supplied(service):
    from app.engine.conversation_memory.schema import DEFAULT_SIMILARITY_THRESHOLD

    service.record_turn(
        "int-1",
        "q-1",
        "Describe your leadership style.",
        "fresh",
        "2026-07-19T10:00:00Z",
    )
    # No threshold argument supplied — should use the module default,
    # not error or require one.
    result = service.has_asked_similar("int-1", "Describe your leadership style")
    assert isinstance(result, bool)
    assert (
        DEFAULT_SIMILARITY_THRESHOLD == 0.85
    )  # confirms the constant is what the contract expects


# AC10 — interview isolation (highest-risk criterion per review)
def test_ac10_interviews_are_fully_isolated(service):
    service.record_turn(
        "int-1",
        "q-1",
        "Tell me about your leadership experience.",
        "fresh",
        "2026-07-19T10:00:00Z",
    )
    service.record_turn(
        "int-2",
        "q-1",
        "What is your approach to financial modeling?",
        "fresh",
        "2026-07-19T10:00:00Z",
    )

    history_1 = service.get_history("int-1")
    history_2 = service.get_history("int-2")

    assert len(history_1) == 1
    assert len(history_2) == 1
    assert history_1[0].question_text == "Tell me about your leadership experience."
    assert history_2[0].question_text == "What is your approach to financial modeling?"

    # Same question_id "q-1" used in both interviews — must NOT collide,
    # since question_id uniqueness is scoped per-interview, not global.
    assert history_1[0].interview_id == "int-1"
    assert history_2[0].interview_id == "int-2"

    # has_asked_similar must also respect interview boundaries — using
    # genuinely dissimilar text here (unlike an earlier draft of this
    # test, which accidentally used near-identical strings differing
    # by one character and produced a false failure — fixed after
    # actually running the test and diagnosing the real cause rather
    # than assuming the implementation was wrong).
    assert (
        service.has_asked_similar("int-2", "Tell me about your leadership experience.")
        is False
    )


# AC11 — record_answer cannot alter non-answer fields
def test_ac11_record_answer_cannot_alter_immutable_fields(service):
    original = service.record_turn(
        "int-1",
        "q-1",
        "Original question text",
        "fresh",
        "2026-07-19T10:00:00Z",
        target_competency_id="leadership",
    )
    updated = service.record_answer(
        "int-1", "q-1", "The answer", "2026-07-19T10:01:00Z"
    )

    assert updated.question_text == original.question_text
    assert updated.target_competency_id == original.target_competency_id
    assert updated.question_type == original.question_type
    assert updated.question_timestamp == original.question_timestamp
    assert updated.turn_id == original.turn_id
    assert updated.sequence_number == original.sequence_number
    # Only these should differ:
    assert updated.answer_text == "The answer"
    assert updated.status == "answered"


# Supporting test: no ProviderAdapter/LLM import anywhere in this module
def test_determinism_no_provider_imports():
    """
    Checks actual import statements, not arbitrary source text — an
    earlier draft of this test checked whether the word
    'ProviderAdapter' appeared anywhere in the source, which falsely
    failed because the module's own docstring mentions it BY NAME
    specifically to explain that it must NOT be imported. Fixed to
    check import lines specifically after running the test and seeing
    the false failure.
    """
    import app.engine.conversation_memory.service as svc_module
    import app.engine.conversation_memory.store as store_module
    import inspect

    forbidden_import_fragments = ["provider_adapter", "import anthropic", "embedding"]

    for module in (svc_module, store_module):
        source = inspect.getsource(module)
        import_lines = [
            line.strip().lower()
            for line in source.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for line in import_lines:
            for forbidden in forbidden_import_fragments:
                assert (
                    forbidden not in line
                ), f"Forbidden import found: '{line}' in {module.__name__}"
