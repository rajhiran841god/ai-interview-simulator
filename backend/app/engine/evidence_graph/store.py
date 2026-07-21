"""
EvidenceGraphStore — storage abstraction, same pattern as
ConversationMemoryStore. Small interface, backend swappable later.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from app.engine.evidence_graph.schema import EvidenceEntry
from app.core.supabase_data_client import get_data_client, as_json_dict


class EvidenceGraphStore(ABC):
    @abstractmethod
    def add_entry(self, entry: EvidenceEntry) -> EvidenceEntry:
        raise NotImplementedError

    @abstractmethod
    def get_entry(self, interview_id: str, evidence_id: str) -> Optional[EvidenceEntry]:
        raise NotImplementedError

    @abstractmethod
    def get_evidence_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[EvidenceEntry]:
        raise NotImplementedError

    @abstractmethod
    def get_evidence_for_turn(
        self, interview_id: str, turn_id: str
    ) -> list[EvidenceEntry]:
        raise NotImplementedError


class InMemoryEvidenceGraphStore(EvidenceGraphStore):
    """
    Pilot-scale implementation. evidence_id is ALWAYS generated here,
    never accepted from a caller — per reviewer's explicit ownership
    guidance, generation is this module's responsibility, not
    something a caller can inject or collide on.

    Duplicate-evidence policy (a conscious decision per reviewer's
    request, not an accident): duplicates ARE allowed. Two add_entry
    calls with identical competency_id/turn_id/excerpt/relation
    produce two distinct evidence_ids, not an error and not silent
    deduplication. Rationale: a candidate could legitimately re-affirm
    the same point in a later answer, and that repetition is itself
    potentially meaningful (e.g. to the Reasoning Engine deciding
    confidence has strengthened) — silently collapsing it would lose
    information. If this turns out to be wrong for the pilot, it's a
    one-line change here, not a schema change.
    """

    def __init__(self):
        self._entries: dict[str, list[EvidenceEntry]] = {}  # interview_id -> entries
        self._by_id: dict[tuple[str, str], EvidenceEntry] = (
            {}
        )  # (interview_id, evidence_id)

    def add_entry(self, entry: EvidenceEntry) -> EvidenceEntry:
        self._entries.setdefault(entry.interview_id, [])
        self._entries[entry.interview_id].append(entry)
        self._by_id[(entry.interview_id, entry.evidence_id)] = entry
        return entry

    def get_entry(self, interview_id: str, evidence_id: str) -> Optional[EvidenceEntry]:
        return self._by_id.get((interview_id, evidence_id))

    def get_evidence_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[EvidenceEntry]:
        return [
            e
            for e in self._entries.get(interview_id, [])
            if e.competency_id == competency_id
        ]

    def get_evidence_for_turn(
        self, interview_id: str, turn_id: str
    ) -> list[EvidenceEntry]:
        return [e for e in self._entries.get(interview_id, []) if e.turn_id == turn_id]


def generate_evidence_id() -> str:
    return str(uuid.uuid4())


class PostgresEvidenceGraphStore(EvidenceGraphStore):
    """Persistent implementation — see PostgresConversationMemoryStore
    for the full rationale (Decision Log #006, cross-process bug fix)."""

    def __init__(self):
        self._client = get_data_client()

    def add_entry(self, entry: EvidenceEntry) -> EvidenceEntry:
        self._client.table("evidence_entries").insert(
            {
                "evidence_id": entry.evidence_id,
                "interview_id": entry.interview_id,
                "turn_id": entry.turn_id,
                "competency_id": entry.competency_id,
                "data": entry.model_dump(),
            }
        ).execute()
        return entry

    def get_entry(self, interview_id: str, evidence_id: str) -> Optional[EvidenceEntry]:
        result = (
            self._client.table("evidence_entries")
            .select("data")
            .eq("interview_id", interview_id)
            .eq("evidence_id", evidence_id)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None
        return EvidenceEntry(**as_json_dict(result.data, "data"))

    def get_evidence_for_competency(
        self, interview_id: str, competency_id: str
    ) -> list[EvidenceEntry]:
        result = (
            self._client.table("evidence_entries")
            .select("data")
            .eq("interview_id", interview_id)
            .eq("competency_id", competency_id)
            .order("created_at")
            .execute()
        )
        return [EvidenceEntry(**as_json_dict(row, "data")) for row in result.data]

    def get_evidence_for_turn(
        self, interview_id: str, turn_id: str
    ) -> list[EvidenceEntry]:
        result = (
            self._client.table("evidence_entries")
            .select("data")
            .eq("interview_id", interview_id)
            .eq("turn_id", turn_id)
            .order("created_at")
            .execute()
        )
        return [EvidenceEntry(**as_json_dict(row, "data")) for row in result.data]
