"""
Competency Model storage + update algorithm. The update math itself
lives here — the "algorithm as code" that must match
Competency_Model_Contract.md's documented formulas exactly.
"""

import datetime
from abc import ABC, abstractmethod
from typing import Optional

from app.engine.competency_model.schema import (
    CompetencyState,
    CompetencySeed,
    CompetencyModelError,
    ErrorCode,
)
from app.shared.reasoning_config import CONTRADICTION_PENALTY
from app.core.supabase_data_client import get_data_client, as_json_dict


class CompetencyModelStore(ABC):
    @abstractmethod
    def initialize(
        self, interview_id: str, seeds: list[CompetencySeed]
    ) -> list[CompetencyState]:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        interview_id: str,
        competency_id: str,
        confidence_contribution: float,
        contradiction_detected: bool,
        evidence_ids_created: list[str],
    ) -> CompetencyState:
        raise NotImplementedError

    @abstractmethod
    def get_state(
        self, interview_id: str, competency_id: str
    ) -> Optional[CompetencyState]:
        raise NotImplementedError

    @abstractmethod
    def get_all_states(self, interview_id: str) -> list[CompetencyState]:
        raise NotImplementedError


class InMemoryCompetencyModelStore(CompetencyModelStore):
    def __init__(self):
        self._states: dict[str, dict[str, CompetencyState]] = (
            {}
        )  # interview_id -> competency_id -> state
        self._initialized_interviews: set[str] = set()

    def initialize(
        self, interview_id: str, seeds: list[CompetencySeed]
    ) -> list[CompetencyState]:
        if interview_id in self._initialized_interviews:
            raise CompetencyModelError(
                ErrorCode.DUPLICATE_INITIALIZATION,
                f"Interview '{interview_id}' has already been initialized.",
            )
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        states = {}
        for seed in seeds:
            states[seed.competency_id] = CompetencyState(
                interview_id=interview_id,
                competency_id=seed.competency_id,
                emphasis=seed.emphasis,
                evidence_count=0,
                positive_evidence=[],
                contradictory_evidence=[],
                confidence=0.0,
                last_updated=now,
            )
        self._states[interview_id] = states
        self._initialized_interviews.add(interview_id)
        return list(states.values())

    def update(
        self,
        interview_id: str,
        competency_id: str,
        confidence_contribution: float,
        contradiction_detected: bool,
        evidence_ids_created: list[str],
    ) -> CompetencyState:
        interview_states = self._states.get(interview_id, {})
        if competency_id not in interview_states:
            raise CompetencyModelError(
                ErrorCode.COMPETENCY_NOT_INITIALIZED,
                f"Competency '{competency_id}' was never initialized for interview '{interview_id}'.",
            )

        current = interview_states[competency_id]
        new_evidence_count = current.evidence_count + len(evidence_ids_created)

        if contradiction_detected:
            new_confidence = max(0.0, current.confidence - CONTRADICTION_PENALTY)
            new_contradictory = current.contradictory_evidence + evidence_ids_created
            new_positive = current.positive_evidence
        else:
            # Incremental mean, exactly as documented in the contract:
            # new_confidence = old + (contribution - old) / evidence_count
            # Guard against division by zero if evidence_ids_created is
            # empty (e.g. a non-answer with no evidence extracted) —
            # in that case there's nothing to average in, confidence
            # is unchanged.
            if new_evidence_count > 0 and len(evidence_ids_created) > 0:
                new_confidence = (
                    current.confidence
                    + (confidence_contribution - current.confidence)
                    / new_evidence_count
                )
            else:
                new_confidence = current.confidence
            new_positive = current.positive_evidence + evidence_ids_created
            new_contradictory = current.contradictory_evidence

        updated = current.model_copy(
            update={
                "evidence_count": new_evidence_count,
                "positive_evidence": new_positive,
                "contradictory_evidence": new_contradictory,
                "confidence": new_confidence,
                "last_updated": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
        )
        interview_states[competency_id] = updated
        return updated

    def get_state(
        self, interview_id: str, competency_id: str
    ) -> Optional[CompetencyState]:
        return self._states.get(interview_id, {}).get(competency_id)

    def get_all_states(self, interview_id: str) -> list[CompetencyState]:
        return list(self._states.get(interview_id, {}).values())


class PostgresCompetencyModelStore(CompetencyModelStore):
    """
    Persistent implementation — see PostgresConversationMemoryStore for
    the full rationale (Decision Log #006, cross-process bug fix).
    Update algorithm copied EXACTLY from InMemoryCompetencyModelStore
    (same incremental-mean/contradiction-penalty formulas, verified
    against Competency_Model_Contract.md) — only the storage read/write
    mechanism differs.
    """

    def __init__(self):
        self._client = get_data_client()

    def initialize(
        self, interview_id: str, seeds: list[CompetencySeed]
    ) -> list[CompetencyState]:
        existing = self.get_all_states(interview_id)
        if existing:
            raise CompetencyModelError(
                ErrorCode.DUPLICATE_INITIALIZATION,
                f"Interview '{interview_id}' has already been initialized.",
            )
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        states = []
        for seed in seeds:
            state = CompetencyState(
                interview_id=interview_id,
                competency_id=seed.competency_id,
                emphasis=seed.emphasis,
                evidence_count=0,
                positive_evidence=[],
                contradictory_evidence=[],
                confidence=0.0,
                last_updated=now,
            )
            self._client.table("competency_states").insert(
                {
                    "interview_id": interview_id,
                    "competency_id": seed.competency_id,
                    "data": state.model_dump(),
                }
            ).execute()
            states.append(state)
        return states

    def update(
        self,
        interview_id: str,
        competency_id: str,
        confidence_contribution: float,
        contradiction_detected: bool,
        evidence_ids_created: list[str],
    ) -> CompetencyState:
        current = self.get_state(interview_id, competency_id)
        if current is None:
            raise CompetencyModelError(
                ErrorCode.COMPETENCY_NOT_INITIALIZED,
                f"Competency '{competency_id}' was never initialized for interview '{interview_id}'.",
            )

        # Exact same formula as InMemoryCompetencyModelStore.update() —
        # see that method's comments for the full contract reference.
        new_evidence_count = current.evidence_count + len(evidence_ids_created)

        if contradiction_detected:
            new_confidence = max(0.0, current.confidence - CONTRADICTION_PENALTY)
            new_contradictory = current.contradictory_evidence + evidence_ids_created
            new_positive = current.positive_evidence
        else:
            if new_evidence_count > 0 and len(evidence_ids_created) > 0:
                new_confidence = (
                    current.confidence
                    + (confidence_contribution - current.confidence)
                    / new_evidence_count
                )
            else:
                new_confidence = current.confidence
            new_positive = current.positive_evidence + evidence_ids_created
            new_contradictory = current.contradictory_evidence

        updated = current.model_copy(
            update={
                "evidence_count": new_evidence_count,
                "positive_evidence": new_positive,
                "contradictory_evidence": new_contradictory,
                "confidence": new_confidence,
                "last_updated": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
        )
        self._client.table("competency_states").update(
            {"data": updated.model_dump()}
        ).eq("interview_id", interview_id).eq("competency_id", competency_id).execute()
        return updated

    def get_state(
        self, interview_id: str, competency_id: str
    ) -> Optional[CompetencyState]:
        result = (
            self._client.table("competency_states")
            .select("data")
            .eq("interview_id", interview_id)
            .eq("competency_id", competency_id)
            .maybe_single()
            .execute()
        )
        if result is None or not result.data:
            return None
        return CompetencyState(**as_json_dict(result.data, "data"))

    def get_all_states(self, interview_id: str) -> list[CompetencyState]:
        result = (
            self._client.table("competency_states")
            .select("data")
            .eq("interview_id", interview_id)
            .execute()
        )
        return [CompetencyState(**as_json_dict(row, "data")) for row in result.data]
