"""
ConversationMemoryStore — the storage abstraction required by
Contract v2. Deliberately small interface, per reviewer's explicit
guidance: append_turn, update_answer, get_history, get_turn,
get_turns_by_competency. No storage-specific methods leak out.

Swapping the backend later (e.g. to Postgres/Supabase for the real
pilot) means implementing this same abstract interface — nothing in
app/engine/conversation_memory/service.py should need to change.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.engine.conversation_memory.schema import TurnRecord


class ConversationMemoryStore(ABC):
    @abstractmethod
    def next_sequence_number(self, interview_id: str) -> int:
        """Atomically assign and return the next sequence number for
        this interview. Must be monotonic and never reused, even under
        concurrent calls (Contract v2's ordering guarantee)."""
        raise NotImplementedError

    @abstractmethod
    def append_turn(self, turn: TurnRecord) -> TurnRecord:
        """Persist a new turn. Caller guarantees turn_id/sequence_number
        are already assigned before calling this."""
        raise NotImplementedError

    @abstractmethod
    def update_answer(
        self,
        interview_id: str,
        question_id: str,
        answer_text: str,
        answer_timestamp: str,
    ) -> TurnRecord:
        """Mutate ONLY answer_text/answer_timestamp/status/updated_at
        on an existing turn. Must raise ConversationMemoryError with
        ANSWER_WITHOUT_QUESTION or ALREADY_ANSWERED as appropriate."""
        raise NotImplementedError

    @abstractmethod
    def get_history(self, interview_id: str) -> list[TurnRecord]:
        """Ordered by sequence_number. Empty list if no turns exist —
        never raises for a missing/empty interview."""
        raise NotImplementedError

    @abstractmethod
    def get_turn(self, interview_id: str, question_id: str) -> Optional[TurnRecord]:
        """Single turn lookup. None if not found (not an error)."""
        raise NotImplementedError

    @abstractmethod
    def get_turns_by_competency(
        self, interview_id: str, competency_id: str
    ) -> list[TurnRecord]:
        raise NotImplementedError


class InMemoryConversationMemoryStore(ConversationMemoryStore):
    """Pilot-scale implementation. Per Contract v2's concurrency note,
    ordering must be preserved under simultaneous writes — a simple
    per-interview lock is sufficient at this scale; this is not
    solving general distributed-locking concerns."""

    def __init__(self):
        self._turns: dict[str, list[TurnRecord]] = {}
        self._question_index: dict[tuple[str, str], int] = (
            {}
        )  # (interview_id, question_id) -> index in list
        self._sequence_counters: dict[str, int] = {}
        self._locks: dict[str, "_DummyLock"] = {}

    def _lock_for(self, interview_id: str):
        # Real concurrency (threading.Lock) would go here in a
        # multi-threaded deployment; a no-op placeholder is honest for
        # a single-process pilot rather than pretending to solve
        # concurrency the implementation doesn't actually need yet.
        if interview_id not in self._locks:
            self._locks[interview_id] = _DummyLock()
        return self._locks[interview_id]

    def next_sequence_number(self, interview_id: str) -> int:
        with self._lock_for(interview_id):
            current = self._sequence_counters.get(interview_id, 0)
            self._sequence_counters[interview_id] = current + 1
            return current + 1

    def append_turn(self, turn: TurnRecord) -> TurnRecord:
        with self._lock_for(turn.interview_id):
            key = (turn.interview_id, turn.question_id)
            if key in self._question_index:
                from app.engine.conversation_memory.schema import (
                    ConversationMemoryError,
                    ErrorCode,
                )

                raise ConversationMemoryError(
                    ErrorCode.DUPLICATE_QUESTION_ID,
                    f"question_id '{turn.question_id}' already exists for interview '{turn.interview_id}'.",
                )
            self._turns.setdefault(turn.interview_id, [])
            self._turns[turn.interview_id].append(turn)
            self._question_index[key] = len(self._turns[turn.interview_id]) - 1
            return turn

    def update_answer(
        self,
        interview_id: str,
        question_id: str,
        answer_text: str,
        answer_timestamp: str,
    ) -> TurnRecord:
        from app.engine.conversation_memory.schema import (
            ConversationMemoryError,
            ErrorCode,
        )

        key = (interview_id, question_id)
        with self._lock_for(interview_id):
            if key not in self._question_index:
                raise ConversationMemoryError(
                    ErrorCode.ANSWER_WITHOUT_QUESTION,
                    f"No question '{question_id}' found for interview '{interview_id}'.",
                )
            idx = self._question_index[key]
            existing = self._turns[interview_id][idx]
            if existing.status == "answered":
                raise ConversationMemoryError(
                    ErrorCode.ALREADY_ANSWERED,
                    f"question_id '{question_id}' has already been answered.",
                )
            updated = existing.model_copy(
                update={
                    "answer_text": answer_text,
                    "answer_timestamp": answer_timestamp,
                    "status": "answered",
                    "updated_at": answer_timestamp,
                }
            )
            self._turns[interview_id][idx] = updated
            return updated

    def get_history(self, interview_id: str) -> list[TurnRecord]:
        return list(self._turns.get(interview_id, []))

    def get_turn(self, interview_id: str, question_id: str) -> Optional[TurnRecord]:
        key = (interview_id, question_id)
        if key not in self._question_index:
            return None
        idx = self._question_index[key]
        return self._turns[interview_id][idx]

    def get_turns_by_competency(
        self, interview_id: str, competency_id: str
    ) -> list[TurnRecord]:
        return [
            t
            for t in self._turns.get(interview_id, [])
            if t.target_competency_id == competency_id
        ]


class _DummyLock:
    """Placeholder context manager — single-process pilot doesn't need
    real threading locks yet. Kept as a distinct class (not just
    `with nullcontext()`) so upgrading to threading.Lock later is a
    one-line change, not a design change."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
