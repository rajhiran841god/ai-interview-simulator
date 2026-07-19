"""
Public API for Conversation Memory. Deterministic only — no
ProviderAdapter, no LLM, no embeddings/semantic search anywhere in
this module (Contract v2's enforceable constraint).
"""

import re
import uuid
from difflib import SequenceMatcher
from typing import Optional

from app.engine.conversation_memory.schema import (
    TurnRecord,
    QuestionType,
    DEFAULT_SIMILARITY_THRESHOLD,
)
from app.engine.conversation_memory.store import (
    ConversationMemoryStore,
    InMemoryConversationMemoryStore,
)

# Module-level default store for simple call sites; callers needing a
# specific store (e.g. under test, or a future DB-backed store) can
# construct a ConversationMemoryService directly instead.
_default_store = InMemoryConversationMemoryStore()


class ConversationMemoryService:
    def __init__(self, store: Optional[ConversationMemoryStore] = None):
        self._store = store or _default_store

    def record_turn(
        self,
        interview_id: str,
        question_id: str,
        question_text: str,
        question_type: QuestionType,
        question_timestamp: str,
        target_competency_id: Optional[str] = None,
    ) -> TurnRecord:
        seq = self._store.next_sequence_number(interview_id)
        turn = TurnRecord(
            turn_id=str(uuid.uuid4()),
            interview_id=interview_id,
            question_id=question_id,
            sequence_number=seq,
            question_text=question_text,
            question_type=question_type,
            target_competency_id=target_competency_id,
            question_timestamp=question_timestamp,
            status="asked",
            created_at=question_timestamp,
            updated_at=question_timestamp,
        )
        return self._store.append_turn(turn)

    def record_answer(
        self,
        interview_id: str,
        question_id: str,
        answer_text: str,
        answer_timestamp: str,
    ) -> TurnRecord:
        return self._store.update_answer(
            interview_id, question_id, answer_text, answer_timestamp
        )

    def get_history(self, interview_id: str) -> list[TurnRecord]:
        return self._store.get_history(interview_id)

    def get_turns_by_competency(
        self, interview_id: str, competency_id: str
    ) -> list[TurnRecord]:
        return self._store.get_turns_by_competency(interview_id, competency_id)

    def has_asked_similar(
        self,
        interview_id: str,
        question_text: str,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> bool:
        """
        Literal/near-literal similarity only — NOT semantic topic
        matching (explicitly out of scope per Contract v2's
        Non-Responsibilities). Uses normalized string comparison via
        difflib's SequenceMatcher, a deterministic, dependency-free
        approach — no embeddings, no LLM call, per the module's
        determinism constraint.
        """
        normalized_target = _normalize_for_comparison(question_text)
        for turn in self._store.get_history(interview_id):
            normalized_existing = _normalize_for_comparison(turn.question_text)
            ratio = SequenceMatcher(
                None, normalized_target, normalized_existing
            ).ratio()
            if ratio >= threshold:
                return True
        return False


def _normalize_for_comparison(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


# Module-level convenience functions using the default store — the
# simplest public API surface for callers that don't need to inject a
# custom store (tests use their own ConversationMemoryService instance
# instead, to avoid shared state between tests).
_default_service = ConversationMemoryService(_default_store)


def record_turn(*args, **kwargs) -> TurnRecord:
    return _default_service.record_turn(*args, **kwargs)


def record_answer(*args, **kwargs) -> TurnRecord:
    return _default_service.record_answer(*args, **kwargs)


def get_history(interview_id: str) -> list[TurnRecord]:
    return _default_service.get_history(interview_id)


def get_turns_by_competency(interview_id: str, competency_id: str) -> list[TurnRecord]:
    return _default_service.get_turns_by_competency(interview_id, competency_id)


def has_asked_similar(
    interview_id: str,
    question_text: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> bool:
    return _default_service.has_asked_similar(interview_id, question_text, threshold)
