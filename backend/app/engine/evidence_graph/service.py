"""
Public API for Evidence Graph. Deterministic — no ProviderAdapter, no
LLM, no embeddings anywhere in this module.

Depends on Conversation Memory to resolve turn_id -> answer_text for
provenance checking. This is the module's one real cross-module
dependency, and it's read-only (this module never writes to
Conversation Memory).
"""

import datetime
from typing import Optional

from app.engine.evidence_graph.schema import (
    EvidenceEntry,
    EvidenceGraphError,
    ErrorCode,
    Relation,
)
from app.engine.evidence_graph.store import (
    EvidenceGraphStore,
    InMemoryEvidenceGraphStore,
    generate_evidence_id,
)
from app.engine.conversation_memory.service import ConversationMemoryService
from app.engine.shared.validator import is_traceable


class EvidenceGraphService:
    def __init__(
        self,
        store: Optional[EvidenceGraphStore] = None,
        conversation_memory: Optional[ConversationMemoryService] = None,
    ):
        self._store = store or InMemoryEvidenceGraphStore()
        # Conversation Memory is required, not optional in practice —
        # a default is provided only so simple call sites don't need
        # to wire it up manually, matching the pattern already used
        # for module-level convenience functions elsewhere.
        self._conversation_memory = conversation_memory or ConversationMemoryService()

    def add_evidence(
        self,
        interview_id: str,
        competency_id: str,
        turn_id: str,
        evidence_excerpt: str,
        relation: Relation,
        contradicts_evidence_id: Optional[str] = None,
    ) -> EvidenceEntry:
        # AC4/AC5 — contradiction target validation first, cheapest checks first
        if relation == "contradicts":
            if not contradicts_evidence_id:
                raise EvidenceGraphError(
                    ErrorCode.MISSING_CONTRADICTION_TARGET,
                    "relation is 'contradicts' but no contradicts_evidence_id was provided.",
                )
            target = self._store.get_entry(interview_id, contradicts_evidence_id)
            if target is None:
                raise EvidenceGraphError(
                    ErrorCode.CONTRADICTS_TARGET_NOT_FOUND,
                    f"contradicts_evidence_id '{contradicts_evidence_id}' does not exist.",
                )

        # AC3 — turn must exist, resolved via Conversation Memory, not
        # a locally-duplicated copy of turn data.
        turn = self._find_turn(interview_id, turn_id)
        if turn is None:
            raise EvidenceGraphError(
                ErrorCode.TURN_NOT_FOUND,
                f"turn_id '{turn_id}' was not found for interview '{interview_id}'.",
            )

        # AC2 — provenance check reusing the SAME shared validator used
        # by Resume and JD Understanding, not a reimplementation.
        answer_text = turn.answer_text or ""
        if not is_traceable(evidence_excerpt, answer_text):
            raise EvidenceGraphError(
                ErrorCode.EXCERPT_NOT_TRACEABLE,
                "evidence_excerpt could not be verified as an actual substring of the turn's answer_text.",
            )

        entry = EvidenceEntry(
            evidence_id=generate_evidence_id(),  # always generated here, never caller-supplied
            interview_id=interview_id,
            competency_id=competency_id,
            turn_id=turn_id,
            question_id=turn.question_id,
            evidence_excerpt=evidence_excerpt,
            relation=relation,
            contradicts_evidence_id=contradicts_evidence_id,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        return self._store.add_entry(entry)

    def get_evidence_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[EvidenceEntry]:
        entries = self._store.get_evidence_for_competency(interview_id, competency_id)
        return self._order_by_turn_sequence(interview_id, entries)

    def get_evidence_for_turn(
        self, interview_id: str, turn_id: str
    ) -> list[EvidenceEntry]:
        return self._store.get_evidence_for_turn(interview_id, turn_id)

    def has_contradictions(self, interview_id: str, competency_id: str) -> bool:
        entries = self._store.get_evidence_for_competency(interview_id, competency_id)
        return any(e.relation == "contradicts" for e in entries)

    def _find_turn(self, interview_id: str, turn_id: str):
        for turn in self._conversation_memory.get_history(interview_id):
            if turn.turn_id == turn_id:
                return turn
        return None

    def _order_by_turn_sequence(
        self, interview_id: str, entries: list[EvidenceEntry]
    ) -> list[EvidenceEntry]:
        # Ordering derives from Conversation Memory's sequence_number
        # (AC7) — not a separately tracked order in this module.
        history = self._conversation_memory.get_history(interview_id)
        seq_by_turn_id = {t.turn_id: t.sequence_number for t in history}
        return sorted(entries, key=lambda e: seq_by_turn_id.get(e.turn_id, 0))
